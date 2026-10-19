import subprocess
from pathlib import Path

import pytest

from video_trim.detect import find_segments
from video_trim.probe import probe
from video_trim.render import render

SIZE = "640x360"


def make_clip(path):
    """motion 4s | static 8s | motion 2s | spinner 6s | motion 4s  (24s) + audio."""
    def motion(d):
        return ["-f", "lavfi", "-i", f"testsrc2=s={SIZE}:r=30:d={d}"]
    cmd = ["ffmpeg", "-v", "error", "-y"] + motion(4)
    cmd += ["-f", "lavfi", "-i", f"color=c=gray:s={SIZE}:r=30:d=8"] + motion(2)
    cmd += ["-f", "lavfi", "-i", f"color=c=gray:s={SIZE}:r=30:d=6"]
    cmd += ["-f", "lavfi", "-i", "testsrc2=s=48x48:r=30:d=6"] + motion(4)
    cmd += ["-f", "lavfi", "-i", "sine=d=24"]
    cmd += ["-filter_complex",
            "[3][4]overlay=300:150[sp];[0][1][2][sp][5]concat=n=5:v=1:a=0[v]",
            "-map", "[v]", "-map", "6:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(path)]
    subprocess.run(cmd, check=True)


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    p = tmp_path_factory.mktemp("c") / "clip.mp4"
    make_clip(p)
    return p


def test_detect(clip):
    info = probe(clip)
    segs = find_segments(clip, info, 2.0)
    assert [s.kind for s in segs] == ["static", "busy"]
    assert segs[0].start == pytest.approx(4, abs=0.5) and segs[0].end == pytest.approx(12, abs=0.5)
    assert segs[1].start == pytest.approx(14, abs=0.5) and segs[1].end == pytest.approx(20, abs=0.5)
    x, y, w, h = segs[1].bbox
    assert 280 <= x <= 320 and 130 <= y <= 170 and w < 100 and h < 100


@pytest.mark.parametrize("mode", ["cut", "speed"])
def test_render(clip, tmp_path, mode):
    info = probe(clip)
    segs = find_segments(clip, info, 2.0)
    out = tmp_path / "o.mov"
    render(clip, out, segs, 2.0, info, mode)
    o = probe(out)
    expected = info.duration - sum(s.length - 2.0 for s in segs)
    assert o.duration == pytest.approx(expected, abs=0.5)
    assert o.has_audio
