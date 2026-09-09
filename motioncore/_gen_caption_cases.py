"""
Monta os casos de paridade das LEGENDAS a partir do edit_config real.

Usa as legendas do projeto de verdade (com acento, pontuacao, tamanho de frase
variado) em vez de texto inventado — e o material que o render vai encontrar.
Os frames escolhidos caem em cima dos momentos que costumam quebrar: entrada do
grupo, cada passo do karaoke, troca de grupo e o meio parado.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "output" / "_bench3" / "edit_config.json"
SAIDA = Path(__file__).parent / "_parity_captions.json"

cfg = json.loads(CFG.read_text(encoding="utf-8"))
fps = cfg.get("fps", 30)
wpg = min(4, max(2, int(cfg.get("captionMaxLines", 2)) + 1))

base_props = {
    "titles": [], "showProgressBar": False, "shapes": [], "playbackRate": 1.0,
    "showCaptions": True,
    "captionBg": cfg.get("captionBg", True),
    "captionFontSize": cfg.get("captionFontSize", 100),
    "captionStyle": cfg.get("captionStyle", "words"),
    "captionFont": cfg.get("captionFont", "Montserrat"),
    "captionX": cfg.get("captionX", 0),
    "captionY": cfg.get("captionY", 0),
    "captionColor": cfg.get("captionColor", "#FFFFFF"),
    "captionHighlightColor": cfg.get("captionHighlightColor", "#E8940A"),
    "captionKaraoke": cfg.get("captionKaraoke", True),
    "captionMaxLines": cfg.get("captionMaxLines", 2),
    "captionContrast": cfg.get("captionContrast", 55),
    "captionWordGap": cfg.get("captionWordGap", 14),
    "captionLineGap": cfg.get("captionLineGap", 6),
}

# escolhe legendas de tamanhos diferentes: curta, media, longa (quebra em 2 linhas)
todas = [c for c in cfg["captions"] if (c.get("text") or "").strip()]
por_tamanho = sorted(todas, key=lambda c: len(c["text"].split()))
escolhidas = [por_tamanho[0], por_tamanho[len(por_tamanho) // 2], por_tamanho[-1]]

casos = []
for n, cap in enumerate(escolhidas):
    palavras = cap["text"].split()
    dur = float(cap["endSec"]) - float(cap["startSec"])
    total = math.ceil(len(palavras) / wpg)
    # frames relativos ao inicio da legenda, ancorada em t=0
    frames = set()
    for gi in range(total):
        d_grupo = dur / total
        n_pal = len(palavras[gi * wpg:(gi + 1) * wpg])
        base = gi * d_grupo
        frames.add(round(base * fps))                       # troca de grupo
        frames.add(round((base + 0.07) * fps))              # meio do quique
        frames.add(round((base + 0.20) * fps))              # grupo ja assentado
        for k in range(n_pal):                              # cada passo do karaoke
            frames.add(round((base + (k + 0.5) * d_grupo / n_pal) * fps))
    frames = sorted(f for f in frames if 0 <= f < round(dur * fps))

    cap0 = {**cap, "startSec": 0.0, "endSec": round(dur, 3)}
    casos.append({
        "name": f"legenda_{n}_{len(palavras)}palavras",
        "frames": frames[:14],
        "props": {**base_props, "captions": [cap0]},
    })

spec = {"width": cfg.get("width", 1080), "height": cfg.get("height", 1920),
        "fps": fps, "frames": [0], "cases": casos}
SAIDA.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")

print(f"{len(casos)} casos em {SAIDA.name}")
for c in casos:
    print(f"  {c['name']:<28} {len(c['frames'])} frames  "
          f"texto={c['props']['captions'][0]['text'][:52]!r}")
