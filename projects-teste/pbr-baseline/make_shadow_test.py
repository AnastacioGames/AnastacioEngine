# Cena nova (nao reaproveita pbr_test.blend legado) para validar Lamps de cena
# (Sun com sombra + Spot com sombra + Point sem sombra) somadas ao IBL no
# BLENDER_GAME, com materiais Principled. Salva como .range para
# RangeRuntime.exe abrir direto.
#
# Uso: RangeEngine.exe -b --python make_shadow_test.py
#
# Nota sobre sombras (gpu_material.c ~L3997): neste engine so LA_SPOT
# (BUFFER_SHADOW ou RAY_SHADOW) e LA_SUN (RAY_SHADOW) geram shadow buffer
# GLSL. Point/LA_LOCAL nao tem shadow buffer implementado aqui -> nao espere
# sombra de Point light, e por isso o teste usa Sun + Spot para sombra.
import bpy, math, os

here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.render.engine = 'BLENDER_GAME'
scn.render.resolution_x = 1280
scn.render.resolution_y = 720

gs = scn.game_settings
gs.use_glsl_shaders = True
gs.use_glsl_nodes = True
gs.use_glsl_lights = True
gs.use_glsl_shadows = True
gs.use_glsl_extra_textures = True
gs.use_glsl_environment_lighting = True
gs.use_shading_nodes = True

scn.world = bpy.data.worlds.new("World")
scn.world.horizon_color = (0.35, 0.45, 0.6)
scn.world.zenith_color = (0.15, 0.25, 0.5)
scn.world.ambient_color = (0.05, 0.05, 0.05)


def principled(name, color, metallic, roughness):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out_n = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    nt.links.new(bsdf.outputs[0], out_n.inputs['Surface'])
    return m


# Chao grande para receber sombra.
bpy.ops.mesh.primitive_plane_add(radius=8, location=(0, 0, 0))
plane = bpy.context.object
plane.name = "Chao"
plane.data.materials.append(principled("Chao", (0.5, 0.5, 0.5, 1.0), 0.0, 0.8))

# Esferas espacadas para projetar sombra clara no chao.
for i, (metallic, roughness) in enumerate([(0.0, 0.3), (1.0, 0.2), (0.0, 0.7)]):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, size=0.6,
                                          location=((i - 1) * 2.2, 0, 0.6))
    o = bpy.context.object
    o.name = "S_%d" % i
    bpy.ops.object.shade_smooth()
    o.data.materials.append(principled(o.name, (0.8, 0.35, 0.2, 1.0), metallic, roughness))

# Sun: fonte principal de sombra (unico tipo com RAY_SHADOW valido para Sun).
bpy.ops.object.lamp_add(type='SUN', location=(4, -6, 8))
sun = bpy.context.object
sun.name = "Sun"
sun.rotation_euler = (math.radians(50), 0, math.radians(35))
sun.data.energy = 1.2
sun.data.use_shadow = True
sun.data.shadow_method = 'RAY_SHADOW'

# Spot: segunda fonte com sombra via shadow buffer (unico caminho de buffer
# shadow implementado neste engine para lamps nao-Sun).
bpy.ops.object.lamp_add(type='SPOT', location=(-3, -4, 5))
spot = bpy.context.object
spot.name = "SpotTest"
spot.data.energy = 2.0
spot.data.distance = 20.0
spot.data.spot_size = math.radians(60)
spot.data.use_shadow = True
spot.data.shadow_method = 'BUFFER_SHADOW'
spot.rotation_euler = (math.radians(35), 0, math.radians(-35))

# Point: contribuicao de luz local sem sombra (limitacao conhecida do engine).
bpy.ops.object.lamp_add(type='POINT', location=(2.5, -3.0, 2.5))
point = bpy.context.object
point.name = "PointTest"
point.data.energy = 1.2
point.data.distance = 12.0

bpy.ops.object.camera_add(location=(0, -9.5, 2.0), rotation=(math.radians(85), 0, 0))
cam = bpy.context.object
cam.name = "Camera"
scn.camera = cam

out = os.path.join(here, "shadow_ibl_test.range")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("SALVO", out)
print("sun.use_shadow", sun.data.use_shadow, sun.data.shadow_method)
print("spot.use_shadow", spot.data.use_shadow, spot.data.shadow_method)
print("ibl", gs.use_glsl_environment_lighting, "shadows", gs.use_glsl_shadows)
