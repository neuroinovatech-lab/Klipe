"""
box.py — as primitivas de CAIXA do CSS: fundo, gradiente, canto, blur.

O `stackedReveal` e a legenda eram texto puro. Os oito estilos mais usados
(lower3rd, hero, flash, kinetic, panel, ribbon, counter, quote) sao texto DENTRO
de caixas: painel com gradiente, barrinha de destaque, sublinhado, brilho
radial atras. Isso mora aqui.

Duas armadilhas do CSS que custam caro se passarem batido:

**Gradiente ate `transparent`.** O CSS interpola gradiente em espaco
PRE-MULTIPLICADO. O Skia, por padrao, interpola sem pre-multiplicar — e ai
`#E8940A -> transparent` passa por cinza sujo no meio, porque `transparent` e
preto com alpha 0. `kInterpolateColorsInPremul_Flag` resolve.

**`filter: blur(Npx)` NAO e a mesma escala de `text-shadow`.** No filtro, N e o
desvio padrao da gaussiana. Na sombra, N e o raio e o desvio e N/2. Trocar um
pelo outro deixa o borrao com o dobro (ou a metade) do tamanho.
"""
from __future__ import annotations

import math
import re
from contextlib import contextmanager

import skia

from .text import css_color

PREMUL = skia.GradientShader.kInterpolateColorsInPremul_Flag


def parse_stops(spec: str):
    """
    `"rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.6) 85%, transparent 100%"`
    -> ([cores], [posicoes 0-1])

    Sem posicao explicita, os stops se espalham por igual, como no CSS.
    """
    partes, nivel, atual = [], 0, ""
    for ch in spec:
        if ch == "(":
            nivel += 1
        elif ch == ")":
            nivel -= 1
        if ch == "," and nivel == 0:
            partes.append(atual.strip())
            atual = ""
        else:
            atual += ch
    if atual.strip():
        partes.append(atual.strip())

    cores, poss = [], []
    for p in partes:
        m = re.search(r"\s([\d.]+)%\s*$", p)
        if m:
            poss.append(float(m.group(1)) / 100.0)
            p = p[:m.start()].strip()
        else:
            poss.append(None)
        cores.append(css_color("rgba(0,0,0,0)" if p == "transparent" else p))

    if poss[0] is None:
        poss[0] = 0.0
    if poss[-1] is None:
        poss[-1] = 1.0
    # preenche buracos distribuindo por igual entre os conhecidos
    i = 0
    while i < len(poss):
        if poss[i] is None:
            j = i
            while poss[j] is None:
                j += 1
            passo = (poss[j] - poss[i - 1]) / (j - i + 1)
            for k in range(i, j):
                poss[k] = poss[i - 1] + passo * (k - i + 1)
            i = j
        i += 1
    return cores, poss


def linear_gradient(rect: skia.Rect, angulo: float, stops: str) -> skia.Shader:
    """
    `linear-gradient(<angulo>deg, <stops>)`.

    No CSS 0deg aponta pra CIMA e o angulo cresce no sentido horario — nao e o
    mesmo referencial da matematica. 90deg = esquerda -> direita.
    """
    cores, poss = parse_stops(stops)
    rad = math.radians(angulo)
    dx, dy = math.sin(rad), -math.cos(rad)
    w, h = rect.width(), rect.height()
    # comprimento da linha do gradiente, como o CSS define
    comp = abs(w * dx) + abs(h * dy)
    cx, cy = rect.centerX(), rect.centerY()
    p0 = skia.Point(cx - dx * comp / 2, cy - dy * comp / 2)
    p1 = skia.Point(cx + dx * comp / 2, cy + dy * comp / 2)
    return skia.GradientShader.MakeLinear([p0, p1], cores, poss, flags=PREMUL)


