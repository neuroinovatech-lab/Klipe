# -*- coding: utf-8 -*-
"""
montar_oficio.py — a mesma linguagem, com as regras medidas de uma peca boa.

Isto e o teste do que os agentes extrairam do `creativly.ai-brand-video`. Nada
aqui e invencao minha: cada numero saiu de contar ocorrencias no codigo de
referencia, e a conferencia cruzada corrigiu tres deles antes de eu usar.

AS SEIS REGRAS, e de onde vieram:

1. CENA CURTA — 2,5 a 5,5 s (media 3,6). As minhas tinham 16,4 s de media, e
   e a causa numero um do "travado": cena de 25 s com um gesto e imagem parada
   com enfeite.

2. UM EASING SO — `outCubic` para tudo que entra. No repo de referencia:
   31 ocorrencias de out(cubic) contra 1 da bezier "cinematic" que eles
   declaram nas constantes. O oficio nao esta na variedade de curva; esta em
   tudo entrar do mesmo jeito e o RITMO fazer a diferenca.

3. MOLA POR FAMILIA, tres e so tres:
     texto entrando      damping 14, stiffness 110, massa 0.5  -> overshoot <=1%
     UM destaque         damping 10, stiffness 150             -> overshoot 6-11%
     mudanca de estado   damping 200                           -> overshoot zero
   Texto que balanca fica ilegivel. Estado de UI que quica parece defeito. O
   pulo aparece uma vez por cena, num elemento so.

4. ESCADA DE CASCATA — 1-2 frames entre letras, 3 entre palavras, 5 entre
   blocos, 20 entre cenas. Nao e um numero: e uma escada, e ela da hierarquia.

5. RUIDO EM TUDO QUE ESTA PARADO — 2 a 4 px de deriva. Invisivel de proposito.
   E o que separa "objeto parado" de "objeto vivo": sem isso, o que nao esta
   animando parece morto. Semente diferente por eixo, e Y com METADE da
   amplitude de X (tremor vertical le como defeito; horizontal, como energia).

6. TRANSICAO DE 20 FRAMES entre cenas — 0,67 s, sempre igual.

    python -m motioncore.montar_oficio
    python -m motioncore.montar_oficio --stills
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from .cena import Cena, validar
from .ffbin import ffmpeg as _ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "output" / "oficio.mp4"
FFMPEG = _ffmpeg()

W, H, FPS = 1080, 1920, 30
F = 1.0 / FPS                     # um frame, em segundos

FUNDO = "#05060A"
TINTA = "#FAFAFA"
MUDO = "#8A93A6"
MARCA = "#3B82F6"
CIANO = "#22D3EE"
ACENTO = "#F43F5E"

# regra 4 — a escada, em segundos
LETRA, PALAVRA, BLOCO = 1.5 * F, 3 * F, 5 * F


def deriva(amp: float = 3.0, escala: float = 0.008, semente: int = 1) -> dict:
    """Regra 5. `amp` em px; o eixo Y deve receber metade disto."""
    return {"ruido": {"escala": escala, "amp": amp, "semente": semente}}


def viva(x: float, y: float, amp: float = 3.0, s: int = 1) -> dict:
    """Posicao com micro-vida. Sementes distintas por eixo, senao o objeto
    desliza na diagonal em vez de vagar."""
    return {
        "x": {"ruido": {"escala": 0.008, "amp": amp, "base": x, "semente": s}},
        "y": {"ruido": {"escala": 0.008, "amp": amp / 2, "base": y, "semente": s + 500}},
    }


def entra(t: float, dur: float = 0.4) -> list:
    """Regra 2 — a curva unica de entrada."""
    return [[t, 0], [t + dur, 1, "outCubic"]]


def sobe(t: float, y: float, de: float = 40, dur: float = 0.42) -> list:
    return [[t, y - de], [t + dur, y, "outCubic"]]


def texto_cascata(txt: str, t0: float, y: float, tam: int, cor: str = TINTA,
                  peso: int = 800, passo: float = LETRA) -> list[dict]:
    """Regra 4 aplicada a letra. Mola da familia TEXTO — sem balanco."""
    # "I" e "J" MAIUSCULOS sao estreitos como os minusculos. Sem eles aqui,
    # "KLIPE" saia "KL I PE": o I ganhava largura de maiuscula normal e abria
    # um vao dos dois lados.
    est = set("ilj.,;:!|'()[]{}t IJ")
    lar = set("mwMW@")

    def lg(c):
        return (0.30 if c in est else 0.92 if c in lar
                else 0.68 if c.isupper() else 0.56) * tam

    largs = [lg(c) for c in txt]
    x = -sum(largs) / 2
    out = []
    for i, (c, w) in enumerate(zip(txt, largs)):
        if c != " ":
            d = t0 + i * passo
            out.append({
                "tipo": "texto", "texto": c, "tamanho": tam, "peso": peso,
                "cor": cor, "x": x + w / 2,
                "y": sobe(d, y, 34),
                "opacidade": entra(d, 0.22),
                # familia TEXTO: chega e para. overshoot <= 1%
                "escala": {"mola": {"damping": 14, "stiffness": 110, "mass": 0.5},
                           "em": d, "de": 0.86, "para": 1.0},
            })
        x += w
    return out


def rotulo(txt: str, t: float, y: float, cor: str = MUDO, tam: int = 26) -> dict:
    return {"tipo": "texto", "texto": txt, "tamanho": tam, "peso": 600,
            "cor": cor, "espacamento": 3, **viva(0, y, 2, 91),
            "opacidade": entra(t, 0.3)}


# ══ as cenas — regra 1: nenhuma passa de 4,5 s ════════════════════════

def c1_marca(d: float) -> dict:
    """3,4 s. Abertura: a marca entra letra a letra, o filete corre."""
    return {"duracao": d, "fundo": FUNDO, "camadas": [
        {"tipo": "elipse", "raio": 560, **viva(0, 120, 26, 3),
         "cor": {"tipo": "radial", "cores": ["#101A33", FUNDO], "raio": 560},
         "opacidade": entra(0, 0.9)},
        *texto_cascata("KLIPE", 0.35, 140, 168, peso=900),
        # o filete: regra 3, familia DESTAQUE — o unico pulo da cena
        {"tipo": "retangulo", "larg": 300, "alt": 6, "raio": 3, "cor": MARCA,
         "y": 24,
         "escalaX": {"mola": {"damping": 10, "stiffness": 150, "mass": 0.6},
                     "em": 0.9, "de": 0.0, "para": 1.0},
         "opacidade": entra(0.9, 0.2)},
        rotulo("EDITOR DE VIDEO COM MOTOR PROPRIO", 1.35, -70),
    ]}


def c2_grade(d: float) -> dict:
    """3,0 s. A grade encaixa — cascata de bloco, nao de letra."""
    pontos = []
    for i in range(7 * 5):
        c, l = i % 7, i // 7
        x, y = (c - 3) * 110, (2 - l) * 110
        dd = 0.25 + (abs(c - 3) + abs(l - 2)) * BLOCO
        pontos.append({
            "tipo": "elipse", "raio": 9, "cor": MARCA,
            **viva(x, y, 2, 10 + i),
            "opacidade": entra(dd, 0.18),
            "escala": {"mola": {"damping": 14, "stiffness": 110, "mass": 0.5},
                       "em": dd, "de": 0.0, "para": 1.0},
        })
    return {"duracao": d, "fundo": FUNDO, "camadas": [
        *pontos,
        rotulo("MOTIONCORE  ·  SKIA", 1.5, -560, CIANO),
    ]}


def c3_numero(d: float) -> dict:
    """2,6 s. Um numero grande. Regra 3: o destaque e UM elemento."""
    return {"duracao": d, "fundo": FUNDO, "camadas": [
        {"tipo": "texto", "texto": "32s", "tamanho": 300, "peso": 900,
         "cor": TINTA, **viva(0, 120, 3, 21),
         "opacidade": entra(0.15, 0.25),
         "escala": {"mola": {"damping": 10, "stiffness": 150, "mass": 0.6},
                    "em": 0.15, "de": 0.72, "para": 1.0}},
        rotulo("RENDER DE 70 SEGUNDOS", 0.75, -120),
        {"tipo": "retangulo", "larg": 420, "alt": 3, "cor": ACENTO, "y": -30,
         "escalaX": entra(0.6, 0.5), "opacidade": entra(0.6, 0.2)},
    ]}


def c4_fala(d: float) -> dict:
    """3,6 s. Cascata de PALAVRA (3 frames), nao de letra."""
    frases = ["A palavra entra", "no instante", "em que e dita"]
    out = [rotulo("LEGENDA ANCORADA NA FALA", 0.2, -520, CIANO)]
    for i, f in enumerate(frases):
        out += texto_cascata(f, 0.4 + i * 0.55, 260 - i * 150, 76,
                             passo=PALAVRA)
    return {"duracao": d, "fundo": FUNDO, "camadas": out}


def c5_tres(d: float) -> dict:
    """3,2 s. Tres blocos, cascata de bloco (5 frames)."""
    itens = [("GRAVA", MARCA), ("CORTA", CIANO), ("RENDERIZA", ACENTO)]
    out = []
    for i, (txt, cor) in enumerate(itens):
        dd = 0.3 + i * (4 * BLOCO)
        y = 330 - i * 330
        out += [
            {"tipo": "retangulo", "larg": 620, "alt": 190, "raio": 20,
             "cor": "#0C1018", "contorno": cor, "contorno_larg": 2,
             **viva(0, y, 3, 40 + i),
             "opacidade": entra(dd, 0.2),
             # familia ESTADO: damping alto, zero overshoot
             "escalaX": {"mola": {"damping": 200, "stiffness": 120, "mass": 0.6},
                         "em": dd, "de": 0.8, "para": 1.0}},
            {"tipo": "texto", "texto": txt, "tamanho": 62, "peso": 800,
             "cor": cor, **viva(0, y - 18, 2, 60 + i),
             "opacidade": entra(dd + 0.12, 0.22)},
        ]
    return {"duracao": d, "fundo": FUNDO, "camadas": out}


def c6_fecho(d: float) -> dict:
    """3,4 s. Aneis que saem, com intervalo que encurta."""
    aneis = []
    for i in range(4):
        dd = 0.2 + sum(0.5 * (0.84 ** k) for k in range(i))
        aneis.append({
            "tipo": "elipse", "raio": 110, "cor": "#00000000",
            "contorno": MARCA, "contorno_larg": 3, "y": 60,
            "escala": [[dd, 0.3], [dd + 1.8, 3.6, "outCubic"]],
            "opacidade": [[dd, 0.85], [dd + 1.8, 0]],
        })
    return {"duracao": d, "fundo": FUNDO, "camadas": [
        *aneis,
        *texto_cascata("KLIPE", 0.5, 60, 130, peso=900),
        rotulo("localhost:3002", 1.6, -180, MUDO, 30),
    ]}


CENAS = [(c1_marca, 3.4), (c2_grade, 3.0), (c3_numero, 2.6),
         (c4_fala, 3.6), (c5_tres, 3.2), (c6_fecho, 3.4)]

TRANSICAO = 20 * F     # regra 6


def montar():
    """Cenas em sequencia, com sobreposicao de 20 frames entre elas."""
    out, t = [], 0.0
    for fn, dur in CENAS:
        out.append((fn(dur), t, t + dur))
        t += dur - TRANSICAO
    return out


def renderizar(cenas) -> Path:
    dur_total = cenas[-1][2]
    n = int(dur_total * FPS)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(
        [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
         "-pix_fmt", "yuv420p", str(SAIDA)], stdin=subprocess.PIPE)

    montadas = [(Cena(s, W, H, FPS), a, b) for s, a, b in cenas]
    surface = skia.Surface(W, H)
    canvas = surface.getCanvas()
    buf = np.empty((H, W, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    t0 = time.time()

    for f in range(n):
        t = f / FPS
        canvas.clear(skia.Color4f(0, 0, 0, 1))
        # A transicao e feita AQUI, e nao dentro da cena: a cena que sai e a
        # que entra existem no mesmo instante, e o cruzamento e de opacidade.
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
        surface.readPixels(info, buf, W * 4, 0, 0)
        p.stdin.write(buf.tobytes())
        if f % 120 == 0:
            print(f"  {f}/{n}", flush=True)

    p.stdin.close()
    p.wait()
    print(f"[Oficio] {n} frames em {time.time()-t0:.1f}s -> {SAIDA} "
          f"({SAIDA.stat().st_size/1e6:.1f} MB)")
    return SAIDA


def provas(cenas):
    pasta = RAIZ / "output" / "_oficio"
    pasta.mkdir(parents=True, exist_ok=True)
    for i, (s, a, b) in enumerate(cenas):
        Cena(s, W, H, FPS).still((b - a) * 0.7).save(str(pasta / f"c{i+1}.png"))
    print(f"[Oficio] provas em {pasta}")


if __name__ == "__main__":
    cenas = montar()
    print(f"  {len(cenas)} cenas, {cenas[-1][2]:.1f}s "
          f"(media {sum(d for _, d in CENAS)/len(CENAS):.1f}s por cena)")
    for i, (s, a, b) in enumerate(cenas):
        e = validar(s)
        if e:
            print(f"  cena {i+1}: {e[:3]}")
            sys.exit(1)
    print("  todas validaram")
    provas(cenas) if "--stills" in sys.argv else renderizar(cenas)
