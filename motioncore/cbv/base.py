# -*- coding: utf-8 -*-
"""
base.py — vocabulario comum das 17 cenas do CreativlyBrandVideo no MotionCore.

Existe para que 17 cenas escritas separadamente saiam como UM video, e nao como
17 dialetos. Tudo que se repete entre cenas mora aqui: paleta, tipografia,
medicao de texto, e os gestos que o material de referencia usa em toda parte
(titulo letra a letra, pilula, card, brilho de fundo, particulas).

TUDO AQUI SAIU DE MEDIR O ORIGINAL. As cores sao o `constants.ts`; os tempos de
mola e cascata sairam de contar ocorrencias no `src/`; as armadilhas comentadas
sao erros que eu ja cometi neste motor e nao quero ver de novo.

AS ARMADILHAS DO DSL — leia antes de escrever cena:

  1. `x` de TEXTO e o CENTRO do bloco, nao a borda. Nao da para "continuar de
     onde o anterior parou" sem medir: use `larg_texto()` daqui.

  2. `traco` corre o CONTORNO. Forma preenchida nao tem traco para correr —
     para desenhar um anel, use `cor: "#00000000"` + `contorno`.

  3. `repetir` CENTRA a grade na posicao da camada, nao parte dela. E aplica a
     MESMA animacao a todas as copias: serve para textura de fundo, nunca para
     elemento que precisa de identidade propria.

  4. `blur` NAO e animavel. Valor fixo por camada.

  5. `y` positivo SOBE na camada. Dentro de `path` e de `linha`, `y` DESCE.

  6. Easing so no keyframe que COMECA o trecho; no ultimo e ignorado.
"""
from __future__ import annotations

import os
from pathlib import Path

# ── formato ──────────────────────────────────────────────────────────────
W, H, FPS = 1920, 1080, 30
F = 1.0 / FPS

# pasta de assets do projeto de referencia
ASSETS = Path(os.environ.get(
    "KLIPE_CBV_ASSETS",
    Path(__file__).resolve().parents[2] / "referencias" / "creativly-brand-video" / "public",
))


def asset(nome: str) -> str:
    return str(ASSETS / nome)


# ── paleta: constants.ts:7-30, valores exatos ────────────────────────────
BG = "#050505"
BG_BRANCO = "#FAFAFA"
BG_GRID = "#222222"
BG_SUP = "#111111"
BG_SUP_CLARO = "#F0F0F0"
BORDA = "#FFFFFF1A"          # rgba(255,255,255,0.1)
BORDA_CLARA = "#FFFFFF40"    # rgba(255,255,255,0.25)
TEXTO = "#ffffff"
TEXTO_PRETO = "#0A0A0A"
MUDO = "#a1a1aa"
MUDO_ESCURO = "#6b7280"
DIM = "#525252"
PRIMARIA = "#3b82f6"
SECUNDARIA = "#8b5cf6"
ACENTO = "#f43f5e"
SUCESSO = "#10b981"
AVISO = "#f59e0b"
MARCA = "#3B82F6"
MARCA_CLARA = "#67E8F9"
MARCA_ESCURA = "#2563EB"
CIANO = "#06B6D4"

# ── ritmo: a escada de cascata medida no original ────────────────────────
LETRA = 1.5 * F      # 1-2 frames entre letras
PALAVRA = 3 * F      # 3 entre palavras
BLOCO = 5 * F        # 5 entre blocos/cards
TRANSICAO = 20 * F   # constants.ts:54 — TRANSITION_FRAMES

# ── molas: as tres familias, medidas ─────────────────────────────────────
# texto entrando — chega e para. Overshoot <=1%: texto que balanca fica ilegivel
MOLA_TEXTO = {"damping": 14, "stiffness": 110, "mass": 0.5}
# UM destaque por cena — o unico lugar onde o pulo aparece
MOLA_DESTAQUE = {"damping": 10, "stiffness": 150, "mass": 0.6}
# mudanca de estado — overshoot zero. Estado de UI que quica parece defeito
MOLA_ESTADO = {"damping": 200, "stiffness": 120, "mass": 0.6}


