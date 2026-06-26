#!/usr/bin/env python3
import argparse
import concurrent.futures
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

try:
    from rich.align import Align
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("rich missing — run: uv tool install ytdld")
    raise SystemExit(1)

import yt_dlp


class LinkProcessor:
    @staticmethod
    def sanitize(input_data: str) -> List[str]:
        vid_pattern = r"(?:v=|v%3D)([a-zA-Z0-9_-]{11})"
        list_pattern = r"(?:list=|list%3D)([a-zA-Z0-9_-]{18,34})"

        vids = re.findall(vid_pattern, input_data)
        playlists = re.findall(list_pattern, input_data)

        clean_links = []
        for p in set(playlists):
            clean_links.append(f"https://www.youtube.com/playlist?list={p}")
        for v in set(vids):
            clean_links.append(f"https://www.youtube.com/watch?v={v}")

        return list(set(clean_links))

    @staticmethod
    def expand_playlists(urls: List[str]) -> List[Dict]:
        expanded: List[Dict] = []
        flat_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "ignoreerrors": True,
        }
        for url in urls:
            if "playlist?list=" not in url:
                expanded.append(
                    {"url": url, "title": url, "duration": None, "uploader": ""}
                )
                continue
            try:
                with yt_dlp.YoutubeDL(flat_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                entries = (info or {}).get("entries") or []
                for e in entries:
                    if not e:
                        continue
                    vid = e.get("id")
                    if not vid:
                        continue
                    expanded.append(
                        {
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "title": e.get("title") or vid,
                            "duration": e.get("duration"),
                            "uploader": e.get("uploader") or e.get("channel") or "",
                        }
                    )
            except Exception:
                expanded.append(
                    {"url": url, "title": url, "duration": None, "uploader": ""}
                )
        seen = set()
        unique: List[Dict] = []
        for e in expanded:
            if e["url"] in seen:
                continue
            seen.add(e["url"])
            unique.append(e)
        return unique


def format_duration(seconds) -> str:
    if not seconds:
        return "  ?:??"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:>3d}:{s:02d}"


def interactive_select(entries: List[Dict]) -> List[Dict]:
    try:
        import questionary
    except ImportError:
        print("--select needs questionary. Run: uv tool install ytdld")
        raise SystemExit(1)

    if not entries:
        return []

    by_url = {e["url"]: e for e in entries}
    choices = []
    for e in entries:
        label = f"{format_duration(e['duration']):>8}  {e['title']}"
        if e["uploader"]:
            label += f"  — {e['uploader']}"
        choices.append(questionary.Choice(title=label, value=e["url"], checked=True))

    selected = questionary.checkbox(
        f"Select tracks ({len(entries)} found, space to toggle, enter to confirm):",
        choices=choices,
    ).ask()
    return [by_url[u] for u in (selected or []) if u in by_url]


@dataclass
class Config:
    root_dir: Path
    mode: str
    workers: int
    input_file: Path = None


class Dashboard:
    def __init__(self, total_tasks):
        self.console = Console()
        self.layout = Layout()
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=10),
        )
        self.layout["footer"].split_row(
            Layout(name="stats", ratio=1), Layout(name="logs", ratio=2)
        )

        self.global_progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(complete_style="green"),
            TextColumn("[bold green]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            expand=True,
        )
        self.global_task = self.global_progress.add_task(
            "Total Progress", total=total_tasks
        )

        self.worker_progress = Progress(
            TextColumn("[bold yellow]{task.description}"),
            BarColumn(style="dim"),
            DownloadColumn(),
            TransferSpeedColumn(),
            expand=True,
        )

        self.stats = {"Downloaded": 0, "Errors": 0, "Active": 0}
        self.log_buffer = []

    def log(self, msg, style="white"):
        self.log_buffer.append(Text(f"• {msg}", style=style))
        if len(self.log_buffer) > 8:
            self.log_buffer.pop(0)

    def update_layout(self):
        self.layout["header"].update(Panel(self.global_progress, border_style="blue"))
        self.layout["body"].update(
            Panel(self.worker_progress, title="Worker Threads", border_style="cyan")
        )

        stats_table = Table.grid(expand=True)
        stats_table.add_row("Success:", f"[green]{self.stats['Downloaded']}")
        stats_table.add_row("Errors:", f"[red]{self.stats['Errors']}")
        stats_table.add_row("Active:", f"[yellow]{self.stats['Active']}")

        self.layout["stats"].update(
            Panel(Align.center(stats_table, vertical="middle"), title="Telemetry")
        )
        self.layout["logs"].update(
            Panel(Text("\n").join(self.log_buffer), title="Events")
        )
        return self.layout


