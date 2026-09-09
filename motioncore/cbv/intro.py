# -*- coding: utf-8 -*-
"""intro.py — a cena Intro do CreativlyBrandVideo.

Abertura de marca sobre fundo #050505 (:216 backgroundColor COLORS.bg): logo
branco 220px entrando de 1.8x com desfoque (:35-42), "VISUAL" 200px em 900 e
"AI" 280px italico em degrade azul-ciano deslizando 400px da direita (:59-77),
sublinhado SVG que se desenha entre os frames 50 e 75 (:44-49, :293-311), e a
escada "The Generative / Playground / for creators" (:80-100).

Ornamento: duas esferas 3D de aro (:129-146), quatro losangos flutuantes
(:149-152), 18 estrelas de 4 pontas com deriva (:23-30, :155-196), 5 aneis de
pulso maxSize 1400 speed 0.3 (:198) e 3 halos girando a 0.8 grau/frame (:52-53,
:201-243). As esferas e os losangos sao projecao ortografica calculada aqui:
rx/ry/rotacao viram keyframes porque o motor nao tem 3D.
"""
import math

from .base import *

__all__ = ["cena"]

# ── tempos do original, em segundos (frame / 30) ─────────────────────────
T_LOGO = 0.0          # :34  Sequence from 0
T_VISUAL = 8 * F      # :64  Sequence from 8
T_AI = 18 * F         # :71  Sequence from 18
T_SUB = 35 * F        # :80  Sequence from 35
T_PLAY = 45 * F       # :87  Sequence from 45
T_CRIA = 60 * F       # :94  Sequence from 60
T_RISCO0 = 50 * F     # :44-48 underlineProgress interpola 50..75
T_RISCO1 = 75 * F

# ── a coluna central, medida do flex do original ─────────────────────────
# logo 220x45.8 + 30 / VISUAL 200@0.8 / AI 280@0.7 com margens negativas /
# risco 30 / "The Generative" 28+15 / "Playground" 90 / "for creators" 22+10.
# Altura somada 643.8, centrada em 540 -> topo em 218.
Y_LOGO = 299.0
Y_VISUAL = 166.0
Y_AI = 18.0
Y_RISCO = -90.0
Y_SUB = -137.0
Y_PLAY = -217.0
Y_CRIA = -308.0
Y_HALO = 70.0         # :205-208 translate(-250,-320) sobre o centro


# ── pseudoaleatorio deterministico (o `random(seed)` do Remotion) ────────
def _rnd(k: float) -> float:
    x = math.sin(k * 127.1 + 311.7) * 43758.5453
    return x - math.floor(x)


def _lerp_cor(a: str, b: str, u: float) -> str:
    """Degrade linear-gradient(135deg, #3B82F6, #06B6D4) resolvido por letra —
    o motor pinta texto com UMA cor, entao o degrade vira a rampa da palavra."""
    u = max(0.0, min(1.0, u))
    ca = [int(a[1 + 2 * i:3 + 2 * i], 16) for i in range(3)]
    cb = [int(b[1 + 2 * i:3 + 2 * i], 16) for i in range(3)]
    return "#" + "".join(f"{int(ca[i] + (cb[i] - ca[i]) * u):02X}" for i in range(3))


# ── algebra 3x3 para a projecao das esferas e dos losangos ───────────────
def _mul(m, n):
    return [[sum(m[i][k] * n[k][j] for k in range(3)) for j in range(3)]
            for i in range(3)]


