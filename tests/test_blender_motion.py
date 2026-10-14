import os,unittest,json,gzip,math
os.environ['QT_QPA_PLATFORM']='offscreen'
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import QPointF
from blender_motion import player,ROOT,BlenderMotion
from mascot_animation import MascotAnimation,ACTORS,OUTFITS
from character_motion import draw_character
app=QApplication.instance() or QApplication([])

class BlenderIntegrationTests(unittest.TestCase):
    def test_every_character_costume_has_blender_clips(self):
        for actor in ACTORS:
            for outfit in OUTFITS:
                model=player.model(actor,outfit); self.assertIsNotNone(model)
                for part in model['parts'].values():
                    for clip in ('idle','walk','happy'):
                        self.assertEqual(len(part['frames'][clip]),60)
                        self.assertEqual(len(part['source']),len(part['frames'][clip][0]))
    def test_live_render_bypasses_rejected_python_leg_solver(self):
        mascot=MascotAnimation(); image=QImage(300,220,QImage.Format_ARGB32); image.fill(0); p=QPainter(image)
        with patch('character_motion.solve_legs',side_effect=AssertionError('Old solver called')):
            for actor in ACTORS:
                result=draw_character(p,mascot,actor,'通勤',150,180,.3,moving=True,
                    walk=dict(phase=.25,weight=1,heading=QPointF(1,0),facing=1))
                self.assertFalse(result.isEmpty())
        p.end()
    def test_loop_closure_has_no_large_vertex_jump(self):
        player.reload()
        for model in player.models.values():
            for part in model['parts'].values():
                for clip in ('idle','walk','happy'):
                    frames=part['frames'][clip]
                    for a,b in zip(frames[-1],frames[0]):
                        self.assertLess(math.dist(a,b),2.5,(model['actor'],clip))
    def test_invalid_export_keeps_last_successful_animation(self):
        import tempfile
        from pathlib import Path
        instance=BlenderMotion(); instance.reload(); original=instance.models
        with tempfile.TemporaryDirectory() as directory:
            with gzip.open(Path(directory)/'baked_motion.json.gz','wt') as output: output.write('{bad')
            with patch('blender_motion.ROOT',Path(directory)): instance.reload()
        self.assertIs(instance.models,original); self.assertTrue(instance.error)

if __name__=='__main__': unittest.main()
