"""
restantes.py — os tres estilos que ainda obrigavam O motor de navegador a subir.

`pointList`, `compound2` e `cutMask` sao os unicos que sobravam no projeto de
referencia. Enquanto UM titulo precisar do motor de navegador, o bundle inteiro sobe —
13 s antes de renderizar o primeiro frame. Portar estes tres nao e por causa do
tempo de desenho deles; e pra apagar esse custo fixo.

Original de cada um: o template antigo, `if (style === "<nome>")`.
"""
from __future__ import annotations

import skia

from ..anim import interpolate, spring
from ..box import camada_alpha, camada_blur, preenche, transform
from ..text import Shadow, TextBlock, css_color
from ._common import TitleCtx, css_opacity
from .basicos import ACC, Estilo, _bloco, _linhas


# ══════════════════════════════════════════════════════════════════════
# CUTMASK — clarao curto de corte (8 frames)
# ══════════════════════════════════════════════════════════════════════
def cut_build(ctx: TitleCtx, reg, w, h):
    return []


def cut_anim(ctx: TitleCtx, blocos=None):
    entra = interpolate(ctx.frame, [0, 3], [0, 1], "clamp", "clamp")
    sai = interpolate(ctx.frame, [5, 8], [1, 0], "clamp", "clamp")
    return (round(min(entra, sai) * 0.55 * css_opacity(ctx.opacity), 6),)


def cut_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    (a,) = cut_anim(ctx, blocos)
    if a <= 0:
        return
    # `mix-blend-mode: screen` sobre fundo transparente e igual a desenhar
    # normal — nao ha o que clarear atras dentro do overlay alpha.
    preenche(canvas, skia.Rect.MakeWH(w, h),
             ("radial", f"rgba(255,255,255,{a}) 0%, rgba(255,255,255,{a*0.6}) 35%, "
                        f"rgba(255,255,255,0) 75%"))


def cut_sig(ctx, blocos):
    return ("cut",) + cut_anim(ctx, blocos)


# ══════════════════════════════════════════════════════════════════════
# POINTLIST — cartao escuro com lista de topicos
# ══════════════════════════════════════════════════════════════════════
# `width: 640` e a largura TOTAL do cartao, nao a do conteudo: o bundle do
# motor de navegador aplica `box-sizing: border-box`, entao padding e borda cabem dentro
# dos 640. Medido: o cartao do motor de navegador tem 640 px de ponta a ponta, nao 713.
CARD_TOTAL = 640
PAD_X, PAD_Y = 34, 30
BORDA = 5             # `border-left: 5px solid`
CARD_CONTEUDO = CARD_TOTAL - BORDA - 2 * PAD_X
GAP_ITEM = 16
DIAMANTE = 14


def pl_build(ctx: TitleCtx, reg, w, h):
    partes = _linhas(ctx.text)
    cabecalho = partes[0] if partes and partes[0] else ""
    itens = partes[1:7]
    fam = ctx.font("'Montserrat', sans-serif")
    cab = (_bloco(ctx, reg, cabecalho, fam, 18, 800, ACC, None, ls=3,
                  maiuscula=True, align="left", largura_max=CARD_CONTEUDO)
           if cabecalho else None)
    # o texto do item divide a linha com o diamante e o gap
    larg_item = CARD_CONTEUDO - DIAMANTE - GAP_ITEM
    blocos = [_bloco(ctx, reg, it, fam, 30, 700, "#fff", 1.2, align="left",
                     largura_max=larg_item)
              for it in itens]
    return [cab] + blocos


def pl_anim(ctx: TitleCtx, blocos=None):
    n = max(0, len(blocos or ()) - 1)
    return (round(css_opacity(ctx.opacity), 6),
            spring(ctx.frame, ctx.fps, damping=16, stiffness=150, mass=0.7),
            tuple(spring(max(0.0, ctx.frame - 8 - i * 6), ctx.fps,
                         damping=17, stiffness=200, mass=0.6) for i in range(n)))


