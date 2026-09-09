# -*- coding: utf-8 -*-
"""
montar_prompt4.py — os quatro prompts de video, feitos pelo MOTOR.

Os prompts foram escritos para um gerador de video por IA (Veo). Custariam
US$ 28,80 e viriam com o que o modelo entendesse — cor aproximada, tempo
aproximado, e nenhuma chance de ajustar um detalhe sem gerar tudo de novo.

Aqui eles viram cena declarativa. Sai de graca, sai igual toda vez, e cada
valor e um numero que da para mexer: se o dourado estiver forte demais, muda
uma linha e re-renderiza em 30 segundos.

O que os prompts pediam, e como cada coisa foi feita:

  "messy lines and scattered dots snapping into        duas camadas: o caos
   perfect symmetrical patterns"                       sai, a grade entra

  "brain lateral view, temporal cortex lights up"      `path` com o contorno,
                                                       setor de elipse acende

  "split-screen: blurry organic left,                  `blur` animado de um
   sharp neon lines shooting right"                    lado, `escalaX` do outro

  "geometric eye of lines and nodes, breathing"        dois arcos + nos em
                                                       `repetir` radial

    python -m motioncore.montar_prompt4
    python -m motioncore.montar_prompt4 --stills
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
from .ffbin import ffmpeg as _ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "public" / "projects" / "eli-premiere" / "prompt4.mp4"
FFMPEG = _ffmpeg()

W, H, FPS = 1080, 1920, 30

# Paleta dos prompts, traduzida para hex. "dark charcoal", "electric blue",
# "neon purple", "amber gold", "soft blue".
CARVAO = "#16171C"
AZUL = "#2E6BFF"
ROXO = "#A855F7"
OURO = "#FFB020"
AZUL_SUAVE = "#7FB3FF"
BRANCO = "#F4F6FA"


# ══ CENA 1 — caos que vira padrao ═════════════════════════════════════
# "messy lines, scattered dots floating in chaos, suddenly snapping and
#  connecting into perfect symmetrical patterns and harmonious grids"
#
# O "snap" e o coracao da cena. Feito com dois tempos: o caos vive ate 3.2s e
# sai em 0.35s; a grade entra em 0.4s com `outBack`, que passa do ponto e volta
# — e o overshoot que o olho le como ENCAIXE, e nao como aparecimento.

def _caco(i: int, n: int) -> dict:
    """Uma linha torta do caos. Angulo e posicao derivam de `i` por uma
    progressao irracional (phi): espalha sem repetir e sem eu escolher a mao."""
    phi = 2.39996
    r = 120 + (i % 7) * 96
    a = i * phi
    x, y = r * math.cos(a), r * math.sin(a) * 1.5
    comp = 60 + (i % 5) * 44
    return {
        "tipo": "linha",
        "de": [-comp / 2, 0], "para": [comp / 2, 0],
        "x": x, "y": y,
        "rotacao": [[0, math.degrees(a) % 180],
                    [3.2, (math.degrees(a) % 180) + 18, "inOutCubic"]],
        "cor": ROXO if i % 3 else AZUL,
        "contorno_larg": 2,
        "opacidade": [[0, 0], [0.25 + (i % 9) * 0.045, 0.75],
                      [3.2, 0.75], [3.55, 0]],
        # deriva lenta: o caos nao fica parado, ele FLUTUA
        "escala": [[0, 0.9], [1.6, 1.08, "inOutCubic"], [3.2, 0.95, "inOutCubic"]],
    }


def cena1(dur: float) -> dict:
    caos = [_caco(i, 34) for i in range(34)]
    pontos_caos = [{
        "tipo": "elipse", "raio": 4, "cor": AZUL_SUAVE,
        "x": 300 * math.cos(i * 2.39996) * (1 + i % 3),
        "y": 210 * math.sin(i * 2.39996) * (1 + i % 4),
        "opacidade": [[0, 0], [0.2 + (i % 7) * 0.05, 0.9], [3.2, 0.9], [3.5, 0]],
    } for i in range(26)]

    # A grade que ENCAIXA. `atraso` com ordem `centro` faz o encaixe irradiar
    # do meio — sem ele os 117 pontos aparecem juntos e vira um bloco.
    grade = {
        "tipo": "elipse", "raio": 6, "cor": AZUL,
        "x": -468, "y": 312,
        "inicio": 3.3,
        "opacidade": [[3.3, 0], [3.45, 1]],
        "escala": [[3.3, 0], [3.62, 1, "outBack"]],
        "repetir": {"cols": 13, "linhas": 9, "espX": 78, "espY": 78,
                    "atraso": 0.022, "ordem": "centro"},
    }
    # as ligacoes: linhas horizontais que crescem DEPOIS dos pontos
    ligacoes = {
        "tipo": "retangulo", "larg": 78, "alt": 2, "cor": ROXO,
        "x": -429, "y": 312,
        "inicio": 3.7,
        "opacidade": [[3.7, 0], [3.9, 0.55]],
        "escalaX": [[3.7, 0], [4.05, 1, "outCubic"]],
        "repetir": {"cols": 12, "linhas": 9, "espX": 78, "espY": 78,
                    "atraso": 0.016, "ordem": "centro"},
    }
    verticais = {
        "tipo": "retangulo", "larg": 2, "alt": 78, "cor": ROXO,
        "x": -468, "y": 273,
        "inicio": 3.9,
        "opacidade": [[3.9, 0], [4.1, 0.4]],
        "escalaY": [[3.9, 0], [4.25, 1, "outCubic"]],
        "repetir": {"cols": 13, "linhas": 8, "espX": 78, "espY": 78,
                    "atraso": 0.016, "ordem": "centro"},
    }
    # respiro final: a grade inteira pulsa uma vez, como quem assentou
    pulso = {
        "tipo": "elipse", "raio": 520, "cor": "#00000000",
        "contorno": AZUL, "contorno_larg": 2,
        "inicio": 4.4,
        "escala": [[4.4, 0.55], [5.6, 1.25, "outCubic"]],
        "opacidade": [[4.4, 0.5], [5.6, 0]],
    }
    return {"duracao": dur, "fundo": CARVAO,
            "camadas": caos + pontos_caos + [grade, ligacoes, verticais, pulso]}


# ══ CENA 2 — o cortex temporal ════════════════════════════════════════
# "stylized 2D brain lateral view, temporal cortex lights up and pulses with
#  warm amber-gold glow, data particles flow in, organizing into linear rows"
#
# O cerebro e um `path` SVG. Desenhado de perfil, virado para a direita, com o
# lobo temporal na parte de baixo-frente — que e onde o setor dourado acende.

CEREBRO = (
    "M 250 40 C 340 40 405 95 415 165 C 470 185 480 250 445 290 "
    "C 455 340 420 385 365 395 C 340 430 285 445 240 430 "
    "C 195 450 140 435 118 395 C 60 390 25 340 40 285 "
    "C 5 245 15 180 70 160 C 82 90 155 40 250 40 Z"
)
# os sulcos: dois tracos internos que dao cara de cerebro sem virar ilustracao
SULCO_A = "M 120 175 C 175 150 235 165 265 205 C 300 250 275 300 225 315"
SULCO_B = "M 330 130 C 365 175 355 235 315 265 C 285 288 300 330 340 345"


def cena2(dur: float) -> dict:
    return {"duracao": dur, "fundo": CARVAO, "camadas": [
        # halo de fundo: da o "professional lighting" sem lampada nenhuma
        {"tipo": "elipse", "raio": 620, "y": 40,
         "cor": {"tipo": "radial", "cores": ["#1E2A44", CARVAO], "raio": 620},
         "opacidade": [[0, 0], [1.2, 1]]},

        # o contorno que se DESENHA. `contorno` (nao preenchimento) porque
        # `traco` corre o traço — anel preenchido nao tem o que correr.
        {"tipo": "path", "d": CEREBRO, "cor": "#00000000",
         "contorno": AZUL_SUAVE, "contorno_larg": 3, "escala": 1.6, "y": 60,
         "traco": [[0, 0], [2.4, 1, "outCubic"]],
         "opacidade": [[0, 0], [0.2, 1]]},
        {"tipo": "path", "d": SULCO_A, "cor": "#00000000",
         "contorno": AZUL_SUAVE, "contorno_larg": 2, "escala": 1.6, "y": 60,
         "opacidade": [[1.4, 0], [2.0, 0.55]],
         "traco": [[1.4, 0], [3.0, 1, "outCubic"]]},
        {"tipo": "path", "d": SULCO_B, "cor": "#00000000",
         "contorno": AZUL_SUAVE, "contorno_larg": 2, "escala": 1.6, "y": 60,
         "opacidade": [[1.7, 0], [2.3, 0.55]],
         "traco": [[1.7, 0], [3.3, 1, "outCubic"]]},

        # o lobo temporal acendendo: setor dourado embaixo-frente
        {"tipo": "elipse", "raio": 250, "raio_int": 120, "cor": OURO,
         "x": 60, "y": -110,
         "de_grau": 152, "varre_grau": [[2.6, 0], [3.8, 74, "outCubic"]],
         "opacidade": [[2.6, 0], [3.0, 0.85], [dur - 1.0, 0.85], [dur, 0.5]]},
        # o brilho: mesma forma, borrada, atras
        {"tipo": "elipse", "raio": 250, "raio_int": 120, "cor": OURO,
         "x": 60, "y": -110, "blur": 34,
         "de_grau": 152, "varre_grau": [[2.6, 0], [3.8, 74, "outCubic"]],
         "opacidade": [[2.6, 0], [3.2, 0.55],
                       [4.6, 0.25], [6.0, 0.55], [7.4, 0.25], [8.8, 0.55]]},

        # as particulas de dado ENTRANDO e se organizando em fileiras.
        # A armadilha do `repetir`: animar `x` na propria grade CISALHA em vez
        # de transladar, porque cada copia le o `x` num instante diferente.
        # Por isso a entrada e por `opacidade` + `escalaX`, e nao por deriva.
        {"tipo": "retangulo", "larg": 46, "alt": 4, "raio": 2, "cor": OURO,
         # x=0: o `repetir` CENTRA a grade na posicao da camada, nao parte
         # dela. Com x=-300 a fileira comecava fora do quadro pela esquerda.
         "x": 0, "y": -560, "inicio": 4.2,
         "opacidade": [[4.2, 0], [4.5, 0.9]],
         "escalaX": [[4.2, 0.05], [4.8, 1, "outCubic"]],
         "repetir": {"cols": 9, "linhas": 5, "espX": 76, "espY": 44,
                     "atraso": 0.045, "ordem": "linha"}},
    ]}


# ══ CENA 3 — a dualidade ══════════════════════════════════════════════
# "split-screen: left blurry distorted organic shapes floating (confusion),
#  right sharp precise neon lines shooting forward like a timeline"

def cena3(dur: float) -> dict:
    esquerda = []
    for i in range(7):
        a = i * 2.39996
        esquerda.append({
            "tipo": "elipse",
            "rx": 90 + (i % 3) * 46, "ry": 120 + (i % 4) * 38,
            "x": -270 + 60 * math.cos(a),
            "y": 520 - i * 150 + 40 * math.sin(a),
            "cor": AZUL_SUAVE,
            # `blur` NAO e animavel — a tabela do DSL marca "nao" e o codigo le
            # com float() direto. O validador deixou passar (ele confere o nome
            # do campo, nao se aquele campo aceita keyframes), e o erro so
            # apareceu no render. A distorcao "respirando" vem da `escala` e da
            # `rotacao`, que sao animaveis; o borrao fica fixo por forma.
            "blur": 30 + (i % 3) * 10,
            "opacidade": [[0, 0], [0.6 + i * 0.12, 0.30]],
            "rotacao": [[0, i * 24], [dur, i * 24 + 40, "inOutCubic"]],
            "escala": [[0, 0.92], [dur / 2, 1.1, "inOutCubic"], [dur, 0.95, "inOutCubic"]],
        })

    direita = [{
        # as linhas que DISPARAM. `escalaX` de 0 a 1 com `outExpo` e o gesto:
        # comeca violento e assenta, que e como se le "previsao".
        "tipo": "retangulo", "larg": 420, "alt": 3, "raio": 2, "cor": AZUL,
        "x": 300, "y": 560, "inicio": 0.5,
        "opacidade": [[0.5, 0], [0.75, 0.95]],
        "escalaX": [[0.5, 0], [1.15, 1, "outExpo"]],
        "repetir": {"cols": 1, "linhas": 11, "espX": 0, "espY": 108,
                    "atraso": 0.14, "ordem": "linha"},
    }, {
        # os nos na ponta: onde cada previsao "chega"
        "tipo": "elipse", "raio": 7, "cor": BRANCO,
        "x": 510, "y": 560, "inicio": 0.9,
        "opacidade": [[0.9, 0], [1.1, 1]],
        "escala": [[0.9, 0], [1.35, 1, "outBack"]],
        "repetir": {"cols": 1, "linhas": 11, "espX": 0, "espY": 108,
                    "atraso": 0.14, "ordem": "linha"},
    }]

    divisor = {
        "tipo": "retangulo", "larg": 2, "alt": [[0, 0], [1.4, 1500, "outCubic"]],
        "cor": "#3A4152", "x": 0,
        "opacidade": [[0, 0], [0.5, 0.7], [dur - 1.2, 0.7], [dur - 0.2, 0]],
    }
    return {"duracao": dur, "fundo": CARVAO,
            "camadas": esquerda + [divisor] + direita}


# ══ CENA 4 — o olho ═══════════════════════════════════════════════════
# "single geometric icon of a glowing eye made of lines and nodes, centered,
#  gently breathes and pulses in an elegant loop, fading into a soft glow"
#
# O amendoado sai de dois arcos espelhados. Um `path` seria mais direto, mas
# arco de elipse anima o `varre_grau` — e e isso que faz o olho ABRIR.

def cena4(dur: float) -> dict:
    def arco(sinal: int, atraso: float) -> dict:
        return {
            "tipo": "elipse", "rx": 330, "ry": 330, "cor": "#00000000",
            "contorno": OURO, "contorno_larg": 3,
            "y": sinal * -238,
            "de_grau": 20 if sinal > 0 else 200,
            "varre_grau": [[atraso, 0], [atraso + 1.1, 140, "outCubic"]],
            "opacidade": [[atraso, 0], [atraso + 0.2, 1]],
        }

    # Os "nodes" do prompt vao no CONTORNO do amendoado, um a um. Com
    # `repetir` viravam uma fileira reta que atravessava o olho e vazava pela
    # esquerda — a grade se CENTRA na camada, e o espacamento e sempre em linha
    # ou coluna. Contorno curvo pede posicao calculada.
    _CONTORNO = [(335, 0), (302, 265), (209, 477), (75, 595), (-75, 595), (-209, 477), (-302, 265), (-335, 0), (-302, -265), (-209, -477), (-75, -595), (75, -595), (209, -477), (302, -265)]
    nos = [{
        "tipo": "elipse", "raio": 6, "cor": OURO,
        "x": px, "y": py,
        "opacidade": [[1.2 + k * 0.045, 0], [1.45 + k * 0.045, 0.95]],
        "escala": [[1.2 + k * 0.045, 0], [1.72 + k * 0.045, 1, "outBack"]],
    } for k, (px, py) in enumerate(_CONTORNO)]

    # a iris: circulo + anel, respirando
    respiro = [[0, 1], [2.2, 1.07, "inOutCubic"], [4.4, 1, "inOutCubic"],
               [6.6, 1.07, "inOutCubic"], [8.8, 1, "inOutCubic"]]
    return {"duracao": dur, "fundo": CARVAO, "camadas": [
        {"tipo": "elipse", "raio": 420, "blur": 60,
         "cor": {"tipo": "radial", "cores": ["#3A2A08", CARVAO], "raio": 420},
         "opacidade": [[0.6, 0], [1.6, 1], [dur - 1.4, 1], [dur, 0]]},
        {"tipo": "grupo", "escala": respiro, "camadas": [
            arco(+1, 0.2), arco(-1, 0.45), *nos,
            {"tipo": "elipse", "raio": 96, "cor": "#00000000",
             "contorno": OURO, "contorno_larg": 3,
             "escala": [[1.5, 0], [2.1, 1, "outBack"]],
             "opacidade": [[1.5, 0], [1.8, 1]]},
            {"tipo": "elipse", "raio": 34, "cor": OURO,
             "escala": [[1.9, 0], [2.4, 1, "outBack"]],
             "opacidade": [[1.9, 0], [2.2, 1]]},
            {"tipo": "elipse", "raio": 34, "cor": OURO, "blur": 26,
             "opacidade": [[2.2, 0.6], [4.4, 0.25, "inOutCubic"],
                           [6.6, 0.6, "inOutCubic"], [8.8, 0.25, "inOutCubic"]]},
        ]},
        # o fecho: tudo se dissolve num brilho
        {"tipo": "elipse", "raio": 700, "cor": OURO, "blur": 90,
         "opacidade": [[dur - 1.6, 0], [dur - 0.5, 0.18], [dur, 0]]},
    ]}


# ══ montagem ══════════════════════════════════════════════════════════
# Os tempos vieram dos proprios prompts.
CENAS = [
    ("1 · caos vira padrao", cena1, 0.0, 14.0),
    ("2 · cortex temporal", cena2, 14.0, 36.0),
    ("3 · dualidade", cena3, 36.0, 61.0),
    ("4 · o olho", cena4, 61.0, 70.0),
]


def montar():
    return [(fn(round(t1 - t0, 3)), t0, t1, nome) for nome, fn, t0, t1 in CENAS]


def _audio() -> Path | None:
    v = RAIZ / "public" / "projects" / "eli-premiere" / "video.mp4"
    return v if v.exists() else None


def renderizar(cenas) -> Path:
    dur_total = cenas[-1][2]
    n_frames = int(dur_total * FPS)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)

    cmd = [FFMPEG, "-y", "-v", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    aud = _audio()
    if aud:
        cmd += ["-i", str(aud), "-map", "0:v", "-map", "1:a",
                "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(SAIDA)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    surface = skia.Surface(W, H)
    canvas = surface.getCanvas()
    buf = np.empty((H, W, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)

    montadas = [(Cena(spec, W, H, FPS), t0, t1) for spec, t0, t1, _ in cenas]
    t_ini = time.time()
    ult_sig, ult_bytes, reusados = None, None, 0

    for f in range(n_frames):
        t = f / FPS
        alvo = next(((c, t - t0) for c, t0, t1 in montadas if t0 <= t < t1), None)
        if alvo is None:
            alvo = (montadas[-1][0], t - montadas[-1][1])
        sig = (id(alvo[0]), alvo[0].assinatura(alvo[1]))
        if sig == ult_sig and ult_bytes is not None:
            p.stdin.write(ult_bytes)
            reusados += 1
        else:
            canvas.clear(skia.Color4f(0, 0, 0, 1))
            alvo[0].desenhar(canvas, alvo[1])
            surface.readPixels(info, buf, W * 4, 0, 0)
            ult_bytes = buf.tobytes()
            p.stdin.write(ult_bytes)
            ult_sig = sig
        if f % 200 == 0:
            print(f"  {f}/{n_frames}", flush=True)

    p.stdin.close()
    p.wait()
    dt = time.time() - t_ini
    print(f"[Prompt4] {n_frames} frames em {dt:.1f}s ({n_frames/dt:.1f} fps) "
          f"| {reusados} reusados")
    print(f"[Prompt4] {SAIDA}  ({SAIDA.stat().st_size/1e6:.1f} MB)")
    return SAIDA


def provas(cenas):
    pasta = RAIZ / "output" / "_prompt4"
    pasta.mkdir(parents=True, exist_ok=True)
    for i, (spec, t0, t1, nome) in enumerate(cenas):
        c = Cena(spec, W, H, FPS)
        for k, frac in enumerate((0.35, 0.75)):
            c.still((t1 - t0) * frac).save(str(pasta / f"c{i+1}_{k}.png"))
    print(f"[Prompt4] provas em {pasta}")


if __name__ == "__main__":
    cenas = montar()
    for spec, t0, t1, nome in cenas:
        erros = validar(spec)
        print(f"  {nome:24} {t1-t0:5.1f}s  {'OK' if not erros else erros[:2]}")
        if erros:
            sys.exit(1)
    if "--stills" in sys.argv:
        provas(cenas)
    else:
        renderizar(cenas)
