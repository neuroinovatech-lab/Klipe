#!/usr/bin/env python
"""
klipe_to_capcut.py — Converte titles do Klipe (edit_config.json) pra formato CapCut JSON.

Os styles do Klipe (hero, ribbon, lower3rd, panel, credit, flash, kinetic,
notification, statBreakdown) sao referencias a componentes React. Pra exportar
um formato STANDARD, expandimos cada style em parametros concretos:
  - text, font, font_size, color
  - position (x, y) absoluta no frame
  - animations (fade in/out, slide, etc)
  - background (cor de bar pro ribbon, etc)

Output: draft_content.json estilo CapCut Desktop com:
  - tracks: text segments com timing
  - materials.texts: dados completos de cada title

USO:
    python klipe_to_capcut.py <project_slug> [output.json]

EXEMPLO:
    python klipe_to_capcut.py abuso-mulheres-autistas
    → public/projects/abuso-mulheres-autistas/draft_content.json
"""
import json, sys, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ─────────────────────────────────────────────────────────────────────────
# STYLE DICTIONARY — expande cada Klipe style em parametros concretos.
# Mapa baseado em src/VideoEditor.tsx + reference_titulos_virais.md.
# ─────────────────────────────────────────────────────────────────────────
def expand_klipe_style(title):
    """Retorna dict com parametros completos de renderizacao."""
    style = title.get("style", "lower3rd")
    text = title.get("text", "")
    posY = title.get("posY")
    posX = title.get("posX")
    fontSize = title.get("fontSize")  # override absoluto
    color = title.get("color", "#FFFFFF")
    base = {
        "text": text,
        "font_path": "Montserrat-Bold.ttf",
        "text_color": _hex_to_rgba(color),
        "background": None,
        "transform_x": posX or 0,
        "transform_y": posY or 0,
        "rotation": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "alignment": "center",
        "shadow": True,
        "shadow_offset_x": 3,
        "shadow_offset_y": 4,
        "shadow_alpha": 0.7,
        "animations": [
            {"id": "in", "name": "fade_in", "duration_us": 300_000},
            {"id": "out", "name": "fade_out", "duration_us": 300_000},
        ],
    }

    if style == "hero":
        # Big bold center — split por | em multiplas linhas
        base.update({
            "font_size": fontSize or 96,
            "font_path": "Montserrat-Black.ttf",
            "transform_y": posY or 0,
            "alignment": "center",
            "lines": text.split("|") if "|" in text else [text],
        })
    elif style == "lower3rd":
        base.update({
            "font_size": fontSize or 56,
            "font_path": "Montserrat-Bold.ttf",
            "transform_y": posY or -380,  # bottom area
            "alignment": "center",
        })
    elif style == "ribbon":
        base.update({
            "font_size": fontSize or 52,
            "font_path": "Montserrat-Bold.ttf",
            "transform_y": posY or -440,
            "background": {
                "color": "#E8940A",
                "alpha": 0.92,
                "padding_x": 40,
                "padding_y": 20,
                "full_width": True,
            },
            "shadow": False,
        })
    elif style == "panel":
        # Multi-line list (text uses | separator)
        base.update({
            "font_size": fontSize or 64,
            "font_path": "Montserrat-Bold.ttf",
            "lines": text.split("|"),
            "alignment": "center",
            "line_spacing": 1.4,
            "transform_y": posY or 0,
        })
    elif style == "credit":
        base.update({
            "font_size": fontSize or 42,
            "font_path": "Montserrat-Italic.ttf",
            "transform_y": posY or -380,
            "alignment": "center",
            "shadow": True,
            "shadow_alpha": 0.6,
        })
    elif style == "flash":
        base.update({
            "font_size": fontSize or 140,
            "font_path": "Montserrat-Black.ttf",
            "transform_y": posY or 0,
            "alignment": "center",
            "animations": [
                {"id": "in", "name": "scale_pop_in", "duration_us": 200_000},
                {"id": "out", "name": "fade_out", "duration_us": 200_000},
            ],
            "uppercase": True,
        })
    elif style == "kinetic":
        # Word-by-word reveal
        words = text.split()
        base.update({
            "font_size": fontSize or 88,
            "font_path": "Montserrat-Black.ttf",
            "uppercase": True,
            "animations": [
                {"id": "kinetic", "name": "word_reveal", "duration_us": int(150_000 * len(words))},
            ],
            "words": words,
        })
    elif style == "notification":
        base.update({
            "font_size": fontSize or 48,
            "font_path": "SF-Pro-Display-Medium.ttf",
            "transform_y": posY or 350,  # top area
            "background": {
                "color": "#1E1E1E",
                "alpha": 0.92,
                "border_radius": 28,
                "padding_x": 32,
                "padding_y": 24,
                "full_width": False,
            },
            "shadow": True,
            "shadow_offset_x": 0,
            "shadow_offset_y": 6,
            "shadow_alpha": 0.4,
            "animations": [
                {"id": "in", "name": "slide_down", "duration_us": 400_000},
                {"id": "out", "name": "slide_up", "duration_us": 300_000},
            ],
        })
    elif style == "statBreakdown":
        # text format: "%|description"
        parts = text.split("|", 1)
        base.update({
            "font_size": fontSize or 200 if len(parts) == 2 else 80,
            "font_path": "Montserrat-Black.ttf",
            "lines": parts if len(parts) == 2 else [text],
            "alignment": "center",
            "stat_layout": True,
            "highlight_color": "#E8940A",
        })
    else:
        # Fallback: lower3rd basico
        base.update({
            "font_size": fontSize or 48,
            "transform_y": posY or -350,
        })
    return base


