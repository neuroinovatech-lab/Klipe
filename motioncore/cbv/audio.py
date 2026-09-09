# -*- coding: utf-8 -*-
"""audio.py — a cena Audio Generation do CreativlyBrandVideo.

Fundo CLARO (`COLORS.bgWhite`, :81): titulo em tres andares — "Generative"
italico 60, "AUDIO" 200 peso 900, "& Music" 80 em degrade azul->ciano (:216-272)
— sobre um equalizador de 40 barras cuja altura e `sin(frame*0.2 + i*0.5)` mais
ruido organico, com entrada em mola escalonada de 0,8 frame por barra (:317-340).
As alturas nao cabem num `ruido` do DSL: a onda ANDA pelas barras (a fase
depende de `i`), entao cada barra sai amostrada em keyframes com a mola do
original avaliada em Python. Reflexo, brilho pulsante (:61-75), marca d'agua
"SOUND" girando de -18 a -15 graus (:54-58), seis diamantes flutuantes
(:137-201) e quatro selos de tecnologia (:429-467) completam a densidade.
"""
import math

from .base import *

# ── numeros do original ───────────────────────────────────────────────────
PRETO = TEXTO_PRETO                 # COLORS.textBlack — :221, :237, :452
AMARELO = "#FFD600"                 # rgba(255,214,0,*) dos diamantes — :141
N_BARRAS = 40                       # BARS — :23
BAR_LARG, BAR_ESP = 20, 12          # :348-349, :313
BAR_BASE = -229.0                   # fundo da coluna: top 50% + (-15%) — :303
BAR_X0 = -(N_BARRAS * BAR_LARG + (N_BARRAS - 1) * BAR_ESP) / 2 + BAR_LARG / 2
SELOS = ["SUNO", "UDIO", "ELEVENLABS", "WHISPER"]   # :429, uppercase de :451


# ── a mola do original, avaliada aqui ─────────────────────────────────────
def _mola_ref(t: float, damping: float, stiffness: float,
              mass: float = 1.0) -> float:
    """O `spring()` de referencia como VALOR, nao como campo animado.

    A altura da barra e `(onda + ruido) * 240 * mola` — a mola entra num
    produto, e produto de dois animaveis o DSL nao expressa. Solucao analitica
    da mesma EDO; para damping 18 / stiffness 80 (:321) o amortecimento e
    critico e a barra sobe sem quicar, igual ao original.
    """
    if t <= 0:
        return 0.0
    z = damping / (2.0 * math.sqrt(stiffness * mass))
    w0 = math.sqrt(stiffness / mass)
    if z < 1.0:
        w1 = w0 * math.sqrt(1.0 - z * z)
        return 1.0 - math.exp(-z * w0 * t) * (
            math.cos(w1 * t) + z * w0 / w1 * math.sin(w1 * t))
    return 1.0 - math.exp(-w0 * t) * (1.0 + w0 * t)


def _onda(i: int, fr: float) -> float:
    """:323-326 — `sin(frame*0.2 + i*0.5)` com `noise2D` por cima.

    O `noise2D` vira duas senoides incomensuraveis: mesma faixa (+-0.25),
    mesma sensacao de variacao organica, e deterministico como o motor exige.
    """
    onda = math.sin(fr * 0.2 + i * 0.5) * 0.5 + 0.5
    u = fr * 0.03
    n = 0.55 * math.sin(1.9 * u + i * 2.17) + 0.45 * math.sin(3.1 * u + i * 4.61 + 1.3)
    return onda + n * 0.25


def _amostrar(n_fr: int, fn, passo: int = 2) -> list:
    """Amostra uma funcao de frame em keyframes lineares.

    Easing em TODOS menos o ultimo: no ultimo ele governaria um trecho que nao
    existe (armadilha 6), e `linear` entre amostras vizinhas e o que reconstroi
    a curva sem inventar uma segunda curva por cima dela.
    """
    ks = []
    fr = 0
    while fr < n_fr:
        ks.append([fr * F, fn(fr), "linear"])
        fr += passo
    ks.append([n_fr * F, fn(n_fr)])
    return ks


