# -*- coding: utf-8 -*-
"""
montar_padroes.py — "PADRÕES": o video da Dra. Eli refeito SEM video.

Ela pediu pra tirar a imagem e deixar so motion, partindo da transcricao. O
assunto ajuda: o video inteiro fala de reconhecimento de PADRAO, entao a peca
pode ser literal — a grade que se forma, a irregularidade que salta, a previsao
que se adianta. A imagem nao esta faltando; ela virou o argumento.

Tudo aqui e cena declarativa (`motioncore.cena`). Nao ha uma linha de Skia
neste arquivo — se houvesse, seria sinal de que o DSL nao aguentou o trabalho.

    python -m motioncore.montar_padroes            # renderiza e abre
    python -m motioncore.montar_padroes --stills   # so as provas visuais
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from .cena import Cena, validar

RAIZ = Path(__file__).resolve().parent.parent
PROJ = RAIZ / "public" / "projects" / "eli-premiere"
SAIDA = RAIZ / "output" / "padroes.mp4"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

W, H, FPS = 1080, 1920, 30
DUR = 69.7527
N_FRAMES = int(round(DUR * FPS))

# ── paleta ───────────────────────────────────────────────────────────────
FUNDO = "#05070E"
CIANO = "#5FD3F3"
AZUL = "#2E5BFF"
AMBAR = "#FFB020"
BRANCO = "#F2F5FA"
CINZA = "#4A5468"
CINZA_CLARO = "#8B97AC"

TIT = "Gilroy"          # ExtraBold nos titulos
CORPO = "Montserrat"
CONDENSADA = "Bebas Neue"

MARGEM = 90             # nada de texto encosta na borda


# ── helpers de tempo ─────────────────────────────────────────────────────
def kf(base: float, pares: list) -> list:
    """Keyframes relativos ao inicio da cena viram absolutos.

    Escrever [[0, 0], [0.4, 1]] e ler "0,4s depois que a cena comeca" — sem
    isso cada cena carregaria o proprio offset na mao e um ajuste de tempo
    viraria caca ao numero magico.
    """
    return [[base + p[0]] + list(p[1:]) for p in pares]


def vida(t0: float, t1: float, entra: float = 0.35, sai: float = 0.4,
         pico: float = 1.0) -> dict:
    """Janela de vida + fade de entrada e saida — o basico de toda camada."""
    return {
        "inicio": t0 - 0.05,
        "fim": t1 + 0.05,
        "opacidade": [[t0, 0], [t0 + entra, pico, "outCubic"],
                      [t1 - sai, pico], [t1, 0, "inCubic"]],
    }


def sobe(t0: float, de: float = 46, dur: float = 0.5) -> list:
    """Entrada padrao de texto: sobe pouco, para firme. Sem overshoot."""
    return [[t0, de], [t0 + dur, 0, "outCubic"]]


def titulo(txt: str, t0: float, t1: float, y: float = 0, tam: float = 120,
           cor: str = BRANCO, fonte: str = TIT, peso: int = 800,
           esp: float = -1.0, larg: float = 0.82, **extra) -> dict:
    c = {
        "tipo": "texto", "texto": txt, "fonte": fonte, "peso": peso,
        "tamanho": tam, "cor": cor, "espacamento": esp,
        "largura_max": W * larg, "entrelinha": 1.08,
        "y": [[t0, y + 46], [t0 + 0.5, y, "outCubic"]],
        **vida(t0, t1),
    }
    c.update(extra)
    return c


def legenda(txt: str, t0: float, t1: float, y: float, tam: float = 40,
            cor: str = CINZA_CLARO, esp: float = 4.0, larg: float = 0.78,
            **extra) -> dict:
    c = {
        "tipo": "texto", "texto": txt, "fonte": CORPO, "peso": 500,
        "tamanho": tam, "cor": cor, "espacamento": esp,
        "largura_max": W * larg, "entrelinha": 1.35, "y": y,
        **vida(t0, t1, 0.4, 0.35),
    }
    c.update(extra)
    return c


def arco(raio: float, de: float, varre: float, cor: str, larg: float,
         t0: float, t1: float, desenha: float = 0.8, y: float = 0, **extra) -> dict:
    """Arco que se DESENHA. `traco` progressivo e o gesto-assinatura da peca."""
    c = {
        "tipo": "elipse", "raio": raio, "de_grau": de, "varre_grau": varre,
        "contorno": cor, "contorno_larg": larg, "y": y,
        "traco": [[t0, 0], [t0 + desenha, 1, "inOutCubic"]],
        **vida(t0, t1, 0.15, 0.35),
    }
    c.update(extra)
    return c


# ═══════════════════════════════════════════════════════════════════════════
# as 11 cenas, coladas na fala
# ═══════════════════════════════════════════════════════════════════════════
def cena_01(t0=0.0, t1=5.60) -> list:
    """"Ja parou para pensar na incrivel capacidade de pessoas autistas
    de entender padroes?"  — o ruido vira grade."""
    return [
        # a grade se forma irradiando do centro: e a tese da peca em 1 segundo
        {"tipo": "elipse", "raio": 7, "cor": CIANO, "y": -60,
         "repetir": {"cols": 9, "linhas": 13, "espX": 108, "espY": 108,
                     "atraso": 0.022, "ordem": "centro"},
         "escala": kf(t0, [[0.15, 0], [0.75, 1, "outCubic"]]),
         "opacidade": kf(t0, [[0.15, 0], [0.6, 0.55]]),
         "inicio": t0, "fim": t1 + 0.1},
        # UM ponto e ambar — quem ve o padrao
        {"tipo": "elipse", "raio": 13, "cor": AMBAR, "x": 0, "y": -60,
         "escala": kf(t0, [[1.5, 0], [2.1, 1, "outBack"]]),
         **vida(t0 + 1.5, t1, 0.5, 0.4)},
        titulo("JÁ PAROU\nPRA PENSAR?", t0 + 0.6, t0 + 3.0, y=560, tam=104),
        titulo("PADRÕES", t0 + 3.0, t1, y=560, tam=150, cor=CIANO, esp=6),
        legenda("a capacidade de enxergar\no que ninguém vê", t0 + 3.3, t1, y=-620),
    ]


