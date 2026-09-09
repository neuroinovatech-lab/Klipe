# -*- coding: utf-8 -*-
"""inpaint.py — a cena Inpainting do CreativlyBrandVideo.

Coluna de texto a esquerda ("Generative / Fill & Fix" + descricao + tres pilulas)
e, a direita, o painel 1000x700 com `focused-editor.jpg` varrido por uma barra de
luz que vai de ponta a ponta entre os frames 20 e 90 em inOut(quad) (:39-43),
deixando atras de si a regiao "antes" escurecida (:334-342) e arrastando faiscas
em estrela de quatro pontas (:27-32, :359-384). A cor da varredura passa por
success -> brand -> #4ade80 -> success (:55-60): como o motor nao interpola cor,
os tres estados sao camadas cruzando por opacidade nesses mesmos instantes.
"""
from __future__ import annotations

import math

from .base import *

# ── geometria do layout (:82-91) ─────────────────────────────────────────
# flex row, gap 80, centrado: coluna de 600 + 80 + painel de 1000 = 1680,
# sobrando 120 de cada lado. Em coordenadas do motor (origem no centro):
COL_ESQ = -840.0                 # borda esquerda da coluna de texto (tela x=120)
PX, PY = 340.0, 0.0              # centro do painel (tela x=1300, y=540)
PW, PH = 1000.0, 700.0           # :318
PANEL_ESQ, PANEL_DIR = PX - PW / 2, PX + PW / 2

# ── a varredura (:39-43) ─────────────────────────────────────────────────
T_S0, T_S1 = 20 * F, 90 * F      # frames 20 -> 90
T_PAINEL = 5 * F                 # :317 — Sequence from={5}
# easing no PRIMEIRO keyframe: e ele que governa o trecho. No ultimo seria lido
# como nada (armadilha 6).
SCAN_X = [[T_S0, PANEL_ESQ, "inOutQuad"], [T_S1, PANEL_DIR]]

# `revelar` corta a partir de -max(W,H)/2 LOCAL, nao da borda da camada: para a
# cortina bater exatamente nas bordas do painel, o progresso anda entre estes
# dois valores, e nao entre 0 e 1.
_REV0 = (W / 2 - PW / 2) / W
_REV1 = (W / 2 + PW / 2) / W
SCAN_REV = [[T_S0, _REV0, "inOutQuad"], [T_S1, _REV1]]

# O painel do original tem `overflow: hidden` (:322) e e ele que segura o
# boxShadow da barra. Sem clip, o halo vaza por cima da coluna de texto nos
# primeiros 20 frames, quando a barra esta parada na borda esquerda. Como
# `revelar` corta em coordenada LOCAL e a barra anda, o corte tem que andar
# junto: e a mesma curva do `x`, so que afim — por isso os dois nunca se
# soltam um do outro.
SCAN_CLIP = {"prog": [[T_S0, (W / 2 - PANEL_ESQ + PANEL_ESQ) / W, "inOutQuad"],
                      [T_S1, (W / 2 - PANEL_ESQ + PANEL_DIR) / W]],
             "dir": "dir"}

# as quatro paradas de cor de :55-60, viradas em tres camadas que se cruzam
VERDE_CLARO = "#4ade80"
OP_A = [[T_PAINEL, 0], [T_PAINEL + 0.3, 1, "outCubic"], [T_S0, 1],
        [40 * F, 0], [65 * F, 0], [90 * F, 1]]
OP_B = [[T_PAINEL, 0], [T_S0, 0], [40 * F, 1], [65 * F, 0]]
OP_C = [[T_S0, 0], [40 * F, 0], [65 * F, 1], [90 * F, 0]]


def _escalar(kf: list, k: float) -> list:
    """Mesma curva, outra amplitude — os brilhos da barra seguem o mesmo cruzamento."""
    return [[a[0], a[1] * k] + a[2:] for a in kf]


# ── degrade #3B82F6 -> #06B6D4 (:104, :259) ──────────────────────────────
def _grad(f: float) -> str:
    """O motor pinta texto com cor solida. O degrade do original vira uma rampa
    de cores POR LETRA — de perto e o mesmo pixel, de longe e o mesmo degrade."""
    a, b = (0x3B, 0x82, 0xF6), (0x06, 0xB6, 0xD4)
    f = max(0.0, min(1.0, f))
    return "#%02X%02X%02X" % tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(3))


def _rnd(i: int, k: int) -> float:
    """random() do Remotion nao e portavel; isto tem a mesma distribuicao."""
    v = math.sin((i + 1) * 12.9898 + k * 78.233) * 43758.5453
    return v - math.floor(v)


