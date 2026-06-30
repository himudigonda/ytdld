"""Command-line entry point.

Verb-first, TUI-by-default. Bare ``ytdld`` (or ``ytdld tui``) opens the
interactive app. A handful of verbs (doctor/update/config) cover maintenance.
Anything else is treated as the headless download fast-path, which keeps the
classic ``-i links.txt --mode mp4`` flags alive for scripting.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import __version__
from . import config as cfgmod

VERBS = {"tui", "doctor", "update", "config", "completions"}

HELP = f"""ytdld {__version__} — interactive YouTube → MP3/MP4/FLAC downloader

usage:
  ytdld                 launch the interactive TUI (default)
  ytdld tui             launch the interactive TUI
  ytdld doctor          check your environment (python, ffmpeg, yt-dlp, PATH)
  ytdld update          self-update via uv
  ytdld config          show config; --edit to open, --reset to restore defaults
  ytdld completions SH  print shell completion (bash|zsh|fish)
  ytdld --version       print version

headless fast-path (for scripts / automation):
  ytdld -i links.txt [options]

  -i, --input PATH         text file of YouTube URLs (required for headless)
  -o, --out DIR            output directory
      --mode {{mp3,mp4,flac}}
      --quality {{best,2160p,1440p,1080p,720p,480p}}   (mp4 only)
      --threads N          parallel workers
      --archive            skip already-downloaded items
      --cookies-from-browser NAME   chrome|firefox|brave|edge|safari|…
      --sponsorblock {{off,mark,skip}}
      --no-thumbnail       do not embed cover art
      --no-metadata        do not embed metadata
      --select             interactive checkbox picker before downloading
      --dry-run            resolve and list tracks without downloading
      --no-notify          suppress the completion notification

Defaults come from {cfgmod.config_path()} (run `ytdld config`).
"""


def launch_tui() -> int:
    try:
        from .tui.app import run_app
    except ImportError as exc:
        print(
            "The TUI requires textual. Install/upgrade with:\n"
            "  uv tool upgrade ytdld\n"
            f"(import error: {exc})",
            file=sys.stderr,
        )
        return 1
    return run_app()


def run_config(argv: list[str]) -> int:
    from rich.console import Console

    console = Console()
    parser = argparse.ArgumentParser(prog="ytdld config", add_help=True)
    parser.add_argument("--edit", action="store_true", help="open the config in $EDITOR")
    parser.add_argument("--reset", action="store_true", help="restore default config")
    parser.add_argument("--path", action="store_true", help="print the config path only")
    args = parser.parse_args(argv)

    path = cfgmod.config_path()

    if args.path:
        print(path)
        return 0

    if args.reset:
        cfgmod.save_config(dict(cfgmod.DEFAULTS))
        console.print(f"[green]Reset config to defaults:[/green] {path}")
        return 0

    if args.edit:
        if not path.exists():
            cfgmod.save_config(cfgmod.load_config())
        editor = os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "vi")
        subprocess.run([editor, str(path)], check=False)
        return 0

    # Default: show current config.
    cfg = cfgmod.load_config()
    console.print(f"[bold cyan]ytdld config[/bold cyan]  [dim]{path}[/dim]")
    if not path.exists():
        console.print("[dim](file does not exist yet — these are the defaults)[/dim]")
    for key in cfgmod.DEFAULTS:
        console.print(f"  {key:>22} = [yellow]{cfg[key]!r}[/yellow]")
    console.print("\nEdit with [cyan]ytdld config --edit[/cyan].")
    return 0


def _build_headless_parser(cfg: dict) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ytdld", add_help=True)
    parser.add_argument("--input", "-i", required=True, help="text file of URLs")
    parser.add_argument("--out", "-o", default=cfg["out_dir"])
    parser.add_argument("--mode", choices=cfgmod.MODES, default=cfg["mode"])
    parser.add_argument("--quality", choices=cfgmod.QUALITIES, default=cfg["quality"])
    parser.add_argument("--threads", type=int, default=cfg["threads"])
    parser.add_argument("--archive", action="store_true", default=cfg["archive"])
    parser.add_argument(
        "--cookies-from-browser",
        dest="cookies_from_browser",
        default=cfg["cookies_from_browser"],
    )
    parser.add_argument(
        "--sponsorblock", choices=cfgmod.SPONSORBLOCK, default=cfg["sponsorblock"]
    )
    parser.add_argument("--no-thumbnail", dest="thumbnail", action="store_false")
    parser.add_argument("--no-metadata", dest="metadata", action="store_false")
    parser.add_argument("--select", action="store_true")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    parser.add_argument("--no-notify", dest="notify", action="store_false")
    parser.set_defaults(
        thumbnail=cfg["embed_thumbnail"],
        metadata=cfg["embed_metadata"],
        notify=cfg["notify"],
    )
    return parser


def run_headless(argv: list[str]) -> int:
    from .core import DownloadOptions
    from .headless import print_dry_run, resolve_entries, run_headless as _run

    cfg = cfgmod.load_config()
    parser = _build_headless_parser(cfg)
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: file not found: {args.input}", file=sys.stderr)
        return 1

    raw = input_path.read_text()

    from rich.console import Console

    console = Console()
    entries = resolve_entries(raw, console=console)

    if args.select:
        from .picker import interactive_select

        entries = interactive_select(entries)

    if not entries:
        console.print("[yellow]No tracks to download.[/yellow]")
        return 0

    if args.dry_run:
        return print_dry_run(entries)

    out_dir = Path(os.path.expanduser(args.out))
    out_dir.mkdir(parents=True, exist_ok=True)

    opts = DownloadOptions(
        out_dir=out_dir,
        mode=args.mode,
        quality=args.quality,
        workers=args.threads,
        archive=args.archive,
        archive_path=cfgmod.archive_path() if args.archive else None,
        cookies_from_browser=args.cookies_from_browser or "",
        sponsorblock=args.sponsorblock,
        embed_thumbnail=args.thumbnail,
        embed_metadata=args.metadata,
    )
    return _run(entries, opts, do_notify=args.notify)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if not argv:
        return launch_tui()

    head = argv[0]

    if head in ("-h", "--help"):
        print(HELP)
        return 0
    if head in ("-V", "--version", "version"):
        print(f"ytdld {__version__}")
        return 0
    if head == "tui":
        return launch_tui()
    if head == "doctor":
        from .doctor import run_doctor

        return run_doctor()
    if head == "update":
        from .update import run_update

        return run_update()
    if head == "config":
        return run_config(argv[1:])
    if head == "completions":
        from .completions import run_completions

        return run_completions(argv[1:])

    # Anything else → headless flag path.
    return run_headless(argv)


if __name__ == "__main__":
    raise SystemExit(main())
