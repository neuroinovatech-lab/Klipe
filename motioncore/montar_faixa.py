# -*- coding: utf-8 -*-
"""
montar_faixa.py — motions compostos PARA a faixa do split (1080x960).

Antes eu recortava um pedaco da prancha 1080x1920 e encaixava na faixa. Sempre
comprometia: ou pegava margem vazia, ou cortava titulo ao meio. Composicao
espremida nao e composicao.

Aqui cada motion nasce no tamanho da faixa. Mesma linguagem da prancha — papel,
tinta, buril, serifa — em outro formato. E o teste util do scene graph: se o
DSL so servisse a um formato, ele nao seria um motor, seria um template.

TERCEIRA VERSAO — O QUE ESTAVA ERRADO NA SEGUNDA
------------------------------------------------
A segunda consertou o movimento (a primeira parava numa pose) mas saiu BASICA,
e o diagnostico dela foi exato. Eu tinha guardado o formato e o gesto da
prancha e jogado fora o CONTEUDO: onde a prancha tem anel de medida, marca de
escala, setor gravado a buril abrindo em `varre_grau`, chamada em cotovelo e
rotulo em italico, a faixa tinha campo de quadradinho e campo de circulo. Grade
de quadrado nao e uma prancha em escala menor — e um padrao generico que
caberia em qualquer peca.

O que faz uma prancha ler como prancha nao e densidade, e APARELHO DE MEDIDA:
a figura vem cercada de anel, marca e chamada, e o rotulo APONTA em vez de
ficar do lado. Entao esta versao traz o vocabulario de `montar_prancha` inteiro
— os mesmos helpers, os mesmos rotulos que ela fala — reduzido de r=452 pra
r~150, que e o que cabe aqui.

A GRAMATICA DA FAIXA
--------------------
Tres registros empilhados, e o eixo continua sendo o horizontal (1080x960 e
largo e baixo; gesto vertical bate na borda antes de virar leitura):

    y +230 .. +60   o campo que ATRAVESSA — o especime passando
    y  +30          a linha de base medida — o instrumento, PARADO
    y  -40 .. -340  a figura medida + chamada + rotulo em italico
    y -380 .. -440  o titulo

Parado contra movel e o par que faz os dois lerem: se tudo anda, nada anda.

DUAS COISAS QUE CUSTARAM DESENHO
--------------------------------
1. `repetir` desloca o tempo LOCAL de cada copia pelo `atraso` — e por isso que
   a grade le como onda e nao como bloco. Mas isso vale pra TODO valor animado
   da camada, `x` inclusive: deriva declarada na propria grade nao a translada,
   ela a CISALHA. A esteira mora num `grupo` por fora, que resolve no tempo
   real da cena, e a onda continua por dentro.

2. O teto da composicao e o `FUSAO = 250` do split, nao gosto: a mascara sobe
   de alpha 0 a 255 nos primeiros 250 px da faixa, entao tudo acima de y 250
   (centrado: 230) sai lavado. De quebra isso tira a banda de cima da legenda
   queimada do video (y 1330-1510 no original) — efeito colateral, nao motivo.

    python -m motioncore.montar_faixa
"""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import skia

from .cena import Cena, validar

RAIZ = Path(__file__).resolve().parent.parent
PROJ = RAIZ / "public" / "projects" / "eli-prancha"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

W, H, FPS = 1080, 960, 30

# ── modo CAMADA ──────────────────────────────────────────────────────────
# `--overlay` troca "split" por "transparência": em vez de o papel TAPAR a
# metade de baixo, ele vira uma folha translúcida por cima do vídeo dela, que
# continua correndo atrás. A gravura some do caminho da imagem sem deixar de
# ser gravura — e nada precisa ser refeito, é a mesma cena com outro fundo.
#
# Sai no formato lado-a-lado (cor | alpha), o mesmo dos blocos da prancha: o
# ffmpeg aqui não grava alpha de verdade em h264, então o alpha vira meia
# imagem em tons de cinza e o shader do player remonta.
OVERLAY = "--overlay" in sys.argv

