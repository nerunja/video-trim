import argparse
import sys
from pathlib import Path

from .detect import find_segments
from .probe import probe, require_binary
from .render import render
from .review import confirm, load_plan, make_thumbnails, print_table, save_plan


def parse_args(argv):
    p = argparse.ArgumentParser(prog="video-trim", description=(
        "Detect static / busy-indicator stretches in a screen recording and shorten them."))
    p.add_argument("input", type=Path)
    p.add_argument("-m", "--max-duration", type=float, required=True,
                   help="max seconds each idle stretch may keep (e.g. 2)")
    p.add_argument("-o", "--output", type=Path, help="default: <name>_trimmed.<ext>")
    p.add_argument("--mode", choices=["cut", "speed"], default="cut",
                   help="cut: keep first N secs of each stretch; speed: speed it up to N secs")
    p.add_argument("--mute-sped", action="store_true", help="mute audio in sped-up parts")
    p.add_argument("--pixel-thresh", type=int, default=12, help="per-pixel diff (0-255) counted as change")
    p.add_argument("--area-thresh", type=float, default=0.02,
                   help="max fraction of frame changing for a frame to count as idle (default 0.02)")
    p.add_argument("--gap", type=float, default=0.3, help="bridge activity blips shorter than this (s)")
    p.add_argument("--min-excess", type=float, default=0.5,
                   help="only report stretches at least this much longer than max-duration")
    p.add_argument("--fps", type=float, default=10.0, help="analysis sampling rate")
    p.add_argument("--plan", type=Path, help="reuse a saved plan JSON instead of detecting")
    p.add_argument("--dry-run", action="store_true", help="report + write plan, don't render")
    p.add_argument("-y", "--yes", action="store_true", help="trim all detected stretches without asking")
    return p.parse_args(argv)


def main(argv=None):
    a = parse_args(sys.argv[1:] if argv is None else argv)
    require_binary("ffmpeg")
    if not a.input.is_file():
        raise SystemExit(f"error: '{a.input}' not found")
    if a.max_duration <= 0:
        raise SystemExit("error: --max-duration must be > 0")
    out = a.output or a.input.with_name(f"{a.input.stem}_trimmed{a.input.suffix}")
    if out.resolve() == a.input.resolve():
        raise SystemExit("error: output must differ from input")

    info = probe(a.input)
    print(f"{a.input.name}: {info.duration:.1f}s, {info.width}x{info.height}"
          f"{', audio' if info.has_audio else ''}")
    if a.plan:
        segments = load_plan(a.plan)
    else:
        print("Analyzing...")
        segments = find_segments(a.input, info, a.max_duration, a.fps, a.pixel_thresh,
                                 a.area_thresh, a.gap, a.min_excess)
    if not segments:
        print("No idle segments longer than the limit were found.")
        return 0

    plan_path = out.with_name(out.stem + "_plan.json")
    save_plan(plan_path, a.input, info.duration, a.max_duration, segments)
    review_dir = out.with_name(out.stem + "_review")
    make_thumbnails(a.input, segments, review_dir)
    print(f"Plan: {plan_path}\nThumbnails: {review_dir}/")

    if a.dry_run:
        print_table(segments, a.max_duration, info.duration)
        return 0
    if a.yes:
        print_table(segments, a.max_duration, info.duration)
    else:
        segments = confirm(segments, a.max_duration, info.duration)
        if not segments:
            print("Nothing selected; no output written.")
            return 0
    render(a.input, out, segments, a.max_duration, info, a.mode, a.mute_sped)
    print(f"Wrote {out} ({probe(out).duration:.1f}s)")
    return 0
