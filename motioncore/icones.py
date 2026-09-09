# -*- coding: utf-8 -*-
"""icones.py — forma emprestada, animacao nossa.

Cada icone aqui e um `path` SVG no sistema do Lucide (MIT): caixa de 24x24,
traco de 2, pontas arredondadas. Nao ha runtime novo, nao ha arquivo binario,
nao ha dependencia: e uma string de comandos que o `path` do DSL ja sabia
desenhar desde sempre.

POR QUE ASSIM E NAO LOTTIE
  Um Lottie pronto traz a animacao de outra pessoa junto com a forma — e ela
  nao e parametrizavel. Aqui entra so a FORMA, e o movimento vem do nosso
  vocabulario: `traco` faz o icone se escrever, `mola` faz ele chegar, `ruido`
  faz ele respirar, `repetir` faz uma grade deles. O icone herda o oficio da
  cena em vez de trazer o dele.

  (E tem a razao pratica: o skia-python deste ambiente nao expoe o Skottie, o
  leitor de Lottie do Skia. Suportar Lottie exigiria subir um navegador — que
  e exatamente o que foi tirado deste projeto.)

COMO USAR
    from .icones import icone
    icone("tesoura", x=0, y=0, tam=96, t=0.4, cor=MARCA)
    icone("tesoura", ..., escreve=True)     # desenha o traco em vez de aparecer

CONFERIDO A OLHO
  Todo icone deste arquivo foi renderizado e OLHADO. Path SVG errado nao da
  erro: da rabisco. `python -m motioncore.icones` refaz a folha de provas.
"""
from __future__ import annotations

import math
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAIXA = 24.0          # o viewBox do Lucide
TRACO = 2.0           # o stroke-width dele, nas mesmas unidades


# ── primitivas: escrever arco de circunferencia a mao da erro ────────────

def _c(cx: float, cy: float, r: float) -> str:
    """Circunferencia como dois arcos de meia volta."""
    return (f"M {cx - r} {cy} A {r} {r} 0 1 0 {cx + r} {cy} "
            f"A {r} {r} 0 1 0 {cx - r} {cy} Z ")


def _r(x: float, y: float, w: float, h: float, k: float = 0.0) -> str:
    """Retangulo, com canto arredondado opcional."""
    if k <= 0:
        return f"M {x} {y} H {x + w} V {y + h} H {x} Z "
    return (f"M {x + k} {y} H {x + w - k} A {k} {k} 0 0 1 {x + w} {y + k} "
            f"V {y + h - k} A {k} {k} 0 0 1 {x + w - k} {y + h} "
            f"H {x + k} A {k} {k} 0 0 1 {x} {y + h - k} "
            f"V {y + k} A {k} {k} 0 0 1 {x + k} {y} Z ")


def _l(x1: float, y1: float, x2: float, y2: float) -> str:
    return f"M {x1} {y1} L {x2} {y2} "


def _p(*pts) -> str:
    """Polilinha aberta."""
    d = f"M {pts[0][0]} {pts[0][1]} "
    for x, y in pts[1:]:
        d += f"L {x} {y} "
    return d


# ── o acervo de formas ───────────────────────────────────────────────────
# Escolhidos pelo VOCABULARIO DO KLIPE: os verbos que a ferramenta faz e os
# nomes dos paineis que ela tem. Nao e um pacote de icone generico.