def _hex_to_rgba(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
        return [r, g, b, 1.0]
    return [1.0, 1.0, 1.0, 1.0]


def build_capcut_json(cfg):
    """Converte Klipe edit_config.json em estrutura draft_content.json (CapCut)."""
    fps = cfg.get("fps", 30)
    duration_us = int(cfg.get("videoDuration", 0) * 1_000_000)
    width = cfg.get("width", 1920)
    height = cfg.get("height", 1080)

    # Material list (text)
    text_materials = []
    text_segments = []
    for i, t in enumerate(cfg.get("titles", [])):
        material_id = f"txt_{uuid.uuid4().hex[:12]}"
        expanded = expand_klipe_style(t)
        text_materials.append({
            "id": material_id,
            "type": "text",
            **expanded,
        })

        seg_id = f"seg_{uuid.uuid4().hex[:12]}"
        start_us = int(t["startSec"] * 1_000_000)
        end_us = int(t["endSec"] * 1_000_000)
        text_segments.append({
            "id": seg_id,
            "material_id": material_id,
            "target_start_time": start_us,
            "target_duration": end_us - start_us,
            "source_start_time": 0,
            "render_index": 14000 + i,  # CapCut convention: text high render index
        })

    return {
        "version": "klipe-export-1.0",
        "fps": fps,
        "duration": duration_us,
        "canvas_config": {
            "width": width,
            "height": height,
            "ratio": cfg.get("aspectRatio", "16:9"),
        },
        "tracks": [{
            "id": f"track_{uuid.uuid4().hex[:12]}",
            "type": "text",
            "segments": text_segments,
        }],
        "materials": {
            "texts": text_materials,
        },
        "_klipe_meta": {
            "source": "Klipe",
            "exported_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
            "title_count": len(text_materials),
        },
    }


def main(slug, out_path=None):
    cfg_path = ROOT / "public" / "projects" / slug / "edit_config.json"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} nao existe")
        sys.exit(1)
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    capcut = build_capcut_json(cfg)

    out_path = Path(out_path) if out_path else (cfg_path.parent / "draft_content.json")
    out_path.write_text(json.dumps(capcut, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK exportado: {out_path}")
    print(f"  {len(cfg.get('titles', []))} titles convertidos")
    print(f"  {capcut['canvas_config']['width']}x{capcut['canvas_config']['height']} @ {capcut['fps']}fps")
    print(f"  duration: {capcut['duration']/1_000_000:.1f}s")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