def cena_02(t0=5.98, t1=8.82) -> list:
    """"E como se a gente tivesse um sexto sentido." — cinco tracos e o sexto."""
    cs = []
    for i in range(6):
        sexto = i == 5
        cs.append({
            "tipo": "retangulo", "larg": 26, "alt": 240, "raio": 13,
            "cor": AMBAR if sexto else CINZA,
            "x": (i - 2.5) * 92, "y": 120,
            "escalaY": kf(t0, [[0.15 + i * 0.09, 0],
                               [0.5 + i * 0.09, 1, "outCubic"]]),
            **vida(t0, t1, 0.2, 0.3),
        })
    cs.append({  # halo do sexto
        "tipo": "elipse", "raio": 90, "cor": AMBAR, "x": 2.5 * 92, "y": 120,
        "blur": 120,
        "opacidade": kf(t0, [[0.7, 0], [1.2, 0.35], [2.3, 0.15]]),
        "inicio": t0, "fim": t1,
    })
    cs.append(titulo("SEXTO\nSENTIDO", t0 + 0.5, t1, y=-330, tam=126, cor=BRANCO))
    return cs


def cena_03(t0=8.94, t1=14.82) -> list:
    """"O nosso cerebro tem um poder extraordinario na criacao de padroes."
    — nos que se ligam."""
    # Rede DELIBERADA, nao aleatoria. A primeira versao sorteava 11 pontos e
    # ligava em cadeia: virou rabisco, e rabisco nao le como "criacao de
    # padrao" — le como falta de padrao, o oposto do que ela esta dizendo.
    # Duas coroas + centro, ligadas por raio e por circunferencia.
    centro = (0.0, 0.0)
    anel1 = [(math.cos(math.radians(a)) * 190, math.sin(math.radians(a)) * 190)
             for a in range(-90, 270, 60)]
    anel2 = [(math.cos(math.radians(a)) * 400, math.sin(math.radians(a)) * 400)
             for a in range(-60, 300, 60)]
    arestas = ([(centro, p) for p in anel1]
               + [(anel1[i], anel1[(i + 1) % 6]) for i in range(6)]
               + [(anel1[i], anel2[i]) for i in range(6)]
               + [(anel1[(i + 1) % 6], anel2[i]) for i in range(6)]
               + [(anel2[i], anel2[(i + 1) % 6]) for i in range(6)])
    cs = []
    for i, ((x0, y0), (x1, y1)) in enumerate(arestas):
        cs.append({
            "tipo": "linha", "de": [x0, y0], "para": [x1, y1], "y": -80,
            "contorno": AZUL, "contorno_larg": 2.5,
            "traco": kf(t0, [[0.4 + i * 0.055, 0],
                             [0.85 + i * 0.055, 1, "outCubic"]]),
            **vida(t0, t1, 0.1, 0.4),
        })
    for i, (x, y) in enumerate([centro] + anel1 + anel2):
        cs.append({
            "tipo": "elipse", "raio": 13 if i == 0 else 9,
            "cor": CIANO if i == 0 else BRANCO, "x": x, "y": y - 80,
            "escala": kf(t0, [[0.3 + i * 0.07, 0], [0.7 + i * 0.07, 1, "outBack"]]),
            **vida(t0, t1, 0.1, 0.4),
        })
    cs.append(titulo("PODER\nEXTRAORDINÁRIO", t0 + 2.6, t1, y=-640, tam=96))
    cs.append(legenda("o cérebro não encontra padrões.\nele os CRIA.",
                      t0 + 3.6, t1, y=-840, tam=36))
    return cs


