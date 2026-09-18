import Range
import time
from collections import OrderedDict

class GpuParticleStressTest(Range.types.KX_PythonComponent):
    args = OrderedDict([('emitter_names', ''), ('duration', 15.0), ('toggle_interval', 2.0)])

    def start(self, args):
        scene = Range.logic.getCurrentScene()
        names = [n.strip() for n in args['emitter_names'].split(',') if n.strip()]
        by_name = {o.name: o for o in scene.objects}
        self.emitters = [by_name[n] for n in names if n in by_name]
        self.duration = max(1.0, float(args['duration']))
        self.toggle_interval = max(0.1, float(args['toggle_interval']))
        self.started = time.perf_counter()
        self.last_toggle = self.started
        self.enabled = True
        self.samples = 0
        self.profile_keys_printed = False
        self.finished = False
        print('[gpu_particle_stress] emissores=%d/%d' % (len(self.emitters), len(names)))

    def update(self):
        if self.finished:
            return
        now = time.perf_counter()
        if now - self.started >= self.duration:
            self.object['gpu_particle_stress_done'] = True
            print('[gpu_particle_stress] PASS: amostras=%d' % self.samples)
            self.finished = True
            return
        if now - self.last_toggle >= self.toggle_interval:
            self.enabled = not self.enabled
            self.last_toggle = now
            for obj in self.emitters:
                obj['GPU_Particles_Enabled'] = 1 if self.enabled else 0
            print('[gpu_particle_stress] enabled=%s' % self.enabled)
        if self.samples % 30 == 0:
            profile = dict(Range.logic.getProfileInfo())
            # A engine publica esta etapa como "ParticleUpdate" (tc_particles).
            particles = profile.get('ParticleUpdate', (0.0, 0.0))
            if not self.profile_keys_printed:
                print('[gpu_particle_stress] profile_keys=%s' % ','.join(sorted(profile.keys())))
                self.profile_keys_printed = True
            print('[gpu_particle_stress] sample=%d particles_ms=%.3f pct=%.2f' %
                  (self.samples, particles[0], particles[1]))
        self.samples += 1

GpuParticleStress = GpuParticleStressTest
