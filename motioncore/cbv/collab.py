# -*- coding: utf-8 -*-
"""collab.py — a cena Collaboration do CreativlyBrandVideo.

Fundo claro (`COLORS.bgWhite`, :182) com a marca d'agua "COLLAB" em degrade
(:184-209), sete losangos 3D flutuando (:66-74), o bloco tipografico
REAL-TIME / Collaboration / TOGETHER (:229-315) e quatro cursores de pessoas
que voam de fora do quadro para os quatro cantos (:22-55, :405-494), puxando
linhas curvas entre si (:317-365) e batendo ondas circulares no destino
(:367-403). Os cantos sao a unica mudanca de posicao contra o .tsx, e o
motivo esta no comentario de `CURSORES`.

Decisoes de animacao, com a linha do .tsx de onde saiu o numero:
  - o "3D" dos losangos e `rotateX(f*1.5*s) rotateY(f*2*s)` (Rotating3D:236-237):
    aqui isso vira escalaX = |cos(rotY)| e escalaY = |cos(rotX)| amostrados de
    3 em 3 frames num `grupo` — precisa ser grupo porque no CSS o `rotate(45deg)`
    e o mais INTERNO e o esmagamento acontece nos eixos da TELA, entao a escala
    tem que ficar por FORA da rotacao (o motor escala por dentro).
  - o `blur(20 -> 0)` do titulo (:167) nao existe: `blur` nao e animavel. Virou
    um fantasma de sombra borrada que floresce e some por baixo das letras.
  - o gradiente de texto (:195-197, CharacterReveal:5-12) nao existe no motor:
    cada letra recebe uma cor interpolada do #3B82F6 ao #06B6D4, que le como
    degrade porque as letras sao camadas separadas.
  - o cursor viaja com a mola do original (damping 18 / stiffness 50, :408-412)
    e cada peca dele (seta, pilula, nome, funcao) carrega a MESMA mola com o
    proprio deslocamento somado no `de`/`para` — assim andam juntas sem grupo.
"""
import math

from .base import *

# ── paleta local, direto do .tsx ─────────────────────────────────────────
AMARELO = "#FFD600"          # rgba(255,214,0,*) dos losangos, :67-73
# A mola de viagem do cursor: :408-412. Nenhuma das tres da base serve, e a
# razao e medida, nao teorica: MOLA_ESTADO chega a 95% em 10 frames e a do
# original leva 20. O planeio lento por 800 px E o plano — com a mola de estado
# os quatro cursores estalam no lugar antes de a segunda linha de texto entrar.
MOLA_CURSOR = {"damping": 18, "stiffness": 50, "mass": 1}

# ── os quatro colaboradores, :22-55 ──────────────────────────────────────
# (cor, nome, funcao, inicio_tela, fim_tela, atraso_em_frames)
# Os destinos NAO sao os do .tsx (:24-52). La os quatro pousam no meio do
# quadro — (760,420), (1120,490), (880,310), (1220,620) — e a pilula opaca de
# cada um cai EM CIMA de "Collaboration": a laranja tapa o "lla", a verde o
# "rati", a magenta o "HER" de TOGETHER. No .tsx isso passa porque o titulo
# entra depois e o olho perdoa em movimento; num quadro parado e um borrao.
# Aqui os quatro pousam nos cantos, fora da caixa do texto (que ocupa
# x 330..1620, y 355..715), e a ORDEM da lista vira o retangulo das linhas de
# conexao: cima (Sarah->Mike), direita (Mike->Alex), baixo (Alex->Nina),
# esquerda (Nina->Sarah) — a moldura passa a emoldurar em vez de riscar.
# A pilula cresce para a DIREITA e para BAIXO do ponto (+143 px no pior caso,
# Sarah/Designer, e +46 px), entao 1620 e 830 sao os limites que cabem.
CURSORES = [
    ("#FF5733", "Sarah", "Designer",  (-220, 760),  (300, 230),   10),
    ("#33FF57", "Mike",  "Developer", (2140, 780),  (1600, 230),  15),
    ("#3357FF", "Alex",  "PM",        (1180, 1260), (1620, 830),  20),
    ("#FF00FF", "Nina",  "Writer",    (760, 1280),  (320, 830),   25),
]

