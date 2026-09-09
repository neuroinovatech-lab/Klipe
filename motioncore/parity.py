"""
parity.py — mede a diferenca entre o render do MotionCore e o do motor de navegador.

Sem isso o porte e chute. O gabarito sao PNGs com alpha gerados por
`_ref_still.js` (renderStill do motor de navegador); aqui a gente renderiza os mesmos
frames em Skia e compara.

Metricas por frame:
  - alpha_mae      erro medio absoluto do canal alpha (0-255)
  - rgb_mae        erro medio absoluto de cor onde os dois tem alpha
  - bbox_ref/got   caixa do conteudo em cada lado (acusa deslocamento e escala)
  - d_centro       deslocamento do centro da caixa (px) — o erro mais revelador
  - cobertura      % de pixels com alpha > 8 em comum sobre a uniao

Uso:
  python -m motioncore.parity --spec motioncore/_parity_spec.json
  python -m motioncore.parity --spec ... --montagem   (gera lado-a-lado + diff)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import skia
from PIL import Image

from .fonts import FontRegistry
from .scene import Title, TitleRenderer

ROOT = Path(__file__).resolve().parent.parent
ALPHA_MIN = 8      # abaixo disso e ruido de sombra, nao conteudo


def _load_rgba(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA"), dtype=np.int16)


def _bbox(alpha: np.ndarray, thr: int = ALPHA_MIN):
    ys, xs = np.where(alpha > thr)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def comparar(ref: np.ndarray, got: np.ndarray) -> dict:
    a_ref, a_got = ref[..., 3], got[..., 3]
    alpha_mae = float(np.abs(a_ref - a_got).mean())

    ambos = (a_ref > ALPHA_MIN) & (a_got > ALPHA_MIN)
    if ambos.sum():
        rgb_mae = float(np.abs(ref[..., :3][ambos] - got[..., :3][ambos]).mean())
    else:
        rgb_mae = float("nan")

    uniao = (a_ref > ALPHA_MIN) | (a_got > ALPHA_MIN)
    cobertura = float(ambos.sum() / uniao.sum()) if uniao.sum() else 1.0

    # `cobertura` conta o pixel mais transparente da sombra igual ao miolo da
    # letra — numa sombra borrada de 28px isso pune diferenca imperceptivel na
    # rampa. `nucleo` olha so o que e opaco: e ele que diz se a LETRA caiu no
    # lugar certo, no tamanho certo.
    n_ref, n_got = a_ref > 200, a_got > 200
    u = (n_ref | n_got).sum()
    nucleo = float((n_ref & n_got).sum() / u) if u else 1.0

    # `dif` = quanto do frame REALMENTE saiu diferente.
    #
    # As duas metricas acima olham sobreposicao, e por isso ficaram CEGAS num
    # estilo com fundo de tela cheia: o `sensoryStorm` pinta 2 milhoes de
    # pixels de fundo identicos nos dois lados, e isso enterrou uma palavra
    # inteira desenhada na fonte errada — cobertura deu 1,000 e nucleo 0,99
    # com a palavra vazando o quadro. Aqui o fundo identico se anula sozinho:
    # so conta pixel onde a imagem mudou de verdade.
    # Compara PRE-MULTIPLICADO: num pixel com alpha ~0 a cor nao aparece, e
    # comparar o RGB cru ali acusa diferenca que ninguem ve (uma textura de
    # alpha 5 marcava 25% do frame como "diferente").
    def _visivel(img):
        a = (img[..., 3:4].astype(np.float32) / 255.0)
        return np.dstack([img[..., :3].astype(np.float32) * a,
                          img[..., 3].astype(np.float32)])

    dif_mask = (np.abs(_visivel(ref) - _visivel(got)).max(axis=2) > 24)
    dif = float(dif_mask.mean())
    # onde a diferenca se concentra, pra saber se e borda ou bloco deslocado
    if dif_mask.any():
        ys, xs = np.where(dif_mask)
        dif_bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    else:
        dif_bbox = None

    b_ref, b_got = _bbox(a_ref), _bbox(a_got)
    d_centro = None
    d_tam = None
    if b_ref and b_got:
        cr = ((b_ref[0] + b_ref[2]) / 2, (b_ref[1] + b_ref[3]) / 2)
        cg = ((b_got[0] + b_got[2]) / 2, (b_got[1] + b_got[3]) / 2)
        d_centro = (round(cg[0] - cr[0], 2), round(cg[1] - cr[1], 2))
        d_tam = (round((b_got[2] - b_got[0]) - (b_ref[2] - b_ref[0]), 2),
                 round((b_got[3] - b_got[1]) - (b_ref[3] - b_ref[1]), 2))

    return {"alpha_mae": round(alpha_mae, 3), "rgb_mae": round(rgb_mae, 2),
            "cobertura": round(cobertura, 4), "nucleo": round(nucleo, 4),
            "dif": round(dif, 5), "dif_bbox": dif_bbox,
            "bbox_ref": b_ref, "bbox_got": b_got,
            "d_centro": d_centro, "d_tam": d_tam}


def montagem(ref: np.ndarray, got: np.ndarray, out: Path, recorte=None):
    """Lado a lado + mapa de diferenca, recortado na regiao com conteudo."""
    if recorte is None:
        a = np.maximum(ref[..., 3], got[..., 3])
        b = _bbox(a)
        if b:
            pad = 40
            x0 = max(0, b[0] - pad); y0 = max(0, b[1] - pad)
            x1 = min(ref.shape[1], b[2] + pad); y1 = min(ref.shape[0], b[3] + pad)
            recorte = (x0, y0, x1, y1)
        else:
            recorte = (0, 0, ref.shape[1], ref.shape[0])
    x0, y0, x1, y1 = recorte
    r = ref[y0:y1, x0:x1]
    g = got[y0:y1, x0:x1]

    # fundo xadrez claro pra enxergar alpha
    h, w = r.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    xadrez = np.where(((xx // 16) + (yy // 16)) % 2 == 0, 235, 205).astype(np.float32)
    xadrez = np.dstack([xadrez] * 3)

    def sobre(img):
        a = (img[..., 3:4] / 255.0).astype(np.float32)
        return (img[..., :3].astype(np.float32) * a + xadrez * (1 - a)).astype(np.uint8)

    # diff: vermelho = so no motor de navegador, verde = so no MotionCore
    da = (r[..., 3].astype(np.float32) - g[..., 3].astype(np.float32))
    diff = np.zeros((h, w, 3), dtype=np.uint8)
    diff[..., 0] = np.clip(da, 0, 255).astype(np.uint8)
    diff[..., 1] = np.clip(-da, 0, 255).astype(np.uint8)

    faixa = np.concatenate([sobre(r), sobre(g), diff], axis=1)
    Image.fromarray(faixa).save(out)


def rodar_caso(caso: dict, spec: dict, reg: FontRegistry, parity_dir: Path,
               fazer_montagem: bool, verboso: bool) -> list[dict]:
    nome = caso["name"]
    frames = caso.get("frames", spec["frames"])
    w, h = spec.get("width", 1080), spec.get("height", 1920)
    fps = spec.get("fps", 30)

    base = parity_dir / nome
    ref_dir, got_dir = base / "ref", base / "skia"
    got_dir.mkdir(parents=True, exist_ok=True)
    mont_dir = base / "montagem"
    if fazer_montagem:
        mont_dir.mkdir(parents=True, exist_ok=True)

    if "props" in caso:
        # caso de OVERLAY (legenda / barra): as props sao as mesmas que o
        # forge_render manda pro monolitico do motor de navegador
        from .overlay import draw_overlay_frame, montar_tiras
        cfg = {**caso["props"], "width": w, "height": h, "fps": fps,
               "videoDuration": max(float(c["endSec"]) for c in caso["props"]["captions"])
               if caso["props"].get("captions") else 1.0}
        tiras = montar_tiras(cfg, w, h, fps, round(cfg["videoDuration"] * fps), reg)

        def render(frame):
            surf = skia.Surface(w, h)
            with surf as cv:
                cv.clear(skia.Color4f(0, 0, 0, 0))
                draw_overlay_frame(cv, tiras, frame)
            return surf.makeImageSnapshot()
    else:
        title = Title.from_dict(caso["title"])
        rend = TitleRenderer(title, w, h, fps=fps, registry=reg)
        render = rend.render_still

    linhas = []
    for frame in frames:
        p_got = got_dir / f"f{frame:04d}.png"
        render(frame).save(str(p_got), skia.kPNG)
        p_ref = ref_dir / f"f{frame:04d}.png"
        if not p_ref.exists():
            continue
        ref, got = _load_rgba(p_ref), _load_rgba(p_got)
        m = comparar(ref, got)
        m["frame"] = frame
        m["caso"] = nome
        linhas.append(m)
        if verboso:
            print(f"  {frame:>5} {m['dif']*100:>8.2f}% {m['nucleo']:>8.4f} "
                  f"{m['cobertura']:>7.3f} {str(m['d_centro']):>15} {str(m['dif_bbox']):>22}")
        if fazer_montagem:
            montagem(ref, got, mont_dir / f"f{frame:04d}.png")
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=str(ROOT / "motioncore" / "_parity_cases.json"))
    ap.add_argument("--caso", help="roda so um caso pelo nome")
    ap.add_argument("--montagem", action="store_true")
    ap.add_argument("-v", "--verboso", action="store_true")
    args = ap.parse_args()

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    parity_dir = spec_path.parent / "_parity"
    casos = [c for c in spec["cases"] if not args.caso or c["name"] == args.caso]
    if not casos:
        raise SystemExit(f"nenhum caso com nome {args.caso!r}")

    reg = FontRegistry()
    todas: list[dict] = []
    print(f"{'caso':<22} {'pior_dif':>9} {'min_nucleo':>10} {'min_cobert':>10} "
          f"{'max_desloc':>11}")
    for caso in casos:
        if args.verboso:
            print(f"\n{caso['name']}")
            print(f"  {'frame':>5} {'dif':>9} {'nucleo':>8} {'cobert':>7} "
                  f"{'d_centro':>15} {'regiao da dif':>22}")
        linhas = rodar_caso(caso, spec, reg, parity_dir, args.montagem, args.verboso)
        if not linhas:
            print(f"{caso['name']:<18} (sem referencia; as douradas vieram do motor de navegador, que saiu)")
            continue
        todas += linhas
        pior_d = max(l["dif"] for l in linhas)
        min_n = min(l["nucleo"] for l in linhas)
        min_c = min(l["cobertura"] for l in linhas)
        desl = max((max(abs(l["d_centro"][0]), abs(l["d_centro"][1]))
                    for l in linhas if l["d_centro"]), default=0.0)
        alerta = "  <<< OLHAR" if pior_d > 0.01 else ""
        print(f"{caso['name']:<22} {pior_d*100:>8.2f}% {min_n:>10.4f} {min_c:>10.4f} "
              f"{desl:>10.1f}px{alerta}")

    if todas:
        pior = max(todas, key=lambda l: l["dif"])
        print(f"\npior frame geral: {pior['caso']} f{pior['frame']} "
              f"alpha_mae={pior['alpha_mae']:.3f} nucleo={pior['nucleo']:.4f}")
        print(f"dif media:       {sum(l['dif'] for l in todas)/len(todas)*100:.3f}%"
              f"   (pixels que sairam DIFERENTES — nao engana com fundo)")
        print(f"nucleo medio:    {sum(l['nucleo'] for l in todas) / len(todas):.4f}"
              f"   (miolo opaco da letra — posicao e tamanho)")
        print(f"cobertura media: {sum(l['cobertura'] for l in todas) / len(todas):.4f}"
              f"   (inclui a rampa da sombra borrada)")
    if args.montagem:
        print(f"montagens em {parity_dir}/<caso>/montagem")


if __name__ == "__main__":
    main()
