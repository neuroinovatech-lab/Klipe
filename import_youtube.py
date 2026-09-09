#!/usr/bin/env python
"""
import_youtube.py — Importa video YouTube → projeto Klipe pronto pra editar.

Pipeline:
  1. yt-dlp download → video.mp4 (1080p h264+aac merge)
  2. ffmpeg preview → video_preview.mp4 (h264 1500k pra player rapido)
  3. faster-whisper GPU CUDA → transcription.json (segment-level)
  4. edit_config.json skeleton (videoSrc + duration + flags default)

USO:
    python import_youtube.py <url> <slug> [inicio-fim]

EXEMPLO:
    python import_youtube.py "https://www.youtube.com/watch?v=ABC" meu-video
    python import_youtube.py "https://..." meu-corte 00:12:00-00:27:00

TRECHO
    O terceiro argumento baixa SO um pedaco, em vez do video inteiro. Existe
    porque o Klipe serve pra fazer CORTE: a materia-prima e podcast de duas,
    tres horas, e ninguem quer baixar 3 GB e esperar uma transcricao de duas
    horas pra usar quinze minutos. O yt-dlp corta no proprio download, entao o
    que nao interessa nunca desce.

    Os tempos da transcricao ficam relativos ao TRECHO, nao ao video original
    — 0s e o comeco do que voce baixou. E o que faz a legenda bater com o que
    o player mostra.

Imprime linhas de progresso prefixadas com [PHASE] que o editor-server captura.
"""
import sys, os, json, subprocess, re, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "public" / "projects"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
PYTHON = sys.executable

def log(phase, msg):
    print(f"[{phase}] {msg}", flush=True)

def slugify(s):
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s-]+", "-", s)
    return s[:60].strip("-") or "video"

