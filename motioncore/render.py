"""
render.py — o motor: desenha frames em Skia e joga direto no ffmpeg.

O caminho do motor de navegador e: Chrome headless -> PNG por frame -> ProRes 4444 em
disco -> ffmpeg le de volta -> QTRLE. Sao tres idas e voltas entre disco, CPU e
GPU pra desenhar texto.

Aqui o caminho e um so: desenha na memoria, le os pixels sem premultiplicacao e
escreve os bytes crus no stdin do ffmpeg, que ja grava o MOV com alpha. Sem
navegador, sem PNG, sem arquivo intermediario.

CLI (espelha o batch de titulos por navegador pra virar drop-in no forge_render.py):
    python -m motioncore.render --tasks tasks.json --workers 8
    echo '<json>' | python -m motioncore.render --tasks - --workers 8

tasks.json: {"width":1080,"height":1920,"fps":30,
             "tasks":[{"hash":"...","outPath":"...","title":{...}}]}
Saida: uma linha JSON {"results":[{"hash","ok","err","frames","seconds"}]}
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import skia

from .gpu import onde, superficie
from .fonts import FontRegistry
from .scene import Title, TitleRenderer
from .styles import STYLES

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

# Registry por processo: carregar 18 arquivos de fonte custa ~100ms e nao muda.
_REG: FontRegistry | None = None


def registry() -> FontRegistry:
    global _REG
    if _REG is None:
        _REG = FontRegistry()
    return _REG


def suporta(style: str) -> bool:
    """O MotionCore ja sabe desenhar esse estilo?"""
    return style in STYLES


def _saida_codec(codec: str, width: int, height: int) -> list[str]:
    """
    Como gravar. Os dois carregam alpha; muda quem consome.

    "qtrle"   — MOV QTRLE/argb, o que o composite do render final ja usa.
    "preview" — H.264 pro navegador tocar. Como <video> nao tem canal alpha,
                a cor vai na metade esquerda e o alpha em cinza na direita; o
                canvas remonta os dois na hora de desenhar.

    Por que nao WebM/VP9 com alpha, que seria o obvio: este ffmpeg (8.0.1)
    aceita `-pix_fmt yuva420p`, escreve `alpha_mode=1` no contêiner e mesmo
    assim grava o stream como yuv420p — o alpha some silenciosamente e o titulo
    sai opaco. Testado com VP9 e VP8, com e sem `auto-alt-ref`, com o formato
    forcado no filtro. Ele decodifica alpha em WebM, mas nao codifica.
    """
    if codec == "qtrle":
        return ["-vf", "unpremultiply=inplace=1",
                "-c:v", "qtrle", "-pix_fmt", "argb"]
    if codec == "preview":
        # metade da resolucao: o layout ja esta assado no arquivo, entao
        # encolher AQUI nao mente sobre quebra de linha (encolher antes de
        # desenhar mentiria — os estilos usam fonte em pixel absoluto)
        #
        # Arredondar pra PAR nao e frescura: h264 em yuv420p subamostra o
        # croma pela metade e recusa lado impar. Vale pra qualquer formato —
        # 1080x1920 (short), 1920x1080 (full HD), 1280x720 (HD) — e protege
        # de tamanhos torto tipo 1078 de largura.
        w = max(2, (width // 2) // 2 * 2)
        h = max(2, (height // 2) // 2 * 2)
        return ["-filter_complex",
                f"unpremultiply=inplace=1,scale={w}:{h},format=rgba,split=2[c][a];"
                f"[c]format=yuv420p[cc];"
                # alphaextract exige entrada COM alpha declarado; sem o
                # `format=rgba` acima ele falha com "Requested planes not available"
                f"[a]alphaextract,format=yuv420p[aa];"
                f"[cc][aa]hstack=inputs=2",
                "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "26",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    raise ValueError(f"codec desconhecido: {codec!r}")


def render_title_mov(title: dict, out_path: str | Path, width: int, height: int,
                     fps: float = 30.0, ffmpeg: str = FFMPEG,
                     loglevel: str = "error", codec: str = "qtrle") -> dict:
    """
    Renderiza UM titulo (ancorado em t=0) num arquivo com alpha.

    codec="qtrle" (padrao): MOV QTRLE/argb — o mesmo formato que o cache
    per-title do forge_render.py ja produz, entao o composite nao muda em nada.

    codec="webm": VP9 com alpha, pro preview tocar no navegador.
    """
    t0 = time.time()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    t = Title.from_dict(title)
    rend = TitleRenderer(t, width, height, fps=fps, registry=registry())
    n = rend.duration_frames
    if n <= 0:
        raise ValueError("duracao do titulo <= 0 frame")

    proc = subprocess.Popen(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", loglevel,
         "-f", "rawvideo", "-pixel_format", "rgba",
         "-video_size", f"{width}x{height}", "-framerate", str(fps),
         "-i", "-",
         # O Skia desenha com alpha pre-multiplicado e os dois formatos de
         # saida esperam alpha reto, entao `unpremultiply` abre as duas
         # correntes em _saida_codec. Converter na leitura custava 40 ms/frame
         # (pixel a pixel em Python); no ffmpeg e SIMD e some no ruido.
         "-an", *_saida_codec(codec, width, height), str(out_path)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    surface, fechar = superficie(width, height)
    canvas = surface.getCanvas()
    # buffer reusado: sem isso cada frame aloca 8 MB e o GC vira o gargalo
    buf = np.empty((height, width, 4), dtype=np.uint8)
    # kPremul e o formato nativo da surface: a leitura vira memcpy (0,9 ms)
    info = skia.ImageInfo.Make(width, height, skia.kRGBA_8888_ColorType,
                               skia.kPremul_AlphaType)
    transparente = skia.Color4f(0, 0, 0, 0)

    try:
        sig_ant, bytes_ant, repetidos = object(), None, 0
        for f in range(n):
            sig = rend.frame_signature(f)
            if sig is not None and sig == sig_ant and bytes_ant is not None:
                # frame identico ao anterior: nao redesenha, nao rele, so repete
                # os bytes. Num titulo de 9s isso cobre uns 85% dos frames.
                proc.stdin.write(bytes_ant)
                repetidos += 1
                continue
            canvas.clear(transparente)
            rend.draw_frame(canvas, f)
            fechar()
            surface.readPixels(info, buf, width * 4, 0, 0)
            bytes_ant = buf.tobytes()
            sig_ant = sig
            proc.stdin.write(bytes_ant)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    except Exception:
        proc.kill()
        raise

    _, err = proc.communicate(timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg saiu {proc.returncode}: {err.decode(errors='replace')[:400]}")
    if not out_path.exists() or out_path.stat().st_size <= 1000:
        raise RuntimeError(f"saida {codec} vazia")

    dt = time.time() - t0
    return {"frames": n, "seconds": round(dt, 2),
            "fps_render": round(n / dt, 1) if dt else 0.0,
            "repetidos": repetidos,
            "size_mb": round(out_path.stat().st_size / 1e6, 2)}


def _worker(task: dict, width: int, height: int, fps: float, ffmpeg: str) -> dict:
    try:
        m = render_title_mov(task["title"], task["outPath"], width, height, fps, ffmpeg)
        return {"hash": task.get("hash"), "ok": True, **m}
    except Exception as e:
        return {"hash": task.get("hash"), "ok": False, "err": str(e)[:500]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True, help="arquivo JSON ou '-' pra stdin")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--ffmpeg", default=FFMPEG)
    args = ap.parse_args()

    raw = sys.stdin.read() if args.tasks == "-" else Path(args.tasks).read_text(encoding="utf-8")
    spec = json.loads(raw)
    w = spec.get("width", 1080)
    h = spec.get("height", 1920)
    fps = spec.get("fps", 30)
    tasks = spec.get("tasks", [])

    nao_suportados = [t for t in tasks if not suporta(t["title"].get("style"))]
    if nao_suportados:
        estilos = sorted({t["title"].get("style") for t in nao_suportados})
        print(f"[MC] {len(nao_suportados)} tasks com estilo nao portado: {estilos}",
              file=sys.stderr)
    tasks = [t for t in tasks if suporta(t["title"].get("style"))]

    t0 = time.time()
    results = []
    if tasks:
        workers = max(1, min(args.workers, len(tasks)))
        with cf.ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_worker, t, w, h, fps, args.ffmpeg): t for t in tasks}
            for i, fut in enumerate(cf.as_completed(futs), 1):
                r = fut.result()
                results.append(r)
                estado = (f"OK {r['frames']}f em {r['seconds']}s ({r['fps_render']} fps)"
                          if r["ok"] else f"FAIL {r.get('err', '')[:120]}")
                print(f"[MC] [{i}/{len(tasks)}] {r['hash']} {estado}", file=sys.stderr)

    dt = time.time() - t0
    ok = sum(1 for r in results if r["ok"])
    total_frames = sum(r.get("frames", 0) for r in results if r["ok"])
    print(f"[MC] DONE em {dt:.1f}s | OK={ok}/{len(results)} | {total_frames} frames"
          + (f" | {total_frames / dt:.0f} fps agregado" if dt else ""), file=sys.stderr)
    sys.stdout.write(json.dumps({"results": results,
                                 "skipped": [t.get("hash") for t in nao_suportados]}) + "\n")


if __name__ == "__main__":
    main()
