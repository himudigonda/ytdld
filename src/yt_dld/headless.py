"""Headless (flag-driven) runner — the scripting / automation fast-path.

Plain, scrolling, CI-friendly output: a single overall progress bar plus one
line per completed track. The live per-worker dashboard lives in the TUI.
"""

from __future__ import annotations

import concurrent.futures
import os
import time
from pathlib import Path
from typing import Dict, List

from .core import DownloadOptions, LinkProcessor, download_entry
from .notify import notify


def _human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.0f}{unit}" if unit == "B" else f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}PB"


def _human_time(seconds: float) -> str:
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def resolve_entries(raw_text: str, console=None) -> List[Dict]:
    links = LinkProcessor.sanitize(raw_text)
    if console:
        console.print(f"Resolving [bold]{len(links)}[/bold] URL(s) into tracks…")
    return LinkProcessor.expand_playlists(links)


def run_headless(entries: List[Dict], opts: DownloadOptions, do_notify: bool) -> int:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeRemainingColumn,
    )

    console = Console()
    label = opts.mode + (f" {opts.quality}" if opts.mode == "mp4" else "")
    console.print(
        f"Downloading [bold]{len(entries)}[/bold] track(s) "
        f"([cyan]{label}[/cyan], {opts.workers} threads) → {opts.out_dir}"
    )

    started = time.monotonic()
    ok_count = 0
    err_count = 0
    errors: List[str] = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Total"),
        BarColumn(complete_style="green"),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
        task = progress.add_task("total", total=len(entries))
        with concurrent.futures.ThreadPoolExecutor(max_workers=opts.workers) as ex:
            futures = {
                ex.submit(download_entry, e, opts): e for e in entries
            }
            for future in concurrent.futures.as_completed(futures):
                entry = futures[future]
                title = (entry.get("title") or entry["url"])[:55]
                try:
                    success, err = future.result()
                except Exception as exc:  # noqa: BLE001
                    success, err = False, str(exc)
                if success:
                    ok_count += 1
                    progress.console.print(f"  [green]✓[/green] {title}")
                else:
                    err_count += 1
                    errors.append(f"{title}: {err}")
                    progress.console.print(f"  [red]✗[/red] {title} [dim]({err})[/dim]")
                progress.advance(task)

    elapsed = _human_time(time.monotonic() - started)
    console.print(
        f"\n[bold]Done.[/bold] [green]{ok_count} ok[/green], "
        f"[red]{err_count} error(s)[/red] in {elapsed} → {opts.out_dir}"
    )
    if errors and err_count <= 10:
        for line in errors:
            console.print(f"  [dim]{line}[/dim]")

    if do_notify:
        notify("ytdld", f"{ok_count} downloaded, {err_count} errors ({elapsed})")

    return 0 if err_count == 0 else 1


def print_dry_run(entries: List[Dict]) -> int:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    if not entries:
        console.print("[yellow]No tracks found.[/yellow]")
        return 0
    table = Table(title=f"Dry run — {len(entries)} track(s)", title_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Duration", justify="right")
    table.add_column("Title")
    table.add_column("Uploader", style="dim")
    for i, e in enumerate(entries, 1):
        dur = e.get("duration")
        if dur:
            m, s = divmod(int(dur), 60)
            dur_str = f"{m}:{s:02d}"
        else:
            dur_str = "?:??"
        table.add_row(str(i), dur_str, (e.get("title") or e["url"])[:60], e.get("uploader", ""))
    console.print(table)
    return 0