def download_task(entry, config, dash):
    url = entry["url"]
    title = (entry.get("title") or url)[:60]
    dash.stats["Active"] += 1
    task_id = dash.worker_progress.add_task(
        f"[yellow]⇣ {title}", total=100, visible=True
    )

    def hook(d):
        if d["status"] == "downloading":
            dash.worker_progress.update(
                task_id,
                visible=True,
                description=f"[yellow]⇣ {title}",
                completed=d.get("downloaded_bytes", 0),
                total=d.get("total_bytes") or d.get("total_bytes_estimate"),
            )
        elif d["status"] == "finished":
            dash.worker_progress.update(task_id, description=f"[cyan]⚙ {title}")

    ydl_opts = {
        "format": (
            "bestvideo+bestaudio/best" if config.mode == "mp4" else "bestaudio/best"
        ),
        "outtmpl": str(config.root_dir / "%(uploader)s/%(title)s.%(ext)s"),
        "windowsfilenames": True,
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }

    if config.mode == "mp3":
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            },
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ]
    else:
        ydl_opts["postprocessors"] = [
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        dash.log(f"Finished: {title[:40]}", "green")
        dash.stats["Downloaded"] += 1
        dash.worker_progress.update(
            task_id,
            description=f"[green]✓ {title}",
            completed=100,
            total=100,
        )
    except Exception as e:
        dash.log(f"Error: {str(e)[:30]}", "bold red")
        dash.stats["Errors"] += 1
        dash.worker_progress.update(
            task_id,
            description=f"[red]✗ {title}",
            completed=0,
            total=100,
        )
    finally:
        dash.stats["Active"] -= 1
        dash.global_progress.advance(dash.global_task)


def main():
    parser = argparse.ArgumentParser(
        description="edm — parallel YouTube → MP3/MP4 downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  edm -i links.txt
  edm -i links.txt --mode mp4 --threads 6
  edm -i links.txt --select            # interactive picker before downloading
        """,
    )
    parser.add_argument("--input", "-i", required=True, help="text file of URLs")
    parser.add_argument(
        "--out",
        "-o",
        default="~/Music/Downloads",
        help="output directory (default: ~/Music/Downloads)",
    )
    parser.add_argument(
        "--mode",
        choices=["mp3", "mp4"],
        default="mp3",
        help="output format (default: mp3)",
    )
    parser.add_argument(
        "--threads", type=int, default=3, help="parallel workers (default: 3)"
    )
    parser.add_argument(
        "--select",
        action="store_true",
        help="interactive checkbox picker before downloading",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: file not found: {args.input}")
        raise SystemExit(1)

    root_dir = Path(os.path.expanduser(args.out))
    root_dir.mkdir(parents=True, exist_ok=True)

    with open(input_path) as f:
        raw_content = f.read()

    links = LinkProcessor.sanitize(raw_content)
    print(f"Resolving {len(links)} URL(s) into tracks...")
    entries = LinkProcessor.expand_playlists(links)

    if args.select:
        entries = interactive_select(entries)
        if not entries:
            print("No tracks selected.")
            return

    if not entries:
        print("No tracks found in input file.")
        return

    config = Config(root_dir=root_dir, mode=args.mode, workers=args.threads)
    dash = Dashboard(len(entries))

    with Live(dash.update_layout(), refresh_per_second=4, screen=True) as live:
        dash.log(f"Loaded {len(entries)} tracks from {input_path.name}")
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.workers
        ) as executor:
            futures = [executor.submit(download_task, e, config, dash) for e in entries]
            while any(f.running() for f in futures):
                live.update(dash.update_layout())
                time.sleep(0.2)

    print(f"\nDone. Files saved to: {root_dir}")


if __name__ == "__main__":
    main()
