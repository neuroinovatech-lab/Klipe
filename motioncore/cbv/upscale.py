# -*- coding: utf-8 -*-
"""upscale.py — a cena Upscaling do CreativlyBrandVideo.

Uma linha de varredura atravessa a foto da esquerda para a direita e troca o
lado borrado pelo lado nitido (`UpscalingScene.tsx:63-67` — frames 15..85,
inOut(quad)); o grid de pixel do lado "antes" apaga junto (:78-83), o contador
sobe de 100% a 800% (:86-91) e o "8K" entra de mola aos 40 frames (:110-116)
enquanto o "HD" apaga (:119-122). A varredura e um `revelar` de cortina, o
contador virou 9 camadas de texto se revezando (o motor nao tem texto dinamico)
e o blur da foto virou borrao por acumulo de copias deslocadas.
"""
from .base import *

import math

FOTO = asset("character-performance_800w.jpg")

# ── o varrimento (:63-67): frames 15..85, inOut(quad), 0 -> 100% ──────────
T0, T1 = 15 / FPS, 85 / FPS

# mistura do degrade 135deg #3B82F6 -> #06B6D4 no meio do caminho: o motor
# desenha texto com UMA cor, entao numero pequeno usa a media e so o "8K" e o
# "UPSCALE" ganham as copias cortadas que fingem o degrade
AZUL_CIANO = "#209CE5"
GRID_COR = "#00000030"           # :226-227 e rgba(0,0,0,0.08) — subi para o
                                 # tracinho de 1px sobreviver ao h.264


def _varre(a: float, b: float) -> list:
    """Keyframes que seguem a curva do scan. Easing no PRIMEIRO keyframe:
    no ultimo o motor ignora (armadilha 6)."""
    return [[T0, a, "inOutQuad"], [T1, b]]


def _quando(s: float) -> float:
    """Em que segundo o scan chega na fracao `s` — inverso do inOutQuad.
    Serve para o `inicio` das faiscas do lado ja tratado (:351)."""
    p = math.sqrt(s / 2) if s < 0.5 else 1 - math.sqrt(max(0.0, 1 - s) / 2)
    return T0 + p * (T1 - T0)


def _corte(x: float) -> float:
    """`revelar` dir='dir' recorta uma janela de max(W,H) ancorada na borda
    direita. Isto devolve o `prog` que poe a borda do corte em `x` local."""
    return (W / 2 - x) / max(W, H)


def _mul(op, k: float):
    """Multiplica uma opacidade (constante ou keyframes) por um fator."""
    if isinstance(op, list):
        return [[q[0], q[1] * k] + list(q[2:]) for q in op]
    return op * k


def _degrade(base: dict, larg: float, n: int = 2) -> list[dict]:
    """Finge o `linear-gradient(135deg, #3B82F6, #06B6D4)` de texto (:172,413):
    o azul inteiro embaixo e N copias cianas cortadas cada vez mais a direita.
    Sao faixas, nao rampa — mas a 240px de fonte o olho le degrade."""
    out = [base]
    for k in range(n):
        c = dict(base)
        c["cor"] = CIANO
        c["opacidade"] = _mul(base.get("opacidade", 1.0), 0.34 + k * 0.22)
        c["revelar"] = {"prog": _corte(-larg / 2 + larg * (k + 1) / (n + 1)),
                        "dir": "dir"}
        out.append(c)
    return out


def _amostrar(f, t0: float, t1: float, passo: float = 0.2) -> list:
    """Curva continua virada keyframe. O ultimo sai SEM easing de proposito."""
    ks, t = [], t0
    while t < t1 - 1e-6:
        ks.append([round(t, 4), round(f(t), 4), "linear"])
        t += passo
    ks.append([round(t1, 4), round(f(t1), 4)])
    return ks


