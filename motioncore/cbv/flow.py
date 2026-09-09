# -*- coding: utf-8 -*-
"""flow.py — a cena Flow Demo do CreativlyBrandVideo.

Um canvas de nos que se monta sozinho: imagem -> video -> imagem -> LLM, com a
camera recuando de 1.45x para 0.75x e derivando de x=+120 para x=-230
(FlowDemoScene.tsx:79-96). Os quatro cards entram por mola nos frames 8/52/72/92
(:103-106), as tres arestas bezier se DESENHAM (traco 0->1) nos frames 52-66,
72-85 e 92-106 (:126-134), e cada prompt e datilografado por `revelar` na janela
exata do typewriter original (:109-112).

Decisao de fundo: a camera do original e um `transform` num div que embrulha o
canvas inteiro. Aqui ela vira keyframes de x/y/escala em CADA camada de canvas
(helper `_na_tela`), amostrados nos mesmos seis nos da interpolacao do .tsx —
assim a cena nao esconde a densidade dentro de um `grupo`, e o mesmo movimento
sai identico. `escala` fica com a camera; a mola de entrada dos cards mora em
`escalaX`/`escalaY`, que o motor multiplica por ela.
"""
import math

from .base import *

# ── formato e relogio ────────────────────────────────────────────────────
DUR = 5.5                       # constants.ts:36 — DURATIONS.flowDemo
CX_CANVAS, CY_CANVAS = 1200.0, 700.0    # centro do canvas 2400x1400 (:257-259)

# ── camera (:79-96) — seis nos, easing inOut(cubic) = "suave" do motor ───
CAM_T = [f * F for f in (0, 20, 55, 90, 125, 165)]
CAM_S = [1.45, 1.25, 1.00, 0.88, 0.78, 0.75]
CAM_X = [120.0, 80.0, -40.0, -150.0, -220.0, -230.0]
CAM_Y = [40.0, 25.0, -10.0, -40.0, -30.0, -25.0]

# ── paleta do FlowNode.tsx:9-14 e do card ────────────────────────────────
COR_IMG = "#3B82F6"
COR_VID = "#8B5CF6"
COR_LLM = "#F59E0B"
CARD_BG = "#121212F2"           # rgba(18,18,18,0.95)
CARD_BORDA = "#FFFFFF14"        # rgba(255,255,255,0.08)
AREA_BG = "#00000059"           # rgba(0,0,0,0.35)
DIVISOR = "#FFFFFF0F"           # rgba(255,255,255,0.06)
PILL_TXT = "#FFFFFF73"          # rgba(255,255,255,0.45)
LABEL_TXT = "#FFFFFFD9"         # rgba(255,255,255,0.85)
PROMPT_BG = "#FFFFFF08"
PROMPT_BORDA = "#FFFFFF0A"
PROMPT_TXT = "#FFFFFF66"        # rgba(255,255,255,0.4)
FIO = "#78788773"               # rgba(120,120,135,0.45) — cor da aresta (:290)

# ── os quatro nos (:27-32), ja em coordenada relativa ao centro do canvas,
#    com y DESCENDO (convencao do CSS de origem) ─────────────────────────
NOS = [
    dict(chave="img1", dx=680 + 150 - CX_CANVAS, dy=360 + 190 - CY_CANVAS,
         w=300, h=380, cor=COR_IMG, rot="Image", modelo="nano-banana",
         t=8 * F, sel0=8 * F, sel1=52 * F, glow=12 * F, s=101),
    dict(chave="vid1", dx=1130 + 150 - CX_CANVAS, dy=490 + 170 - CY_CANVAS,
         w=300, h=340, cor=COR_VID, rot="Video", modelo="veo-3.1",
         t=52 * F, sel0=52 * F, sel1=72 * F, glow=55 * F, s=202),
    dict(chave="img2", dx=1130 + 150 - CX_CANVAS, dy=110 + 170 - CY_CANVAS,
         w=300, h=340, cor=COR_IMG, rot="Image", modelo="nano-banana",
         t=72 * F, sel0=72 * F, sel1=92 * F, glow=75 * F, s=303),
    dict(chave="llm1", dx=1580 + 160 - CX_CANVAS, dy=400 + 140 - CY_CANVAS,
         w=320, h=280, cor=COR_LLM, rot="LLM", modelo="gemini-flash",
         t=92 * F, sel0=92 * F, sel1=130 * F, glow=95 * F, s=404),
]


