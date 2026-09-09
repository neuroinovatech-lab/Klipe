"""
livre.py — o estilo que o criador de templates monta.

Os outros estilos são PORTES: cada um reproduz um layout fixo que já existia no
motor de navegador, e os overrides (`font1..3`, `color1..3`) só ajustam o que aquele
layout já desenhava. Por isso param em 3 partes — é o que os originais usavam.

Este aqui é o contrário: não tem layout próprio. Ele lê uma lista de partes de
tamanho livre e desenha cada uma com a fonte, o tamanho, a cor, o peso e a
ANIMAÇÃO DE ENTRADA que você escolheu pra ela. É o que permite construir um
título do zero em vez de escolher entre os prontos.

Cada parte:
    {
      "texto":     "PERTENCER",
      "fonte":     "BebasNeue",        (vazio = Montserrat)
      "tamanho":   96,                 (px, na escala de 1080x1920)
      "cor":       "#FFFFFF",
      "peso":      800,
      "italico":   false,
      "entrada":   "subir",            (ver ENTRADAS)
      "atraso":    4,                  (frames depois da parte anterior)
      "alinha":    "centro",           (esquerda | centro | direita)
      "espaco":    0                   (px extras acima desta parte)
    }
"""
from __future__ import annotations

import skia

from ..anim import interpolate, spring
from ..text import TextBlock, css_transform
from ._common import TitleCtx, css_opacity

# Os tamanhos das partes são em px referenciados ao LADO CURTO do quadro.
# Escalar pela largura faria o mesmo template sair 78% maior em 16:9 que em
# 9:16; pelo lado curto, "tamanho 96" quer dizer a mesma coisa nos dois.
BASE_W = 1080
STAGGER_PADRAO = 4     # frames entre uma parte e a seguinte

# Cada entrada devolve (dx, dy, escala, opacidade) a partir do progresso 0..1.
# Ficam juntas aqui pra `draw` e `signature` lerem exatamente a mesma conta —
# se divergirem, o dedup de frame passa a mentir e o título "congela".
ENTRADAS = {
    "nenhuma":  lambda p: (0.0, 0.0, 1.0, 1.0),
    "fade":     lambda p: (0.0, 0.0, 1.0, p),
    "subir":    lambda p: (0.0, 40 * (1 - p), 1.0, p),
    "descer":   lambda p: (0.0, -40 * (1 - p), 1.0, p),
    "esquerda": lambda p: (-60 * (1 - p), 0.0, 1.0, p),
    "direita":  lambda p: (60 * (1 - p), 0.0, 1.0, p),
    "escala":   lambda p: (0.0, 0.0, 0.7 + 0.3 * p, p),
    "estourar": lambda p: (0.0, 0.0, 1.18 - 0.18 * p, p),
}


def _partes(ctx: TitleCtx) -> list[dict]:
    """A lista de partes; sem ela, cai pro texto separado por `|`."""
    ps = getattr(ctx, "partes", None)
    if ps:
        return [p for p in ps if str(p.get("texto", "")).strip()]
    return [{"texto": t.strip()} for t in str(ctx.text or "").split("|") if t.strip()]


def _prog(ctx: TitleCtx, i: int, p: dict) -> float:
    """Progresso da entrada desta parte, 0..1."""
    if (p.get("entrada") or "subir") == "nenhuma":
        return 1.0
    atraso = float(p.get("atraso", STAGGER_PADRAO)) * i
    return spring(max(0.0, ctx.frame - atraso), ctx.fps, damping=15, stiffness=170)


def build(ctx: TitleCtx, registry, canvas_w: int, canvas_h: int):
    esc = 1.0   # a escala de formato ja vem da transform do TitleRenderer          # acompanha o formato do projeto
    blocos = []
    for p in _partes(ctx):
        fam = p.get("fonte") or ""
        blocos.append(TextBlock(
            registry=registry,
            text=str(p.get("texto", "")),
            css_family=f"'{fam}', sans-serif" if fam else ctx.font("'Montserrat', sans-serif"),
            weight=int(p.get("peso", 800)),
            italic=bool(p.get("italico")),
            font_size=max(8, round(float(p.get("tamanho", 80)) * esc)),
            color=p.get("cor") or ctx.clr,
            line_height=1.05,
            align=p.get("alinha", "centro").replace("centro", "center")
                                          .replace("esquerda", "left")
                                          .replace("direita", "right"),
            max_width=canvas_w * 0.92,
        ))
    return blocos


def signature(ctx: TitleCtx, blocos) -> tuple:
    grupo = round(css_opacity(ctx.opacity), 4)
    if grupo <= 0:
        return ("vazio",)
    ps = _partes(ctx)
    return (grupo, tuple(round(_prog(ctx, i, p), 5) for i, p in enumerate(ps)))


def draw(canvas: skia.Canvas, ctx: TitleCtx, registry, canvas_w: int, canvas_h: int,
         blocos=None):
    if blocos is None:
        blocos = build(ctx, registry, canvas_w, canvas_h)
    ps = _partes(ctx)
    if not blocos or not ps:
        return
    grupo = css_opacity(ctx.opacity)
    if grupo <= 0:
        return

    esc = 1.0   # a escala de formato ja vem da transform do TitleRenderer
    espacos = [float(p.get("espaco", 0)) * esc for p in ps]
    altura = sum(b.height for b in blocos) + sum(espacos[1:])
    # `posY` NAO entra aqui: a transform externa do TitleRenderer ja aplicou.
    # Aplicar de novo dobraria o deslocamento.
    y = (canvas_h - altura) / 2

    for i, (b, p) in enumerate(zip(blocos, ps)):
        if i:
            y += espacos[i]
        dx, dy, escala, op = ENTRADAS.get(p.get("entrada") or "subir",
                                          ENTRADAS["subir"])(_prog(ctx, i, p))
        alinha = p.get("alinha", "centro")
        centro_x = (canvas_w / 2 if alinha == "centro"
                    else canvas_w * 0.04 + b.width / 2 if alinha == "esquerda"
                    else canvas_w * 0.96 - b.width / 2)

        canvas.save()
        # a escala gira no centro da propria parte, senao o texto "foge" pro canto
        css_transform(canvas, (centro_x, y + b.height / 2),
                      (dx * esc, dy * esc), escala)
        b.draw(canvas, centro_x, y, opacity=grupo * css_opacity(op))
        canvas.restore()
        y += b.height