W_OVER, H_OVER = 1080, 1920      # a camada ocupa o quadro inteiro
FAIXA_TOPO = H_OVER - H          # 960 — a prancha vive na metade de baixo
# A transparência serve pra ONDE ELA APARECE, não pro papel. Deixei em 0,62 na
# primeira tentativa e a folha inteira virou vidro: ela aparecia através do
# diagrama todo e o quadro leu como reflexo, não como prancha. O papel volta a
# ser papel — o que a camada resolve não é a opacidade, é não ter vídeo assado
# dentro do arquivo. Baixe daqui se algum dia quiser a folha meio vazada.
PAPEL_ALFA = 1.0
FUSAO_TOPO = 220                 # a emenda com a imagem dela desaparece num
                                 # degradê, como fazia a máscara do split

PAPEL = "#C7A978"
PAPEL_CLARO = "#D8C092"
PRETO = "#1E1A16"
MARROM = "#34281C"
CINZA = "#625847"
DOURADO = "#90713F"
VERMELHO = "#8F1D18"
VERMELHO_ESC = "#68120F"
GARAMOND = "CormorantGaramond"
SERIF = "PlayfairDisplay"

TETO = 230        # onde a folha ja e opaca (ver FUSAO=250 no split)
BASE = 30         # a linha de base medida
FIG_X, FIG_Y = -334, -186     # a figura medida, a esquerda
CAMPO_Y = 142                 # o centro do campo que atravessa


# ── tempo ────────────────────────────────────────────────────────────────
def surge(t0, dur=0.6):
    return [[t0, 0], [t0 + dur, 1, "inOutCubic"]]


def desenha(t0, dur=0.9):
    """Traco progressivo — a pena tecnica correndo sobre a folha."""
    return [[t0, 0], [t0 + dur, 1, "inOutCubic"]]


def esteira(dur, vel, x0=0.0):
    """`x` continuo a `vel` px/s (sinal = direcao) do primeiro ao ultimo frame.

    Linear de proposito. Esteira que acelera e freia denuncia que e um loop, e
    o olho para de ler travessia e passa a ler animacao.
    """
    return [[0.0, x0, "linear"], [dur, x0 + vel * dur, "linear"]]


def pulso(dur, periodo, lo, hi, de=None):
    """Oscila lo<->hi sem nunca assentar. `de` e o valor de partida — passe 0
    pra camada nascer do nada (util com `repetir`, que joga as copias do fim da
    fila pra tempo local negativo, onde o keyframe segura este primeiro valor).

    O ultimo keyframe cai depois de `dur` porque keyframe segura o valor da
    ponta: se o ciclo terminasse dentro da cena, os ultimos frames congelariam.
    """
    ks = [[0.0, hi if de is None else de, "inOutSine"]]
    alvo = hi if de is not None else lo
    t = 0.0
    while t <= dur:
        t += periodo / 2.0
        ks.append([round(t, 3), alvo, "inOutSine"])
        alvo = lo if alvo == hi else hi
    return ks


def varre(dur, x0, x1, travessia):
    """Vai-e-volta entre `x0` e `x1`, `travessia` segundos por ida."""
    ks = [[0.0, x0, "inOutSine"]]
    alvo, t = x1, 0.0
    while t <= dur:
        t += travessia
        ks.append([round(t, 3), alvo, "inOutSine"])
        alvo = x0 if alvo == x1 else x1
    return ks


def gira(dur, de, quanto):
    """Angulo que avanca sem parar — pro setor varrer como instrumento."""
    return [[0.0, de, "linear"], [dur, de + quanto, "linear"]]


# ── material ─────────────────────────────────────────────────────────────
def folha():
    # semente diferente da prancha: duas folhas identicas lado a lado no mesmo
    # video denunciariam que e a mesma textura repetida
    c = {"tipo": "textura", "cor": PAPEL, "grao": 0.05, "manchas": 6,
         "vinheta": 0.42, "falhas": 14, "semente": 2027}
    if OVERLAY:
        # só o PAPEL fica translúcido. A tinta (marcas, anéis, buril, serifa)
        # continua cheia — gravura lavada não lê como gravura, lê como erro.
        c["opacidade"] = PAPEL_ALFA
    return c


