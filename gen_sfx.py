#!/usr/bin/env python3
"""
gen_sfx.py — Gera sfx[] com REGRA DE PRIORIDADE (sem som dobrado).

Regra: pra cada momento, escolhe O MAIS IMPORTANTE som — não acumula.
Categorias com min gap por GRUPO (não por arquivo):
  - WHOOSH (qualquer arquivo): max 1 por 0.8s
  - CLICK: max 1 por 0.55s
  - MARKER: max 1 por 0.65s
  - IMPACT: max 1 por 4s

Quando 2 sons do MESMO grupo coincidem, vence o de maior prioridade
(ex: zoom_in_start vence sobre fast_woosh).
"""
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
CFG_PATH = PUBLIC / "edit_config.json"
PROJECT = "abuso-mulheres-autistas"
PROJ_CFG = PUBLIC / "projects" / PROJECT / "edit_config.json"

# ============= SFX DICT =============
SFX = {
    "slow_woosh":      ("sfx/whooshes/Slow Woosh - SoundConteúdo.mp3",                 0.40, 0.85),
    "swish_whoosh":    ("sfx/whooshes/Swish Whoosh Large.mp3",                         0.55, 0.78),
    "cinematic_woosh": ("sfx/whooshes/Cinematic Piano Whoosh  - SoundConteúdo.wav",    0.40, 1.20),
    "fast_woosh":      ("sfx/whooshes/Fast Woosh - SoundConteúdo.mp3",                 0.40, 0.87),
    "mouse_click":     ("sfx/pop_click/Mouse Click - SoundConteúdo.wav",               0.90, 0.40),
    "marker":          ("sfx/pop_click/Marker - SoundConteúdo.wav",                    0.55, 0.50),
    "zoom_in_start":   ("sfx/transition_sweep/Zoom In.mp3",                            1.995262, 0.29),
    "zoom_in_end":     ("sfx/foley/scrooling_2.MP3",                                   0.70, 0.23),
    "bass_drop":       ("sfx/bass_drop/Deep Bass Faded Long (197098).mp3",             0.45, 1.20),
    "boom_impact":     ("sfx/transition_impacts/Boom - Giant Impact.mp3",              0.55, 2.50),
    "boom_soft":       ("sfx/transition_impacts/Boom - Giant Impact.mp3",              0.32, 2.50),
    "cinematic_hit":   ("sfx/transition_impacts/CinematicHITS 2 - SoundConteúdo.wav",  0.32, 2.80),
    "grand_hit":       ("sfx/transition_impacts/Grand Hit - Desconhecido.wav",         0.38, 3.00),
    "reveal":          ("sfx/reverse/Reveal - SoundConteúdo.wav",                      0.70, 2.10),
}

GROUP_OF = {
    "slow_woosh": "WHOOSH", "swish_whoosh": "WHOOSH",
    "cinematic_woosh": "WHOOSH", "fast_woosh": "WHOOSH",
    "zoom_in_start": "WHOOSH",
    "zoom_in_end": "WHOOSH",
    "mouse_click": "CLICK",
    "marker": "MARKER",
    "bass_drop": "IMPACT", "boom_impact": "IMPACT", "boom_soft": "IMPACT",
    "cinematic_hit": "IMPACT", "grand_hit": "IMPACT",
    "reveal": "IMPACT",
}

GROUP_MIN_GAP = {
    "WHOOSH": 0.80,
    "CLICK":  0.55,
    "MARKER": 0.65,
    "IMPACT": 4.00,
}

PRIORITY = {
    "zoom_in_start":   100,
    "zoom_in_end":     100,
    "bass_drop":       90,
    "boom_impact":     90,
    "boom_soft":       80,
    "cinematic_hit":   90,
    "grand_hit":       90,
    "reveal":          85,
    "swish_whoosh":    60,
    "slow_woosh":      55,
    "cinematic_woosh": 55,
    "marker":          70,
    "mouse_click":     65,
    "fast_woosh":      40,
}

WHOOSH_CYCLE = ["fast_woosh", "swish_whoosh"]  # apenas 2 sons rotativos pros titles convencionais

