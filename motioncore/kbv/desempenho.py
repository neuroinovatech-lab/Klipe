# -*- coding: utf-8 -*-
"""desempenho.py — 2,5 s. Um numero.

Equivale a `PerformanceScene`, a cena mais curta da referencia: dois segundos e
meio, um numero gigante, nada mais. E a licao de ritmo mais util que tirei
dali — cena de UMA mensagem pode ser curta, e a brevidade E o efeito.

O numero foi medido: 32 s pra renderizar 70 s de video, com b-roll, legenda,
zoom e SFX, nesta maquina. Nao e marketing, e o log.
"""
from .base import *


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.3)
    C.append(brilho(0, 60, 900, MARCA + "2A", 0.0, 0.55, 221))
    C.append(marca_dagua("GPU", 480, MARCA, -8, 0.045, 0))
    C += particulas(26, MARCA, VERM, 20, 223)

    # aneis saindo do numero — o unico pulo da cena esta no proprio numero
    for i in range(3):
        d = 0.25 + sum(0.42 * (0.85 ** k) for k in range(i))
        C.append({"tipo": "elipse", "raio": 200, "cor": "#00000000",
                  "contorno": MARCA, "contorno_larg": 3, "y": 60,
                  "escala": [[d, 0.35], [d + 1.6, 2.6, "outCubic"]],
                  "opacidade": [[d, 0.5], [d + 1.6, 0]]})

    C.append(rotulo("DESEMPENHO", 0.08, 372, MARCA, 24))

    # o numero: familia DESTAQUE, o unico quique
    C.append({"tipo": "texto", "texto": "32", "tamanho": 300, "peso": 900,
              "cor": TEXTO, "x": -52, **viva(-52, 60, 3, 225),
              "opacidade": entra(0.2, 0.22),
              "escala": {"mola": MOLA_DESTAQUE, "em": 0.2, "de": 0.7,
                         "para": 1.0},
              "sombra": [{"x": 0, "y": 0, "blur": 80, "cor": MARCA + "55"}]})
    C.append({"tipo": "texto", "texto": "s", "tamanho": 150, "peso": 800,
              "cor": MARCA, **viva(140, 24, 2, 226),
              "opacidade": entra(0.42, 0.25),
              "escala": {"mola": MOLA_TEXTO, "em": 0.42, "de": 0.6,
                         "para": 1.0}})

    C.append({"tipo": "retangulo", "larg": 560, "alt": 4, "raio": 2,
              "cor": MARCA, "y": -110, "opacidade": entra(0.7, 0.2),
              "escalaX": {"mola": MOLA_ESTADO, "em": 0.7, "de": 0.0,
                          "para": 1.0}})

    C.append(rotulo("PARA RENDERIZAR 70 SEGUNDOS DE VIDEO", 0.72, -180,
                    MUDO, 26))
    C.append(rotulo("COM B-ROLL, LEGENDA, ZOOM E SFX", 0.95, -238,
                    MUDO_ESCURO, 20))

    # as quatro coisas que estavam no render, entrando em cascata
    for i, (nome, cor) in enumerate((("b-roll", VERDE), ("legenda", CIANO),
                                     ("zoom", AZUL), ("SFX", ROXO))):
        x = -360 + i * 240
        t = 0.92 + i * (0.55 * BLOCO)
        w = larg_texto(nome, 22) + 50
        C.append({"tipo": "retangulo", "larg": w, "alt": 46, "raio": 23,
                  "cor": cor + "1A", "contorno": cor + "66",
                  "contorno_larg": 1, "x": x, "y": -320,
                  "opacidade": entra(t, 0.25),
                  "escala": {"mola": MOLA_TEXTO, "em": t, "de": 0.8,
                             "para": 1.0}})
        C.append({"tipo": "texto", "texto": nome, "tamanho": 22, "peso": 700,
                  "cor": cor, "x": x, "y": -322,
                  "opacidade": entra(t + 0.06, 0.25)})

    return {"duracao": dur, "fundo": BG, "camadas": C}
