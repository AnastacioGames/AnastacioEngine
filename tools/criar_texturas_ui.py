"""Gera as texturas seamless do tema em source/release/datafiles/ui_textures.

Usa as fórmulas de textura da própria engine. Rodar sem janela:
  build/bin/AnastacioEngine.exe --background --factory-startup --python tools/criar_texturas_ui.py
"""
import os
import bpy

SIZE = 256
PERIOD = 4.0
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "source", "release", "datafiles", "ui_textures")


def clouds(t):
    t.noise_scale = 0.6
    t.noise_depth = 4


def marble(t):
    t.noise_scale = 0.8
    t.turbulence = 6.0


def wood(t):
    t.wood_type = 'BANDNOISE'
    t.noise_scale = 0.7
    t.turbulence = 8.0


def voronoi(t):
    t.noise_scale = 0.35


def stucci(t):
    t.noise_scale = 0.25
    t.turbulence = 6.0


TEXTURES = (("clouds", 'CLOUDS', clouds), ("marble", 'MARBLE', marble), ("wood", 'WOOD', wood),
            ("voronoi", 'VORONOI', voronoi), ("stucci", 'STUCCI', stucci))


def sample(tex, x, y):
    r, g, b, a = tex.evaluate((x, y, 0.0))
    return (r + g + b) / 3.0 if (r or g or b) else a


def seamless(tex):
    """Mistura quatro cópias deslocadas de um período: as bordas opostas ficam iguais."""
    values = []
    for j in range(SIZE):
        v = j / SIZE
        for i in range(SIZE):
            u = i / SIZE
            x, y = u * PERIOD, v * PERIOD
            values.append(sample(tex, x, y) * (1 - u) * (1 - v) +
                          sample(tex, x - PERIOD, y) * u * (1 - v) +
                          sample(tex, x, y - PERIOD) * (1 - u) * v +
                          sample(tex, x - PERIOD, y - PERIOD) * u * v)
    low, high = min(values), max(values)
    return [0.35 + 0.65 * (value - low) / max(high - low, 1e-6) for value in values]


os.makedirs(OUT, exist_ok=True)
for name, kind, setup in TEXTURES:
    tex = bpy.data.textures.new(name, kind)
    setup(tex)
    values = seamless(tex)
    image = bpy.data.images.new(name, SIZE, SIZE, alpha=False)
    pixels = []
    for value in values:
        pixels += (value, value, value, 1.0)
    image.pixels = pixels
    image.filepath_raw = os.path.join(OUT, name + ".png")
    image.file_format = 'PNG'
    image.save()
    print("UITEX", name, min(values), max(values))
