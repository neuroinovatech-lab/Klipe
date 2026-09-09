"""
text.py — modelo de caixa de linha do CSS em cima do Skia.

O que o navegador faz com `<div style="font-size:82px; line-height:0.98">TEXTO</div>`
e o que a gente precisa reproduzir:

    altura da caixa = line-height * font-size          (80.36px, nao 82)
    meia-entrelinha = (altura - (ascent+descent)) / 2   (negativa quando lh < 1)
    baseline        = topo + meia-entrelinha + ascent

`ascent`/`descent` vem das metricas da fonte ARREDONDADAS pra inteiro — o Blink
faz `SkScalarRoundToScalar` nas duas antes de montar a caixa. Sem esse
arredondamento a linha desloca uma fracao de pixel e o diff acusa.

Quebra de linha e gulosa, igual ao Blink: enche a linha enquanto couber e
quebra no ultimo espaco. Titulo longo com `maxWidth: 90%` depende disso.

`text-shadow` do CSS vira `DropShadowOnly` numa saveLayer: e a sombra da forma
ja desenhada, igualzinho a semantica do CSS (a sombra e do glifo, nao um texto
extra desenhado por tras). Raio de blur do CSS = 2 * sigma da gaussiana.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import skia
from skia import textlayout as tl

from .fonts import FontRegistry


def css_color(c: str, alpha_mult: float = 1.0) -> int:
    """'#E8940A', '#E8940A55' ou 'rgba(0,0,0,0.85)' -> cor ARGB do Skia."""
    c = c.strip()
    if c.startswith("rgba(") or c.startswith("rgb("):
        nums = c[c.index("(") + 1:c.rindex(")")].split(",")
        r, g, b = (int(float(x)) for x in nums[:3])
        a = float(nums[3]) if len(nums) > 3 else 1.0
    elif c.startswith("#"):
        h = c[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    else:
        raise ValueError(f"cor CSS nao suportada: {c!r}")
    a = max(0.0, min(1.0, a * alpha_mult))
    return skia.Color4f(r / 255, g / 255, b / 255, a).toColor()


@dataclass(frozen=True)
class Shadow:
    """Uma entrada de `text-shadow`. `blur` e o RAIO do CSS, nao o sigma."""
    dx: float
    dy: float
    blur: float
    color: str

    @property
    def sigma(self) -> float:
        return self.blur / 2.0


@dataclass
class TextBlock:
    """
    Um `<div>` de texto: uma familia, um tamanho, uma cor — e N linhas visuais
    depois da quebra. Mede como o CSS mede e desenha como o CSS desenha.
    """
    registry: FontRegistry
    text: str
    css_family: str
    weight: int = 400
    italic: bool = False
    font_size: float = 82.0
    color: str = "#FFFFFF"
    # multiplicador do CSS. `None` = `line-height: normal`, que NAO e 1: o
    # navegador usa a altura natural da fonte (ascent+descent+lineGap). Assumir
    # 1 onde o TSX nao especifica desloca a linha verticalmente.
    line_height: float | None = 1.0
    # `text-align`. O padrao do CSS e `left` — varios estilos (quote, lower3rd,
    # panel) nao especificam e portanto alinham a esquerda quando quebram.
    align: str = "center"
    shadows: list[Shadow] = field(default_factory=list)
    max_width: float | None = None           # None = nunca quebra
    # `-webkit-text-stroke` com `paint-order: stroke fill`: o contorno e
    # centrado no contorno do glifo, entao o preenchimento cobre a metade de
    # dentro e sobra metade pra fora. Nao mexe na largura do texto (e so pintura).
    stroke_width: float = 0.0
    stroke_color: str = "#000000"
    # `letter-spacing` do CSS entra DEPOIS de cada caractere, inclusive o
    # ultimo — entao a largura de avanco carrega um espaco sobrando no fim.
    # O Chrome inclui esse sobrando ao centralizar, e o skparagraph tambem;
    # descontar aqui desalinharia o texto em metade do espacamento.
    letter_spacing: float = 0.0

    def __post_init__(self):
        self.face = self.registry.resolve(self.css_family, self.weight, self.italic)
        m = skia.Font(self.face.typeface, self.font_size).getMetrics()
        # o Blink arredonda ascent/descent pra inteiro antes de montar a caixa
        self.ascent = round(-m.fAscent)
        self.descent = round(m.fDescent)
        # fTop/fBottom limitam QUALQUER glifo da fonte — servem pra caixa de tinta
        self._ink_top, self._ink_bottom = m.fTop, m.fBottom
        # `line-height: normal` = altura natural da fonte
        self._normal_lh = self.ascent + self.descent + round(m.fLeading)
        self._cache: dict[tuple[str, int], tl.Paragraph] = {}
        self._wrap()

    # ── medicao ───────────────────────────────────────────────────────────
    FILL, STROKE = -1, -2

    def _paragraph(self, text: str, variante: int = FILL) -> tl.Paragraph:
        """
        `variante`: FILL = preenchimento, STROKE = contorno, >= 0 = sombra N.

        Cada variante e um paragrafo proprio porque o skparagraph carrega o
        Paint dentro do TextStyle. O shaping e o custo real e ele acontece uma
        vez por (texto, variante) — depois e so redesenhar.
        """
        key = (text, variante)
        par = self._cache.get(key)
        if par is not None:
            return par

        ts = tl.TextStyle()
        ts.setFontFamilies([self.face.alias])
        ts.setFontSize(self.font_size)
        if self.letter_spacing:
            ts.setLetterSpacing(self.letter_spacing)
        if variante == self.FILL and not self.shadows and self.stroke_width <= 0:
            ts.setColor(css_color(self.color))
        elif variante == self.FILL:
            ts.setForegroundPaint(skia.Paint(AntiAlias=True, Color=css_color(self.color)))
        elif variante == self.STROKE:
            ts.setForegroundPaint(skia.Paint(
                AntiAlias=True, Color=css_color(self.stroke_color),
                Style=skia.Paint.kStroke_Style, StrokeWidth=self.stroke_width,
                StrokeJoin=skia.Paint.kRound_Join))
        else:
            sh = self.shadows[variante]
            p = skia.Paint(AntiAlias=True, Color=css_color(sh.color))
            if self.stroke_width > 0:
                # A sombra do CSS e da silhueta do texto JA pintado — ou seja,
                # preenchimento uniao contorno. kStrokeAndFill resolve isso num
                # passe so; borrar contorno e preenchimento separados daria
                # alpha dobrado na sobreposicao.
                p.setStyle(skia.Paint.kStrokeAndFill_Style)
                p.setStrokeWidth(self.stroke_width)
                p.setStrokeJoin(skia.Paint.kRound_Join)
            if sh.sigma > 0:
                # `text-shadow` do CSS borra a MASCARA do glifo. Fazer isso com
                # MaskFilter custa o tamanho do texto; fazer com saveLayer +
                # ImageFilter custa uma camada de tela cheia por sombra — era
                # isso que fazia o frame levar 1,9s.
                p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sh.sigma))
            ts.setForegroundPaint(p)

        ps = tl.ParagraphStyle()
        ps.setTextStyle(ts)
        b = tl.ParagraphBuilder.make(ps, self.registry.collection, self.registry.unicode)
        b.addText(text)
        par = b.Build()
        par.layout(1e6)      # largura infinita: mede a linha inteira sem quebrar
        self._cache[key] = par
        return par

    def measure(self, text: str) -> float:
        return self._paragraph(text).LongestLine

    def _wrap(self):
        """
        Quebra gulosa igual ao Blink: enche a linha enquanto couber.

        Alem do espaco, o CSS permite quebrar DEPOIS de um hifen — e por isso
        que o Chrome parte "mal-entendidos" em "mal-" / "entendidos". Sem essa
        oportunidade de quebra, a linha estoura a caixa.

        `\\n` e quebra que o AUTOR pediu e sobrevive a tudo — como o `pre-line`
        do CSS. Antes o `re.split(r"\\s+")` engolia a newline junto com os
        espacos, entao todo texto escrito em duas linhas era rejuntado e
        requebrado so pela largura: "o que sai do padrao\\nsalta primeiro aos
        olhos" saia partido em "...padrao salta / primeiro aos olhos". Quem
        escreve a cena decidia a quebra e o motor desfazia calado.
        """
        duras = re.split(r"\r?\n", self.text)
        self.lines = []
        for dura in duras:
            self.lines.extend(self._quebrar(dura))
        if not self.lines:
            self.lines = [self.text]
        # O Chrome conta o `letter-spacing` que vem DEPOIS do ultimo caractere
        # na largura da caixa; o skparagraph nao. Sem somar de volta, o texto
        # centralizado sai meio espacamento pra direita — 4 px visiveis num
        # titulo com `letter-spacing: 8`.
        self.line_widths = [self.measure(ln) + self.letter_spacing for ln in self.lines]

        # Largura da CAIXA, que nao e a da maior linha. O CSS usa shrink-to-fit:
        # `min(max-content, disponivel)`. Se o texto coube, a caixa e o texto;
        # se quebrou, a caixa ocupa a largura disponivel INTEIRA — mesmo que a
        # linha mais longa tenha ficado bem menor. E isso que decide onde acaba
        # o painel do lower3rd e onde comeca o texto alinhado a esquerda.
        # ...e com `\n` o max-content e a maior linha DURA sozinha, nao todas
        # emendadas: a quebra obrigatoria significa que o conteudo NUNCA
        # precisaria da soma das duas.
        max_content = max(self.measure(d) for d in duras) + self.letter_spacing
        self.width = (min(max_content, self.max_width) if self.max_width is not None
                      else max_content)
        if self.line_widths:
            self.width = max(self.width, max(self.line_widths))

    def _quebrar(self, txt: str) -> list[str]:
        """Quebra UMA linha dura pela largura disponivel."""
        # cada pedaco carrega o separador que vem antes dele: " palavra" ou
        # o rabicho depois do hifen, que gruda sem espaco
        pedacos = []
        for w in [x for x in re.split(r"\s+", txt) if x]:
            partes = re.split(r"(?<=-)(?=.)", w)
            for i, p in enumerate(partes):
                pedacos.append((p, i == 0))      # True = precisa de espaco antes
        if not pedacos:
            return [""]                          # linha em branco pedida e linha
        if self.max_width is None:
            return [txt]
        linhas, cur = [], ""
        for p, com_espaco in pedacos:
            cand = (f"{cur} {p}" if com_espaco else f"{cur}{p}") if cur else p
            if cur and self.measure(cand) > self.max_width:
                linhas.append(cur)
                cur = p
            else:
                cur = cand
        if cur:
            linhas.append(cur)
        return linhas

    # ── geometria da caixa (CSS) ──────────────────────────────────────────
    @property
    def line_box_height(self) -> float:
        if self.line_height is None:
            return float(self._normal_lh)
        return self.line_height * self.font_size

    @property
    def height(self) -> float:
        return self.line_box_height * len(self.lines)

    @property
    def baseline_offset(self) -> float:
        """Distancia do topo da caixa de UMA linha ate a baseline dela."""
        half_leading = (self.line_box_height - (self.ascent + self.descent)) / 2.0
        return half_leading + self.ascent

    # ── caixa de tinta ────────────────────────────────────────────────────
    def glyph_bounds(self, center_x: float, box_top: float) -> skia.Rect:
        """Retangulo dos glifos, sem sombra."""
        meia = self.width / 2.0
        topo = box_top + self.baseline_offset + self._ink_top
        base = (box_top + (len(self.lines) - 1) * self.line_box_height
                + self.baseline_offset + self._ink_bottom)
        return skia.Rect.MakeLTRB(center_x - meia, topo, center_x + meia, base)

    def ink_bounds(self, center_x: float, box_top: float) -> skia.Rect:
        """Retangulo que cobre glifos, contorno E sombras."""
        r = self.glyph_bounds(center_x, box_top)
        if self.stroke_width > 0:
            r.outset(self.stroke_width, self.stroke_width)
        for sh in self.shadows:
            # 3 sigmas cobrem >99,7% da gaussiana; +2px de folga pro arredondamento
            m = 3 * sh.sigma + 2
            r.join(skia.Rect.MakeLTRB(r.left() + sh.dx - m, r.top() + sh.dy - m,
                                      r.right() + sh.dx + m, r.bottom() + sh.dy + m))
        return r

    # ── imagens cacheadas ─────────────────────────────────────────────────
    #
    # A chave e so a parte FRACIONARIA da posicao, nao a posicao inteira. A
    # imagem e construida com a fracao ja assada dentro e blitada em coordenada
    # inteira — entao a mesma palavra em x diferentes reusa a mesma imagem, em
    # vez de reconstruir a cada aparicao. Numa legenda isso importa: a mesma
    # palavra cai em posicao diferente a cada grupo.
    def _imagem(self, cache: dict, center_x: float, box_top: float, pintar):
        fx, fy = center_x - math.floor(center_x), box_top - math.floor(box_top)
        chave = (round(fx, 3), round(fy, 3))
        item = cache.get(chave)
        if item is None:
            r = self.ink_bounds(fx, fy)
            x0, y0 = math.floor(r.left()), math.floor(r.top())
            w = max(1, math.ceil(r.right()) - x0)
            h = max(1, math.ceil(r.bottom()) - y0)
            surf = skia.Surface(w, h)
            cv = surf.getCanvas()
            cv.clear(skia.Color4f(0, 0, 0, 0))
            cv.translate(-x0, -y0)
            pintar(cv, fx, fy)
            item = (surf.makeImageSnapshot(), x0, y0)
            cache[chave] = item
        img, x0, y0 = item
        return img, math.floor(center_x) + x0, math.floor(box_top) + y0

    def draw_flat(self, canvas: skia.Canvas, center_x: float, box_top: float) -> bool:
        """
        Desenha a linha inteira a partir de UMA imagem cacheada.

        So vale quando a transform ja assentou em identidade — que e o caso da
        esmagadora maioria dos frames: a entrada dura ~20 frames, o resto do
        titulo fica parado. Nesses frames a copia e 1:1, pixel por pixel igual
        ao redesenho, e custa ~0,1 ms em vez de ~3 ms por linha.

        Durante a animacao o chamador NAO usa isso — a linha e redesenhada
        nitida no tamanho transformado, igual o navegador faz.
        """
        if not hasattr(self, "_flat_cache"):
            self._flat_cache = {}
        img, x, y = self._imagem(self._flat_cache, center_x, box_top,
                                 self._draw_direto)
        canvas.drawImage(img, x, y)
        return True

    def _shadow_image(self, center_x: float, box_top: float):
        """
        As sombras nao mudam entre frames — so a transform muda. Borrar a
        mascara do glifo toda vez custava 27 dos 30 ms da linha de destaque
        (glow de 38px + sombra de 16px). Aqui isso vira UMA rasterizacao,
        reusada em todos os frames.

        Reamostrar um borrao e invisivel; o texto em si continua sendo
        redesenhado nitido a cada frame, entao a borda do glifo nao perde nada.
        """
        if not self.shadows:
            return None
        if not hasattr(self, "_sh_cache"):
            self._sh_cache = {}

        def pintar(cv, cx, bt):
            for i in range(len(self.shadows) - 1, -1, -1):
                sh = self.shadows[i]
                self._paint_runs(cv, cx, bt, variante=i, dx=sh.dx, dy=sh.dy)

        return self._imagem(self._sh_cache, center_x, box_top, pintar)

    # ── desenho ───────────────────────────────────────────────────────────
    def _line_left(self, i: int, center_x: float) -> float:
        """`text-align` dentro da caixa (cuja largura e a da maior linha)."""
        if self.align == "center":
            return center_x - self.line_widths[i] / 2.0
        borda = center_x - self.width / 2.0
        if self.align == "right":
            return borda + self.width - self.line_widths[i]
        return borda

    def _paint_runs(self, canvas: skia.Canvas, center_x: float, box_top: float,
                    variante: int = -1, dx: float = 0.0, dy: float = 0.0):
        for i, ln in enumerate(self.lines):
            par = self._paragraph(ln, variante)
            left = self._line_left(i, center_x)
            baseline_y = box_top + i * self.line_box_height + self.baseline_offset
            par.paint(canvas, left + dx, baseline_y - par.AlphabeticBaseline + dy)

    def _draw_direto(self, canvas: skia.Canvas, center_x: float, box_top: float):
        # As sombras do CSS empilham na ordem declarada: a primeira fica por
        # cima das seguintes, e todas ficam atras do texto — a imagem cacheada
        # ja vem com elas nessa ordem.
        cache = self._shadow_image(center_x, box_top)
        if cache:
            img, sx, sy = cache
            canvas.drawImage(img, sx, sy)
        # `paint-order: stroke fill`: o contorno vai primeiro e o preenchimento
        # cobre a metade de dentro dele.
        if self.stroke_width > 0:
            self._paint_runs(canvas, center_x, box_top, variante=self.STROKE)
        self._paint_runs(canvas, center_x, box_top)

    def draw(self, canvas: skia.Canvas, center_x: float, box_top: float,
             opacity: float = 1.0):
        """Desenha centralizado em `center_x`, com o topo da caixa em `box_top`."""
        if opacity <= 0:
            return

        need_layer = opacity < 1.0
        if need_layer:
            # opacidade do CSS e do elemento inteiro (texto + sombras juntos),
            # nao de cada parte — por isso uma layer unica em volta de tudo.
            # Limitada a caixa de tinta: sem isso cada linha aloca a tela inteira.
            canvas.saveLayerAlpha(self.ink_bounds(center_x, box_top),
                                  int(round(opacity * 255)))

        self._draw_direto(canvas, center_x, box_top)

        if need_layer:
            canvas.restore()


def css_transform(canvas: skia.Canvas, origin: tuple[float, float],
                  translate: tuple[float, float] = (0.0, 0.0), scale: float = 1.0):
    """
    Aplica `transform: translate(...) scale(...)` do CSS em torno de `origin`
    (que no CSS e o centro da caixa de borda por padrao).

    A lista do CSS vira o produto das matrizes na ordem escrita, entao
    `translate(T) scale(S)` resulta em p' = O + T + S*(p - O).
    """
    canvas.translate(origin[0] + translate[0], origin[1] + translate[1])
    canvas.scale(scale, scale)
    canvas.translate(-origin[0], -origin[1])
