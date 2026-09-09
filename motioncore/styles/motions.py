"""
motions.py — os 8 motion graphics que faltavam.

`descending`, `wordCollapse`, `echoWords`, `liveComments`, `paradoxQuote`,
`sensoryStorm`, `mixedSerif` e `letterEyebrow`. São os estilos mais elaborados
do Klipe: pilha que desaba com gravidade, frases em eco, comentários de live
subindo, tempestade de palavras. Ficaram de fora da primeira leva porque a
edição precisava rodar sem motor de navegador e eu portei o essencial primeiro.

Original de cada um: o template antigo, `if (style === "<nome>")`.
"""
from __future__ import annotations

import math

import skia

from ..anim import interpolate, spring
from ..box import camada_alpha, camada_blur, preenche, transform
from ..text import Shadow, TextBlock, css_color
from ._common import TitleCtx, css_opacity
from .basicos import ACC, _rgba, Estilo, _bloco, _flex_linhas, _linhas

SANS = "'Montserrat', sans-serif"
# familia LITERAL do TSX: 'PlayfairDisplay' sem espaco CASA com o @font-face
# (diferente do `quote`, que escreve 'Playfair Display' e cai na Georgia)
SERIF = "'PlayfairDisplay', Georgia, serif"


# ══════════════════════════════════════════════════════════════════════
# DESCENDING — palavras caindo de cima, uma a uma
# ══════════════════════════════════════════════════════════════════════
def desc_build(ctx: TitleCtx, reg, w, h):
    return [_bloco(ctx, reg, p, ctx.font(SANS), 60, 800, ctx.clr, None,
                   maiuscula=True, sombras=[Shadow(0, 4, 24, "rgba(0,0,0,0.95)")])
            for p in (ctx.text or "").split() if p]


def desc_anim(ctx: TitleCtx, blocos=None):
    n = len(blocos or ())
    return (round(css_opacity(ctx.opacity), 6),
            tuple(spring(max(0.0, ctx.frame - i * 4), ctx.fps,
                         damping=10, stiffness=200, mass=0.4) for i in range(n)))


def desc_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or desc_build(ctx, reg, w, h)
    op, molas = desc_anim(ctx, blocos)
    if op <= 0 or not blocos:
        return
    largura = w - 200                          # `padding: 0 100px`
    linhas = _flex_linhas(blocos, largura, 18)  # `gap: 0 18px` (so na horizontal)
    alt_linha = max(b.height for b in blocos)
    total = len(linhas) * alt_linha
    topo = (h - 0.20 * h) - total              # `bottom: 20%`
    cx = w / 2

    caixa = skia.Rect.MakeXYWH(0, topo - 90, w, total + 180)
    with camada_alpha(canvas, caixa, op):
        preenche(canvas, skia.Rect.MakeXYWH(-60, topo - 40, w + 120, total + 80),
                 ("radial", "rgba(0,0,0,0.6) 0%, transparent 70%"))
        i, y = 0, topo
        for palavras, larg in linhas:
            x = cx - larg / 2
            for b in palavras:
                e = molas[i]
                borrao = interpolate(e, [0, 0.5, 1], [12, 2, 0])
                with transform(canvas, (0, 0),
                               translate=(0, interpolate(e, [0, 1], [-80, 0]))):
                    cb = skia.Rect.MakeXYWH(x - 40, y - 40, b.width + 80, b.height + 80)
                    with camada_blur(canvas, cb, borrao):
                        b.draw(canvas, x + b.width / 2, y, opacity=css_opacity(e))
                x += b.width + 18
                i += 1
            y += alt_linha


# ══════════════════════════════════════════════════════════════════════
# WORDCOLLAPSE — pilha de palavras que desaba com gravidade
# ══════════════════════════════════════════════════════════════════════
COLAPSO = 2.6          # segundos ate a pilha ruir


def wc_build(ctx: TitleCtx, reg, w, h):
    palavras = _linhas(ctx.text)[:6]
    out = []
    for i, p in enumerate(palavras):
        impar = i % 2 == 1
        out.append(_bloco(ctx, reg, p, ctx.font(SANS), 86 if impar else 104, 900,
                          "#fff" if impar else ACC, None, ls=-1,
                          sombras=([Shadow(0, 4, 18, "rgba(0,0,0,0.8)")] if impar
                                   else [Shadow(0, 0, 26, ACC + "66")])))
    return out


