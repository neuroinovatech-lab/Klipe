# -*- coding: utf-8 -*-
"""models.py — a cena Models do CreativlyBrandVideo.

Dois aneis de badges de modelos giram em perspectiva falsa em volta de um card
central que CONTA ate "30+" (ModelsScene.tsx:171-228 e :56-61). O `z` do orbital
e a cena inteira: vira escala 0.4->1.4, opacidade 0.08->1 (:188-189) — por isso
x/escala/opacidade dos 14 badges sao keyframes amostrados da mesma orbita.
Ao fundo: marca d'agua "MODELS" 500px a -8deg (:81-104), duas orbitas elipticas
desenhadas por `traco` (:63-70, :160-165), tres aneis de pulso (:157), duas
esferas de arame e dois diamantes 3D (:107-112) e estrelas de 4 pontas (:115-140).
"""
from .base import *

import math

# ── o catalogo do original (:23-30) ──────────────────────────────────────
MODELOS = [
    "GPT-4o", "Claude 3.5", "Midjourney 6", "Runway Gen-3",
    "Pika Art", "Suno v3", "ElevenLabs", "Gemini 1.5",
    "Llama 3", "Mistral Large", "Cohere", "Fal.ai",
    "Stable Video", "HuggingFace", "Flux Pro", "Ideogram",
    "Kling", "Luma Dream", "Sora", "DALL-E 3",
    "Whisper", "ControlNet", "AnimateDiff", "Jukebox",
]
# :174 poe 12 por anel; aqui 7, porque cada badge custa DUAS camadas (pilula +
# texto) e o teto de densidade e 90. Os 14 primeiros nomes, na ordem do original.
POR_ANEL = 7

TITULO = "MODELS INCLUDED"       # :293, textTransform uppercase
ESP_TITULO = 44 * 0.15           # :288 letterSpacing 0.15em

# a contagem de :56-61 — interpolate(frame,[15,45],[0,30], out(cubic)), com
# Math.floor. Estes sao os instantes exatos em que o numero VIRA, resolvidos
# de 30*(1-(1-p)^3) = v. Sete degraus: o olho le ticker, nao interpolacao.
DEGRAUS = [(0, 0.40), (10, 0.626), (17, 0.743), (22, 0.857),
           (26, 0.989), (29, 1.178), (30, 1.500)]

# :39-40 — as duas orbitas, ja centradas em (960,540) no proprio `d`
ORBITA_1 = "M 960 200 A 760 340 0 1 1 959 200"
ORBITA_2 = "M 960 140 A 820 400 0 1 0 959 140"


# ── amostragem ───────────────────────────────────────────────────────────
def _kf(f, dur: float, passo: float = 0.1) -> list:
    """Funcao continua -> keyframes lineares.

    O motor nao tem expressao; orbita, seno e ruido do original viram amostras.
    `linear` no keyframe que COMECA cada trecho (armadilha 6: no ultimo seria
    configuracao morta), e por isso o ultimo sai sem easing nenhum.
    """
    n = int(dur / passo) + 2
    ks = [[round(k * passo, 4), round(float(f(k * passo)), 4), "linear"]
          for k in range(n)]
    ks[-1] = ks[-1][:2]
    return ks


def _rampa(t: float, t0: float, d: float = 0.45) -> float:
    """outCubic 0->1, a entrada de mola do original achatada em curva."""
    p = min(1.0, max(0.0, (t - t0) / d))
    return 1.0 - (1.0 - p) ** 3


# ── fundo ────────────────────────────────────────────────────────────────
def _brilho_central() -> list:
    """:143-155 — 600x600 com tres paradas, blur 60, respirando por ruido
    (:54, centerGlow = 0.4 + 0.15*noise(frame*0.02))."""
    fora = []
    for raio, cor, base, amp, s in ((620, PRIMARIA, 0.13, 0.05, 5),
                                    (420, MARCA, 0.40, 0.14, 7),
                                    (260, CIANO, 0.34, 0.12, 9)):
        g = brilho(0, 0, raio, cor, 0.0, base, s=s)
        g["blur"] = 60
        g["opacidade"] = pulso(base, amp, 0.02, s)
        g["escala"] = pulso(1.10, 0.05, 0.02, s + 3)
        fora.append(g)
    return fora


