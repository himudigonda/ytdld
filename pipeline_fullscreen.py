#!/usr/bin/env python3
"""
██████╗ ██╗██████╗ ███████╗██╗     ██╗███╗   ██╗███████╗
██╔══██╗██║██╔══██╗██╔════╝██║     ██║████╗  ██║██╔════╝
██████╔╝██║██████╔╝█████╗  ██║     ██║██╔██╗ ██║█████╗  
██╔═══╝ ██║██╔═══╝ ██╔══╝  ██║     ██║██║╚██╗██║██╔══╝  
██║     ██║██║     ███████╗███████╗██║██║ ╚████║███████╗
╚═╝     ╚═╝╚═╝     ╚══════╝╚══════╝╚═╝╚═╝  ╚═══╝╚══════╝

AUDIO INGESTION PIPELINE (FULLSCREEN TUI EDITION)
"""

import argparse
import concurrent.futures
import datetime
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# --- TUI IMPORTS ---
try:
    from rich.progress import (
        Progress, SpinnerColumn, BarColumn, TextColumn, 
        TimeRemainingColumn, DownloadColumn, TransferSpeedColumn
    )
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.console import Console
    from rich.text import Text
    from rich.align import Align
except ImportError:
    print("❌ CRITICAL: 'rich' library missing. Run: uv add rich")
    exit(1)

# ==============================================================================
# 1. THE MANIFEST
# ==============================================================================
SOURCE_MANIFEST = [
    ("Big_Room", "DVBBS", "https://www.youtube.com/playlist?list=PL3Pm4GBeZ8uRXPiAkb39kWA0DX8nhoKUJ"),
    ("Trap", "JackU", "https://www.youtube.com/playlist?list=PLZv6xnm6clDZmoWjn5_CrAXF0pkgkWcNi"),
    ("Big_Room", "Hardwell", "https://www.youtube.com/playlist?list=PL_i8pHQnIHP7QjHSaomS6EL2kF6xIc1se"),
    ("Trap", "NGHTMRE", "https://www.youtube.com/playlist?list=PL0swi7qp01V9V3GZBpQkHwQViFmdIXGBZ"),
    ("Big_Room", "W&W", "https://www.youtube.com/playlist?list=PLDF56FDF8359244D6"),
    ("Dubstep", "Knife_Party", "https://www.youtube.com/playlist?list=PL2_QW5oIQAfNAaQZpqBhGgRq26ejZMZtc"),
    ("Big_Room", "Martin_Garrix", "https://www.youtube.com/playlist?list=PLloICdICtvxriCa432XKmEQ8J_uWW0sCP"),
    ("Trap", "Yellow_Claw", "https://www.youtube.com/playlist?list=PLKJzkJ4iq1UEbmrBYLLTiQWQVZJKhspBF"),
    ("Big_Room", "Dimitri_Vegas_Like_Mike", "https://www.youtube.com/playlist?list=PLGSqXzlm-rLjX48a7qJGbAJOTmuSaoVdh"),
    ("House_Drill", "EU_Drill_Fred_Vibe", "https://www.youtube.com/playlist?list=PLebm-Raf_VV7_VypT85dFPp2QXGTUr0x7"),
    ("Trap", "Trap_City", "https://www.youtube.com/playlist?list=PLU_bQfSFrM2OFFmHoiL2_rVlH3CsLCpxv"),
    ("Trap", "Trap_Nation", "https://www.youtube.com/playlist?list=PLC1og_v3eb4hrv4wsqG1G5dsNZh9bIscJ"),
    ("Big_Room", "Spinnin_Records_Mix", "https://www.youtube.com/playlist?list=PLx_tr69QV8CDEZplKQ3kJGeLQX9CUtKPt"),
    ("Dubstep", "DSG_Dubstep", "https://www.youtube.com/playlist?list=PLfuTShtxY5qn8m-Z872Bo_QhpCg72ekcC"),
    ("Mixes", "Spinnin_Top_100", "https://www.youtube.com/watch?v=9QJRUNwUO04&list=RD9QJRUNwUO04&start_radio=1"),
]