def _mix(a: str, b: str, k: float) -> str:
    k = max(0.0, min(1.0, k))
    pa = [int(a[1 + 2 * i:3 + 2 * i], 16) for i in range(3)]
    pb = [int(b[1 + 2 * i:3 + 2 * i], 16) for i in range(3)]
    return "#" + "".join("%02X" % round(x + (y - x) * k) for x, y in zip(pa, pb))


def _cor_barra(i: int) -> str:
    """:331-340 — preto nas pontas, MARCA do 30% ao 70% do equalizador."""
    a, b = N_BARRAS * 0.3, N_BARRAS * 0.7
    if i <= a:
        return _mix(PRETO, MARCA, i / a)
    if i >= b:
        return _mix(MARCA, PRETO, (i - b) / ((N_BARRAS - 1) - b))
    return MARCA


def _caminho_onda(barras: int = 60) -> str:
    """:26-35 — a senoide de fundo, ponto a ponto, na convencao SVG (y DESCE)."""
    d = "M 0 150"
    for i in range(barras + 1):
        x = (i / barras) * 1200.0
        y = 150.0 - math.sin(i * 0.3) * 60.0
        d += " L %.2f %.2f" % (x, y)
    return d


def cena(dur: float) -> dict:
    n_fr = int(round(dur * FPS))
    cam: list = []

    # ── marca d'agua "SOUND" (:87-111) ────────────────────────────────────
    # 350px, italica, letter-spacing 30, opacidade 0.04, girando de -18 a -15
    # em 60 frames. O degrade do CSS (azul->ciano a 135 graus) nao existe em
    # `cor`, entao ele vira uma letra por camada com a cor interpolada. O giro
    # e do BLOCO: cada letra girando no proprio centro cisalharia a palavra —
    # por isso as cinco vao dentro de um grupo, e quem gira e o grupo.
    letras = []
    x = -(larg_texto("SOUND", 350) + 30 * 4) / 2
    for i, ch in enumerate("SOUND"):
        w = larg_char(ch, 350)
        l = marca_dagua(ch, 350, _mix(MARCA, CIANO, i / 4), 0.0, 0.04)
        l["x"] = x + w / 2
        l["espacamento"] = 0
        letras.append(l)
        x += w + 30
    cam.append({"tipo": "grupo",
                "rotacao": [[0, -18, "outCubic"], [2.0, -15]],
                "camadas": letras})

    # ── a senoide de fundo, desenhada pela pena (:114-135) ────────────────
    # `traco` de 0 a 1 entre os frames 5 e 40 (:42-46). Sem `cor`: forma
    # preenchida nao tem contorno pra correr (armadilha 2).
    cam.append({
        "tipo": "path", "d": _caminho_onda(60),
        "contorno": MARCA, "contorno_larg": 3,
        "opacidade": 0.06,
        "traco": [[5 * F, 0, "outCubic"], [40 * F, 1]],
    })

    # ── seis diamantes flutuantes (:137-201) ──────────────────────────────
    # O FloatingDiamond e um plano quadrado a 45 graus tombando em X e Y
    # (:229-230). Aqui o tombo vira escalaX/escalaY = |cos| do angulo, e a
    # entrada (mola 16/80) multiplica a mesma amostra. `blur` nao anima
    # (armadilha 4), entao o halo do box-shadow vira um `brilho` proprio atras.
    diamantes = [
        # tam, alpha, esq, topo, veloc, atraso(frames)
        (50, "2E", 120, 100, 0.7, 5), (35, "24", 1700, 150, 1.2, 12),
        (70, "1A", 200, 800, 0.5, 8), (28, "33", 1600, 750, 1.5, 18),
        (45, "1F", 950, 60, 0.9, 15), (55, "14", 80, 480, 0.6, 20),
    ]
    for k, (tam, al, esq, topo, vel, atraso) in enumerate(diamantes):
        cx = esq + tam / 2 - W / 2
        cy = H / 2 - (topo + tam / 2)
        t0 = atraso * F

        def _ent(fr, atraso=atraso):
            return _mola_ref(max(0.0, fr - atraso) * F, 16, 80)

        def _sx(fr, vel=vel, _e=_ent):
            return max(0.08, abs(math.cos(math.radians(fr * 2.0 * vel)))) * _e(fr)

        def _sy(fr, vel=vel, _e=_ent):
            return max(0.08, abs(math.cos(math.radians(fr * 1.5 * vel)))) * _e(fr)

        cam.append(brilho(cx, cy, tam * 1.4, MARCA, t0, 0.20, 40 + k))
        cam.append({
            "tipo": "retangulo", "larg": tam, "alt": tam, "raio": 2,
            "cor": AMARELO + al, "rotacao": 45,
            **viva(cx, cy, 10, 60 + k),
            "escalaX": _amostrar(n_fr, _sx, 2),
            "escalaY": _amostrar(n_fr, _sy, 2),
            "opacidade": {"mola": {"damping": 16, "stiffness": 80},
                          "em": t0, "de": 0, "para": 0.8},
        })

    # ── brilho pulsante atras das barras (:277-294) ───────────────────────
    # caixa de 1100x400 => circulo de raio 550 achatado por escalaY. O pulso do
    # CSS mora na COR (alpha 0.15->0.35), e cor nao anima: ele desce pra
    # opacidade da camada, multiplicado pela mola de entrada (20/60).
    def _op_glow(fr):
        ent = _mola_ref(max(0.0, fr - 10) * F, 20, 60)
        return ent * (0.15 + (math.sin(fr * 0.08) + 1) / 2 * 0.20)

    def _esc_glow(fr):
        return 0.9 + (math.sin(fr * 0.05) + 1) / 2 * 0.20

    g = brilho(0, 40, 550, MARCA, 10 * F, 0.35, 7)
    g["escalaY"] = 400.0 / 1100.0
    g["escala"] = _amostrar(n_fr, _esc_glow, 3)
    g["opacidade"] = _amostrar(n_fr, _op_glow, 3)
    cam.append(g)
    g2 = brilho(0, 40, 780, CIANO, 10 * F, 0.10, 9)      # a parada ciano a 40%
    g2["escalaY"] = 0.40
    cam.append(g2)

    # ── hierarquia tipografica (:204-274) ─────────────────────────────────
    # O SplitText do original quebra por PALAVRA; aqui a cascata e por LETRA,
    # que e o vocabulario da casa. Os atrasos de palavra (0, 4, 8 frames)
    # viram o t0 de cada andar.
    cam += titulo("Generative", 0.0, 444, 60, PRETO, 700, italico=True)

    audio = titulo("AUDIO", 4 * F, 328, 200, PRETO, 900)
    for l in audio:                        # o UNICO destaque da cena: o original
        l["escala"]["mola"] = MOLA_DESTAQUE  # ja da a AUDIO uma mola propria,
    cam += audio                             # mais solta que a dos vizinhos (:251)

    musica = titulo("& Music", 8 * F, 183, 80, MARCA, 700, italico=True)
    for k, l in enumerate(musica):         # o degrade 135deg do GRADIENT_STYLE
        l["cor"] = _mix(MARCA, CIANO, k / max(1, len(musica) - 1))
    cam += musica

    # ── as 40 barras (:317-360) ───────────────────────────────────────────
    for i in range(N_BARRAS):
        bx = BAR_X0 + i * (BAR_LARG + BAR_ESP)
        cor = _cor_barra(i)

        def _h(fr, i=i):
            spr = _mola_ref(max(0.0, fr - 10 - i * 0.8) * F, 18, 80)
            return max(10.0, _onda(i, fr) * 240.0 * spr)

        alt = _amostrar(n_fr, _h, 2)
        cam.append({
            "tipo": "retangulo", "larg": BAR_LARG, "raio": 10,
            "alt": alt,
            # a barra cresce a partir do CHAO: `alt` sozinha cresceria pros dois
            # lados, entao o centro sobe metade da altura junto
            "y": [[k[0], BAR_BASE + k[1] / 2] + k[2:] for k in alt],
            "x": bx,
            "cor": {"tipo": "linear", "cores": [cor, cor + "CC"],
                    "de": [0, 120], "para": [0, -120]},
            "opacidade": {"mola": MOLA_ESTADO, "em": (10 + i * 0.8) * F,
                          "de": 0, "para": 0.9},
        })

    # ── o reflexo (:363-412) ──────────────────────────────────────────────
    # No original e UM container espelhado com uma mascara de degrade — aqui
    # tambem e uma unidade so: um grupo. Cada barra refletida tem sua altura,
    # mas nenhuma tem identidade propria, e a mascara vira o degrade do
    # preenchimento (opaco em cima, transparente embaixo; dentro do `cor` o
    # y DESCE, armadilha 5).
    reflexo = []
    for i in range(N_BARRAS):
        bx = BAR_X0 + i * (BAR_LARG + BAR_ESP)
        cor = _cor_barra(i)

        def _hr(fr, i=i):
            spr = _mola_ref(max(0.0, fr - 10 - i * 0.8) * F, 18, 80)
            return max(4.0, _onda(i, fr) * 50.0 * spr)

        alt = _amostrar(n_fr, _hr, 3)
        reflexo.append({
            "tipo": "retangulo", "larg": BAR_LARG, "raio": 10,
            "alt": alt,
            "y": [[k[0], BAR_BASE - k[1] / 2] + k[2:] for k in alt],
            "x": bx,
            "cor": {"tipo": "linear", "cores": [cor + "33", cor + "00"],
                    "de": [0, -30], "para": [0, 30]},
            # sem isto o reflexo aparece antes da barra e o rodape vira uma
            # regua pontilhada de 4 px atravessando o quadro
            "opacidade": {"mola": MOLA_ESTADO, "em": (10 + i * 0.8) * F,
                          "de": 0, "para": 1},
        })
    cam.append({"tipo": "grupo", "camadas": reflexo})

    # ── os quatro selos (:417-468) ────────────────────────────────────────
    # fonte 28 peso 900, espacamento 2, padding 16/36, raio 14, borda
    # #0A0A0A18, fundo quase branco. A entrada e mola 14/120/0.5 de 0.6 a 1 —
    # o `translateY(30)` do original ficou de fora de proposito: ele brigaria
    # com o float de ruido (+-3 px, :440-441), que e o que mantem o selo vivo.
    largs = [larg_texto(s, 28) + 2 * len(s) + 72 for s in SELOS]
    total = sum(largs) + 40 * (len(SELOS) - 1)
    x = -total / 2
    for i, nome in enumerate(SELOS):
        t = (30 + i * 5) * F
        cx = x + largs[i] / 2
        c = card(cx, -425, largs[i], 68, t, "#FFFFFFE6", "#0A0A0A18", 14, 200 + i)
        c["escala"] = {"mola": MOLA_TEXTO, "em": t, "de": 0.6, "para": 1.0}
        cam.append(c)
        cam.append({
            "tipo": "texto", "texto": nome, "tamanho": 28, "peso": 900,
            "cor": PRETO, "espacamento": 2,
            **viva(cx, -427, 2.5, 200 + i),      # mesma semente do card: os dois
            "opacidade": entra(t, 0.3),          # derivam juntos, nao um do outro
            "escala": {"mola": MOLA_TEXTO, "em": t, "de": 0.6, "para": 1.0},
        })
        x += largs[i] + 40

    return {"duracao": dur, "fundo": BG_BRANCO, "camadas": cam}
