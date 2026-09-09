# -*- coding: utf-8 -*-
"""
montar_prancha.py — "DE FORMIS" : as 11 falas da Dra. Eli como prancha gravada.

Segunda tentativa. A primeira (montar_padroes) saiu competente e generica
porque eu peguei emprestado o vocabulario dos presets virais do Klipe — ciano
e ambar sobre azul-marinho — em vez de desenhar um mundo pra esta peca. Ela
apontou isso com precisao: "ta mais do mesmo que ja fizemos antes".

Aqui a peca tem MATERIAL: papel envelhecido, tinta, buril, serifa editorial. E
tem MEMORIA — e uma folha so, onde cada fala acrescenta uma camada e o que foi
desenhado PERMANECE. Aos 60s ainda esta la o que nasceu aos 4s. Era isso que
separava o RadiusMotion de uma sequencia de slides.

Nao ha uma linha de Skia neste arquivo: papel e hachura viraram primitivas do
DSL (`motioncore.cena.textura`), entao a proxima peca com material nao comeca
do zero.

    python -m motioncore.montar_prancha --stills
    python -m motioncore.montar_prancha --cenas     # 1 mp4 por cena, pro Klipe
"""
from __future__ import annotations

import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from .cena import Cena, validar

RAIZ = Path(__file__).resolve().parent.parent
PROJ = RAIZ / "public" / "projects" / "eli-prancha"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

W, H, FPS = 1080, 1920, 30
DUR = 69.7527
N_FRAMES = int(round(DUR * FPS))

# `--overlay` faz a prancha sair como CAMADA (cor|alpha) em vez de video
# pronto. E a separacao que um editor precisa: video principal de um lado,
# efeito de outro, cada um trocavel sem refazer o outro.
OVERLAY = "--overlay" in sys.argv

# A prancha sai em BLOCOS, nao num clipe unico de 70s. O motivo nao e tecnico,
# e de edicao: clipe de 70s nao tem onde pegar. Em blocos ela vira material
# que ela reposiciona, encurta e apaga na UI sem depender de mim pra coisa
# basica. Cada bloco e uma batida de conteudo, nao uma fatia de relogio.
BLOCOS = [
    ("abertura",   0.00,  8.90),   # moldura, grade, COMPOSIÇÃO / PADRÕES
    ("malha",      8.90, 15.40),   # a rede se fechando
    ("cortex",    15.40, 22.50),   # aneis + setor a buril + CÓRTEX TEMPORAL
    ("irregular", 22.50, 31.60),   # grade de quadrados + a irregularidade
    ("ambiente",  31.60, 36.00),   # a regua atravessando
    ("pessoal",   36.00, 48.50),   # EU VEJO + a agulha + EU ANTECIPO
    ("dualidade", 48.50, 62.60),   # a folha dividida
    ("fecho",     62.60, 69.75),   # E VOCÊ?
]

# ── tinta sobre papel ────────────────────────────────────────────────────
PAPEL = "#C7A978"
PAPEL_CLARO = "#D8C092"
PRETO = "#1E1A16"
MARROM = "#34281C"
CINZA = "#625847"
DOURADO = "#90713F"
VERMELHO = "#8F1D18"
VERMELHO_ESC = "#68120F"

SERIF = "PlayfairDisplay"       # o Bodoni da peca
GARAMOND = "CormorantGaramond"  # caps e latim

CX, CY = 0.0, -120.0            # centro do diagrama (relativo ao centro da tela)

# Janelas onde o PAPEL sai e entra a imagem dela: 20,45s de 69,75s = 29%.
# Ela pediu metade; ficou em 29% porque escolhi pelos trechos em PRIMEIRA
# PESSOA ("eu vejo", "eu antecipo", "e você?") e sao esses que existem na
# fala. Chegar a 50% exige abrir uma terceira janela num trecho expositivo,
# onde a imagem dela acrescenta menos — decisao dela, nao minha.
JANELAS = [
    (35.60, 48.60),   # "eu, por exemplo" + "eu antecipo" + "observação"
    (62.30, 69.75),   # "e você?"
]


# ── helpers ──────────────────────────────────────────────────────────────
def kf(base: float, pares: list) -> list:
    return [[base + p[0]] + list(p[1:]) for p in pares]


def surge(t0: float, dur: float = 0.7) -> list:
    """A tinta ENCOSTA no papel: aparece e fica. Nada nesta peca pisca."""
    return [[t0, 0], [t0 + dur, 1, "inOutCubic"]]


def desenha(t0: float, dur: float = 1.0) -> list:
    """Traco progressivo — a pena tecnica correndo sobre a folha."""
    return [[t0, 0], [t0 + dur, 1, "inOutCubic"]]


def vive(t0: float, ate: float, dur: float = 0.7, pico: float = 1.0,
         saida: float = 0.9) -> dict:
    """Aparece, fica, e SAI.

    "Nada e apagado" foi longe demais: a grade de quadrados ficava 50s na tela
    e a folha parava de acontecer. A prancha tem que renovar — cada figura tem
    o seu tempo, e o que fica e o esqueleto (moldura, aneis, eixo), nao tudo.
    """
    return {
        "opacidade": [[t0, 0], [t0 + dur, pico, "inOutCubic"],
                      [ate - saida, pico], [ate, 0, "inOutCubic"]],
        "inicio": t0 - 0.05, "fim": ate + 0.05,
    }