def _aneis_pulso(dur: float, n: int = 3, r_max: float = 700.0) -> list:
    """:157 — PulseRings count 3, maxSize 1400, speed 0.3 (ciclo = 100 frames),
    opacidade em rampa [0, 0.2, 1] -> [0, 0.8, 0]."""
    ciclo = 100 * F
    fora = []
    for i in range(n):
        off = (i / n) * ciclo

        def prog(t, off=off):
            return ((t + off) % ciclo) / ciclo

        def fr(t, off=off):
            return prog(t, off) * r_max

        def fo(t, off=off):
            p = prog(t, off)
            return (p / 0.2) * 0.55 if p < 0.2 else (1.0 - (p - 0.2) / 0.8) * 0.55

        fora.append({
            "tipo": "elipse", "raio": _kf(fr, dur, 0.06), "cor": "#00000000",
            "contorno": MARCA + "40", "contorno_larg": 1,
            "opacidade": _kf(fo, dur, 0.06)})
    return fora


def _orbitas() -> list:
    """:63-70 — evolvePath desenhando as duas elipses. `traco` corre o CONTORNO
    (armadilha 2), entao o preenchimento e transparente. Easing no PRIMEIRO
    keyframe, senao o outCubic seria ignorado (armadilha 6)."""
    return [
        {"tipo": "path", "d": ORBITA_1, "cor": "#00000000",
         "contorno": MARCA + "55", "contorno_larg": 1.5,
         "traco": [[5 * F, 0.0, "outCubic"], [35 * F, 1.0]],
         **viva(0, 0, 4, 61)},
        {"tipo": "path", "d": ORBITA_2, "cor": "#00000000",
         "contorno": SECUNDARIA + "45", "contorno_larg": 1,
         "traco": [[10 * F, 0.0, "outCubic"], [40 * F, 1.0]],
         **viva(0, 0, 4, 77)},
    ]


def _esfera(cx, cy, raio, cor, vel, atraso, nv, nh, s, dur) -> list:
    """:107-108 + Rotating3D.tsx — a esfera de arame e um feixe de aneis:
    girando em Y, cada anel vertical projeta uma elipse de rx = R*|cos(a)|.
    Todos os aneis usam a MESMA semente de `viva` para a esfera derivar inteira."""
    fora = []
    for k in range(nv):
        a0 = (k / max(nv, 1)) * 180.0

        def frx(t, a0=a0):
            return max(2.0, raio * abs(math.cos(math.radians(a0 + t * FPS * 0.8 * vel))))

        fora.append({
            "tipo": "elipse", "rx": _kf(frx, dur, 0.08), "ry": raio,
            "cor": "#00000000", "contorno": cor, "contorno_larg": 1.5,
            **viva(cx, cy, 3, s), "opacidade": entra(atraso, 0.5),
            "escala": {"mola": MOLA_ESTADO, "em": atraso, "de": 0.5, "para": 1.0}})
    for k in range(nh):
        a0 = (k / max(nh, 1)) * 180.0

        def fry(t, a0=a0):
            return max(2.0, raio * abs(math.cos(math.radians(a0 + t * FPS * 0.5 * vel))))

        fora.append({
            "tipo": "elipse", "rx": raio, "ry": _kf(fry, dur, 0.08),
            "cor": "#00000000", "contorno": cor, "contorno_larg": 1,
            **viva(cx, cy, 3, s), "opacidade": entra(atraso + 0.05, 0.5),
            "escala": {"mola": MOLA_ESTADO, "em": atraso, "de": 0.5, "para": 1.0}})
    return fora


def _diamante(cx, cy, tam, cor, vel, atraso, s, dur) -> dict:
    """:111-112 — rotateX/rotateY continuos sobre um quadrado a 45deg. Em 2D o
    giro 3D e o achatamento: escalaX = |cos(rotY)|, escalaY = |cos(rotX)|."""
    def fex(t):
        return max(0.10, abs(math.cos(math.radians(t * FPS * 2.0 * vel))))

    def fey(t):
        return max(0.10, abs(math.cos(math.radians(t * FPS * 1.5 * vel))))

    return {"tipo": "retangulo", "larg": tam, "alt": tam, "cor": cor,
            "rotacao": 45, "escalaX": _kf(fex, dur, 0.05),
            "escalaY": _kf(fey, dur, 0.05),
            **viva(cx, cy, 10, s), "opacidade": entra(atraso, 0.5),
            "escala": {"mola": MOLA_ESTADO, "em": atraso, "de": 0.0, "para": 1.0}}


