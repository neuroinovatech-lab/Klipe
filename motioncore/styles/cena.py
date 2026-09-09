"""
cena.py — ponte entre o scene graph e o contrato de estilo do MotionCore.

De proposito minusculo. Entrar como estilo normal (`STYLES["cena"]`) e o que
faz o resto do sistema nao precisar saber que o scene graph existe: o cache de
titulo, o dedup de frame, o servidor de preview e o render continuam chamando
`build`/`draw`/`signature` como sempre chamaram.

O clip carrega a cena no campo `cena`, do mesmo jeito que o estilo `livre`
carrega `partes`.
"""
from __future__ import annotations

import skia

from ..cena import Cena
from ._common import TitleCtx


def _com_texto(spec: dict, texto: str) -> dict:
    """Enfia o texto DO CLIPE nos params da cena.

    Sem isto, uma cena usada como titulo desenha o texto que estava cravado no
    JSON e ignora o que a pessoa digitou — o campo "Texto" do painel nao faria
    nada, que e a diferenca entre um motion GRAVADO e um titulo REUTILIZAVEL.

    O texto do clipe GANHA de um `titulo` declarado na cena: o da cena e so o
    padrao de quem a escreveu. `linha1`/`linha2` saem da quebra, pra cena poder
    tratar chamada e complemento separados sem obrigar quem usa a saber disso.

    Copia rasa e suficiente: so `params` e trocado, e as camadas seguem
    compartilhadas — a cena original nao pode ser mutada, senao o segundo
    titulo que a usasse herdaria o texto do primeiro.
    """
    linhas = (texto or "").split("\n")
    novo = dict(spec)
    novo["params"] = {
        **(spec.get("params") or {}),
        "titulo": texto or "",
        "linha1": linhas[0] if linhas else "",
        "linha2": "\n".join(linhas[1:]),
    }
    return novo


def build(ctx: TitleCtx, registry, canvas_w: int, canvas_h: int):
    if not ctx.cena:
        return None
    return Cena(_com_texto(ctx.cena, ctx.text), canvas_w, canvas_h, ctx.fps, registry)


def draw(canvas: skia.Canvas, ctx: TitleCtx, registry, canvas_w: int, canvas_h: int,
         blocos=None):
    cena = blocos if isinstance(blocos, Cena) else build(ctx, registry, canvas_w, canvas_h)
    if cena is None:
        return
    cena.desenhar(canvas, ctx.frame / ctx.fps)


def signature(ctx: TitleCtx, blocos):
    if not isinstance(blocos, Cena):
        return None          # sem cena construida, quem renderiza desenha tudo
    return blocos.assinatura(ctx.frame / ctx.fps)
