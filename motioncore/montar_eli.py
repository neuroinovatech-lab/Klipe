"""
montar_eli.py — edição do vertical da Dra sobre percepção de padrões.

Aplica a receita validada em `command_klipe_edit_vertical` (memória):

  - zona segura: título entre o centro e o guide 66,66% (y≈1280 de 1920)
  - VARIAÇÃO de altura entre estilos (achatar tudo na mesma linha foi rejeitado)
  - hero/kinetic no CENTRO (sem posY) — "os títulos mais forte é no meio mesmo"
  - flash em -330 (o layout centralizado do flash cai no rosto em 9:16)
  - quote 620 / lower3rd e ribbon 430, ambos fontSize 110 (135 estoura a largura)
  - punch-in nas viradas: hardIn 1.26 + cutMask + Fast Woosh
  - SFX Regra 1: zoom >= 1.25 leva Zoom In no começo E scrooling no fim

**Todo texto sai da fala dela.** Cada elemento aponta pra um trecho da
transcrição e o script acha o segundo. Sem âncora, não entra.

Não corta nada — [[feedback_no_auto_cuts]]: só corta se ela pedir.

    python -m motioncore.montar_eli
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "public" / "projects" / "eli-premiere"
DESTINO = ROOT / "public" / "edit_config.json"

LARG, ALT, FPS = 1080, 1920, 30
DUR = 69.73

# posY por estilo — a tabela da memória, validada na tela pela usuária.
POS = {"flash": -330, "quote": 620, "lower3rd": 430, "ribbon": 430,
       "counter": 300, "livre": 0}
FONTE_MENOR = {"quote", "lower3rd", "ribbon"}     # 110; 135 estoura em 9:16

# (âncora na fala, estilo, texto, duração)
EDICAO = [
    ("capacidade de que pessoas autistas",  "flash",    "PESSOAS AUTISTAS", 2.6),
    ("como se a gente tivesse um sexto sentido", "hero", "UM SEXTO SENTIDO", 3.4),
    ("poder extraordinário na criação de padrões", "kinetic", "CRIAÇÃO DE PADRÕES", 3.0),
    ("é o córtex temporal",                 "ribbon",   "CÓRTEX TEMPORAL", 3.4),
    ("processamento de informações sensoriais", "lower3rd",
     "Processa informação sensorial e identifica irregularidades", 4.2),
    ("perceber e analisar padrões no ambiente", "livre", None, 4.0),
    ("eu antecipo as coisas",               "kinetic",  "EU ANTECIPO AS COISAS", 3.0),
    ("dualidade de não captar indiretas",   "livre",    None, 4.6),
    ("de inocente para sensitiva em segundos", "quote",
     "Passando de inocente para sensitiva em segundos", 4.4),
    ("já parou para refletir sobre a sua capacidade", "hero",
     "E VOCÊ, PERCEBE PADRÕES?", 4.0),
]

# O estilo `livre`: partes com fonte, tamanho, cor e entrada próprias.
# Tamanho em px absoluto — aqui o quadro é 1920 de altura, então cabe maior
# que no projeto 16:9.
LIVRES = {
    "perceber e analisar padrões no ambiente": [
        {"texto": "O CÓRTEX TEMPORAL", "fonte": "Montserrat", "tamanho": 40,
         "cor": "#78909C", "peso": 800, "entrada": "descer", "espaco": 0},
        {"texto": "PERCEBE", "fonte": "BebasNeue", "tamanho": 130,
         "cor": "#FFFFFF", "peso": 400, "entrada": "esquerda", "espaco": 10},
        {"texto": "E ANALISA", "fonte": "BebasNeue", "tamanho": 130,
         "cor": "#FFFFFF", "peso": 400, "entrada": "direita", "espaco": 0},
        {"texto": "padrões no ambiente", "fonte": "PlayfairDisplay", "tamanho": 46,
         "cor": "#E8940A", "peso": 400, "italico": True, "entrada": "subir",
         "espaco": 16},
    ],
    "dualidade de não captar indiretas": [
        {"texto": "A DUALIDADE", "fonte": "Montserrat", "tamanho": 38,
         "cor": "#E8940A", "peso": 800, "entrada": "fade", "espaco": 0},
        {"texto": "NÃO CAPTAR", "fonte": "BebasNeue", "tamanho": 120,
         "cor": "#B0BEC5", "peso": 400, "entrada": "esquerda", "espaco": 12},
        {"texto": "INDIRETAS", "fonte": "BebasNeue", "tamanho": 120,
         "cor": "#B0BEC5", "peso": 400, "entrada": "esquerda", "espaco": 0},
        {"texto": "MAS PREVER", "fonte": "BebasNeue", "tamanho": 132,
         "cor": "#FFFFFF", "peso": 400, "entrada": "direita", "espaco": 18},
        {"texto": "EVENTOS FUTUROS", "fonte": "BebasNeue", "tamanho": 132,
         "cor": "#FFD54F", "peso": 400, "entrada": "estourar", "espaco": 0},
    ],
}

# (âncora, direção, intensidade, duração, atraso)
#
# `in` com easing suave, NAO `hardIn`. O hardIn entra travado na intensidade e
# fica parado — medi que o zoom aplicava (diferenca 11,02 dentro da janela
# contra 0,76 fora), mas sem movimento ninguem percebe. `in` deriva de 1,0 ate
# a intensidade ao longo da janela inteira, que foi o que ela escolheu.
ZOOMS = [
    ("capacidade de que pessoas autistas",  "in", 1.26, 3.0, 0.0),
    ("como se a gente tivesse um sexto sentido", "in", 1.26, 3.0, 0.0),
    ("poder extraordinário na criação de padrões", "in", 1.14, 3.4, 0.0),
    ("é o córtex temporal",                 "in", 1.26, 3.0, 0.0),
    ("eu, por exemplo, sou ótima em padrões", "in",    1.12, 3.2, 0.0),
    ("eu antecipo as coisas",               "in", 1.26, 3.0, 0.0),
    ("dualidade de não captar indiretas",   "in",     1.15, 4.0, 0.2),
    ("de inocente para sensitiva em segundos", "in", 1.28, 2.6, 0.0),
    ("já parou para refletir sobre a sua capacidade", "in", 1.12, 4.0, 0.0),
]

# (âncora, arquivo, duração, atraso)
BROLLS = [
    ("poder extraordinário na criação de padrões", "broll_padroes.mp4",  3.2, 0.2),
    ("é o córtex temporal",                        "broll_cerebro.mp4",  3.4, 0.3),
    ("no meu trabalho ou com familiares",          "broll_trabalho.mp4", 3.2, 0.2),
    ("dualidade de não captar indiretas",          "broll_conexoes.mp4", 3.2, 0.3),
    # os 3 novos pedidos: "todos em split + mais alguns"
    ("um sexto sentido",                           "broll_pensando.mp4", 3.0, 0.4),
    ("processamento de informações sensoriais",    "broll_cerebro.mp4",  3.0, 0.3),
    ("prever eventos futuros",                     "broll_padroes.mp4",  2.8, 0.2),
]

# SFX — Regra 1: zoom forte leva DUPLA (Zoom In no start, scrooling no end).
# Esquecer o scrooling é o erro recorrente que ela percebe.
ZOOM_IN = "sfx/transition_sweep/Zoom In.mp3"
SCROOLING = "sfx/foley/scrooling_2.MP3"
WOOSH = "sfx/whooshes/Fast Woosh - SoundConteúdo.mp3"
IMPACTO = "sfx/riser_synth/Riser Deep Impact - SoundConteúdo.wav"


_DUR_CACHE = {}


def dur_real(rel: str) -> float:
    """Duração REAL do arquivo de SFX — regra do feedback_sfx_real_duration.

    Os spans eram chutados: dei 1,1s pro scrooling (arquivo tem 0,24s) e 1,4s
    pro Deep Impact (tem 10,8s). O chute quebra o alinhamento: o scrooling
    tem que TERMINAR exato no fim do zoom, e só a duração medida garante isso.
    """
    if rel not in _DUR_CACHE:
        import subprocess
        r = subprocess.run(["C:/ffmpeg/bin/ffprobe.exe", "-v", "error",
                            "-show_entries", "format=duration", "-of", "csv=p=0",
                            str(ROOT / "public" / rel)],
                           capture_output=True, text=True)
        _DUR_CACHE[rel] = float(r.stdout.strip() or 1.0)
    return _DUR_CACHE[rel]


def normaliza(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


def medir_tinta(a):
    """
    Caixa do TEXTO, ignorando fundo de tela cheia.

    O `hero` tem degradê ocupando o quadro inteiro e o `flash` tem brilho de
    fundo; medir alpha cru daria "0..1919" e mandaria o título pro céu. Uma
    linha coberta em mais de 85% da largura é fundo, não texto.
    """
    import numpy as np
    alpha = a[..., 3]
    solido = alpha > 200
    cobertura = solido.mean(axis=1)
    linhas = np.where((cobertura > 0) & (cobertura < 0.85))[0]
    if not len(linhas):
        return None
    cols = np.where(solido[linhas].max(axis=0))[0]
    return int(linhas.min()), int(linhas.max()), int(cols.min()), int(cols.max())


def corrigir_posy(titulos, cfg_base, reg):
    """
    Sobe o título só o necessário pra não invadir a legenda nem passar do guide.

    A receita manda MANTER variação de altura entre estilos — achatar tudo na
    mesma linha foi rejeitado. Então aqui não se recalcula posição: parte-se da
    tabela da receita e corrige-se apenas quem colide, pelo tanto exato.
    """
    import numpy as np

    from .captions import CaptionRenderer
    from .scene import Title, TitleRenderer

    cap = CaptionRenderer(cfg_base, LARG, ALT, fps=FPS, registry=reg)
    limite = cap.band()[0] - 28 if cfg_base.get("showCaptions") else round(ALT * 0.6666)
    limite = min(limite, round(ALT * 0.6666))
    topo = round(ALT * 0.06)
    ajustes = []
    for t in titulos:
        r = TitleRenderer(Title.from_dict(t), LARG, ALT, fps=FPS, registry=reg)
        a = np.frombuffer(r.render_still(round(r.duration_frames * 0.6)).tobytes(),
                          np.uint8).reshape(ALT, LARG, 4)
        cx = medir_tinta(a)
        if not cx:
            continue
        y0, y1, _, _ = cx
        sobe = max(0, y1 - limite)          # posY positivo SOBE
        if y0 - sobe < topo:                 # não empurrar pra fora por cima
            sobe = max(0, y0 - topo)
        if sobe > 0:
            t["posY"] = int(t.get("posY", 0)) + sobe
            ajustes.append((t["style"], y0, y1, sobe))
    return limite, ajustes


def main() -> int:
    from .render import suporta

    segs = json.loads((PROJ / "transcription.json").read_text(encoding="utf-8"))
    corrido, mapa = "", []
    for s in segs:
        t = normaliza(s["text"]) + " "
        mapa += [float(s["start"])] * len(t)
        corrido += t

    def achar(b):
        p = corrido.find(normaliza(b))
        return mapa[p] if p >= 0 else None

    caps = [{"id": f"c-{i:03d}", "startSec": round(float(s["start"]), 3),
             "endSec": round(float(s["end"]), 3), "text": s["text"].strip()}
            for i, s in enumerate(segs) if s["text"].strip()]

    # ordena por TEMPO antes de atribuir — a ordem da lista nao pode mandar,
    # senao o controle de sobreposicao descarta o que vem antes no video
    ancorados, faltaram = [], []
    for busca, estilo, texto, d in EDICAO:
        t = achar(busca)
        (ancorados if t is not None else faltaram).append(
            (t, busca, estilo, texto, d) if t is not None else busca)
    ancorados.sort(key=lambda x: x[0])

    titulos, sfx, usado_ate = [], [], -1.0
    for ini, busca, estilo, texto, d in ancorados:
        ini = max(ini, usado_ate)
        fim = min(ini + d, DUR)
        if fim - ini < 1.0:
            faltaram.append(busca + " (sem espaço)")
            continue
        t = {"id": f"t-{len(titulos):02d}", "startSec": round(ini, 2),
             "endSec": round(fim, 2), "style": estilo, "text": texto or ""}
        if estilo in POS:
            t["posY"] = POS[estilo]
        if estilo in FONTE_MENOR:
            t["fontSize"] = 110
        if estilo == "livre":
            t["partes"] = LIVRES[busca]
            t["text"] = " ".join(p["texto"] for p in LIVRES[busca])
        titulos.append(t)
        som = IMPACTO if estilo in ("flash", "hero") else WOOSH
        s_ini = max(0, ini - 0.2)
        # span = duração real, mas o Deep Impact tem 10,8s — cobre o título
        # com 1s de respiro e sai em fade em vez de inundar a fala
        s_dur = min(dur_real(som), (fim - ini) + 1.0)
        sfx.append({"id": f"s-{len(sfx):02d}", "src": som,
                    "startSec": round(s_ini, 2),
                    "endSec": round(s_ini + s_dur, 2),
                    "volume": 0.42, "fadeIn": 0, "fadeOut": 0.4, "srcStart": 0,
                    "baseDurationSec": round(dur_real(som), 2)})
        usado_ate = fim + 0.4

    zooms, sem_z = [], []
    for busca, direcao, forca, d, atraso in ZOOMS:
        ini = achar(busca)
        if ini is None:
            sem_z.append(busca)
            continue
        ini += atraso
        fim = min(ini + d, DUR)
        zooms.append({"id": f"z-{len(zooms):02d}", "startSec": round(ini, 2),
                      "endSec": round(fim, 2), "direction": direcao,
                      "intensity": forca, "easing": "smooth"})
        # Regra 1: zoom forte = SFX dupla
        if forca >= 1.25:
            dz = dur_real(ZOOM_IN)          # 0,29s medido
            ds = dur_real(SCROOLING)        # 0,24s medido
            sfx.append({"id": f"s-z{len(sfx):02d}", "src": ZOOM_IN,
                        "startSec": round(ini, 2), "endSec": round(ini + dz, 2),
                        "volume": 1.995, "fadeIn": 0, "fadeOut": 0, "srcStart": 0,
                        "baseDurationSec": round(dz, 2)})
            # o scrooling TERMINA exato no fim do zoom — começa dur_real antes
            sfx.append({"id": f"s-e{len(sfx):02d}", "src": SCROOLING,
                        "startSec": round(max(0, fim - ds), 2), "endSec": round(fim, 2),
                        "volume": 0.70, "fadeIn": 0, "fadeOut": 0, "srcStart": 0,
                        "baseDurationSec": round(ds, 2)})
    zooms.sort(key=lambda z: z["startSec"])

    brolls, sem_b = [], []
    for busca, arq, d, atraso in BROLLS:
        ini = achar(busca)
        if ini is None or not (PROJ / "brolls" / arq).exists():
            sem_b.append(busca if ini is None else f"{arq} faltando")
            continue
        ini += atraso
        brolls.append({"id": f"b-{len(brolls):02d}",
                       "src": f"projects/eli-premiere/brolls/{arq}",
                       "startSec": round(ini, 2), "endSec": round(min(ini + d, DUR), 2),
                       "label": arq.replace("broll_", "").replace(".mp4", ""),
                       "fadeIn": 0.15, "fadeOut": 0.15})
    brolls.sort(key=lambda b: b["startSec"])
    sfx.sort(key=lambda s: s["startSec"])

    cfg = {
        "videoSrc": "projects/eli-premiere/video.mp4",
        "videoDuration": DUR, "fps": FPS, "width": LARG, "height": ALT,
        "aspectRatio": "9:16",
        "titles": titulos, "zooms": zooms, "brolls": brolls, "sfx": sfx,
        "captions": caps, "shapes": [], "musicTracks": [],
        "keepRanges": [], "videoClips": [], "audioRegions": [], "cutMarks": [],
        # LIGADA a pedido dela ("pode deixar por cima, e so um video exemplo").
        # Atencao pro proximo projeto: este master ja vem com legenda QUEIMADA
        # do Premiere, entao ficam DUAS na tela. Com master limpo, some.
        "showCaptions": True, "showProgressBar": True,
        "captionStyle": "destaque", "captionFont": "Montserrat",
        "captionFontSize": 82, "captionColor": "#FFFFFF",
        "captionHighlightColor": "#E8940A", "captionKaraoke": True,
        "captionMaxLines": 2, "captionWordGap": 12, "captionLineGap": 8,
        "captionX": 0, "captionY": 0,
        "colorCorrection": {"brightness": 0, "contrast": 0,
                            "saturation": 0, "temperature": 0},
        "videoPosX": 0, "videoPosY": 0, "videoBaseScale": 1, "videoRotation": 0,
        "videoOpacity": 1, "videoVolume": 1, "videoMuted": False,
        "videoPlaybackRate": 1, "videoBaseDurationSec": DUR,
        "barColor": "#E8940A", "barHeight": 5, "trackZOrders": {},
    }
    # Valida e corrige ANTES de gravar — a regra de ouro da receita e nunca
    # descobrir posicao errada depois do render.
    from .render import registry as _reg
    limite, ajustes = corrigir_posy(titulos, cfg, _reg())
    cfg["titles"] = titulos

    DESTINO.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")

    nao = sorted({t["style"] for t in titulos if not suporta(t["style"])})
    print(f"{len(titulos)} titulos | {len(brolls)} brolls | {len(zooms)} zooms | "
          f"{len(sfx)} sfx | {len(caps)} legendas")
    print(f"  {LARG}x{ALT} 9:16 @ {FPS}fps | {DUR}s")
    print(f"  fora do MotionCore: {nao or 'NENHUM'}")
    print(f"  limite (legenda/guide): y{limite}")
    for t in titulos:
        print(f"    {t['startSec']:>5.1f}s {t['style']:<9} posY={t.get('posY','centro'):<7} {t['text'][:34]}")
    if ajustes:
        print("  subidos pra nao colidir:")
        for est, y0, y1, sobe in ajustes:
            print(f"    {est:<9} tinta y{y0}..{y1} -> subiu {sobe}px")
    if faltaram:
        print(f"  NAO ancorados: {faltaram}")
    if sem_z:
        print(f"  zooms sem ancora: {sem_z}")
    if sem_b:
        print(f"  brolls sem ancora: {sem_b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