# ==============================================================================
# 2. CONFIGURATION
# ==============================================================================
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

@dataclass
class PipelineConfig:
    root_dir: Path
    workers: int = 3
    max_songs_per_list: int = 60
    sleep_min: int = 20
    sleep_max: int = 50
    audio_quality: str = "0"
    dry_run: bool = False

# ==============================================================================
# 3. DASHBOARD CONTROLLER (FULLSCREEN LAYOUT)
# ==============================================================================
class Dashboard:
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        
        # Define the Fullscreen Grid
        # Header (Top), Body (Middle), Footer (Bottom)
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=12)
        )
        self.layout["footer"].split_row(
            Layout(name="stats", ratio=1),
            Layout(name="logs", ratio=2)
        )

        # 1. Global Progress Bar
        self.global_progress = Progress(
            SpinnerColumn("dots", style="bold cyan"),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None, style="dim white", complete_style="green"),
            TextColumn("[bold green]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            expand=True
        )
        self.global_task_id = self.global_progress.add_task("[bold]Mission Status", total=len(SOURCE_MANIFEST))

        # 2. Worker Progress Bars
        self.worker_progress = Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(style="dim", complete_style="yellow"),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            expand=True
        )

        # 3. Stats Data
        self.stats = {"Downloaded": 0, "Skipped": 0, "Errors": 0, "Active Threads": 0}
        self.log_buffer = []

    def update_stats(self, key, value=1, set_val=False):
        if key in self.stats:
            if set_val:
                self.stats[key] = value
            else:
                self.stats[key] += value
        
    def log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        # Add coloring based on content
        style = "white"
        if "✅" in message: style = "green"
        if "❌" in message: style = "bold red"
        if "⚠️" in message: style = "yellow"
        
        self.log_buffer.append(Text(f"[{timestamp}] {message}", style=style))
        # Keep last 10 lines
        if len(self.log_buffer) > 10:
            self.log_buffer.pop(0)

    def refresh_layout(self):
        # Header
        self.layout["header"].update(
            Panel(self.global_progress, border_style="green", style="on black")
        )
        
        # Body (Workers)
        self.layout["body"].update(
            Panel(
                self.worker_progress, 
                title=f"ACTIVE OPERATIONS (Threads: {self.stats['Active Threads']})", 
                border_style="cyan",
                padding=(1, 2)
            )
        )
        
        # Footer: Stats Table
        stats_table = Table.grid(expand=True, padding=(0, 2))
        stats_table.add_column("Metric", style="bold cyan")
        stats_table.add_column("Value", justify="right", style="bold magenta")
        
        stats_table.add_row("Songs Secured", str(self.stats["Downloaded"]))
        stats_table.add_row("Duplicate/Skip", str(self.stats["Skipped"]))
        stats_table.add_row("Errors", f"[red]{self.stats['Errors']}[/red]")
        
        # Big Stats Panel
        self.layout["stats"].update(
            Panel(
                Align.center(stats_table, vertical="middle"),
                title="TELEMETRY",
                border_style="magenta"
            )
        )

        # Footer: Logs
        log_content = Text("\n").join(self.log_buffer)
        self.layout["logs"].update(
            Panel(log_content, title="EVENT LOG", border_style="white")
        )

        return self.layout

