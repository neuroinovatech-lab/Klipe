# -*- coding: utf-8 -*-
"""templates.py — a cena Templates do CreativlyBrandVideo.

Fundo claro (#FAFAFA, :120) com grade de pontos respirando (:123-131), duas
marcas d'agua "TEMPLATES" italicas sobrepostas (:133-187), oito formas
decorativas girando (:189-227) e sete losangos amarelos (:229-249). Por cima,
o cabecalho — rotulo "WORKFLOW" que troca de cor (:71-75), titulo 120px letra
a letra (:295-301), sublinhado que abre (:94-101) e o separador de losango
(:337-373). Embaixo, a grade 3x2 de cards (:378-608): entram com atraso de 5
frames (:389), sobem 100px, escala 0.6->1, filete colorido no topo que corre da
esquerda (:516-527), brilho varrendo (:504-513) e, de 1,0 s a 3,0 s, o anel
azul percorre os seis cards um a um (:104-109).
"""
import math

from .base import *


def cena(dur: float) -> dict:
    cam: list[dict] = []

    # ── geometria da grade 3x2 ────────────────────────────────────────
    # :385 padding "220px 80px 60px", :383-384 3 colunas x 2 linhas, gap 20.
    # O padding do topo virou 268 e nao 220: no HTML o cabecalho e um bloco que
    # empurra: aqui cada peca tem `y` absoluto e nada empurra ninguem. Com 220 o
    # separador (y 313) caia ABAIXO da borda de cima dos cards (y 320) e era
    # desenhado por cima da foto do card 2 — cabecalho e depois na lista, entao
    # ganha. 268 e a altura que a pilha do cabecalho realmente ocupa: rotulo,
    # titulo de 120px COM a barriga do "p", sublinhado, tagline e separador,
    # com 12px de ar entre cada um. Os 48px que saem da altura do card saem de
    # onde nao doi — a foto e `cobrir`, ela so recorta um pouco mais.
    TOPO, RODAPE, GAP = 268.0, 52.0, 20.0
    CW = (1920 - 160 - 40) / 3.0                    # 573.33
    CH = (1080 - TOPO - RODAPE - GAP) / 2.0         # 370
    COLS = [-(CW + 20), 0.0, (CW + 20)]
    LINHAS = [540 - (TOPO + CH / 2),
              540 - (TOPO + CH + GAP + CH / 2)]     # +87, -303

    ITENS = [
        ("Surrealist Concept Art", "#FF5F56", "surrealist-concept_800w.jpg"),
        ("Launch Film + Ad Suite", "#FFBD2E", "launch-film-suite_800w.jpg"),
        ("UGC Product Story", "#27C93F", "ugc-product-story_800w.jpg"),
        ("Director Storyboard", "#3357FF", "director-board_800w.jpg"),
        ("Character Perf Rig", "#A833FF", "character-performance_800w.jpg"),
        ("Brand Identity System", "#FF33A8", "brand-identity-system_800w.jpg"),
    ]

    # ══ FUNDO ════════════════════════════════════════════════════════
    # :123-131 — grade de pontos de 40px, opacidade respirando 0.25..0.45.
    # Aqui `repetir` E o certo: e textura, nao elemento com identidade.
    cam.append({
        "tipo": "elipse", "raio": 1.6, "cor": "#0000001A",
        "opacidade": pulso(0.35, 0.10, 0.02, 7),
        "repetir": {"cols": 49, "linhas": 28, "espX": 40, "espY": 40,
                    "atraso": 0.0, "ordem": "linha"},
    })

    # :133-159 — "TEMPLATES" 320px italica, -8deg, opacidade 0.06.
    # :161-187 — o fantasma a 340px, -6deg, deslocado, a 40% da opacidade.
    md = marca_dagua("TEMPLATES", 320, MARCA, -8.0, 0.06, 0.0)
    md["escala"] = {"mola": MOLA_TEXTO, "em": 0.1, "de": 0.80, "para": 1.00}
    cam.append(md)
    gh = marca_dagua("TEMPLATES", 340, CIANO, -6.0, 0.024, 21.6)
    gh["x"] = 19.2
    gh["espacamento"] = 17
    gh["escala"] = {"mola": MOLA_TEXTO, "em": 0.1, "de": 0.76, "para": 0.95}
    cam.append(gh)

    # :189-227 — oito formas de contorno: triangulo de lado 60 ou circulo de
    # raio 25, traco 1.5, opacidade sobe ate 0.12 em 20 frames, cada uma
    # girando na sua velocidade. Anel = cor transparente + contorno (armadilha 2).
    DECO = [
        (-636.0, -234.0, 0, 0.62, MARCA),
        (678.0, 250.5, 1, -0.85, "#FFBD2E"),
        (-114.0, 364.5, 1, 0.31, "#27C93F"),
        (354.0, -386.0, 0, -0.44, "#3357FF"),
        (-780.0, 127.0, 1, 0.77, MARCA),
        (822.0, -129.5, 1, -0.19, "#FF33A8"),
        (-312.0, 3.5, 0, 0.53, "#FF5F56"),
        (156.0, -300.5, 1, -0.68, "#FFBD2E"),
    ]
    for i, (dx, dy, tri, vel, cor) in enumerate(DECO):
        base = {
            **viva(dx, dy, 15, 610 + i * 3),
            "cor": "#00000000", "contorno": cor, "contorno_larg": 1.5,
            "rotacao": [[0, 0, "linear"], [dur, vel * dur * FPS]],
            "opacidade": [[0, 0, "outCubic"], [20 * F, 0.12]],
        }
        if tri == 0:
            cam.append({"tipo": "path", "d": "M 30 0 L 60 52 L 0 52 Z",
                        "centrar": True, **base})
        else:
            cam.append({"tipo": "elipse", "raio": 25, **base})

    # :229-249 + Rotating3D.tsx:205-268 — losangos flutuantes: quadrado a 45
    # graus girando em rotateX/rotateY. Sem 3D no motor, o giro vira o que ele
    # produz na tela: escalaX = |cos(rotY)| e escalaY = |cos(rotX)|, amostrados.
    DIAM = [
        (-860.0, 400.0, 40, 0.8, 5, "#FFD60040"),
        (817.5, 312.5, 55, 1.2, 8, "#FFD60026"),
        (-792.5, -327.5, 35, 0.6, 12, "#FFD6001A"),
        (745.0, -265.0, 50, 1.0, 10, "#FFD60040"),
        (15.0, 465.0, 30, 1.5, 15, "#FFD60026"),
        (872.5, 7.5, 25, 0.9, 18, "#FFD6001A"),
        (-887.5, 17.5, 45, 0.7, 7, "#FFD60040"),
    ]
    for i, (dx, dy, s, vel, atraso, cor) in enumerate(DIAM):
        t0 = atraso * F
        passo = 4
        quadros = list(range(0, int(dur * FPS) + passo, passo))
        ex, ey = [], []
        for k, f in enumerate(quadros):
            fim = k == len(quadros) - 1
            vx = max(0.06, abs(math.cos(math.radians(f * 2.0 * vel))))
            vy = max(0.06, abs(math.cos(math.radians(f * 1.5 * vel))))
            ex.append([f * F, round(vx, 4)] if fim else [f * F, round(vx, 4), "linear"])
            ey.append([f * F, round(vy, 4)] if fim else [f * F, round(vy, 4), "linear"])
        cam.append({
            "tipo": "retangulo", "larg": s, "alt": s, "raio": 2, "cor": cor,
            "rotacao": 45, **viva(dx, dy, 12, 720 + i * 4),
            "escalaX": ex, "escalaY": ey,
            "escala": {"mola": MOLA_ESTADO, "em": t0, "de": 0.0, "para": 1.0},
            "opacidade": [[t0, 0, "outCubic"], [t0 + 0.45, 0.8]],
        })

    # ══ OS SEIS CARDS ════════════════════════════════════════════════
    # :390-394 mola damping 14 / stiffness 80 / mass 0.6; :389 atraso i*5;
    # :396-398 escala 0.6->1, sobe 100px. Card e UI: MOLA_ESTADO, sem quique.
    for i, (nome, cor, img) in enumerate(ITENS):
        cx = COLS[i % 3]
        cy = LINHAS[i // 3]
        t = 8 * F + i * BLOCO
        nx = viva(cx, cy, 3, 40 + i * 7)["x"]     # :425-426 micro-ruido de 3px
        esc = {"mola": MOLA_ESTADO, "em": t, "de": 0.6, "para": 1.0}
        op = entra(t, 0.4)

        # :477 — escala e deslocamento saem da MESMA mola, entao o que esta
        # deslocado do centro do card tem que encolher junto: uma peca a `o` px
        # do centro esta em cy - 100(1-p) + o(0,6 + 0,4p) — que e a mola de
        # (cy - 100 + 0,6o) ate (cy + o). Sem isto o filete do topo descola.
        ry = lambda o: {"mola": MOLA_ESTADO, "em": t,
                        "de": cy - 100 + 0.6 * o, "para": cy + o}
        rx = lambda o: {"mola": MOLA_ESTADO, "em": t,
                        "de": cx + 0.6 * o, "para": cx + o}
        ny = ry(0.0)

        # janela em que ESTE card e o ativo (:104-109 — frames 30..90, 10 por card)
        a = 1.0 + i / 3.0
        b = a + 1 / 3.0
        aceso = [[0, 0], [max(0.02, a - 0.12), 0, "outCubic"], [a + 0.06, 1.0],
                 [b - 0.06, 1.0, "outCubic"], [min(dur, b + 0.12), 0]]
        halo = [[k[0], k[1] * 0.42] + k[2:] for k in aceso]

        # sombra do card (:481) — a helper, com a subida do card por cima
        s = sombra(cx, cy, CW, CH, t, raio=20, n=1)[0]
        s["x"] = nx
        s["y"] = ry(-8.0)
        s["escala"] = esc
        cam.append(s)

        # brilho azul do card ativo (:450-452 — 0 0 20px brand66 + 40px brand33)
        cam.append({"tipo": "retangulo", "larg": CW + 44, "alt": CH + 44,
                    "raio": 24, "cor": MARCA, "blur": 30,
                    "x": nx, "y": ny, "escala": esc, "opacidade": halo})

        # a foto (:485-492) — objectFit cover
        cam.append({"tipo": "imagem", "src": asset(img), "larg": CW, "alt": CH,
                    "ajuste": "cobrir", "x": nx, "y": ny, "escala": esc,
                    "opacidade": op})

        # veu escuro de baixo para cima (:494-502).
        # raio 10 e nao 20 (:474): `imagem` recorta em RETANGULO, sem raio — com
        # 20 o canto quadrado da foto aparecia por fora do veu e do anel.
        cam.append({"tipo": "retangulo", "larg": CW, "alt": CH, "raio": 10,
                    "cor": {"tipo": "linear",
                            "cores": ["#000000D9", "#00000033", "#00000000"],
                            "de": [0, CH / 2], "para": [0, -CH / 2],
                            "paradas": [0.0, 0.5, 1.0]},
                    "x": nx, "y": ny, "escala": esc, "opacidade": op})

        # brilho varrendo (:504-513) — banda a -15 graus, dentro do card
        ts, te = t + 15 * F, t + 50 * F
        cam.append({"tipo": "retangulo", "larg": 100, "alt": 330, "rotacao": -15,
                    "cor": {"tipo": "linear",
                            "cores": ["#FFFFFF00", "#FFFFFF33", "#FFFFFF00"],
                            "de": [-50, 0], "para": [50, 0]},
                    "x": [[ts, cx - 190, "outCubic"], [te, cx + 190]],
                    "y": ny, "escala": esc,
                    "opacidade": [[ts, 0, "outCubic"], [ts + 0.2, 1.0],
                                  [te - 0.2, 1.0, "outCubic"], [te, 0]]})

        # filete colorido no topo, correndo da esquerda (:516-527)
        td, tf = t + 5 * F, t + 30 * F
        cam.append({"tipo": "retangulo", "alt": 3, "raio": 2,
                    "larg": [[td, 0, "outCubic"], [tf, CW]],
                    "cor": {"tipo": "linear", "cores": [cor, MARCA, CIANO, "#06B6D400"],
                            "de": [-CW / 2, 0], "para": [CW / 2, 0],
                            "paradas": [0.0, 0.35, 0.7, 1.0]},
                    "x": [[td, cx - CW / 2, "outCubic"], [tf, cx]],
                    "y": ry(CH / 2 - 1.5), "escala": esc,
                    "opacidade": entra(td, 0.2)})

        # o anel que acende no card ativo (:454-461 — borda vira COLORS.brand)
        cam.append({"tipo": "retangulo", "larg": CW, "alt": CH, "raio": 10,
                    "cor": "#00000000", "contorno": MARCA, "contorno_larg": 3,
                    "x": nx, "y": ny, "escala": esc, "opacidade": aceso})

        # indice "01".."06" (:556-583) — 11px, italico, espacado, 0.7
        idx = f"{i + 1:02d}"
        cam.append({"tipo": "texto", "texto": idx, "tamanho": 11, "peso": 600,
                    "italico": True, "cor": MARCA, "espacamento": 2,
                    "x": rx(-CW / 2 + 20 + larg_texto(idx, 11) / 2),
                    "y": ry(-138.0), "escala": esc,
                    "opacidade": [[t + 0.25, 0, "outCubic"], [t + 0.5, 0.7]]})

        # o titulo do card (:584-603) — 22px italico com sombra de texto
        cam.append({"tipo": "texto", "texto": nome, "tamanho": 22, "peso": 700,
                    "italico": True, "cor": TEXTO,
                    "sombra": [{"x": 0, "y": 2, "blur": 10, "cor": "#000000CC"}],
                    "x": rx(-CW / 2 + 20 + larg_texto(nome, 22) / 2),
                    "y": ry(-162.0), "escala": esc,
                    "opacidade": [[t + 0.2, 0, "outCubic"], [t + 0.45, 1.0]]})

    # ══ CABECALHO (zIndex 10, por cima de tudo) ══════════════════════
    # :266-279 rotulo "WORKFLOW" 18px italico, espacamento 0.2em. A cor anda de
    # cinza para azul e volta (:71-75); o motor nao anima cor, entao sao duas
    # copias cruzando por opacidade — mesmo texto, mesma semente, mesmo tremor.
    cz = rotulo("WORKFLOW", 0.0, 489, MUDO_ESCURO, 18, 0.0, 4, 400)
    cz["italico"] = True
    cam.append(cz)
    az = rotulo("WORKFLOW", 0.0, 489, MARCA, 18, 0.0, 4, 400)
    az["italico"] = True
    az["opacidade"] = [[0, 0, "outCubic"], [dur / 2, 1.0, "outCubic"], [dur, 0]]
    cam.append(az)

    # :281-301 titulo 120px, peso 900, italico, preto — letra a letra
    cam += titulo("Templates", 5 * F, 410, 120, TEXTO_PRETO, 900, LETRA,
                  0.0, True)

    # :303-316 sublinhado que abre de 0 a 400px. E o unico destaque da cena.
    cam.append({"tipo": "retangulo", "alt": 4, "raio": 2, "y": 352,
                "larg": {"mola": MOLA_DESTAQUE, "em": 6 * F, "de": 0, "para": 400},
                "cor": {"tipo": "linear",
                        "cores": ["#3B82F600", MARCA, CIANO, "#06B6D400"],
                        "de": [-200, 0], "para": [200, 0],
                        "paradas": [0.0, 0.35, 0.65, 1.0]},
                "opacidade": [[6 * F, 0, "outCubic"], [0.7, 0.35]]})

    # :319-335 "curated collection" 14px italico, espacamento 0.35em
    tg = rotulo("curated collection", 12 * F, 334, MUDO_ESCURO, 14, 0.0, 5, 400)
    tg["italico"] = True
    cam.append(tg)

    # :337-373 separador: filete, losango de 6px, filete — gap 8
    for dx in (-26.0, 26.0):
        cam.append({"tipo": "retangulo", "larg": 30, "alt": 1, "x": dx, "y": 313,
                    "cor": {"tipo": "linear", "cores": [MARCA, CIANO],
                            "de": [-15, 0], "para": [15, 0]},
                    "opacidade": [[0.5, 0, "outCubic"], [0.8, 0.5]]})
    cam.append({"tipo": "retangulo", "larg": 6, "alt": 6, "rotacao": 45,
                **viva(0.0, 313, 2, 311),
                "cor": {"tipo": "linear", "cores": [MARCA, CIANO],
                        "de": [-3, -3], "para": [3, 3]},
                "opacidade": [[0.5, 0, "outCubic"], [0.8, 0.5]]})

    return {"duracao": dur, "fundo": BG_BRANCO, "camadas": cam}
