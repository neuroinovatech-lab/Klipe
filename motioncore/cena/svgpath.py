"""
svgpath.py — parser do atributo `d` do SVG pra skia.Path.

Por que escrever isso a mao: o skia-python 144 NAO expoe `Path.ParseSVG` nem
`SkParsePath` (conferido — so tem `SVGCanvas` e `SVGDOM`, que sao pra
documento inteiro, nao pra um path solto). E o `d` do SVG e o formato universal
de vetor: e o que sai do Illustrator, do Figma, do Inkscape, e e o que um
modelo escreve sem precisar aprender formato nosso.

Cobre a gramatica inteira: M L H V C S Q T A Z, maiuscula (absoluto) e
minuscula (relativo), incluindo o arco eliptico — o skia tem o overload com a
parametrizacao do SVG (rx, ry, xAxisRotate, largeArc, sweep, x, y), entao `A`
nao precisa de aproximacao por cubicas.
"""
from __future__ import annotations

import re

import skia

_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
# quantos numeros cada comando consome por repeticao
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def parse(d: str) -> skia.Path:
    """Converte `d` num skia.Path. Levanta ValueError em `d` malformado."""
    toks = _TOKEN.findall(d or "")
    path = skia.Path()
    i = 0
    cmd = ""
    x = y = 0.0                 # ponto atual
    sx = sy = 0.0               # inicio do subpath (pro Z)
    cx = cy = None              # ultimo controle (pro S/T refletirem)

    def num():
        nonlocal i
        if i >= len(toks):
            raise ValueError(f"path acabou no meio do comando {cmd!r}: {d!r}")
        v = toks[i]
        i += 1
        return float(v)

    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
        elif not cmd:
            raise ValueError(f"path comeca sem comando: {d!r}")
        elif cmd in ("M", "m"):
            # repeticao depois de um M vira L implicito (regra do SVG)
            cmd = "L" if cmd == "M" else "l"

        base = cmd.upper()
        if base not in _ARGS:
            raise ValueError(f"comando de path desconhecido: {cmd!r}")
        rel = cmd.islower()
        ox, oy = (x, y) if rel else (0.0, 0.0)

        if base == "Z":
            path.close()
            x, y = sx, sy
            cx = cy = None
            continue

        if base == "M":
            x, y = num() + ox, num() + oy
            path.moveTo(x, y)
            sx, sy = x, y
            cx = cy = None
        elif base == "L":
            x, y = num() + ox, num() + oy
            path.lineTo(x, y)
            cx = cy = None
        elif base == "H":
            x = num() + ox
            path.lineTo(x, y)
            cx = cy = None
        elif base == "V":
            y = num() + oy
            path.lineTo(x, y)
            cx = cy = None
        elif base == "C":
            x1, y1 = num() + ox, num() + oy
            x2, y2 = num() + ox, num() + oy
            x, y = num() + ox, num() + oy
            path.cubicTo(x1, y1, x2, y2, x, y)
            cx, cy = x2, y2
        elif base == "S":
            # o primeiro controle e o reflexo do ultimo — so vale se o comando
            # anterior tambem foi cubica; senao e o proprio ponto atual
            x1, y1 = (2 * x - cx, 2 * y - cy) if cx is not None else (x, y)
            x2, y2 = num() + ox, num() + oy
            x, y = num() + ox, num() + oy
            path.cubicTo(x1, y1, x2, y2, x, y)
            cx, cy = x2, y2
        elif base == "Q":
            x1, y1 = num() + ox, num() + oy
            x, y = num() + ox, num() + oy
            path.quadTo(x1, y1, x, y)
            cx, cy = x1, y1
        elif base == "T":
            x1, y1 = (2 * x - cx, 2 * y - cy) if cx is not None else (x, y)
            x, y = num() + ox, num() + oy
            path.quadTo(x1, y1, x, y)
            cx, cy = x1, y1
        elif base == "A":
            rx, ry, rot = num(), num(), num()
            grande, varre = num(), num()
            x, y = num() + ox, num() + oy
            path.arcTo(rx, ry, rot,
                       skia.Path.kLarge_ArcSize if grande else skia.Path.kSmall_ArcSize,
                       skia.PathDirection.kCW if varre else skia.PathDirection.kCCW,
                       x, y)
            cx = cy = None

    return path


def trecho(path: skia.Path, frac: float) -> skia.Path:
    """Pedaco inicial do path — e o que faz a linha "ser desenhada" na tela.

    Sem isso, "traco progressivo" so da pra fingir com mascara retangular, que
    denuncia na hora em curva.
    """
    if frac >= 1.0:
        return path
    dst = skia.Path()
    if frac <= 0.0:
        return dst
    med = skia.PathMeasure(path, False)
    comps = []
    while True:
        comps.append(med.getLength())
        if not med.nextContour():
            break
    alvo = sum(comps) * frac
    med = skia.PathMeasure(path, False)
    acc = 0.0
    for comp in comps:
        if alvo <= acc:
            break
        med.getSegment(0.0, min(comp, alvo - acc), dst, True)
        acc += comp
        if not med.nextContour():
            break
    return dst
