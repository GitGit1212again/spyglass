#!/bin/bash
# Starts Spyglass on a Mac (also works on Linux). It closes itself when the browser page closes.
#
# First time only, in Terminal:   chmod +x Run-Spyglass.command
# Then double-click this file in Finder, or run:   ./Run-Spyglass.command
# (If macOS says the file is from an unidentified developer: right-click it, choose Open, then Open.)
cd "$(dirname "$0")" || exit 1

pause_then_exit() {
  echo
  read -r -n 1 -s -p "Press any key to close this window. "
  echo
  exit "${1:-1}"
}

if [ ! -x ".venv/bin/python" ] || [ ! -f ".venv/.spyglass-ready" ]; then
  # find a Python 3.10 or newer
  PY=""
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PY="$c"
      break
    fi
  done
  if [ -z "$PY" ]; then
    echo "Spyglass needs Python 3.10 or newer, and this Mac does not have it."
    echo "Install it with Homebrew:  brew install python"
    echo "or download it from https://www.python.org/downloads/ and run this again."
    pause_then_exit 1
  fi

  echo "Setting up Spyglass for the first time. This downloads the tools and takes a few minutes."
  if [ ! -x ".venv/bin/python" ]; then
    "$PY" -m venv .venv || { echo "Could not create the private Python folder (.venv)."; pause_then_exit 1; }
  fi
  .venv/bin/python -m pip install --upgrade pip \
    && .venv/bin/python -m pip install -r requirements.txt \
    || { echo; echo "The install did not finish. Check your internet connection, then run this again."; pause_then_exit 1; }
  touch .venv/.spyglass-ready
fi

if ! command -v exiftool >/dev/null 2>&1; then
  echo "Note: ExifTool is not installed, so the photo and file detail tools are switched off."
  echo "      Install it with:  brew install exiftool"
fi

.venv/bin/python server.py --open
status=$?
echo
echo "Spyglass stopped."
exit $status