def wc_anim(ctx: TitleCtx, blocos=None):
    n = len(blocos or ())
    t = ctx.frame / ctx.fps
    entradas, quedas = [], []
    for i in range(n):
        entradas.append(spring(max(0.0, ctx.frame - i * 7), ctx.fps,
                               damping=14, stiffness=170, mass=0.7))
        ft = max(0.0, t - COLAPSO - i * 0.12)
        quedas.append((round(0.5 * 2100 * ft * ft, 4),               # s = ½gt²
                       round(ft * (55 if i % 2 == 0 else -48), 4),
                       round(max(0.0, 1 - ft * 0.75) if ft > 0 else 1.0, 6)))
    trinca = round(max(0.0, 1 - (t - COLAPSO) * 0.8), 6) if t > COLAPSO - 0.25 else 0.0
    escala_trinca = round(min(1.0, (t - COLAPSO + 0.25) * 3), 6) if t > COLAPSO - 0.25 else 0.0
    return (round(css_opacity(ctx.opacity), 6), tuple(entradas), tuple(quedas),
            trinca, escala_trinca)


def wc_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or wc_build(ctx, reg, w, h)
    op, entradas, quedas, trinca, esc_trinca = wc_anim(ctx, blocos)
    if op <= 0:
        return
    with camada_alpha(canvas, None, op):
        preenche(canvas, skia.Rect.MakeWH(w, h),
                 ("radial", f"rgba(8,6,4,{0.62*op}) 0%, rgba(4,3,2,{0.88*op}) 100%"))
        for i, b in enumerate(blocos):
            e = entradas[i]
            queda_y, rot, op_queda = quedas[i]
            y = 300 + i * 190
            alfa = css_opacity(e * op_queda)
            if alfa <= 0:
                continue
            cy = y + b.height / 2
            with transform(canvas, (w / 2, cy),
                           translate=(0, interpolate(e, [0, 1], [70, 0]) + queda_y),
                           scale=0.85 + 0.15 * e, rotate=rot):
                b.draw(canvas, w / 2, y, opacity=alfa)
        if trinca > 0 and esc_trinca > 0:
            larg = (w * 0.88) * esc_trinca
            preenche(canvas, skia.Rect.MakeXYWH(w / 2 - larg / 2, 1180, larg, 4),
                     ("linear", 90, f"transparent 0%, {ACC} 50%, transparent 100%"),
                     alpha=trinca)


# ══════════════════════════════════════════════════════════════════════
# ECHOWORDS — frases em eco que sobem e somem
# ══════════════════════════════════════════════════════════════════════
EW_FRIO = "#9aa6c4"


def ew_build(ctx: TitleCtx, reg, w, h):
    frases = _linhas(ctx.text)[:5]
    out = []
    for i, p in enumerate(frases):
        destaque = i == len(frases) - 1
        principal = _bloco(ctx, reg, p, ctx.font(SANS), 62, 800,
                           ACC if destaque else "#e8ecf5", None, ls=0.5,
                           sombras=[Shadow(0, 3, 16, "rgba(0,0,0,0.85)")],
                           largura_max=w * 0.88)
        # as duas copias fantasma atras, maiores e borradas
        ecos = [_bloco(ctx, reg, p, ctx.font(SANS), 62 + e * 6, 800,
                       ACC if destaque else EW_FRIO, None, largura_max=w * 0.88)
                for e in (2, 1)]
        out.append((principal, ecos))
    return out


def ew_anim(ctx: TitleCtx, blocos=None):
    vals = []
    for i in range(len(blocos or ())):
        lp = max(0.0, ctx.frame - i * 20)
        vida = lp / ctx.fps
        vals.append((spring(lp, ctx.fps, damping=20, stiffness=120),
                     round(vida * 26, 4),                                  # sobe
                     round(max(0.0, 1 - max(0.0, vida - 2.2) * 0.55), 6)))  # some
    return (round(css_opacity(ctx.opacity), 6), tuple(vals))


