# -*- coding: utf-8 -*-
"""recorder.py — a cena Recorder do CreativlyBrandVideo.

Janela "Screen Recorder" 1200x720 empurrada 280px pra direita (:311-314), com
badge REC de anel progressivo (:417-467), medidor de 24 barras em onda viajante
(:471-511), overlay de webcam com borda rosa que estoura no frame 15 (:368-411)
e o rotulo gigante "RECORDER" a esquerda (:228-296). A janela inteira sobe 80px
e cresce de 0.85 numa unica mola (:40-47) — aqui a mola vira lerp de posicao
mais `escala` por camada, que e como o motor reproduz escala de grupo sem
perder a contagem de camadas. Fundo #050505 (:94), marca d'agua "REC" 500px
italica a -10deg (:96-120).
"""
from .base import *

import math

# ── a janela: 1200x720, centrada com paddingLeft 280 (:311-314) ──────────
# AbsoluteFill com paddingLeft 280 => area util 280..1920, centro em x=1100.
_CX, _CY = 140.0, 0.0          # (1100,540) em coordenadas de quadro centrado
_JW, _JH = 1200.0, 720.0         # borda esquerda em -460, topo em +360

_ORANGE = "#ff6b35"            # :62 — o passo intermediario do glow
_VERDE_CLARO = "#4ade80"       # :493 — o meio do degrade das barras
_VERMELHO = "#ff0000"          # :436 — o anel de gravacao
_CINZA_UI = "#333333"          # :346-349 — os esqueletos de conteudo
_PAINEL = "#222222"            # :338 — o painel interno


def _mix(a: str, b: str, k: float) -> str:
    """interpolateColors do Remotion, em hex. Usado no degrade das barras."""
    k = max(0.0, min(1.0, k))
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(
        f"{round(int(a[i:i+2], 16) * (1 - k) + int(b[i:i+2], 16) * k):02X}"
        for i in (0, 2, 4))


def _lin(pts: list) -> list:
    """Amostragem densa: cada trecho e linear. Sem isto o padrao `suave`
    poe um ease em CADA amostra e a onda anda aos trancos.
    Easing fora do ULTIMO keyframe — armadilha 6."""
    ks = [[t, v, "linear"] for t, v in pts]
    ks[-1] = [pts[-1][0], pts[-1][1]]
    return ks


def _pisca(janelas: list, eps: float = 0.012) -> list:
    """Estado vira tempo: janelas de aceso, com corte quase seco."""
    ks: list = []
    for a, b in janelas:
        if a <= 0.0:
            ks += [[0.0, 1.0], [b - eps, 1.0], [b, 0.0]]
        else:
            ks += [[a - eps, 0.0], [a, 1.0], [b - eps, 1.0], [b, 0.0]]
    if not ks or ks[0][0] > 0:
        ks = [[0.0, 0.0]] + ks
    return ks


def _ent(px: float, py: float, t0: float = 0.0, de: float = 0.85,
         dy: float = -80.0) -> dict:
    """A entrada da janela (:40-47): spring damping 15 / stiffness 80 /
    mass 0.6, translateY 80->0 e scale 0.85->1.

    Escala de GRUPO no motor: a posicao interpola do centro da janela pra fora
    na mesma mola que a `escala` da camada. Assim as 40 pecas da janela crescem
    juntas como um objeto so, sem virar um `grupo` (que sumiria da contagem).
    """
    return {
        "x": {"mola": MOLA_ESTADO, "em": t0, "de": _CX + (px - _CX) * de,
              "para": px},
        "y": {"mola": MOLA_ESTADO, "em": t0, "de": _CY + (py - _CY) * de + dy,
              "para": py},
        "escala": {"mola": MOLA_ESTADO, "em": t0, "de": de, "para": 1.0},
        "opacidade": entra(t0, 0.45),
    }