def serifa(txt: str, t0: float, y: float, tam: float = 120, cor: str = PRETO,
           fonte: str = SERIF, peso: int = 400, esp: float = 0.0,
           ital: bool = False, larg: float = 0.84, dur: float = 0.8,
           ate: float | None = None, **extra) -> dict:
    """`ate` fecha a janela do rotulo.

    "Nada e apagado" vale pro DESENHO — a folha tem que lembrar o que ja foi
    tracado. Nao vale pro TEXTO: sem `ate`, PADROES, CORTEX TEMPORALIS e
    E VOCE? imprimiram um por cima do outro e a folha virou borrao. Numa
    prancha de verdade o diagrama acumula; o rotulo cede a vez.
    """
    op = surge(t0, dur) if ate is None else [
        [t0, 0], [t0 + dur, 1, "inOutCubic"],
        [ate - 0.6, 1], [ate, 0, "inOutCubic"]]
    c = {
        "tipo": "texto", "texto": txt, "fonte": fonte, "peso": peso,
        "italico": ital, "tamanho": tam, "cor": cor, "espacamento": esp,
        "largura_max": W * larg, "entrelinha": 1.14, "y": y,
        "opacidade": op, "inicio": t0 - 0.05,
    }
    if ate is not None:
        c["fim"] = ate + 0.05
    c.update(extra)
    return c


def anel(raio: float, t0: float, larg: float = 1.6, cor: str = MARROM,
         de: float = -90, varre: float = 360, dur: float = 1.2, **extra) -> dict:
    c = {
        "tipo": "elipse", "raio": raio, "de_grau": de, "varre_grau": varre,
        "contorno": cor, "contorno_larg": larg, "x": CX, "y": CY,
        "traco": desenha(t0, dur), "opacidade": surge(t0, 0.2),
        "inicio": t0 - 0.05,
    }
    c.update(extra)
    return c


def setor(r_ext: float, de: float, varre: float, t0: float, r_int: float = 0.0,
          cor: str = PRETO,
          passo: float = 0.5, op_hach: float = 0.6, dur: float = 0.9,
          **extra) -> dict:
    """Setor preenchido a BURIL, nao a cor chapada — e o que da a gravura."""
    c = {
        "tipo": "elipse", "raio": r_ext, "raio_int": r_int, "de_grau": de,
        "x": CX, "y": CY,
        "varre_grau": [[t0, 0.5], [t0 + dur, varre, "inOutCubic"]],
        "hachura": {"modo": "radial", "passo": passo, "cor": cor,
                    "opacidade": op_hach, "largura": 0.8, "r0": r_int},
        "opacidade": surge(t0, 0.3), "inicio": t0 - 0.05,
    }
    c.update(extra)
    return c


def rotulo(txt: str, t0: float, x: float, y: float, tam: float = 34,
           cor: str = MARROM, larg: float = 0.42,
           ate: float | None = None, **extra) -> dict:
    """Rotulo de prancha: italico, pequeno, discreto. Nunca compete."""
    return serifa(txt, t0, y, tam=tam, cor=cor, fonte=GARAMOND, ital=True,
                  larg=larg, dur=0.6, x=x, ate=ate, **extra)