def pl_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or pl_build(ctx, reg, w, h)
    op, entra, molas = pl_anim(ctx, blocos)
    if op <= 0:
        return
    cab, itens = blocos[0], blocos[1:]

    alt_itens = [max(b.height, DIAMANTE) for b in itens]
    conteudo = (cab.height + 20 if cab else 0) + sum(alt_itens) \
        + GAP_ITEM * max(0, len(itens) - 1)
    card_h = conteudo + 2 * PAD_Y
    card_w = CARD_TOTAL
    esq = 0.04 * w                       # `left: 4%`
    topo = h / 2 - card_h / 2            # `top: 50%` + `translateY(-50%)`

    caixa = skia.Rect.MakeXYWH(esq - 20, topo - 20, card_w + 40, card_h + 40)
    with camada_alpha(canvas, caixa, op):
        with transform(canvas, (0, 0),
                       translate=(interpolate(entra, [0, 1], [-50, 0]), 0)):
            with camada_alpha(canvas, caixa, css_opacity(entra)):
                card = skia.Rect.MakeXYWH(esq, topo, card_w, card_h)
                preenche(canvas, card, "rgba(15,17,23,0.92)", raio=16)
                # a borda esquerda vive DENTRO da caixa, colada no canto
                preenche(canvas, skia.Rect.MakeXYWH(esq, topo, BORDA, card_h),
                         ACC, raio=[(16, 16), (0, 0), (0, 0), (16, 16)])

                x_txt = esq + BORDA + PAD_X
                y = topo + PAD_Y
                if cab:
                    cab.draw(canvas, x_txt + cab.width / 2, y)
                    y += cab.height + 20
                for i, b in enumerate(itens):
                    ip = molas[i]
                    linha_h = alt_itens[i]
                    with transform(canvas, (0, 0),
                                   translate=(interpolate(ip, [0, 1], [-22, 0]), 0)):
                        with camada_alpha(canvas, None, css_opacity(ip)):
                            # losango: quadrado girado 45 graus, centrado na linha
                            cd = (x_txt + DIAMANTE / 2, y + linha_h / 2)
                            with transform(canvas, cd, rotate=45, scale=max(0.0, ip)):
                                preenche(canvas, skia.Rect.MakeXYWH(
                                    cd[0] - DIAMANTE / 2, cd[1] - DIAMANTE / 2,
                                    DIAMANTE, DIAMANTE), ACC, raio=3)
                            bx = x_txt + DIAMANTE + GAP_ITEM
                            b.draw(canvas, bx + b.width / 2,
                                   y + (linha_h - b.height) / 2)
                    y += linha_h + GAP_ITEM


def pl_sig(ctx, blocos):
    return ("pl",) + pl_anim(ctx, blocos)


# ══════════════════════════════════════════════════════════════════════
# COMPOUND2 — tres partes empilhadas em escada
# ══════════════════════════════════════════════════════════════════════
# Familia LITERAL do TSX: `'Playfair Display'` com espaco nao casa com o
# @font-face `'PlayfairDisplay'` — quem desenha e a Georgia. Ver fonts.py.
SERIF = "'Playfair Display', Georgia, serif"


def c2_build(ctx: TitleCtx, reg, w, h):
    partes = (ctx.text or "").split("|")
    topo = partes[0].strip() if partes else ""
    meio = partes[1].strip() if len(partes) > 1 else (ctx.text or "")
    base = partes[2].strip() if len(partes) > 2 else ""
    larg = w - 160                        # `padding: 0 80px`

    bt = (_bloco(ctx, reg, topo, ctx.part_font(0, SERIF), 40 * ctx.part_scale(0),
                 700, ctx.part_clr(0), 1.0, italico=True, align="left",
                 largura_max=larg)
          if topo else None)
    bm = _bloco(ctx, reg, meio, ctx.part_font(1, SERIF), 96 * ctx.part_scale(1),
                700, ctx.part_clr(1), 0.85, ls=-2, italico=True, align="left",
                largura_max=larg - 80)
    bb = (_bloco(ctx, reg, base, ctx.part_font(2, "'Montserrat', sans-serif"),
                 34 * ctx.part_scale(2), 600, ctx.part_clr(2), 1.0, align="left",
                 largura_max=larg - 320)
          if base else None)
    return [bt, bm, bb]


