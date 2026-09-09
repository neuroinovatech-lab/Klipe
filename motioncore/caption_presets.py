"""
caption_presets.py — o motor de legenda dirigido por PRESET.

É o mesmo movimento que o estilo `livre` fez nos títulos. Lá, em vez de mais um
layout fixo no código, o estilo passou a ler uma lista de partes com fonte,
tamanho, cor e animação próprias. Aqui a legenda faz igual: em vez de um `if
estilo == "boxed"` espalhado pelo desenho, existe um PRESET declarativo e o
desenho só executa o que ele manda.

É assim que os plugins de legenda do Premiere e do CapCut funcionam — o que eles
vendem é um catálogo de presets, não um motor por estilo.

O QUE UM PRESET DESCREVE
------------------------
Uma legenda tem palavras em três PAPÉIS, e o visual viral vem justamente de
tratar cada um diferente:

  power   a palavra que carrega a frase (número, ou a mais longa que não seja
          palavra-vazia). É a que ganha fonte maior, outra cor, destaque.
  normal  o resto do conteúdo.
  small   palavras-vazias (artigo, preposição, conectivo) — costumam entrar
          menores e apagadas, o que faz a frase "respirar".

E a palavra ATIVA (a que está sendo falada agora) recebe um tratamento por
cima do papel dela: cor, caixa, contorno, brilho, estouro de escala.

Cada papel aceita: fonte, escala (relativa ao tamanho base), cor, peso,
itálico, contorno, sombra, caixa de fundo, e deslocamento x/y.

`outline` e `boxed` viram presets também — não são mais caminho especial no
código. Isso garante que o motor novo continue desenhando os dois exatamente
como antes.
"""
from __future__ import annotations

import re
import unicodedata

# Palavras-vazias do pt-BR. Não entram na disputa de "palavra forte" e, nos
# presets que usam o papel `small`, entram menores.
VAZIAS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos",
    "das", "em", "no", "na", "nos", "nas", "por", "pra", "para", "pelo", "pela",
    "com", "sem", "e", "ou", "mas", "que", "se", "ao", "aos", "à", "às", "é",
    "eu", "tu", "ele", "ela", "nos", "vos", "eles", "elas", "me", "te", "lhe",
    "meu", "minha", "seu", "sua", "esse", "essa", "isso", "este", "esta",
    "isto", "aquele", "aquela", "aquilo", "já", "só", "até", "mais", "muito",
    "tão", "como", "quando", "onde", "aqui", "ali", "lá", "não", "sim", "the",
    "of", "to", "in", "on", "and", "or", "a", "an",
}


def _limpa(w: str) -> str:
    s = unicodedata.normalize("NFD", w or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]", "", s).lower()


def classificar(palavras: list[str]) -> list[str]:
    """
    Papel de cada palavra do grupo: "power", "normal" ou "small".

    Mesma regra do original (VideoEditor.tsx ~5526): número vale 100, senão
    vale o comprimento; palavra-vazia não disputa. Se TODAS forem vazias, a
    mais longa vira a forte — senão o grupo ficaria sem destaque nenhum.
    """
    if not palavras:
        return []
    limpas = [_limpa(w) for w in palavras]
    vazia = [c in VAZIAS or not c for c in limpas]
    numero = [bool(c) and c.isdigit() for c in limpas]

    melhor, pontos = -1, 0
    for i, w in enumerate(limpas):
        if vazia[i]:
            continue
        p = 100 if numero[i] else len(w)
        if p > pontos:
            pontos, melhor = p, i
    if melhor < 0:
        melhor = max(range(len(limpas)), key=lambda i: len(limpas[i]))
        vazia[melhor] = False

    return ["power" if i == melhor else "small" if vazia[i] else "normal"
            for i in range(len(palavras))]