def ew_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or ew_build(ctx, reg, w, h)
    op, vals = ew_anim(ctx, blocos)
    if op <= 0:
        return
    with camada_alpha(canvas, None, op):
        preenche(canvas, skia.Rect.MakeWH(w, h), ("linear", 180,
                 f"rgba(6,7,12,{0.55*op}) 0%, rgba(4,5,9,{0.86*op}) 55%, "
                 f"rgba(6,7,12,{0.55*op}) 100%"))
        for i, (principal, ecos) in enumerate(blocos):
            surge, sobe, some = vals[i]
            # 1240 e 150 foram afinados pra um quadro de 1920 de altura. Em
            # 1080 a primeira frase ja nasce 160 px abaixo da borda, e o que
            # se via era a peca cortada pela base. `ev` e 1.0 em 9:16, entao
            # o formato de origem nao muda um pixel.
            y = (1240 - i * 150 - sobe) * ctx.ev
            for k, eco in enumerate(ecos):          # e = 2 depois 1
                e = 2 - k
                alfa = css_opacity(surge * some * (0.13 / e))
                if alfa <= 0:
                    continue
                cb = skia.Rect.MakeXYWH(0, y + e * 9 - 40, w, eco.height + 80)
                with camada_blur(canvas, cb, e * 3):
                    eco.draw(canvas, w / 2, y + e * 9, opacity=alfa)
            principal.draw(canvas, w / 2, y, opacity=css_opacity(surge * some))


# ══════════════════════════════════════════════════════════════════════
# LIVECOMMENTS — comentarios de live subindo
# ══════════════════════════════════════════════════════════════════════
LC_CORES = ["#E8940A", "#7C5CFA", "#E63F8A", "#00C9C9",
            "#00D97E", "#FF6B6B", "#5B8DEF", "#F5A623"]
LC_PASSO, LC_SUBIDA, LC_BASE = 1.15, 118, 1500


def lc_build(ctx: TitleCtx, reg, w, h):
    out = []
    for i, bruto in enumerate(_linhas(ctx.text)):
        ci = bruto.find(":")
        nome = bruto[:ci].strip() if ci > 0 else ""
        msg = bruto[ci + 1:].strip() if ci > 0 else bruto
        cor = LC_CORES[i % len(LC_CORES)]
        inicial = (nome or "A")[0].upper()
        out.append({
            "cor": cor,
            "inicial": _bloco(ctx, reg, inicial, ctx.font(SANS), 26, 900, "#0d0e12", None),
            "nome": (_bloco(ctx, reg, nome, ctx.font(SANS), 20, 800, cor, None)
                     if nome else None),
            "msg": _bloco(ctx, reg, msg, ctx.font(SANS), 30, 600, "#fff", 1.25,
                          align="left", largura_max=900 - 58 - 14 - 40),
        })
    return out


def lc_anim(ctx: TitleCtx, blocos=None):
    t = ctx.frame / ctx.fps
    vals = []
    for i in range(len(blocos or ())):
        t0 = i * LC_PASSO
        vida = t - t0
        if vida < 0:
            vals.append(None)
            continue
        # A faixa inteira e proporcional: em 1080 os comentarios nasciam em
        # 1500, ou seja 420 px ABAIXO da borda, e levavam 3,56 s so pra
        # entrar no quadro. Em clipe curto horizontal o estilo era tela preta.
        ev = ctx.ev
        base, saida, banda = LC_BASE * ev, 380 * ev, 240 * ev
        y = base - vida * LC_SUBIDA * ev
        if y < saida:                     # ja saiu por cima
            vals.append(None)
            continue
        entra = spring(max(0.0, ctx.frame - round(t0 * ctx.fps)), ctx.fps,
                       damping=16, stiffness=190, mass=0.6)
        fade = (max(0.0, (y - saida) / banda)
                if y < saida + banda else 1.0)
        vals.append((round(y, 3), entra, round(fade, 6)))
    return (round(css_opacity(ctx.opacity), 6), tuple(vals))


