# -*- coding: utf-8 -*-
"""outro.py — a cena Outro do CreativlyBrandVideo.

O fecho de marca sobre #050505 (:114 backgroundColor COLORS.bg): o logo de sete
circulos montando-se um a um dentro de um halo de 200 px que se desenha entre os
frames 5 e 45 (:56-59, :204-215), "creativly" 130px branco letra a letra e ".ai"
130px italico em degrade azul-ciano (:220-266), a assinatura "the future of
creation" (:269-290) e o botao "Start Creating" com o "free" e o risco de 500 px
que corre do frame 40 ao 60 (:293-345).

A coluna inteira entra numa mola 0.6 -> 1 (:43-48): como o motor escala em torno
da origem da propria camada, o zoom de grupo virou POSICAO multiplicada pela mola
mais `escalaX/escalaY` na mesma mola — o produto e o transform do grupo. Fundo:
aurora de 3 blobs (:119-123), duas esferas 3D de aro (:133-134), tres losangos
(:137-139), 14 faiscas de 4 pontas (:142-166), 5 aneis de pulso maxSize 1600
(:168) e o brilho central que respira em 0.6 + 0.15*ruido (:54, :170-182).
"""
import math

from .base import *

__all__ = ["cena"]

# ── tempos do original, em segundos (frame / 30) ─────────────────────────
T_LOGO = 0.0            # :43-48  logoSpr sem atraso
T_NOME = 5 * F          # :80-84  nameSpr, Sequence from 5
T_AI = 15 * F           # :87-91  aiSpr
T_TAG = 18 * F          # :269-271 tagSpr
T_CTA = 25 * F          # :95-99  ctaSpr
T_FREE = 35 * F         # :105-109 freeSpr
T_HALO0, T_HALO1 = 5 * F, 45 * F     # :56-58  haloDraw
T_RISCO0, T_RISCO1 = 40 * F, 60 * F  # :61-63  ctaDraw

# ── a coluna central, medida do flex do original (gap 30, :184-194) ──────
# logo 300x334 / 30 / linha do nome 196.3 / 30 / tag 26.6 com marginTop -15 /
# 30 / botao 114.8 + 12 + risco 6. Soma 764.7, centrada em 1080 -> topo 157.65,
# e o centro da coluna cai EXATAMENTE no centro do quadro (y=0).
Y_LOGO = 215.4          # centro do bloco do logo
Y_NOME = -79.8          # centro da linha "creativly.ai"
Y_TAG = -206.3
Y_CTA = -307.0          # centro do botao
Y_FREE = -315.0
Y_RISCO = -379.4
Y_GLOW = 54.0           # :173 top 45% -> 540 - 486

# ── medidas do bloco de texto ────────────────────────────────────────────
TAM_NOME = 130          # :228 fontSize 130
ESP_NOME = -0.05 * TAM_NOME     # :231 letterSpacing -0.05em
PAD_AI = 0.3 * TAM_NOME         # :255 padding "0.15em 0.3em"
TAM_CTA = 42            # :304
TAM_FREE = 20           # :319

L_NOME = larg_texto("creativly", TAM_NOME) + 9 * ESP_NOME
L_AI = larg_texto(".ai", TAM_NOME) + 3 * ESP_NOME
X0_NOME = -(L_NOME + L_AI + 2 * PAD_AI) / 2
X_NOME = X0_NOME + L_NOME / 2
X_AI = X0_NOME + L_NOME + PAD_AI + L_AI / 2

L_BTN = larg_texto("Start Creating", TAM_CTA) + 160     # :298 padding 32px 80px
A_BTN = TAM_CTA * 1.21 + 64
L_FREE = larg_texto("free", TAM_FREE)
X0_CTA = -(L_BTN + 15 + L_FREE + 0.6 * TAM_FREE) / 2    # :295 gap 15
X_BTN = X0_CTA + L_BTN / 2
X_FREE = X0_CTA + L_BTN + 15 + 0.3 * TAM_FREE + L_FREE / 2