# ── o vocabulario da prancha, em escala de faixa ─────────────────────────
def anel(raio, t0, x=0, y=0, larg=1.3, cor=MARROM, de=-90, varre_=360,
         dur=0.9, **extra):
    c = {"tipo": "elipse", "raio": raio, "de_grau": de, "varre_grau": varre_,
         "contorno": cor, "contorno_larg": larg, "x": x, "y": y,
         "traco": desenha(t0, dur), "opacidade": surge(t0, 0.2),
         "inicio": t0 - 0.05}
    c.update(extra)
    return c


def marcas(raio, n, t0, x=0, y=0, alt=10, cor=MARROM, passo=0.014, **extra):
    """As marcas de escala em volta da figura.

    E o unico item desta lista que nao desenha nada de novo — e ainda assim e o
    que faz um circulo virar instrumento de medida em vez de circulo. Sem elas
    a figura e um desenho; com elas e uma leitura.
    """
    out = []
    for i in range(n):
        a = math.radians(i * 360.0 / n)
        c = {"tipo": "retangulo", "larg": 1.7, "alt": alt, "cor": cor,
             "x": x + math.cos(a) * raio, "y": y + math.sin(a) * raio,
             "rotacao": -i * 360.0 / n + 90,
             "opacidade": surge(t0 + i * passo, 0.3),
             "inicio": t0 + i * passo - 0.05}
        c.update(extra)
        out.append(c)
    return out


def setor(r_ext, r_int, de, varre_, t0, x=0, y=0, cor=PRETO, passo=0.55,
          op_hach=0.85, dur=0.9, **extra):
    """Setor preenchido a BURIL, nao a cor chapada — e o que da a gravura."""
    c = {"tipo": "elipse", "raio": r_ext, "raio_int": r_int, "de_grau": de,
         "x": x, "y": y,
         "varre_grau": [[t0, 0.5], [t0 + dur, varre_, "inOutCubic"]],
         "hachura": {"modo": "radial", "passo": passo, "cor": cor,
                     "opacidade": op_hach, "largura": 0.8, "r0": r_int},
         "opacidade": surge(t0, 0.3), "inicio": t0 - 0.05}
    c.update(extra)
    return c


def chamada(d, x, y, t0, cor=VERMELHO, larg=1.5):
    """Chamada em cotovelo — a linha que liga a figura ao rotulo.

    Sem ela o rotulo esta AO LADO do desenho; com ela ele APONTA. E a diferenca
    entre legenda e prancha, e custa uma camada.
    """
    return {"tipo": "path", "d": d, "centrar": False, "x": x, "y": y,
            "contorno": cor, "contorno_larg": larg,
            "traco": desenha(t0, 0.6), "opacidade": surge(t0, 0.2),
            "inicio": t0 - 0.05}


def base_medida(t0=0.1, y=BASE, cols=13, espX=84, cor=MARROM):
    """A linha de base com marcas. Fica PARADA enquanto o campo atravessa —
    numa prancha o instrumento nao anda junto com o que ele mede."""
    return [
        {"tipo": "linha", "de": [-(W / 2 - 38), 0], "para": [W / 2 - 38, 0],
         "y": y, "contorno": cor, "contorno_larg": 1.5,
         "traco": desenha(t0, 0.8), "opacidade": surge(t0, 0.2)},
        {"tipo": "retangulo", "larg": 1.6, "alt": 15, "cor": cor, "y": y - 9,
         "repetir": {"cols": cols, "linhas": 1, "espX": espX, "atraso": 0.022},
         "opacidade": surge(t0 + 0.25, 0.35)},
    ]


def rotulo(txt, t0, x, y, tam=32, cor=MARROM, larg=0.36):
    """Rotulo de prancha: italico, pequeno, discreto. Nunca compete."""
    return {"tipo": "texto", "texto": txt, "fonte": GARAMOND, "peso": 400,
            "italico": True, "tamanho": tam, "cor": cor, "y": y, "x": x,
            "largura_max": W * larg, "entrelinha": 1.18,
            "opacidade": surge(t0, 0.6), "inicio": t0 - 0.05}


