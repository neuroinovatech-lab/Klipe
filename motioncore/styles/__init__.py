"""Registro de estilos portados pro MotionCore."""
from . import camera_follow, cena, livre, slide_reveal, stacked_reveal
from ._common import TitleCtx
from .basicos import ESTILOS as _BASICOS
from .motions import ESTILOS as _MOTIONS
from .restantes import ESTILOS as _RESTANTES

# Cada estilo expoe build(ctx, registry, w, h), draw(canvas, ctx, registry, w, h,
# blocos) e — opcionalmente — signature(ctx, blocos) pra pular frame repetido.
STYLES = {
    "stackedReveal": stacked_reveal,
    # o estilo que o criador de templates monta: N partes, cada uma com sua
    # fonte, tamanho, cor e animacao de entrada
    "livre": livre,
    # scene graph declarativo: o estilo que nao e um estilo — desenha o que a
    # cena mandar, em vez de um look fixo
    "cena": cena,
    "slideReveal": slide_reveal,
    "cameraFollow": camera_follow,
    **_BASICOS,
    **_RESTANTES,
    **_MOTIONS,
}

__all__ = ["STYLES", "TitleCtx"]
