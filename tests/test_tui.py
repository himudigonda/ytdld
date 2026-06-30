from pathlib import Path

import pytest

import yt_dld.tui.app as appmod
from yt_dld.core import DownloadOptions, ProgressEvent
from yt_dld.tui.app import ConfigScreen, ProgressScreen, SelectScreen, YtdldApp
from textual.widgets import DataTable, Select, SelectionList, TextArea


def _fake_download(entry, opts, on_event):
    on_event(ProgressEvent("downloading", downloaded=50, total=100, speed=2_000_000))
    on_event(ProgressEvent("downloading", downloaded=100, total=100, speed=2_000_000))
    on_event(ProgressEvent("postprocessing"))
    on_event(ProgressEvent("finished"))
    if entry["url"] == "u-fail":
        return False, "boom"
    return True, None


ENTRIES = [
    {"url": "u1", "title": "Track One", "duration": 200, "uploader": "A"},
    {"url": "u2", "title": "Track Two", "duration": 300, "uploader": "B"},
    {"url": "u-fail", "title": "Bad Track", "duration": None, "uploader": ""},
]


@pytest.mark.asyncio
async def test_config_screen_mode_quality_interaction():
    app = YtdldApp()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, ConfigScreen)
        screen.query_one("#links", TextArea)
        mode = screen.query_one("#mode", Select)
        quality = screen.query_one("#quality", Select)
        assert quality.disabled is True
        mode.value = "mp4"
        await pilot.pause()
        assert quality.disabled is False


@pytest.mark.asyncio
async def test_progress_screen_end_to_end(monkeypatch):
    monkeypatch.setattr(appmod, "download_entry", _fake_download)
    app = YtdldApp()
    async with app.run_test() as pilot:
        opts = DownloadOptions(out_dir=Path("/tmp/ytdld-test"), mode="mp3", workers=2)
        screen = ProgressScreen(ENTRIES, opts, do_notify=False)
        await app.push_screen(screen)
        for _ in range(200):
            if screen.done:
                break
            await pilot.pause(0.05)
        assert screen.done
        assert screen.ok == 2
        assert screen.err == 1
        assert screen.query_one("#rows", DataTable).row_count == 3


@pytest.mark.asyncio
async def test_select_screen_preselects_all():
    app = YtdldApp()
    async with app.run_test() as pilot:
        opts = DownloadOptions(out_dir=Path("/tmp/ytdld-test"))
        sel = SelectScreen(ENTRIES, opts, do_notify=False)
        await app.push_screen(sel)
        await pilot.pause()
        assert len(app.screen.query_one("#tracks", SelectionList).selected) == 3


@pytest.mark.asyncio
async def test_resolve_and_download_all_flow(monkeypatch):
    monkeypatch.setattr(appmod, "download_entry", _fake_download)
    monkeypatch.setattr(
        appmod.LinkProcessor,
        "expand_playlists",
        lambda links, on_progress=None, enrich=True: list(ENTRIES),
    )
    app = YtdldApp()
    async with app.run_test() as pilot:
        app.screen.query_one("#links", TextArea).text = "https://youtu.be/aqz-KE-bpKQ"
        app.screen.action_download()  # "Download all" → loading → progress
        for _ in range(200):
            scr = app.screen
            if isinstance(scr, ProgressScreen) and scr.done:
                break
            await pilot.pause(0.05)
        assert isinstance(app.screen, ProgressScreen)
        assert app.screen.ok == 2 and app.screen.err == 1


@pytest.mark.asyncio
async def test_retry_failed_spawns_new_screen(monkeypatch):
    monkeypatch.setattr(appmod, "download_entry", _fake_download)
    app = YtdldApp()
    async with app.run_test() as pilot:
        opts = DownloadOptions(out_dir=Path("/tmp/ytdld-test"), mode="mp3", workers=2)
        screen = ProgressScreen(ENTRIES, opts, do_notify=False)
        await app.push_screen(screen)
        for _ in range(200):
            if screen.done:
                break
            await pilot.pause(0.05)
        assert screen.failed == [2]
        screen.action_retry()
        await pilot.pause()
        assert isinstance(app.screen, ProgressScreen)
        assert app.screen is not screen
        assert len(app.screen.entries) == 1
        assert app.screen.entries[0]["url"] == "u-fail"
