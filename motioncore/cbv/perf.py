# -*- coding: utf-8 -*-
"""perf.py — a cena Performance do CreativlyBrandVideo.

Fundo branco (:123 `COLORS.bgWhite`) atravessado por 40 linhas de velocidade e
14 setas (:154-217), com aneis de energia (:222-260), estouro radial de
particulas (:265-304) e losangos 3D (:309-326) ao redor do bloco cinetico
"LIGHTNING / FAST / blazing speed" (:348-410). Embaixo, a barra de progresso de
1000x36 (:436-468) e o contador "Rendered in NN% Real-time" (:496-552).

Todos os tempos vem da mola de progresso de :58-62 (damping 12, stiffness 50,
mass 0.5, comecando no frame 5): ela governa a largura da barra, o numero do
contador e a escala de FAST. O contador virou 12 camadas de texto trocando por
opacidade, uma por valor amostrado da propria mola — o motor nao tem texto
dinamico, entao o numero que muda vira tempo, como as pilulas do prova_estilos.
"""
from __future__ import annotations

import math

from .base import *

DUR = 2.5

# ── a mola de progresso, :58-62 ──────────────────────────────────────────
MOLA_PROG = {"damping": 12, "stiffness": 50, "mass": 0.5}
T_PROG = 5 * F                      # spring({frame: max(0, frame - 5)})

# ── geometria da barra, :436-468 ─────────────────────────────────────────
BARRA_L = 1000.0                    # width: 1000
BARRA_A = 36.0                      # height: 36
PAD = 6.0                           # padding: 6
INT_L = BARRA_L - 2 * PAD           # 988 uteis
INT_A = BARRA_A - 2 * PAD           # 24
Y_BARRA = -270.0
ESQ = -BARRA_L / 2 + PAD            # -494: borda esquerda do preenchimento

BORDA_ESCURA = "#0000001A"          # constants.ts borderDark rgba(0,0,0,0.1)
AMARELO_DIA = "#FFD60040"           # :320 rgba(255,214,0,0.25) — literal no .tsx


# ── utilitarios locais ───────────────────────────────────────────────────
def _r(i: int, s: int = 0) -> float:
    """Substituto determinista do `random(seed)` do Remotion: nao da os MESMOS
    numeros, da a mesma DISTRIBUICAO (uniforme em [0,1))."""
    return (((i * 2654435761 + s * 40503 + 12345) % 100003) / 100003.0)


def _mix(a: str, b: str, k: float) -> str:
    """Interpola dois hex — o motor nao pinta texto com degrade, entao o
    degrade 135deg de :382 vira uma cor por letra."""
    k = max(0.0, min(1.0, k))
    return "#" + "".join(
        f"{round(int(a[1 + 2 * i:3 + 2 * i], 16) * (1 - k) + int(b[1 + 2 * i:3 + 2 * i], 16) * k):02X}"
        for i in range(3))


def _passa(periodo: float, xs: float, xe: float, fase: float) -> list:
    """Varredura horizontal que reinicia: cada passada e um par de keyframes
    lineares, e o retorno ao inicio leva 1 ms — o `%` do original (:158) nao
    existe no DSL, entao o ciclo e escrito por extenso."""
    ks: list = []
    t = -fase * periodo
    while t < DUR + periodo:
        ks.append([round(t, 4), xs, "linear"])
        ks.append([round(t + periodo - 0.001, 4), xe, "linear"])
        t += periodo
    return ks


