"""
scene.py — o wrapper que o TitlesOverlay poe em volta de cada titulo.

Espelha o `<Sequence>` + `<AbsoluteFill>` de src/VideoEditor.tsx (~linha 7561):
posX/posY/scale/rotation/fontSize viram uma transform unica, e `opacity` do clip
multiplica tudo. Sem isso, um titulo com posY sairia no lugar errado mesmo com o
estilo perfeito.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import skia

from .fonts import FontRegistry
from .styles import STYLES, TitleCtx


@dataclass
class Title:
    """Um clip de titulo da timeline do Klipe."""
    startSec: float
    endSec: float
    text: str
    style: str
    posX: float = 0.0
    posY: float = 0.0
    scale: float = 1.0
    rotation: float = 0.0
    fontSize: float = 100.0
    opacity: float = 1.0
    fontFamily: str | None = None
    color: str | None = None
    font1: str | None = None
    font2: str | None = None
    font3: str | None = None
    color1: str | None = None
    color2: str | None = None
    color3: str | None = None
    scale1: float | None = None
    scale2: float | None = None
    scale3: float | None = None
    offsetX1: float | None = None
    offsetY1: float | None = None
    offsetX2: float | None = None
    offsetY2: float | None = None
    offsetX3: float | None = None
    offsetY3: float | None = None
    # lista de partes do estilo `livre` — tamanho livre, nao 3
    partes: list | None = None
    # scene graph declarativo do estilo `cena`
    cena: dict | None = None
    # Ajustes que so um estilo entende. Os campos acima (color1..3, scale1..3)
    # sao um formulario fixo herdado do motor de navegador: servem pra "ate tres
    # trechos de texto" e nao tem onde pendurar "quanto de ar a camera deixa".
    # Estilo novo declara os proprios ajustes aqui, com nome, em vez de
    # sequestrar um campo que quer dizer outra coisa.
    opcoes: dict | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Title":
        campos = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in campos})


class TitleRenderer:
    """
    Desenha UM titulo em qualquer frame. Mede uma vez e reusa: a medicao de
    texto (shaping) e o custo fixo por titulo, o desenho e o custo por frame.
    """

    def __init__(self, title: Title, width: int, height: int, fps: float = 30.0,
                 playback_rate: float = 1.0, registry: FontRegistry | None = None):
        if title.style not in STYLES:
            raise KeyError(f"estilo ainda nao portado pro MotionCore: {title.style!r}")
        self.title = title
        self.w, self.h, self.fps = width, height, fps
        self.registry = registry or FontRegistry()
        self.module = STYLES[title.style]
        # mesma conta do TitlesOverlay: secToFrame usa round, nao floor
        self.start_frame = round((title.startSec / playback_rate) * fps)
        self.duration_frames = round(((title.endSec - title.startSec) / playback_rate) * fps)
        self._ctx0 = self._ctx(0)
        self._blocos = self.module.build(self._ctx0, self.registry, self.w, self.h)

    def _ctx(self, frame: float) -> TitleCtx:
        t = self.title
        return TitleCtx(frame=frame, fps=self.fps, duration_frames=self.duration_frames,
                        larg=float(self.w), alt=float(self.h),
                        text=t.text, font_family=t.fontFamily, color=t.color,
                        font1=t.font1, font2=t.font2, font3=t.font3,
                        color1=t.color1, color2=t.color2, color3=t.color3,
                        scale1=t.scale1, scale2=t.scale2, scale3=t.scale3,
                        offsetX1=t.offsetX1, offsetY1=t.offsetY1,
                        offsetX2=t.offsetX2, offsetY2=t.offsetY2,
                        offsetX3=t.offsetX3, offsetY3=t.offsetY3,
                        partes=t.partes, cena=t.cena, opcoes=t.opcoes)

    def frame_signature(self, frame: float):
        """
        Identifica frames visualmente identicos. `None` quando o estilo nao
        sabe responder — nesse caso quem renderiza desenha tudo, sempre.
        """
        if frame < 0 or frame >= self.duration_frames:
            return ("fora",)
        sig = getattr(self.module, "signature", None)
        if sig is None:
            return None
        return sig(self._ctx(frame), self._blocos)

    def draw_frame(self, canvas: skia.Canvas, frame: float):
        """`frame` e relativo ao inicio do titulo (0 = primeiro frame dele)."""
        if frame < 0 or frame >= self.duration_frames:
            return
        t = self.title
        canvas.save()
        # A transform da AbsoluteFill do clip: origem no centro do canvas, que e
        # o centro da caixa de borda de um elemento que ocupa a tela toda.
        cx, cy = self.w / 2.0, self.h / 2.0
        canvas.translate(cx + t.posX, cy - t.posY)
        if t.rotation:
            canvas.rotate(t.rotation)
        # NAO existe escala automatica de formato aqui, e isso e deliberado.
        # Tentei `s = self.w / 1080` pra "consertar" o 16:9 e o resultado foi
        # 13 de 15 titulos vazando pra fora do quadro: os estilos JA sao
        # parcialmente responsivos — o `max_width` deles usa `canvas_w` — entao
        # multiplicar de novo conta duas vezes. Tamanho por formato e ajuste
        # de DESENHO, estilo a estilo, nao um multiplicador global.
        s = 1.0
        if t.scale and t.scale != 1:
            s *= t.scale
        if t.fontSize and t.fontSize != 100:
            s *= max(0.2, t.fontSize / 100.0)
        if s != 1.0:
            canvas.scale(s, s)
        canvas.translate(-cx, -cy)

        clip_op = 1.0 if t.opacity is None else max(0.0, min(1.0, t.opacity))
        if clip_op < 1.0:
            canvas.saveLayerAlpha(None, int(round(clip_op * 255)))
        self.module.draw(canvas, self._ctx(frame), self.registry, self.w, self.h,
                         blocos=self._blocos)
        if clip_op < 1.0:
            canvas.restore()
        canvas.restore()

    def render_still(self, frame: float) -> skia.Image:
        surface = skia.Surface(self.w, self.h)
        with surface as canvas:
            canvas.clear(skia.Color4f(0, 0, 0, 0))
            self.draw_frame(canvas, frame)
        return surface.makeImageSnapshot()
