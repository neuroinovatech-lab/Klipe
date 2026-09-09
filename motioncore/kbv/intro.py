# -*- coding: utf-8 -*-
"""intro.py — 3,5 s. A abertura, com a composicao da `IntroScene`.

Isto e a entrada da referencia refeita: marca pequena no topo, uma palavra
enorme em branco, a segunda enorme na cor da marca ATRAS e mais embaixo, o
filete curvo, a linha de caixa-alta espacada, a palavra grande em italico e a
assinatura miuda. Ao fundo, o brilho radial, os arcos concentricos, as duas
esferas de arame nos cantos opostos e as estrelas de quatro pontas.

O que muda e o texto — e ele nao foi inventado. Cada linha e uma parte do
proprio nome:

    KLIPE / NLE                      o nome e o que ele e
    KINETIC LINKING INTELLIGENT      as tres primeiras iniciais
    Production Engine                as duas ultimas
    para quem edita                  pra quem

E cada linha usa um estilo que existe na biblioteca do Klipe, nao um desenho
avulso: as duas grandes sao `hero` letra a letra, a espacada e `rotulo`, a
italica e a cauda do `letterEyebrow`.
"""
import math

from .base import *


def _estrela(x: float, y: float, r: float, t: float, cor: str,
             s: int = 1) -> dict:
    """Estrela de quatro pontas — as que ficam boiando no fundo da referencia.

    O `path` e concavo de proposito: quatro pontas finas com a barriga puxada
    pro centro. Estrela de pontas retas viraria um losango.
    """
    k = r * 0.16
    d = (f"M 0 {-r} C 0 {-k} {k} 0 {r} 0 "
         f"C {k} 0 0 {k} 0 {r} "
         f"C 0 {k} {-k} 0 {-r} 0 "
         f"C {-k} 0 0 {-k} 0 {-r} Z")
    return {"tipo": "path", "d": d, "cor": cor, **viva(x, y, 4, s),
            "rotacao": {"ruido": {"escala": 0.004, "amp": 12, "base": 0,
                                  "semente": s + 40}},
            "opacidade": [[t, 0], [t + 0.7, 0.55, "outCubic"]],
            "escala": pulso(1.0, 0.12, 0.03, s + 70)}


def _esfera(x: float, y: float, r: float, t: float, cor: str,
            s: int = 1) -> list[dict]:
    """Esfera de arame. Os meridianos sao elipses de mesmo raio vertical e raio
    horizontal `r*cos(theta)` — e o que faz uma pilha de elipses virar volume.
    """
    out = [{"tipo": "elipse", "raio": r, "cor": "#00000000", "contorno": cor,
            "contorno_larg": 1.6, **viva(x, y, 5, s),
            "opacidade": [[t, 0], [t + 0.8, 0.5, "outCubic"]]}]
    for i in range(1, 5):                       # meridianos
        rx = r * math.cos(i * math.pi / 10)
        out.append({"tipo": "elipse", "rx": rx, "ry": r, "cor": "#00000000",
                    "contorno": cor, "contorno_larg": 1.2,
                    **viva(x, y, 5, s), "opacidade":
                    [[t + i * LETRA, 0], [t + 0.8 + i * LETRA, 0.34, "outCubic"]]})
    for i, f in enumerate((0.34, 0.66, 0.9)):   # paralelos
        out.append({"tipo": "elipse", "rx": r * math.sin(math.acos(f - 0.5)),
                    "ry": r * 0.1, "cor": "#00000000", "contorno": cor,
                    "contorno_larg": 1.2, **viva(x, y + (f - 0.5) * 2 * r, 5, s),
                    "opacidade": [[t + 0.2, 0], [t + 1.0, 0.28, "outCubic"]]})
    return out


def _marca(t: float, y: float) -> list[dict]:
    """A marca miuda no topo: o triangulo de play, os nos, e a palavra."""
    out = [
        {"tipo": "path", "d": "M 0 0 L 26 15 L 0 30 Z", "cor": MARCA,
         "x": -104, "y": y, "escala": 0.85, "opacidade": entra(t, 0.35)},
        {"tipo": "texto", "texto": "klipe", "tamanho": 30, "peso": 700,
         "cor": MUDO, "x": -14, "y": y - 2, "opacidade": entra(t + 0.1, 0.35)},
    ]
    for i, (dx, dy, rr) in enumerate(((-72, 16, 5), (-52, -12, 4),
                                      (-64, -2, 7))):
        out.append({"tipo": "elipse", "raio": rr, "cor": MARCA_CLARA,
                    "x": dx, "y": y + dy,
                    "opacidade": entra(t + 0.05 + i * LETRA, 0.3)})
    return out


