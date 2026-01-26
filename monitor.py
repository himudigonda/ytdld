import time
import os
from pathlib import Path
from collections import Counter
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.panel import Panel
from rich.align import Align

ROOT_DIR = Path(os.path.expanduser("~/Music"))

def get_counts():
    """Scans the music directory and counts MP3s per folder."""
    # We look for files like: ~/Music/Genre/Artist/Song.mp3
    # We want to group by 'Artist' (the parent folder of the file)
    artist_counts = Counter()
    total_files = 0
    
    # Fast recursive glob
    for mp3 in ROOT_DIR.rglob("*.mp3"):
        # parent.name is the Artist folder name
        artist_counts[mp3.parent.name] += 1
        total_files += 1
        
    return artist_counts, total_files

def generate_dashboard():
    counts, total = get_counts()
    
    # 1. Main Table
    table = Table(title=f"🎧 LIBRARY MONITOR (Total: [bold green]{total}[/])", expand=True, border_style="cyan")
    table.add_column("Artist", style="bold white")
    table.add_column("Count", justify="right", style="magenta")
    table.add_column("Status", justify="center")

    # Sort by count (highest first)
    for artist, count in counts.most_common():
        # Simple heuristic for status bar
        if count >= 60:
            bar = "[green]██████████[/] (MAX)"
        else:
            # Draw a mini bar chart
            filled = int((count / 60) * 10)
            bar = f"[blue]{'█' * filled}{'░' * (10 - filled)}[/]"
            
        table.add_row(artist, str(count), bar)

    return Panel(
        Align.center(table),
        title="[bold yellow]Real-time Ingestion Stats[/]",
        border_style="blue",
        padding=(1, 2)
    )

if __name__ == "__main__":
    console = Console()
    console.print("[dim]Starting telemetry link...[/dim]")
    
    # refresh_per_second=4 gives a smooth 4fps update without eating CPU
    try:
        with Live(generate_dashboard(), refresh_per_second=2) as live:
            while True:
                time.sleep(1)
                live.update(generate_dashboard())
    except KeyboardInterrupt:
        print("\n👋 Monitor closed.")
