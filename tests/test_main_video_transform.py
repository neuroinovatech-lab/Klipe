import subprocess
import unittest

from forge_render import build_video_filter_graph, FFMPEG_EXTERNAL


class MainVideoTransformTests(unittest.TestCase):
    def pixels(self, **changes):
        source = changes.pop('_source', 'color=red:s=64x64:r=4:d=2')
        cfg = dict(width=64, height=64, fps=4, videoDuration=2, titles=[], brolls=[])
        cfg.update(changes)
        graph = build_video_filter_graph(cfg, 0, None, skip_titles=True)
        proc = subprocess.run([FFMPEG_EXTERNAL, '-v', 'error', '-filter_complex_threads', '1',
            '-f', 'lavfi', '-i', source, '-filter_complex', graph,
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

    def test_rotation_has_transparent_outside_not_stretched_edges(self):
        at = self.pixels(videoClips=[dict(startSec=0,endSec=2,scale=.5,rotation=45)])
        self.assertGreater(at(2,32,32)[0],220)
        for x,y in [(2,2),(16,16),(2,32),(32,2),(60,60)]:
            self.assertLess(max(at(2,x,y)),10)

    def test_independent_scale_and_anchor(self):
        at = self.pixels(videoClips=[dict(startSec=0,endSec=2,scaleX=.5,scaleY=.25,anchorX=16,anchorY=-8)])
        self.assertGreater(at(2,40,26)[0],220)
        self.assertLess(max(at(2,20,26)),10)
        self.assertLess(max(at(2,40,40)),10)

    def test_flip_horizontal_and_vertical(self):
        for key,box,blue,red in [('flipX','w=32:h=64',(56,32),(8,32)),('flipY','w=64:h=32',(32,56),(32,8))]:
            at=self.pixels(_source='color=red:s=64x64:r=4:d=2,drawbox=x=0:y=0:'+box+':color=blue:t=fill',
                           videoClips=[dict(startSec=0,endSec=2,**{key:True})])
            self.assertGreater(at(2,*blue)[2],220)
            self.assertGreater(at(2,*red)[0],220)

    def test_perspective_and_disabled_transform(self):
        clip=dict(startSec=0,endSec=2,scale=.6,pitch=40,yaw=-35,rotation=12)
        at=self.pixels(videoClips=[clip])
        self.assertGreater(at(2,32,32)[0],220)
        self.assertLess(max(at(2,2,2)),10)
        at=self.pixels(videoClips=[dict(clip,transformEnabled=False)])
        self.assertGreater(at(2,2,2)[0],220)


if __name__ == '__main__':
    unittest.main()
