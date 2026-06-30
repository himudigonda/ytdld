"""Questionary-based checkbox picker for the headless --select flag.

(The TUI has its own selection screen; this keeps the classic CLI flow.)
"""

from __future__ import annotations

from typing import Dict, List


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
        print("--select needs questionary. Run: uv tool upgrade ytdld")
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