def cena_04(t0=14.82, t1=21.46) -> list:
    """"A regiao do cerebro que faz isso e o cortex temporal."
    — o diagrama, com um setor aceso."""
    cs = [
        arco(360, 0, 360, CINZA_CLARO, 2.5, t0 + 0.1, t1, 1.1, y=-40),
        arco(280, 0, 360, CINZA, 2, t0 + 0.35, t1, 1.1, y=-40),
        arco(200, 0, 360, CINZA, 2, t0 + 0.6, t1, 1.1, y=-40),
        arco(120, 0, 360, CINZA, 1.5, t0 + 0.85, t1, 1.1, y=-40),
        # o setor temporal: tres arcos concentricos acesos, nao um traco solto —
        # um arco sozinho lia como spinner de carregamento
        arco(360, 150, 78, AMBAR, 5, t0 + 1.6, t1, 0.9, y=-40),
        arco(320, 150, 78, AMBAR, 22, t0 + 1.75, t1, 0.9, y=-40),
        arco(280, 150, 78, AMBAR, 5, t0 + 1.9, t1, 0.9, y=-40),
        {"tipo": "elipse", "raio": 150, "x": -250, "y": 60, "cor": AMBAR,
         "blur": 190, "opacidade": kf(t0, [[1.8, 0], [2.6, 0.3]]),
         "inicio": t0, "fim": t1},
        # Chamada em cotovelo, saindo DO setor. A primeira versao era uma
        # diagonal solta que lia como risco na tela, nao como linha-guia — o
        # que faz a diferenca e ela nascer colada no que aponta.
        {"tipo": "path", "d": "M0,0 L-150,-150 L-330,-150", "y": 200, "x": -230,
         "contorno": AMBAR, "contorno_larg": 2, "centrar": False,
         "traco": kf(t0, [[2.5, 0], [3.1, 1, "outCubic"]]),
         **vida(t0 + 2.5, t1, 0.1, 0.3)},
        {"tipo": "elipse", "raio": 7, "cor": AMBAR, "x": -230, "y": 200,
         "escala": kf(t0, [[2.4, 0], [2.8, 1, "outBack"]]),
         **vida(t0 + 2.4, t1, 0.2, 0.3)},
        titulo("CÓRTEX\nTEMPORAL", t0 + 2.9, t1, y=560, tam=110, cor=AMBAR),
        legenda("a região que identifica o padrão", t0 + 4.0, t1, y=-700),
    ]
    for i in range(24):    # marcas de escala na borda
        cs.append({
            "tipo": "retangulo", "larg": 3, "alt": 18, "cor": CINZA,
            "x": math.cos(math.radians(i * 15)) * 400,
            "y": -40 + math.sin(math.radians(i * 15)) * 400,
            "rotacao": -i * 15 + 90,
            "opacidade": kf(t0, [[0.8 + i * 0.02, 0], [1.1 + i * 0.02, 0.7]]),
            "inicio": t0, "fim": t1,
        })
    return cs