# Whoosh FIXO por style (substitui rotativo) — cada estilo tem seu som proprio
STYLE_WHOOSH = {
    "lower3rd":     "slow_woosh",       # discreto, secundario
    "panel":        "slow_woosh",       # discreto, listas
    "credit":       "slow_woosh",       # apresentacao
    "quote":        "swish_whoosh",     # dramatic citacao
    "terminal":     "cinematic_woosh",  # texto tecnico
    "notification": "swish_whoosh",     # banner alerta
    "hero":         "cinematic_woosh",  # impacto opening
    "ribbon":       "swish_whoosh",     # faixa atravessando
    "kinetic":      "swish_whoosh",     # palavra forte
    "flash":        "swish_whoosh",     # flash 1-2 palavras
    "socialCta":    None,               # nao tem whoosh — usa Reveal
}


def make_sfx(start, sfx_key, vol_override=None):
    src, vol, dur = SFX[sfx_key]
    if vol_override is not None:
        vol = vol_override
    return {
        "startSec": round(start, 3),
        "endSec": round(start + dur, 3),
        "src": src,
        "volume": vol,
        "_key": sfx_key,
    }


def add(sfx_list, start, sfx_key, vol_override=None):
    """Adiciona com regra de prioridade. Retorna True se foi adicionado."""
    group = GROUP_OF[sfx_key]
    min_gap = GROUP_MIN_GAP[group]
    new_pri = PRIORITY.get(sfx_key, 50)

    conflicts = []
    for i, existing in enumerate(sfx_list):
        ex_key = existing.get("_key")
        if ex_key not in GROUP_OF or GROUP_OF[ex_key] != group:
            continue
        if abs(start - existing["startSec"]) < min_gap:
            conflicts.append((i, existing, PRIORITY.get(ex_key, 50)))

    if conflicts:
        max_existing = max(c[2] for c in conflicts)
        if new_pri > max_existing:
            for idx, _, _ in sorted(conflicts, reverse=True):
                sfx_list.pop(idx)
            sfx_list.append(make_sfx(start, sfx_key, vol_override))
            return True
        else:
            return False
    else:
        sfx_list.append(make_sfx(start, sfx_key, vol_override))
        return True


