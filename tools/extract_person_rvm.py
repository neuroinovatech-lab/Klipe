"""
extract_person_rvm.py — Gera video da pessoa com canal alpha NATIVO
usando RVM (Robust Video Matting).

Saida: WebM VP9 com pix_fmt=yuva420p (4 canais: Y, U, V, A).
Compositavel diretamente no browser via <video> + tag transparente,
sem precisar de SVG filter ou mix-blend-mode.

Uso:
    python extract_person_rvm.py --input <video.mp4> --output <video_person.webm>
                                 [--start 0] [--end 60]
                                 [--device cuda|cpu] [--downsample 0.25]
                                 [--model mobilenetv3|resnet50]

Requisitos:
    pip install torch torchvision av tqdm pims

Referencia: https://github.com/PeterL1n/RobustVideoMatting
"""

import argparse
import os
import sys
import subprocess
import tempfile

# Force UTF-8 on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def log(msg):
    try:
        print(f"[RVM] {msg}", flush=True)
    except UnicodeEncodeError:
        safe = str(msg).encode("ascii", errors="replace").decode("ascii")
        print(f"[RVM] {safe}", flush=True)

def run(cmd, **kwargs):
    log(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)

def trim_with_ffmpeg(src, dst, start, end):
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-ss", str(start), "-to", str(end),
        "-i", src,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-an", dst,
    ]
    run(cmd)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--start", type=float, default=None)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--downsample", type=float, default=0.25)
    ap.add_argument("--model", default="mobilenetv3", choices=["mobilenetv3", "resnet50"])
    ap.add_argument("--seq-chunk", type=int, default=12)
    args = ap.parse_args()

    if not os.path.exists(args.input):
        log(f"ERRO: arquivo nao encontrado: {args.input}")
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)

    # ── Trim input if range specified ──
    processing_input = args.input
    tmp_trim = None
    if args.start is not None or args.end is not None:
        start = args.start if args.start is not None else 0.0
        end = args.end if args.end is not None else 999999.0
        log(f"trimando entrada [{start}s, {end}s]")
        tmp_trim = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        try:
            trim_with_ffmpeg(args.input, tmp_trim, start, end)
            processing_input = tmp_trim
        except subprocess.CalledProcessError as e:
            log(f"ERRO no trim: {e}")
            if tmp_trim and os.path.exists(tmp_trim):
                os.unlink(tmp_trim)
            sys.exit(5)

    # ── Load dependencies ──
    try:
        import torch
        from torchvision.transforms import ToTensor
        from torch.utils.data import DataLoader
        from tqdm import tqdm
        import av
        import pims
        import numpy as np
        from fractions import Fraction
    except ImportError as e:
        log(f"ERRO import: {e}")
        log("Instale: pip install torch torchvision av tqdm pims")
        sys.exit(2)

    # ── Device ──
    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    dtype = torch.float16 if device == "cuda" else torch.float32
    log(f"device={device} | model={args.model} | downsample={args.downsample}")

    # ── Load RVM model ──
    log("carregando modelo RVM...")
    try:
        model = torch.hub.load("PeterL1n/RobustVideoMatting", args.model, trust_repo=True).to(device)
        if device == "cuda":
            model = model.half()
        model.eval()
    except Exception as e:
        log(f"ERRO modelo: {e}")
        sys.exit(3)

    # ── Load video ──
    log(f"carregando video: {processing_input}")
    transform = ToTensor()

    # Use pims for reading (same as RVM's VideoReader)
    video = pims.PyAVVideoReader(processing_input)
    frame_rate = float(video.frame_rate)
    total_frames = len(video)
    log(f"frames: {total_frames} | fps: {frame_rate:.2f}")

    # ── Setup PyAV output writer (WebM VP9 with NATIVE ALPHA channel) ──
    # PyAV 16+ requires Fraction for rate, not float.
    # libvpx-vp9 + yuva420p = true 4-channel video, browser composites natively.
    rate_fraction = Fraction(frame_rate).limit_denominator(1000)
    output_container = av.open(args.output, mode='w', format='webm')
    output_stream = output_container.add_stream('libvpx-vp9', rate=rate_fraction)
    output_stream.pix_fmt = 'yuva420p'  # 4 channels: Y U V A
    output_stream.bit_rate = 4_000_000
    # VP9 options: row-mt for parallelism, deadline=good for quality, alpha-q-mode for alpha encoding
    output_stream.options = {
        'deadline': 'good',
        'cpu-used': '4',
        'row-mt': '1',
        'tile-columns': '2',
        'auto-alt-ref': '0',  # required for alpha
    }
    first_frame_written = False

    # ── Custom inference loop: fgr (RGB) + pha (alpha) → 4-channel RGBA ──
    log("rodando inferencia RVM (RGBA com alpha nativo)...")
    rec = [None] * 4
    downsample_ratio = args.downsample
    bar = tqdm(total=total_frames, dynamic_ncols=True, desc="RVM")

    # Process in chunks via DataLoader
    from PIL import Image as PILImage

    class VideoDataset(torch.utils.data.Dataset):
        def __init__(self, pims_video, transform):
            self.video = pims_video
            self.transform = transform
        def __len__(self):
            return len(self.video)
        def __getitem__(self, idx):
            frame = self.video[idx]
            img = PILImage.fromarray(np.asarray(frame))
            return self.transform(img)

    dataset = VideoDataset(video, transform)
    loader = DataLoader(dataset, batch_size=args.seq_chunk, pin_memory=True, num_workers=0)

    try:
        with torch.no_grad():
            for batch in loader:
                batch_size = batch.shape[0]
                src = batch.to(device, dtype).unsqueeze(0)  # [1, T, C, H, W]

                if downsample_ratio is None:
                    h, w = src.shape[3], src.shape[4]
                    downsample_ratio = min(512 / max(h, w), 1)

                fgr, pha, *rec = model(src, *rec, downsample_ratio)

                # Stack RGB + alpha into 4-channel RGBA
                # fgr: [1, T, 3, H, W], pha: [1, T, 1, H, W]
                fgr_clamp = fgr.clamp(0, 1)[0]  # [T, 3, H, W]
                pha_clamp = pha.clamp(0, 1)[0]  # [T, 1, H, W]
                rgba = torch.cat([fgr_clamp, pha_clamp], dim=1)  # [T, 4, H, W]

                # Convert to uint8 and write frames
                frames_np = rgba.mul(255).byte().cpu().permute(0, 2, 3, 1).numpy()  # [T, H, W, 4]

                for t in range(frames_np.shape[0]):
                    rgba_frame = frames_np[t]  # [H, W, 4]
                    if not first_frame_written:
                        output_stream.width = rgba_frame.shape[1]
                        output_stream.height = rgba_frame.shape[0]
                        first_frame_written = True
                    # PyAV: rgba → yuva420p via VideoFrame format conversion
                    frame = av.VideoFrame.from_ndarray(rgba_frame, format='rgba')
                    frame = frame.reformat(format='yuva420p')
                    for pkt in output_stream.encode(frame):
                        output_container.mux(pkt)

                bar.update(batch_size)

        # Flush encoder
        for pkt in output_stream.encode():
            output_container.mux(pkt)

    finally:
        output_container.close()
        bar.close()

    log(f"PRONTO: {args.output}")
    log(f"total frames: {total_frames}, output: {os.path.getsize(args.output) / 1024:.0f} KB")

    # Cleanup
    if tmp_trim and os.path.exists(tmp_trim):
        try:
            os.unlink(tmp_trim)
        except OSError:
            pass

if __name__ == "__main__":
    main()
