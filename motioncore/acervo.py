# -*- coding: utf-8 -*-
"""acervo.py — o catalogo: cada titulo do Klipe, com o som que combina.

Isto NAO e uma maquete. Cada titulo que aparece e desenhado pelo `TitleRenderer`
— o mesmo que a linha do tempo usa pra renderizar o video de verdade. Se um
estilo estiver quebrado, ele quebra aqui tambem, e e pra isso que serve um
catalogo: mostrar o acervo como ele e.

O QUE ENTRA
  22 estilos que o motor desenha. Os outros 24 do catalogo da interface estao
  marcados "(nao desenhado)" la e ficam de fora daqui — mostrar o que nao
  desenha seria propaganda enganosa do proprio produto.

O SOM
  Cada estilo casa com um SFX pelo GESTO, nao pelo nome: o que bate ganha
  impacto, o que desliza ganha whoosh, o que conta ganha shimmer, o que se
  escreve ganha risco. As duracoes foram MEDIDAS com ffprobe, uma por uma —
  duracao de SFX nunca se chuta.

O ACENTO
  Os estilos desenham com a laranja `#E8940A`, que e do icone antigo. Aqui o
  acervo troca pelo indigo da marca EM TEMPO DE EXECUCAO, sem tocar no arquivo:
  os 27 projetos que ja existem continuam saindo como sempre sairam. Trocar de
  vez sao 5 linhas, e esta escrito abaixo quais.

    python -m motioncore.acervo
    python -m motioncore.acervo --stills
    python -m motioncore.acervo --mudo      (pula a mixagem de audio)
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from .cena import Cena, validar
from .ffbin import ffmpeg as _ffmpeg, ffprobe as _ffprobe
from .fonts import FontRegistry
from .gpu import onde, superficie
from .scene import Title, TitleRenderer
from .styles import basicos, motions, restantes, stacked_reveal

from .kbv.base import (W, H, FPS, F, LETRA, BLOCO, MOLA_TEXTO, MOLA_DESTAQUE,
                       MOLA_ESTADO, BG, BG_SUP, BG_GRADE, BORDA, TEXTO, MUDO,
                       MUDO_ESCURO, DIM, MARCA, MARCA_CLARA, AZUL, VERDE,
                       CIANO, ROXO, VERM, larg_texto, entra, viva, pulso,
                       titulo, rotulo, card, sombra, brilho, particulas,
                       marca_dagua, grade_fundo, sigla)

RAIZ = Path(__file__).resolve().parent.parent
SFX_DIR = RAIZ / "public" / "sfx"
SAIDA = RAIZ / "output" / "klipe_acervo.mp4"
FFMPEG = _ffmpeg()
FFPROBE = _ffprobe()

DUR_ITEM = 2.2          # cada peca do acervo
DUR_CARTAO = 2.6        # os cartoes de secao


# ══ o acervo ══════════════════════════════════════════════════════════
# (estilo, nome, familia, amostra, sfx, volume, DURACAO)
#
# A amostra DESCREVE O EFEITO. A biblioteca antiga tinha 23 amostras vindas do
# mesmo video de um cliente, e era dai que vinha o vies.
#
# A DURACAO E POR PECA, e isso nao e capricho. Num slot fixo de 2,2 s o
# `liveComments` nao desenha UM pixel — os comentarios dele sobem a cada
# 1,15 s. O `echoWords` mostra um terco. Ja o `cutMask` e um flash de virada:
# num slot longo ele fica quase o tempo todo em tela vazia, que e o certo pra
# ele. Slot uniforme mentiria sobre metade do acervo.
TITULOS = [
    ("hero", "Hero", "Impacto", "TITULO DE IMPACTO",
     "transition_impacts/Grand Hit - Desconhecido.wav", 0.5, 2.2),
    ("flash", "Kinetic type", "Impacto", "IMPACTO CURTO",
     "transition_impacts/CinematicHITS 1 - SoundConteúdo.wav", 0.45, 2.2),
    ("descending", "Character reveal", "Impacto", "LETRA POR LETRA",
     "whooshes/Low Whoosh - SoundConteúdo.wav", 0.5, 2.4),
    ("kinetic", "Split text", "Revelação", "CADA PALAVRA NO SEU TEMPO",
     "pop_click/Marker - SoundConteúdo.wav", 0.6, 2.6),
    # o cutMask e um FLASH de virada, nao um titulo que fica: 0,33 s de
    # glitch e pronto. Slot curto e o unico honesto pra ele.
    ("cutMask", "Cut mask", "Revelação", "CORTE",
     "glitch/VHS - SoundConteúdo.wav", 0.4, 1.5),

    ("mixedSerif", "Word highlight", "Ênfase", "a palavra que|IMPORTA",
     "whooshes/Fast Woosh - SoundConteúdo.mp3", 0.5, 2.4),
    ("lower3rd", "Lower third", "Rótulo", "Rotulo com barra de accent",
     "transition_sweep/Zoom In.mp3", 0.55, 2.2),
    ("ribbon", "Ribbon", "Rótulo", "FAIXA HORIZONTAL",
     "whooshes/Swish Whoosh Large.mp3", 0.5, 2.2),
    # SEM `|`: o counter separa por ESPACO (regex numero + rotulo). Com pipe
    # ele desenhava o proprio pipe na tela.
    ("counter", "Counter", "Dado", "72% o que o numero quer dizer",
     "shimmer/Contagem 2 - SoundConteúdo.wav", 0.55, 2.4),

    ("quote", "Quote", "Citação", "Uma frase entre aspas, em serifada",
     "shimmer/Ideia - SoundConteúdo.mp3", 0.5, 2.4),
    ("paradoxQuote", "Paradox", "Citação",
     "linha leve|LINHA FORTE|outra leve|OUTRA FORTE",
     "reverse/Reveal - SoundConteúdo.wav", 0.5, 2.8),

    ("letterEyebrow", "Letter eyebrow", "Composto",
     "rotulo pequeno|LINHA PRINCIPAL|cauda em italico",
     "whooshes/Deep Whoosh - SoundConteúdo.mp3", 0.45, 2.6),
    ("compound2", "Compound blur", "Composto",
     "primeira linha|SEGUNDA EM BLUR|terceira sobe",
     "riser_synth/Riser de Transition - SoundConteúdo.wav", 0.45, 2.6),
    ("stackedReveal", "Stacked reveal", "Composto",
     "PRIMEIRA|segunda|TERCEIRA",
     "pop_click/Mouse Click - SoundConteúdo.wav", 0.5, 2.6),
    ("slideReveal", "Slide reveal", "Composto",
     "entra da esquerda|ENTRA DA DIREITA|e a terceira sobe",
     "whooshes/Whoosh Slow - SoundConteúdo.wav", 0.45, 2.6),
    ("livre", "Livre", "Montar do zero", "SEU TITULO",
     "pop_click/Click - SoundConteúdo.wav", 0.7, 2.2),
]

MOTIONS = [
    ("pointList", "Point list", "Tela cheia",
     "TITULO DA LISTA|Primeiro item|Segundo item|Terceiro item",
     "shimmer/Ui - SoundConteúdo.mp3", 0.5, 3.6),
    ("panel", "Panel", "Tela cheia",
     "Primeiro item|Segundo item|Terceiro item",
     "foley/Gear.mp3", 0.4, 3.4),
    # 5,4 s porque este estilo NAO DESENHA NADA antes do frame 108 (3,6 s) em
    # 16:9 — medido, nao suposto. O `LC_BASE = 1500` dele foi afinado pra
    # 1080x1920: num quadro de 1080 de altura os comentarios nascem 420 px
    # abaixo da borda e levam 3,6 s pra chegar. Em video horizontal curto ele
    # e uma tela preta, e isso esta no relatorio.
    ("liveComments", "Live comments", "Tela cheia",
     "um comentario sobe|outro aparece|e mais um",
     "pop_click/Click - SoundConteúdo.wav", 0.6, 5.4),
    ("wordCollapse", "Word collapse", "Tela cheia",
     "PALAVRA|PALAVRA MAIOR|MENOR|COLAPSA",
     "riser_synth/Riser Short Distorting - SoundConteúdo.wav", 0.4, 3.4),
    ("echoWords", "Echo words", "Tela cheia",
     "primeira frase|segunda frase|terceira frase",
     "glitch/Extreme Tension - SoundConteúdo.wav", 0.3, 4.2),
    ("sensoryStorm", "Sensory storm", "Tela cheia",
     "PALAVRA|PALAVRA|PALAVRA|PALAVRA|PALAVRA",
     "riser_synth/Riser Short Screaming - SoundConteúdo.wav", 0.4, 3.0),
]

# as 13 gavetas de som, com o que cada uma serve
GAVETAS = [
    ("riser_synth", 14, "sobe antes do corte", MARCA),
    ("whooshes", 10, "passa e leva junto", CIANO),
    ("foley", 7, "objeto do mundo", VERDE),
    ("transition_impacts", 5, "o baque da virada", VERM),
    ("shimmer", 4, "brilho e contagem", MARCA_CLARA),
    ("pop_click", 3, "o toque miudo", AZUL),
    ("writing", 3, "risco desenhado", ROXO),
    ("glitch", 2, "a falha proposital", VERM),
    ("bass_drop", 1, "o chao sumindo", MARCA),
    ("reverse", 1, "o tempo de tras", ROXO),
    ("transition_sweep", 1, "a varrida curta", CIANO),
]


def _dur_sfx(rel: str) -> float:
    """Duracao MEDIDA com ffprobe. Nunca chutada — e a regra."""
    p = SFX_DIR / rel
    if not p.exists():
        return 0.0
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout
        return float(out.strip())
    except Exception:
        return 0.0


def _acento_da_marca():
    """Troca a laranja do icone antigo pelo indigo da marca, EM MEMORIA.

    Os estilos leem `ACC` dentro das funcoes de desenho, entao religar o nome
    no modulo basta e nenhum arquivo muda. Os 27 projetos que ja existem
    continuam saindo como sempre sairam.

    Pra trocar de vez, sao estes cinco lugares:
        styles/basicos.py:29        ACC
        styles/motions.py:200       LC_CORES[0]
        styles/motions.py:358       SS_PALETA[0]
        styles/restantes.py:232     HN_TAG_FUNDO
        styles/stacked_reveal.py:49 o padrao de ctx.color2
    """
    # `motions.py` e `restantes.py` fazem `from .basicos import ACC`, o que
    # copia o VALOR. Religar so `basicos.ACC` deixava metade dos titulos
    # laranja e a outra metade indigo — foi o que a primeira prova mostrou.
    basicos.ACC = MARCA
    motions.ACC = MARCA
    restantes.ACC = MARCA
    motions.LC_CORES = [MARCA, ROXO, "#E63F8A", CIANO,
                        VERDE, VERM, AZUL, MARCA_CLARA]
    motions.SS_PALETA = [MARCA, "#F0F0F0", MARCA_CLARA, "#A0A0A0", "#FFFFFF"]
    restantes.HN_TAG_FUNDO = MARCA


# ══ a moldura: o que fica em volta do titulo ══════════════════════════
# Ela mora nas BORDAS de proposito. Sete dos estilos sao motion de tela cheia,
# e qualquer coisa minha perto do centro colidiria com eles.

def _moldura(i: int, n: int, nome: str, familia: str, estilo: str,
             sfx: str, dur_sfx: float, cor: str, dur: float) -> dict:
    som = sfx.split("/")[-1].rsplit(" - ", 1)[0].rsplit(".", 1)[0]
    C = [
        # o indice, na quina de cima
        {"tipo": "texto", "texto": f"{i:02d}", "tamanho": 78, "peso": 900,
         "cor": "#FFFFFF12", "x": -880, "y": 452, "opacidade": entra(0.05, 0.3)},
        {"tipo": "texto", "texto": f"/{n}", "tamanho": 26, "peso": 700,
         "cor": DIM, "x": -812, "y": 424, "opacidade": entra(0.12, 0.3)},
        # a familia, na quina de cima a direita
        {"tipo": "texto", "texto": familia.upper(), "tamanho": 20, "peso": 800,
         "cor": cor, "espacamento": 4, "x": 800, "y": 452,
         "opacidade": entra(0.1, 0.3)},
        # a barra de baixo
        {"tipo": "retangulo", "larg": 1920, "alt": 108, "cor": "#000000B8",
         "y": -486, "opacidade": entra(0.08, 0.3)},
        {"tipo": "retangulo", "larg": 1920, "alt": 2, "cor": cor + "66",
         "y": -432, "opacidade": entra(0.08, 0.3),
         "escalaX": {"mola": MOLA_ESTADO, "em": 0.08, "de": 0.0, "para": 1.0}},
        # o nome do estilo
        {"tipo": "texto", "texto": nome, "tamanho": 34, "peso": 900,
         "cor": TEXTO, "x": -700, "y": -466, "opacidade": entra(0.18, 0.3)},
        {"tipo": "texto", "texto": estilo, "tamanho": 19, "peso": 600,
         "cor": DIM, "x": -700, "y": -508, "opacidade": entra(0.26, 0.3)},
        # o som que combina
        {"tipo": "elipse", "raio": 7, "cor": cor, "x": 250, "y": -466,
         "opacidade": entra(0.34, 0.3), "escala": pulso(1.0, 0.3, 0.06, 7)},
        {"tipo": "texto", "texto": som, "tamanho": 26, "peso": 700,
         "cor": cor, "x": 520, "y": -468, "opacidade": entra(0.34, 0.3)},
        {"tipo": "texto", "texto": f"{dur_sfx:.2f}s medidos", "tamanho": 18,
         "peso": 600, "cor": DIM, "x": 520, "y": -508,
         "opacidade": entra(0.42, 0.3)},
    ]
    # a barrinha de tempo do item, correndo
    C.append({"tipo": "retangulo", "larg": 1920, "alt": 4, "cor": cor,
              "y": -538, "x": [[0, -960], [dur, 0, "linear"]],
              "escalaX": [[0, 0.0], [dur, 1.0, "linear"]],
              "opacidade": entra(0.05, 0.2)})
    # `fundo` VAZIO de proposito: `Cena.desenhar` pinta o fundo no canvas
    # inteiro quando ele existe, e a moldura entra DEPOIS do titulo. Com BG
    # aqui, ela apagava o titulo — que e o assunto da cena.
    return {"duracao": dur, "fundo": None, "camadas": C}


def _fundo_item(cor: str, s: int) -> list[dict]:
    """Fundo discreto: ele nao pode competir com o titulo, que e o assunto."""
    return (grade_fundo(120, BG_GRADE, 0.22)
            + [brilho(0, 0, 900, cor + "14", 0.0, 0.5, s)]
            + particulas(10, cor, MARCA, 12, s + 3))


# ══ os cartoes ════════════════════════════════════════════════════════

def c_abertura() -> dict:
    n_sfx = sum(g[1] for g in GAVETAS)
    C = (grade_fundo(96, BG_GRADE, 0.4)
         + [brilho(0, 60, 780, MARCA + "2E", 0.0, 0.55, 3),
            marca_dagua("ACERVO", 460, MARCA, -7, 0.05, 0)]
         + particulas(26, MARCA, MARCA_CLARA, 18, 5))
    C += titulo("O ACERVO", 0.3, 150, 150, TEXTO, 900)
    C.append({"tipo": "retangulo", "larg": 620, "alt": 6, "raio": 3,
              "cor": MARCA, "y": 30, "opacidade": entra(0.9, 0.2),
              "escalaX": {"mola": MOLA_DESTAQUE, "em": 0.9, "de": 0.0,
                          "para": 1.0}})
    for i, (num, rot, cor) in enumerate(((str(len(TITULOS)), "TITULOS", MARCA),
                                         (str(len(MOTIONS)), "MOTIONS", CIANO),
                                         (str(n_sfx), "SONS", VERDE))):
        x = -520 + i * 520
        t = 0.95 + i * BLOCO
        C += sombra(x, -140, 420, 220, t, raio=16, n=2)
        C.append(card(x, -140, 420, 220, t, BG_SUP, cor + "33", 16, 20 + i))
        C.append({"tipo": "texto", "texto": num, "tamanho": 88, "peso": 900,
                  "cor": cor, "x": x, "y": -112, "opacidade": entra(t + 0.12, 0.25),
                  "escala": {"mola": MOLA_DESTAQUE, "em": t + 0.12,
                             "de": 0.6, "para": 1.0}})
        C.append({"tipo": "texto", "texto": rot, "tamanho": 24, "peso": 800,
                  "cor": MUDO, "espacamento": 3, "x": x, "y": -196,
                  "opacidade": entra(t + 0.24, 0.25)})
    C.append(rotulo("CADA UM DESENHADO PELO MOTOR, COM O SOM QUE COMBINA",
                    2.0, -330, MUDO_ESCURO, 21))
    return {"duracao": DUR_CARTAO, "fundo": BG, "camadas": C}


def c_secao(txt: str, sub: str, cor: str, s: int) -> dict:
    C = (grade_fundo(96, BG_GRADE, 0.3)
         + [brilho(0, 20, 820, cor + "26", 0.0, 0.5, s),
            marca_dagua(txt, 420, cor, -6, 0.045, 0)]
         + particulas(18, cor, MARCA, 15, s + 2))
    C += titulo(txt, 0.25, 60, 120, TEXTO, 900)
    C.append({"tipo": "retangulo", "larg": 460, "alt": 5, "raio": 3,
              "cor": cor, "y": -40, "opacidade": entra(0.8, 0.2),
              "escalaX": {"mola": MOLA_DESTAQUE, "em": 0.8, "de": 0.0,
                          "para": 1.0}})
    C.append(rotulo(sub, 1.1, -120, MUDO, 24))
    return {"duracao": DUR_CARTAO * 0.7, "fundo": BG, "camadas": C}


def c_sons() -> dict:
    """As gavetas de som, com a contagem de cada uma."""
    C = (grade_fundo(96, BG_GRADE, 0.28)
         + [brilho(0, 30, 900, VERDE + "1C", 0.0, 0.45, 41),
            marca_dagua("SONS", 440, VERDE, -6, 0.04, 0)]
         + particulas(16, VERDE, CIANO, 14, 43))
    C.append(rotulo("BIBLIOTECA DE EFEITOS", 0.08, 440, VERDE, 24))
    n = sum(g[1] for g in GAVETAS)
    C += titulo(f"{n} sons em {len(GAVETAS)} gavetas", 0.2, 348, 68, TEXTO, 800)
    for i, (nome, qtd, serve, cor) in enumerate(GAVETAS):
        col, lin = i % 4, i // 4
        x = (col - 1.5) * 452
        y = 150 - lin * 158
        t = 0.5 + (abs(col - 1.5) + lin) * BLOCO
        C += sombra(x, y, 420, 132, t, raio=12, n=2)
        C.append(card(x, y, 420, 132, t, BG_SUP, cor + "33", 12, 50 + i))
        C.append({"tipo": "texto", "texto": nome, "tamanho": 25, "peso": 800,
                  "cor": TEXTO, "x": x - 40, "y": y + 22,
                  "opacidade": entra(t + 0.12, 0.25)})
        C.append({"tipo": "texto", "texto": str(qtd), "tamanho": 30,
                  "peso": 900, "cor": cor, "x": x + 158, "y": y + 20,
                  "opacidade": entra(t + 0.18, 0.25)})
        C.append({"tipo": "texto", "texto": serve, "tamanho": 19, "peso": 500,
                  "cor": MUDO, "x": x - 40, "y": y - 26,
                  "opacidade": entra(t + 0.24, 0.25)})
    C.append(rotulo("DURACAO MEDIDA COM FFPROBE, UMA POR UMA",
                    2.55, -400, MUDO_ESCURO, 20))
    return {"duracao": 3.6, "fundo": BG, "camadas": C}


def c_fecho() -> dict:
    C = (grade_fundo(96, BG_GRADE, 0.32)
         + [brilho(0, 80, 900, MARCA + "2E", 0.0, 0.55, 61)]
         + particulas(24, MARCA, MARCA_CLARA, 18, 63))
    for i in range(3):
        d = 0.2 + sum(0.5 * (0.84 ** k) for k in range(i))
        C.append({"tipo": "elipse", "raio": 170, "cor": "#00000000",
                  "contorno": MARCA, "contorno_larg": 3, "y": 90,
                  "escala": [[d, 0.3], [d + 1.9, 3.0, "outCubic"]],
                  "opacidade": [[d, 0.65], [d + 1.9, 0]]})
    C += titulo("KLIPE", 0.4, 90, 170, TEXTO, 900)
    C.append({"tipo": "retangulo", "larg": 620, "alt": 6, "raio": 3,
              "cor": MARCA, "y": -20, "opacidade": entra(1.0, 0.2),
              "escalaX": {"mola": MOLA_DESTAQUE, "em": 1.0, "de": 0.0,
                          "para": 1.0}})
    C += sigla(1.25, -95, 30)
    C.append(rotulo("TUDO ISSO JA VEM INSTALADO", 2.0, -230, MUDO, 24))
    C.append(rotulo("NENHUM PLUGIN, NENHUMA ASSINATURA", 2.3, -290,
                    MUDO_ESCURO, 20))
    return {"duracao": DUR_CARTAO + 0.6, "fundo": BG, "camadas": C}


# ══ montagem ══════════════════════════════════════════════════════════

def montar():
    """Devolve a lista de trechos e a trilha de sons a mixar.

    Cada trecho e (rotulo, spec_do_fundo, spec_da_moldura, titulo_ou_None).
    O titulo NAO cabe no DSL — ele e desenhado pelo renderizador de verdade,
    entao viaja ao lado e e composto no mesmo canvas.
    """
    trechos, sons, t = [], [], 0.0

    def por(nome, spec, tit=None, fundo=None):
        nonlocal t
        trechos.append((nome, fundo, spec, tit, t, t + spec["duracao"]))
        t += spec["duracao"]

    por("abertura", c_abertura())
    por("sec-titulos", c_secao("TITULOS", "TEXTO SOBRE O VIDEO", MARCA, 31))

    n_tot = len(TITULOS) + len(MOTIONS)
    idx = 0
    for lista, cor_fam, secao in ((TITULOS, MARCA, None),
                                  (MOTIONS, CIANO, ("MOTIONS",
                                                    "PECA DE TELA CHEIA"))):
        if secao:
            por("sec-motions", c_secao(secao[0], secao[1], cor_fam, 33))
        for estilo, nome, familia, texto, sfx, vol, dur in lista:
            idx += 1
            d = _dur_sfx(sfx)
            spec = _moldura(idx, n_tot, nome, familia, estilo, sfx, d,
                            cor_fam, dur)
            tit = Title.from_dict({"startSec": 0, "endSec": dur,
                                   "style": estilo, "text": texto,
                                   # o stacked_reveal le o acento de ctx.color2;
                                   # e o unico que nao usa a constante do modulo
                                   "color2": MARCA})
            por(f"{idx:02d}-{estilo}", spec, tit,
                {"duracao": dur, "fundo": BG,
                 "camadas": _fundo_item(cor_fam, 100 + idx)})
            if d > 0:
                # o som entra junto com o titulo, nao antes
                sons.append((sfx, trechos[-1][4] + 0.06, vol))

    por("sec-sons", c_secao("SONS", "O EFEITO QUE CASA COM O GESTO", VERDE, 35))
    por("gavetas", c_sons())
    por("fecho", c_fecho())
    return trechos, sons, t


def renderizar(trechos, total, com_som=True, sons=None) -> Path:
    n = int(total * FPS)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    mudo = SAIDA.with_name("_acervo_mudo.mp4")
    p = subprocess.Popen(
        [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", str(mudo)], stdin=subprocess.PIPE)

    reg = FontRegistry()
    prontos = []
    for nome, fundo, spec, tit, a, b in trechos:
        cf = Cena(fundo, W, H, FPS) if fundo else None
        cm = Cena(spec, W, H, FPS)
        tr = TitleRenderer(tit, W, H, float(FPS), registry=reg) if tit else None
        prontos.append((cf, cm, tr, a, b))

    surface, fechar = superficie(W, H)
    canvas = surface.getCanvas()
    print(f"  desenhando na {onde()}", flush=True)
    buf = np.empty((H, W, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType,
                               skia.kPremul_AlphaType)
    t0 = time.time()
    for f in range(n):
        t = f / FPS
        canvas.clear(skia.Color4f(0.02, 0.02, 0.03, 1))
        for cf, cm, tr, a, b in prontos:
            if not (a <= t < b):
                continue
            rel = t - a
            if cf:
                cf.desenhar(canvas, rel)          # o fundo
            if tr:
                tr.draw_frame(canvas, rel * FPS)  # o TITULO DE VERDADE
            cm.desenhar(canvas, rel)              # a moldura por cima
            break
        fechar()
        surface.readPixels(info, buf, W * 4, 0, 0)
        p.stdin.write(buf.tobytes())
        if f % 150 == 0:
            print(f"  {f}/{n} ({f * 100 // max(1, n)}%)", flush=True)
    p.stdin.close()
    p.wait()
    print(f"[Acervo] {n} frames em {time.time() - t0:.1f}s")

    if not com_som or not sons:
        mudo.replace(SAIDA)
        return SAIDA
    return mixar(mudo, sons)


def mixar(video: Path, sons: list) -> Path:
    """Poe cada SFX no seu instante. `adelay` desloca, `amix` soma.

    `dropout_transition` alto e `normalize=0` porque o padrao do amix ABAIXA o
    volume geral a cada entrada nova — o catalogo ficaria com o primeiro som
    alto e o resto sumindo.
    """
    entradas, filtros, rotulos = ["-i", str(video)], [], []
    for k, (rel, offset, vol) in enumerate(sons):
        entradas += ["-i", str(SFX_DIR / rel)]
        ms = int(offset * 1000)
        filtros.append(f"[{k + 1}:a]adelay={ms}|{ms},volume={vol}[s{k}]")
        rotulos.append(f"[s{k}]")
    filtros.append(f"{''.join(rotulos)}amix=inputs={len(sons)}:"
                   f"normalize=0:dropout_transition=0[mix]")
    cmd = ([FFMPEG, "-y", "-v", "error"] + entradas
           + ["-filter_complex", ";".join(filtros),
              "-map", "0:v", "-map", "[mix]", "-c:v", "copy",
              "-c:a", "aac", "-b:a", "192k", "-shortest", str(SAIDA)])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("  mixagem falhou:", (r.stderr or "")[-400:])
        video.replace(SAIDA)
    else:
        video.unlink(missing_ok=True)
        print(f"[Acervo] {len(sons)} sons mixados")
    return SAIDA


if __name__ == "__main__":
    _acento_da_marca()
    trechos, sons, total = montar()

    erros = 0
    for nome, fundo, spec, tit, a, b in trechos:
        e = validar(spec) + (validar(fundo) if fundo else [])
        if e:
            erros += 1
            print(f"  {nome:18} {e[0][:80]}")
    print(f"  {len(trechos)} trechos · {len(sons)} sons · {total:.1f}s"
          f" · {erros} com erro")
    if erros:
        sys.exit(1)

    if "--stills" in sys.argv:
        pasta = RAIZ / "output" / "_acervo"
        pasta.mkdir(parents=True, exist_ok=True)
        reg = FontRegistry()
        for nome, fundo, spec, tit, a, b in trechos:
            surf = skia.Surface(W, H)
            c = surf.getCanvas()
            c.clear(skia.Color4f(0.02, 0.02, 0.03, 1))
            rel = (b - a) * 0.62
            if fundo:
                Cena(fundo, W, H, FPS).desenhar(c, rel)
            if tit:
                TitleRenderer(tit, W, H, float(FPS),
                              registry=reg).draw_frame(c, rel * FPS)
            Cena(spec, W, H, FPS).desenhar(c, rel)
            surf.makeImageSnapshot().save(str(pasta / f"{nome}.png"))
        print(f"  provas em {pasta}")
    else:
        renderizar(trechos, total, "--mudo" not in sys.argv, sons)
