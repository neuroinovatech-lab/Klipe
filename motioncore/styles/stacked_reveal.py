"""
stacked_reveal.py — porta do estilo `stackedReveal` (empilhado kinetico de Reels).

Original: o template antigo, `if (style === "stackedReveal")` (linha ~3178).

Estrutura no DOM que a gente reproduz:

    AbsoluteFill (flex, centro/centro, opacity = sai * opacity)
      div (text-align:center, max-width:90%)      <- largura = maior linha
        div * N (font-size, line-height:0.98, margin-top:-6 a partir da 2a)

Cada linha entra com spring proprio defasado em 5 frames (`frame - i*5`), sobe
26px e cresce de 0.92 ate 1 — com overshoot, porque o `interpolate` do motor de navegador
extrapola por padrao. Clampar ali mataria o "pop".
"""
from __future__ import annotations

import math

import skia

from ..anim import interpolate, spring
from ..text import Shadow, TextBlock, css_transform
from ._common import TitleCtx, css_opacity

BASE_SZ = 82
LINE_HEIGHT = 0.98
GAP = -6            # margin-top das linhas a partir da segunda
STAGGER = 5         # frames de defasagem entre linhas
RISE = 26           # px que a linha sobe na entrada


def split_lines(text: str) -> list[str]:
    """`"A|B|C"` vira 3 linhas; frase solta vira 2-4 linhas equilibradas."""
    bruto = [x.strip() for x in (text or "").split("|")]
    bruto = [x for x in bruto if x]
    if len(bruto) > 1:
        return bruto[:4]
    ws = [w for w in (bruto[0] if bruto else "").split() if w]
    alvo = 2 if len(ws) <= 3 else 3 if len(ws) <= 6 else 4
    por_linha = math.ceil(len(ws) / alvo) if ws else 1
    linhas = [" ".join(ws[i:i + por_linha]) for i in range(0, len(ws), por_linha)]
    return linhas[:4]


def build(ctx: TitleCtx, registry, canvas_w: int, canvas_h: int):
    """Monta os blocos de texto (medicao) — separado do desenho pra dar cache."""
    linhas = split_lines(ctx.text)
    ACC = ctx.color2 or "#E8940A"
    BASE = ctx.color or "#FFFFFF"
    SANS = ctx.font("'Montserrat', sans-serif")
    SERIF = ctx.font("'PlayfairDisplay', Georgia, serif")

    # A linha de destaque depende da QUANTIDADE de linhas: com 4+ e a terceira,
    # com menos e a ultima. Fixar no indice 2 (como era antes) fazia o destaque
    # sumir no modo legenda, que costuma mandar so 2 linhas.
    i_acc = 2 if len(linhas) >= 4 else len(linhas) - 1

    blocos = []
    for i, ln in enumerate(linhas):
        if i == i_acc:
            fam, italic, weight, sz, cor = SERIF, True, 700, 1.34, ACC
        else:
            fam, italic, weight = SANS, False, (900 if i == 0 else 800)
            sz, cor = (1.0 if i == 0 else 1.1), BASE
        # sem sombra preta (pedido do user 2026-08-03) — so o brilho da accent fica
        shadows = [Shadow(0, 0, 38, ACC + "55")] if cor == ACC else []
        blocos.append(TextBlock(
            registry=registry, text=ln, css_family=fam, weight=weight, italic=italic,
            font_size=round(BASE_SZ * sz), color=cor, line_height=LINE_HEIGHT,
            shadows=shadows, max_width=canvas_w * 0.9,
        ))
    return blocos


def signature(ctx: TitleCtx, blocos) -> tuple:
    """
    Tudo que muda de um frame pro outro. Frames com a mesma assinatura sao
    pixel a pixel identicos — e num titulo de 9s a animacao dura ~1s, entao a
    grande maioria dos frames repete o anterior. Quem renderiza usa isso pra
    nao redesenhar nem reler o mesmo frame varias vezes.
    """
    sai = interpolate(ctx.frame,
                      [ctx.duration_frames - 8, ctx.duration_frames - 1], [1, 0],
                      "clamp", "clamp")
    grupo = round(css_opacity(sai * ctx.opacity), 4)
    if grupo <= 0:
        return ("vazio",)
    linhas = tuple(round(spring(max(0.0, ctx.frame - i * STAGGER), ctx.fps,
                                damping=15, stiffness=150), 5)
                   for i in range(len(blocos or ())))
    return (grupo, linhas)


def draw(canvas: skia.Canvas, ctx: TitleCtx, registry, canvas_w: int, canvas_h: int,
         blocos=None):
    if blocos is None:
        blocos = build(ctx, registry, canvas_w, canvas_h)
    if not blocos:
        return

    sai = interpolate(ctx.frame,
                      [ctx.duration_frames - 8, ctx.duration_frames - 1], [1, 0],
                      "clamp", "clamp")
    grupo = css_opacity(sai * ctx.opacity)
    if grupo <= 0:
        return

    # altura do div externo: soma das caixas + as margens negativas
    altura = sum(b.height for b in blocos) + GAP * (len(blocos) - 1)
    topo = (canvas_h - altura) / 2.0
    center_x = canvas_w / 2.0

    # A camada do grupo vai so ate onde tem tinta: o RISE de entrada e o
    # overshoot do scale sao pequenos, entao uma folga generosa ja cobre.
    caixa = skia.Rect.MakeEmpty()
    yy = topo
    for b in blocos:
        caixa.join(b.ink_bounds(center_x, yy))
        yy += b.height + GAP
    caixa.outset(RISE + 8, RISE + 8)

    tem_layer = grupo < 1.0
    if tem_layer:
        canvas.saveLayerAlpha(caixa, int(round(grupo * 255)))
    y = topo
    for i, b in enumerate(blocos):
        e = spring(max(0.0, ctx.frame - i * STAGGER), ctx.fps, damping=15, stiffness=150)
        escala = interpolate(e, [0, 1], [0.92, 1])
        subida = (1 - e) * RISE
        alfa = css_opacity(e)
        # Depois que o spring assenta a transform vira identidade e nao muda
        # mais ate o fim do titulo. Nesses frames a linha sai de uma imagem
        # pronta em vez de rasterizar os glifos de novo — mesmos pixels,
        # ~20x mais barato. Durante a entrada, redesenha nitido.
        if abs(escala - 1) < 1e-4 and abs(subida) < 1e-3 and alfa >= 1.0:
            b.draw_flat(canvas, center_x, y)
        else:
            canvas.save()
            css_transform(canvas, origin=(center_x, y + b.height / 2.0),
                          translate=(0.0, subida), scale=escala)
            b.draw(canvas, center_x, y, opacity=alfa)
            canvas.restore()
        y += b.height + GAP
    if tem_layer:
        canvas.restore()
