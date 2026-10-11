"""Optional local face analysis and person segmentation for Klipe.

Receives one JSON request on stdin; writes one JSON result on stdout.
MediaPipe model is obtained separately from Google's official model catalog.
"""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def dimensions(config, maximum=960):
    w, h = int(config.get('width', 1920)), int(config.get('height', 1080))
    if w < 16 or h < 16 or max(w, h) > 7680:
        raise ValueError('Dimensoes invalidas.')
    ratio = min(1, maximum / max(w, h))
    return max(2, round(w * ratio / 2) * 2), max(2, round(h * ratio / 2) * 2)


def decode_args(req, start, duration, w, h, fps):
    return [req['ffmpeg'], '-v', 'error', '-nostdin', '-ss', str(start), '-i', req['source'],
            '-t', str(duration), '-an', '-vf',
            f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}',
            '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1']


def frames(req, start, duration, w, h, fps):
    import numpy as np
    with tempfile.TemporaryFile() as log:
        p = subprocess.Popen(decode_args(req, start, duration, w, h, fps), stdout=subprocess.PIPE,
                             stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            while True:
                data = p.stdout.read(w * h * 3)
                if not data:
                    break
                if len(data) != w * h * 3:
                    raise RuntimeError('Quadro incompleto ao decodificar o video.')
                yield np.frombuffer(data, dtype=np.uint8).reshape(h, w, 3)
            if p.wait(timeout=30):
                log.seek(0)
                raise RuntimeError(log.read().decode('utf8', errors='replace')[-2000:])
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
            p.stdout.close()


def face_analysis(req):
    import cv2
    cfg = req['config']
    w, h = dimensions(cfg, 640)
    # Haar ships with OpenCV: no external model download or video upload.
    detector = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml'))
    if detector.empty():
        raise RuntimeError('Modelo de rosto do OpenCV indisponivel.')
    duration = float(cfg['videoDuration'])
    step = max(.5, duration / 300)
    result = []
    for i, frame in enumerate(frames(req, 0, duration, w, h, 1 / step)):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        found = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
        for x, y, fw, fh in found:
            # Padding includes detector jitter and nearby hair/chin.
            result.append({'startSec': max(0, i*step-step/2), 'endSec': min(duration,(i+1.5)*step),
                           'x': max(0, (float(x)-fw*.18)/w), 'y': max(0,(float(y)-fh*.24)/h),
                           'w': min(1, float(fw)*1.36/w), 'h': min(1,float(fh)*1.55/h)})
    return {'faces': result, 'sampleStep': step}


def segment_person(req):
    import cv2
    import mediapipe as mp
    import numpy as np
    model = Path(req['model'])
    if not model.is_file():
        raise RuntimeError('Modelo de recorte ausente. Execute tools/setup_assistant_vision.py conforme docs/ASSISTENTE.md.')
    start, end = float(req['startSec']), float(req['endSec'])
    fps = float(req['config'].get('fps', 30))
    if not math.isfinite(fps) or not 1 <= fps <= 120 or not 0 < end-start <= 30:
        raise ValueError('FPS ou intervalo invalido.')
    w, h = dimensions(req['config'], 1280)
    strength = float(req.get('strength', 0)) / 100
    feather = float(req.get('feather', .6))
    if not math.isfinite(strength) or not 0 <= strength <= 1 or not math.isfinite(feather) or not 0 <= feather <= 4:
        raise ValueError('Ajustes de mascara invalidos.')
    target = Path(req['output'])
    temporary = target.with_name(target.stem + '.tmp.mp4')
    options = mp.tasks.vision.ImageSegmenterOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        output_category_mask=False, output_confidence_masks=True)
    count = 0
    with tempfile.TemporaryFile() as log:
        encoder = subprocess.Popen([req['ffmpeg'], '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                    '-s', f'{w*2}x{h}', '-r', str(fps), '-i', 'pipe:0', '-an',
                                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p',
                                    '-movflags', '+faststart', str(temporary)], stdin=subprocess.PIPE, stderr=log,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            with mp.tasks.vision.ImageSegmenter.create_from_options(options) as segmenter:
                for i, rgb in enumerate(frames(req, start, end-start, w, h, fps)):
                    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
                    masks = segmenter.segment_for_video(image, round(i*1000/fps)).confidence_masks
                    if len(masks) != 6:
                        raise RuntimeError('Modelo deve ser Selfie Multiclass com seis classes.')
                    alpha = np.clip(1-masks[0].numpy_view(), 0, 1)
                    alpha = cv2.resize(alpha, (w,h), interpolation=cv2.INTER_LINEAR)
                    alpha = np.clip((alpha - .292*strength) / (1-.632*strength), 0, 1)
                    if feather > 0:
                        alpha = cv2.GaussianBlur(alpha, (0,0), feather)
                    mask = np.repeat((alpha[...,None]*255).astype(np.uint8),3,axis=2)
                    # Klipe's existing alpha transport: RGB | grayscale alpha.
                    encoder.stdin.write(np.concatenate([rgb,mask],axis=1).tobytes())
                    count += 1
            encoder.stdin.close()
            if encoder.wait(timeout=60):
                log.seek(0)
                raise RuntimeError(log.read().decode('utf8', errors='replace')[-2000:])
            if count < 1:
                raise RuntimeError('O trecho nao produziu quadros.')
            os.replace(temporary,target)
        finally:
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait()
            if not encoder.stdin.closed:
                encoder.stdin.close()
            temporary.unlink(missing_ok=True)
    if req.get('backgroundOutput'):
        subprocess.run([req['ffmpeg'], '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        f'color=c=black:s={w}x{h}:r={fps}', '-t', str(count/fps), '-an',
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', req['backgroundOutput']], check=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return {'duration': count/fps, 'frames': count, 'width': w, 'height': h}


def main():
    try:
        req = json.load(sys.stdin)
        mode = sys.argv[1]
        result = face_analysis(req) if mode == 'faces' else segment_person(req) if mode == 'person' else None
        if result is None:
            raise ValueError('Modo desconhecido.')
        print(json.dumps(result))
    except ImportError as exc:
        print(f'Analise visual nao instalada ({exc.name}). Execute tools/setup_assistant_vision.py conforme docs/ASSISTENTE.md.', file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