# ── os sete losangos, :66-74 ─────────────────────────────────────────────
# (x_tela, y_tela, tamanho, velocidade, atraso_frames, cor, alfa, brilha)
LOSANGOS = [
    (120,  140, 50, 0.8,  3, AMARELO,     0.18, True),
    (1750, 180, 70, 1.1,  6, AMARELO,     0.14, True),
    (1650, 820, 40, 1.4,  9, TEXTO_PRETO, 0.08, False),
    (200,  750, 55, 0.6, 12, AMARELO,     0.12, True),
    (960,  120, 35, 1.0,  5, TEXTO_PRETO, 0.06, False),
    (1400, 450, 45, 0.9,  8, AMARELO,     0.10, True),
    (350,  400, 30, 1.3, 14, TEXTO_PRETO, 0.05, False),
]

# ── o bloco tipografico, :229-315 ────────────────────────────────────────
# Alturas de caixa do CSS: 32*1.21 + 8 + 180*0.9 + 10 + 100*1.21 = 339,7 px,
# centrado no quadro. Dai sai o y de cada linha.
Y_SUB, Y_TIT, Y_TOG = 150.0, 42.0, -109.0
ESP_SUB = 0.35 * 32          # letterSpacing 0.35em, :253
ESP_TIT = -0.03 * 180        # letterSpacing -0.03em, :279
ESP_TOG = 0.02 * 100         # letterSpacing 0.02em, :301
DERIVA = 31                  # semente unica: as tres linhas derivam JUNTAS (:178)


# ── utilidades locais ────────────────────────────────────────────────────
def _px(x: float, y: float) -> tuple[float, float]:
    """Coordenada de tela do original -> coordenada de camada (origem no meio)."""
    return x - W / 2.0, H / 2.0 - y


def _mistura(a: str, b: str, t: float) -> str:
    """Um ponto do degrade linear-gradient(135deg, #3B82F6, #06B6D4)."""
    t = max(0.0, min(1.0, t))
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(round(ca[i] + (cb[i] - ca[i]) * t)):02X}"
                         for i in range(3))


def _espacar(letras: list[dict], esp: float) -> list[dict]:
    """letter-spacing depois do fato: `titulo()` nao tem o campo, e nas tres
    linhas ele muda tudo (0.35em na primeira e quase o dobro da largura)."""
    n = len(letras)
    for i, lay in enumerate(letras):
        lay["x"] += (i - (n - 1) / 2.0) * esp
    return letras


# Correcao de avanco por caractere, em fracao de em. `larg_char()` da base tem
# tres classes de largura: resolve COLISAO, que e o problema que ela veio
# resolver, mas nao kerning. A 180 px o 'r' do Inter Black (0,435em de verdade
# contra os 0,56em da tabela) abria um buraco de 22 px no meio de
# "Collaboration". Aqui ficam so os desvios dos caracteres que ESTA cena poe em
# corpo grande — nada disso vale a pena abaixo de ~40 px.
_KERN = {"C": 0.042, "o": 0.056, "l": -0.007, "a": 0.034, "b": 0.070,
         "r": -0.125, "t": 0.098, "i": -0.007, "n": 0.070,
         "T": -0.075, "O": 0.079, "G": 0.079, "E": -0.084, "H": 0.043,
         "R": -0.023, "A": 0.020, "L": -0.103, "M": -0.035, "I": 0.020,
         "-": -0.210}


def _avanco(ch: str, tam: float) -> float:
    return larg_char(ch, tam) + _KERN.get(ch, 0.0) * tam


def _kern(letras: list[dict], txt: str, tam: float) -> list[dict]:
    """Aplica `_KERN` ao que `titulo()` ja posicionou, sem tirar do centro."""
    corr = [_KERN.get(c, 0.0) * tam for c in txt]
    acc = -sum(corr) / 2.0
    for lay, dc in zip(letras, corr):
        lay["x"] += acc + dc / 2.0
        acc += dc
    return letras