def _estrela_d(R: float) -> str:
    """makeStar({points: 4, innerRadius: R*0.3, outerRadius: R}) (:116)."""
    pts = []
    for k in range(8):
        a = -math.pi / 2 + k * math.pi / 4
        r = R if k % 2 == 0 else R * 0.3
        pts.append(f"{r * math.cos(a):.2f} {r * math.sin(a):.2f}")
    return "M " + " L ".join(pts) + " Z"


def _estrelas(n: int, dur: float) -> list:
    """:115-140 — 15 estrelas com deriva de ruido, giro proprio e pulso por
    seno. Aqui 9 (teto de camadas) e a posicao e determinista: o `random()` do
    Remotion nao da pra reproduzir fora dele."""
    fora = []
    for i in range(n):
        bx = ((((i * 173 + 41) % 100) / 100) - 0.5) * W * 0.94
        by = ((((i * 97 + 17) % 100) / 100) - 0.5) * H * 0.88
        tam = 4 + ((i * 37) % 13)
        atraso = ((i * 27) % 25) * F
        cor = MARCA if i % 3 == 0 else (PRIMARIA if i % 2 == 0 else SECUNDARIA)
        giro = 1.0 if i % 2 == 0 else -1.0

        def fo(t, i=i, atraso=atraso):
            p = math.sin(t * FPS * 0.08 + i * 1.5) * 0.3 + 0.4
            return _rampa(t, atraso, 0.4) * p * 0.30

        fora.append({
            "tipo": "path", "d": _estrela_d(tam * 1.25), "cor": cor + "99",
            "rotacao": [[0.0, 0.0, "linear"], [dur, dur * FPS * giro]],
            **viva(bx, by, 16, 400 + i * 7), "opacidade": _kf(fo, dur, 0.1)})
    return fora


# ── os badges em orbita ──────────────────────────────────────────────────
def _badge(nome: str, i: int, anel: int, k: int, dur: float) -> list:
    """:171-228. speed 0.8 com direcao alternada; z -> escala e opacidade.

    O raio unico de :178 (600/850) virou par rx/ry: ver comentario abaixo.
    """
    # ELIPSE, nao circulo. O original orbita em circulo e deixa o badge passar
    # por cima do card — la o card e opaco e oclui. Aqui o card e #000000A8:
    # o badge vazava atraves dele. rx/ry abaixo mantem a orbita INTEIRA fora da
    # caixa do card e dentro do quadro (conferido por _auditar()).
    rx, ry = (690.0, 350.0) if anel == 0 else (810.0, 465.0)
    vel = 0.8 * (1.0 if anel == 0 else -1.0)
    a0 = (k / POR_ANEL) * math.pi * 2.0
    t0 = (10 + i * 1.5) * F                     # Sequence from=5 + :194
    tam = 24
    larg = larg_texto(nome, tam) + 64           # padding 16/32 (:206)
    alt = tam + 32

    def ang(t):
        return a0 + t * FPS * vel * 0.01

    def fx(t):                                   # :181, :184
        return (math.cos(ang(t)) * rx
                + math.sin(t * 0.9 + i * 1.7) * 11 + math.sin(t * 2.3 + i * 0.6) * 7)

    def fy(t):                                   # :182, :186. `y` SOBE (armadilha 5),
        # entao o -sin joga a FRENTE da orbita para baixo — que e onde o badge
        # tambem esta maior. Grande embaixo = perto: a perspectiva fecha.
        return (-math.sin(ang(t)) * ry
                + math.sin(t * 1.1 + i * 2.4) * 9 + math.sin(t * 1.9 + i * 1.2) * 5)

    def fe(t):                                   # :188 [0.4,1.4], fechado em [0.62,1.28]
        return (0.95 + 0.33 * math.sin(ang(t))) * _rampa(t, t0)

    def fo(t):                                   # :189 [0.08,1] -> [0.22,1]:
        # 0.08 nao e profundidade, e camada invisivel. O piso sobe ate LER.
        return (0.61 + 0.39 * math.sin(ang(t))) * _rampa(t, t0)

    kx, ky = _kf(fx, dur, 0.1), _kf(fy, dur, 0.1)
    ke, ko = _kf(fe, dur, 0.1), _kf(fo, dur, 0.1)
    cor_b = MARCA if anel == 0 else SECUNDARIA
    return [
        {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": 50,
         "cor": "#FFFFFF14" if anel == 0 else "#FFFFFF0A",
         "contorno": cor_b, "contorno_larg": 1,
         "x": kx, "y": ky, "escala": ke, "opacidade": ko},
        {"tipo": "texto", "texto": nome, "tamanho": tam, "peso": 700,
         "cor": TEXTO, "x": kx, "y": ky, "escala": ke, "opacidade": ko},
    ]