def cena_05(t0=21.46, t1=30.96) -> list:
    """"Processamento de informacoes sensoriais e identificacao de
    irregularidades." — o intruso na fileira."""
    cs = [
        # a grade regular
        {"tipo": "retangulo", "larg": 44, "alt": 44, "raio": 6, "cor": CINZA,
         "y": -80,
         "repetir": {"cols": 7, "linhas": 9, "espX": 130, "espY": 130,
                     "atraso": 0.03, "ordem": "linha"},
         "escala": kf(t0, [[0.3, 0], [0.75, 1, "outCubic"]]),
         "opacidade": kf(t0, [[0.3, 0], [0.7, 0.85]]),
         "rotacao": kf(t0, [[0.3, -25], [0.9, 0, "outCubic"]]),
         "inicio": t0, "fim": t1},
        # a irregularidade: girada, ambar, maior
        {"tipo": "retangulo", "larg": 62, "alt": 62, "raio": 8, "cor": AMBAR,
         "x": 130, "y": -80 + 130,
         "rotacao": kf(t0, [[3.2, 0], [4.0, 45, "outBack"]]),
         "escala": kf(t0, [[3.2, 1], [4.0, 1.35, "outBack"]]),
         **vida(t0 + 3.0, t1, 0.3, 0.4)},
        # o anel que a acha
        arco(120, 0, 360, AMBAR, 4, t0 + 4.0, t1, 0.7, y=-80 + 130, x=130),
        titulo("IRREGULARIDADES", t0 + 5.0, t1, y=640, tam=84, cor=AMBAR, esp=2),
        legenda("o que está fora do padrão\nsalta aos olhos", t0 + 5.6, t1, y=-760),
    ]
    return cs


def cena_06(t0=31.14, t1=35.70) -> list:
    """"Nos ajuda a perceber e analisar padroes no ambiente." — a varredura."""
    return [
        {"tipo": "elipse", "raio": 6, "cor": CIANO, "y": -40,
         "repetir": {"cols": 8, "linhas": 11, "espX": 118, "espY": 118,
                     "atraso": 0.014, "ordem": "linha"},
         "escala": kf(t0, [[0.1, 0], [0.5, 1, "outCubic"]]),
         "opacidade": kf(t0, [[0.1, 0], [0.5, 0.5]]),
         "inicio": t0, "fim": t1},
        # a linha de varredura atravessa a grade de cima a baixo
        {"tipo": "retangulo", "larg": W, "alt": 3, "cor": CIANO,
         "y": kf(t0, [[0.6, 700], [3.4, -700, "inOutCubic"]]),
         **vida(t0 + 0.6, t1, 0.25, 0.3)},
        {"tipo": "retangulo", "larg": W, "alt": 160, "cor": CIANO, "blur": 160,
         "y": kf(t0, [[0.6, 700], [3.4, -700, "inOutCubic"]]),
         **vida(t0 + 0.6, t1, 0.25, 0.3, pico=0.18)},
        titulo("NO AMBIENTE", t0 + 1.4, t1, y=700, tam=92, esp=3),
        legenda("perceber · analisar · antecipar", t0 + 2.2, t1, y=-800, tam=34),
    ]


def cena_07(t0=35.96, t1=38.16) -> list:
    """"Eu, por exemplo, sou otima em padroes." — vira pessoal."""
    # `largura_max` menor que a linha mais longa QUEBRA a palavra e o bloco
    # sai da tela: foi assim que "EM PADRÕES" virou "DRÕES" no primeiro teste.
    # Com alinha=left o bloco continua CENTRADO em `x` — a borda esquerda cai
    # em x - larg/2, e e ela que tem que bater com a barra ambar.
    larg_cx = W * 0.80
    barra_x = -larg_cx / 2 - 40
    return [
        {"tipo": "retangulo", "larg": 8, "alt": 330, "cor": AMBAR, "x": barra_x,
         "escalaY": kf(t0, [[0.1, 0], [0.5, 1, "outCubic"]]),
         **vida(t0, t1, 0.15, 0.25)},
        titulo("SOU ÓTIMA\nEM PADRÕES", t0 + 0.2, t1, y=0, tam=112,
               alinha="left", larg=0.80, x=0),
    ]