def _diamante(tam: float, cor: str, cx: float, cy: float, vel: float,
              atraso: float, dur: float, glow: str | None = None,
              s: int = 1) -> list[dict]:
    """FloatingDiamond (Rotating3D.tsx:180-239): quadrado a 45deg girando em
    rotateX/rotateY. Aqui o giro 3D vira esmagamento: escalaX = |cos(rotY)|,
    escalaY = |cos(rotX)| — o losango achata, passa de perfil e volta."""
    n = int(dur * FPS) + 1
    sx, sy = [], []
    for f in range(0, n + 3, 3):
        t = f * F
        sx.append([t, max(0.07, abs(math.cos(math.radians(f * 2.0 * vel))))])
        sy.append([t, max(0.07, abs(math.cos(math.radians(f * 1.5 * vel))))])
    out: list[dict] = []
    if glow:
        out.append({
            "tipo": "elipse", "raio": tam * 1.1, "cor": glow, "blur": 40,
            **viva(cx, cy, 12, s),
            "opacidade": [[atraso, 0], [atraso + 0.6, 0.22, "outCubic"]],
        })
    out.append({
        "tipo": "retangulo", "larg": tam, "alt": tam, "raio": 2, "cor": cor,
        "rotacao": 45, "escalaX": _lin(sx), "escalaY": _lin(sy),
        **viva(cx, cy, 12, s + 40),
        "escala": {"mola": {"damping": 16, "stiffness": 80, "mass": 1.0},
                   "em": atraso, "de": 0.0, "para": 1.0},
        "opacidade": [[atraso, 0], [atraso + 0.45, 0.8, "outCubic"]],
    })
    return out


