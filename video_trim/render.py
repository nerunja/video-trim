"""Render the trimmed video with ffmpeg."""
import os
import subprocess
import tempfile

from .probe import require_binary


def build_pieces(segments, max_duration, duration, mode):
    """Return [(start, end, speed)] covering the kept video in order."""
    pieces, pos = [], 0.0
    for s in sorted(segments, key=lambda s: s.start):
        if s.length <= max_duration:
            continue
        if s.start > pos:
            pieces.append((pos, s.start, 1.0))
        if mode == "cut":
            pieces.append((s.start, s.start + max_duration, 1.0))
        else:
            pieces.append((s.start, s.end, s.length / max_duration))
        pos = s.end
    if pos < duration:
        pieces.append((pos, duration, 1.0))
    return [p for p in pieces if p[1] - p[0] > 0.001]


def atempo_chain(speed):
    parts = []
    while speed > 2.0:
        parts.append("atempo=2.0")
        speed /= 2.0
    parts.append(f"atempo={speed:.6f}")
    return ",".join(parts)


def build_filter(pieces, has_audio, mute_sped):
    lines, labels = [], []
    for i, (a, b, sp) in enumerate(pieces):
        lines.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{sp:.6f}[v{i}]")
        if has_audio:
            chain = f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS"
            if sp != 1.0:
                chain += "," + atempo_chain(sp)
                if mute_sped:
                    chain += ",volume=0"
            lines.append(chain + f"[a{i}]")
            labels.append(f"[v{i}][a{i}]")
        else:
            labels.append(f"[v{i}]")
    n = len(pieces)
    if has_audio:
        lines.append("".join(labels) + f"concat=n={n}:v=1:a=1[vc][a]")
    else:
        lines.append("".join(labels) + f"concat=n={n}:v=1:a=0[vc]")
    lines.append("[vc]scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p[v]")
    return ";\n".join(lines)


def render(src, dst, segments, max_duration, info, mode="cut", mute_sped=False):
    ffmpeg = require_binary("ffmpeg")
    pieces = build_pieces(segments, max_duration, info.duration, mode)
    if not pieces:
        raise SystemExit("error: nothing left to render")
    graph = build_filter(pieces, info.has_audio, mute_sped)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(graph)
        script = f.name
    try:
        cmd = [ffmpeg, "-hide_banner", "-v", "error", "-stats", "-y", "-i", str(src),
               "-filter_complex_script", script, "-map", "[v]"]
        if info.has_audio:
            cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
        cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "medium",
                "-movflags", "+faststart", str(dst)]
        if subprocess.run(cmd).returncode != 0:
            raise SystemExit("error: ffmpeg render failed")
    finally:
        os.unlink(script)
