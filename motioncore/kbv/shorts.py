# -*- coding: utf-8 -*-
"""shorts.py — 3,5 s. Varios cortes de uma vez.

Equivale a `BatchGenerationScene`: ali uma grade de imagens gerando em
paralelo, cada uma terminando no seu tempo. Aqui sao os trechos que a IA achou
no video longo — cada cartao com a nota que ela deu e o recorte ja em 9:16.

O importante da cena e a palavra HIBRIDO: a IA acha e propoe, e voce ajusta.
O botao de detectar sozinho nunca acerta o suficiente pra decidir por voce.
"""
from .base import *

# a nota e o instante de cada trecho, no formato que a deteccao devolve
TRECHOS = [("00:14", "92", VERDE), ("01:07", "88", VERDE),
           ("02:31", "81", MARCA), ("04:02", "76", MARCA),
           ("05:48", "71", MUDO)]
LARG_C, ALT_C = 226, 402


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.26)
    C.append(brilho(0, 20, 980, MARCA + "1A", 0.0, 0.45, 201))
    C.append(marca_dagua("SHORTS", 420, MARCA, -6, 0.035, 0))
    C += particulas(20, MARCA, VERDE, 16, 203)

    C.append(rotulo("VERTICAL", 0.08, 458, MARCA, 24))
    C += titulo("A IA acha, voce ajusta", 0.2, 372, 72, TEXTO, 800)

    for i, (marca_t, nota, cor) in enumerate(TRECHOS):
        x = -(LARG_C + 44) * (len(TRECHOS) - 1) / 2 + i * (LARG_C + 44)
        t = 0.38 + i * (1.6 * BLOCO)

        C += sombra(x, 20, LARG_C, ALT_C, t, raio=14, n=2)
        C.append(card(x, 20, LARG_C, ALT_C, t, BG_SUP, cor + "44", 14, 210 + i))
        # o recorte 9:16 por dentro, com um quadro DE VERDADE.
        # Os dois se alternam porque os cinco shorts saem do MESMO video longo
        # — cartao com foto diferente em cada um contaria outra historia.
        C.append({"tipo": "retangulo", "larg": LARG_C - 22, "alt": ALT_C - 96,
                  "raio": 8, "cor": "#0A0C11", "x": x, "y": 44,
                  "opacidade": entra(t + 0.1, 0.25)})
        quadro = "demo1.jpg" if i % 2 == 0 else "demo2.jpg"
        if existe(quadro):
            C.append({"tipo": "imagem", "src": asset(quadro),
                      "larg": LARG_C - 22, "alt": ALT_C - 96, "ajuste": "cobrir",
                      "x": x, "y": 44, "opacidade": entra(t + 0.14, 0.3)})
        # a moldura de rosto: o corte segue a CARA, nao o centro do quadro
        C.append({"tipo": "retangulo", "larg": 92, "alt": 108, "raio": 8,
                  "cor": "#00000000", "contorno": cor, "contorno_larg": 2,
                  "x": x + (12 if i % 2 else -14), "y": 108,
                  "traco": [[t + 0.4, 0.0, "outCubic"], [t + 0.75, 1.0]],
                  "opacidade": [[t + 0.4, 0], [t + 0.5, 0.9]]})
        C.append({"tipo": "texto", "texto": "rosto", "tamanho": 14,
                  "peso": 700, "cor": cor,
                  "x": x + (12 if i % 2 else -14), "y": 38,
                  "opacidade": entra(t + 0.6, 0.25)})
        # a legenda queimada, embaixo do recorte
        for j in range(2):
            C.append({"tipo": "retangulo", "larg": (120 if j else 158),
                      "alt": 11, "raio": 5, "cor": TEXTO + "55", "x": x,
                      "y": -74 - j * 20, "opacidade": entra(t + 0.55, 0.25)})
        # o instante e a nota
        C.append({"tipo": "texto", "texto": marca_t, "tamanho": 20,
                  "peso": 700, "cor": MUDO, "x": x - 52, "y": -140,
                  "opacidade": entra(t + 0.24, 0.25)})
        C.append({"tipo": "elipse", "raio": 24, "cor": cor + "26",
                  "contorno": cor + "88", "contorno_larg": 2, "x": x + 58,
                  "y": -136, "opacidade": entra(t + 0.3, 0.25),
                  "escala": {"mola": MOLA_TEXTO, "em": t + 0.3, "de": 0.0,
                             "para": 1.0}})
        C.append({"tipo": "texto", "texto": nota, "tamanho": 21, "peso": 900,
                  "cor": cor, "x": x + 58, "y": -143,
                  "opacidade": entra(t + 0.38, 0.25)})
        # a barra de nota
        C.append({"tipo": "retangulo", "larg": LARG_C - 40, "alt": 5,
                  "raio": 3, "cor": "#FFFFFF14", "x": x, "y": -178,
                  "opacidade": entra(t + 0.42, 0.25)})
        frac = int(nota) / 100.0
        C.append({"tipo": "retangulo", "larg": (LARG_C - 40) * frac, "alt": 5,
                  "raio": 3, "cor": cor,
                  "x": x - (LARG_C - 40) * (1 - frac) / 2, "y": -178,
                  "opacidade": entra(t + 0.42, 0.25),
                  "escalaX": [[t + 0.42, 0.0], [t + 1.0, 1.0, "outCubic"]]})

    C.append(rotulo("DETECCAO POR IA: US$ 0,0002 NO VIDEO INTEIRO",
                    fim(dur, 0, 2), -290, MARCA, 22))
    C.append(rotulo("O CORTE SEGUE O ROSTO, NAO O CENTRO DO QUADRO",
                    fim(dur, 1, 2), -348, MUDO_ESCURO, 19))

    return {"duracao": dur, "fundo": BG, "camadas": C}
