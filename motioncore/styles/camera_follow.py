"""
camera_follow.py — "Camera Follow Captions": legenda palavra a palavra onde
quem se move é a CÂMERA, não o texto.

Porta de uma sessão privada do HyperFrames que o usuário colou à mão em
2026-08-30 (o original em GSAP/DOM está em
referencias/hyperframes-sessoes/caption-camera-follow.html).

O layout é autossimilar: cada palavra nova nasce como fração da ALTURA da
caixa de tudo que já foi escrito, e encosta à direita ou embaixo dessa caixa,
conforme ela esteja mais estreita ou mais larga que o quadro. Como a caixa
cresce a partir de si mesma, ela cresce em progressão geométrica — e é por
isso que a câmera recua num ritmo exponencial constante e cada palavra chega
em tela mais ou menos do mesmo tamanho. As palavras velhas não apagam: só
ficam pequenas, empilhando pro canto de cima como escrita enchendo a página.

Por que é módulo Python e não uma `cena` declarativa: a posição de cada
palavra depende da largura MEDIDA da anterior, numa corrente. O DSL anima
valor conhecido de antemão, não sabe "meça o que já foi escrito" (ver
motioncore/cena/DSL.md, "Quando não usar o DSL"). Com texto livre, a medição
precisa rodar de verdade — e roda uma vez, no `build`.

Ajustes (em `opcoes`, ver `Title.opcoes`), com os mesmos nomes e valores do
original:

    acento    gold | green | blue | violet     cor das palavras destacadas
    ar        tight | standard | wide          ar que a câmera deixa em volta
    borrao    off | subtle | standard | heavy  quanto o corte de câmera arrasta

Quais palavras ganham o destaque, o original decidia à mão no roteiro dele.
Aqui é `*assim*`: qualquer palavra com asterisco sai na cor de acento. Sem
nenhum asterisco, sai tudo na cor do texto — que é o que o original faria com
uma frase sem palavra marcada.

Uma diferença de propósito, e é a única: `line-height`, `letter-spacing`,
`text-transform`, as cinco curvas bezier, a cadência (STEP/MOVE), a razão de
crescimento e as margens são as do original, número por número. A FONTE não
pode ser: o original pede Helvetica Neue, que não existe aqui. O padrão é
Montserrat 700, o peso que o original usa.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import skia

from ..box import camada_alpha, camada_blur, preenche, transform
from ..cena.valores import easing as _bezier
from ..text import TextBlock
from ._common import TitleCtx, css_opacity

# ── as tabelas de opção, iguais às do original ───────────────────────────
ACENTOS = {"gold": "#FFD84D", "green": "#34D399", "blue": "#38BDF8",
           "violet": "#A78BFA"}
ARES = {"tight": 0.82, "standard": 1.0, "wide": 1.25}
BORROES = {"off": 0.0, "subtle": 0.5, "standard": 1.0, "heavy": 1.9}

INK = "#FFFFFF"

# ── ritmo e geometria, número por número do original ─────────────────────
STEP = 0.52            # segundos entre a chegada de uma palavra e a próxima
MOVE = 0.4             # duração de cada corte de câmera
RATIO = 0.72           # palavra nova = esta fração da altura da caixa atual
MARGEM = 1.36          # ar em volta do bloco, nos cortes internos
LH = 0.78              # `line-height` do original — é também a altura da caixa
LS = 0.005             # `letter-spacing` em em
GAP = 0.07             # respiro entre palavras, em fração do tamanho da fonte
BASE_FRAC = 0.16       # a primeira palavra, em fração do maior lado do quadro
MARGEM_FIM = 1.2       # o plano final abre mais que os cortes internos
ESPERA_FIM = 0.62      # segundos entre a última palavra e o recuo final
DUR_FIM = 0.94
PICO = 0.026           # pico do borrão, em fração da largura do quadro
SOBE, DESCE = 0.24, 0.44          # do corte, em fração de MOVE
SOBE_FIM, DESCE_FIM = 0.3, 0.58   # do recuo final, em segundos
PICO_FIM = 0.8                    # o recuo final arrasta menos que os cortes
VINHETA = "rgba(0,0,0,0) 42%, rgba(0,0,0,0.55) 100%"

# As cinco curvas do original. Todas bezier cúbica escrita à mão — nenhuma é
# um easing nomeado, e trocar por "o nomeado mais parecido" muda o gesto.
E_CORTE = _bezier([0.31, 0, 0.11, 1])     # sai rápido, passa o tempo chegando
E_FIM = _bezier([0.42, 0, 0.14, 1])       # o recuo final: sai devagar, desliza
E_TINTA = _bezier([0.2, 0.7, 0.3, 1])     # a palavra acendendo
E_BORRA_SOBE = _bezier([0.2, 0.8, 0.4, 1])
E_BORRA_DESCE = _bezier([0.5, 0, 0.2, 1])


@dataclass
class _Palavra:
    bloco: TextBlock
    fs: float
    x: float
    y: float
    w: float
    h: float
    box: tuple                 # caixa acumulada ATÉ e incluindo esta palavra
    cx: float                  # centro da palavra, pro cálculo do borrão radial
    cy: float


def _palavras(texto: str) -> list[tuple[str, bool]]:
    """Separa em palavras e diz quais estão marcadas com `*`.

    Tolerante de propósito: `*palavra*`, `*palavra`, `palavra*` e `*palavra*,`
    marcam todas. Quem escreve legenda não vai conferir se fechou o asterisco,
    e a alternativa (ignorar calado a marca malfeita) é a pior das duas.
    """
    fora = []
    for p in re.split(r"\s+", (texto or "").strip()):
        if not p:
            continue
        limpo = p.replace("*", "")
        if limpo:
            fora.append((limpo, "*" in p))
    return fora


def _pose(box, margem, w, h):
    """Onde a câmera fica pra enquadrar `box` com `margem` de ar em volta."""
    bw = (box[2] - box[0]) * margem
    bh = (box[3] - box[1]) * margem
    if bw <= 0 or bh <= 0:
        return (0.0, 0.0, 1.0)
    s = min(w / bw, h / bh)
    return (w / 2.0 - s * (box[0] + box[2]) / 2.0,
            h / 2.0 - s * (box[1] + box[3]) / 2.0, s)


def build(ctx: TitleCtx, registry, canvas_w: int, canvas_h: int):
    pares = _palavras(ctx.text) or [("escreva", False), ("o", False),
                                    ("texto", True), ("aqui", False)]
    familia = ctx.font("'Montserrat', sans-serif")
    tinta = ctx.clr
    acento = ctx.opcao("acento", ACENTOS, "gold")

    base = max(canvas_w, canvas_h) * BASE_FRAC
    itens: list[_Palavra] = []
    box = None
    for i, (txt, marcada) in enumerate(pares):
        alto = txt.upper()
        fs = base if i == 0 else (box[3] - box[1]) * RATIO
        bloco = TextBlock(registry=registry, text=alto, css_family=familia,
                          weight=700, font_size=fs,
                          color=acento if marcada else tinta,
                          line_height=LH, letter_spacing=fs * LS)
        bw = bloco.measure(alto) + fs * LS
        bh = fs * LH
        gap = fs * GAP

        if i == 0:
            x, y = 0.0, 0.0
        elif (box[2] - box[0]) / (box[3] - box[1]) < canvas_w / canvas_h:
            # bloco mais estreito que o quadro: cresce pro lado, mesma base
            x, y = box[2] + gap, box[3] - bh
        else:
            # bloco já tomou a largura: desce pra linha nova, alinhado à esquerda
            x, y = box[0], box[3] + gap

        nova = (x, y, x + bw, y + bh)
        box = (min(box[0], nova[0]), min(box[1], nova[1]),
               max(box[2], nova[2]), max(box[3], nova[3])) if box else nova
        itens.append(_Palavra(bloco, fs, x, y, bw, bh, box,
                              x + bw / 2.0, y + bh / 2.0))
    return itens


def _segmentos(itens, w, h, margem, margem_fim):
    """Um segmento por corte de câmera.

    Cada um carrega, além do par de poses, o que o borrão precisa: o CENTRO do
    que a câmera está mirando e a ESCALA de destino. É daí que sai o quanto
    cada palavra arrasta — quem está longe do alvo varre mais quadro e por
    isso borra mais, que é o que faz o corte parecer câmera e não corte seco.
    """
    segs = []
    pose = _pose(itens[0].box, margem, w, h)
    for i, p in enumerate(itens):
        if i == 0:
            continue
        t0 = i * STEP
        alvo = _pose(p.box, margem, w, h)
        centro = ((p.box[0] + p.box[2]) / 2.0, (p.box[1] + p.box[3]) / 2.0)
        segs.append((t0, t0 + MOVE, pose, alvo, E_CORTE, centro, alvo[2],
                     MOVE * SOBE, MOVE * DESCE, 1.0, i + 1))
        pose = alvo
    cheio = itens[-1].box
    t0 = (len(itens) - 1) * STEP + ESPERA_FIM
    alvo = _pose(cheio, margem_fim, w, h)
    centro = ((cheio[0] + cheio[2]) / 2.0, (cheio[1] + cheio[3]) / 2.0)
    segs.append((t0, t0 + DUR_FIM, pose, alvo, E_FIM, centro, alvo[2],
                 SOBE_FIM, DESCE_FIM, PICO_FIM, len(itens)))
    return segs, _pose(itens[0].box, margem, w, h)


def _pose_em(t, segs, pose0):
    pose = pose0
    for t0, t1, p0, p1, ease, *_ in segs:
        if t <= t0:
            return pose
        if t >= t1:
            pose = p1
            continue
        f = ease((t - t0) / (t1 - t0))
        return tuple(p0[k] + (p1[k] - p0[k]) * f for k in range(3))
    return pose


def _borrao_em(t, segs, pico):
    """(quanto de borrão, centro do corte, escala do corte, quantas palavras).

    O valor volta em unidade de MUNDO, não de tela: o borrão é aplicado dentro
    da transform da câmera, então um raio pedido aqui sai multiplicado pela
    escala quando chega na tela. Dividir pela escala de destino desfaz isso —
    é a mesma conta que o CSS faz num `filter` dentro de um pai escalado, e é
    por isso que o original escreve `amt = peak / scale`.
    """
    if pico <= 0:
        return 0.0, (0.0, 0.0), 1.0, 0
    for t0, _t1, _p0, _p1, _e, centro, escala, sobe, desce, mult, n in segs:
        if not (t0 <= t < t0 + sobe + desce):
            continue
        alvo = (pico * mult) / max(escala, 1e-6)
        if t < t0 + sobe:
            return alvo * E_BORRA_SOBE((t - t0) / sobe), centro, escala, n
        return (alvo * (1.0 - E_BORRA_DESCE((t - t0 - sobe) / desce)),
                centro, escala, n)
    return 0.0, (0.0, 0.0), 1.0, 0


def _anim(ctx: TitleCtx, itens):
    if not itens:
        return (0.0, (0.0, 0.0, 1.0), (), ())
    w, h = ctx.larg, ctx.alt
    ar = ctx.opcao("ar", ARES, "standard")
    forca = ctx.opcao("borrao", BORROES, "standard")
    segs, pose0 = _segmentos(itens, w, h, MARGEM * ar, MARGEM_FIM * ar)

    t = ctx.frame / ctx.fps
    pose = _pose_em(t, segs, pose0)

    ops = []
    for i in range(len(itens)):
        if i == 0:
            ops.append(1.0)          # já está na página quando o plano abre
            continue
        ops.append(round(E_TINTA(min(1.0, max(0.0, (t - i * STEP) / 0.16))), 4))

    amt, centro, escala, n = _borrao_em(t, segs, w * PICO * forca)
    meia_diag = math.hypot(w, h) / 2.0
    borroes = []
    for i, it in enumerate(itens):
        if amt <= 0 or i >= n:
            borroes.append(0.0)
            continue
        # Quanto esta palavra varre de quadro durante o corte: longe do alvo,
        # varre mais, borra mais. É o borrão radial — o quadro esfrega pra
        # fora do ponto que a câmera está mirando.
        d = escala * math.hypot(it.cx - centro[0], it.cy - centro[1]) / meia_diag
        borroes.append(round((0.2 + 1.15 * min(1.0, d)) * amt, 3))

    return (round(css_opacity(ctx.opacity), 6),
            tuple(round(v, 3) for v in pose),
            tuple(ops), tuple(borroes))


def draw(canvas: skia.Canvas, ctx: TitleCtx, registry, canvas_w: int,
         canvas_h: int, blocos=None):
    itens = blocos or build(ctx, registry, canvas_w, canvas_h)
    op, pose, ops, borroes = _anim(ctx, itens)
    if op <= 0 or not itens:
        return
    camx, camy, esc = pose

    with camada_alpha(canvas, None, op):
        with transform(canvas, (0.0, 0.0), translate=(camx, camy), scale=esc):
            for i, it in enumerate(itens):
                o = ops[i] if i < len(ops) else 1.0
                if o <= 0.001:
                    continue
                cx = it.x + it.w / 2.0
                sigma = borroes[i] if i < len(borroes) else 0.0
                if sigma > 0.3:
                    # uma camada por palavra: cada uma borra o SEU tanto, que é
                    # o que separa borrão radial de borrão chapado no quadro
                    with camada_blur(canvas, it.bloco.ink_bounds(cx, it.y), sigma):
                        it.bloco.draw(canvas, cx, it.y, opacity=o)
                else:
                    it.bloco.draw(canvas, cx, it.y, opacity=o)
        # Fora da transform: a vinheta é do QUADRO, não do mundo — se entrasse
        # junto ela escalaria com a câmera e sumiria no primeiro recuo.
        preenche(canvas, skia.Rect.MakeWH(canvas_w, canvas_h),
                 ("radial", VINHETA))


def signature(ctx: TitleCtx, blocos) -> tuple:
    return ("cf",) + _anim(ctx, blocos)
