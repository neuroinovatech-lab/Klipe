"""
slide_reveal.py — porta do `slideReveal` (linhas deslizam com máscara de recorte).

Original: src/VideoEditor.tsx linha ~3380. Minimalista P&B: cada linha desliza
de fora pra dentro por trás de uma janela de recorte (`overflow: hidden`),
alternando direita/esquerda. "|" separa as linhas; a linha do MEIO é a grande
(96px peso 900), as outras são pequenas (44px peso 500, minúsculas, tracking 4).

Foi o primeiro estilo que a usuária clicou e viu sumir — o motor não o
desenhava. Entra na frente da fila por isso.
"""
from __future__ import annotations

import skia

from ..anim import interpolate, spring
from ..text import Shadow, TextBlock
from ._common import TitleCtx, css_opacity

LINE_HEIGHT = 1.05
STAGGER = 3          # frames de defasagem entre linhas


def _linhas(text: str) -> list[str]:
    return [x.strip() for x in (text or "").split("|") if x.strip()]


def build(ctx: TitleCtx, registry, canvas_w: int, canvas_h: int):
    linhas = _linhas(ctx.text)
    meio = len(linhas) // 2
    blocos = []
    for i, ln in enumerate(linhas):
        small = (i != meio) and len(linhas) > 1
        cor = (ctx.color or "#FFFFFF") if small else (ctx.color2 or ctx.color or "#FFFFFF")
        blocos.append(TextBlock(
            registry=registry,
            text=ln.lower() if small else ln,
            css_family=ctx.font("'Montserrat', sans-serif"),
            weight=500 if small else 900,
            font_size=44 if small else 96,
            color=cor,
            line_height=LINE_HEIGHT,
            letter_spacing=4.0 if small else -1.0,
            shadows=[Shadow(0, 3, 14, "rgba(0,0,0,0.8)")],
            max_width=None,
        ))
    return blocos


def _anim(ctx: TitleCtx, n: int):
    saida = interpolate(ctx.frame,
                        [ctx.duration_frames - 8, ctx.duration_frames - 1], [1, 0],
                        "clamp", "clamp")
    entradas = [spring(max(0.0, ctx.frame - i * STAGGER), ctx.fps,
                       damping=17, stiffness=160) for i in range(n)]
    return saida, entradas


def signature(ctx: TitleCtx, blocos) -> tuple:
    saida, entradas = _anim(ctx, len(blocos or ()))
    grupo = round(css_opacity(saida), 4)
    if grupo <= 0:
        return ("vazio",)
    return (grupo, tuple(round(e, 5) for e in entradas))


def draw(canvas: skia.Canvas, ctx: TitleCtx, registry, canvas_w: int, canvas_h: int,
         blocos=None):
    if blocos is None:
        blocos = build(ctx, registry, canvas_w, canvas_h)
    if not blocos:
        return
    saida, entradas = _anim(ctx, len(blocos))
    grupo = css_opacity(saida)
    if grupo <= 0:
        return

    altura = sum(b.height for b in blocos)
    y = (canvas_h - altura) / 2
    cx = canvas_w / 2

    for i, b in enumerate(blocos):
        from_right = (i % 2 == 0)
        off = (1.0 - entradas[i]) * b.width          # 100% da largura da linha
        dx = off if from_right else -off
        # a JANELA de recorte é a caixa da linha: o texto desliza por trás
        # dela — sem o clip, viraria um slide comum sem "reveal"
        canvas.save()
        canvas.clipRect(skia.Rect.MakeXYWH(cx - b.width / 2, y, b.width, b.height))
        b.draw(canvas, cx + dx, y, opacity=grupo)
        canvas.restore()
        y += b.height