def _badges(dur: float) -> list:
    fora = []
    for anel in (0, 1):
        k = 0
        for i, nome in enumerate(MODELOS):
            if i % 2 != anel or k >= POR_ANEL:
                continue
            fora += _badge(nome, i, anel, k, dur)
            k += 1
    return fora


def _auditar(passo: float = 0.05) -> dict:
    """Prova numerica de que a orbita nao colide. Roda a volta INTEIRA (nao so
    a duracao da cena) e devolve as folgas minimas, em px:

      card   — badge x caixa do card. <=0 significa texto sobre texto.
      quadro — badge x borda de 1920x1080. <=0 significa nome cortado.
      anel   — badge do anel 0 x badge do anel 1.

    Existe porque rx/ry acima sao numeros escolhidos, e numero escolhido sem
    prova apodrece no primeiro nome novo em MODELOS. Se algum valor ficar
    negativo, e essa lista que mudou — mexa em rx/ry, nao no render.
    """
    cw = larg_texto(TITULO, 44) + ESP_TITULO * (len(TITULO) - 1) + 200
    ca, cb = cw / 2 + 4, 151 + 4          # +4 = deriva do `viva` do card
    volta = 2 * math.pi / (FPS * 0.8 * 0.01)

    def caminho(anel, k, i, nome):
        rx, ry = (690.0, 350.0) if anel == 0 else (810.0, 465.0)
        vel = 0.8 * (1.0 if anel == 0 else -1.0)
        a0 = (k / POR_ANEL) * math.pi * 2.0
        hw0, hh0 = (larg_texto(nome, 24) + 64) / 2, (24 + 32) / 2
        for n in range(int(volta / passo) + 1):
            t = n * passo
            a = a0 + t * FPS * vel * 0.01
            e = 0.95 + 0.33 * math.sin(a)
            yield (math.cos(a) * rx + math.sin(t * 0.9 + i * 1.7) * 11
                   + math.sin(t * 2.3 + i * 0.6) * 7,
                   -math.sin(a) * ry + math.sin(t * 1.1 + i * 2.4) * 9
                   + math.sin(t * 1.9 + i * 1.2) * 5,
                   hw0 * e, hh0 * e)

    trilhas = {0: [], 1: []}
    for anel in (0, 1):
        k = 0
        for i, nome in enumerate(MODELOS):
            if i % 2 != anel or k >= POR_ANEL:
                continue
            trilhas[anel].append(list(caminho(anel, k, i, nome)))
            k += 1

    card = quadro = anel_x = 1e9
    for anel in (0, 1):
        for tr in trilhas[anel]:
            for x, y, hw, hh in tr:
                card = min(card, max(abs(x) - (ca + hw), abs(y) - (cb + hh)))
                quadro = min(quadro, W / 2 - (abs(x) + hw), H / 2 - (abs(y) + hh))
    for a in trilhas[0]:
        for b in trilhas[1]:
            for (x1, y1, w1, h1), (x2, y2, w2, h2) in zip(a, b):
                anel_x = min(anel_x, max(abs(x1 - x2) - (w1 + w2),
                                         abs(y1 - y2) - (h1 + h2)))
    return {"card": round(card, 1), "quadro": round(quadro, 1),
            "anel": round(anel_x, 1)}


