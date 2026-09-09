# -*- coding: utf-8 -*-
"""opensource.py — a cena Open Source do CreativlyBrandVideo.

Fundo GitHub (#0D1117, :127) com chuva de matriz verde (:134) e grade de pontos
(:137-145); ao centro, o anel do logo desenhado a `traco` de f5 a f35 (:60-64) e
o octocat, depois o titulo partido "Open" 160 italico + "Source" 100 regular
(:356-405), a tagline em degrade (:408-431), a licenca (:434-468) e tres cartoes
de estatistica com contador (:471-644). O contador nao existe no motor: virou
cinco recortes do `interpolate(frame,[20,65],[0,12400],outCubic)` cruzando por
opacidade — estado vira tempo, como as pilulas da prova. As 26 estrelas de 4
pontas (:204-255) e os 5 losangos 3D (:258-312) sao camadas proprias, cada uma
com deriva de ruido propria; o losango projeta o rotateX/rotateY como |cos| em
escalaY/escalaX dentro de um grupo, para a escala vir DEPOIS do rotate(45deg).
"""
import math

from .base import *

# ── paleta desta cena: :127, :141, :440, :460, :531, :134 ────────────────
BG_GH = "#0D1117"          # :127  backgroundColor
VERDE = "#30d158"          # :86   glowGreen inicio/fim
VERDE_CLARO = "#4ade80"    # :87   glowGreen no meio (f50)
BORDA_GH = "#30363d"       # :141/:523  grade de pontos e borda dos cartoes
CINZA_GH = "#8b949e"       # :440  cor da licenca
AMARELO = "#f0c000"        # :531  estrela do contador
OURO = "#FFD600"           # :261  rgba(255,214,0,...) dos losangos

DUR_REF = 3.5              # DURATIONS.openSource


# ── utilidades locais ────────────────────────────────────────────────────
def _r(seed: float) -> float:
    """O mesmo `seededRandom` do MatrixRain (:3-6) — determinista e sem numpy."""
    x = math.sin(seed * 12.9898 + 78.233) * 43758.5453
    return x - math.floor(x)


def _estrela(pontos: int, ri: float, ro: float) -> str:
    """makeStar({points, innerRadius, outerRadius}) (:205) em `d` de SVG."""
    p = []
    for i in range(pontos * 2):
        a = -math.pi / 2 + i * math.pi / pontos
        r = ro if i % 2 == 0 else ri
        p.append((r * math.cos(a), r * math.sin(a)))
    return ("M %.2f %.2f " % p[0]) + " ".join("L %.2f %.2f" % q for q in p[1:]) + " Z"


def _cos_kf(grau_por_frame: float, dur: float, passo: int = 3) -> list:
    """|cos| amostrado — a projecao ortografica de um plano girando em X ou Y.

    O CSS gira em 3D (:194-196 do Rotating3D); o motor e 2D. Um quadrado plano
    girado de `a` graus em torno do eixo X aparece com altura `|cos a|`. Piso de
    0.04 porque escala 0 apaga a camada e o losango sumiria de vez na borda.
    """
    ks = []
    f = 0
    while f <= dur * FPS + passo:
        v = abs(math.cos(math.radians(f * grau_por_frame)))
        ks.append([round(f * F, 4), round(max(0.04, v), 4)])
        f += passo
    return ks


def _janela(t0: float, t1: float | None, entrada: float = 0.0) -> list:
    """Recorte de tempo de UM valor do contador. Sem `t1`, segura ate o fim."""
    if entrada:
        ks = [[t0, 0], [t0 + entrada, 1, "outCubic"]]
    else:
        ks = [[max(0.0, t0 - 0.01), 0], [t0, 1]]
    if t1 is not None:
        ks += [[t1 - 0.01, 1], [t1, 0]]
    return ks


# o octocat de :349 e os tres icones dos cartoes, em viewBox 24x24
ICONE_GITHUB = (
    "M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261"
    ".793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333"
    "-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834"
    " 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467"
    "-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322"
    " 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552"
    " 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221"
    " 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801"
    ".576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z")
