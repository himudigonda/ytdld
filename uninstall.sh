#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found — edm-pipeline was not installed via uv tool"
  exit 1
fi

uv tool uninstall edm-pipeline
echo "edm uninstalled."