def lc_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or lc_build(ctx, reg, w, h)
    op, vals = lc_anim(ctx, blocos)
    if op <= 0:
        return
    with camada_alpha(canvas, None, op):
        # escurecida so na base, pra ler sem tapar o rosto
        preenche(canvas, skia.Rect.MakeXYWH(0, h - 900, w, 900), ("linear", 180,
                 "rgba(4,5,9,0) 0%, rgba(4,5,9,0.55) 55%, rgba(4,5,9,0.72) 100%"),
                 alpha=op)
        for i, item in enumerate(blocos):
            v = vals[i]
            if v is None:
                continue
            y, entra, fade = v
            alfa = css_opacity(entra * fade)
            if alfa <= 0:
                continue
            with transform(canvas, (0, 0),
                           translate=(interpolate(entra, [0, 1], [-40, 0]), 0)):
                with camada_alpha(canvas, None, alfa):
                    x = 52
                    # avatar redondo com a inicial
                    preenche(canvas, skia.Rect.MakeXYWH(x, y, 58, 58), item["cor"], raio=29)
                    ini = item["inicial"]
                    item["inicial"].draw(canvas, x + 29, y + (58 - ini.height) / 2)
                    # bolha do comentario
                    bx = x + 58 + 14
                    nome, msg = item["nome"], item["msg"]
                    alt = 24 + (nome.height + 3 if nome else 0) + msg.height
                    larg = 40 + max(msg.width, nome.width if nome else 0)
                    preenche(canvas, skia.Rect.MakeXYWH(bx, y, larg, alt),
                             "rgba(12,14,20,0.86)", raio=18)
                    ty = y + 12
                    if nome:
                        nome.draw(canvas, bx + 20 + nome.width / 2, ty)
                        ty += nome.height + 3
                    msg.draw(canvas, bx + 20 + msg.width / 2, ty)


# ══════════════════════════════════════════════════════════════════════
# PARADOXQUOTE — duas metades que se opoem, com divisor
# ══════════════════════════════════════════════════════════════════════
PQ_FRIO = "#7FA8C9"


def pq_build(ctx: TitleCtx, reg, w, h):
    p = [x.strip() for x in (ctx.text or "").split("|")]
    def _p(i, padrao):
        return p[i] if len(p) > i and p[i] else padrao
    # O padrao aqui era o texto de UM cliente ("Muito normal / PRA SER AUTISTA /
    # e muito estranho / FAZER NORMAL"). Era a camada mais funda daquele vies:
    # a biblioteca e o catalogo ja tinham sido limpos, mas o MOTOR ainda
    # carregava o assunto de um video especifico como reserva.
    #
    # Agora o padrao descreve a FORMA do estilo — leve/forte, leve/forte — que
    # e o que a pessoa precisa ver pra entender o que ela vai escrever.
    partes = [(_p(0, "linha leve"), _p(1, "LINHA FORTE"), ACC),
              (_p(2, "outra leve"), _p(3, "OUTRA FORTE"), PQ_FRIO)]
    out = []
    for linha, chave, cor in partes:
        out.append((
            _bloco(ctx, reg, linha, ctx.font(SANS), 46, 600,
                   "rgba(255,255,255,0.82)", None, ls=0.5, largura_max=w * 0.88),
            _bloco(ctx, reg, chave, ctx.font(SANS), 78, 900, cor, 1.05, ls=-0.5,
                   largura_max=w * 0.88),
            cor))
    out.append(_bloco(ctx, reg, "≠", ctx.font(SANS), 30, 900, "#fff", None))
    return out


def pq_anim(ctx: TitleCtx, blocos=None):
    t = ctx.frame / ctx.fps
    return (round(css_opacity(ctx.opacity), 6),
            spring(ctx.frame, ctx.fps, damping=17, stiffness=150),
            spring(max(0.0, ctx.frame - 26), ctx.fps, damping=17, stiffness=150),
            round(interpolate(ctx.frame, [20, 40], [0, 1], "clamp", "clamp"), 6),
            round(0.75 + 0.25 * math.sin(t * 2.4), 6),
            round(0.75 + 0.25 * math.sin(t * 2.4 + math.pi), 6))