def _rx(g):
    c, s = math.cos(math.radians(g)), math.sin(math.radians(g))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _ry(g):
    c, s = math.cos(math.radians(g)), math.sin(math.radians(g))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def _aro(raio, rot_x, rot_y, giro, dur, passo=4 * F):
    """Circulo de raio R sob Rx(A)*Ry(B)*giro, projetado ortograficamente.

    O projetado de um circulo e uma elipse: u = M(R,0,0), v = M(0,R,0) largados
    no plano da tela. Os semi-eixos saem dos valores singulares de [u|v] e a
    inclinacao de meia-arctan — que e exatamente o que `rx`, `ry` e `rotacao`
    pedem. Desenrolo o angulo em multiplos de 180 (elipse e simetrica) senao a
    volta do arctan faz o aro dar um pinote entre dois keyframes.
    """
    krx, kry, kro, ant = [], [], [], 0.0
    n = int(dur / passo) + 2
    for i in range(n):
        t = min(i * passo, dur)
        f = t * FPS
        m = _mul(_mul(_rx(rot_x(f)), _ry(rot_y(f))), giro)
        ux, uy = m[0][0] * raio, m[1][0] * raio
        vx, vy = m[0][1] * raio, m[1][1] * raio
        a, b = ux * ux + uy * uy, vx * vx + vy * vy
        c = ux * vx + uy * vy
        d = math.hypot((a - b) / 2, c)
        s1 = math.sqrt(max(0.25, (a + b) / 2 + d))
        s2 = math.sqrt(max(0.25, (a + b) / 2 - d))
        ang = math.degrees(0.5 * math.atan2(2 * c, a - b))
        while ang - ant > 90:
            ang -= 180
        while ant - ang > 90:
            ang += 180
        ant = ang
        krx.append([round(t, 4), round(s1, 2)])
        kry.append([round(t, 4), round(s2, 2)])
        kro.append([round(t, 4), round(ang, 2)])
    return krx, kry, kro


def _esfera(cx, cy, tam, cor, vel, atraso, dur, s):
    """:129-146 Rotating3DSphere — 5 aros verticais (rotateY) + 5 horizontais
    (rotateX, 1px e metade da opacidade), girando em rotateX(f*0.5*vel) e
    rotateY(f*0.8*vel). Entrada por mola damping 14 stiffness 60, escala 0.5->1."""
    raio, t0 = tam / 2.0, atraso * F
    mola = {"mola": {"damping": 14, "stiffness": 60, "mass": 1.0},
            "em": t0, "de": 0.5, "para": 1.0}
    out = []
    for fam in ("v", "h"):
        for i in range(5):
            g = (i / 5.0) * 180.0
            giro = _ry(g) if fam == "v" else _rx(g)
            krx, kry, kro = _aro(raio, lambda f: f * 0.5 * vel,
                                 lambda f: f * 0.8 * vel, giro, dur)
            op = 1.0 if fam == "v" else 0.5
            out.append({
                "tipo": "elipse", "rx": krx, "ry": kry, "rotacao": kro,
                "cor": "#00000000", "contorno": cor,
                "contorno_larg": 1.5 if fam == "v" else 1.0,
                **viva(cx, cy, 4, s + i + (0 if fam == "v" else 40)),
                "opacidade": [[t0, 0, "outCubic"], [t0 + 0.5, op]],
                "escala": mola,
            })
    return out


def _losango(cx, cy, tam, cor, vel, atraso, dur, s):
    """:149-152 FloatingDiamond — quadrado em rotate(45deg) sob rotateX(f*1.5*vel)
    e rotateY(f*2*vel). O 45 vai ASSADO no path: no motor a escala vem depois da
    rotacao, e o achatamento do CSS vem antes — com `rotacao` o losango cisalha."""
    d = tam * 0.7071
    kx, ky = [], []
    n = int(dur / (2 * F)) + 2
    for i in range(n):
        t = min(i * 2 * F, dur)
        f = t * FPS
        kx.append([round(t, 4), round(max(0.07, abs(math.cos(math.radians(f * 2.0 * vel)))), 3)])
        ky.append([round(t, 4), round(max(0.07, abs(math.cos(math.radians(f * 1.5 * vel)))), 3)])
    t0 = atraso * F
    return {
        "tipo": "path", "d": f"M 0 {-d:.1f} L {d:.1f} 0 L 0 {d:.1f} L {-d:.1f} 0 Z",
        "cor": cor, "contorno": cor, "contorno_larg": 1,
        **viva(cx, cy, 12, s),
        "escalaX": kx, "escalaY": ky,
        "opacidade": [[t0, 0, "outCubic"], [t0 + 0.53, 0.8]],
        "escala": {"mola": {"damping": 16, "stiffness": 80, "mass": 1.0},
                   "em": t0, "de": 0.0, "para": 1.0},
    }


def _estrela_d(r, ri, pontos=4):
    p = []
    for j in range(2 * pontos):
        a = math.radians(-90 + j * 180.0 / pontos)
        rr = r if j % 2 == 0 else ri
        p.append(f"{rr * math.cos(a):.2f} {rr * math.sin(a):.2f}")
    return "M " + " L ".join(p) + " Z"


