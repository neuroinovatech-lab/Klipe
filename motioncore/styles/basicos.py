"""
basicos.py — os oito estilos de titulo que o Klipe realmente usa.

A escolha veio da contagem nos projetos, nao da intuicao: lower3rd (64 usos),
hero (47), flash (29), kinetic (26), panel (22), ribbon (18), counter (17) e
quote (15). Juntos sao 76% de tudo que ja foi posto em timeline. A lista antiga
do plano tinha letterings/scribble/headline, que somam menos de 1%.

Cada estilo e um `Estilo(build, draw, signature)` — mesmo contrato do
`stacked_reveal`, so que agrupados aqui porque compartilham quase todo o
esqueleto (caixa + texto + sublinhado + brilho radial atras).

Original de cada um: src/VideoEditor.tsx, `if (style === "<nome>")`.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable

import skia

from ..anim import interpolate, spring
from ..box import camada_alpha, camada_blur, preenche, transform
from ..text import Shadow, TextBlock
from ._common import TitleCtx, css_opacity

ACC = "#E8940A"


def _clarear(hexa: str, f: float = 0.28) -> str:
    """Puxa a cor pro branco. Serve pro meio do degrade do hero, que antes era
    uma SEGUNDA laranja fixa (`#F0B030`) e nao acompanhava o acento."""
    h = hexa.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02X%02X%02X" % tuple(min(255, int(c + (255 - c) * f))
                                   for c in (r, g, b))


def _rgba(hexa: str, a: float) -> str:
    h = hexa.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"


@dataclass
class Estilo:
    """Adaptador com a mesma cara de um modulo de estilo."""
    build: Callable
    draw: Callable
    signature: Callable | None = None


def _linhas(texto: str) -> list[str]:
    """`|` quebra linha — convencao de todos os estilos multi-linha."""
    ls = [x.strip() for x in (texto or "").split("|")]
    return [x for x in ls if x] or [""]


def _bloco(ctx, reg, texto, familia, tamanho, peso, cor, lh, *, ls=0.0,
           italico=False, sombras=(), largura_max=None, maiuscula=False,
           align="center"):
    """`lh=None` = `line-height: normal` (altura natural da fonte, nao 1)."""
    return TextBlock(
        registry=reg, text=texto.upper() if maiuscula else texto,
        css_family=familia, weight=peso, italic=italico, font_size=tamanho,
        color=cor, line_height=lh, shadows=list(sombras),
        letter_spacing=ls, max_width=largura_max, align=align)


def _pilha(blocos):
    """Altura total de uma pilha de blocos coladas (sem margem)."""
    return sum(b.height for b in blocos)


def _sublinhado(canvas, cx, y, largura, altura, raio, fundo, alpha=1.0):
    if largura <= 0 or alpha <= 0:
        return
    r = skia.Rect.MakeXYWH(cx - largura / 2, y, largura, altura)
    preenche(canvas, r, fundo, raio=raio, alpha=alpha)


# ══════════════════════════════════════════════════════════════════════
# HERO — impacto de tela cheia, com cortina escura por tras
# ══════════════════════════════════════════════════════════════════════
def hero_build(ctx: TitleCtx, reg, w, h):
    linhas = _linhas(ctx.text)
    blocos = [_bloco(ctx, reg, ln, ctx.font("'Gotham', 'Gilroy', sans-serif"),
                     72, 900, ctx.clr, 1.1, ls=5, maiuscula=True,
                     sombras=[Shadow(0, 6, 40, "rgba(0,0,0,1)"),
                              Shadow(0, 0, 80, "rgba(0,0,0,0.6)")],
                     largura_max=w - 200)
              for ln in linhas]
    return blocos


def hero_anim(ctx: TitleCtx, blocos=None):
    return (round(css_opacity(ctx.opacity), 6),
            round(interpolate(ctx.enter, [0, 1], [1.6, 1], "extend", "clamp")
                  * interpolate(ctx.exit_prog, [0, 1], [1, 0.9]), 6),
            round(interpolate(ctx.frame, [0, 8], [16, 0], "clamp", "clamp")
                  + interpolate(ctx.exit_prog, [0, 1], [0, 12]), 6),
            round(interpolate(ctx.frame, [4, 18], [0, 100], "clamp", "clamp"), 6))


def hero_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or hero_build(ctx, reg, w, h)
    op, esc, borrao, hlw = hero_anim(ctx, blocos)
    if op <= 0:
        return

    # A cortina NAO esta dentro do elemento com `opacity` — o alpha dela ja vem
    # multiplicado dentro da propria cor no TSX.
    preenche(canvas, skia.Rect.MakeWH(w, h), ("linear", 180,
             f"rgba(0,0,0,{0.75*op}) 0%, rgba(0,0,0,{0.6*op}) 40%, rgba(0,0,0,{0.7*op}) 100%"))

    texto_h = _pilha(blocos)
    largura = max(b.width for b in blocos)
    total = texto_h + 18 + 6
    topo = (h - total) / 2
    cx = w / 2

    caixa = skia.Rect.MakeXYWH(cx - largura / 2 - 120, topo - 60,
                               largura + 240, total + 120)
    with transform(canvas, (cx, h / 2), scale=esc):
        with camada_blur(canvas, caixa, borrao):
            with camada_alpha(canvas, caixa, op):
                y = topo
                for b in blocos:
                    b.draw(canvas, cx, y)
                    y += b.height
                _sublinhado(canvas, cx, y + 18,
                            min(largura * hlw / 100, 480), 6, 3,
                            ("linear", 90, f"{ACC} 0%, {_clarear(ACC)} 50%, {ACC} 100%"))


def hero_sig(ctx, blocos):
    return ("hero",) + hero_anim(ctx, blocos)


# ══════════════════════════════════════════════════════════════════════
# LOWER3RD — barra inferior com listra de destaque
# ══════════════════════════════════════════════════════════════════════
def l3_build(ctx: TitleCtx, reg, w, h):
    # A caixa e `position:absolute; left:60` SEM largura: encolhe pro conteudo,
    # mas o limite e a borda direita da tela. Descontando a listra (11) e o
    # padding (22+40), sobra isto pro texto — e por isso que o Chrome quebra
    # frase longa em duas linhas.
    largura = w - 60 - 11 - 22 - 40
    return [_bloco(ctx, reg, ln, ctx.font("'Montserrat', sans-serif"), 46, 700,
                   ctx.clr, 1.2, ls=1.5, align="left", largura_max=largura,
                   sombras=[Shadow(0, 2, 8, "rgba(0,0,0,0.5)")])
            for ln in _linhas(ctx.text)]


def l3_anim(ctx: TitleCtx, blocos=None):
    return (round(css_opacity(ctx.opacity), 6),
            round(interpolate(ctx.enter, [0, 1], [-600, 0], "extend", "clamp")
                  + interpolate(ctx.exit_prog, [0, 1], [0, 600]), 6),
            round(min(1.0, interpolate(ctx.frame, [0, 12], [0, 100], "clamp", "clamp") / 100), 6),
            round((interpolate(ctx.frame, [0, 8], [16, 0], "clamp", "clamp")
                   + interpolate(ctx.exit_prog, [0, 1], [0, 12])) * 0.5, 6))


def l3_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or l3_build(ctx, reg, w, h)
    op, desliza, barra, borrao = l3_anim(ctx, blocos)
    if op <= 0:
        return

    texto_h = _pilha(blocos)
    texto_w = max(b.width for b in blocos)
    painel_h = texto_h + 28           # padding 14 em cima e embaixo
    painel_w = 22 + texto_w + 40
    base = h - 310                    # `bottom: 310`
    topo = base - painel_h
    x = 60                            # `left: 60`

    caixa = skia.Rect.MakeXYWH(x - 20, topo - 20, 11 + painel_w + 40, painel_h + 40)
    with transform(canvas, (0, 0), translate=(desliza, 0)):
        with camada_blur(canvas, caixa, borrao):
            with camada_alpha(canvas, caixa, op):
                # listra: cresce de cima pra baixo (`transformOrigin: top`)
                preenche(canvas, skia.Rect.MakeXYWH(x, topo, 11, painel_h * barra),
                         ACC, raio=[(4, 4), (0, 0), (0, 0), (4, 4)])
                preenche(canvas, skia.Rect.MakeXYWH(x + 11, topo, painel_w, painel_h),
                         ("linear", 90, "rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.6) 85%, transparent 100%"),
                         raio=[(0, 0), (4, 4), (4, 4), (0, 0)])
                y = topo + 14
                for b in blocos:
                    b.draw(canvas, x + 11 + 22 + b.width / 2, y)
                    y += b.height


def l3_sig(ctx, blocos):
    return ("l3",) + l3_anim(ctx, blocos)


# ══════════════════════════════════════════════════════════════════════
# FLASH — impacto seco de 1-2 palavras
# ══════════════════════════════════════════════════════════════════════
def flash_build(ctx: TitleCtx, reg, w, h):
    # fonte literal no TSX: nao passa por font(), entao nao aceita override
    return [_bloco(ctx, reg, ln, "'Noka', 'Gotham', sans-serif", 120, 900,
                   ctx.clr, 1.05, ls=8, maiuscula=True,
                   sombras=[Shadow(0, 0, 60, _rgba(ACC, 0.3)),
                            Shadow(0, 8, 50, "rgba(0,0,0,1)")],
                   largura_max=w)
            for ln in _linhas(ctx.text)]


def flash_anim(ctx: TitleCtx, blocos=None):
    spr = spring(ctx.frame, ctx.fps, damping=6, stiffness=300, mass=0.4)
    return (round(css_opacity(ctx.opacity), 6),
            round(interpolate(spr, [0, 1], [2.5, 1]), 6),
            round(interpolate(spr, [0, 0.3, 1], [24, 6, 0]), 6))


def flash_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or flash_build(ctx, reg, w, h)
    op, esc, borrao = flash_anim(ctx, blocos)
    if op <= 0:
        return

    preenche(canvas, skia.Rect.MakeWH(w, h),
             ("radial", f"rgba(0,0,0,{0.5*op}) 0%, transparent 70%"))

    alt = _pilha(blocos)
    largura = max(b.width for b in blocos)
    topo = (h - alt) / 2
    cx = w / 2
    caixa = skia.Rect.MakeXYWH(cx - largura / 2 - 100, topo - 80, largura + 200, alt + 160)

    with transform(canvas, (cx, h / 2), scale=esc):
        with camada_blur(canvas, caixa, borrao):
            with camada_alpha(canvas, caixa, op):
                y = topo
                for b in blocos:
                    b.draw(canvas, cx, y)
                    y += b.height


def flash_sig(ctx, blocos):
    return ("flash",) + flash_anim(ctx, blocos)


# ══════════════════════════════════════════════════════════════════════
# KINETIC — palavras entrando em cascata
# ══════════════════════════════════════════════════════════════════════
def kin_build(ctx: TitleCtx, reg, w, h):
    # o span do TSX nao declara line-height => `normal`, nao 1
    return [_bloco(ctx, reg, p, ctx.font("'Gotham', 'Gilroy', sans-serif"), 68,
                   900, ctx.clr, None, ls=3, maiuscula=True,
                   sombras=[Shadow(0, 4, 30, "rgba(0,0,0,0.95)")])
            for p in (ctx.text or "").split(" ") if p]


def _flex_linhas(blocos, largura_max, gap):
    linhas, atual, larg = [], [], 0.0
    for b in blocos:
        passo = b.width if not atual else gap + b.width
        if atual and larg + passo > largura_max:
            linhas.append((atual, larg))
            atual, larg = [b], b.width
        else:
            atual.append(b)
            larg += passo
    if atual:
        linhas.append((atual, larg))
    return linhas


def kin_anim(ctx: TitleCtx, blocos=None):
    n = len(blocos or ())
    return (round(css_opacity(ctx.opacity), 6),
            round(interpolate(ctx.frame, [4, 18], [0, 100], "clamp", "clamp"), 6),
            round(interpolate(ctx.frame, [10, 22], [0, 0.8], "clamp", "clamp"), 6),
            tuple(spring(max(0.0, ctx.frame - i * 4), ctx.fps,
                         damping=10, stiffness=260, mass=0.4) for i in range(n)))


def kin_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or kin_build(ctx, reg, w, h)
    op, hlw, op_linha, molas = kin_anim(ctx, blocos)
    if op <= 0 or not blocos:
        return

    largura_disp = w - 160                       # `padding: 0 80px`
    linhas = _flex_linhas(blocos, largura_disp, 16)
    altura_linha = max(b.height for b in blocos)
    # `gap: 16` no CSS vale pros DOIS eixos: entre palavras E entre linhas.
    # Aplicar so entre palavras deixa as linhas 16 px coladas demais.
    GAP_LINHA = 16
    texto_h = len(linhas) * altura_linha + (len(linhas) - 1) * GAP_LINHA
    total = texto_h + 14 + 5
    base = h - 0.22 * h                          # `bottom: 22%`
    topo = base - total
    cx = w / 2

    caixa = skia.Rect.MakeXYWH(0, topo - 80, w, total + 160)
    with camada_alpha(canvas, caixa, op):
        preenche(canvas, skia.Rect.MakeXYWH(-120, topo - 60, w + 240, total + 120),
                 ("radial", "rgba(0,0,0,0.7) 0%, transparent 70%"))
        i, y = 0, topo
        for palavras, larg in linhas:
            x = cx - larg / 2
            for b in palavras:
                ws = molas[i]
                borrao = interpolate(ws, [0, 0.5, 1], [10, 3, 0])
                pc = (x + b.width / 2, y + b.height / 2)
                with transform(canvas, pc,
                               translate=(0, interpolate(ws, [0, 1], [60, 0])),
                               scale=interpolate(ws, [0, 1], [0.3, 1])):
                    cx_b = skia.Rect.MakeXYWH(x - 40, y - 40, b.width + 80, b.height + 80)
                    with camada_blur(canvas, cx_b, borrao):
                        b.draw(canvas, x + b.width / 2, y, opacity=css_opacity(ws))
                x += b.width + 16
                i += 1
            y += altura_linha + GAP_LINHA
        _sublinhado(canvas, cx, y + 14, min(largura_disp * hlw / 100, 300), 5, 3,
                    ACC, alpha=op_linha)


def kin_sig(ctx, blocos):
    return ("kin",) + kin_anim(ctx, blocos)


# ══════════════════════════════════════════════════════════════════════
# QUOTE — citacao serifada com aspa de abertura
# ══════════════════════════════════════════════════════════════════════
def quote_build(ctx: TitleCtx, reg, w, h):
    txt = " ".join(p.strip() for p in (ctx.text or "").split("|") if p.strip())
    # Familia LITERAL do TSX: `'Playfair Display'` com espaco nao casa com o
    # @font-face `'PlayfairDisplay'`, entao quem desenha e a Georgia. Ver a nota
    # em fonts.py — nao "corrigir" isso aqui sem mudar o TSX junto.
    FAM = "'Playfair Display', 'Georgia', serif"
    aspa = _bloco(ctx, reg, "“", FAM, 90, 900, ACC, 0.65)
    corpo = _bloco(ctx, reg, txt, FAM, 50, 700,
                   ctx.clr, 1.25, italico=True, align="left",
                   sombras=[Shadow(0, 3, 24, "rgba(0,0,0,0.9)"),
                            Shadow(0, 0, 50, "rgba(0,0,0,0.4)")],
                   largura_max=w - 240 - aspa.width - 8)
    return [aspa, corpo]


def quote_anim(ctx: TitleCtx, blocos=None):
    return (round(css_opacity(ctx.opacity), 6),
            round(interpolate(ctx.enter, [0, 0.5, 1], [14, 3, 0])
                  + interpolate(ctx.exit_prog, [0, 1], [0, 12]), 6),
            round(interpolate(ctx.enter, [0, 1], [40, 0]), 6),
            round(interpolate(ctx.frame, [10, 25], [0, 1], "clamp", "clamp"), 6))


def quote_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or quote_build(ctx, reg, w, h)
    aspa, corpo = blocos
    op, borrao, sobe, op_linha = quote_anim(ctx, blocos)
    if op <= 0:
        return

    linha_h = max(aspa.height, corpo.height)
    total = linha_h + 10 + 4
    base = h - 0.18 * h                          # `bottom: 18%`
    topo = base - total
    esq = 120                                    # `padding: 0 120px`

    caixa = skia.Rect.MakeXYWH(0, topo - 70, w, total + 140)
    with transform(canvas, (w / 2, topo + total / 2), translate=(0, sobe)):
        with camada_blur(canvas, caixa, borrao):
            with camada_alpha(canvas, caixa, op):
                # `inset: -50px -80px` mede da caixa de PADDING do pai (a tela
                # inteira, 0..w), nao da caixa de conteudo (120..w-120).
                preenche(canvas, skia.Rect.MakeXYWH(-80, topo - 50,
                                                    w + 160, total + 100),
                         ("radial", "rgba(0,0,0,0.7) 0%, transparent 70%"))
                # `align-items: flex-start` — os dois colam no topo da linha
                aspa.draw(canvas, esq + aspa.width / 2, topo + 4, opacity=0.8)
                corpo.draw(canvas, esq + aspa.width + 8 + corpo.width / 2, topo)
                _sublinhado(canvas, esq + 100 + 40, topo + linha_h + 10, 80, 4, 2,
                            ACC, alpha=op_linha)


def quote_sig(ctx, blocos):
    return ("quote",) + quote_anim(ctx, blocos)


# ══════════════════════════════════════════════════════════════════════
# RIBBON — faixa horizontal que entra deslizando
# ══════════════════════════════════════════════════════════════════════
def rib_build(ctx: TitleCtx, reg, w, h):
    return [_bloco(ctx, reg, ln, ctx.font("'Gotham', 'Gilroy', sans-serif"), 52,
                   900, ctx.clr, 1.1, ls=4, maiuscula=True,
                   sombras=[Shadow(0, 2, 8, "rgba(0,0,0,0.3)")],
                   largura_max=w - 160)
            for ln in _linhas(ctx.text)]


def rib_anim(ctx: TitleCtx, blocos=None):
    return (round(css_opacity(ctx.opacity), 6),
            round(interpolate(ctx.enter, [0, 1], [1920, 0], "extend", "clamp")
                  + interpolate(ctx.exit_prog, [0, 1], [0, -1920]), 6))


def rib_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or rib_build(ctx, reg, w, h)
    op, desliza = rib_anim(ctx, blocos)
    if op <= 0:
        return
    texto_h = _pilha(blocos)
    faixa_h = texto_h + 36                       # `padding: 18px 80px`
    topo = 0.65 * h                              # `top: 65%`
    cx = w / 2

    caixa = skia.Rect.MakeXYWH(0, topo, w, faixa_h)
    with transform(canvas, (0, 0), translate=(desliza, 0)):
        with camada_alpha(canvas, caixa, op):
            # a faixa era a ultima laranja escondida: a cor vinha escrita
            # dentro da string do degrade, entao nenhum grep por hex achava
            _f = _rgba(ACC, 0.95)
            preenche(canvas, caixa, ("linear", 90,
                     f"transparent 0%, {_f} 8%, {_f} 92%, transparent 100%"))
            y = topo + 18
            for b in blocos:
                b.draw(canvas, cx, y)
                y += b.height


def rib_sig(ctx, blocos):
    return ("rib",) + rib_anim(ctx, blocos)


# ══════════════════════════════════════════════════════════════════════
# COUNTER — numero gigante + rotulo
# ══════════════════════════════════════════════════════════════════════
def cnt_build(ctx: TitleCtx, reg, w, h):
    m = re.match(r"^([\d,.%:]+)\s*(.*)$", ctx.text or "")
    num = m.group(1) if m else (ctx.text or "")
    rot = m.group(2) if m else ""
    nb = _bloco(ctx, reg, num, ctx.font("'BebasNeue', sans-serif"),
                110 if len(num) > 6 else 160, 400, ACC, 1.0, ls=8,
                sombras=[Shadow(0, 0, 60, _rgba(ACC, 0.4)),
                         Shadow(0, 8, 40, "rgba(0,0,0,0.9)")])
    # o rotulo nao declara line-height => `normal`
    rb = (_bloco(ctx, reg, rot, ctx.font("'Montserrat', sans-serif"), 36, 700,
                 "rgba(255,255,255,0.9)", None, ls=5, maiuscula=True,
                 sombras=[Shadow(0, 3, 15, "rgba(0,0,0,0.8)")],
                 largura_max=w - 120)
          if rot else None)
    return [nb, rb]


def cnt_anim(ctx: TitleCtx, blocos=None):
    spr = spring(ctx.frame, ctx.fps, damping=8, stiffness=180, mass=0.9)
    return (round(css_opacity(ctx.opacity), 6),
            round(interpolate(spr, [0, 1], [0.2, 1]), 6),
            round(interpolate(spr, [0, 0.6, 1], [20, 4, 0]), 6),
            round(interpolate(ctx.frame, [4, 18], [0, 100], "clamp", "clamp"), 6),
            round(interpolate(ctx.frame, [12, 26], [0, 1], "clamp", "clamp"), 6),
            round(interpolate(ctx.frame, [12, 26], [20, 0], "clamp", "clamp"), 6))


def cnt_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or cnt_build(ctx, reg, w, h)
    nb, rb = blocos
    op, esc_num, borrao, hlw, op_rot, sobe_rot = cnt_anim(ctx, blocos)
    if op <= 0:
        return

    total = nb.height + (10 + rb.height if rb else 0) + 16 + 4
    base = h - 0.24 * h                          # `bottom: 24%`
    topo = base - total
    cx = w / 2
    largura = max(nb.width, rb.width if rb else 0)

    caixa = skia.Rect.MakeXYWH(0, topo - 100, w, total + 200)
    with camada_alpha(canvas, caixa, op):
        preenche(canvas, skia.Rect.MakeXYWH(-150, topo - 80, w + 300, total + 160),
                 ("radial", "rgba(0,0,0,0.75) 0%, transparent 60%"))
        y = topo
        with transform(canvas, (cx, y + nb.height / 2), scale=esc_num):
            cxn = skia.Rect.MakeXYWH(cx - nb.width / 2 - 60, y - 60,
                                     nb.width + 120, nb.height + 120)
            with camada_blur(canvas, cxn, borrao):
                nb.draw(canvas, cx, y)
        y += nb.height
        if rb:
            y += 10
            with transform(canvas, (cx, y + rb.height / 2), translate=(0, sobe_rot)):
                rb.draw(canvas, cx, y, opacity=css_opacity(op_rot))
            y += rb.height
        _sublinhado(canvas, cx, y + 16, min(largura * hlw / 100, 200), 4, 2,
                    ("linear", 90, f"transparent 10%, {ACC} 50%, transparent 90%"))


def cnt_sig(ctx, blocos):
    return ("cnt",) + cnt_anim(ctx, blocos)


# ══════════════════════════════════════════════════════════════════════
# PANEL — lista numerada na lateral esquerda
# ══════════════════════════════════════════════════════════════════════
def pan_build(ctx: TitleCtx, reg, w, h):
    itens = [x.strip() for x in (ctx.text or "").split("|")]
    largura = 0.44 * w - 65 - 50                 # `width: 44%`, padding 65/50
    out = []
    for i, it in enumerate(itens):
        num = _bloco(ctx, reg, f"{i+1:02d}", ctx.font("'BebasNeue', sans-serif"),
                     38, 400, _rgba(ACC, 0.7), 1.0, ls=3)
        txt = _bloco(ctx, reg, it, ctx.font("'Montserrat', sans-serif"), 44, 700,
                     ctx.clr, 1.15, align="left",
                     sombras=[Shadow(0, 2, 12, "rgba(0,0,0,0.6)")],
                     largura_max=largura)
        out.append((num, txt))
    return out


def pan_anim(ctx: TitleCtx, blocos=None):
    n = len(blocos or ())
    return (round(css_opacity(ctx.opacity), 6),
            round(interpolate(ctx.exit_prog, [0, 1], [0, 12]), 6),
            round(interpolate(ctx.frame, [0, 15], [0, 0.9], "clamp", "clamp"), 6),
            tuple(spring(max(0.0, ctx.frame - i * 7), ctx.fps,
                         damping=12, stiffness=180, mass=0.5) for i in range(n)))


def pan_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or pan_build(ctx, reg, w, h)
    op, borrao_saida, op_barra, molas = pan_anim(ctx, blocos)
    if op <= 0 or not blocos:
        return
    largura_painel = 0.44 * w
    esq = 65
    alturas = [n.height + t.height + 24 for n, t in blocos]   # `marginBottom: 24`
    total = sum(alturas) - 24
    topo = (h - total) / 2

    caixa = skia.Rect.MakeWH(largura_painel, h)
    with camada_blur(canvas, caixa, borrao_saida):
        with camada_alpha(canvas, caixa, op):
            preenche(canvas, caixa, ("linear", 90,
                     "rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.65) 70%, transparent 100%"))
            y = topo
            for i, (num, txt) in enumerate(blocos):
                s = molas[i]
                borrao = interpolate(s, [0, 0.6, 1], [8, 2, 0])
                alt = num.height + txt.height
                cx_i = skia.Rect.MakeXYWH(esq - 30, y - 20,
                                          largura_painel - esq + 60, alt + 40)
                with transform(canvas, (0, 0),
                               translate=(interpolate(s, [0, 1], [-80, 0]), 0)):
                    with camada_blur(canvas, cx_i, borrao):
                        with camada_alpha(canvas, cx_i, css_opacity(s)):
                            num.draw(canvas, esq + num.width / 2, y)
                            txt.draw(canvas, esq + txt.width / 2, y + num.height)
                y += alt + 24
            preenche(canvas, skia.Rect.MakeXYWH(0, 0.12 * h, 5, 0.76 * h),
                     ("linear", 180, f"transparent 0%, {ACC} 50%, transparent 100%"),
                     alpha=op_barra)


def pan_sig(ctx, blocos):
    return ("pan",) + pan_anim(ctx, blocos)


ESTILOS = {
    "hero": Estilo(hero_build, hero_draw, hero_sig),
    "lower3rd": Estilo(l3_build, l3_draw, l3_sig),
    "flash": Estilo(flash_build, flash_draw, flash_sig),
    "kinetic": Estilo(kin_build, kin_draw, kin_sig),
    "quote": Estilo(quote_build, quote_draw, quote_sig),
    "ribbon": Estilo(rib_build, rib_draw, rib_sig),
    "counter": Estilo(cnt_build, cnt_draw, cnt_sig),
    "panel": Estilo(pan_build, pan_draw, pan_sig),
}
