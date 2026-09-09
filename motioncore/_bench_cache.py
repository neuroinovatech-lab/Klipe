"""
_bench_cache.py — mede as duas suspeitas sobre o custo do composite.

1. **O overlay e guardado em tela cheia sem precisar.** A gente transporta so a
   faixa (1080x489) pelo cano, mas manda o ffmpeg fazer `pad` pra 1080x1920
   antes de gravar. Resultado: 4x mais disco e 4x mais pixel pra decodificar em
   cada frame do composite. Guardar a faixa e deslocar no composite deveria
   custar 1/4.

2. **O composite escala com o NUMERO de entradas.** Com 1 overlay ele roda a
   5,68x tempo real; o render real, com 45, roda a 2,16x. Aqui mede quanto cada
   entrada extra custa, pra saber se vale reduzir e ate quanto.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
SRC = ROOT / "public" / "projects" / "mascaramento-autismo" / "video_cut.mp4"
OVERLAY = ROOT / "output" / ".forge_cache" / "a8f7ee7aff75" / "titles.mov"
IND = ROOT / "output" / ".forge_cache" / "titles_indiv"
TMP = ROOT / "output" / "_bench_cache"
SEGS = 60
NVENC = ["-c:v", "h264_nvenc", "-preset", "p7", "-rc", "vbr", "-cq", "19", "-b:v", "0"]

# faixa da legenda medida pelo proprio motor
FAIXA_Y, FAIXA_H = 1253, 484
BARRA_H = 5


def cron(cmd: list[str]) -> float:
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        linhas = (r.stderr or "").strip().splitlines()
        print("      FALHOU:", linhas[-1][:100] if linhas else "?")
        return -1.0
    return time.time() - t0


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    if not OVERLAY.exists():
        print("faltou o overlay de referencia")
        return 1

    print("=== 1. guardar a FAIXA em vez da tela cheia ===")
    cheio = TMP / "cheio.mov"
    faixa = TMP / "faixa.mov"
    cron([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-t", str(SEGS),
          "-i", str(OVERLAY), "-c:v", "qtrle", "-pix_fmt", "argb", str(cheio)])
    # empilha as duas tiras (barra no topo + legenda) num quadro so
    cron([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-t", str(SEGS),
          "-i", str(OVERLAY), "-filter_complex",
          f"[0:v]split=2[a][b];"
          f"[a]crop=1080:{BARRA_H}:0:0[bar];"
          f"[b]crop=1080:{FAIXA_H}:0:{FAIXA_Y}[cap];"
          f"[bar][cap]vstack=inputs=2[v]",
          "-map", "[v]", "-c:v", "qtrle", "-pix_fmt", "argb", str(faixa)])
    if cheio.exists() and faixa.exists():
        a, b = cheio.stat().st_size, faixa.stat().st_size
        print(f"  tela cheia 1080x1920 : {a/1e6:7.1f} MB  ({a/1e9*17.63/1:.2f} GB no video todo)")
        print(f"  faixa 1080x{BARRA_H+FAIXA_H:<9}: {b/1e6:7.1f} MB  ({b/1e9*17.63:.2f} GB)  -> {a/b:.1f}x menor")

    print("\n=== 2. quanto custa DECODIFICAR cada um no composite ===")
    for nome, ovl, filtro in [
        ("overlay tela cheia", cheio, "[0:v][1:v]overlay=0:0:format=auto[v]"),
        ("overlay em faixa", faixa,
         f"[1:v]split=2[x][y];"
         f"[x]crop=1080:{BARRA_H}:0:0[bar];"
         f"[y]crop=1080:{FAIXA_H}:0:{BARRA_H}[cap];"
         f"[0:v][bar]overlay=0:0[t1];[t1][cap]overlay=0:{FAIXA_Y}:format=auto[v]"),
    ]:
        if not ovl.exists():
            continue
        dt = cron([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                   "-t", str(SEGS), "-i", str(SRC), "-i", str(ovl), "-an",
                   "-filter_complex", filtro, "-map", "[v]"] + NVENC
                  + [str(TMP / f"dec_{ovl.stem}.mp4")])
        if dt > 0:
            print(f"  {nome:<22} {dt:6.1f}s  ({SEGS/dt:5.2f}x tempo real)")

    print("\n=== 3. o composite escala com o NUMERO de entradas? ===")
    movs = sorted(IND.glob("*.mov"))
    if not movs:
        print("  (sem MOVs de titulo em cache pra testar)")
        return 0
    base = movs[0]
    for n in (1, 5, 15, 30, 44):
        entradas, filtro, atual = [], [], "[0:v]"
        for i in range(n):
            entradas += ["-t", str(SEGS), "-i", str(base)]
            saida = "[v]" if i == n - 1 else f"[m{i}]"
            filtro.append(f"{atual}[{i+1}:v]overlay=0:0:format=auto{saida}")
            atual = saida
        dt = cron([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                   "-t", str(SEGS), "-i", str(SRC)] + entradas +
                  ["-an", "-filter_complex", ";".join(filtro), "-map", "[v]"]
                  + NVENC + [str(TMP / f"n{n}.mp4")])
        if dt > 0:
            print(f"  {n:2d} entradas de alpha : {dt:6.1f}s  ({SEGS/dt:5.2f}x)  "
                  f"-> video todo: {1057.8/(SEGS/dt)/60:5.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