def _estrelas(n, dur):
    """:23-30 e :155-196 — 18 estrelas de 4 pontas, so contorno, com deriva de
    ruido +-20px, giro de f*speed*2 graus e pulso sin(f*0.08 + i*2)*0.4+0.4
    multiplicado por 0.3, com rampa de 15 frames a partir do proprio atraso."""
    cores = (MARCA, PRIMARIA, SECUNDARIA)
    out = []
    for i in range(n):
        bx = _rnd(i * 5 + 1) * W - W / 2
        by = H / 2 - _rnd(i * 5 + 2) * H
        tam = _rnd(i * 5 + 3) * 20 + 8
        vel = _rnd(i * 5 + 4) * 0.4 + 0.1
        d = _rnd(i * 5 + 5) * 30 * F
        op = [[d, 0.0]]
        t = d + 0.5
        while t < dur:
            v = (math.sin(t * 2.4 + i * 2) * 0.4 + 0.4) * 0.3
            op.append([round(t, 3), round(max(0.0, v), 3)])
            t += 0.22
        if len(op) == 1:
            op.append([dur, 0.12])
        out.append({
            "tipo": "path", "d": _estrela_d(tam * 1.25, tam * 0.375),
            "cor": "#00000000", "contorno": cores[i % 3], "contorno_larg": 1,
            **viva(bx, by, 18, 700 + i),
            "rotacao": [[0, 0.0, "linear"], [dur, round(dur * 60 * vel, 1)]],
            "opacidade": op,
        })
    return out


def _aneis_pulso(dur, n=5, cor="#3B82F615"):
    """:198 PulseRings count 5 maxSize 1400 speed 0.3 -> ciclo de 100 frames.
    O anel nasce no centro, cresce ate 700 de raio e some; a opacidade sobe a
    0.8 em 20% do ciclo e cai a zero no fim. Cada anel entra defasado de 1/5."""
    ciclo = FPS / 0.3 * F
    out = []
    for i in range(n):
        raio, op, k = [], [], -1
        while True:
            t0 = k * ciclo - (i / n) * ciclo
            if t0 > dur:
                break
            t1 = t0 + ciclo
            raio += [[round(t0, 4), 0.0, "linear"],
                     [round(t1 - 1e-3, 4), 700.0, "linear"]]
            op += [[round(t0, 4), 0.0, "linear"],
                   [round(t0 + 0.2 * ciclo, 4), 0.8, "linear"],
                   [round(t1 - 1e-3, 4), 0.0, "linear"]]
            k += 1
        raio[-1] = raio[-1][:2]
        op[-1] = op[-1][:2]
        out.append({"tipo": "elipse", "raio": raio, "cor": "#00000000",
                    "contorno": cor, "contorno_larg": 1, "opacidade": op})
    return out


def _halo(raio, faint, vivo, de_grau, larg, giro, op, dur):
    """:201-243 — aro tenue inteiro + o quarto aceso da borda (borderTop /
    borderBottom / borderLeft), que e o unico pedaco onde o giro aparece.
    Anel = cor transparente + contorno: forma preenchida nao tem contorno pra
    correr, e o preenchimento comeria o centro do quadro."""
    o = [[0, 0.0, "outCubic"], [25 * F, op]]
    rot = [[0, 0.0, "linear"], [dur, round(giro * FPS * dur, 1)]]
    return [
        {"tipo": "elipse", "raio": raio, "cor": "#00000000", "contorno": faint,
         "contorno_larg": larg, **viva(0, Y_HALO, 3, 61), "opacidade": o},
        {"tipo": "elipse", "raio": raio, "cor": "#00000000", "contorno": vivo,
         "contorno_larg": larg + 0.5, "de_grau": de_grau, "varre_grau": 90,
         "x": 0, "y": Y_HALO, "rotacao": rot, "opacidade": o},
    ]


