# -*- coding: utf-8 -*-
"""focused.py — a cena Focused Demo do CreativlyBrandVideo.

O estudio de edicao inteiro numa tela: o hero `focused-editor.jpg` entra com
mola e sai de foco (:43-49), a barra de acoes de vidro desliza pela direita
(:52-57), a tira de miniaturas sobe e a ativa corre de uma a outra (:149-152),
o comparador varre 48% do hero entre os frames 48 e 78 (:68-76), a barra de
prompt sobe no frame 62 e o texto se digita entre 64 e 92 (:169-172), o modo
vira IMG->VID no frame 85-95 (:87-91) e o anel de progresso fecha em 100-115
(:94-98). O titulo "Creative Studio" fecha letra a letra no frame 88 (:143).
"""
from .base import *


def cena(dur: float) -> dict:
    # ── css -> cena. `x` positivo vai pra direita, `y` positivo SOBE ────
    def px(l: float) -> float:
        return l - 960.0

    def py(t: float) -> float:
        return 540.0 - t

    def kf(f: float) -> float:
        """frame do original -> segundo (o .tsx roda a 30 fps)."""
        return f / 30.0

    C: list[dict] = []

    # ═══ ATMOSFERA (:180-208) ══════════════════════════════════════════
    # dois blobs radiais, dois pulse rings e os tres losangos flutuantes
    # nos mesmos cantos do original.
    C.append(brilho(px(976), py(516), 460, MARCA, 0.0, 0.38, 11))
    C.append(brilho(px(1382), py(722), 320, CIANO, 0.15, 0.28, 23))

    # PulseRings maxSize 1000, speed 0.2 -> ciclo de 5 s, defasagem de 1/3.
    # O anel some no fim do ciclo e renasce no centro.
    _ciclo, _fase, _pico = 5.0, 5.0 / 3.0, 0.26
    for i in range(2):
        off = i * _fase
        volta = 0.0 if off == 0 else _ciclo - off      # instante do renascimento
        raio, opac = [], []
        if volta <= 0.0:
            raio = [[0, 0, "linear"], [dur, 500 * dur / _ciclo]]
            opac = [[0, 0, "linear"], [1.0, _pico, "linear"],
                    [dur, _pico * (1 - (dur / _ciclo - 0.2) / 0.8)]]
        else:
            p0 = off / _ciclo
            raio = [[0, 500 * p0, "linear"], [volta, 500, "linear"],
                    [volta + 0.02, 0, "linear"], [dur, 500 * (dur - volta) / _ciclo]]
            pf = (dur - volta) / _ciclo
            opac = [[0, _pico * (1 - (p0 - 0.2) / 0.8), "linear"],
                    [volta, 0.0, "linear"], [volta + 0.02, 0.0, "linear"]]
            if pf > 0.2:
                opac += [[volta + 0.2 * _ciclo, _pico, "linear"],
                         [dur, _pico * (1 - (pf - 0.2) / 0.8)]]
            else:
                opac += [[dur, _pico * pf / 0.2]]
        C.append({"tipo": "elipse", "raio": raio, "cor": "#00000000",
                  "contorno": MARCA, "contorno_larg": 1, "opacidade": opac})

    # FloatingDiamond x3 (:204-206) — quadrado a 45 graus girando devagar
    for sz, cor, cxx, cyy, vel, atraso, sem in (
            (28, "#3B82F633", px(114), py(164), 0.8, kf(5), 41),
            (20, "#06B6D42B", px(1810), py(210), 1.1, kf(10), 57),
            (35, "#8B5CF626", px(1717), py(867), 0.5, kf(15), 73)):
        C.append({
            "tipo": "retangulo", "larg": sz, "alt": sz, "raio": 3, "cor": cor,
            "contorno": cor, "contorno_larg": 1,
            **viva(cxx, cyy, 12, sem),
            "rotacao": [[atraso, 45], [dur, 45 + 45 * vel * dur]],
            "escalaX": pulso(0.85, 0.28, 0.03, sem + 300),
            "opacidade": entra(atraso, 0.5),
            "escala": {"mola": {"damping": 16, "stiffness": 80},
                       "em": atraso, "de": 0.0, "para": 0.8},
        })

    # ═══ MARCA D'AGUA "FOCUS" (:211-235): 420px, italica, -12deg ═══════
    C.append(marca_dagua("FOCUS", 420, MARCA, -12.0, 0.045))

    # ═══ HERO (:238-257) — left 340 / top 55 / 1140x660 ════════════════
    HX, HY, HW, HH = px(340 + 570), py(55 + 330), 1140, 660
    HL, HR = HX - HW / 2, HX + HW / 2
    HT, HB = HY + HH / 2, HY - HH / 2
    T_HERO = kf(6)
    MOLA_HERO = {"damping": 14, "stiffness": 80, "mass": 0.7}

    C += sombra(HX, HY, HW, HH, T_HERO, 20, n=1)
    # o `blur` de entrada (16 -> 0, :49) nao existe aqui: `blur` nao e animavel
    # e a camada `imagem` nem o le. O desfoque vira um halo — a mesma foto num
    # enquadramento 3,5% maior, na MESMA rampa de mola, dissolvendo por cima.
    # Com escalas diferentes as duas copias separavam e viravam foto dupla.
    C.append({
        "tipo": "imagem", "src": asset("focused-editor.jpg"),
        "larg": HW * 1.035, "alt": HH * 1.035, "ajuste": "cobrir",
        "x": HX, "y": HY, "tingir": "#C2CEE0",
        "opacidade": [[T_HERO, 0, "outCubic"], [T_HERO + 0.16, 0.7],
                      [T_HERO + 0.80, 0]],
        "escala": {"mola": MOLA_HERO, "em": T_HERO, "de": 1.08, "para": 1.0},
    })
    C.append({
        "tipo": "imagem", "src": asset("focused-editor.jpg"),
        "larg": HW, "alt": HH, "ajuste": "cobrir", "x": HX, "y": HY,
        "opacidade": [[T_HERO, 0, "outCubic"], [T_HERO + 0.30, 0.6],
                      [T_HERO + 0.75, 1]],
        "escala": {"mola": MOLA_HERO, "em": T_HERO, "de": 1.08, "para": 1.0},
    })
    # contador 3/8 (:286-309, opacidade de 0 a 1 entre os frames 18 e 28)
    C.append({"tipo": "texto", "texto": "3 / 8", "tamanho": 15, "peso": 700,
              "cor": "#FFFFFF80", "espacamento": 1.5,
              **viva(HR - 14 - larg_texto("3 / 8", 15) / 2, HT - 22, 1.5, 34),
              "opacidade": [[kf(18), 0], [kf(28), 1, "outCubic"]]})

    # ═══ COMPARADOR (:312-420) — 0 -> 48% do hero, frames 48..78 ═══════
    T_S0, T_S1, T_SOP = kf(48), kf(78), kf(55)
    _fim = 0.48
    # o easing vai no keyframe que COMECA o trecho; no ultimo ele e ignorado
    _dx = [[T_S0, HL, "outCubic"], [T_S1, HL + HW * _fim]]
    _op_s = [[T_S0, 0, "outCubic"], [T_SOP, 1]]
    # o lado "before": a mesma foto tingida, revelada por cortina.
    # `revelar` corta em coordenadas do QUADRO centradas na camada, entao a
    # fracao do hero vira prog = (960 - HW/2 + HW*f) / 1920.
    C.append({
        "tipo": "imagem", "src": asset("focused-editor.jpg"),
        "larg": HW, "alt": HH, "ajuste": "cobrir", "x": HX, "y": HY,
        "tingir": "#6E7A85", "inicio": T_S0,
        "revelar": {"prog": [[T_S0, (960 - HW / 2) / 1920, "outCubic"],
                             [T_S1, (960 - HW / 2 + HW * _fim) / 1920]],
                    "dir": "esq"},
        "opacidade": _op_s})
    C.append({"tipo": "retangulo", "larg": 2, "alt": HH, "cor": "#FFFFFFB3",
              "x": _dx, "y": HY, "inicio": T_S0, "opacidade": _op_s})
    C.append({"tipo": "retangulo", "larg": 32, "alt": 48, "raio": 8,
              "cor": "#FFFFFF", "x": _dx, "y": HY, "inicio": T_S0,
              "opacidade": _op_s})
    # os seis pontinhos do punho: identicos e sem identidade — `repetir` serve
    C.append({"tipo": "elipse", "raio": 1.6, "cor": "#00000059",
              "x": _dx, "y": HY, "inicio": T_S0, "opacidade": _op_s,
              "repetir": {"cols": 2, "linhas": 3, "espX": 7, "espY": 7,
                          "atraso": 0.0, "ordem": "linha"}})
    C.append({"tipo": "texto", "texto": "BEFORE", "tamanho": 16, "peso": 700,
              "cor": "#FFFFFFB3", "espacamento": 2.4, "inicio": T_S0,
              "x": HL + 16 + (larg_texto("BEFORE", 16) + 14) / 2, "y": HB + 30,
              "opacidade": _op_s})
    C.append({"tipo": "texto", "texto": "AFTER", "tamanho": 16, "peso": 700,
              "cor": MARCA, "espacamento": 2.4, "inicio": T_S0,
              "x": HR - 16 - (larg_texto("AFTER", 16) + 12) / 2, "y": HB + 30,
              "opacidade": _op_s})

    # ═══ PINCEL (:425-453) — frames 90..110, 650->780 / 420->350 ═══════
    T_B0, T_B1 = kf(90), kf(110)
    _bx = [[T_B0, HL + 650, "inOutQuad"], [T_B1, HL + 780]]
    _by = [[T_B0, HT - 420, "inOutQuad"], [T_B1, HT - 350]]
    _op_b = [[T_B0, 0, "outCubic"], [kf(100), 1]]
    C.append({"tipo": "elipse", "raio": 22, "cor": "#3B82F62E",
              "contorno": "#FFFFFFCC", "contorno_larg": 2,
              "x": _bx, "y": _by, "inicio": T_B0, "opacidade": _op_b})

    # ═══ BARRA DE ACOES, DIREITA (:458-535) ════════════════════════════
    # right 90, centrada em altura; entra deslizando 60px pela direita
    TBX, TBY = px(1920 - 90 - 32), 0.0
    T_TB = kf(22)
    MOLA_TB = {"damping": 16, "stiffness": 100, "mass": 0.5}
    C.append({"tipo": "retangulo", "larg": 64, "alt": 168, "raio": 20,
              "cor": "#0A0A0CB3", "contorno": "#FFFFFF14", "contorno_larg": 1,
              "x": {"mola": MOLA_TB, "em": T_TB, "de": TBX + 60, "para": TBX},
              "y": TBY, "inicio": kf(20), "opacidade": entra(T_TB, 0.35)})
    _icones = (
        ("#3B82F622", "#3B82F644", MARCA, 2.0,
         "M4 20 L6 14 L16 4 L20 8 L10 18 Z M4 20 L10 18"),
        ("#FFFFFF0A", "#FFFFFF10", "#FFFFFF80", 2.0,
         "M4 15 V19 H20 V15 M12 3 V15 M7 10 L12 15 L17 10"),
        ("#FFFFFF0A", "#FFFFFF10", "#FFFFFF59", 2.0,
         "M4 6 H20 M6 6 V20 H18 V6 M10 3 H14"),
    )
    for k, (bg, bd, tin, lw, d) in enumerate(_icones):
        by = TBY + 52 - k * 52
        tb = T_TB + k * BLOCO
        _mx = {"mola": MOLA_TB, "em": tb, "de": TBX + 60, "para": TBX}
        C.append({"tipo": "retangulo", "larg": 44, "alt": 44, "raio": 12,
                  "cor": bg, "contorno": bd, "contorno_larg": 1,
                  "x": _mx, "y": by, "inicio": kf(20),
                  "opacidade": entra(tb, 0.35)})
        C.append({"tipo": "path", "d": d, "cor": "#00000000", "contorno": tin,
                  "contorno_larg": lw, "escala": 0.78, "x": _mx, "y": by,
                  "inicio": kf(20), "opacidade": entra(tb + 0.06, 0.35)})

    # ═══ TIRA DE MINIATURAS (:539-590) — bottom 178 ════════════════════
    FY = py(1080 - 178 - 40)
    T_F = kf(35)
    MOLA_F = {"damping": 18, "stiffness": 90, "mass": 0.5}
    C.append({"tipo": "retangulo", "larg": 452, "alt": 80, "raio": 18,
              "cor": "#0A0A0CA6", "contorno": "#FFFFFF10", "contorno_larg": 1,
              "x": 0, "y": {"mola": MOLA_F, "em": T_F, "de": FY - 40, "para": FY},
              "inicio": kf(33), "opacidade": entra(T_F, 0.35)})
    THUMBS = ["surrealist-concept_800w.jpg", "brand-identity-system_800w.jpg",
              "character-performance_800w.jpg", "launch-film-suite_800w.jpg",
              "director-board_800w.jpg", "ugc-product-story_800w.jpg"]
    for i, nome in enumerate(THUMBS):
        t = kf(36 + i * 3)
        C.append({
            "tipo": "imagem", "src": asset(nome), "larg": 60, "alt": 60,
            "ajuste": "cobrir", "x": -180 + i * 72,
            "y": {"mola": MOLA_F, "em": T_F, "de": FY - 40, "para": FY},
            "inicio": kf(33), "opacidade": entra(t, 0.3),
            "escala": {"mola": {"damping": 14, "stiffness": 120, "mass": 0.4},
                       "em": t, "de": 0.7, "para": 1.0}})
    # a ativa (:149-152) corre da 0 a 5 entre os frames 40 e 105 — um anel
    # unico saltando de posicao vale mais que seis aneis cruzando opacidade
    _pas = (kf(105) - kf(40)) / 6.0
    _salto = []
    for i in range(6):
        a = kf(40) + i * _pas
        _salto += [[a, -180 + i * 72], [a + _pas * 0.82, -180 + i * 72]]
    C.append({"tipo": "retangulo", "larg": 66, "alt": 66, "raio": 11,
              "cor": "#3B82F61A", "contorno": MARCA, "contorno_larg": 2,
              "x": _salto, "y": FY, "inicio": kf(40),
              "escala": {"mola": MOLA_DESTAQUE, "em": kf(40), "de": 0.8,
                         "para": 1.12},
              "opacidade": entra(kf(40), 0.2)})

    # ═══ BARRA DE FERRAMENTAS, ESQUERDA (:970-1020) — frame 85 ═════════
    LTX = px(50 + 26)
    T_LT = kf(85)
    C.append({"tipo": "retangulo", "larg": 52, "alt": 132, "raio": 18,
              "cor": "#0A0A0CB3", "contorno": "#FFFFFF10", "contorno_larg": 1,
              **viva(LTX, 0, 2.0, 61), "inicio": T_LT,
              "opacidade": entra(T_LT, 0.3),
              "escala": {"mola": MOLA_ESTADO, "em": T_LT, "de": 0.9, "para": 1.0}})
    C.append({"tipo": "retangulo", "larg": 36, "alt": 36, "raio": 10,
              "cor": "#3B82F625", "contorno": "#3B82F644", "contorno_larg": 1,
              "x": LTX, "y": 0, "inicio": T_LT, "opacidade": entra(T_LT, 0.3)})
    # os dois quadradinhos inativos: mesma forma, mesma animacao -> `repetir`
    C.append({"tipo": "retangulo", "larg": 14, "alt": 14, "raio": 3,
              "cor": "#00000000", "contorno": "#FFFFFF40", "contorno_larg": 1.5,
              "x": LTX, "y": 0, "inicio": T_LT, "opacidade": entra(T_LT, 0.3),
              "repetir": {"cols": 1, "linhas": 2, "espX": 0, "espY": 80,
                          "atraso": 0.03, "ordem": "linha"}})
    C.append({"tipo": "elipse", "raio": 7, "cor": "#00000000",
              "contorno": MARCA, "contorno_larg": 1.5, "x": LTX, "y": 0,
              "inicio": T_LT, "opacidade": entra(T_LT + 0.05, 0.3)})

    # ═══ PAINEL DE PARAMETROS (:1024-1115) — left 75, bottom 310 ═══════
    PPX, PPY = px(175), py(709)
    T_PP = kf(70)
    MOLA_PP = {"damping": 18, "stiffness": 90, "mass": 0.5}
    _ppy = {"mola": MOLA_PP, "em": T_PP, "de": PPY - 20, "para": PPY}
    C.append({"tipo": "retangulo", "larg": 200, "alt": 122, "raio": 16,
              "cor": "#0A0A0CBF", "contorno": "#FFFFFF10", "contorno_larg": 1,
              "x": PPX, "y": _ppy, "inicio": T_PP,
              "opacidade": entra(T_PP, 0.3)})
    PARAMS = (("CFG Scale", "7.5", 60), ("Steps", "28", 70), ("Sampler", "DPM++", 45))
    for i, (rot, val, alvo) in enumerate(PARAMS):
        yl = py(671 + 34 * i)
        C.append({"tipo": "texto", "texto": rot, "tamanho": 12, "peso": 500,
                  "cor": "#FFFFFF66", "y": yl, "inicio": T_PP,
                  "x": px(91) + larg_texto(rot, 12) / 2,
                  "opacidade": entra(T_PP + i * BLOCO, 0.3)})
        C.append({"tipo": "texto", "texto": val, "tamanho": 12, "peso": 600,
                  "cor": "#FFFFFF8C", "y": yl, "inicio": T_PP,
                  "x": px(259) - larg_texto(val, 12) / 2,
                  "opacidade": entra(T_PP + i * BLOCO, 0.3)})
        a, b = kf(72 + i * 5), kf(87 + i * 5)
        w = 168 * alvo / 100.0
        C.append({"tipo": "retangulo", "raio": 2, "alt": 4,
                  "larg": [[a, 0, "outCubic"], [b, w]],
                  "x": [[a, px(91), "outCubic"], [b, px(91) + w / 2]],
                  "y": py(684 + 34 * i), "inicio": T_PP,
                  "cor": {"tipo": "linear", "cores": [MARCA, CIANO],
                          "de": [-w / 2, 0], "para": [w / 2, 0]},
                  "opacidade": entra(a, 0.2)})
    # os tres trilhos cinza sao identicos e empilhados: textura, nao elemento
    C.append({"tipo": "retangulo", "larg": 168, "alt": 4, "raio": 2,
              "cor": "#FFFFFF12", "x": PPX, "y": py(684 + 34),
              "inicio": T_PP, "opacidade": entra(T_PP, 0.3),
              "repetir": {"cols": 1, "linhas": 3, "espX": 0, "espY": 34,
                          "atraso": 0.04, "ordem": "linha"}})

    # ═══ BARRA DE PROMPT (:594-966) — bottom 40, 860 de largura ════════
    BX, BY, BW, BH = 0.0, py(978), 860, 124
    T_P = kf(62)
    MOLA_P = {"damping": 16, "stiffness": 80, "mass": 0.6}
    _by_p = {"mola": MOLA_P, "em": T_P, "de": BY - 50, "para": BY}
    C.append({"tipo": "retangulo", "larg": BW, "alt": BH, "raio": 22,
              "cor": "#0A0A0CD9", "contorno": "#FFFFFF14", "contorno_larg": 1,
              "x": BX, "y": _by_p, "inicio": kf(60),
              "opacidade": entra(T_P, 0.35)})

    # texto se digitando (:169-172): 57 caracteres entre os frames 64 e 92.
    # Uma camada so, com `revelar` de cortina — quebrar em pedacos abriria
    # buraco entre eles, porque larg_texto e estimativa e nao medida.
    PROMPT = "A serene mountain lake at golden hour, cinematic lighting"
    T_T0, T_T1 = kf(64), kf(92)
    _wp = larg_texto(PROMPT, 16) * 0.92
    C.append({"tipo": "texto", "texto": PROMPT, "tamanho": 16, "peso": 400,
              "cor": "#FFFFFFBF", "x": px(548) + _wp / 2, "y": py(939),
              "inicio": T_T0,
              "revelar": {"prog": [[T_T0, (960 - _wp / 2) / 1920, "linear"],
                                   [T_T1, (960 + _wp / 2) / 1920]],
                          "dir": "esq"}})
    C.append({"tipo": "texto", "texto": "|", "tamanho": 16, "peso": 400,
              "cor": MARCA, "y": py(939), "inicio": T_T0,
              "x": [[T_T0, px(548), "linear"], [T_T1, px(548) + _wp]],
              "opacidade": pulso(0.5, 0.3, 0.05, 77)})

    # linha do prompt negativo (:669-712) — mola de estado, frame 75
    T_N = kf(75)
    _wneg = larg_texto("NEG", 11) + 16
    _yn = {"mola": MOLA_ESTADO, "em": T_N, "de": py(977), "para": py(967)}
    C.append({"tipo": "retangulo", "larg": _wneg, "alt": 20, "raio": 8,
              "cor": "#F43F5E26", "contorno": "#F43F5E40", "contorno_larg": 1,
              "x": px(548) + _wneg / 2, "y": _yn, "inicio": T_N,
              "opacidade": entra(T_N, 0.3)})
    C.append({"tipo": "texto", "texto": "NEG", "tamanho": 11, "peso": 700,
              "cor": ACENTO, "espacamento": 0.5,
              "x": px(548) + _wneg / 2, "y": _yn, "inicio": T_N,
              "opacidade": entra(T_N, 0.3)})
    C.append({"tipo": "texto", "texto": "blur, watermark, low quality...",
              "tamanho": 13, "peso": 400, "italico": True, "cor": "#FFFFFF33",
              "x": px(548) + _wneg + 8 + larg_texto("blur, watermark, low quality...", 13) / 2,
              "y": _yn, "inicio": T_N, "opacidade": entra(T_N + 0.06, 0.3)})

    C.append({"tipo": "retangulo", "larg": 832, "alt": 1, "cor": "#FFFFFF14",
              "x": BX, "y": py(984), "inicio": T_P,
              "opacidade": entra(T_P + 0.1, 0.3)})

    # ─── deck de baixo: modo IMG/VID, slots, modelo, gerar ─────────────
    DY = py(1011)
    T_M0, T_M1 = kf(85), kf(95)
    BEZ = [0.2, 0, 0, 1]
    C.append({"tipo": "retangulo", "larg": 110, "alt": 34, "raio": 12,
              "cor": "#FFFFFF0D", "x": px(599), "y": DY, "inicio": T_P,
              "opacidade": entra(T_P + 0.1, 0.3)})
    C.append({"tipo": "retangulo", "larg": 50, "alt": 28, "raio": 10,
              "cor": "#FFFFFF1A", "y": DY, "inicio": T_P,
              "x": [[T_M0, px(572), BEZ], [T_M1, px(624)]],
              "opacidade": entra(T_P + 0.1, 0.3)})
    _op_img = [[T_P, 0], [T_P + 0.3, 1, "outCubic"], [kf(88), 1], [kf(93), 0]]
    _op_vid = [[T_P, 0], [T_P + 0.3, 1, "outCubic"], [kf(88), 1], [kf(93), 0]]
    C.append({"tipo": "texto", "texto": "IMG", "tamanho": 12, "peso": 600,
              "cor": MARCA, "x": px(572), "y": DY, "inicio": T_P,
              "opacidade": _op_img})
    C.append({"tipo": "texto", "texto": "IMG", "tamanho": 12, "peso": 600,
              "cor": "#FFFFFF59", "x": px(572), "y": DY, "inicio": kf(88),
              "opacidade": [[kf(88), 0], [kf(93), 1, "outCubic"]]})
    C.append({"tipo": "texto", "texto": "VID", "tamanho": 12, "peso": 600,
              "cor": "#FFFFFF59", "x": px(624), "y": DY, "inicio": T_P,
              "opacidade": _op_vid})
    C.append({"tipo": "texto", "texto": "VID", "tamanho": 12, "peso": 600,
              "cor": SUCESSO, "x": px(624), "y": DY, "inicio": kf(88),
              "opacidade": [[kf(88), 0], [kf(93), 1, "outCubic"]]})

    # slots de quadro de referencia (:785-843)
    C.append({"tipo": "retangulo", "larg": 32, "alt": 40, "raio": 8,
              "cor": "#00000000", "contorno": "#FFFFFF1F", "contorno_larg": 1,
              "x": px(680), "y": DY, "inicio": T_P,
              "opacidade": entra(T_P + 0.14, 0.3)})
    C.append({"tipo": "path", "d": "M -5 0 L 5 0 M 0 -5 L 0 5",
              "cor": "#00000000", "contorno": "#FFFFFF3D", "contorno_larg": 1.5,
              "x": px(680), "y": DY, "inicio": T_P,
              "opacidade": entra(T_P + 0.16, 0.3)})
    C.append({"tipo": "retangulo", "larg": 32, "alt": 40, "raio": 8,
              "cor": {"tipo": "linear", "cores": ["#6366f1", "#ec4899", "#f59e0b"],
                      "de": [-16, -20], "para": [16, 20], "paradas": [0, 0.5, 1]},
              "x": px(718), "y": DY, "inicio": T_P,
              "opacidade": entra(T_P + 0.18, 0.3)})

    # chip do modelo, engrenagem e botao de gerar (:846-963)
    _wchip = larg_texto("nano-banana", 12) + 38
    C.append({"tipo": "retangulo", "larg": _wchip, "alt": 34, "raio": 10,
              "cor": "#FFFFFF0A", "contorno": "#FFFFFF10", "contorno_larg": 1,
              "x": px(1310) - 42 - _wchip / 2, "y": DY, "inicio": T_P,
              "opacidade": entra(T_P + 0.14, 0.3)})
    C.append({"tipo": "texto", "texto": "nano-banana", "tamanho": 12,
              "peso": 500, "cor": "#FFFFFF66", "y": DY, "inicio": T_P,
              "x": px(1310) - 42 - _wchip / 2 - 7,
              "opacidade": entra(T_P + 0.16, 0.3)})
    C.append({"tipo": "retangulo", "larg": 34, "alt": 34, "raio": 10,
              "cor": "#FFFFFF0A", "contorno": "#FFFFFF10", "contorno_larg": 1,
              "x": px(1309), "y": DY, "inicio": T_P,
              "opacidade": entra(T_P + 0.18, 0.3)})
    C.append({"tipo": "path",
              "d": ("M -6 -2.5 L -2.5 -6 L 2.5 -6 L 6 -2.5 L 6 2.5 "
                    "L 2.5 6 L -2.5 6 L -6 2.5 Z M -2.4 0 L 2.4 0"),
              "cor": "#00000000", "contorno": "#FFFFFF59", "contorno_larg": 1.4,
              "x": px(1309), "y": DY, "inicio": T_P,
              "opacidade": entra(T_P + 0.2, 0.3)})
    GBX = px(1355)
    C.append({"tipo": "retangulo", "larg": 42, "alt": 34, "raio": 10,
              "cor": MARCA, "x": GBX, "y": DY, "inicio": T_P,
              "opacidade": [[T_P, 0], [T_P + 0.3, 1, "outCubic"],
                            [kf(88), 1], [kf(93), 0]],
              "escala": {"mola": MOLA_DESTAQUE, "em": T_P + 0.2, "de": 0.6,
                         "para": 1.0}})
    C.append({"tipo": "retangulo", "larg": 42, "alt": 34, "raio": 10,
              "cor": SUCESSO, "x": GBX, "y": DY, "inicio": kf(88),
              "opacidade": [[kf(88), 0], [kf(93), 1, "outCubic"]]})
    C.append({"tipo": "path", "d": "M 0 7 L 0 -7 M -7 0 L 0 -7 L 7 0",
              "cor": "#00000000", "contorno": "#FFFFFF", "contorno_larg": 2.5,
              "x": GBX, "y": DY, "inicio": T_P,
              "opacidade": entra(T_P + 0.22, 0.3)})
    # anel de progresso (:931-961): o `traco` corre o CONTORNO — por isso o
    # retangulo precisa de preenchimento vazio
    C.append({"tipo": "retangulo", "larg": 54, "alt": 46, "raio": 14,
              "cor": "#00000000", "contorno": SUCESSO, "contorno_larg": 2.5,
              "x": GBX, "y": DY, "inicio": kf(100),
              "traco": [[kf(100), 0, "outCubic"], [kf(115), 1]],
              "opacidade": [[kf(100), 0], [kf(101), 1, "linear"],
                            [kf(114), 1, "linear"], [kf(115), 0.6]]})

    # ═══ TITULO (:1119-1162) — bottom 175, left 75 ═════════════════════
    _lab = "AI-POWERED"
    C.append(rotulo(_lab, kf(80), py(828), MUDO, 20,
                    px(75) + (larg_texto(_lab, 20) + 5 * (len(_lab) - 1)) / 2, 5, 400))
    # -0.03em de tracking (:1155) mais a folga da estimativa de largura
    _tit, _tam, _ap = "Creative Studio", 60, 0.88
    _x = px(75)
    for i, ch in enumerate(_tit):
        w = larg_char(ch, _tam) * _ap
        if ch != " ":
            f = i / (len(_tit) - 1)
            cor = "#%02X%02X%02X" % (int(59 + (6 - 59) * f),
                                     int(130 + (182 - 130) * f),
                                     int(246 + (212 - 246) * f))
            C += titulo(ch, kf(88) + i * LETRA, py(875), _tam, cor, 900,
                        LETRA, _x + w / 2)
        _x += w

    return {"duracao": dur, "fundo": BG, "camadas": C}