def cena_08(t0=38.30, t1=44.06) -> list:
    """"As vezes eu antecipo as coisas que irao acontecer." — a previsao."""
    cs = [
        # a linha do tempo
        {"tipo": "linha", "de": [-420, 0], "para": [420, 0], "y": -60,
         "contorno": CINZA, "contorno_larg": 3,
         "traco": kf(t0, [[0.2, 0], [0.9, 1, "outCubic"]]),
         **vida(t0, t1, 0.15, 0.35)},
        # marcos do passado
        {"tipo": "elipse", "raio": 10, "cor": CINZA_CLARO, "x": -300, "y": -60,
         "repetir": {"cols": 5, "linhas": 1, "espX": 150, "atraso": 0.12},
         "escala": kf(t0, [[0.7, 0], [1.0, 1, "outBack"]]),
         "inicio": t0, "fim": t1},
        # o salto: o marcador se adianta
        {"tipo": "elipse", "raio": 20, "cor": AMBAR, "y": -60,
         "x": kf(t0, [[1.4, -300], [2.3, 60, "inOutCubic"],
                      [3.0, 60], [3.6, 420, "inOutCubic"]]),
         **vida(t0 + 1.3, t1, 0.25, 0.35)},
        {"tipo": "elipse", "raio": 62, "cor": AMBAR, "blur": 80, "y": -60,
         "x": kf(t0, [[1.4, -300], [2.3, 60, "inOutCubic"],
                      [3.0, 60], [3.6, 420, "inOutCubic"]]),
         **vida(t0 + 1.3, t1, 0.25, 0.35, pico=0.4)},
        # o futuro, tracejado
        {"tipo": "retangulo", "larg": 26, "alt": 3, "cor": AMBAR, "y": -60,
         "x": 120,
         "repetir": {"cols": 7, "linhas": 1, "espX": 48, "atraso": 0.05},
         "escalaX": kf(t0, [[3.4, 0], [3.8, 1, "outCubic"]]),
         "inicio": t0, "fim": t1},
        titulo("EU ANTECIPO", t0 + 0.5, t1, y=560, tam=118, cor=BRANCO),
        legenda("no trabalho · com a família", t0 + 2.6, t1, y=-620, tam=36),
    ]
    return cs


def cena_09(t0=44.06, t1=48.46) -> list:
    """"...pelo simples fato de observacoes de padroes." — tudo converge."""
    cs = []
    for i in range(14):
        a = math.radians(i * (360 / 14) - 90)
        cs.append({
            "tipo": "linha",
            "de": [math.cos(a) * 520, math.sin(a) * 520],
            "para": [math.cos(a) * 90, math.sin(a) * 90],
            "y": -60, "contorno": AZUL, "contorno_larg": 2,
            "traco": kf(t0, [[0.3 + i * 0.05, 0], [1.1 + i * 0.05, 1, "inOutCubic"]]),
            **vida(t0, t1, 0.15, 0.4),
        })
    cs.append({
        "tipo": "elipse", "raio": 44, "cor": CIANO, "y": -60,
        "escala": kf(t0, [[1.7, 0], [2.3, 1, "outBack"]]),
        **vida(t0 + 1.6, t1, 0.3, 0.4),
    })
    cs.append(titulo("OBSERVAÇÃO", t0 + 1.0, t1, y=680, tam=100, esp=4))
    return cs


