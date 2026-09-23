import Range
import time
from collections import OrderedDict

class SensorReparentStressTest(Range.types.KX_PythonComponent):
    args = OrderedDict([('parent_name', ''), ('cycles', 200), ('interval', 0.05),
                        ('do_reparent', True)])

    def start(self, args):
        self.scene = Range.logic.getCurrentScene()
        self.parent = next((o for o in self.scene.objects if o.name == args['parent_name']), None)
        self.cycles = max(1, int(args['cycles']))
        self.interval = max(0.0, float(args['interval']))
        self.do_reparent = bool(args['do_reparent'])
        self.i = 0
        self.next_time = time.perf_counter()
        self.done = self.parent is None
        self.callback_count = 0
        if not self.done:
            try:
                self.object.collisionCallbacks = [self._collision_callback]
            except Exception as exc:
                print('[sensor_reparent] aviso: callback nao instalado:', repr(exc))
        if self.done:
            print('[sensor_reparent] FAIL: parent_name nao encontrado')

    def update(self):
        if self.done or time.perf_counter() < self.next_time:
            return
        self.next_time = time.perf_counter() + self.interval
        try:
            if self.do_reparent:
                if self.i & 1:
                    self.object.removeParent()
                else:
                    self.object.setParent(self.parent)
            if self.i % 25 == 0:
                profile = dict(Range.logic.getProfileInfo())
                print('[sensor_reparent] ciclo=%d sensors=%d callbacks=%d collision_ms=%.3f' %
                      (self.i, len(self.object.sensors), self.callback_count,
                       profile.get('Collision', (0.0, 0.0))[0]))
            self.i += 1
            if self.i >= self.cycles:
                self.done = True
                self.object['sensor_reparent_done'] = True
                print('[sensor_reparent] PASS: ciclos=%d callbacks=%d; compare com e sem reparent' %
                      (self.i, self.callback_count))
        except Exception as exc:
            self.done = True
            self.object['sensor_reparent_failed'] = True
            print('[sensor_reparent] FAIL:', repr(exc))

    def _collision_callback(self, other, point):
        self.callback_count += 1

SensorReparentStress = SensorReparentStressTest
