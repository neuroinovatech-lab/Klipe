# -*- coding: utf-8 -*-
"""fluxo.py — 5,5 s. O caminho inteiro, de ponta a ponta.

Equivale ao `FlowDemoScene`, que e a cena mais longa da referencia e a que
explica o produto: caixas ligadas por arestas que se desenham, com um pulso
percorrendo o grafo. Ali sao etapas de geracao de imagem; aqui sao as seis
etapas que o Klipe faz sozinho num video.

Tres coisas herdadas do original:
  · a aresta SE DESENHA (`traco`) em vez de aparecer — mostra a direcao
  · o pulso viaja depois que a aresta chegou, nao junto
  · cada no acende quando o pulso passa nele, e nao no comeco
"""
from .base import *

# (nome, o que faz, cor, o que SAI da etapa — todos medidos no demo-completo)
ETAPAS = [
    ("VIDEO",      "o arquivo entra",     AZUL,  "70s"),
    ("TRANSCREVE", "Whisper, local",      CIANO, "287 palavras"),
    ("CORTA",      "silencio e vicio",    VERDE, "14 trechos"),
    ("B-ROLL",     "busca e encaixa",     ROXO,  "9 clipes"),
    ("LEGENDA",    "palavra por palavra", MARCA, "287 tempos"),
    ("RENDER",     "na sua GPU",          VERM,  "32s"),
]

LARG_NO, ALT_NO = 262, 132
PASSO = 292
Y_NO = 40


def _x(i: int) -> float:
    return -PASSO * (len(ETAPAS) - 1) / 2 + i * PASSO


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.35)
    C.append(brilho(0, 40, 980, MARCA + "1C", 0.0, 0.5, 11))
    C.append(marca_dagua("FLUXO", 430, MARCA, -6, 0.04, 0))
    C += particulas(22, MARCA, CIANO, 16, 13)

    C.append(rotulo("DO ARQUIVO AO RENDER", 0.1, 420, MARCA, 24))
    C += titulo("Seis etapas, uma janela", 0.25, 320, 76, TEXTO, 800)

    # ── as arestas primeiro, para ficarem ATRAS das caixas ────────────────
    # cada uma sai 0,25 s depois que o no de tras acendeu
    for i in range(len(ETAPAS) - 1):
        t = 0.85 + i * 0.52
        C.append(aresta(_x(i) + LARG_NO / 2, Y_NO,
                        _x(i + 1) - LARG_NO / 2, Y_NO, t,
                        ETAPAS[i][2] + "AA", 0.34))

    # ── as seis caixas ────────────────────────────────────────────────────
    for i, (nome, sub, cor, saida) in enumerate(ETAPAS):
        x, t = _x(i), 0.6 + i * 0.52
        C += no(x, Y_NO, LARG_NO, ALT_NO, t, cor, 20 + i)
        C.append({"tipo": "texto", "texto": nome, "tamanho": 30, "peso": 900,
                  "cor": cor, "espacamento": 1, "x": x, "y": Y_NO + 16,
                  "opacidade": entra(t + 0.15, 0.25)})
        C.append({"tipo": "texto", "texto": sub, "tamanho": 19, "peso": 500,
                  "cor": MUDO, "x": x, "y": Y_NO - 26,
                  "opacidade": entra(t + 0.25, 0.25)})
        # o numero da etapa, na quina de cima
        C.append({"tipo": "texto", "texto": str(i + 1), "tamanho": 16,
                  "peso": 800, "cor": cor + "AA",
                  "x": x - LARG_NO / 2 + 18, "y": Y_NO + ALT_NO / 2 - 20,
                  "opacidade": entra(t + 0.1, 0.25)})
        # O RESULTADO da etapa, que so aparece quando o pulso chega nela.
        # Sem isto a metade de baixo do quadro ficava vazia — e numa cena de
        # 5,5 s, que e a mais longa do roteiro, vazio le como cena parada.
        t_pulso = 0.9 + i * 0.52
        C.append({"tipo": "linha", "de": [0, 0], "para": [0, 34],
                  "contorno": cor + "55", "contorno_larg": 2,
                  "x": x, "y": Y_NO - ALT_NO / 2 - 4,
                  "traco": [[t_pulso, 0.0, "outCubic"], [t_pulso + 0.2, 1.0]],
                  "opacidade": [[t_pulso, 0], [t_pulso + 0.08, 1]]})
        C.append({"tipo": "texto", "texto": saida, "tamanho": 27, "peso": 900,
                  "cor": cor, "x": x, "y": Y_NO - 148,
                  "opacidade": entra(t_pulso + 0.16, 0.25),
                  "escala": {"mola": MOLA_TEXTO, "em": t_pulso + 0.16,
                             "de": 0.7, "para": 1.0}})
        C.append({"tipo": "texto", "texto": "sai", "tamanho": 15, "peso": 600,
                  "cor": DIM, "x": x, "y": Y_NO - 186,
                  "opacidade": entra(t_pulso + 0.26, 0.25)})

    # ── o pulso: uma bolinha que percorre a fila inteira ──────────────────
    # a posicao e uma cadeia de keyframes que para em cada caixa — o intervalo
    # PARADO e o que faz parecer que a etapa esta trabalhando
    ks_x, ks_o = [], [[0.7, 0]]
    t = 0.9
    for i in range(len(ETAPAS)):
        ks_x.append([round(t, 3), _x(i)])
        t += 0.24                                   # parado, trabalhando
        ks_x.append([round(t, 3), _x(i)])
        if i < len(ETAPAS) - 1:
            t += 0.28                               # viajando
            ks_x.append([round(t, 3), _x(i + 1), "inOutCubic"])
    ks_o += [[0.9, 1], [t, 1], [t + 0.3, 0]]
    C.append({"tipo": "elipse", "raio": 13, "cor": TEXTO,
              "x": ks_x, "y": Y_NO, "opacidade": ks_o})
    C.append({"tipo": "elipse", "raio": 34, "cor": MARCA, "blur": 26,
              "x": ks_x, "y": Y_NO,
              "opacidade": [[0.9, 0], [1.0, 0.7], [t, 0.7], [t + 0.3, 0]]})

    # ── a barra de progresso embaixo, correndo junto ──────────────────────
    C += barra_prog(0, -290, 1520, 0.9, MARCA, t - 0.9, 8)
    C.append(rotulo("NADA DISSO ABRE OUTRO PROGRAMA", fim(dur, 0, 2),
                    -360, MUDO, 22))
    C.append(rotulo("NEM SOBE PRA NUVEM", fim(dur, 1, 2), -418,
                    MUDO_ESCURO, 19))

    return {"duracao": dur, "fundo": BG, "camadas": C}