def _estrela(r: float, pontas: int = 4, fr: float = 0.3) -> str:
    """makeStar({points:4, innerRadius: size*0.3}) (:360) em sintaxe SVG."""
    pts = []
    for k in range(pontas * 2):
        ang = math.radians(-90 + k * (180.0 / pontas))
        rr = r if k % 2 == 0 else r * fr
        pts.append(f"{rr * math.cos(ang):.2f} {rr * math.sin(ang):.2f}")
    return "M " + " L ".join(pts) + " Z"


def _flip(gpf: float, dur: float, piso: float = 0.10) -> list:
    """As faces do FloatingDiamond (:230-231): rotX/rotY em graus por frame.

    Em 2D o giro 3D de um plano le como |cos| do angulo. Amostrado de 4 em 4
    frames, com piso para o losango nunca sumir de vez no perfil."""
    kf, f = [], 0
    while f / FPS <= dur + 0.2:
        v = max(piso, abs(math.cos(math.radians(f * gpf))))
        kf.append([round(f / FPS, 3), round(v, 4), "linear"])
        f += 4
    kf[-1] = kf[-1][:2]          # no ultimo keyframe o easing e morto (armadilha 6)
    return kf


def _palavras(txt: str, t0: float, y: float, tam: int, cor: str,
              esq: float, peso: int = 400, passo: float = PALAVRA,
              esp: float = 0.0, italico: bool = False) -> list[dict]:
    """Bloco de texto alinhado a ESQUERDA — `x` e o centro (armadilha 1), entao
    cada palavra e medida e o cursor anda sozinho."""
    out, cx = [], esq
    for i, p in enumerate(txt.split(" ")):
        w = larg_texto(p, tam) + esp * len(p)
        d = t0 + i * passo
        out.append({"tipo": "texto", "texto": p, "tamanho": tam, "peso": peso,
                    "cor": cor, "italico": italico, "espacamento": esp,
                    "x": cx + w / 2, "y": sobe(d, y, 14, 0.42),
                    "opacidade": entra(d, 0.35)})
        cx += w + larg_char(" ", tam)
    return out


# ── a cena ───────────────────────────────────────────────────────────────
FEATS = ["Object Removal", "Style Transfer", "Background Replace"]
DIAMANTES = [
    # (tam, x_css, y_css, alpha, speed, delay_frames, cor_do_brilho) — :122-174
    (45, 80, 120, 0.25, 0.7, 10, MARCA),
    (30, 1750, 80, 0.18, 1.1, 18, MARCA),
    (55, 150, 850, 0.20, 0.5, 5, MARCA_ESCURA),
    (25, 1680, 900, 0.30, 1.3, 22, MARCA),
    (38, 950, 50, 0.15, 0.9, 15, MARCA),
]


