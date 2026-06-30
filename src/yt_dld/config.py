"""Persistent user configuration stored as TOML.

The config file holds the *defaults* that both the TUI controls and the
headless flag path start from. Location follows the XDG spec:
``$XDG_CONFIG_HOME/ytdld/config.toml`` (``~/.config/ytdld/config.toml``).
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Dict

APP_NAME = "ytdld"

# The full schema. Keys here define what is valid; anything else in a user's
# file is ignored on load. Order is preserved when writing the file back.
DEFAULTS: Dict[str, Any] = {
    "out_dir": "~/Music/Downloads",
    "mode": "mp3",  # mp3 | mp4 | flac
    "quality": "best",  # best | 2160p | 1440p | 1080p | 720p | 480p (mp4 only)
    "threads": 3,
    "archive": False,  # skip already-downloaded items via a download archive
    "cookies_from_browser": "",  # "" = none, else chrome/firefox/brave/edge/safari
    "sponsorblock": "off",  # off | mark | skip
    "embed_thumbnail": True,
    "embed_metadata": True,
    "notify": True,  # desktop notification when a batch finishes
}

MODES = ("mp3", "mp4", "flac")
QUALITIES = ("best", "2160p", "1440p", "1080p", "720p", "480p")
SPONSORBLOCK = ("off", "mark", "skip")
BROWSERS = ("", "chrome", "firefox", "brave", "edge", "safari", "chromium", "opera", "vivaldi")


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(str(Path.home()), ".config")
    return Path(base) / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.toml"


def archive_path() -> Path:
    return config_dir() / "archive.txt"


def load_config() -> Dict[str, Any]:
    """Return defaults overlaid with any values found in the config file."""
    data = dict(DEFAULTS)
    path = config_path()
    if path.exists():
        try:
            with open(path, "rb") as fh:
                user = tomllib.load(fh)
            for key, value in user.items():
                if key in DEFAULTS and isinstance(value, type(DEFAULTS[key])):
                    data[key] = value
        except (OSError, tomllib.TOMLDecodeError):
            pass
    return data


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def save_config(data: Dict[str, Any]) -> Path:
    """Write the config file, restricted to known keys, and return its path."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ytdld configuration",
        "# Edit by hand, or run `ytdld config --edit`. Reset with `ytdld config --reset`.",
        "",
    ]
    for key in DEFAULTS:
        value = data.get(key, DEFAULTS[key])
        lines.append(f"{key} = {_toml_scalar(value)}")
    path.write_text("\n".join(lines) + "\n")
    return path