def titulo(txt, t0, y, tam=50, cor=MARROM, esp=10, x=0, larg=0.86):
    # o titulo NAO deriva: numa prancha a etiqueta e o referencial parado contra
    # o qual o campo anda. Rotulo que anda junto zera a leitura de movimento.
    return {"tipo": "texto", "texto": txt, "fonte": GARAMOND, "peso": 700,
            "tamanho": tam, "cor": cor, "espacamento": esp, "y": y, "x": x,
            "largura_max": W * larg, "opacidade": surge(t0), "inicio": t0 - 0.05}


# ═══════════════════════════════════════════════════════════════════════════
def cena_sensorial(dur=4.0) -> dict:
    """"Processamento de informacoes sensoriais" — o campo passa pelo aparelho.

    A rosacea a esquerda e o cortex da prancha reduzido de r=452 pra r=150: os
    mesmos aneis concentricos, as mesmas marcas de escala, o mesmo setor a
    buril. So que aqui o setor NAO assenta depois de abrir — ele segue varrendo
    devagar em `de_grau`, que e o que um instrumento faz.
    """
    giro = gira(dur, 138, 46)
    cs = [folha()]
    cs += base_medida(0.1)
    cs.append({  # o campo que atravessa
        "tipo": "grupo", "x": esteira(dur, -44), "camadas": [{
            "tipo": "retangulo", "larg": 22, "alt": 22, "cor": MARROM,
            "y": CAMPO_Y,
            # 25 x 74 = 1776 de vao: sobra 348 de cada lado contra 176 de
            # deriva, entao a borda nunca fica a descoberto
            "repetir": {"cols": 25, "linhas": 3, "espX": 74, "espY": 62,
                        "atraso": 0.010, "ordem": "linha"},
            "escala": pulso(dur, 1.15, 0.55, 1.0, de=0),
            "opacidade": pulso(dur, 1.15, 0.45, 0.80, de=0)}]})
    cs.append({  # o indice: cursor de leitura correndo sobre o campo
        "tipo": "linha", "de": [0, -96], "para": [0, 96], "y": CAMPO_Y,
        "x": varre(dur, -540, 540, 1.7),
        "contorno": VERMELHO, "contorno_larg": 1.6,
        "opacidade": surge(0.45, 0.4)})
    # a figura medida
    cs += [anel(46, 0.45, FIG_X, FIG_Y, larg=1.0, dur=0.6),
           anel(90, 0.70, FIG_X, FIG_Y, larg=1.0, dur=0.7),
           anel(134, 0.95, FIG_X, FIG_Y, larg=1.7, dur=0.8)]
    cs += marcas(150, 24, 1.25, FIG_X, FIG_Y)
    cs += [
        setor(134, 78, giro, 74, 1.75, FIG_X, FIG_Y),
        anel(134, 1.75, FIG_X, FIG_Y, larg=1.9, cor=PRETO, de=giro, varre_=74,
             dur=0.7),
        anel(78, 1.85, FIG_X, FIG_Y, larg=1.9, cor=PRETO, de=giro, varre_=74,
             dur=0.7),
        # a chamada e o rotulo tem que ASSENTAR dentro da janela, nao chegar
        # nela: rotulo que so fica legivel no ultimo decimo de um clipe de 4s
        # nao foi lido por ninguem
        chamada("M0,0 L84,-62 L292,-62", FIG_X + 134, FIG_Y, 2.25),
        rotulo("o córtex temporal\ndistingue as formas", 2.55,
               x=FIG_X + 486, y=FIG_Y + 62, tam=34),
        titulo("SENSORIAL", 1.5, y=-402, tam=50),
    ]
    return {"duracao": dur, "camadas": cs}


