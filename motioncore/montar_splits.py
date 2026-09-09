"""
montar_splits.py — pré-monta os b-rolls em SPLIT com fusão suave.

Formato que ela pediu: ela em cima, b-roll embaixo, **sem linha de separação**
("é como se não houvesse separação, é uma estratégia nova que os editores
usam"). O b-roll emerge da imagem numa zona de fusão de 250px.

Por que pré-montar em vez de fazer no motor: o split é um ARRANJO de duas
fontes, não um estilo. Montado aqui, ele entra no config como b-roll normal e o
composite não precisa saber que existe split.

Duas coisas que decidem se fica bom ou amador:

  ENTRADA (y): 900 corta ela no queixo neste enquadramento. O rosto dela ocupa
  a faixa 300-1000, então o b-roll tem que entrar ABAIXO disso. Medido, não
  chutado — ver `_achar_entrada()`.

  CROP do b-roll: `crop=1080:H` pega o MIOLO. Sem isso aparece a parte errada
  (a receita registra o caso do cabelo em vez do caderno).

    python -m motioncore.montar_splits
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "public" / "projects" / "eli-premiere"
SPLITS = PROJ / "splits"
# Resolvido em tempo de execucao (env > Configuracoes > C:/ffmpeg > PATH):
# cravar o caminho aqui fazia o render morrer em qualquer maquina que nao
# fosse a de quem escreveu. Ver motioncore/ffbin.py.
from .ffbin import ffmpeg as _ffmpeg
FFMPEG = _ffmpeg()

LARG, ALT = 1080, 1920
FUSAO = 250          # altura da zona de gradiente
# O broll ocupa a METADE DE BAIXO e ela SOBE pra caber inteira em cima — foi o
# que ela pediu ("continuar as broll ate no meio mas a pessoa sobe um pouco").
#
# Sem subir, o broll em 960 cortaria ela no peito. Subindo o video 300px, o
# rosto sai do centro do quadro e vai pro centro da METADE de cima, que e onde
# ele tem que estar num split. Testei 180 (fica baixa demais) e 420 (corta o
# topo da cabeca) — 300 e o ponto.
#
# O buraco preto que sobra embaixo depois de subir e coberto pelo proprio
# broll, entao nunca aparece.
ENTRADA = 960
SUBIR = 300


def mascara(altura: int) -> Path:
    """Gradiente alpha 0->255 nos primeiros `FUSAO` px."""
    p = SPLITS / f"feather_{altura}.png"
    if p.exists():
        return p
    SPLITS.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-f", "lavfi",
         "-i", f"color=c=black:s={LARG}x{altura}",
         "-vf", f"format=gray,geq=lum='clip(Y*255/{FUSAO},0,255)'",
         "-frames:v", "1", str(p)], check=True)
    return p


def montar(video: Path, broll: Path, ini: float, dur: float, saida: Path,
           entrada: int = ENTRADA, subir: int = SUBIR) -> bool:
    altura = ALT - entrada
    m = mascara(altura)
    r = subprocess.run(
        [FFMPEG, "-y", "-v", "error",
         "-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", str(video),
         "-stream_loop", "-1", "-i", str(broll),
         "-i", str(m),
         "-filter_complex",
         # `crop` a partir de `subir` + `pad` no topo = o video inteiro sobe
         f"[0:v]crop={LARG}:{ALT - subir}:0:{subir},"
         f"pad={LARG}:{ALT}:0:0:black,setpts=PTS-STARTPTS[t];"
         # `increase` + crop pega o MIOLO do broll, nao a borda
         f"[1:v]scale={LARG}:-1:force_original_aspect_ratio=increase,"
         f"crop={LARG}:{altura},setpts=PTS-STARTPTS[b];"
         "[2:v]format=gray[m];[b][m]alphamerge[ba];"
         f"[t][ba]overlay=0:{entrada}[v]",
         "-map", "[v]", "-an", "-c:v", "h264_nvenc", "-preset", "p5",
         "-cq", "22", "-pix_fmt", "yuv420p", "-t", f"{dur:.3f}", str(saida)],
        capture_output=True)
    return r.returncode == 0 and saida.exists() and saida.stat().st_size > 10000


def main() -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("projeto", nargs="?", default="eli-premiere")
    ap.add_argument("--entrada", type=int, default=ENTRADA,
                    help="y onde o b-roll comeca. TEM que ficar abaixo do queixo "
                         "da pessoa NESTE enquadramento — meca, nao herde.")
    ap.add_argument("--subir", type=int, default=SUBIR,
                    help="quantos px o video sobe pra pessoa caber inteira em cima")
    ap.add_argument("--ids", default="",
                    help="so estes b-rolls (ids separados por virgula); vazio = todos")
    args = ap.parse_args()

    proj = ROOT / "public" / "projects" / args.projeto
    splits = proj / "splits"
    globals()["SPLITS"] = splits
    alvos = {x.strip() for x in args.ids.split(",") if x.strip()}

    cfg_path = proj / "edit_config.json"
    if not cfg_path.exists():
        cfg_path = ROOT / "public" / "edit_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    video = ROOT / "public" / cfg["videoSrc"]
    splits.mkdir(parents=True, exist_ok=True)

    feitos = []
    for b in cfg.get("brolls", []):
        if alvos and b.get("id") not in alvos:
            continue
        src = ROOT / "public" / b["src"]
        if not src.exists():
            print(f"  ! b-roll faltando: {b['src']}")
            continue
        dur = float(b["endSec"]) - float(b["startSec"])
        # nome pelo ID, nao pelo label: dois b-rolls podem usar o MESMO arquivo
        # de origem, e nomear pelo label fazia o segundo sobrescrever o primeiro
        nome = f"split_{b['id']}_{b['label']}.mp4"
        saida = splits / nome
        if montar(video, src, float(b["startSec"]), dur, saida,
                  entrada=args.entrada, subir=args.subir):
            feitos.append((b["id"], f"projects/{args.projeto}/splits/{nome}",
                           b["startSec"], b["endSec"], b["label"]))
            print(f"  {nome:<28} {dur:.1f}s  {saida.stat().st_size/1e6:.1f} MB")
        else:
            print(f"  ! falhou: {nome}")
    # aponta os b-rolls do config pros splits: eles entram como b-roll normal,
    # o composite nao precisa saber que existe split
    mapa = {i: src for i, src, *_ in feitos}
    for b in cfg.get("brolls", []):
        if b["id"] in mapa:
            b["src"] = mapa[b["id"]]
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(feitos)} splits montados e ligados no config")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
