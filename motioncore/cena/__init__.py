"""
cena — o scene graph declarativo do MotionCore.

O motor sabia desenhar qualquer coisa (o Skia nao tem limite), mas o CONTRATO
so aceitava estilo hardcoded: um modulo Python por look, catalogo fechado de 44.
A liberdade existia embaixo e estava murada em cima. Esta pasta abre a mureta.

Uma cena e um dict JSON-serializavel:

    {
      "duracao": 4.0,                       # segundos (opcional)
      "params": {"titulo": "AGORA", "cor": "#F5C518"},
      "camadas": [
        {"tipo": "retangulo", "larg": "60%", "alt": 160, "cor": "@cor",
         "escalaX": [[0, 0], [0.35, 1, "outCubic"]]},
        {"tipo": "texto", "texto": "@titulo", "tamanho": 120, "peso": 900,
         "y": {"mola": {"damping": 14}, "de": -60, "para": 0},
         "opacidade": [[0, 0], [0.25, 1]]}
      ]
    }

Tres coisas que isso resolve e o modulo-por-estilo nao resolvia:

  - **e dado**: um modelo emite cena sem que a gente execute codigo dele. Sem
    sandbox, sem Babel no browser do cliente.
  - **hasheia**: entra no cache de titulo e no dedup de frame que ja existem,
    sem uma linha nova nos dois.
  - **edita**: o criador de template passa a mexer na cena direto, em vez de
    escolher de uma lista fechada.

O que ela NAO tenta ser: Turing-completa. Quando a peca precisa de algo que o
DSL nao expressa — a hachura de buril do RadiusMotion, `PathMeasure` com
logica propria, filtro de imagem — o caminho continua sendo um modulo Python
em `styles/`. DSL pros 95%, codigo pros 5% que sao de verdade novos. E assim
que esse tipo de projeto evita virar uma linguagem de programacao em JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import skia

from ..fonts import FontRegistry
from . import camadas as _cam
from .camadas import Ctx
from .valores import EASINGS, aplicar_params

__all__ = ["Cena", "EASINGS", "validar"]


# ── o que cada tipo aceita ────────────────────────────────────────────────
# Esta tabela existe por um motivo so: o motor IGNORA campo que nao conhece.
# `opacidad` em vez de `opacidade` passava limpo, a camada nao animava, e nao
# havia sintoma nenhum ate alguem assistir o video. Pra cena escrita a mao isso
# e chato; pra cena emitida por um modelo e o pior modo de falha que existe.
_COMUNS = {
    "tipo", "x", "y", "escala", "escalaX", "escalaY", "rotacao", "opacidade",
    "traco", "revelar", "inicio", "fim", "blur", "repetir", "efeito",
}
_POR_TIPO = {
    "texto": {"texto", "fonte", "peso", "tamanho", "cor", "italico",
              "entrelinha", "alinha", "espacamento", "largura_max",
              "contorno", "contorno_larg", "sombra"},
    "retangulo": {"larg", "alt", "raio", "cor", "contorno", "contorno_larg",
                  "hachura"},
    "elipse": {"raio", "rx", "ry", "de_grau", "varre_grau", "raio_int",
               "cor", "contorno", "contorno_larg", "hachura"},
    "linha": {"de", "para", "cor", "contorno", "contorno_larg", "hachura"},
    "path": {"d", "centrar", "cor", "contorno", "contorno_larg", "hachura"},
    "grupo": {"camadas"},
    "textura": {"cor", "grao", "manchas", "vinheta", "falhas", "facho",
                "semente"},
    # `src` e caminho de arquivo; `ajuste` e cobrir | caber | original;
    # `tingir` multiplica a imagem por uma cor, para trocar o "look" da mesma
    # foto sem ter outra copia dela.
    "imagem": {"src", "larg", "alt", "ajuste", "tingir"},
}
_REPETIR = {"cols", "linhas", "espX", "espY", "atraso", "ordem"}
_ORDENS = {"linha", "centro", "aleatorio"}
_HACHURA = {"modo", "angulo", "passo", "cor", "opacidade", "largura", "r0"}
_REVELAR = {"prog", "dir"}
# efeitos de contorno. `fase` anima nos dois que aceitam — e o que separa
# enfeite parado de movimento.
_EFEITOS = {
    "tracejado": {"traco", "vao", "fase"},
    "rabisco": {"seg", "amp", "semente"},
    "quina": {"raio"},
}
# `carimbo` (Path1DPathEffect) NAO entra: neste build do skia-python o efeito e
# criado mas o desenho ignora — sai a linha lisa, sem erro nenhum. Ver a nota
# em camadas.py:_efeito.
_DIRECOES = {"esq", "dir", "cima", "baixo"}
_TOPO = {"camadas", "duracao", "fundo", "params"}


def _perto(nome: str, validos) -> str:
    """Sugere o campo certo quando o errado e so uma letra trocada."""
    import difflib
    p = difflib.get_close_matches(nome, sorted(validos), n=1, cutoff=0.7)
    return f" — voce quis dizer {p[0]!r}?" if p else ""


def _checar_animavel(v: Any, caminho: str, erros: list[str]):
    """Forma de keyframe e nome de easing. Erro aqui so aparecia no desenho."""
    if isinstance(v, dict):
        if "mola" in v and not isinstance(v["mola"], (dict, bool)):
            erros.append(f"{caminho}: 'mola' precisa ser um objeto")
        return
    if not isinstance(v, list) or not v or not isinstance(v[0], (list, tuple)):
        return                      # constante ou nao e lista de keyframes
    for i, k in enumerate(v):
        onde = f"{caminho}[{i}]"
        if not isinstance(k, (list, tuple)) or len(k) < 2:
            erros.append(f"{onde}: keyframe precisa ser [tempo, valor] "
                         f"ou [tempo, valor, easing]")
            continue
        if not isinstance(k[0], (int, float)) or isinstance(k[0], bool):
            erros.append(f"{onde}: tempo do keyframe precisa ser numero, "
                         f"veio {k[0]!r}")
        if len(k) > 2 and k[2] is not None:
            # Bezier cubica: [x1, y1, x2, y2], os quatro pontos de controle do
            # CSS. Sem este ramo o validador estourava com "unhashable type:
            # list" ao encontrar uma — erro de Python cru na cara de quem
            # escreveu a cena, em vez da mensagem que o validador existe para dar.
            if isinstance(k[2], (list, tuple)):
                if len(k[2]) != 4 or not all(
                        isinstance(n, (int, float)) and not isinstance(n, bool)
                        for n in k[2]):
                    erros.append(f"{onde}: bezier precisa de 4 numeros "
                                 f"[x1,y1,x2,y2], veio {k[2]!r}")
            elif k[2] not in EASINGS:
                erros.append(f"{onde}: easing {k[2]!r} nao existe"
                             + _perto(str(k[2]), EASINGS))
            elif i == len(v) - 1:
                # o easing governa o trecho que COMECA nele; no ultimo nao
                # comeca trecho nenhum, entao ele e configuracao morta.
                #
                # AVISO e nao erro por uma razao medida: os helpers `surge` e
                # `desenha` do projeto escrevem assim, e isso aparece 300 vezes
                # so na prancha. Como o easing que eles pedem (`inOutCubic`) e
                # exatamente o padrao (`suave`), o desenho nunca saiu errado —
                # bloquear agora derrubaria toda cena que existe pra corrigir
                # algo que, ali, nao tem efeito. Onde o easing pedido NAO e o
                # padrao (lower_third pede `outBack`), a cena anima diferente do
                # que esta escrito — e por isso o aviso precisa existir.
                erros.append(f"aviso: {onde}: easing {k[2]!r} no ULTIMO keyframe "
                             f"nunca e usado — ele governa o trecho que COMECA "
                             f"nele. Mova pro keyframe anterior.")


def validar(spec: dict, avisos: bool = False) -> list[str]:
    """Devolve a lista de problemas. Vazia = cena valida.

    Existe separado de `Cena()` porque o gerador precisa poder criticar uma
    cena ANTES de tentar desenhar — mensagem de erro boa e o que torna saida
    de modelo utilizavel em vez de tentativa e erro as cegas.

    Duas severidades, e a diferenca importa:

      ERRO  — a cena nao desenha, ou desenha errado calada. Campo inexistente,
              easing que nao existe, keyframe malformado. `Cena()` recusa.
      AVISO — a cena desenha certo, mas tem configuracao morta ou suspeita.
              So aparece com `avisos=True`; nunca bloqueia.

    Sem essa separacao o criador de cena aprende a ignorar a saida inteira —
    e ai ela deixa de servir pra qualquer coisa.
    """
    erros: list[str] = []
    if not isinstance(spec, dict):
        return ["cena precisa ser um objeto"]
    if not isinstance(spec.get("camadas"), list):
        erros.append("falta a lista 'camadas'")
    for k in spec:
        if k not in _TOPO and not k.startswith("_"):
            erros.append(f"cena: chave {k!r} desconhecida no topo"
                         + _perto(k, _TOPO))

    def olhar(c: Any, caminho: str):
        if not isinstance(c, dict):
            erros.append(f"{caminho}: camada precisa ser um objeto")
            return
        tipo = c.get("tipo")
        if tipo not in _cam.TIPOS:
            erros.append(f"{caminho}: tipo {tipo!r} desconhecido "
                         f"(tem: {', '.join(sorted(_cam.TIPOS))})")
            return
        if tipo == "texto" and not str(c.get("texto", "")).strip():
            erros.append(f"{caminho}: camada de texto sem 'texto'")
        if tipo == "path" and not c.get("d"):
            erros.append(f"{caminho}: camada de path sem 'd'")

        aceitos = _COMUNS | _POR_TIPO[tipo]
        for k, v in c.items():
            # `_` na frente e escape pra anotacao/comentario na propria cena
            if k not in aceitos and not k.startswith("_"):
                erros.append(f"{caminho}: campo {k!r} nao existe em {tipo!r}"
                             + _perto(k, aceitos))
                continue
            _checar_animavel(v, f"{caminho}.{k}", erros)

        rep = c.get("repetir")
        if rep is not None:
            if not isinstance(rep, dict):
                erros.append(f"{caminho}.repetir: precisa ser um objeto")
            else:
                for k in rep:
                    if k not in _REPETIR:
                        erros.append(f"{caminho}.repetir: campo {k!r} nao existe"
                                     + _perto(k, _REPETIR))
                if "ordem" in rep and rep["ordem"] not in _ORDENS:
                    erros.append(f"{caminho}.repetir.ordem: {rep['ordem']!r} "
                                 f"invalida (tem: {', '.join(sorted(_ORDENS))})")

        ha = c.get("hachura")
        if ha is not None:
            if not isinstance(ha, dict):
                erros.append(f"{caminho}.hachura: precisa ser um objeto")
            else:
                for k in ha:
                    if k not in _HACHURA:
                        erros.append(f"{caminho}.hachura: campo {k!r} nao existe"
                                     + _perto(k, _HACHURA))

        rev = c.get("revelar")
        if isinstance(rev, dict):
            for k in rev:
                if k not in _REVELAR:
                    erros.append(f"{caminho}.revelar: campo {k!r} nao existe"
                                 + _perto(k, _REVELAR))
            if "dir" in rev and rev["dir"] not in _DIRECOES:
                erros.append(f"{caminho}.revelar.dir: {rev['dir']!r} invalida "
                             f"(tem: {', '.join(sorted(_DIRECOES))})")

        ef = c.get("efeito")
        if isinstance(ef, dict):
            t_ef = ef.get("tipo")
            if t_ef not in _EFEITOS:
                erros.append(f"{caminho}.efeito.tipo: {t_ef!r} nao existe "
                             f"(tem: {', '.join(sorted(_EFEITOS))})")
            else:
                validos = _EFEITOS[t_ef] | {"tipo"}
                for k in ef:
                    if k not in validos:
                        erros.append(
                            f"{caminho}.efeito[{t_ef}]: campo {k!r} nao existe"
                            + _perto(k, validos))
        elif ef is not None:
            erros.append(f"{caminho}.efeito: tem que ser um dicionario "
                         "com 'tipo'")

        if tipo == "grupo":
            for i, f in enumerate(c.get("camadas") or []):
                olhar(f, f"{caminho}.camadas[{i}]")

    for i, c in enumerate(spec.get("camadas") or []):
        olhar(c, f"camadas[{i}]")
    if not avisos:
        erros = [e for e in erros if not e.startswith("aviso:")]
    return erros


class Cena:
    """Uma cena construida: mede uma vez, desenha em qualquer instante."""

    def __init__(self, spec: dict, width: int, height: int, fps: float = 30.0,
                 registry: FontRegistry | None = None):
        erros = validar(spec)
        if erros:
            raise ValueError("cena invalida:\n  - " + "\n  - ".join(erros))
        self.spec = aplicar_params(
            {k: v for k, v in spec.items() if k != "params"},
            spec.get("params") or {})
        self.w, self.h, self.fps = width, height, fps
        self.registry = registry or FontRegistry()
        self.duracao = float(spec.get("duracao", 0) or 0)
        self.fundo = self.spec.get("fundo")
        # os TextBlocks nascem aqui: shaping e custo por CENA, desenho e custo
        # por FRAME. Construir dentro do loop multiplicaria o caro pelo barato.
        self._blocos: dict[int, Any] = {}
        ctx0 = Ctx(0.0, fps, width, height, self.registry)
        self._medir(self.spec.get("camadas") or [], ctx0)

    def _medir(self, cs: list, ctx: Ctx):
        for c in cs:
            if c["tipo"] == "texto":
                self._blocos[id(c)] = _cam.construir_texto(c, ctx)
            elif c["tipo"] == "grupo":
                self._medir(c.get("camadas") or [], ctx)

    def _ctx(self, t: float) -> Ctx:
        return Ctx(t, self.fps, self.w, self.h, self.registry)

    def desenhar(self, canvas: skia.Canvas, t: float):
        """`t` em SEGUNDOS desde o inicio da cena."""
        ctx = self._ctx(t)
        if self.fundo:
            canvas.drawPaint(_cam._tinta(self.fundo, 1.0))
        # origem no centro do quadro, UMA vez — dai pra baixo cada camada so
        # aplica o proprio deslocamento, e grupo aninha certo
        canvas.save()
        canvas.translate(self.w / 2.0, self.h / 2.0)
        for c in self.spec.get("camadas") or []:
            if _cam.viva(c, t):
                _cam.pintar(canvas, c, _cam.resolver(c, ctx), ctx, self._blocos)
        canvas.restore()

    def assinatura(self, t: float) -> tuple:
        """Frames com a mesma assinatura sao o mesmo pixel — pula o desenho."""
        ctx = self._ctx(t)
        return tuple(_cam.assinar(c, ctx) if _cam.viva(c, t) else ("morta",)
                     for c in self.spec.get("camadas") or [])

    def still(self, t: float) -> skia.Image:
        s = skia.Surface(self.w, self.h)
        with s as canvas:
            canvas.clear(skia.Color4f(0, 0, 0, 0))
            self.desenhar(canvas, t)
        return s.makeImageSnapshot()

    @classmethod
    def de_arquivo(cls, caminho: str | Path, width: int, height: int,
                   fps: float = 30.0, registry: FontRegistry | None = None) -> "Cena":
        spec = json.loads(Path(caminho).read_text(encoding="utf-8"))
        return cls(spec, width, height, fps, registry)