# molas do original, na notacao do motor
M_COLUNA = {"damping": 14, "stiffness": 60, "mass": 0.5}    # :43-48
M_LOGO = {"damping": 12, "stiffness": 100, "mass": 0.8}     # CreativlyLogo:79
M_NOME = {"damping": 12, "stiffness": 80, "mass": 0.5}      # :80-84
M_LETRA = {"damping": 14, "stiffness": 100, "mass": 0.5}    # :239
M_AI = {"damping": 10, "stiffness": 100, "mass": 0.4}       # :87-91
M_CTA = {"damping": 14, "stiffness": 80, "mass": 0.5}       # :95-99
M_FREE = {"damping": 16, "stiffness": 100, "mass": 1.0}     # :105-109
ESC_COL = {"mola": M_COLUNA, "em": 0.0, "de": 0.6, "para": 1.0}


# ── o spring do original, integrado passo a passo ────────────────────────
# Formula fechada da valores PROXIMOS, nao iguais, e a diferenca mora no comeco
# da animacao — que e onde o olho olha. Entao repito o loop, como o anim.py faz.
def _avanca(cur, vel, last, now, damping, mass, stiffness):
    dt = min(now - last, 64.0) / 1000.0
    v0, x0 = -vel, 1.0 - cur
    zeta = damping / (2 * math.sqrt(stiffness * mass))
    w0 = math.sqrt(stiffness / mass)
    if zeta < 1:
        w1 = w0 * math.sqrt(1 - zeta * zeta)
        s1, c1 = math.sin(w1 * dt), math.cos(w1 * dt)
        env = math.exp(-zeta * w0 * dt)
        frag = env * (s1 * ((v0 + zeta * w0 * x0) / w1) + x0 * c1)
        return (1.0 - frag,
                zeta * w0 * frag
                - env * (c1 * (v0 + zeta * w0 * x0) - w1 * x0 * s1))
    env = math.exp(-w0 * dt)
    return (1.0 - env * (x0 + (v0 + w0 * x0) * dt),
            env * (v0 * (dt * w0 - 1) + dt * x0 * w0 * w0))


def _spr(t: float, cfg: dict, em: float = 0.0) -> float:
    """Valor da mola `cfg` no instante `t`, comecando em `em`."""
    frame = max(0.0, (t - em) * FPS)
    cur, vel, last = 0.0, 0.0, 0.0
    for f in range(int(math.floor(frame)) + 1):
        now = (f / FPS) * 1000.0
        cur, vel = _avanca(cur, vel, last, now, cfg["damping"], cfg["mass"],
                           cfg["stiffness"])
        last = now
    return cur


def _col(t: float) -> float:
    """:48 logoScale — a coluna inteira sai de 0.6 e chega em 1."""
    return 0.6 + 0.4 * _spr(t, M_COLUNA)


def _amostrar(fn, dur, fino=1.2, p1=2 * F, p2=5 * F, casas=2):
    """Keyframes de uma funcao: passo curto enquanto a mola corre, longo depois."""
    ks, t = [], 0.0
    while t < dur - 1e-6:
        ks.append([round(t, 4), round(fn(t), casas)])
        t += p1 if t < fino else p2
    ks.append([round(dur, 4), round(fn(dur), casas)])
    return ks


def _rnd(k: float) -> float:
    """O `random(seed)` do Remotion: determinista e espalhado."""
    x = math.sin(k * 127.1 + 311.7) * 43758.5453
    return x - math.floor(x)


def _lerp_cor(a: str, b: str, u: float) -> str:
    """linear-gradient(135deg, #3B82F6, #06B6D4) resolvido POR LETRA — o motor
    pinta texto com uma cor so, entao o degrade vira a rampa da palavra."""
    u = max(0.0, min(1.0, u))
    ca = [int(a[1 + 2 * i:3 + 2 * i], 16) for i in range(3)]
    cb = [int(b[1 + 2 * i:3 + 2 * i], 16) for i in range(3)]
    return "#" + "".join(f"{int(ca[i] + (cb[i] - ca[i]) * u):02X}" for i in range(3))


