#!/usr/bin/env bash
set -euo pipefail

REPO="himudigonda/edm-pipeline"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

fail() {
  echo "install.sh: $*" >&2
  exit 1
}

# --- ensure uv is available ---
ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi

  echo "uv not found — installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # source the uv env so it's on PATH for the rest of this script
  if [ -f "$HOME/.local/bin/env" ]; then
    # shellcheck disable=SC1091
    . "$HOME/.local/bin/env"
  elif [ -f "$HOME/.cargo/env" ]; then
    # shellcheck disable=SC1091
    . "$HOME/.cargo/env"
  fi

  if ! command -v uv >/dev/null 2>&1; then
    export PATH="$HOME/.local/bin:$PATH"
  fi

  command -v uv >/dev/null 2>&1 || fail "uv install succeeded but uv is still not on PATH — add $HOME/.local/bin to your PATH and re-run"
}

# --- check ffmpeg ---
check_ffmpeg() {
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo ""
    echo "Warning: ffmpeg not found."
    echo "  MP3 conversion and thumbnail embedding require ffmpeg."
    echo "  macOS: brew install ffmpeg"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo ""
  fi
}

main() {
  ensure_uv
  check_ffmpeg

  echo "Installing edm from github.com/${REPO}..."
  uv tool install "edm-pipeline @ git+https://github.com/${REPO}"

  # uv tool installs the shim into ~/.local/bin by default
  EDM_PATH="$(uv tool dir)/../bin/edm"

  echo ""
  echo "Installed: edm"
  if [[ ":$PATH:" != *":${INSTALL_DIR}:"* ]]; then
    echo ""
    echo "Add this to your shell profile (~/.zshrc or ~/.bashrc):"
    echo "  export PATH=\"${INSTALL_DIR}:\$PATH\""
  fi
  echo ""
  echo "Run: edm --help"
}

main "$@"