def cena_10(t0=48.46, t1=62.30) -> list:
    """"A dualidade de nao captar indiretas, mas conseguir prever eventos
    futuros — de inocente para sensitiva em segundos."

    A cena mais longa (13,8s): sem estrutura interna ela morre. Divide em
    tres tempos — o lado frio, o lado quente, e a virada entre os dois.
    """
    meio = t0 + 6.4
    cs = [
        {"tipo": "retangulo", "larg": 2, "alt": 1250, "cor": CINZA_CLARO,
         "escalaY": kf(t0, [[0.3, 0], [1.0, 1, "inOutCubic"]]),
         **vida(t0, t1, 0.2, 0.5, pico=0.5)},
        # ── esquerda: o que nao capta. Grade FROUXA e fria ──
        {"tipo": "elipse", "raio": 7, "cor": CINZA_CLARO, "x": -262, "y": 120,
         "repetir": {"cols": 5, "linhas": 9, "espX": 96, "espY": 96,
                     "atraso": 0.025, "ordem": "linha"},
         "opacidade": kf(t0, [[0.6, 0], [1.3, 0.5]]),
         "inicio": t0, "fim": t1},
        titulo("INOCENTE", t0 + 1.2, t1, y=700, tam=72, cor=CINZA_CLARO,
               x=-262, larg=0.42),
        legenda("não capta\na indireta", t0 + 2.0, t1, y=560, tam=30,
                x=-262, cor=CINZA_CLARO, larg=0.4),
        # ── direita: o que preve. A mesma grade, mas ACESA e em onda ──
        {"tipo": "elipse", "raio": 7, "cor": AMBAR, "x": 262, "y": 120,
         "repetir": {"cols": 5, "linhas": 9, "espX": 96, "espY": 96,
                     "atraso": 0.045, "ordem": "centro"},
         "escala": kf(t0, [[6.4, 0.5], [7.8, 1.6, "outCubic"]]),
         "opacidade": kf(t0, [[6.4, 0], [7.4, 0.95]]),
         "inicio": t0, "fim": t1},
        titulo("SENSITIVA", meio, t1, y=700, tam=72, cor=AMBAR,
               x=262, larg=0.42),
        legenda("prevê\no que vem", meio + 0.8, t1, y=560, tam=30, x=262,
                cor=AMBAR, larg=0.4),
        # ── a virada: uma seta atravessa o divisor, de frio pra quente ──
        {"tipo": "linha", "de": [-200, 0], "para": [200, 0], "y": -380,
         "contorno": AMBAR, "contorno_larg": 5,
         "traco": kf(t0, [[6.0, 0], [7.2, 1, "inOutCubic"]]),
         **vida(t0 + 5.9, t1, 0.2, 0.4)},
        {"tipo": "path", "d": "M-30,-26 L14,0 L-30,26", "y": -380, "x": 190,
         "contorno": AMBAR, "contorno_larg": 5,
         "traco": kf(t0, [[7.0, 0], [7.5, 1, "outCubic"]]),
         **vida(t0 + 6.9, t1, 0.15, 0.4)},
        titulo("EM SEGUNDOS", t0 + 10.2, t1, y=-560, tam=68, cor=BRANCO, esp=8),
        legenda("a dualidade", t0 + 0.4, t1, y=-820, tam=40, cor=CINZA_CLARO,
                esp=14),
    ]
    return cs


def cena_11(t0=62.52, t1=69.40) -> list:
    """"E voce, ja parou para refletir sobre a sua capacidade?"
    — devolve a pergunta, e a grade volta pro comeco."""
    return [
        {"tipo": "elipse", "raio": 7, "cor": CIANO, "y": -60,
         "repetir": {"cols": 9, "linhas": 13, "espX": 108, "espY": 108,
                     "atraso": 0.02, "ordem": "centro"},
         "escala": kf(t0, [[0.2, 0], [0.9, 1, "outCubic"]]),
         "opacidade": kf(t0, [[0.2, 0], [0.8, 0.5], [5.4, 0.5], [6.4, 0]]),
         "inicio": t0, "fim": t1},
        # agora o ponto ambar e o espectador
        {"tipo": "elipse", "raio": 15, "cor": AMBAR, "y": -60,
         "escala": kf(t0, [[1.6, 0], [2.3, 1, "outBack"]]),
         **vida(t0 + 1.6, t1 - 0.6, 0.5, 0.6)},
        titulo("E VOCÊ?", t0 + 0.5, t1, y=620, tam=170, cor=BRANCO, esp=4),
        legenda("já reparou nos padrões\nque te cercam todo dia?",
                t0 + 2.2, t1, y=-660, tam=42, cor=CINZA_CLARO),
    ]


# ═══════════════════════════════════════════════════════════════════════════
def montar() -> dict:
    """A cena completa: fundo + as 11, todas na mesma linha do tempo."""
    camadas = [
        # fundo vivo: o degrade respira devagar, senao 70s de chapado cansa
        {"tipo": "retangulo", "larg": W, "alt": H,
         "cor": {"tipo": "radial", "cores": ["#111A38", FUNDO], "raio": 1150},
         "escala": [[0, 1.0], [35, 1.15, "inOutSine"], [69.75, 1.0, "inOutSine"]]},
    ]
    for f in (cena_01, cena_02, cena_03, cena_04, cena_05, cena_06,
              cena_07, cena_08, cena_09, cena_10, cena_11):
        camadas.extend(f())
    # vinheta por cima de tudo, pra grade nao encostar na borda visualmente
    camadas.append({
        "tipo": "retangulo", "larg": W, "alt": H,
        "cor": {"tipo": "radial", "cores": ["#00000000", "#000000C0"],
                "raio": 1050, "paradas": [0.55, 1.0]},
    })
    return {"duracao": DUR, "camadas": camadas}