# ── algebra 3x3 para a projecao ortografica das esferas ──────────────────
def _mul(m, n):
    return [[sum(m[i][k] * n[k][j] for k in range(3)) for j in range(3)]
            for i in range(3)]


def _rx(g):
    c, s = math.cos(math.radians(g)), math.sin(math.radians(g))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _ry(g):
    c, s = math.cos(math.radians(g)), math.sin(math.radians(g))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def _aro(raio, vel, giro, dur, passo=4 * F):
    """Circulo de raio R sob Rx(f*0.5*v)*Ry(f*0.8*v)*giro, projetado.

    O projetado de um circulo e uma elipse: os semi-eixos saem dos valores
    singulares de [u|v] e a inclinacao de meia-arctan — que e exatamente o que
    `rx`, `ry` e `rotacao` pedem. Desenrolo o angulo em multiplos de 180 (a
    elipse e simetrica) senao a volta do arctan da um pinote entre keyframes.
    """
    krx, kry, kro, ant = [], [], [], 0.0
    for i in range(int(dur / passo) + 2):
        t = min(i * passo, dur)
        f = t * FPS
        m = _mul(_mul(_rx(f * 0.5 * vel), _ry(f * 0.8 * vel)), giro)
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
    """:133-134 Rotating3DSphere — 5 aros verticais (rotateY) + 5 horizontais
    (rotateX, 1px e metade da opacidade). Entrada damping 14 stiffness 60,
    escala 0.5 -> 1."""
    raio, t0 = tam / 2.0, atraso * F
    mola = {"mola": {"damping": 14, "stiffness": 60, "mass": 1.0},
            "em": t0, "de": 0.5, "para": 1.0}
    out = []
    for fam in ("v", "h"):
        for i in range(5):
            g = (i / 5.0) * 180.0
            krx, kry, kro = _aro(raio, vel, _ry(g) if fam == "v" else _rx(g), dur)
            out.append({
                "tipo": "elipse", "rx": krx, "ry": kry, "rotacao": kro,
                "cor": "#00000000", "contorno": cor,
                "contorno_larg": 1.5 if fam == "v" else 1.0,
                **viva(cx, cy, 4, s + i + (0 if fam == "v" else 40)),
                "opacidade": [[t0, 0, "outCubic"],
                              [t0 + 0.5, 1.0 if fam == "v" else 0.5]],
                "escala": mola})
    return out


def _losango(cx, cy, tam, cor, vel, atraso, dur, s):
    """:137-139 FloatingDiamond — quadrado em rotate(45deg) sob rotateX(f*1.5*v)
    e rotateY(f*2*v). O 45 vai ASSADO no path: no motor a escala vem DEPOIS da
    rotacao e no CSS vem antes, e com `rotacao` o losango cisalharia."""
    d = tam * 0.7071
    kx, ky = [], []
    for i in range(int(dur / (2 * F)) + 2):
        t = min(i * 2 * F, dur)
        f = t * FPS
        kx.append([round(t, 4),
                   round(max(0.07, abs(math.cos(math.radians(f * 2.0 * vel)))), 3)])
        ky.append([round(t, 4),
                   round(max(0.07, abs(math.cos(math.radians(f * 1.5 * vel)))), 3)])
    t0 = atraso * F
    return {
        "tipo": "path", "d": f"M 0 {-d:.1f} L {d:.1f} 0 L 0 {d:.1f} L {-d:.1f} 0 Z",
        "cor": cor, "contorno": cor, "contorno_larg": 1,
        **viva(cx, cy, 12, s), "escalaX": kx, "escalaY": ky,
        "opacidade": [[t0, 0, "outCubic"], [t0 + 0.53, 0.8]],
        "escala": {"mola": {"damping": 16, "stiffness": 80, "mass": 1.0},
                   "em": t0, "de": 0.0, "para": 1.0}}


