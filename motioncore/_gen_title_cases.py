"""
Monta os casos de paridade dos 8 titulos mais usados, com textos reais.

Pega de cada estilo o titulo mais usado no edit_config de verdade — texto com
acento, com `|`, do tamanho que aparece na pratica. Inventar texto curto e
bonitinho esconde justamente os casos que quebram (quebra de linha, acento,
multi-linha).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAIDA = Path(__file__).parent / "_parity_titulos.json"
ESTILOS = ["lower3rd", "hero", "flash", "kinetic", "panel", "ribbon", "counter", "quote"]

cfg = json.loads((ROOT / "public" / "edit_config.json").read_text(encoding="utf-8"))
por_estilo: dict[str, list] = {}
for t in cfg.get("titles") or []:
    por_estilo.setdefault(t.get("style"), []).append(t)

# alguns estilos nao aparecem neste projeto — texto de reserva no formato certo
RESERVA = {
    "counter": "87% das mulheres autistas",
    "panel": "O COLAPSO|Exaustão física|Exaustão emocional|Exaustão mental",
    "ribbon": "Atrasar o diagnóstico traz consequências",
}

casos = []
for estilo in ESTILOS:
    cands = por_estilo.get(estilo) or []
    if cands:
        # o de texto mais longo: exercita quebra de linha e multi-linha
        t = max(cands, key=lambda x: len(x.get("text") or ""))
        texto = t["text"]
    else:
        texto = RESERVA.get(estilo, f"Teste de {estilo}")
    casos.append({
        "name": estilo,
        "frames": [0, 2, 5, 9, 14, 22, 40, 90, 143],
        "title": {"startSec": 0, "endSec": 5, "style": estilo, "text": texto},
    })

spec = {"width": cfg.get("width", 1080), "height": cfg.get("height", 1920),
        "fps": cfg.get("fps", 30), "frames": [0], "cases": casos}
SAIDA.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")

print(f"{len(casos)} casos em {SAIDA.name}")
for c in casos:
    print(f"  {c['name']:<12} {c['title']['text'][:64]!r}")
