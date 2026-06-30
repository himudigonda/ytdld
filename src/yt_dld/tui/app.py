"""The ytdld interactive TUI, built on Textual.

Three screens:
  * ConfigScreen   — paste/load links and set every option as a control
  * SelectScreen   — checkbox list to trim the resolved track list
  * ProgressScreen — live per-track dashboard while downloading

Network work (resolving playlists, downloading) runs in worker threads and
pushes updates back to the UI thread via ``call_from_thread``.
"""

from __future__ import annotations

import concurrent.futures
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    ProgressBar,
    RichLog,
    Select,
    SelectionList,
    Static,
    Switch,
    TextArea,
)
from textual.widgets.selection_list import Selection

from .. import __version__, config as cfgmod
from ..core import DownloadOptions, LinkProcessor, ProgressEvent, download_entry
from ..notify import notify


def read_clipboard() -> str:
    """Best-effort clipboard read across platforms."""
    candidates = [
        ["pbpaste"],
        ["wl-paste"],
        ["xclip", "-selection", "clipboard", "-o"],
        ["xsel", "--clipboard", "--output"],
    ]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            try:
                out = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if out.returncode == 0:
                    return out.stdout
            except Exception:
                pass
    return ""


def fmt_duration(seconds) -> str:
    if not seconds:
        return "?:??"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_size(num: Optional[float]) -> str:
    if not num:
        return ""
    for unit in ("B", "K", "M", "G", "T"):
        if num < 1024:
            return f"{num:.0f}{unit}"
        num /= 1024
    return f"{num:.0f}P"


def mini_bar(pct: float, width: int = 12) -> str:
    filled = int(round(pct / 100 * width))
    return "█" * filled + "░" * (width - filled)


class _Cancelled(Exception):
    """Raised inside a progress hook to abort an in-flight download."""


class LoadingScreen(Screen):
    """Full-screen spinner shown while playlists resolve."""

    def __init__(self, message: str = "Working…"):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="loading-box"):
            yield Static(self._message, id="loading-msg")
            yield LoadingIndicator()

    def set_message(self, message: str) -> None:
        self.query_one("#loading-msg", Static).update(message)