def pq_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or pq_build(ctx, reg, w, h)
    op, e1, e2, cresce, glow1, glow2 = pq_anim(ctx, blocos)
    if op <= 0:
        return
    metades, simbolo = blocos[:2], blocos[2]
    with camada_alpha(canvas, None, op):
        preenche(canvas, skia.Rect.MakeWH(w, h),
                 ("radial", f"rgba(6,8,13,{0.70*op}) 0%, rgba(3,4,8,{0.92*op}) 100%"))
        # 560 e 960 sao as ancoras do original, em quadro de 1920. A segunda
        # metade comeca em 960 e desce mais uns 200 — em 1080 ela sai pela
        # base, que e o "VAZAv" que a medicao acusou.
        for k, (topo_y, entra, glow, vira) in enumerate(
                ((560 * ctx.ev, e1, glow1, False),
                 (960 * ctx.ev, e2, glow2, True))):
            linha, chave, cor = metades[k]
            alfa = css_opacity(entra)
            if alfa <= 0:
                continue
            dx = interpolate(entra, [0, 1], [60 if vira else -60, 0])
            with transform(canvas, (0, 0), translate=(dx, 0)):
                with camada_alpha(canvas, None, alfa):
                    linha.draw(canvas, w / 2, topo_y)
                    y2 = topo_y + linha.height + 6      # `margin-bottom: 6`
                    # o glow do TSX pulsa: `0 0 (18+16*glow)px cor88`
                    chave.shadows = [Shadow(0, 0, 18 + 16 * glow, cor + "88")]
                    chave._sh_cache = {}
                    chave._flat_cache = {}
                    chave.draw(canvas, w / 2, y2)
        if cresce > 0:
            larg = (w * 0.76) * cresce
            preenche(canvas, skia.Rect.MakeXYWH(w / 2 - larg / 2, 880, larg, 3),
                     ("linear", 90, f"transparent 0%, {ACC} 33%, {PQ_FRIO} 66%, transparent 100%"))
            with transform(canvas, (w / 2, 852 + 29),
                           rotate=interpolate(cresce, [0, 1], [-90, 0])):
                with camada_alpha(canvas, None, css_opacity(cresce)):
                    preenche(canvas, skia.Rect.MakeXYWH(w / 2 - 29, 852, 58, 58),
                             "rgba(8,10,16,0.92)", raio=29)
                    simbolo.draw(canvas, w / 2, 852 + (58 - simbolo.height) / 2)


# ══════════════════════════════════════════════════════════════════════
# SENSORYSTORM — tempestade de palavras espalhadas
# ══════════════════════════════════════════════════════════════════════
SS_PALETA = ["#E8940A", "#F0F0F0", "#FFB347", "#A0A0A0", "#FFFFFF"]


def _hash(n: float) -> float:
    """Mesmo hash do TSX: caotico na aparencia, deterministico no resultado."""
    s = math.sin(n * 12.9898 + 78.233) * 43758.5453
    return s - math.floor(s)


def ss_build(ctx: TitleCtx, reg, w, h):
    palavras = _linhas(ctx.text)
    out = []
    for i, p in enumerate(palavras):
        semente = i + 1
        cor = SS_PALETA[i % len(SS_PALETA)]
        tam = 36 + _hash(semente * 3.1) * 90
        # `'Bebas Neue'` COM espaco nao casa com o @font-face 'BebasNeue' —
        # o Chrome cai no proximo da lista, 'Impact'. Ver a nota em fonts.py.
        fam = "'Bebas Neue', 'Impact', sans-serif" if i % 2 == 0 else SANS
        out.append({
            "b": _bloco(ctx, reg, p, ctx.font(fam), round(tam), 900, cor, None,
                        ls=4 if i % 3 == 0 else 1, maiuscula=True,
                        sombras=[Shadow(0, 0, 20, cor + "80"),
                                 Shadow(0, 4, 16, "rgba(0,0,0,0.9)")]),
            "x": (8 + _hash(semente * 1.7) * 84) / 100,
            "y": (8 + _hash(semente * 2.3) * 84) / 100,
            "rot": (_hash(semente * 4.7) - 0.5) * 30,
            "borrao": 0.5 if i % 5 == 0 else 0.0,
        })
    return out


def ss_anim(ctx: TitleCtx, blocos=None):
    f = ctx.frame
    vals = []
    for i in range(len(blocos or ())):
        entra = spring(f - i * 3, ctx.fps, damping=8, stiffness=140, mass=0.6)
        pisca = (1.0 if i % 4 != 0 else (1.0 if math.sin(f * 0.5 + i) > -0.7 else 0.3))
        vals.append((entra,
                     round(math.sin(f * 0.3 + i * 1.7) * 4, 4),
                     round(math.cos(f * 0.27 + i * 2.1) * 3, 4),
                     round(pisca, 4)))
    return (round(css_opacity(ctx.opacity), 6),
            round(0.85 + 0.15 * math.sin(f * 0.4) * math.sin(f * 0.13), 6),
            tuple(vals))


