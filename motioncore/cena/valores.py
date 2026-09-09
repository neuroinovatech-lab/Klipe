"""
valores.py — parametros, keyframes e easing do scene graph.

Uma cena e DADO, nao codigo. Isso decide duas coisas de produto:

  1. um LLM pode emitir uma cena sem que a gente execute nada que ele escreveu.
     O template do motor antigo resolve o mesmo problema compilando TSX gerado com
     Babel no browser do cliente — num sistema que a gente vende, isso e
     execucao de codigo arbitrario na maquina de quem comprou.

  2. o dedup de frame sai DE GRACA. Hoje cada estilo escreve sua propria
     `signature()` a mao, e quando ela deixa de espelhar o `draw()` o dedup
     mente e o video sai com frame errado (ja aconteceu). Aqui a assinatura e
     a tupla dos valores animados resolvidos no instante `t` — ela nao PODE
     divergir do desenho, porque e a mesma leitura.

Um valor animavel aparece em tres formas:

    82                          constante
    [[0, 0], [0.4, 1]]          keyframes: [t_em_segundos, valor, easing?]
    {"mola": {...}}             mola (o spring de referencia, pra manter paridade
                                com os 44 estilos ja portados)

O easing nomeado num keyframe vale pro trecho que COMECA nele.
"""
from __future__ import annotations

import math
from typing import Any

from ..anim import spring


# ── easing ───────────────────────────────────────────────────────────────
# Nomes em ingles de proposito: `outCubic` e vocabulario universal de motion,
# quem escreve cena (pessoa ou modelo) ja chega sabendo. As CHAVES do spec sao
# em portugues porque sao conceito nosso.
def _in_out(f):
    return lambda t: f(2 * t) / 2 if t < 0.5 else 1 - f(2 - 2 * t) / 2


_QUAD = lambda t: t * t
_CUBIC = lambda t: t ** 3
_QUART = lambda t: t ** 4
_QUINT = lambda t: t ** 5
_EXPO = lambda t: 0.0 if t <= 0 else 2 ** (10 * t - 10)
_SINE = lambda t: 1 - math.cos(t * math.pi / 2)
_CIRC = lambda t: 1 - math.sqrt(max(0.0, 1 - t * t))
_BACK = lambda t: 2.70158 * t ** 3 - 1.70158 * t * t


def _out(f):
    return lambda t: 1 - f(1 - t)


def _out_bounce(t: float) -> float:
    n, d = 7.5625, 2.75
    if t < 1 / d:
        return n * t * t
    if t < 2 / d:
        t -= 1.5 / d
        return n * t * t + 0.75
    if t < 2.5 / d:
        t -= 2.25 / d
        return n * t * t + 0.9375
    t -= 2.625 / d
    return n * t * t + 0.984375


def _out_elastic(t: float) -> float:
    if t <= 0 or t >= 1:
        return float(t)
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi / 3)) + 1


EASINGS: dict[str, Any] = {
    "linear": lambda t: t,
    "inQuad": _QUAD, "outQuad": _out(_QUAD), "inOutQuad": _in_out(_QUAD),
    "inCubic": _CUBIC, "outCubic": _out(_CUBIC), "inOutCubic": _in_out(_CUBIC),
    "inQuart": _QUART, "outQuart": _out(_QUART), "inOutQuart": _in_out(_QUART),
    "inQuint": _QUINT, "outQuint": _out(_QUINT), "inOutQuint": _in_out(_QUINT),
    "inExpo": _EXPO, "outExpo": _out(_EXPO), "inOutExpo": _in_out(_EXPO),
    "inSine": _SINE, "outSine": _out(_SINE), "inOutSine": _in_out(_SINE),
    "inCirc": _CIRC, "outCirc": _out(_CIRC), "inOutCirc": _in_out(_CIRC),
    "inBack": _BACK, "outBack": _out(_BACK), "inOutBack": _in_out(_BACK),
    "outElastic": _out_elastic,
    "outBounce": _out_bounce, "inBounce": _out(_out_bounce),
}
# `suave` e o default de trecho. NAO e linear: keyframe linear em motion
# graphics le como maquete, e o default tem que produzir a coisa certa pra quem
# escreveu a cena sem pensar em easing. Quem quer linear escreve "linear".
EASINGS["suave"] = EASINGS["inOutCubic"]
EASINGS["entra"] = EASINGS["inCubic"]
EASINGS["sai"] = EASINGS["outCubic"]