def _letras(txt, t0, y, tam, cor, peso=900, italico=False, passo=LETRA,
            esp=0.0, mola=MOLA_TEXTO, de=0.84, c2=None, halo=None):
    """O `titulo()` da base com tres folgas que esta cena precisa: letter-spacing
    negativo (-0.06em em VISUAL, -0.08em em AI, -0.03em em Playground), cor que
    anda de MARCA a CIANO ao longo da palavra, e o `textShadow`/`drop-shadow`
    que o original poe nas tres (:301, :325, :393)."""
    largs = [larg_char(c, tam) + esp for c in txt]
    total = sum(largs)
    x = -total / 2
    out, n = [], max(1, len(txt) - 1)
    for i, ch in enumerate(txt):
        w = larg_char(ch, tam)
        if ch != " ":
            d = t0 + i * passo
            cam = {
                "tipo": "texto", "texto": ch, "tamanho": tam, "peso": peso,
                "cor": _lerp_cor(cor, c2, i / n) if c2 else cor,
                "italico": italico, "x": x + w / 2,
                "y": sobe(d, y, tam * 0.18),
                "opacidade": entra(d, 0.22),
                "escala": {"mola": mola, "em": d, "de": de, "para": 1.0},
            }
            if halo:
                cam["sombra"] = [{"x": 0, "y": 0, "blur": halo[0],
                                  "cor": halo[1]}]
            out.append(cam)
        x += largs[i]
    return out


