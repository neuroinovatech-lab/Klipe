import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import forge_render as render
from motioncore import ffbin


class FFmpegCompatibilityTests(unittest.TestCase):
    def test_video_and_audio_filter_files_render(self):
        with tempfile.TemporaryDirectory(prefix='klipe ffmpeg ') as directory:
            root = Path(directory)
            video = root / 'source.mp4'
            sound = root / 'sound.wav'
            subprocess.run([render.FFMPEG_EXTERNAL, '-v', 'error', '-f', 'lavfi', '-i',
                'color=c=red:s=64x64:r=30:d=1', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(video)], check=True)
            subprocess.run([render.FFMPEG_EXTERNAL, '-v', 'error', '-f', 'lavfi', '-i',
                'sine=frequency=880:duration=0.3', str(sound)], check=True)
            cfg = dict(videoSrc=str(video), videoDuration=1, width=64, height=64, fps=30,
                       titles=[], brolls=[], zooms=[], musicTracks=[],
                       sfx=[dict(src=str(sound),startSec=.2,endSec=.5,volume=.1)])
            stems = render.ensure_audio_stems(cfg, root)
            self.assertTrue(all(p.stat().st_size > 44 for p in stems))
            result, _, _ = render.render_composite(cfg, None, root/'final.mp4', encoder='cpu')
            self.assertGreater(result.stat().st_size, 1000)
            probe = Path(render.FFMPEG_EXTERNAL).with_name('ffprobe.exe' if Path(render.FFMPEG_EXTERNAL).suffix == '.exe' else 'ffprobe')
            meta = json.loads(subprocess.check_output([str(probe), '-v', 'error', '-show_entries',
                'stream=codec_type,nb_frames:format=duration', '-of', 'json', str(result)]))
            self.assertEqual({s['codec_type'] for s in meta['streams']}, {'video','audio'})
            self.assertAlmostEqual(float(meta['format']['duration']), 1, places=1)

    def test_python_resolver_reads_bom_runtime_without_overriding_explicit_env(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / 'ffmpeg.exe'
            explicit = root / 'custom.exe'
            installed.touch(); explicit.touch()
            (root/'.klipe-runtime.json').write_text(json.dumps({'ffmpeg':str(installed)}),encoding='utf-8-sig')
            try:
                with patch.object(ffbin,'RAIZ',root), patch.object(ffbin,'_das_configuracoes',return_value=None), patch.dict('os.environ',{'KLIPE_FFMPEG':''}):
                    ffbin._achar.cache_clear()
                    self.assertEqual(ffbin.ffmpeg(),str(installed))
                    with patch.dict('os.environ',{'KLIPE_FFMPEG':str(explicit)}):
                        ffbin._achar.cache_clear()
                        self.assertEqual(ffbin.ffmpeg(),str(explicit))
            finally:
                ffbin._achar.cache_clear()


if __name__ == '__main__':
    unittest.main()
