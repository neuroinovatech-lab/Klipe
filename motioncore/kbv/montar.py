# -*- coding: utf-8 -*-
"""montar.py — junta as 17 cenas do video de marca do Klipe.

A ordem e as duracoes sao as do `constants.ts` da referencia, cena por cena.
Nao e coincidencia nem homenagem: aquele roteiro tem um ritmo que funciona —
abre curto, explica no longo (5,5 s), alterna denso e leve, joga a cena de 2,5 s
como respiro antes do fecho, e inverte o fundo uma unica vez.

A transicao mora AQUI e nao dentro da cena: a que sai e a que entra existem no
mesmo instante e cruzam por opacidade em 20 frames. Assim nenhuma cena precisa
saber quem vem antes ou depois dela.

    python -m motioncore.kbv.montar             # renderiza
    python -m motioncore.kbv.montar --stills    # um PNG por cena
    python -m motioncore.kbv.montar intro fecho # so as citadas
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
from .base import W, H, FPS, TRANSICAO, claro

RAIZ = Path(__file__).resolve().parent.parent.parent
SAIDA = RAIZ / "output" / "klipe_marca.mp4"
FFMPEG = _ffmpeg()

# (modulo, duracao, cena da referencia, fundo claro?)
#
# A alternancia e a batida do filme. As tres cenas que desenham a INTERFACE
# (corte, linha, omni) ficam escuras porque o Klipe e escuro — inverter ali
# mostraria um programa que nao existe. As que mostram RESULTADO (galeria,
# legenda, som, saida, shorts) e as de argumento (copiloto, conta) clareiam.
# Nunca mais de duas claras seguidas, e nunca a abertura nem o fecho.
ORDEM = [
    ("intro",      3.5, "IntroScene",           False),
    ("fluxo",      5.5, "FlowDemoScene",        False),
    ("templates",  3.0, "TemplatesScene",       True),
    ("corte",      4.0, "FocusedDemoScene",     False),
    ("copiloto",   3.0, "CollaborationScene",   True),
    ("modelos",    3.5, "ModelsScene",          False),
    ("legenda",    3.5, "TextGenerationScene",  True),
    ("estilos",    4.0, "StylePresetsScene",    False),
    ("som",        3.5, "AudioGenerationScene", True),
    ("gravar",     3.0, "RecorderScene",        False),
    ("linha",      3.5, "EditorScene",          False),
    ("omni",       4.0, "InpaintingScene",      False),
    ("render",     3.5, "UpscalingScene",       True),
    ("shorts",     3.5, "BatchGenerationScene", True),
    ("desempenho", 2.5, "PerformanceScene",     False),
    ("local",      3.5, "OpenSourceScene",      True),
    ("fecho",      4.0, "OutroScene",           False),
]


def carregar(quais: list[str] | None = None):
    """Uma cena que quebra NAO derruba as outras — com 17 modulos, uma falha
    nao pode custar o video inteiro."""
    out, faltando, t = [], [], 0.0
    for slug, dur, _ref, inverter in ORDEM:
        if quais and slug not in quais:
            continue
        try:
            mod = importlib.import_module(f".{slug}", __package__)
            spec = mod.cena(dur)
            if inverter:
                spec = claro(spec)
            erros = validar(spec)
            if erros:
                faltando.append((slug, erros[0]))
                continue
            out.append((slug, spec, t, t + dur))
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

    montadas = [(Cena(s, W, H, FPS), a, b) for _, s, a, b in cenas]
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
    print(f"[KBV] {n} frames em {dt:.1f}s ({n / dt:.1f} fps) | "
          f"{SAIDA} ({SAIDA.stat().st_size / 1e6:.1f} MB)")
    return SAIDA


def provas(cenas):
    """Um PNG por cena, no ponto em que ela ja mostrou tudo (75% da duracao).

    60% pegava varias cenas com o ultimo bloco ainda entrando, e prova assim
    faz eu aprovar layout que o espectador nunca ve completo.
    """
    pasta = RAIZ / "output" / "_kbv"
    pasta.mkdir(parents=True, exist_ok=True)
    for slug, spec, a, b in cenas:
        Cena(spec, W, H, FPS).still((b - a) * 0.75).save(str(pasta / f"{slug}.png"))
    print(f"[KBV] {len(cenas)} provas em {pasta}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cenas, faltando = carregar(args or None)

    print(f"  {len(cenas)}/{len(ORDEM)} cenas")
    ref = {s: (r, c) for s, _d, r, c in ORDEM}
    for slug, spec, a, b in cenas:
        r, c = ref[slug]
        print(f"    {slug:11} {b - a:4.1f}s  {len(spec['camadas']):4} camadas"
              f"  {'CLARO' if c else '     '}  <- {r}")
    if faltando:
        print(f"  {len(faltando)} com problema:")
        for slug, erro in faltando:
            print(f"    {slug:11} {str(erro)[:90]}")
    if not cenas:
        sys.exit(1)

    total = sum(len(s["camadas"]) for _, s, _, _ in cenas)
    print(f"  {total} camadas · {cenas[-1][3]:.1f}s de video")
    provas(cenas) if "--stills" in sys.argv else renderizar(cenas)
