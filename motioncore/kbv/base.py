# -*- coding: utf-8 -*-
"""base.py — o vocabulario do video de marca do Klipe.

Isto NAO reinventa nada. O oficio (as tres familias de mola, a escada de
cascata, o ruido em tudo que fica parado, a transicao de 20 frames) foi medido
no `creativly.ai-brand-video` e ja mora em `cbv/base.py`. Aqui so entram duas
coisas:

  1. A PALETA do Klipe por cima da estrutura de la. A referencia usa azul de
     marca sobre quase-preto; o Klipe usa a laranja da propria logo. As cores
     estruturais (fundo, borda, mudo) ficam iguais porque nao sao da marca de
     ninguem — sao do oficio.

  2. Os gestos que a referencia nao precisava e o Klipe precisa: moldura de
     JANELA DE APLICATIVO (a referencia enquadra fotos; o Klipe enquadra a
     propria tela) e a SIGLA, porque KLIPE quer dizer alguma coisa.

As seis armadilhas do DSL continuam valendo e estao escritas em `cbv/base.py`.
A que mais pega aqui e a terceira: `repetir` CENTRA a grade na camada e da a
MESMA animacao a todas as copias. Serve pra textura de fundo; nao serve pra
nada que precise de identidade propria.
"""
from __future__ import annotations

from pathlib import Path

# o oficio medido vem inteiro de la — molas, escada, gestos, medicao de texto
from ..cbv.base import (                                    # noqa: F401
    W, H, FPS, F,
    LETRA, PALAVRA, BLOCO, TRANSICAO,
    MOLA_TEXTO, MOLA_DESTAQUE, MOLA_ESTADO,
    larg_char, larg_texto,
    entra, sai, sobe, viva, pulso,
    titulo, rotulo, pilula, card, sombra, brilho,
    particulas, marca_dagua, grade_fundo,
)

RAIZ = Path(__file__).resolve().parent.parent.parent
ATIVOS = RAIZ / "public" / "comercial"


def asset(nome: str) -> str:
    return str(ATIVOS / nome)


def existe(nome: str) -> bool:
    return (ATIVOS / nome).exists()


# ── paleta ───────────────────────────────────────────────────────────────
# Estruturais: iguais as da referencia. Nao sao cor de marca, sao o oficio —
# quase-preto de fundo, borda a 10% de branco, cinza de rotulo.
BG = "#050505"
BG_CLARO = "#FAFAFA"
BG_GRADE = "#1A1B1F"
BG_SUP = "#0D0F14"
BG_SUP_CLARO = "#F0F0F0"
BORDA = "#FFFFFF1A"
BORDA_CLARA = "#FFFFFF40"
TEXTO = "#FFFFFF"
TEXTO_PRETO = "#0A0A0A"
MUDO = "#8B93A7"
MUDO_ESCURO = "#5B6474"
DIM = "#3A4152"

# De marca: o AZUL-VIOLETA da logo, amostrado de public/marca/klipe-logo.png —
# matiz 247 graus, o mesmo do degrade que corre pelo "K" e pela palavra. Eu
# vinha usando a laranja #E8940A, que e do `klipe-icon.svg` ANTIGO; a marca
# atual e a de public/marca/, e ela nao tem amarelo nenhum.
#
# Os tons do arquivo (#443E5F a #3A4982) sao feitos pra fundo claro, entao aqui
# eles sobem de saturacao e brilho pra aguentar o quase-preto — mesmo matiz,
# outra luz.
MARCA = "#7C6BE8"            # o indigo da marca
MARCA_CLARA = "#A99BFF"      # a ponta clara do degrade
MARCA_ESCURA = "#4C3C75"     # a ponta escura, como no arquivo
AZUL = "#3B82F6"
VERDE = "#10B981"
CIANO = "#22D3EE"
ROXO = "#C084FC"             # afastado do indigo pra nao virar a mesma cor
VERM = "#F43F5E"


