# -*- coding: utf-8 -*-
"""linha.py — 3,5 s. A linha do tempo.

Equivale a `EditorScene`: a interface de edicao ocupando o quadro, com o
cabecote correndo. Aqui sao as cinco trilhas que o Klipe tem — video, dois
b-rolls, audio com onda e SFX picado — dentro de uma janela de aplicativo.

Os clipes entram por `escalaX` a partir da borda esquerda, nao do centro: um
clipe que cresce pros dois lados nao parece um clipe, parece um balao.
"""
from .base import *

TRILHAS = [
    ("VIDEO",    AZUL,  [(0, 1000)]),
    ("B-ROLL 1", VERDE, [(14, 134), (160, 116), (288, 96), (396, 122),
                         (530, 192), (736, 128)]),
    ("B-ROLL 2", VERDE, [(38, 77), (141, 84), (449, 90), (641, 103)]),
    ("AUDIO",    CIANO, [(0, 1000)]),
    ("SFX",      MARCA, [(115, 38), (269, 32), (333, 45), (487, 35),
                         (577, 42), (756, 32), (846, 38)]),
]
LARG_J, ALT_J = 1620, 560
Y_J = -20
X0, LARG = -640, 1290           # a area de clipes, dentro da janela
ESC = LARG / 1000.0


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.22)
    C.append(brilho(0, -20, 980, AZUL + "16", 0.0, 0.45, 141))
    C.append(marca_dagua("EDITOR", 420, AZUL, -5, 0.032, 0))
    C += particulas(14, AZUL, CIANO, 13, 143)

    C.append(rotulo("LINHA DO TEMPO", 0.08, 448, AZUL, 24))
    C += titulo("Cinco trilhas, um arquivo", 0.2, 366, 68, TEXTO, 800)

    C += janela(0, Y_J, LARG_J, ALT_J, 0.35, 145)
    C.append(barra_titulo(0, Y_J, LARG_J, ALT_J, "Klipe NLE  ·  MotionCore",
                          0.35, MUDO_ESCURO))

    # ── a regua ───────────────────────────────────────────────────────────
    for i in range(9):
        x = X0 + i * (LARG / 8)
        seg = i * 10
        C.append({"tipo": "retangulo", "larg": 2, "alt": 12, "cor": DIM,
                  "x": x, "y": 178, "opacidade": entra(0.6 + i * LETRA, 0.2)})
        C.append({"tipo": "texto", "texto": "%02d:%02d" % (seg // 60, seg % 60),
                  "tamanho": 16, "peso": 600, "cor": DIM, "x": x + 32,
                  "y": 200, "opacidade": entra(0.6 + i * LETRA, 0.2)})

    # ── as trilhas ────────────────────────────────────────────────────────
    for k, (nome, cor, clipes) in enumerate(TRILHAS):
        y = 118 - k * 76
        d = 0.7 + k * BLOCO
        C += [
            {"tipo": "retangulo", "larg": 164, "alt": 56, "raio": 8,
             "cor": "#0B0E14", "contorno": BORDA, "contorno_larg": 1,
             **viva(X0 - 112, y, 2, 150 + k), "opacidade": entra(d, 0.25)},
            {"tipo": "texto", "texto": nome, "tamanho": 19, "peso": 800,
             "cor": cor, "espacamento": 1, "x": X0 - 112, "y": y - 2,
             "opacidade": entra(d + 0.06, 0.25)},
        ]
        for j, (off, w) in enumerate(clipes):
            off, w = off * ESC, w * ESC
            de = d + 0.12 + j * LETRA
            C.append({
                "tipo": "retangulo", "larg": w, "alt": 56, "raio": 7,
                "cor": cor + "2E", "contorno": cor + "88", "contorno_larg": 2,
                "x": X0 + off + w / 2, "y": y, "opacidade": entra(de, 0.22),
                "escalaX": {"mola": MOLA_ESTADO, "em": de, "de": 0.0,
                            "para": 1.0}})
        if nome == "AUDIO":
            n = 64
            passo = (LARG - 24) / (n - 1)
            for j in range(n):
                h = 8 + 30 * abs(((j * 37) % 23) / 23 - 0.5) * 2
                C.append({"tipo": "retangulo", "larg": 4, "alt": h, "raio": 2,
                          "cor": CIANO + "AA", "x": X0 + 12 + j * passo,
                          "y": y, "opacidade": entra(d + 0.3 + j * 0.004, 0.2)})

    # ── o cabecote ────────────────────────────────────────────────────────
    C.append({"tipo": "retangulo", "larg": 3, "alt": 420, "cor": VERM,
              "y": -32, "x": [[0.85, X0], [dur - 0.3, X0 + LARG, "inOutCubic"]],
              "opacidade": [[0.85, 0], [1.0, 1]]})
    C.append({"tipo": "elipse", "raio": 8, "cor": VERM, "y": 180,
              "x": [[0.85, X0], [dur - 0.3, X0 + LARG, "inOutCubic"]],
              "opacidade": [[0.85, 0], [1.0, 1]]})

    C.append(rotulo("VIDEO  ·  B-ROLL  ·  AUDIO  ·  SFX  ·  LEGENDA",
                    fim(dur, 0, 2), -330, MUDO, 22))
    C.append(rotulo("O QUE VOCE VE NO PREVIEW E O QUE O RENDER FAZ",
                    fim(dur, 1, 2), -385, MUDO_ESCURO, 19))

    return {"duracao": dur, "fundo": BG, "camadas": C}