def _estrela(ro: float, pontas: int = 4, fator: float = 0.3) -> str:
    """makeStar({points:4, innerRadius: size*0.3, outerRadius: size}) (:307-311)."""
    ri = ro * fator
    p = []
    for k in range(pontas * 2):
        r = ro if k % 2 == 0 else ri
        a = -math.pi / 2 + k * math.pi / pontas
        p.append(f"{r * math.cos(a):.2f} {r * math.sin(a):.2f}")
    return "M " + " L ".join(p) + " Z"


def _pct(f: float) -> int:
    """:86-91 — interpolate(frame,[20,80],[1,8],out(cubic)), depois *100."""
    p = min(1.0, max(0.0, (f - 20) / 60))
    return int((1 + 7 * (1 - (1 - p) ** 3)) * 100)


# posicoes medidas do flex: faixa de 80% (1536px) com space-between e baseline
X_HD, Y_HD = -698.0, 129.0          # :394-405 — 100px, mudo
X_8K, Y_8K = 553.0, 180.0           # :408-427 — 240px, italico, degrade
Y_BADGE = -68.0                     # :440-470 — pilula branca, borda 3px
Y_FINO = -155.0                     # :473-488 — "pixel perfect"
Y_NUM = -243.0                      # :505-523 — o contador
Y_ROT = -307.0                      # :526-539 — "Enhancement"
L_BADGE, A_BADGE = 474.0, 124.0

# :49-56 — os seis diamantes, ja convertidos de canto/topo para centro do quadro
DIAMANTES = [
    (-860.0, 400.0, 40, 0.8, 5 / FPS),
    (847.5, 312.5, 55, 1.2, 12 / FPS),
    (-792.5, -327.5, 35, 0.6, 20 / FPS),
    (764.0, -264.0, 48, 1.0, 8 / FPS),
    (15.0, 465.0, 30, 1.4, 25 / FPS),
    (909.0, 21.0, 38, 0.9, 18 / FPS),
]


