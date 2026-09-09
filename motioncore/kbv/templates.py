# -*- coding: utf-8 -*-
"""templates.py — 3,0 s. A galeria.

Equivale a `TemplatesScene`: uma grade de cartoes que entra em cascata, com o
rotulo da familia em cada um. Ali sao templates de imagem; aqui sao as nove
categorias de titulo do Klipe.

A amostra de cada cartao DESCREVE O EFEITO — "cada palavra no seu tempo",
"letra por letra". A biblioteca antiga tinha 23 templates e as 23 amostras
vinham do mesmo video de um cliente, e era dai que vinha o vies: quem abre a
galeria pra escolher ve aquele mundo, e e aquele mundo que sai do outro lado.
"""
from .base import *

# as nove categorias reais de public/title_templates.json
CATS = [
    ("REVELACAO",  "4", "como o texto chega",   MARCA),
    ("ENFASE",     "3", "o que fica grande",    VERM),
    ("ROTULO",     "2", "acompanha sem roubar", CIANO),
    ("DADO",       "2", "numero na tela",       VERDE),
    ("CITACAO",    "2", "frase entre aspas",    ROXO),
    ("COMPOSTO",   "4", "tres tempos numa peca", AZUL),
    ("LISTA",      "2", "titulo mais itens",    MARCA_CLARA),
    ("TELA CHEIA", "4", "ocupa o quadro",       VERM),
    ("DO ZERO",    "3", "monta parte a parte",  MUDO),
]
LARG_C, ALT_C = 396, 168
PASSO_X, PASSO_Y = 424, 196


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.3)
    C.append(brilho(0, 20, 940, MARCA + "1A", 0.0, 0.45, 21))
    C.append(marca_dagua("TITULOS", 420, MARCA, -7, 0.04, 0))
    C += particulas(20, MARCA, ROXO, 15, 23)

    C.append(rotulo("BIBLIOTECA", 0.08, 430, MARCA, 24))
    C += titulo("26 templates, 9 familias", 0.2, 336, 72, TEXTO, 800)

    # ── a grade 3x3, cascata a partir do centro ───────────────────────────
    for i, (nome, n, sub, cor) in enumerate(CATS):
        col, lin = i % 3, i // 3
        x = (col - 1) * PASSO_X
        y = 130 - lin * PASSO_Y
        # a escada irradia do meio: distancia de Manhattan ao centro da grade
        d = 0.45 + (abs(col - 1) + abs(lin - 1)) * (2 * BLOCO)

        C += sombra(x, y, LARG_C, ALT_C, d, raio=14, n=2)
        C.append(card(x, y, LARG_C, ALT_C, d, BG_SUP, cor + "33", 14, 40 + i))
        # a faixa de cor na borda de cima — o que separa uma familia da outra
        C.append({"tipo": "retangulo", "larg": LARG_C - 26, "alt": 4, "raio": 2,
                  "cor": cor, "x": x, "y": y + ALT_C / 2 - 16,
                  "opacidade": entra(d + 0.1, 0.25),
                  "escalaX": {"mola": MOLA_ESTADO, "em": d + 0.1, "de": 0.0,
                              "para": 1.0}})
        C.append({"tipo": "texto", "texto": nome, "tamanho": 27, "peso": 900,
                  "cor": TEXTO, "espacamento": 1, "x": x - 22, "y": y + 22,
                  "opacidade": entra(d + 0.16, 0.25)})
        # a contagem, num circulo na direita
        C.append({"tipo": "elipse", "raio": 22, "cor": cor + "26",
                  "contorno": cor + "77", "contorno_larg": 2,
                  "x": x + LARG_C / 2 - 42, "y": y + 22,
                  "opacidade": entra(d + 0.2, 0.25),
                  "escala": {"mola": MOLA_TEXTO, "em": d + 0.2, "de": 0.0,
                             "para": 1.0}})
        C.append({"tipo": "texto", "texto": n, "tamanho": 22, "peso": 900,
                  "cor": cor, "x": x + LARG_C / 2 - 42, "y": y + 14,
                  "opacidade": entra(d + 0.26, 0.25)})
        C.append({"tipo": "texto", "texto": sub, "tamanho": 19, "peso": 500,
                  "cor": MUDO, "x": x, "y": y - 32,
                  "opacidade": entra(d + 0.3, 0.25)})

    C.append(rotulo("A AMOSTRA DESCREVE O EFEITO, NAO UM VIDEO",
                    fim(dur), -420, MUDO_ESCURO, 20))

    return {"duracao": dur, "fundo": BG, "camadas": C}
