"""Explosive > Ground Mark: ready-made mark objects (scorch, burn, crack, wet stain) for the explosion styles."""
import bpy
import math
import random
from bpy.props import BoolProperty, EnumProperty

# Per style: color at the center, color at the edge, opacity, how much the edge is torn by rays/cracks.
MARK_STYLES = {
    'FIRE': ((0.02, 0.018, 0.015), (0.12, 0.09, 0.06), 0.95, 0.55),
    'ELECTRIC': ((0.02, 0.025, 0.04), (0.1, 0.13, 0.2), 0.9, 0.8),
    'CONCRETE': ((0.25, 0.24, 0.22), (0.45, 0.42, 0.38), 0.85, 0.35),
    'WATER': ((0.0, 0.0, 0.0), (0.02, 0.03, 0.04), 0.45, 0.15),
}
SIZE = 256


def _value_noise(seed, cells):
    """Smooth noise in 0..1 on a cells x cells grid that wraps."""
    rnd = random.Random(seed)
    grid = [[rnd.random() for _ in range(cells)] for _ in range(cells)]

    def sample(u, v):
        x, y = u * cells, v * cells
        x0, y0 = int(math.floor(x)), int(math.floor(y))
        fx, fy = x - x0, y - y0
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a = grid[y0 % cells][x0 % cells]
        b = grid[y0 % cells][(x0 + 1) % cells]
        c = grid[(y0 + 1) % cells][x0 % cells]
        d = grid[(y0 + 1) % cells][(x0 + 1) % cells]
        return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy
    return sample


def _mark_pixels(style):
    inner, outer, opacity, tear = MARK_STYLES[style]
    coarse = _value_noise(7, 6)
    fine = _value_noise(13, 24)
    rnd = random.Random(3)
    # Rays/cracks: a few angular frequencies with random phases.
    waves = [(rnd.randint(5, 17), rnd.random() * 6.283, rnd.random()) for _ in range(5)]
    pixels = [0.0] * (SIZE * SIZE * 4)
    for j in range(SIZE):
        v = j / (SIZE - 1)
        for i in range(SIZE):
            u = i / (SIZE - 1)
            dx, dy = u * 2 - 1, v * 2 - 1
            r = math.sqrt(dx * dx + dy * dy)
            angle = math.atan2(dy, dx)
            rays = sum(w * max(0.0, math.sin(angle * k + p)) ** 6 for k, p, w in waves) / 2.5
            n = coarse(u, v) * 0.65 + fine(u, v) * 0.35
            # Edge pushed out by the rays, torn by the noise.
            edge = 0.72 + tear * (rays * 0.25 + (n - 0.5) * 0.25)
            a = max(0.0, min(1.0, (edge - r) / 0.25))
            a = a * a * (3 - 2 * a) * opacity * (0.75 + 0.25 * n)
            if r >= 0.98:
                a = 0.0
            t = max(0.0, min(1.0, r / max(edge, 0.01)))
            k = (j * SIZE + i) * 4
            for c in range(3):
                pixels[k + c] = (inner[c] + (outer[c] - inner[c]) * t) * (0.8 + 0.4 * n)
            pixels[k + 3] = a
    return pixels


class OBJECT_OT_explosive_mark_add(bpy.types.Operator):
    """Make a Ground Mark object (in layer 20) for the explosion style and use it as the Mark"""
    bl_idname = "object.explosive_mark_add"
    bl_label = "New Ground Mark"
    bl_options = {'REGISTER', 'UNDO'}

    style: EnumProperty(name="Look", items=(
        ('FIRE', "Scorch", "Black burnt ground with rays"),
        ('ELECTRIC', "Burn", "Blue-black burn with long cracks"),
        ('CONCRETE', "Dust", "Grey dust and debris marks"),
        ('WATER', "Wet", "Dark wet stain"),
    ))
    destruction: BoolProperty(name="Destruction", description="Use it as the Ground Mark of the Destruction panel")

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        target = context.object
        scene = context.scene
        name = "ExplosionMark_" + self.style.title()

        image = bpy.data.images.new(name, SIZE, SIZE, alpha=True)
        image.pixels = _mark_pixels(self.style)
        image.pack(as_png=True)

        tex = bpy.data.textures.new(name, 'IMAGE')
        tex.image = image
        tex.extension = 'CLIP'

        mat = bpy.data.materials.new(name)
        mat.diffuse_color = (1.0, 1.0, 1.0)
        mat.specular_intensity = 0.0
        mat.use_transparency = True
        mat.transparency_method = 'Z_TRANSPARENCY'
        mat.alpha = 0.0
        mat.use_cast_shadows = False
        mat.game_settings.alpha_blend = 'ALPHA'
        slot = mat.texture_slots.add()
        slot.texture = tex
        slot.texture_coords = 'UV'
        slot.use_map_color_diffuse = True
        slot.use_map_alpha = True

        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
        mesh.uv_textures.new()
        mesh.update()
        mesh.materials.append(mat)
        ob = bpy.data.objects.new(name, mesh)
        ob.location = target.location
        ob.game.physics_type = 'NO_COLLISION'
        scene.objects.link(ob)
        # The Mark is a template: it must sit in a layer that isn't shown in the game.
        ob.layers = [i == 19 for i in range(20)]
        if scene.layers[19]:
            self.report({'WARNING'}, "Layer 20 is visible: hide it so the Mark template isn't drawn in the game")

        if self.destruction:
            target.game.destruction.fx.mark = ob
        else:
            target.game.explosive.mark = ob
        return {'FINISHED'}


classes = (
    OBJECT_OT_explosive_mark_add,
)