# ═══════════════════════════════════════════════════════════════════════════
# A FOLHA — uma so, construida em 70s. Nada e apagado.
# ═══════════════════════════════════════════════════════════════════════════
def camadas() -> list:
    # O papel some nas JANELAS DE IMAGEM e entra o video dela. A escolha nao e
    # decorativa: sai papel exatamente onde ela fala de si — "eu vejo os
    # padroes", "eu antecipo", "e voce?". A gravura continua por cima, entao a
    # peca nao troca de linguagem, so troca de superficie.
    cs: list = [
        {"tipo": "textura", "cor": PAPEL, "grao": 0.05, "manchas": 10,
         "vinheta": 0.5, "falhas": 26, "semente": 1879,
         **vive(0.0, JANELAS[0][0], 0.5, 1.0, 0.9)},
        {"tipo": "textura", "cor": PAPEL, "grao": 0.05, "manchas": 10,
         "vinheta": 0.5, "falhas": 26, "semente": 1879,
         **vive(JANELAS[0][1], JANELAS[1][0], 0.9, 1.0, 0.9)},
    ]

    # ── moldura e cabecalho da prancha (0–2s) ────────────────────────────
    cs += [
        {"tipo": "retangulo", "larg": W - 108, "alt": H - 108,
         "contorno": MARROM, "contorno_larg": 2.2,
         "traco": desenha(0.2, 1.6), "opacidade": surge(0.2, 0.2)},
        {"tipo": "retangulo", "larg": W - 132, "alt": H - 132,
         "contorno": MARROM, "contorno_larg": 0.9,
         "traco": desenha(0.5, 1.6), "opacidade": surge(0.5, 0.2), "y": 0},
    ]

    # ═══ 1. "Ja parou para pensar na incrivel capacidade de pessoas
    #        autistas de entender padroes?"  (0.00–5.60) ═══
    # A grade de pontos nasce irradiando: e a tese em um gesto.
    cs += [
        {"tipo": "elipse", "raio": 4.5, "cor": MARROM, "x": CX, "y": CY,
         "repetir": {"cols": 9, "linhas": 11, "espX": 96, "espY": 96,
                     "atraso": 0.028, "ordem": "centro"},
         "escala": kf(0.0, [[0.9, 0], [1.5, 1, "inOutCubic"]]),
         "opacidade": [[0.9, 0], [1.5, 0.75, "inOutCubic"], [14.4, 0.75],
                       [15.6, 0, "inOutCubic"]], "inicio": 0.8, "fim": 15.7},
        serifa("COMPOSIÇÃO", 1.6, y=700, tam=74, fonte=GARAMOND, peso=700,
               esp=18, cor=MARROM, ate=15.0),
        {"tipo": "linha", "de": [-120, 0], "para": [120, 0], "y": 625,
         "contorno": MARROM, "contorno_larg": 1.4,
         "traco": desenha(2.0, 0.5), "opacidade": surge(2.0, 0.2), "inicio": 1.9},
        serifa("PADRÕES", 2.3, y=495, tam=192, esp=2, ate=15.0),
        serifa("o que o cérebro vê\nantes de você", 3.4, y=372, tam=54, fonte=GARAMOND,
               ital=True, cor=CINZA, ate=15.0),
        # um ponto vira TINTA CHEIA — quem enxerga o padrao
        {"tipo": "elipse", "raio": 11, "cor": VERMELHO, "x": CX, "y": CY,
         "escala": kf(0.0, [[4.1, 0], [4.8, 1, "inOutCubic"]]), "inicio": 4.0},
            ]

    # ═══ 2. "E como se a gente tivesse um sexto sentido." (5.98–8.82) ═══
    # Cinco raios medidos e um sexto que nao devia existir.
    for i in range(6):
        a = math.radians(-90 + i * 36)
        sexto = i == 5
        cs.append({
            "tipo": "linha",
            "de": [CX + math.cos(a) * 60, CY + math.sin(a) * 60],
            "para": [CX + math.cos(a) * 470, CY + math.sin(a) * 470],
            "contorno": VERMELHO if sexto else MARROM,
            "contorno_larg": 2.6 if sexto else 1.3,
            "traco": desenha(6.2 + i * 0.22, 0.5),
            **vive(6.2 + i * 0.22, 15.4, 0.2),
        })
    cs += [
        serifa("SEXTO SENTIDO", 6.9, y=-560, tam=104, fonte=GARAMOND, peso=700,
               esp=8, cor=VERMELHO, ate=9.2),
        rotulo("o sentido que ninguém conta", 8.0, x=0, y=-670, tam=42, larg=0.8, ate=9.2),
    ]

    # ═══ 3. "O nosso cerebro tem um poder extraordinario na criacao de
    #        padroes." (8.94–14.82) ═══
    # A malha se fecha: os pontos soltos viram estrutura.
    anel1 = [(CX + math.cos(math.radians(a)) * 170,
              CY + math.sin(math.radians(a)) * 170) for a in range(-90, 270, 60)]
    anel2 = [(CX + math.cos(math.radians(a)) * 380,
              CY + math.sin(math.radians(a)) * 380) for a in range(-60, 300, 60)]
    arestas = ([(anel1[i], anel1[(i + 1) % 6]) for i in range(6)]
               + [(anel1[i], anel2[i]) for i in range(6)]
               + [(anel1[(i + 1) % 6], anel2[i]) for i in range(6)]
               + [(anel2[i], anel2[(i + 1) % 6]) for i in range(6)])
    for i, ((x0, y0), (x1, y1)) in enumerate(arestas):
        cs.append({
            "tipo": "linha", "de": [x0, y0], "para": [x1, y1],
            "contorno": MARROM, "contorno_larg": 1.15,
            "traco": desenha(9.3 + i * 0.10, 0.45),
            **vive(9.3 + i * 0.10, 21.2, 0.2),
        })
    for i, (x, y) in enumerate(anel1 + anel2):
        cs.append({
            "tipo": "elipse", "raio": 6, "cor": PRETO, "x": x, "y": y,
            "escala": kf(0, [[9.2 + i * 0.09, 0], [9.7 + i * 0.09, 1, "inOutCubic"]]),
            **vive(9.2 + i * 0.09, 21.2, 0.4),
        })
    cs += [
        serifa("O CÉREBRO\nNÃO ACHA — ELE CRIA", 12.0, y=-575, tam=86, fonte=GARAMOND,
               peso=700, esp=4, cor=MARROM, ate=15.2, larg=0.9),
        rotulo("força criadora de formas", 13.8, x=0, y=-730, tam=40,
               larg=0.8, ate=15.2),
    ]

    # ═══ 4. "A regiao do cerebro que faz isso e o cortex temporal."
    #        (14.82–21.46) ═══
    # Os aneis de medida se fecham e UM setor recebe tinta.
    for i, r in enumerate([120, 230, 330, 430]):
        cs.append(anel(r, 15.1 + i * 0.30, larg=1.9 if i == 3 else 1.2, dur=1.3))
    for i in range(36):                      # marcas de escala
        a = math.radians(i * 10)
        cs.append({
            "tipo": "retangulo", "larg": 2, "alt": 14, "cor": MARROM,
            "x": CX + math.cos(a) * 452, "y": CY + math.sin(a) * 452,
            "rotacao": -i * 10 + 90,
            **vive(16.4 + i * 0.012, 31.6, 0.5, 0.9),
        })
    cs += [
        setor(430, 152, 74, 17.4, r_int=262, cor=PRETO, passo=0.6, op_hach=0.9,
              dur=1.1, **vive(17.4, 31.6, 0.3)),
        anel(430, 17.4, larg=2.2, cor=PRETO, de=152, varre=74, dur=1.1),
        anel(262, 17.6, larg=2.2, cor=PRETO, de=152, varre=74, dur=1.1),
        # chamada em cotovelo, nascendo colada no setor
        {"tipo": "path", "d": "M0,0 L-110,-110 L-200,-110", "centrar": False,
         "x": CX - 232, "y": CY - 170, "contorno": VERMELHO, "contorno_larg": 1.6,
         "traco": desenha(18.9, 0.7), "opacidade": surge(18.9, 0.2), "inicio": 18.8},
        serifa("CÓRTEX\nTEMPORAL", 19.0, y=565, tam=126, fonte=GARAMOND,
               peso=700, esp=4, cor=VERMELHO, ate=31.4),
        rotulo("a região que distingue as formas", 20.3, x=0, y=418,
               tam=40, larg=0.86, ate=31.4),
    ]

    # ═══ 5. "Processamento de informacoes sensoriais e identificacao de
    #        irregularidades." (21.46–30.96) ═══
    # A grade regular ganha peso; um elemento sai do eixo.
    cs += [
        {"tipo": "retangulo", "larg": 30, "alt": 30, "cor": MARROM,
         "x": CX, "y": CY,
         "repetir": {"cols": 7, "linhas": 9, "espX": 112, "espY": 112,
                     "atraso": 0.035, "ordem": "linha"},
         "escala": kf(0, [[22.0, 0], [22.6, 1, "inOutCubic"]]),
         "opacidade": [[22.0, 0], [22.6, 0.55, "inOutCubic"], [34.8, 0.55],
                      [36.0, 0, "inOutCubic"]], "inicio": 21.9, "fim": 36.1},
        # a irregularidade
        {"tipo": "retangulo", "larg": 44, "alt": 44, "cor": VERMELHO,
         "x": CX + 112, "y": CY + 112,
         "rotacao": kf(0, [[25.4, 0], [26.4, 45, "inOutCubic"]]),
         "opacidade": surge(25.2, 0.5), "inicio": 25.1},
        anel(96, 26.6, larg=2.0, cor=VERMELHO, dur=0.8,
             x=CX + 112, y=CY + 112),
        serifa("IRREGULARIDADE", 26.9, y=-560, tam=96, fonte=GARAMOND,
               peso=700, esp=4, cor=VERMELHO, ate=31.2),
        rotulo("o que sai do padrão\nsalta primeiro aos olhos", 28.4, x=0, y=-700,
               tam=42, larg=0.84, ate=31.2),
        serifa("ordem · sentido · sinal", 24.2, y=712, tam=50, fonte=GARAMOND,
               ital=True, cor=CINZA, ate=31.4),
    ]

    # ═══ 6. "Nos ajuda a perceber e analisar padroes no ambiente."
    #        (31.14–35.70) ═══
    # Uma regua de medida atravessa a folha, de baixo pra cima.
    cs += [
        {"tipo": "linha", "de": [-430, 0], "para": [430, 0],
         "y": kf(0, [[31.5, -560], [35.0, 380, "inOutCubic"]]),
         "contorno": VERMELHO, "contorno_larg": 1.6,
         "opacidade": [[31.4, 0], [31.9, 0.9, "outCubic"],
                       [34.6, 0.9], [35.3, 0]], "inicio": 31.3, "fim": 35.4},
        {"tipo": "retangulo", "larg": 12, "alt": 2, "cor": VERMELHO, "x": -430,
         "repetir": {"cols": 2, "linhas": 1, "espX": 860},
         "y": kf(0, [[31.5, -560], [35.0, 380, "inOutCubic"]]),
         "opacidade": [[31.4, 0], [31.9, 0.9], [34.6, 0.9], [35.3, 0]],
         "inicio": 31.3, "fim": 35.4},
        serifa("NO AMBIENTE", 32.3, y=-560, tam=100, fonte=GARAMOND, peso=700,
               esp=6, cor=MARROM, ate=36.0),
    ]

    # ═══ 7. "Eu, por exemplo, sou otima em padroes." (35.96–38.16) ═══
    cs += [
        {"tipo": "linha", "de": [0, -150], "para": [0, 150], "x": -400, "y": 760,
         "contorno": VERMELHO, "contorno_larg": 3,
         "traco": desenha(36.1, 0.4), "opacidade": surge(36.1, 0.2),
         "inicio": 36.0},
        serifa("quanto a mim", 36.3, y=848, tam=60, fonte=GARAMOND, ital=True,
               cor=CINZA, alinha="left", larg=0.78, ate=48.2),
        serifa("EU VEJO\nOS PADRÕES", 36.7, y=700, tam=104, fonte=GARAMOND,
               peso=700, esp=2, alinha="left", larg=0.80, ate=48.2),
    ]

    # ═══ 8. "As vezes eu antecipo as coisas que irao acontecer."
    #        (38.30–44.06) ═══
    # Escala de tempo: marcas medidas, e uma agulha que se adianta.
    cs += [
        {"tipo": "linha", "de": [-400, 0], "para": [400, 0], "y": -770,
         "contorno": MARROM, "contorno_larg": 1.6,
         "traco": desenha(38.6, 0.8), **vive(38.6, 48.5, 0.2)},
        {"tipo": "retangulo", "larg": 1.6, "alt": 20, "cor": MARROM,
         "x": -400, "y": -782,
         "repetir": {"cols": 9, "linhas": 1, "espX": 100, "atraso": 0.07},
         **vive(39.3, 48.5, 0.4, 0.85)},
        # a agulha: passa do presente e para adiante
        {"tipo": "retangulo", "larg": 2.5, "alt": 74, "cor": VERMELHO, "y": -770,
         "x": kf(0, [[40.0, -400], [41.4, 40, "inOutCubic"],
                     [42.0, 40], [43.0, 330, "inOutCubic"]]),
         **vive(40.0, 48.5, 0.3)},
        {"tipo": "elipse", "raio": 9, "cor": VERMELHO, "y": -700,
         "x": kf(0, [[40.0, -400], [41.4, 40, "inOutCubic"],
                     [42.0, 40], [43.0, 330, "inOutCubic"]]),
         **vive(40.0, 48.5, 0.3)},
        serifa("EU ANTECIPO", 41.2, y=-452, tam=104, _halo=False, fonte=GARAMOND, peso=700,
               esp=4, cor=VERMELHO, ate=46.1),
        rotulo("no trabalho · com a família", 42.8, x=0, y=-560, tam=38, _halo=False,
               larg=0.8, ate=46.1),
    ]

    # ═══ 9. "...pelo simples fato de observacoes de padroes." (44.06–48.46) ═══
    # Todos os raios convergem — a folha volta a ter um centro.
    for i in range(18):
        a = math.radians(i * 20)
        cs.append({
            "tipo": "linha",
            "de": [CX + math.cos(a) * 470, CY + math.sin(a) * 470],
            "para": [CX + math.cos(a) * 60, CY + math.sin(a) * 60],
            "contorno": DOURADO, "contorno_larg": 1.0,
            "traco": desenha(44.4 + i * 0.05, 0.7),
            **vive(44.4 + i * 0.05, 49.4, 0.2),
        })
    cs += [
        {"tipo": "elipse", "raio": 30, "cor": PRETO, "x": CX, "y": CY,
         "escala": kf(0, [[46.4, 0], [47.1, 1, "inOutCubic"]]), "inicio": 46.3},
        serifa("OBSERVAÇÃO", 46.5, y=-452, tam=96, _halo=False, fonte=GARAMOND, peso=700,
               esp=6, cor=MARROM, ate=48.4),
    ]

    # ═══ 10. "A dualidade: nao captar indiretas, mas prever eventos futuros
    #         — de inocente para sensitiva em segundos." (48.46–62.30) ═══
    # A folha se divide. Esquerda vazia e medida; direita gravada a buril.
    cs += [
        {"tipo": "linha", "de": [0, -620], "para": [0, 620], "y": CY + 60,
         "contorno": MARROM, "contorno_larg": 1.3,
         "traco": desenha(48.8, 1.0), "opacidade": surge(48.8, 0.2),
         "inicio": 48.7},
        serifa("DUALIDADE", 49.4, y=772, tam=98, fonte=GARAMOND, peso=700,
               esp=8, cor=MARROM, ate=62.6),
        # esquerda: contorno vazio
        {"tipo": "elipse", "raio": 42, "contorno": CINZA, "contorno_larg": 1.4,
         "x": -250, "y": CY + 60,
         "repetir": {"cols": 3, "linhas": 5, "espX": 118, "espY": 118,
                     "atraso": 0.05, "ordem": "linha"},
         **vive(50.0, 62.9, 0.6)},
        serifa("INOCENTE", 51.2, y=-620, tam=68, fonte=GARAMOND, peso=700,
               esp=2, cor=CINZA, x=-250, larg=0.45, ate=62.6),
        rotulo("não capta\no que se cala", 52.0, x=-250, y=-712, tam=36,
               cor=CINZA, larg=0.45, ate=62.6),
        # direita: os mesmos circulos, agora GRAVADOS
        {"tipo": "elipse", "raio": 42, "x": 250, "y": CY + 60,
         "repetir": {"cols": 3, "linhas": 5, "espX": 118, "espY": 118,
                     "atraso": 0.09, "ordem": "centro"},
         "hachura": {"modo": "paralela", "angulo": 34, "passo": 5,
                     "cor": VERMELHO_ESC, "opacidade": 0.75, "largura": 0.9},
         "contorno": VERMELHO_ESC, "contorno_larg": 1.4,
         **vive(55.0, 62.9, 0.5)},
        serifa("SENSITIVA", 56.4, y=-620, tam=68, fonte=GARAMOND, peso=700,
               esp=2, cor=VERMELHO, x=250, larg=0.45, ate=62.6),
        rotulo("prevê o que\nestá por vir", 57.2, x=250, y=-712, tam=36,
               cor=VERMELHO, larg=0.45, ate=62.6),
        # a travessia
        {"tipo": "linha", "de": [-190, 0], "para": [170, 0], "y": 620,
         "contorno": VERMELHO, "contorno_larg": 2.4,
         "traco": desenha(58.4, 1.0), "opacidade": surge(58.4, 0.2),
         "inicio": 58.3},
        {"tipo": "path", "d": "M-24,-20 L12,0 L-24,20", "centrar": False,
         "x": 170, "y": 620, "contorno": VERMELHO, "contorno_larg": 2.4,
         "traco": desenha(59.3, 0.4), "opacidade": surge(59.3, 0.2),
         "inicio": 59.2},
        serifa("em segundos", 60.0, y=548, tam=72, fonte=GARAMOND, ital=True,
               cor=MARROM, ate=62.6),
    ]

    # ═══ 11. "E voce, ja parou para refletir sobre a sua capacidade?"
    #         (62.52–69.04) ═══
    # A folha inteira permanece. So a pergunta e nova — e o ponto vermelho
    # do inicio ganha um segundo, que e o espectador.
    cs += [
        {"tipo": "elipse", "raio": 11, "cor": VERMELHO, "x": CX + 96, "y": CY,
         "escala": kf(0, [[63.6, 0], [64.4, 1, "inOutCubic"]]), "inicio": 63.5},
        anel(150, 64.6, larg=1.6, cor=VERMELHO, dur=1.0, x=CX + 48, y=CY),
        {"tipo": "retangulo", "larg": 340, "alt": 3, "cor": MARROM, "y": 660,
         "escalaX": kf(0, [[62.9, 0], [63.6, 1, "inOutCubic"]]), "inicio": 62.8},
        serifa("E VOCÊ?", 63.2, y=520, tam=190, esp=4),
        serifa("já reparou nos padrões\nque te cercam todo dia?", 64.6, y=352,
               tam=58, fonte=GARAMOND, ital=True, cor=MARROM, larg=0.82),
        serifa("perceber é um trabalho", 63.9, y=-452, tam=76, fonte=GARAMOND,
               peso=700, esp=4, cor=MARROM, ate=69.3, _halo=False),
    ]
    # ── rotulos acrescentados: a folha estava muda em trechos longos ─────
    cs += [
        rotulo("a malha que o cérebro fecha", 10.6, x=0, y=845,
               tam=38, larg=0.86, ate=15.0),
        serifa("SENSORIAL", 22.6, y=-380, tam=58, fonte=GARAMOND, peso=700,
               esp=14, cor=CINZA, ate=26.6),
        rotulo("perceber · analisar", 33.6, x=0, y=-680, tam=42,
               larg=0.8, ate=36.0),
        rotulo("a agulha que se adianta", 43.4, x=0, y=-640,
               tam=36, larg=0.84, ate=48.3),
        rotulo("os dois lados da mesma leitura", 50.4, x=0, y=690,
               tam=38, larg=0.86, ate=62.6),
        serifa("de um lado ao outro", 61.0, y=470, tam=48, fonte=GARAMOND,
               ital=True, cor=CINZA, ate=62.6),
    ]
    # ═══ figuras novas — a folha tem que ACONTECER, nao so acumular ══════
    cs += [
        # (cena 6) janela de medida percorrendo a folha: instrumento, nao régua
        {"tipo": "retangulo", "larg": 300, "alt": 300, "contorno": VERMELHO,
         "contorno_larg": 1.8, "x": kf(0, [[31.6, -230], [35.0, 210, "inOutCubic"]]),
         "y": kf(0, [[31.6, -420], [35.0, 260, "inOutCubic"]]),
         **vive(31.6, 35.6, 0.4)},
        {"tipo": "linha", "de": [-38, 0], "para": [38, 0],
         "contorno": VERMELHO, "contorno_larg": 1.4,
         "x": kf(0, [[31.6, -230], [35.0, 210, "inOutCubic"]]),
         "y": kf(0, [[31.6, -420], [35.0, 260, "inOutCubic"]]),
         **vive(31.6, 35.6, 0.4)},
        {"tipo": "linha", "de": [0, -38], "para": [0, 38],
         "contorno": VERMELHO, "contorno_larg": 1.4,
         "x": kf(0, [[31.6, -230], [35.0, 210, "inOutCubic"]]),
         "y": kf(0, [[31.6, -420], [35.0, 260, "inOutCubic"]]),
         **vive(31.6, 35.6, 0.4)},

        # (cena 7) o trecho pessoal ganha figura propria: uma espiral aberta,
        # desenhada a mao livre, sem grade — e o unico gesto nao-geometrico
        {"tipo": "path", "centrar": False, "x": CX, "y": CY + 40,
         "d": "M0,0 C40,-40 100,-10 100,50 C100,130 10,160 -70,140 "
              "C-170,116 -215,10 -180,-90 C-140,-205 -10,-260 110,-220",
         "contorno": VERMELHO, "contorno_larg": 2.6,
         "traco": desenha(36.2, 1.5), **vive(36.2, 44.0, 0.2)},

        # (cena 11) fecho: os aneis se re-desenham sozinhos, mais leves,
        # e a folha termina com a mesma figura do comeco em outra escala
        anel(180, 63.4, larg=1.4, cor=MARROM, dur=1.4, **vive(63.4, 69.5, 0.3)),
        anel(300, 64.2, larg=1.1, cor=MARROM, dur=1.6, **vive(64.2, 69.5, 0.3)),
        anel(420, 65.0, larg=0.9, cor=MARROM, dur=1.8, **vive(65.0, 69.5, 0.3)),
        {"tipo": "elipse", "raio": 5, "cor": MARROM, "x": CX, "y": CY,
         "repetir": {"cols": 5, "linhas": 5, "espX": 150, "espY": 150,
                     "atraso": 0.06, "ordem": "centro"},
         "escala": kf(0, [[65.4, 0], [66.2, 1, "inOutCubic"]]),
         **vive(65.4, 69.5, 0.6, 0.7)},
    ]
    # ── tarja de papel nas janelas de imagem ─────────────────────────────
    # O video original TEM LEGENDA QUEIMADA (ela editou no Premiere com o
    # texto embutido), entao usar a imagem dela traz a legenda junto. Medido:
    # a faixa fica em y 1330–1510 da tela, que aqui e y ≈ -460.
    #
    # Cobrir com uma tarja de papel impresso nao e remendo — e a solucao na
    # propria linguagem da peca: numa prancha, legenda de figura vem em faixa
    # reservada. O defeito virou o lugar certo do rotulo.
    for (ja, jb) in JANELAS:
        cs += [
            {"tipo": "retangulo", "larg": W - 116, "alt": 186, "raio": 4,
             "cor": PAPEL_CLARO, **vive(ja + 0.15, jb - 0.1, 0.5, 0.97, 0.5),
             "y": -460},
            {"tipo": "linha", "de": [-(W - 116) / 2, 0], "para": [(W - 116) / 2, 0],
             "y": -370, "contorno": MARROM, "contorno_larg": 1.2,
             **vive(ja + 0.2, jb - 0.1, 0.4, 0.8, 0.5)},
            {"tipo": "linha", "de": [-(W - 116) / 2, 0], "para": [(W - 116) / 2, 0],
             "y": -552, "contorno": MARROM, "contorno_larg": 1.2,
             **vive(ja + 0.2, jb - 0.1, 0.4, 0.8, 0.5)},
        ]
    return cs


