"""
_check_fontes.py — acha família de fonte que NÃO casa com o @font-face.

Esse erro já mordeu duas vezes, e das duas o sintoma foi visual e silencioso:

  - `'Playfair Display'` (com espaço) não casa com o @font-face
    `'PlayfairDisplay'` → o Chrome cai na **Georgia**.
  - `'Bebas Neue'` (com espaço) não casa com `'BebasNeue'` → cai na **Impact**,
    que é condensada. O MotionCore não tinha Impact registrada e caía na
    Montserrat: 46% mais larga, palavra cortada no render.

Nenhum dos dois dá erro. O texto só sai com a fonte errada — e só aparece
quando alguém olha o vídeo.

Aqui todas as famílias declaradas no VideoEditor.tsx são conferidas contra o
@font-face e contra o que o MotionCore resolve. Quando as duas pontas não
apontam pro mesmo arquivo, acusa.

    python -m motioncore._check_fontes
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motioncore.fonts import FACES, FontRegistry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TSX = ROOT / "src" / "VideoEditor.tsx"

# famílias declaradas no bloco @font-face (o que o Chrome REALMENTE conhece)
DECLARADAS = {f.lower() for f, _, _, _ in FACES}


def familias_do_tsx() -> dict[str, list[int]]:
    """Toda string de fontFamily do TSX, com a linha onde aparece."""
    achadas: dict[str, list[int]] = {}
    for n, linha in enumerate(TSX.read_text(encoding="utf-8").splitlines(), 1):
        for m in re.finditer(r'fontFamily:\s*(?:font\()?\s*["\`]([^"\`]+)["\`]', linha):
            achadas.setdefault(m.group(1).strip(), []).append(n)
    return achadas


def main() -> int:
    reg = FontRegistry()
    problemas = 0
    print(f"{'familia declarada no TSX':<44}{'1a que existe':<20}{'MotionCore usa':<20}")
    for css, linhas in sorted(familias_do_tsx().items()):
        nomes = FontRegistry.parse_css_family(css)
        # qual é a primeira da lista que o @font-face conhece
        primeira_conhecida = next((n for n in nomes if n.lower() in DECLARADAS), None)
        # o que o Chrome usaria: a primeira que EXISTE (font-face ou sistema)
        try:
            face = reg.resolve(css, 900, False)
            usada = face.family
        except KeyError:
            usada = "??? NAO RESOLVE"

        # o caso perigoso: a 1a da lista NAO é conhecida, então cai em outra
        primeira = nomes[0] if nomes else ""
        caiu = primeira.lower() not in DECLARADAS and primeira.lower() not in (
            "sans-serif", "serif", "monospace")
        marca = ""
        if usada.startswith("???"):
            marca = "  <<< SEM FONTE"
            problemas += 1
        elif caiu:
            marca = f"  <<< '{primeira}' nao existe, cai em {usada}"
            problemas += 1
        print(f"{css[:43]:<44}{(primeira_conhecida or '—'):<20}{usada:<20}{marca}")
        if marca:
            print(f"{'':<44}linhas: {linhas[:6]}")

    print()
    if problemas:
        print(f"{problemas} familia(s) caindo em fonte diferente da declarada.")
        print("Isso NAO e erro por si so — o Chrome faz o mesmo. O que importa e")
        print("que o MotionCore caia na MESMA fonte, senao a largura do texto muda.")
    else:
        print("nenhuma familia orfa")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
