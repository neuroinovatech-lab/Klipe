# -*- coding: utf-8 -*-
"""corte.py — 4,0 s. Corte pelo texto.

Equivale ao `FocusedDemoScene`, a cena mais densa da referencia: uma janela de
produto ocupando o quadro, um gesto acontecendo dentro dela, e o resultado
aparecendo. Ali e um prompt virando imagem; aqui e a coisa que o Premiere
chama de text-based editing.

O gesto: a transcricao esta na tela, tres vicios de linguagem sao riscados em
vermelho, e o clipe embaixo ENCOLHE na mesma hora. E a demonstracao inteira do
recurso — apagar a palavra apaga o video.
"""
from .base import *

FRASE = ["Entao", "o", "que", "eu", "queria", "falar", "hoje", "e",
         "tipo", "sobre", "como", "a", "gente", "ne", "monta", "isso"]
# os indices que sao vicio e vao cair
VICIOS = {0, 8, 13}

TAM_P = 34
GAP = 16
Y_TEXTO = 96
LARG_J, ALT_J = 1500, 620
Y_J = 20


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.25)
    C.append(brilho(0, 0, 980, VERM + "16", 0.0, 0.45, 31))
    C.append(marca_dagua("CORTE", 430, VERM, -6, 0.035, 0))
    C += particulas(16, VERM, MARCA, 14, 33)

    C.append(rotulo("EDICAO PELO TEXTO", 0.08, 470, VERM, 24))
    C += titulo("Apaga a palavra, some do video", 0.2, 384, 64, TEXTO, 800)

    # ── a janela do aplicativo ────────────────────────────────────────────
    C += janela(0, Y_J, LARG_J, ALT_J, 0.4, 35)
    C.append(barra_titulo(0, Y_J, LARG_J, ALT_J, "transcricao  ·  reel.mp4",
                          0.4, MUDO_ESCURO))

    # ── a frase, palavra a palavra ────────────────────────────────────────
    largs = [larg_texto(w, TAM_P) + 26 for w in FRASE]
    # duas linhas: quebra onde a soma passaria da largura util
    util = LARG_J - 120
    linhas, atual, soma = [], [], 0.0
    for i, w in enumerate(largs):
        if soma + w + GAP > util and atual:
            linhas.append(atual); atual, soma = [], 0.0
        atual.append(i); soma += w + GAP
    if atual:
        linhas.append(atual)

    T_RISCO = 1.75          # o instante em que os vicios caem
    for li, idxs in enumerate(linhas):
        total = sum(largs[i] for i in idxs) + GAP * (len(idxs) - 1)
        x = -total / 2
        y = Y_TEXTO + 130 - li * 92
        for i in idxs:
            w = largs[i]
            cx = x + w / 2
            d = 0.72 + i * (2 * LETRA)
            vicio = i in VICIOS
            # a pilula da palavra
            C.append({"tipo": "retangulo", "larg": w, "alt": 56, "raio": 8,
                      "cor": "#FFFFFF08", "contorno": BORDA,
                      "contorno_larg": 1, "x": cx, "y": y,
                      "opacidade": entra(d, 0.22)})
            C.append({"tipo": "texto", "texto": FRASE[i], "tamanho": TAM_P,
                      "peso": 700 if not vicio else 800,
                      "cor": TEXTO if not vicio else MUDO,
                      "x": cx, "y": y - 2, "opacidade": entra(d, 0.22)})
            if vicio:
                # o fundo vermelho acende
                C.append({"tipo": "retangulo", "larg": w, "alt": 56, "raio": 8,
                          "cor": VERM + "33", "contorno": VERM,
                          "contorno_larg": 2, "x": cx, "y": y,
                          "opacidade": [[T_RISCO, 0], [T_RISCO + 0.18, 1]]})
                C.append({"tipo": "texto", "texto": FRASE[i], "tamanho": TAM_P,
                          "peso": 800, "cor": VERM, "x": cx, "y": y - 2,
                          "opacidade": [[T_RISCO, 0], [T_RISCO + 0.18, 1]]})
                # o risco, que se DESENHA da esquerda pra direita
                C.append({"tipo": "linha", "de": [-w / 2 + 8, 0],
                          "para": [w / 2 - 8, 0], "contorno": VERM,
                          "contorno_larg": 4, "x": cx, "y": y,
                          "traco": [[T_RISCO + 0.1, 0.0, "outCubic"],
                                    [T_RISCO + 0.42, 1.0]],
                          "opacidade": [[T_RISCO + 0.1, 0], [T_RISCO + 0.2, 1]]})
            x += w + GAP

    # ── o clipe embaixo, que encolhe quando os vicios caem ────────────────
    Y_CLIP = Y_J - 190
    C.append({"tipo": "texto", "texto": "linha do tempo", "tamanho": 17,
              "peso": 600, "cor": DIM, "x": -util / 2 + 60, "y": Y_CLIP + 52,
              "opacidade": entra(1.0, 0.25)})
    C.append({"tipo": "retangulo", "larg": util, "alt": 64, "raio": 8,
              "cor": "#FFFFFF08", "y": Y_CLIP, "opacidade": entra(1.0, 0.25)})
    # o preenchimento encolhe pela DIREITA: encolher pelo centro pareceria
    # que o video inteiro mudou, e o que sumiu foram tres pedacos
    C.append({"tipo": "retangulo", "larg": util, "alt": 64, "raio": 8,
              "cor": AZUL + "3A", "contorno": AZUL + "99", "contorno_larg": 2,
              "y": Y_CLIP,
              "x": [[1.05, 0], [T_RISCO + 0.45, -util * 0.09, "outCubic"]],
              "opacidade": entra(1.05, 0.25),
              "escalaX": [[1.05, 1.0], [T_RISCO + 0.45, 0.82, "outCubic"]]})
    # as tres falhas que se abrem onde os vicios estavam
    for j, fx in enumerate((-0.36, 0.02, 0.31)):
        C.append({"tipo": "retangulo", "larg": 26, "alt": 64, "raio": 4,
                  "cor": VERM + "55", "x": util * fx, "y": Y_CLIP,
                  "opacidade": [[T_RISCO + 0.15, 0], [T_RISCO + 0.3, 1],
                                [T_RISCO + 0.75, 0]]})

    # ── o placar ──────────────────────────────────────────────────────────
    C.append({"tipo": "texto", "texto": "-3 palavras", "tamanho": 30,
              "peso": 900, "cor": VERM, "x": util / 2 - 110, "y": Y_CLIP + 52,
              "opacidade": [[T_RISCO + 0.4, 0], [T_RISCO + 0.6, 1]],
              "escala": {"mola": MOLA_DESTAQUE, "em": T_RISCO + 0.4,
                         "de": 0.6, "para": 1.0}})

    C.append(rotulo("SELECIONA A PALAVRA, NAO A FRASE INTEIRA",
                    fim(dur), -400, MUDO, 22))

    return {"duracao": dur, "fundo": BG, "camadas": C}
