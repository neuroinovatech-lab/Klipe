"""
Verifica que `signature()` nunca mente.

O render pula o desenho quando a assinatura do frame repete a do anterior. Se
uma assinatura esquecer alguma coisa que muda na tela, o frame anterior e
repetido e o video sai ERRADO — e calado, que e o pior tipo de bug.

Aqui todo frame e desenhado de verdade e comparado com o anterior. Se a
assinatura disse "igual" e os pixels diferem, acusa.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import skia

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motioncore.fonts import FontRegistry           # noqa: E402
from motioncore.scene import Title, TitleRenderer   # noqa: E402
from motioncore.styles import STYLES                # noqa: E402

TEXTOS = {
    "lower3rd": "Esconder características gera mal-entendidos",
    "hero": "MASKING = SOBREVIVÊNCIA",
    "flash": "DIAGNÓSTICO TARDIO",
    "kinetic": "CIRCUITO DOPAMINÉRGICO",
    "panel": "O COLAPSO|Exaustão física|Exaustão emocional|Exaustão mental",
    "ribbon": "Atrasar o diagnóstico traz consequências",
    "counter": "87% das mulheres autistas",
    "quote": "Não falo só como médica — é a minha realidade",
    "stackedReveal": "MASKING|É CANSAR|todo dia|SEM PARAR",
    "pointList": "MASCARAMENTO É|Camuflar comportamentos|Suprimir o natural|Imitar quem está em volta",
    "compound2": "Mulheres autistas|SENTEM MAIS|não menos",
    "descending": "A GENTE COLAPSA",
    "wordCollapse": "EXAUSTÃO|EXAUSTÃO EMOCIONAL|MENTAL|COLAPSA",
    "echoWords": "Você vai ser invalidada|Não sabem lidar|Principalmente mulheres",
    "liveComments": "Nossa, eu me identifico|Eu sou assim|É real, gente",
    "paradoxQuote": "Muito normal|PRA SER AUTISTA|e muito estranho|PARA SER NORMAL",
    "sensoryStorm": "PERTENCER|SE ENCAIXAR|OS GRUPOS|PRESSÃO SOCIAL|MASCARAR",
    "mixedSerif": "Adolescência|pressão pra se encaixar",
    "letterEyebrow": "Antes do diagnóstico|VOCÊ FAZIA AS COISAS|mas não era consciente",
    "cutMask": "",
}

W, H, FPS, DUR = 1080, 1920, 30, 5.0


def main():
    reg = FontRegistry()
    surf = skia.Surface(W, H)
    cv = surf.getCanvas()
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    buf = np.empty((H, W, 4), dtype=np.uint8)
    ruim = 0

    print(f"{'estilo':<16} {'frames':>7} {'repetidos':>10} {'mentiras':>9} {'pior diff':>10}")
    for estilo, texto in TEXTOS.items():
        if estilo not in STYLES:
            continue
        t = Title.from_dict({"startSec": 0, "endSec": DUR, "style": estilo, "text": texto})
        r = TitleRenderer(t, W, H, fps=FPS, registry=reg)

        sig_ant, px_ant = object(), None
        repetidos = mentiras = 0
        pior = 0
        for f in range(r.duration_frames):
            sig = r.frame_signature(f)
            cv.clear(skia.Color4f(0, 0, 0, 0))
            r.draw_frame(cv, f)
            surf.readPixels(info, buf, W * 4, 0, 0)
            px = buf.copy()
            if px_ant is not None and sig is not None and sig == sig_ant:
                repetidos += 1
                d = int(np.abs(px.astype(np.int16) - px_ant.astype(np.int16)).max())
                if d > 0:
                    mentiras += 1
                    pior = max(pior, d)
            sig_ant, px_ant = sig, px
        ruim += mentiras
        marca = "" if not mentiras else "  <-- ASSINATURA MENTIU"
        print(f"{estilo:<16} {r.duration_frames:>7} {repetidos:>10} {mentiras:>9} "
              f"{pior:>10}{marca}")

    print("\nOK — nenhuma assinatura mentiu" if not ruim
          else f"\nFALHOU: {ruim} frames repetidos indevidamente")
    return 1 if ruim else 0


if __name__ == "__main__":
    raise SystemExit(main())