def c2_anim(ctx: TitleCtx, blocos=None):
    top = spring(max(0.0, ctx.frame - 1), ctx.fps, damping=14, stiffness=180, mass=0.5)
    mid = spring(ctx.frame, ctx.fps, damping=10, stiffness=120, mass=0.8)
    bot = spring(max(0.0, ctx.frame - 5), ctx.fps, damping=14, stiffness=200, mass=0.5)
    return (round(css_opacity(ctx.opacity), 6),
            top, round(interpolate(top, [0, 0.6, 1], [20, 5, 0]), 6),
            mid, round(interpolate(mid, [0, 1], [1.15, 1]), 6),
            round(interpolate(mid, [0, 0.3, 1], [35, 8, 0]), 6),
            bot, round(interpolate(bot, [0, 1], [25, 0]), 6),
            round(interpolate(bot, [0, 0.5, 1], [18, 4, 0]), 6))


def c2_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or c2_build(ctx, reg, w, h)
    bt, bm, bb = blocos
    (op, top, top_b, mid, mid_s, mid_b, bot, bot_y, bot_b) = c2_anim(ctx, blocos)
    if op <= 0:
        return

    alt = ((bt.height - 14) if bt else 0) + bm.height + ((bb.height - 8) if bb else 0)
    base_y = h - 0.20 * h                 # `bottom: 20%`
    topo = base_y - alt
    esq = 80                              # `padding: 0 80px`
    cx = w / 2

    caixa = skia.Rect.MakeXYWH(0, topo - 60, w, alt + 120)
    with camada_alpha(canvas, caixa, op):
        # `radial-gradient(ellipse at 40% 60%, ...)` — nao e no centro
        preenche(canvas, skia.Rect.MakeXYWH(-60, topo - 20, w + 120, alt + 40),
                 ("radial", "rgba(0,0,0,0.8) 0%, transparent 60%", (0.40, 0.60)))
        y = topo
        if bt:
            dx, dy = ctx.part_offset(0)
            with transform(canvas, (0, 0), translate=(dx, dy)):
                with camada_blur(canvas, caixa, top_b):
                    bt.draw(canvas, esq + bt.width / 2, y, opacity=css_opacity(top))
            y += bt.height - 14           # `margin-bottom: -14`
        dx, dy = ctx.part_offset(1)
        with transform(canvas, (cx, y + bm.height / 2), translate=(dx, dy), scale=mid_s):
            with camada_blur(canvas, caixa, mid_b):
                bm.draw(canvas, esq + 80 + bm.width / 2, y, opacity=css_opacity(mid))
        y += bm.height
        if bb:
            dx, dy = ctx.part_offset(2)
            y -= 8                        # `margin-top: -8`
            with transform(canvas, (0, 0), translate=(dx, dy + bot_y)):
                with camada_blur(canvas, caixa, bot_b):
                    bb.draw(canvas, esq + 320 + bb.width / 2, y,
                            opacity=css_opacity(bot))


def c2_sig(ctx, blocos):
    return ("c2",) + c2_anim(ctx, blocos)


# ══════════════════════════════════════════════════════════════════════
# HEADLINE NEWS — tag na cor de destaque sobre faixa branca, GC de telejornal.
# Original: o template antigo, `if (style === "headlineNews")`.
#
# Era o ULTIMO estilo de titulo que ainda obrigava o Chrome a subir: 1 uso em
# 720 titulos de 27 projetos, segurando O motor de navegador inteiro de pe por causa dele.
# ══════════════════════════════════════════════════════════════════════
HN_TAG_FUNDO = "#E8940A"
HN_TEXTO = "#0D0D10"
HN_FAIXA = "rgba(255,255,255,0.96)"
HN_PAD_TAG_X, HN_PAD_TAG_Y = 20.0, 6.0
HN_PAD_FAIXA_X, HN_PAD_FAIXA_Y = 26.0, 16.0


