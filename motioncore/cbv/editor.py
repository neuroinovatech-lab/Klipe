# -*- coding: utf-8 -*-
"""editor.py — a cena Editor do CreativlyBrandVideo.

Uma janela de navegador de 1500x900 com o print do timeline-editor entra
inclinada (rotateX 15deg, :225-233) subindo 150 px e crescendo de 0.8 (:44-46);
sobre ela desce o painel de timeline com 4 trilhas x 3 clipes que acendem em
cascata (:294-359) e um playhead vermelho que atravessa 600 px em 100 frames
(:56-60) desenhando o proprio traco entre os frames 5 e 30 (:66-71). O cartao
branco flutuante com "Video Editing" em 70 px sai de :429-513; o fundo e
#FAFAFA (:107) com "EDIT" de 400 px italico atras (:114-140) e sete diamantes
dourados a deriva (:142-217).

Decisoes: a janela e um CORPO RIGIDO — todos os seus pedacos compartilham as
mesmas keyframes de entrada e a mesma deriva lenta no fim, porque no original
sao um `div` so; a micro-vida por ruido fica no que de fato flutua sozinho
(marca d'agua, diamantes, poeira, brilhos, painel, clipes, cartao). O `traco`
do playhead corre no CONTORNO da linha, nunca no preenchimento; o crescimento
do `layerSep` (translateZ 0->70, :49-53) virou escala 1.0->1.03 no painel e nos
clipes, que e o que a perspectiva 1500 faz com 70 px de profundidade.
"""
import math

from .base import *