# ═══════════════════════════════════════════════════════════════════════════
def _halo(c: dict) -> dict | None:
    """Área de papel limpa atrás do rótulo.

    Numa prancha gravada o texto nao e impresso EM CIMA do desenho — o gravador
    deixa a regiao em branco e escreve ali. Sem isso as linhas do diagrama
    cruzam as letras e o titulo some no meio da malha, que foi exatamente o que
    apareceu no Klipe.

    A caixa e estimada pelo tamanho da fonte (nao medida): o halo e borrado e
    generoso, entao erro de 10% nao aparece — e medir aqui exigiria montar o
    TextBlock fora da cena.
    """
    if c.get("tipo") != "texto" or not c.pop("_halo", True):
        return None
    linhas = str(c.get("texto", "")).split("\n")
    tam = float(c.get("tamanho", 60))
    larg = max(len(l) for l in linhas) * tam * 0.52 + tam * 1.1
    alt = len(linhas) * tam * 1.18 + tam * 0.55
    h = {
        "tipo": "retangulo",
        "larg": min(larg, W - 150), "alt": alt, "raio": tam * 0.4,
        "cor": PAPEL_CLARO, "blur": tam * 0.75,
        "x": c.get("x", 0), "y": c.get("y", 0),
        "opacidade": c["opacidade"],
    }
    for k in ("inicio", "fim"):
        if k in c:
            h[k] = c[k]
    return h


