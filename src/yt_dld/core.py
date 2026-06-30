"""Core download logic — link parsing, option building, and a single
download primitive that reports progress through a callback.

This module is deliberately UI-agnostic: both the Textual TUI and the
headless flag path drive it. Nothing here imports rich or textual.
"""

from __future__ import annotations

import concurrent.futures
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import yt_dlp

# Match a bare 11-char video id from watch URLs, youtu.be short links, embeds,
# shorts, and url-encoded copy-paste. Match playlist ids separately.
_VIDEO_PATTERNS = [
    r"(?:v=|v%3D)([a-zA-Z0-9_-]{11})",
    r"youtu\.be/([a-zA-Z0-9_-]{11})",
    r"youtube\.com/(?:embed|shorts|v)/([a-zA-Z0-9_-]{11})",
]
_LIST_PATTERN = r"(?:list=|list%3D)([a-zA-Z0-9_-]{18,34})"

SPONSOR_CATEGORIES = [
    "sponsor",
    "selfpromo",
    "interaction",
    "intro",
    "outro",
    "preview",
    "music_offtopic",
]


class LinkProcessor:
    @staticmethod
    def sanitize(input_data: str) -> List[str]:
        """Extract every valid video/playlist id from arbitrary text."""
        vids: List[str] = []
        for pattern in _VIDEO_PATTERNS:
            vids.extend(re.findall(pattern, input_data))
        playlists = re.findall(_LIST_PATTERN, input_data)

        clean: List[str] = []
        for p in dict.fromkeys(playlists):
            clean.append(f"https://www.youtube.com/playlist?list={p}")
        for v in dict.fromkeys(vids):
            clean.append(f"https://www.youtube.com/watch?v={v}")
        # De-dupe while preserving order.
        return list(dict.fromkeys(clean))

    @staticmethod
    def _fetch_meta(url: str) -> Optional[Dict]:
        """Fetch title/duration/uploader for a single video (no download)."""
        opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False, process=False)
            if not info:
                return None
            return {
                "title": info.get("title") or url,
                "duration": info.get("duration"),
                "uploader": info.get("uploader") or info.get("channel") or "",
            }
        except Exception:
            return None

    @staticmethod
    def expand_playlists(
        urls: List[str],
        on_progress: Optional[Callable[[int, int], None]] = None,
        enrich: bool = True,
    ) -> List[Dict]:
        """Resolve playlist URLs into individual video entries with metadata.

        Playlist entries get titles for free; standalone videos are enriched
        in parallel so the picker shows real titles, not raw URLs.
        """
        expanded: List[Dict] = []
        flat_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "ignoreerrors": True,
        }
        total = len(urls)
        for index, url in enumerate(urls):
            if on_progress:
                on_progress(index, total)
            if "playlist?list=" not in url:
                expanded.append(
                    {"url": url, "title": url, "duration": None, "uploader": ""}
                )
                continue
            try:
                with yt_dlp.YoutubeDL(flat_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                for entry in (info or {}).get("entries") or []:
                    if not entry:
                        continue
                    vid = entry.get("id")
                    if not vid:
                        continue
                    expanded.append(
                        {
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "title": entry.get("title") or vid,
                            "duration": entry.get("duration"),
                            "uploader": entry.get("uploader")
                            or entry.get("channel")
                            or "",
                        }
                    )
            except Exception:
                expanded.append(
                    {"url": url, "title": url, "duration": None, "uploader": ""}
                )
        if on_progress:
            on_progress(total, total)

        seen = set()
        unique: List[Dict] = []
        for entry in expanded:
            if entry["url"] in seen:
                continue
            seen.add(entry["url"])
            unique.append(entry)

        if enrich:
            todo = [e for e in unique if e["title"] == e["url"]]
            if todo:
                workers = min(8, len(todo))
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                    futures = {
                        ex.submit(LinkProcessor._fetch_meta, e["url"]): e
                        for e in todo
                    }
                    for fut in concurrent.futures.as_completed(futures):
                        meta = fut.result()
                        if meta:
                            futures[fut].update(meta)
        return unique


@dataclass
class DownloadOptions:
    out_dir: Path
    mode: str = "mp3"  # mp3 | mp4 | flac
    quality: str = "best"  # mp4 height cap
    workers: int = 3
    archive: bool = False
    archive_path: Optional[Path] = None
    cookies_from_browser: str = ""
    sponsorblock: str = "off"  # off | mark | skip
    embed_thumbnail: bool = True
    embed_metadata: bool = True

    @classmethod
    def from_config(cls, cfg: Dict, out_dir: Path) -> "DownloadOptions":
        return cls(
            out_dir=out_dir,
            mode=cfg.get("mode", "mp3"),
            quality=cfg.get("quality", "best"),
            workers=int(cfg.get("threads", 3)),
            archive=bool(cfg.get("archive", False)),
            cookies_from_browser=cfg.get("cookies_from_browser", "") or "",
            sponsorblock=cfg.get("sponsorblock", "off"),
            embed_thumbnail=bool(cfg.get("embed_thumbnail", True)),
            embed_metadata=bool(cfg.get("embed_metadata", True)),
        )


@dataclass
class ProgressEvent:
    status: str  # downloading | postprocessing | finished | error
    downloaded: int = 0
    total: Optional[int] = None
    speed: Optional[float] = None
    eta: Optional[int] = None


def _format_string(opts: DownloadOptions) -> str:
    if opts.mode in ("mp3", "flac"):
        return "bestaudio/best"
    if opts.quality == "best":
        return "bestvideo+bestaudio/best"
    height = {
        "2160p": 2160,
        "1440p": 1440,
        "1080p": 1080,
        "720p": 720,
        "480p": 480,
    }.get(opts.quality)
    if not height:
        return "bestvideo+bestaudio/best"
    return (
        f"bestvideo[height<={height}]+bestaudio/"
        f"best[height<={height}]/best"
    )


def _postprocessors(opts: DownloadOptions) -> List[Dict]:
    pps: List[Dict] = []
    if opts.sponsorblock in ("mark", "skip"):
        pps.append(
            {
                "key": "SponsorBlock",
                "categories": SPONSOR_CATEGORIES,
                "when": "after_filter",
            }
        )
    if opts.sponsorblock == "skip":
        pps.append(
            {
                "key": "ModifyChapters",
                "remove_sponsor_segments": SPONSOR_CATEGORIES,
            }
        )
    if opts.mode == "mp3":
        pps.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            }
        )
    elif opts.mode == "flac":
        pps.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "flac",
                "preferredquality": "0",
            }
        )
    if opts.embed_metadata:
        pps.append({"key": "FFmpegMetadata"})
    if opts.embed_thumbnail:
        pps.append({"key": "EmbedThumbnail"})
    return pps


