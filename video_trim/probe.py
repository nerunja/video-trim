"""ffprobe helpers."""
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass


def require_binary(name):
    path = shutil.which(name)
    if not path:
        hint = "brew install ffmpeg" if sys.platform == "darwin" else "sudo apt install ffmpeg"
        raise SystemExit(f"error: '{name}' not found in PATH. Install ffmpeg (e.g. `{hint}`).")
    return path


@dataclass
class VideoInfo:
    duration: float
    width: int
    height: int
    has_audio: bool


def probe(path):
    ffprobe = require_binary("ffprobe")
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise SystemExit(f"error: cannot read '{path}': {out.stderr.strip()}")
    data = json.loads(out.stdout)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise SystemExit(f"error: no video stream in '{path}'")
    w, h = int(video["width"]), int(video["height"])
    # Rotation metadata (common for phone/QuickTime clips): ffmpeg auto-rotates, so swap.
    rot = 0
    for sd in video.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    if abs(rot) % 180 == 90:
        w, h = h, w
    duration = float(data["format"].get("duration") or video.get("duration") or 0)
    has_audio = any(s["codec_type"] == "audio" for s in data["streams"])
    return VideoInfo(duration, w, h, has_audio)
