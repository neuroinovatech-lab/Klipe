"""
anim.py — primitivas de animacao do motor de navegador portadas 1:1 pro Python.

Nao e "parecido": e a MESMA matematica. O spring de referencia nao e formula
fechada — e uma integracao iterativa, um passo por frame, com deltaTime
limitado a 64ms. Reimplementar por formula analitica da valores proximos mas
nao identicos, e a diferenca aparece justo no comeco da animacao (onde o olho
mais percebe). Entao aqui a gente repete o loop dele.

Referencia: a implementacao de referencia do spring
            a implementacao de referencia do interpolate
"""
from __future__ import annotations

import math
from typing import Sequence

# defaultSpringConfig do motor de navegador
_DEFAULT_SPRING = {"damping": 10.0, "mass": 1.0, "stiffness": 100.0, "overshootClamping": False}

# O loop de spring roda 1x por frame por chamada. Um titulo de 10s a 30fps com
# 4 linhas = 1200 chamadas, cada uma refazendo o loop inteiro do zero (O(n^2)).
# O motor de navegador tem o mesmo problema e resolve com cache — a gente tambem.
_spring_cache: dict[tuple, float] = {}


def _advance(current: float, velocity: float, last_ts: float, now: float,
             damping: float, mass: float, stiffness: float) -> tuple[float, float]:
    """Um passo de integracao. Espelha `advance()` do spring-utils.js."""
    to_value = 1.0
    delta_time = min(now - last_ts, 64.0)
    if damping <= 0:
        raise ValueError("spring damping tem que ser > 0")

    v0 = -velocity
    x0 = to_value - current
    zeta = damping / (2 * math.sqrt(stiffness * mass))
    omega0 = math.sqrt(stiffness / mass)
    omega1 = omega0 * math.sqrt(1 - zeta ** 2) if zeta < 1 else 0.0
    t = delta_time / 1000.0

    if zeta < 1:
        sin1 = math.sin(omega1 * t)
        cos1 = math.cos(omega1 * t)
        envelope = math.exp(-zeta * omega0 * t)
        frag1 = envelope * (sin1 * ((v0 + zeta * omega0 * x0) / omega1) + x0 * cos1)
        position = to_value - frag1
        vel = (zeta * omega0 * frag1
               - envelope * (cos1 * (v0 + zeta * omega0 * x0) - omega1 * x0 * sin1))
    else:
        envelope = math.exp(-omega0 * t)
        position = to_value - envelope * (x0 + (v0 + omega0 * x0) * t)
        vel = envelope * (v0 * (t * omega0 - 1) + t * x0 * omega0 * omega0)

    return position, vel


def spring(frame: float, fps: float, damping: float = 10.0, mass: float = 1.0,
           stiffness: float = 100.0, overshoot_clamping: bool = False,
           from_: float = 0.0, to: float = 1.0) -> float:
    """
    Equivalente a `spring({frame, fps, config})` do motor de navegador.

    So cobre o caminho que os estilos usam: sem durationInFrames, sem reverse,
    sem delay (o codigo dos estilos faz o delay na mao, passando
    `frame: Math.max(0, frame - i*5)`).
    """
    key = (frame, fps, damping, mass, stiffness, overshoot_clamping)
    cached = _spring_cache.get(key)
    if cached is None:
        current, velocity, last_ts = 0.0, 0.0, 0.0
        frame_clamped = max(0.0, frame)
        uneven_rest = frame_clamped % 1
        floor = math.floor(frame_clamped)
        f = 0
        while f <= floor:
            # o loop do motor de navegador faz `f += unevenRest` no ultimo passo pra
            # suportar frame fracionario (usado quando ha playbackRate)
            step = f + uneven_rest if f == floor else float(f)
            now = (step / fps) * 1000.0
            current, velocity = _advance(current, velocity, last_ts, now,
                                         damping, mass, stiffness)
            last_ts = now
            f += 1
        # Arredondar aqui (e nao so na assinatura de frame) e o que torna o
        # "pular frame repetido" seguro: o spring converge assintoticamente e
        # nunca chega a um valor fixo, entao sem isso dois frames visualmente
        # identicos teriam valores diferentes na 12a casa. Quem desenha e quem
        # compara passam a ler o MESMO numero. 1e-6 e imperceptivel: num
        # titulo de 160 px isso e 0,00016 px.
        cached = round(current, 6)
        _spring_cache[key] = cached

    inner = cached
    if overshoot_clamping:
        inner = min(inner, to) if to >= from_ else max(inner, to)
    if from_ == 0.0 and to == 1.0:
        return inner
    return interpolate(inner, [0.0, 1.0], [from_, to])


def interpolate(value: float, input_range: Sequence[float], output_range: Sequence[float],
                extrapolate_left: str = "extend", extrapolate_right: str = "extend") -> float:
    """
    Equivalente a `interpolate()` do motor de navegador.

    Default e "extend" nos dois lados — importante: o `scale` do stackedReveal
    depende disso pra estourar acima de 1 quando o spring da overshoot. Trocar
    por clamp mataria o "pop" da animacao.
    """
    n = len(input_range)
    if n != len(output_range):
        raise ValueError("input_range e output_range precisam do mesmo tamanho")
    if n < 2:
        raise ValueError("range precisa de pelo menos 2 pontos")

    # acha o segmento
    i = 0
    while i < n - 2 and value >= input_range[i + 1]:
        i += 1

    in0, in1 = input_range[i], input_range[i + 1]
    out0, out1 = output_range[i], output_range[i + 1]

    if value < input_range[0]:
        if extrapolate_left == "clamp":
            return output_range[0]
        if extrapolate_left == "identity":
            return value
    if value > input_range[-1]:
        if extrapolate_right == "clamp":
            return output_range[-1]
        if extrapolate_right == "identity":
            return value

    if in1 == in0:
        return out0
    return out0 + (value - in0) * (out1 - out0) / (in1 - in0)