def main(url, slug=None, trecho=None):
    # Step 0: get video info to derive slug if not provided
    log("START", f"url={url} slug={slug or '(auto)'} trecho={trecho or '(inteiro)'}")

    if not slug or slug == "auto":
        log("INFO", "Buscando metadata do video...")
        try:
            import yt_dlp
        except ImportError:
            log("FAIL", "yt-dlp nao instalado")
            sys.exit(1)
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            slug = slugify(info.get("title", "video"))
            log("INFO", f"slug derivado: {slug} (titulo: {info.get('title')})")

    proj_dir = PROJECTS / slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    video_path = proj_dir / "video.mp4"
    preview_path = proj_dir / "video_preview.mp4"
    trans_path = proj_dir / "transcription.json"
    cfg_path = proj_dir / "edit_config.json"

    # Step 1: Download via yt-dlp
    log("DOWNLOAD", "Iniciando yt-dlp...")
    if video_path.exists() and video_path.stat().st_size > 1_000_000:
        log("DOWNLOAD", f"Reusando existente: {video_path.name} ({video_path.stat().st_size//1024//1024}MB)")
    else:
        cmd = [
            PYTHON, "-m", "yt_dlp",
            "-f", "bv*[ext=mp4][height<=1080]+ba[ext=m4a]",
            "--merge-output-format", "mp4",
            "-o", str(video_path),
            "--newline", "--progress",
        ]
        if trecho:
            # `--download-sections` corta no download: o resto do arquivo nunca
            # desce. `--force-keyframes-at-cuts` reencoda as bordas pro corte
            # cair no segundo pedido — sem isso ele pula pro keyframe mais
            # proximo e o trecho comeca ate alguns segundos fora do lugar,
            # jogando a transcricao inteira fora de sincronia.
            cmd += ["--download-sections", f"*{trecho}", "--force-keyframes-at-cuts"]
        cmd.append(url)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            line = line.strip()
            if not line: continue
            # Filter to progress lines (yt-dlp prints lots of debug)
            if "[download]" in line or "Downloading" in line or "ERROR" in line:
                log("DOWNLOAD", line[:140])
        proc.wait()
        if proc.returncode != 0:
            log("FAIL", f"yt-dlp exit {proc.returncode}")
            sys.exit(1)
        if not video_path.exists():
            log("FAIL", f"video.mp4 nao foi criado")
            sys.exit(1)
        log("DOWNLOAD", f"OK {video_path.stat().st_size//1024//1024}MB")

    # Get duration via ffprobe
    log("PROBE", "Extraindo duracao...")
    r = subprocess.run([
        FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error",
        "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ], capture_output=True, text=True)
    try:
        duration = float(r.stdout.strip())
    except ValueError:
        log("FAIL", f"ffprobe falhou: {r.stderr[:200]}")
        sys.exit(1)
    log("PROBE", f"duration={duration:.2f}s")

    # Step 2: Preview
    log("PREVIEW", "Gerando preview h264 1500k...")
    if preview_path.exists() and preview_path.stat().st_size > 1_000_000:
        log("PREVIEW", "Reusando preview existente")
    else:
        # Scale preservando aspect: max edge = 1920. Vertical (9:16) vira 1080x1920, horizontal (16:9) vira 1920x1080.
        r = subprocess.run([
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_path),
            "-vf", "scale='if(gt(iw,ih),min(1920,iw),-2)':'if(gt(ih,iw),min(1920,ih),-2)':force_original_aspect_ratio=decrease",
            "-c:v", "libx264", "-b:v", "2500k", "-preset", "fast",
            "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "128k",
            str(preview_path)
        ])
        if r.returncode != 0:
            log("FAIL", "ffmpeg preview falhou")
            sys.exit(1)
        log("PREVIEW", f"OK {preview_path.stat().st_size//1024//1024}MB")

    # Step 2b: Resolucao real do preview — o skeleton PRECISA disto.
    # Sem largura/altura escritas, o config guarda width/height/aspectRatio
    # como null e o player nao tem como saber se o quadro e 16:9 ou 9:16; ele
    # cai num tamanho de palpite e a tela desenha cortada errado. So aparece
    # quando alguem OLHA o vídeo, nunca no import — por isso passou batido.
    r = subprocess.run([
        FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error",
        "-select_streams", "v:0", "-show_entries", "stream=width,height",
        "-of", "csv=p=0", str(preview_path)
    ], capture_output=True, text=True)
    try:
        vid_w, vid_h = (int(x) for x in r.stdout.strip().split(","))
    except ValueError:
        log("FAIL", f"ffprobe resolucao falhou: {r.stderr[:200]}")
        sys.exit(1)
    aspect = "9:16" if vid_h > vid_w else "16:9"
    log("PROBE", f"resolucao={vid_w}x{vid_h} aspect={aspect}")

    # Step 3: Transcribe (only if not exists)
    log("TRANSCRIBE", "Iniciando faster-whisper GPU CUDA...")
    if trans_path.exists() and trans_path.stat().st_size > 100:
        log("TRANSCRIBE", "Transcricao existente, reusando")
    else:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            log("FAIL", "faster_whisper nao instalado")
            sys.exit(1)

        # A queda pra CPU precisa envolver a TRANSCRICAO, nao so o carregamento
        # do modelo. Sem as libs cuBLAS/cuDNN da NVIDIA no PATH o modelo carrega
        # normalmente na GPU e so estoura no primeiro `encode` — entao um `try`
        # que so cobria o construtor nunca via o erro, e o import morria com
        # `cublas64_12.dll is not found` depois de ja ter baixado o video.
        def _rodar(device, compute_type):
            model = WhisperModel("large-v3", device=device, compute_type=compute_type)
            log("TRANSCRIBE", f"{device} pronto ({compute_type})")
            segments_iter, _info = model.transcribe(
                str(video_path),
                language="pt",
                beam_size=5,
                vad_filter=True,
                # Tempo por PALAVRA, nao so por segmento. O motor de legenda
                # precisa disto: sem `words` ele nao sabe QUAL palavra esta
                # sendo falada agora, e todo o destaque palavra a palavra —
                # que e o recurso principal — simplesmente nao acontece.
                # O importador estava entregando transcricao que o resto do
                # sistema nao conseguia usar por inteiro.
                word_timestamps=True,
            )
            saida = []
            for seg in segments_iter:
                saida.append({
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text.strip(),
                    "words": [{"start": round(w.start, 3),
                               "end": round(w.end, 3),
                               "text": w.word.strip(),
                               "prob": round(w.probability, 3)}
                              for w in (seg.words or [])],
                })
                if len(saida) % 10 == 0:
                    log("TRANSCRIBE", f"{len(saida)} segments | t={seg.end:.1f}s")
            return saida

        t0 = time.time()
        try:
            segments = _rodar("cuda", "float16")
        except Exception as e:
            log("TRANSCRIBE", f"GPU falhou ({type(e).__name__}: {e}) — refazendo na CPU")
            segments = _rodar("cpu", "int8")
        elapsed = time.time() - t0
        trans_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
        log("TRANSCRIBE", f"OK {len(segments)} segments em {elapsed:.1f}s")

    # Step 4: Skeleton edit_config
    log("CONFIG", "Gerando edit_config skeleton...")
    cfg = {
        "videoDuration": round(duration, 3),
        "fps": 30,
        "width": vid_w,
        "height": vid_h,
        "aspectRatio": aspect,
        "videoSrc": f"projects/{slug}/video_preview.mp4",
        "videoClips": [{
            "id": "v1",
            "startSec": 0,
            "endSec": round(duration, 3),
            "src": f"projects/{slug}/video_preview.mp4",
            "baseDurationSec": round(duration, 3),
        }],
        "titles": [],
        "brolls": [],
        "zooms": [],
        "sfx": [],
        "musicTracks": [],
        "showCaptions": True,
        "captionStyle": "words",
        "captionKaraoke": True,
        "captionFontSize": 100,
        "captionFont": "Montserrat",
        "captionColor": "#FFFFFF",
        "captionHighlightColor": "#E8940A",
        "captionMaxLines": 2,
        "captionBg": True,
        "showProgressBar": True,
        "barColor": "#E8940A",
        "barHeight": 4,
        "brightness": 0,
        "contrast": 5,
        "saturation": -3,
        "temperature": 0,
    }
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    log("CONFIG", f"OK {cfg_path}")

    log("DONE", f"slug={slug}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    url = sys.argv[1]
    slug = sys.argv[2] if len(sys.argv) > 2 else None
    trecho = sys.argv[3] if len(sys.argv) > 3 else None
    main(url, slug, trecho)
