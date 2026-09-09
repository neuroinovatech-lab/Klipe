# -*- coding: utf-8 -*-
"""som.py — 3,5 s. Som: o que existe e o que se faz.

Equivale a `AudioGenerationScene`: onda pulsando, cartoes de som entrando em
cascata. A diferenca de postura esta na cena: o Klipe prefere som PRONTO. O
gerador existe, mora fora do editor e vem DESLIGADO — e a cena diz isso, com
o interruptor desenhado na posicao certa.

A duracao de um SFX se MEDE com ffprobe, nunca se chuta. Os numeros dos
cartoes aqui sao os que estao nos arquivos.
"""
from .base import *

SONS = [("Boom", "2.7s", VERM), ("Riser", "3.8s", MARCA),
        ("Whoosh", "0.9s", CIANO), ("Click", "0.085s", VERDE),
        ("Impact", "1.4s", ROXO)]
N_ONDA = 68


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.28)
    C.append(brilho(0, 120, 940, CIANO + "1A", 0.0, 0.45, 101))
    C.append(marca_dagua("SOM", 440, CIANO, -6, 0.035, 0))
    C += particulas(18, CIANO, ROXO, 15, 103)

    C.append(rotulo("AUDIO", 0.08, 440, CIANO, 24))
    C += titulo("Biblioteca primeiro", 0.2, 350, 74, TEXTO, 800)

    # ── a onda circular: aneis pulsando em volta do centro ────────────────
    for i in range(N_ONDA):
        ang = i * (360.0 / N_ONDA)
        r = 150
        import math
        rad = math.radians(ang)
        h = 22 + 46 * abs(((i * 31) % 19) / 19 - 0.5) * 2
        C.append({
            "tipo": "retangulo", "larg": 5, "alt": h, "raio": 3,
            "cor": CIANO + "88", "rotacao": -ang,
            "x": r * math.cos(rad), "y": 110 + r * math.sin(rad),
            "opacidade": entra(0.5 + i * 0.006, 0.25),
            "escalaY": pulso(1.0, 0.35, 0.05, 200 + i)})
    C.append({"tipo": "elipse", "raio": 108, "cor": "#00000000",
              "contorno": CIANO + "44", "contorno_larg": 2, "y": 110,
              "opacidade": entra(0.45, 0.3)})
    C.append({"tipo": "texto", "texto": "SFX", "tamanho": 46, "peso": 900,
              "cor": CIANO, "espacamento": 3, "y": 106,
              "opacidade": entra(0.7, 0.3),
              "escala": {"mola": MOLA_DESTAQUE, "em": 0.7, "de": 0.5,
                         "para": 1.0}})

    # ── os cartoes de som ─────────────────────────────────────────────────
    largs = [max(160, larg_texto(n, 26) + 90) for n, _d, _c in SONS]
    total = sum(largs) + 22 * (len(SONS) - 1)
    x = -total / 2
    for i, (nome, durs, cor) in enumerate(SONS):
        w = largs[i]
        cx = x + w / 2
        t = 0.82 + i * (1.5 * BLOCO)
        C += sombra(cx, -128, w, 108, t, raio=12, n=2)
        C.append(card(cx, -128, w, 108, t, BG_SUP, cor + "44", 12, 110 + i))
        C.append({"tipo": "texto", "texto": nome, "tamanho": 26, "peso": 800,
                  "cor": TEXTO, "x": cx, "y": -110,
                  "opacidade": entra(t + 0.12, 0.25)})
        C.append({"tipo": "texto", "texto": durs, "tamanho": 20, "peso": 600,
                  "cor": cor, "x": cx, "y": -152,
                  "opacidade": entra(t + 0.2, 0.25)})
        x += w + 22

    # ── o interruptor do gerador, DESLIGADO ───────────────────────────────
    T_SW = fim(dur) - 0.2
    C.append({"tipo": "retangulo", "larg": 76, "alt": 40, "raio": 20,
              "cor": "#FFFFFF14", "contorno": BORDA, "contorno_larg": 1,
              "x": -258, "y": -288, "opacidade": entra(T_SW, 0.25)})
    C.append({"tipo": "elipse", "raio": 15, "cor": MUDO_ESCURO, "x": -276,
              "y": -288, "opacidade": entra(T_SW + 0.06, 0.25)})
    C.append({"tipo": "texto", "texto": "gerador de som",
              "tamanho": 24, "peso": 700, "cor": MUDO, "x": -70, "y": -290,
              "opacidade": entra(T_SW + 0.1, 0.25)})
    C.append({"tipo": "texto", "texto": "desligado por padrao",
              "tamanho": 20, "peso": 600, "cor": DIM, "x": 220, "y": -290,
              "opacidade": entra(T_SW + 0.18, 0.25)})

    C.append(rotulo("SOM PRONTO QUASE SEMPRE GANHA DE SOM GERADO",
                    fim(dur), -370, MUDO_ESCURO, 20))

    return {"duracao": dur, "fundo": BG, "camadas": C}
