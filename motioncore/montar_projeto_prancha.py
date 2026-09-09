# -*- coding: utf-8 -*-
"""
montar_projeto_prancha.py — poe "DE FORMIS" no Klipe como projeto editavel.

A prancha entra como video principal, trechos do video REAL dela entram por
cima nos momentos em que a presenca dela vale mais que o desenho, e as SFX
acompanham os gestos da pena.

Regra que essa edicao respeita e que ja custou caro antes: **duracao de SFX se
MEDE, nao se chuta.** Um zoom de 0,29s com span de 1,2s no config faz o som
arrastar depois que o movimento acabou, e o corte inteiro perde a batida.
Aqui todo span sai de um ffprobe.

    python -m motioncore.montar_projeto_prancha
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PUB = RAIZ / "public"
PROJ = PUB / "projects" / "eli-prancha"
ORIG = PUB / "projects" / "eli-premiere" / "video.mp4"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"

DUR = 69.7527
W, H, FPS = 1080, 1920, 30

# ── trechos do video REAL que ficam ──────────────────────────────────────
# Onde o rosto dela diz mais que o desenho: quando ela fala de si e quando
# devolve a pergunta. O resto e prancha.
TRECHOS = [
    (5.98, 8.82, "sexto-sentido"),      # "é como se a gente tivesse..."
    (35.96, 38.16, "eu-por-exemplo"),   # "eu, por exemplo, sou ótima"
    (63.40, 69.04, "e-voce"),           # a pergunta de volta
]

# ── trechos reeditados pelo OMNI ─────────────────────────────────────────
# O que so geracao faz: mexer nos pixels que sao ELA ou o que esta atras dela.
# Entram ANTES da prancha na lista porque o player desenha b-roll em ordem de
# array — o OMNI substitui a imagem dela, a prancha desenha por cima.
#
# Normalizados pra 1080x1920@30: o OMNI devolve 720x1280@24, e 24 em linha de
# 30 nao divide certo (aparece tranco no movimento).
OMNI = [
    ("omni/omni_8_9s_149540_norm.mp4", 8.94, 12.94, "malha na parede"),
    # Os dois abaixo eu recomendei descartar e ela mandou entrar pra ver
    # rodando. O que os condena e o mesmo: o OMNI regenera o quadro INTEIRO,
    # e a legenda queimada faz parte do quadro — entao ele a redesenha de
    # memoria e sai embaralhada ("nos kjude a perceber"). O corte da parede
    # escapou porque a mudanca era local.
    # Segunda rodada, com pedido LOCAL (parede, ar em volta) em vez de global.
    # A legenda queimada saiu quase intacta — so uma palavra trocada por
    # trecho, contra frase inteira embaralhada nos globais. A licao: pedido
    # contido nao e so mais seguro, e mais fiel.
    ("omni/omni_2_3s_756442_norm.mp4",  2.30,  5.60, "PADROES atras dela"),
    ("omni/omni_14_8s_848268_norm.mp4", 14.82, 18.82, "cerebro na parede"),
    ("omni/omni_40_0s_797284_norm.mp4", 40.00, 44.00, "icones flutuando"),
]

# ── a prancha em BLOCOS ──────────────────────────────────────────────────
# Oito clipes em vez de um de 70s. O motivo nao e tecnico, e de edicao: clipe
# de 70s nao tem onde pegar. Em blocos ela reposiciona, encurta e apaga na UI
# sem depender de mim pra coisa basica — que e o ponto do hibrido. Cada bloco
# leva alpha, entao segue sendo camada de efeito sobre a imagem dela.
BLOCOS = [
    ("bloco_abertura.mp4",   0.00,  8.90, "prancha abertura"),
    ("bloco_malha.mp4",      8.90, 15.40, "prancha malha"),
    ("bloco_cortex.mp4",    15.40, 22.50, "prancha cortex"),
    ("bloco_irregular.mp4", 22.50, 31.60, "prancha irregular"),
    ("bloco_ambiente.mp4",  31.60, 36.00, "prancha ambiente"),
    ("bloco_pessoal.mp4",   36.00, 48.50, "prancha pessoal"),
    ("bloco_dualidade.mp4", 48.50, 62.60, "prancha dualidade"),
    ("bloco_fecho.mp4",     62.60, 69.75, "prancha fecho"),
]

# ── splits: ela em cima, a prancha embaixo, sem linha de corte ───────────
# So onde a folha EXISTE — dentro das janelas de imagem o papel sai e a metade
# de baixo viria preta.
SPLITS = [
    ("split_sensorial.mp4",      22.60, 26.60, "split sensorial"),
    ("split_irregularidade.mp4", 26.80, 30.80, "split irregularidade"),
    ("split_dualidade.mp4",      50.60, 54.40, "split dualidade"),
]

# ── gestos da pena que pedem som ─────────────────────────────────────────
# (instante, arquivo, volume)  — o span sai da duracao MEDIDA
GESTOS = [
    (0.20, "writing/Scribble Underline Longo.wav", 0.30),   # a moldura
    (2.30, "pop_click/Marker - SoundConteúdo.wav", 0.35),   # PADRÕES
    (4.10, "pop_click/Click - SoundConteúdo.wav", 0.45),    # o ponto vermelho
    (6.20, "writing/Scribble Circle Curto.wav", 0.28),      # os raios
    (9.30, "writing/Scribble Circle.wav", 0.26),            # a malha
    (15.10, "foley/Gear.mp3", 0.22),                        # os anéis
    (17.40, "reverse/Reveal - SoundConteúdo.wav", 0.34),    # o córtex
    (25.40, "foley/Cam Shutter - SoundConteúdo.wav", 0.40),  # a irregularidade
    (31.50, "transition_sweep/Zoom In.mp3", 0.30),          # a régua
    (40.00, "foley/Fast Metal Slice - SoundConteúdo.wav", 0.32),  # a agulha
    (44.40, "writing/Scribble Circle.wav", 0.26),           # convergência
    (48.80, "riser_synth/Dark Riser - SoundConteúdo.wav", 0.22),  # a dualidade
    (58.40, "transition_sweep/Zoom In.mp3", 0.34),          # a travessia
    (63.20, "pop_click/Marker - SoundConteúdo.wav", 0.38),  # E VOCÊ?
]

# ── zooms: só onde o desenho ganha um detalhe que merece aproximação ─────
ZOOMS = [
    (4.00, 5.30, "in", 1.26),
    (17.30, 19.20, "in", 1.30),
    (25.30, 27.00, "in", 1.34),
    (39.90, 41.60, "in", 1.28),
    (63.10, 65.00, "in", 1.24),
]


def dur_real(rel: str) -> float:
    """Duração MEDIDA do arquivo. Nunca chutada — ver docstring do módulo."""
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(PUB / "sfx" / rel)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise SystemExit(f"não consegui medir a SFX: {rel}")


def cortar_trechos() -> list[dict]:
    """Recorta os pedaços do vídeo original em arquivos próprios."""
    PROJ.mkdir(parents=True, exist_ok=True)
    saida = []
    for i, (ini, fim, nome) in enumerate(TRECHOS):
        arq = PROJ / f"real_{nome}.mp4"
        if not arq.exists():
            subprocess.run(
                [FFMPEG, "-y", "-v", "error", "-ss", f"{ini:.3f}",
                 "-t", f"{fim-ini:.3f}", "-i", str(ORIG),
                 "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                        f"crop={W}:{H}",
                 "-an", "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21",
                 "-pix_fmt", "yuv420p", str(arq)], check=True)
        saida.append({
            "id": f"real-{i+1}", "src": versionar(arq),
            "startSec": round(ini, 2), "endSec": round(fim, 2),
            "label": nome, "fadeIn": 0.25, "fadeOut": 0.25,
        })
        print(f"  trecho real {nome:<16} {ini:6.2f}–{fim:5.2f}")
    return saida


def versionar(arq: Path) -> str:
    """Copia o arquivo pra um nome com versao e devolve o caminho relativo.

    O servidor nao manda `Cache-Control`, `ETag` nem `Last-Modified` nos
    videos. Sem validador o browser NAO consegue revalidar: ele segura a copia
    que baixou — inclusive uma copia quebrada, pega enquanto o arquivo estava
    sendo reescrito — e F5 nao adianta. Foi o que travou o preview aqui.

    Query string (`?v=123`) resolveria no browser mas quebraria o lado do
    render, que resolve `videoSrc` como caminho de disco. Versionar o NOME
    serve aos dois: URL nova pro browser, arquivo real pro render.
    """
    v = int(arq.stat().st_mtime)
    novo = arq.with_name(f"{arq.stem}_v{v}{arq.suffix}")
    if not novo.exists():
        shutil.copy2(arq, novo)
    for velho in arq.parent.glob(f"{arq.stem}_v*{arq.suffix}"):
        if velho != novo:
            velho.unlink(missing_ok=True)
    return f"projects/{arq.parent.name}/{novo.name}"


def main() -> int:

    # A PRANCHA E CAMADA, nao video. O principal e a imagem dela, crua e
    # trocavel; o efeito entra por cima com alpha. Antes eu tinha fundido os
    # dois num mp4 so — num editor isso mata a separacao: nao da pra trocar a
    # base sem refazer o efeito, nem mexer no efeito sem re-render a base.
    brolls = []
    for i, (rel, ini, fim, rot) in enumerate(OMNI):
        arq = PUB / "projects" / "eli-premiere" / rel
        if not arq.exists():
            print(f"  ! omni faltando: {rel}")
            continue
        brolls.append({
            "id": f"omni-{i+1}", "src": f"projects/eli-premiere/{rel}",
            "startSec": ini, "endSec": fim, "label": rot,
            "fadeIn": 0, "fadeOut": 0,
        })
        print(f"  omni  {rot:<22} {ini:6.2f}–{fim:5.2f}")
    for i, (arq, ini, fim, rot) in enumerate(SPLITS):
        if not (PROJ / arq).exists():
            print(f"  ! split faltando: {arq}"); continue
        brolls.append({
            "id": f"split-{i+1}", "src": f"projects/eli-prancha/{arq}",
            "startSec": ini, "endSec": fim, "label": rot,
            "fadeIn": 0.2, "fadeOut": 0.2,
        })
        print(f"  split {rot:<22} {ini:6.2f}–{fim:5.2f}")
    for i, (arq, ini, fim, rot) in enumerate(BLOCOS):
        if not (PROJ / arq).exists():
            print(f"  ! bloco faltando: {arq}"); continue
        brolls.append({
            "id": f"prancha-{i+1}", "src": f"projects/eli-prancha/{arq}",
            "startSec": ini, "endSec": fim, "label": rot,
            "alpha": True, "fadeIn": 0, "fadeOut": 0,
        })
        print(f"  bloco {rot:<22} {ini:6.2f}–{fim:5.2f}")

    sfx = []
    for i, (t, rel, vol) in enumerate(GESTOS):
        d = dur_real(rel)
        # o som ocupa exatamente o que ele DURA (ou o que sobra até o fim)
        span = min(d, DUR - t)
        sfx.append({
            "id": f"sfx-{i+1}", "src": f"sfx/{rel}",
            "startSec": round(t, 2), "endSec": round(t + span, 2),
            "volume": vol, "fadeIn": 0.02, "fadeOut": min(0.25, span * 0.35),
            "srcStart": 0, "baseDurationSec": round(d, 3),
        })
        print(f"  sfx {Path(rel).stem:<28} {t:6.2f}  dur real {d:.2f}s")

    zooms = [{"id": f"z-{i+1}", "startSec": a, "endSec": b,
              "direction": d, "intensity": v, "easing": "inOutCubic"}
             for i, (a, b, d, v) in enumerate(ZOOMS)]

    cfg = {
        "videoSrc": "projects/eli-premiere/video.mp4",
        "videoDuration": DUR, "videoBaseDurationSec": DUR,
        "fps": FPS, "width": W, "height": H, "aspectRatio": "9:16",
        "titles": [], "shapes": [], "captions": [], "musicTracks": [],
        "keepRanges": [], "videoClips": [], "audioRegions": [], "cutMarks": [],
        "brolls": brolls, "sfx": sfx, "zooms": zooms,
        # a prancha ja tem a voz dela embutida? nao — o audio vem do original,
        # entao a faixa principal e a da prancha renderizada com audio
        "showCaptions": False, "showProgressBar": False,
        # A grade da imagem dela era assada no ffmpeg do render; agora vive
        # aqui, onde o painel de Filtros alcanca. Mesmos numeros de antes
        # (satur. 0.30, contraste 1.10, colorbalance rs 0.16) na escala do
        # editor — a diferenca e que agora voce mexe neles.
        "colorCorrection": {"brightness": 1, "contrast": 10, "saturation": -70,
                            "temperature": 32, "hue": 0, "highlight": 0,
                            "shadow": 0, "filterIntensity": 100,
                            "filterName": "Prancha"},
        "videoPosX": 0, "videoPosY": 0, "videoBaseScale": 1, "videoRotation": 0,
        "videoOpacity": 1, "videoVolume": 1, "videoMuted": False,
        "videoPlaybackRate": 1,
        "barColor": "#8F1D18", "barHeight": 4, "trackZOrders": {},
    }

    alvo = PUB / "edit_config.json"
    # Preserva TODA chave que este builder nao define. Eu tinha escrito o
    # config do zero e sumido com 11 campos `caption*`; o editor le esses
    # campos sem guarda e o projeto parou de carregar. Escrever por fora so e
    # seguro se o que nao se conhece sobrevive — vale pra qualquer campo que o
    # Klipe ganhar depois, nao so pros que quebraram desta vez.
    if alvo.exists():
        try:
            atual = json.loads(alvo.read_text(encoding="utf-8"))
            for k, v in atual.items():
                cfg.setdefault(k, v)
        except json.JSONDecodeError:
            pass
    for k, v in {
        "captionStyle": "destaque", "captionFont": "Montserrat",
        "captionFontSize": 82, "captionColor": "#FFFFFF",
        "captionHighlightColor": "#8F1D18", "captionKaraoke": True,
        "captionMaxLines": 2, "captionWordGap": 12, "captionLineGap": 8,
        "captionX": 0, "captionY": 0,
    }.items():
        cfg.setdefault(k, v)
    alvo.write_text(json.dumps(cfg, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"\nconfig escrito: {alvo}")
    print(f"  {len(brolls)} trechos reais · {len(sfx)} sfx · {len(zooms)} zooms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
