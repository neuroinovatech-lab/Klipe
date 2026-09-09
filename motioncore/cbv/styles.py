# -*- coding: utf-8 -*-
"""styles.py — a cena Style Presets do CreativlyBrandVideo.

Fundo escuro (:75 backgroundColor COLORS.bg) com a foto surrealista a 0.35 sob
vinheta radial (:148-155); marca d'agua STYLES italica 400px a -15deg (:76-101);
titulo "Style Presets" 140px letra a letra e as seis pilulas de 16/40 raio 100
(:234-274) trocando de ativa a cada 20 frames (:48).

O motor nao tem estado: o ciclo de 20 frames vira TEMPO. Cada coisa que no .tsx
depende de `activeStyleIndex` (a foto com o filtro do estilo :151, o brilho
radial :140, a linha indicadora :282) existe aqui em seis copias que cruzam por
opacidade em janelas de 0.667 s — e a linha se redesenha por `traco` nos
primeiros 30% de cada janela, como o `evolvePath` do original (:62-65).
"""
import math

from .base import *

# :26-33 — os seis estilos e a cor de cada um
ESTILOS = [
    ("Cinematic", "#FF5F56", "#FFDDB0"),      # contrast(1.2) sepia(0.2)
    ("Anime", MARCA, "#E4EEFF"),              # saturate(1.5) contrast(1.1)
    ("3D Render", "#27C93F", "#FFFFFF"),      # brightness(1.1)
    ("Claymation", "#3357FF", "#E6D8CC"),     # contrast(0.9) saturate(0.8)
    ("Line Art", "#A833FF", "#B8B8C0"),       # grayscale(1) contrast(1.5)
    ("Photographic", "#FF33A8", "#FFFFFF"),   # none
]
TROCA = 20 * F          # :48 — Math.floor(frame / 20) % 6
FOTO = "surrealist-concept_800w.jpg"

# ── layout medido do fluxo do .tsx ───────────────────────────────────────
# curated(24, mb 5) / titulo(140, mb 10) / sub(20, mb 40) / pilulas / linha(mt 40)
Y_ROTULO, Y_TITULO, Y_SUB = 232, 128, 18
Y_FILA1, Y_FILA2, Y_LINHA = -72, -163, -242
TAM_P = 32                                   # :258 fontSize 32
FILAS = [(0, 1, 2, 3), (4, 5)]               # :235 width 1200 + gap 20 -> quebra


def _larg_pilula(nome: str) -> float:
    return larg_texto(nome, TAM_P) + 80       # :251 padding 16px 40px


def _janelas(idx: int, dur: float) -> list:
    """Os trechos em que ESTE estilo e o ativo, dentro da cena."""
    n = int(dur / TROCA) + 1
    return [(k * TROCA, (k + 1) * TROCA)
            for k in range(n) if k % len(ESTILOS) == idx and k * TROCA < dur]


def _op(idx: int, dur: float, alto: float = 1.0, cross: float = 0.06,
        desde: float = 0.0, ease: str | None = None) -> list:
    """Estado vira tempo: keyframes que acendem so na janela deste estilo.

    `ease` "linear" mantem a soma das seis copias constante no cruzamento —
    com o padrao `suave` a foto de fundo piscaria a cada troca.
    """
    ks: list = [[0.0, 0.0]]

    def k(t, v):
        return [round(t, 3), v] + ([ease] if ease else [])

    for a, b in _janelas(idx, dur):
        a = max(a, desde)
        if b - a < 0.08:
            continue
        if a - cross > ks[-1][0] + 1e-3:
            ks.append(k(a - cross, 0.0))
        ks.append(k(a + cross, alto))
        ks.append(k(min(b - cross, dur), alto))
        ks.append(k(min(b + cross, dur + 0.1), 0.0))
    ks[-1] = ks[-1][:2]          # armadilha 6: easing no ultimo e ignorado
    return ks