# ── o card central ───────────────────────────────────────────────────────
def _contador(y: float) -> list:
    """:246-266 — o numero em degrau. O motor nao anima TEXTO, entao cada valor
    e uma camada e o estado vira tempo: corte seco entre elas, sem crossfade."""
    fora = []
    for j, (v, t_on) in enumerate(DEGRAUS):
        t_off = DEGRAUS[j + 1][1] if j + 1 < len(DEGRAUS) else None
        sobe_em = 0.15 if j == 0 else 0.03
        op = [[t_on, 0.0, "outCubic"], [t_on + sobe_em, 1.0]]
        if t_off is not None:
            op += [[t_off - 0.03, 1.0, "linear"], [t_off, 0.0]]
        fora.append({
            "tipo": "texto", "texto": f"{v}+", "tamanho": 120, "peso": 900,
            "italico": True, "cor": CIANO, "contorno": MARCA, "contorno_larg": 2,
            "sombra": [{"x": 0, "y": 0, "blur": 30, "cor": MARCA + "66"}],
            **viva(0, y, 1.5, 21), "opacidade": op})
    return fora


def _card() -> list:
    """:231-301 — padding 50/100, raio 40, borda brand44, mola de DESTAQUE
    (a unica da cena) e blur 20->0. O grupo existe porque o original escala o
    DIV INTEIRO: fora dele, o texto nao subiria junto com a caixa."""
    larg_ti = larg_texto(TITULO, 44) + ESP_TITULO * (len(TITULO) - 1)
    cw, ch = larg_ti + 200, 302.0
    t_card = 12 * F                              # :47 spring(frame - 12)

    dentro = sombra(0, 0, cw, ch, t_card, raio=40, n=3)

    # fantasma borrado: `blur` nao e animavel (armadilha 4), entao o foco
    # entrando e uma copia fixa em blur 16 saindo por baixo da nitida (:243)
    dentro.append({"tipo": "retangulo", "larg": cw, "alt": ch, "raio": 40,
                   "cor": "#0A1220", "contorno": MARCA + "55", "contorno_larg": 1,
                   "blur": 16,
                   "opacidade": [[t_card, 0.0, "outCubic"], [t_card + 0.12, 0.85],
                                 [t_card + 0.2, 0.85, "outCubic"], [0.9, 0.0]]})

    caixa = card(0, 0, cw, ch, t_card, cor="#000000A8", borda=MARCA + "55",
                 raio=40, s=31)
    caixa["escala"] = 1.0        # a escala mora no GRUPO — ver docstring
    caixa["x"], caixa["y"] = 0, 0
    dentro.append(caixa)

    dentro += _contador(50.0)
    dentro.append(rotulo("AI", 0.45, -23.0, MUDO, 28, 0.0, 8, 400))   # :268-280

    # :292-298 — CharacterReveal delay 5, stagger 2 frames, offsetY 25
    letras = titulo(TITULO, (8 + 5) * F, -74.0, 44, TEXTO, 900, 2 * F)
    vivos = [j for j, ch in enumerate(TITULO) if ch != " "]
    for L, j in zip(letras, vivos):
        L["x"] += (j - (len(TITULO) - 1) / 2) * ESP_TITULO
    dentro += letras

    g = brilho(0, 0, 460, MARCA, t_card, 0.16, s=13)   # :241 glow 100px brand15
    grupo = {"tipo": "grupo", **viva(0, 0, 2.5, 31),
             "escala": {"mola": MOLA_DESTAQUE, "em": t_card, "de": 0.3,
                        "para": 1.0},
             "camadas": dentro}
    return [g, grupo]


# ── a cena ───────────────────────────────────────────────────────────────
def cena(dur: float) -> dict:
    camadas = [marca_dagua("MODELS", 500, MARCA, -8, 0.06)]      # :81-104
    camadas += _brilho_central()
    camadas += _aneis_pulso(dur)
    camadas += _orbitas()
    camadas += _esfera(-760, 340, 60, MARCA + "40", 0.8, 3 * F, 4, 2, 811, dur)
    camadas += _esfera(690, -310, 40, PRIMARIA + "35", 1.1, 8 * F, 3, 1, 822, dur)
    camadas += [
        brilho(-860, -260, 90, MARCA, 5 * F, 0.30, s=91),        # :111 glow
        _diamante(-860, -260, 30, MARCA + "66", 0.9, 5 * F, 93, dur),
        _diamante(790, 340, 25, SECUNDARIA + "55", 1.2, 10 * F, 95, dur),
    ]
    camadas += _estrelas(9, dur)
    camadas += _badges(dur)
    camadas += _card()
    return {"duracao": dur, "fundo": BG, "camadas": camadas}
