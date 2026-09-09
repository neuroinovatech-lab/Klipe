# -*- coding: utf-8 -*-
"""render.py — 3,5 s. O render.

Equivale a `UpscalingScene`: ali o lado esquerdo esta borrado e o direito
nitido, e uma linha divide os dois. Aqui a divisao e entre o PREVIEW e o
RENDER — e a promessa e que nao ha diferenca nenhuma entre eles.

Essa e a unica frase deste video que e uma promessa de engenharia e nao um
numero: o que voce ve no preview, o render faz. Um editor onde os dois
divergem faz voce renderizar pra descobrir o que fez.
"""
from .base import *

FORMATOS = [("1080p", "1920x1080", VERDE), ("4K", "3840x2160", MARCA),
            ("9:16", "1080x1920", CIANO), ("1:1", "1080x1080", ROXO)]
LARG_J, ALT_J, Y_J = 1300, 460, 70


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.25)
    C.append(brilho(0, 60, 960, VERDE + "18", 0.0, 0.45, 181))
    C.append(marca_dagua("RENDER", 420, VERDE, -6, 0.035, 0))
    C += particulas(18, VERDE, MARCA, 15, 183)

    C.append(rotulo("SAIDA", 0.08, 452, VERDE, 24))
    C += titulo("O preview e o render", 0.2, 366, 72, TEXTO, 800)

    # ── a janela partida ao meio ──────────────────────────────────────────
    C += janela(0, Y_J, LARG_J, ALT_J, 0.35, 185)
    if existe("demo2.jpg"):
        C.append({"tipo": "imagem", "src": asset("demo2.jpg"),
                  "larg": LARG_J - 30, "alt": ALT_J - 70, "ajuste": "cobrir",
                  **viva(0, Y_J - 22, 2, 186), "opacidade": entra(0.55, 0.4)})
    else:
        C.append(card(0, Y_J - 22, LARG_J - 30, ALT_J - 70, 0.55,
                      "#0F1218", BORDA, 8, 186))

    # a linha divisoria, que desce ate o meio e fica
    C.append({"tipo": "retangulo", "larg": 3, "alt": ALT_J - 70, "cor": TEXTO,
              "x": 0, "y": Y_J - 22, "opacidade": entra(0.9, 0.25),
              "escalaY": {"mola": MOLA_ESTADO, "em": 0.9, "de": 0.0,
                          "para": 1.0}})
    for i, (lado, nome, cor) in enumerate(((-1, "PREVIEW", MUDO),
                                           (1, "RENDER", VERDE))):
        x = lado * (LARG_J / 4)
        t = 1.05 + i * (2 * BLOCO)
        C.append({"tipo": "retangulo", "larg": larg_texto(nome, 22) + 44,
                  "alt": 42, "raio": 21, "cor": "#000000AA",
                  "contorno": cor + "77", "contorno_larg": 1,
                  "x": x, "y": Y_J + ALT_J / 2 - 92, "opacidade": entra(t, 0.25)})
        C.append({"tipo": "texto", "texto": nome, "tamanho": 22, "peso": 800,
                  "cor": cor, "espacamento": 2, "x": x,
                  "y": Y_J + ALT_J / 2 - 94, "opacidade": entra(t + 0.06, 0.25)})

    # ── a barra de render correndo ────────────────────────────────────────
    C += barra_prog(0, -190, 1160, 1.25, VERDE, 1.5, 12)
    C.append({"tipo": "texto", "texto": "libx264  ·  crf 18  ·  yuv420p",
              "tamanho": 20, "peso": 600, "cor": DIM, "x": -420, "y": -232,
              "opacidade": entra(1.5, 0.25)})
    for k, (pct, t) in enumerate(((" 0%", 1.2), ("38%", 1.52), ("74%", 1.86),
                                  ("100%", 2.2))):
        C.append({"tipo": "texto", "texto": pct, "tamanho": 22, "peso": 800,
                  "cor": VERDE if k == 3 else MUDO, "x": 470, "y": -232,
                  "opacidade": [[t, 0], [t + 0.06, 1]] +
                               ([[t + 0.4, 1], [t + 0.46, 0]] if k < 3 else [])})

    # ── os formatos ───────────────────────────────────────────────────────
    for i, (nome, res, cor) in enumerate(FORMATOS):
        x = -570 + i * 380
        t = 1.6 + i * (0.8 * BLOCO)
        C.append({"tipo": "retangulo", "larg": 330, "alt": 92, "raio": 12,
                  "cor": BG_SUP, "contorno": cor + "44", "contorno_larg": 1,
                  **viva(x, -320, 2, 190 + i), "opacidade": entra(t, 0.25),
                  "escala": {"mola": MOLA_ESTADO, "em": t, "de": 0.9,
                             "para": 1.0}})
        C.append({"tipo": "texto", "texto": nome, "tamanho": 27, "peso": 900,
                  "cor": cor, "x": x - 80, "y": -320,
                  "opacidade": entra(t + 0.1, 0.25)})
        C.append({"tipo": "texto", "texto": res, "tamanho": 19, "peso": 600,
                  "cor": DIM, "x": x + 60, "y": -322,
                  "opacidade": entra(t + 0.16, 0.25)})

    C.append(rotulo("O QUE VOCE VE NO PREVIEW, O RENDER FAZ",
                    fim(dur), -420, MUDO, 22))

    return {"duracao": dur, "fundo": BG, "camadas": C}