def ordenar(cs: list) -> list:
    """Desenho embaixo, halo, texto por cima.

    Z-order e independente do tempo aqui: toda camada carrega `inicio`/`fim`,
    entao reordenar a lista muda so quem cobre quem. O texto TEM que ser o
    ultimo — foi o pedido dela ("os titulos tem que vir para frente").
    """
    graficos = [c for c in cs if c.get("tipo") != "texto"]
    textos = [c for c in cs if c.get("tipo") == "texto"]
    halos = [h for h in (_halo(c) for c in textos) if h]
    return graficos + halos + textos


def spec() -> dict:
    return {"duracao": DUR, "camadas": ordenar(camadas())}


# ═══════════════════════════════════════════════════════════════════════════
def _render(cena: Cena, saida: Path, t_ini: float, t_fim: float,
            audio: Path | None = None, ss: float | None = None) -> Path:
    """Renderiza a janela [t_ini, t_fim) da folha num mp4."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    n = int(round((t_fim - t_ini) * FPS))
    fundo = RAIZ / "public" / "projects" / "eli-premiere" / "video.mp4"
    cmd = [FFMPEG, "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    if OVERLAY:
        # CAMADA DE EFEITO, nao video pronto. Sai no formato lado-a-lado
        # (cor | alpha) que os titulos ja usam — o ffmpeg aqui NAO consegue
        # gravar alpha em WebM/VP9 (escreve alpha_mode=1 mas entrega yuv420p,
        # o alpha some calado), entao alpha vira meia imagem em tons de cinza
        # e o shader do player remonta.
        #
        # `format=rgba` antes do `split` e obrigatorio: sem ele o
        # `alphaextract` falha com "Requested planes not available".
        cmd += ["-filter_complex",
                "[0:v]format=rgba,split=2[c][a];"
                "[c]format=yuv420p[cc];[a]alphaextract,format=yuv420p[aa];"
                "[cc][aa]hstack=inputs=2[v]",
                "-map", "[v]", "-an"]
    elif fundo.exists():
        # A prancha sai com ALPHA e a imagem dela entra por baixo. Nas janelas
        # sem papel o fundo aparece; no resto o papel e opaco e cobre tudo —
        # a mesma passada serve as duas metades, sem cortar e colar depois.
        #
        # A cor dela e puxada pro tom da folha (dessatura + esquenta). Sem isso
        # a troca de superficie le como dois videos emendados, nao como uma
        # peca que muda de suporte.
        cmd += ["-i", str(fundo)]
        cmd += ["-filter_complex",
                "[1:v]scale=%d:%d:force_original_aspect_ratio=increase,"
                "crop=%d:%d,eq=saturation=0.30:contrast=1.10:brightness=0.012:gamma=1.04,"
                "colorbalance=rs=0.16:gs=0.04:bs=-0.18,setpts=PTS-STARTPTS[bg];"
                "[bg][0:v]overlay=0:0:format=auto[v]" % (W, H, W, H),
                "-map", "[v]", "-map", "1:a"]
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    elif audio:
        cmd += ["-ss", f"{ss or 0:.3f}", "-i", str(audio),
                "-c:a", "aac", "-b:a", "192k", "-shortest"]
    #  NAO e detalhe: sem ele o moov fica no fim do arquivo e o
    # browser precisa baixar os 33 MB antes do primeiro frame — no Klipe isso
    # aparece como "preview falhou", nao como lentidao.
    cmd += ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(saida)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    surf = skia.Surface(W, H)
    canvas = surf.getCanvas()
    buf = np.empty((H, W, 4), dtype=np.uint8)
    # RGBA explicito: `tobytes()` cru devolveria o BGRA nativo do Windows
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType,
                               skia.kPremul_AlphaType)
    sig_ant, bytes_ant, reus = None, None, 0
    for f in range(n):
        t = t_ini + f / FPS
        sig = cena.assinatura(t)
        if sig == sig_ant and bytes_ant is not None:
            p.stdin.write(bytes_ant)
            reus += 1
        else:
            # TRANSPARENTE, nao preto: o alpha e o que deixa a imagem dela
            # aparecer nas janelas sem papel
            canvas.clear(skia.Color4f(0, 0, 0, 0))
            cena.desenhar(canvas, t)
            surf.readPixels(info, buf, W * 4, 0, 0)
            bytes_ant = buf.tobytes()
            p.stdin.write(bytes_ant)
            sig_ant = sig
    p.stdin.close()
    p.wait()
    return saida


def main() -> int:
    s = s_spec = spec()
    erros = validar(s)
    if erros:
        print("cena invalida:")
        for e in erros:
            print("  -", e)
        return 1
    print(f"{len(s['camadas'])} camadas, {DUR:.2f}s")
    cena = Cena(s, W, H, FPS)

    if "--stills" in sys.argv:
        out = RAIZ / "output" / "prancha_stills"
        out.mkdir(parents=True, exist_ok=True)
        for t in [2.5, 5.0, 8.5, 13.5, 18.0, 21.0, 27.0, 30.0, 34.0,
                  37.5, 43.0, 47.5, 53.0, 60.0, 65.0, 69.0]:
            sf = skia.Surface(W, H)
            with sf as c:
                c.clear(skia.Color4f(0, 0, 0, 1))
                cena.desenhar(c, t)
            sf.makeImageSnapshot().save(str(out / f"t{t:05.1f}.png"))
        print(f"stills -> {out}")
        return 0

    t0 = time.time()
    PROJ.mkdir(parents=True, exist_ok=True)
    if "--blocos" in sys.argv:
        import json as _j
        cenas = RAIZ / "public" / "cenas"; cenas.mkdir(parents=True, exist_ok=True)
        (cenas / "prancha.json").write_text(
            _j.dumps(s_spec, ensure_ascii=False, indent=1), encoding="utf-8")
        for nome, a, b in BLOCOS:
            alvo = PROJ / f"bloco_{nome}.mp4"
            _render(cena, alvo, a, b)
            print(f"  {nome:<12} {a:6.2f}–{b:5.2f}  {alvo.stat().st_size/1e6:.1f} MB")
        print(f"{len(BLOCOS)} blocos em {time.time()-t0:.1f}s")
        return 0
    # A cena vai pra arquivo proprio. O mp4 e CACHE — descartavel, refazivel;
    # a cena e a fonte, e e ela que fica pra editar e reusar noutro projeto.
    # Guardar aqui em vez de dentro do edit_config tambem evita inchar o
    # projeto: sao ~200 camadas de JSON.
    import json as _json
    cenas = RAIZ / "public" / "cenas"
    cenas.mkdir(parents=True, exist_ok=True)
    (cenas / "prancha.json").write_text(
        _json.dumps(s_spec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cena salva -> {cenas / 'prancha.json'}")
    alvo = PROJ / ("prancha_overlay.mp4" if OVERLAY else "prancha.mp4")
    _render(cena, alvo, 0.0, DUR)
    print(f"pronto em {time.time()-t0:.1f}s -> {alvo} "
          f"({alvo.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