def main():
    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    titles = sorted(cfg["titles"], key=lambda t: t["startSec"])
    zooms = sorted(cfg.get("zooms", []), key=lambda z: z["startSec"])
    brolls = sorted(cfg.get("brolls", []), key=lambda b: b["startSec"])

    sfx_out = []

    # === PASS 1: ZOOMS HARDIN (sempre vence) ===
    for z in zooms:
        d = z.get("direction", "in")
        intensity = z.get("intensity", 1.10)
        s = z["startSec"]
        e = z["endSec"]
        if d == "hardIn" and intensity >= 1.20:
            add(sfx_out, s, "zoom_in_start")
            add(sfx_out, e - 0.23, "zoom_in_end")
        elif d == "hardOut":
            add(sfx_out, s, "zoom_in_start", vol_override=1.0)

    # === PASS 2: IMPACTS NARRATIVOS ===
    impacts = [
        (127.0, "boom_soft"),
        (197.0, "cinematic_hit"),
        (302.5, "grand_hit"),
        (396.5, "grand_hit"),
        (480.5, "bass_drop"),
        (597.0, "grand_hit"),
        (749.0, "boom_soft"),
        (773.5, "boom_impact"),
        (809.0, "reveal"),
    ]
    for s, key in impacts:
        add(sfx_out, s, key)

    # === PASS 3: MOTION-BROLLS CUSTOMS ===
    motion_styles = {"alertaAbertura", "chatBubble", "naoPulsa", "flowDiagram",
                     "compareVisual", "microAcoes", "mentalChaos",
                     "documentLei", "sensoryOverload", "uiMockup"}

    for t in titles:
        s = t["startSec"]
        style = t["style"]
        text = t["text"]
        if style not in motion_styles:
            continue

        if style == "alertaAbertura":
            add(sfx_out, s, "bass_drop")
            add(sfx_out, s + 0.7, "marker")

        elif style == "chatBubble":
            phrases = [p for p in text.split("|") if p.strip()]
            for i in range(len(phrases)):
                add(sfx_out, s + 0.1 + i * 0.65, "mouse_click", vol_override=0.85)

        elif style == "mentalChaos":
            add(sfx_out, s, "cinematic_hit")
            words = [w for w in text.split("|") if w.strip()][:6]
            for i in range(min(3, len(words))):
                add(sfx_out, s + 1.0 + i * 0.7, "mouse_click", vol_override=0.6)

        elif style == "compareVisual":
            add(sfx_out, s + 0.2, "marker")
            add(sfx_out, s + 0.85, "marker")

        elif style == "sensoryOverload":
            add(sfx_out, s, "bass_drop")
            words = [w for w in text.split("|") if w.strip()][:6]
            for i in range(min(3, len(words))):
                add(sfx_out, s + 0.6 + i * 0.65, "mouse_click", vol_override=0.7)

        elif style == "microAcoes":
            items = [w for w in text.split("|") if w.strip()][:5]
            for i in range(len(items)):
                add(sfx_out, s + 0.15 + i * 0.65, "mouse_click")

        elif style == "naoPulsa":
            add(sfx_out, s, "boom_impact", vol_override=0.55)

        elif style == "uiMockup":
            items = [w for w in text.split("|") if w.strip()][1:]
            for i in range(min(len(items), 4)):
                add(sfx_out, s + 0.65 + i * 0.65, "mouse_click", vol_override=0.85)

        elif style == "flowDiagram":
            steps = [w for w in text.split("|") if w.strip()][:5]
            for i in range(len(steps)):
                add(sfx_out, s + 0.1 + i * 0.7, "marker")

        elif style == "documentLei":
            add(sfx_out, s, "slow_woosh")
            add(sfx_out, s + 1.0, "reveal")

    # === PASS 4: TITLES whoosh ROTATIVO (Slow → Swish → Cinematic → repeat) ===
    # Regra original: cada title tem 1 whoosh, NUNCA repete o mesmo em 2 consecutivos
    whoosh_idx = 0
    mouse_count = sum(1 for s in sfx_out if s.get("_key") == "mouse_click")
    marker_count = sum(1 for s in sfx_out if s.get("_key") == "marker")

    for t in titles:
        s = t["startSec"]
        style = t["style"]
        if style in motion_styles:
            continue
        woosh_key = WHOOSH_CYCLE[whoosh_idx % len(WHOOSH_CYCLE)]
        added = add(sfx_out, s, woosh_key)
        if added:
            whoosh_idx += 1
        # Mouse Click sem limite global pra titles "destaque"
        if style in ("kinetic", "flash", "ribbon", "quote"):
            if add(sfx_out, s + 0.05, "mouse_click"):
                mouse_count += 1
        if style == "hero" and marker_count < 6:
            if add(sfx_out, s, "marker"):
                marker_count += 1

    # === PASS 5: BROLLS — Fast Woosh start (skip se conflito) ===
    for b in brolls:
        add(sfx_out, b["startSec"], "fast_woosh")
        add(sfx_out, b["endSec"] - 0.5, "fast_woosh")

    # === PASS 6: ZOOM SOFT (in/out) — Fast Woosh start ===
    for z in zooms:
        d = z.get("direction", "in")
        if d in ("in", "out") and z.get("intensity", 1.10) < 1.20:
            add(sfx_out, z["startSec"], "fast_woosh")

    # === SORT + ID + LIMPA _key ===
    sfx_out.sort(key=lambda s: s["startSec"])
    final = []
    for i, s in enumerate(sfx_out):
        s.pop("_key", None)
        s["id"] = f"sfx{i+1:03d}"
        final.append(s)

    cfg["sfx"] = final
    payload = json.dumps(cfg, ensure_ascii=False, indent=2)
    CFG_PATH.write_text(payload, encoding="utf-8")
    PROJ_CFG.write_text(payload, encoding="utf-8")

    src_counter = Counter(s["src"].split("/")[-1] for s in final)
    print(f"[GenSFX] Total: {len(final)} SFX entries")
    for src, n in sorted(src_counter.items(), key=lambda x: -x[1]):
        print(f"  {n:>3}x {src}")
    mouse = sum(1 for s in final if 'Mouse Click' in s['src'])
    marker = sum(1 for s in final if 'Marker' in s['src'])
    print(f"  Mouse Clicks: {mouse} | Markers: {marker}")


if __name__ == "__main__":
    main()