class ConfigScreen(Screen):
    """Compose a batch: links on the left, every option as a control on the right."""

    BINDINGS = [
        ("ctrl+d", "download", "Download all"),
        ("ctrl+r", "resolve", "Resolve & pick"),
        ("ctrl+l", "clear", "Clear links"),
    ]

    def compose(self) -> ComposeResult:
        cfg = self.app.cfg
        yield Header(show_clock=True)
        with Horizontal(id="main-row"):
            with Vertical(id="links-pane"):
                yield Label("[b]Paste YouTube links[/b]  [dim](any format — playlists, youtu.be, messy copy-paste)[/dim]")
                yield TextArea(id="links", language=None)
                with Horizontal(id="links-actions"):
                    yield Input(placeholder="path/to/links.txt", id="filepath")
                    yield Button("Load file", id="load-file")
                    yield Button("Paste clipboard", id="paste-clip")
                    yield Button("Clear", id="clear-links", variant="warning")
            with VerticalScroll(id="opts-pane"):
                yield Label("[b]Output folder[/b]")
                yield Input(value=cfg["out_dir"], id="out")

                yield Label("[b]Format[/b]")
                yield Select(
                    [("MP3  (audio)", "mp3"), ("MP4  (video)", "mp4"), ("FLAC (lossless)", "flac")],
                    value=cfg["mode"],
                    allow_blank=False,
                    id="mode",
                )
                yield Label("[b]Quality[/b]  [dim](MP4 only)[/dim]")
                yield Select(
                    [(q, q) for q in cfgmod.QUALITIES],
                    value=cfg["quality"],
                    allow_blank=False,
                    id="quality",
                )
                yield Label("[b]Parallel threads[/b]")
                yield Select(
                    [(str(n), str(n)) for n in range(1, 9)],
                    value=str(cfg["threads"]),
                    allow_blank=False,
                    id="threads",
                )
                yield Label("[b]SponsorBlock[/b]")
                yield Select(
                    [("off", "off"), ("mark chapters", "mark"), ("skip segments", "skip")],
                    value=cfg["sponsorblock"],
                    allow_blank=False,
                    id="sponsorblock",
                )
                yield Label("[b]Cookies from browser[/b]  [dim](for age-gated)[/dim]")
                yield Select(
                    [("none" if b == "" else b, b) for b in cfgmod.BROWSERS],
                    value=cfg["cookies_from_browser"],
                    allow_blank=False,
                    id="cookies",
                )
                with Horizontal(classes="toggle-row"):
                    yield Switch(value=cfg["archive"], id="archive")
                    yield Label("Skip already-downloaded (archive)")
                with Horizontal(classes="toggle-row"):
                    yield Switch(value=cfg["embed_thumbnail"], id="thumbnail")
                    yield Label("Embed thumbnail / cover art")
                with Horizontal(classes="toggle-row"):
                    yield Switch(value=cfg["embed_metadata"], id="metadata")
                    yield Label("Embed metadata")
                with Horizontal(classes="toggle-row"):
                    yield Switch(value=cfg["notify"], id="notify")
                    yield Label("Notify when finished")
        with Horizontal(id="footer-actions"):
            yield Button("⬇  Download all", id="download", variant="success")
            yield Button("☑  Resolve & pick", id="resolve", variant="primary")
            yield Button("Quit", id="quit", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "ytdld"
        self.sub_title = f"v{__version__}"
        self._sync_quality_enabled()

    def _sync_quality_enabled(self) -> None:
        mode = self.query_one("#mode", Select).value
        self.query_one("#quality", Select).disabled = mode != "mp4"

    @on(Select.Changed, "#mode")
    def _mode_changed(self) -> None:
        self._sync_quality_enabled()

    @on(Button.Pressed, "#quit")
    def _quit(self) -> None:
        self.app.exit()

    @on(Button.Pressed, "#clear-links")
    def action_clear(self) -> None:
        self.query_one("#links", TextArea).text = ""

    @on(Button.Pressed, "#load-file")
    def _load_file(self) -> None:
        path = self.query_one("#filepath", Input).value.strip()
        if not path:
            self.app.bell()
            return
        p = Path(os.path.expanduser(path))
        if not p.exists():
            self.notify(f"File not found: {p}", severity="error")
            return
        self.query_one("#links", TextArea).text = p.read_text()
        self.notify(f"Loaded {p.name}")

    @on(Button.Pressed, "#paste-clip")
    def _paste_clip(self) -> None:
        text = read_clipboard()
        if not text:
            self.notify("Clipboard empty or unavailable", severity="warning")
            return
        area = self.query_one("#links", TextArea)
        area.text = (area.text + "\n" + text).strip()
        self.notify("Pasted from clipboard")

    def _build_options(self) -> DownloadOptions:
        out = self.query_one("#out", Input).value.strip() or "~/Music/Downloads"
        out_dir = Path(os.path.expanduser(out))
        archive_on = self.query_one("#archive", Switch).value
        return DownloadOptions(
            out_dir=out_dir,
            mode=self.query_one("#mode", Select).value,
            quality=self.query_one("#quality", Select).value,
            workers=int(self.query_one("#threads", Select).value),
            archive=archive_on,
            archive_path=cfgmod.archive_path() if archive_on else None,
            cookies_from_browser=self.query_one("#cookies", Select).value or "",
            sponsorblock=self.query_one("#sponsorblock", Select).value,
            embed_thumbnail=self.query_one("#thumbnail", Switch).value,
            embed_metadata=self.query_one("#metadata", Switch).value,
        )

    def _persist(self, opts: DownloadOptions) -> None:
        cfg = dict(self.app.cfg)
        cfg.update(
            out_dir=self.query_one("#out", Input).value.strip() or cfg["out_dir"],
            mode=opts.mode,
            quality=opts.quality,
            threads=opts.workers,
            archive=opts.archive,
            cookies_from_browser=opts.cookies_from_browser,
            sponsorblock=opts.sponsorblock,
            embed_thumbnail=opts.embed_thumbnail,
            embed_metadata=opts.embed_metadata,
            notify=self.query_one("#notify", Switch).value,
        )
        self.app.cfg = cfg
        try:
            cfgmod.save_config(cfg)
        except Exception:
            pass

    def _raw_links(self) -> str:
        return self.query_one("#links", TextArea).text

    @on(Button.Pressed, "#download")
    def action_download(self) -> None:
        self._start(go_to_select=False)

    @on(Button.Pressed, "#resolve")
    def action_resolve(self) -> None:
        self._start(go_to_select=True)

    def _start(self, go_to_select: bool) -> None:
        raw = self._raw_links()
        links = LinkProcessor.sanitize(raw)
        if not links:
            self.notify("No valid YouTube links found", severity="error")
            return
        opts = self._build_options()
        self._persist(opts)
        do_notify = self.query_one("#notify", Switch).value
        try:
            opts.out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self.notify(f"Cannot create output dir: {exc}", severity="error")
            return
        loading = LoadingScreen(f"Resolving {len(links)} link(s)…")
        self.app.push_screen(loading)
        self._resolve_worker(links, opts, go_to_select, do_notify, loading)

    @work(thread=True, exclusive=True)
    def _resolve_worker(self, links, opts, go_to_select, do_notify, loading) -> None:
        def progress(done, total):
            self.app.call_from_thread(
                loading.set_message, f"Resolving playlists… {done}/{total}"
            )

        entries = LinkProcessor.expand_playlists(links, on_progress=progress)

        def finish():
            self.app.pop_screen()  # remove the loading screen
            if not entries:
                self.notify("Nothing to download", severity="warning")
                return
            if go_to_select:
                self.app.push_screen(SelectScreen(entries, opts, do_notify))
            else:
                self.app.push_screen(ProgressScreen(entries, opts, do_notify))

        self.app.call_from_thread(finish)


class SelectScreen(Screen):
    """Trim the resolved track list before downloading."""

    BINDINGS = [
        ("ctrl+d", "download", "Download selected"),
        ("escape", "back", "Back"),
    ]

    def __init__(self, entries: List[Dict], opts: DownloadOptions, do_notify: bool):
        super().__init__()
        self.entries = entries
        self.opts = opts
        self.do_notify = do_notify

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(
            f"[b]{len(self.entries)} tracks[/b]  "
            "[dim]space to toggle · a all · n none · ctrl+d download[/dim]",
            id="select-head",
        )
        selections = []
        for i, e in enumerate(self.entries):
            dur = fmt_duration(e.get("duration"))
            up = f"  — {e['uploader']}" if e.get("uploader") else ""
            label = f"{dur:>7}  {e.get('title') or e['url']}{up}"
            selections.append(Selection(label, i, True))
        yield SelectionList(*selections, id="tracks")
        with Horizontal(id="footer-actions"):
            yield Button("⬇  Download selected", id="download", variant="success")
            yield Button("All", id="all")
            yield Button("None", id="none")
            yield Button("Back", id="back", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "ytdld — select"
        self.query_one("#tracks", SelectionList).focus()

    @on(Button.Pressed, "#all")
    def _all(self) -> None:
        self.query_one("#tracks", SelectionList).select_all()

    @on(Button.Pressed, "#none")
    def _none(self) -> None:
        self.query_one("#tracks", SelectionList).deselect_all()

    @on(Button.Pressed, "#back")
    def action_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#download")
    def action_download(self) -> None:
        picked = self.query_one("#tracks", SelectionList).selected
        if not picked:
            self.notify("Nothing selected", severity="warning")
            return
        chosen = [self.entries[i] for i in picked]
        self.app.push_screen(ProgressScreen(chosen, self.opts, self.do_notify))


class ProgressScreen(Screen):
    """Live per-track download dashboard."""

    BINDINGS = [
        ("q", "finish", "Quit"),
        ("o", "open_folder", "Open folder"),
        ("r", "retry", "Retry failed"),
    ]

    def __init__(self, entries: List[Dict], opts: DownloadOptions, do_notify: bool):
        super().__init__()
        self.entries = entries
        self.opts = opts
        self.do_notify = do_notify
        self.ok = 0
        self.err = 0
        self.active = 0
        self.done = False
        self.failed: List[int] = []
        self.cancel_event = threading.Event()
        self._last_pct: Dict[int, int] = {}
        self._started = 0.0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="prog-head"):
            yield ProgressBar(total=len(self.entries), show_eta=True, id="total")
            yield Static("", id="stats")
        yield DataTable(id="rows", zebra_stripes=True)
        yield RichLog(id="events", highlight=False, markup=True, max_lines=200)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "ytdld — downloading"
        table = self.query_one("#rows", DataTable)
        table.add_columns("", "Track", "Progress", "Speed")
        for i, e in enumerate(self.entries):
            title = (e.get("title") or e["url"])[:60]
            table.add_row("•", title, mini_bar(0), "", key=str(i))
        self._update_stats()
        self._started = time.monotonic()
        self._run_batch()

    def _update_stats(self) -> None:
        self.query_one("#stats", Static).update(
            f" [green]✓ {self.ok}[/green]  [red]✗ {self.err}[/red]  "
            f"[yellow]⇣ {self.active}[/yellow]  / {len(self.entries)}"
        )

    def _set_row(self, index, icon, pct=None, speed=None) -> None:
        table = self.query_one("#rows", DataTable)
        key = str(index)
        try:
            table.update_cell(key, "", icon)
            if pct is not None:
                table.update_cell(key, "Progress", mini_bar(pct))
            if speed is not None:
                table.update_cell(key, "Speed", speed)
        except Exception:
            pass

    def _log(self, msg) -> None:
        self.query_one("#events", RichLog).write(msg)

    def _on_entry_start(self, index) -> None:
        self.active += 1
        self._set_row(index, "[yellow]⇣[/yellow]")
        self._update_stats()

    def _on_entry_progress(self, index, pct, speed) -> None:
        self._set_row(index, "[yellow]⇣[/yellow]", pct=pct, speed=speed)

    def _on_entry_post(self, index) -> None:
        self._set_row(index, "[cyan]⚙[/cyan]")

    def _on_entry_done(self, index, success, title, err) -> None:
        self.active = max(0, self.active - 1)
        if success:
            self.ok += 1
            self._set_row(index, "[green]✓[/green]", pct=100, speed="")
            self._log(f"[green]✓[/green] {title}")
        else:
            self.err += 1
            self.failed.append(index)
            self._set_row(index, "[red]✗[/red]", speed="")
            self._log(f"[red]✗[/red] {title} [dim]{(err or '')[:50]}[/dim]")
        self.query_one("#total", ProgressBar).advance(1)
        self._update_stats()

    @work(thread=True, exclusive=True)
    def _run_batch(self) -> None:
        app = self.app
        cancel = self.cancel_event

        def one(index: int, entry: Dict):
            if cancel.is_set():
                return
            title = (entry.get("title") or entry["url"])[:60]
            app.call_from_thread(self._on_entry_start, index)
            self._last_pct[index] = 0

            def on_event(ev: ProgressEvent):
                if cancel.is_set():
                    raise _Cancelled()
                if ev.status == "downloading":
                    total = ev.total or 0
                    pct = (ev.downloaded / total * 100) if total else 0
                    last = self._last_pct.get(index, 0)
                    if pct - last >= 1 or pct >= 100:
                        self._last_pct[index] = int(pct)
                        speed = fmt_size(ev.speed) + "/s" if ev.speed else ""
                        app.call_from_thread(
                            self._on_entry_progress, index, pct, speed
                        )
                elif ev.status == "postprocessing":
                    app.call_from_thread(self._on_entry_post, index)

            success, err = download_entry(entry, self.opts, on_event)
            if cancel.is_set():
                return
            app.call_from_thread(self._on_entry_done, index, success, title, err)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.opts.workers
        ) as ex:
            futures = [ex.submit(one, i, e) for i, e in enumerate(self.entries)]
            concurrent.futures.wait(futures)

        if not cancel.is_set():
            app.call_from_thread(self._finish_batch)

    def _finish_batch(self) -> None:
        self.done = True
        elapsed = int(time.monotonic() - self._started)
        m, s = divmod(elapsed, 60)
        when = f"{m}m{s:02d}s" if m else f"{s}s"
        retry_hint = " · [b]r[/b] retry failed" if self.failed else ""
        self._log(
            f"\n[b]Done[/b] — [green]{self.ok} ok[/green], "
            f"[red]{self.err} error(s)[/red] in {when}. "
            f"Press [b]q[/b] to quit · [b]o[/b] to open folder{retry_hint}."
        )
        self.title = "ytdld — done"
        if self.do_notify:
            notify("ytdld", f"{self.ok} downloaded, {self.err} errors ({when})")

    def action_open_folder(self) -> None:
        path = str(self.opts.out_dir)
        try:
            if shutil.which("open"):
                subprocess.run(["open", path], check=False)
            elif shutil.which("xdg-open"):
                subprocess.run(["xdg-open", path], check=False)
        except Exception:
            pass

    def action_retry(self) -> None:
        if not self.done or not self.failed:
            return
        retry_entries = [self.entries[i] for i in self.failed]
        self.app.push_screen(ProgressScreen(retry_entries, self.opts, self.do_notify))

    def action_finish(self) -> None:
        if not self.done:
            # Abort any in-flight downloads before tearing the app down.
            self.cancel_event.set()
        self.app.exit()


