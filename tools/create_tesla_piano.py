"""Tesla piano demo: each keyboard key fires a bolt (Lightning emitter with Target) and plays a note.

Run with:  RangeEngine -b --python tools/create_tesla_piano.py -- build/bin/demos/TeslaPiano/TeslaPiano.range

Based on layer 3 of demos/Lightning (Empty with Lightning > Target). Eight Tesla coils in an arc,
each with a MANUAL lightning Empty on top aimed at a central terminal sphere. A Python controller
reads the keyboard and calls strikeLightning() on the coil of the key; the sound is synthesized
with aud + numpy like a real singing Tesla coil (a train of spark clicks at the note frequency, plus
a crack and a low thunder tail), so bolt and note are one sound; no audio files needed.

    A S D F G H J K   do re mi fa sol la si do   (white keys)
    W E   T Y U       sharps, fired from the coil to the left
    ESPACO            thunder: every coil at once
"""
import bpy
import math
import os
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = os.path.abspath(argv[0] if argv else "TeslaPiano.range")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.resolution_x = 1280
scene.game_settings.resolution_y = 720
scene.game_settings.show_framerate_profile = False
scene.game_settings.show_debug_properties = False

world = bpy.data.worlds.new("Laboratorio")
world.horizon_color = (0.01, 0.012, 0.025)
world.zenith_color = (0.0, 0.0, 0.005)
world.use_sky_blend = True
scene.world = world
ws = world.weather_settings
ws.use_rain = True              # the screen flash of strikeLightning() needs Rain on
ws.rain_intensity = 0.0         # ...but no rain drops inside the lab
ws.use_rain_droplets = False
ws.use_rain_ripple = False
ws.use_clouds = False
ws.use_lens_flare = False


def material(name, color, emit=0.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    m.specular_intensity = spec
    m.emit = emit
    return m


metal = material("Metal", (0.55, 0.55, 0.6), spec=1.0)
copper = material("Cobre", (0.72, 0.36, 0.15), spec=0.8)
dark = material("Base", (0.05, 0.05, 0.06), spec=0.1)
glow = material("Terminal", (0.6, 0.75, 1.0), emit=0.6, spec=1.0)


def add_mesh(op, mat, **kw):
    op(**kw)
    ob = bpy.context.object
    ob.data.materials.append(mat)
    return ob


# Floor and central terminal (the target of every bolt)
add_mesh(bpy.ops.mesh.primitive_plane_add, dark, radius=40.0, location=(0, 0, 0)).name = "Chao"
add_mesh(bpy.ops.mesh.primitive_cylinder_add, metal, vertices=32, radius=0.25, depth=4.0,
         location=(0, 6, 2.0)).name = "Haste_Central"
terminal = add_mesh(bpy.ops.mesh.primitive_uv_sphere_add, glow, segments=48, ring_count=24, size=1.2,
                    location=(0, 6, 4.6))
terminal.name = "Terminal"
bpy.ops.object.shade_smooth()

NOTES = [  # key, name, frequency (C4..C5)
    ("A", "Do", 261.63), ("S", "Re", 293.66), ("D", "Mi", 329.63), ("F", "Fa", 349.23),
    ("G", "Sol", 392.00), ("H", "La", 440.00), ("J", "Si", 493.88), ("K", "Do", 523.25),
]
RADIUS = 11.0
for i, (key, note, freq) in enumerate(NOTES):
    ang = math.radians(-70 + i * 140 / (len(NOTES) - 1))
    x, y = RADIUS * math.sin(ang), 6 - RADIUS * math.cos(ang) * 0.55
    h = 3.0 + 0.25 * i          # higher note, taller coil
    add_mesh(bpy.ops.mesh.primitive_cylinder_add, dark, vertices=24, radius=0.9, depth=0.4,
             location=(x, y, 0.2)).name = "Bobina_%d_Base" % i
    add_mesh(bpy.ops.mesh.primitive_cylinder_add, copper, vertices=24, radius=0.35, depth=h,
             location=(x, y, 0.4 + h / 2)).name = "Bobina_%d" % i
    top = add_mesh(bpy.ops.mesh.primitive_torus_add, metal, major_radius=0.7, minor_radius=0.22,
                   location=(x, y, 0.5 + h))
    top.name = "Bobina_%d_Toro" % i
    bpy.ops.object.shade_smooth()

    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(x, y, 0.8 + h))
    em = bpy.context.object
    em.name = "Raio_%d" % i
    em.empty_draw_size = 0.4
    em.use_lightning = True
    L = em.lightning
    L.mode = 'MANUAL'
    L.shape = 'CIRCLE'
    L.target = terminal
    L.big_chance = 1.0
    L.intensity = 0.6
    L.width = 0.5
    L.flash_distance = 30.0
    L.color = (0.55 + 0.05 * i, 0.65, 1.0 - 0.04 * i)

    bpy.ops.object.text_add(location=(x, y - 1.3, 0.05))
    lab = bpy.context.object
    lab.name = "Tecla_%d" % i
    lab.data.body = "%s\n%s" % (key, note)
    lab.data.align_x = 'CENTER'
    lab.data.size = 0.6
    lab.data.materials.append(glow)

