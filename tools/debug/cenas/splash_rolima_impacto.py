"""Configura raio localizado e template de explosao na copia do splash."""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def setup(scene):
    for name in ('Splash_Raio_Impacto', 'Splash_Impacto_Alvo', 'Splash_Explosao_Template'):
        old = scene.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
    road = scene.objects['Cenario_Road_Parte1.004']
    surface = BVHTree.FromPolygons([v.co for v in road.data.vertices],
                                   [p.vertices for p in road.data.polygons])
    point, _, _, _ = surface.ray_cast(road.matrix_world.inverted() * Vector((0, 9, 100)),
                                     road.matrix_world.inverted().to_3x3() * Vector((0, 0, -1)))
    assert point is not None, 'Impacto fora do asfalto'
    position = road.matrix_world * point + Vector((0, 0, 0.06))
    target = bpy.data.objects.new('Splash_Impacto_Alvo', None)
    scene.objects.link(target)
    target.location = position
    emitter = bpy.data.objects.new('Splash_Raio_Impacto', None)
    scene.objects.link(emitter)
    emitter.location = position + Vector((0, 0, 14))
    emitter.empty_draw_size = 0.01
    emitter.use_lightning = True
    lightning = emitter.lightning
    lightning.mode = 'MANUAL'
    lightning.target = target
    lightning.height = 14
    lightning.use_hit_ground = False
    lightning.use_sound = False
    lightning.big_chance = 1.0
    lightning.intensity = 1.2
    lightning.width = 0.6
    lightning.color = (0.45, 0.65, 1.0)
    lightning.flash_distance = 100
    scene.world.weather_settings.rain_lightning_rate = 0

    mesh = bpy.data.meshes.new('Splash_Impacto_Template')
    mesh.from_pydata([(-0.03,-0.03,0), (0.03,-0.03,0), (0,0.03,0), (0,0,0.06)],
                     [], [(0,1,2), (0,3,1), (1,3,2), (2,3,0)])
    mesh.update()
    material = bpy.data.materials.new('Splash_Impacto_Invisivel')
    mesh.materials.append(material)
    bomb = bpy.data.objects.new('Splash_Explosao_Template', mesh)
    scene.objects.link(bomb)
    bomb.location = position
    bomb.layers = [i == 19 for i in range(20)]
    bomb.hide_render = True
    bomb.game.physics_type = 'NO_COLLISION'
    bomb.game.use_explosive = True
    ex = bomb.game.explosive
    ex.fuse = 0
    ex.force = 0
    ex.radius = 2
    ex.use_explode_on_impact = False
    ex.use_chain_reaction = False
    ex.use_particle_explosion = True
    ex.particle_style = 'FIRE'
    ex.particle_size = 'SMALL'
    ex.use_light_flash = True
    ex.use_ground_mark = False
    ex.smoke_duration = 3
    return emitter