def _cubo(x: float, y: float, lado: float, cor: str, aro: str, vel: float,
          t0: float, s: int, dur: float) -> list:
    """Rotating3DBox (:101-102) sem 3D real: tres quadrados concentricos que
    giram em Z e achatam em X seguindo |cos(rotY)| — o mesmo `frame*1.2*speed`
    do componente. E o que sobra de um cubo quando o motor e 2D."""
    out = []
    for j in range(3):
        kx = []
        for p in range(11):
            t = dur * p / 10.0
            ry = math.radians(t * FPS * 1.2 * vel + j * 55)
            kx.append([round(t, 3), round(max(0.20, abs(math.cos(ry))), 3),
                       "linear"])
        kx[-1] = kx[-1][:2]                   # easing no ultimo e ignorado
        rz = j * 28
        out.append({
            "tipo": "retangulo", "larg": lado * (1 - j * 0.18),
            "alt": lado * (1 - j * 0.18), "raio": 2,
            "cor": cor, "contorno": aro, "contorno_larg": 1,
            **viva(x, y, 3, s + j),
            "rotacao": [[0.0, rz, "linear"], [dur, rz + dur * FPS * 0.3 * vel]],
            "escalaX": kx,
            "opacidade": entra(t0 + j * 0.05, 0.5),
            "escala": {"mola": MOLA_ESTADO, "em": t0 + j * 0.05,
                       "de": 0.0, "para": 1.0},
        })
    return out


