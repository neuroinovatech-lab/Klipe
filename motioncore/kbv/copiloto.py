# -*- coding: utf-8 -*-
"""copiloto.py — 3,0 s. Dois caminhos, uma implementacao.

Equivale a `CollaborationScene`: ali dois cursores mexem no mesmo documento;
aqui sao dois clientes falando com o mesmo conjunto de ferramentas. O chat que
mora dentro do Klipe e o Claude Code que fala de fora por MCP chegam no MESMO
lugar — e o lugar e um so, nao duas copias que divergem.

O gesto e a convergencia: as duas caixas entram pelas bordas, as arestas se
desenham pra dentro, e o bloco do meio so acende quando as duas chegaram.
"""
from .base import *

FERR = ["cortar", "zoom", "b-roll", "legenda", "SFX", "titulo",
        "render", "shorts", "gravar"]


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.3)
    C.append(brilho(-520, 60, 640, AZUL + "22", 0.0, 0.45, 41))
    C.append(brilho(520, 60, 640, ROXO + "22", 0.15, 0.45, 43))
    C.append(marca_dagua("COPILOTO", 380, MARCA, -6, 0.035, 0))
    C += particulas(20, AZUL, ROXO, 16, 45)

    C.append(rotulo("UMA IMPLEMENTACAO", 0.08, 430, MARCA, 24))
    C += titulo("Por dentro e por fora", 0.2, 340, 74, TEXTO, 800)

    # ── os dois clientes ──────────────────────────────────────────────────
    lados = [(-560, "CHAT", "dentro do Klipe", AZUL, 0.45),
             (560, "MCP", "Claude Code, de fora", ROXO, 0.62)]
    for i, (x, nome, sub, cor, t) in enumerate(lados):
        C += no(x, 60, 420, 200, t, cor, 50 + i)
        C.append({"tipo": "texto", "texto": nome, "tamanho": 52, "peso": 900,
                  "cor": cor, "espacamento": 2, "x": x, "y": 82,
                  "opacidade": entra(t + 0.15, 0.25)})
        C.append({"tipo": "texto", "texto": sub, "tamanho": 21, "peso": 500,
                  "cor": MUDO, "x": x, "y": 16,
                  "opacidade": entra(t + 0.25, 0.25)})
        # a aresta entrando: sai da caixa e chega no meio
        C.append(aresta(x + (210 if x < 0 else -210), 60,
                        (-190 if x < 0 else 190), 60, t + 0.35,
                        cor + "AA", 0.32))

    # ── o bloco do meio: as ferramentas ───────────────────────────────────
    T_MEIO = 1.15
    C += no(0, 60, 340, 200, T_MEIO, MARCA, 55)
    C.append({"tipo": "texto", "texto": "18", "tamanho": 92, "peso": 900,
              "cor": MARCA, "x": 0, "y": 92,
              "opacidade": entra(T_MEIO + 0.1, 0.25),
              "escala": {"mola": MOLA_DESTAQUE, "em": T_MEIO + 0.1,
                         "de": 0.6, "para": 1.0}})
    C.append({"tipo": "texto", "texto": "ferramentas", "tamanho": 24,
              "peso": 600, "cor": MUDO, "x": 0, "y": 12,
              "opacidade": entra(T_MEIO + 0.28, 0.25)})

    # ── as ferramentas espalhadas embaixo, entrando em cascata ────────────
    largs = [larg_texto(f, 22) + 44 for f in FERR]
    total = sum(largs) + 14 * (len(FERR) - 1)
    x = -total / 2
    for i, f in enumerate(FERR):
        w = largs[i]
        d = 1.02 + i * (0.4 * BLOCO)
        C.append({"tipo": "retangulo", "larg": w, "alt": 46, "raio": 23,
                  "cor": "#FFFFFF0A", "contorno": MARCA + "44",
                  "contorno_larg": 1, "x": x + w / 2, "y": -130,
                  "opacidade": entra(d, 0.25),
                  "escala": {"mola": MOLA_TEXTO, "em": d, "de": 0.8,
                             "para": 1.0}})
        C.append({"tipo": "texto", "texto": f, "tamanho": 22, "peso": 700,
                  "cor": MUDO, "x": x + w / 2, "y": -132,
                  "opacidade": entra(d + 0.06, 0.25)})
        x += w + 14

    C.append(rotulo("O QUE VOCE PEDE NO CHAT, O AGENTE DE FORA TAMBEM FAZ",
                    fim(dur, 0, 2), -250, MUDO, 21))
    C.append(rotulo("MESMO CODIGO, NENHUMA CREDENCIAL NO MEIO",
                    fim(dur, 1, 2), -305, MUDO_ESCURO, 18))

    return {"duracao": dur, "fundo": BG, "camadas": C}