def cena(dur: float) -> dict:
    c: list[dict] = []

    # ── luz de fundo ─────────────────────────────────────────────────────
    c.append(brilho(-560, 40, 640, MARCA, 0.0, 0.16, s=3))
    c.append(brilho(PX, PY, 760, CIANO, 0.15, 0.10, s=17))

    # ── marca d'agua "FILL", 450px italica, -12deg (:93-119) ─────────────
    # o original a pinta em degrade; aqui cada letra tem sua parada da rampa,
    # e por isso ela nao pode sair de `marca_dagua` numa camada so.
    _LT = "FILL"
    _ESP = 450 * 0.05                     # letterSpacing 0.05em (:112)
    _lg = [larg_char(ch, 450) for ch in _LT]
    _tot = sum(_lg) + _ESP * (len(_LT) - 1)
    _d = -_tot / 2
    for i, ch in enumerate(_LT):
        m = marca_dagua(ch, 450, _grad(i / (len(_LT) - 1)), -12, 0.05)
        m["espacamento"] = 0
        m["x"] = (_d + _lg[i] / 2) * math.cos(math.radians(12))
        m["y"] = (_d + _lg[i] / 2) * math.sin(math.radians(12))
        # :68-72 — o pulso lento de opacidade, sem fade de entrada (ela ja esta la)
        m["opacidade"] = pulso(0.048, 0.016, 0.004, 40 + i)
        c.append(m)
        _d += _lg[i] + _ESP

    # poeira de fundo — o original nao tem, mas sem ela o preto entre o texto e
    # o painel fica morto no meio de um filme que respira
    c += particulas(6, MARCA, CIANO, amp=22, semente=31)

    # ── os cinco FloatingDiamond (:121-174) ──────────────────────────────
    for i, (tam, xc, yc, al, vel, atr, gcor) in enumerate(DIAMANTES):
        x = xc + tam / 2 - W / 2
        y = H / 2 - (yc + tam / 2)
        t = atr * F
        c.append(brilho(x, y, tam * 2.6, gcor, t, 0.22, s=200 + i))
        c.append({
            "tipo": "retangulo", "larg": tam, "alt": tam, "raio": 2,
            "cor": "#FFD600", "rotacao": 45,
            **viva(x, y, 12, 260 + i),
            "opacidade": [[t, 0], [t + 0.4, al * 0.8, "outCubic"]],
            "escala": {"mola": MOLA_ESTADO, "em": t, "de": 0.0, "para": 1.0},
            "escalaX": _flip(2.0 * vel, dur),      # rotY = frame*2*speed (:231)
            "escalaY": _flip(1.5 * vel, dur),      # rotX = frame*1.5*speed (:230)
        })

    # ── o painel de imagem (:317-342) ────────────────────────────────────
    # sem `sombra()`: o original nao tem box-shadow no painel (so a borda de
    # 1px), e a caixa preta borrada da sombra recortava um retangulo escuro
    # visivel por cima do brilho de fundo. O painel se separa pelo brilho.
    c.append({
        "tipo": "imagem", "src": asset("focused-editor.jpg"),
        "larg": PW, "alt": PH, "ajuste": "cobrir",
        **viva(PX, PY, 2.0, 71),
        "opacidade": entra(T_PAINEL, 0.32),
        # o UNICO destaque da cena: o painel e o assunto
        "escala": {"mola": MOLA_DESTAQUE, "em": T_PAINEL, "de": 0.93, "para": 1.0},
    })
    # a regiao "antes" (:334-342): a cortina anda junto com a barra
    c.append({
        "tipo": "imagem", "src": asset("focused-editor.jpg"),
        "larg": PW, "alt": PH, "ajuste": "cobrir", "tingir": "#6E7480",
        **viva(PX, PY, 2.0, 71),
        "opacidade": entra(T_PAINEL, 0.32),
        "escala": {"mola": MOLA_DESTAQUE, "em": T_PAINEL, "de": 0.93, "para": 1.0},
        "revelar": {"prog": SCAN_REV, "dir": "esq"},
    })
    # borda 1px (:326) — anel: preenchimento transparente + contorno (armadilha 2)
    c.append({
        "tipo": "retangulo", "larg": PW, "alt": PH, "raio": 20,
        "cor": "#00000000", "contorno": BORDA_CLARA, "contorno_larg": 1.5,
        **viva(PX, PY, 2.0, 71), "opacidade": entra(T_PAINEL, 0.32),
        "escala": {"mola": MOLA_DESTAQUE, "em": T_PAINEL, "de": 0.93, "para": 1.0},
    })

    # ── a barra de varredura e seus brilhos (:344-356) ───────────────────
    # boxShadow: 0 0 90px brand44, 0 0 60px scanColor, 0 0 20px white
    c.append({"tipo": "retangulo", "larg": 150, "alt": PH, "cor": MARCA,
              "blur": 70, "x": SCAN_X, "y": PY, "revelar": SCAN_CLIP,
              "opacidade": [[T_PAINEL, 0], [T_PAINEL + 0.4, 0.20, "outCubic"]]})
    for cor, op in ((SUCESSO, OP_A), (MARCA, OP_B), (VERDE_CLARO, OP_C)):
        c.append({"tipo": "retangulo", "larg": 80, "alt": PH, "cor": cor,
                  "blur": 46, "x": SCAN_X, "y": PY, "revelar": SCAN_CLIP,
                  "opacidade": _escalar(op, 0.45)})
    for cor, op in ((SUCESSO, OP_A), (MARCA, OP_B), (VERDE_CLARO, OP_C)):
        c.append({"tipo": "retangulo", "larg": 6, "alt": PH, "cor": cor,
                  "x": SCAN_X, "y": PY, "revelar": SCAN_CLIP, "opacidade": op})
    c.append({"tipo": "retangulo", "larg": 2, "alt": PH, "cor": TEXTO,
              "blur": 20, "x": SCAN_X, "y": PY, "revelar": SCAN_CLIP,
              "opacidade": [[T_PAINEL, 0], [T_PAINEL + 0.3, 0.9, "outCubic"]]})

    # ── as faiscas em estrela ao longo da barra (:27-32, :359-384) ───────
    # cada uma e camada propria: com `repetir` (armadilha 3) todas girariam e
    # piscariam juntas, e o que faz isto parecer faisca e cada uma ir sozinha.
    for i in range(12):
        s_tam = _rnd(i, 5) * 6 + 2                 # :29
        offx = (_rnd(i, 9) - 0.5) * 40             # :30
        vel = _rnd(i, 13) * 0.3 + 0.1              # :31
        by = PH / 2 - _rnd(i, 1) * PH              # yPct sobre a altura do painel
        r = s_tam * 1.5                            # svg de size*3 sobre viewBox 2*size
        c.append({
            "tipo": "path", "d": _estrela(r), "cor": TEXTO,
            "x": [[T_S0, PANEL_ESQ + offx, "inOutQuad"], [T_S1, PANEL_DIR + offx]],
            "y": {"ruido": {"escala": 0.02, "amp": 10, "base": by,
                            "semente": 700 + i}},
            "rotacao": [[T_PAINEL, 0, "linear"], [dur, 360 * vel]],
            "opacidade": pulso(0.34, 0.30, 0.02 + vel * 0.06, 820 + i),
            # mesmo corte da barra, pelo outro lado: no fim da varredura as
            # faiscas param na borda direita do painel e nao passam dela
            "revelar": {"prog": [[T_S0, (W / 2 + PW - offx) / W, "inOutQuad"],
                                 [T_S1, (W / 2 - offx) / W]], "dir": "esq"},
            "inicio": T_PAINEL + 0.28,
        })

    # ── coluna de texto: "Generative" 50px italico 400 (:195-213) ────────
    c += titulo("Generative", 0.0, 190, 50, TEXTO, peso=400,
                x0=COL_ESQ + larg_texto("Generative", 50) / 2, italico=True)

    # ── "Fill & Fix" 120px peso 800 em degrade (:214-231) ───────────────
    # SplitText com delay 8 e stagger 3 POR PALAVRA; dentro da palavra, a
    # cascata de LETRA da casa.
    _T = "Fill & Fix"
    _largs = [larg_char(ch, 120) for ch in _T]
    _x = COL_ESQ
    _t0, _iw, _n = 8 * F, 0, sum(1 for ch in _T if ch != " ")
    _k = 0
    for i, ch in enumerate(_T):
        w = _largs[i]
        if ch == " ":
            _t0 += PALAVRA
            _iw = 0
        else:
            c += titulo(ch, _t0 + _iw * LETRA, 90, 120, _grad(_k / (_n - 1)),
                        peso=800, x0=_x + w / 2)
            _iw += 1
            _k += 1
        _x += w

    # ── descricao 30px, duas linhas, entra no frame 12 (:235-250) ───────
    c += _palavras("Modify any video frame with", 12 * F, -40, 30, MUDO, COL_ESQ)
    c += _palavras("natural language prompts.", 12 * F + 5 * PALAVRA, -85, 30,
                   MUDO, COL_ESQ)

    # ── tagline 16px italica em degrade, frame 25 (:252-274) ────────────
    _tg, _cx = ["ai-powered", "editing"], COL_ESQ
    for i, p in enumerate(_tg):
        w = larg_texto(p, 16) + 2.4 * len(p)
        d = 25 * F + i * PALAVRA
        c.append({"tipo": "texto", "texto": p, "tamanho": 16, "peso": 400,
                  "italico": True, "cor": _grad(i / (len(_tg) - 1)),
                  "espacamento": 2.4, "x": _cx + w / 2,
                  "y": sobe(d, -128, 12, 0.4),
                  "opacidade": [[d, 0], [d + 0.35, 0.7, "outCubic"]]})
        _cx += w + larg_char(" ", 16)

    # ── as tres pilulas, frame 38 + i*6 (:277-312) ──────────────────────
    # padding 8/20 e fonte 18: a `pilula()` da casa nasce com padding 16/40, que
    # aqui estouraria os 600 da coluna — a caixa e reajustada, a entrada nao.
    _larg = [larg_texto(n, 18) + 40 for n in FEATS]
    _px = COL_ESQ
    for i, nome in enumerate(FEATS):
        t = (38 + i * 6) * F
        x = _px + _larg[i] / 2
        p = pilula(nome, t, x, -187, tam=18)
        p[0]["larg"], p[0]["alt"] = _larg[i], 38
        p[0]["cor"] = MARCA + "15"                 # :295 — `${scanColor}15`
        p[0]["contorno"] = MARCA + "33"            # :296
        p[0]["escala"] = {"mola": MOLA_TEXTO, "em": t, "de": 0.7, "para": 1.0}
        p[1]["cor"] = MARCA
        p[1]["peso"] = 600
        c += p
        # os outros dois estados de cor da varredura, cruzando por cima
        c.append({"tipo": "texto", "texto": nome, "tamanho": 18, "peso": 600,
                  "cor": VERDE_CLARO, "x": x, "y": -189,
                  "opacidade": [[48 * F, 0], [65 * F, 1], [80 * F, 0]]})
        c.append({"tipo": "retangulo", "larg": _larg[i], "alt": 38, "raio": 100,
                  "cor": SUCESSO + "15", "contorno": SUCESSO + "33",
                  "contorno_larg": 1, **viva(x, -187, 2, 400 + i),
                  "opacidade": [[75 * F, 0], [90 * F, 1]]})
        c.append({"tipo": "texto", "texto": nome, "tamanho": 18, "peso": 600,
                  "cor": SUCESSO, "x": x, "y": -189,
                  "opacidade": [[75 * F, 0], [90 * F, 1]]})
        _px += _larg[i] + 12                       # gap 12 (:278)

    return {"duracao": dur, "fundo": BG, "camadas": c}
