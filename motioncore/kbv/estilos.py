# -*- coding: utf-8 -*-
"""estilos.py — 4,0 s. Os estilos de titulo.

Esta e a cena que eu ja tinha refeito uma vez pra provar que dava — a
`StylePresetsScene`. O mecanismo dela e o mais bonito da referencia: a pilula
ativa troca a cada 20 frames, e TUDO que depende do estilo ativo (a amostra
grande, o halo, a linha indicadora) troca junto.

O motor nao tem estado. Entao o estado vira TEMPO: cada coisa existe em seis
copias que cruzam por opacidade em janelas de 0,667 s. A linha indicadora se
REDESENHA (`traco`) nos primeiros 30% de cada janela, como o `evolvePath` do
original.
"""
from .base import *

# seis estilos que o motor do Klipe desenha de verdade, com a amostra que
# descreve o proprio efeito
ESTILOS = [
    ("Split text",    MARCA,  "CADA PALAVRA NO SEU TEMPO"),
    ("Word highlight", CIANO, "a palavra que IMPORTA"),
    ("Counter",       VERDE,  "72%"),
    ("Point list",    AZUL,   "titulo + itens, um a um"),
    ("Stacked",       ROXO,   "PRIMEIRA / segunda / TERCEIRA"),
    ("Paradox",       VERM,   "linha leve / LINHA FORTE"),
]
TROCA = 20 * F                    # constants.ts:48 — o ciclo do original
TAM_P = 32
Y_AMOSTRA, Y_FILA1, Y_FILA2, Y_LINHA = 120, -70, -162, -250
FILAS = [(0, 1, 2), (3, 4, 5)]


def _janelas(i: int, dur: float) -> list:
    n = int(dur / TROCA) + 1
    return [(k * TROCA, (k + 1) * TROCA)
            for k in range(n) if k % len(ESTILOS) == i and k * TROCA < dur]


def _op(i: int, dur: float, alto: float = 1.0, cross: float = 0.06,
        desde: float = 0.0) -> list:
    """Acende so na janela deste estilo. `linear` no cruzamento mantem a soma
    das seis copias constante — com curva suave o fundo piscaria a cada troca.
    """
    ks: list = [[0.0, 0.0]]
    for a, b in _janelas(i, dur):
        a = max(a, desde)
        if a >= b:
            continue
        ks += [[round(max(0.0, a - cross), 3), 0.0, "linear"],
               [round(a + cross, 3), alto, "linear"],
               [round(b - cross, 3), alto, "linear"],
               [round(b + cross, 3), 0.0, "linear"]]
    return ks


def cena(dur: float) -> dict:
    C: list = []

    C += grade_fundo(96, BG_GRADE, 0.28)
    C.append(marca_dagua("ESTILOS", 400, MARCA, -15, 0.05, 0))
    C += particulas(30, MARCA, CIANO, 20, 91)

    # o brilho de fundo troca de cor junto com o estilo ativo
    for i, (_n, cor, _a) in enumerate(ESTILOS):
        b = brilho(0, 60, 880, cor + "26", 0.0, 0.5, 95 + i)
        b["opacidade"] = _op(i, dur, 0.5, 0.09, 0.3)
        C.append(b)

    C.append(rotulo("titulos", 0.05, 300, MUDO, 24))
    for lay in titulo("22 estilos", 0.12, 210, 96, TEXTO, 900):
        lay["sombra"] = [{"x": 0, "y": 0, "blur": 60, "cor": MARCA + "33"}]
        C.append(lay)

    # ── a amostra grande, trocando com o estilo ───────────────────────────
    for i, (_n, cor, amostra) in enumerate(ESTILOS):
        C.append({"tipo": "texto", "texto": amostra, "tamanho": 44,
                  "peso": 800, "cor": cor, "y": Y_AMOSTRA,
                  "largura_max": 1500, "alinha": "centro",
                  "opacidade": _op(i, dur, 1.0, 0.05, 0.35)})

    # ── as seis pilulas ───────────────────────────────────────────────────
    largs = [larg_texto(n, TAM_P) + 80 for n, _c, _a in ESTILOS]
    for fi, idxs in enumerate(FILAS):
        total = sum(largs[i] for i in idxs) + 20 * (len(idxs) - 1)
        px = -total / 2
        yf = Y_FILA1 if fi == 0 else Y_FILA2
        for i in idxs:
            nome, cor, _a = ESTILOS[i]
            cx = px + largs[i] / 2
            t0 = 0.3 + i * BLOCO
            # o halo da ativa
            C.append({"tipo": "retangulo", "larg": largs[i] + 44,
                      "alt": TAM_P + 76, "raio": 100, "cor": cor, "blur": 42,
                      "x": cx, "y": yf,
                      "opacidade": _op(i, dur, 0.42, 0.08, t0 + 0.12)})
            p = pilula(nome, t0, cx, yf, cor, TAM_P,
                       _op(i, dur, 1.0, 0.06, t0 + 0.12))
            for lay in p[2:]:
                lay["escala"] = pulso(1.12, 0.03, 0.03, 500 + i)
            p[3]["peso"] = 900
            C += p
            px += largs[i] + 20

    # ── a linha indicadora, que se redesenha a cada troca ─────────────────
    for i, (_n, cor, _a) in enumerate(ESTILOS):
        jan = _janelas(i, dur)
        a = jan[0][0] if jan else 0.0
        C.append({"tipo": "linha", "de": [-110, 0], "para": [110, 0],
                  "contorno": cor, "contorno_larg": 4,
                  **viva(0, Y_LINHA, 2, 800 + i),
                  "traco": [[max(0.0, a), 0.02, "outCubic"],
                            [a + 0.30 * TROCA, 1.0]],
                  "opacidade": _op(i, dur, 0.85, 0.05, 0.45)})

    C.append(rotulo("TODOS DESENHADOS PELO MOTOR, NENHUM PRESO A UM PROJETO",
                    fim(dur), -340, MUDO_ESCURO, 20))

    return {"duracao": dur, "fundo": BG, "camadas": C}
