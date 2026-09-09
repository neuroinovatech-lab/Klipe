# -*- coding: utf-8 -*-
"""
prova_estilos.py — a cena "Style Presets" do creativly.ai, refeita no MotionCore.

Isto e a prova. Nao e "inspirado em": e a MESMA cena, com os mesmos numeros
lidos do `StylePresetsScene.tsx`, para a comparacao ser direta.

O que o original faz, e de onde tirei cada valor:

  foto de fundo a 120% do quadro, opacidade 0.35        :138-152
  marca d'agua "STYLES" italica, 400px, rot -15deg,     :76-101
    opacidade 0.025, em degrade
  rotulo "curated" 24px cinza                           :164
  titulo "Style Presets" 140px branco, letra a letra    :183-195
  seis pilhas: padding 16/40, raio 100, fonte 32        :250-262
  a ativa troca a cada 20 frames (0,667 s)              :47
  30 particulas com deriva de ruido +-20px              :113-120
  brilho pulsando: 0.15 + 0.08 * ruido(f * 0.02)        :52

O QUE FALTAVA NO MOTOR e eu acrescentei para isto existir:

  tipo `imagem`   — o DSL tinha sete tipos e nenhum era foto. Era ISSO que
                    separava as minhas pecas das profissionais, e nao a curva
                    de easing que passei horas afinando.
  `ruido`         — 114 usos no material de referencia, zero no motor.
  bezier cubica   — para portar curva exata.

    python -m motioncore.prova_estilos
    python -m motioncore.prova_estilos --stills
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from .cena import Cena, validar
from .ffbin import ffmpeg as _ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
REF = Path(os.environ.get(
    "KLIPE_CBV_ASSETS",
    RAIZ.parent / "referencias" / "creativly-brand-video" / "public",
))
SAIDA = RAIZ / "output" / "prova_estilos.mp4"
FFMPEG = _ffmpeg()

# 1920x1080 como o original — a comparacao tem que ser no mesmo formato
W, H, FPS, DUR = 1920, 1080, 30, 4.0
F = 1.0 / FPS

# constants.ts do original
BG = "#050505"
TEXTO = "#ffffff"
MUDO = "#a1a1aa"
MARCA = "#3B82F6"
CIANO = "#06B6D4"

ESTILOS = [
    ("Cinematic", "#FF5F56"),
    ("Anime", MARCA),
    ("3D Render", "#27C93F"),
    ("Claymation", "#3357FF"),
    ("Line Art", "#A833FF"),
    ("Photographic", "#FF33A8"),
]
TROCA = 20 * F      # :47 — a ativa muda a cada 20 frames

_ESTREITAS = set("ilj.,;:!|'()[]{}t IJ")
_LARGAS = set("mwMW@")


def _lg(ch: str, tam: float) -> float:
    return (0.30 if ch in _ESTREITAS else 0.92 if ch in _LARGAS
            else 0.68 if ch.isupper() else 0.56) * tam


def _larg(txt: str, tam: float) -> float:
    return sum(_lg(c, tam) for c in txt)


def split_text(txt: str, t0: float, y: float, tam: int, cor: str = TEXTO,
               peso: int = 900, passo: float = 1.5 * F) -> list[dict]:
    """Letra a letra, mola da familia TEXTO (damping 14) — sem balanco."""
    x = -_larg(txt, tam) / 2
    out = []
    for i, ch in enumerate(txt):
        w = _lg(ch, tam)
        if ch != " ":
            d = t0 + i * passo
            out.append({
                "tipo": "texto", "texto": ch, "tamanho": tam, "peso": peso,
                "cor": cor, "x": x + w / 2,
                "y": [[d, y - 26], [d + 0.4, y, "outCubic"]],
                "opacidade": [[d, 0], [d + 0.2, 1, "outCubic"]],
                "escala": {"mola": {"damping": 14, "stiffness": 110, "mass": 0.5},
                           "em": d, "de": 0.82, "para": 1.0},
            })
        x += w
    return out


def particulas(n: int = 30) -> list[dict]:
    """:113-120 — deriva de ruido de +-20 px, pulso por seno.

    Aqui cada uma e uma camada propria: `repetir` daria a MESMA deriva a todas,
    e o que faz isto parecer poeira e justamente cada uma ir para um lado.
    """
    out = []
    for i in range(n):
        # posicao base determinista, espalhada por progressao irracional
        a = i * 2.39996
        bx = (((i * 37) % 100) / 100 - 0.5) * W
        by = (((i * 61) % 100) / 100 - 0.5) * H
        tam = 1 + (i % 3)
        out.append({
            "tipo": "elipse", "raio": tam,
            "cor": MARCA if i % 3 else CIANO,
            "x": {"ruido": {"escala": 0.015, "amp": 20, "base": bx, "semente": 100 + i}},
            "y": {"ruido": {"escala": 0.015, "amp": 20, "base": by, "semente": 600 + i}},
            "opacidade": {"ruido": {"escala": 0.06, "amp": 0.3, "base": 0.5,
                                    "semente": 200 + i}},
        })
    return out


def pilula(nome: str, cor: str, idx: int, x: float, y: float,
           t_entra: float) -> list[dict]:
    """:250-262 — padding 16/40, raio 100, fonte 32.

    A ativa e preenchida com a cor e o texto vira PRETO; as outras ficam
    contornadas e cinza. A troca a cada 20 frames e feita com keyframes de
    opacidade cruzando as duas versoes — o motor nao tem "estado", entao o
    estado vira tempo.
    """
    tam = 32
    larg = _larg(nome, tam) + 80      # padding 40 de cada lado
    alt = tam + 32                    # padding 16
    # janelas em que ESTA pilula e a ativa, dentro da duracao da cena
    janelas = [(k * TROCA, (k + 1) * TROCA)
               for k in range(int(DUR / TROCA) + 1) if k % len(ESTILOS) == idx]

    def op_ativa():
        ks = [[0, 0]]
        for a, b in janelas:
            ks += [[max(0, a - 0.06), 0], [a + 0.06, 1],
                   [b - 0.06, 1], [b + 0.06, 0]]
        return ks

    return [
        # a versao apagada, sempre presente
        {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": 100,
         "cor": "#FFFFFF08", "contorno": "#FFFFFF1A", "contorno_larg": 1,
         "x": x, "y": y,
         "opacidade": [[t_entra, 0], [t_entra + 0.3, 1, "outCubic"]],
         "escala": {"mola": {"damping": 14, "stiffness": 110, "mass": 0.5},
                    "em": t_entra, "de": 0.86, "para": 1.0}},
        {"tipo": "texto", "texto": nome, "tamanho": tam, "peso": 700,
         "cor": MUDO, "x": x, "y": y - 2,
         "opacidade": [[t_entra, 0], [t_entra + 0.3, 1, "outCubic"]]},
        # a versao ACESA por cima, cruzando por opacidade
        {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": 100,
         "cor": cor, "x": x, "y": y, "opacidade": op_ativa()},
        {"tipo": "texto", "texto": nome, "tamanho": tam, "peso": 700,
         "cor": "#000000", "x": x, "y": y - 2, "opacidade": op_ativa()},
    ]


def cena() -> dict:
    foto = REF / "surrealist-concept_800w.jpg"
    camadas: list[dict] = []

    # ── a foto de fundo, 120% do quadro, 0.35 (:138-152) ──────────────
    if foto.exists():
        camadas.append({
            "tipo": "imagem", "src": str(foto),
            "larg": "120%", "alt": "120%", "ajuste": "cobrir",
            "opacidade": [[0, 0], [0.7, 0.35, "outCubic"]],
            # respiro lento: a foto nunca fica travada
            "escala": {"ruido": {"escala": 0.004, "amp": 0.02,
                                 "base": 1.02, "semente": 5}},
        })
        # vinheta por cima, para o texto ter contraste
        camadas.append({
            "tipo": "elipse", "raio": W * 0.72,
            "cor": {"tipo": "radial", "cores": ["#00000000", BG], "raio": W * 0.72},
            "opacidade": 0.95})

    # ── marca d'agua "STYLES" (:76-101): 400px, italica, -15deg, 0.025 ──
    camadas.append({
        "tipo": "texto", "texto": "STYLES", "tamanho": 400, "peso": 900,
        "italico": True, "cor": MARCA, "rotacao": -15,
        "espacamento": -20,
        "opacidade": [[0, 0], [1.0, 0.06, "outCubic"]],
    })

    camadas += particulas(30)

    # ── o bloco central ───────────────────────────────────────────────
    camadas.append({
        "tipo": "texto", "texto": "curated", "tamanho": 24, "peso": 500,
        "cor": MUDO, "italico": True, "y": 250,
        "opacidade": [[0.1, 0], [0.45, 1, "outCubic"]],
    })
    camadas += split_text("Style Presets", 0.25, 130, 140)
    camadas.append({
        "tipo": "texto", "texto": "transform everything", "tamanho": 20,
        "peso": 600, "cor": CIANO, "espacamento": 4, "y": 40,
        "opacidade": [[0.7, 0], [1.0, 1, "outCubic"]],
    })

    # ── as seis pilulas, em duas fileiras centradas ───────────────────
    tam = 32
    largs = [_larg(n, tam) + 80 for n, _ in ESTILOS]
    linhas = [list(range(0, 4)), list(range(4, 6))]
    for li, idxs in enumerate(linhas):
        total = sum(largs[i] for i in idxs) + 20 * (len(idxs) - 1)
        x = -total / 2
        y = -120 - li * 96
        for i in idxs:
            nome, cor = ESTILOS[i]
            camadas += pilula(nome, cor, i, x + largs[i] / 2, y,
                              0.9 + i * (3 * F))
            x += largs[i] + 20

    return {"duracao": DUR, "fundo": BG, "camadas": camadas}


def renderizar() -> Path:
    spec = cena()
    erros = validar(spec)
    if erros:
        print("  " + "\n  ".join(erros[:6]))
        sys.exit(1)
    print(f"  {len(spec['camadas'])} camadas · validou")
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    n = int(DUR * FPS)
    p = subprocess.Popen(
        [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
         "-pix_fmt", "yuv420p", str(SAIDA)], stdin=subprocess.PIPE)
    c = Cena(spec, W, H, FPS)
    surface = skia.Surface(W, H)
    canvas = surface.getCanvas()
    buf = np.empty((H, W, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    t0 = time.time()
    for f in range(n):
        canvas.clear(skia.Color4f(0, 0, 0, 1))
        c.desenhar(canvas, f / FPS)
        surface.readPixels(info, buf, W * 4, 0, 0)
        p.stdin.write(buf.tobytes())
    p.stdin.close()
    p.wait()
    print(f"[Prova] {n} frames em {time.time()-t0:.1f}s -> {SAIDA}")
    return SAIDA


if __name__ == "__main__":
    spec = cena()
    e = validar(spec)
    print(f"  {len(spec['camadas'])} camadas · {e or 'validou'}")
    if e:
        sys.exit(1)
    if "--stills" in sys.argv:
        pasta = RAIZ / "output" / "_prova"
        pasta.mkdir(parents=True, exist_ok=True)
        c = Cena(spec, W, H, FPS)
        for k, t in enumerate((1.2, 2.4, 3.4)):
            c.still(t).save(str(pasta / f"t{k}.png"))
        print(f"  provas em {pasta}")
    else:
        renderizar()