def _estrela_d(r, ri, pontos=4):
    p = []
    for j in range(2 * pontos):
        a = math.radians(-90 + j * 180.0 / pontos)
        rr = r if j % 2 == 0 else ri
        p.append(f"{rr * math.cos(a):.2f} {rr * math.sin(a):.2f}")
    return "M " + " L ".join(p) + " Z"


def _faiscas(n, dur):
    """:29-34 e :142-166 — estrelas de 4 pontas PREENCHIDAS, innerRadius 30% do
    outer, num svg de 3x o tamanho (logo raio de tela = tam*1.5). Deriva de
    ruido +-20 px, giro de f*speed*2 graus e opacidade sin(f*0.05+i*2)*0.3+0.5
    multiplicada por 0.2 (:158). O drop-shadow de 2px virou `blur`."""
    out = []
    for i in range(n):
        px, py = _rnd(i * 7 + 1) * 100, _rnd(i * 7 + 2) * 100
        tam = _rnd(i * 7 + 3) * 4 + 1.5
        vel = _rnd(i * 7 + 4) * 0.5 + 0.2
        bx, by = px / 100 * W - W / 2, H / 2 - py / 100 * H
        op, t = [], 0.0
        while t < dur:
            v = (math.sin(t * FPS * 0.05 + i * 2) * 0.3 + 0.5) * 0.2
            op.append([round(t, 3), round(max(0.0, v), 4)])
            t += 0.18
        op.append([round(dur, 3), 0.1])
        out.append({
            "tipo": "path", "d": _estrela_d(tam * 1.5, tam * 0.45),
            "cor": MARCA, "blur": 2, **viva(bx, by, 20, 400 + i),
            "rotacao": [[0, 0.0, "linear"], [dur, round(dur * FPS * vel * 2, 1)]],
            "opacidade": op})
    return out


def _aneis(dur, n=5, cor="#3B82F612", maxi=1600.0, vel=0.25):
    """:168 PulseRings count 5 maxSize 1600 speed 0.25 -> ciclo de 120 frames.
    Nasce no centro, chega a 800 de raio e some; a opacidade sobe a 0.8 em 20%
    do ciclo. Anel = cor transparente + contorno; forma cheia comeria o quadro."""
    ciclo = FPS / vel * F
    out = []
    for i in range(n):
        raio, op, k = [], [], -1
        while True:
            t0 = k * ciclo - (i / n) * ciclo
            if t0 > dur:
                break
            t1 = t0 + ciclo
            raio += [[round(t0, 4), 0.0, "linear"],
                     [round(t1 - 1e-3, 4), maxi / 2, "linear"]]
            op += [[round(t0, 4), 0.0, "linear"],
                   [round(t0 + 0.2 * ciclo, 4), 0.8, "linear"],
                   [round(t1 - 1e-3, 4), 0.0, "linear"]]
            k += 1
        raio[-1], op[-1] = raio[-1][:2], op[-1][:2]
        out.append({"tipo": "elipse", "raio": raio, "cor": "#00000000",
                    "contorno": cor, "contorno_larg": 1, "opacidade": op})
    return out