def ss_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or ss_build(ctx, reg, w, h)
    op, flicker, vals = ss_anim(ctx, blocos)
    if op <= 0:
        return
    preenche(canvas, skia.Rect.MakeWH(w, h), ("radial",
             f"rgba(40,28,12,{0.95*op*flicker}) 0%, rgba(15,12,8,{0.98*op}) 70%, "
             f"rgba(0,0,0,{op}) 100%"))
    # scan lines de CRT: `repeating-linear-gradient(0deg, transparent 3px,
    # rgba(255,255,255,0.02) 3px 4px)`. Alpha 5 de 255 — quase invisivel, mas
    # cobre a tela toda e NAO e multiplicado pelo opacity no TSX.
    linha = skia.Paint(AntiAlias=False, Color=css_color("rgba(255,255,255,0.02)"))
    for y in range(3, int(h), 4):
        canvas.drawRect(skia.Rect.MakeXYWH(0, y, w, 1), linha)
    for i, item in enumerate(blocos):
        entra, jx, jy, pisca = vals[i]
        alfa = css_opacity(op * entra * pisca)
        if alfa <= 0:
            continue
        b = item["b"]
        cx, cy = item["x"] * w, item["y"] * h
        # `translate(-50%,-50%)` centra a palavra no ponto
        topo = cy - b.height / 2
        with transform(canvas, (cx, cy), translate=(jx, jy),
                       scale=max(0.0, entra), rotate=item["rot"]):
            cb = skia.Rect.MakeXYWH(cx - b.width / 2 - 40, topo - 40,
                                    b.width + 80, b.height + 80)
            with camada_blur(canvas, cb, item["borrao"]):
                b.draw(canvas, cx, topo, opacity=alfa)
    # vinheta: visao tunelada
    preenche(canvas, skia.Rect.MakeWH(w, h),
             ("radial", f"transparent 40%, rgba(0,0,0,{0.7*op}) 100%"))


# ══════════════════════════════════════════════════════════════════════
# MIXEDSERIF — sans branca e serif italica alternando, inclinado
# ══════════════════════════════════════════════════════════════════════
def ms_build(ctx: TitleCtx, reg, w, h):
    out = []
    for i, ln in enumerate(_linhas(ctx.text)):
        serif = i % 2 == 1
        # A caixa e shrink-to-fit dentro da tela, entao a linha quebra quando
        # passa da largura disponivel — descontado o padding do proprio lado
        # (`padding-left: 60` no serif, `padding-right: 40` no sans). Sem esse
        # limite a linha serifada saía numa linha so e vazava o quadro.
        out.append(_bloco(
            ctx, reg, ln, SERIF if serif else SANS, 108 if serif else 76,
            700 if serif else 900, ACC if serif else "#FFFFFF", 1.0,
            ls=0 if serif else -1, italico=serif, largura_max=w - (60 if serif else 40),
            sombras=([Shadow(0, 0, 46, _rgba(ACC, 0.65)),
                      Shadow(0, 0, 90, _rgba(ACC, 0.35))] if serif else [])))
    return out


def ms_anim(ctx: TitleCtx, blocos=None):
    return (round(interpolate(ctx.frame,
                              [ctx.duration_frames - 9, ctx.duration_frames - 1],
                              [1, 0], "clamp", "clamp"), 6),
            tuple(spring(ctx.frame - i * 4, ctx.fps, damping=14, stiffness=130)
                  for i in range(len(blocos or ()))))


def ms_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or ms_build(ctx, reg, w, h)
    sai, molas = ms_anim(ctx, blocos)
    if sai <= 0 or not blocos:
        return
    # o TSX NAO multiplica pelo `opacity` do ViralTitle aqui — so pelo `exit`
    alt = sum(b.height for b in blocos) - 26 * (len(blocos) - 1)
    topo = (h - alt) / 2
    cx = w / 2
    with camada_alpha(canvas, None, css_opacity(sai)):
        with transform(canvas, (cx, h / 2), rotate=-3):
            y = topo
            for i, b in enumerate(blocos):
                serif = i % 2 == 1
                e = molas[i]
                # `padding-left: 60` no serif, `padding-right: 40` no sans:
                # deslocam o texto centralizado pra um lado
                desloc = 30 if serif else -20
                with transform(canvas, (0, 0),
                               translate=((1 - e) * (70 if serif else -70), 0)):
                    b.draw(canvas, cx + desloc, y, opacity=css_opacity(min(1.0, e * 1.2)))
                y += b.height - (26 if i < len(blocos) - 1 else 0)


