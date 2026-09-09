"""
montar_gmod.py — edição completa do vídeo de gameplay (GMod da Mentira).

É o oposto do vídeo da médica: 16:9 em vez de 9:16, fala rápida, humor de
gritaria em grupo. Serve de teste do motor num formato que nunca passou por
ele — os 20 estilos portados foram todos calibrados em 9:16.

**Todo texto sai da fala.** Cada elemento aponta pra um trecho da transcrição e
o script acha o segundo em que aquilo é dito. Se não encontrar, avisa e NÃO
inventa posição.

Não corta nada: silêncio e respiração ficam como estão.

**posY é MEDIDO, não chutado.** Cada estilo ancora numa altura própria, feita
pra um quadro de 1920 de altura. Em 16:9 (1080) vários caem em cima da legenda
ou fora da área segura — foi o que aconteceu na primeira versão. Aqui o script
desenha cada título, mede a caixa de tinta sólida e calcula o deslocamento.
Funciona pra qualquer formato, sem tabela de posição por estilo.

    python -m motioncore.montar_gmod
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "public" / "projects" / "gmod-mentira"
DESTINO = ROOT / "public" / "edit_config.json"

LARG, ALT, FPS = 1920, 1080, 30
DUR = 739.99

# Só o texto sólido conta. Abaixo disso é o brilho de fundo do estilo, que no
# `flash` sozinho cobre 897px de 1080 e faria o cálculo mandar o título pro céu.
TINTA = 140
MARGEM = 0.06          # título-seguro
FOLGA_LEGENDA = 30     # respiro entre o título e o topo da legenda

# Estes desenham colados no rodapé por natureza; ficam logo acima da legenda
# em vez de subirem pro meio do quadro.
RODAPE = {"lower3rd", "ribbon"}

# (trecho pra ancorar, estilo, texto, duração)
EDICAO = [
    ("povo de chat é muito burro",     "flash",    "POVO DE CHAT É MUITO BURRO", 3.2),
    ("cês são surdos",                 "flash",    "CÊS SÃO SURDOS!", 2.6),
    ("eu sou inocêncio",               "kinetic",  "INOCÊNCIO", 2.6),
    ("Isso aí é pior que assassino",   "lower3rd", "Pior que assassino", 3.0),
    ("eu dropo a Golden Gun",          "ribbon",   "SE ACUSAREM ALGUÉM, EU DROPO A GOLDEN GUN", 4.0),
    ("Tem cinco minutos na mão",       "counter",  "5 minutos", 3.0),
    ("Pede pro cara soletrar inocente", "livre",   None, 4.5),
    ("letra inocente ao contrario",    "livre",    None, 4.5),
    ("Deu uma louca no policia",       "flash",    "A POLÍCIA TÁ LOUCA", 2.8),
    ("o cara me atropelou",            "flash",    "ATROPELADO", 2.4),
    ("O carro matou os dois",          "kinetic",  "O CARRO MATOU OS DOIS", 3.2),
    ("Vocês que tão pão no ouvido",    "lower3rd", "Pão no ouvido", 2.8),
    ("estratégia de matar meu amigo",  "quote",    "Usei a estratégia de matar meu amigo traidor pra ficar imune à desconfiança", 6.0),
    ("Ele fica cozinhando",            "flash",    "COZINHANDO", 2.4),
    ("Eu falei que era o Sam",         "kinetic",  "EU FALEI QUE ERA O SAM", 3.0),

    # segunda passada: fecha os buracos pra edição cobrir os 12 min inteiros,
    # não só os picos. Ritmo alvo ~1 título a cada 25s.
    ("Sai de perto do Davy Jones",     "flash",    "SAI DE PERTO DO DAVY JONES", 2.6),
    ("Tem um gato",                    "kinetic",  "TEM UM GATO", 2.4),
    ("Dá pra subir no gato",           "lower3rd", "Dá pra subir no gato", 2.6),
    ("Cara, Squid Game",               "flash",    "SQUID GAME", 2.4),
    ("Me assassinaram",                "kinetic",  "ME ASSASSINARAM", 2.6),
    ("Quem é o detetive",              "counter",  "Quem é o detetive?", 2.8),
    ("Ambulância, meu Deus",           "flash",    "AMBULÂNCIA", 2.2),
    ("Mataram o detetive",             "kinetic",  "MATARAM O DETETIVE", 2.8),
    ("É suspeito, hein",               "ribbon",   "É SUSPEITO, HEIN", 3.0),
    ("Eu acho que reviveram o Chico",  "lower3rd", "Reviveram o Chico?", 2.8),
    ("Olha só, o Acre",                "kinetic",  "O ACRE", 2.4),
    ("morreram no carro",              "quote",    "O carro matou os dois terroristas", 4.0),
    ("É o Coyote",                     "flash",    "É O COYOTE!", 2.4),
    ("Jogaram fumaça aqui",            "kinetic",  "JOGARAM FUMAÇA", 2.6),
    ("tá atirando em todo mundo",      "flash",    "ATIRANDO EM TODO MUNDO", 2.6),
    ("Me matei de carro",              "flash",    "ME MATEI DE CARRO", 2.6),
]

LIVRES = {
    "Pede pro cara soletrar inocente": [
        {"texto": "TESTE DO POLÍGRAFO", "fonte": "Montserrat", "tamanho": 46,
         "cor": "#B388FF", "peso": 800, "entrada": "descer", "espaco": 0},
        {"texto": "SOLETRA", "fonte": "BebasNeue", "tamanho": 150,
         "cor": "#FFFFFF", "peso": 400, "entrada": "esquerda", "espaco": 8},
        {"texto": "INOCENTE", "fonte": "BebasNeue", "tamanho": 150,
         "cor": "#FFD54F", "peso": 400, "entrada": "direita", "espaco": 0},
    ],
    "letra inocente ao contrario": [
        {"texto": "AGORA", "fonte": "Montserrat", "tamanho": 46,
         "cor": "#78909C", "peso": 800, "entrada": "fade", "espaco": 0},
        {"texto": "AO CONTRÁRIO", "fonte": "BebasNeue", "tamanho": 168,
         "cor": "#FF5252", "peso": 400, "entrada": "estourar", "espaco": 8},
        {"texto": "3, 2, 1", "fonte": "Montserrat", "tamanho": 62,
         "cor": "#FFFFFF", "peso": 900, "entrada": "subir", "espaco": 14},
    ],
}

# Zoom: em gameplay o corte de câmera é o que dá ritmo. Entra na reação, não
# na fala inteira — por isso são curtos e presos ao mesmo gancho do título.
# (trecho, direção, intensidade, duração, atraso em relação ao gancho)
ZOOMS = [
    ("povo de chat é muito burro",      "in",     1.12, 3.0, 0.0),
    ("cês são surdos",                  "hardIn", 1.22, 2.0, 0.0),
    ("Sai de perto do Davy Jones",      "in",     1.10, 2.5, 0.0),
    ("eu dropo a Golden Gun",           "in",     1.14, 3.5, 0.0),
    ("Pede pro cara soletrar inocente", "hardIn", 1.18, 3.0, 0.5),
    ("Deu uma louca no policia",        "hardIn", 1.25, 2.2, 0.0),
    ("o cara me atropelou",             "hardIn", 1.28, 2.0, 0.0),
    ("O carro matou os dois",           "in",     1.15, 3.0, 0.0),
    ("letra inocente ao contrario",     "hardIn", 1.20, 3.0, 0.4),
    ("estratégia de matar meu amigo",   "in",     1.10, 5.0, 0.0),
    ("Eu falei que era o Sam",          "hardIn", 1.24, 2.5, 0.0),
    ("Tem um gato",                     "in",     1.16, 2.4, 0.0),
    ("Cara, Squid Game",                "hardIn", 1.20, 2.2, 0.0),
    ("Me assassinaram",                 "hardIn", 1.26, 2.0, 0.0),
    ("Quem e o detetive",               "in",     1.10, 2.8, 0.0),
    ("Ambulancia, meu Deus",            "hardIn", 1.22, 2.0, 0.0),
    ("Mataram o detetive",              "hardIn", 1.20, 2.6, 0.0),
    ("E suspeito, hein",                "in",     1.14, 3.0, 0.0),
    ("Olha so, o Acre",                 "hardIn", 1.18, 2.2, 0.0),
    ("E o Coyote",                      "hardIn", 1.24, 2.2, 0.0),
    ("Jogaram fumaca aqui",             "in",     1.16, 2.5, 0.0),
    ("ta atirando em todo mundo",       "hardIn", 1.22, 2.4, 0.0),
    ("Me matei de carro",               "hardIn", 1.26, 2.4, 0.0),
]

# B-roll do Pexels. Aqui ele é CUTAWAY CÔMICO: entra na piada que o próprio
# vídeo já faz — polígrafo quando mandam soletrar "inocente", viatura quando
# gritam que a polícia enlouqueceu. Curto de propósito: cutaway longo em
# gameplay mata o ritmo, porque o que prende é a reação deles.
# (trecho, arquivo, duração, atraso)
BROLLS = [
    ("Pede pro cara soletrar inocente", "broll_poligrafo.mp4", 2.6, 0.4),
    ("Deu uma louca no policia",        "broll_policia.mp4",   2.2, 0.2),
    ("o cara me atropelou",             "broll_atropelo.mp4",  2.0, 0.1),
    ("Quem é o detetive",               "broll_detetive.mp4",  2.4, 0.3),
    ("É suspeito, hein",                "broll_suspeita.mp4",  2.2, 0.2),
    ("estratégia de matar meu amigo",   "broll_traicao.mp4",   2.8, 0.6),
    ("Tem um gato",                     "broll_gato.mp4",      2.2, 0.3),
    ("Ambulância, meu Deus",            "broll_ambulancia.mp4", 2.0, 0.2),
    ("Jogaram fumaça aqui",             "broll_fumaca.mp4",    2.2, 0.3),
    ("tá atirando em todo mundo",       "broll_caos.mp4",      2.2, 0.2),
    ("Cara, Squid Game",                "broll_mascara.mp4",   2.2, 0.2),
    ("Tem cinco minutos na mão",        "broll_relogio.mp4",   2.2, 0.3),
]

# SFX: whoosh na entrada do título, impacto nos picos. Volume baixo — o vídeo
# já é gritaria, som de edição por cima vira poluição.
WHOOSH = "sfx/riser_synth/Riser Reverse Whoosh - SoundConteúdo.wav"
IMPACTO = "sfx/riser_synth/Riser Deep Impact - SoundConteúdo.wav"
CLIQUE = "sfx/pop_click/Marker - SoundConteúdo.wav"


def normaliza(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


def medir_posy(titulo: dict, cap_topo: int, reg) -> int:
    """Quanto este título precisa subir pra caber na área segura."""
    from .scene import Title, TitleRenderer

    d = dict(titulo, posY=0)
    r = TitleRenderer(Title.from_dict(d), LARG, ALT, fps=FPS, registry=reg)
    img = r.render_still(round(r.duration_frames * 0.6))
    a = np.frombuffer(img.tobytes(), np.uint8).reshape(ALT, LARG, 4)
    ys = np.where(a[..., 3].max(axis=1) > TINTA)[0]
    if not len(ys):
        return 0
    y0, y1 = int(ys.min()), int(ys.max())

    limite = cap_topo - FOLGA_LEGENDA
    if titulo["style"] in RODAPE:
        return int(y1 - limite)          # encosta na legenda sem invadir
    topo = round(ALT * MARGEM)
    return int((y0 + y1) / 2 - (topo + limite) / 2)


def main() -> int:
    from .captions import CaptionRenderer
    from .render import registry, suporta

    segs = json.loads((PROJ / "transcription.json").read_text(encoding="utf-8"))
    reg = registry()

    corrido, mapa = "", []
    for s in segs:
        t = normaliza(s["text"]) + " "
        mapa += [float(s["start"])] * len(t)
        corrido += t

    def achar(busca):
        p = corrido.find(normaliza(busca))
        return mapa[p] if p >= 0 else None

    caps = [{"id": f"c-{i:03d}", "startSec": round(float(s["start"]), 3),
             "endSec": round(float(s["end"]), 3), "text": s["text"].strip()}
            for i, s in enumerate(segs) if s["text"].strip()]

    base = {"width": LARG, "height": ALT, "fps": FPS, "captions": caps,
            "captionStyle": "boxed", "captionFont": "Montserrat",
            "captionFontSize": 78, "captionColor": "#FFFFFF",
            "captionHighlightColor": "#FFD54F", "captionKaraoke": True,
            "captionMaxLines": 2, "captionWordGap": 12, "captionLineGap": 8,
            "captionX": 0, "captionY": 40}
    cap_topo = CaptionRenderer(base, LARG, ALT, fps=FPS, registry=reg).band()[0]

    # Ordenar por TEMPO antes de atribuir, não pela ordem da lista. Sem isso o
    # controle de sobreposição (`usado_ate`) descarta tudo que aparece depois
    # na lista mas antes no vídeo — foi assim que 5 títulos sumiram calados.
    ancorados = []
    faltaram = []
    for busca, estilo, texto, d in EDICAO:
        ini = achar(busca)
        if ini is None:
            faltaram.append(busca)
        else:
            ancorados.append((ini, busca, estilo, texto, d))
    ancorados.sort(key=lambda x: x[0])

    titulos, sfx, usado_ate = [], [], -1.0
    for ini, busca, estilo, texto, d in ancorados:
        ini = max(ini, usado_ate)
        fim = min(ini + d, DUR)
        if fim - ini < 1.0:
            faltaram.append(busca + "  (sem espaço)")
            continue
        t = {"id": f"t-{len(titulos):02d}", "startSec": round(ini, 2),
             "endSec": round(fim, 2), "style": estilo, "text": texto or ""}
        if estilo == "livre":
            t["partes"] = LIVRES[busca]
            # o rótulo existe pro clipe não aparecer vazio na timeline; quem
            # desenha são as `partes`
            t["text"] = " ".join(p["texto"] for p in LIVRES[busca])
        t["posY"] = medir_posy(t, cap_topo, reg)
        titulos.append(t)

        som = IMPACTO if estilo == "flash" else CLIQUE if estilo == "lower3rd" else WHOOSH
        sfx.append({"id": f"s-{len(sfx):02d}", "src": som,
                    "startSec": round(max(0, ini - 0.25), 2),
                    "endSec": round(max(0, ini - 0.25) + 1.6, 2),
                    "volume": 0.28, "fadeIn": 0, "fadeOut": 0.3, "srcStart": 0})
        usado_ate = fim + 0.6

    zooms, sem_zoom = [], []
    for busca, direcao, forca, d, atraso in ZOOMS:
        ini = achar(busca)
        if ini is None:
            sem_zoom.append(busca)
            continue
        ini += atraso
        zooms.append({"id": f"z-{len(zooms):02d}", "startSec": round(ini, 2),
                      "endSec": round(min(ini + d, DUR), 2), "direction": direcao,
                      "intensity": forca, "easing": "smooth"})
    zooms.sort(key=lambda z: z["startSec"])

    brolls, sem_broll = [], []
    for busca, arq, d, atraso in BROLLS:
        ini = achar(busca)
        if ini is None or not (PROJ / "brolls" / arq).exists():
            sem_broll.append(busca if ini is None else f"{arq} (arquivo faltando)")
            continue
        ini += atraso
        brolls.append({"id": f"b-{len(brolls):02d}",
                       "src": f"projects/gmod-mentira/brolls/{arq}",
                       "startSec": round(ini, 2),
                       "endSec": round(min(ini + d, DUR), 2),
                       "label": arq.replace("broll_", "").replace(".mp4", ""),
                       "fadeIn": 0.12, "fadeOut": 0.12})
    brolls.sort(key=lambda b: b["startSec"])

    cfg = dict(base)
    cfg.update({
        "videoSrc": "projects/gmod-mentira/video.mp4",
        "videoDuration": DUR, "aspectRatio": "16:9",
        "titles": titulos, "zooms": zooms, "sfx": sfx, "brolls": brolls,
        "shapes": [], "musicTracks": [],
        "keepRanges": [], "videoClips": [], "audioRegions": [], "cutMarks": [],
        "showCaptions": True, "showProgressBar": True,
        "colorCorrection": {"brightness": 0, "contrast": 0,
                            "saturation": 0, "temperature": 0},
        "videoPosX": 0, "videoPosY": 0, "videoBaseScale": 1, "videoRotation": 0,
        "videoOpacity": 1, "videoVolume": 1, "videoMuted": False,
        "videoPlaybackRate": 1, "videoBaseDurationSec": DUR,
        "barColor": "#FFD54F", "barHeight": 5, "trackZOrders": {},
    })
    DESTINO.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")

    nao = sorted({t["style"] for t in titulos if not suporta(t["style"])})
    print(f"{len(titulos)} titulos | {len(brolls)} brolls | {len(zooms)} zooms | {len(sfx)} sfx | {len(caps)} legendas")
    print(f"  formato: {LARG}x{ALT} 16:9 @ {FPS}fps | legenda comeca em y={cap_topo}")
    print(f"  fora do MotionCore: {nao or 'NENHUM'}")
    print("  posY medido por titulo:")
    for t in titulos:
        print(f"    {t['style']:<9} posY {t['posY']:>5}  {t['text'][:34]}")
    if faltaram:
        print(f"  titulos NAO ancorados: {faltaram}")
    if sem_zoom:
        print(f"  zooms NAO ancorados: {sem_zoom}")
    if sem_broll:
        print(f"  brolls NAO ancorados: {sem_broll}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
