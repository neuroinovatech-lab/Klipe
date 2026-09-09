# -*- coding: utf-8 -*-
"""
comercial.py — o comercial do Klipe, feito pelo proprio Klipe.

Doze cenas, 42 s, 1920x1080. Toda a linguagem aprendida hoje esta aplicada:
cena curta, `outCubic` para tudo que entra, tres familias de mola, escada de
cascata, ruido em tudo que fica parado, transicao de 20 frames.

E a decisao que mais importa, aprendida da forma mais cara: DENSIDADE E IMAGEM
REAL. As interfaces sao desenhadas em codigo (e o que o material de referencia
faz — so as fotos sao imagens), e as imagens sao frames dos renders que o
proprio Klipe produziu hoje. Nao ha mockup: o que aparece na tela e saida de
verdade da ferramenta.

Cada numero de venda foi MEDIDO nesta sessao, nao inventado:
  32 s de render      medido no demo-completo (70 s de video, 127 MB)
  287 palavras        a transcricao do reel-suporte com tempo por palavra
  18 ferramentas      o que o chat expoe hoje, e o MCP serve identico
  1.456 camadas       o comercial de referencia replicado
  US$ 0,0002          o custo real de uma deteccao de shorts por IA

    python -m motioncore.comercial
    python -m motioncore.comercial --stills
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from .cena import Cena, validar
from .cbv.base import (W, H, FPS, F, LETRA, PALAVRA, BLOCO, TRANSICAO,
                       MOLA_TEXTO, MOLA_DESTAQUE, MOLA_ESTADO,
                       entra, sobe, viva, pulso, titulo, rotulo, card,
                       sombra, brilho, particulas, marca_dagua, grade_fundo,
                       larg_texto, larg_char, BORDA)
from .ffbin import ffmpeg as _ffmpeg
from .gpu import onde, superficie

RAIZ = Path(__file__).resolve().parent.parent
ATIVOS = RAIZ / "public" / "comercial"
SAIDA = RAIZ / "output" / "klipe_comercial.mp4"
FFMPEG = _ffmpeg()

# ── paleta do Klipe: a laranja da marca, sobre quase-preto ───────────────
BG = "#07080C"
BG_CLARO = "#F7F8FA"
TINTA = "#FFFFFF"
TINTA_ESC = "#0A0B0F"
MUDO = "#8B93A7"
MUDO_CLARO = "#5B6474"
LARANJA = "#E8940A"
AZUL = "#3B82F6"
CIANO = "#22D3EE"
VERDE = "#10B981"
VERM = "#F43F5E"


def img(nome: str) -> str:
    return str(ATIVOS / nome)


def existe(nome: str) -> bool:
    return (ATIVOS / nome).exists()


def moldura_video(x: float, y: float, larg: float, alt: float, t: float,
                  arquivo: str | None = None, s: int = 1) -> list[dict]:
    """Um quadro de video com moldura — o gesto que se repete no comercial.

    A sombra e desenhada (tres retangulos com alpha caindo) porque o motor nao
    tem box-shadow multiplo, e sombra unica chapa o card contra o fundo.
    """
    out = sombra(x, y, larg, alt, t, raio=14)
    if arquivo and existe(arquivo):
        out.append({
            "tipo": "imagem", "src": img(arquivo),
            "larg": larg, "alt": alt, "ajuste": "cobrir",
            **viva(x, y, 2, s),
            "opacidade": entra(t + 0.1, 0.4),
            "escala": {"mola": MOLA_ESTADO, "em": t, "de": 0.92, "para": 1.0},
        })
    else:
        out.append(card(x, y, larg, alt, t, "#0F1218", BORDA, 14, s))
    # o contorno por cima, para a imagem nao encostar no fundo
    out.append({
        "tipo": "retangulo", "larg": larg, "alt": alt, "raio": 14,
        "cor": "#00000000", "contorno": "#FFFFFF22", "contorno_larg": 2,
        **viva(x, y, 2, s), "opacidade": entra(t + 0.1, 0.4)})
    return out


def sigla(t0: float, y: float, tam: int = 30) -> list[dict]:
    """KLIPE nao e um nome inventado — e uma sigla, e ela mora embaixo da marca.

    A inicial de cada palavra fica na cor da marca e o resto apagado: quem olha
    um segundo le KLIPE, quem olha tres le a frase inteira. Uma camada por
    palavra, com a escada de BLOCO (5 frames) entre elas.
    """
    palavras = ["Kinetic", "Linking", "Intelligent", "Production", "Engine"]
    gap = 26.0
    largs = [larg_texto(w, tam) for w in palavras]
    total = sum(largs) + gap * (len(palavras) - 1)
    x = -total / 2
    out = []
    for i, (w, lw) in enumerate(zip(palavras, largs)):
        d = t0 + i * BLOCO
        li = larg_char(w[0], tam)
        out.append({
            "tipo": "texto", "texto": w[0], "tamanho": tam, "peso": 900,
            "cor": LARANJA, "x": x + li / 2, "y": y,
            "opacidade": entra(d, 0.28),
            "escala": {"mola": MOLA_TEXTO, "em": d, "de": 0.78, "para": 1.0}})
        resto = w[1:]
        out.append({
            "tipo": "texto", "texto": resto, "tamanho": tam, "peso": 600,
            "cor": MUDO_CLARO, "x": x + li + larg_texto(resto, tam) / 2, "y": y,
            "opacidade": entra(d + 0.08, 0.28)})
        x += lw + gap
    return out


def glifo(qual: str, x: float, y: float, t: float, cor: str) -> list[dict]:
    """Icone de ferramenta desenhado em FORMAS.

    O motor nao tem fonte de icone, e um PNG de icone ficaria mole no tamanho
    que o quadro pede. Desenhado, ele e nitido em qualquer escala — que e
    exatamente o argumento do proprio Klipe.
    """
    op = entra(t + 0.12, 0.25)
    if qual == "midia":                       # duas fitas sobrepostas
        return [
            {"tipo": "retangulo", "larg": 36, "alt": 27, "raio": 4,
             "cor": "#00000000", "contorno": cor, "contorno_larg": 3,
             "x": x - 6, "y": y + 5, "opacidade": op},
            {"tipo": "retangulo", "larg": 36, "alt": 27, "raio": 4,
             "cor": cor, "x": x + 7, "y": y - 6, "opacidade": op}]
    if qual == "audio":                       # tres barras de alturas diferentes
        return [{"tipo": "retangulo", "larg": 7, "alt": h, "raio": 3,
                 "cor": cor, "x": x - 14 + i * 14, "y": y, "opacidade": op}
                for i, h in enumerate((22, 46, 30))]
    if qual == "texto":                       # um T
        return [
            {"tipo": "retangulo", "larg": 46, "alt": 8, "raio": 3, "cor": cor,
             "x": x, "y": y + 17, "opacidade": op},
            {"tipo": "retangulo", "larg": 8, "alt": 44, "raio": 3, "cor": cor,
             "x": x, "y": y - 6, "opacidade": op}]
    if qual == "template":                    # grade 2x2
        return [{"tipo": "retangulo", "larg": 19, "alt": 19, "raio": 4,
                 "cor": cor if (i % 3 == 0) else "#00000000",
                 "contorno": cor, "contorno_larg": 2,
                 "x": x - 11 + (i % 2) * 22, "y": y + 11 - (i // 2) * 22,
                 "opacidade": op} for i in range(4)]
    if qual == "filtros":                     # circulo meio cheio
        return [
            {"tipo": "elipse", "raio": 23, "cor": "#00000000", "contorno": cor,
             "contorno_larg": 3, "x": x, "y": y, "opacidade": op},
            {"tipo": "elipse", "raio": 23, "cor": cor, "x": x, "y": y,
             "de_grau": -90, "varre_grau": 180, "opacidade": op}]
    if qual == "zoom":                        # lupa
        return [
            {"tipo": "elipse", "raio": 19, "cor": "#00000000", "contorno": cor,
             "contorno_larg": 3, "x": x + 4, "y": y + 5, "opacidade": op},
            {"tipo": "retangulo", "larg": 18, "alt": 5, "raio": 3, "cor": cor,
             "x": x - 13, "y": y - 13, "rotacao": 45, "opacidade": op}]
    # formas: triangulo + circulo + quadrado
    return [
        {"tipo": "path", "d": "M 20 0 L 40 34 L 0 34 Z", "cor": cor,
         "x": x - 15, "y": y + 6, "escala": 0.8, "opacidade": op},
        {"tipo": "elipse", "raio": 11, "cor": "#00000000", "contorno": cor,
         "contorno_larg": 3, "x": x + 15, "y": y + 11, "opacidade": op},
        {"tipo": "retangulo", "larg": 20, "alt": 20, "raio": 3,
         "cor": "#00000000", "contorno": cor, "contorno_larg": 3,
         "x": x + 12, "y": y - 15, "opacidade": op}]


# ══ 1 · abertura ══════════════════════════════════════════════════════
def c_abertura(d: float) -> dict:
    return {"duracao": d, "fundo": BG, "camadas": [
        *grade_fundo(96, "#12151C", 0.6),
        brilho(0, 60, 760, LARANJA + "26", 0, 0.5, 3),
        marca_dagua("KLIPE", 520, LARANJA, -8, 0.045, 0),
        *particulas(26, LARANJA, AZUL, 18, 4),
        *titulo("KLIPE", 0.35, 130, 200, TINTA, 900),
        # o filete: o unico pulo da cena
        {"tipo": "retangulo", "larg": 620, "alt": 7, "raio": 4, "cor": LARANJA,
         "y": 10, "opacidade": entra(0.95, 0.2),
         "escalaX": {"mola": MOLA_DESTAQUE, "em": 0.95, "de": 0, "para": 1}},
        # o nome nao e invencao: as cinco iniciais sao uma frase
        *sigla(1.25, -60, 32),
        rotulo("EDITOR DE VIDEO COM MOTOR PROPRIO", 2.05, -180, MUDO, 26),
        rotulo("RODA NO SEU COMPUTADOR", 2.35, -240, MUDO_CLARO, 20),
    ]}


# ══ 2 · o motor ═══════════════════════════════════════════════════════
def c_motor(d: float) -> dict:
    barras = []
    for i in range(9):
        x = -520 + i * 130
        alt = 90 + (i % 4) * 60
        dd = 0.45 + i * BLOCO
        barras += [
            {"tipo": "retangulo", "larg": 74, "alt": alt, "raio": 8,
             "cor": AZUL if i % 2 else CIANO, **viva(x, -200 + alt / 2, 2, 30 + i),
             "opacidade": entra(dd, 0.25),
             "escalaY": {"mola": MOLA_ESTADO, "em": dd, "de": 0.05, "para": 1.0}},
        ]
    return {"duracao": d, "fundo": BG, "camadas": [
        *grade_fundo(96, "#12151C", 0.4),
        marca_dagua("SKIA", 460, AZUL, 6, 0.05, -80),
        brilho(-300, 220, 620, AZUL + "22", 0, 0.45, 7),
        *particulas(20, AZUL, CIANO, 16, 9),
        rotulo("SEM CHROME  ·  SEM NAVEGADOR", 0.15, 400, CIANO, 24),
        *titulo("MotionCore", 0.3, 280, 118, TINTA, 900),
        *barras,
        rotulo("MOTOR DE MOTION GRAPHICS SOBRE SKIA", 1.5, -330, MUDO, 22),
    ]}


# ══ 3 · o render ══════════════════════════════════════════════════════
def c_render(d: float) -> dict:
    return {"duracao": d, "fundo": BG, "camadas": [
        *grade_fundo(96, "#12151C", 0.3),
        brilho(0, 0, 820, VERDE + "1F", 0, 0.5, 11),
        marca_dagua("FAST", 480, VERDE, -10, 0.04, 40),
        *particulas(18, VERDE, CIANO, 14, 13),
        rotulo("VIDEO DE 70 SEGUNDOS", 0.15, 330, MUDO, 24),
        # o numero: familia DESTAQUE, o unico pulo
        {"tipo": "texto", "texto": "32s", "tamanho": 330, "peso": 900,
         "cor": TINTA, **viva(0, 60, 3, 21),
         "opacidade": entra(0.25, 0.22),
         "escala": {"mola": MOLA_DESTAQUE, "em": 0.25, "de": 0.7, "para": 1.0}},
        {"tipo": "retangulo", "larg": 560, "alt": 4, "cor": VERDE, "y": -110,
         "opacidade": entra(0.9, 0.2),
         "escalaX": [[0.9, 0], [1.5, 1, "outCubic"]]},
        rotulo("RENDER NA SUA GPU  ·  NVENC", 1.2, -190, VERDE, 22),
        rotulo("O QUE VOCE VE NO PREVIEW, O RENDER FAZ", 1.6, -260, MUDO_CLARO, 20),
    ]}


# ══ 4 · legenda na fala ═══════════════════════════════════════════════
def c_legenda(d: float) -> dict:
    palavras = ["A", "palavra", "entra", "quando", "e", "dita"]
    out = [
        *grade_fundo(96, "#12151C", 0.3),
        brilho(420, 0, 700, LARANJA + "1A", 0, 0.5, 17),
        marca_dagua("FALA", 440, LARANJA, 8, 0.04, 0),
        *particulas(16, LARANJA, None, 14, 19),
        rotulo("LEGENDA ANCORADA NA FALA", 0.15, 400, LARANJA, 24, -420),
    ]
    # as palavras entrando uma a uma, como no produto
    x = -820
    for i, p in enumerate(palavras):
        w = larg_texto(p, 64)
        dd = 0.4 + i * (5 * PALAVRA)
        out.append({
            "tipo": "texto", "texto": p, "tamanho": 64, "peso": 800,
            "cor": TINTA, "x": x + w / 2, "y": sobe(dd, 210, 22),
            "opacidade": entra(dd, 0.18),
            "escala": {"mola": MOLA_TEXTO, "em": dd, "de": 0.86, "para": 1}})
        x += w + 22
    # a forma de onda embaixo, marcando o tempo de cada palavra
    for i in range(56):
        bx = -820 + i * 30
        alt = 12 + ((i * 37) % 60)
        out.append({
            "tipo": "retangulo", "larg": 8, "alt": alt, "raio": 4,
            "cor": LARANJA if i % 9 < 4 else "#2A2F3A",
            "x": bx, "y": 60,
            "opacidade": entra(0.3 + i * 0.008, 0.2),
            "escalaY": {"mola": MOLA_ESTADO, "em": 0.3 + i * 0.008,
                        "de": 0.1, "para": 1.0}})
    out += [
        rotulo("287 PALAVRAS COM TEMPO PROPRIO", 1.8, -110, MUDO, 22, -420),
        rotulo("WHISPER RODANDO LOCAL", 2.1, -170, MUDO_CLARO, 19, -420),
    ]
    if existe("sincronia.jpg"):
        out += moldura_video(640, -20, 380, 676, 0.5, "sincronia.jpg", 41)
    return {"duracao": d, "fundo": BG, "camadas": out}


# ══ 5 · corte pelo texto ══════════════════════════════════════════════
def c_texto(d: float) -> dict:
    frase = ["Isso", "aqui", "e", "tipo", "o", "que", "eu", "queria", "dizer"]
    cortadas = {3, 4}          # "tipo", "o" — os vicios
    out = [
        *grade_fundo(96, "#12151C", 0.3),
        brilho(0, 120, 760, VERM + "1A", 0, 0.45, 23),
        marca_dagua("CORTE", 430, VERM, -6, 0.04, 0),
        *particulas(14, VERM, LARANJA, 12, 27),
        rotulo("CORTE PELO TEXTO", 0.15, 380, VERM, 24),
        rotulo("APAGA A PALAVRA, SOME DO VIDEO", 0.45, 320, MUDO, 20),
    ]
    x = -sum(larg_texto(p, 72) + 26 for p in frase) / 2
    for i, p in enumerate(frase):
        w = larg_texto(p, 72)
        dd = 0.6 + i * PALAVRA
        cor = VERM if i in cortadas else TINTA
        out.append({
            "tipo": "texto", "texto": p, "tamanho": 72, "peso": 800,
            "cor": cor, "x": x + w / 2, "y": sobe(dd, 130, 20),
            "opacidade": entra(dd, 0.18) if i not in cortadas
                         else [[dd, 0], [dd + 0.18, 1], [2.3, 1], [2.7, 0.28]],
            "escala": {"mola": MOLA_TEXTO, "em": dd, "de": 0.88, "para": 1}})
        if i in cortadas:
            out.append({
                "tipo": "retangulo", "larg": w + 10, "alt": 5, "raio": 3,
                "cor": VERM, "x": x + w / 2, "y": 118,
                "opacidade": entra(2.3, 0.2),
                "escalaX": [[2.3, 0], [2.65, 1, "outCubic"]]})
        x += w + 26
    out += [
        rotulo("PAUSAS E VICIOS ACHADOS SOZINHOS", 2.9, -80, MUDO, 22),
        rotulo("NADA SAI ATE VOCE MANDAR", 3.2, -140, MUDO_CLARO, 19),
    ]
    return {"duracao": d, "fundo": BG, "camadas": out}


# ══ 6 · o copiloto ════════════════════════════════════════════════════
def c_copiloto(d: float) -> dict:
    ferramentas = ["adicionar_titulo", "marcar_cortes", "adicionar_zoom",
                   "buscar_broll", "aplicar_look", "renderizar",
                   "sugerir_shorts", "estilo_legenda"]
    out = [
        *grade_fundo(96, "#12151C", 0.3),
        brilho(-360, 0, 700, AZUL + "22", 0, 0.5, 31),
        marca_dagua("IA", 520, AZUL, 10, 0.05, 0),
        *particulas(18, AZUL, CIANO, 16, 33),
        rotulo("COPILOTO", 0.15, 400, CIANO, 24, -480),
        *titulo("Peca em portugues", 0.3, 290, 82, TINTA, 800, x0=-480),
        rotulo("ELE MEXE NO PROJETO", 1.0, 210, MUDO, 22, -480),
    ]
    # a caixa do chat
    out += sombra(-480, -40, 780, 320, 0.5, raio=16)
    out.append(card(-480, -40, 780, 320, 0.5, "#0D1117", BORDA, 16, 34))
    for i, txt in enumerate(['"Poe um titulo no ponto forte da fala"',
                             '"Marca os cortes das partes arrastadas"',
                             '"Sugere 3 shorts deste video"']):
        dd = 0.9 + i * (3 * BLOCO)
        out.append({
            "tipo": "texto", "texto": txt, "tamanho": 26, "peso": 500,
            "cor": MUDO, "x": -480, "y": 50 - i * 74,
            "opacidade": entra(dd, 0.25)})
    # as ferramentas, em pilulas do lado direito
    for i, f in enumerate(ferramentas):
        col, lin = i % 2, i // 2
        dd = 1.1 + i * BLOCO
        x = 500 + col * 320
        y = 220 - lin * 96
        out += [
            {"tipo": "retangulo", "larg": 290, "alt": 66, "raio": 33,
             "cor": "#FFFFFF08", "contorno": AZUL + "44", "contorno_larg": 1,
             **viva(x, y, 2, 50 + i), "opacidade": entra(dd, 0.22),
             "escala": {"mola": MOLA_ESTADO, "em": dd, "de": 0.85, "para": 1}},
            {"tipo": "texto", "texto": f, "tamanho": 22, "peso": 600,
             "cor": CIANO, "x": x, "y": y - 2, "opacidade": entra(dd + 0.08, 0.2)},
        ]
    out.append(rotulo("18 FERRAMENTAS  ·  QUALQUER LLM LOCAL", 2.3, -330, MUDO, 22))
    return {"duracao": d, "fundo": BG, "camadas": out}


# ══ 7 · shorts ════════════════════════════════════════════════════════
def c_shorts(d: float) -> dict:
    out = [
        *grade_fundo(96, "#12151C", 0.3),
        brilho(0, 0, 800, VERM + "1A", 0, 0.45, 37),
        marca_dagua("SHORTS", 400, VERM, -8, 0.04, 0),
        *particulas(16, VERM, LARANJA, 14, 39),
        rotulo("SHORTS", 0.15, 400, VERM, 24),
        *titulo("A IA acha, voce ajusta", 0.3, 310, 76, TINTA, 800),
    ]
    # tres clipes verticais
    for i, (arq, nota) in enumerate([("demo1.jpg", "90"), ("sincronia.jpg", "95"),
                                     ("demo2.jpg", "88")]):
        x = -460 + i * 460
        dd = 0.6 + i * (4 * BLOCO)
        out += moldura_video(x, -60, 300, 534, dd, arq, 60 + i)
        out += [
            {"tipo": "retangulo", "larg": 96, "alt": 44, "raio": 22,
             "cor": VERM, "x": x + 90, "y": 160,
             "opacidade": entra(dd + 0.4, 0.2),
             "escala": {"mola": MOLA_ESTADO, "em": dd + 0.4, "de": 0.7, "para": 1}},
            {"tipo": "texto", "texto": nota + "pt", "tamanho": 24, "peso": 800,
             "cor": "#000000", "x": x + 90, "y": 158,
             "opacidade": entra(dd + 0.48, 0.2)},
        ]
    out.append(rotulo("NADA SE PERDE QUANDO VOCE MEXE", 2.4, -390, MUDO, 22))
    return {"duracao": d, "fundo": BG, "camadas": out}


# ══ 8 · gravar ════════════════════════════════════════════════════════
def c_gravar(d: float) -> dict:
    botoes = [("MIC", MUDO), ("CAMERA", AZUL), ("TELA", AZUL),
              ("PROMPTER", MUDO), ("REC", VERM)]
    out = [
        *grade_fundo(96, "#12151C", 0.3),
        brilho(0, -120, 720, AZUL + "1F", 0, 0.45, 43),
        marca_dagua("REC", 460, VERM, 6, 0.04, 60),
        *particulas(14, AZUL, None, 12, 45),
        rotulo("GRAVACAO", 0.15, 400, AZUL, 24),
        *titulo("Grave sem sair daqui", 0.3, 300, 78, TINTA, 800),
    ]
    # a barra de gravacao, como no produto
    out += sombra(0, -60, 720, 96, 0.6, raio=48)
    out.append({"tipo": "retangulo", "larg": 720, "alt": 96, "raio": 48,
                "cor": "#12151C", "contorno": BORDA, "contorno_larg": 1,
                **viva(0, -60, 2, 46), "opacidade": entra(0.6, 0.3),
                "escala": {"mola": MOLA_ESTADO, "em": 0.6, "de": 0.9, "para": 1}})
    for i, (nome, cor) in enumerate(botoes):
        x = -280 + i * 140
        dd = 0.85 + i * BLOCO
        aceso = cor != MUDO
        out += [
            {"tipo": "elipse", "raio": 32, "cor": cor if aceso else "#21262D",
             "x": x, "y": -60, "opacidade": entra(dd, 0.2),
             "escala": {"mola": MOLA_ESTADO, "em": dd, "de": 0.6, "para": 1}},
            {"tipo": "texto", "texto": nome, "tamanho": 15, "peso": 700,
             "cor": MUDO_CLARO, "x": x, "y": -130, "espacamento": 1,
             "opacidade": entra(dd + 0.1, 0.2)},
        ]
    out += [
        rotulo("TELA  ·  CAMERA  ·  AS DUAS JUNTAS", 1.9, -260, MUDO, 22),
        rotulo("TELEPROMPTER QUE VAI PARA ONDE VOCE QUISER", 2.2, -320,
               MUDO_CLARO, 19),
    ]
    return {"duracao": d, "fundo": BG, "camadas": out}


# ══ 9 · motion ════════════════════════════════════════════════════════
def c_motion(d: float) -> dict:
    out = [
        *grade_fundo(96, "#12151C", 0.25),
        brilho(0, 0, 860, LARANJA + "1A", 0, 0.4, 49),
        marca_dagua("MOTION", 420, LARANJA, -6, 0.04, 0),
        *particulas(20, LARANJA, CIANO, 16, 51),
        rotulo("MOTION GRAPHICS", 0.15, 410, LARANJA, 24),
        *titulo("24 estilos de titulo", 0.3, 320, 78, TINTA, 800),
    ]
    if existe("cbv.jpg"):
        out += moldura_video(0, -40, 900, 506, 0.55, "cbv.jpg", 52)
    out += [
        rotulo("CENA DECLARATIVA  ·  SEM DEPENDENCIA EXTERNA", 2.0, -350, MUDO, 22),
        rotulo("1.456 CAMADAS NESTA PECA", 2.3, -410, MUDO_CLARO, 19),
    ]
    return {"duracao": d, "fundo": BG, "camadas": out}


# ══ 10 · custo ════════════════════════════════════════════════════════
def c_custo(d: float) -> dict:
    """Fundo CLARO. A alternancia claro/escuro e o que da ritmo no macro."""
    linhas = [("Deteccao de shorts por IA", "US$ 0,0002"),
              ("Render de 70 segundos", "US$ 0,00"),
              ("Motion graphics completo", "US$ 0,00")]
    out = [
        brilho(0, 0, 900, "#00000010", 0, 0.5, 55),
        marca_dagua("CUSTO", 440, "#0A0B0F", 8, 0.035, 0),
        rotulo("TRANSPARENCIA", 0.15, 390, MUDO_CLARO, 24),
        *titulo("Voce ve o que gasta", 0.3, 290, 86, TINTA_ESC, 900),
    ]
    for i, (o_que, quanto) in enumerate(linhas):
        dd = 0.75 + i * (4 * BLOCO)
        y = 120 - i * 110
        out += sombra(0, y, 1080, 88, dd, raio=14, n=2)
        out += [
            {"tipo": "retangulo", "larg": 1080, "alt": 88, "raio": 14,
             "cor": "#FFFFFF", "contorno": "#00000014", "contorno_larg": 1,
             **viva(0, y, 2, 70 + i), "opacidade": entra(dd, 0.25),
             "escala": {"mola": MOLA_ESTADO, "em": dd, "de": 0.94, "para": 1}},
            {"tipo": "texto", "texto": o_que, "tamanho": 30, "peso": 600,
             "cor": "#3A4152", "x": -180, "y": y - 2,
             "opacidade": entra(dd + 0.1, 0.2)},
            {"tipo": "texto", "texto": quanto, "tamanho": 34, "peso": 800,
             "cor": VERDE if "0,00" == quanto[-4:] else LARANJA,
             "x": 380, "y": y - 2, "opacidade": entra(dd + 0.15, 0.2)},
        ]
    out.append(rotulo("SUA CHAVE, SUA MAQUINA, SEU CUSTO", 2.5, -290,
                      MUDO_CLARO, 22))
    return {"duracao": d, "fundo": BG_CLARO, "camadas": out}


# ══ 11 · aberto ═══════════════════════════════════════════════════════
def c_aberto(d: float) -> dict:
    itens = [("MCP", "opere de fora"), ("LOCAL", "roda no seu PC"),
             ("SEM NUVEM", "nada sai daqui")]
    out = [
        *grade_fundo(96, "#12151C", 0.3),
        brilho(0, 0, 820, CIANO + "1A", 0, 0.45, 61),
        marca_dagua("ABERTO", 420, CIANO, -8, 0.04, 0),
        *particulas(18, CIANO, AZUL, 14, 63),
        rotulo("ARQUITETURA", 0.15, 400, CIANO, 24),
        *titulo("Uma implementacao", 0.3, 300, 76, TINTA, 800),
        rotulo("O CHAT DE DENTRO E O CLAUDE CODE DE FORA", 1.0, 220, MUDO, 22),
    ]
    for i, (nome, sub) in enumerate(itens):
        x = -520 + i * 520
        dd = 0.7 + i * (4 * BLOCO)
        out += sombra(x, -60, 420, 220, dd, raio=16)
        out += [
            card(x, -60, 420, 220, dd, "#0D1117", CIANO + "33", 16, 80 + i),
            {"tipo": "texto", "texto": nome, "tamanho": 52, "peso": 900,
             "cor": CIANO, "x": x, "y": -30, "opacidade": entra(dd + 0.15, 0.22)},
            {"tipo": "texto", "texto": sub, "tamanho": 24, "peso": 500,
             "cor": MUDO, "x": x, "y": -110, "opacidade": entra(dd + 0.25, 0.22)},
        ]
    out.append(rotulo("MESMAS 18 FERRAMENTAS NOS DOIS CAMINHOS", 2.5, -350,
                      MUDO_CLARO, 20))
    return {"duracao": d, "fundo": BG, "camadas": out}


# ══ 12 · fecho ════════════════════════════════════════════════════════
def c_fecho(d: float) -> dict:
    aneis = []
    for i in range(4):
        dd = 0.3 + sum(0.5 * (0.84 ** k) for k in range(i))
        aneis.append({
            "tipo": "elipse", "raio": 150, "cor": "#00000000",
            "contorno": LARANJA, "contorno_larg": 3, "y": 60,
            "escala": [[dd, 0.3], [dd + 1.9, 3.4, "outCubic"]],
            "opacidade": [[dd, 0.8], [dd + 1.9, 0]]})
    return {"duracao": d, "fundo": BG, "camadas": [
        *grade_fundo(96, "#12151C", 0.3),
        brilho(0, 60, 900, LARANJA + "26", 0, 0.5, 67),
        *particulas(24, LARANJA, AZUL, 18, 69),
        *aneis,
        *titulo("KLIPE", 0.5, 120, 170, TINTA, 900),
        {"tipo": "retangulo", "larg": 620, "alt": 6, "raio": 3, "cor": LARANJA,
         "y": 10, "opacidade": entra(1.15, 0.2),
         "escalaX": {"mola": MOLA_DESTAQUE, "em": 1.15, "de": 0, "para": 1}},
        *sigla(1.4, -60, 30),
        rotulo("localhost:3002", 2.2, -180, MUDO, 30, esp=2),
        rotulo("DOIS CLIQUES E ELE SOBE", 2.5, -245, MUDO_CLARO, 20),
    ]}


# ══ 13 · as ferramentas ═══════════════════════════
def c_ferramentas(d: float) -> dict:
    """A barra de ferramentas de verdade, desenhada em formas.

    Sao os sete paineis que existem na tela, na ordem em que estao la: Midia,
    Audio, Texto, Template, Filtros, Zoom, Formas. Nao e ilustracao — e o
    inventario.
    """
    ferr = [("midia", "MIDIA"), ("audio", "AUDIO"), ("texto", "TEXTO"),
            ("template", "TEMPLATE"), ("filtros", "FILTROS"),
            ("zoom", "ZOOM"), ("formas", "FORMAS")]
    out = [
        *grade_fundo(96, "#12151C", 0.28),
        brilho(0, 40, 880, LARANJA + "1F", 0, 0.45, 101),
        marca_dagua("PAINEIS", 400, LARANJA, -6, 0.038, 0),
        *particulas(20, LARANJA, AZUL, 16, 103),
        rotulo("A JANELA INTEIRA", 0.15, 430, LARANJA, 24),
        *titulo("Sete paineis, um lugar so", 0.3, 340, 72, TINTA, 800),
    ]
    for i, (qual, nome) in enumerate(ferr):
        x = -744 + i * 248
        dd = 0.7 + i * BLOCO
        # o TEXTO e o painel que o resto do comercial usa — ele acende
        aceso = qual == "texto"
        cor = LARANJA if aceso else MUDO
        out += sombra(x, 60, 210, 200, dd, raio=16, n=2)
        out.append(card(x, 60, 210, 200, dd, "#0D1117",
                        LARANJA + "55" if aceso else BORDA, 16, 110 + i))
        out += glifo(qual, x, 95, dd, cor)
        out.append({"tipo": "texto", "texto": nome, "tamanho": 22, "peso": 800,
                    "cor": cor, "espacamento": 2, "x": x, "y": 0,
                    "opacidade": entra(dd + 0.2, 0.25)})
    # a barra de cima: os quatro botoes que abrem o resto
    for i, (nome, cor) in enumerate((("Chat", AZUL), ("Gravar", CIANO),
                                     ("Shorts", VERDE), ("Render", VERM))):
        x = -450 + i * 300
        dd = 2.0 + i * BLOCO
        larg = larg_texto(nome, 30) + 90
        out += [
            {"tipo": "retangulo", "larg": larg, "alt": 62, "raio": 31,
             "cor": cor + "1F", "contorno": cor + "66", "contorno_larg": 2,
             **viva(x, -190, 2, 120 + i), "opacidade": entra(dd, 0.25),
             "escala": {"mola": MOLA_ESTADO, "em": dd, "de": 0.9, "para": 1}},
            {"tipo": "texto", "texto": nome, "tamanho": 30, "peso": 800,
             "cor": cor, "x": x, "y": -192, "opacidade": entra(dd + 0.08, 0.25)}]
    out.append(rotulo("NADA ABRE OUTRO PROGRAMA", 2.55, -320, MUDO, 22))
    return {"duracao": d, "fundo": BG, "camadas": out}


# ══ 14 · a linha do tempo ═════════════════════════
def c_trilhas(d: float) -> dict:
    """As cinco trilhas, com o cabecote correndo por cima.

    As quantidades de clipe sao as do projeto que esta aberto agora: b-rolls
    em duas trilhas, audio continuo, SFX picados. Nao inventei nenhuma.
    """
    trilhas = [("VIDEO", AZUL, [(0, 1560)]),
               ("B-ROLL 1", VERDE, [(20, 210), (250, 180), (450, 150),
                                    (620, 190), (830, 300), (1150, 200)]),
               ("B-ROLL 2", VERDE, [(60, 120), (220, 130), (700, 140),
                                    (1000, 160)]),
               ("AUDIO", CIANO, [(0, 1560)]),
               ("SFX", LARANJA, [(180, 60), (420, 50), (520, 70), (760, 55),
                                 (900, 65), (1180, 50), (1320, 60)])]
    # A faixa inteira tem que caber em 1920 CONTANDO o cabecalho: com X0=-760
    # a coluna de nomes comecava em -985 e a prova saiu com "VIDEO" cortado.
    X0, LARG = -720, 1490
    ESC = LARG / 1560.0            # os clipes foram desenhados pra 1560
    out = [
        *grade_fundo(96, "#12151C", 0.22),
        brilho(0, 0, 900, AZUL + "16", 0, 0.45, 131),
        marca_dagua("TIMELINE", 380, AZUL, -5, 0.035, 0),
        rotulo("LINHA DO TEMPO", 0.15, 450, AZUL, 24),
        *titulo("Cinco trilhas, um arquivo", 0.3, 370, 70, TINTA, 800),
    ]
    # a regua
    for i in range(9):
        x = X0 + i * (LARG / 8)
        out.append({"tipo": "retangulo", "larg": 2, "alt": 14, "cor": "#3A4152",
                    "x": x, "y": 245, "opacidade": entra(0.6 + i * LETRA, 0.2)})
        seg = i * 10
        out.append({"tipo": "texto", "texto": "%02d:%02d" % (seg // 60, seg % 60),
                    "tamanho": 17,
                    "peso": 600, "cor": "#4B5563", "x": x + 34, "y": 268,
                    "opacidade": entra(0.6 + i * LETRA, 0.2)})
    for k, (nome, cor, clipes) in enumerate(trilhas):
        y = 180 - k * 84
        dd = 0.75 + k * BLOCO
        # o cabecalho da trilha
        out += [
            {"tipo": "retangulo", "larg": 176, "alt": 62, "raio": 8,
             "cor": "#0D1117", "contorno": BORDA, "contorno_larg": 1,
             **viva(X0 - 118, y, 2, 140 + k), "opacidade": entra(dd, 0.25)},
            {"tipo": "texto", "texto": nome, "tamanho": 20, "peso": 800,
             "cor": cor, "espacamento": 1, "x": X0 - 118, "y": y - 2,
             "opacidade": entra(dd + 0.06, 0.25)}]
        for j, (off, w) in enumerate(clipes):
            off, w = off * ESC, w * ESC
            cx = X0 + off + w / 2
            de = dd + 0.12 + j * LETRA
            out.append({
                "tipo": "retangulo", "larg": w, "alt": 62, "raio": 7,
                "cor": cor + "2E", "contorno": cor + "88", "contorno_larg": 2,
                "x": cx, "y": y, "opacidade": entra(de, 0.22),
                "escalaX": {"mola": MOLA_ESTADO, "em": de, "de": 0.0, "para": 1}})
        # a onda do audio, dentro da trilha de audio
        if nome == "AUDIO":
            n_onda = 74
            passo = (LARG - 28) / (n_onda - 1)
            for j in range(n_onda):
                h = 8 + 34 * abs(((j * 37) % 23) / 23 - 0.5) * 2
                out.append({
                    "tipo": "retangulo", "larg": 4, "alt": h, "raio": 2,
                    "cor": CIANO + "AA", "x": X0 + 14 + j * passo, "y": y,
                    "opacidade": entra(dd + 0.3 + j * 0.004, 0.2)})
    # o cabecote: atravessa a cena inteira, uma vez
    out.append({
        "tipo": "retangulo", "larg": 3, "alt": 480, "cor": VERM, "y": -10,
        "x": [[0.9, X0], [d - 0.35, X0 + LARG, "inOutCubic"]],
        "opacidade": [[0.9, 0], [1.05, 1]]})
    out.append(rotulo("VIDEO  ·  B-ROLL  ·  AUDIO  ·  SFX  ·  LEGENDA",
                      2.5, -330, MUDO, 22))
    return {"duracao": d, "fundo": BG, "camadas": out}


# ══ 15 · a biblioteca ═════════════════════════════
def c_biblioteca(d: float) -> dict:
    """O painel de Texto: as abas, e a galeria de titulos.

    Os seis cartoes sao seis estilos que o motor desenha de verdade, e a
    amostra de cada um DESCREVE O EFEITO — nao conta a historia de nenhum
    video. Foi assim que a biblioteca foi refeita: a antiga tinha 23 templates
    e as 23 amostras vinham do mesmo cliente.
    """
    abas = ["TODOS", "TITULOS", "MOTIONS", "TRANSICOES"]
    cartoes = [("SPLIT TEXT", "cada palavra no seu tempo", LARANJA),
               ("WORD HIGHLIGHT", "a palavra que importa", CIANO),
               ("COUNTER", "72%", VERDE),
               ("POINT LIST", "titulo + itens, um a um", AZUL),
               ("STACKED REVEAL", "PRIMEIRA / segunda / TERCEIRA", MUDO),
               ("PARADOX", "linha leve / LINHA FORTE", VERM)]
    out = [
        *grade_fundo(96, "#12151C", 0.25),
        brilho(0, 30, 900, LARANJA + "1C", 0, 0.45, 161),
        marca_dagua("TITULOS", 400, LARANJA, -7, 0.038, 0),
        *particulas(18, LARANJA, CIANO, 15, 163),
        rotulo("BIBLIOTECA", 0.15, 440, LARANJA, 24),
        *titulo("22 estilos que o motor desenha", 0.3, 350, 66, TINTA, 800),
    ]
    # as abas, com TITULOS acesa
    x = -430
    for i, nome in enumerate(abas):
        larg = larg_texto(nome, 24) + 56
        dd = 0.65 + i * BLOCO
        aceso = nome == "TITULOS"
        out += [
            {"tipo": "retangulo", "larg": larg, "alt": 50, "raio": 25,
             "cor": LARANJA if aceso else "#FFFFFF0A",
             "contorno": "#00000000" if aceso else BORDA, "contorno_larg": 1,
             "x": x + larg / 2, "y": 250, "opacidade": entra(dd, 0.25),
             "escala": {"mola": MOLA_ESTADO, "em": dd, "de": 0.88, "para": 1}},
            {"tipo": "texto", "texto": nome, "tamanho": 24, "peso": 800,
             "cor": "#0A0B0F" if aceso else MUDO, "espacamento": 1,
             "x": x + larg / 2, "y": 248, "opacidade": entra(dd + 0.06, 0.25)}]
        x += larg + 22
    # a grade de cartoes: 3 por linha
    for i, (nome, amostra, cor) in enumerate(cartoes):
        cx = -560 + (i % 3) * 560
        cy = 60 - (i // 3) * 230
        dd = 0.95 + i * BLOCO
        out += sombra(cx, cy, 500, 195, dd, raio=14, n=2)
        out.append(card(cx, cy, 500, 195, dd, "#0D1117", BORDA, 14, 170 + i))
        out += [
            # a miniatura: a amostra desenhada dentro do cartao
            {"tipo": "retangulo", "larg": 460, "alt": 96, "raio": 8,
             "cor": "#080A0E", "x": cx, "y": cy + 38,
             "opacidade": entra(dd + 0.1, 0.25)},
            {"tipo": "texto", "texto": amostra, "tamanho": 26, "peso": 700,
             "cor": cor, "x": cx, "y": cy + 36, "largura_max": 430,
             "alinha": "centro", "opacidade": entra(dd + 0.2, 0.25)},
            {"tipo": "texto", "texto": nome, "tamanho": 24, "peso": 900,
             "cor": TINTA, "espacamento": 1, "x": cx, "y": cy - 55,
             "opacidade": entra(dd + 0.28, 0.25)}]
    out += [
        rotulo("26 TEMPLATES EM 9 CATEGORIAS", 2.75, -290, MUDO, 22),
        rotulo("A AMOSTRA DESCREVE O EFEITO, NAO UM VIDEO", 3.0, -350,
               MUDO_CLARO, 19),
    ]
    return {"duracao": d, "fundo": BG, "camadas": out}


# A ordem conta uma historia: o que E (abertura, motor), o que TEM
# (ferramentas, trilhas), o que FAZ (render, legenda, texto, copiloto,
# shorts, gravar, biblioteca, motion), o que CUSTA, e como se abre.
CENAS = [
    ("abertura", c_abertura, 4.0), ("motor", c_motor, 3.4),
    ("ferramentas", c_ferramentas, 3.6), ("trilhas", c_trilhas, 3.6),
    ("render", c_render, 3.0), ("legenda", c_legenda, 4.0),
    ("texto", c_texto, 4.2), ("copiloto", c_copiloto, 4.2),
    ("shorts", c_shorts, 3.8), ("gravar", c_gravar, 3.6),
    ("biblioteca", c_biblioteca, 4.0), ("motion", c_motion, 3.6),
    ("custo", c_custo, 3.8), ("aberto", c_aberto, 3.6),
    ("fecho", c_fecho, 4.0),
]


def montar():
    out, t = [], 0.0
    for nome, fn, dur in CENAS:
        out.append((nome, fn(dur), t, t + dur))
        t += dur - TRANSICAO
    return out


def renderizar(cenas) -> Path:
    dur_total = cenas[-1][3]
    n = int(dur_total * FPS)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(
        [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", str(SAIDA)], stdin=subprocess.PIPE)
    montadas = [(Cena(s, W, H, FPS), a, b) for _, s, a, b in cenas]
    surface, fechar = superficie(W, H)
    canvas = surface.getCanvas()
    print(f"  desenhando na {onde()}", flush=True)
    buf = np.empty((H, W, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType,
                               skia.kPremul_AlphaType)
    t0 = time.time()
    for f in range(n):
        t = f / FPS
        canvas.clear(skia.Color4f(0, 0, 0, 1))
        for c, a, b in montadas:
            if not (a <= t < b):
                continue
            alpha = 1.0
            if t < a + TRANSICAO and a > 0:
                alpha = (t - a) / TRANSICAO
            elif t > b - TRANSICAO and b < dur_total:
                alpha = max(0.0, (b - t) / TRANSICAO)
            canvas.saveLayerAlpha(None, int(255 * min(1.0, alpha)))
            c.desenhar(canvas, t - a)
            canvas.restore()
        fechar()
        surface.readPixels(info, buf, W * 4, 0, 0)
        p.stdin.write(buf.tobytes())
        if f % 150 == 0:
            print(f"  {f}/{n} ({f * 100 // max(1, n)}%)", flush=True)
    p.stdin.close()
    p.wait()
    dt = time.time() - t0
    print(f"[Comercial] {n} frames em {dt:.0f}s | {SAIDA} "
          f"({SAIDA.stat().st_size / 1e6:.1f} MB)")
    return SAIDA


if __name__ == "__main__":
    cenas = montar()
    total = 0
    for nome, spec, a, b in cenas:
        e = validar(spec)
        total += len(spec["camadas"])
        print(f"  {nome:10} {b - a:4.1f}s  {len(spec['camadas']):3} camadas  "
              f"{'OK' if not e else e[:2]}")
        if e:
            sys.exit(1)
    print(f"  {len(cenas)} cenas · {total} camadas · {cenas[-1][3]:.1f}s")
    if "--stills" in sys.argv:
        pasta = RAIZ / "output" / "_comercial"
        pasta.mkdir(parents=True, exist_ok=True)
        for nome, spec, a, b in cenas:
            Cena(spec, W, H, FPS).still((b - a) * 0.65).save(str(pasta / f"{nome}.png"))
        print(f"  provas em {pasta}")
    else:
        renderizar(cenas)