def _giro(vel_graus: float, dur: float, passo: int = 3) -> list:
    """|cos| do angulo de rotacao 3D, amostrado em frames.

    Rotating3D:236-237 gira em graus POR FRAME; o achatamento que a tela ve e
    o cosseno disso. Amostrar de 3 em 3 frames com `linear` entre as amostras
    da menos de 9 graus por trecho — erro invisivel, e vira um valor que o
    motor sabe animar.
    """
    ks, f = [], 0.0
    limite = dur * FPS + passo
    while f <= limite:
        v = abs(math.cos(math.radians(f * vel_graus)))
        ks.append([round(f * F, 4), round(max(0.06, v), 4), "linear"])
        f += passo
    ks[-1] = ks[-1][:2]          # armadilha 6: easing no ultimo e ignorado
    return ks


def _clique(tc: float, base: float = 1.0) -> list:
    """:414-419 — a mola de clique mapeada em 1 -> 0,75 -> 1."""
    return [[tc, base, "outCubic"], [tc + 0.09, base * 0.75, "outCubic"],
            [tc + 0.21, base * 1.06, "outCubic"], [tc + 0.34, base]]


def cena(dur: float) -> dict:
    camadas: list[dict] = []

    # ══ marca d'agua "COLLAB" (:184-209) ═════════════════════════════════
    # 400px, 900, italica, -10deg, letterSpacing 0.05em, opacidade 0.04, com
    # deriva de ruido. O degrade de texto nao existe no motor: cada letra e uma
    # camada, entao a cor interpola letra a letra e o olho le degrade.
    palavra, tam_wm, esp_wm = "COLLAB", 400, 0.05 * 400
    largs = [_avanco(c, tam_wm) for c in palavra]
    total = sum(largs) + esp_wm * (len(palavra) - 1)
    cur = -total / 2.0
    cos10, sin10 = math.cos(math.radians(10)), math.sin(math.radians(10))
    for i, ch in enumerate(palavra):
        d = cur + largs[i] / 2.0
        wx, wy = d * cos10, d * sin10        # baseline girada -10deg
        camadas.append({
            "tipo": "texto", "texto": ch, "tamanho": tam_wm, "peso": 900,
            "italico": True, "rotacao": -10,
            "cor": _mistura(MARCA, CIANO, i / (len(palavra) - 1)),
            **viva(wx, wy, 20, 7),           # :150-151 — mesma semente = mesma deriva
            "opacidade": [[0, 0, "outCubic"], [1.0, 0.05]],
        })
        cur += largs[i] + esp_wm

    # ══ os brilhos dos losangos (boxShadow do Rotating3D:264) ════════════
    for i, (px, py, tamL, _v, atr, _c, _a, brilha) in enumerate(LOSANGOS):
        if not brilha:
            continue
        gx, gy = _px(px + tamL / 2.0, py + tamL / 2.0)
        camadas.append(brilho(gx, gy, tamL * 2.2, MARCA, atr * F, 0.22, 60 + i))

    # ══ os sete losangos 3D (:66-74 + Rotating3D:212-270) ════════════════
    for i, (px, py, tamL, vel, atr, cor, alfa, _b) in enumerate(LOSANGOS):
        lx, ly = _px(px + tamL / 2.0, py + tamL / 2.0)
        t0 = atr * F
        camadas.append({
            "tipo": "grupo",
            **viva(lx, ly, 15, 70 + i),      # floatX 10 / floatY 15, escala 0.015
            "escala": {"mola": MOLA_TEXTO, "em": t0, "de": 0.0, "para": 1.0},
            "escalaX": _giro(2.0 * vel, dur),    # rotateY achata a largura
            "escalaY": _giro(1.5 * vel, dur),    # rotateX achata a altura
            # opacidade mora no FILHO: opacidade de grupo nao cascateia no
            # motor (`_pintar_um` so a usa pra decidir se desenha o grupo).
            # O alfa e o do rgba() do original vezes o 0.8 de Rotating3D:262.
            "camadas": [{
                "tipo": "retangulo", "larg": tamL, "alt": tamL, "rotacao": 45,
                "cor": cor,
                "opacidade": [[t0, 0, "outCubic"], [t0 + 0.4, round(alfa * 0.8, 4)]],
            }],
        })

    # ══ o bloco tipografico (:229-315) ═══════════════════════════════════
    # fantasma borrado: substitui o `filter: blur(20 -> 0)` de :167, que o motor
    # nao anima. Sombra pura (preenchimento transparente) = so o borrao.
    camadas.append({
        "tipo": "texto", "texto": "Collaboration", "tamanho": 180, "peso": 900,
        "cor": "#00000000", "espacamento": ESP_TIT, "x": 0, "y": Y_TIT,
        "sombra": [{"x": 0, "y": 0, "blur": 44, "cor": TEXTO_PRETO}],
        "escala": {"mola": MOLA_DESTAQUE, "em": 6 * F, "de": 0.6, "para": 1.0},
        "opacidade": [[0.45, 0, "outCubic"], [0.74, 0.34, "outCubic"], [1.15, 0]],
    })

    # "REAL-TIME" — 32px, 400, italica, maiuscula, #6b7280 (:245-266)
    sub = _kern(_espacar(titulo("REAL-TIME", 0.0, 0.0, 32, MUDO_ESCURO, 400,
                                2 * F, italico=True), ESP_SUB),
                "REAL-TIME", 32)
    for i, lay in enumerate(sub):
        lay["y"] = sobe(i * 2 * F, 0.0, 25)          # offsetY=25, :264
    camadas.append({
        "tipo": "grupo", **viva(0, Y_SUB, 4, DERIVA),
        "camadas": [{
            "tipo": "grupo",
            "y": {"mola": MOLA_TEXTO, "em": 0.0, "de": -50.0, "para": 0.0},
            "camadas": sub,
        }],
    })

    # "Collaboration" — 180px, 900, preto (:268-289). A escala 0.6 -> 1 do bloco
    # e o UNICO destaque da cena, entao e ela que leva MOLA_DESTAQUE.
    tit = _kern(_espacar(titulo("Collaboration", 8 * F, 0.0, 180, TEXTO_PRETO,
                                900, LETRA), ESP_TIT), "Collaboration", 180)
    for i, lay in enumerate(tit):
        lay["y"] = sobe(8 * F + i * LETRA, 0.0, 60)  # offsetY=60, :287
    camadas.append({
        "tipo": "grupo", **viva(0, Y_TIT, 4, DERIVA),
        "escala": {"mola": MOLA_DESTAQUE, "em": 6 * F, "de": 0.6, "para": 1.0},
        "camadas": tit,
    })

    # "TOGETHER" — 100px, 900, italica, em degrade, girando 8deg -> -3deg
    # (:291-312). O degrade vira uma cor por letra.
    tog = _kern(_espacar(titulo("TOGETHER", 20 * F, 0.0, 100, MARCA, 900,
                                2 * F, italico=True), ESP_TOG),
                "TOGETHER", 100)
    for i, lay in enumerate(tog):
        lay["y"] = sobe(20 * F + i * 2 * F, 0.0, 40)  # offsetY=40, :309
        lay["cor"] = _mistura(MARCA, CIANO, i / (len(tog) - 1))
    camadas.append({
        "tipo": "grupo", **viva(0, Y_TOG, 4, DERIVA),
        "camadas": [{
            "tipo": "grupo",
            "y": {"mola": MOLA_TEXTO, "em": 18 * F, "de": -60.0, "para": 0.0},
            "rotacao": {"mola": MOLA_TEXTO, "em": 18 * F, "de": 8.0, "para": -3.0},
            "camadas": tog,
        }],
    })

    # ══ as linhas de conexao (:57-63, :317-365) ══════════════════════════
    # `path` com centrar=False: as coordenadas sao as da tela deslocadas para o
    # centro do quadro — e dentro de `d` o y DESCE (armadilha 5).
    # O `- 100` do controle (:60-61) so curva quando o segmento e horizontal:
    # no .tsx todos os pares eram diagonais no meio do quadro, entao dava certo
    # por acidente. Com os quatro nos cantos, dois dos pares ficam VERTICAIS e o
    # controle no meio deles nao curva nada — viram dois fios de cabelo retos ao
    # lado do titulo. Aqui o desvio e perpendicular ao segmento e apontado para
    # FORA do centro do quadro: os quatro arcos fecham uma moldura arredondada
    # em volta do texto, com a mesma barriga de 90 px em qualquer direcao.
    for i, (cor, _n, _f, _s, fim, atraso) in enumerate(CURSORES):
        prox = CURSORES[(i + 1) % len(CURSORES)]
        fx, fy = fim
        px, py = prox[4]
        mx, my = (fx + px) / 2.0, (fy + py) / 2.0
        vx, vy = px - fx, py - fy
        comp = math.hypot(vx, vy) or 1.0
        nx, ny = -vy / comp, vx / comp                      # normal do segmento
        if (mx - W / 2.0) * nx + (my - H / 2.0) * ny < 0:   # aponta para fora
            nx, ny = -nx, -ny
        mx, my = mx + nx * 90, my + ny * 90
        t0 = (15 + max(atraso, prox[5]) + 10) * F           # :329-333
        camadas.append({
            "tipo": "path", "centrar": False,
            "d": (f"M {fx - W/2} {fy - H/2} Q {mx - W/2} {my - H/2} "
                  f"{px - W/2} {py - H/2}"),
            "contorno": cor, "contorno_larg": 2,
            "traco": [[t0, 0, "outCubic"], [t0 + 25 * F, 1]],   # evolvePath, :344
            "opacidade": pulso(0.25, 0.1, 0.02, 210 + i),       # :347-348
        })

    # ══ as ondas circulares no destino (:367-403) ════════════════════════
    # Anel = preenchimento transparente + contorno (armadilha 2).
    for i, (cor, _n, _f, _s, fim, atraso) in enumerate(CURSORES):
        ax, ay = _px(*fim)
        for anel in range(3):
            t0 = (20 + atraso + 15 + anel * 7) * F           # :370-373
            camadas.append({
                "tipo": "elipse", "raio": [[t0, 0, "linear"], [t0 + 1.0, 60]],
                "cor": "#00000000", "contorno": cor, "contorno_larg": 2,
                "x": ax, "y": ay,
                "opacidade": [[t0, 0, "linear"],
                              [t0 + 8 * F, 0.5, "linear"], [t0 + 1.0, 0]],
            })

    # ══ os quatro cursores (:405-494) ════════════════════════════════════
    # A seta do original e um SVG 24x24 desenhado a 36x36 -> escala 1,5.
    SETA = ("M5.65376 12.3673H5.46026L5.31717 12.4976L0.500002 16.8829"
            "L0.500002 1.1943L11.4841 12.3673H5.65376Z")
    CENTRO_SETA = (8.988, 13.558)      # centro dos limites do path, ja em 1,5x

    for i, (cor, nome, funcao, ini, fim, atraso) in enumerate(CURSORES):
        t_ini = (5 + atraso) * F        # Sequence from=5 + delay, :406, :409
        t_rot = (10 + atraso) * F       # labelSpr, :438-442
        t_clk = (27 + atraso) * F       # click, :414-418

        def mola(dx: float, dy: float) -> dict:
            """A MESMA mola de viagem com o deslocamento da peca somado — e o
            que mantem seta, pilula e textos colados sem precisar de grupo."""
            ax0, ay0 = _px(ini[0] + dx, ini[1] + dy)
            ax1, ay1 = _px(fim[0] + dx, fim[1] + dy)
            return {
                "x": {"mola": MOLA_CURSOR, "em": t_ini, "de": ax0, "para": ax1},
                "y": {"mola": MOLA_CURSOR, "em": t_ini, "de": ay0, "para": ay1},
            }

        aparece = [[t_ini, 0, "outCubic"], [t_ini + 0.1, 1]]   # :448-453

        # rastro: bolinha borrada no ponto de ancoragem, :458-472
        camadas.append({
            "tipo": "elipse", "raio": 7, "cor": cor, "blur": 12,
            **mola(0, 0),
            "opacidade": [[t_ini, 0, "outCubic"], [t_ini + 0.12, 0.35, "outCubic"],
                          [t_ini + 0.85, 0.35, "outCubic"], [t_ini + 1.15, 0]],
        })
        # halo: o `drop-shadow(0 0 16px color77)` da seta, :97
        camadas.append({
            "tipo": "elipse", "raio": 34, **mola(*CENTRO_SETA),
            "cor": {"tipo": "radial", "cores": [cor, "#00000000"], "raio": 34},
            "opacidade": [[t_ini, 0, "outCubic"], [t_ini + 0.25, 0.42]],
        })
        # a seta, :100-105
        camadas.append({
            "tipo": "path", "d": SETA, "cor": cor,
            "contorno": TEXTO, "contorno_larg": 1.2,
            **mola(*CENTRO_SETA),
            "escala": _clique(t_clk, 1.5),
            "rotacao": pulso(0.0, 4.0, 0.035, 320 + i),   # :423-428, o tremor do trajeto
            "opacidade": aparece,
        })

        # a pilula do nome: left 18 / top 18, padding 5/14/5/12, raio 20 (:107-127)
        larg_nome = larg_texto(nome, 15)
        larg_func = larg_texto(funcao, 11)
        larg_pil = 12 + larg_nome + 6 + 2 + larg_func + 14
        alt_pil = 28.0
        camadas.append({
            "tipo": "retangulo", "larg": larg_pil, "alt": alt_pil, "raio": 20,
            "cor": cor, **mola(18 + larg_pil / 2.0, 18 + alt_pil / 2.0),
            "opacidade": entra(t_rot, 0.3),
            "escala": {"mola": MOLA_ESTADO, "em": t_rot, "de": 0.85, "para": 1.0},
        })
        camadas.append({
            "tipo": "texto", "texto": nome, "tamanho": 15, "peso": 800,
            "cor": TEXTO, "espacamento": 0.02 * 15,
            **mola(18 + 12 + larg_nome / 2.0, 18 + alt_pil / 2.0),
            "opacidade": entra(t_rot, 0.3),
        })
        camadas.append({
            "tipo": "texto", "texto": funcao, "tamanho": 11, "peso": 400,
            "cor": TEXTO, "italico": True,
            **mola(18 + 12 + larg_nome + 8 + larg_func / 2.0,
                   18 + alt_pil / 2.0),
            "opacidade": [[t_rot, 0, "outCubic"], [t_rot + 0.3, 0.8]],
        })

    # ══ os pontos decorativos da borda (:496-532) ════════════════════════
    for i in range(12):
        ang = (i / 12.0) * math.pi * 2
        raio_orb = 420 + (i % 3) * 60
        dx, dy = math.cos(ang) * raio_orb, -math.sin(ang) * raio_orb
        t0 = i * 3 * F
        par = (i % 2 == 0)
        camadas.append({
            "tipo": "elipse", "raio": (4 + (i % 3) * 2) / 2.0,
            "cor": _mistura(MARCA, CIANO, i / 11.0) if par else TEXTO_PRETO,
            **viva(dx, dy, 6, 400 + i),
            "opacidade": [[t0, 0, "outCubic"], [t0 + 0.35, 0.25 if par else 0.08]],
            "escala": {"mola": MOLA_TEXTO, "em": t0, "de": 0.4, "para": 1.0},
        })

    return {"duracao": dur, "fundo": BG_BRANCO, "camadas": camadas}