# ── tema claro ───────────────────────────────────────────────────────────
# A referencia inverte o fundo uma vez no video inteiro, e e o que da ritmo na
# escala macro: quinze cenas escuras seguidas viram uma so. Metade e ainda
# melhor — a alternancia vira a batida do filme.
#
# Em vez de escrever cada cena duas vezes, a inversao e uma TRANSFORMACAO
# aplicada na montagem. Isso tem uma vantagem que a duplicacao nao tem: a cena
# so existe uma vez, entao clara e escura nunca divergem quando eu mexo numa.
#
# O mapa e explicito de proposito. Inverter por luminancia calculada chega a
# resultado plausivel e erra nas sombras — sombra continua PRETA no fundo
# claro, e uma regra automatica a viraria branca.
_CLARO = {
    # a escala neutra
    "050505": "FAFAFA", "0A0B0F": "16181D", "0A0A0A": "FFFFFF",
    "0D0F14": "FFFFFF", "0A0C11": "FFFFFF", "0B0E14": "F4F5F8",
    "141821": "ECEEF3", "0F1218": "F4F5F8", "080A0E": "EEF0F5",
    "1A1B1F": "DFE3EA", "FFFFFF": "16181D", "FAFAFA": "16181D",
    "F0F0F0": "16181D",
    # os cinzas de texto trocam de lado
    "8B93A7": "5B6474", "5B6474": "8A93A6", "8A93A6": "5B6474",
    "3A4152": "9AA2B2",
    # os acentos escurecem pra aguentar branco atras
    "7C6BE8": "5B4BC4", "A99BFF": "7C6BE8", "4C3C75": "4C3C75",
    "3B82F6": "2563EB", "10B981": "059669", "22D3EE": "0E7490",
    "C084FC": "9333EA", "F43F5E": "E11D48", "F59E0B": "B45309",
}


def _cor_clara(v):
    """Uma cor do tema escuro no equivalente do tema claro.

    Guarda o alfa: `#7C6BE81C` vira `#5B4BC41C`, entao brilho de fundo e borda
    continuam com a mesma forca relativa.
    """
    if isinstance(v, dict):                       # degrade
        out = dict(v)
        if "cores" in v:
            out["cores"] = [_cor_clara(c) for c in v["cores"]]
        return out
    if not isinstance(v, str) or not v.startswith("#"):
        return v
    corpo, alfa = v[1:7].upper(), v[7:]
    if corpo == "000000":                         # sombra continua preta
        return v
    if corpo == "FFFFFF" and alfa:                # verniz branco vira verniz preto
        return "#000000" + alfa
    return "#" + _CLARO.get(corpo, corpo) + alfa


_CAMPOS_COR = ("cor", "contorno")


def claro(spec: dict) -> dict:
    """Devolve a cena com o tema invertido. Nao mexe na original."""
    def trata(c: dict) -> dict:
        d = dict(c)
        for k in _CAMPOS_COR:
            if k in d:
                d[k] = _cor_clara(d[k])
        if isinstance(d.get("sombra"), list):
            d["sombra"] = [{**x, "cor": _cor_clara(x.get("cor", "#000000"))}
                           for x in d["sombra"]]
        if isinstance(d.get("camadas"), list):
            d["camadas"] = [trata(x) for x in d["camadas"]]
        return d
    return {**spec, "fundo": _cor_clara(spec.get("fundo", BG)),
            "camadas": [trata(c) for c in spec["camadas"]]}


# ── a sigla ──────────────────────────────────────────────────────────────
SIGLA = ["Kinetic", "Linking", "Intelligent", "Production", "Engine"]


def sigla(t0: float, y: float, tam: int = 30, gap: float = 26.0) -> list[dict]:
    """KLIPE nao e nome inventado: as cinco iniciais sao uma frase.

    A inicial fica na cor da marca e o resto apagado — quem olha um segundo le
    KLIPE, quem olha tres le a frase inteira. Uma camada por palavra, com a
    escada de BLOCO entre elas.
    """
    largs = [larg_texto(w, tam) for w in SIGLA]
    x = -(sum(largs) + gap * (len(SIGLA) - 1)) / 2
    out = []
    for i, (w, lw) in enumerate(zip(SIGLA, largs)):
        d = t0 + i * BLOCO
        li = larg_char(w[0], tam)
        out.append({
            "tipo": "texto", "texto": w[0], "tamanho": tam, "peso": 900,
            "cor": MARCA, "x": x + li / 2, "y": y, "opacidade": entra(d, 0.28),
            "escala": {"mola": MOLA_TEXTO, "em": d, "de": 0.78, "para": 1.0}})
        out.append({
            "tipo": "texto", "texto": w[1:], "tamanho": tam, "peso": 600,
            "cor": MUDO_ESCURO, "y": y,
            "x": x + li + larg_texto(w[1:], tam) / 2,
            "opacidade": entra(d + 0.08, 0.28)})
        x += lw + gap
    return out


def fim(dur: float, i: int = 0, n: int = 1) -> float:
    """A hora certa da i-esima linha de fecho, numa cena de `dur` segundos.

    Tudo que comeca a entrar nos ultimos TRANSICAO + 0.5 s sobe enquanto a
    cena ja esta descendo — vira fantasma. Este calculo poe a ULTIMA linha
    nesse limite e escalona as anteriores pra tras, entao a ordem de leitura
    se mantem e nenhuma cai dentro da transicao.
    """
    return dur - TRANSICAO - 0.5 - (n - 1 - i) * 0.28


