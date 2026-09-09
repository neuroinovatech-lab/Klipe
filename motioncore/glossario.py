# -*- coding: utf-8 -*-
"""glossario.py — os termos que o Whisper nao conhece.

O Whisper erra nome proprio, sigla e jargao: transcreve o que soa parecido e
que ele ja viu muito. "MotionCore" vira "motion core", "Klipe" vira "clipe",
"ROAS" vira "roas" ou "rows". Em video de nicho isso acontece toda hora, e
quem conserta e a pessoa, palavra por palavra.

DE ONDE VEIO A IDEIA, E ONDE ELA MELHORA
  O concorrente (Vendus Content Studio) tem uma lista de termos do dominio no
  `transcript-quality.mjs`. Mas ela so entra num RELATORIO de qualidade — a
  lista nao volta pro modelo. O erro continua na transcricao; o programa so
  avisa que talvez exista.

  O faster-whisper aceita `hotwords`, que enviesa a decodificacao em CADA
  janela de audio. Entao aqui a lista age ANTES do erro, e nao depois.

AS DUAS CAMADAS
  1. `hotwords` — vale pra TODO termo. O modelo ja decodifica sabendo que eles
     existem, e nao ha como isso piorar nada.
  2. correcao por semelhanca — so pros termos marcados com `*` no fim.

POR QUE A CORRECAO E OPT-IN, E NAO AUTOMATICA
  Rodei a correcao automatica numa transcricao de verdade (287 palavras) com
  "adolescencia" no glossario. Ela trocou "adolescente" por "adolescencia"
  SEIS vezes. Sao palavras diferentes que dividem a raiz — semelhanca 0.87.

  E o oposto do que eu tinha suposto: eu achava que palavra longa era mais
  segura de corrigir. E o contrario. Palavra longa divide RAIZ com as vizinhas,
  entao a semelhanca alta quer dizer "familia", nao "erro de audicao".

  Nenhum limiar resolve isso, porque a informacao que falta nao esta na escrita:
  esta em saber se o termo e uma palavra comum ou um nome proprio. Quem sabe e
  quem escreveu o glossario. Entao ele marca:

      adolescencia        so enviesa o modelo (seguro sempre)
      MotionCore*         tambem corrige o que chegar perto

  Escrever `*` e mais trabalho pra pessoa. Mas trocar a palavra dela por outra
  sem avisar e pior — ainda mais numa legenda que vai ao ar.

A REGRA QUE NAO SE QUEBRA
  Correcao mexe no TEXTO e nunca no tempo. O corte pelo texto depende do tempo
  por palavra: trocar "cliper" por "Klipe" tem que manter o mesmo inicio e o
  mesmo fim, senao a palavra corrigida corta o pedaco errado do video.

O ARQUIVO NASCE VAZIO — E DE PROPOSITO
  Glossario e pessoal. O do concorrente vem com os termos DELES ("200K",
  "Vendus", "ROAS"), o que enviesa a transcricao de quem instalar pro assunto
  de outra pessoa. O nosso vem com instrucao e nenhum termo.

    %LOCALAPPDATA%\\Klipe\\glossario.txt          vale pra tudo
    public/projects/<projeto>/glossario.txt      so pra esse projeto
"""
from __future__ import annotations

import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# ── o limiar, e o que ele NAO resolve ────────────────────────────────────
# Testei 8 erros de audicao reais contra 17 palavras legitimas parecidas:
#
#     fixo 0.84 (meu primeiro chute)   acerta 2/8   erra  0/17
#     fixo 0.78                        acerta 5/8   erra  0/17
#     fixo 0.75                        acerta 7/8   erra  1/17
#     curto >=0.92, longo >=0.78       acerta 3/8   erra  0/17
#
# 0.78 e o ponto: pega a maioria sem errar nenhuma.
#
# E o mais importante: NAO EXISTE limiar perfeito, e isso e propriedade do
# problema, nao falta de afinacao. "rosa" contra "ROAS" da 0.750; "skya" contra
# "Skia" tambem da 0.750. As duas distribuicoes se sobrepoem, entao qualquer
# corte deixa passar erro ou inventa correcao.
#
# Por isso a correcao e a SEGUNDA camada, nao a principal. Quem evita o erro e
# o `hotwords`, que age antes da transcricao e nao tem como errar pra pior. A
# correcao so limpa o que escapou, e prefere deixar passar a inventar.
LIMIAR = 0.78
MIN_LETRAS = 4          # abaixo disso quase tudo parece com quase tudo
MAX_HOTWORDS = 60       # a lista entra no contexto do modelo; longa demais dilui

CABECALHO = """# Glossario do Klipe — os termos que o Whisper erra.
#
# Um por linha. Nome proprio, sigla, jargao, marca. Escreva do jeito CERTO,
# com maiuscula e acento — e assim que ele vai aparecer na legenda.
#
# Duas coisas acontecem com esta lista:
#   1. o Whisper transcreve ja sabendo que estes termos existem;
#   2. termos marcados com * no fim tambem CORRIGEM o que chegar perto.
#
# Use o * so em nome proprio, marca, sigla e jargao:
#
#     MotionCore*      corrige "moshoncore", "motion core"
#     adolescencia     so enviesa — sem *, porque "adolescente" existe e nao
#                      pode virar "adolescencia" sozinha
#
# O tempo de cada palavra NUNCA muda — so o texto. Entao o corte pelo texto
# continua cortando o pedaco certo.
#
# Linhas com # sao ignoradas. Termo de ate duas palavras funciona.
"""


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _chave(s: str) -> str:
    """A forma comparavel: sem acento, sem pontuacao, minuscula."""
    return re.sub(r"[^\w]+", "", _sem_acento(s)).lower()