class YtdldApp(App):
    CSS = """
    Screen { background: $surface; }

    #main-row { height: 1fr; }
    #links-pane { width: 1fr; padding: 1 2; }
    #opts-pane { width: 46; padding: 1 2; border-left: solid $primary; }
    #links { height: 1fr; border: round $primary; }
    #links-actions { height: auto; margin-top: 1; }
    #links-actions Input { width: 1fr; }
    #links-actions Button { margin-left: 1; }

    #opts-pane Label { margin-top: 1; }
    #opts-pane Select, #opts-pane Input { width: 100%; }
    .toggle-row { height: auto; margin-top: 1; align: left middle; }
    .toggle-row Switch { margin-right: 1; }

    #footer-actions { height: auto; padding: 1 2; align: center middle; }
    #footer-actions Button { margin: 0 1; }

    #prog-head { height: auto; padding: 1 2; }
    #prog-head ProgressBar { width: 1fr; }
    #stats { width: auto; padding-left: 2; content-align: right middle; }
    #rows { height: 1fr; margin: 0 1; }
    #events { height: 10; border: round $primary; margin: 0 1 1 1; }
    #select-head { padding: 1 2; }
    #tracks { height: 1fr; margin: 0 2; border: round $primary; }

    #loading-box { align: center middle; height: 1fr; }
    #loading-msg { text-align: center; width: 100%; margin-bottom: 1; }
    """

    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self.cfg = cfgmod.load_config()

    def on_mount(self) -> None:
        self.push_screen(ConfigScreen())


def run_app() -> int:
    YtdldApp().run()
    return 0
