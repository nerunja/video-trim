# video-trim

Shortens idle stretches in screen recordings (mp4/mov): fully static screens **and** stretches where only
a small region changes (spinners, progress bars, blinking cursors). Detected stretches are listed for
confirmation before anything is cut.

Works on macOS and Linux. Needs `python3` (3.9+) and `ffmpeg` (`brew install ffmpeg` / `sudo apt install ffmpeg`).

    ./setup.sh                       # creates .venv, installs numpy
    ./video-trim demo.mov -m 2       # keep at most 2s of each idle stretch

It prints a numbered table (time range, static/busy + spinner region, time saved), writes red-boxed
thumbnails to `<out>_review/`, then asks what to trim: `all`, `none`, `1,3,5-7`, or `e <n> <start> <end>` to
adjust a segment.

Options: `--mode cut|speed` (drop the excess, or speed it up to N s), `--mute-sped`, `-o out.mov`,
`-y` (no prompt), `--dry-run` (report only), `--plan plan.json` (reuse a saved/edited plan),
`--area-thresh 0.02` (max fraction of the frame that may change and still be "idle"; raise for noisy
backgrounds), `--pixel-thresh 12`, `--gap 0.3`, `--fps 10`.

Limits: detection is visual only — narration over a static screen is cut too unless you exclude that segment.

Tests: `.venv/bin/pip install pytest && .venv/bin/python -m pytest tests`