# ==============================================================================
# 4. WORKER ENGINE
# ==============================================================================
class Worker:
    def __init__(self, config: PipelineConfig, dashboard: Dashboard):
        self.cfg = config
        self.dash = dashboard
        self.archive_dir = config.root_dir / "_pipeline" / "archives"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, job_data):
        genre, artist, url = job_data
        agent = random.choice(USER_AGENTS)
        
        self.dash.update_stats("Active Threads", 1)
        task_id = self.dash.worker_progress.add_task(f"[dim]Initializing...[/dim]", total=100, visible=False)
        
        output_path = self.cfg.root_dir / genre / artist
        output_path.mkdir(parents=True, exist_ok=True)
        archive_file = self.archive_dir / f"{genre}_{artist}.txt"
        
        # --- YT-DLP HOOK ---
        def progress_hook(d):
            if d['status'] == 'downloading':
                self.dash.worker_progress.update(task_id, visible=True)
                filename = d.get('filename', '').split('/')[-1][:35] # Truncate for clean UI
                self.dash.worker_progress.update(task_id, description=f"[bold yellow]{artist}[/]: {filename}")
                
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    self.dash.worker_progress.update(task_id, completed=downloaded, total=total)

            elif d['status'] == 'finished':
                self.dash.worker_progress.update(task_id, visible=False)
                self.dash.update_stats("Downloaded")
                self.dash.log(f"✅ {artist}: Track secured.")

        import yt_dlp
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(output_path / "%(title)s.%(ext)s"),
            'ignoreerrors': True,
            'no_warnings': True,
            'quiet': True,
            'download_archive': str(archive_file),
            'user_agent': agent,
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': self.cfg.audio_quality}, 
                               {'key': 'FFmpegMetadata'}, {'key': 'EmbedThumbnail'}],
            'playlistend': self.cfg.max_songs_per_list,
            'match_filter': yt_dlp.utils.match_filter_func("duration > 60"),
            'retries': 10,
            'fragment_retries': 10,
            'progress_hooks': [progress_hook],
        }

        # Jitter Start
        time.sleep(random.randint(1, 8)) 

        if self.cfg.dry_run:
            self.dash.log(f"Simulating: {artist}")
            time.sleep(1) # Fake work
            self.dash.worker_progress.remove_task(task_id)
            self.dash.update_stats("Active Threads", -1)
            self.dash.global_progress.advance(self.dash.global_task_id)
            return

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self.dash.log(f"🎉 Playlist Complete: {artist}")
        except Exception as e:
            self.dash.log(f"❌ Error {artist}: {str(e)[:20]}...")
            self.dash.update_stats("Errors")
        
        self.dash.worker_progress.remove_task(task_id)
        self.dash.update_stats("Active Threads", -1)
        self.dash.global_progress.advance(self.dash.global_task_id)

# ==============================================================================
# 5. MAIN
# ==============================================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="~/Music", help="Root Music Directory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root_path = Path(os.path.expanduser(args.root))
    config = PipelineConfig(root_dir=root_path, dry_run=args.dry_run)
    
    dashboard = Dashboard()
    worker = Worker(config, dashboard)

    # screen=True enables FULLSCREEN mode (alternate buffer)
    with Live(dashboard.refresh_layout(), refresh_per_second=10, screen=True) as live:
        
        dashboard.log("🚀 MISSION CONTROL INITIALIZED")
        dashboard.log(f"📂 Target: {config.root_dir}")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.workers) as executor:
            futures = [executor.submit(worker.execute, job) for job in SOURCE_MANIFEST]
            
            while any(f.running() for f in futures):
                live.update(dashboard.refresh_layout())
                time.sleep(0.1)
            
            concurrent.futures.wait(futures)

    # Playlist Generation (After screen restore)
    print("generating playlists...")
    gen_playlists(config.root_dir)
    print("Done.")

def gen_playlists(root):
    p_dir = root / "_playlists"
    p_dir.mkdir(exist_ok=True)
    all_t = []
    for g_dir in [d for d in root.iterdir() if d.is_dir() and not d.name.startswith("_")]:
        for a_dir in [d for d in g_dir.iterdir() if d.is_dir()]:
            tracks = [str(f.absolute()) for f in a_dir.glob("*.mp3")]
            if tracks:
                all_t.extend(tracks)
                with open(p_dir / f"{g_dir.name}_{a_dir.name}.m3u8", "w") as f:
                    f.write("#EXTM3U\n" + "\n".join(tracks))
    with open(p_dir / "MASTER_LIBRARY.m3u8", "w") as f:
        f.write("#EXTM3U\n" + "\n".join(all_t))

if __name__ == "__main__":
    main()
