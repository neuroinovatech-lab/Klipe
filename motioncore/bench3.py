"""
bench3.py — monta o projeto de 3 minutos que serve de regua pro render.

Recorta o edit_config real nos primeiros N segundos (default 180) e corta o
video na mesma medida. Assim da pra medir "antes e depois" sempre no MESMO
material, em vez de comparar render de projetos diferentes.

    python -m motioncore.bench3                 # monta o projeto de 180s
    python -m motioncore.bench3 --segundos 60   # versao curta pra iterar

Depois:
    python forge_render.py --config output/_bench3/edit_config.json \
        --per-title --out bench3.mp4
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

# arrays com (startSec, endSec) que precisam ser recortados junto
LISTAS_TEMPORAIS = ["captions", "titles", "brolls", "sfx", "zooms", "shapes",
                    "musicTracks", "audioRegions"]


def recorta(cfg: dict, dur: float) -> dict:
    novo = dict(cfg)
    for chave in LISTAS_TEMPORAIS:
        itens = cfg.get(chave) or []
        mantidos = []
        for it in itens:
            if not isinstance(it, dict) or "startSec" not in it:
                continue
            ini = float(it.get("startSec", 0))
            if ini >= dur:
                continue
            it = dict(it)
            it["endSec"] = min(float(it.get("endSec", dur)), dur)
            if it["endSec"] - ini <= 0:
                continue
            mantidos.append(it)
        novo[chave] = mantidos
    novo["videoDuration"] = dur
    novo["videoBaseDurationSec"] = dur
    # cortes/keeps sao do fluxo de edicao, nao do render — fora do recorte eles
    # so confundem a medicao
    for k in ("cutMarks", "keepRanges", "videoClips"):
        novo.pop(k, None)
    return novo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segundos", type=float, default=180.0)
    ap.add_argument("--config", default=str(PUBLIC / "edit_config.json"))
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    dur = args.segundos
    destino = ROOT / "output" / "_bench3"
    destino.mkdir(parents=True, exist_ok=True)

    src = PUBLIC / cfg["videoSrc"]
    if not src.exists():
        raise SystemExit(f"video de origem nao encontrado: {src}")

    # O corte fica DENTRO de public/ porque o videoSrc do cfg e relativo a ela.
    rel = f"projects/_bench3/video_{int(dur)}s.mp4"
    corte = PUBLIC / rel
    corte.parent.mkdir(parents=True, exist_ok=True)
    if not corte.exists():
        print(f"cortando {dur:.0f}s de {src.name}...")
        t0 = time.time()
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(src), "-t", str(dur),
                        "-c", "copy", "-avoid_negative_ts", "make_zero", str(corte)],
                       check=True)
        print(f"  ok em {time.time()-t0:.1f}s ({corte.stat().st_size/1e6:.0f} MB)")
    else:
        print(f"corte ja existe: {corte.name}")

    novo = recorta(cfg, dur)
    novo["videoSrc"] = rel
    saida = destino / "edit_config.json"
    saida.write_text(json.dumps(novo, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nprojeto de {dur:.0f}s em {saida}")
    for k in LISTAS_TEMPORAIS:
        n = len(novo.get(k) or [])
        if n:
            print(f"  {k:<12} {n}")
    print(f"  legendas ligadas: {novo.get('showCaptions')} | estilo {novo.get('captionStyle')!r}")
    print(f"\nrodar:\n  python forge_render.py --config {saida.relative_to(ROOT)} "
          f"--per-title --out bench3.mp4")


if __name__ == "__main__":
    main()
