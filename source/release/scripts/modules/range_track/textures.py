# Texturas geradas do Track Tool (tileáveis, 128 px), ligadas a um material pelo nome do preset:
# a faixa do preset pode ter "texture": "<nome>" (ver TEXTURES).
#
# Orientação: nas faixas paramétricas u = lateral/uv_repeat e v = s/uv_repeat (sweep.py), então
# u atravessa a rua (u = 0 no eixo) e v corre ao longo dela.
import bpy
import math
from mathutils import Vector, noise

from . import decor as _decor

LADO = 128


def _smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _toro(fu, fv, raio=1.3):
    """Ponto num toro para ruído periódico em u e v."""
    a = 2 * math.pi * fu
    b = 2 * math.pi * fv
    return Vector((math.cos(a) * raio, math.sin(a) * raio, math.cos(b) * raio + math.sin(b) * 0.7))


def _dirt_road(fu, fv):
    """Rua de terra batida: dois trilhos de pneu mais escuros e lisos, mato ralo no meio e nas
    beiradas, pedrinhas e poças secas."""
    q = _toro(fu, fv)
    n1 = noise.noise(q * 2.0) * 0.5 + 0.5
    n2 = noise.noise(q * 8.0 + Vector((3, 1, 2))) * 0.5 + 0.5
    n3 = noise.noise(q * 30.0 + Vector((7, 5, 1))) * 0.5 + 0.5
    # distância lateral ao eixo (u tileável: 0 no eixo, 0.5 na beirada)
    d = abs(((fu + 0.5) % 1.0) - 0.5)
    ondula = (n1 - 0.5) * 0.06                       # trilho não é reto
    trilho = 1.0 - _smooth(0.04, 0.09, abs(d - 0.25 + ondula))
    meio = 1.0 - _smooth(0.05, 0.11, d + ondula * 0.5)
    beira = _smooth(0.40, 0.49, d - ondula)
    mato = max(meio * 0.75, beira) * _smooth(0.35, 0.65, n2)
    base = 0.80 + 0.30 * n1 + 0.12 * (n3 - 0.5)
    r, g, b = 0.50 * base, 0.36 * base, 0.22 * base   # terra avermelhada
    escuro = 1.0 - 0.22 * trilho
    r, g, b = r * escuro, g * escuro, b * escuro
    if n3 > 0.80:                                    # pedrinha clara
        p = _smooth(0.80, 0.86, n3)
        r, g, b = r + (0.62 - r) * p, g + (0.58 - g) * p, b + (0.52 - b) * p
    poca = _smooth(0.70, 0.76, n1) * trilho          # barro seco no trilho
    r, g, b = r * (1 - 0.18 * poca), g * (1 - 0.20 * poca), b * (1 - 0.20 * poca)
    gr = (0.22 * base, 0.38 * base, 0.13 * base)
    return (r + (gr[0] - r) * mato, g + (gr[1] - g) * mato, b + (gr[2] - b) * mato)


TEXTURES = {
    "dirt_road": _dirt_road,
}


def textured_material(mat, texture):
    """Gera (ou repinta) a imagem <material> e liga no primeiro slot como textura UV."""
    fn = TEXTURES.get(texture)
    if fn is None or mat is None:
        return mat
    name = mat.name
    img = bpy.data.images.get(name)
    if img is None or tuple(img.size) != (LADO, LADO):
        if img is not None:
            img.name = name + "_velho"
        img = bpy.data.images.new(name, LADO, LADO, alpha=False)
    px = [1.0] * (LADO * LADO * 4)
    for yy in range(LADO):
        for xx in range(LADO):
            c = fn(xx / LADO, yy / LADO)
            k = (yy * LADO + xx) * 4
            px[k], px[k + 1], px[k + 2] = c
    img.pixels = px
    _decor.store_image(img, name + ".png")
    mat.diffuse_color = (1, 1, 1)
    mat.specular_intensity = 0.02
    tex = bpy.data.textures.get(name)
    if tex is None or tex.type != 'IMAGE':
        tex = bpy.data.textures.new(name, 'IMAGE')
    tex.image = img
    slot = mat.texture_slots[0] if mat.texture_slots[0] else mat.texture_slots.add()
    slot.texture = tex
    slot.texture_coords = 'UV'
    return mat
