"""
_check_video.py — procura frame preto no render final.

Escrito depois de eu entregar um video com trechos apagados: a fita de titulos
preenchia os buracos com preto OPACO em vez de transparente, e eu tinha
conferido seis instantes que por acaso cairam todos em cima de titulos —
validei justo onde o bug nao aparecia.

Por isso este script amostra de proposito os BURACOS: os trechos sem titulo
nenhum, que sao onde um preenchimento errado apaga a imagem. E tambem varre o
video inteiro em intervalo fixo, pra nao depender de eu escolher bem.

    python -m motioncore._check_video output/edicao_v3.mp4
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
LIMIAR = 8.0        # brilho medio abaixo disso = frame praticamente preto


def brilho(video: Path, t: float) -> float | None:
    r = subprocess.run(
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
         "-i", str(video), "-vframes", "1", "-vf", "scale=192:-1",
         "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        return float(np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGB")).mean())
    except Exception:
        return None


def buracos(cfg: dict, margem: float = 1.0) -> list[float]:
    """Instantes SEM nenhum titulo na tela — onde o preenchimento aparece."""
    janelas = sorted((float(t["startSec"]), float(t["endSec"]))
                     for t in cfg.get("titles") or [])
    dur = float(cfg["videoDuration"])
    pontos, cursor = [], 0.0
    for ini, fim in janelas:
        if ini - cursor > 2 * margem:
            pontos.append((cursor + ini) / 2)      # meio do buraco
        cursor = max(cursor, fim)
    if dur - cursor > 2 * margem:
        pontos.append((cursor + dur) / 2)
    return pontos


def main() -> int:
    video = Path(sys.argv[1] if len(sys.argv) > 1 else "output/edicao_v3.mp4")
    cfg = json.loads((ROOT / "public" / "edit_config.json").read_text(encoding="utf-8"))
    if not video.exists():
        print(f"nao achei {video}")
        return 1

    dur = float(cfg["videoDuration"])
    vazios = buracos(cfg)
    varredura = [t for t in np.arange(5, dur, 45)]
    print(f"{video.name}  |  {len(vazios)} buracos entre titulos + "
          f"{len(varredura)} pontos de varredura\n")

    ruins = []
    for rotulo, pontos in (("buracos (sem titulo)", vazios), ("varredura", varredura)):
        vals = []
        for t in pontos:
            b = brilho(video, t)
            if b is None:
                continue
            vals.append((t, b))
            if b < LIMIAR:
                ruins.append((rotulo, t, b))
        if vals:
            pior = min(vals, key=lambda x: x[1])
            print(f"  {rotulo:<22} {len(vals)} pontos | brilho medio "
                  f"{sum(v for _, v in vals)/len(vals):5.1f} | "
                  f"mais escuro {pior[1]:5.1f} em {pior[0]:.0f}s")

    print()
    if ruins:
        print(f"  {len(ruins)} FRAME(S) PRETO(S):")
        for rotulo, t, b in ruins[:12]:
            print(f"    {t:7.1f}s  brilho {b:4.1f}  ({rotulo})")
        return 1
    print("  nenhum frame preto")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
