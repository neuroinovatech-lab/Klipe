"""ffbin.py — onde estao o ffmpeg e o ffprobe NESTA maquina.

Cinco arquivos do caminho principal cravavam `C:\\ffmpeg\\bin\\ffmpeg.exe`.
Na maquina de quem escreveu funcionava; em qualquer outra, o render morria com
"arquivo nao encontrado" apontando pra um caminho que a pessoa nunca viu.

A ordem de busca vai do mais explicito ao mais generico, e cada degrau existe
por um motivo:

  1. KLIPE_FFMPEG        — a pessoa mandou usar ESTE. Ganha de tudo.
  2. klipe_settings.json — o que ela escolheu em Configuracoes, sem terminal.
  3. C:\\ffmpeg\\bin        — onde estava cravado; mantido pra nao quebrar
                            a maquina onde ja funciona.
  4. PATH                — instalacao normal (choco, winget, apt, brew).

O resultado e memorizado: isto e chamado dentro de lacos de render, e
`shutil.which` bate no disco toda vez.

O ffprobe NAO e derivado por replace de string no caminho inteiro — trocar
"ffmpeg" por "ffprobe" em C:\\ffmpeg\\bin\\ffmpeg.exe produzia
C:\\ffprobe\\bin\\ffprobe.exe, que nao existe. Esse bug ja custou o cache
per-title inteiro uma vez: a validacao falhava sempre e todo render refazia
todos os titulos. So o NOME do arquivo muda.
"""
from __future__ import annotations

import json
import os
import shutil
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Onde o instalador do Klipe poe o ffmpeg. LOCALAPPDATA, e nao C:\ffmpeg, de
# proposito: C:\ exige administrador (testado — OSError sem elevacao), entao
# instalar la ou dispara UAC ou falha calado. Na pasta do usuario nao precisa
# de permissao nenhuma, e cada pessoa tem a sua.
INSTALADO = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Klipe" / "ffmpeg" / "bin"
_PADRAO_WIN = Path(r"C:\ffmpeg\bin")


# As configuracoes sairam da pasta do projeto: instalar e copiar a pasta, e
# as chaves de quem copiou nao podem viajar junto. A pasta antiga continua
# sendo lida em segundo lugar, para quem ainda nao migrou.
CONFIG_USUARIO = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Klipe" / "klipe_settings.json"


def _das_configuracoes(chave: str) -> str | None:
    for arq in (CONFIG_USUARIO, RAIZ / "klipe_settings.json"):
        try:
            j = json.loads(arq.read_text(encoding="utf-8"))
            v = (j.get(chave) or "").strip()
            if v:
                return v
        except Exception:
            continue
    return None


@lru_cache(maxsize=4)
def _achar(nome: str) -> str:
    """`nome` e 'ffmpeg' ou 'ffprobe' (sem extensao)."""
    env = os.environ.get(f"KLIPE_{nome.upper()}")
    if env and Path(env).exists():
        return env

    cfg = _das_configuracoes(f"{nome}_path")
    if cfg and Path(cfg).exists():
        return cfg

    # se a pessoa configurou o ffmpeg, o ffprobe mora ao lado dele
    irmao = _das_configuracoes("ffmpeg_path")
    if irmao:
        cand = Path(irmao).with_name(f"{nome}{Path(irmao).suffix}")
        if cand.exists():
            return str(cand)

    # o que o proprio Klipe instalou vem antes do C:\ffmpeg: se a pessoa
    # clicou em "Instalar", e esse que ela espera que seja usado
    for pasta in (INSTALADO, _PADRAO_WIN):
        for ext in (".exe", ""):
            cand = pasta / f"{nome}{ext}"
            if cand.exists():
                return str(cand)

    achado = shutil.which(nome)
    if achado:
        return achado

    # Devolve o nome cru: o erro do subprocess vai dizer "ffmpeg nao
    # encontrado", que e diagnosticavel — melhor que um caminho inventado
    # que so existia no computador de outra pessoa.
    return nome


def ffmpeg() -> str:
    return _achar("ffmpeg")


def ffprobe() -> str:
    return _achar("ffprobe")


def diagnostico() -> dict:
    """Pra interface poder mostrar o que foi encontrado, e onde."""
    return {
        "ffmpeg": ffmpeg(),
        "ffprobe": ffprobe(),
        "ffmpeg_ok": Path(ffmpeg()).exists() or shutil.which(ffmpeg()) is not None,
        "ffprobe_ok": Path(ffprobe()).exists() or shutil.which(ffprobe()) is not None,
    }


if __name__ == "__main__":
    for k, v in diagnostico().items():
        print(f"  {k:<12} {v}")
