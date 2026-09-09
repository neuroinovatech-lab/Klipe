"""
textura.py — papel envelhecido e hachura de buril como PRIMITIVAS do DSL.

Existe por um motivo especifico. O RadiusMotion tinha material — papel, grao,
falha de impressao, hachura — e por isso nao lia como template. Mas tudo aquilo
era Skia solto dentro de um script, entao a proxima peca teria que reescrever
do zero. Trazendo pra ca, "material" vira uma opcao de qualquer cena, e o motor
deixa de saber desenhar so um estilo.

A textura e cara (ruido, borrao, vinheta) e por isso nasce UMA vez por cena e
fica em cache pela chave dos parametros. Desenhar por frame seria inviavel.
"""
from __future__ import annotations

import math

import numpy as np
import skia

from ..text import css_color

_CACHE: dict[tuple, skia.Image] = {}


def _rgba(cor: str) -> tuple[int, int, int]:
    c = css_color(cor, 1.0)
    return ((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)


def papel(w: int, h: int, cfg: dict) -> skia.Image:
    """Folha envelhecida: luz radial, manchas, vinheta, grao e falhas."""
    chave = (w, h, tuple(sorted((k, str(v)) for k, v in cfg.items())))
    if chave in _CACHE:
        return _CACHE[chave]

    base = cfg.get("cor", "#C7A978")
    semente = int(cfg.get("semente", 1879))
    rng = np.random.default_rng(semente)
    surf = skia.Surface(w, h)
    c = surf.getCanvas()
    r, g, b = _rgba(base)

    claro = f"#{min(255, r+26):02X}{min(255, g+24):02X}{min(255, b+20):02X}"
    escuro = f"#{max(0, r-34):02X}{max(0, g-30):02X}{max(0, b-24):02X}"

    # A FOLHA. Tem que vir primeiro e opaca: as camadas seguintes sao todas
    # translucidas, e sem base a superficie fica preta e so o facho aparece.
    c.drawColor(css_color(base, 1.0))

    # luz de epoca: fora do centro, puxada pra esquerda-alto. Centrada demais
    # le como degrade de software; deslocada le como folha sob uma janela.
    sh = skia.GradientShader.MakeRadial(
        (w * 0.38, h * 0.42), w * 0.75,
        [css_color(claro, 0.22), css_color(claro, 0.0)])
    c.drawPaint(skia.Paint(Shader=sh))

    # manchas: metade escurece (umidade), metade clareia (desbotado). So
    # escuras a folha fica suja em vez de velha.
    for _ in range(int(cfg.get("manchas", 9))):
        px, py = rng.uniform(0, w), rng.uniform(0, h)
        rr = rng.uniform(w * 0.06, w * 0.22)
        tom = escuro if rng.random() < 0.6 else claro
        p = skia.Paint(AntiAlias=True, Color=css_color(tom, rng.uniform(0.05, 0.10)))
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, rr / 3))
        c.drawCircle(px, py, rr, p)

    # facho de luz diagonal entrando pelo alto-esquerda
    if cfg.get("facho", True):
        c.save()
        c.translate(-40, -60)
        c.rotate(34)
        fx = skia.GradientShader.MakeLinear(
            [(0, 0), (0, h * 0.16)],
            [css_color("#FFFFFF", 0.0), css_color("#FFF4DC", 0.19),
             css_color("#FFFFFF", 0.0)])
        pf = skia.Paint(Shader=fx)
        pf.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 40))
        c.drawRect(skia.Rect.MakeXYWH(-200, 0, w * 1.4, h * 0.16), pf)
        c.restore()

    # Vinheta como BORDA retangular grossa e borrada, nao como circulo. E a
    # diferenca entre "pagina impressa" e "foto com vinheta" — a folha escurece
    # nas quatro margens, nao num anel.
    vin = float(cfg.get("vinheta", 0.55))
    if vin > 0:
        for larg, op in ((90, 0.33 * vin / 0.55), (210, 0.19 * vin / 0.55)):
            pv = skia.Paint(AntiAlias=True, Color=css_color("#1E1A16", op),
                            Style=skia.Paint.kStroke_Style, StrokeWidth=larg)
            pv.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 60))
            c.drawRect(skia.Rect.MakeLTRB(-40, -40, w + 40, h + 40), pv)

    # Grao em MEIA resolucao, esticado: cada grao vira 2x2 px e le como fibra
    # de papel. Ruido por pixel (o que eu tinha antes) le como ruido digital —
    # e o mesmo motivo de filme granulado nao ser a mesma coisa que ISO alto.
    forca = float(cfg.get("grao", 0.055))
    if forca > 0:
        n = (rng.normal(0, 1, (h // 2, w // 2)) * 10 + 128).clip(0, 255).astype(np.uint8)
        alfa = np.full_like(n, int(255 * min(1.0, forca * 2.0)))
        gr = skia.Image.fromarray(np.dstack([n, n, n, alfa]).copy(),
                                  skia.ColorType.kRGBA_8888_ColorType)
        c.drawImageRect(gr, skia.Rect.MakeWH(w, h), skia.SamplingOptions())

    # falhas de impressao: risquinhos claros, curtos, quase invisiveis
    for _ in range(int(cfg.get("falhas", 22))):
        x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
        ang = rng.uniform(-0.35, 0.35)
        L = rng.uniform(12, 60)
        p = skia.Paint(AntiAlias=True, Color=css_color(claro, rng.uniform(0.10, 0.22)),
                       Style=skia.Paint.kStroke_Style, StrokeWidth=rng.uniform(0.5, 1.2))
        c.drawLine(x0, y0, x0 + math.cos(ang) * L, y0 + math.sin(ang) * L, p)

    out = surf.makeImageSnapshot()
    _CACHE[chave] = out
    return out


def hachurar(canvas: skia.Canvas, recorte: skia.Path, cfg: dict, alpha: float):
    """Linhas finissimas dentro de um recorte — a textura de buril.

    E o que separa "setor vetorial chapado" de "impressao do seculo XIX": na
    gravura o preenchimento e feito de centenas de tracos, nao de cor solida.
    """
    canvas.save()
    canvas.clipPath(recorte, doAntiAlias=True)
    cor = cfg.get("cor", "#34281C")
    op = float(cfg.get("opacidade", 0.5)) * alpha
    larg = float(cfg.get("largura", 0.6))
    p = skia.Paint(AntiAlias=True, Color=css_color(cor, op),
                   Style=skia.Paint.kStroke_Style, StrokeWidth=larg)
    b = recorte.getBounds()
    alcance = max(abs(b.left()), abs(b.right()), abs(b.top()), abs(b.bottom())) * 1.6 + 40
    path = skia.Path()

    if cfg.get("modo") == "radial":
        # saindo do centro da camada: e o preenchimento dos aneis
        passo = float(cfg.get("passo", 0.45))     # em GRAUS
        r0 = float(cfg.get("r0", 0))
        a = 0.0
        while a < 360.0:
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            path.moveTo(r0 * ca, r0 * sa)
            path.lineTo(alcance * ca, alcance * sa)
            a += passo
    else:
        passo = float(cfg.get("passo", 4.0))      # em PIXELS
        canvas.rotate(float(cfg.get("angulo", 30.0)))
        k = -alcance
        while k <= alcance:
            path.moveTo(-alcance, k)
            path.lineTo(alcance, k)
            k += passo
    canvas.drawPath(path, p)
    canvas.restore()
