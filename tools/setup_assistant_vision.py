"""Install optional vision in its own environment; download only official model data."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import venv

ROOT = Path(__file__).resolve().parents[1]
MODEL_URL = ('https://storage.googleapis.com/mediapipe-models/image_segmenter/'
             'selfie_multiclass_256x256/float32/1/selfie_multiclass_256x256.tflite')


def main():
    env = ROOT / '.venv-vision'
    python = env / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(env)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements-vision.txt')], check=True)
    folder = ROOT / 'models'
    folder.mkdir(exist_ok=True)
    target = folder / 'selfie_multiclass.tflite'
    if not target.exists():
        temporary = target.with_suffix('.download')
        try:
            with urllib.request.urlopen(MODEL_URL, timeout=60) as source, temporary.open('wb') as dest:
                while chunk := source.read(1024*1024):
                    dest.write(chunk)
            if temporary.stat().st_size < 100000:
                raise RuntimeError('Download incompleto do modelo.')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    metadata = {'url': MODEL_URL, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'documentation': 'https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter',
                'modelCard': 'https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Multiclass%20Segmentation.pdf'}
    (folder / 'selfie_multiclass.source.json').write_text(json.dumps(metadata, indent=2), encoding='utf8')
    print('Visao instalada em', env)


if __name__ == '__main__':
    main()
