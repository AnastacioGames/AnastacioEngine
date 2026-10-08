"""Five-lane rhythm game component for the Tesla cinematic demo."""
from collections import OrderedDict
import math
import aud
import bgl
import blf
import Range
from Range import logic, events, render
from mathutils import Vector
from anastacio_rhythm_core import Judge, make_chart, BPM, BEAT, LEAD

COLORS = [(0.2, 1, 0.45), (1, 0.35, 0.35), (1, 0.85, 0.15),
          (0.3, 0.65, 1), (0.9, 0.35, 1)]


class AnastacioTeslaRhythm(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ('C_Icons', 'SOUND'), ('Music', '//tesla_rhythm.wav'),
        ('Travel seconds', 2.0), ('Offset ms', 0.0),
        ('Camera beats', 8), ('Camera motion', True),
        ('Volume', 0.65),
    ])

    def start(self, args):
        self.scene = self.object.scene
        self.camera = self.scene.active_camera
        self.target = self.scene.objects['Terminal']
        self.travel = max(0.5, args['Travel seconds'])
        self.offset = args['Offset ms'] / 1000.0
        self.camera_period = max(4, args['Camera beats']) * BEAT
        self.motion = args['Camera motion']
        self.chart = make_chart()
        self.end = self.chart[-1][0] + 2.0
        self.device = aud.Device()
        self.sound = aud.Sound(logic.expandPath(args['Music'])).cache()
        self.volume = max(0.0, min(1.0, args['Volume']))
        self.handle = None
        self.state = 'READY'
        self.now = 0.0
        self.judge = Judge(self.chart)
        self.feedback = ''
        self.feedback_until = 0.0
        self.flashes = [0.0] * 5
        self.keys = [events.AKEY, events.SKEY, events.DKEY, events.FKEY, events.GKEY]
        self.draw_callback = self.draw
        self.scene.post_draw.append(self.draw_callback)
        self.move_camera(0.0)
        print('TESLA_RHYTHM component ready: %d notes, %.2fs' %
              (len(self.chart), self.end), flush=True)

    def begin(self):
        if self.handle:
            self.handle.stop()
        self.handle = self.device.play(self.sound)
        self.handle.volume = self.volume
        self.handle.keep = True
        self.state = 'PLAYING'
        self.now = 0.0
        self.judge = Judge(self.chart)
        self.feedback = ''
        self.flashes = [0.0] * 5

    def update(self):
        kb = logic.keyboard.events
        pressed = logic.KX_INPUT_JUST_ACTIVATED
        if kb[events.RKEY] == pressed:
            self.begin()
        elif kb[events.SPACEKEY] == pressed:
            if self.state in ('READY', 'RESULT'):
                self.begin()
            elif self.state == 'PLAYING':
                self.handle.pause()
                self.state = 'PAUSED'
            else:
                self.handle.resume()
                self.state = 'PLAYING'
        if kb[events.LEFTARROWKEY] == pressed:
            self.offset -= 0.005
        if kb[events.RIGHTARROWKEY] == pressed:
            self.offset += 0.005
        if self.state != 'PLAYING':
            return
        # Audio backend estimates may fluctuate slightly between buffer updates.
        self.now = max(self.now, self.handle.position)
        song_time = self.now - self.offset
        if self.judge.expire(song_time):
            self.feedback = 'PERDEU'
            self.feedback_until = self.now + 0.45
        for lane, key in enumerate(self.keys):
            if kb[key] == pressed:
                self.feedback = self.judge.press(lane, song_time)
                self.feedback_until = self.now + 0.45
                self.flashes[lane] = self.now + 0.14
                if self.feedback != 'FORA DO TEMPO':
                    self.scene.objects['Raio_%d' % lane].strikeLightning()
                    self.camera.shake(0.10)
                    spark = self.scene.objects.get('Anastacio_GPU_Faiscas_%d' % lane)
                    if spark:
                        spark.particles.enabled = True
                        spark['rhythm_until'] = self.now + 0.35
        for lane in range(8):
            spark = self.scene.objects.get('Anastacio_GPU_Faiscas_%d' % lane)
            if spark:
                spark.particles.enabled = self.now < spark.get('rhythm_until', -1.0)
        if self.motion:
            self.move_camera(self.now)
        if self.now >= self.end or self.handle.status == aud.STATUS_STOPPED:
            self.judge.expire(self.end + abs(self.offset) + 1.0)
            self.state = 'RESULT'
            self.handle.stop()

    def move_camera(self, now):
        # Alternate sides within the original front hemisphere; always look at Terminal.
        phase = max(0.0, now - LEAD) / self.camera_period
        angle = math.radians(25) * math.cos(math.pi * phase)
        center = self.target.worldPosition
        self.camera.worldPosition = center + Vector((23 * math.sin(angle),
                                                     -23 * math.cos(angle), 6))
        direction = center - self.camera.worldPosition
        self.camera.worldOrientation = direction.to_track_quat('-Z', 'Y').to_matrix()

    def dispose(self):
        if getattr(self, 'handle', None):
            self.handle.stop()
        if hasattr(self, 'draw_callback') and self.draw_callback in self.scene.post_draw:
            self.scene.post_draw.remove(self.draw_callback)

    def draw(self):
        w, h = render.getWindowWidth(), render.getWindowHeight()
        width = min(w * 0.40, h * 0.66)
        left = (w - width) * 0.5
        bottom, top = h * 0.13, h * 0.86
        lane_w = width / 5.0
        # Preserve compatibility GL state so the HUD does not affect scene rendering.
        bgl.glPushAttrib(bgl.GL_ALL_ATTRIB_BITS)
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glPushMatrix()
        bgl.glLoadIdentity()
        bgl.glOrtho(0, w, 0, h, -1, 1)
        bgl.glMatrixMode(bgl.GL_MODELVIEW)
        bgl.glPushMatrix()
        bgl.glLoadIdentity()
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        bgl.glDisable(bgl.GL_TEXTURE_2D)
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
        try:
            def rect(x, y, rw, rh, color, alpha=1):
                bgl.glColor4f(color[0], color[1], color[2], alpha)
                bgl.glBegin(bgl.GL_QUADS)
                for px, py in [(x, y), (x + rw, y), (x + rw, y + rh), (x, y + rh)]:
                    bgl.glVertex2f(px, py)
                bgl.glEnd()

            def text(x, y, value, size=20):
                bgl.glColor4f(1, 1, 1, 1)
                blf.size(0, int(size * max(0.7, h / 720.0)), 72)
                blf.position(0, x, y, 0)
                blf.draw(0, value)

            rect(left, bottom - 25, width, top - bottom + 45, (0.015, 0.02, 0.045), 0.78)
            for lane, color in enumerate(COLORS):
                x = left + lane * lane_w
                rect(x, bottom, 1, top - bottom, color, 0.35)
                rect(x + 5, bottom - 9, lane_w - 10, 18, color,
                     1 if self.now < self.flashes[lane] else 0.5)
                text(x + lane_w * 0.4, bottom - 38, 'ASDFG'[lane])
            rect(left, bottom + 12, width, 2, (1, 1, 1), 0.9)
            song_time = self.now - self.offset
            for index, (stamp, lane) in enumerate(self.chart):
                remaining = stamp - song_time
                if index not in self.judge.done and -0.14 <= remaining <= self.travel:
                    y = bottom + remaining / self.travel * (top - bottom)
                    rect(left + lane * lane_w + 7, y - 7, lane_w - 14, 14, COLORS[lane])
                    rect(left + lane * lane_w + 10, y + 2, lane_w - 20, 3, (1, 1, 1), 0.7)
            text(24, h - 40, 'TESLA / PULSO ELETRICO', 25)
            text(24, h - 75, 'Pontos %d   Combo %d' % (self.judge.score, self.judge.combo))
            text(24, h - 105, 'Precisao %.1f%%' % self.judge.accuracy)
            text(24, 28, 'ESPACO iniciar/pausar | R reiniciar | setas ajuste: %+.0f ms' %
                 (self.offset * 1000), 15)
            rect(left, top + 28, width, 4, (0.2, 0.25, 0.3))
            rect(left, top + 28, width * min(1, self.now / self.end), 4, (0.3, 0.8, 1))
            message = ''
            if self.state == 'READY':
                message = 'ESPACO PARA COMECAR'
            elif self.state == 'PAUSED':
                message = 'PAUSADO / ESPACO CONTINUA'
            elif self.state == 'RESULT':
                message = 'FIM! Combo max %d / %.1f%% / R repetir' % (self.judge.best, self.judge.accuracy)
            elif self.now < LEAD:
                message = 'PREPARE-SE: %d' % max(1, math.ceil(LEAD - self.now))
            elif self.now < self.feedback_until:
                message = self.feedback
            if message:
                text(left - 20, h * 0.48, message, 21)
        finally:
            bgl.glMatrixMode(bgl.GL_MODELVIEW)
            bgl.glPopMatrix()
            bgl.glMatrixMode(bgl.GL_PROJECTION)
            bgl.glPopMatrix()
            bgl.glPopAttrib()