ICONE_ESTRELA = ("M12 .587l3.668 7.568 8.332 1.151-6.064 5.828 1.48 8.279-7.416-3.967"
                 "-7.417 3.967 1.481-8.279-6.064-5.828 8.332-1.151z")
# :576 — o mesmo path, com os flags do arco SEPARADOS. No SVG "0 110-3.5" e
# large=1 sweep=1 x=0 y=-3.5 compactado; o tokenizador do motor le "110" como um
# numero so e o arco estoura. Separar e o unico jeito, e nao muda a figura.
ICONE_FORK = (
    "M12 21 a1.75 1.75 0 1 1 0 -3.5 a1.75 1.75 0 0 1 0 3.5 z"
    "m-3.25 -8.25 a1.75 1.75 0 1 1 -3.5 0 a1.75 1.75 0 0 1 3.5 0 z"
    "m12.5 0 a1.75 1.75 0 1 1 -3.5 0 a1.75 1.75 0 0 1 3.5 0 z"
    "M5.75 11.5 h.5 a.75 .75 0 0 1 .75 .75 v3 a.75 .75 0 0 1 -.75 .75"
    " h-.5 a.75 .75 0 0 1 -.75 -.75 v-3 a.75 .75 0 0 1 .75 -.75 z"
    "m6.25 -8 a1.75 1.75 0 1 1 0 3.5 a1.75 1.75 0 0 1 0 -3.5 z"
    "M12 4.75 a.75 .75 0 0 1 .75 .75 v5.75 a.75 .75 0 0 1 -1.5 0"
    " V5.5 a.75 .75 0 0 1 .75 -.75 z")
ICONE_GENTE = (
    "M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66"
    " 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 "
    "3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 "
    "1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z")

# alturas do bloco central, medidas do fluxo de :314-645
Y_LOGO = 205
Y_OPEN = 5
Y_SOURCE = -15
Y_TAG = -110
Y_LIC = -168
Y_ARCO = -220
Y_STAT = -256


