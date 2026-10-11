"""Pixel-level foreground ordering using the production FFmpeg graph."""
import json
from pathlib import Path
import subprocess
import unittest

from forge_render import build_video_filter_graph, FFMPEG_EXTERNAL


class ForegroundRenderTests(unittest.TestCase):
    def pixels(self, foreground, captions=False):
        cfg = {'width':64,'height':64,'fps':4,'videoDuration':2,'titles':[],
               'brolls':[{'src':'test.mp4','startSec':.5,'endSec':1.5,'alpha':True,'foreground':foreground}]}
        graph = build_video_filter_graph(cfg,1,2,
            titles_indiv=[(2,0,2,{},True)] if captions else None)
        # Left half of the alpha is opaque, right half transparent.
        packed = 'color=red:s=128x64:r=4:d=2,drawbox=x=64:y=0:w=32:h=64:c=white:t=fill,drawbox=x=96:y=0:w=32:h=64:c=black:t=fill'
        proc = subprocess.run([FFMPEG_EXTERNAL,'-v','error','-filter_complex_threads','1',
            '-f','lavfi','-i','color=blue:s=64x64:r=4:d=2',
            '-f','lavfi','-i',packed,'-f','lavfi','-i','color=lime:s=64x64:r=4:d=2',
            '-filter_complex',graph,'-map','[vout]','-frames:v','8','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        self.assertEqual(proc.returncode,0,proc.stderr.decode(errors='replace'))
        self.assertEqual(len(proc.stdout),8*64*64*3)
        def at(frame,x,y):
            pos=(frame*64*64+y*64+x)*3
            return tuple(proc.stdout[pos:pos+3])
        return at

    def test_foreground_covers_title_only_inside_its_alpha_and_interval(self):
        at=self.pixels(True)
        self.assertGreater(at(3,10,32)[0],220)
        self.assertLess(at(3,10,32)[1],25)
        for frame,x in [(0,10),(3,54),(7,10)]:
            self.assertGreater(at(frame,x,32)[1],220)
            self.assertLess(at(frame,x,32)[0],25)

    def test_ordinary_broll_stays_below_titles(self):
        at=self.pixels(False)
        self.assertGreater(at(3,10,32)[1],220)
        self.assertLess(at(3,10,32)[0],25)

    def test_caption_overlay_stays_above_foreground(self):
        at=self.pixels(True,captions=True)
        self.assertGreater(at(3,10,32)[1],220)
        self.assertLess(at(3,10,32)[0],25)

    def test_generated_scene_is_valid_motioncore(self):
        from motioncore.cena import validar
        root=Path(__file__).resolve().parents[1]
        script="const a=require('./public/klipe-assist-core'); console.log(JSON.stringify(a.title({width:1080,height:1920},{startSec:0,endSec:3,text:'Texto editavel'},[]).cena));"
        result=subprocess.run(['node','-e',script],cwd=root,capture_output=True,text=True,check=True)
        self.assertEqual(validar(json.loads(result.stdout)),[])


if __name__ == '__main__':
    unittest.main()
