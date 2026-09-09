# -*- coding: utf-8 -*-
"""
montar_sincronia.py — "SINCRONIA": o video da Dra. Eli como tipografia cinetica.

Ja existe um `montar_padroes.py` que refaz este mesmo video em geometria
abstrata — grade, irregularidade, previsao. Esta peca vai por outro caminho de
proposito, e o motivo e uma capacidade que nao existia quando aquela foi
escrita: a transcricao agora tem TEMPO POR PALAVRA.

Com isso, a palavra pode nascer no quadro no instante exato em que a boca dela
a diz. Nao e legenda acompanhando a fala — e a fala VIRANDO imagem. E o assunto
fecha sozinho: o video fala de perceber padroes, e o padrao que a peca constroi
e o ritmo da propria pessoa falando.

Tres regras que me impus:

  1. Nada de Skia neste arquivo. So cena declarativa. Se eu precisasse descer
     para o canvas, seria sinal de que o DSL nao aguentou o trabalho.

  2. A palavra entra no tempo DELA, nunca num tempo bonito que eu escolhi.
     Quando a fala acelera, a imagem acelera junto — de graca, porque o tempo
     vem do audio e nao de mim.

  3. Nenhum "momento" e decorativo. Cada motivo geometrico existe porque a
     frase daquele trecho pede: a grade quando ela fala de padrao, a
     irregularidade quando ela fala de irregularidade, o eco adiantado quando
     ela fala de antecipar.

    python -m motioncore.montar_sincronia
    python -m motioncore.montar_sincronia --stills   # so as provas
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from .cena import Cena, validar
from .ffbin import ffmpeg as _ffmpeg

RAIZ = Path(__file__).resolve().parent.parent
PROJ = RAIZ / "public" / "projects" / "eli-premiere"
SAIDA = PROJ / "sincronia.mp4"
FFMPEG = _ffmpeg()

W, H, FPS = 1080, 1920, 30

# ── paleta ────────────────────────────────────────────────────────────
# Fundo quase preto com um azul dentro: preto puro num video vertical fica
# chapado no celular, e o azul da profundidade sem virar "tema escuro".
FUNDO = "#07080D"
TINTA = "#F2F4F8"      # a palavra dita AGORA
ECO = "#3A4152"        # o que ja foi dito, ou ainda vai ser
ACENTO = "#FF7A18"     # a irregularidade, o que salta
FRIO = "#3EC5FF"       # o cerebro, o sistema, o que e dela


def _transcricao() -> list[dict]:
    """As palavras, achatadas, com o tempo de cada uma."""
    t = json.loads((PROJ / "transcription.json").read_text(encoding="utf-8"))
    palavras = []
    for seg in t:
        for w in (seg.get("words") or []):
            txt = str(w.get("text", "")).strip()
            if txt:
                palavras.append({"t": float(w["start"]), "fim": float(w["end"]),
                                 "txt": txt, "frase": float(seg["start"])})
    if not palavras:
        raise SystemExit("A transcricao nao tem tempo por palavra. "
                         "Rode: python transcribe_klipe.py eli-premiere")
    return palavras


def _frases(palavras: list[dict]) -> list[list[dict]]:
    """Agrupa por frase — e a unidade que cabe num quadro."""
    grupos: dict[float, list] = {}
    for p in palavras:
        grupos.setdefault(p["frase"], []).append(p)
    return [grupos[k] for k in sorted(grupos)]


# ══ os motivos ════════════════════════════════════════════════════════
# Cada um existe por causa de uma frase especifica. O comentario diz qual.

def campo_de_pontos(t0: float, dur: float, cor: str = ECO,
                    op: float = 0.5, semente_x: int = 0) -> dict:
    """A grade que respira ao fundo. Presente o video inteiro, baixinha.

    `atraso` e o que faz dela um padrao em vez de um bloco: sem ele as 273
    copias pulsam em unissono e o olho le uma coisa so, nao um tecido.
    """
    return {
        "tipo": "elipse", "raio": 3, "cor": cor,
        "x": -W / 2 + 60 + semente_x, "y": H / 2 - 60,
        "opacidade": [[0, 0], [0.8, op], [dur - 0.6, op], [dur, 0]],
        "escala": [[0, 0.6], [0.5, 1.15, "outCubic"], [1.1, 0.85, "inOutCubic"],
                   [1.9, 1.15, "inOutCubic"], [2.7, 0.85, "inOutCubic"]],
        "repetir": {"cols": 13, "linhas": 21, "espX": 78, "espY": 92,
                    "atraso": 0.006, "ordem": "centro"},
    }


def anel_cortex(t_ini: float, dur: float, y: float = 0) -> dict:
    """"A regiao do cerebro que desempenha esse papel e o cortex temporal."

    Um anel que se DESENHA (`traco` de 0 a 1) e depois preenche um setor. O
    setor e a regiao: o resto do anel fica, para ela ser uma PARTE e nao o todo.
    """
    return {"tipo": "grupo", "y": y, "camadas": [
        # `traco` recorta o CONTORNO. Feito como anel preenchido (`raio_int`)
        # nao havia contorno para a pena correr, e o anel simplesmente nao
        # aparecia. Circulo vazado com `contorno` e o que desenha.
        {"tipo": "elipse", "raio": 240, "cor": "#00000000",
         "contorno": ECO, "contorno_larg": 3,
         "traco": [[0, 0], [1.5, 1, "outCubic"]],
         "opacidade": [[0, 0], [0.25, 1]]},
        {"tipo": "elipse", "raio": 246, "raio_int": 186, "cor": FRIO,
         "de_grau": -128, "varre_grau": [[0.9, 0], [2.1, 96, "outCubic"]],
         "opacidade": [[0.9, 0], [1.2, 1]]},
        # o pulso que sai da regiao: e ela "acendendo"
        {"tipo": "elipse", "raio": 250, "raio_int": 244, "cor": FRIO, "blur": 10,
         "escala": [[2.0, 1], [3.4, 1.7, "outCubic"]],
         "opacidade": [[2.0, 0.9], [3.4, 0]]},
    ]}


def linha_do_ritmo(y: float, n: int, passo: float, dur: float,
                   irregular: int | None = None) -> dict:
    """A batida regular — e, quando pedido, a que sai dela.

    Serve duas frases: "identificacao de irregularidades" (com `irregular`) e
    "perceber e analisar padroes" (sem).
    """
    filhos = [{
        "tipo": "retangulo", "larg": 5, "alt": 46, "raio": 3, "cor": ECO,
        "x": -(n - 1) * passo / 2, "y": y,
        "opacidade": [[0, 0], [0.25, 0.85]],
        "escalaY": [[0, 0.2], [0.3, 1, "outBack"]],
        "repetir": {"cols": n, "linhas": 1, "espX": passo,
                    "espY": 0, "atraso": 0.055, "ordem": "linha"},
    }]
    if irregular is not None:
        x_ir = -(n - 1) * passo / 2 + irregular * passo
        filhos += [
            # a barra fora do ritmo: mais alta, na cor que salta
            {"tipo": "retangulo", "larg": 7, "alt": 96, "raio": 4, "cor": ACENTO,
             "x": x_ir, "y": y,
             "opacidade": [[1.5, 0], [1.8, 1]],
             "escalaY": [[1.5, 0.1], [1.9, 1, "outBack"]]},
            # o anel que a encontra
            {"tipo": "elipse", "raio": 74, "raio_int": 71, "cor": ACENTO,
             "x": x_ir, "y": y,
             "escala": [[1.9, 0.4], [2.5, 1, "outCubic"]],
             "opacidade": [[1.9, 0], [2.2, 0.95], [3.6, 0.35]]},
        ]
    return {"tipo": "grupo", "camadas": filhos}


def eco_adiantado(y: float, dur: float) -> dict:
    """"As vezes eu antecipo as coisas que irao acontecer."

    Tres marcas chegam no ritmo; a QUARTA aparece antes da hora dela, em
    contorno — a previsao desenhada como fantasma do que ainda nao veio.
    """
    passo = 150
    x0 = -1.5 * passo
    filhos = []
    for i in range(3):
        filhos.append({
            "tipo": "elipse", "raio": 15, "cor": TINTA, "x": x0 + i * passo, "y": y,
            "opacidade": [[0.3 + i * 0.55, 0], [0.5 + i * 0.55, 1]],
            "escala": [[0.3 + i * 0.55, 0.2], [0.62 + i * 0.55, 1, "outBack"]],
        })
    # o fantasma: entra ANTES do terceiro ponto, so contorno
    filhos.append({
        "tipo": "elipse", "raio": 15, "cor": "#00000000",
        "contorno": ACENTO, "contorno_larg": 3,
        "x": x0 + 3 * passo, "y": y,
        "opacidade": [[1.05, 0], [1.35, 0.9], [2.6, 0.9], [2.9, 1]],
        "escala": [[1.05, 2.2], [1.5, 1, "outCubic"]],
    })
    # e entao ele se confirma, preenchendo
    filhos.append({
        "tipo": "elipse", "raio": 15, "cor": ACENTO,
        "x": x0 + 3 * passo, "y": y,
        "opacidade": [[2.6, 0], [2.9, 1]],
        "escala": [[2.6, 0.3], [3.1, 1, "outBack"]],
    })
    return {"tipo": "grupo", "camadas": filhos}


def dualidade(dur: float) -> dict:
    """"De nao captar indiretas, mas conseguir prever eventos futuros."

    Duas metades espelhadas. A de baixo e a mesma forma, invertida e fria —
    a mesma pessoa, o outro lado. Elas trocam de peso no meio do trecho.
    """
    def meia(sinal: int, cor: str, atraso: float):
        return {"tipo": "grupo", "camadas": [
            {"tipo": "retangulo", "larg": 3, "alt": 120, "raio": 2, "cor": cor,
             "x": -420, "y": sinal * 210,
             "escalaY": [[atraso, 0.15], [atraso + 0.5, 1, "outCubic"]],
             "opacidade": [[atraso, 0], [atraso + 0.3, 0.9]],
             "repetir": {"cols": 8, "linhas": 1, "espX": 120, "espY": 0,
                         "atraso": 0.07, "ordem": "linha"}},
        ]}
    return {"tipo": "grupo", "camadas": [
        meia(+1, TINTA, 0.2),
        meia(-1, FRIO, 0.9),
        # a linha que separa — e que some no fim, porque as duas sao uma so
        {"tipo": "retangulo", "larg": [[0, 0], [1.2, 980, "outCubic"]],
         "alt": 2, "cor": ECO, "y": 0,
         "opacidade": [[0, 0], [1.0, 0.8], [dur - 1.2, 0.8], [dur - 0.2, 0]]},
    ]}


# ══ a frase virando quadro ════════════════════════════════════════════

# Largura aproximada por CLASSE de caractere. Um fator unico (0.52 * n) colava
# "que desempenha" em "quaedesempenha": num tipo com 'm' e 'w' o erro acumula
# rapido, e a colisao aparece justo nas palavras longas, que sao as que importam.
_ESTREITAS = set("ilj.,;:!|'iI()[]{}t ")
_LARGAS = set("mwMW@")


def _larg_texto(txt: str, tamanho: float) -> float:
    """Sem registro de fontes aqui dentro, medir exato exigiria carregar o Skia.
    Tres classes ja tiram a colisao, que era o problema de verdade."""
    u = 0.0
    for ch in txt:
        if ch in _ESTREITAS:
            u += 0.30
        elif ch in _LARGAS:
            u += 0.92
        elif ch.isupper():
            u += 0.68
        else:
            u += 0.56
    return max(tamanho * 0.4, u * tamanho)


def _quebrar(palavras: list[dict], por_linha: int = 3) -> list[list[dict]]:
    linhas, atual = [], []
    for p in palavras:
        atual.append(p)
        if len(atual) >= por_linha:
            linhas.append(atual)
            atual = []
    if atual:
        linhas.append(atual)
    return linhas


def bloco_de_fala(palavras: list[dict], t0: float, dur: float,
                  tamanho: int = 74, y_base: float = 430) -> list[dict]:
    """Cada palavra e uma camada que nasce no instante em que e dita.

    A ARMADILHA que isto contorna: em texto do DSL, `x` e o CENTRO do bloco, e
    nao a borda esquerda. Nao da para "continuar de onde a anterior parou" sem
    medir a fonte. Entao a linha e centrada por construcao: eu calculo a largura
    aproximada de cada palavra e distribuo em torno do zero.

    A aproximacao (0.52 * tamanho por caractere) e grosseira de proposito —
    medir exato exigiria o registro de fontes aqui dentro, e o erro de meio
    caractere nao aparece numa peca em movimento.
    """
    camadas = []
    linhas = _quebrar(palavras)
    alt_linha = tamanho * 1.30
    topo = y_base + (len(linhas) - 1) * alt_linha / 2

    for i, linha in enumerate(linhas):
        # A linha ENCOLHE se nao couber. Sem isto uma palavra longa empurrava a
        # linha para fora do quadro — "responsável" saia cortado na borda, e o
        # erro nao aparecia no still de outra cena. Como a largura aqui e
        # estimada, a garantia tem que vir de uma margem, nao da conta exata.
        LARG_SEGURA = W - 120
        tam = tamanho
        for _ in range(6):
            larguras = [_larg_texto(p["txt"], tam) for p in linha]
            espaco = tam * 0.30
            total = sum(larguras) + espaco * (len(linha) - 1)
            if total <= LARG_SEGURA:
                break
            tam *= LARG_SEGURA / total * 0.97
        x = -total / 2
        y = topo - i * alt_linha
        for p, larg in zip(linha, larguras):
            rel = max(0.0, p["t"] - t0)
            camadas.append({
                "tipo": "texto", "texto": p["txt"], "tamanho": round(tam),
                "peso": 800, "fonte": "Inter", "cor": TINTA,
                "x": x + larg / 2, "y": y,
                # nasce no instante da fala: sobe um pouco e assenta
                "opacidade": [[rel, 0], [rel + 0.10, 1]],
                "escala": [[rel, 0.86], [rel + 0.26, 1, "outBack"]],
                "blur": [[rel, 7], [rel + 0.18, 0]],
            })
            x += larg + espaco
    return camadas


def cena_da_frase(idx: int, palavras: list[dict], t0: float, t1: float,
                  motivo) -> dict:
    """Um quadro por frase: o fundo que respira, o motivo, e a fala."""
    dur = round(t1 - t0, 3)
    camadas = [campo_de_pontos(t0, dur, semente_x=(idx % 3) * 9)]
    if motivo is not None:
        camadas.append(motivo(dur))
    camadas += bloco_de_fala(palavras, t0, dur)
    return {"duracao": dur, "fundo": FUNDO, "camadas": camadas}


def montar() -> list[tuple[dict, float, float]]:
    """Devolve [(spec, t_inicio, t_fim)] — uma cena por frase.

    O motivo de cada trecho e escolhido pela PALAVRA que a frase carrega, nao
    por posicao: se a transcricao mudar, o motivo continua caindo no lugar.
    """
    palavras = _transcricao()
    frases = _frases(palavras)
    fim_total = max(p["fim"] for p in palavras)

    def gatilho(txt: str):
        t = txt.lower()
        if "córtex" in t or "cortex" in t or "cérebro" in t or "cerebro" in t:
            return lambda d: anel_cortex(0, d, y=-330)
        # RADICAL, nao a palavra inteira: o Whisper partiu "irregularidades"
        # entre duas frases ("...de ir" / "regularidades nos ajuda..."), e o
        # gatilho exato nao casou em nenhuma das duas. Radical pega as duas
        # metades e sobrevive a proxima transcricao, que vai partir noutro lugar.
        if "irregular" in t or "sensoria" in t:
            return lambda d: linha_do_ritmo(-380, 9, 108, d, irregular=6)
        if "antecipo" in t or "prever" in t or "futuro" in t:
            return lambda d: eco_adiantado(-400, d)
        if "dualidade" in t or "inocente" in t or "sensitiva" in t:
            return lambda d: dualidade(d)
        if "padr" in t:   # padrao, padroes — a palavra-chave da peca
            return lambda d: linha_do_ritmo(-380, 11, 92, d)
        return None

    cenas = []
    for i, fr in enumerate(frases):
        t0 = fr[0]["t"] - 0.12          # um respiro antes da primeira palavra
        t1 = frases[i + 1][0]["t"] - 0.12 if i + 1 < len(frases) else fim_total + 1.2
        texto = " ".join(p["txt"] for p in fr)
        cenas.append((cena_da_frase(i, fr, t0, t1, gatilho(texto)), t0, t1))
    return cenas


# ══ render ════════════════════════════════════════════════════════════

def _audio() -> Path | None:
    v = PROJ / "video.mp4"
    return v if v.exists() else None


def renderizar(cenas, abrir: bool = True) -> Path:
    """Uma Surface so para todas as cenas: trocar de cena e trocar de spec.

    O dedup por assinatura vale por cena — entre cenas a assinatura muda de
    forma, entao nao ha risco de reusar frame de uma noutra.
    """
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
    # RGBA explicito: o formato NATIVO da Surface no Windows e BGRA, e declarar
    # "rgba" no cano sem converter troca vermelho por azul.
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)

    montadas = [(Cena(spec, W, H, FPS), t0, t1) for spec, t0, t1 in cenas]
    t_ini = time.time()
    ult_sig, ult_bytes, reusados = None, None, 0

    for f in range(n_frames):
        t = f / FPS
        alvo = None
        for c, t0, t1 in montadas:
            if t0 <= t < t1:
                alvo = (c, t - t0)
                break
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

        if f % 150 == 0:
            print(f"  {f}/{n_frames} ({f * 100 // max(1, n_frames)}%)", flush=True)

    p.stdin.close()
    p.wait()
    dt = time.time() - t_ini
    print(f"[Sincronia] {n_frames} frames em {dt:.1f}s "
          f"({n_frames / dt:.1f} fps) | {reusados} reusados")
    print(f"[Sincronia] {SAIDA}  ({SAIDA.stat().st_size / 1e6:.1f} MB)")
    return SAIDA


def provas(cenas):
    """Um still por cena, para conferir composicao sem esperar o render."""
    pasta = RAIZ / "output" / "_sincronia"
    pasta.mkdir(parents=True, exist_ok=True)
    for i, (spec, t0, t1) in enumerate(cenas):
        c = Cena(spec, W, H, FPS)
        img = c.still(min(1.4, (t1 - t0) * 0.6))
        img.save(str(pasta / f"cena_{i:02d}.png"))
    print(f"[Sincronia] {len(cenas)} provas em {pasta}")


if __name__ == "__main__":
    cenas = montar()
    print(f"[Sincronia] {len(cenas)} cenas, ate {cenas[-1][2]:.1f}s")
    for i, (spec, t0, t1) in enumerate(cenas):
        erros = validar(spec)
        if erros:
            print(f"  cena {i}: {erros[:3]}")
            sys.exit(1)
    print("[Sincronia] todas as cenas passaram no validador")
    if "--stills" in sys.argv:
        provas(cenas)
    else:
        renderizar(cenas)
