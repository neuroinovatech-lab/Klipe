# -*- coding: utf-8 -*-
"""
montar.py — junta as 17 cenas num video so.

As duracoes sao as do `constants.ts` do original, e a transicao e o
TRANSITION_FRAMES=20 dele. A cena que sai e a que entra existem no mesmo
instante e cruzam por opacidade — a transicao mora AQUI e nao dentro da cena,
para nenhuma delas precisar saber quem vem antes ou depois.

    python -m motioncore.cbv.montar            # renderiza tudo
    python -m motioncore.cbv.montar --stills   # um PNG por cena
    python -m motioncore.cbv.montar intro flow # so as citadas
"""
from __future__ import annotations

import importlib
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from ..cena import Cena, validar
from ..ffbin import ffmpeg as _ffmpeg
from ..gpu import onde, superficie
from .base import W, H, FPS, TRANSICAO

RAIZ = Path(__file__).resolve().parent.parent.parent
SAIDA = RAIZ / "output" / "cbv_klipe.mp4"
FFMPEG = _ffmpeg()

# constants.ts:33-52 — a ordem e as duracoes do original
ORDEM = [
    ("intro", 3.5), ("flow", 5.5), ("templates", 3.0), ("focused", 4.0),
    ("collab", 3.0), ("models", 3.5), ("textgen", 3.5), ("styles", 4.0),
    ("audio", 3.5), ("recorder", 3.0), ("editor", 3.5), ("inpaint", 4.0),
    ("upscale", 3.5), ("batch", 3.5), ("perf", 2.5), ("opensource", 3.5),
    ("outro", 4.0),
]


def carregar(quais: list[str] | None = None):
    """Importa cada cena. A que faltar ou quebrar NAO derruba as outras —
    com 17 modulos escritos em paralelo, uma falha nao pode custar o video."""
    out, faltando = [], []
    t = 0.0
    for slug, dur in ORDEM:
        if quais and slug not in quais:
            continue
        try:
            mod = importlib.import_module(f".{slug}", __package__)
            spec = mod.cena(dur)
            erros = validar(spec)
            if erros:
                faltando.append((slug, erros[0]))
                continue
            out.append((slug, spec, t, t + dur, len(spec["camadas"])))
            t += dur - TRANSICAO
        except Exception as e:
            faltando.append((slug, f"{type(e).__name__}: {e}"))
    return out, faltando


def renderizar(cenas) -> Path:
    dur_total = cenas[-1][3]
    n = int(dur_total * FPS)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(
        [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", str(SAIDA)], stdin=subprocess.PIPE)

    montadas = [(Cena(s, W, H, FPS), a, b) for _, s, a, b, _ in cenas]
    surface, fechar = superficie(W, H)
    canvas = surface.getCanvas()
    print(f"  desenhando na {onde()}", flush=True)
    buf = np.empty((H, W, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType,
                               skia.kPremul_AlphaType)
    t0 = time.time()

    for f in range(n):
        t = f / FPS
        canvas.clear(skia.Color4f(0, 0, 0, 1))
        for c, a, b in montadas:
            if not (a <= t < b):
                continue
            alpha = 1.0
            if t < a + TRANSICAO and a > 0:
                alpha = (t - a) / TRANSICAO
            elif t > b - TRANSICAO and b < dur_total:
                alpha = max(0.0, (b - t) / TRANSICAO)
            canvas.saveLayerAlpha(None, int(255 * min(1.0, alpha)))
            c.desenhar(canvas, t - a)
            canvas.restore()
        fechar()
        surface.readPixels(info, buf, W * 4, 0, 0)
        p.stdin.write(buf.tobytes())
        if f % 150 == 0:
            print(f"  {f}/{n} ({f * 100 // max(1, n)}%)", flush=True)

    p.stdin.close()
    p.wait()
    dt = time.time() - t0
    print(f"[CBV] {n} frames em {dt:.1f}s ({n / dt:.1f} fps) | "
          f"{SAIDA} ({SAIDA.stat().st_size / 1e6:.1f} MB)")
    return SAIDA


def provas(cenas):
    pasta = RAIZ / "output" / "_cbv"
    pasta.mkdir(parents=True, exist_ok=True)
    for slug, spec, a, b, n in cenas:
        Cena(spec, W, H, FPS).still((b - a) * 0.6).save(str(pasta / f"{slug}.png"))
    print(f"[CBV] {len(cenas)} provas em {pasta}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cenas, faltando = carregar(args or None)

    print(f"  {len(cenas)}/{len(ORDEM)} cenas prontas")
    for slug, _, a, b, n in cenas:
        print(f"    {slug:12} {b - a:4.1f}s  {n:3} camadas")
    if faltando:
        print(f"  {len(faltando)} faltando:")
        for slug, erro in faltando:
            print(f"    {slug:12} {str(erro)[:80]}")
    if not cenas:
        sys.exit(1)

    total = sum(len(s["camadas"]) for _, s, _, _, _ in cenas)
    print(f"  {total} camadas no total, {cenas[-1][3]:.1f}s de video")
    provas(cenas) if "--stills" in sys.argv else renderizar(cenas)
