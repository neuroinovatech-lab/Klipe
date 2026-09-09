#!/usr/bin/env python3
"""
apply_silence_cuts.py — Aplica os cuts de silencio/filler no source video.

Le os cuts gerados por silence_detect.py (ou fornecidos via JSON) e gera
video_edited.mp4 sem os trechos cortados, preservando audio+video sincronizado.

Pipeline:
  1. Calcula KEEP ranges (intervalos preservados, complemento dos cuts)
  2. Constroi ffmpeg filter_complex com select+aselect por range
  3. Encoda com NVENC h264 (qualidade alta, rapido)

Uso:
  python apply_silence_cuts.py <project> [--silence-min 0.5]
  python apply_silence_cuts.py abuso-mulheres-autistas --silence-min 0.5
  python apply_silence_cuts.py abuso-mulheres-autistas --cuts-file cuts.json

Output: public/projects/<project>/video_edited.mp4
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from motioncore.ffbin import ffmpeg, ffprobe

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "public" / "projects"
FFMPEG = ffmpeg()
FFPROBE = ffprobe()
PYTHON = sys.executable


def get_video_duration(path: Path) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def calc_keep_ranges(cuts, total_dur):
    """Dado cuts ordenados [{startSec, endSec}], retorna keep ranges [(start, end), ...]."""
    cuts = sorted(cuts, key=lambda c: c["startSec"])
    keep = []
    cur = 0.0
    for c in cuts:
        if c["startSec"] > cur:
            keep.append((cur, c["startSec"]))
        cur = max(cur, c["endSec"])
    if cur < total_dur:
        keep.append((cur, total_dur))
    # Filtra ranges minusculos (<0.05s)
    return [(s, e) for s, e in keep if e - s >= 0.05]


def get_cuts(project: str, silence_min: float, cuts_file: str = None):
    if cuts_file:
        return json.loads(Path(cuts_file).read_text(encoding="utf-8"))["cuts"]
    # Roda silence_detect.py
    r = subprocess.run([PYTHON, str(ROOT / "silence_detect.py"), project,
                        "--silence-min", str(silence_min)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"FAIL silence_detect: {r.stderr}")
        sys.exit(1)
    # Pega ultima linha que comeca com {
    for line in reversed(r.stdout.split("\n")):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)["cuts"]
    print("FAIL: nao achou JSON output do silence_detect")
    sys.exit(1)


def build_concat_filter(keep_ranges):
    """Constroi filter_complex com trim+atrim+concat (robusto pra audio+video sync).

    Pra cada range:
      [0:v]trim=start:end,setpts=PTS-STARTPTS[v_i]
      [0:a]atrim=start:end,asetpts=PTS-STARTPTS[a_i]
    Final: [v_0][a_0][v_1][a_1]...concat=n=N:v=1:a=1[v][a]
    """
    parts = []
    streams = []
    for i, (start, end) in enumerate(keep_ranges):
        parts.append(f"[0:v]trim={start:.3f}:{end:.3f},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim={start:.3f}:{end:.3f},asetpts=PTS-STARTPTS[a{i}]")
        streams.append(f"[v{i}][a{i}]")
    parts.append(f"{''.join(streams)}concat=n={len(keep_ranges)}:v=1:a=1[v][a]")
    return ";".join(parts)


def apply_cuts(project: str, silence_min: float, cuts_file: str = None):
    proj_dir = PROJECTS / project
    src = proj_dir / "video.mp4"
    if not src.exists():
        src = proj_dir / "video_preview.mp4"
    if not src.exists():
        print(f"FAIL: video source nao encontrado em {proj_dir}")
        sys.exit(1)

    out = proj_dir / "video_edited.mp4"
    print(f"[ApplyCuts] Source: {src}")
    print(f"[ApplyCuts] Output: {out}")

    # 1. Pega cuts
    cuts = get_cuts(project, silence_min, cuts_file)
    print(f"[ApplyCuts] {len(cuts)} cuts identificados")

    # 2. Calcula keep ranges
    total_dur = get_video_duration(src)
    keep_ranges = calc_keep_ranges(cuts, total_dur)
    keep_dur = sum(e - s for s, e in keep_ranges)
    cut_dur = total_dur - keep_dur
    print(f"[ApplyCuts] Source: {total_dur:.2f}s -> Output: {keep_dur:.2f}s (cortado: {cut_dur:.2f}s = {cut_dur/total_dur*100:.1f}%)")

    if len(keep_ranges) < 2:
        print(f"[ApplyCuts] Apenas {len(keep_ranges)} keep range(s) — nada pra cortar")
        return

    # 3. Build filter_complex (trim+atrim+concat — sincroniza video+audio)
    filter_complex = build_concat_filter(keep_ranges)

    # 4. NVENC encode
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
           "-i", str(src),
           "-filter_complex", filter_complex,
           "-map", "[v]", "-map", "[a]",
           "-c:v", "h264_nvenc",
           "-preset", "p7", "-tune", "hq",
           "-rc", "vbr", "-cq", "19",
           "-b:v", "0",
           "-multipass", "fullres",
           "-rc-lookahead", "32",
           "-spatial-aq", "1", "-temporal-aq", "1",
           "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart",
           str(out)]

    print(f"[ApplyCuts] Encoding via NVENC ({len(keep_ranges)} segments mesclados)...")
    print(f"[ApplyCuts] filter expr len: {len(filter_complex)} chars")
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t0

    if r.returncode != 0:
        print(f"[ApplyCuts] FFMPEG FAIL ({elapsed:.1f}s):")
        print(r.stderr[-2000:])
        sys.exit(1)

    final_dur = get_video_duration(out)
    sz_mb = out.stat().st_size / 1024 / 1024
    print(f"[ApplyCuts] OK em {elapsed:.1f}s | {sz_mb:.1f} MB | duracao: {final_dur:.2f}s")
    print(f"[ApplyCuts] Saved: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--silence-min", type=float, default=0.5)
    ap.add_argument("--cuts-file", default=None, help="JSON com cuts pre-calculados (opcional)")
    args = ap.parse_args()
    apply_cuts(args.project, args.silence_min, args.cuts_file)


if __name__ == "__main__":
    main()
