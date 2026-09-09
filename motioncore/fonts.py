"""
fonts.py — registro de fontes espelhando o bloco @font-face do template antigo.

Duas responsabilidades:

1. **Casar peso/estilo como o navegador casa.** O estilo `stackedReveal` pede
   `fontWeight: 900` pra primeira linha, mas o @font-face so declara Montserrat
   600/700/800. O Chrome NAO sintetiza negrito nesse caso — ele cai pro 800 pelo
   algoritmo de matching do CSS Fonts 4. Se a gente ignorasse isso e sintetizasse,
   o texto sairia mais gordo que o do motor de navegador e a paridade quebrava logo na
   primeira linha.

2. **Registrar tudo num TypefaceFontProvider** pro skparagraph moldar o texto
   (kerning GPOS). Medir com `Font.measureText` seria 4px mais largo em
   "SEM PARAR" — o Chrome aplica kerning, entao a gente tambem aplica.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import skia
from skia import textlayout as tl

FONTS_DIR = Path(__file__).resolve().parent.parent / "public" / "fonts"

# Espelho literal de `fontFaces` em o template antigo (linhas 28-47).
# (familia, peso, italico, arquivo)
FACES: list[tuple[str, int, bool, str]] = [
    ("Gilroy", 800, False, "Gilroy-ExtraBold.ttf"),
    ("Gilroy", 700, False, "Gilroy-Bold.ttf"),
    ("Gotham", 900, False, "Gotham-Black.otf"),
    ("Gotham", 700, False, "Gotham-Bold.otf"),
    ("Gotham", 500, False, "Gotham-Medium.otf"),
    ("PlayfairDisplay", 700, True, "playfair-display.bold-italic.ttf"),
    ("PlayfairDisplay", 400, True, "playfair-display.italic.ttf"),
    ("PlayfairDisplay", 700, False, "playfair-display.bold.ttf"),
    ("BebasNeue", 400, False, "BebasNeue-Regular.otf"),
    ("Montserrat", 800, False, "Montserrat-ExtraBold.ttf"),
    ("Montserrat", 700, False, "Montserrat-Bold.ttf"),
    ("Montserrat", 600, False, "Montserrat-SemiBold.ttf"),
    ("CormorantGaramond", 700, False, "CormorantGaramond-Bold.ttf"),
    ("CormorantGaramond", 400, True, "CormorantGaramond-Italic.ttf"),
    ("Poppins", 800, False, "Poppins-ExtraBold.ttf"),
    ("Poppins", 700, False, "Poppins-Bold.ttf"),
    ("Noka", 900, False, "Noka_Black.otf"),
    ("Steelhead", 400, False, "Steelhead.otf"),
]

# Fontes DO SISTEMA que o Chrome usa quando a familia declarada nao casa com
# nenhum @font-face.
#
# Isso nao e refinamento: o estilo `quote` pede `'Playfair Display'` COM ESPACO,
# e o @font-face registra `'PlayfairDisplay'` SEM espaco. Os nomes nao batem, o
# Chrome pula pro proximo da lista e renderiza em **Georgia**. Ou seja: o Klipe
# entrega `quote` em Georgia hoje, nao em Playfair. Reproduzir isso e o que da
# paridade; "consertar" pra Playfair mudaria o visual de tudo que ja foi feito.
# (Mesmo caso em compound / compound3 / compound4.)
SYSTEM_FACES: list[tuple[str, int, bool, str]] = [
    ("Georgia", 400, False, r"C:\Windows\Fonts\georgia.ttf"),
    ("Georgia", 700, False, r"C:\Windows\Fonts\georgiab.ttf"),
    ("Georgia", 400, True, r"C:\Windows\Fonts\georgiai.ttf"),
    ("Georgia", 700, True, r"C:\Windows\Fonts\georgiaz.ttf"),
    ("Times New Roman", 400, False, r"C:\Windows\Fonts\times.ttf"),
    ("Times New Roman", 700, False, r"C:\Windows\Fonts\timesbd.ttf"),
    ("Times New Roman", 400, True, r"C:\Windows\Fonts\timesi.ttf"),
    ("Times New Roman", 700, True, r"C:\Windows\Fonts\timesbi.ttf"),
    # O `sensoryStorm` pede `'Bebas Neue', 'Impact', sans-serif`. "Bebas Neue"
    # COM espaco nao casa com o @font-face 'BebasNeue', entao quem desenha e a
    # Impact — que e CONDENSADA. Sem ela registrada aqui a palavra caía na
    # Montserrat e ficava 46% mais larga ("PERTENCER" a 86px: 550 px contra
    # 377 px), vazando a lateral do quadro e sendo cortada no render.
    ("Impact", 400, False, r"C:\Windows\Fonts\impact.ttf"),
    # genericas: quando a lista de familias acaba sem casar nada, e uma destas
    # que o Chrome usa no Windows
    ("Arial", 400, False, r"C:\Windows\Fonts\arial.ttf"),
    ("Arial", 700, False, r"C:\Windows\Fonts\arialbd.ttf"),
    ("Arial", 400, True, r"C:\Windows\Fonts\ariali.ttf"),
    ("Arial", 700, True, r"C:\Windows\Fonts\arialbi.ttf"),
    ("Consolas", 400, False, r"C:\Windows\Fonts\consola.ttf"),
    ("Consolas", 700, False, r"C:\Windows\Fonts\consolab.ttf"),
    ("Courier New", 400, False, r"C:\Windows\Fonts\cour.ttf"),
    ("Courier New", 700, False, r"C:\Windows\Fonts\courbd.ttf"),
    ("Comic Sans MS", 400, False, r"C:\Windows\Fonts\comic.ttf"),
    ("Comic Sans MS", 700, False, r"C:\Windows\Fonts\comicbd.ttf"),
    ("Segoe UI", 400, False, r"C:\Windows\Fonts\segoeui.ttf"),
    ("Segoe UI", 700, False, r"C:\Windows\Fonts\segoeuib.ttf"),
]

# Familias genericas do CSS -> a fonte que o Chrome escolhe no Windows.
#
# `sans-serif` NAO e Montserrat: no Windows o Chrome usa **Arial**. Enquanto
# isso apontava pra Montserrat, qualquer estilo cuja lista acabasse em
# `sans-serif` sem casar nada era desenhado numa fonte mais larga que a do
# preview — o mesmo tipo de erro que cortou a palavra no `sensoryStorm`.
GENERIC_FALLBACK = {
    "sans-serif": "Arial",
    "serif": "Times New Roman",
    "monospace": "Consolas",
    # apelidos do sistema que o TSX usa e que no Windows resolvem pra Segoe UI
    "-apple-system": "Segoe UI",
    "blinkmacsystemfont": "Segoe UI",
    "system-ui": "Segoe UI",
}


@dataclass(frozen=True)
class Face:
    family: str
    weight: int
    italic: bool
    path: Path
    alias: str          # nome unico registrado no provider
    typeface: skia.Typeface


class FontRegistry:
    """Carrega os arquivos uma vez e resolve (familia, peso, italico) -> Face."""

    def __init__(self, fonts_dir: Path | None = None):
        self.dir = Path(fonts_dir) if fonts_dir else FONTS_DIR
        self._faces: list[Face] = []
        self.provider = tl.TypefaceFontProvider()

        candidatas = ([(f, w, i, self.dir / n) for f, w, i, n in FACES]
                      + [(f, w, i, Path(p)) for f, w, i, p in SYSTEM_FACES])
        for family, weight, italic, path in candidatas:
            if not path.exists():
                continue
            tf = skia.Typeface.MakeFromFile(str(path))
            if tf is None:
                raise RuntimeError(f"nao consegui carregar a fonte: {path}")
            # Alias unico por arquivo: assim o skparagraph escolhe EXATAMENTE o
            # arquivo que a gente resolveu, sem refazer matching por conta propria.
            alias = f"MC::{path.stem}"
            self.provider.registerTypeface(tf, alias)
            self._faces.append(Face(family, weight, italic, path, alias, tf))

        self.collection = tl.FontCollection()
        # O provider e o UNICO font manager: como cada face tem alias proprio, o
        # skparagraph nunca precisa decidir nada — a gente ja resolveu qual
        # arquivo usar. Sem fonte do sistema no meio, sem surpresa de fallback.
        self.collection.setDefaultFontManager(self.provider)
        self.unicode = skia.Unicode()

    # ── matching ──────────────────────────────────────────────────────────
    @staticmethod
    def parse_css_family(css: str) -> list[str]:
        """`"'PlayfairDisplay', Georgia, serif"` -> ['PlayfairDisplay','Georgia','serif']"""
        out = []
        for part in css.split(","):
            p = part.strip().strip("'\"").strip()
            if p:
                out.append(p)
        return out

    def resolve(self, css_family: str, weight: int = 400, italic: bool = False) -> Face:
        for name in self.parse_css_family(css_family):
            cands = [f for f in self._faces if f.family.lower() == name.lower()]
            if not cands:
                generic = GENERIC_FALLBACK.get(name.lower())
                if generic:
                    cands = [f for f in self._faces if f.family.lower() == generic.lower()]
            if not cands:
                continue
            return self._match(cands, weight, italic)
        raise KeyError(f"nenhuma familia encontrada para {css_family!r}")

    @staticmethod
    def _match(cands: list[Face], weight: int, italic: bool) -> Face:
        """Algoritmo de matching do CSS Fonts 4 (estilo primeiro, depois peso)."""
        same_style = [f for f in cands if f.italic == italic]
        pool = same_style or cands

        exact = [f for f in pool if f.weight == weight]
        if exact:
            return exact[0]

        # 400/500 tem regra propria; fora disso: >= alvo subindo, depois <= descendo
        # (pra alvo > 500) ou <= alvo descendo, depois >= subindo (pra alvo < 400).
        if weight > 500:
            # CSS Fonts 4: pra alvo > 500 procura pesos MAIORES primeiro; se nao
            # houver, procura menores. Montserrat 900 -> nao tem >900 -> pega 800.
            above = sorted([f for f in pool if f.weight > weight], key=lambda f: f.weight)
            below = sorted([f for f in pool if f.weight < weight], key=lambda f: -f.weight)
            order = above + below
        elif weight < 400:
            below = sorted([f for f in pool if f.weight < weight], key=lambda f: -f.weight)
            above = sorted([f for f in pool if f.weight > weight], key=lambda f: f.weight)
            order = below + above
        else:
            # 400 aceita 500 antes de descer; 500 aceita 400 antes de subir
            mid = sorted([f for f in pool if 400 <= f.weight <= 500], key=lambda f: f.weight)
            below = sorted([f for f in pool if f.weight < 400], key=lambda f: -f.weight)
            above = sorted([f for f in pool if f.weight > 500], key=lambda f: f.weight)
            order = mid + below + above
        if not order:
            return pool[0]
        return order[0]
