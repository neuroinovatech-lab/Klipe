"""
forge_titles_native.py — Renderiza titles via ffmpeg drawtext nativo (sem motor de navegador).

Suporta os 5 estilos mais comuns: hero, lower3rd, ribbon, credit, panel.
Pra outros styles complexos (kinetic, contort, statBreakdown, notification etc),
cai pro motor de navegador (cache por title individual ja existe).

Cada title vira filtros drawtext+drawbox aplicados na video chain do composite.
Suporta fade in/out (0.3s default) via alpha expression.
"""
import re
from pathlib import Path

# Styles que sabemos renderizar em drawtext nativo
NATIVE_STYLES = {"hero", "lower3rd", "ribbon", "credit", "panel"}

# Font path (Windows fallback)
FONT_PATH = r"C\:/Windows/Fonts/MontserratBlack-DEMO.otf"  # se existir
FONT_FALLBACK = r"C\:/Windows/Fonts/arial.ttf"
FONT_BOLD = r"C\:/Windows/Fonts/arialbd.ttf"


def _font_for_style(style):
    """Retorna fontfile path pra ffmpeg, escapado pra Windows."""
    bold_styles = {"hero", "ribbon", "panel"}
    if style in bold_styles:
        return FONT_BOLD
    return FONT_FALLBACK


def _escape_drawtext(text):
    """Escape chars pra drawtext: : \ ' (mas não emoji)."""
    return (text
            .replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "’")  # smart quote
            .replace("%", "\\%")
            )


def can_render_native(titles):
    """Retorna True se TODOS os titles tem style suportado nativamente."""
    return all(t.get("style") in NATIVE_STYLES for t in titles)


def native_styles_only(titles):
    """Retorna True se PELO MENOS UM title tem style nativo."""
    return any(t.get("style") in NATIVE_STYLES for t in titles)


def build_title_filter(title, w, h):
    """Constroi chain ffmpeg pra um title.

    Retorna lista de filtros pra concatenar com video chain principal.
    Inclui fade in/out automatico (0.3s) via alpha expression.

    Layout (output W x H):
      hero:      bold 96px center
      lower3rd:  medium 60px y=h-220
      ribbon:    bar W x 110px com text inside, y=h-260
      credit:    italic 48px y=h-180
      panel:     N lines (separadas por |), 70px each, center vertical
    """
    style = title["style"]
    text = title["text"]
    start = float(title["startSec"])
    end = float(title["endSec"])
    dur = end - start
    fade = 0.3
    # Alpha expression: 0 fora da janela, 1 dentro com fade in/out
    # if(between(t,s,e), if(lt(t,s+fade), (t-s)/fade, if(gt(t,e-fade), (e-t)/fade, 1)), 0)
    alpha = (
        f"if(between(t\\,{start}\\,{end})\\,"
        f"if(lt(t\\,{start+fade})\\,(t-{start})/{fade}\\,"
        f"if(gt(t\\,{end-fade})\\,({end}-t)/{fade}\\,1))\\,0)"
    )
    enable = f"between(t\\,{start}\\,{end})"

    if style == "hero":
        # Big bold center
        # Word wrap by lines (split at | first, then auto-wrap)
        lines = text.split("|") if "|" in text else [text]
        font_size = 88 if w >= 1080 else 60
        line_h = int(font_size * 1.1)
        n = len(lines)
        total_h = line_h * n
        chain = []
        for i, line in enumerate(lines):
            esc = _escape_drawtext(line.strip())
            y = f"(h-{total_h})/2+{i * line_h}"
            chain.append(
                f"drawtext=fontfile='{FONT_BOLD}':text='{esc}':"
                f"fontcolor=white@1:fontsize={font_size}:"
                f"shadowcolor=black@0.7:shadowx=3:shadowy=4:"
                f"x=(w-text_w)/2:y={y}:"
                f"alpha='{alpha}':enable='{enable}'"
            )
        return chain

    elif style == "lower3rd":
        font_size = 56 if w >= 1080 else 42
        esc = _escape_drawtext(text)
        return [
            f"drawtext=fontfile='{FONT_BOLD}':text='{esc}':"
            f"fontcolor=white@1:fontsize={font_size}:"
            f"shadowcolor=black@0.7:shadowx=2:shadowy=3:"
            f"x=(w-text_w)/2:y=h-220:"
            f"alpha='{alpha}':enable='{enable}'"
        ]

    elif style == "ribbon":
        # Bar com cor de fundo + texto branco bold
        font_size = 52 if w >= 1080 else 40
        esc = _escape_drawtext(text)
        bar_color = "0xE8940A"  # laranja Klipe brand
        return [
            # iw/ih, e nao w/h: dentro do drawbox, `w` e `h` sao a largura e a
            # altura DA CAIXA, entao `w=w` e uma definicao circular e o ffmpeg
            # aborta com "Error when evaluating the expression 'w'". E `y=h-280`
            # media a partir da caixa (110), nao do video. No drawtext ao lado
            # w/h sao mesmo o quadro — por isso so esta linha muda.
            f"drawbox=x=0:y=ih-280:w=iw:h=110:color={bar_color}@0.92:t=fill:"
            f"enable='{enable}'",
            f"drawtext=fontfile='{FONT_BOLD}':text='{esc}':"
            f"fontcolor=white@1:fontsize={font_size}:"
            f"x=(w-text_w)/2:y=h-280+(110-text_h)/2-5:"
            f"alpha='{alpha}':enable='{enable}'"
        ]

    elif style == "credit":
        font_size = 42 if w >= 1080 else 32
        esc = _escape_drawtext(text)
        return [
            f"drawtext=fontfile='{FONT_FALLBACK}':text='{esc}':"
            f"fontcolor=white@1:fontsize={font_size}:"
            f"shadowcolor=black@0.6:shadowx=2:shadowy=2:"
            f"x=(w-text_w)/2:y=h-180:"
            f"alpha='{alpha}':enable='{enable}'"
        ]

    elif style == "panel":
        # Lista vertical centralizada — text usa | como separador de itens
        items = text.split("|")
        font_size = 64 if w >= 1080 else 48
        line_h = int(font_size * 1.4)
        total_h = line_h * len(items)
        chain = []
        for i, item in enumerate(items):
            esc = _escape_drawtext(item.strip())
            y = f"(h-{total_h})/2+{i * line_h}"
            chain.append(
                f"drawtext=fontfile='{FONT_BOLD}':text='{esc}':"
                f"fontcolor=white@1:fontsize={font_size}:"
                f"shadowcolor=black@0.7:shadowx=3:shadowy=4:"
                f"x=(w-text_w)/2:y={y}:"
                f"alpha='{alpha}':enable='{enable}'"
            )
        return chain

    # Fallback: single line lower-third style
    font_size = 48 if w >= 1080 else 36
    esc = _escape_drawtext(text)
    return [
        f"drawtext=fontfile='{FONT_FALLBACK}':text='{esc}':"
        f"fontcolor=white@1:fontsize={font_size}:"
        f"x=(w-text_w)/2:y=h-200:"
        f"alpha='{alpha}':enable='{enable}'"
    ]


def build_native_titles_chain(titles, w, h):
    """Concatena drawtext+drawbox de todos os titles numa chain unica.

    Retorna string com filtros separados por virgula pronta pra
    concatenar com a chain principal do video filter.
    """
    parts = []
    for t in titles:
        if t.get("style") not in NATIVE_STYLES:
            continue
        parts.extend(build_title_filter(t, w, h))
    return ",".join(parts) if parts else ""