def cena_irregularidade(dur=4.0) -> dict:
    """"...e identificacao de irregularidades" — achar, depois ampliar.

    Dois registros, que e como uma prancha de verdade trata uma anomalia: no
    campo o anel FLAGRA o intruso (e viaja junto com ele, senao marcaria um
    ponto do quadro em vez de marcar o elemento); a esquerda a figura de
    detalhe o mostra ampliado e parado, pra poder ser lido.
    """
    lin_y = CAMPO_Y - 62      # a fileira do intruso, no reticulado das linhas
    col_x = 264               # cruza o centro por volta de 2,9s
    cs = [folha()]
    cs += base_medida(0.1)
    cs.append({
        "tipo": "grupo", "x": esteira(dur, -92), "camadas": [
            {"tipo": "retangulo", "larg": 26, "alt": 26, "cor": MARROM,
             "y": CAMPO_Y,
             # 23 x 90 = 1980 de vao contra 368 de deriva
             "repetir": {"cols": 23, "linhas": 3, "espX": 90, "espY": 62,
                         "atraso": 0.011, "ordem": "linha"},
             "escala": pulso(dur, 1.4, 0.80, 1.0, de=0),
             "opacidade": pulso(dur, 1.4, 0.48, 0.70, de=0)},
            {"tipo": "retangulo", "larg": 38, "alt": 38, "cor": VERMELHO,
             "x": col_x, "y": lin_y,
             # giro continuo e linear: o unico elemento do quadro que nunca
             # coincide com a ordem dos outros, em nenhum frame
             "rotacao": [[0, 0, "linear"], [dur, 200, "linear"]],
             "escala": pulso(dur, 0.9, 0.92, 1.12, de=0),
             "opacidade": surge(0.3, 0.4)},
            {"tipo": "elipse", "raio": pulso(dur, 1.0, 58, 70),
             "x": col_x, "y": lin_y, "contorno": VERMELHO,
             "contorno_larg": 2.0, "traco": desenha(1.55, 0.5),
             "opacidade": surge(1.5, 0.25), "inicio": 1.5},
        ]})
    # a figura de detalhe: o mesmo elemento, ampliado e cercado de medida
    cs += [anel(122, 1.95, FIG_X, FIG_Y, larg=1.7, cor=VERMELHO, dur=0.7)]
    cs += marcas(138, 20, 2.2, FIG_X, FIG_Y, cor=VERMELHO_ESC)
    cs += [
        {"tipo": "retangulo", "larg": 74, "alt": 74, "cor": VERMELHO,
         "x": FIG_X, "y": FIG_Y,
         "rotacao": [[0, 0, "linear"], [dur, 132, "linear"]],
         "escala": [[2.05, 0], [2.55, 1, "inOutCubic"]], "inicio": 2.0},
        chamada("M0,0 L84,-62 L292,-62", FIG_X + 122, FIG_Y, 2.6),
        rotulo("o que sai do padrão\nsalta primeiro aos olhos", 2.85,
               x=FIG_X + 486, y=FIG_Y + 62, tam=34, cor=VERMELHO),
        titulo("IRREGULARIDADE", 2.35, y=-402, tam=46, cor=VERMELHO, esp=8),
    ]
    return {"duracao": dur, "camadas": cs}