# ══════════════════════════════════════════════════════════════════════
# LETTEREYEBROW — sobrancelha + manchete + rabicho serifado
# ══════════════════════════════════════════════════════════════════════
def le_partes(texto: str):
    brutas = [x.strip() for x in (texto or "").split("|") if x.strip()]
    if len(brutas) >= 3:
        return brutas[0], brutas[1], brutas[2]
    if len(brutas) == 2:
        return "", brutas[0], brutas[1]
    ws = (brutas[0] if brutas else "").split()
    if len(ws) >= 4:
        return ws[0], " ".join(ws[1:-1]), ws[-1]
    if len(ws) == 3:
        return ws[0], ws[1], ws[2]
    if len(ws) == 2:
        return "", ws[0], ws[1]
    return "", (ws[0] if ws else ""), ""


def le_build(ctx: TitleCtx, reg, w, h):
    sobrancelha, principal, rabicho = le_partes(ctx.text)
    base = ctx.color or "#FFFFFF"
    acc = ctx.color2 or ACC
    sombra = []          # sem sombra preta (pedido do user 2026-08-03)
    larg = w * 0.88
    return [
        (_bloco(ctx, reg, sobrancelha, ctx.font(SANS), 30, 700, base, None, ls=6,
                maiuscula=True, sombras=sombra, largura_max=larg)
         if sobrancelha else None),
        _bloco(ctx, reg, principal, ctx.font(SANS), 96, 900, base, 0.98,
               sombras=sombra, largura_max=larg),
        (_bloco(ctx, reg, rabicho, SERIF, 44, 500, acc, None, italico=True,
                sombras=sombra, largura_max=larg) if rabicho else None),
    ]


def le_anim(ctx: TitleCtx, blocos=None):
    return (round(css_opacity(
                interpolate(ctx.frame,
                            [ctx.duration_frames - 9, ctx.duration_frames - 1],
                            [1, 0], "clamp", "clamp") * ctx.opacity), 6),
            spring(ctx.frame, ctx.fps, damping=16, stiffness=140),
            spring(max(0.0, ctx.frame - 4), ctx.fps, damping=16, stiffness=140),
            spring(max(0.0, ctx.frame - 8), ctx.fps, damping=16, stiffness=140))


def le_draw(canvas, ctx: TitleCtx, reg, w, h, blocos=None):
    blocos = blocos or le_build(ctx, reg, w, h)
    vis, e1, e2, e3 = le_anim(ctx, blocos)
    if vis <= 0:
        return
    sobra, principal, rabicho = blocos
    alt = ((sobra.height + 8) if sobra else 0) + principal.height \
        + ((rabicho.height + 4) if rabicho else 0)
    topo = (h - alt) / 2
    cx = w / 2
    with camada_alpha(canvas, None, vis):
        y = topo
        if sobra:
            sobra.draw(canvas, cx, y, opacity=css_opacity(e1))
            y += sobra.height + 8                      # `margin-bottom: 8`
        with transform(canvas, (0, 0), translate=(0, (1 - e2) * 22)):
            principal.draw(canvas, cx, y, opacity=css_opacity(e2))
        y += principal.height
        if rabicho:
            y += 4                                     # `margin-top: 4`
            rabicho.draw(canvas, cx, y, opacity=css_opacity(e3))


def _sig(nome, fn):
    return lambda ctx, blocos: (nome,) + tuple(fn(ctx, blocos))


ESTILOS = {
    "descending": Estilo(desc_build, desc_draw, _sig("desc", desc_anim)),
    "wordCollapse": Estilo(wc_build, wc_draw, _sig("wc", wc_anim)),
    "echoWords": Estilo(ew_build, ew_draw, _sig("ew", ew_anim)),
    "liveComments": Estilo(lc_build, lc_draw, _sig("lc", lc_anim)),
    "paradoxQuote": Estilo(pq_build, pq_draw, _sig("pq", pq_anim)),
    "sensoryStorm": Estilo(ss_build, ss_draw, _sig("ss", ss_anim)),
    "mixedSerif": Estilo(ms_build, ms_draw, _sig("ms", ms_anim)),
    "letterEyebrow": Estilo(le_build, le_draw, _sig("le", le_anim)),
}
