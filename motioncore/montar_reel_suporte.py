#!/usr/bin/env python3
"""montar_reel_suporte.py — camadas do reel sobre suporte na adolescencia.

O MUNDO desta peca (construido do assunto, nao herdado de nada):

  Onde vive? Uma FICHA DE ATENDIMENTO. O video e um profissional respondendo
  a pergunta de uma mae, e a estrutura da fala e literalmente uma lista: ele
  faz quatro perguntas antes de responder, depois abre tres frentes.

  Qual o material? Cartao claro, tinta escura, um acento ambar. Calmo. O
  assunto e o filho de alguem — nada pisca, nada estoura, nada quica.

  Qual o gesto? Cada item ATERRISSA e recebe uma marca, como quem anota o que
  ouve. O mesmo gesto nas duas cenas — e ele que da unidade.

Nao ha papel envelhecido nem serifa de gravura aqui: aquilo e o estilo de
outra peca, e este pedido nao chamou por ele.

Saida: cor|alpha lado a lado (2160x1920), que e o que o Klipe consome como
b-roll com `alpha: true`.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import skia

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motioncore.cena import Cena, validar  # noqa: E402

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
W, H, FPS = 1080, 1920, 30
RAIZ = Path(__file__).resolve().parent.parent
PROJ = RAIZ / "public" / "projects" / "reel-suporte"

# Paleta — ficha de atendimento, nao prancha cientifica.
TINTA = "#16242E"      # azul-ardosia escuro
CARTAO = "#F4EFE7"     # branco quente
ACENTO = "#D98324"     # ambar
APAGADO = "#6B7B85"    # cinza-azulado dos subtitulos

FONTE = "Montserrat"


def surge(t0, dur=0.45, de=0.0, para=1.0, easing="outCubic"):
    """Entrada por opacidade. O easing vai no keyframe que COMECA o trecho —
    no ultimo ele e ignorado em silencio."""
    return [[t0, de, easing], [t0 + dur, para]]


# Por que TUDO e centrado nesta ficha: no DSL o `x` de um texto e o CENTRO do
# bloco, e `alinha` so alinha as linhas DENTRO dele (camadas.py desenha em
# `0.0, -altura/2`). Nao ha como ancorar a borda esquerda sem saber a largura
# medida do texto — entao alinhar a esquerda faria cada item comecar num lugar
# diferente conforme o tamanho da frase. Centrado e o unico alinhamento que o
# DSL sustenta sem medir.

BASE = -690          # a base do cartao, igual nas duas fichas — e o que faz
                     # as duas lerem como a mesma peca e nao dois desenhos


def bloco(cabecalho, itens, duracao):
    """Uma ficha: cabecalho + itens que aterrissam quando ele os diz.

    `itens` = [(t, titulo, subtitulo)] com t em tempo LOCAL da cena.
    """
    camadas = []
    passo = 112                                  # distancia entre itens
    alt_cartao = 178 + passo * len(itens)
    y_topo_card = BASE + alt_cartao              # a BORDA DE CIMA, fixa
    y_topo_interno = y_topo_card - 78            # onde comeca o cabecalho

    # 1. o cartao. Ele CRESCE conforme a lista se preenche, em vez de nascer
    #    no tamanho final: cartao cheio de vazio nos primeiros segundos le
    #    como layout quebrado, e o crescimento e o proprio gesto de anotar.
    #    A borda de cima fica parada e a de baixo desce — por isso `alt` e `y`
    #    animam juntos: o centro de um retangulo e (topo - alt/2).
    alt_kf, y_kf = [], []
    altura_ate = lambda k: 118 + passo * k
    for k in range(len(itens) + 1):
        # a altura k vale a partir do instante em que o item k aterrissa
        t = 0.0 if k == 0 else itens[k - 1][0]
        a = altura_ate(k)
        alt_kf.append([t, a, "outCubic"])
        y_kf.append([t, y_topo_card - a / 2, "outCubic"])
        if k < len(itens):
            # segura o tamanho ate o proximo item — sem isso ele cresceria em
            # rampa continua e nenhum item teria um momento de aterrissagem
            t_seg = itens[k][0] - 0.001
            alt_kf.append([t_seg, a, "outCubic"])
            y_kf.append([t_seg, y_topo_card - a / 2, "outCubic"])

    camadas.append({
        "tipo": "retangulo", "larg": 940, "raio": 26, "cor": CARTAO,
        "alt": alt_kf, "y": y_kf,
        # OPACO, nao 0,96. Com 4% de transparencia a legenda queimada do
        # original atravessava o cartao — e como ela diz as mesmas palavras
        # que ele esta falando, o resultado era o texto aparecendo duplicado
        # e fantasma. Opaco tambem cobre aquela faixa e limpa o quadro.
        "opacidade": surge(0.0, 0.5),
    })

    # 2. cabecalho
    camadas.append({
        "tipo": "texto", "texto": cabecalho, "fonte": FONTE, "peso": 700,
        "tamanho": 30, "cor": ACENTO, "espacamento": 4.0,
        "y": y_topo_interno,
        "opacidade": surge(0.18, 0.5),
    })

    # 3. a regua de progresso. Cresce a cena INTEIRA — e o que impede a ficha
    #    de virar foto nos segundos entre um item e outro. `escalaX` abre do
    #    centro pros dois lados, que e o gesto de uma medida sendo tomada.
    camadas.append({
        "tipo": "retangulo", "larg": 760, "alt": 3, "raio": 2,
        "cor": ACENTO, "y": y_topo_interno - 34,
        "opacidade": surge(0.3, 0.4, para=0.75),
        # `linear`, nao `suave`: progresso que desacelera no fim para de mudar
        # o suficiente pra render quadro novo, e a ficha congela no ultimo
        # segundo. Aqui linear e o honesto — o tempo passa em ritmo constante.
        "escalaX": [[0.3, 0.02, "linear"], [duracao, 1.0]],
    })

    # 4. os itens
    for i, (t, titulo, sub) in enumerate(itens):
        y = y_topo_interno - 96 - i * passo

        camadas.append({
            "tipo": "texto", "texto": titulo, "fonte": FONTE, "peso": 700,
            "tamanho": 36, "cor": TINTA, "largura_max": 850, "y": y,
            "opacidade": surge(t, 0.4),
        })
        if sub:
            camadas.append({
                "tipo": "texto", "texto": sub, "fonte": FONTE, "peso": 500,
                "tamanho": 23, "cor": APAGADO, "largura_max": 830,
                # sobe 14 px ao entrar: o item ATERRISSA, nao pisca
                "y": [[t + 0.16, y - 62, "outCubic"], [t + 0.7, y - 48]],
                "opacidade": surge(t + 0.16, 0.45, para=0.95),
            })

    return {"duracao": duracao, "camadas": camadas}


def selo(frase, duracao, destaque=None):
    """Uma frase que ele disse, posta como anotacao curta.

    Mesmo cartao, mesma ambar, mesma base — e o que faz os cinco blocos
    lerem como UMA peca. Estilo de titulo emprestado de outro projeto
    entraria brigando com as fichas.
    """
    linhas = frase.count("\n") + 1
    alt_cartao = 104 + linhas * 64
    y_topo_card = BASE + alt_cartao

    camadas = [
        {"tipo": "retangulo", "larg": 940, "alt": alt_cartao, "raio": 26,
         "cor": CARTAO, "y": y_topo_card - alt_cartao / 2,
         "opacidade": surge(0.0, 0.45),
         "escalaY": [[0.0, 0.9, "outCubic"], [0.5, 1.0]]},
        # a regua entra pela esquerda e some pela direita: o selo tem comeco e
        # fim, ao contrario da ficha, que acumula
        {"tipo": "retangulo", "larg": 760, "alt": 3, "raio": 2, "cor": ACENTO,
         "y": y_topo_card - 46,
         "opacidade": surge(0.25, 0.35, para=0.8),
         "escalaX": [[0.25, 0.02, "linear"], [duracao, 1.0]]},
        {"tipo": "texto", "texto": frase, "fonte": FONTE, "peso": 700,
         "tamanho": 44, "cor": TINTA, "largura_max": 840, "entrelinha": 1.22,
         "y": [[0.28, y_topo_card - 108 - (linhas - 1) * 38 - 12, "outCubic"],
               [0.85, y_topo_card - 108 - (linhas - 1) * 38]],
         "opacidade": surge(0.28, 0.45)},
    ]
    if destaque:
        camadas.append(
            {"tipo": "texto", "texto": destaque, "fonte": FONTE, "peso": 600,
             "tamanho": 23, "cor": APAGADO, "largura_max": 830,
             "y": y_topo_card - alt_cartao + 46,
             "opacidade": surge(0.55, 0.45, para=0.95)})
    return {"duracao": duracao, "camadas": camadas}


# ── as duas fichas ──────────────────────────────────────────────────────
# Os tempos saem da transcricao: cada item aterrissa no segundo em que ele
# DIZ aquilo. Texto na tela que nao esta ancorado na fala vira legenda
# decorativa e a peca perde o chao.

CENAS = {
    # 18,30 -> 46,00 | "Antes de qualquer resposta, eu preciso te fazer
    # algumas perguntas."
    "ficha_perguntas": bloco(
        "ANTES DE RESPONDER",
        [
            (3.86, "Qual o nível de suporte?", "autismo é um espectro"),
            (9.36, "Qual a idade dele?",       "2 anos não é 17 anos"),
            (16.74, "Quais ambientes frequenta?", "escola, igreja, esporte, amigos"),
            (22.88, "Tem rotina fixa?",        "se ainda não parou pra pensar, tudo bem"),
        ],
        duracao=27.7,
    ),

    # 66,90 -> 88,50 | "algumas frentes se destacam nessa fase da vida"
    "ficha_frentes": bloco(
        "TRÊS FRENTES",
        [
            (0.44, "Regulação emocional", "a cobrança social aumenta"),
            (5.32, "Comunicação social",  "ironia, piadas, dinâmica de grupo"),
            (13.18, "Autonomia",          "profissão, relacionamentos, futuro"),
        ],
        duracao=21.6,
    ),

    # 13,46 -> 17,84 | "porque nao e igual uma receita de bolo, porque cada
    # adolescente autista e unico"
    "selo_unico": selo("Não existe\nreceita de bolo", 4.6,
                       destaque="cada adolescente autista é único"),

    # 58,36 -> 62,60 | "E e ai que entra o suporte"
    "selo_suporte": selo("É aí que entra\no suporte", 4.4,
                         destaque="cada ambiente pede uma habilidade"),

    # 93,42 -> 99,20 | "para que esse adolescente autista seja funcional e
    # tenha uma qualidade de vida em todas as areas"
    "selo_fim": selo("No ritmo que\ncada um consegue", 5.9,
                     destaque="funcionalidade e qualidade de vida"),
}


def renderizar(nome, spec):
    erros = validar(spec)
    if erros:
        raise SystemExit(f"{nome}: " + "; ".join(erros))

    cena = Cena(spec, W, H, FPS)
    n = int(round(spec["duracao"] * FPS))
    PROJ.mkdir(parents=True, exist_ok=True)
    saida = PROJ / f"{nome}.mp4"

    p = subprocess.Popen(
        [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         # `format=rgba` antes do split e obrigatorio: sem ele o alphaextract
         # falha com "Requested planes not available"
         "-filter_complex",
         "[0:v]format=rgba,split=2[c][a];"
         "[c]format=yuv420p[cc];[a]alphaextract,format=yuv420p[aa];"
         "[cc][aa]hstack=inputs=2[v]",
         "-map", "[v]", "-an",
         "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(saida)],
        stdin=subprocess.PIPE)

    surf = skia.Surface(W, H)
    canvas = surf.getCanvas()
    quadro = np.empty((H, W, 4), dtype=np.uint8)
    # UNPREMUL de proposito: o `rgba` do ffmpeg e alpha DIRETO. Entregando o
    # premultiplicado do Skia, a cor viria ja multiplicada e o player
    # multiplicaria de novo — o cartao sairia sujo nas bordas.
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType,
                               skia.kUnpremul_AlphaType)

    # Quadro repetido = a peca parou. Guardo ONDE, nao so quantos: "85 parados"
    # nao diz se e um buraco de 3s no meio (que o olho resolve e desiste) ou
    # poeira espalhada (que nao incomoda ninguem).
    vistos, repetidos, faixas = set(), 0, []
    for f in range(n):
        a = cena.assinatura(f / FPS)
        if a in vistos:
            repetidos += 1
            if faixas and faixas[-1][1] == f - 1:
                faixas[-1][1] = f
            else:
                faixas.append([f, f])
        vistos.add(a)
        canvas.clear(skia.Color4f(0, 0, 0, 0))
        cena.desenhar(canvas, f / FPS)
        surf.readPixels(info, quadro, W * 4, 0, 0)
        p.stdin.write(quadro.tobytes())
    p.stdin.close()
    p.wait()

    mb = saida.stat().st_size / 1e6
    print(f"  {nome:<18} {spec['duracao']:5.1f}s  {n:4d} quadros  {mb:5.1f} MB"
          f"  parados: {repetidos}")
    for a, b in faixas:
        if b - a >= 8:      # menos de ~0,27s ninguem enxerga
            print(f"      parado {a/FPS:5.1f}s -> {b/FPS:5.1f}s  ({(b-a+1)/FPS:.1f}s)")
    return saida


def main():
    print(f"[reel-suporte] cor|alpha {W*2}x{H} @ {FPS}fps")
    for nome, spec in CENAS.items():
        renderizar(nome, spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
