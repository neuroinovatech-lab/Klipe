# -*- coding: utf-8 -*-
"""
comparar_snap.py — o mesmo momento, do meu jeito e com oficio. Lado a lado.

O usuario disse que os meus motions ficam duros. Medi e ele tem razao: em duas
pecas inteiras usei 4 easings de 31, e `outCubic` sozinho 19 vezes.

Esta peca isola UM momento — o caos virando padrao — e desenha duas vezes na
mesma tela. Em cima, do jeito que eu vinha fazendo. Embaixo, com as quatro
coisas que faltavam. Quatro segundos, o mesmo conteudo, a mesma paleta: a unica
variavel e o oficio.

A DESCOBERTA que motivou o arquivo:

    `repetir` e o que torna a grade barata — uma camada vira 117 copias. Mas
    ele aplica a MESMA animacao a todas: mesma curva, mesmo overshoot, mesmo
    tudo, deslocado so no tempo. E exatamente isso que o olho le como
    "maquina": 117 objetos com identidade unica.

    Variedade por elemento custa 117 camadas em vez de 1. Mais caro de
    escrever, mais caro de desenhar — e e a diferenca inteira.

O QUE MUDA, item por item:

  1. Antecipacao   antes de encaixar, o ponto RECUA. Dois keyframes.
  2. Easing por    cada ponto sorteia entre outBack, outElastic, outQuint e
     elemento      outCirc. Peso diferente por objeto.
  3. Ritmo no      o atraso nao e constante: comeca lento e acelera, como
     atraso        quem percebe o padrao e vai ficando mais rapido.
  4. Arco          x e y com curvas DIFERENTES. Mesma curva nos dois eixos
                   da trajetoria reta, que e o que parece robotico.

    python -m motioncore.comparar_snap
"""
from __future__ import annotations

import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from .cena import Cena, validar
from .ffbin import ffmpeg as _ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "output" / "comparar_snap.mp4"
FFMPEG = _ffmpeg()

W, H, FPS, DUR = 1080, 1920, 30, 5.0

CARVAO = "#16171C"
AZUL = "#2E6BFF"
ROXO = "#A855F7"
CINZA = "#5A6072"

COLS, LINHAS, ESP = 9, 5, 74
T_SNAP = 1.2          # quando a grade encaixa


def _alvo(i: int) -> tuple[float, float]:
    """Onde o ponto TERMINA — a posicao dele na grade."""
    c, l = i % COLS, i // COLS
    return ((c - (COLS - 1) / 2) * ESP, ((LINHAS - 1) / 2 - l) * ESP)


def _origem(i: int) -> tuple[float, float]:
    """De onde ele vem — o caos. Progressao irracional: espalha sem repetir."""
    a = i * 2.39996
    r = 180 + (i % 6) * 70
    return (r * math.cos(a) * 1.4, r * math.sin(a) * 0.9)


# ══ EM CIMA: como eu vinha fazendo ════════════════════════════════════
# Uma camada, `repetir`, um easing so, atraso constante.

def versao_antes(y0: float) -> list[dict]:
    return [
        {"tipo": "texto", "texto": "ANTES", "tamanho": 30, "peso": 800,
         "cor": CINZA, "espacamento": 4, "y": y0 + 300},
        {
            "tipo": "elipse", "raio": 7, "cor": AZUL,
            "x": 0, "y": y0,
            "opacidade": [[T_SNAP, 0], [T_SNAP + 0.12, 1]],
            # o easing unico, o overshoot unico, iguais para os 45
            "escala": [[T_SNAP, 0], [T_SNAP + 0.34, 1, "outBack"]],
            "repetir": {"cols": COLS, "linhas": LINHAS, "espX": ESP, "espY": ESP,
                        "atraso": 0.03, "ordem": "centro"},
        },
    ]


# ══ EMBAIXO: com oficio ═══════════════════════════════════════════════
# 45 camadas, cada uma com a sua curva, o seu tempo e a sua trajetoria.

_EASINGS = ["outBack", "outElastic", "outQuint", "outCirc"]


def versao_depois(y0: float) -> list[dict]:
    camadas = [{"tipo": "texto", "texto": "DEPOIS", "tamanho": 30, "peso": 800,
                "cor": ROXO, "espacamento": 4, "y": y0 + 300}]
    n = COLS * LINHAS
    for i in range(n):
        ax, ay = _alvo(i)
        ox, oy = _origem(i)
        # 3. RITMO: o atraso acelera. Os primeiros demoram, os ultimos pipocam.
        #    `k**1.7` comprime o fim — quem percebe o padrao vai ficando rapido.
        k = (abs(ax) + abs(ay)) / (ESP * (COLS + LINHAS) / 2)
        d = T_SNAP + 0.55 * (k ** 1.7)

        e = _EASINGS[i % len(_EASINGS)]          # 2. easing POR elemento
        camadas.append({
            "tipo": "elipse", "raio": 7, "cor": AZUL,
            # 4. ARCO: x e y com curvas diferentes. Mesma curva nos dois eixos
            #    da linha reta — e linha reta e o que parece robo.
            "x": [[0, ox], [d - 0.18, ox * 1.12, "inOutSine"],
                  [d + 0.42, ax, e]],
            "y": [[0, oy + y0], [d - 0.18, (oy + y0) * 1.06, "inOutQuad"],
                  [d + 0.52, ay + y0, "outQuint"]],
            # 1. ANTECIPACAO: encolhe um pouco ANTES de encaixar, e so entao
            #    cresce. E o "puxar para trás" que faz o encaixe ter peso.
            "escala": [[0, 0.55], [d - 0.18, 0.34, "inOutSine"],
                       [d + 0.30, 1.18, e], [d + 0.52, 1.0, "outQuad"]],
            "opacidade": [[0, 0.35], [d - 0.2, 0.55], [d + 0.2, 1]],
        })

    # ACAO SOBREPOSTA: as ligacoes chegam DEPOIS que os pontos assentam, e cada
    # uma com o seu tempo. No `antes` elas nem existiriam — sairiam todas juntas.
    for i in range(n):
        c, l = i % COLS, i // COLS
        if c == COLS - 1:
            continue
        ax, ay = _alvo(i)
        k = (abs(ax) + abs(ay)) / (ESP * (COLS + LINHAS) / 2)
        d = T_SNAP + 0.55 * (k ** 1.7) + 0.42
        camadas.append({
            "tipo": "retangulo", "larg": ESP, "alt": 2, "cor": ROXO,
            "x": ax + ESP / 2, "y": ay + y0,
            "opacidade": [[d, 0], [d + 0.16, 0.5]],
            "escalaX": [[d, 0], [d + 0.34, 1, "outCirc"]],
        })
    return camadas


def cena() -> dict:
    return {"duracao": DUR, "fundo": CARVAO, "camadas": [
        *versao_antes(+430),
        {"tipo": "retangulo", "larg": 900, "alt": 1, "cor": "#2A2E3A", "y": 0,
         "opacidade": 0.6},
        *versao_depois(-430),
    ]}


def renderizar() -> Path:
    spec = cena()
    erros = validar(spec)
    if erros:
        print("  " + "\n  ".join(erros[:5]))
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
    print(f"[Comparar] {n} frames em {time.time()-t0:.1f}s -> {SAIDA}")
    return SAIDA


if __name__ == "__main__":
    renderizar()
