#!/usr/bin/env python3
"""
consolidate_cuts.py — "Juntar Cortes" estilo CapCut

Le edit_config.json, calcula keep ranges dos videoClips, aplica os cortes no source
(via ffmpeg + NVENC), regenera video_preview, e atualiza config pra 1 unico clip
continuo (sem gaps na timeline).

Pode ser chamado via:
  python consolidate_cuts.py <project>           # consolida + atualiza config

Comportamento:
- Source 832s + 3 videoClips com 5s de cuts -> source 827s + 1 videoClip de 0->827
- Apos consolidar, todos os timestamps dos titles/zooms/sfx precisam ser ajustados
  (caller decide se faz; recomendado: rodar shift_timestamps depois)
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "public" / "projects"
PUBLIC = ROOT / "public"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"


def consolidate(project: str):
    proj_dir = PROJECTS / project
    cfg_path = PUBLIC / "edit_config.json"  # cfg ATIVO no Klipe
    if not cfg_path.exists():
        print(f"FAIL: {cfg_path} nao existe")
        sys.exit(1)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    src = proj_dir / "video.mp4"
    if not src.exists():
        print(f"FAIL: source {src} nao existe")
        sys.exit(1)

    DURATION = cfg["videoDuration"]
    clips = sorted(cfg.get("videoClips", []), key=lambda c: c["startSec"])
    if len(clips) <= 1:
        print(f"Nada pra consolidar — apenas {len(clips)} clip(s)")
        return {"ok": True, "message": "Nada pra consolidar", "newDuration": DURATION}

    # Keep ranges = videoClips em ordem (cada clip ja eh um keep range)
    keeps = [(c["startSec"], c["endSec"]) for c in clips]
    keep_dur = sum(e - s for s, e in keeps)
    cut_dur = DURATION - keep_dur
    print(f"[Consolidate] {len(keeps)} keep ranges | {keep_dur:.2f}s mantidos | {cut_dur:.2f}s cortados")

    # Backup original (se nao tem)
    backup = proj_dir / "video_pre_consolidate.mp4"
    if not backup.exists():
        shutil.copy2(src, backup)
        print(f"[Consolidate] Backup salvo: {backup.name}")

    # ffmpeg: concat demuxer com -c copy (FAST — sem reencode)
    # Usa inpoint/outpoint pra cada keep range, concat protocol direto
    # Caveat: cortes nao caem em keyframes EXATOS — pode haver +/-1 frame de drift
    # mas pra cortes de silencio (Dra Eli) eh imperceptivel
    out_video = proj_dir / "video_consolidated.mp4"
    concat_list = proj_dir / "_concat_list.txt"
    src_str = str(src).replace("\\", "/")
    lines = []
    for s, e in keeps:
        lines.append(f"file '{src_str}'")
        lines.append(f"inpoint {s:.3f}")
        lines.append(f"outpoint {e:.3f}")
    concat_list.write_text("\n".join(lines), encoding="utf-8")

    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
           "-f", "concat", "-safe", "0",
           "-i", str(concat_list),
           "-c", "copy",  # SEM reencode — copia stream direto
           "-movflags", "+faststart",
           str(out_video)]
    print(f"[Consolidate] ffmpeg concat -c copy ({len(keeps)} segments — sem reencode)...")
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t0
    concat_list.unlink(missing_ok=True)
    if r.returncode != 0:
        print(f"FAIL ffmpeg ({elapsed:.1f}s):\n{r.stderr[-1500:]}")
        sys.exit(1)

    # Substitui source
    src_old = proj_dir / "_video_old.mp4"
    src.rename(src_old)
    out_video.rename(src)
    src_old.unlink()
    print(f"[Consolidate] video.mp4 substituido em {elapsed:.1f}s | {src.stat().st_size//1024//1024} MB")

    # Regenera preview RAPIDO via -c copy (sem reencode)
    preview = proj_dir / "video_preview.mp4"
    if preview.exists(): preview.unlink()
    t1 = time.time()
    subprocess.run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-c", "copy",
        "-movflags", "+faststart",
        str(preview)
    ], check=True)
    print(f"[Consolidate] video_preview.mp4 (copy, {time.time()-t1:.1f}s) | {preview.stat().st_size//1024//1024} MB")

    # Atualiza config: 1 unico videoClip de 0 -> nova duracao
    new_dur = round(keep_dur, 2)
    SRC_REL = f"projects/{project}/video_preview.mp4"
    cfg["videoDuration"] = new_dur
    cfg["videoBaseDurationSec"] = new_dur
    cfg["videoSrc"] = SRC_REL
    cfg["videoClips"] = [{
        "id": "v01",
        "startSec": 0,
        "endSec": new_dur,
        "src": SRC_REL,
        "posX": 0, "posY": 0, "scale": 1, "rotation": 0,
        "opacity": 1, "volume": 1, "muted": False,
        "speed": 1, "fadeIn": 0, "fadeOut": 0,
        "baseDurationSec": new_dur,
    }]
    # Move appliedCuts pra historico (tracking)
    cfg.setdefault("_consolidatedHistory", []).append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cuts": cfg.get("_appliedCuts", []),
        "newDuration": new_dur,
        "oldDuration": DURATION,
    })
    cfg.pop("_appliedCuts", None)
    cfg.pop("segments", None)

    # Salva tanto no public quanto no projeto
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    (proj_dir / "edit_config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Consolidate] config atualizado | nova duracao: {new_dur}s")

    return {
        "ok": True,
        "newDuration": new_dur,
        "oldDuration": DURATION,
        "cutTotal": round(cut_dur, 2),
        "keepRanges": len(keeps),
        "elapsedSec": round(elapsed, 1),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    args = ap.parse_args()
    result = consolidate(args.project)
    print(f"\n{json.dumps(result, ensure_ascii=False, indent=2)}")
