# -*- coding: utf-8 -*-
"""fecho.py — 4,0 s. O fecho.

Equivale a `OutroScene`: a marca volta, os aneis saem dela, e fica o endereco.
O arco fecha onde abriu — mesma marca, mesma sigla, mesmo filete — e a unica
coisa nova e o endereco, que e o que a pessoa precisa levar.

`localhost:3002` e o endereco de verdade. Nao ha site pra visitar nem conta
pra criar: o Klipe sobe na maquina de quem instalou.
"""
from .base import *


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.32)
    C.append(brilho(0, 90, 940, MARCA + "2E", 0.0, 0.55, 261))
    C.append(brilho(-420, -220, 560, AZUL + "1C", 0.3, 0.4, 263))
    C.append(marca_dagua("KLIPE", 500, MARCA, -8, 0.05, 30))
    C += particulas(28, MARCA, AZUL, 20, 265)

    # ── os aneis, com intervalo encurtando ────────────────────────────────
    for i in range(4):
        d = 0.2 + sum(0.5 * (0.84 ** k) for k in range(i))
        C.append({"tipo": "elipse", "raio": 170, "cor": "#00000000",
                  "contorno": MARCA, "contorno_larg": 3, "y": 110,
                  "escala": [[d, 0.3], [d + 2.0, 3.2, "outCubic"]],
                  "opacidade": [[d, 0.7], [d + 2.0, 0]]})

    # ── a marca ───────────────────────────────────────────────────────────
    for lay in titulo("KLIPE", 0.4, 110, 190, TEXTO, 900):
        lay["sombra"] = [{"x": 0, "y": 0, "blur": 70, "cor": MARCA + "44"}]
        C.append(lay)

    C.append({"tipo": "retangulo", "larg": 620, "alt": 6, "raio": 3,
              "cor": MARCA, "y": 0, "opacidade": entra(1.05, 0.2),
              "escalaX": {"mola": MOLA_DESTAQUE, "em": 1.05, "de": 0.0,
                          "para": 1.0}})

    C += sigla(1.3, -68, 30)

    # ── o endereco, dentro de uma barra de navegacao ──────────────────────
    T_END = 2.15
    C += sombra(0, -200, 560, 78, T_END, raio=39, n=2)
    C.append({"tipo": "retangulo", "larg": 560, "alt": 78, "raio": 39,
              "cor": BG_SUP, "contorno": MARCA + "55", "contorno_larg": 2,
              **viva(0, -200, 2, 267), "opacidade": entra(T_END, 0.28),
              "escala": {"mola": MOLA_ESTADO, "em": T_END, "de": 0.9,
                         "para": 1.0}})
    C.append({"tipo": "elipse", "raio": 8, "cor": VERDE, "x": -212, "y": -200,
              "opacidade": entra(T_END + 0.12, 0.25),
              "escala": pulso(1.0, 0.25, 0.05, 268)})
    C.append({"tipo": "texto", "texto": "localhost:3002", "tamanho": 34,
              "peso": 700, "cor": TEXTO, "espacamento": 1, "x": 22, "y": -203,
              "opacidade": entra(T_END + 0.16, 0.28)})

    C.append(rotulo("DOIS CLIQUES E ELE SOBE", fim(dur, 0, 2), -300,
                    MUDO, 22))
    C.append(rotulo("SEM SITE, SEM CONTA, SEM NUVEM", fim(dur, 1, 2),
                    -356, MUDO_ESCURO, 19))

    # ── os cantos de enquadramento, fechando como na abertura ─────────────
    for i, (sx, sy) in enumerate(((-1, 1), (1, 1), (-1, -1), (1, -1))):
        bx, by = sx * 850, sy * 450
        d = 2.0 + i * (0.65 * BLOCO)
        C += [
            {"tipo": "retangulo", "larg": 56, "alt": 3, "cor": MARCA + "88",
             "x": bx + sx * -20, "y": by, "opacidade": entra(d, 0.3),
             "escalaX": {"mola": MOLA_ESTADO, "em": d, "de": 0.0, "para": 1.0}},
            {"tipo": "retangulo", "larg": 3, "alt": 56, "cor": MARCA + "88",
             "x": bx, "y": by + sy * -20, "opacidade": entra(d + 0.05, 0.3),
             "escalaY": {"mola": MOLA_ESTADO, "em": d + 0.05, "de": 0.0,
                         "para": 1.0}},
        ]

    return {"duracao": dur, "fundo": BG, "camadas": C}