def cena(dur: float) -> dict:
    C: list = []

    # ── a foto, seis vezes: cada copia leva o `filter` de um estilo (:151) ──
    for i, (_n, _c, tint) in enumerate(ESTILOS):
        C.append({
            "tipo": "imagem", "src": asset(FOTO),
            "larg": "100%", "alt": "100%", "ajuste": "cobrir", "tingir": tint,
            "opacidade": _op(i, dur, 0.35, 0.12, ease="linear"),
            "escala": pulso(1.03, 0.02, 0.004, 5),
        })

    # vinheta radial por cima da foto (:153) — e ela que da contraste ao texto
    C.append({"tipo": "elipse", "raio": W * 0.72, "opacidade": 0.82,
              "cor": {"tipo": "radial", "cores": ["#00000000", BG],
                      "raio": W * 0.72}})

    # ── marca d'agua STYLES (:76-101): 400px, italica, -15deg, degrade ──────
    # o degrade de texto nao existe no motor: duas copias deslocadas,
    # MARCA atras e CIANO na frente, aproximam o brand->cyan do original
    C.append(marca_dagua("STYLES", 400, MARCA, -15, 0.055, 0))
    _c = marca_dagua("STYLES", 400, CIANO, -15, 0.035, -6)
    _c["x"] = 10
    C.append(_c)

    # ── o brilho radial que muda de cor com o estilo (:135-145) ────────────
    for i, (_n, cor, _t) in enumerate(ESTILOS):
        g = brilho(0, 0, W * 0.6, cor, 0.0, 0.2, 40 + i)
        g["opacidade"] = _op(i, dur, 0.22, 0.12, ease="linear")
        g["escala"] = pulso(1.0, 0.05, 0.02, 60 + i)   # :51 glowPulse
        C.append(g)

    # ── poeira (:35-40, :112-133) ──────────────────────────────────────────
    C += particulas(30, MARCA, CIANO, 22, 3)   # :35-40 length 30

    # ── os dois cubos e os dois diamantes das bordas (:101-106) ────────────
    C += _cubo(-810, 390, 60, "#3B82F60D", "#3B82F626", 0.5, 0.17, 210, dur)
    C += _cubo(762, -332, 45, "#3b82f60A", "#3b82f61F", 0.8, 0.33, 260, dur)

    # diamante com brilho (:105) — o UNICO destaque com mola de quique
    C.append({"tipo": "elipse", "raio": 42, "blur": 24,
              **viva(-745, -325, 10, 311),
              "cor": {"tipo": "radial", "cores": [MARCA, "#00000000"],
                      "raio": 42},
              "opacidade": entra(0.2, 0.6)})
    C.append({"tipo": "retangulo", "larg": 30, "alt": 30, "raio": 3,
              "cor": "#3B82F64D", "contorno": "#3B82F680", "contorno_larg": 1,
              **viva(-745, -325, 12, 312),
              "rotacao": [[0.0, 45, "linear"], [dur, 45 + dur * FPS * 2 * 0.7]],
              "escalaY": pulso(1.0, 0.28, 0.02, 313),
              "opacidade": entra(0.2, 0.4),
              "escala": {"mola": MOLA_DESTAQUE, "em": 0.2, "de": 0.0,
                         "para": 1.0}})
    C.append({"tipo": "retangulo", "larg": 20, "alt": 20, "raio": 2,
              "cor": "#3b82f640", "contorno": "#3b82f66B", "contorno_larg": 1,
              **viva(700, 330, 10, 314),
              "rotacao": [[0.0, 45, "linear"], [dur, 45 + dur * FPS * 2 * 1.0]],
              "escalaY": pulso(1.0, 0.30, 0.022, 315),
              "opacidade": entra(0.4, 0.4),
              "escala": {"mola": MOLA_TEXTO, "em": 0.4, "de": 0.0, "para": 1.0}})

    # ── rotulo "curated" (:158-175): 24px, italico, letter-spacing 0.2em ────
    r = rotulo("curated", 0.05, Y_ROTULO, MUDO, 24, 0.0, 5, 400)
    r["italico"] = True
    C.append(r)

    # ── titulo 140px letra a letra (:179-202) ──────────────────────────────
    # o textShadow `0 0 60px transColor33` (:187) vira `sombra` da propria
    # letra: cor fixa, porque sombra de texto nao e animavel
    for lay in titulo("Style Presets", 0.10, Y_TITULO, 140, TEXTO, 900):
        lay["sombra"] = [{"x": 0, "y": 0, "blur": 60, "cor": "#3B82F633"}]
        C.append(lay)

    # ── "transform everything" (:205-230): 20px italico, degrade brand->cyan ─
    _w1 = larg_texto("transform", 20) + 2 * 9
    _w2 = larg_texto("everything", 20) + 2 * 10
    _tot = _w1 + 12 + _w2
    for j, (pal, cor, xw) in enumerate((
            ("transform", MARCA, -_tot / 2 + _w1 / 2),
            ("everything", CIANO, _tot / 2 - _w2 / 2))):
        C.append({"tipo": "texto", "texto": pal, "tamanho": 20, "peso": 700,
                  "italico": True, "cor": cor, "espacamento": 2,
                  **viva(xw, Y_SUB, 2, 720 + j),
                  "opacidade": entra(0.17 + j * PALAVRA, 0.3)})

    # ── as seis pilulas (:234-274) ─────────────────────────────────────────
    largs = [_larg_pilula(n) for n, _c, _t in ESTILOS]
    for fi, idxs in enumerate(FILAS):
        total = sum(largs[i] for i in idxs) + 20 * (len(idxs) - 1)
        px = -total / 2
        yf = Y_FILA1 if fi == 0 else Y_FILA2
        for i in idxs:
            nome, cor, _t = ESTILOS[i]
            cx = px + largs[i] / 2
            t0 = 0.27 + i * BLOCO                     # :239 frame 8 + i*4
            # halo: o boxShadow `0 0 40px color66` da ativa (:265-267)
            C.append({"tipo": "retangulo", "larg": largs[i] + 44,
                      "alt": TAM_P + 76, "raio": 100, "cor": cor, "blur": 42,
                      "x": cx, "y": yf,
                      "opacidade": _op(i, dur, 0.42, 0.08, t0 + 0.12)})
            p = pilula(nome, t0, cx, yf, cor, TAM_P,
                       _op(i, dur, 1.0, 0.06, t0 + 0.12))
            # :243 activeScale = 1.12 + 0.02 * sin(frame * 0.2)
            for lay in p[2:]:
                lay["escala"] = pulso(1.12, 0.03, 0.03, 500 + i)
            p[3]["peso"] = 900                        # :257 ativa e 900 italico
            p[3]["italico"] = True
            C += p
            px += largs[i] + 20

    # ── linha indicadora (:276-290): 200x4, redesenhada a cada janela ───────
    for i, (_n, cor, _t) in enumerate(ESTILOS):
        jan = _janelas(i, dur)
        a = jan[0][0] if jan else 0.0
        C.append({"tipo": "linha", "de": [-100, 0], "para": [100, 0],
                  "contorno": cor, "contorno_larg": 4,
                  **viva(0, Y_LINHA, 2, 800 + i),
                  # :62 indicatorProg — 0 -> 1 nos primeiros 30% da janela
                  "traco": [[max(0.0, a), 0.02, "outCubic"],
                            [a + 0.30 * TROCA, 1.0]],
                  "opacidade": _op(i, dur, 0.8, 0.05, 0.4)})

    return {"duracao": dur, "fundo": BG, "camadas": C}