# Um papel sem nada declarado herda isto.
PADRAO_PAPEL = {
    "fonte": None,        # None = usa a fonte global da legenda
    "escala": 1.0,        # multiplica o tamanho base
    "cor": None,          # None = usa captionColor
    "peso": 900,
    "italico": False,
    "contorno": 0.0,      # px de stroke preto
    "sombra": None,       # (dx, dy, blur, cor) ou None
    "caixa": None,        # cor de fundo da pílula, ou None
    "offX": 0.0,
    "offY": 0.0,
}

# Tratamento da palavra ATIVA, por cima do papel.
PADRAO_ATIVA = {
    "cor": None,          # None = usa captionHighlightColor
    "caixa": None,
    "escala": 1.12,       # estouro
    "brilho": 0.0,        # raio do glow na cor de destaque
    "sombra": None,
    # Onde o estouro ASSENTA depois do pulso de entrada. `None` = mantém a
    # regra por nome que está em `captions.estado` (1.12 no outline/words,
    # 1.08 no resto) — é o que os presets existentes usam, e mexer nisso
    # mudaria o desenho deles sem ninguém ter pedido. Um preset que declara um
    # número aqui passa a mandar no próprio estouro; 1.0 significa "some o
    # karaokê, sobra só o pulso de entrada".
    "assenta": None,
    # De onde o estouro cresce. "centro" (o padrao, e o que sempre foi feito)
    # empurra a palavra pros DOIS lados, entao com estouro de 1,12 numa palavra
    # larga ela avanca ~6% da largura sobre o vao — mais que o vao inteiro, e as
    # duas encostam. Nos presets com contorno isso nao aparece; sem contorno,
    # aparece. "esq" cresce a partir do canto de baixo a esquerda: a palavra so
    # avanca pra direita, pro espaco que ainda nao foi lido.
    "origem": "centro",   # centro | esq
}