def build_ydl_opts(
    opts: DownloadOptions,
    progress_hook: Optional[Callable[[Dict], None]] = None,
    extra: Optional[Dict] = None,
) -> Dict:
    ydl_opts: Dict = {
        "format": _format_string(opts),
        "outtmpl": str(
            opts.out_dir / "%(uploader,channel|Unknown Uploader)s/%(title)s.%(ext)s"
        ),
        "windowsfilenames": True,
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
        # We render our own progress (TUI / headless); silence yt-dlp's so it
        # never writes to stdout and corrupts the Textual display.
        "noprogress": True,
        "consoletitle": False,
        # Be resilient to flaky networks and transient extractor errors.
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 3,
        "postprocessors": _postprocessors(opts),
    }
    if opts.embed_thumbnail:
        ydl_opts["writethumbnail"] = True
    if opts.mode == "mp4":
        ydl_opts["merge_output_format"] = "mp4"
    if opts.archive and opts.archive_path:
        ydl_opts["download_archive"] = str(opts.archive_path)
    if opts.cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (opts.cookies_from_browser,)
    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]
    if extra:
        ydl_opts.update(extra)
    return ydl_opts


def download_entry(
    entry: Dict,
    opts: DownloadOptions,
    on_event: Optional[Callable[[ProgressEvent], None]] = None,
) -> Tuple[bool, Optional[str]]:
    """Download a single entry. Returns (ok, error_message)."""
    url = entry["url"]

    def hook(d: Dict) -> None:
        if not on_event:
            return
        status = d.get("status")
        if status == "downloading":
            on_event(
                ProgressEvent(
                    "downloading",
                    downloaded=d.get("downloaded_bytes") or 0,
                    total=d.get("total_bytes") or d.get("total_bytes_estimate"),
                    speed=d.get("speed"),
                    eta=d.get("eta"),
                )
            )
        elif status == "finished":
            on_event(ProgressEvent("postprocessing"))

    ydl_opts = build_ydl_opts(opts, progress_hook=hook)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            retcode = ydl.download([url])
        if retcode == 0:
            if on_event:
                on_event(ProgressEvent("finished"))
            return True, None
        if on_event:
            on_event(ProgressEvent("error"))
        return False, "download failed"
    except Exception as exc:  # noqa: BLE001 — surface any yt-dlp error to caller
        if on_event:
            on_event(ProgressEvent("error"))
        return False, str(exc)
