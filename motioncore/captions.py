"""
captions.py — porta do CaptionOverlay (legenda palavra a palavra estilo CapCut).

Original: o template antigo, `CaptionOverlay` (linha ~5289). Aqui estao os
estilos `outline` e `boxed`, que sao os do Klipe 2.0.

Por que legenda e o alvo numero um: ela e um overlay do video INTEIRO. Um video
de 18 min com legenda ligada custa ~930 s de render monolitico por navegador — mais que o
resto do render somado. Titulo e pontual; legenda e o tempo todo.

Duas coisas seguram o custo aqui:

1. **So a faixa.** A legenda vive numa tira embaixo da tela. Renderizar
   1080x1920 inteiro seriam 8,3 MB por frame no pipe; a faixa costuma dar um
   terco disso.
2. **Palavra vira imagem.** A aparencia de uma palavra depende so do texto e de
   estar ativa ou nao — a animacao e transform. Palavra parada sai de cache;
   so a palavra ativa (uma por frame) e redesenhada nitida.

Layout: flexbox com quebra, `justify-content: center`, `column-gap`/`row-gap`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import skia

from .fonts import FontRegistry
from .caption_presets import classificar, resolver
from .text import Shadow, TextBlock, css_color

# Constantes que vem do TSX e nao sao configuraveis pela UI
BASE_FONT = 62            # tamanho base antes do multiplicador do usuario
BOTTOM_PCT = 0.20         # `bottom: "20%"` do container externo
LARGURA_PCT = 0.88        # `width: "88%"` do container interno
LARGURA_MAX = 1400
LINE_HEIGHT = 1.25

# So o que esta REALMENTE portado entra aqui: anunciar um estilo que nao
# desenha certo faria o render sair errado calado.
ESTILOS = ("outline", "boxed", "destaque", "editorial", "forte-caixa",
           "serif-mista", "words")

# `boxed` — a legenda de caixa, o visual CapCut/Premiere. Do TSX (linha ~5466):
#   padding: 6px 18px ; borderRadius: 14 ; fontWeight 900 ; uppercase
#   ativa   -> texto #0A0A0A sobre a cor de destaque
#   parada  -> texto captionColor sobre rgba(0,0,0,0.72)
# O padding entra na LARGURA da palavra, senao a quebra de linha do flex sai
# em outro lugar e a legenda ocupa outra area da tela.
BOX_PAD_X = 18.0
BOX_PAD_Y = 6.0
BOX_RAIO = 14.0
BOX_FUNDO_PARADO = "rgba(0,0,0,0.72)"


def word_pop(we_sec: float, settle: float = 1.08) -> float:
    """
    Estouro da palavra ativa. Deterministico pelo tempo — `transition` do CSS
    nao anima no render, entao o valor tem que sair do relogio, nao do estado.
    """
    p = min(1.0, max(0.0, we_sec / 0.16))
    return 0.8 + (settle - 0.8) * (1 - (1 - p) ** 3) + 0.14 * math.sin(p * math.pi)


def grupo_scale(group_elapsed: float) -> float:
    """Quique de entrada do grupo de palavras."""
    g = min(1.0, max(0.0, group_elapsed / 0.14))
    return 0.9 + 0.1 * (1 - (1 - g) ** 3) + 0.05 * math.sin(g * math.pi)


@dataclass
class Palavra:
    texto: str
    largura: float
    normal: TextBlock
    ativa: TextBlock
    papel: str = "normal"   # power | normal | small — define fonte/cor/escala


@dataclass
class EstadoGrupo:
    palavras: list[Palavra]
    hi: int                 # indice da palavra ativa (-1 = sem karaoke)
    pop: float              # escala da palavra ativa
    escala: float           # escala do grupo
    estilo: str = "outline" # estilo DESTA legenda (subStyle ou o global)


class CaptionRenderer:
    """Desenha a legenda de qualquer frame, em coordenadas absolutas do canvas."""

    def __init__(self, cfg: dict, width: int, height: int, fps: float = 30.0,
                 registry: FontRegistry | None = None):
        self.w, self.h, self.fps = width, height, fps
        self.reg = registry or FontRegistry()

        self.estilo = cfg.get("captionStyle", "words")
        # Cada legenda pode ter `subStyle` proprio (o editor ja oferece isso).
        # Todos os que aparecem TEM que estar portados: deixar um passar faria
        # a legenda sumir so naquele trecho, calada.
        usados = {self.estilo} | {
            c.get("subStyle") for c in (cfg.get("captions") or []) if c.get("subStyle")}
        fora = sorted(e for e in usados if e not in ESTILOS)
        if fora:
            raise KeyError(f"estilo de legenda ainda nao portado: {fora[0]!r}"
                           + (f" (e mais {len(fora)-1})" if len(fora) > 1 else ""))
        self.estilos_usados = usados
        # Cada estilo vira um preset resolvido. `captionPreset` no config
        # sobrescreve campo a campo, que e o que permite catalogo de variacoes
        # sem redeclarar o preset inteiro.
        custom = cfg.get("captionPreset") or None
        self._preset = {e: resolver(e, custom) for e in usados}

        self.rate = float(cfg.get("videoPlaybackRate", 1.0) or 1.0)
        self.fonte = cfg.get("captionFont", "Montserrat")
        self.cor = cfg.get("captionColor", "#FFFFFF")
        self.destaque = cfg.get("captionHighlightColor", "#E8940A")
        self.karaoke = cfg.get("captionKaraoke", True)
        self.max_linhas = int(cfg.get("captionMaxLines", 2))
        self.gap_col = float(cfg.get("captionWordGap", 14))
        self.gap_row = float(cfg.get("captionLineGap", 6))
        self.pos_x = float(cfg.get("captionX", 0) or 0)
        self.pos_y = float(cfg.get("captionY", 0) or 0)

        tamanho = round(BASE_FONT * (float(cfg.get("captionFontSize", 100)) / 100.0))
        self.fs = round(tamanho * 1.15)
        self.stroke = max(4, round(self.fs * 0.09))
        # A altura depende do estilo: a pilula do `boxed` tem 6px acima e
        # abaixo do texto. Com estilos mesclados nao da pra ter um valor so.
        self._alt = {e: LINE_HEIGHT * self.fs + (2 * BOX_PAD_Y if e == "boxed" else 0)
                     for e in ESTILOS}
        self.altura_linha = self._alt[self.estilo]
        self.largura_container = min(LARGURA_PCT * width, LARGURA_MAX)
        # min(4, max(2, maxLines+1)) — o TSX chama isso de "palavras por grupo"
        self.wpg = min(4, max(2, self.max_linhas + 1))

        self.legendas = sorted(
            [c for c in (cfg.get("captions") or []) if (c.get("text") or "").strip()],
            key=lambda c: float(c["startSec"]))
        self._palavras: dict[str, Palavra] = {}
        self._banda = None

    # ── construcao das palavras ───────────────────────────────────────────
    def _resolver_cor(self, v):
        """`destaque` no preset significa a cor de destaque do projeto."""
        if not v:
            return None
        if isinstance(v, str) and v.startswith("destaque"):
            return self.destaque + v[len("destaque"):]
        return v

    def _bloco(self, texto: str, ativa: bool, estilo: str | None = None,
               papel: str = "normal") -> TextBlock:
        """Monta a palavra segundo o PRESET — nada de estilo no if."""
        estilo = estilo or self.estilo
        pr = self._preset[estilo]
        pp = pr["papeis"][papel]
        at = pr["ativa"]

        cor = self._resolver_cor(pp["cor"]) or self.cor
        if ativa:
            if at["cor"]:
                cor = self._resolver_cor(at["cor"])
            elif not pp["caixa"]:
                cor = self.destaque
            # papel com caixa colorida e ativa sem cor propria: mantem a cor
            # do papel — senao vira texto amarelo em pilula amarela e a
            # palavra desaparece exatamente quando e falada

        sombras = []
        base_sombra = at["sombra"] if (ativa and at["sombra"]) else pp["sombra"]
        # brilho da palavra ativa: um halo na cor de destaque
        if ativa and at["brilho"]:
            sombras.append(Shadow(0, 0, float(at["brilho"]), self.destaque + "90"))
        if base_sombra:
            dx, dy, blur, c = base_sombra
            sombras.append(Shadow(dx, dy, blur, self._resolver_cor(c) or c))

        # "auto" = a espessura que o estilo classico usava (9% do tamanho)
        cont = pp["contorno"]
        stroke = float(self.stroke) if cont == "auto" else float(cont or 0)
        # Palavra com caixa: o texto e chapado e a sombra pertence a PILULA
        # (o _caixa desenha ela). Deixar a sombra no texto dobraria o efeito
        # e divergiria do boxed classico.
        if pp["caixa"] or (ativa and at["caixa"]):
            sombras = []
            stroke = 0.0

        fam = pp["fonte"] or self.fonte
        return TextBlock(
            registry=self.reg, text=texto, css_family=f"'{fam}', sans-serif",
            weight=int(pp["peso"]), italic=bool(pp["italico"]),
            font_size=max(8, round(self.fs * float(pp["escala"]))),
            color=cor, line_height=LINE_HEIGHT,
            shadows=sombras, stroke_width=stroke, max_width=None)

    def palavra(self, bruta: str, estilo: str | None = None,
                papel: str = "normal") -> Palavra:
        """`text-transform` do preset — em pt-BR o .upper() do Python ja acentua certo."""
        estilo = estilo or self.estilo
        texto = bruta.upper() if self._preset[estilo].get("caixa_alta", True) else bruta
        # cache por (estilo, papel, texto): a mesma palavra como `power` e como
        # `small` sao imagens diferentes
        chave = (estilo, papel, texto)
        p = self._palavras.get(chave)
        if p is None:
            normal = self._bloco(texto, False, estilo, papel)
            # com caixa, a "palavra" e a pilula inteira: o padding entra na
            # largura, senao o flex quebraria a linha no lugar errado
            tem_caixa = bool(self._preset[estilo]["papeis"][papel]["caixa"])
            larg = normal.width + (2 * BOX_PAD_X if tem_caixa else 0)
            p = Palavra(texto=texto, largura=larg, papel=papel,
                        normal=normal, ativa=self._bloco(texto, True, estilo, papel))
            self._palavras[chave] = p
        return p

    # ── estado por tempo ──────────────────────────────────────────────────
    def _ativa_em(self, t: float):
        lo, hi = 0, len(self.legendas) - 1
        while lo <= hi:
            mid = (lo + hi) >> 1
            c = self.legendas[mid]
            if t < float(c["startSec"]):
                hi = mid - 1
            elif t >= float(c["endSec"]):
                lo = mid + 1
            else:
                return c
        return None

    def estado(self, frame: float) -> EstadoGrupo | None:
        t = (frame / self.fps) * self.rate
        ativa = self._ativa_em(t)
        if not ativa:
            return None
        palavras_txt = [w for w in (ativa.get("text") or "").split() if w]
        if not palavras_txt:
            return None

        dur = float(ativa["endSec"]) - float(ativa["startSec"])
        decorrido = t - float(ativa["startSec"])
        progresso = min(max(decorrido / dur, 0.0), 1.0) if dur > 0 else 0.0

        total = math.ceil(len(palavras_txt) / self.wpg)
        gi = min(int(progresso * total), total - 1)
        do_grupo = palavras_txt[gi * self.wpg:min((gi + 1) * self.wpg, len(palavras_txt))]

        dur_grupo = dur / total
        decorrido_grupo = decorrido - gi * dur_grupo
        prog_grupo = min(max(decorrido_grupo / dur_grupo, 0.0), 1.0) if dur_grupo > 0 else 0.0

        hi = (min(int(prog_grupo * len(do_grupo)), len(do_grupo) - 1)
              if self.karaoke else -1)
        dur_palavra = dur_grupo / len(do_grupo)
        decorrido_palavra = max(0.0, (prog_grupo * len(do_grupo) - hi) * dur_palavra)
        estilo = ativa.get("subStyle") or self.estilo
        # `wordPop(..., 1.12)` no TSX vale pro outline E pro words; os demais
        # assentam em 1.08. Deixei como constante em vez de ler `ativa.escala`
        # do preset porque isso mudaria `destaque` e `forte-caixa` (que pedem
        # 1.10) sem ninguem ter pedido.
        settle = 1.12 if estilo in ("outline", "words") else 1.08
        # ...mas um preset PODE declarar o próprio assentamento. Quem não
        # declara (todos os seis originais) continua caindo na regra acima.
        declarado = self._preset[estilo]["ativa"].get("assenta")
        if declarado is not None:
            settle = float(declarado)

        papeis = classificar(do_grupo)
        return EstadoGrupo(
            palavras=[self.palavra(w, estilo, pa)
                      for w, pa in zip(do_grupo, papeis)],
            hi=hi,
            # `assenta <= 1` = preset sem karaokê nenhum. Não basta assentar em
            # 1.0: `word_pop` sobe de 0.8 e passa de 1.11 no meio do pulso, e
            # numa palavra larga esses 11% valem mais que o vão inteiro — a
            # palavra ativa encosta na anterior. No original isso não aparece
            # porque lá o pico da escala coincide com a opacidade quase zero da
            # entrada; aqui a palavra ativa já está opaca.
            pop=word_pop(decorrido_palavra, settle) if settle > 1.0 else 1.0,
            escala=grupo_scale(decorrido_grupo),
            estilo=estilo,
        )

    def signature(self, frame: float):
        """Frames com a mesma assinatura sao identicos — quem renderiza pula."""
        e = self.estado(frame)
        if e is None:
            return ("vazio",)
        return (e.estilo, tuple((p.texto, p.papel) for p in e.palavras), e.hi,
                round(e.pop, 4), round(e.escala, 4))

    # ── layout flex ───────────────────────────────────────────────────────
    def _linhas(self, palavras: list[Palavra]):
        """Quebra do flex-wrap: enche a linha enquanto couber na largura."""
        linhas, atual, larg = [], [], 0.0
        for p in palavras:
            passo = p.largura if not atual else self.gap_col + p.largura
            if atual and larg + passo > self.largura_container:
                linhas.append((atual, larg))
                atual, larg = [p], p.largura
            else:
                atual.append(p)
                larg += passo
        if atual:
            linhas.append((atual, larg))
        return linhas

    def _geometria(self, linhas, estilo: str | None = None):
        """Devolve (altura, topo, centro_y_do_container_interno)."""
        alt = self._alt[estilo or self.estilo]
        n = len(linhas)
        altura = n * alt + (n - 1) * self.gap_row
        # `bottom: 20%` mede da base do container; o transform do CSS e
        # translate(captionX, -captionY), entao posY positivo SOBE.
        base = (self.h - BOTTOM_PCT * self.h) - self.pos_y
        topo = base - altura
        return altura, topo, topo + altura / 2

    # ── desenho ───────────────────────────────────────────────────────────
    def _caixa(self, canvas: skia.Canvas, x: float, y: float, larg: float,
               ativa: bool, alt: float | None = None, fundo: str | None = None):
        """A pilula do `boxed`: fundo arredondado + a sombra dela."""
        rect = skia.RRect.MakeRectXY(
            skia.Rect.MakeXYWH(x, y, larg, alt or self.altura_linha), BOX_RAIO, BOX_RAIO)

        # box-shadow do CSS: um blur do proprio retangulo, deslocado.
        # ativa  -> 0 6px 26px destaque70  +  0 2px 10px rgba(0,0,0,.5)
        # parada -> 0 2px 10px rgba(0,0,0,.4)
        sombras = ([(0, 6, 26, self.destaque + "70"), (0, 2, 10, "#00000080")] if ativa
                   else [(0, 2, 10, "#00000066")])
        for dx, dy, blur, cor in sombras:
            p = skia.Paint(AntiAlias=True, Color=css_color(cor))
            # o raio do CSS e 2 sigma, igual ao text-shadow
            p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur / 2.0))
            canvas.save()
            canvas.translate(dx, dy)
            canvas.drawRRect(rect, p)
            canvas.restore()

        fundo = css_color(fundo or (self.destaque if ativa else BOX_FUNDO_PARADO))
        canvas.drawRRect(rect, skia.Paint(AntiAlias=True, Color=fundo))

    def draw_frame(self, canvas: skia.Canvas, frame: float, estado: EstadoGrupo | None = None):
        e = self.estado(frame) if estado is None else estado
        if e is None:
            return
        estilo = e.estilo
        alt_linha = self._alt[estilo]
        linhas = self._linhas(e.palavras)
        altura, topo, centro_y = self._geometria(linhas, estilo)
        centro_x = self.w / 2 + self.pos_x

        canvas.save()
        # escala do grupo, em torno do centro da caixa interna
        canvas.translate(centro_x, centro_y)
        canvas.scale(e.escala, e.escala)
        canvas.translate(-centro_x, -centro_y)

        # Caixa do GRUPO — vem DEPOIS da escala (cresce junto com o texto no
        # quique de entrada) e ANTES das palavras, senao cobriria o texto.
        cont = self._preset[estilo].get("container")
        if cont and linhas:
            larg_max = max(l[1] for l in linhas)
            cw = larg_max + cont["pad_x"] * 2
            ch = altura + cont["pad_y"] * 2
            canvas.drawRRect(
                skia.RRect.MakeRectXY(
                    skia.Rect.MakeXYWH(centro_x - cw / 2, topo - cont["pad_y"],
                                       cw, ch),
                    cont["raio"], cont["raio"]),
                skia.Paint(AntiAlias=True, Color=css_color(cont["fundo"])))

        idx = 0
        y = topo
        for palavras, larg in linhas:
            x = centro_x - larg / 2
            for p in palavras:
                ativa = idx == e.hi
                bloco = p.ativa if ativa else p.normal
                cx = x + p.largura / 2
                pr = self._preset[estilo]
                precisa_pop = ativa and abs(e.pop - 1) > 1e-4
                if precisa_pop:
                    canvas.save()
                    # de onde o estouro cresce — ver `origem` em PADRAO_ATIVA
                    if pr["ativa"].get("origem") == "esq":
                        ox, oy = x, y + alt_linha
                    else:
                        ox, oy = cx, y + alt_linha / 2
                    canvas.translate(ox, oy)
                    canvas.scale(e.pop, e.pop)
                    canvas.translate(-ox, -oy)
                fundo = (self._resolver_cor(pr["ativa"]["caixa"]) if ativa else None) \
                        or self._resolver_cor(pr["papeis"][p.papel]["caixa"])
                if fundo:
                    self._caixa(canvas, x, y, p.largura, ativa, alt_linha, fundo)
                    # o texto fica centrado na pilula: o padding vertical
                    # empurra o topo pra baixo
                    bloco.draw(canvas, cx, y + BOX_PAD_Y)
                elif not precisa_pop and abs(e.escala - 1) < 1e-4:
                    # grupo parado e palavra sem estouro: sai direto do cache
                    bloco.draw_flat(canvas, cx, y)
                else:
                    bloco.draw(canvas, cx, y)
                if precisa_pop:
                    canvas.restore()
                x += p.largura + self.gap_col
                idx += 1
            y += alt_linha + self.gap_row
        canvas.restore()

    # ── faixa vertical ────────────────────────────────────────────────────
    def band(self, margem: float = 8.0) -> tuple[int, int]:
        """
        Menor faixa (y0, y1) que contem QUALQUER frame de legenda.

        Renderizar so ela e o que torna o overlay de video inteiro viavel:
        frame cheio de 1080x1920 sao 8,3 MB; a faixa costuma dar um terco.
        """
        if self._banda is not None:
            return self._banda

        pior_topo, pior_base = self.h, 0.0
        # o pior caso combina o quique do grupo com o estouro da palavra
        esc_max = max(grupo_scale(g / 100.0 * 0.14) for g in range(101))
        pop_max = max(word_pop(p / 100.0 * 0.16, 1.12) for p in range(101))

        vistos = set()
        for c in self.legendas:
            palavras_txt = [w for w in (c.get("text") or "").split() if w]
            total = math.ceil(len(palavras_txt) / self.wpg) if palavras_txt else 0
            for gi in range(total):
                grupo = tuple(palavras_txt[gi * self.wpg:(gi + 1) * self.wpg])
                if grupo in vistos:
                    continue
                vistos.add(grupo)
                est = c.get("subStyle") or self.estilo
                palavras = [self.palavra(w, est, pa)
                            for w, pa in zip(grupo, classificar(list(grupo)))]
                linhas = self._linhas(palavras)
                altura, topo, centro_y = self._geometria(linhas, est)
                alt_est = self._alt[est]
                y = topo
                for _, _ in linhas:
                    for p in palavras[:1] + palavras[-1:]:
                        r = p.ativa.ink_bounds(self.w / 2, y)
                        cy = y + alt_est / 2
                        # estouro da palavra, depois quique do grupo
                        t0 = cy + (r.top() - cy) * pop_max
                        b0 = cy + (r.bottom() - cy) * pop_max
                        t0 = centro_y + (t0 - centro_y) * esc_max
                        b0 = centro_y + (b0 - centro_y) * esc_max
                        pior_topo = min(pior_topo, t0)
                        pior_base = max(pior_base, b0)
                    y += alt_est + self.gap_row

        if pior_base <= pior_topo:      # sem legenda nenhuma
            self._banda = (0, 0)
            return self._banda

        # A faixa mede a TINTA das palavras. Onde ha caixa de grupo, ela passa
        # do texto pelo padding — e a faixa tem que conter a CAIXA, senao o
        # overlay corta o topo dela e a legenda sai com o fundo decepado.
        pad_cont = max((float((p.get("container") or {}).get("pad_y", 0.0))
                        for p in self._preset.values()), default=0.0)
        if pad_cont:
            pior_topo -= pad_cont * esc_max
            pior_base += pad_cont * esc_max
        y0 = max(0, int(math.floor(pior_topo - margem)))
        y1 = min(self.h, int(math.ceil(pior_base + margem)))
        # altura par: alguns codecs implicam com dimensao impar
        if (y1 - y0) % 2:
            y1 = min(self.h, y1 + 1) if y1 < self.h else y1
            if (y1 - y0) % 2:
                y0 = max(0, y0 - 1)
        self._banda = (y0, y1)
        return self._banda