# `outline` e `boxed` expressos como preset. São a prova de que o motor novo
# cobre o antigo: se o desenho por preset não reproduzir estes dois, ele está
# errado.
PRESETS = {
    "outline": {
        "papeis": {
            "power":  {"contorno": "auto", "sombra": (0, 4, 14, "rgba(0,0,0,0.65)")},
            "normal": {"contorno": "auto", "sombra": (0, 4, 14, "rgba(0,0,0,0.65)")},
            "small":  {"contorno": "auto", "sombra": (0, 4, 14, "rgba(0,0,0,0.65)")},
        },
        "ativa": {"escala": 1.12, "brilho": 28},
    },
    "boxed": {
        "papeis": {
            "power":  {"caixa": "rgba(0,0,0,0.72)"},
            "normal": {"caixa": "rgba(0,0,0,0.72)"},
            "small":  {"caixa": "rgba(0,0,0,0.72)"},
        },
        # no boxed quem brilha é a pílula; o texto da ativa fica escuro
        "ativa": {"cor": "#0A0A0A", "caixa": "destaque", "escala": 1.08,
                  "sombra": (0, 6, 26, "destaque70")},
    },

    # ── os primeiros presets NOVOS — o que só o motor de papel sabe fazer ──
    # A palavra forte maior e colorida, a vazia menor e apagada: é o visual
    # dos plugins de legenda do Premiere/CapCut, que nenhum estilo antigo
    # reproduzia porque tratavam toda palavra igual.
    "destaque": {
        "papeis": {
            "power":  {"escala": 1.22, "cor": "destaque",
                       "contorno": "auto", "sombra": (0, 4, 14, "rgba(0,0,0,0.65)")},
            "normal": {"contorno": "auto", "sombra": (0, 4, 14, "rgba(0,0,0,0.65)")},
            "small":  {"escala": 0.78, "cor": "#B8B8B8",
                       "contorno": "auto", "sombra": (0, 4, 14, "rgba(0,0,0,0.65)")},
        },
        "ativa": {"escala": 1.10, "brilho": 24},
    },
    # A forte numa pílula na cor de destaque o tempo todo; o resto limpo.
    "forte-caixa": {
        "papeis": {
            "power":  {"caixa": "destaque", "cor": "#0A0A0A", "escala": 1.08},
            "normal": {"contorno": "auto", "sombra": (0, 4, 14, "rgba(0,0,0,0.65)")},
            "small":  {"escala": 0.82, "contorno": "auto",
                       "sombra": (0, 4, 14, "rgba(0,0,0,0.65)")},
        },
        "ativa": {"escala": 1.10, "brilho": 20},
    },
    # `words` — o estilo PADRAO do Klipe, o visual CapCut. Grupo de ate 3
    # palavras dentro de UMA caixa escura, karaoke trocando so a cor da ativa.
    #
    # Duas coisas o separam do resto e por isso ele nao podia ser apelido de
    # ninguem: NAO tem papel (toda palavra e igual, ao contrario de `destaque` e
    # `serif-mista`), e a caixa e do GRUPO, nao da palavra (ao contrario de
    # `boxed`, onde cada uma tem sua pilula). Ate hoje o `resolver` mandava
    # `words` cair em `outline` calado — que nao tem caixa, nem janela de grupo.
    #
    # Original: src/VideoEditor.tsx, o ramo final do CaptionOverlay (~5750).
    "words": {
        "papeis": {p: {"peso": 800, "sombra": (0, 2, 8, "rgba(0,0,0,0.6)")}
                   for p in ("power", "normal", "small")},
        # `textShadow: 0 0 20px <destaque>80, 0 2px 8px rgba(0,0,0,.6)`
        "ativa": {"cor": "destaque", "escala": 1.12, "brilho": 20.0,
                  "sombra": (0, 2, 8, "rgba(0,0,0,0.6)")},
        # `padding: "14px 28px"; borderRadius: 16; background: rgba(0,0,0,0.7)`
        "container": {"fundo": "rgba(0,0,0,0.7)", "pad_x": 28.0,
                      "pad_y": 14.0, "raio": 16.0},
    },

    # ── editorial ──────────────────────────────────────────────────────
    # Porte do "Editorial Emphasis" do HyperFrames (o .zip está em
    # referencias/hyperframes-sessoes/editorial-emphasis/).
    #
    # É primo do `serif-mista` — os dois põem serifada itálica na palavra
    # forte e sans no resto — e a diferença entre eles é o EXAGERO, que é
    # justamente o efeito:
    #
    #   serif-mista   forte 1,26x do corpo, na cor de destaque
    #   editorial     forte 2,09x (180px contra 86px no original), e TODAS as
    #                 palavras no mesmo creme — sem cor de destaque nenhuma
    #
    # A ausência de cor é deliberada e é metade do visual: o contraste vem do
    # tamanho e da forma da letra, não de pintar a palavra. Por isso `ativa`
    # repete o creme em vez de deixar `None` (que puxaria a cor de destaque do
    # projeto e ligaria um karaokê que o original não tem).
    #
    # Na proporção de 2,09x a palavra forte quase sempre estoura a linha
    # sozinha — que é como o original a põe, numa linha só pra ela.
    #
    # A fonte do texto miúdo é Arial e não Inter porque Inter não está
    # instalada aqui; é o mesmo fallback que o Chrome faria, e das disponíveis
    # é a mais próxima (as duas são neo-grotescas). A serifada é a do
    # original: Playfair Display itálica, no peso 700 em vez de 800, que é o
    # mais pesado que existe no acervo.
    "editorial": {
        # o único que NÃO vai em caixa alta: ver a nota em `resolver`
        "caixa_alta": False,
        "papeis": {
            "power":  {"fonte": "PlayfairDisplay", "italico": True, "peso": 700,
                       "escala": 2.09, "cor": "#F5F0D0", "contorno": 0,
                       "sombra": (0, 4, 24, "rgba(0,0,0,0.6)")},
            "normal": {"fonte": "Arial", "peso": 400, "cor": "#F5F0D0",
                       "contorno": 0, "sombra": (0, 2, 12, "rgba(0,0,0,0.6)")},
            "small":  {"fonte": "Arial", "peso": 400, "cor": "#F5F0D0",
                       "contorno": 0, "sombra": (0, 2, 12, "rgba(0,0,0,0.6)")},
        },
        # `assenta: 1.0` — a palavra ativa volta ao tamanho normal em vez de
        # ficar 8% maior enquanto é falada. No original não há karaokê nenhum:
        # o pulso é só de entrada (1.12→1 em 0,1s) e depois toda palavra fica
        # igual, no mesmo creme. Com o assentamento padrão (1.08) a palavra
        # ativa ficava permanentemente maior e encostava na anterior — aqui não
        # há contorno segurando a separação, então isso aparecia.
        #
        # `origem: esq` é o `transform-origin: 0% 100%` do original — no pulso
        # a palavra cresce só pra direita, pro espaço ainda não lido, em vez de
        # avançar também sobre a palavra anterior.
        "ativa": {"cor": "#F5F0D0", "brilho": 0.0, "assenta": 1.0, "origem": "esq"},
    },

    # Serifada na palavra forte, sans no resto — o "mixed fonts" dos plugins.
    "serif-mista": {
        "papeis": {
            "power":  {"fonte": "PlayfairDisplay", "italico": True, "escala": 1.26,
                       "cor": "destaque", "contorno": 0,
                       "sombra": (0, 4, 16, "rgba(0,0,0,0.75)")},
            "normal": {"contorno": "auto", "sombra": (0, 4, 14, "rgba(0,0,0,0.65)")},
            "small":  {"escala": 0.8, "cor": "#CFCFCF", "contorno": "auto",
                       "sombra": (0, 4, 14, "rgba(0,0,0,0.65)")},
        },
        "ativa": {"escala": 1.08, "brilho": 22},
    },
}


