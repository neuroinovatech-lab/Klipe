"""
_bench_composite.py — descobre O QUE custa no composite, peca por peca.

O composite virou 64% do render e a pergunta e se trocar de ferramenta ajuda.
Antes de trocar, precisa saber onde o tempo esta: decode? zoom? overlay alpha?
encode? Cada um tem um caminho de GPU diferente — e alguns nao tem nenhum.

Roda variantes sobre 60s do material real e cronometra.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
SRC = ROOT / "public" / "projects" / "mascaramento-autismo" / "video_cut.mp4"
OVERLAY = ROOT / "output" / ".forge_cache" / "a8f7ee7aff75" / "titles.mov"
SAIDA = ROOT / "output" / "_bench_comp"
SEGS = 60

NVENC = ["-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq", "-rc", "vbr",
         "-cq", "19", "-b:v", "0", "-bf", "3"]

# zoom dinamico igual ao do forge_render (a expressao real e maior; esta tem a
# mesma forma: scale com eval=frame + crop)
ZOOM = ("scale=w='1080*(1.0+0.2*(0.5-0.5*cos(3.14159*min(1,t/20))))':"
        "h='1920*(1.0+0.2*(0.5-0.5*cos(3.14159*min(1,t/20))))':eval=frame:flags=bilinear,"
        "crop=1080:1920:x='(iw-1080)/2':y='(ih-1920)/2'")


def roda(nome: str, args: list[str], saida: str) -> float:
    out = SAIDA / saida
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"] + args + [str(out)]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    dt = time.time() - t0
    if r.returncode != 0:
        erro = (r.stderr or "").strip().splitlines()
        print(f"  {nome:<38} FALHOU: {erro[-1][:90] if erro else '?'}")
        return -1.0
    print(f"  {nome:<38} {dt:6.1f}s   ({SEGS/dt:5.2f}x tempo real)")
    return dt


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    if not SRC.exists() or not OVERLAY.exists():
        print(f"faltou material: {SRC.exists()=} {OVERLAY.exists()=}")
        return 1
    print(f"60s do material real | fonte {SRC.name} | overlay {OVERLAY.stat().st_size/1e9:.1f} GB\n")

    print("CPU (o caminho de hoje):")
    base = roda("1. decode + encode NVENC",
                ["-t", str(SEGS), "-i", str(SRC), "-an"] + NVENC, "a.mp4")
    zoom = roda("2. + zoom dinamico (scale eval=frame)",
                ["-t", str(SEGS), "-i", str(SRC), "-an", "-vf", ZOOM] + NVENC, "b.mp4")
    ov = roda("3. + overlay alpha (1 entrada)",
              ["-t", str(SEGS), "-i", str(SRC), "-t", str(SEGS), "-i", str(OVERLAY),
               "-an", "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
               "-map", "[v]"] + NVENC, "c.mp4")
    tudo = roda("4. zoom + overlay alpha",
                ["-t", str(SEGS), "-i", str(SRC), "-t", str(SEGS), "-i", str(OVERLAY),
                 "-an", "-filter_complex", f"[0:v]{ZOOM}[z];[z][1:v]overlay=0:0:format=auto[v]",
                 "-map", "[v]"] + NVENC, "d.mp4")

    print("\nGPU (o que a placa consegue assumir):")
    roda("5. decode CUVID + encode NVENC",
         ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
          "-t", str(SEGS), "-i", str(SRC), "-an"] + NVENC, "e.mp4")
    roda("6. + scale_cuda (tamanho FIXO)",
         ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
          "-t", str(SEGS), "-i", str(SRC), "-an",
          "-vf", "scale_cuda=1080:1920"] + NVENC, "f.mp4")
    roda("7. scale_cuda com eval=frame (zoom dinamico)",
         ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
          "-t", str(SEGS), "-i", str(SRC), "-an",
          "-vf", "scale_cuda=w='1080*(1.0+0.2*t/20)':h='1920*(1.0+0.2*t/20)':eval=frame"] + NVENC, "g.mp4")
    roda("8. overlay_cuda com ALPHA",
         ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
          "-t", str(SEGS), "-i", str(SRC),
          "-t", str(SEGS), "-i", str(OVERLAY),
          "-an", "-filter_complex",
          "[1:v]format=yuva420p,hwupload_cuda[ov];[0:v][ov]overlay_cuda=0:0[v]",
          "-map", "[v]"] + NVENC, "h.mp4")

    if base > 0 and ov > 0:
        print(f"\n  o overlay alpha sozinho custa {ov - base:+.1f}s sobre o decode+encode")
    if base > 0 and zoom > 0:
        print(f"  o zoom dinamico sozinho custa {zoom - base:+.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
