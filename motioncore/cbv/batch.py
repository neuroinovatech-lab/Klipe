# -*- coding: utf-8 -*-
"""batch.py — a cena Batch Generation do CreativlyBrandVideo.

Seis variantes da mesma ideia nascendo ao mesmo tempo: titulo "Batch /
GENERATION" (:241-282), a barra de progresso com seis tracos e o contador N/6
(:314-376) e a grade 3x2 de 1400 px com as seis fotos entrando em cascata de 4
frames cada (:381-418). O gesto central e a VARREDURA: cada card entra tapado
por `COLORS.bg` e vai sendo destapado da esquerda para a direita (:430-438) —
aqui isso e `revelar` na propria imagem, mais uma barra de luz correndo na
borda do corte. O contador e sete camadas de texto trocando por janela de
opacidade, porque `Math.floor(interpolate(frame,[5,25],[0,6]))` (:69-77) e
estado, e o motor nao tem estado: estado vira tempo.
"""
from .base import *

# :32-39 — as seis variantes, na ordem em que o original as lista
VARIANTES = [
    "director-board_800w.jpg",
    "ugc-product-story_800w.jpg",
    "launch-film-suite_800w.jpg",
    "surrealist-concept_800w.jpg",
    "character-performance_800w.jpg",
    "brand-identity-system_800w.jpg",
]

# ── geometria do empilhamento vertical do AbsoluteFill (coluna centrada) ──
# titulo 230 + 10 · progresso 37 + 40 · grade 532,5  =  849,5 de altura total,
# logo o topo cai em (1080-849,5)/2 = 115,25. Dai saem todos os `y` abaixo.
Y_BATCH = 392          # linha "Batch" 60px italico    :242-261
Y_GERACAO = 294        # linha "GENERATION" 130px      :263-282
Y_TAG = 207            # tagline 20px italico          :285-299
Y_PONTOS = 175         # fileira de tracos + contador  :314-362
Y_BARRA = 151          # svg de 400x6                  :365-376
CARD_L, CARD_A = 446.67, 251.25    # (1400-60)/3, aspect 16/9   :383-388
COL_X = (-476.67, 0.0, 476.67)
ROW_Y = (-17.9, -299.1)

T_CARD = [(5 + 4 * i) * F for i in range(6)]   # :391-395 — spring(frame-5-i*4)
T_PONTO = [(5 + 3 * i) * F for i in range(6)]  # :316-320 — spring(frame-i*3-5)

# `revelar` corta contra a extensao do QUADRO (max(W,H)), nao contra a caixa da
# camada: num card de 447 px a cortina so encosta na borda esquerda em 0,384 e
# ja passou da direita em 0,617. Sem esta conversao a varredura quase nao anda —
# foi o que a primeira versao fez, e o card aparecia inteiro de uma vez.
_EXT = float(max(W, H))
REV0 = (_EXT / 2 - CARD_L / 2) / _EXT
REV1 = (_EXT / 2 + CARD_L / 2 + 6) / _EXT


def _ate(dur: float, ks: list) -> list:
    """Corta a lista de keyframes em `dur`, mantendo os tempos crescentes.

    A cena tem tempos absolutos lidos do original (o ciclo de cor bate em 2,33 s,
    o cintilar da faisca em 1,9 s depois do card). Com uma `dur` mais curta esses
    tempos passariam do fim e sairiam fora de ordem — o motor nao reclama, so
    anima errado. Aqui a lista termina sempre exatamente no fim da cena.
    """
    out: list = []
    for k in ks:
        if out and k[0] >= dur:
            break
        out.append([min(float(k[0]), dur)] + list(k[1:]))
    if out[-1][0] < dur:
        out.append([dur, out[-1][1]])
    return out


def _estrela(r: float) -> str:
    """Faisca de 4 pontas — o `makeStar({points:4, innerRadius: .3r})` :463-467."""
    i = r * 0.212
    return (f"M 0 {-r:.2f} L {i:.2f} {-i:.2f} L {r:.2f} 0 L {i:.2f} {i:.2f} "
            f"L 0 {r:.2f} L {-i:.2f} {i:.2f} L {-r:.2f} 0 L {-i:.2f} {-i:.2f} Z")


