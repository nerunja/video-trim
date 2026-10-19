"""Detect idle stretches: fully static, or only a small region changing (spinner etc.)."""
import subprocess
from dataclasses import dataclass, asdict

import numpy as np

from .probe import require_binary

AW, AH = 320, 180  # analysis resolution


@dataclass
class Segment:
    start: float
    end: float
    kind: str  # "static" | "busy"
    bbox: list = None  # [x, y, w, h] in source pixels for busy segments

    @property
    def length(self):
        return self.end - self.start

    def to_dict(self):
        return asdict(self)


def analyze(path, fps=10.0, pixel_thresh=12):
    ffmpeg = require_binary("ffmpeg")
    cmd = [ffmpeg, "-v", "error", "-i", str(path), "-an",
           "-vf", f"fps={fps},scale={AW}:{AH},format=gray",
           "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = AW * AH
    prev = None
    fracs, boxes = [], []
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        cur = np.frombuffer(buf, dtype=np.uint8).astype(np.int16)
        if prev is not None:
            mask = (np.abs(cur - prev) > pixel_thresh).reshape(AH, AW)
            n = int(mask.sum())
            fracs.append(n / size)
            if n:
                ys = np.flatnonzero(mask.any(axis=1))
                xs = np.flatnonzero(mask.any(axis=0))
                boxes.append((xs[0], ys[0], xs[-1] + 1, ys[-1] + 1))
            else:
                boxes.append(None)
        prev = cur
    proc.stdout.close()
    if proc.wait() != 0:
        raise SystemExit(f"error: ffmpeg failed decoding '{path}'")
    return fracs, boxes


def find_segments(path, info, max_duration, fps=10.0, pixel_thresh=12,
                  area_thresh=0.02, gap=0.3, min_excess=0.5):
    fracs, boxes = analyze(path, fps, pixel_thresh)
    n = len(fracs)
    if n == 0:
        return []
    idle = [f < area_thresh for f in fracs]
    # diff i (0-based) covers time [i/fps, (i+1)/fps]
    runs = []
    i = 0
    while i < n:
        if idle[i]:
            j = i
            while j + 1 < n and idle[j + 1]:
                j += 1
            runs.append([i, j])
            i = j + 1
        else:
            i += 1
    # bridge short non-idle gaps
    gap_frames = int(round(gap * fps))
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 <= gap_frames:
            merged[-1][1] = r[1]
        else:
            merged.append(r)

    segments = []
    for a, b in merged:
        start = a / fps
        end = min((b + 1) / fps, info.duration)
        if end - start < max_duration + min_excess:
            continue
        seg_fracs = fracs[a:b + 1]
        seg_boxes = [bx for bx in boxes[a:b + 1] if bx is not None]
        if len(seg_boxes) < 0.1 * len(seg_fracs):  # almost no frame changes
            segments.append(Segment(round(start, 3), round(end, 3), "static"))
            continue
        x0 = min(bx[0] for bx in seg_boxes); y0 = min(bx[1] for bx in seg_boxes)
        x1 = max(bx[2] for bx in seg_boxes); y1 = max(bx[3] for bx in seg_boxes)
        sx, sy = info.width / AW, info.height / AH
        bbox = [int(x0 * sx), int(y0 * sy), int((x1 - x0) * sx), int((y1 - y0) * sy)]
        segments.append(Segment(round(start, 3), round(end, 3), "busy", bbox))
    return segments
