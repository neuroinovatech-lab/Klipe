import subprocess
import unittest

from forge_render import build_video_filter_graph, FFMPEG_EXTERNAL


class MainVideoTransformTests(unittest.TestCase):
    def pixels(self, **changes):
        cfg = dict(width=64, height=64, fps=4, videoDuration=2, titles=[], brolls=[])
        cfg.update(changes)
        graph = build_video_filter_graph(cfg, 0, None, skip_titles=True)
        proc = subprocess.run([FFMPEG_EXTERNAL, '-v', 'error', '-filter_complex_threads', '1',
            '-f', 'lavfi', '-i', 'color=red:s=64x64:r=4:d=2', '-filter_complex', graph,
            '-map', '[vout]', '-frames:v', '8', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'],
            capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors='replace'))
        self.assertEqual(len(proc.stdout), 8*64*64*3)
        return lambda frame, x, y: tuple(proc.stdout[(frame*4096+y*64+x)*3:][:3])

    def test_scale_position_and_interval(self):
        at = self.pixels(videoClips=[dict(startSec=.5,endSec=1.5,scale=.5,posX=16,posY=-8)])
        self.assertGreater(at(3,40,15)[0], 220)
        self.assertLess(max(at(3,16,16)), 8)
        self.assertLess(max(at(3,40,48)), 8)
        self.assertGreater(at(0,16,16)[0], 220)
        self.assertGreater(at(7,16,16)[0], 220)

    def test_transform_does_not_leak_into_next_clip(self):
        at = self.pixels(videoClips=[dict(startSec=0,endSec=1,scale=.5),dict(startSec=1,endSec=2)])
        self.assertLess(max(at(1,2,2)), 8)
        self.assertGreater(at(4,2,2)[0], 220)

    def test_legacy_transform_and_explicit_reset(self):
        at = self.pixels(videoBaseScale=.5)
        self.assertLess(max(at(1,2,2)), 8)
        reset = self.pixels(videoBaseScale=.5,videoClips=[dict(startSec=0,endSec=2,scale=1)])
        self.assertGreater(reset(1,2,2)[0], 220)

    def test_zoom_remains_inside_shrunken_frame(self):
        at = self.pixels(videoClips=[dict(startSec=0,endSec=2,scale=.5)],
                         zooms=[dict(startSec=0,endSec=2,direction='hardIn',intensity=1.5)])
        self.assertLess(max(at(3,10,32)), 8)
        self.assertGreater(at(3,32,32)[0], 220)

    def test_first_clip_wins_overlapping_intervals(self):
        at = self.pixels(videoClips=[dict(startSec=0,endSec=2),dict(startSec=0,endSec=2,scale=.5)])
        self.assertGreater(at(3,2,2)[0], 220)


if __name__ == '__main__':
    unittest.main()