def cena_dualidade(dur=3.8) -> dict:
    """"De inocente para sensitiva em segundos" — duas ordens se cruzando.

    Em cima os dois campos correm em sentidos contrarios e passam um pelo
    outro: o contraste vira evento continuo, nao dois grupos parados lado a
    lado. Embaixo a legenda medida — um especime de cada tipo, cercado de
    escala, com o rotulo da propria prancha — e a TRAVESSIA de um pro outro,
    que e literalmente o que ela diz.
    """
    cs = [folha()]
    cs += base_medida(0.1)
    cs.append({"tipo": "linha", "de": [0, -(TETO - BASE) / 2 - 16],
               "para": [0, (TETO - BASE) / 2 + 16], "y": (TETO + BASE) / 2,
               "contorno": MARROM, "contorno_larg": 1.3,
               "traco": desenha(0.25, 0.6), "opacidade": surge(0.25, 0.2)})
    # Densidade e o assunto aqui. Com passo 120 e raio 44 as circunferencias se
    # comiam e o quadro virava textura, onde nao se le "duas ordens se
    # cruzando", se le ruido. E com o MESMO passo nos dois campos elas travavam
    # em pares verticais e voltavam a ler como uma textura so — dai os passos
    # incomensuraveis (150 e 178), que fazem a fase relativa deslizar.
    cs.append({  # os vazios, andando pra direita
        "tipo": "grupo", "x": esteira(dur, 64), "camadas": [{
            # espY 96 com os dois campos meia linha fora de fase deixa 48 de
            # folga vertical entre quaisquer dois circulos: raio 24 encosta sem
            # invadir. E o de baixo para em y 46, acima das marcas da regua —
            # antes o campo sentava em cima do instrumento.
            "tipo": "elipse", "raio": pulso(dur, 1.3, 19, 24), "y": 166,
            "contorno": CINZA, "contorno_larg": 1.5,
            "repetir": {"cols": 13, "linhas": 2, "espX": 150, "espY": 96,
                        "atraso": 0.030, "ordem": "linha"},
            "traco": desenha(0.6, 0.5),
            "opacidade": pulso(dur, 1.3, 0.55, 0.85, de=0)}]})
    cs.append({  # os gravados a buril, andando pra esquerda
        "tipo": "grupo", "x": esteira(dur, -64), "camadas": [{
            "tipo": "elipse", "raio": 23, "y": 118,
            "contorno": VERMELHO_ESC, "contorno_larg": 1.5,
            "repetir": {"cols": 11, "linhas": 2, "espX": 178, "espY": 96,
                        "atraso": 0.038, "ordem": "centro"},
            "hachura": {"modo": "paralela", "angulo": 34, "passo": 4,
                        "cor": VERMELHO_ESC, "opacidade": 0.75, "largura": 0.9},
            "opacidade": pulso(dur, 1.3, 0.60, 0.90, de=0)}]})
    # a legenda medida: um especime de cada tipo, com escala em volta
    esq, dir_, ly = -268, 268, -150
    cs += [{"tipo": "elipse", "raio": 34, "x": esq, "y": ly,
            "contorno": CINZA, "contorno_larg": 1.5,
            "traco": desenha(0.9, 0.5), "opacidade": surge(0.9, 0.25),
            "inicio": 0.85}]
    cs += marcas(48, 16, 1.15, esq, ly, alt=8, cor=CINZA)
    cs += [{"tipo": "elipse", "raio": 34, "x": dir_, "y": ly,
            "contorno": VERMELHO_ESC, "contorno_larg": 1.5,
            "hachura": {"modo": "paralela", "angulo": 34, "passo": 4,
                        "cor": VERMELHO_ESC, "opacidade": 0.75, "largura": 0.9},
            "opacidade": surge(1.9, 0.3), "inicio": 1.85}]
    cs += marcas(48, 16, 2.15, dir_, ly, alt=8, cor=VERMELHO_ESC)
    cs += [
        # a travessia — "em segundos" e o proprio movimento entre os dois
        {"tipo": "linha", "de": [-142, 0], "para": [142, 0], "y": ly,
         "contorno": VERMELHO, "contorno_larg": 2.2,
         "traco": desenha(2.1, 0.7), "opacidade": surge(2.1, 0.2),
         "inicio": 2.05},
        {"tipo": "path", "d": "M-22,-18 L11,0 L-22,18", "centrar": False,
         "x": 142, "y": ly, "contorno": VERMELHO, "contorno_larg": 2.2,
         "traco": desenha(2.7, 0.35), "opacidade": surge(2.7, 0.2),
         "inicio": 2.65},
        rotulo("em segundos", 2.95, x=0, y=ly + 62, tam=34, larg=0.30),
        titulo("INOCENTE", 1.25, y=-268, tam=42, cor=CINZA, esp=6,
               x=esq, larg=0.40),
        rotulo("não capta\no que se cala", 1.65, x=esq, y=-352, tam=30,
               cor=CINZA, larg=0.34),
        titulo("SENSITIVA", 2.15, y=-268, tam=42, cor=VERMELHO, esp=6,
               x=dir_, larg=0.40),
        rotulo("prevê o que\nestá por vir", 2.55, x=dir_, y=-352, tam=30,
               cor=VERMELHO, larg=0.34),
    ]
    return {"duracao": dur, "camadas": cs}


