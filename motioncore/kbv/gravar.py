# -*- coding: utf-8 -*-
"""gravar.py — 3,0 s. A gravacao.

Equivale a `RecorderScene`: a moldura de captura, o ponto vermelho piscando, o
contador correndo. Ali grava a tela do produto; aqui grava a SUA tela, a sua
camera, ou as duas juntas — e tem teleprompter, que e o que falta em quase
todo gravador de tela.

O ponto vermelho pisca por keyframes repetidos, nao por ruido: pisca de
gravacao tem periodo fixo, e ruido daria uma irregularidade que le como falha.
"""
from .base import *

MODOS = [("TELA", "a janela inteira", AZUL),
         ("CAMERA", "so voce", VERDE),
         ("AS DUAS", "uma sobre a outra", MARCA)]


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.26)
    C.append(brilho(0, 40, 940, VERM + "18", 0.0, 0.45, 121))
    C.append(marca_dagua("REC", 460, VERM, -6, 0.035, 0))
    C += particulas(16, VERM, MARCA, 14, 123)

    C.append(rotulo("GRAVACAO", 0.08, 440, VERM, 24))
    C += titulo("Sem instalar outro programa", 0.2, 350, 70, TEXTO, 800)

    # ── a moldura de captura, com os cantos ───────────────────────────────
    LARG, ALT, Y = 1080, 400, 60
    C += janela(0, Y, LARG, ALT, 0.42, 125)
    for i, (sx, sy) in enumerate(((-1, 1), (1, 1), (-1, -1), (1, -1))):
        bx = sx * (LARG / 2 - 34)
        by = Y + sy * (ALT / 2 - 34)
        d = 0.8 + i * BLOCO
        C += [
            {"tipo": "retangulo", "larg": 42, "alt": 3, "cor": VERM,
             "x": bx + sx * -14, "y": by, "opacidade": entra(d, 0.25)},
            {"tipo": "retangulo", "larg": 3, "alt": 42, "cor": VERM,
             "x": bx, "y": by + sy * -14, "opacidade": entra(d + 0.04, 0.25)},
        ]

    # ── o ponto de gravacao e o contador ──────────────────────────────────
    piscar: list = []
    t = 0.9
    while t < dur:
        piscar += [[round(t, 3), 1.0], [round(t + 0.45, 3), 1.0],
                   [round(t + 0.5, 3), 0.15], [round(t + 0.9, 3), 0.15],
                   [round(t + 0.95, 3), 1.0]]
        t += 1.0
    C.append({"tipo": "elipse", "raio": 12, "cor": VERM, "x": -300,
              "y": Y + 118, "opacidade": [[0.85, 0]] + piscar})
    C.append({"tipo": "elipse", "raio": 30, "cor": VERM, "blur": 20, "x": -300,
              "y": Y + 118, "opacidade": [[0.85, 0]] +
              [[k[0], k[1] * 0.5] + k[2:] for k in piscar]})
    C.append({"tipo": "texto", "texto": "REC", "tamanho": 28, "peso": 900,
              "cor": VERM, "espacamento": 3, "x": -232, "y": Y + 112,
              "opacidade": entra(0.9, 0.25)})
    # o contador correndo — um numero por segundo, trocando por opacidade
    for s in range(0, 3):
        C.append({"tipo": "texto", "texto": "00:0%d" % s, "tamanho": 28,
                  "peso": 700, "cor": MUDO, "x": -110, "y": Y + 112,
                  "opacidade": [[0.9 + s * 0.42, 0], [0.95 + s * 0.42, 1],
                                [1.3 + s * 0.42, 1], [1.35 + s * 0.42, 0]]})

    # ── o teleprompter, rolando dentro da moldura ─────────────────────────
    ROTEIRO = ["o texto sobe enquanto voce fala",
               "e para onde voce quiser que pare",
               "sem tirar o olho da camera"]
    for i, linha in enumerate(ROTEIRO):
        C.append({"tipo": "texto", "texto": linha, "tamanho": 32,
                  "peso": 700 if i == 1 else 600,
                  "cor": TEXTO if i == 1 else MUDO_ESCURO, "x": 0,
                  "y": [[1.0, Y - 40 - i * 62], [dur, Y + 34 - i * 62,
                                                 "linear"]],
                  "opacidade": entra(0.95 + i * BLOCO, 0.3)})

    # ── os tres modos ─────────────────────────────────────────────────────
    for i, (nome, sub, cor) in enumerate(MODOS):
        x = -430 + i * 430
        t0 = 1.12 + i * (1.2 * BLOCO)
        w = 380
        C += sombra(x, -240, w, 112, t0, raio=14, n=2)
        C.append(card(x, -240, w, 112, t0, BG_SUP, cor + "44", 14, 130 + i))
        C.append({"tipo": "texto", "texto": nome, "tamanho": 28, "peso": 900,
                  "cor": cor, "espacamento": 2, "x": x, "y": -222,
                  "opacidade": entra(t0 + 0.12, 0.25)})
        C.append({"tipo": "texto", "texto": sub, "tamanho": 19, "peso": 500,
                  "cor": MUDO, "x": x, "y": -264,
                  "opacidade": entra(t0 + 0.2, 0.25)})

    C.append(rotulo("COM TELEPROMPTER, E ELE VAI PRA ONDE VOCE QUISER",
                    fim(dur), -350, MUDO_ESCURO, 20))

    return {"duracao": dur, "fundo": BG, "camadas": C}