def cena(dur: float) -> dict:
    c: list[dict] = []

    # ── marca d'agua "SPEED", :126-150 ───────────────────────────────────
    # 500px, italica, girando de -8 a -6 graus e subindo 15px; opacidade
    # 0 -> 0.03 (f10) -> 0.03 (f70) -> 0.01 (f90).
    mw = marca_dagua("SPEED", 500, MARCA, -8, 0.03)
    mw["rotacao"] = [[0, -8, "linear"], [3.0, -6]]
    mw["y"] = [[0, 0.0, "linear"], [3.0, 15.0]]
    mw["opacidade"] = [[0, 0, "outCubic"], [10 * F, 0.03],
                       [70 * F, 0.03], [90 * F, 0.01]]
    c.append(mw)

    # ── duas manchas de luz: o boxShadow da barra (:454) e o brilho do
    #    bloco FAST, que no original vem do texto em degrade ───────────────
    c.append(brilho(120, 40, 720, MARCA, 0.0, 0.10, s=11))
    c.append(brilho(0, Y_BARRA, 460, CIANO, 0.15, 0.14, s=12))

    # ── 16 linhas de velocidade, :154-181 ────────────────────────────────
    # O original tem 40; aqui sao 16 amostradas na mesma faixa de alturas.
    # A velocidade base (i+1)*45 px/frame chega a 51 passadas em 2,5 s nas
    # ultimas linhas — a 30 fps isso estrobosca em vez de correr, entao a
    # escada de periodos foi comprimida para 1,87 s .. 0,36 s.
    for i in range(16):
        io = round(i * 2.5)                       # indice equivalente nos 40
        amarela = io % 3 == 0                     # :163
        cor = MARCA if amarela else PRIMARIA      # sao a mesma cor no .tsx
        alt = 3 if amarela else 2                 # :175
        larg = 450 + _r(io, 7) * 250              # :173-174
        cy = H / 2 - (i / 16.0) * H - alt / 2     # top: (i/40)*100%
        periodo = max(0.30, 1.87 / (1 + i * 0.28))
        xs = -300 + larg / 2 - W / 2
        xe = (W + 300) + larg / 2 - W / 2
        c.append({
            "tipo": "retangulo", "larg": larg, "alt": alt,
            "cor": {"tipo": "linear",
                    "cores": [cor + "00", cor + "50", cor + "00"],
                    "paradas": [0.0, 0.5, 1.0],
                    "de": [-larg / 2, 0], "para": [larg / 2, 0]},
            "x": _passa(periodo, xs, xe, _r(io, 3)),
            "y": cy,
            "opacidade": pulso(0.28, 0.14, 0.03, 400 + io),
        })

    # ── 8 setas de velocidade, :185-217 ──────────────────────────────────
    # makeTriangle(direction "right"): triangulo apontando para a direita.
    for i in range(8):
        tam = _r(i, 21) * 14 + 8                  # :26
        vel = _r(i, 22) * 80 + 40                 # :25  px/frame
        amarela = _r(i, 24) > 0.5                 # :28
        cor = MARCA if amarela else PRIMARIA
        cy = H / 2 - (_r(i, 20) * 90 + 5) / 100.0 * H
        periodo = (W + 200) / (vel * FPS)
        w = tam * 0.866
        c.append({
            "tipo": "path",
            "d": f"M 0 0 L {w:.1f} {tam / 2:.1f} L 0 {tam:.1f} Z",
            "centrar": True, "cor": cor,
            "x": _passa(periodo, -100 - W / 2, (W + 100) - W / 2, _r(i, 25)),
            "y": cy,
            # opacity: sin(frame*0.12 + i*3) mapeado em [0.08, 0.45] (:193-197)
            "opacidade": pulso(0.26, 0.17, 0.02, 500 + i),
        })

    # ── 5 aneis de energia, :222-260 ─────────────────────────────────────
    # 1800px de diametro em 45 frames com outCubic; opacidade 0 -> 0.22 (f8)
    # -> 0 (f45); cada anel comeca 8 frames depois do anterior.
    for i in range(5):
        t0 = i * 8 * F
        cor = MARCA_ESCURA if i % 2 == 0 else MARCA
        c.append({
            "tipo": "elipse",
            "raio": [[t0, 0.0, "outCubic"], [t0 + 45 * F, 900.0]],
            "cor": "#00000000",                   # armadilha 2: anel = so contorno
            "contorno": cor, "contorno_larg": 2,
            "x": {"ruido": {"escala": 0.02, "amp": 6, "base": 0, "semente": 60 + i}},
            "y": {"ruido": {"escala": 0.02, "amp": 6, "base": 0, "semente": 660 + i}},
            "opacidade": [[t0, 0.0, "outCubic"], [t0 + 8 * F, 0.22],
                          [t0 + 45 * F, 0.0]],
        })

    # ── 14 particulas do estouro radial, :265-304 ────────────────────────
    # burstProg linear de f8 a f55; distancia 80..360; opacidade 0 -> 0.55
    # (em 25% do caminho) -> 0.
    t_b0, t_b1 = 8 * F, 55 * F
    for i in range(14):
        ang = (i / 14.0) * math.pi * 2
        dist = _r(i, 31) * 280 + 80
        raio = (_r(i, 32) * 4 + 1.5) / 2
        cor = MARCA if _r(i, 33) > 0.4 else CIANO
        px, py = math.cos(ang) * dist, math.sin(ang) * dist
        c.append({
            "tipo": "elipse", "raio": raio, "cor": cor,
            "x": [[t_b0, 0.0, "linear"], [t_b1, px]],
            "y": [[t_b0, 0.0, "linear"], [t_b1, py]],
            "opacidade": [[t_b0, 0.0, "outCubic"],
                          [t_b0 + (t_b1 - t_b0) * 0.25, 0.55],
                          [t_b1, 0.0]],
        })

    # ── 7 losangos flutuantes, :309-326 + Rotating3D.tsx:170-230 ─────────
    # Quadrado girado 45 graus, com rotX/rotY continuos. O achatamento do
    # rotateX vira `escalaY` por ruido — o motor e 2D.
    for i in range(7):
        tam = _r(i, 41) * 40 + 25
        vel = _r(i, 42) * 1.5 + 0.5
        atraso = math.floor(_r(i, 43) * 15) * F + 2 * F
        amarelo = _r(i, 44) > 0.35
        cx = _r(i, 45) * 1800 + 60 - W / 2
        cy = H / 2 - (_r(i, 46) * 900 + 90)
        c.append({
            "tipo": "retangulo", "larg": tam, "alt": tam,
            "cor": AMARELO_DIA if amarelo else "#3B82F626",
            "contorno": (MARCA if amarelo else CIANO) + "33", "contorno_larg": 1,
            **viva(cx, cy, 10, 70 + i),
            "rotacao": [[0, 45.0, "linear"], [DUR, 45.0 + 150.0 * vel]],
            "escala": {"mola": MOLA_ESTADO, "em": atraso, "de": 0.0, "para": 1.0},
            "escalaY": {"ruido": {"escala": 0.02 * vel, "amp": 0.42,
                                  "base": 0.58, "semente": 770 + i}},
            "opacidade": entra(atraso, 0.35),
        })

    # ── "LIGHTNING": 220px, italica, peso 900, letra a letra, :348-369 ──
    # CharacterReveal com stagger 1.5 frames = LETRA.
    c += titulo("LIGHTNING", 0.0, 300, 220, TEXTO_PRETO, 900, LETRA,
                0.0, italico=True)

    # ── "FAST": 300px, degrade 135deg #3B82F6 -> #06B6D4, :371-391 ──────
    # translateX vai de -60 a +120 pela mola de :106-111; a escala 0.7 -> 1
    # e o UNICO destaque da cena.
    TAM_F, ESP_F = 300, -12          # letterSpacing -0.04em
    palavra = "FAST"
    largs = [larg_char(ch, TAM_F) for ch in palavra]
    total_f = sum(largs) + ESP_F * (len(palavra) - 1)
    px = -total_f / 2
    for i, ch in enumerate(palavra):
        bx = px + largs[i] / 2
        c.append({
            "tipo": "texto", "texto": ch, "tamanho": TAM_F, "peso": 900,
            "italico": True, "cor": _mix(MARCA, CIANO, i / (len(palavra) - 1)),
            "x": {"mola": MOLA_TEXTO, "em": 10 * F, "de": bx - 60, "para": bx + 120},
            "y": 30,
            "escala": {"mola": MOLA_DESTAQUE, "em": T_PROG, "de": 0.70, "para": 1.0},
            "opacidade": entra(i * LETRA, 0.25),
        })
        px += largs[i] + ESP_F

    # ── "blazing speed": 18px, espacamento 0.35em, :393-410 ─────────────
    c.append({
        "tipo": "texto", "texto": "BLAZING SPEED", "tamanho": 18, "peso": 700,
        "italico": True, "cor": MUDO_ESCURO, "espacamento": 6,
        "x": {"mola": MOLA_TEXTO, "em": 10 * F, "de": -40, "para": 140},
        "y": -160,
        "opacidade": entra(22 * F, 0.3),
    })

    # ── a barra de progresso, :415-492 ──────────────────────────────────
    # trilho
    c.append({
        "tipo": "retangulo", "larg": BARRA_L, "alt": BARRA_A, "raio": 18,
        "cor": BG_SUP_CLARO, "contorno": BORDA_ESCURA, "contorno_larg": 1,
        "x": 0, "y": Y_BARRA,
        "opacidade": entra(5 * F, 0.25),
        "escala": {"mola": MOLA_ESTADO, "em": 5 * F, "de": 0.94, "para": 1.0},
    })
    # o brilho de 40px do boxShadow (:454), desenhado como retangulo borrado
    c.append({
        "tipo": "retangulo", "alt": INT_A + 10, "raio": 16, "cor": MARCA,
        "blur": 40,
        "larg": {"mola": MOLA_PROG, "em": T_PROG, "de": 0.0, "para": INT_L},
        "x": {"mola": MOLA_PROG, "em": T_PROG, "de": ESQ, "para": ESQ + INT_L / 2},
        "y": Y_BARRA, "opacidade": [[5 * F, 0.0, "outCubic"], [0.6, 0.40]],
    })
    # o preenchimento em degrade brandDark -> brand -> brandCyan (:452)
    c.append({
        "tipo": "retangulo", "alt": INT_A, "raio": 12,
        "cor": {"tipo": "linear", "cores": [MARCA_ESCURA, MARCA, CIANO],
                "paradas": [0.0, 0.5, 1.0],
                "de": [-INT_L / 2, 0], "para": [INT_L / 2, 0]},
        "larg": {"mola": MOLA_PROG, "em": T_PROG, "de": 0.0, "para": INT_L},
        "x": {"mola": MOLA_PROG, "em": T_PROG, "de": ESQ, "para": ESQ + INT_L / 2},
        "y": Y_BARRA,
    })
    # o brilho que corre por dentro (:458-466): a posicao vem de ruido, como
    # o `noise2D("shimmer", frame*0.06, 0)` do original
    c.append({
        "tipo": "retangulo", "larg": 300, "alt": INT_A, "raio": 12,
        "cor": {"tipo": "linear",
                "cores": ["#FFFFFF00", "#FFFFFF73", "#FFFFFF00"],
                "paradas": [0.0, 0.5, 1.0], "de": [-150, 0], "para": [150, 0]},
        "x": {"ruido": {"escala": 0.06, "amp": 290, "base": 0, "semente": 31}},
        "y": Y_BARRA, "opacidade": [[0.30, 0.0, "outCubic"], [0.70, 1.0]],
    })
    # o path SVG de 1000px que se desenha de f8 a f40 (:418-434)
    c.append({
        "tipo": "linha", "de": [-500, 0], "para": [500, 0],
        "contorno": MARCA, "contorno_larg": 1.5,
        "y": Y_BARRA + BARRA_A / 2 + 10, "opacidade": 0.4,
        "traco": [[8 * F, 0.0, "outCubic"], [40 * F, 1.0]],
    })
    # o ponto aceso na ponta (:471-491) — halo e nucleo
    c.append({
        "tipo": "elipse", "raio": 34,
        "cor": {"tipo": "radial", "cores": [MARCA + "AA", "#00000000"], "raio": 34},
        "x": {"mola": MOLA_PROG, "em": T_PROG, "de": ESQ, "para": ESQ + INT_L},
        "y": Y_BARRA, "blur": 12,
        "opacidade": [[5 * F, 0.0, "outCubic"], [0.5, 0.85]],
    })
    c.append({
        "tipo": "elipse", "raio": 12,
        "cor": {"tipo": "radial", "cores": [CIANO, MARCA], "raio": 12},
        "x": {"mola": MOLA_PROG, "em": T_PROG, "de": ESQ, "para": ESQ + INT_L},
        "y": Y_BARRA,
        "opacidade": pulso(0.65, 0.25, 0.05, 33),
    })

    # ── o contador, :496-552 ─────────────────────────────────────────────
    # "Rendered in" 36 / NN% 80 italico / "Real-time" 36, gap 16, alinhados
    # pela base. Entram juntos no frame 8.
    Y_NUM, Y_PEQ = -400.0, -415.0
    T_CNT = 8 * F
    # `larg_texto` subestima digito bold italico de 80px em 14% (medido no
    # shaper: "100%" da 204,6 px contra 179,2 estimados). Sem a folga o slot
    # nasce mais estreito que o proprio numero e o gap 16 de :510 some.
    GAP = 26
    w1 = larg_texto("Rendered in", 36)
    wn = larg_texto("100%", 80) * 1.15
    w2 = larg_texto("Real-time", 36)
    tot = w1 + GAP + wn + GAP + w2
    x1 = -tot / 2 + w1 / 2
    xn = -tot / 2 + w1 + GAP + wn / 2
    x2 = tot / 2 - w2 / 2
    SEM_CNT = 77                      # mesma semente: a linha inteira deriva junta

    for txt, xx in (("Rendered in", x1), ("Real-time", x2)):
        c.append({
            "tipo": "texto", "texto": txt, "tamanho": 36, "peso": 700,
            "cor": MUDO_ESCURO, **viva(xx, Y_PEQ, 4, SEM_CNT),
            "opacidade": entra(T_CNT, 0.3),
        })

    # os 12 valores amostrados da mola de progresso (conferidos frame a frame):
    # f8=26 f9=38 f10=49 f11=59 f12=67 f13=74 f15=84 f17=90 f19=94 f21=96
    # f25=99 f58=100. Cada um e uma camada que acende na sua janela.
    PASSOS = [(8, 26), (9, 38), (10, 49), (11, 59), (12, 67), (13, 74),
              (15, 84), (17, 90), (19, 94), (21, 96), (25, 99), (58, 100)]
    for k, (fr, val) in enumerate(PASSOS):
        t0 = fr * F
        t1 = PASSOS[k + 1][0] * F if k + 1 < len(PASSOS) else DUR + 1.0
        # counterColor: brandDark (f5) -> brand (f40), :87-91
        cor = _mix(MARCA_ESCURA, MARCA, (fr - 5) / 35.0)
        if k == 0:
            sobe_ = min(0.05, (t1 - t0) * 0.5)
            op = [[t0, 0.0, "outCubic"], [t0 + sobe_, 1.0],
                  [t1 - 0.001, 1.0, "linear"], [t1, 0.0]]
        else:
            op = [[t0 - 0.001, 0.0, "linear"], [t0, 1.0],
                  [t1 - 0.001, 1.0, "linear"], [t1, 0.0]]
        c.append({
            "tipo": "texto", "texto": f"{val}%", "tamanho": 80, "peso": 900,
            "italico": True, "cor": cor,
            **viva(xn, Y_NUM, 4, SEM_CNT),
            "opacidade": op,
        })

    return {"duracao": dur, "fundo": BG_BRANCO, "camadas": c}
