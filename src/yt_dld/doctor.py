"""`ytdld doctor` — environment diagnostics.

Checks the things that actually break downloads: Python version, ffmpeg,
yt-dlp, config/output writability, and whether the install dir is on PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .config import config_path, load_config


def _ffmpeg_version() -> str | None:
    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-version"], capture_output=True, text=True, check=False
        )
        first = out.stdout.splitlines()[0] if out.stdout else ""
        return first or exe
    except Exception:
        return exe


def _ytdlp_version() -> str | None:
    try:
        import yt_dlp

        return getattr(yt_dlp.version, "__version__", "unknown")
    except Exception:
        return None


def run_doctor() -> int:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title=f"ytdld {__version__} — doctor", title_style="bold cyan")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    ok = "[green]✓[/green]"
    warn = "[yellow]![/yellow]"
    bad = "[red]✗[/red]"
    problems = 0

    # Python
    py = sys.version_info
    py_ok = py >= (3, 11)
    table.add_row(
        "Python",
        ok if py_ok else bad,
        f"{py.major}.{py.minor}.{py.micro}" + ("" if py_ok else " (need 3.11+)"),
    )
    problems += 0 if py_ok else 1

    # ffmpeg
    ff = _ffmpeg_version()
    table.add_row(
        "ffmpeg",
        ok if ff else bad,
        ff or "not found — required for audio conversion + thumbnails",
    )
    problems += 0 if ff else 1

    # yt-dlp
    ydl = _ytdlp_version()
    table.add_row(
        "yt-dlp", ok if ydl else bad, ydl or "not importable"
    )
    problems += 0 if ydl else 1

    # config
    cpath = config_path()
    table.add_row(
        "config",
        ok if cpath.exists() else warn,
        str(cpath) if cpath.exists() else f"{cpath} (defaults in use)",
    )

    # output dir
    cfg = load_config()
    out = Path(os.path.expanduser(cfg.get("out_dir", "~/Music/Downloads")))
    writable = False
    try:
        out.mkdir(parents=True, exist_ok=True)
        writable = os.access(out, os.W_OK)
    except Exception:
        writable = False
    table.add_row(
        "output dir",
        ok if writable else bad,
        f"{out}" + ("" if writable else " (not writable)"),
    )
    problems += 0 if writable else 1

    # PATH for the typical uv install location
    local_bin = os.path.join(str(Path.home()), ".local", "bin")
    on_path = local_bin in os.environ.get("PATH", "").split(os.pathsep)
    table.add_row(
        "PATH",
        ok if on_path else warn,
        f"{local_bin} on PATH" if on_path else f"add {local_bin} to PATH",
    )

    console.print(table)
    if problems:
        console.print(f"\n[red]{problems} problem(s) found.[/red] See details above.")
        return 1
    console.print("\n[green]All checks passed.[/green]")
    return 0