# ── medicao de texto ─────────────────────────────────────────────────────
# ANTES isto era um chute de tres classes de largura, e o chute errava feio: no
# Montserrat 900, `J` sai 86% mais largo que a estimativa e `W` 22%. Num titulo
# de dez letras a 200px o erro somava centenas de pixels — foi o que fez
# "KLIPE" sair "KL I PE", com um vao dos dois lados do I.
#
# O ironico e que o motor SEMPRE soube medir: o `FontRegistry` carrega os
# arquivos de fonte e o `TextBlock` usa shaping de verdade pra desenhar os
# titulos. Quem chutava era so o DSL — o mesmo projeto tinha os dois.
#
# Agora a largura vem do AVANCO REAL do glifo, na fonte, no peso e no tamanho
# que vao ser desenhados. A heuristica fica de reserva: se o registro de fontes
# nao subir, o DSL erra o espacamento em vez de derrubar o render.
_ESTREITAS = set("ilj.,;:!|'()[]{}t IJ")
_LARGAS = set("mwMW@")

# o mesmo padrao do desenho — `camadas.py:134` usa "'Inter', sans-serif"
FONTE_PADRAO = "'Inter', sans-serif"
_reg = None
_fontes: dict = {}


def _fonte(tam: float, fam: str, peso: int, italico: bool):
    """A `skia.Font` pronta pra medir. Cacheada: resolver a face e construir a
    fonte custa, e uma cena chama isto uma vez por LETRA."""
    global _reg
    chave = (fam, peso, italico, round(float(tam), 2))
    f = _fontes.get(chave)
    if f is not None:
        return f
    try:
        if _reg is None:
            import skia                       # noqa: F401
            from ..fonts import FontRegistry
            _reg = FontRegistry()
        import skia
        face = _reg.resolve(fam, peso, italico)
        f = skia.Font(face.typeface, float(tam))
    except Exception:
        f = False                             # marca "nao da", sem tentar de novo
    _fontes[chave] = f
    return f


def _chute(ch: str, tam: float) -> float:
    return (0.30 if ch in _ESTREITAS else 0.92 if ch in _LARGAS
            else 0.68 if ch.isupper() else 0.56) * tam


def larg_char(ch: str, tam: float, peso: int = 700,
              fonte: str | None = None, italico: bool = False) -> float:
    f = _fonte(tam, fonte or FONTE_PADRAO, peso, italico)
    return f.measureText(ch) if f else _chute(ch, tam)


def larg_texto(txt: str, tam: float, peso: int = 700,
               fonte: str | None = None, italico: bool = False) -> float:
    """SOMA dos avancos, nao a medida da linha inteira.

    Parece detalhe e nao e: `titulo()` posiciona letra por letra acumulando
    `larg_char`. Se a largura total viesse da medida com kerning — que e um
    pouco menor — o centro calculado nao bateria com a soma das posicoes, e o
    bloco inteiro sairia torto pra um lado.
    """
    f = _fonte(tam, fonte or FONTE_PADRAO, peso, italico)
    if not f:
        return sum(_chute(c, tam) for c in txt)
    return sum(f.measureText(c) for c in txt)


# ── gestos ───────────────────────────────────────────────────────────────

def entra(t: float, dur: float = 0.4) -> list:
    """A curva unica de entrada. No original: 31 usos de out(cubic) contra 1
    de bezier — o oficio nao esta na variedade de curva."""
    return [[t, 0], [t + dur, 1, "outCubic"]]


def sai(t: float, dur: float = 0.3) -> list:
    return [[t, 1], [t + dur, 0, "outCubic"]]


def sobe(t: float, y: float, de: float = 30, dur: float = 0.42) -> list:
    return [[t, y - de], [t + dur, y, "outCubic"]]