def cena(dur: float) -> dict:
    c: list[dict] = []

    # ── chuva de matriz (:134, MatrixRain 50 colunas, 0.12, 16px) ────────
    # Seis camadas de nove copias, e nao 54 camadas: aqui `repetir` E o certo,
    # porque isto e textura de fundo. O `atraso` com ordem "aleatoria" e o que
    # espalha as colunas na VERTICAL — cada copia le a rampa de queda num
    # instante diferente, que e exatamente o `(frame*speed + offset) % ciclo`
    # de :57. Nove copias por camada e o teto: com treze, a mesma cadeia de
    # caracteres reaparecia a cada 148 px e o fundo virava papel de parede.
    ALFA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789{}[]()<>=/|@#$%&*+-~"
    for k in range(6):
        n = 10 + (k * 3) % 8
        txt = "\n".join(ALFA[int(_r(k * 31 + j * 7 + 1) * len(ALFA))]
                        for j in range(n))
        alt = n * 16 * 1.4
        c.append({
            "tipo": "texto", "texto": txt, "tamanho": 16, "peso": 400,
            "fonte": "monospace", "entrelinha": 1.4, "cor": VERDE,
            "x": -160 + k * 36,
            "y": [[-12, H / 2 + alt / 2, "linear"], [12, -H / 2 - alt / 2]],
            # opacidade CONSTANTE de proposito: `atraso` desloca o tempo LOCAL
            # de cada copia, entao um fade-in em keyframes deixaria toda coluna
            # com rank alto presa no 0 do inicio da rampa. Custou um render.
            # 0.09 e nao 0.12 porque no original cada caractere ainda leva o
            # proprio degrade de cauda (:106) — o valor cheio so vale na cabeca.
            "opacidade": 0.09,
            "repetir": {"cols": 9, "linhas": 1, "espX": 214, "espY": 0,
                        "atraso": 2.6 + k * 0.11, "ordem": "aleatorio"},
        })

    # ── grade de pontos 30px, #30363d, 0.15 (:137-145) ───────────────────
    c.append({
        "tipo": "elipse", "raio": 1.5, "cor": BORDA_GH,
        # 0.0004 x 2304 celulas = 0.9 s de onda irradiando do centro. Com o
        # 0.0015 que eu tinha, a borda da grade so acendia depois do fim da cena.
        "opacidade": [[0, 0, "outCubic"], [0.8, 0.20]],
        "repetir": {"cols": 64, "linhas": 36, "espX": 30, "espY": 30,
                    "atraso": 0.0004, "ordem": "centro"},
    })

    # ── marca d'agua "OPEN" 450px italica, -15deg (:147-173) ─────────────
    # Em degrade no original; texto do motor so aceita cor chapada, entao o
    # degrade vira uma cor por letra. Girar cada letra -15 em torno do proprio
    # centro E colocar os centros sobre a reta de -15 equivale a girar o bloco.
    esp_wm = 450 * 0.05
    largs_wm = [larg_char(ch, 450) for ch in "OPEN"]
    total_wm = sum(largs_wm) + esp_wm * 3
    dx = -total_wm / 2
    mola_wm = {"damping": 30, "stiffness": 40, "mass": 1.2}   # :106-110
    for i, ch in enumerate("OPEN"):
        cx = dx + largs_wm[i] / 2
        f = i / 3
        cor = ["#3B82F6", "#2B8FF3", "#1C9CD1", "#06B6D4"][i]
        c.append({
            "tipo": "texto", "texto": ch, "tamanho": 450, "peso": 900,
            "italico": True, "cor": cor, "rotacao": -15,
            "x": cx * math.cos(math.radians(15)),
            "y": cx * math.sin(math.radians(15)),
            "opacidade": [[2 * F, 0, "outCubic"], [1.1, 0.045]],
            "escala": {"mola": mola_wm, "em": 2 * F, "de": 0.8, "para": 1.0},
        })
        dx += largs_wm[i] + esp_wm

    # ── brilho verde central 700px, pulso 0.12+0.06*ruido (:175-187, :91) ─
    c.append({
        "tipo": "elipse", "raio": 350, "blur": 60,
        "cor": {"tipo": "radial", "cores": [VERDE, "#00000000"], "raio": 350},
        **viva(0, 0, 12, 41),
        "opacidade": pulso(0.13, 0.055, 0.02, 7),
    })
    # o ciclo de cor :84-88 (verde -> verde claro -> verde) vira uma segunda
    # mancha cruzando por opacidade: o motor nao interpola cor.
    c.append({
        "tipo": "elipse", "raio": 330, "blur": 60,
        "cor": {"tipo": "radial", "cores": [VERDE_CLARO, "#00000000"], "raio": 330},
        **viva(0, 0, 12, 63),
        "opacidade": [[0, 0], [50 * F, 0.11, "suave"], [105 * F, 0]],
    })
    # brilho de marca 500px em top 40% / left 55% (:189-201)
    c.append({
        "tipo": "elipse", "raio": 250, "blur": 80,
        "cor": {"tipo": "radial", "cores": [MARCA, CIANO, "#00000000"],
                "raio": 250, "paradas": [0, 0.4, 1]},
        **viva(96, 108, 16, 77),
        "opacidade": [[0, 0, "outCubic"], [1.0, 0.22]],
    })

    # ── 16 estrelas verdes de 4 pontas (:204-228) ────────────────────────
    for i in range(12):
        tam = _r(i * 3 + 2) * 5 + 2
        vel = _r(i * 7 + 5) * 0.3 + 0.15
        bx = (_r(i * 11 + 1) - 0.5) * W
        by = (_r(i * 13 + 4) - 0.5) * H
        c.append({
            "tipo": "path", "d": _estrela(4, tam * 0.45, tam * 1.5),
            "cor": VERDE, "blur": 2, **viva(bx, by, 15, 200 + i),
            "rotacao": [[0, 0, "linear"], [dur, dur * FPS * vel * 2]],
            "opacidade": pulso(0.10, 0.045, 0.012, 400 + i),
        })

    # ── 10 estrelas de marca (:231-255) ──────────────────────────────────
    for i in range(7):
        tam = _r(i * 5 + 9) * 6 + 3
        vel = _r(i * 9 + 6) * 0.25 + 0.1
        bx = (_r(i * 23 + 3) - 0.5) * W
        by = (_r(i * 29 + 8) - 0.5) * H
        c.append({
            "tipo": "path", "d": _estrela(4, tam * 0.5, tam * 1.5),
            "cor": MARCA, "blur": 3, **viva(bx, by, 18, 600 + i),
            "rotacao": [[0, 45, "linear"], [dur, 45 + dur * FPS * vel * 1.8]],
            "opacidade": pulso(0.135, 0.05, 0.01, 700 + i),
        })

    # ── 5 losangos 3D (:258-312) ─────────────────────────────────────────
    # css (left, top) -> centro da camada: x = px-960+t/2, y = 540-py-t/2
    # o alfa final e o do CSS vezes o `entrance * 0.8` do container (:243):
    # rgba(...,0.25) * 0.8 = 0.20, e nao 0.25 — sem isso o losango amarelo
    # chapava e virava o objeto mais brilhante do quadro.
    DIAM = [(50, OURO, 0.20, 120, 150, 0.8, 5, MARCA, True),
            (35, VERDE, 0.16, 1700, 200, 1.1, 8, VERDE, True),
            (45, OURO, 0.16, 1600, 800, 0.7, 12, MARCA, False),
            (30, VERDE, 0.20, 200, 750, 1.3, 10, VERDE, True),
            (25, OURO, 0.24, 960, 100, 0.9, 15, MARCA, False)]
    for i, (tam, cor, op, px, py, vel, atr, gcor, tem_luz) in enumerate(DIAM):
        x = px - W / 2 + tam / 2
        y = H / 2 - py - tam / 2
        t0 = atr * F
        mola_d = {"damping": 16, "stiffness": 80, "mass": 1.0}   # :224-227
        if tem_luz:
            c.append({
                "tipo": "elipse", "raio": tam * 1.5, "blur": 30,
                "cor": {"tipo": "radial", "cores": [gcor, "#00000000"],
                        "raio": tam * 1.5},
                **viva(x, y, 11, 820 + i),
                "opacidade": [[t0, 0, "outCubic"], [t0 + 0.6, 0.30]],
            })
        c.append({
            "tipo": "grupo", **viva(x, y, 11, 820 + i),
            "escala": {"mola": mola_d, "em": t0, "de": 0.0, "para": 1.0},
            "escalaY": _cos_kf(1.5 * vel, dur),     # rotateX -> altura
            "escalaX": _cos_kf(2.0 * vel, dur),     # rotateY -> largura
            "opacidade": {"mola": mola_d, "em": t0, "de": 0, "para": op},
            "camadas": [{"tipo": "retangulo", "larg": tam, "alt": tam,
                         "cor": cor, "rotacao": 45}],
        })

    # ── o logo: brilho, anel de fundo, anel desenhado, halo, octocat ─────
    mola_logo = {"damping": 14, "stiffness": 80, "mass": 0.5}     # :51-55
    c.append({
        "tipo": "elipse", "raio": 130, "blur": 40,
        "cor": {"tipo": "radial", "cores": ["#FFFFFF", "#00000000"], "raio": 130},
        **viva(0, Y_LOGO, 4, 91),
        "opacidade": pulso(0.10, 0.04, 0.015, 93),
    })
    c.append({          # :335 — anel apagado, rgba(255,255,255,0.1), 2px
        "tipo": "elipse", "raio": 78, "cor": "#00000000",
        "contorno": BORDA, "contorno_larg": 2,
        **viva(0, Y_LOGO, 4, 11),
        "opacidade": {"mola": mola_logo, "em": 0, "de": 0, "para": 1},
        "escala": {"mola": mola_logo, "em": 0, "de": 0.6, "para": 1.0},
    })
    c.append({          # :336 — o anel que corre, f5 -> f35 (:60-64)
        "tipo": "elipse", "raio": 78, "cor": "#00000000",
        "contorno": "#FFFFFF", "contorno_larg": 3,
        **viva(0, Y_LOGO, 4, 11),
        "traco": [[5 * F, 0.0, "outCubic"], [35 * F, 1.0]],
        "opacidade": {"mola": mola_logo, "em": 0, "de": 0, "para": 1},
        "escala": {"mola": mola_logo, "em": 0, "de": 0.6, "para": 1.0},
    })
    c.append({          # halo verde: o `blur(10px)->0` de :325 nao e animavel
        "tipo": "path", "d": ICONE_GITHUB, "cor": VERDE, "blur": 14,
        **viva(0, Y_LOGO, 4, 11), "escala": 3.1,
        "opacidade": [[0, 0], [0.5, 0.35, "outCubic"], [1.4, 0.12]],
    })
    c.append({          # :348 — o octocat, 70px branco. UNICO MOLA_DESTAQUE
        "tipo": "path", "d": ICONE_GITHUB, "cor": TEXTO,
        **viva(0, Y_LOGO, 4, 11),
        "escala": {"mola": MOLA_DESTAQUE, "em": 2 * F, "de": 1.75, "para": 2.917},
        "opacidade": {"mola": mola_logo, "em": 0, "de": 0, "para": 1},
    })

    # ── o titulo partido (:356-405): "Open" 160 italico 900 + "Source" 100 ─
    l_open = larg_texto("Open", 160)
    l_src = larg_texto("Source", 100)
    x0 = -(l_open + 20 + l_src) / 2
    c += titulo("Open", 3 * F, Y_OPEN, 160, TEXTO, 900, LETRA,
                x0 + l_open / 2, italico=True)
    c += titulo("Source", 9 * F, Y_SOURCE, 100, TEXTO, 400, LETRA,
                x0 + l_open + 20 + l_src / 2)

    # ── tagline "community driven" em degrade (:408-431) ─────────────────
    # 26px italico, letter-spacing 0.15em. O texto do motor nao aceita degrade
    # como `cor`, entao o degrade vira uma cor por pedaco — e o corte fica no
    # ESPACO entre as palavras. Cortar dentro da palavra tambem funcionava, mas
    # `larg_texto` e uma aproximacao em tres classes de largura e a costura
    # aparecia como um buraco no meio de "community".
    mola_tag = {"damping": 16, "stiffness": 100, "mass": 0.5}
    t_tag = 18 * F
    esp_tag = 26 * 0.15
    pedacos = ["community", " driven"]
    cores_tag = ["#3B82F6", "#0FADD4"]
    largs_tag = [larg_texto(p, 26) + esp_tag * len(p) for p in pedacos]
    dxt = -sum(largs_tag) / 2
    for i, p in enumerate(pedacos):
        c.append({
            "tipo": "texto", "texto": p, "tamanho": 26, "peso": 400,
            "italico": True, "cor": cores_tag[i], "espacamento": esp_tag,
            "x": dxt + largs_tag[i] / 2,
            "y": sobe(t_tag, Y_TAG, 10, 0.35),
            "opacidade": entra(t_tag, 0.3),
            "escala": {"mola": mola_tag, "em": t_tag, "de": 0.94, "para": 1.0},
        })
        dxt += largs_tag[i]

    # ── licenca (:434-468): 40px, molas em f12 / f16 / f20 ───────────────
    LIC = [("MIT License", CINZA_GH), ("|", BORDA_GH), ("Self-Hostable", CINZA_GH)]
    largs_lic = [larg_texto(t, 40) for t, _ in LIC]
    total_lic = sum(largs_lic) + 40 * 2
    dxl = -total_lic / 2
    for i, (txt, cor) in enumerate(LIC):
        t = (12 + i * 4) * F
        cx = dxl + largs_lic[i] / 2
        c.append({
            "tipo": "texto", "texto": txt, "tamanho": 40, "peso": 400,
            "cor": cor, **viva(cx, Y_LIC, 2, 310 + i * 40),
            "opacidade": entra(t, 0.3),
            "escala": {"mola": MOLA_TEXTO, "em": t, "de": 0.92, "para": 1.0},
        })
        dxl += largs_lic[i] + 40

    # ── o arco que liga os cartoes (:482-503), traco de f35 a f55 ────────
    c.append({
        "tipo": "path", "d": "M 0 0 C 60 -30 120 -30 180 0", "x": 0, "y": Y_ARCO,
        "contorno": VERDE, "contorno_larg": 1,
        "traco": [[35 * F, 0.0, "outCubic"], [55 * F, 1.0]],
        "opacidade": [[35 * F, 0, "outCubic"], [40 * F, 0.20]],
    })

    # ── os tres cartoes de estatistica (:471-644) ────────────────────────
    # (icone, escala, cor, largura do icone, valores, tempos, largura do numero)
    STATS = [
        (ICONE_ESTRELA, 22 / 24, AMARELO, 22, 22 * F,
         ["1,578", "7,284", "10,744", "12,134", "12,400"],
         [0.733, 1.05, 1.40, 1.75, 2.167]),
        (ICONE_FORK, 20 / 24, CINZA_GH, 20, 26 * F,
         ["117", "1,023", "1,543", "1,769", "1,800"],
         [0.867, 1.20, 1.55, 1.95, 2.333]),
        (ICONE_GENTE, 20 / 24, VERDE, 20, 30 * F,
         ["0+", "186+", "288+", "333+", "340+"],
         [1.0, 1.35, 1.70, 2.10, 2.5]),
    ]
    largs_card = []
    for _, _, _, wi, _, vals, _ in STATS:
        largs_card.append(28 + wi + 10 + larg_texto(vals[-1], 24) + 28)
    total_st = sum(largs_card) + 40 * 2
    dxs = -total_st / 2
    for i, (icone, esc, cor_i, wi, t0, vals, tempos) in enumerate(STATS):
        larg = largs_card[i]
        cx = dxs + larg / 2
        conteudo = wi + 10 + larg_texto(vals[-1], 24)
        x_ico = cx - conteudo / 2 + wi / 2
        x_num = cx - conteudo / 2 + wi + 10 + larg_texto(vals[-1], 24) / 2
        s = 500 + i * 30
        # boxShadow 0 0 20px verde (:528)
        c.append({
            "tipo": "retangulo", "larg": larg + 18, "alt": 76, "raio": 22,
            "cor": VERDE, "blur": 22, **viva(cx, Y_STAT, 2.5, s),
            "opacidade": [[t0, 0, "outCubic"], [t0 + 0.4, 0.10]],
        })
        # o cartao: rgba(255,255,255,0.05), borda #30363d, raio 14 (:521-524)
        c.append(card(cx, Y_STAT, larg, 58, t0, "#FFFFFF0D", BORDA_GH, 14, s))
        c.append({
            "tipo": "path", "d": icone, "cor": cor_i,
            **viva(x_ico, Y_STAT, 2.5, s),
            "escala": {"mola": MOLA_ESTADO, "em": t0, "de": esc * 0.7,
                       "para": esc},
            "opacidade": entra(t0, 0.3),
        })
        # o contador: cinco recortes do interpolate com outCubic, cruzando
        for k, v in enumerate(vals):
            t1 = tempos[k + 1] if k + 1 < len(tempos) else None
            c.append({
                "tipo": "texto", "texto": v, "tamanho": 24, "peso": 700,
                "cor": TEXTO, "x": x_num, "y": Y_STAT - 1,
                "opacidade": _janela(tempos[k], t1, 0.22 if k == 0 else 0.0),
            })
        dxs += larg + 40

    return {"duracao": dur, "fundo": BG_GH, "camadas": c}
