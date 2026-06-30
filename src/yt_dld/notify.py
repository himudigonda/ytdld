"""Best-effort desktop notification when a batch finishes.

macOS uses ``osascript``; Linux uses ``notify-send`` if present. Any failure
is swallowed — a missing notifier must never break a download run.
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def _applescript_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def notify(title: str, message: str) -> None:
    try:
        if sys.platform == "darwin":
            script = (
                f"display notification {_applescript_quote(message)} "
                f"with title {_applescript_quote(title)}"
            )
            subprocess.run(
                ["osascript", "-e", script],
                check=False,
                capture_output=True,
            )
        elif shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", title, message],
                check=False,
                capture_output=True,
            )
    except Exception:
        pass