def cena(dur: float) -> dict:
    c: list[dict] = []

    # ═══ 1. os tres glows de fundo (:122-163) ════════════════════════════
    # glow1 troca de cor nos frames 0/30/60/90 (:60-65). O motor nao anima cor
    # dentro de degrade — entao sao TRES manchas no mesmo ponto, cruzando por
    # opacidade, que e como a troca acontece de verdade no olho.
    for cor, ks in ((ACENTO, [[0, 0], [0.4, 0.30, "outCubic"], [1.0, 0.0],
                              [2.0, 0.0], [dur, 0.30]]),
                    (_ORANGE, [[0, 0], [1.0, 0.30, "outCubic"], [2.0, 0.0]]),
                    (MARCA, [[0.9, 0], [2.0, 0.30, "outCubic"], [dur, 0.0]])):
        g = brilho(-760, 340, 470, cor, 0.0, 0.30, s=11)
        g["opacidade"] = ks
        c.append(g)
    c.append(brilho(810, -390, 400, PRIMARIA, 0.0, 0.20, s=12))
    g3 = brilho(660, 140, 350, CIANO, 0.0, 0.16, s=13)
    g3["opacidade"] = pulso(0.11, 0.05, 0.02, 77)      # :157-161, sin(f*0.04)
    c.append(g3)

    # ═══ 2. marca d'agua "REC" 500px, -10deg, 0.025 (:96-120) ════════════
    wm = marca_dagua("REC", 500, MARCA, -10, 0.09)
    wm.update(viva(0, 0, 20, 3))                       # :84-85, deriva lenta
    wm["opacidade"] = [[0, 0], [0.45, 0, "outCubic"], [1.2, 0.09]]
    c.append(wm)

    # ═══ 3. os seis losangos flutuantes (:166-225) ═══════════════════════
    # left/top do CSS -> centro do quadro: (x + tam/2 - 960, 540 - y - tam/2)
    for tam, cor, dx, dy, vel, atr, gl in (
            (45, "#FFD60040", 120, 180, 0.8, 5 * F, MARCA),
            (30, "#FFD60026", 1700, 120, 1.2, 10 * F, None),
            (55, "#F43F5E33", 1650, 800, 0.6, 15 * F, ACENTO),
            (25, "#FFD6004D", 200, 850, 1.5, 12 * F, None),
            (38, "#3B82F633", 80, 520, 0.9, 20 * F, None),
            (20, "#FFD60059", 1780, 480, 1.8, 8 * F, MARCA)):
        c += _diamante(tam, cor, dx + tam / 2 - 960, 540 - dy - tam / 2,
                       vel, atr, dur, gl, s=int(dx) % 700)

    # ═══ 4. a janela do navegador (BrowserWindow.tsx) ════════════════════
    c += sombra(_CX, _CY, _JW, _JH, 0.0, raio=16, n=3)
    c.append({"tipo": "retangulo", "larg": _JW, "alt": _JH, "raio": 16,
              "cor": "#0F0F11A0", "contorno": BORDA_CLARA, "contorno_larg": 1,
              **_ent(_CX, _CY)})
    # barra de titulo 44px, degrade branco 0.03 -> 0 (:27-38)
    c.append({"tipo": "retangulo", "larg": _JW, "alt": 44, "raio": 12,
              "cor": {"tipo": "linear", "cores": ["#FFFFFF08", "#FFFFFF00"],
                      "de": [0, -22], "para": [0, 22]},
              **_ent(_CX, 338)})
    c.append({"tipo": "retangulo", "larg": _JW, "alt": 1, "cor": BORDA,
              **_ent(_CX, 316)})
    for i, cor in enumerate(("#FF5F56", "#FFBD2E", "#27C93F")):   # :41-67
        c.append({"tipo": "elipse", "raio": 6, "cor": cor,
                  **_ent(-434 + i * 20, 338)})
    c.append({"tipo": "retangulo", "larg": 1092, "alt": 24, "raio": 6,
              "cor": "#0000004D", "contorno": "#FFFFFF0D", "contorno_larg": 1,
              **_ent(174, 338)})
    w1, w2 = larg_texto("creativly.ai / ", 11), larg_texto("Screen Recorder", 11)
    x0 = 174 - (w1 + w2) / 2
    c.append({"tipo": "texto", "texto": "creativly.ai / ", "tamanho": 11,
              "peso": 500, "cor": MUDO, "espacamento": 0.22,
              **_ent(x0 + w1 / 2, 338), "opacidade": entra(0.05, 0.5)})
    c.append({"tipo": "texto", "texto": "Screen Recorder", "tamanho": 11,
              "peso": 500, "cor": TEXTO, "espacamento": 0.22,
              **_ent(x0 + w1 + w2 / 2, 338), "opacidade": entra(0.05, 0.5)})

    # ── o conteudo capturado (:316-365) ──────────────────────────────────
    c.append({"tipo": "retangulo", "larg": _JW, "alt": 676, "cor": BG_SUP,
              **_ent(_CX, -22)})
    c.append({"tipo": "retangulo", "larg": 1120, "alt": 596, "raio": 12,
              "cor": _PAINEL, **_ent(_CX, -22)})
    for larg, alt, px, py, raio in ((416, 40, -172, 216, 8),
                                    (1040, 20, 140, 166, 4),
                                    (936, 20, 88, 126, 4),
                                    (728, 20, -16, 86, 4)):
        c.append({"tipo": "retangulo", "larg": larg, "alt": alt, "raio": raio,
                  "cor": _CINZA_UI, **_ent(px, py)})
    # cursor: left 30% +- 25%, top 40% +- 18% do painel (:352-364).
    # Aqui a deriva de ruido E a identidade da camada — ela nao entra na mola
    # de grupo, so na opacidade.
    cur_x = {"ruido": {"escala": 0.015, "amp": 280, "base": -84, "semente": 21}}
    cur_y = {"ruido": {"escala": 0.015, "amp": 107, "base": 38, "semente": 5021}}
    c.append({"tipo": "elipse", "raio": 16, "cor": PRIMARIA, "blur": 24,
              "x": cur_x, "y": cur_y, "opacidade": entra(0.1, 0.5)})
    c.append({"tipo": "elipse", "raio": 6, "cor": PRIMARIA,
              "x": cur_x, "y": cur_y,
              "opacidade": [[0.1, 0], [0.6, 0.8, "outCubic"]]})

    # ── overlay da webcam, frame 15, scale 0.5 -> 1 (:368-411) ───────────
    # O UNICO MOLA_DESTAQUE da cena: no original camSpr tem damping 14 e
    # stiffness 100 (zeta 0.7) — e o unico elemento que quica.
    t_cam = 15 * F
    c.append({"tipo": "elipse", "rx": 190, "ry": 120, "cor": ACENTO,
              "blur": 60, **_ent(530, -210),
              "opacidade": [[t_cam, 0], [t_cam + 0.5, 0.22, "outCubic"]]})
    for camada in ({"tipo": "retangulo", "larg": 300, "alt": 180, "raio": 20,
                    "cor": BG_SUP, "contorno": ACENTO, "contorno_larg": 4},
                   {"tipo": "retangulo", "larg": 288, "alt": 168, "raio": 16,
                    "cor": {"tipo": "linear", "cores": ["#333333", "#444444"],
                            "de": [-144, -84], "para": [144, 84]}},
                   {"tipo": "texto", "texto": "USER CAM", "tamanho": 18,
                    "peso": 800, "cor": TEXTO}):
        camada.update(_ent(530, -210))
        camada["escala"] = {"mola": MOLA_DESTAQUE, "em": t_cam, "de": 0.5,
                            "para": 1.0}
        camada["opacidade"] = entra(t_cam, 0.3)
        c.append(camada)

    # ── badge REC, frame 5 (:417-467) ────────────────────────────────────
    t_rec = 5 * F
    w_rec = larg_texto("REC", 16)
    w_seg = larg_texto("00:00.", 14)
    w_cent = larg_texto("00", 14)
    w_pill = 16 + 28 + 12 + w_rec + 12 + w_seg + w_cent + 16
    px_pill = -420 + w_pill / 2                        # left 40 da janela
    c.append({"tipo": "retangulo", "larg": w_pill, "alt": 44, "raio": 100,
              "cor": "#00000099", **_ent(px_pill, 278),
              "opacidade": entra(t_rec, 0.3)})
    x_anel = -420 + 16 + 14
    c.append({"tipo": "elipse", "raio": 13, "cor": "#00000000",
              "contorno": "#FF000033", "contorno_larg": 2.3,
              **_ent(x_anel, 278), "opacidade": entra(t_rec, 0.3)})
    # armadilha 2: forma preenchida nao tem contorno pra correr — anel e
    # cor transparente + contorno. `traco` 0->1 nos 90 frames (:50-54).
    c.append({"tipo": "elipse", "raio": 13, "cor": "#00000000",
              "contorno": _VERMELHO, "contorno_larg": 2.3,
              "traco": [[0, 0, "linear"], [dur, 1]],
              **_ent(x_anel, 278), "opacidade": entra(t_rec, 0.3)})
    # blink: sin(frame*0.2) > 0 -> periodo 31.4 frames (:30-32)
    per = 2 * math.pi / 0.2 * F
    bl = [[t_rec, 0.0], [t_rec + 0.12, 1.0]]
    for k in range(4):
        a, b = k * per, k * per + per / 2
        if a > t_rec + 0.12:
            bl += [[a - 0.02, 0.3], [a, 1.0]]
        if b > t_rec + 0.12:
            bl += [[b, 1.0], [b + 0.02, 0.3]]
    bl = [p for p in bl if p[0] <= dur]
    c.append({"tipo": "elipse", "raio": 12, "cor": _VERMELHO, "blur": 20,
              **_ent(x_anel, 278),
              "opacidade": [[t, v * 0.5] for t, v in bl]})
    c.append({"tipo": "elipse", "raio": 5, "cor": _VERMELHO,
              **_ent(x_anel, 278), "opacidade": bl})
    x_txt = -420 + 16 + 28 + 12
    c.append({"tipo": "texto", "texto": "REC", "tamanho": 16, "peso": 700,
              "cor": TEXTO, **_ent(x_txt + w_rec / 2, 278),
              "opacidade": entra(t_rec, 0.3)})
    # o cronometro (:35-37). Texto nao anima: o estado vira tempo, com uma
    # camada por valor cruzando por opacidade. Segundos em 3, centesimos em 5.
    x_seg = x_txt + w_rec + 12
    for s in range(3):
        ks = _pisca([(float(s), float(s + 1))])
        c.append({"tipo": "texto", "texto": f"00:0{s}.", "tamanho": 14,
                  "peso": 400, "cor": MUDO,
                  **_ent(x_seg + w_seg / 2, 278),
                  "opacidade": [[t, v] for t, v in ks if t >= t_rec] or ks})
    for j in range(5):
        jan = [(s + j * 6 * F, s + (j + 1) * 6 * F) for s in (0.0, 1.0, 2.0)]
        c.append({"tipo": "texto", "texto": f"{j * 20:02d}", "tamanho": 14,
                  "peso": 400, "cor": MUDO,
                  **_ent(x_seg + w_seg + w_cent / 2, 278),
                  "opacidade": _pisca(jan)})

    # ── medidor de audio, frame 8: 24 barras (:471-511) ──────────────────
    t_wav = 8 * F
    N = 24
    w_wav = 32 + N * 3 + (N - 1) * 3
    c.append({"tipo": "retangulo", "larg": w_wav, "alt": 44, "raio": 100,
              "cor": "#00000099", **_ent(700 - w_wav / 2, 278),
              "opacidade": entra(t_wav, 0.3)})
    x_b0 = 700 - 16 - (N * 3 + (N - 1) * 3) + 1.5
    n_f = int(dur * FPS) + 2
    for i in range(N):
        k = i / (N - 1)
        cor = (_mix(SUCESSO, _VERDE_CLARO, k * 2) if k < 0.5
               else _mix(_VERDE_CLARO, SUCESSO, (k - 0.5) * 2))
        pts = []
        for f in range(0, n_f + 2, 2):
            onda = math.sin(f * 0.3 + i * 0.8) * 0.5 + 0.5
            ruid = math.sin(f * 0.11 + i * 2.1)          # substituto de noise2D
            pts.append([f * F, round(max(2.0, 4 + (onda + ruid * 0.3) * 16), 2)])
        c.append({"tipo": "retangulo", "larg": 3, "alt": _lin(pts), "raio": 2,
                  "cor": cor, **_ent(x_b0 + i * 6, 278),
                  "opacidade": [[t_wav, 0], [t_wav + 0.3, 0.8, "outCubic"]]})

    # ═══ 6. o rotulo gigante, POR CIMA da janela — zIndex 10 (:239) ══════
    # left 80, top 340. "Screen" 22 italico / "RECORDER" 80 peso 800 /
    # "capture everything" 14 italico com espacamento 0.3em (:243-293).
    ESQ_ROT = 80 - 960                                  # -880
    w_scr = larg_texto("SCREEN", 22) + 3.3 * 6
    c.append(rotulo("SCREEN", 8 * F, 187, MUDO, 22,
                    ESQ_ROT + w_scr / 2, esp=3, peso=500))
    c += titulo("RECORDER", 8 * F, 136, 80, TEXTO, 800, LETRA,
                ESQ_ROT + larg_texto("RECORDER", 80) / 2)
    # o tagline e degrade #3B82F6 -> #06B6D4 (:279): duas metades, duas cores
    w_a = larg_texto("capture ", 14) + 4.2 * 8
    w_b = larg_texto("everything", 14) + 4.2 * 10
    for txt, cor, x0, w in (("capture ", MARCA, ESQ_ROT + 4, w_a),
                            ("everything", CIANO, ESQ_ROT + 4 + w_a, w_b)):
        c.append({
            "tipo": "texto", "texto": txt, "tamanho": 14, "peso": 400,
            "italico": True, "cor": cor, "espacamento": 4.2,
            **viva(x0 + w / 2, 81, 1.5, 500 + len(txt)),
            "opacidade": [[18 * F, 0], [18 * F + 0.35, 1, "outCubic"]],
        })

    return {"duracao": dur, "fundo": BG, "camadas": c}