# ── janela de aplicativo ─────────────────────────────────────────────────

def janela(x: float, y: float, larg: float, alt: float, t: float,
           s: int = 1, cor: str = "#0A0C11") -> list[dict]:
    """Moldura de janela: barra de titulo, tres botoes, corpo.

    A referencia tem `BrowserWindow` porque o produto dela mora no navegador.
    O Klipe e um aplicativo que sobe na sua maquina, entao a moldura e de
    janela mesmo — e e ela que enquadra toda tela de produto deste video.
    """
    topo = 44
    out = sombra(x, y, larg, alt, t, raio=14, n=3)
    out += [
        {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": 14, "cor": cor,
         "contorno": BORDA, "contorno_larg": 2, **viva(x, y, 2, s),
         "opacidade": entra(t, 0.3),
         "escala": {"mola": MOLA_ESTADO, "em": t, "de": 0.92, "para": 1.0}},
        {"tipo": "retangulo", "larg": larg - 4, "alt": topo, "raio": 12,
         "cor": "#141821", **viva(x, y + alt / 2 - topo / 2 - 2, 2, s),
         "opacidade": entra(t + 0.08, 0.25)},
    ]
    for i, c in enumerate(("#F43F5E", "#F59E0B", "#10B981")):
        out.append({
            "tipo": "elipse", "raio": 6, "cor": c,
            "x": x - larg / 2 + 30 + i * 22, "y": y + alt / 2 - topo / 2 - 2,
            "opacidade": entra(t + 0.16 + i * LETRA, 0.2),
            "escala": {"mola": MOLA_TEXTO, "em": t + 0.16 + i * LETRA,
                       "de": 0.0, "para": 1.0}})
    return out


def barra_titulo(x: float, y: float, larg: float, alt: float, txt: str,
                 t: float, cor: str = MUDO) -> dict:
    """O nome do projeto, no meio da barra de titulo da janela."""
    return {"tipo": "texto", "texto": txt, "tamanho": 18, "peso": 600,
            "cor": cor, "x": x, "y": y + alt / 2 - 24,
            "opacidade": entra(t + 0.2, 0.25)}


# ── no de fluxo ──────────────────────────────────────────────────────────

def no(x: float, y: float, larg: float, alt: float, t: float, cor: str,
       s: int = 1) -> list[dict]:
    """Caixa de etapa, no estilo dos `FlowNode` da referencia: fundo escuro,
    borda na cor da etapa, e um halo borrado atras que da o brilho."""
    return [
        {"tipo": "retangulo", "larg": larg + 30, "alt": alt + 30, "raio": 20,
         "cor": cor, "blur": 34, "x": x, "y": y,
         "opacidade": [[t, 0], [t + 0.5, 0.20, "outCubic"]]},
        {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": 14,
         "cor": BG_SUP, "contorno": cor + "99", "contorno_larg": 2,
         **viva(x, y, 2, s), "opacidade": entra(t, 0.28),
         "escala": {"mola": MOLA_ESTADO, "em": t, "de": 0.86, "para": 1.0}},
    ]


def aresta(x1: float, y1: float, x2: float, y2: float, t: float, cor: str,
           dur: float = 0.45) -> dict:
    """A ligacao entre duas etapas, que se DESENHA — `traco` corre o contorno,
    e por isso a linha e contorno e nao preenchimento."""
    return {"tipo": "linha", "de": [x1, -y1], "para": [x2, -y2],
            "contorno": cor, "contorno_larg": 3,
            "traco": [[t, 0.0, "outCubic"], [t + dur, 1.0]],
            "opacidade": [[t, 0], [t + 0.12, 0.85]]}


# ── medidor ──────────────────────────────────────────────────────────────

def barra_prog(x: float, y: float, larg: float, t: float, cor: str,
               dur: float = 1.2, alt: float = 10) -> list[dict]:
    """Trilho + preenchimento que corre. O preenchimento cresce por `escalaX`
    a partir da borda esquerda: por isso ele nasce com metade da largura de
    deslocamento, senao cresceria pros dois lados a partir do centro."""
    return [
        {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": alt / 2,
         "cor": "#FFFFFF14", "x": x, "y": y, "opacidade": entra(t, 0.25)},
        {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": alt / 2,
         "cor": cor, "x": [[t, x - larg / 2], [t + dur, x, "outCubic"]],
         "y": y, "opacidade": entra(t, 0.25),
         "escalaX": [[t, 0.0], [t + dur, 1.0, "outCubic"]]},
    ]
