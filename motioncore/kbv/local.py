# -*- coding: utf-8 -*-
"""local.py — 3,5 s. A conta.

Equivale a `OpenSourceScene`. Ela e uma das cenas de FUNDO CLARO, mas isso nao
esta escrito aqui: a inversao mora em `montar.py`, que aplica `claro()` nas
cenas marcadas. Assim a cena existe uma vez so, e clara e escura nunca
divergem quando eu mexo numa delas.

O conteudo aqui e a conta. Cada linha e um custo medido nesta maquina, e as
tres primeiras sao zero porque rodam na sua GPU e no seu Whisper. So a
deteccao por IA custa, e custa duas decimas de milesimo de dolar.
"""
from .base import *

LINHAS = [("Render de 70 segundos de video", "US$ 0,00", VERDE),
          ("Transcricao de 287 palavras", "US$ 0,00", VERDE),
          ("Motion graphics, 955 camadas", "US$ 0,00", VERDE),
          ("Deteccao de shorts por IA", "US$ 0,0002", MARCA)]



def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.28)
    C.append(brilho(0, 0, 980, MARCA + "18", 0.0, 0.45, 241))
    C += particulas(16, MARCA, VERDE, 14, 243)
    C.append(marca_dagua("SEU PC", 400, MARCA, 8, 0.04, 0))

    C.append(rotulo("TRANSPARENCIA", 0.08, 434, MARCA, 24))
    for lay in titulo("Voce ve o que gasta", 0.2, 340, 82, TEXTO, 900):
        C.append(lay)

    for i, (o_que, quanto, cor) in enumerate(LINHAS):
        y = 168 - i * 104
        t = 0.6 + i * (3 * BLOCO)
        C += sombra(0, y, 1180, 82, t, raio=14, n=2)
        C.append({"tipo": "retangulo", "larg": 1180, "alt": 82, "raio": 14,
                  "cor": BG_SUP, "contorno": BORDA,
                  "contorno_larg": 1, **viva(0, y, 2, 250 + i),
                  "opacidade": entra(t, 0.25),
                  "escala": {"mola": MOLA_ESTADO, "em": t, "de": 0.94,
                             "para": 1.0}})
        C.append({"tipo": "elipse", "raio": 7, "cor": cor, "x": -520, "y": y,
                  "opacidade": entra(t + 0.08, 0.25)})
        C.append({"tipo": "texto", "texto": o_que, "tamanho": 29, "peso": 600,
                  "cor": MUDO, "x": -190, "y": y - 2,
                  "opacidade": entra(t + 0.1, 0.25)})
        C.append({"tipo": "texto", "texto": quanto, "tamanho": 32, "peso": 900,
                  "cor": cor, "x": 430, "y": y - 2,
                  "opacidade": entra(t + 0.16, 0.25)})

    # ── as tres garantias ─────────────────────────────────────────────────
    for i, (nome, sub) in enumerate((("SUA CHAVE", "cada um poe a dele"),
                                     ("SUA MAQUINA", "nada sobe pra nuvem"),
                                     ("SEU CUSTO", "contado por segundo"))):
        x = -460 + i * 460
        t = 1.6 + i * (1.15 * BLOCO)
        C.append({"tipo": "texto", "texto": nome, "tamanho": 27, "peso": 900,
                  "cor": TEXTO, "espacamento": 1, "x": x, "y": -300,
                  "opacidade": entra(t, 0.25),
                  "escala": {"mola": MOLA_TEXTO, "em": t, "de": 0.85,
                             "para": 1.0}})
        C.append({"tipo": "texto", "texto": sub, "tamanho": 20, "peso": 500,
                  "cor": MUDO, "x": x, "y": -344,
                  "opacidade": entra(t + 0.1, 0.25)})
        if i < 2:
            C.append({"tipo": "retangulo", "larg": 2, "alt": 62,
                      "cor": BORDA, "x": x + 230, "y": -318,
                      "opacidade": entra(t + 0.14, 0.25)})

    C.append(rotulo("O KLIPE CONTA OS SEGUNDOS COM EXATIDAO", fim(dur),
                    -412, MUDO_ESCURO, 20))

    return {"duracao": dur, "fundo": BG, "camadas": C}
