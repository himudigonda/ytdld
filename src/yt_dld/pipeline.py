"""Backwards-compatibility shim.

The implementation moved into focused modules (cli/core/config/tui) in v3.0.
This keeps ``yt_dld.pipeline:main`` importable for anything pinned to it.
"""

from .cli import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