def cena(dur: float) -> dict:
    c: list[dict] = []

    # ── o "antes": a foto inteira, borrada (:209-218) ─────────────────────
    # o motor nao borra imagem, entao o blur(10px) e feito por acumulo: cinco
    # copias deslocadas por cima da base, cada uma a 40%
    c.append({"tipo": "imagem", "src": FOTO, "larg": "110%", "alt": "110%",
              "ajuste": "cobrir", "opacidade": [[0, 0], [0.3, 1]]})
    # o borrao so precisa existir do lado que o scan ainda nao tratou: alem de
    # ser o certo, o recorte corta pela metade o custo (o Skia paga por pixel
    # de destino, e uma foto de 800px esticada a 2112 e o item caro da cena)
    for dx, dy, op in ((9, 0, 0.42), (-9, 0, 0.42), (0, 9, 0.38),
                       (0, -9, 0.38), (14, 13, 0.30)):
        c.append({"tipo": "imagem", "src": FOTO, "larg": "112%", "alt": "112%",
                  "ajuste": "cobrir", "x": dx, "y": dy,
                  "revelar": {"prog": [[T0, 1, "inOutQuad"], [T1, 0]],
                              "dir": "dir"},
                  "opacidade": [[0, 0], [0.3, op]]})

    # ── grade de pixel de 20px sobre o lado ainda cru (:221-233) ──────────
    # `repetir` aqui e o uso certo: e textura. Mas o recorte tem de ficar num
    # GRUPO — em camada com `repetir` o clip seria refeito em volta de CADA
    # copia, e nenhuma linha seria cortada (armadilha 3).
    op_grade = [[0, 0.5, "linear"], [T0, 0.5, "inOutQuad"], [1.543, 0.05]]
    c.append({"tipo": "grupo", "revelar": {"prog": [[T0, 1, "inOutQuad"],
                                                    [T1, 0]], "dir": "dir"},
              "camadas": [
                  {"tipo": "retangulo", "larg": 1, "alt": H, "cor": GRID_COR,
                   "opacidade": op_grade,
                   "repetir": {"cols": W // 20 + 1, "linhas": 1, "espX": 20,
                               "espY": 0, "atraso": 0.002, "ordem": "linha"}},
                  {"tipo": "retangulo", "larg": W, "alt": 1, "cor": GRID_COR,
                   "opacidade": op_grade,
                   "repetir": {"cols": 1, "linhas": H // 20 + 1, "espX": 0,
                               "espY": 20, "atraso": 0.002, "ordem": "linha"}}]})

    # ── o "depois": a mesma foto, limpa, entrando por cortina (:236-257) ──
    # o zoom de 1.1 esta na CAIXA (larg/alt), nao em `escala`: `revelar`
    # recorta depois do transform, e escalar moveria a linha do corte junto
    c.append({"tipo": "imagem", "src": FOTO, "larg": "110%", "alt": "110%",
              "ajuste": "cobrir",
              "revelar": {"prog": [[T0, 0, "inOutQuad"], [T1, 1]], "dir": "esq"}})

    # ── marca d'agua "UPSCALE", 350px, italica, 0.04 (:158-187) ───────────
    wm = marca_dagua("UPSCALE", 350, MARCA, 0.0, 0.05, 0.0)
    wm["espacamento"] = -8
    wm["escala"] = {"mola": {"damping": 20, "stiffness": 40, "mass": 1.2},
                    "em": 5 / FPS, "de": 0.85, "para": 1.0}
    c += _degrade(wm, larg_texto("UPSCALE", 350), 1)

    # ── os seis diamantes 3D (:190-203) ───────────────────────────────────
    # rotateX/rotateY viram achatamento: escalaX = |cos(rotY)|, escalaY =
    # |cos(rotX)|, que e a silhueta que o quadrado em perspectiva desenha
    for i, (x, y, tam, vel, t) in enumerate(DIAMANTES):
        c.append(brilho(x, y, tam * 2.2, MARCA, t, 0.22, 40 + i))
    for i, (x, y, tam, vel, t) in enumerate(DIAMANTES):
        c.append({
            "tipo": "retangulo", "larg": tam, "alt": tam, "rotacao": 45,
            "cor": "#FFD600" + ("26", "3B", "4F")[i % 3],
            "contorno": MARCA + "55", "contorno_larg": 1,
            **viva(x, y, 10, 60 + i),
            "opacidade": _mul(entra(t, 0.5), 0.8),
            "escala": {"mola": {"damping": 16, "stiffness": 80}, "em": t,
                       "de": 0.0, "para": 1.0},
            "escalaX": _amostrar(
                lambda s, v=vel: max(0.12, abs(math.cos(math.radians(
                    s * FPS * 2 * v)))), 0.0, dur),
            "escalaY": _amostrar(
                lambda s, v=vel: max(0.12, abs(math.cos(math.radians(
                    s * FPS * 1.5 * v)))), 0.0, dur)})

    # ── o facho largo atras da linha (:272-282) ───────────────────────────
    # a cor do original desliza brand -> ciano -> brand nos frames 15/50/85
    # (:94-98); sem cor animavel, sao duas copias cruzando por opacidade
    op_ciano = [[T0, 0], [50 / FPS, 1], [T1, 0]]
    for cor, op in ((MARCA, 1.0), (CIANO, op_ciano)):
        c.append({"tipo": "retangulo", "larg": 66, "alt": H, "blur": 12,
                  "x": _varre(-W / 2, W / 2), "inicio": 8 / FPS,
                  "opacidade": op,
                  "cor": {"tipo": "linear", "de": [-33, 0], "para": [33, 0],
                          "cores": [cor + "00", cor + "33", cor + "99",
                                    cor + "33", cor + "00"],
                          "paradas": [0.0, 0.25, 0.5, 0.75, 1.0]}})

    # ── a linha, desenhada de cima para baixo entre os frames 10 e 30 ─────
    # (:70-75, evolvePath). `revelar` cima recorta uma janela de max(W,H): os
    # limites 0.21875/0.78125 mapeiam esse corte nos 1080px do quadro
    for cor, op in ((MARCA, 1.0), (CIANO, op_ciano)):
        c.append({"tipo": "retangulo", "larg": pulso(6, 2, 0.035, 11),
                  "alt": H, "raio": 3, "cor": cor, "inicio": 8 / FPS,
                  "x": _varre(-W / 2, W / 2), "opacidade": op,
                  "revelar": {"prog": [[10 / FPS, 0.21875, "outCubic"],
                                       [30 / FPS, 0.78125]], "dir": "cima"}})

    # ── 18 estrelas de 4 pontas na beira do corte (:305-338) ──────────────
    for i in range(18):
        yp = ((i * 0.618034) % 1.0) * 100
        tam = 3 + ((i * 0.381966) % 1.0) * 6
        ox = (((i * 0.754878) % 1.0) - 0.5) * 40
        vel = 0.15 + ((i * 0.274997) % 1.0) * 0.3
        ro = tam * 1.5                      # svg 3*size num viewBox de 2*size
        c.append({
            "tipo": "path", "d": _estrela(ro), "cor": TEXTO,
            "inicio": 12 / FPS,
            "x": _varre(-W / 2 + ox, W / 2 + ox),
            "y": {"ruido": {"escala": 0.02, "amp": 10,
                            "base": H / 2 - yp * (H / 100), "semente": 400 + i}},
            "rotacao": [[0, 0, "linear"], [dur, dur * FPS * vel * 3]],
            "opacidade": pulso(0.45, 0.35, 0.05 + (i % 4) * 0.015, 700 + i),
            "escala": {"mola": MOLA_TEXTO, "em": 0.4 + i * 0.012,
                       "de": 0.0, "para": 1.0}})

    # ── 10 faiscas de ambiente, so depois que o scan passa por elas ───────
    # (:342-374) — `isVisible = s.xPct < scan` vira `inicio`, que e o unico
    # jeito de casar aparicao com ruido continuo na mesma camada
    for i in range(10):
        xp = ((i * 0.618034) % 1.0) * 45
        yp = ((i * 0.414214) % 1.0) * 100
        tam = 2 + ((i * 0.274997) % 1.0) * 4
        vel = 0.1 + ((i * 0.381966) % 1.0) * 0.2
        c.append({
            "tipo": "path", "d": _estrela(tam * 1.5, 4, 0.25), "cor": MARCA,
            "inicio": max(20 / FPS, _quando(xp / 100)),
            **viva(-W / 2 + xp * (W / 100), H / 2 - yp * (H / 100), 6, 80 + i),
            "rotacao": [[0, i * 45, "linear"], [dur, i * 45 + dur * FPS * vel * 4]],
            "opacidade": pulso(0.24, 0.16, 0.05 + (i % 3) * 0.02, 820 + i)})

    # ── "HD": pequeno, mudo, apagando conforme o scan avanca (:394-405) ───
    c.append({"tipo": "texto", "texto": "HD", "tamanho": 100, "peso": 900,
              "cor": MUDO, "espacamento": 2,
              "sombra": [{"x": 0, "y": 4, "blur": 20, "cor": "#00000033"}],
              **viva(X_HD, Y_HD, 2, 31),
              "opacidade": [[0, 0.5, "linear"], [T0, 0.5, "inOutQuad"],
                            [1.79, 0.08]]})

    # ── "8K": o destaque da cena — 240px, italico, degrade, brilho ────────
    t8 = 40 / FPS
    c.append(brilho(X_8K, Y_8K, 400, MARCA, t8, 0.30, 7))
    c.append(brilho(X_8K, Y_8K, 210, MARCA_CLARA, t8, 0.26, 8))
    oito = {"tipo": "texto", "texto": "8K", "tamanho": 240, "peso": 900,
            "italico": True, "cor": MARCA, "espacamento": -6,
            **viva(X_8K, Y_8K, 2, 77), "opacidade": entra(t8, 0.3),
            "escala": {"mola": MOLA_DESTAQUE, "em": t8, "de": 0.3, "para": 1.0}}
    c += _degrade(oito, larg_texto("8K", 240) - 12, 3)

    # ── a pilula "AI Upscaling" (:431-470) ────────────────────────────────
    tb = 10 / FPS
    c += sombra(0, Y_BADGE, L_BADGE, A_BADGE, tb, 100, 2)
    mola_b = {"mola": MOLA_TEXTO, "em": tb, "de": 0.6, "para": 1.0}
    # blur(12px)->0 nao e animavel (armadilha 4): sao duas copias cruzando
    c.append({"tipo": "retangulo", "larg": L_BADGE, "alt": A_BADGE, "raio": 100,
              "cor": "#FFFFFFEB", "contorno": MARCA, "contorno_larg": 3,
              "blur": 12, "x": 0, "y": Y_BADGE, "escala": mola_b,
              "opacidade": [[tb, 0], [0.5, 0.8], [0.95, 0]]})
    c.append({"tipo": "retangulo", "larg": L_BADGE, "alt": A_BADGE, "raio": 100,
              "cor": "#FFFFFFEB", "contorno": MARCA, "contorno_larg": 3,
              **viva(0, Y_BADGE, 2, 21), "escala": mola_b,
              "opacidade": [[tb, 0], [0.62, 1]]})
    # SplitText por PALAVRA (:463-469, stagger 2) e, por dentro, por LETRA
    c += titulo("AI", 0.4, Y_BADGE, 52, TEXTO_PRETO, 900, LETRA, -128.5)
    c += titulo("Upscaling", 0.4 + PALAVRA, Y_BADGE, 52, TEXTO_PRETO, 900,
                LETRA, 33.2)

    fino = rotulo("PIXEL PERFECT", 22 / FPS, Y_FINO, MUDO_ESCURO, 18, 0.0, 4, 700)
    fino["italico"] = True
    fino["opacidade"] = [[22 / FPS, 0], [1.03, 0.7]]
    c.append(fino)

    # ── o contador 100% -> 800% (:493-523) ────────────────────────────────
    # texto e fixo no motor: cada valor amostrado e uma camada com janela de
    # opacidade. Corte seco, sem cross-fade — contador que dissolve vira borrao
    quadros = [30, 40, 46, 52, 58, 64, 70, 76, 82]
    for k, f in enumerate(quadros):
        ta = f / FPS
        tf = quadros[k + 1] / FPS if k + 1 < len(quadros) else max(dur, ta + 1)
        op = ([[ta, 0], [ta + 0.25, 1], [tf - 0.02, 1], [tf, 0]] if k == 0
              else [[ta - 0.02, 0], [ta, 1], [tf - 0.02, 1], [tf, 0]]
              if k + 1 < len(quadros) else [[ta - 0.02, 0], [ta, 1]])
        c.append({"tipo": "texto", "texto": f"{_pct(f)}%", "tamanho": 72,
                  "peso": 900, "italico": True, "cor": AZUL_CIANO,
                  "sombra": [{"x": 0, "y": 0, "blur": 15, "cor": MARCA + "44"}],
                  "x": 0, "opacidade": op,
                  "y": sobe(1.0, Y_NUM, 20) if k == 0 else Y_NUM})

    rot = rotulo("ENHANCEMENT", 1.0, Y_ROT, MUDO_ESCURO, 22, 0.0, 3, 700)
    rot["opacidade"] = [[1.0, 0], [1.3, 0.7]]
    c.append(rot)

    return {"duracao": dur, "fundo": BG_BRANCO, "camadas": c}