def viva(x: float, y: float, amp: float = 3.0, s: int = 1) -> dict:
    """Micro-deriva por ruido. E o que separa objeto parado de objeto vivo.

    Sementes DIFERENTES por eixo — com a mesma, o objeto desliza na diagonal.
    Y com METADE da amplitude: tremor vertical le como defeito de render,
    horizontal le como energia.
    """
    return {
        "x": {"ruido": {"escala": 0.008, "amp": amp, "base": x, "semente": s}},
        "y": {"ruido": {"escala": 0.008, "amp": amp / 2, "base": y,
                        "semente": s + 5000}},
    }


def pulso(base: float, amp: float, escala: float = 0.02, s: int = 1) -> dict:
    """Respiracao que nunca zera nem dobra. No original a amplitude fica
    sempre entre 25% e 50% da base."""
    return {"ruido": {"escala": escala, "amp": amp, "base": base, "semente": s}}


def titulo(txt: str, t0: float, y: float, tam: int, cor: str = TEXTO,
           peso: int = 900, passo: float = LETRA, x0: float = 0.0,
           italico: bool = False) -> list[dict]:
    """Titulo letra a letra, mola da familia TEXTO."""
    x = x0 - larg_texto(txt, tam, peso, italico=italico) / 2
    out = []
    for i, ch in enumerate(txt):
        w = larg_char(ch, tam, peso, italico=italico)
        if ch != " ":
            d = t0 + i * passo
            out.append({
                "tipo": "texto", "texto": ch, "tamanho": tam, "peso": peso,
                "cor": cor, "italico": italico, "x": x + w / 2,
                "y": sobe(d, y, tam * 0.2),
                "opacidade": entra(d, 0.22),
                "escala": {"mola": MOLA_TEXTO, "em": d, "de": 0.84, "para": 1.0},
            })
        x += w
    return out


def rotulo(txt: str, t: float, y: float, cor: str = MUDO, tam: int = 24,
           x: float = 0.0, esp: int = 3, peso: int = 600) -> dict:
    """Rotulo pequeno, com micro-vida."""
    return {"tipo": "texto", "texto": txt, "tamanho": tam, "peso": peso,
            "cor": cor, "espacamento": esp, **viva(x, y, 2, hash(txt) % 900),
            "opacidade": entra(t, 0.3)}


def pilula(nome: str, t: float, x: float, y: float, cor: str = MARCA,
           tam: int = 32, ativa: list | None = None) -> list[dict]:
    """Pilula do original: padding 16/40, raio 100, fonte 32.

    `ativa` e a lista de keyframes de opacidade da versao ACESA. O motor nao
    tem estado — estado vira tempo, cruzando duas versoes por opacidade.
    """
    larg = larg_texto(nome, tam) + 80
    alt = tam + 32
    base = [
        {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": 100,
         "cor": "#FFFFFF08", "contorno": BORDA, "contorno_larg": 1,
         "x": x, "y": y, "opacidade": entra(t, 0.3),
         "escala": {"mola": MOLA_TEXTO, "em": t, "de": 0.86, "para": 1.0}},
        {"tipo": "texto", "texto": nome, "tamanho": tam, "peso": 700,
         "cor": MUDO, "x": x, "y": y - 2, "opacidade": entra(t, 0.3)},
    ]
    if ativa:
        base += [
            {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": 100,
             "cor": cor, "x": x, "y": y, "opacidade": ativa},
            {"tipo": "texto", "texto": nome, "tamanho": tam, "peso": 700,
             "cor": "#000000", "x": x, "y": y - 2, "opacidade": ativa},
        ]
    return base


def card(x: float, y: float, larg: float, alt: float, t: float,
         cor: str = "#0C1018", borda: str = BORDA, raio: int = 16,
         s: int = 1) -> dict:
    """Card de UI. Mola de ESTADO — sem quique."""
    return {"tipo": "retangulo", "larg": larg, "alt": alt, "raio": raio,
            "cor": cor, "contorno": borda, "contorno_larg": 1,
            **viva(x, y, 2.5, s), "opacidade": entra(t, 0.3),
            "escala": {"mola": MOLA_ESTADO, "em": t, "de": 0.9, "para": 1.0}}


