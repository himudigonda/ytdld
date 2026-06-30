"""`ytdld update` — self-update via uv.

Upgrades the installed tool (which pulls a fresh yt-dlp as a dependency).
"""

from __future__ import annotations

import shutil
import subprocess


def run_update() -> int:
    from rich.console import Console

    console = Console()
    if not shutil.which("uv"):
        console.print(
            "[red]uv not found.[/red] ytdld self-update requires uv.\n"
            "Install it: [cyan]curl -LsSf https://astral.sh/uv/install.sh | sh[/cyan]"
        )
        return 1

    console.print("[cyan]Upgrading ytdld via uv…[/cyan]")
    result = subprocess.run(["uv", "tool", "upgrade", "ytdld"], check=False)
    if result.returncode == 0:
        console.print("[green]ytdld is up to date.[/green]")
    else:
        console.print(
            "[yellow]Upgrade command exited non-zero.[/yellow] "
            "If ytdld was installed another way, update it the same way."
        )
    return result.returncode
