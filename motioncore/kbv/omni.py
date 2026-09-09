# -*- coding: utf-8 -*-
"""omni.py — 4,0 s. Reeditar um trecho do proprio video.

Equivale a `InpaintingScene`: a regiao marcada, o pedido escrito, e o pedaco
voltando diferente. Ali e uma foto; aqui e um TRECHO DE VIDEO — o OMNI pega no
maximo 10 segundos e regenera o quadro a partir do que voce pediu.

A cena e honesta sobre o preco: leva de 2 a 5 minutos, o fundo pode variar, e
o custo aparece escrito. E o unico lugar deste video onde a conta nao e zero.
"""
from .base import *

LARG_J, ALT_J, Y_J = 1180, 520, 60


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.25)
    C.append(brilho(0, 40, 960, ROXO + "1E", 0.0, 0.45, 161))
    C.append(marca_dagua("OMNI", 450, ROXO, -6, 0.035, 0))
    C += particulas(20, ROXO, MARCA, 16, 163)

    C.append(rotulo("REEDICAO", 0.08, 452, ROXO, 24))
    C += titulo("Muda o trecho, nao o video", 0.2, 366, 68, TEXTO, 800)

    # ── a janela com o quadro ─────────────────────────────────────────────
    C += janela(0, Y_J, LARG_J, ALT_J, 0.38, 165)
    C.append(barra_titulo(0, Y_J, LARG_J, ALT_J, "trecho 00:12 – 00:20",
                          0.38, MUDO_ESCURO))
    # O quadro e DESENHADO, nao fotografado. Um frame real dos nossos renders
    # tem titulo gravado nele, e a cena passaria a parecer que o OMNI esta
    # reeditando a propria marca. Desenhado, o pedido escrito embaixo e o
    # resultado dentro da regiao combinam — que e o ponto da cena.
    QW, QH, QY = LARG_J - 30, ALT_J - 70, Y_J - 22
    C.append({"tipo": "retangulo", "larg": QW, "alt": QH, "raio": 8,
              "cor": {"tipo": "linear", "cores": ["#241B14", "#12100F"],
                      "de": [0, QH / 2], "para": [0, -QH / 2]},
              "x": 0, "y": QY, "opacidade": entra(0.5, 0.35)})
    # a luz da janela, fora de quadro a esquerda
    C.append({"tipo": "elipse", "raio": 320, "x": -380, "y": QY + 60,
              "cor": {"tipo": "radial", "cores": ["#C9A06022", "#00000000"],
                      "raio": 320}, "opacidade": entra(0.6, 0.5)})
    # o rodape da parede
    C.append({"tipo": "retangulo", "larg": QW, "alt": 3, "cor": "#3A2F26",
              "x": 0, "y": QY - QH / 2 + 92, "opacidade": entra(0.62, 0.3)})
    # a pessoa, de costas pra parede
    C.append({"tipo": "elipse", "raio": 46, "cor": "#1C1A19", "x": -210,
              "y": QY + 52, "opacidade": entra(0.66, 0.35)})
    C.append({"tipo": "retangulo", "larg": 186, "alt": 190, "raio": 78,
              "cor": "#1C1A19", "x": -210, "y": QY - 96,
              "opacidade": entra(0.7, 0.35)})

    # ── a regiao marcada: retangulo tracejado que se DESENHA ──────────────
    T_MARCA = 1.0
    RX, RY, RW, RH = 250, Y_J + 10, 360, 250
    C.append({"tipo": "retangulo", "larg": RW, "alt": RH, "raio": 8,
              "cor": ROXO + "1F", "x": RX, "y": RY,
              "opacidade": [[T_MARCA, 0], [T_MARCA + 0.3, 1]]})
    C.append({"tipo": "retangulo", "larg": RW, "alt": RH, "raio": 8,
              "cor": "#00000000", "contorno": ROXO, "contorno_larg": 3,
              "x": RX, "y": RY,
              "traco": [[T_MARCA, 0.0, "outCubic"], [T_MARCA + 0.5, 1.0]],
              "opacidade": [[T_MARCA, 0], [T_MARCA + 0.1, 1]]})
    # as alcas nos quatro cantos
    for i, (sx, sy) in enumerate(((-1, 1), (1, 1), (-1, -1), (1, -1))):
        C.append({"tipo": "retangulo", "larg": 12, "alt": 12, "raio": 2,
                  "cor": ROXO, "x": RX + sx * RW / 2, "y": RY + sy * RH / 2,
                  "opacidade": [[T_MARCA + 0.35 + i * LETRA, 0],
                                [T_MARCA + 0.5 + i * LETRA, 1]],
                  "escala": {"mola": MOLA_TEXTO,
                             "em": T_MARCA + 0.35 + i * LETRA,
                             "de": 0.0, "para": 1.0}})
    # a varredura: uma faixa clara que passa pela regiao, gerando
    C.append({"tipo": "retangulo", "larg": 8, "alt": RH, "cor": MARCA_CLARA,
              "blur": 14, "y": RY,
              "x": [[T_MARCA + 0.55, RX - RW / 2],
                    [T_MARCA + 1.5, RX + RW / 2, "inOutCubic"]],
              "opacidade": [[T_MARCA + 0.55, 0], [T_MARCA + 0.7, 0.9],
                            [T_MARCA + 1.4, 0.9], [T_MARCA + 1.55, 0]]})

    # a estante, que aparece DENTRO da regiao depois que a varredura passa
    T_EST = T_MARCA + 1.15
    for k in range(3):
        py = RY - 78 + k * 74
        C.append({"tipo": "retangulo", "larg": RW - 90, "alt": 7, "raio": 2,
                  "cor": "#8A6A45", "x": RX, "y": py,
                  "opacidade": [[T_EST + k * BLOCO, 0],
                                [T_EST + 0.2 + k * BLOCO, 1]],
                  "escalaX": {"mola": MOLA_ESTADO, "em": T_EST + k * BLOCO,
                              "de": 0.0, "para": 1.0}})
        for j in range(6):
            C.append({"tipo": "retangulo", "larg": 15, "alt": 42 - (j % 3) * 7,
                      "raio": 2,
                      "cor": ("#7A5C3E", "#5E4B6B", "#3F5A52")[j % 3],
                      "x": RX - RW / 2 + 62 + j * 22,
                      "y": py + 26 - (j % 3) * 3,
                      "opacidade": [[T_EST + 0.12 + k * BLOCO + j * LETRA, 0],
                                    [T_EST + 0.3 + k * BLOCO + j * LETRA, 1]]})

    # ── o pedido, digitado ────────────────────────────────────────────────
    PEDIDO = "coloque uma estante atras da pessoa"
    T_TXT = 0.85
    C.append({"tipo": "retangulo", "larg": 900, "alt": 74, "raio": 12,
              "cor": "#FFFFFF0A", "contorno": ROXO + "55", "contorno_larg": 2,
              "x": 0, "y": -280, "opacidade": entra(T_TXT, 0.28),
              "escala": {"mola": MOLA_ESTADO, "em": T_TXT, "de": 0.92,
                         "para": 1.0}})
    # letra a letra, do jeito que se digita
    largs = [larg_char(c, 28) for c in PEDIDO]
    x = -sum(largs) / 2
    for i, (c, w) in enumerate(zip(PEDIDO, largs)):
        if c != " ":
            C.append({"tipo": "texto", "texto": c, "tamanho": 28, "peso": 600,
                      "cor": TEXTO, "x": x + w / 2, "y": -282,
                      "opacidade": [[T_TXT + 0.15 + i * 0.018, 0],
                                    [T_TXT + 0.2 + i * 0.018, 1]]})
        x += w
    # o cursor, no fim da linha
    C.append({"tipo": "retangulo", "larg": 3, "alt": 32, "cor": ROXO,
              "x": sum(largs) / 2 + 8, "y": -282,
              "opacidade": [[T_TXT + 0.15, 1], [T_TXT + 0.9, 1],
                            [T_TXT + 0.95, 0.1], [T_TXT + 1.25, 0.1],
                            [T_TXT + 1.3, 1]]})

    # ── o preco na cara ───────────────────────────────────────────────────
    for i, (rot, val, cor) in enumerate((("maximo", "10s", MUDO),
                                         ("leva", "2 a 5 min", MUDO),
                                         ("custo", "US$ 0,04", MARCA))):
        x = -330 + i * 330
        t = 2.02 + i * (1.4 * BLOCO)
        C.append({"tipo": "texto", "texto": rot, "tamanho": 19, "peso": 600,
                  "cor": DIM, "x": x, "y": -352, "opacidade": entra(t, 0.25)})
        C.append({"tipo": "texto", "texto": val, "tamanho": 30, "peso": 900,
                  "cor": cor, "x": x, "y": -398,
                  "opacidade": entra(t + 0.08, 0.25)})

    C.append(rotulo("REGENERA O QUADRO — O FUNDO PODE VARIAR",
                    fim(dur), -458, MUDO_ESCURO, 19))

    return {"duracao": dur, "fundo": BG, "camadas": C}