def sombra(x: float, y: float, larg: float, alt: float, t: float,
           raio: int = 16, n: int = 3) -> list[dict]:
    """Sombra em camadas — o motor nao tem box-shadow multiplo, entao ela e
    desenhada: N retangulos maiores, deslocados para baixo, com alpha caindo."""
    out = []
    for k in range(n, 0, -1):
        e = 1 + k * 0.02
        out.append({
            "tipo": "retangulo", "larg": larg * e, "alt": alt * e,
            "raio": raio + k * 3, "cor": "#000000",
            "x": x, "y": y - k * 8, "blur": 8 + k * 10,
            "opacidade": [[t, 0], [t + 0.4, 0.30 / k, "outCubic"]]})
    return out


def brilho(x: float, y: float, raio: float, cor: str, t: float = 0.0,
           op: float = 0.35, s: int = 1) -> dict:
    """Mancha de luz ao fundo. Respira por ruido, como no original."""
    return {"tipo": "elipse", "raio": raio, **viva(x, y, 20, s),
            "cor": {"tipo": "radial", "cores": [cor, "#00000000"], "raio": raio},
            "opacidade": [[t, 0], [t + 0.9, op, "outCubic"]]}


def particulas(n: int = 24, cor: str = MARCA, cor2: str | None = None,
               amp: float = 20, semente: int = 0) -> list[dict]:
    """Poeira de fundo. Cada uma e uma camada — com `repetir` todas derivariam
    igual, e o que faz parecer poeira e cada uma ir para um lado."""
    out = []
    for i in range(n):
        bx = (((i * 37 + semente) % 100) / 100 - 0.5) * W
        by = (((i * 61 + semente) % 100) / 100 - 0.5) * H
        out.append({
            "tipo": "elipse", "raio": 1 + (i % 3),
            "cor": cor2 if (cor2 and i % 3 == 0) else cor,
            "x": {"ruido": {"escala": 0.015, "amp": amp, "base": bx,
                            "semente": 100 + i + semente}},
            "y": {"ruido": {"escala": 0.015, "amp": amp, "base": by,
                            "semente": 900 + i + semente}},
            "opacidade": pulso(0.45, 0.25, 0.06, 300 + i),
        })
    return out


def marca_dagua(txt: str, tam: int = 400, cor: str = MARCA, rot: float = 0.0,
                op: float = 0.05, y: float = 0.0) -> dict:
    """Tipografia gigante ao fundo. E o que da profundidade sem ocupar espaco
    — o original usa em quase toda cena, cortada pela borda."""
    return {"tipo": "texto", "texto": txt, "tamanho": tam, "peso": 900,
            "italico": True, "cor": cor, "rotacao": rot, "y": y,
            "espacamento": -tam // 20,
            "opacidade": [[0, 0], [1.0, op, "outCubic"]]}


def grade_fundo(esp: int = 80, cor: str = BG_GRID, op: float = 0.5) -> list[dict]:
    """Grade tenue. Aqui `repetir` E o certo: e textura, nao elemento."""
    return [
        {"tipo": "retangulo", "larg": 1, "alt": H, "cor": cor,
         "x": -W / 2, "y": 0, "opacidade": [[0, 0], [0.8, op]],
         "repetir": {"cols": W // esp + 1, "linhas": 1, "espX": esp,
                     "espY": 0, "atraso": 0.004, "ordem": "linha"}},
        {"tipo": "retangulo", "larg": W, "alt": 1, "cor": cor,
         "x": 0, "y": -H / 2, "opacidade": [[0, 0], [0.8, op]],
         "repetir": {"cols": 1, "linhas": H // esp + 1, "espX": 0,
                     "espY": esp, "atraso": 0.004, "ordem": "linha"}},
    ]
