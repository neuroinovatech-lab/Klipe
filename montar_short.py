#!/usr/bin/env python
"""montar_short.py — recorta um trecho e devolve um short 9:16, no MotionCore.

Antes isto era uma composicao React renderizada por navegador. A troca nao foi
reescrever aquela composicao em Skia: foi perceber que um short JA E um render
do Klipe, so que de um pedaco e noutro enquadramento. Entao o caminho e derivar
um projeto e mandar pro mesmo forge_render que faz o video inteiro — mesma
legenda, mesmo titulo, mesmo SFX, mesma correcao de cor.

Duas decisoes que valem explicar:

1. O trecho e CORTADO no disco antes de renderizar, e nao passado como janela
   de tempo para o render. Assim nada no forge_render precisa saber o que e um
   short: ele recebe um projeto que comeca no zero, como qualquer outro. Um
   parametro de janela atravessaria o caminho principal do render inteiro, que
   e a parte do sistema onde erro custa mais caro.

2. O enquadramento vertical corta pela CABECA, nao pelo centro. Video de fala
   tem a pessoa na metade de cima; recorte central em 16:9 -> 9:16 decapita.
   `faceX`/`faceY` vem da interface em porcentagem e viram o centro do recorte.

Uso:
    python montar_short.py <config.json> --inicio 12.5 --fim 45.0 \\
        --saida short_01.mp4 [--face-x 50 --face-y 35] \\
        [--gancho "TEXTO GRANDE"] [--topo "faixa inferior"]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from motioncore.ffbin import ffmpeg as _ffmpeg, ffprobe as _ffprobe

RAIZ = Path(__file__).resolve().parent
PUBLIC = RAIZ / "public"
FFMPEG = _ffmpeg()
FFPROBE = _ffprobe()

LARGURA, ALTURA = 1080, 1920


def _dimensoes(caminho: Path) -> tuple[int, int]:
    """Mede o video em vez de confiar no config: o config diz o tamanho da
    COMPOSICAO, que nem sempre e o do arquivo de origem."""
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(caminho)],
        capture_output=True, text=True)
    w, h = r.stdout.strip().split("x")[:2]
    return int(w), int(h)


def _recorta(origem: Path, destino: Path, inicio: float, dur: float,
             face_x: float, face_y: float) -> None:
    lw, lh = _dimensoes(origem)
    alvo = LARGURA / ALTURA          # 0.5625

    if abs(lw / lh - alvo) < 0.01:
        vf = f"scale={LARGURA}:{ALTURA}"
    else:
        # a maior janela 9:16 que cabe, deslocada para o rosto
        cw = min(lw, int(lh * alvo))
        ch = min(lh, int(cw / alvo))
        cx = max(0, min(lw - cw, int(lw * face_x / 100 - cw / 2)))
        cy = max(0, min(lh - ch, int(lh * face_y / 100 - ch / 2)))
        vf = f"crop={cw}:{ch}:{cx}:{cy},scale={LARGURA}:{ALTURA}"

    # -ss ANTES do -i busca por keyframe (rapido) e o -ss depois refina; os dois
    # juntos dao corte exato sem reler o arquivo desde o comeco.
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-ss", f"{max(0, inicio - 2):.3f}", "-i", str(origem),
           "-ss", f"{min(2, inicio):.3f}", "-t", f"{dur:.3f}",
           "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-c:a", "aac", "-b:a", "192k", str(destino)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not destino.exists():
        raise RuntimeError(f"corte falhou: {r.stderr[-400:]}")


def _na_janela(itens, ini: float, fim: float, campos=("startSec", "endSec")):
    """Mantem o que aparece na janela e move para o tempo do trecho.

    Corta nas bordas em vez de descartar: uma legenda que comeca 0,2 s antes do
    inicio do short e a primeira palavra que a pessoa ouve — jogar fora deixaria
    o short mudo de texto justo na abertura.
    """
    a, b = campos
    saida = []
    for it in itens or []:
        s, e = float(it.get(a, 0)), float(it.get(b, 0))
        if e <= ini or s >= fim:
            continue
        novo = dict(it)
        novo[a] = round(max(0.0, s - ini), 3)
        novo[b] = round(min(fim, e) - ini, 3)
        if novo[b] - novo[a] <= 0.05:
            continue
        # legenda tem palavras com tempo proprio
        if isinstance(it.get("words"), list):
            pal = []
            for w in it["words"]:
                ws, we = float(w.get("start", 0)), float(w.get("end", 0))
                if we <= ini or ws >= fim:
                    continue
                pal.append({**w, "start": round(max(0.0, ws - ini), 3),
                            "end": round(min(fim, we) - ini, 3)})
            novo["words"] = pal
        saida.append(novo)
    return saida


def montar(config: Path, inicio: float, fim: float, saida: str,
           face_x: float = 50, face_y: float = 35,
           gancho: str = "", topo: str = "", cor: str = "#FF6B00",
           crf: int = 18) -> Path:
    # absoluto desde o inicio: `config.parent` alimenta o relative_to(PUBLIC)
    # mais abaixo, e caminho relativo na entrada quebrava ali, longe daqui.
    config = Path(config).resolve()
    cfg = json.loads(config.read_text(encoding="utf-8"))
    dur = round(fim - inicio, 3)
    if dur <= 0:
        raise ValueError("fim tem que ser maior que inicio")

    origem = PUBLIC / str(cfg["videoSrc"]).replace("\\", "/")
    if not origem.exists():
        raise FileNotFoundError(origem)

    destino = config.parent / "shorts"
    destino.mkdir(parents=True, exist_ok=True)
    clipe = destino / f"{Path(saida).stem}_fonte.mp4"

    print(f"[Short] recortando {inicio:.2f}s..{fim:.2f}s ({dur:.1f}s) "
          f"com foco em {face_x:.0f}%,{face_y:.0f}%")
    _recorta(origem, clipe, inicio, dur, face_x, face_y)

    novo = dict(cfg)
    novo["videoSrc"] = str(clipe.relative_to(PUBLIC)).replace("\\", "/")
    novo["videoDuration"] = dur
    novo["width"], novo["height"] = LARGURA, ALTURA
    novo["captions"] = _na_janela(cfg.get("captions"), inicio, fim)
    novo["titles"] = _na_janela(cfg.get("titles"), inicio, fim)
    novo["zooms"] = _na_janela(cfg.get("zooms"), inicio, fim)
    novo["brolls"] = _na_janela(cfg.get("brolls"), inicio, fim)
    novo["shapes"] = _na_janela(cfg.get("shapes"), inicio, fim)
    novo["sfx"] = [{**s, "startSec": round(float(s["startSec"]) - inicio, 3)}
                   for s in (cfg.get("sfx") or [])
                   if inicio <= float(s.get("startSec", 0)) < fim]
    novo["musicTracks"] = _na_janela(cfg.get("musicTracks"), inicio, fim)

    # O gancho e o texto que segura os 2 primeiros segundos — e onde o short
    # ganha ou perde quem esta rolando o feed.
    if gancho:
        novo["titles"].insert(0, {"id": "short-gancho", "startSec": 0.0,
                                  "endSec": min(2.5, dur), "style": "hero",
                                  "text": gancho})
    if topo:
        novo["titles"].append({"id": "short-topo", "startSec": 0.0,
                               "endSec": dur, "style": "lower3rd", "text": topo})
    if cor:
        novo["barColor"] = cor

    cfg_out = destino / f"{Path(saida).stem}_config.json"
    cfg_out.write_text(json.dumps(novo, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[Short] {len(novo['captions'])} legendas, {len(novo['titles'])} titulos, "
          f"{len(novo['sfx'])} sfx, {len(novo['brolls'])} b-rolls no trecho")

    r = subprocess.run([sys.executable, "forge_render.py",
                        "--config", str(cfg_out), "--out", saida,
                        "--encoder", "auto"], cwd=RAIZ)
    if r.returncode != 0:
        raise RuntimeError(f"forge_render saiu {r.returncode}")

    return cfg_out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Recorta um short 9:16 de um projeto.")
    ap.add_argument("config")
    ap.add_argument("--inicio", type=float, required=True)
    ap.add_argument("--fim", type=float, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--face-x", type=float, default=50)
    ap.add_argument("--face-y", type=float, default=35)
    ap.add_argument("--gancho", default="")
    ap.add_argument("--topo", default="")
    ap.add_argument("--cor", default="#FF6B00")
    ap.add_argument("--crf", type=int, default=18)
    a = ap.parse_args()
    montar(Path(a.config), a.inicio, a.fim, a.saida,
           a.face_x, a.face_y, a.gancho, a.topo, a.cor, a.crf)
