#!/usr/bin/env bash
# Works on macOS and Linux. Requires python3 and ffmpeg.
set -e
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "ffmpeg missing: brew install ffmpeg | sudo apt install ffmpeg"; exit 1; }
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
echo "Done. Run ./video-trim input.mov -m 2"