def _aurora(dur):
    """:119-123 + AuroraBackground — 3 blobs de 60% do quadro, cada um andando
    em sin/cos de t=segundos*0.3, com escalaX/escalaY proprias, blur 80 e
    opacidade 0.2 depois de uma rampa de 30 frames."""
    out = []
    for i, cor in enumerate((MARCA, PRIMARIA, SECUNDARIA)):
        def _p(t, i=i):
            return t * 0.3 + i * 2 * math.pi / 3

        out.append({
            "tipo": "elipse", "raio": W * 0.3,
            "cor": {"tipo": "radial", "raio": W * 0.3, "paradas": [0.0, 0.3, 0.7],
                    "cores": [cor + "66", cor + "22", "#00000000"]},
            "blur": 80,
            "x": _amostrar(lambda t, i=i: (50 + math.sin(_p(t, i)) * 25
                                           + math.cos(_p(t, i) * 0.7 + i) * 10)
                           / 100 * W - W / 2, dur, 0, 3 * F, 3 * F),
            "y": _amostrar(lambda t, i=i: H / 2 - (50 + math.cos(_p(t, i) * 0.8) * 20
                                                   + math.sin(_p(t, i) * 1.3 + i * 2) * 8)
                           / 100 * H, dur, 0, 3 * F, 3 * F),
            "escalaX": _amostrar(lambda t, i=i: 1 + math.sin(t * 0.3 * 0.5 + i * 1.5) * 0.3,
                                 dur, 0, 3 * F, 3 * F, 3),
            "escalaY": _amostrar(lambda t, i=i: (1 + math.cos(t * 0.3 * 0.7 + i) * 0.2) * 0.5625,
                                 dur, 0, 3 * F, 3 * F, 3),
            "opacidade": [[0, 0.0, "linear"], [1.0, 0.2]]})
    return out


# ── o logo: 7 circulos que se montam (CreativlyLogo.tsx:6-16, :62-108) ───
_CIRCULOS = [(52.58, 17.07), (17.03, 37.8), (88.12, 37.8), (52.58, 58.54),
             (17.03, 79.27), (88.12, 79.27), (52.58, 100.01)]
_ESCALA_LOGO = 300.0 / 106.0      # :214 CreativlyLogo size 300, viewBox 106x118
_RAIO_LOGO = 17.03 * _ESCALA_LOGO
_DESLOC = 60.0 * _ESCALA_LOGO     # :101 yOffset 60 -> 0


def _logo(dur):
    """Cada circulo entra com atraso de 2 frames, escala 0 -> 1, e o `g` gira
    -90 -> 0 EM TORNO da propria ancora enquanto o circulo esta deslocado 60
    para baixo (:96-107). Isso nao e uma reta: e um arco, e por isso x e y saem
    amostrados em vez de mola. A escala da coluna entra multiplicando a posicao
    (`escalaX/escalaY` cuidam do tamanho) — o produto e o transform do grupo."""
    out = []
    for i, (cx, cy) in enumerate(_CIRCULOS):
        bx = (cx - 53.0) * _ESCALA_LOGO
        by = -(cy - 59.0) * _ESCALA_LOGO + Y_LOGO
        em = i * 2 * F

        def _pos(t, bx=bx, by=by, em=em, i=i):
            p = _spr(t, M_LOGO, em)
            q, ang = 1.0 - p, math.radians(-90.0 * (1.0 - p))
            d = _DESLOC * q
            # :51-52 logoFloat — o bloco inteiro vagando +-5 px
            fx = 5.0 * math.sin(t * 0.9 + i * 0.4)
            fy = 2.5 * math.cos(t * 0.7 + i * 0.4)
            return ((bx - d * math.sin(ang) + fx) * _col(t),
                    (by - d * math.cos(ang) + fy) * _col(t))

        out.append({
            "tipo": "elipse", "raio": round(_RAIO_LOGO, 2), "cor": TEXTO,
            "x": _amostrar(lambda t, f=_pos: f(t)[0], dur),
            "y": _amostrar(lambda t, f=_pos: f(t)[1], dur),
            "escala": {"mola": M_LOGO, "em": em, "de": 0.0, "para": 1.0},
            "escalaX": ESC_COL, "escalaY": ESC_COL,
            "opacidade": _amostrar(
                lambda t, em=em: min(1.0, _spr(t, M_LOGO, em) / 0.3)
                * _spr(t, M_COLUNA), dur, casas=3)})
    return out


