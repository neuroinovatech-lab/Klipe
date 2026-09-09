"""
_common.py — as primitivas que TODO estilo do ViralTitle compartilha.

Espelha o topo de `ViralTitle` em o template antigo (linhas ~488-519): os
mesmos springs, os mesmos ranges de interpolate. Qualquer estilo portado
comeca daqui, senao a entrada/saida ja nasce fora de sincronia com O motor de navegador.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..anim import interpolate, spring


@dataclass
class TitleCtx:
    """O que o ViralTitle recebe e deriva, por frame."""
    frame: float
    fps: float
    duration_frames: int
    text: str
    # O FORMATO do quadro. Estava faltando, e a falta custou caro: sem saber a
    # altura, um estilo so podia usar pixel absoluto, e pixel absoluto afinado
    # pra 1920 nasce fora de um quadro de 1080.
    larg: float = 1080.0
    alt: float = 1920.0
    # overrides que vem do clip na timeline
    font_family: str | None = None
    color: str | None = None
    font1: str | None = None
    font2: str | None = None
    font3: str | None = None
    color1: str | None = None
    color2: str | None = None
    color3: str | None = None

    # ── primitivas compartilhadas ─────────────────────────────────────────
    ALT_REF = 1920.0          # a altura pra qual os estilos foram afinados

    @property
    def ev(self) -> float:
        """Escala VERTICAL: quanto o quadro atual e mais curto que a referencia.

        1.0 em 1080x1920 — nada muda no formato de origem, e essa e a garantia
        que torna isto seguro. 0.5625 em 1920x1080.

        E preciso dizer por que nao e `larg / 1080`: essa foi tentada antes e
        vazou 13 de 15 titulos (a nota esta em `scene.py`). O motivo e que ela
        da 1.78 em 16:9 — AUMENTA o que ja nao cabia. O eixo errado. Pela
        altura da 0.56, que e a direcao certa: quadro mais baixo, peca menor.

        E nao vira multiplicador global: so os estilos que usam pixel vertical
        absoluto consultam isto. Os 19 que ja cabem nos dois formatos nao
        encostam nela — encolher quem ja estava bom deixaria titulo minusculo
        em video horizontal.
        """
        return float(self.alt) / self.ALT_REF

    @property
    def enter(self) -> float:
        return spring(self.frame, self.fps, damping=14, stiffness=200, mass=0.6)

    @property
    def exit_prog(self) -> float:
        return interpolate(self.frame,
                           [self.duration_frames - 12, self.duration_frames], [0, 1],
                           "clamp", "clamp")

    @property
    def opacity(self) -> float:
        """`opacity` do ViralTitle: some na saida e respeita a entrada do spring."""
        return interpolate(self.exit_prog, [0, 1], [1, 0]) * min(self.enter, 1.0)

    # overrides por PARTE, usados pelos estilos compostos
    scale1: float | None = None
    scale2: float | None = None
    scale3: float | None = None
    offsetX1: float | None = None
    offsetY1: float | None = None
    offsetX2: float | None = None
    offsetY2: float | None = None
    offsetX3: float | None = None
    offsetY3: float | None = None
    # partes do estilo `livre` (lista de dicts) — os outros estilos ignoram
    partes: list | None = None
    # scene graph do estilo `cena` (dict declarativo) — idem
    cena: dict | None = None
    # ajustes nomeados que so um estilo entende (ver `Title.opcoes`)
    opcoes: dict | None = None

    def opcao(self, nome: str, tabela: dict, padrao: str):
        """Escolhe numa tabela de opcoes nomeadas, caindo no padrao.

        Vale pro valor ausente E pro valor que nao existe na tabela: template
        antigo (sem a opcao) e template com nome escrito errado tem que dar os
        dois no MESMO desenho conhecido, nunca em erro nem em tela preta.
        """
        v = (self.opcoes or {}).get(nome)
        return tabela[v] if v in tabela else tabela[padrao]

    # ── helpers de override (font()/clr()/partFont() do TSX) ──────────────
    def font(self, default_css: str) -> str:
        return f"'{self.font_family}', sans-serif" if self.font_family else default_css

    @property
    def clr(self) -> str:
        return self.color or "#FFFFFF"

    def part_font(self, i: int, default_css: str) -> str:
        pf = [self.font1, self.font2, self.font3][i]
        return f"'{pf}', sans-serif" if pf else self.font(default_css)

    def part_clr(self, i: int) -> str:
        return [self.color1, self.color2, self.color3][i] or self.clr

    def part_scale(self, i: int) -> float:
        v = [self.scale1, self.scale2, self.scale3][i]
        return 1.0 if v is None else float(v)

    def part_offset(self, i: int) -> tuple[float, float]:
        """`y` vem invertido do TSX: posY positivo SOBE."""
        x = [self.offsetX1, self.offsetX2, self.offsetX3][i]
        y = [self.offsetY1, self.offsetY2, self.offsetY3][i]
        return (0.0 if x is None else float(x), -(0.0 if y is None else float(y)))


def css_opacity(v: float) -> float:
    """O CSS limita `opacity` a [0,1] — o spring pode passar de 1 no overshoot."""
    return max(0.0, min(1.0, v))
