# -*- coding: utf-8 -*-
"""Gera o pack inicial de TRANSICOES do Klipe em public/transitions/.

Dois tipos (mesmo formato interno dos packs de CapCut/DaVinci):
- luma/*.mp4    — luma mattes P&B 0.6s: branco = clip novo, preto = clip antigo.
                  Usados com xfade custom ou maskedmerge no corte.
- overlay/*.mp4 — overlays pra blend SCREEN por cima do corte (light leak, glitch, flash).

Tudo sintetizado via ffmpeg lavfi — sem download, sem licenca, regeneravel.
"""
import subprocess, json
from pathlib import Path

FF = "C:/ffmpeg/bin/ffmpeg.exe"
ROOT = Path(__file__).parent
LUMA = ROOT / "public" / "transitions" / "luma"
OVER = ROOT / "public" / "transitions" / "overlay"
LUMA.mkdir(parents=True, exist_ok=True)
OVER.mkdir(parents=True, exist_ok=True)

W, H, FPS = 960, 540, 30
D = 0.6  # duracao padrao das lumas

def gen(out, vf_src, dur):
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={dur}",
           "-vf", vf_src, "-c:v", "libx264", "-preset", "fast", "-crf", "16",
           "-pix_fmt", "yuv420p", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and out.exists() and out.stat().st_size > 2000
    print(("  OK   " if ok else "  FAIL ") + out.name + ("" if ok else "  " + r.stderr[-160:]))
    return ok

print("LUMA MATTES (0.6s):")
lumas = {
    # nome -> expressao geq de luminancia (T normalizado 0..1 via T/D)
    "wipe_direita":   f"255*lte(X, W*(T/{D}))",
    "wipe_esquerda":  f"255*gte(X, W*(1-T/{D}))",
    "wipe_baixo":     f"255*lte(Y, H*(T/{D}))",
    "wipe_cima":      f"255*gte(Y, H*(1-T/{D}))",
    "diagonal":       f"255*lte(X+Y, (W+H)*(T/{D}))",
    "circulo_abre":   f"255*lte(hypot(X-W/2,Y-H/2), (T/{D})*hypot(W/2,H/2))",
    "circulo_fecha":  f"255*gte(hypot(X-W/2,Y-H/2), (1-T/{D})*hypot(W/2,H/2))",
    "relogio":        f"255*lte(mod(atan2(Y-H/2,X-W/2)+PI,2*PI), 2*PI*(T/{D}))",
    "persianas":      f"255*lte(mod(Y,90), 90*(T/{D}))",
    "dissolve":       f"255*lte(mod(sin(X*12.9898+Y*78.233)*43758.545,1), T/{D})",
}
count = 0
for nome, expr in lumas.items():
    if gen(LUMA / f"{nome}.mp4", f"geq=lum='{expr}':cb=128:cr=128,format=yuv420p", D):
        count += 1

print("OVERLAYS (blend screen):")
overlays = {
    "light_leak_quente": (1.2,
        "geq="
        "r='255*exp(-(pow(X-W*(T/1.2),2)+pow(Y-H*0.35,2))/(2*pow(W*0.20,2)))':"
        "g='150*exp(-(pow(X-W*(T/1.2),2)+pow(Y-H*0.35,2))/(2*pow(W*0.20,2)))':"
        "b='40*exp(-(pow(X-W*(T/1.2),2)+pow(Y-H*0.35,2))/(2*pow(W*0.20,2)))'"),
    "light_leak_frio": (1.2,
        "geq="
        "r='60*exp(-(pow(X-W*(1-T/1.2),2)+pow(Y-H*0.6,2))/(2*pow(W*0.22,2)))':"
        "g='130*exp(-(pow(X-W*(1-T/1.2),2)+pow(Y-H*0.6,2))/(2*pow(W*0.22,2)))':"
        "b='255*exp(-(pow(X-W*(1-T/1.2),2)+pow(Y-H*0.6,2))/(2*pow(W*0.22,2)))'"),
    "flash_suave": (0.4,
        "geq="
        "r='255*exp(-(pow(X-W/2,2)+pow(Y-H/2,2))/(2*pow(W*0.4,2)))*sin(PI*T/0.4)':"
        "g='255*exp(-(pow(X-W/2,2)+pow(Y-H/2,2))/(2*pow(W*0.4,2)))*sin(PI*T/0.4)':"
        "b='255*exp(-(pow(X-W/2,2)+pow(Y-H/2,2))/(2*pow(W*0.4,2)))*sin(PI*T/0.4)'"),
    "glitch_slices": (0.4,
        "geq="
        "r='if(lt(mod(Y+floor(T*40)*37,110),16), 255*gt(random(0),0.35), 0)':"
        "g='if(lt(mod(Y+floor(T*40)*53,130),14), 255*gt(random(0),0.45), 0)':"
        "b='if(lt(mod(Y+floor(T*40)*71,90),12), 255*gt(random(0),0.4), 0)'"),
}
for nome, (dur, vf) in overlays.items():
    if gen(OVER / f"{nome}.mp4", vf + ",format=yuv420p", dur):
        count += 1

manifest = {
    "luma": [{"nome": n, "file": f"transitions/luma/{n}.mp4", "dur": D} for n in lumas],
    "overlay": [{"nome": n, "file": f"transitions/overlay/{n}.mp4", "dur": overlays[n][0]} for n in overlays],
    "nota": "luma: branco=clip novo. overlay: blend screen por cima do corte.",
}
(ROOT / "public" / "transitions" / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"DONE: {count} transicoes + manifest.json")