# ── a camera, amostrada ──────────────────────────────────────────────────
def _io3(u: float) -> float:
    """inOut(cubic) — a curva que o .tsx pede nos tres interpolate da camera."""
    return 4 * u * u * u if u < 0.5 else 1 - ((-2 * u + 2) ** 3) / 2


def _ioq(u: float) -> float:
    """inOut(quad) — a varredura do scan line (:120-122)."""
    return 2 * u * u if u < 0.5 else 1 - ((-2 * u + 2) ** 2) / 2


def _entre(t: float, ys: list) -> float:
    if t <= CAM_T[0]:
        return float(ys[0])
    if t >= CAM_T[-1]:
        return float(ys[-1])
    for i in range(len(CAM_T) - 1):
        if CAM_T[i] <= t <= CAM_T[i + 1]:
            d = CAM_T[i + 1] - CAM_T[i]
            u = 0.0 if d <= 0 else (t - CAM_T[i]) / d
            return ys[i] + (ys[i + 1] - ys[i]) * _io3(u)
    return float(ys[-1])


def _cam(t: float) -> tuple:
    return _entre(t, CAM_S), _entre(t, CAM_X), _entre(t, CAM_Y)


def _na_tela(dx: float, dy: float, t0: float = 0.0, subir: float = 0.0) -> dict:
    """Ponto do canvas -> x/y/escala de tela, com a camera embutida.

    `dy` DESCE (coordenada do .tsx); o motor sobe, entao ele e negado.
    `subir` e a translateY(20*(1-entrance)) do FlowNode.tsx:114 — vira um no
    extra de 0.45 s no inicio da lista, com outCubic no keyframe que ABRE o
    trecho (armadilha 6).
    """
    marcas = [round(t0, 4), DUR] + [round(k, 4) for k in CAM_T if t0 < k < DUR]
    if subir and t0 + 0.45 < DUR:
        marcas.append(round(t0 + 0.45, 4))
    ts = sorted(set(marcas))
    kx, ky, ke = [], [], []
    for t in ts:
        s, cx, cy = _cam(t)
        kx.append([t, cx + s * dx])
        ky.append([t, -(cy + s * dy) - (subir if t <= t0 else 0.0)])
        ke.append([t, s])
    if subir:
        ky[0] = [ts[0], ky[0][1], "outCubic"]
    return {"x": kx, "y": ky, "escala": ke}


def _varre(dx0: float, dx1: float, dy: float, t0: float, t1: float,
           curva=None, n: int = 7) -> dict:
    """Como `_na_tela`, mas o ponto TAMBEM caminha em x entre t0 e t1.

    A camera nao pode virar mola nem ruido — ela e keyframe. Entao quem se move
    por cima dela e amostrado junto, e o trecho entre amostras vai em "linear".
    """
    ts = sorted(set([t0 + (t1 - t0) * i / n for i in range(n + 1)]
                    + [k for k in CAM_T if t0 < k < t1]))
    kx, ky, ke = [], [], []
    for t in ts:
        u = 1.0 if t1 <= t0 else min(1.0, max(0.0, (t - t0) / (t1 - t0)))
        if curva:
            u = curva(u)
        s, cx, cy = _cam(t)
        kx.append([round(t, 4), cx + s * (dx0 + (dx1 - dx0) * u), "linear"])
        ky.append([round(t, 4), -(cy + s * dy), "linear"])
        ke.append([round(t, 4), s, "linear"])
    for k in (kx, ky, ke):
        k[-1] = k[-1][:2]
    return {"x": kx, "y": ky, "escala": ke}


# ── gestos locais ────────────────────────────────────────────────────────
def _sel(n: dict) -> list:
    """Envelope da borda de selecao: acende com o spring de glow, apaga quando
    o proximo no e escolhido (:137-144)."""
    return [[n["sel0"], 0.0, "outCubic"], [n["glow"] + 0.45, 1.0],
            [n["sel1"], 1.0], [n["sel1"] + 0.28, 0.0]]