def cena(dur: float) -> dict:
    C: list = []

    # ── o fundo: brilho radial e arcos concentricos ───────────────────────
    C.append({"tipo": "elipse", "raio": 760, "y": 40,
              "cor": {"tipo": "radial", "cores": ["#12224E", BG], "raio": 760},
              "opacidade": [[0, 0], [1.1, 1, "outCubic"]]})
    C.append(brilho(0, 60, 620, MARCA + "33", 0.0, 0.6, 3))
    for i in range(5):
        r = 330 + i * 118
        C.append({"tipo": "elipse", "raio": r, "cor": "#00000000",
                  "contorno": MARCA, "contorno_larg": 1.4, "y": 40,
                  "opacidade": [[0.1 + i * BLOCO, 0],
                                [0.9 + i * BLOCO, 0.22 - i * 0.03, "outCubic"]],
                  "escala": {"mola": MOLA_ESTADO, "em": 0.1 + i * BLOCO,
                             "de": 0.9, "para": 1.0}})

    # ── as duas esferas de arame, em cantos opostos ───────────────────────
    C += _esfera(-830, 400, 88, 0.15, MARCA + "AA", 11)
    C += _esfera(790, -390, 74, 0.35, MARCA + "AA", 13)

    # ── as estrelas e os losangos boiando ─────────────────────────────────
    ESTRELAS = ((-700, 300, 26), (-820, 150, 18), (-640, -330, 22),
                (830, 250, 20), (760, -170, 26), (620, -420, 16),
                (-540, -430, 14), (880, 60, 15))
    for i, (x, y, r) in enumerate(ESTRELAS):
        C.append(_estrela(x, y, r, 0.3 + i * BLOCO, MARCA + "CC", 20 + i))
    for i, (x, y, r) in enumerate(((-760, 60, 13), (-560, 380, 10),
                                   (700, 420, 12), (840, -60, 9))):
        C.append({"tipo": "retangulo", "larg": r * 2, "alt": r * 2, "raio": 2,
                  "cor": MARCA + "55", "contorno": MARCA + "AA",
                  "contorno_larg": 1.2, "rotacao": 45, **viva(x, y, 4, 30 + i),
                  "opacidade": [[0.5 + i * BLOCO, 0],
                                [1.2 + i * BLOCO, 0.7, "outCubic"]]})

    C += particulas(20, MARCA, MARCA_CLARA, 16, 7)

    # ── a marca no topo ───────────────────────────────────────────────────
    C += _marca(0.12, 236)

    # ── as duas palavras grandes ──────────────────────────────────────────
    # "NLE" entra ANTES e fica ATRAS, mais embaixo e maior — e a sobreposicao
    # que da profundidade na referencia. Como o motor desenha na ordem da
    # lista, quem vem primeiro fica atras: nao ha z-index pra resolver isso.
    for lay in titulo("NLE", 0.45, -58, 250, MARCA, 900):
        lay["sombra"] = [{"x": 0, "y": 0, "blur": 70, "cor": MARCA + "66"}]
        C.append(lay)
    for lay in titulo("KLIPE", 0.28, 110, 190, TEXTO, 900):
        lay["sombra"] = [{"x": 0, "y": 6, "blur": 40, "cor": "#00000099"}]
        C.append(lay)

    # ── o filete curvo sob as palavras ────────────────────────────────────
    # arco raso desenhado por `traco`; `path` tem o y invertido, entao a
    # barriga pra baixo se escreve com o controle POSITIVO
    C.append({"tipo": "path", "d": "M -300 0 Q 0 34 300 0", "cor": "#00000000",
              "contorno": MARCA_CLARA, "contorno_larg": 2.5, "y": -208,
              "traco": [[1.05, 0.0, "outCubic"], [1.6, 1.0]],
              "opacidade": [[1.05, 0], [1.2, 0.8]]})

    # ── a linha de caixa-alta espacada ────────────────────────────────────
    C.append(rotulo("KINETIC  LINKING  INTELLIGENT", 1.35, -266, MUDO, 26,
                    esp=6))

    # ── a palavra grande em italico ───────────────────────────────────────
    for lay in titulo("Production Engine", 1.42, -352, 92, MARCA_CLARA, 900,
                      italico=True):
        lay["sombra"] = [{"x": 0, "y": 0, "blur": 46, "cor": MARCA + "55"}]
        C.append(lay)

    # ── a assinatura ──────────────────────────────────────────────────────
    C.append({"tipo": "texto", "texto": "para quem edita", "tamanho": 24,
              "peso": 500, "italico": True, "cor": MUDO_ESCURO,
              **viva(0, -444, 2, 9), "opacidade": entra(fim(dur), 0.35)})

    return {"duracao": dur, "fundo": BG, "camadas": C}