def _peso_cor(dur, quente: bool):
    """:72-77 ringColor interpola brand -> primary -> secondary -> brand nos
    frames 0/40/80/120. brand e primary sao o MESMO hex, entao a troca real e
    azul -> roxo -> azul: duas copias cruzando por opacidade dao a mesma cor."""
    a, b, c = 40 * F, 80 * F, 120 * F
    v = (1.0, 1.0, 0.0, 1.0) if quente else (0.0, 0.0, 1.0, 0.0)
    return [[0, v[0], "linear"], [a, v[1], "linear"], [b, v[2], "linear"], [c, v[3]]]


def cena(dur: float) -> dict:
    c: list[dict] = []

    # ── aurora de 3 blobs + a vinheta radial de :125-130 ─────────────────
    c += _aurora(dur)
    c.append({"tipo": "retangulo", "larg": W, "alt": H,
              "cor": {"tipo": "radial", "raio": 1100, "cores": [BG_SUP, BG]},
              "opacidade": 0.7})

    # ── brilho central que respira :170-182 — 0.6 + 0.15*ruido, blur 80 ──
    c.append({
        "tipo": "elipse", "raio": 400, "blur": 80, "y": Y_GLOW,
        "cor": {"tipo": "radial", "raio": 400, "paradas": [0.0, 0.4, 0.7],
                "cores": ["#3B82F640", "#06B6D428", "#00000000"]},
        "escala": pulso(0.6, 0.15, 0.02, 41),
        "opacidade": [[0, 0, "outCubic"], [0.9, 1.0]]})

    # ── duas esferas 3D :133-134 ─────────────────────────────────────────
    c += _esfera(-760, 340, 140, "#3B82F620", 0.5, 3, dur, 120)
    c += _esfera(690, -260, 90, "#3b82f615", 0.8, 8, dur, 300)

    # ── tres losangos :137-139 (x,y do CSS sao o canto: +tam/2) ──────────
    c.append(brilho(-640, -280, 130, MARCA, 5 * F, 0.16, 51))
    c.append(brilho(-792, 122, 120, MARCA, 15 * F, 0.14, 52))
    c.append(_losango(-640, -280, 40, "#3B82F630", 0.6, 5, dur, 11))
    c.append(_losango(552, 277, 25, "#8b5cf625", 1.0, 10, dur, 22))
    c.append(_losango(-792, 122, 35, "#3B82F620", 0.8, 15, dur, 33))

    # ── 14 faiscas e os 5 aneis de pulso ─────────────────────────────────
    c += _faiscas(14, dur)
    c += _aneis(dur)

    # ── o halo de 200 px :204-212 ────────────────────────────────────────
    # Anel = cor "#00000000" + contorno: forma preenchida nao tem contorno pra
    # correr, e o preenchimento comeria o logo inteiro.
    halo_y = _amostrar(lambda t: Y_LOGO * _col(t), dur)
    c.append({"tipo": "elipse", "raio": 200, "cor": "#00000000",
              "contorno": MARCA, "contorno_larg": 1, "x": 0, "y": halo_y,
              "escalaX": ESC_COL, "escalaY": ESC_COL,
              "opacidade": [[0, 0, "outCubic"], [0.5, 0.09]]})
    for quente, cor in ((True, MARCA), (False, SECUNDARIA)):
        peso = _peso_cor(dur, quente)
        c.append({
            "tipo": "elipse", "raio": 200, "cor": "#00000000", "contorno": cor,
            "contorno_larg": 2, "x": 0, "y": halo_y,
            "escalaX": ESC_COL, "escalaY": ESC_COL,
            "traco": [[T_HALO0, 0.0, "outCubic"], [T_HALO1, 1.0]],
            "opacidade": [[k[0], round(k[1] * 0.3, 3)] + k[2:] for k in peso]})

    # ── logo :213-215 — drop-shadow 0 0 80px brand66 + os 7 circulos ─────
    c.append(brilho(0, Y_LOGO, 300, MARCA, 0.0, 0.34, 7))
    c += _logo(dur)

    # ── "creativly" :224-243 — 130px/900, CharacterReveal stagger 2 ──────
    # offsetY 40 por letra, mais os 30 px do bloco (nameSpr), tudo multiplicado
    # pela mola da coluna. O textShadow de 80px vai no campo `sombra`.
    x = X_NOME - (L_NOME) / 2
    for i, ch in enumerate("creativly"):
        w = larg_char(ch, TAM_NOME) + ESP_NOME
        em = T_NOME + i * 2 * F
        cx = x + w / 2

        def _y(t, em=em):
            return (Y_NOME - 40.0 * (1.0 - _spr(t, M_LETRA, em))
                    - 30.0 * (1.0 - _spr(t, M_NOME, T_NOME))) * _col(t)

        c.append({
            "tipo": "texto", "texto": ch, "tamanho": TAM_NOME, "peso": 900,
            "cor": TEXTO, "sombra": [{"x": 0, "y": 0, "blur": 80,
                                      "cor": "#3B82F633"}],
            "x": _amostrar(lambda t, cx=cx: cx * _col(t), dur, 0.9),
            "y": _amostrar(_y, dur, 1.4),
            "escalaX": ESC_COL, "escalaY": ESC_COL,
            "opacidade": _amostrar(
                lambda t, em=em: _spr(t, M_LETRA, em) * _spr(t, M_NOME, T_NOME)
                * _spr(t, M_COLUNA), dur, 1.4, casas=3)})
        x += w
    # O fantasma desfocado da CharacterReveal (blur 8*(1-spr), :55). Vai BEM
    # borrado de proposito: as letras acima sao posicionadas por larg_char e a
    # palavra inteira e medida pelo Skia — com blur pequeno as duas larguras
    # nao batem e o fantasma le como texto duplicado, nao como bloom.
    c.append({
        "tipo": "texto", "texto": "creativly", "tamanho": TAM_NOME, "peso": 900,
        "cor": TEXTO, "espacamento": ESP_NOME, "blur": 26, "x": X_NOME,
        "y": Y_NOME, "escalaX": ESC_COL, "escalaY": ESC_COL,
        "opacidade": [[T_NOME, 0.0], [T_NOME + 0.18, 0.32, "outCubic"],
                      [T_NOME + 0.8, 0.0]]})

    # ── ".ai" :245-264 — 130px italico, degrade, mola 0.3 -> 1 e sobe 20 ─
    esc_ai = {"mola": M_AI, "em": T_AI, "de": 0.3, "para": 1.0}
    c.append({
        "tipo": "texto", "texto": ".ai", "tamanho": TAM_NOME, "peso": 900,
        "italico": True, "cor": MARCA, "espacamento": ESP_NOME, "blur": 15,
        "x": X_AI, "y": Y_NOME, "escala": esc_ai,
        "escalaX": ESC_COL, "escalaY": ESC_COL,
        "opacidade": [[T_AI, 0.0, "outCubic"], [T_AI + 0.4, 0.4]]})
    x = X_AI - L_AI / 2
    for i, ch in enumerate(".ai"):
        w = larg_char(ch, TAM_NOME) + ESP_NOME
        c.append({
            "tipo": "texto", "texto": ch, "tamanho": TAM_NOME, "peso": 900,
            "italico": True, "cor": _lerp_cor(MARCA, CIANO, i / 2.0),
            "x": x + w / 2, "escala": esc_ai,
            "escalaX": ESC_COL, "escalaY": ESC_COL,
            "y": {"mola": M_AI, "em": T_AI, "de": Y_NOME - 20, "para": Y_NOME},
            "opacidade": entra(T_AI, 0.3)})
        x += w

    # ── "the future of creation" :269-290 — 22px italico, 0.15em ─────────
    tag = rotulo("the future of creation", T_TAG, Y_TAG, MUDO, 22, 0, 3, 400)
    tag["italico"] = True
    tag["y"] = sobe(T_TAG, Y_TAG, 10, 0.45)
    tag["escalaX"] = ESC_COL
    tag["escalaY"] = ESC_COL
    c.append(tag)

    # ── o botao :296-312 — padding 32/80, raio 100, degrade, sombra azul ─
    c.append(brilho(X_BTN, Y_CTA, 430, MARCA, T_CTA, 0.20, 61))
    c.append(brilho(X_BTN, Y_CTA, 250, MARCA, T_CTA, 0.28, 62))
    grad = {"tipo": "linear", "cores": [MARCA, CIANO],
            "de": [-L_BTN / 2, -A_BTN / 2], "para": [L_BTN / 2, A_BTN / 2]}
    esc_cta = {"mola": M_CTA, "em": T_CTA, "de": 0.8, "para": 1.0}
    # ctaBlur 8 -> 0 (:100): `blur` nao e animavel, entao vira uma copia
    # desfocada que cruza com a nitida.
    c.append({"tipo": "retangulo", "larg": L_BTN, "alt": A_BTN, "raio": 100,
              "cor": grad, "blur": 9, "x": X_BTN, "y": Y_CTA,
              "escala": esc_cta,
              "opacidade": [[T_CTA, 0.0], [T_CTA + 0.16, 0.55, "outCubic"],
                            [T_CTA + 0.7, 0.0]]})
    c.append({"tipo": "retangulo", "larg": L_BTN, "alt": A_BTN, "raio": 100,
              "cor": grad, **viva(X_BTN, Y_CTA, 2, 63), "escala": esc_cta,
              # :102 ctaPulse — 1% de respiracao que nunca para
              "escalaX": pulso(1.0, 0.012, 0.03, 77),
              "escalaY": pulso(1.0, 0.012, 0.03, 78),
              "opacidade": entra(T_CTA, 0.35)})
    c.append({"tipo": "texto", "texto": "Start Creating", "tamanho": TAM_CTA,
              "peso": 900, "cor": "#000000", **viva(X_BTN, Y_CTA - 2, 2, 64),
              "escala": esc_cta, "opacidade": entra(T_CTA, 0.35)})

    # ── "free" :314-331 — 20px italico em degrade, sobe 10 ───────────────
    x = X_FREE - L_FREE / 2
    for i, ch in enumerate("free"):
        w = larg_char(ch, TAM_FREE)
        c.append({
            "tipo": "texto", "texto": ch, "tamanho": TAM_FREE, "peso": 700,
            "italico": True, "cor": _lerp_cor(MARCA, CIANO, i / 3.0),
            "x": x + w / 2,
            "y": {"mola": M_FREE, "em": T_FREE, "de": Y_FREE - 10,
                  "para": Y_FREE},
            "opacidade": entra(T_FREE, 0.3)})
        x += w

    # ── o risco de 500 px :334-344 — corre do frame 40 ao 60, opacidade .4 ─
    # `y` DESCE dentro de `linha`: aqui os dois pontos ficam em 0 e a camada
    # inteira e que sobe pelo `y`.
    for quente, cor in ((True, MARCA), (False, SECUNDARIA)):
        peso = _peso_cor(dur, quente)
        c.append({
            "tipo": "linha", "de": [-250, 0], "para": [250, 0],
            "contorno": cor, "contorno_larg": 2,
            **viva(0, Y_RISCO, 2, 65 + int(quente)),
            "traco": [[T_RISCO0, 0.0, "outCubic"], [T_RISCO1, 1.0]],
            "opacidade": [[k[0], round(k[1] * 0.4, 3)] + k[2:] for k in peso]})

    return {"duracao": dur, "fundo": BG, "camadas": c}