CENAS = [
    ("faixa_sensorial", cena_sensorial),
    ("faixa_irregularidade", cena_irregularidade),
    ("faixa_dualidade", cena_dualidade),
]


def renderizar_overlay(nome: str, spec: dict) -> Path:
    """A mesma cena, como CAMADA transparente de quadro inteiro."""
    erros = validar(spec)
    if erros:
        raise SystemExit(f"{nome}: " + "; ".join(erros))
    cena = Cena(spec, W, H, FPS)
    n = int(round(spec["duracao"] * FPS))
    saida = PROJ / f"{nome}_camada.mp4"
    p = subprocess.Popen(
        [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W_OVER}x{H_OVER}", "-r", str(FPS), "-i", "-",
         # `format=rgba` antes do split e obrigatorio: sem ele o alphaextract
         # falha com "Requested planes not available"
         "-filter_complex",
         "[0:v]format=rgba,split=2[c][a];"
         "[c]format=yuv420p[cc];[a]alphaextract,format=yuv420p[aa];"
         "[cc][aa]hstack=inputs=2[v]",
         "-map", "[v]", "-an",
         "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(saida)],
        stdin=subprocess.PIPE)

    surf = skia.Surface(W, H)
    canvas = surf.getCanvas()
    tira = np.empty((H, W, 4), dtype=np.uint8)
    # UNPREMUL de proposito: o `rgba` do ffmpeg e alpha DIRETO. Entregando o
    # premultiplicado do Skia, a cor ja viria multiplicada pelo alpha e o player
    # multiplicaria de novo — o papel a 0,62 sairia a 0,38 e a folha ficaria
    # suja. Com papel opaco isso nunca aparecia; translucido, aparece inteiro.
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType,
                               skia.kUnpremul_AlphaType)
    quadro = np.zeros((H_OVER, W_OVER, 4), dtype=np.uint8)   # topo transparente
    rampa = np.linspace(0.0, 1.0, FUSAO_TOPO, dtype=np.float32)[:, None]
    for f in range(n):
        canvas.clear(skia.Color4f(0, 0, 0, 0))   # transparente, nao preto
        cena.desenhar(canvas, f / FPS)
        surf.readPixels(info, tira, W * 4, 0, 0)
        # a emenda com a imagem dela morre num degrade, como a mascara do split
        tira[:FUSAO_TOPO, :, 3] = (tira[:FUSAO_TOPO, :, 3] * rampa).astype(np.uint8)
        quadro[FAIXA_TOPO:, :, :] = tira
        p.stdin.write(quadro.tobytes())
    p.stdin.close()
    p.wait()
    print(f"  {nome + '_camada':<24} {spec['duracao']:.1f}s  "
          f"{saida.stat().st_size/1e6:.1f} MB  (cor|alpha {W_OVER*2}x{H_OVER})")
    return saida


def renderizar(nome: str, spec: dict) -> Path:
    if OVERLAY:
        return renderizar_overlay(nome, spec)
    erros = validar(spec)
    if erros:
        raise SystemExit(f"{nome}: " + "; ".join(erros))
    cena = Cena(spec, W, H, FPS)
    n = int(round(spec["duracao"] * FPS))
    saida = PROJ / f"{nome}.mp4"
    p = subprocess.Popen(
        [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(saida)],
        stdin=subprocess.PIPE)
    surf = skia.Surface(W, H)
    canvas = surf.getCanvas()
    buf = np.empty((H, W, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType,
                               skia.kPremul_AlphaType)
    for f in range(n):
        canvas.clear(skia.Color4f(0, 0, 0, 1))
        cena.desenhar(canvas, f / FPS)
        surf.readPixels(info, buf, W * 4, 0, 0)
        p.stdin.write(buf.tobytes())
    p.stdin.close()
    p.wait()
    print(f"  {nome:<24} {spec['duracao']:.1f}s  {saida.stat().st_size/1e6:.1f} MB")
    return saida


def main() -> int:
    PROJ.mkdir(parents=True, exist_ok=True)
    for nome, fn in CENAS:
        renderizar(nome, fn())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