# ═══════════════════════════════════════════════════════════════════════════
def _audio() -> Path | None:
    """Audio original do video — a peca e narrada por ela, so a imagem saiu."""
    src = PROJ / "video.mp4"
    if not src.exists():
        return None
    out = RAIZ / "output" / "padroes_audio.m4a"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(src),
                        "-vn", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    return out


def renderizar(cena: Cena, abrir: bool = True) -> Path:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    aud = _audio()
    cmd = [FFMPEG, "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    if aud:
        cmd += ["-i", str(aud), "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19",
            "-pix_fmt", "yuv420p", str(SAIDA)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    surface = skia.Surface(W, H)
    canvas = surface.getCanvas()
    # `makeImageSnapshot().tobytes()` devolve o formato NATIVO da Surface, que
    # no Windows e BGRA — declarar "rgba" no pipe trocou R por B e a peca saiu
    # com o ciano laranja e o fundo marrom. `readPixels` com ImageInfo explicito
    # converte, entao o formato deixa de depender da plataforma.
    buf = np.empty((H, W, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType,
                               skia.kPremul_AlphaType)
    t_ini = time.time()
    # dedup: frame com a mesma assinatura reusa os bytes do anterior
    ultima_sig, ultimos_bytes, reusados = None, None, 0
    for f in range(N_FRAMES):
        t = f / FPS
        sig = cena.assinatura(t)
        if sig == ultima_sig and ultimos_bytes is not None:
            p.stdin.write(ultimos_bytes)
            reusados += 1
        else:
            canvas.clear(skia.Color4f(0, 0, 0, 1))
            cena.desenhar(canvas, t)
            surface.readPixels(info, buf, W * 4, 0, 0)
            ultimos_bytes = buf.tobytes()
            p.stdin.write(ultimos_bytes)
            ultima_sig = sig
        if f % 300 == 0 and f:
            print(f"  frame {f}/{N_FRAMES}  ({reusados} reusados)")
    p.stdin.close()
    p.wait()
    dt = time.time() - t_ini
    mb = SAIDA.stat().st_size / 1e6
    print(f"pronto em {dt:.1f}s -> {SAIDA} ({mb:.1f} MB)")
    print(f"dedup: {reusados}/{N_FRAMES} frames reusados "
          f"({100*reusados/N_FRAMES:.1f}%)")
    if abrir:
        subprocess.run(["cmd", "/c", "start", "", str(SAIDA)], shell=False)
    return SAIDA


def stills(cena: Cena, quando: list[float]):
    out = RAIZ / "output" / "padroes_stills"
    out.mkdir(parents=True, exist_ok=True)
    for t in quando:
        s = skia.Surface(W, H)
        with s as c:
            c.clear(skia.Color4f(0, 0, 0, 1))
            cena.desenhar(c, t)
        s.makeImageSnapshot().save(str(out / f"t{t:05.1f}.png"))
    print(f"{len(quando)} stills -> {out}")


def main() -> int:
    spec = montar()
    # o validar() como critico: erra cedo e com endereco, em vez de desenhar
    # errado e a gente descobrir no video pronto
    erros = validar(spec)
    if erros:
        print("cena invalida:")
        for e in erros:
            print("  -", e)
        return 1
    print(f"{len(spec['camadas'])} camadas, {DUR:.2f}s, {N_FRAMES} frames")
    cena = Cena(spec, W, H, FPS)
    if "--stills" in sys.argv:
        stills(cena, [1.0, 4.0, 7.0, 11.5, 17.5, 20.0, 26.0, 29.0,
                      33.0, 37.0, 41.5, 46.5, 52.0, 58.0, 64.5, 67.5])
        return 0
    renderizar(cena, abrir="--no-open" not in sys.argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