ICONES: dict[str, str] = {
    # ── o que se faz com video ──────────────────────────────────────────
    "tesoura":   _c(6, 6, 3) + _c(6, 18, 3) + _l(20, 4, 8.12, 15.88)
                 + _l(14.47, 14.48, 20, 20) + _l(8.12, 8.12, 12, 12),
    "play":      _p((6, 3), (20, 12), (6, 21)) + "Z ",
    "pausa":     _r(6, 4, 4, 16, 1) + _r(14, 4, 4, 16, 1),
    "gravar":    _c(12, 12, 10) + _c(12, 12, 4),
    "filme":     _r(2, 2, 20, 20, 2.5) + _l(2, 8, 22, 8) + _l(2, 16, 22, 16)
                 + _l(7, 2, 7, 22) + _l(17, 2, 17, 22),
    "camera":    _r(2, 6, 14, 12, 2) + _p((22, 8), (16, 12), (22, 16)) + "Z ",
    "tela":      _r(2, 3, 20, 14, 2) + _l(8, 21, 16, 21) + _l(12, 17, 12, 21),
    "cortar":    _p((6, 2), (6, 18), (22, 18)) + _p((2, 6), (18, 6), (18, 22)),
    "camadas":   _p((12, 2), (22, 7), (12, 12), (2, 7)) + "Z "
                 + _p((2, 12), (12, 17), (22, 12))
                 + _p((2, 17), (12, 22), (22, 17)),
    "grade":     _r(3, 3, 7, 7, 1) + _r(14, 3, 7, 7, 1)
                 + _r(3, 14, 7, 7, 1) + _r(14, 14, 7, 7, 1),

    # ── som ─────────────────────────────────────────────────────────────
    "microfone": _r(9, 2, 6, 12, 3) + _p((5, 11), (5, 12))
                 + "M 5 11 A 7 7 0 0 0 19 11 " + _l(12, 19, 12, 22)
                 + _l(8, 22, 16, 22),
    "volume":    _p((11, 5), (6, 9), (2, 9), (2, 15), (6, 15), (11, 19)) + "Z "
                 + "M 15.5 8.5 A 5 5 0 0 1 15.5 15.5 "
                 + "M 18.5 5.5 A 9 9 0 0 1 18.5 18.5 ",
    "musica":    _l(9, 18, 9, 4) + _l(9, 4, 21, 2) + _l(21, 2, 21, 16)
                 + _c(6, 18, 3) + _c(18, 16, 3),
    "onda":      _l(2, 10, 2, 14) + _l(5, 8, 5, 16) + _l(8, 4, 8, 20)
                 + _l(11, 9, 11, 15) + _l(14, 6, 14, 18) + _l(17, 10, 17, 14)
                 + _l(20, 7, 20, 17) + _l(22, 11, 22, 13),

    # ── texto e titulo ──────────────────────────────────────────────────
    "texto":     _l(4, 5, 20, 5) + _l(12, 5, 12, 20) + _l(8, 20, 16, 20),
    "legenda":   _r(2, 5, 20, 14, 2.5) + _l(6, 12, 10, 12) + _l(14, 12, 18, 12)
                 + _l(6, 15.5, 13, 15.5),
    "citacao":   "M 3 21 C 3 15 5 12 10 11 M 10 11 L 10 5 L 4 5 L 4 11 Z "
                 "M 14 21 C 14 15 16 12 21 11 M 21 11 L 21 5 L 15 5 L 15 11 Z ",
    "lista":     _l(8, 6, 21, 6) + _l(8, 12, 21, 12) + _l(8, 18, 21, 18)
                 + _c(3.5, 6, 1.2) + _c(3.5, 12, 1.2) + _c(3.5, 18, 1.2),

    # ── imagem ──────────────────────────────────────────────────────────
    "imagem":    _r(3, 3, 18, 18, 2.5) + _c(8.5, 8.5, 1.5)
                 + _p((21, 15), (16, 10), (3, 21)),
    "zoom":      _c(11, 11, 8) + _l(16.65, 16.65, 22, 22)
                 + _l(8, 11, 14, 11) + _l(11, 8, 11, 14),
    "olho":      "M 2 12 C 5 6 9 4 12 4 C 15 4 19 6 22 12 "
                 "C 19 18 15 20 12 20 C 9 20 5 18 2 12 Z " + _c(12, 12, 3),
    "recorte":   _r(3, 3, 18, 18, 2) + _l(3, 9, 21, 9) + _l(9, 3, 9, 21),

    # ── IA e automacao ──────────────────────────────────────────────────
    "faisca":    "M 12 2 C 12 7 13 9 18 10 C 13 11 12 13 12 18 "
                 "C 12 13 11 11 6 10 C 11 9 12 7 12 2 Z "
                 "M 19 15 C 19 17 19.5 18 21.5 18.5 C 19.5 19 19 20 19 22 "
                 "C 19 20 18.5 19 16.5 18.5 C 18.5 18 19 17 19 15 Z ",
    "varinha":   _l(3, 21, 15, 9) + _l(15, 9, 18, 12) + _l(18, 12, 21, 9)
                 + _l(21, 9, 18, 6) + _l(18, 6, 15, 9) + _l(9, 3, 9, 7)
                 + _l(7, 5, 11, 5),
    "raio":      _p((13, 2), (4, 14), (11, 14), (11, 22), (20, 10), (13, 10))
                 + "Z ",
    "chip":      _r(6, 6, 12, 12, 1.5) + _r(9, 9, 6, 6, 0.5)
                 + _l(9, 2, 9, 6) + _l(15, 2, 15, 6) + _l(9, 18, 9, 22)
                 + _l(15, 18, 15, 22) + _l(2, 9, 6, 9) + _l(2, 15, 6, 15)
                 + _l(18, 9, 22, 9) + _l(18, 15, 22, 15),
    "chat":      "M 3 5 A 2 2 0 0 1 5 3 H 19 A 2 2 0 0 1 21 5 V 15 "
                 "A 2 2 0 0 1 19 17 H 8 L 3 21 Z ",

    # ── arquivo e maquina ───────────────────────────────────────────────
    "pasta":     "M 2 6 A 2 2 0 0 1 4 4 H 9 L 11.5 7 H 20 A 2 2 0 0 1 22 9 "
                 "V 18 A 2 2 0 0 1 20 20 H 4 A 2 2 0 0 1 2 18 Z ",
    "salvar":    "M 3 5 A 2 2 0 0 1 5 3 H 16 L 21 8 V 19 A 2 2 0 0 1 19 21 "
                 "H 5 A 2 2 0 0 1 3 19 Z " + _r(7, 3, 10, 6, 0)
                 + _r(7, 13, 10, 8, 0),
    "baixar":    _l(12, 3, 12, 16) + _p((7, 11), (12, 16), (17, 11))
                 + _p((3, 19), (3, 21), (21, 21), (21, 19)),
    "nuvem_nao": ("M 6.5 19 A 4.5 4.5 0 0 1 6.5 10 "
                  "A 6 6 0 0 1 18 9.5 A 4.5 4.5 0 0 1 17.5 19 Z ")
                 + _l(3, 3, 21, 21),
    "cadeado":   _r(3, 11, 18, 11, 2) + "M 7 11 V 7 A 5 5 0 0 1 17 7 V 11 ",
    "relogio":   _c(12, 12, 10) + _p((12, 6), (12, 12), (16.5, 14.5)),
    "ajustes":   _l(4, 6, 20, 6) + _l(4, 12, 20, 12) + _l(4, 18, 20, 18)
                 + _c(9, 6, 2) + _c(15, 12, 2) + _c(7, 18, 2),
    "alvo":      _c(12, 12, 10) + _c(12, 12, 6) + _c(12, 12, 2),
    "check":     _p((4, 12.5), (9.5, 18), (20, 6)),
}