def _cantos(lg: float, al: float, r: float = 16.0, folga: float = 4.0) -> str:
    """O `overflow: hidden` do card (:411-412), que o motor nao tem.

    `imagem` nao aceita raio, entao a foto sai de canto vivo e denuncia. Isto e
    um ANEL: retangulo externo no sentido horario mais retangulo arredondado no
    ANTI-horario. Com preenchimento por winding, so a casca entre os dois pinta
    — as quatro pontas quadradas somem sob a cor do fundo. Os cantos sao Q em
    vez de A: a r=16 a quadratica e a mesma curva, sem os flags do arco.
    """
    x, y = lg / 2 + folga, al / 2 + folga
    w, h = lg / 2, al / 2
    return (f"M {-x:.1f} {-y:.1f} L {x:.1f} {-y:.1f} L {x:.1f} {y:.1f} "
            f"L {-x:.1f} {y:.1f} Z "
            f"M {-w:.1f} {-h + r:.1f} L {-w:.1f} {h - r:.1f} "
            f"Q {-w:.1f} {h:.1f} {-w + r:.1f} {h:.1f} "
            f"L {w - r:.1f} {h:.1f} Q {w:.1f} {h:.1f} {w:.1f} {h - r:.1f} "
            f"L {w:.1f} {-h + r:.1f} Q {w:.1f} {-h:.1f} {w - r:.1f} {-h:.1f} "
            f"L {-w + r:.1f} {-h:.1f} Q {-w:.1f} {-h:.1f} {-w:.1f} {-h + r:.1f} Z")


