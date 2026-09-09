# -*- coding: utf-8 -*-
"""modelos.py — 3,5 s. Os modelos que ja estao na sua maquina.

Equivale a `ModelsScene`: ali uma fila de cartoes de modelo de imagem, cada um
com o nome e um tracinho de status. Aqui sao os cinco runtimes locais que o
Klipe PROCURA sozinho ao abrir o seletor — bate na porta de cada um e mostra
quem respondeu.

O gesto herdado: o cartao entra apagado e o ponto de status acende DEPOIS, com
um atraso proprio. E o que le como "foi verificado" em vez de "estava escrito".
"""
from .base import *

# llm.js — RUNTIMES_LOCAIS, as portas reais que o Klipe sonda
RUNTIMES = [
    ("Ollama",    "11434", VERDE, True),
    ("LM Studio", "1234",  VERDE, True),
    ("Jan",       "1337",  MUDO,  False),
    ("llama.cpp", "8080",  MUDO,  False),
    ("vLLM",      "8000",  MUDO,  False),
]
LARG_C, ALT_C = 300, 260
PASSO = 328


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.3)
    C.append(brilho(0, 30, 960, VERDE + "16", 0.0, 0.45, 61))
    C.append(marca_dagua("LOCAL", 430, VERDE, -6, 0.035, 0))
    C += particulas(20, VERDE, CIANO, 16, 63)

    C.append(rotulo("MODELOS", 0.08, 440, VERDE, 24))
    C += titulo("O que ja roda no seu PC", 0.2, 348, 74, TEXTO, 800)

    for i, (nome, porta, cor, vivo) in enumerate(RUNTIMES):
        x = -PASSO * (len(RUNTIMES) - 1) / 2 + i * PASSO
        t = 0.32 + i * (1.7 * BLOCO)

        C += sombra(x, 40, LARG_C, ALT_C, t, raio=16, n=2)
        C.append(card(x, 40, LARG_C, ALT_C, t, BG_SUP,
                      cor + "44" if vivo else BORDA, 16, 70 + i))
        # o halo so nos que responderam
        if vivo:
            C.append({"tipo": "retangulo", "larg": LARG_C + 26,
                      "alt": ALT_C + 26, "raio": 22, "cor": cor, "blur": 34,
                      "x": x, "y": 40,
                      "opacidade": [[t + 0.5, 0], [t + 0.9, 0.16, "outCubic"]]})

        C.append({"tipo": "texto", "texto": nome, "tamanho": 30, "peso": 900,
                  "cor": TEXTO if vivo else MUDO, "x": x, "y": 84,
                  "opacidade": entra(t + 0.14, 0.25)})
        C.append({"tipo": "texto", "texto": ":" + porta, "tamanho": 22,
                  "peso": 600, "cor": DIM, "x": x, "y": 34,
                  "opacidade": entra(t + 0.2, 0.25)})

        # o ponto de status: acende DEPOIS do cartao, e pulsa se estiver vivo
        C.append({"tipo": "elipse", "raio": 9, "cor": cor, "x": x - 46,
                  "y": -30, "opacidade": entra(t + 0.5, 0.2),
                  "escala": pulso(1.0, 0.22, 0.05, 80 + i) if vivo else 1.0})
        if vivo:
            C.append({"tipo": "elipse", "raio": 22, "cor": cor, "blur": 16,
                      "x": x - 46, "y": -30,
                      "opacidade": [[t + 0.5, 0], [t + 0.75, 0.5]]})
        C.append({"tipo": "texto",
                  "texto": "respondeu" if vivo else "nao achei",
                  "tamanho": 19, "peso": 600, "cor": cor if vivo else DIM,
                  "x": x + 26, "y": -34, "opacidade": entra(t + 0.56, 0.25)})

    C.append(rotulo("O KLIPE BATE NAS CINCO PORTAS AO ABRIR O SELETOR",
                    fim(dur, 0, 2), -270, MUDO, 22))
    C.append(rotulo("NUVEM SO SE VOCE PUSER A SUA CHAVE",
                    fim(dur, 1, 2), -325, MUDO_ESCURO, 19))

    return {"duracao": dur, "fundo": BG, "camadas": C}