def cena(dur: float) -> dict:
    c: list[dict] = []

    # ── brilho ambiente :219-231 — radial brand25 -> cyan15 -> nada ──────
    c.append(brilho(0, 0, W * 0.42, MARCA, 0.0, 0.26, 3))
    c.append(brilho(0, -40, W * 0.58, CIANO, 0.0, 0.15, 9))

    # ── as duas esferas de aro :233-249 ──────────────────────────────────
    c += _esfera(-810, 420, 160, "#3B82F644", 0.7, 5, dur, 120)
    c += _esfera(690, -260, 100, "#3b82f636", 1.2, 10, dur, 300)

    # ── quatro losangos :252-255 ─────────────────────────────────────────
    c.append(_losango(-640, -230, 40, "#3B82F659", 0.8, 8, dur, 11))
    c.append(_losango(552, 327, 25, "#3b82f64d", 1.3, 12, dur, 22))
    c.append(_losango(767, 12, 55, "#8b5cf640", 0.6, 15, dur, 33))
    c.append(_losango(-745, 175, 30, "#3B82F666", 1.0, 20, dur, 44))

    # ── 18 estrelas e 5 aneis de pulso ───────────────────────────────────
    c += _estrelas(18, dur)
    c += _aneis_pulso(dur)

    # ── tres halos girando :201-243 ──────────────────────────────────────
    c += _halo(250, "#3B82F622", "#3B82F6", -135, 2.0, 0.8, 0.40, dur)
    c += _halo(300, "#8b5cf615", "#8b5cf6", 45, 1.0, -0.56, 0.40, dur)
    c += _halo(190, "#3b82f618", "#3b82f6", 135, 1.0, 1.04, 0.24, dur)

    # ── logo :263-282 — 1.8x com blur 25 que fecha em nitido ─────────────
    # `blur` nao chega em `imagem` (so `_pintar_forma` o le), entao o
    # blur-to-sharp vira uma bolha de luz que encolhe junto e apaga.
    c.append(brilho(0, Y_LOGO, 300, MARCA, 0.0, 0.30, 7))
    mola_logo = {"damping": 12, "stiffness": 80, "mass": 0.6}
    c.append({
        "tipo": "elipse", "rx": 190, "ry": 62, "x": 0, "y": Y_LOGO,
        "cor": {"tipo": "radial", "cores": ["#DDE9FFAA", "#00000000"],
                "raio": 190},
        "opacidade": [[0, 0], [0.20, 0.55], [0.78, 0.0]],
        "escala": {"mola": mola_logo, "em": T_LOGO, "de": 1.8, "para": 1.0},
    })
    c.append({
        "tipo": "imagem", "src": asset("logo-white.png"),
        "larg": 220, "alt": 46, "ajuste": "caber",
        **viva(0, Y_LOGO, 8, 31), "opacidade": [[0, 0, "outCubic"], [0.62, 1.0]],
        "escala": {"mola": mola_logo, "em": T_LOGO, "de": 1.8, "para": 1.0},
    })

    # ── VISUAL :285-303 — 200px/900, letter-spacing -0.06em ──────────────
    c.append(brilho(0, Y_VISUAL, 520, MARCA, T_VISUAL, 0.22, 13))
    c.append({          # o fantasma da entrada de escala 3 com blur 20 (:299)
        # texto nao le `blur` — o borrado sai de uma `sombra` sem deslocamento
        # sobre preenchimento transparente: fica so a mascara do glifo borrada.
        "tipo": "texto", "texto": "VISUAL", "tamanho": 200, "peso": 900,
        "cor": "#00000000", "espacamento": -12, "x": 0, "y": Y_VISUAL,
        "sombra": [{"x": 0, "y": 0, "blur": 60, "cor": "#FFFFFF"}],
        "opacidade": [[T_VISUAL, 0], [T_VISUAL + 0.13, 0.45],
                      [T_VISUAL + 0.52, 0.0]],
        "rotacao": [[T_VISUAL, -8.0, "outCubic"], [T_VISUAL + 0.7, 0.0]],
        "escala": {"mola": {"damping": 10, "stiffness": 80, "mass": 0.6},
                   "em": T_VISUAL, "de": 3.0, "para": 1.0},
    })
    c += _letras("VISUAL", T_VISUAL, Y_VISUAL, 200, TEXTO, esp=-12,
                 halo=(80, "#3B82F633"))

    # ── AI :305-330 — 280px italico, degrade, desliza 400px da direita ───
    c.append(brilho(0, Y_AI, 420, MARCA, T_AI, 0.28, 17))
    mola_ai = {"damping": 12, "stiffness": 60, "mass": 0.5}
    for i, (ch, u) in enumerate((("A", 0.0), ("I", 1.0))):
        base_x = (-19.6, 95.2)[i]
        c.append({
            "tipo": "texto", "texto": ch, "tamanho": 280, "peso": 900,
            "italico": True, "cor": _lerp_cor(MARCA, CIANO, u),
            "x": {"mola": mola_ai, "em": T_AI, "de": base_x + 400,
                  "para": base_x},
            "y": Y_AI, "opacidade": entra(T_AI, 0.3),
            "sombra": [{"x": 0, "y": 0, "blur": 60, "cor": "#3B82F644"}],
        })
    c.append({                        # a mesma copia borrada saindo (blur 15)
        "tipo": "texto", "texto": "AI", "tamanho": 280, "peso": 900,
        "italico": True, "cor": "#00000000", "espacamento": -22,
        "sombra": [{"x": 0, "y": 0, "blur": 44, "cor": MARCA}],
        "x": {"mola": mola_ai, "em": T_AI, "de": 400, "para": 0}, "y": Y_AI,
        "opacidade": [[T_AI, 0], [T_AI + 0.18, 0.5], [T_AI + 0.72, 0.0]],
    })

    # ── risco :333-352 — "M 0 0 Q 200 -20 400 0 Q 600 20 800 0" a 0.6 ────
    # `traco` corre o contorno: o path fica sem `cor` e a pena o percorre.
    c.append({
        "tipo": "path", "d": "M 0 0 Q 120 -12 240 0 Q 360 12 480 0",
        "contorno": MARCA, "contorno_larg": 3, "x": 0, "y": Y_RISCO,
        "traco": [[T_RISCO0, 0.0, "outCubic"], [T_RISCO1, 1.0]],
        "opacidade": [[T_RISCO0, 0.0, "outCubic"], [T_RISCO1, 1.0]],
    })

    # ── "The Generative" :355-373 — 28px, 0.25em, sobe 30px ──────────────
    sub = rotulo("THE GENERATIVE", T_SUB, Y_SUB, MUDO, 28, 0, 7, 400)
    sub["y"] = sobe(T_SUB, Y_SUB, 30, 0.5)
    c.append(sub)

    # ── "Playground" :375-397 — 90px italico, degrade, a mola do destaque ─
    c.append(brilho(0, Y_PLAY, 300, CIANO, T_PLAY, 0.20, 23))
    c += _letras("Playground", T_PLAY, Y_PLAY, 90, MARCA, italico=True,
                 esp=-2.7, mola=MOLA_DESTAQUE, de=0.30, c2=CIANO,
                 halo=(30, "#3B82F655"))

    # ── "for creators" :399-416 — 22px italico, sobe 15px ────────────────
    cri = rotulo("for creators", T_CRIA, Y_CRIA, "#a1a1aacc", 22, 0, 2, 700)
    cri["italico"] = True
    cri["y"] = sobe(T_CRIA, Y_CRIA, 15, 0.5)
    c.append(cri)

    # ── o push-in de cena :39-41 — scale 1 -> 1.06 em out(quad) ──────────
    empurra = [[0, 1.0, "outQuad"], [dur, 1.06]]
    for cam in c:
        cam.setdefault("escalaX", empurra)
        cam.setdefault("escalaY", empurra)

    return {"duracao": dur, "fundo": BG, "camadas": c}
