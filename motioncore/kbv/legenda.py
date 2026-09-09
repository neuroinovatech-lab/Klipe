# -*- coding: utf-8 -*-
"""legenda.py — 3,5 s. A palavra no instante em que e dita.

Equivale a `TextGenerationScene`: ali o texto se escreve enquanto uma onda
pulsa; aqui a onda E o audio de verdade e cada palavra acende no seu proprio
tempo, que e o que o Whisper devolve com `word_timestamps=True`.

O que faz a cena funcionar e a AMARRA: a palavra que acende esta exatamente
sobre a barra da onda que esta alta. Legenda que nao esta ancorada no que a
pessoa fala e so texto passando por cima do video.
"""
from .base import *

FRASE = ["A", "palavra", "acende", "no", "instante", "em", "que", "e", "dita"]
TAM_P = 52
GAP = 22
N_ONDA = 96
LARG_ONDA = 1560
T0 = 0.62            # quando a primeira palavra acende
PASSO_P = 0.16       # o intervalo entre palavras


def _alt_onda(j: int) -> float:
    """Envelope determinista: cresce e cai em blocos, como fala de verdade."""
    base = abs(((j * 41) % 29) / 29 - 0.5) * 2
    env = 0.35 + 0.65 * abs(((j * 7) % 24) / 24 - 0.5) * 2
    return 10 + 74 * base * env


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.25)
    C.append(brilho(0, -140, 980, CIANO + "1A", 0.0, 0.45, 81))
    C.append(marca_dagua("FALA", 440, CIANO, -6, 0.035, 0))
    C += particulas(18, CIANO, MARCA, 15, 83)

    C.append(rotulo("LEGENDA ANCORADA", 0.08, 440, CIANO, 24))
    C += titulo("287 palavras, 287 tempos", 0.2, 348, 72, TEXTO, 800)

    # ── a onda ────────────────────────────────────────────────────────────
    passo = LARG_ONDA / (N_ONDA - 1)
    x0 = -LARG_ONDA / 2
    for j in range(N_ONDA):
        h = _alt_onda(j)
        # a barra "toca" quando o cabecote passa por ela
        t_toca = T0 + (j / N_ONDA) * (len(FRASE) * PASSO_P)
        C.append({"tipo": "retangulo", "larg": 6, "alt": h, "raio": 3,
                  "cor": CIANO + "55", "x": x0 + j * passo, "y": -130,
                  "opacidade": entra(0.35 + j * 0.003, 0.2)})
        C.append({"tipo": "retangulo", "larg": 6, "alt": h, "raio": 3,
                  "cor": CIANO, "x": x0 + j * passo, "y": -130,
                  "opacidade": [[t_toca, 0], [t_toca + 0.08, 1],
                                [t_toca + 0.5, 0.35]]})

    # ── o cabecote correndo por cima da onda ──────────────────────────────
    t_fim = T0 + len(FRASE) * PASSO_P
    C.append({"tipo": "retangulo", "larg": 3, "alt": 230, "cor": MARCA,
              "y": -130,
              "x": [[T0, x0], [t_fim, x0 + LARG_ONDA, "linear"]],
              "opacidade": [[T0 - 0.1, 0], [T0, 1], [t_fim, 1],
                            [t_fim + 0.25, 0]]})

    # ── a frase: cada palavra acende no seu instante ──────────────────────
    largs = [larg_texto(w, TAM_P) + 30 for w in FRASE]
    total = sum(largs) + GAP * (len(FRASE) - 1)
    x = -total / 2
    for i, w in enumerate(FRASE):
        lw = largs[i]
        cx = x + lw / 2
        t_ac = T0 + i * PASSO_P
        # a versao apagada, sempre na tela desde o comeco
        C.append({"tipo": "texto", "texto": w, "tamanho": TAM_P, "peso": 800,
                  "cor": MUDO_ESCURO, "x": cx, "y": 110,
                  "opacidade": entra(0.4 + i * LETRA, 0.25)})
        # a caixa da ativa
        C.append({"tipo": "retangulo", "larg": lw, "alt": 74, "raio": 10,
                  "cor": MARCA, "x": cx, "y": 108,
                  "opacidade": [[t_ac, 0], [t_ac + 0.06, 1],
                                [t_ac + PASSO_P, 1], [t_ac + PASSO_P + 0.1, 0]],
                  "escala": {"mola": MOLA_ESTADO, "em": t_ac, "de": 0.86,
                             "para": 1.0}})
        C.append({"tipo": "texto", "texto": w, "tamanho": TAM_P, "peso": 900,
                  "cor": "#0A0A0A", "x": cx, "y": 110,
                  "opacidade": [[t_ac, 0], [t_ac + 0.06, 1],
                                [t_ac + PASSO_P, 1], [t_ac + PASSO_P + 0.1, 0]]})
        # depois que passou, fica branca — ja foi dita
        C.append({"tipo": "texto", "texto": w, "tamanho": TAM_P, "peso": 800,
                  "cor": TEXTO, "x": cx, "y": 110,
                  "opacidade": [[t_ac + PASSO_P, 0],
                                [t_ac + PASSO_P + 0.12, 1]]})
        # o carimbo de tempo embaixo
        C.append({"tipo": "texto", "texto": "%0.2f" % (i * 0.31 + 0.14),
                  "tamanho": 15, "peso": 600, "cor": DIM, "x": cx, "y": 58,
                  "opacidade": entra(0.5 + i * LETRA, 0.25)})
        x += lw + GAP

    C.append(rotulo("WHISPER RODANDO NA SUA MAQUINA", fim(dur, 0, 2),
                    -300, MUDO, 22))
    C.append(rotulo("TEMPO POR PALAVRA, NAO POR FRASE",
                    fim(dur, 1, 2), -355, MUDO_ESCURO, 19))

    return {"duracao": dur, "fundo": BG, "camadas": C}