def cena(dur: float) -> dict:
    # ── o container 3D do original: 1500x900, rotateX(15deg) ─────────────
    CW, CH = 1500, 900                 # :222-223
    KY = 0.95                          # foreshortening do rotateX(15deg) :229
    ENT = 0.55                         # a mola damping 18/stiff 70 :39-43

    def cxp(px: float) -> float:
        """px do container (esquerda->direita) para x do motor."""
        return px - CW / 2

    def cyp(py: float) -> float:
        """py do container (cima->baixo) para y do motor (positivo SOBE)."""
        return (CH / 2 - py) * KY

    def chh(v: float) -> float:
        return v * KY

    # entrada do corpo rigido: translateY(150) o scale(0.8) o rotateX  :225-233
    # a terceira keyframe e a deriva lenta que impede a janela de morrer parada
    def ex(px: float) -> list:
        v = cxp(px)
        return [[0, v * 0.8], [ENT, v, "outCubic"], [dur, v - 5]]

    def ey(py: float) -> list:
        v = cyp(py)
        return [[0, v * 0.8 - 150], [ENT, v, "outCubic"], [dur, v + 6]]

    def es() -> list:
        return [[0, 0.8], [ENT, 1.0, "outCubic"], [dur, 1.006]]

    C: list[dict] = []

    # ── "EDIT" gigante ao fundo (:114-140) ───────────────────────────────
    # 400 px, italico, rot -8 -> -6, escala 0.7 -> 1, translateY 80 -> 0.
    # O degrade 135deg #3B82F6 -> #06B6D4 (:125) sai de duas copias: a azul
    # inteira e a ciano revelada da direita.
    MOLA_FUNDO = {"damping": 30, "stiffness": 40, "mass": 1.2}      # :77-81
    for cor_wm, rev in ((MARCA, None), (CIANO, {"prog": 0.55, "dir": "dir"})):
        wm = marca_dagua("EDIT", 400, cor_wm, -6.0, 0.11)
        wm["escala"] = {"mola": MOLA_FUNDO, "em": 0.1, "de": 0.7, "para": 1.0}
        wm["y"] = [[0.1, -80, "outCubic"], [1.1, 0]]                # :84
        wm["rotacao"] = [[0.1, -8, "outCubic"], [1.1, -6]]          # :83
        if rev:
            wm["revelar"] = rev
        C.append(wm)

    # ── poeira dourada: a mesma familia dos diamantes, so miuda ──────────
    C += particulas(8, AVISO, MARCA, 18, 7)

    # ── os sete diamantes flutuantes (:142-217) ──────────────────────────
    # (x, y no motor, tamanho, alfa do rgba(255,214,0,a), cor do brilho,
    #  velocidade, atraso em frames) — centros convertidos de left/top.
    DIAMANTES = [
        (-817.5, 437.5, 45, "5C", MARCA, 0.7, 5),        # :143-153
        (737.5, 372.5, 35, "47", MARCA, 1.1, 8),         # :154-164
        (815.0, -235.0, 50, "66", MARCA, 0.5, 12),       # :165-175
        (-865.0, -275.0, 30, "3D", MARCA, 0.9, 15),      # :176-186
        (2.5, 477.5, 25, "33", MARCA_CLARA, 1.3, 10),    # :187-197
        (-750.0, 80.0, 20, "29", None, 1.5, 20),         # :198-206
        (654.0, 26.0, 28, "4D", MARCA_ESCURA, 0.6, 18),  # :207-217
    ]
    for i, (dx, dy, tam, alfa, gcor, vel, atraso) in enumerate(DIAMANTES):
        t0 = atraso * F
        if gcor:                                                   # :151-152
            C.append(brilho(dx, dy, tam * 2.4, gcor, t0, 0.16, 610 + i))
        C.append({
            "tipo": "retangulo", "larg": tam, "alt": tam, "raio": 3,
            "cor": "#FFD600" + alfa,
            **viva(dx, dy, 12, 620 + i),                           # :250-251
            # rotateX/rotateY do original (:246-247) nao existem em 2D. Girar
            # no plano destruiria a leitura de LOSANGO, que e a identidade da
            # forma — entao a rotacao oscila em torno de 45 e o achatamento
            # horizontal e quem faz o papel do giro em profundidade.
            "rotacao": pulso(45, 16, 0.018 * vel, 630 + i),
            "escalaX": pulso(0.86, 0.24, 0.02 * vel, 640 + i),
            "escala": {"mola": {"damping": 16, "stiffness": 80, "mass": 1.0},
                       "em": t0, "de": 0.0, "para": 1.0},          # :246-249
            "opacidade": [[t0, 0, "outCubic"], [t0 + 0.45, 0.8]],
        })

    # ── brilho azul/ciano sob a janela (:236-250) ────────────────────────
    # bottom -60, 70% da largura, altura 180, scaleX 1.2 scaleY 0.8, blur 40
    g1 = brilho(0, cyp(870), 630, MARCA, 10 * F, 0.30, 811)
    g1["ry"], g1["blur"] = 72, 40
    g1["escala"] = pulso(1.0, 0.08, 0.02, 813)                     # :94
    g2 = brilho(0, cyp(880), 470, CIANO, 12 * F, 0.20, 812)
    g2["ry"], g2["blur"] = 56, 40
    g2["escala"] = pulso(1.0, 0.08, 0.02, 814)
    C += [g1, g2]

    # ── a janela: sombra, fantasma desfocado, corpo ──────────────────────
    C += sombra(0, cyp(450), CW, chh(CH), 0.20, 16, 3)              # :288
    # `blur` nao e animavel: o blur 12 -> 0 da entrada (:46) vira uma copia
    # borrada por baixo que se apaga enquanto a nitida chega.
    C.append({"tipo": "retangulo", "larg": CW, "alt": chh(CH), "raio": 16,
              "cor": "#0F0F11", "blur": 12,
              "x": ex(750), "y": ey(450), "escala": es(),
              "opacidade": [[0, 0.5], [0.10, 0.5, "outCubic"], [0.42, 0]]})
    C.append({"tipo": "retangulo", "larg": CW, "alt": chh(CH), "raio": 16,
              "cor": "#0F0F11E6", "contorno": BORDA_CLARA, "contorno_larg": 1,
              "x": ex(750), "y": ey(450), "escala": es(),
              "opacidade": entra(0, 0.28)})

    # o print, na area de conteudo (abaixo da barra de 44 px)
    C.append({"tipo": "imagem", "src": asset("timeline-editor.jpg"),
              "larg": CW - 4, "alt": chh(856), "ajuste": "cobrir",
              "x": ex(750), "y": ey(472), "escala": es(),
              "opacidade": [[0.05, 0, "outCubic"], [0.48, 1]]})
    # o veu preto de 40% para baixo (:265-272)
    C.append({"tipo": "retangulo", "larg": CW - 4, "alt": chh(856),
              "cor": {"tipo": "linear",
                      "cores": ["#00000000", "#00000000", "#000000CC"],
                      "de": [0, -chh(856) / 2], "para": [0, chh(856) / 2],
                      "paradas": [0, 0.4, 1]},
              "x": ex(750), "y": ey(472), "escala": es(),
              "opacidade": entra(0.10, 0.4)})

    # ── a barra de titulo do BrowserWindow ───────────────────────────────
    C.append({"tipo": "retangulo", "larg": CW, "alt": chh(44), "raio": 12,
              "cor": {"tipo": "linear", "cores": ["#FFFFFF0D", "#FFFFFF00"],
                      "de": [0, -chh(22)], "para": [0, chh(22)]},
              "x": ex(750), "y": ey(22), "escala": es(),
              "opacidade": entra(0.02, 0.28)})
    C.append({"tipo": "retangulo", "larg": CW, "alt": 1, "cor": BORDA,
              "x": ex(750), "y": ey(44), "escala": es(),
              "opacidade": entra(0.06, 0.3)})

    # os tres semaforos: 12 px, gap 8, padding 20 — cada um com o seu halo
    for i, (px, cor_d) in enumerate(((26, "#FF5F56"), (46, "#FFBD2E"),
                                     (66, "#27C93F"))):
        td = 0.30 + i * PALAVRA
        C.append({"tipo": "elipse", "raio": 20, "blur": 6,
                  "cor": {"tipo": "radial", "cores": [cor_d, "#00000000"],
                          "raio": 20},
                  "x": ex(px), "y": ey(22), "escala": es(),
                  "opacidade": [[td, 0, "outCubic"], [td + 0.35, 0.34]]})
        C.append({"tipo": "elipse", "raio": 6, "cor": cor_d,
                  "x": ex(px), "y": ey(22),
                  "opacidade": entra(td, 0.25),
                  "escala": {"mola": MOLA_ESTADO, "em": td, "de": 0.3,
                             "para": 1.0}})

    # a barra de endereco e o titulo "creativly.ai / Pro Video Editor"
    C.append({"tipo": "retangulo", "larg": 1392, "alt": chh(24), "raio": 6,
              "cor": "#0000004D", "contorno": "#FFFFFF0D", "contorno_larg": 1,
              "x": ex(784), "y": ey(22), "escala": es(),
              "opacidade": entra(0.08, 0.3)})
    TB = 16          # o original usa 11 px; 11 px sem hinting vira mancha
    wa = larg_texto("creativly.ai / ", TB)
    wb = larg_texto("Pro Video Editor", TB)
    x_url = 784 - (wa + wb) / 2
    C.append({"tipo": "texto", "texto": "creativly.ai / ", "tamanho": TB,
              "peso": 500, "cor": MUDO, "espacamento": 0.3,
              "x": ex(x_url + wa / 2), "y": ey(22), "escala": es(),
              "opacidade": [[0.34, 0, "outCubic"], [0.62, 0.42]]})
    C.append({"tipo": "texto", "texto": "Pro Video Editor", "tamanho": TB,
              "peso": 500, "cor": TEXTO, "espacamento": 0.3,
              "x": ex(x_url + wa + wb / 2), "y": ey(22), "escala": es(),
              "opacidade": [[0.38, 0, "outCubic"], [0.66, 0.85]]})

    # ── o painel de timeline: 45% da altura, colado embaixo (:277-292) ───
    PAN_T = 15 * F                     # <Sequence from={15}>
    PAN_PY = 697.5                     # centro de 495..900
    # translateZ 0 -> 70 com perspectiva 1500 = escala 1 -> 1.049 (:49-53)
    CRESCE = [[0.667, 1.0, [0.22, 1, 0.36, 1]], [3.333, 1.03]]
    C.append({"tipo": "elipse", "rx": CW * 0.52, "ry": 90, "blur": 34,
              "cor": {"tipo": "radial", "cores": [ACENTO, "#00000000"],
                      "raio": CW * 0.52},
              **viva(cxp(750), cyp(495), 6, 901),
              "opacidade": [[PAN_T, 0, "outCubic"], [PAN_T + 0.5, 0.16]]})
    pan = card(cxp(750), cyp(PAN_PY), CW - 4, chh(405), PAN_T,
               "#141414CC", "#F43F5E44", 16, 902)
    pan["escala"] = [[PAN_T, 0.94], [PAN_T + 0.3, 1.0, [0.22, 1, 0.36, 1]],
                     [3.333, 1.03]]
    C.append(pan)
    C.append({"tipo": "retangulo", "larg": CW - 4, "alt": 2, "cor": ACENTO,
              **viva(cxp(750), cyp(495), 2, 903),                   # borderTop
              "opacidade": [[PAN_T, 0, "outCubic"], [PAN_T + 0.35, 0.9]],
              "escalaX": {"mola": MOLA_ESTADO, "em": PAN_T, "de": 0.3,
                          "para": 1.0}})

    # ── 4 trilhas x 3 clipes, em cascata (:294-359) ──────────────────────
    CORES_TRILHA = [PRIMARIA, ACENTO, SUCESSO, SECUNDARIA]          # :74
    for tr in range(4):
        cor_t = CORES_TRILHA[tr]
        for cl in range(3):
            larg = 80 + math.sin(tr * 3 + cl * 7) * 40              # :308-310
            esq = 120 + cl * 160 + tr * 20                          # :311
            py = 545 + tr * 80                     # top 20+tr*80, clipe top 10
            td = 0.667 + tr * BLOCO + cl * PALAVRA                  # :314-325
            # transformOrigin "left center" com scaleX 0.5 -> 1: o motor escala
            # pelo centro, entao o x tambem anda meia largura.
            xa, xb = cxp(esq + larg * 0.25), cxp(esq + larg * 0.5)
            C.append({
                "tipo": "retangulo", "larg": larg, "alt": chh(40), "raio": 6,
                # preenchimento fiel (:350); contorno subiu de 55 para 99 —
                # o original conta com o backdrop-filter para destacar a borda,
                # e o motor nao tem backdrop-filter.
                "cor": cor_t + "33", "contorno": cor_t + "99",
                "contorno_larg": 1,
                "x": [[td, xa], [td + 0.42, xb, [0.22, 1, 0.36, 1]],
                      [3.333, xb * 1.03]],
                # micro-deriva de +-2 px do original (:333-339)
                "y": {"ruido": {"escala": 0.008, "amp": 1.6,
                                "base": cyp(py), "semente": 430 + tr * 7 + cl}},
                "escalaX": {"mola": MOLA_ESTADO, "em": td, "de": 0.5,
                            "para": 1.0},
                "escala": CRESCE,
                "opacidade": [[td, 0, "outCubic"], [td + 0.35, 0.6]],
            })

    # ── o playhead (:366-408) ────────────────────────────────────────────
    # left 30% do container + translateX 0..600 em 100 frames, inOutQuad
    PLAY_X = [[0, cxp(450), "inOutQuad"], [100 * F, cxp(1050)]]
    PLAY_DRAW = [[5 * F, 0, "outCubic"], [30 * F, 1]]               # :66-70
    # O playhead vive DENTRO da janela. No original o `overflow:hidden` do
    # BrowserWindow (:224) corta o que passa da moldura; o motor nao corta,
    # entao a linha e MEDIDA: comeca abaixo da barra de titulo (44 px) e
    # morre acima da borda de baixo (900 px). Sem isso ela sangra 114 px por
    # cima e 48 por baixo no fundo branco e vira risco solto, e a cabeca cai
    # em cima de "Pro Video Editor".
    PLAY_T, PLAY_B = 62.0, 886.0
    C.append({"tipo": "retangulo", "larg": 10, "alt": chh(PLAY_B - PLAY_T),
              "cor": ACENTO, "blur": 26,
              "x": PLAY_X, "y": cyp((PLAY_T + PLAY_B) / 2),
              "revelar": {"prog": PLAY_DRAW, "dir": "cima"},
              "opacidade": pulso(0.20, 0.07, 0.03, 921)})
    # `traco` corre no CONTORNO: a linha nao tem `cor`, so `contorno`.
    C.append({"tipo": "linha",
              "de": [0, -cyp(PLAY_T)], "para": [0, -cyp(PLAY_B)],
              "contorno": ACENTO, "contorno_larg": 3,
              "x": PLAY_X, "y": 0, "traco": PLAY_DRAW})
    gh = brilho(0, cyp(PLAY_T), 46, ACENTO, 10 * F, 0.55, 931)
    gh["x"] = PLAY_X
    gh["raio"] = pulso(46, 14, 0.03, 933)                           # :63, :404
    C.append(gh)
    C.append({"tipo": "retangulo", "larg": 19, "alt": 19, "raio": 2,
              "cor": ACENTO, "rotacao": 45, "x": PLAY_X, "y": cyp(PLAY_T),
              "opacidade": PLAY_DRAW,
              # o UNICO destaque da cena
              "escala": {"mola": MOLA_DESTAQUE, "em": 10 * F, "de": 0.2,
                         "para": 1.0}})

    # ── o cartao branco flutuante (:412-515) ─────────────────────────────
    LAB_T = 8 * F
    TAM_TIT = 70
    w_tit = larg_texto("Video Editing", TAM_TIT)
    CARD_W = w_tit + 112                                # padding 56 dos lados
    CARD_L = cxp(-100)                                  # left: -100 (:433)
    CARD_X = CARD_L + CARD_W / 2
    CARD_H = chh(200)                                   # 36+29+4+74+10+18+28
    CARD_TOPO = cyp(720) + CARD_H                       # bottom: 180 (:434)
    CARD_Y = CARD_TOPO - CARD_H / 2
    TXT_L = CARD_L + 56

    C += sombra(CARD_X, CARD_Y, CARD_W, CARD_H, 0.30, 28, 3)        # :440
    cd = card(CARD_X, CARD_Y, CARD_W, CARD_H, LAB_T, BG_BRANCO,
              "#0000001A", 28, 941)
    cd["escala"] = {"mola": {"damping": 16, "stiffness": 80, "mass": 1.0},
                    "em": LAB_T, "de": 0.85, "para": 1.0}           # :413-423
    cd["escalaX"] = [[LAB_T, 0.94, "outCubic"], [0.9, 0.985]]       # rotateY
    C.append(cd)

    # "PROFESSIONAL" — 24 px, italico, letterSpacing .15em, em degrade
    w_pro = larg_texto("PROFESSIONAL", 24) + 3.6 * 11
    y_pro = CARD_TOPO - chh(50)
    for cor_p, rev in ((MARCA, None), (CIANO, {"prog": 0.55, "dir": "dir"})):
        r = rotulo("PROFESSIONAL", 0.30, y_pro, cor_p, 24,
                   TXT_L + w_pro / 2, 4, 600)
        r["italico"] = True
        r["opacidade"] = [[0.30, 0, "outCubic"], [0.62, 0.9]]       # :460
        if rev:
            r["revelar"] = rev
        C.append(r)

    # "Video Editing" — 70 px, italico 900, preto, letra a letra
    C += titulo("Video Editing", 0.30, CARD_TOPO - chh(106), TAM_TIT,
                TEXTO_PRETO, 900, LETRA, TXT_L + w_tit / 2, True)

    # "timeline precision" — 16 px (o original usa 15), sobe 20 px (:492-512)
    y_sec = CARD_TOPO - chh(162)
    w_sec = larg_texto("timeline precision", 16) + 3.2 * 17
    sec = rotulo("timeline precision", 0.6, y_sec, CIANO, 16,
                 TXT_L + w_sec / 2, 3, 400)
    sec["italico"] = True
    sec["y"] = [[0.6, y_sec - 20, "outCubic"], [1.0, y_sec]]        # :508
    sec["opacidade"] = [[0.6, 0, "outCubic"], [0.95, 0.7]]          # :507
    C.append(sec)

    return {"duracao": dur, "fundo": BG_BRANCO, "camadas": C}
