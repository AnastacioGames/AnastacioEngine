"""Author a temporary runtime probe; never changes the playable scene."""
import bpy
import os

source = '''from collections import OrderedDict
import time
import Range
from Range import logic

class RhythmProbe(Range.types.KX_PythonComponent):
    args = OrderedDict()
    def start(self, args):
        self.wall = time.monotonic()
        self.stage = 0
        self.clock = []
    def update(self):
        try:
            c = self.object.components[0]
            if self.stage == 0:
                assert c.state == 'READY'
                c.begin()
                c.draw()
                self.stage = 1
            self.clock.append(c.now)
            if self.stage == 1 and c.now > 3.2:
                assert all(b >= a for a, b in zip(self.clock, self.clock[1:]))
                stamp, lane = c.chart[10]
                assert c.judge.press(lane, stamp) == 'PERFEITO'
                c.scene.objects['Raio_%d' % lane].strikeLightning()
                delta = c.target.worldPosition - c.camera.worldPosition
                facing = c.camera.worldOrientation * Range.mathutils.Vector((0,0,-1))
                assert delta.normalized().dot(facing) > 0.999
                c.handle.pause()
                self.pause_pos = c.handle.position
                self.pause_wall = time.monotonic()
                c.state = 'PAUSED'
                self.stage = 2
            if self.stage == 2 and time.monotonic() - self.pause_wall > 0.3:
                assert abs(c.handle.position - self.pause_pos) < 0.03
                c.handle.resume()
                c.state = 'PLAYING'
                c.handle.position = c.end + 0.1
                self.stage = 3
            if self.stage == 3 and c.state == 'RESULT':
                assert len(c.judge.done) == len(c.chart)
                c.begin()
                assert c.judge.score == 0 and not c.judge.done
                c.dispose()
                assert c.draw_callback not in c.scene.post_draw
                with open(logic.expandPath('//rhythm_probe_result.txt'), 'w') as out:
                    out.write('PASS: clock, scoring, camera, pause, result, restart, cleanup')
                print('TESLA_RHYTHM RUNTIME PASS: clock, scoring, camera, pause, result, restart, cleanup', flush=True)
                logic.endGame()
            if time.monotonic() - self.wall > 15:
                raise RuntimeError('probe timeout stage %d' % self.stage)
        except Exception:
            import traceback
            with open(logic.expandPath('//rhythm_probe_result.txt'), 'w') as out:
                out.write(traceback.format_exc())
            traceback.print_exc()
            logic.endGame()
'''.replace('Range.mathutils.Vector', 'Vector').replace('import time', 'import time\nfrom mathutils import Vector')
text = bpy.data.texts.new('anastacio_rhythm_probe.py')
text.from_string(source)
cam = bpy.context.scene.camera
bpy.context.scene.objects.active = cam
assert bpy.ops.logic.python_component_register(component_name='anastacio_rhythm_probe.RhythmProbe') == {'FINISHED'}
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(bpy.data.filepath), 'TeslaPiano_Rhythm_probe.range'))