bpy.ops.object.lamp_add(type='POINT', location=(0, 6, 7))
bpy.context.object.data.color = (0.5, 0.6, 1.0)
bpy.context.object.data.distance = 25
bpy.ops.object.lamp_add(type='HEMI', location=(0, -10, 10))
bpy.context.object.data.energy = 0.15

bpy.ops.object.camera_add(location=(0, -16, 7.5), rotation=(math.radians(75), 0, 0))
cam = bpy.context.object
scene.camera = cam

# ---------------------------------------------------------------- logic
script = bpy.data.texts.new("piano_tesla.py")
script.from_string('''"""Piano Tesla: cada tecla solta um raio de uma bobina e toca uma nota (som gerado com aud)."""
from bge import logic, events
import aud
import numpy as np

RATE = 48000
g = logic.globalDict
if "tesla" not in g:
    device = aud.Device()
    rng = np.random.default_rng(7)

    def ruido(seg):
        return rng.uniform(-1.0, 1.0, int(RATE * seg)).astype(np.float32)

    def envelope(n, ataque, queda):
        t = np.arange(n) / RATE
        return np.minimum(t / ataque, 1.0) * np.exp(-t / queda)

    def nota(freq, dur=0.9):
        # Como uma bobina de Tesla musical (Zeusophone): a nota e um trem de faiscas,
        # um estalo curto de ruido repetido 'freq' vezes por segundo.
        n = int(RATE * dur)
        t = np.arange(n) / RATE
        fase = (t * freq) % 1.0
        faisca = np.exp(-fase / 0.12) * ruido(dur) * 0.6 + np.exp(-fase / 0.05) * 0.5
        tom = faisca * envelope(n, 0.005, 0.35)
        # estalo do raio no inicio (ruido agudo forte)
        k = int(RATE * 0.12)
        tom[:k] += ruido(0.12) * envelope(k, 0.001, 0.025) * 0.9
        # rabo de trovao grave e baixo, por baixo da nota
        trov = aud.Sound.buffer((ruido(dur) * envelope(n, 0.02, 0.4)).astype(np.float32), RATE)
        trov = trov.lowpass(160).volume(1.4)
        som = aud.Sound.buffer(np.clip(tom, -1, 1).astype(np.float32), RATE).highpass(80)
        return som.volume(0.5).mix(trov).cache()

    def trovao(dur=3.0):
        n = int(RATE * dur)
        r = ruido(dur) * envelope(n, 0.01, 0.9)
        r[:int(RATE * 0.2)] *= 2.5          # estouro inicial
        grave = aud.Sound.buffer(r.astype(np.float32), RATE).lowpass(220).volume(1.8)
        estalo = aud.Sound.buffer((ruido(0.3) * envelope(int(RATE * 0.3), 0.001, 0.06)).astype(np.float32), RATE)
        return grave.mix(estalo.volume(0.6)).cache()

    # tecla -> (bobina, frequencia)
    teclas = {
        events.AKEY: (0, 261.63), events.SKEY: (1, 293.66), events.DKEY: (2, 329.63),
        events.FKEY: (3, 349.23), events.GKEY: (4, 392.00), events.HKEY: (5, 440.00),
        events.JKEY: (6, 493.88), events.KKEY: (7, 523.25),
        # sustenidos: saem da bobina da nota de baixo
        events.WKEY: (0, 277.18), events.EKEY: (1, 311.13), events.TKEY: (3, 369.99),
        events.YKEY: (4, 415.30), events.UKEY: (5, 466.16),
    }
    g["tesla"] = (device, {k: (b, nota(f)) for k, (b, f) in teclas.items()}, trovao())

device, sons, som_trovao = g["tesla"]
kb = logic.keyboard.events
objs = logic.getCurrentScene().objects
JA = logic.KX_INPUT_JUST_ACTIVATED

for tecla, (bobina, som) in sons.items():
    if kb[tecla] == JA:
        objs["Raio_%d" % bobina].strikeLightning()
        device.play(som)

if kb[events.SPACEKEY] == JA:
    for i in range(8):
        objs["Raio_%d" % i].strikeLightning(i % 3 == 0)   # alguns raios, todos com clarao
    device.play(som_trovao)
''')
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
cam.game.sensors[-1].use_pulse_true_level = True
cam.game.controllers[-1].text = script
cam.game.sensors[-1].link(cam.game.controllers[-1])

leia = bpy.data.texts.new("LEIA-ME")
leia.from_string(__doc__.split("Based on")[0] + '''
Aperte P. Teclas A S D F G H J K = do re mi fa sol la si do; W E T Y U = sustenidos;
ESPACO = trovao com todas as bobinas. Edite piano_tesla.py para trocar notas e timbre.
Cada Empty Raio_N: Object Data > Lightning, modo Manual, Target = Terminal.
''')

os.makedirs(os.path.dirname(output), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=output)