def caminho_global() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Klipe"
    return base / "glossario.txt"


def garantir_arquivo() -> Path:
    """Cria o arquivo vazio com a instrucao dentro, se ainda nao existe."""
    p = caminho_global()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(CABECALHO, encoding="utf-8")
    return p


def _ler(p: Path) -> list[str]:
    if not p.exists():
        return []
    out = []
    for linha in p.read_text(encoding="utf-8").splitlines():
        t = linha.split("#")[0].strip()
        if t and len(t.rstrip("*").strip()) >= 2:
            out.append(t)
    return out


def _corrigivel(t: str) -> bool:
    """O `*` no fim: a pessoa autorizou trocar palavra parecida por esta."""
    return t.rstrip().endswith("*")


def limpo(t: str) -> str:
    return t.rstrip().rstrip("*").rstrip()


def termos(projeto: str | None = None) -> list[str]:
    """Os do projeto vem DEPOIS dos globais: em empate de semelhanca, o termo
    mais especifico ganha, que e o que a pessoa quis dizer ao criar o local."""
    fora = _ler(garantir_arquivo())
    dentro = []
    if projeto:
        dentro = _ler(RAIZ / "public" / "projects" / projeto / "glossario.txt")
    vistos, out = set(), []
    for t in fora + dentro:
        k = _chave(limpo(t))
        if k and k not in vistos:
            vistos.add(k)
            out.append(t)
    return out


def hotwords(lista: list[str]) -> str | None:
    """A string que o faster-whisper usa pra enviesar CADA janela.

    Cortada em MAX_HOTWORDS porque ela ocupa contexto do modelo: lista longa
    demais dilui o peso de cada termo e come espaco que a fala precisa.
    """
    if not lista:
        return None
    return " ".join(limpo(t) for t in lista[:MAX_HOTWORDS])


def _perto(palavra: str, alvos: dict) -> str | None:
    k = _chave(palavra)
    if len(k) < MIN_LETRAS or k in alvos:
        return None
    melhor, nota = None, 0.0
    for chave_alvo, termo in alvos.items():
        # diferenca grande de tamanho nao e erro de audicao, e outra palavra
        if abs(len(chave_alvo) - len(k)) > 3:
            continue
        r = SequenceMatcher(None, k, chave_alvo).ratio()
        if r > nota:
            melhor, nota = termo, r
    return melhor if nota >= LIMIAR else None


def corrigir(palavras: list[dict], lista: list[str]) -> tuple[list[dict], list]:
    """Troca o texto das palavras que passaram perto de um termo.

    `palavras` sao os dicionarios com tempo do Whisper. O que volta tem o MESMO
    `start` e `end` — so o `word` muda. Devolve tambem o registro do que foi
    trocado, pra poder conferir em vez de confiar.
    """
    if not lista or not palavras:
        return palavras, []
    # O faster-whisper cru chama de `word`; o que o Klipe GRAVA chama de
    # `text`. Descobrir isso na hora evita um adaptador entre os dois e evita
    # o modo de falha silencioso: ler a chave errada nao da erro, so nunca
    # corrige nada — e a funcao pareceria funcionar.
    campo = "word" if "word" in palavras[0] else "text"
    marcados = [limpo(t) for t in lista if _corrigivel(t)]
    if not marcados:
        return palavras, []
    simples = {_chave(t): t for t in marcados if " " not in t}
    duplos = {_chave(t): t for t in marcados if t.count(" ") == 1}
    trocas = []

    # ── primeiro os de duas palavras, senao cada metade e corrigida sozinha
    i = 0
    while duplos and i < len(palavras) - 1:
        a = (palavras[i].get(campo) or "").strip()
        b = (palavras[i + 1].get(campo) or "").strip()
        alvo = _perto(a + b, duplos)
        if alvo:
            antes = f"{a} {b}"
            esq, dir_ = alvo.split(" ", 1)
            palavras[i][campo] = (" " if (palavras[i].get(campo) or "").startswith(" ")
                                   else "") + esq
            palavras[i + 1][campo] = " " + dir_
            trocas.append((antes, alvo, round(float(palavras[i].get("start", 0)), 2)))
            i += 2
            continue
        i += 1

    # ── depois os de uma palavra
    for p in palavras:
        bruta = p.get(campo) or ""
        nu = bruta.strip()
        alvo = _perto(nu, simples)
        if not alvo:
            continue
        # pontuacao colada volta pro lugar: "clipe," -> "Klipe,"
        sufixo = re.sub(r"^[\wÀ-ſ]+", "", nu)
        prefixo = " " if bruta.startswith(" ") else ""
        p[campo] = prefixo + alvo + sufixo
        trocas.append((nu, alvo + sufixo, round(float(p.get("start", 0)), 2)))
    return palavras, trocas