def resolver(nome: str, custom: dict | None = None) -> dict:
    """
    Devolve o preset completo, com todo papel preenchido.

    `custom` vem do projeto (`captionPreset` no config) e sobrescreve por
    campo, não por bloco — assim dá pra mudar só a cor da palavra forte sem
    redeclarar o preset inteiro.
    """
    base = PRESETS.get(nome) or PRESETS["outline"]
    # `text-transform: uppercase` era lei no motor, não escolha do preset. Vira
    # escolha aqui, com o padrão TRUE — assim os seis presets que existiam
    # continuam idênticos e só quem pedir sai em caixa baixa. Importa porque
    # serifada itálica em caixa alta perde exatamente o que ela tem de bom: o
    # desenho da minúscula.
    spec = {"papeis": {}, "ativa": dict(PADRAO_ATIVA),
            "caixa_alta": bool(base.get("caixa_alta", True))}
    if custom and "caixa_alta" in custom:
        spec["caixa_alta"] = bool(custom["caixa_alta"])
    for papel in ("power", "normal", "small"):
        d = dict(PADRAO_PAPEL)
        d.update(base.get("papeis", {}).get(papel, {}))
        if custom:
            d.update((custom.get("papeis", {}) or {}).get(papel, {}))
        spec["papeis"][papel] = d
    spec["ativa"].update(base.get("ativa", {}))
    if custom:
        spec["ativa"].update(custom.get("ativa", {}) or {})
    # caixa do GRUPO. Fica fora de "papeis" e de "ativa" de proposito: ela nao
    # pertence a palavra nenhuma. Sem carregar aqui, o preset chegaria ao
    # desenho sem ela e o `words` sairia sem fundo, calado.
    cont = (custom or {}).get("container") or base.get("container")
    if cont:
        spec["container"] = dict(cont)
    return spec


def nomes() -> list[str]:
    return sorted(PRESETS)
