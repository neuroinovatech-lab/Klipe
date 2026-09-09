"""
caption_ass.py — legenda dinamica via libass, dirigida pelos MESMOS presets.

Descoberta que muda o custo (05/08): o `\\t` do ASS anima escala e cor por
TRECHO da linha, com curva de aceleracao. Ou seja, o estouro da palavra ativa
e o papel por palavra (forte maior/colorida, vazia menor/apagada) cabem no
libass — e queimar 60s custou 4,6s, o mesmo que o composite sem legenda.
O caminho por video (Skia -> QTRLE -> overlay) custava 267s no render de 12min.

O que NAO cabe: pilula com canto arredondado por palavra (`boxed`,
`forte-caixa`) — exigiria camada de desenho vetorial. Esses continuam no
caminho Skia. `expressa_em_ass()` decide, e o forge_render escolhe a rota.
"""
from __future__ import annotations

import io
import math
from pathlib import Path

from .caption_presets import classificar, resolver

# So entra aqui o que o mapeamento reproduz com fidelidade. `serif-mista`
# depende da PlayfairDisplay estar instalada no sistema (libass nao le o
# @font-face do projeto) — fora ate ser verificada.
ASS_OK = {"outline", "destaque"}

BASE_FONT = 62
LINE_HEIGHT = 1.25


def expressa_em_ass(cfg: dict) -> bool:
    if not cfg.get("captionKaraoke", True):
        pass  # sem karaoke tambem e expressavel — só nao anima
    usados = {cfg.get("captionStyle", "words")} | {
        c.get("subStyle") for c in (cfg.get("captions") or []) if c.get("subStyle")}
    if not all(e in ASS_OK for e in usados):
        return False

    # Campos que o mapeamento pro ASS NAO reproduz. Se algum estiver fora do
    # padrao, a rota rapida MENTE: o preview mostra o ajuste e o arquivo sai
    # sem ele — espacamento entre palavras/linhas e deslocamento horizontal
    # simplesmente somem. Nesse caso a legenda volta pro overlay do
    # MotionCore, que respeita os tres. Custa tempo de render e entrega o que
    # a tela prometeu; o contrario nao tem conserto depois.
    if int(cfg.get("captionX", 0) or 0) != 0:
        return False
    if int(cfg.get("captionWordGap", 12) or 12) != 12:
        return False
    if int(cfg.get("captionLineGap", 8) or 8) != 8:
        return False
    return True


def _bgr(hexa: str) -> str:
    h = (hexa or "#FFFFFF").lstrip("#")
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def _tempo(t: float) -> str:
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def gerar(cfg: dict, destino: str | Path) -> Path:
    """Escreve o .ass do video inteiro segundo o preset de cada legenda."""
    fs = round(round(BASE_FONT * float(cfg.get("captionFontSize", 100)) / 100.0) * 1.15)
    stroke = max(4, round(fs * 0.09))
    W = int(cfg.get("width", 1080)); H = int(cfg.get("height", 1920))
    cor_base = _bgr(cfg.get("captionColor", "#FFFFFF"))
    destaque_hex = cfg.get("captionHighlightColor", "#E8940A")
    destaque = _bgr(destaque_hex)
    fonte = cfg.get("captionFont", "Montserrat")
    karaoke = bool(cfg.get("captionKaraoke", True))
    # bottom 20% + captionY (positivo sobe), em margem a partir da base
    margv = round(H * 0.20 + float(cfg.get("captionY", 0) or 0))
    wpg = min(4, max(2, int(cfg.get("captionMaxLines", 2)) + 1))
    estilo_global = cfg.get("captionStyle", "outline")
    custom = cfg.get("captionPreset") or None

    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: base,{fonte},{fs},{cor_base},{cor_base},&H000000&,&H80000000&,-1,0,0,0,100,100,0,0,1,{stroke},2,2,60,60,{margv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    linhas = []
    for c in (cfg.get("captions") or []):
        ws = [w for w in (c.get("text") or "").split() if w]
        if not ws:
            continue
        estilo = c.get("subStyle") or estilo_global
        pr = resolver(estilo, custom)
        ini, fim = float(c["startSec"]), float(c["endSec"])
        grupos = [ws[i:i + wpg] for i in range(0, len(ws), wpg)]
        dg = (fim - ini) / len(grupos)
        for gi, grupo in enumerate(grupos):
            g0 = ini + gi * dg
            papeis = classificar(grupo)
            dp = dg / len(grupo)
            runs = []
            for wi, (w, papel) in enumerate(zip(grupo, papeis)):
                pp = pr["papeis"][papel]
                esc = round(100 * float(pp["escala"]))
                cor = _bgr(pp["cor"].replace("destaque", destaque_hex)) if pp["cor"] \
                    else cor_base
                t0 = round(wi * dp * 1000); t1 = round((wi + 1) * dp * 1000)
                anim = ""
                if karaoke:
                    alvo = round(esc * float(pr["ativa"]["escala"]))
                    # mola aproximada: passa do alvo e assenta, com aceleracao
                    anim = (f"\\t({t0},{t0+120},0.6,\\fscx{alvo+6}\\fscy{alvo+6})"
                            f"\\t({t0+120},{t0+300},1.4,\\fscx{esc}\\fscy{esc})")
                    if papel != "power":
                        anim += (f"\\t({t0},{t0+60},\\1c{destaque})"
                                 f"\\t({t1},{t1+60},\\1c{cor})")
                runs.append(f"{{\\fscx{esc}\\fscy{esc}\\1c{cor}{anim}}}{w.upper()}")
            linhas.append(f"Dialogue: 0,{_tempo(g0)},{_tempo(g0+dg)},base,,0,0,0,,"
                          + "\\h".join(runs))

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    io.open(destino, "w", encoding="utf-8-sig").write(cab + "\n".join(linhas))
    return destino