def cena(dur: float) -> dict:
    c: list[dict] = []

    # ── marca d'agua "BATCH", 400px italica, -15deg com ruido (:116-141) ──
    wm = marca_dagua("BATCH", 400, MARCA, -15.0, 0.055)
    wm["rotacao"] = pulso(-15.0, 2.0, 0.005, 77)      # :93-94
    wm["espacamento"] = 40                            # letterSpacing 0.1em
    c.append(wm)

    # ── grade de 80px em `primary` (:144-159); o gridGlow oscila em 0.1+0.05 ──
    c += grade_fundo(80, "#3B82F644", 0.5)

    # o `maskImage` radial do original nao existe no motor: a vinheta faz o
    # papel de apagar a grade nas bordas. Vem AQUI, antes de tudo que brilha.
    c.append({
        "tipo": "elipse", "raio": W * 0.62,
        "cor": {"tipo": "radial", "cores": ["#00000000", BG], "raio": W * 0.62},
        "opacidade": [[0, 0.95]]})

    # ── o brilho central (:161-173), 800x400 no topo 40% = y 108 ──────────
    # glowColor cicla brand -> primary -> secondary -> brand (:86-90). Cor nao
    # e animavel: duas manchas cruzando por opacidade fazem o mesmo ciclo.
    g1 = brilho(0, 108, 430, MARCA, 0.0, 0.32, 3)
    g1["opacidade"] = _ate(dur, [[0, 0], [0.9, 0.32, "outCubic"], [1.8, 0.32],
                                 [2.4, 0.11], [3.0, 0.11], [3.5, 0.30]])
    c.append(g1)
    g2 = brilho(0, 108, 300, SECUNDARIA, 0.0, 0.22, 9)
    g2["opacidade"] = _ate(dur, [[0, 0], [1.6, 0], [2.4, 0.24], [2.9, 0.24],
                                 [3.5, 0.05]])
    c.append(g2)

    # ── os quatro solidos 3D (:176-225). Sem 3D no motor: quadrado girando ──
    # FloatingDiamond canto superior esquerdo, 50px, delay 5f, speed 0.8
    c.append(brilho(-815, 435, 90, MARCA, 0.17, 0.30, 21))
    c.append({
        "tipo": "retangulo", "larg": 50, "alt": 50, "cor": "#3B82F630",
        "contorno": "#3B82F655", "contorno_larg": 1,
        **viva(-815, 435, 10, 21),
        "rotacao": [[0, 45, "linear"], [dur, 45 + 1.6 * 30 * dur]],
        "opacidade": entra(0.17, 0.5),
        "escala": {"mola": MOLA_TEXTO, "em": 0.17, "de": 0.0, "para": 1.0}})
    # FloatingDiamond canto inferior direito, 35px, delay 10f, speed 1.2
    c.append({
        "tipo": "retangulo", "larg": 35, "alt": 35, "cor": "#3B82F625",
        "contorno": "#3B82F644", "contorno_larg": 1,
        **viva(757, -327, 9, 33),
        "rotacao": [[0, 45, "linear"], [dur, 45 + 2.4 * 30 * dur]],
        "opacidade": entra(0.33, 0.5),
        "escala": {"mola": MOLA_TEXTO, "em": 0.33, "de": 0.0, "para": 1.0}})
    # Rotating3DBox canto superior direito, 80px, delay 8f, speed 0.6.
    # A rotacao em Y do cubo vira achatamento horizontal por ruido.
    c.append({
        "tipo": "retangulo", "larg": 80, "alt": 80, "raio": 2,
        "cor": "#3B82F608", "contorno": "#3B82F618", "contorno_larg": 1,
        **viva(800, 440, 5, 45),
        "escalaX": pulso(0.72, 0.28, 0.03, 46),
        "rotacao": [[0, 0, "linear"], [dur, 0.18 * 30 * dur]],
        "opacidade": [[0.27, 0], [0.8, 0.5, "outCubic"]],
        "escala": {"mola": MOLA_ESTADO, "em": 0.27, "de": 0.0, "para": 1.0}})
    # Rotating3DBox canto inferior esquerdo, 60px, delay 12f, speed 0.9
    c.append({
        "tipo": "retangulo", "larg": 60, "alt": 60, "raio": 2,
        "cor": "#3B82F606", "contorno": "#3B82F614", "contorno_larg": 1,
        **viva(-850, -370, 5, 57),
        "escalaX": pulso(0.70, 0.30, 0.036, 58),
        "rotacao": [[0, 0, "linear"], [dur, 0.27 * 30 * dur]],
        "opacidade": [[0.4, 0], [0.95, 0.4, "outCubic"]],
        "escala": {"mola": MOLA_ESTADO, "em": 0.4, "de": 0.0, "para": 1.0}})

    # ── titulo (:228-299) ─────────────────────────────────────────────────
    # O SplitText do original quebra por PALAVRA; "Batch" e "GENERATION" sao
    # uma palavra cada, entao la entram inteiras. Aqui a cascata e por LETRA,
    # que e o gesto da casa — mesmos tempos de partida (delay 0 e 2 frames).
    c += titulo("Batch", 0.0, Y_BATCH, 60, TEXTO, 700, LETRA, 0.0, True)
    ger = titulo("GENERATION", 2 * F, Y_GERACAO, 130, TEXTO, 900, LETRA)
    # letterSpacing -0.02em (:270): a medida do base nao tem tracking, entao a
    # linha inteira e comprimida pelo mesmo fator que -2,6 px por letra daria.
    fator = 1 - 9 * 2.6 / larg_texto("GENERATION", 130)
    for cam in ger:
        cam["x"] *= fator
    c += ger
    c.append(rotulo("mass produce, iterate fast", 8 * F, Y_TAG, MUDO, 20,
                    0.0, 3, 400))

    # ── os seis tracos de progresso (:314-344): 40x6, raio 3, gap 8 ───────
    # scaleX 0.5->1 e a cor indo de textDim a brand. Como `cor` nao anima, a
    # versao acesa entra por cima cruzando opacidade — o mesmo truque de
    # `pilula()` no base.
    for i in range(6):
        px = -139.5 + i * 48
        t = T_PONTO[i]
        mola_x = {"mola": MOLA_ESTADO, "em": t, "de": 0.5, "para": 1.0}
        c.append({"tipo": "retangulo", "larg": 40, "alt": 6, "raio": 3,
                  "cor": DIM, "x": px, "y": Y_PONTOS, "escalaX": mola_x,
                  "opacidade": [[0.1, 0], [0.4, 0.3, "outCubic"]]})
        c.append({"tipo": "retangulo", "larg": 40, "alt": 6, "raio": 3,
                  "cor": MARCA, "x": px, "y": Y_PONTOS, "escalaX": mola_x,
                  "blur": 3,
                  "opacidade": [[t, 0], [t + 0.28, 1, "outCubic"]]})

    # ── o contador N/6 (:345-361 + :69-77): floor de 0 a 6 entre f5 e f25 ──
    # Sete camadas, cada uma acesa na sua janela. A ultima ganha a mola de
    # DESTAQUE: e o unico pulo da cena, no frame em que fecha 6/6.
    for k in range(7):
        a = (5 + k * 20 / 6) * F if k else 0.1
        b = (5 + (k + 1) * 20 / 6) * F
        op = ([[0, 0], [max(0.0, a - 0.01), 0], [a, 1]] if k == 0 else
              [[0, 0], [a - 0.01, 0], [a, 1]])
        if k < 6:
            op += [[b - 0.01, 1], [b, 0]]
        cam = {"tipo": "texto", "texto": f"{k}/6", "tamanho": 16, "peso": 700,
               "cor": MARCA_CLARA, "x": 144, "y": Y_PONTOS, "opacidade": op}
        if k == 6:
            cam["escala"] = {"mola": MOLA_DESTAQUE, "em": b - 20 / 6 * F,
                             "de": 0.55, "para": 1.0}
        c.append(cam)

    # ── a barra de 400px desenhada por evolvePath (:78-83, :365-376) ──────
    # `traco` e exatamente isso: o contorno recortado de 0 a 1.
    c.append({"tipo": "linha", "de": [-200, 0], "para": [200, 0],
              "contorno": MARCA, "contorno_larg": 2, "y": Y_BARRA,
              "opacidade": [[0.1, 0], [0.4, 0.4, "outCubic"]],
              "traco": [[5 * F, 0.001, "outCubic"], [25 * F, 1.0]]})

    # ── a grade 3x2 (:381-509) ────────────────────────────────────────────
    for i, nome in enumerate(VARIANTES):
        cx, cy = COL_X[i % 3], ROW_Y[i // 3]
        t = T_CARD[i]
        s = 200 + i * 11
        mola = {"mola": MOLA_ESTADO, "em": t, "de": 0.7, "para": 1.0}

        # a foto, com a varredura de geracao (:430-438) virando `revelar`
        c.append({
            "tipo": "imagem", "src": asset(nome),
            "larg": CARD_L, "alt": CARD_A, "ajuste": "cobrir",
            **viva(cx, cy, 3, s), "escala": mola,
            "opacidade": entra(t, 0.2),
            "revelar": {"prog": [[t, REV0, "outCubic"], [t + 0.55, REV1],
                                 [t + 0.62, 1.0]], "dir": "esq"}})
        # a linha de luz que corre no corte da varredura
        c.append({
            "tipo": "retangulo", "larg": 5, "alt": CARD_A, "cor": MARCA_CLARA,
            "blur": 7, "y": cy,
            "x": [[t, cx - CARD_L / 2, "outCubic"], [t + 0.55, cx + CARD_L / 2]],
            "escalaY": mola,
            "opacidade": [[t, 0], [t + 0.16, 0.8], [t + 0.44, 0.8],
                          [t + 0.56, 0]]})
        # o recorte dos cantos — ver `_cantos()`
        c.append({
            "tipo": "path", "d": _cantos(CARD_L, CARD_A), "cor": BG,
            "centrar": False, **viva(cx, cy, 3, s), "escala": mola,
            # mascara e opaca de imediato: a meio caminho ela deixaria o canto
            # vivo da foto aparecer por baixo, que foi o defeito da 1a versao.
            "opacidade": [[t, 0], [t + 0.05, 1]]})
        # a borda de 1px, raio 16 (:410-417) — anel: cor nula + contorno
        c.append({
            "tipo": "retangulo", "larg": CARD_L, "alt": CARD_A, "raio": 16,
            "cor": "#00000000", "contorno": BORDA_CLARA, "contorno_larg": 1,
            **viva(cx, cy, 3, s), "escala": mola,
            "opacidade": entra(t, 0.2)})
        # o cracha "V1..V6": top 16 / left 16, padding 4/14, raio 8 (:441-458)
        bl = larg_texto(f"V{i+1}", 14) + 28
        bx, by = cx - CARD_L / 2 + 16 + bl / 2, cy + CARD_A / 2 - 16 - 12
        c.append({
            "tipo": "retangulo", "larg": bl, "alt": 24, "raio": 8, "cor": MARCA,
            **viva(bx, by, 3, s), "opacidade": entra(t + 0.1, 0.3),
            "escala": {"mola": MOLA_ESTADO, "em": t + 0.1, "de": 0.7,
                       "para": 1.0}})
        c.append({
            "tipo": "texto", "texto": f"V{i+1}", "tamanho": 14, "peso": 700,
            "cor": TEXTO, **viva(bx, by - 1, 3, s),
            "opacidade": entra(t + 0.14, 0.3)})

    # ── as faiscas de conclusao (:460-506), so depois de cardSpr > 0.9 ────
    # angulo i/12*2pi, distancia 10-30 px do canto superior direito, girando.
    for i in range(6):
        cx, cy = COL_X[i % 3], ROW_Y[i // 3]
        td = T_CARD[i] + 0.45
        for j, (dx, dy, r, vel) in enumerate(
                ((-28.0, -10.0, 6.0, 0.32),)):
            sx = cx + CARD_L / 2 + dx
            sy = cy + CARD_A / 2 + dy
            c.append({
                "tipo": "path", "d": _estrela(r), "cor": TEXTO,
                **viva(sx, sy, 8, 610 + i * 7 + j),
                "rotacao": [[td, 0, "linear"], [dur, vel * 3 * 30 * (dur - td)]],
                "opacidade": _ate(dur, [
                    [td, 0], [td + 0.18, 0.55], [td + 0.5, 0.16],
                    [td + 0.9, 0.6], [td + 1.35, 0.2], [td + 1.9, 0.5],
                    [td + 2.4, 0.28]])})

    return {"duracao": dur, "fundo": BG, "camadas": c}