def _hn_partes(texto: str) -> tuple[str, str]:
    """`"TAG|manchete"`. Sem a barra, a tag e "DESTAQUE" e o texto todo e manchete."""
    ps = [x.strip() for x in (texto or "").split("|") if x.strip()]
    if len(ps) > 1:
        return ps[0], " ".join(ps[1:])
    return "DESTAQUE", (ps[0] if ps else "")


def _hn_larg(w: int) -> float:
    return min(w * 0.88, 1500.0)          # `width: 88%; maxWidth: 1500`


def hn_build(ctx: TitleCtx, reg, w, h):
    tag, manchete = _hn_partes(ctx.text)
    larg = _hn_larg(w)
    return [
        _bloco(ctx, reg, tag, "'Montserrat', sans-serif", 34, 900,
               "#FFFFFF", 1.2, ls=3, maiuscula=True),
        # a faixa ocupa a largura toda do container; o texto quebra dentro dela
        _bloco(ctx, reg, manchete, "'Montserrat', sans-serif", 56, 800,
               HN_TEXTO, 1.2, largura_max=larg - HN_PAD_FAIXA_X * 2,
               align="left"),
    ]


def hn_anim(ctx: TitleCtx, blocos=None):
    entra = spring(ctx.frame, ctx.fps, damping=16, stiffness=130)
    sai = interpolate(ctx.frame,
                      [ctx.duration_frames - 10, ctx.duration_frames - 1],
                      [1, 0], "clamp", "clamp")
    return (round(css_opacity(min(entra, sai) * ctx.opacity), 6),
            round((1 - entra) * -60.0, 6))


def hn_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or hn_build(ctx, reg, w, h)
    op, desliza = hn_anim(ctx, blocos)
    if op <= 0:
        return
    tag_b, faixa_b = blocos
    larg = _hn_larg(w)
    esq = (w - larg) / 2.0                # `alignItems: center`

    tag_h = tag_b.height + HN_PAD_TAG_Y * 2
    tag_w = tag_b.width + HN_PAD_TAG_X * 2
    faixa_h = faixa_b.height + HN_PAD_FAIXA_Y * 2

    # `marginBottom: "24%"` — porcentagem de margem no CSS resolve contra a
    # LARGURA do bloco contenedor, nunca contra a altura. Medir pela altura
    # poria a manchete a 460 px do rodape em vez de 259 num 1080x1920.
    base = h - w * 0.24
    topo = base - (tag_h + faixa_h)

    caixa = skia.Rect.MakeXYWH(esq - 40, topo - 40, larg + 80,
                               tag_h + faixa_h + 80)
    with transform(canvas, (0, 0), translate=(desliza, 0)):
        with camada_alpha(canvas, caixa, op):
            preenche(canvas, skia.Rect.MakeXYWH(esq, topo, tag_w, tag_h),
                     HN_TAG_FUNDO,
                     raio=[(6, 6), (6, 6), (0, 0), (0, 0)])
            preenche(canvas,
                     skia.Rect.MakeXYWH(esq, topo + tag_h, larg, faixa_h),
                     HN_FAIXA, raio=[(0, 0), (8, 8), (8, 8), (8, 8)])
            tag_b.draw(canvas, esq + HN_PAD_TAG_X + tag_b.width / 2,
                       topo + HN_PAD_TAG_Y)
            faixa_b.draw(canvas,
                         esq + HN_PAD_FAIXA_X + faixa_b.width / 2,
                         topo + tag_h + HN_PAD_FAIXA_Y)


def hn_sig(ctx, blocos):
    return ("hn",) + hn_anim(ctx, blocos)


ESTILOS = {
    "cutMask": Estilo(cut_build, cut_draw, cut_sig),
    "pointList": Estilo(pl_build, pl_draw, pl_sig),
    "compound2": Estilo(c2_build, c2_draw, c2_sig),
    "headlineNews": Estilo(hn_build, hn_draw, hn_sig),
}
