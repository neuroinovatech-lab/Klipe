# -*- coding: utf-8 -*-
"""
assets_ref.py — componentes do repositorio de referencia, refeitos no MotionCore.

O repo `creativly.ai-brand-video-remotion` tem 16 componentes reusaveis. Este
arquivo refaz quatro deles para responder uma pergunta com prova em vez de
opiniao: da para replicar aquilo aqui?

Escolhi os quatro que mais servem como ASSET DE TITULO — coisa que vira um
estilo salvo e reaproveitavel, e nao um momento amarrado a uma cena:

    SplitText      texto que entra letra a letra, escalonado
    PulseRings     aneis que pulsam para fora de um ponto
    GlowOrb        esfera de luz com degrade radial
    BrowserWindow  moldura de navegador, para enquadrar captura de tela

A LICAO DE ONTEM esta aplicada aqui: nada de `repetir` para os elementos que
precisam de identidade propria. Cada letra e cada anel e uma camada, com a sua
curva e o seu tempo. Foi o `repetir` — mesma animacao em N copias — que deixou
as pecas anteriores com cara de maquina.

    python -m motioncore.assets_ref
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from .cena import Cena, validar
from .ffbin import ffmpeg as _ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "output" / "assets_ref.mp4"
FFMPEG = _ffmpeg()

W, H, FPS, DUR = 1080, 1920, 30, 12.0

FUNDO = "#0B0D12"
CIANO = "#22D3EE"
VIOLETA = "#8B5CF6"
BRANCO = "#F8FAFC"
CINZA = "#4B5563"


# ── largura por classe de caractere (mesma heuristica de montar_sincronia) ──
_ESTREITAS = set("ilj.,;:!|'()[]{}t ")
_LARGAS = set("mwMW@")


def _larg(ch: str, tam: float) -> float:
    if ch in _ESTREITAS:
        return 0.30 * tam
    if ch in _LARGAS:
        return 0.92 * tam
    if ch.isupper():
        return 0.68 * tam
    return 0.56 * tam


# ══ 1. SplitText ══════════════════════════════════════════════════════
# "character stagger reveal". Uma camada POR LETRA, e a graca esta em cada
# uma ter tempo e curva propria — com `repetir` sairia o robo de ontem.

def split_text(texto: str, t0: float, y: float = 0, tam: int = 96,
               cor: str = BRANCO) -> list[dict]:
    larguras = [_larg(c, tam) for c in texto]
    total = sum(larguras)
    x = -total / 2
    curvas = ["outBack", "outQuint", "outCirc", "outExpo"]
    camadas = []
    for i, (ch, lg) in enumerate(zip(texto, larguras)):
        if ch != " ":
            d = t0 + i * 0.045
            camadas.append({
                "tipo": "texto", "texto": ch, "tamanho": tam, "peso": 900,
                "cor": cor, "x": x + lg / 2, "y": y,
                # sobe de baixo, com antecipacao: desce um tico antes de subir
                "y": [[d, y - 46], [d + 0.06, y - 54, "inOutSine"],
                      [d + 0.42, y, curvas[i % 4]]],
                "opacidade": [[d, 0], [d + 0.10, 1]],
                "escala": [[d, 0.7], [d + 0.40, 1, curvas[i % 4]]],
            })
        x += lg
    return camadas


# ══ 2. PulseRings ═════════════════════════════════════════════════════
# Aneis saindo de um ponto. O intervalo entre eles NAO e constante — vai
# encurtando, que e o que da sensacao de energia crescendo.

def pulse_rings(t0: float, y: float, n: int = 5, cor: str = CIANO) -> list[dict]:
    out = []
    for i in range(n):
        d = t0 + sum(0.62 * (0.86 ** k) for k in range(i))
        out.append({
            "tipo": "elipse", "raio": 90, "cor": "#00000000",
            "contorno": cor, "contorno_larg": 3, "y": y,
            "escala": [[d, 0.25], [d + 1.7, 3.4, "outCirc"]],
            "opacidade": [[d, 0.9], [d + 1.7, 0]],
        })
    out.append({
        "tipo": "elipse", "raio": 26, "cor": cor, "y": y,
        "escala": [[t0, 0], [t0 + 0.4, 1, "outBack"],
                   [t0 + 1.4, 1.12, "inOutSine"], [t0 + 2.4, 1, "inOutSine"],
                   [t0 + 3.4, 1.12, "inOutSine"]],
        "opacidade": [[t0, 0], [t0 + 0.2, 1]],
    })
    return out


# ══ 3. GlowOrb ════════════════════════════════════════════════════════
# Esfera de luz. Degrade radial + halo borrado atras. O `blur` nao anima,
# entao a respiracao vem da escala.

def glow_orb(t0: float, x: float, y: float, cor: str, r: int = 150) -> list[dict]:
    respiro = [[t0, 0], [t0 + 0.7, 1.06, "outCubic"], [t0 + 2.4, 0.94, "inOutSine"],
               [t0 + 4.1, 1.06, "inOutSine"], [t0 + 5.8, 0.96, "inOutSine"]]
    return [
        {"tipo": "elipse", "raio": r * 1.9, "x": x, "y": y, "blur": 46,
         "cor": {"tipo": "radial", "cores": [cor, "#00000000"], "raio": r * 1.9},
         "escala": respiro, "opacidade": [[t0, 0], [t0 + 0.8, 0.55]]},
        {"tipo": "elipse", "raio": r, "x": x, "y": y,
         "cor": {"tipo": "radial", "cores": ["#FFFFFF", cor], "raio": r},
         "escala": respiro, "opacidade": [[t0, 0], [t0 + 0.5, 1]]},
    ]


# ══ 4. BrowserWindow ══════════════════════════════════════════════════
# Moldura de navegador. Serve para enquadrar captura de tela — e o Klipe
# agora GRAVA tela, entao este e o asset que casa com aquilo.

def browser_window(t0: float, y: float, larg: int = 880, alt: int = 560) -> list[dict]:
    topo = 46
    return [
        {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": 16,
         "cor": "#111827", "contorno": "#1F2937", "contorno_larg": 2, "y": y,
         "escala": [[t0, 0.88], [t0 + 0.5, 1.02, "outBack"], [t0 + 0.7, 1, "outQuad"]],
         "opacidade": [[t0, 0], [t0 + 0.18, 1]]},
        # a barra de titulo
        {"tipo": "retangulo", "larg": larg - 4, "alt": topo, "raio": 14,
         "cor": "#1F2937", "y": y + alt / 2 - topo / 2 - 2,
         "opacidade": [[t0 + 0.2, 0], [t0 + 0.4, 1]]},
    ] + [
        # os tres botoes, entrando um a um
        {"tipo": "elipse", "raio": 7, "cor": c,
         "x": -larg / 2 + 34 + i * 26, "y": y + alt / 2 - topo / 2 - 2,
         "escala": [[t0 + 0.42 + i * 0.07, 0], [t0 + 0.72 + i * 0.07, 1, "outBack"]],
         "opacidade": [[t0 + 0.42 + i * 0.07, 0], [t0 + 0.55 + i * 0.07, 1]]}
        for i, c in enumerate(("#EF4444", "#F59E0B", "#22C55E"))
    ] + [
        # a barra de endereco, crescendo
        {"tipo": "retangulo", "larg": larg - 220, "alt": 22, "raio": 11,
         "cor": "#374151", "y": y + alt / 2 - topo / 2 - 2, "x": 40,
         "escalaX": [[t0 + 0.6, 0], [t0 + 1.0, 1, "outCirc"]],
         "opacidade": [[t0 + 0.6, 0], [t0 + 0.75, 1]]},
        # o conteudo revelando por cortina, de cima para baixo
        {"tipo": "retangulo", "larg": larg - 40, "alt": alt - topo - 26, "raio": 8,
         "cor": {"tipo": "linear", "cores": ["#1E293B", "#0F172A"],
                 "de": [0, -200], "para": [0, 200]},
         "y": y - topo / 2 - 6,
         "revelar": {"dir": "baixo", "prog": [[t0 + 0.9, 0], [t0 + 1.5, 1, "outCubic"]]},
         "opacidade": [[t0 + 0.9, 0], [t0 + 1.0, 1]]},
    ]


def cena() -> dict:
    return {"duracao": DUR, "fundo": FUNDO, "camadas": [
        # fundo: dois orbes atras de tudo
        *glow_orb(0.2, -330, 620, VIOLETA, 190),
        *glow_orb(0.6, 340, -560, CIANO, 210),

        *split_text("SPLIT TEXT", 0.4, y=760, tam=86),
        {"tipo": "texto", "texto": "letra a letra, cada uma com sua curva",
         "tamanho": 26, "cor": CINZA, "y": 676,
         "opacidade": [[1.1, 0], [1.5, 1]]},

        *pulse_rings(1.8, y=330),
        {"tipo": "texto", "texto": "PULSE RINGS", "tamanho": 30, "peso": 800,
         "cor": CIANO, "espacamento": 3, "y": 130,
         "opacidade": [[2.2, 0], [2.6, 1]]},

        *browser_window(3.6, y=-330),
        {"tipo": "texto", "texto": "BROWSER WINDOW", "tamanho": 30, "peso": 800,
         "cor": VIOLETA, "espacamento": 3, "y": -700,
         "opacidade": [[4.4, 0], [4.8, 1]]},

        {"tipo": "texto", "texto": "GLOW ORB  ·  fundo", "tamanho": 24,
         "cor": CINZA, "y": -830,
         "opacidade": [[5.4, 0], [5.9, 1]]},
    ]}


def renderizar() -> Path:
    spec = cena()
    erros = validar(spec)
    if erros:
        print("  " + "\n  ".join(erros[:6]))
        sys.exit(1)
    print(f"  {len(spec['camadas'])} camadas · validou")
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    n = int(DUR * FPS)
    p = subprocess.Popen(
        [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
         "-pix_fmt", "yuv420p", str(SAIDA)], stdin=subprocess.PIPE)
    c = Cena(spec, W, H, FPS)
    surface = skia.Surface(W, H)
    canvas = surface.getCanvas()
    buf = np.empty((H, W, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    t0 = time.time()
    for f in range(n):
        canvas.clear(skia.Color4f(0, 0, 0, 1))
        c.desenhar(canvas, f / FPS)
        surface.readPixels(info, buf, W * 4, 0, 0)
        p.stdin.write(buf.tobytes())
    p.stdin.close()
    p.wait()
    print(f"[Assets] {n} frames em {time.time()-t0:.1f}s -> {SAIDA}")
    return SAIDA


if __name__ == "__main__":
    renderizar()
