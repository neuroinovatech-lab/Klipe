"""
camadas.py — os tipos de camada do scene graph e como cada uma vira pixel.

A regra estrutural desta pasta: **quem avalia nao desenha, e quem desenha nao
avalia.** Cada camada expoe `resolver()`, que devolve TODOS os valores animados
naquele instante, e `pintar()`, que so consome esse dicionario.

Isso nao e organizacao — e o conserto de um bug de classe inteira. Do jeito
antigo, cada estilo escrevia `draw()` e `signature()` separados, lendo a
animacao duas vezes; quando as duas leituras divergiam, o dedup jurava que dois
frames eram iguais e o video saia com frame errado. Aqui a assinatura E o
`resolver()`, entao divergir e impossivel.

Tipos: texto, retangulo, elipse, linha, path, grupo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import skia

from ..text import Shadow, TextBlock, css_color
from . import svgpath, textura
from .valores import assinatura, avaliar, medida


@dataclass
class Ctx:
    """O que toda camada precisa saber pra se resolver."""
    t: float                 # segundos desde o inicio da cena
    fps: float
    w: int
    h: int
    registry: Any


# ── transform comum a toda camada ────────────────────────────────────────
_TRANSFORM = ("x", "y", "escala", "escalaX", "escalaY", "rotacao", "opacidade")


def _resolver_transform(c: dict, ctx: Ctx) -> dict:
    return {
        "x": medida(c.get("x"), ctx.t, ctx.fps, ctx.w, 0.0),
        "y": medida(c.get("y"), ctx.t, ctx.fps, ctx.h, 0.0),
        "escala": avaliar(c.get("escala"), ctx.t, ctx.fps, 1.0),
        "escalaX": avaliar(c.get("escalaX"), ctx.t, ctx.fps, 1.0),
        "escalaY": avaliar(c.get("escalaY"), ctx.t, ctx.fps, 1.0),
        "rotacao": avaliar(c.get("rotacao"), ctx.t, ctx.fps, 0.0),
        "opacidade": avaliar(c.get("opacidade"), ctx.t, ctx.fps, 1.0),
        "revelar": avaliar((c.get("revelar") or {}).get("prog")
                           if isinstance(c.get("revelar"), dict) else c.get("revelar"),
                           ctx.t, ctx.fps, 1.0),
        "traco": avaliar(c.get("traco"), ctx.t, ctx.fps, 1.0),
    }


def viva(c: dict, t: float) -> bool:
    """`inicio`/`fim` em segundos. Fora da janela a camada nem e avaliada."""
    if "inicio" in c and t < float(c["inicio"]):
        return False
    if "fim" in c and t >= float(c["fim"]):
        return False
    return True


# ── pintura auxiliar ─────────────────────────────────────────────────────
def _tinta(cor, alpha: float, blur: float = 0.0) -> skia.Paint:
    if isinstance(cor, dict):
        return _tinta_gradiente(cor, alpha, blur)
    p = skia.Paint(AntiAlias=True, Color=css_color(cor, alpha))
    if blur:
        # o blur do CSS tem raio = 2 sigma; sem dividir, tudo sai o dobro de
        # borrado do que quem escreveu a cena pediu
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur / 2.0))
    return p


def _tinta_gradiente(g: dict, alpha: float, blur: float = 0.0) -> skia.Paint:
    """`cor` como objeto vira degrade. Coordenadas relativas a camada.

        {"tipo": "radial", "cores": ["#2A2A55", "#0A0A12"], "raio": 900}
        {"tipo": "linear", "cores": [...], "de": [0,-400], "para": [0,400]}
    """
    cores = [css_color(c, alpha) for c in g.get("cores", ["#FFF", "#000"])]
    paradas = g.get("paradas")
    if g.get("tipo") == "radial":
        sh = skia.GradientShader.MakeRadial(
            tuple(g.get("centro", (0, 0))), float(g.get("raio", 500)), cores, paradas)
    else:
        sh = skia.GradientShader.MakeLinear(
            [tuple(g.get("de", (0, -400))), tuple(g.get("para", (0, 400)))],
            cores, paradas)
    p = skia.Paint(AntiAlias=True, Shader=sh)
    if blur:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur / 2.0))
    return p


def _pena(cor, larg: float, alpha: float, blur: float = 0.0) -> skia.Paint:
    p = _tinta(cor, alpha, blur)
    p.setStyle(skia.Paint.kStroke_Style)
    p.setStrokeWidth(larg)
    p.setStrokeCap(skia.Paint.kRound_Cap)
    p.setStrokeJoin(skia.Paint.kRound_Join)
    return p


def _efeito(spec, ctx) -> "skia.PathEffect | None":
    """Efeitos de contorno do Skia — o que transforma UMA forma em varias.

    O motor sabia fazer uma coisa com um contorno: correr ele (`traco`). O
    Skia sabe fazer quatro, e as quatro estavam disponiveis desde sempre:

      tracejado  linha picotada. A `fase` ANIMA — e a formiguinha do recorte,
                 e e o que faz um contorno parado parecer vivo.
      rabisco    deforma o traco em segmentos curtos. E a diferenca entre
                 "desenhado por um programa" e "desenhado por uma pessoa".
      quina      arredonda TODA quina do path, inclusive as do texto em curva.
    `fase` passa por `avaliar` porque efeito parado e enfeite; efeito que anda
    e movimento.

    FORA: o `Path1DPathEffect` — carimbar uma forma ao longo do caminho — seria
    o quarto, e e o mais bonito dos quatro. Testado direto no Skia, sem o DSL
    no meio: o objeto e criado, `Make` devolve um PathEffect, e o `drawPath`
    IGNORA ele. Nao ha erro, nao ha aviso — sai a linha lisa. E limitacao deste
    build do skia-python, nao do codigo aqui.

    Nao entra enquanto nao funcionar. Recurso documentado que nao faz nada e
    exatamente o modo de falha que este projeto passa a vida caçando: o
    validador aprova o nome do campo e o video sai errado calado.
    """
    if not spec:
        return None
    t = spec.get("tipo")
    fase = float(avaliar(spec.get("fase", 0.0), ctx.t, ctx.fps, 0.0))
    if t == "tracejado":
        return skia.DashPathEffect.Make(
            [float(spec.get("traco", 12)), float(spec.get("vao", 8))], fase)
    if t == "rabisco":
        return skia.DiscretePathEffect.Make(
            float(spec.get("seg", 6)), float(spec.get("amp", 3)),
            int(spec.get("semente", 0)))
    if t == "quina":
        return skia.CornerPathEffect.Make(float(spec.get("raio", 8)))
    return None


def _pintar_forma(canvas: skia.Canvas, path: skia.Path, c: dict, vals: dict,
                  ctx=None):
    """Preenche e/ou contorna. `traco` recorta o contorno progressivamente."""
    op = vals["opacidade"]
    blur = float(c.get("blur", 0) or 0)
    if c.get("cor"):
        canvas.drawPath(path, _tinta(c["cor"], op, blur))
    if c.get("hachura"):
        textura.hachurar(canvas, path, c["hachura"], op)
    if c.get("contorno"):
        larg = float(c.get("contorno_larg", 2))
        alvo = svgpath.trecho(path, vals["traco"]) if vals["traco"] < 1.0 else path
        pena = _pena(c["contorno"], larg, op, blur)
        if c.get("efeito") and ctx is not None:
            ef = _efeito(c["efeito"], ctx)
            if ef is not None:
                pena.setPathEffect(ef)
        canvas.drawPath(alvo, pena)


# ── texto ────────────────────────────────────────────────────────────────
def construir_texto(c: dict, ctx: Ctx) -> TextBlock:
    """Medir texto e o custo FIXO da camada; desenhar e o custo por frame.

    Por isso o TextBlock nasce uma vez, na construcao da cena, e nao aqui
    dentro do loop de frames.
    """
    sombras = [Shadow(float(s.get("x", 0)), float(s.get("y", 0)),
                      float(s.get("blur", 0)), s.get("cor", "rgba(0,0,0,0.6)"))
               for s in (c.get("sombra") or [])]
    fonte = c.get("fonte") or "'Inter', sans-serif"
    if "," not in fonte and "'" not in fonte:
        fonte = f"'{fonte}', sans-serif"     # deixa escrever so o nome da familia
    lm = c.get("largura_max")
    return TextBlock(
        registry=ctx.registry,
        text=str(c.get("texto", "")),
        css_family=fonte,
        weight=int(c.get("peso", 400)),
        italic=bool(c.get("italico", False)),
        font_size=float(c.get("tamanho", 82)),
        color=c.get("cor", "#FFFFFF"),
        line_height=c.get("entrelinha", 1.0),
        align=c.get("alinha", "center"),
        shadows=sombras,
        max_width=(medida(lm, 0, ctx.fps, ctx.w) if lm is not None else None),
        stroke_width=float(c.get("contorno_larg", 0) if c.get("contorno") else 0),
        stroke_color=c.get("contorno", "#000000"),
        letter_spacing=float(c.get("espacamento", 0)),
    )


def _pintar_texto(canvas: skia.Canvas, c: dict, vals: dict, bloco: TextBlock):
    if bloco is None:
        return
    # ja estamos no ponto da camada: centro em x, caixa centrada em y
    bloco.draw(canvas, 0.0, -bloco.height / 2.0, opacity=vals["opacidade"])


# ── formas ───────────────────────────────────────────────────────────────
def _path_da_camada(c: dict, ctx: Ctx, vals: dict) -> skia.Path | None:
    tipo = c["tipo"]
    if tipo == "retangulo":
        larg = medida(c.get("larg", 200), ctx.t, ctx.fps, ctx.w)
        alt = medida(c.get("alt", 200), ctx.t, ctx.fps, ctx.h)
        r = avaliar(c.get("raio"), ctx.t, ctx.fps, 0.0)
        rect = skia.Rect.MakeXYWH(-larg / 2, -alt / 2, larg, alt)
        p = skia.Path()
        if r > 0:
            p.addRRect(skia.RRect.MakeRectXY(rect, r, r))
        else:
            p.addRect(rect)
        return p
    if tipo == "elipse":
        rx = medida(c.get("rx", c.get("raio", 100)), ctx.t, ctx.fps, ctx.w)
        ry = medida(c.get("ry", c.get("raio", 100)), ctx.t, ctx.fps, ctx.h)
        # de_grau/varre_grau sao ANIMAVEIS — e assim que um setor "cresce" em
        # angulo, que e o gesto de gravura (a tinta abre o leque). `float()`
        # direto quebrava com keyframes.
        de = avaliar(c.get("de_grau"), ctx.t, ctx.fps, 0.0)
        varre = avaliar(c.get("varre_grau"), ctx.t, ctx.fps, 360.0)
        ri = avaliar(c.get("raio_int"), ctx.t, ctx.fps, 0.0)
        p = skia.Path()
        if ri > 0:
            # SETOR ANULAR (arco de fora + arco de volta por dentro).
            # Sem raio interno, um arco nao fechado vira SEGMENTO — a corda
            # liga as duas pontas e o preenchimento sai como lente, nao como
            # fatia. Pior: hachura radial converge no centro e chapa tudo, que
            # foi como o cortex temporal virou uma mancha cinza.
            rxi = ri * (rx / max(rx, 1e-6))
            p.arcTo(skia.Rect.MakeLTRB(-rx, -ry, rx, ry), de, varre, True)
            p.arcTo(skia.Rect.MakeLTRB(-rxi, -rxi, rxi, rxi), de + varre, -varre, False)
            p.close()
        else:
            # `addArc` em vez de `addOval`: o oval fecha o contorno e o `traco`
            # progressivo comecaria do lugar errado. O arco de 360 comeca as 3h.
            p.addArc(skia.Rect.MakeLTRB(-rx, -ry, rx, ry), de, varre)
        return p
    if tipo == "linha":
        de = c.get("de", [0, 0])
        para = c.get("para", [100, 0])
        p = skia.Path()
        p.moveTo(medida(de[0], ctx.t, ctx.fps, ctx.w),
                 medida(de[1], ctx.t, ctx.fps, ctx.h))
        p.lineTo(medida(para[0], ctx.t, ctx.fps, ctx.w),
                 medida(para[1], ctx.t, ctx.fps, ctx.h))
        return p
    if tipo == "path":
        p = svgpath.parse(c.get("d", ""))
        if c.get("centrar", True):
            b = p.getBounds()
            m = skia.Matrix()
            m.setTranslate(-(b.left() + b.right()) / 2, -(b.top() + b.bottom()) / 2)
            p.transform(m)
        return p
    return None


# ── despacho ─────────────────────────────────────────────────────────────
TIPOS = {"texto", "retangulo", "elipse", "linha", "path", "grupo", "textura",
         "imagem"}


def resolver(c: dict, ctx: Ctx) -> dict:
    """Todos os valores animados desta camada no instante de `ctx`."""
    return _resolver_transform(c, ctx)


def grade(rep: dict, ctx: Ctx):
    """Itera as copias de `repetir`: devolve (dx, dy, t_local) de cada uma.

    O `atraso` e o que transforma grade em PADRAO: sem defasagem as N copias
    animam em unissono e o olho le um bloco so. Com defasagem ele le uma onda
    atravessando a grade, que e a coisa toda.

    `ordem` decide o formato da onda — "linha" varre da esquerda, "centro"
    irradia do meio, "aleatorio" pipoca (deterministico: mesmo filme sempre).
    """
    cols = max(1, int(rep.get("cols", 1)))
    lins = max(1, int(rep.get("linhas", 1)))
    ex = float(rep.get("espX", 100))
    ey = float(rep.get("espY", 100))
    atraso = float(rep.get("atraso", 0.0))
    cels = [((j - (cols - 1) / 2) * ex, (i - (lins - 1) / 2) * ey)
            for i in range(lins) for j in range(cols)]
    ordem = rep.get("ordem", "linha")
    if ordem == "centro":
        pos = sorted(range(len(cels)), key=lambda k: math.hypot(*cels[k]))
    elif ordem == "aleatorio":
        pos = sorted(range(len(cels)), key=lambda k: (k * 2654435761) % 1000003)
    else:
        pos = list(range(len(cels)))
    rank = {k: r for r, k in enumerate(pos)}
    for k, (dx, dy) in enumerate(cels):
        yield dx, dy, ctx.t - rank[k] * atraso


def pintar(canvas: skia.Canvas, c: dict, vals: dict, ctx: Ctx,
           blocos: dict | None = None):
    """Desenha a camada — uma vez, ou N vezes se ela tiver `repetir`."""
    rep = c.get("repetir")
    if not rep:
        _pintar_um(canvas, c, vals, ctx, blocos)
        return
    for dx, dy, tl in grade(rep, ctx):
        if not viva(c, tl):
            continue
        sub = Ctx(tl, ctx.fps, ctx.w, ctx.h, ctx.registry)
        canvas.save()
        canvas.translate(dx, -dy)
        _pintar_um(canvas, c, resolver(c, sub), sub, blocos)
        canvas.restore()


def _pintar_um(canvas: skia.Canvas, c: dict, vals: dict, ctx: Ctx,
               blocos: dict | None = None):
    """Desenha a camada ja resolvida. NAO chama `avaliar` — de proposito.

    O canvas ja chega com a origem no CENTRO do quadro (quem faz isso e
    `Cena.desenhar`, uma vez so). Traduzir pro centro aqui dentro somaria de
    novo a cada nivel, e filho de grupo ia parar fora da tela — foi o primeiro
    bug que apareceu no teste.
    """
    if vals["opacidade"] <= 0.001:
        return
    canvas.save()
    canvas.translate(vals["x"], -vals["y"])
    if vals["rotacao"]:
        canvas.rotate(vals["rotacao"])
    sx = vals["escala"] * vals["escalaX"]
    sy = vals["escala"] * vals["escalaY"]
    if sx != 1.0 or sy != 1.0:
        canvas.scale(sx, sy)

    # `revelar`: cortina que varre a caixa da camada. E wipe, nao reveal por
    # caractere — nomear certo importa, porque reveal por letra exigiria
    # remedir o texto a cada frame e ai o custo fixo viraria custo por frame.
    rev = vals["revelar"]
    if rev < 1.0:
        r = c.get("revelar") if isinstance(c.get("revelar"), dict) else {}
        lado = (r or {}).get("dir", "esq")
        ext = max(ctx.w, ctx.h)
        if lado in ("esq", "dir"):
            larg = ext * rev
            x0 = -ext / 2 if lado == "esq" else ext / 2 - larg
            canvas.clipRect(skia.Rect.MakeXYWH(x0, -ext / 2, larg, ext))
        else:
            alt = ext * rev
            y0 = -ext / 2 if lado == "cima" else ext / 2 - alt
            canvas.clipRect(skia.Rect.MakeXYWH(-ext / 2, y0, ext, alt))

    tipo = c["tipo"]
    if tipo == "grupo":
        for f in c.get("camadas") or []:
            if viva(f, ctx.t):
                pintar(canvas, f, resolver(f, ctx), ctx, blocos)
    elif tipo == "textura":
        img = textura.papel(ctx.w, ctx.h, c)
        pt = skia.Paint(AntiAlias=True)
        pt.setAlphaf(vals["opacidade"])
        canvas.drawImage(img, -ctx.w / 2.0, -ctx.h / 2.0, skia.SamplingOptions(), pt)
    elif tipo == "imagem":
        _pintar_imagem(canvas, c, vals, ctx)
    elif tipo == "texto":
        _pintar_texto(canvas, c, vals, (blocos or {}).get(id(c)))
    else:
        path = _path_da_camada(c, ctx, vals)
        if path is not None:
            _pintar_forma(canvas, path, c, vals, ctx)
    canvas.restore()


# ── imagem ───────────────────────────────────────────────────────────────
# O DSL tinha sete tipos e nenhum era imagem — e foi ISSO que separou as minhas
# pecas das profissionais, nao a curva de easing. Video de marca e foto e
# captura de tela compostas; geometria abstrata sozinha vira slide.
#
# Cache por caminho: decodificar um JPEG por frame custaria mais que desenhar a
# cena inteira, e a mesma foto costuma aparecer em varias camadas.
_CACHE_IMG: dict[str, "skia.Image"] = {}


def _carregar(caminho: str):
    img = _CACHE_IMG.get(caminho)
    if img is None:
        img = skia.Image.open(caminho)
        if img is None:
            raise FileNotFoundError(f"imagem nao carregou: {caminho}")
        _CACHE_IMG[caminho] = img
    return img


def _pintar_imagem(canvas: skia.Canvas, c: dict, vals: dict, ctx: Ctx):
    img = _carregar(str(c["src"]))
    iw, ih = float(img.width()), float(img.height())

    # `larg`/`alt` sao a CAIXA; a imagem se ajusta dentro dela.
    larg = medida(c.get("larg", "100%"), ctx.t, ctx.fps, ctx.w)
    alt = medida(c.get("alt", "100%"), ctx.t, ctx.fps, ctx.h)

    modo = c.get("ajuste", "cobrir")
    if modo == "cobrir":
        # preenche a caixa e corta o excedente — o `object-fit: cover` do CSS.
        # E o que se quer em fundo: esticar a foto denuncia na hora.
        e = max(larg / iw, alt / ih)
    elif modo == "caber":
        e = min(larg / iw, alt / ih)
    else:
        e = 1.0
    dw, dh = iw * e, ih * e

    pt = skia.Paint(AntiAlias=True)
    pt.setAlphaf(max(0.0, min(1.0, vals["opacidade"])))
    tint = c.get("tingir")
    if tint:
        # tingir a imagem inteira numa cor, mantendo a luminancia — e como o
        # material de referencia troca o "look" da mesma foto por cena.
        pt.setColorFilter(skia.ColorFilters.Blend(css_color(tint), skia.BlendMode.kModulate))

    canvas.save()
    canvas.clipRect(skia.Rect.MakeXYWH(-larg / 2, -alt / 2, larg, alt))
    canvas.drawImageRect(
        img, skia.Rect.MakeXYWH(-dw / 2, -dh / 2, dw, dh),
        skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear), pt)
    canvas.restore()


def assinar(c: dict, ctx: Ctx) -> tuple:
    """Assinatura da camada: so o que MUDA entre frames entra."""
    rep = c.get("repetir")
    if rep:
        # cada copia vive num instante proprio, entao cada uma assina sozinha
        return tuple(_assinar_um(c, Ctx(tl, ctx.fps, ctx.w, ctx.h, ctx.registry))
                     if viva(c, tl) else ("morta",)
                     for _, _, tl in grade(rep, ctx))
    return _assinar_um(c, ctx)


def _assinar_um(c: dict, ctx: Ctx) -> tuple:
    itens = []
    for k in _TRANSFORM + ("revelar", "traco"):
        v = c.get(k)
        if isinstance(v, dict) and k == "revelar":
            v = v.get("prog")
        total = ctx.w if k == "x" else (ctx.h if k == "y" else None)
        a = assinatura(v, ctx.t, ctx.fps, total)
        if a is not None:
            itens.append((k, a))
    # geometria animada (larg/alt/raio/rx/ry/varre_grau/de/para) tambem conta
    for k in ("larg", "alt", "raio", "rx", "ry", "de_grau", "varre_grau"):
        a = assinatura(c.get(k), ctx.t, ctx.fps)
        if a is not None:
            itens.append((k, a))
    if c["tipo"] == "grupo":
        itens.append(("filhos", tuple(
            assinar(f, ctx) if viva(f, ctx.t) else ("morta",)
            for f in (c.get("camadas") or []))))
    return tuple(itens)