# ── bezier cubica ────────────────────────────────────────────────────────
# Os 31 easings nomeados cobrem o comum, mas motion design de verdade usa curva
# feita a mao: `[0.22, 1, 0.36, 1]` e a "cinematic" que aparece em toda peca
# boa, e nao existe entre os nomeados. Sem isto, portar uma curva de referencia
# obrigava a escolher o nomeado "mais parecido" — e parecido nao e igual.
#
# Newton-Raphson em x para achar t, depois avalia y. Oito passos bastam: o erro
# fica abaixo de 1e-6, que e menos de um decimo de pixel em qualquer animacao.
def _bezier(x1: float, y1: float, x2: float, y2: float):
    def _cur(a1, a2, t):
        return (((1 - 3 * a2 + 3 * a1) * t + (3 * a2 - 6 * a1)) * t + 3 * a1) * t

    def _slope(a1, a2, t):
        return 3 * (1 - 3 * a2 + 3 * a1) * t * t + 2 * (3 * a2 - 6 * a1) * t + 3 * a1

    def f(x: float) -> float:
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        t = x
        for _ in range(8):
            s = _slope(x1, x2, t)
            if abs(s) < 1e-6:
                break
            t -= (_cur(x1, x2, t) - x) / s
            t = min(1.0, max(0.0, t))
        return _cur(y1, y2, t)
    return f


def easing(nome):
    if not nome:
        return EASINGS["suave"]
    # forma bezier: [x1, y1, x2, y2] — os quatro pontos de controle do CSS
    if isinstance(nome, (list, tuple)):
        if len(nome) != 4:
            raise KeyError(f"bezier precisa de 4 numeros [x1,y1,x2,y2], veio {nome!r}")
        return _bezier(*(float(v) for v in nome))
    f = EASINGS.get(nome)
    if f is None:
        raise KeyError(f"easing desconhecido: {nome!r} "
                       f"(tem: {', '.join(sorted(EASINGS))}, ou [x1,y1,x2,y2])")
    return f


# ── parametros ("constants-first") ───────────────────────────────────────
# A unica ideia do template do motor antigo que vale copiar inteira: todo texto,
# cor e tempo declarado num bloco no topo, pra peca continuar EDITAVEL depois
# de gerada. La isso e convencao de prompt (o modelo "deve" declarar consts no
# topo); aqui e estrutura, entao nao tem como o gerador esquecer.
def aplicar_params(no: Any, params: dict) -> Any:
    """Troca "@nome" pelo valor do parametro, recursivamente.

    Roda UMA vez, na construcao da cena — nao por frame.
    """
    if isinstance(no, str):
        if no.startswith("@"):
            chave = no[1:]
            if chave not in params:
                raise KeyError(f"parametro nao declarado: @{chave}")
            return params[chave]
        return no
    if isinstance(no, list):
        return [aplicar_params(x, params) for x in no]
    if isinstance(no, dict):
        return {k: aplicar_params(v, params) for k, v in no.items()}
    return no


# ── resolucao de valor ───────────────────────────────────────────────────
def animado(v: Any) -> bool:
    """Keyframes ou mola. Constante nao entra na assinatura de frame."""
    if isinstance(v, list):
        return bool(v) and isinstance(v[0], (list, tuple))
    return isinstance(v, dict) and ("mola" in v or "ruido" in v)


def avaliar(v: Any, t: float, fps: float, default: float = 0.0) -> float:
    """Valor de `v` no instante `t` (segundos)."""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict) and "mola" in v:
        return _mola(v, t, fps)
    if isinstance(v, dict) and "ruido" in v:
        return _ruido(v, t, fps)
    if isinstance(v, list) and v and isinstance(v[0], (list, tuple)):
        return _keyframes(v, t)
    if isinstance(v, str):
        raise TypeError(f"valor numerico esperado, veio texto: {v!r} "
                        f"(faltou declarar o parametro?)")
    raise TypeError(f"valor nao entendido: {v!r}")