def radial_ellipse(rect: skia.Rect, stops: str,
                   centro: tuple[float, float] = (0.5, 0.5)) -> skia.Shader:
    """
    `radial-gradient(ellipse [at X% Y%], <stops>)`.

    `centro` e a posicao em fracao da caixa — o `at 40% 60%` do CSS. Deixar no
    meio quando o estilo pede deslocado joga o brilho no lugar errado (foi o
    que aconteceu no compound2).

    O Skia so tem gradiente radial circular; a elipse sai de uma matriz local
    que estica o circulo nos dois eixos. O tamanho e `farthest-corner`, o
    padrao do CSS: a elipse passa pelo canto mais distante do centro.
    """
    cores, poss = parse_stops(stops)
    w, h = rect.width(), rect.height()
    if w <= 0 or h <= 0:
        return None
    cx = rect.left() + centro[0] * w
    cy = rect.top() + centro[1] * h
    # farthest-side em cada eixo, depois esticado ate o canto mais distante
    rx = max(cx - rect.left(), rect.right() - cx) or 1.0
    ry = max(cy - rect.top(), rect.bottom() - cy) or 1.0
    dx = max(abs(cx - rect.left()), abs(rect.right() - cx))
    dy = max(abs(cy - rect.top()), abs(rect.bottom() - cy))
    k = math.hypot(dx / rx, dy / ry) or 1.0
    m = skia.Matrix()
    m.setTranslate(cx, cy)
    m.preScale(rx * k, ry * k)
    return skia.GradientShader.MakeRadial(
        skia.Point(0, 0), 1.0, cores, poss, flags=PREMUL, localMatrix=m)


def preenche(canvas: skia.Canvas, rect: skia.Rect, fundo, raio=None,
             alpha: float = 1.0):
    """
    Pinta uma caixa. `fundo` pode ser cor CSS, uma spec de gradiente
    (`("linear", angulo, stops)` / `("radial", stops)`) ou um Shader pronto.
    `raio` e um numero ou 4 pares (canto superior esquerdo em diante).
    """
    if rect.isEmpty():
        return
    p = skia.Paint(AntiAlias=True)
    if isinstance(fundo, str):
        p.setColor(css_color(fundo))
    elif isinstance(fundo, tuple) and fundo and fundo[0] == "linear":
        p.setShader(linear_gradient(rect, fundo[1], fundo[2]))
    elif isinstance(fundo, tuple) and fundo and fundo[0] == "radial":
        # ("radial", stops) ou ("radial", stops, (fx, fy)) pro `at X% Y%`
        sh = radial_ellipse(rect, fundo[1], fundo[2] if len(fundo) > 2 else (0.5, 0.5))
        if sh is None:
            return
        p.setShader(sh)
    else:
        p.setShader(fundo)
    if alpha < 1.0:
        p.setAlphaf(p.getAlphaf() * alpha)

    if not raio:
        canvas.drawRect(rect, p)
    elif isinstance(raio, (int, float)):
        canvas.drawRRect(skia.RRect.MakeRectXY(rect, raio, raio), p)
    else:
        rr = skia.RRect()
        rr.setRectRadii(rect, [skia.Point(*r) if isinstance(r, tuple)
                               else skia.Point(r, r) for r in raio])
        canvas.drawRRect(rr, p)


@contextmanager
def camada_blur(canvas: skia.Canvas, limites: skia.Rect, sigma: float):
    """
    `filter: blur(Npx)` do CSS — aqui N JA e o desvio padrao (diferente de
    `text-shadow`, onde N e o raio e o desvio e N/2).

    Sem limites apertados isso aloca a tela toda; por isso `limites` e
    obrigatorio.
    """
    if sigma <= 0.3:
        yield
        return
    p = skia.Paint(ImageFilter=skia.ImageFilters.Blur(sigma, sigma))
    canvas.saveLayer(limites.makeOutset(sigma * 3 + 2, sigma * 3 + 2), p)
    try:
        yield
    finally:
        canvas.restore()


@contextmanager
def camada_alpha(canvas: skia.Canvas, limites: skia.Rect | None, alpha: float):
    """`opacity` do CSS: agrupa o elemento inteiro antes de aplicar."""
    if alpha >= 1.0:
        yield
        return
    canvas.saveLayerAlpha(limites, int(round(max(0.0, alpha) * 255)))
    try:
        yield
    finally:
        canvas.restore()


@contextmanager
def transform(canvas: skia.Canvas, origem: tuple[float, float],
              translate: tuple[float, float] = (0.0, 0.0), scale: float = 1.0,
              scale_y: float | None = None, rotate: float = 0.0):
    """`transform` do CSS em torno de `origem` (centro da caixa, por padrao)."""
    canvas.save()
    canvas.translate(origem[0] + translate[0], origem[1] + translate[1])
    if rotate:
        canvas.rotate(rotate)
    sy = scale if scale_y is None else scale_y
    if scale != 1.0 or sy != 1.0:
        canvas.scale(scale, sy)
    canvas.translate(-origem[0], -origem[1])
    try:
        yield
    finally:
        canvas.restore()
