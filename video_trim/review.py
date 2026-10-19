"""Show detected segments, make thumbnails, ask the user which to trim, plan JSON I/O."""
import json
import re
import subprocess
from pathlib import Path

from .detect import Segment
from .probe import require_binary


def fmt_t(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def print_table(segments, max_duration, duration, selected=None):
    if not segments:
        print("No idle segments longer than the limit were found.")
        return
    print(f"\n{'#':>3}  {'sel':3}  {'start':>8}  {'end':>8}  {'length':>7}  {'saves':>6}  kind / region")
    for i, s in enumerate(segments, 1):
        mark = "[x]" if selected is None or i in selected else "[ ]"
        region = f"busy @ x={s.bbox[0]} y={s.bbox[1]} {s.bbox[2]}x{s.bbox[3]}" if s.kind == "busy" else "static"
        print(f"{i:>3}  {mark:3}  {fmt_t(s.start):>8}  {fmt_t(s.end):>8}  {s.length:6.1f}s  "
              f"{max(0, s.length - max_duration):5.1f}s  {region}")
    saved = sum(max(0, s.length - max_duration) for k, s in enumerate(segments, 1)
                if selected is None or k in selected)
    print(f"\nOriginal {fmt_t(duration)}  ->  about {fmt_t(duration - saved)} (saves {saved:.1f}s)")


def make_thumbnails(src, segments, outdir):
    ffmpeg = require_binary("ffmpeg")
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(segments, 1):
        vf = "scale=640:-2"
        if s.bbox:
            x, y, w, h = s.bbox
            vf = f"drawbox=x={x}:y={y}:w={w}:h={h}:color=red:t=4,scale=640:-2"
        subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", f"{(s.start + s.end) / 2:.3f}",
                        "-i", str(src), "-frames:v", "1", "-vf", vf,
                        str(outdir / f"seg_{i}.jpg")], check=False)


def parse_selection(text, count):
    text = text.strip().lower()
    if text in ("all", "a", "y", "yes", ""):
        return set(range(1, count + 1))
    if text in ("none", "n", "no"):
        return set()
    sel = set()
    for part in text.replace(" ", "").split(","):
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise ValueError(f"bad selection '{part}'")
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        sel.update(range(a, b + 1))
    if any(i < 1 or i > count for i in sel):
        raise ValueError(f"segment numbers must be 1..{count}")
    return sel


def confirm(segments, max_duration, duration):
    """Interactive loop. Returns the list of confirmed segments (possibly edited)."""
    selected = set(range(1, len(segments) + 1))
    print_table(segments, max_duration, duration, selected)
    while True:
        ans = input("\nTrim which? [all / none / 1,3,5-7 / e <n> <start> <end> (seconds) / q]: ").strip()
        if ans.lower() in ("q", "quit"):
            return []
        if ans.lower().startswith("e "):
            try:
                _, n, a, b = ans.split()
                n, a, b = int(n), float(a), float(b)
                if not (1 <= n <= len(segments) and 0 <= a < b <= duration):
                    raise ValueError
            except ValueError:
                print("usage: e <n> <start_sec> <end_sec>")
                continue
            segments[n - 1].start, segments[n - 1].end = a, b
            print_table(segments, max_duration, duration, selected)
            continue
        try:
            selected = parse_selection(ans, len(segments))
        except ValueError as e:
            print(e)
            continue
        print_table(segments, max_duration, duration, selected)
        if input("Proceed with these? [Y/n] ").strip().lower() in ("", "y", "yes"):
            return [s for i, s in enumerate(segments, 1) if i in selected]


def save_plan(path, src, duration, max_duration, segments):
    Path(path).write_text(json.dumps({
        "input": str(src), "duration": duration, "max_duration": max_duration,
        "segments": [s.to_dict() for s in segments]}, indent=2))


def load_plan(path):
    d = json.loads(Path(path).read_text())
    return [Segment(**s) for s in d["segments"]]