# ── ruido ────────────────────────────────────────────────────────────────
# A peca de referencia usa ruido em 114 lugares, e e o que separa "objeto
# parado" de "objeto vivo". Nao e efeito: e o micro-movimento que o olho
# registra sem perceber. Sem isto, tudo que nao esta animando fica MORTO.
#
# Value noise com interpolacao suave, nao Perlin de verdade: para deriva de
# 2 a 30 px a diferenca visual e nula, e cabe em 20 linhas sem dependencia.
#
# Determinismo importa mais que qualidade aqui — dois renders da mesma cena
# tem que sair identicos, senao o cache de frame por assinatura quebra.
def _hash01(n: int, semente: int) -> float:
    x = (n * 374761393 + semente * 668265263) & 0xFFFFFFFF
    x = (x ^ (x >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((x ^ (x >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF * 2.0 - 1.0


def _ruido1(x: float, semente: int) -> float:
    """Ruido em [-1, 1], continuo e derivavel o bastante para movimento."""
    i = math.floor(x)
    f = x - i
    # smoothstep entre as duas ancoras: sem isto o movimento tem quinas
    u = f * f * (3.0 - 2.0 * f)
    return _hash01(int(i), semente) * (1 - u) + _hash01(int(i) + 1, semente) * u


def _ruido(v: dict, t: float, fps: float) -> float:
    """{"ruido": {"escala": 0.01, "amp": 8, "base": 0, "semente": 1}}

    `escala` e por FRAME, como no material de referencia, para os numeros de
    la valerem aqui sem conversao:

        0.003-0.005  deriva lenta (~10 s de periodo) — marca d'agua, glow
        0.006-0.008  micro-deriva de card, tremor de camera (~5 s)
        0.01 -0.015  flutuacao de elemento, particula, logo (~3 s)
        0.02 -0.03   pulso de brilho, faisca (~1,5 s)
        0.04 -0.06   barra de onda, LED piscando (~0,8 s)
        0.1          tremor violento

    Amplitude tipica: 2-4 px (micro), 5-8 (logo), 10-20 (particula),
    25-30 (blob de fundo). Para pulso, use `base` e mantenha
    `amp` entre 25% e 50% dele — assim nunca zera nem dobra.
    """
    cfg = v["ruido"] if isinstance(v["ruido"], dict) else {}
    escala = float(cfg.get("escala", 0.01))
    amp = float(cfg.get("amp", 1.0))
    base = float(cfg.get("base", 0.0))
    semente = int(cfg.get("semente", 1))
    return base + amp * _ruido1(t * fps * escala, semente)


def _mola(v: dict, t: float, fps: float) -> float:
    cfg = v["mola"] if isinstance(v["mola"], dict) else {}
    em = float(v.get("em", cfg.get("em", 0.0)))
    de = float(v.get("de", 0.0))
    para = float(v.get("para", 1.0))
    # `frame` relativo ao inicio da mola — o mesmo truque que os estilos
    # portados fazem na mao com `Math.max(0, frame - i*5)`
    frame = max(0.0, (t - em) * fps)
    return spring(frame, fps,
                  damping=float(cfg.get("damping", 14.0)),
                  mass=float(cfg.get("mass", 1.0)),
                  stiffness=float(cfg.get("stiffness", 200.0)),
                  overshoot_clamping=bool(cfg.get("clamp", False)),
                  from_=de, to=para)


def _keyframes(ks: list, t: float) -> float:
    """Interpola entre keyframes. Fora do range, segura o valor da ponta."""
    if len(ks) == 1:
        return float(ks[0][1])
    if t <= ks[0][0]:
        return float(ks[0][1])
    if t >= ks[-1][0]:
        return float(ks[-1][1])
    for i in range(len(ks) - 1):
        t0, v0 = float(ks[i][0]), float(ks[i][1])
        t1, v1 = float(ks[i + 1][0]), float(ks[i + 1][1])
        if t0 <= t <= t1:
            if t1 <= t0:
                return v1
            # o easing nomeado no keyframe i governa o trecho i -> i+1
            nome = ks[i][2] if len(ks[i]) > 2 else None
            f = easing(nome)
            return v0 + (v1 - v0) * f((t - t0) / (t1 - t0))
    return float(ks[-1][1])


def medida(v: Any, t: float, fps: float, total: float, default: float = 0.0) -> float:
    """Como `avaliar`, mas aceita "50%" — fracao de `total`.

    A origem e o CENTRO do quadro (mesma convencao do posX/posY do clip), entao
    "0%" e o centro e "50%" e a borda direita. Escrever em % e o que faz a mesma
    cena servir 1080x1920 e 1920x1080 sem reescrever coordenada.
    """
    if isinstance(v, str) and v.rstrip().endswith("%"):
        return float(v.rstrip().rstrip("%")) / 100.0 * total
    return avaliar(v, t, fps, default)


def assinatura(v: Any, t: float, fps: float, total: float | None = None):
    """O que este valor contribui pra assinatura do frame — `None` se constante."""
    if not animado(v):
        return None
    bruto = medida(v, t, fps, total) if total is not None else avaliar(v, t, fps)
    # 1e-4 px: abaixo disso dois frames sao o mesmo pixel depois do antialias.
    # Mesma logica do `round(current, 6)` no spring — quem desenha e quem
    # compara precisam ler o MESMO numero, senao o dedup nunca acerta.
    return round(bruto, 4)