# ── o gesto ──────────────────────────────────────────────────────────────

def icone(nome: str, x: float = 0.0, y: float = 0.0, tam: float = 96.0,
          t: float = 0.0, cor: str = "#FFFFFF", traco: float = TRACO,
          escreve: bool = False, dur: float = 0.45,
          preenche: bool = False) -> dict:
    """Uma camada de `path` pronta.

    `escreve=True` troca o aparecer pelo DESENHAR: o `traco` corre o contorno,
    e o icone se escreve na tela. E o que um Lottie pronto nao te da de graca.

    `preenche=True` pinta em vez de contornar — serve pros que sao silhueta
    (play, raio, faisca) quando voce quer peso em vez de linha.
    """
    d = ICONES.get(nome)
    if d is None:
        raise KeyError(f"icone {nome!r} nao existe. Tem: "
                       + ", ".join(sorted(ICONES)))
    c: dict = {
        "tipo": "path", "d": d, "centrar": True,
        "x": x, "y": y, "escala": tam / CAIXA,
        "cor": cor if preenche else "#00000000",
    }
    if not preenche:
        c["contorno"] = cor
        c["contorno_larg"] = traco
    if escreve:
        c["traco"] = [[t, 0.0, "outCubic"], [t + dur * 2, 1.0]]
        c["opacidade"] = [[t, 0], [t + 0.08, 1]]
    else:
        c["opacidade"] = [[t, 0], [t + dur, 1, "outCubic"]]
        c["escala"] = {"mola": {"damping": 14, "stiffness": 110, "mass": 0.5},
                       "em": t, "de": (tam / CAIXA) * 0.7, "para": tam / CAIXA}
    return c


def nomes() -> list[str]:
    return sorted(ICONES)


# ── folha de provas ──────────────────────────────────────────────────────
# Path SVG errado NAO da erro: da rabisco. A unica conferencia que vale e
# olhar, e por isso isto e um alvo de execucao e nao um comentario.

if __name__ == "__main__":
    import skia
    from .cena import Cena, validar

    COLS, TAM, PASSO = 7, 110, 250
    itens = nomes()
    linhas = math.ceil(len(itens) / COLS)
    W = COLS * PASSO
    H = linhas * PASSO + 40
    C = []
    for i, n in enumerate(itens):
        col, lin = i % COLS, i // COLS
        cx = (col - (COLS - 1) / 2) * PASSO
        cy = (linhas - 1) / 2 * PASSO - lin * PASSO
        C.append(icone(n, cx, cy + 26, TAM, 0.0, "#7C6BE8"))
        C.append({"tipo": "texto", "texto": n, "tamanho": 22, "peso": 600,
                  "cor": "#8B93A7", "x": cx, "y": cy - 76, "opacidade": 1.0})
    spec = {"duracao": 1.0, "fundo": "#0A0B0F", "camadas": C}
    erros = validar(spec)
    print(f"  {len(itens)} icones · {erros or 'valida'}")
    if erros:
        raise SystemExit(1)
    surf = skia.Surface(W, H)
    Cena(spec, W, H, 30).desenhar(surf.getCanvas(), 0.9)
    destino = RAIZ / "output" / "_icones.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    surf.makeImageSnapshot().save(str(destino))
    print(f"  folha em {destino}  ({W}x{H})")
