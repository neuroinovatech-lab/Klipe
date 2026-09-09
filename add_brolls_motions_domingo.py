#!/usr/bin/env python
"""
Atualiza edit_config.json do projeto domingo-com-ritalina adicionando:
  - Brolls reais (de public/projects/domingo-com-ritalina/brolls/)
  - Motion-brolls usando styles existentes (notification, statBreakdown)
  - Mantem cuts e captions atuais

Roda DEPOIS de apply_edit_plan_domingo.py + download_brolls.py.
"""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJ = ROOT / "public" / "projects" / "domingo-com-ritalina"
CFG_PATH = PROJ / "edit_config.json"
BROLLS_DIR = PROJ / "brolls"

# Mapeia momento (timeline_sec_start, sec_end) → broll file + label
# Times referem ao timeline cortado (302s total)
BROLL_PLACEMENTS = [
    # (tl_start, tl_end, file_name, label)
    (3.0,    8.0,    "broll_lonely_thinking.mp4",   "Mulher pensativa"),
    (12.0,   17.0,   "broll_empty_party.mp4",       "Festa vazia"),
    (19.0,   25.0,   "broll_baby_shower.mp4",       "Bebê chá"),
    (40.0,   46.0,   "broll_pregnant_belly.mp4",    "Gestação"),
    (75.0,   81.0,   "broll_sad_face_hands.mp4",    "Triste"),
    (105.0,  111.0,  "broll_wall_shadow.mp4",       "Barreiras"),
    (135.0,  141.0,  "broll_anxious_night.mp4",     "Ansiedade noite"),
    (192.0,  198.0,  "broll_typing_laptop.mp4",     "Digitando"),
    (235.0,  240.0,  "broll_couple_celebrate.mp4",  "Casal celebra"),
    (270.0,  275.0,  "broll_woman_hug_support.mp4", "Apoio"),
    (294.0,  300.0,  "broll_confident_sunset.mp4",  "Vitoriosa"),
]

# Substitui titulos por motion-brolls onde adequado
# (id_match_or_text_match, novo_style, novo_text_se_mudar)
TITLE_REPLACEMENTS = [
    # title atual "Às vezes eu só consigo falar escrevendo." → notification (phone msg)
    ("Às vezes eu só consigo falar escrevendo.", "notification", "💬 Amor, preciso conversar..."),
    # title atual "Ansiedade · Insônia" → statBreakdown
    ("Ansiedade · Insônia", "statBreakdown", "Crise|de ansiedade"),
]

def main():
    cfg = json.load(open(CFG_PATH, encoding="utf-8"))
    print(f"Carregado: {len(cfg.get('titles', []))} titles, {len(cfg.get('brolls', []))} brolls iniciais")

    # 1. Substituir titulos -> motion-brolls
    for i, t in enumerate(cfg.get("titles", [])):
        for match_text, new_style, new_text in TITLE_REPLACEMENTS:
            if t.get("text") == match_text:
                old_style = t["style"]
                t["style"] = new_style
                if new_text:
                    t["text"] = new_text
                print(f"  Title[{i}] '{match_text[:40]}...' style: {old_style} → {new_style}")

    # 2. Adicionar brolls
    brolls = []
    for i, (start, end, fname, label) in enumerate(BROLL_PLACEMENTS):
        path = BROLLS_DIR / fname
        if not path.exists():
            print(f"  WARN: broll missing: {fname}")
            continue
        brolls.append({
            "id": f"br{i+1:02d}",
            "startSec": round(start, 2),
            "endSec": round(end, 2),
            "src": f"projects/domingo-com-ritalina/brolls/{fname}",
            "label": label,
        })
    cfg["brolls"] = brolls
    print(f"  Brolls adicionados: {len(brolls)}/{len(BROLL_PLACEMENTS)}")

    # Save
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nOK: {CFG_PATH}")
    print(f"  Total: {len(cfg['titles'])} titles, {len(cfg['brolls'])} brolls, {len(cfg.get('zooms',[]))} zooms")

if __name__ == "__main__":
    main()