def _maquina(txt: str, tam: float, t0: float, t1: float) -> dict:
    """Typewriter por cortina. O motor nao revela por caractere — `revelar` e
    wipe. Medindo o bloco com larg_texto(), a cortina passa pela caixa do texto
    na mesma janela de frames do `promptChars` original."""
    meia = larg_texto(txt, tam) * 0.62
    ext = 1920.0
    return {"prog": [[round(t0, 4), (ext / 2 - meia) / ext, "linear"],
                     [round(t1, 4), (ext / 2 + meia) / ext]], "dir": "esq"}


def _estrela_d(r: float) -> str:
    """makeStar({points:4}) do @remotion/shapes (:360), escrito a mao."""
    p = []
    for i in range(8):
        a = -math.pi / 2 + i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.3
        p.append("%.2f %.2f" % (rr * math.cos(a), rr * math.sin(a)))
    return "M " + " L ".join(p) + " Z"


def cena(dur: float) -> dict:
    cam: list = []

    # ══ 1. ATMOSFERA (espaco de tela, fora da camera) ═══════════════════
    # tres orbes de luz (:182-216) — posicoes convertidas de %/px do CSS
    cam.append(brilho(-322, -80, 350, MARCA, 0.0, 0.30, 3))
    cam.append(brilho(614, -304, 250, CIANO, 0.12, 0.24, 11))
    cam.append(brilho(8, -232, 200, SECUNDARIA, 0.24, 0.18, 17))

    # quatro diamantes flutuantes (:219-223) — quadrado girando, com micro-vida
    for i, (x, y, t, cor, giro) in enumerate([
            (-870, 440, 32, MARCA, 115), (820, 410, 22, CIANO, 180),
            (720, -340, 40, SECUNDARIA, 82), (-780, -310, 18, MARCA, 148)]):
        cam.append({
            "tipo": "retangulo", "larg": t, "alt": t, "raio": 3,
            "cor": cor + "12", "contorno": cor + "44", "contorno_larg": 1.5,
            "rotacao": [[0, 45.0, "linear"], [DUR, 45.0 + giro]],
            **viva(x, y, 7, 40 + i * 13),
            "opacidade": [[0.1 + i * BLOCO, 0.0, "outCubic"],
                          [0.9 + i * BLOCO, 0.85]]})

    # dois aneis de pulso (:226) — anel = sem `cor`, so contorno (armadilha 2)
    cam.append({"tipo": "elipse", "contorno": MARCA + "1C", "contorno_larg": 1.5,
                "raio": [[0, 150, "linear"], [DUR, 620]],
                "opacidade": [[0, 0.0, "outCubic"], [0.9, 1.0], [DUR, 0.0]]})
    cam.append({"tipo": "elipse", "contorno": CIANO + "16", "contorno_larg": 1.5,
                "raio": [[0, 400, "linear"], [DUR, 880]],
                "opacidade": [[0, 0.9], [DUR, 0.0]]})

    # marca d'agua "FLOW" 480px italica -12deg, respirando entre 0.012 e 0.028
    # (:229-253). O original a pinta em degrade; texto do motor e cor chapada.
    agua = marca_dagua("FLOW", 480, MARCA, -12, 0.028)
    agua["opacidade"] = pulso(0.022, 0.009, 0.005, 7)
    cam.append(agua)

    # grade de pontos do canvas (:268-278) — textura, entao `repetir` E o certo
    cam.append({
        "tipo": "elipse", "raio": 1.6, "cor": TEXTO,
        "opacidade": [[0, 0.0, "outCubic"], [0.6, 0.07]],
        "repetir": {"cols": 25, "linhas": 15, "espX": 80, "espY": 80,
                    "atraso": 0.004, "ordem": "centro"}})

    # duas estrelas de 4 pontas dentro do canvas (:359-389)
    for i, (dx, dy, r, cor, vel) in enumerate([
            (-700, -380, 13, MARCA, 1.0), (640, 330, 9, CIANO, 1.4)]):
        cam.append({
            "tipo": "path", "d": _estrela_d(r), "contorno": cor,
            "contorno_larg": 0.8,
            "rotacao": [[0, 0.0, "linear"], [DUR, 250 * vel]],
            "opacidade": pulso(0.30, 0.14, 0.03, 700 + i),
            **_na_tela(dx, dy, 0.2 + i * BLOCO)})

    # ══ 2. ARESTAS (:281-319) — bezier com o controle no meio do vao ════
    # Escritas em coordenada de canvas absoluta, com `centrar: false`; a camada
    # inteira senta no ponto (0,0) do canvas. Dentro de `path`, y DESCE — que e
    # exatamente a convencao em que o .tsx ja escreve.
    ARESTAS = [
        # (x1, y1, x2, y2, t_ini, t_fim, cor do brilho, semente)
        (-220, -150, -70, -40, 52 * F, 66 * F, MARCA, 51),
        (-220, -150, -70, -420, 72 * F, 85 * F, MARCA, 52),
        (230, -40, 380, -160, 92 * F, 106 * F, CIANO, 53),
    ]
    for x1, y1, x2, y2, ta, tb, gcor, sem in ARESTAS:
        mx = (x1 + x2) / 2.0
        d = "M %g %g C %g %g %g %g %g %g" % (x1, y1, mx, y1, mx, y2, x2, y2)
        base = _na_tela(0, 0)
        # halo (:63-73): mesma curva, pena +8, alpha 0.12
        cam.append({"tipo": "path", "d": d, "centrar": False,
                    "contorno": gcor, "contorno_larg": 10, "blur": 7,
                    "opacidade": 0.14, "inicio": ta - 2 * F,
                    "traco": [[ta, 0.0, "outCubic"], [tb, 1.0]], **base})
        # traco principal
        cam.append({"tipo": "path", "d": d, "centrar": False,
                    "contorno": FIO, "contorno_larg": 2,
                    "inicio": ta - 2 * F,
                    "traco": [[ta, 0.0, "outCubic"], [tb, 1.0]], **base})

    # ══ 3. OS QUATRO NOS ════════════════════════════════════════════════
    for n in NOS:
        dx, dy, w, h, cor = n["dx"], n["dy"], n["w"], n["h"], n["cor"]
        t, ehllm = n["t"], n["chave"] == "llm1"
        # FlowNode.tsx:83 — a caixa da imagem e `height - 150`; a do LLM cresce
        # com o texto (minHeight), entao ela ocupa o corpo inteiro do card
        alt_img = (h - 70) if ehllm else (h - 150)
        y_area = -h / 2 + 46 + 12 + alt_img / 2
        larg_area = w - 24
        op = entra(t, 0.32)
        mola = {"mola": MOLA_ESTADO, "em": t, "de": 0.70, "para": 1.0}

        def tela(ox, oy, _t=t, _dx=dx, _dy=dy):
            return _na_tela(_dx + ox, _dy + oy, _t, 22.0)

        def base(ox, oy, extra=None, _op=None):
            c = {"opacidade": _op if _op is not None else op,
                 "escalaX": mola, "escalaY": mola, "inicio": t - 0.05}
            c.update(tela(ox, oy))
            if extra:
                c.update(extra)
            return c

        # o card — helper `card()` da base, com a posicao trocada pela camera
        # e a mola realocada para escalaX/escalaY (escala e da camera)
        cartao = card(0, 0, w, h, t, cor=CARD_BG, borda=CARD_BORDA, raio=16,
                      s=n["s"])
        cartao.pop("escala", None)
        cartao.update(base(0, 0))
        cam.append(cartao)

        # borda de selecao 2px (:99-101) — anel: sem `cor`, so contorno
        cam.append(base(0, 0, {"tipo": "retangulo", "larg": w + 4, "alt": h + 4,
                               "raio": 18, "contorno": cor + "CC",
                               "contorno_larg": 2}, _op=_sel(n)))

        # cabecalho de 46px: fio divisor, ponto do tipo, rotulo, pilula do modelo
        cam.append(base(0, -h / 2 + 46,
                        {"tipo": "retangulo", "larg": w, "alt": 1,
                         "cor": DIVISOR}))
        cam.append(base(-w / 2 + 19, -h / 2 + 23,
                        {"tipo": "elipse", "raio": 5, "cor": cor}))
        lw = larg_texto(n["rot"], 13)
        cam.append(base(-w / 2 + 32 + lw / 2, -h / 2 + 23,
                        {"tipo": "texto", "texto": n["rot"], "tamanho": 13,
                         "peso": 600, "cor": LABEL_TXT, "espacamento": 0.3}))
        pw = larg_texto(n["modelo"], 11) + 22
        cam.append(base(w / 2 - 14 - pw / 2, -h / 2 + 23,
                        {"tipo": "retangulo", "larg": pw, "alt": 20, "raio": 100,
                         "cor": "#FFFFFF0F", "contorno": "#FFFFFF1A",
                         "contorno_larg": 1}))
        cam.append(base(w / 2 - 14 - pw / 2, -h / 2 + 23,
                        {"tipo": "texto", "texto": n["modelo"], "tamanho": 11,
                         "peso": 600, "cor": PILL_TXT, "espacamento": 0.4}))

        # a area de resultado (imagem/video) ou a caixa de texto do LLM
        cam.append(base(0, y_area,
                        {"tipo": "retangulo", "larg": larg_area, "alt": alt_img,
                         "raio": 10, "cor": AREA_BG, "contorno": "#FFFFFF0A",
                         "contorno_larg": 1}))

        # punhos esquerdo e direito (:394-430) — o esquerdo e onde a aresta chega
        cam.append(base(-w / 2, 0, {"tipo": "elipse", "raio": 6,
                                    "cor": "#1A1A1A", "contorno": "#FFFFFF26",
                                    "contorno_larg": 2.5}))
        if not ehllm:
            cam.append(base(w / 2, 0, {"tipo": "elipse", "raio": 6,
                                       "cor": "#1A1A1A", "contorno": cor + "66",
                                       "contorno_larg": 2.5}))

        # ── conteudo especifico ────────────────────────────────────────
        if n["chave"] == "img1":
            # resultado: revelacao nos frames 46-56 (:115)
            cam.append(base(0, y_area, {
                "tipo": "imagem", "src": asset("surrealist-concept_800w.jpg"),
                "larg": larg_area - 2, "alt": alt_img - 2, "ajuste": "cobrir",
                "tingir": "#A87BE8"},
                _op=[[46 * F, 0.0, "outCubic"], [56 * F, 1.0]]))
            # scan line varrendo 0->100% nos frames 40-53 (:120-123)
            cam.append({
                "tipo": "retangulo", "larg": 4, "alt": alt_img - 4, "cor": cor,
                "blur": 9, "opacidade": 0.95,
                "inicio": 40 * F, "fim": 53.5 * F,
                **_varre(dx - larg_area / 2, dx + larg_area / 2, dy + y_area,
                         40 * F, 53 * F, _ioq)})
            cam.append(base(0, y_area, {
                "tipo": "retangulo", "larg": 118, "alt": 24, "raio": 6,
                "cor": "#000000A6", "inicio": 40 * F, "fim": 53.5 * F},
                _op=1.0))
            cam.append(base(0, y_area, {
                "tipo": "texto", "texto": "GENERATING", "tamanho": 11,
                "peso": 700, "espacamento": 2.0, "cor": cor,
                "inicio": 40 * F, "fim": 53.5 * F}, _op=1.0))
            # prompt datilografado nos frames 28-48 (:109)
            frase = '"Make it anime style"'
            y_p = -h / 2 + 46 + 12 + alt_img + 10 + 17
            cam.append(base(0, y_p, {"tipo": "retangulo", "larg": larg_area,
                                     "alt": 34, "raio": 8, "cor": PROMPT_BG,
                                     "contorno": PROMPT_BORDA,
                                     "contorno_larg": 1}))
            fw = larg_texto(frase, 12)
            cam.append(base(-larg_area / 2 + 12 + fw / 2, y_p, {
                "tipo": "texto", "texto": frase, "tamanho": 12, "peso": 400,
                "italico": True, "cor": PROMPT_TXT,
                "revelar": _maquina(frase, 12, 28 * F, 48 * F)}))
            # o cursor que corre junto com a cortina
            cam.append({
                "tipo": "retangulo", "larg": 1.6, "alt": 15, "cor": "#FFFFFF55",
                "opacidade": [[28 * F, 0.0, "outCubic"], [29 * F, 0.9],
                              [48 * F, 0.9], [50 * F, 0.0]],
                "inicio": 27 * F, "fim": 51 * F,
                **_varre(dx - larg_area / 2 + 12 + fw * 0.06,
                         dx - larg_area / 2 + 12 + fw * 1.02, dy + y_p,
                         28 * F, 48 * F)})

        elif n["chave"] == "vid1":
            cam.append(base(0, y_area, {
                "tipo": "imagem", "src": asset("character-performance_800w.jpg"),
                "larg": larg_area - 2, "alt": alt_img - 2, "ajuste": "cobrir",
                "tingir": "#4EA8D6"},
                _op=[[66 * F, 0.0, "outCubic"], [76 * F, 1.0]]))
            # botao de play (:180-210)
            cam.append(base(0, y_area, {
                "tipo": "elipse", "raio": 25, "cor": "#0000008C",
                "contorno": "#FFFFFF40", "contorno_larg": 2},
                _op=[[66 * F, 0.0, "outCubic"], [76 * F, 1.0]]))
            cam.append(base(2, y_area, {
                "tipo": "path", "d": "M -8 -10 L 12 0 L -8 10 Z", "cor": TEXTO},
                _op=[[66 * F, 0.0, "outCubic"], [76 * F, 1.0]]))
            frase = '"Gentle wind moving the flowers"'
            y_p = -h / 2 + 46 + 12 + alt_img + 10 + 17
            cam.append(base(0, y_p, {"tipo": "retangulo", "larg": larg_area,
                                     "alt": 34, "raio": 8, "cor": PROMPT_BG,
                                     "contorno": PROMPT_BORDA,
                                     "contorno_larg": 1}))
            fw = larg_texto(frase, 12)
            cam.append(base(-larg_area / 2 + 12 + fw / 2, y_p, {
                "tipo": "texto", "texto": frase, "tamanho": 12, "peso": 400,
                "italico": True, "cor": PROMPT_TXT,
                "revelar": _maquina(frase, 12, 58 * F, 73 * F)}))

        elif n["chave"] == "img2":
            cam.append(base(0, y_area, {
                "tipo": "imagem", "src": asset("ugc-product-story_800w.jpg"),
                "larg": larg_area - 2, "alt": alt_img - 2, "ajuste": "cobrir",
                "tingir": "#F0A03C"},
                _op=[[86 * F, 0.0, "outCubic"], [96 * F, 1.0]]))
            frase = '"Add fantasy lighting"'
            y_p = -h / 2 + 46 + 12 + alt_img + 10 + 17
            cam.append(base(0, y_p, {"tipo": "retangulo", "larg": larg_area,
                                     "alt": 34, "raio": 8, "cor": PROMPT_BG,
                                     "contorno": PROMPT_BORDA,
                                     "contorno_larg": 1}))
            fw = larg_texto(frase, 12)
            cam.append(base(-larg_area / 2 + 12 + fw / 2, y_p, {
                "tipo": "texto", "texto": frase, "tamanho": 12, "peso": 400,
                "italico": True, "cor": PROMPT_TXT,
                "revelar": _maquina(frase, 12, 78 * F, 90 * F)}))

        else:
            # LLM_TEXT (:54) quebrado nas tres linhas que cabem na caixa; cada
            # uma tem a sua janela dentro dos frames 102-135 (:112), na
            # proporcao do numero de caracteres — e o mesmo ritmo de digitacao.
            linhas = ["Summary: cinematic flower field,",
                      "soft breeze, warm golden glow.",
                      "Ready for post-production assembly."]
            tot = sum(len(s) for s in linhas)
            ta = 102 * F
            for i, s in enumerate(linhas):
                tb = ta + (135 - 102) * F * len(s) / tot
                lw2 = larg_texto(s, 12)
                cam.append(base(-larg_area / 2 + 14 + lw2 / 2,
                                y_area - alt_img / 2 + 24 + i * 21, {
                    "tipo": "texto", "texto": s, "tamanho": 12, "peso": 400,
                    "cor": "#FFFFFFB3", "espacamento": 0.2,
                    "revelar": _maquina(s, 12, ta, tb)}))
                ta = tb

    # ══ 4. PONTOS DE CHEGADA das arestas (:322-356) — por cima dos punhos ═
    for i, (_, _, x2, y2, ta, tb, gcor, sem) in enumerate(ARESTAS):
        cam.append({"tipo": "elipse", "raio": 4.5, "cor": gcor,
                    "blur": 3, "inicio": tb,
                    "opacidade": pulso(0.62, 0.30, 0.03, sem),
                    **_na_tela(x2, y2, tb)})

    # ══ 5. TITULO (:565-612) — canto inferior esquerdo, sobre tudo ══════
    esq = -960 + 75
    cam.append(rotulo("NODE-BASED", 115 * F, -384,
                      cor=MUDO, tam=20, esp=5,
                      x=esq + (larg_texto("NODE-BASED", 20) + 10 * 5) / 2,
                      peso=400))
    x_pal = esq
    for i, (pal, cor_p) in enumerate([("Creative", MARCA), ("Pipeline", CIANO)]):
        pw2 = larg_texto(pal, 68) - 2 * len(pal)
        t_p = 125 * F + i * PALAVRA
        # UM destaque por cena: a palavra que fecha o titulo
        m = MOLA_DESTAQUE if i == 1 else MOLA_TEXTO
        cam.append({
            "tipo": "texto", "texto": pal, "tamanho": 68, "peso": 900,
            "cor": cor_p, "espacamento": -2,
            "x": {"ruido": {"escala": 0.008, "amp": 2.0,
                            "base": x_pal + pw2 / 2, "semente": 610 + i}},
            "y": sobe(t_p, -436, 30, 0.45),
            "opacidade": entra(t_p, 0.3),
            "escala": {"mola": m, "em": t_p, "de": 0.88, "para": 1.0}})
        x_pal += pw2 + 12

    # ══ 6. BARRA DE ESTADO (:950-980) — entra no frame 92, quando a conta
    #        de nos e arestas ja e a final ═══════════════════════════════
    est = "4 nodes  ·  3 edges  ·  GPU: 87%"
    cam.append({"tipo": "retangulo", "larg": larg_texto(est, 11) + 34,
                "alt": 26, "raio": 8, "cor": "#0A0A0C80",
                "contorno": "#FFFFFF0D", "contorno_larg": 1,
                "opacidade": [[92 * F, 0.0, "outCubic"], [102 * F, 1.0]],
                **viva(0, -501, 2, 88)})
    cam.append({"tipo": "texto", "texto": est, "tamanho": 11, "peso": 500,
                "cor": "#FFFFFF4D", "espacamento": 0.5,
                "opacidade": [[92 * F, 0.0, "outCubic"], [102 * F, 1.0]],
                **viva(0, -501, 2, 88)})

    # ══ 7. TOAST "Generation Complete" (:867-926) — frames 56 a 92 ══════
    t_toast = 56 * F
    op_toast = [[t_toast, 0.0, "outCubic"], [t_toast + 0.30, 1.0],
                [82 * F, 1.0], [90 * F, 0.0]]
    esc_toast = {"mola": MOLA_ESTADO, "em": t_toast, "de": 0.88, "para": 1.0}
    tx, ty = 825.0, 488.0
    cam.append({"tipo": "retangulo", "larg": 210, "alt": 56, "raio": 14,
                "cor": "#0A0A0CD9", "contorno": "#FFFFFF14",
                "contorno_larg": 1, "opacidade": op_toast,
                "escala": esc_toast, "inicio": t_toast, "fim": 91 * F,
                **viva(tx, ty, 2.5, 71)})
    cam.append({"tipo": "elipse", "raio": 12, "cor": "#10B98122",
                "contorno": "#10B98166", "contorno_larg": 1,
                "opacidade": op_toast, "escala": esc_toast,
                "inicio": t_toast, "fim": 91 * F, **viva(tx - 77, ty, 2.5, 72)})
    cam.append({"tipo": "path", "d": "M -5 0 L -1.5 3.5 L 5 -3.5",
                "contorno": SUCESSO, "contorno_larg": 2,
                "opacidade": op_toast, "escala": esc_toast,
                "inicio": t_toast, "fim": 91 * F, **viva(tx - 77, ty, 2.5, 73)})
    for i, (s, tam, cor_s, dyy) in enumerate([
            ("Generation Complete", 12, "#FFFFFFBF", 9),
            ("Image Node 1 ready", 11, "#FFFFFF4D", -9)]):
        cam.append({"tipo": "texto", "texto": s, "tamanho": tam,
                    "peso": 600 if i == 0 else 400, "cor": cor_s,
                    "opacidade": op_toast, "escala": esc_toast,
                    "inicio": t_toast, "fim": 91 * F,
                    **viva(tx - 55 + larg_texto(s, tam) / 2, ty + dyy, 2.5,
                           74 + i)})

    return {"duracao": dur, "fundo": BG, "camadas": cam}
