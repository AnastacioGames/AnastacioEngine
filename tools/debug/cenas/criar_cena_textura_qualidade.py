# Cena de teste de Range.render.setTextureQuality, filtros de mipmap/anisotropia sem recarga e
# light.shadowMapSize: plano com textura 1024x1024 (PNG ao lado do .range), sol com sombra de 2048
# e um script que mede pelo OpenGL o tamanho da textura, os filtros e o mapa de sombra, grava em
# RANGE_TEXQ_OUT (padrao: texq.txt ao lado do .range) e fecha o jogo.
#   AnastacioEngine.exe -b --factory-startup --python criar_cena_textura_qualidade.py -- saida.range
import bpy
import os
import sys
from mathutils import Vector

out = sys.argv[sys.argv.index('--') + 1]
out_dir = os.path.dirname(os.path.abspath(out))
scene = bpy.context.scene
for ob in list(scene.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = False

# Textura xadrez 1024x1024 salva em PNG: imagem de arquivo como num jogo real.
size = 1024
img = bpy.data.images.new('xadrez', size, size)
px = []
for y in range(size):
    for x in range(size):
        on = ((x // 64) + (y // 64)) % 2
        px.extend((0.9, 0.5, 0.1, 1.0) if on else (0.1, 0.2, 0.8, 1.0))
img.pixels = px
png = os.path.join(out_dir, 'xadrez.png')
img.filepath_raw = png
img.file_format = 'PNG'
img.save()
img = bpy.data.images.load(png)

tex = bpy.data.textures.new('xadrez', 'IMAGE')
tex.image = img
mat = bpy.data.materials.new('chao_xadrez')
slot = mat.texture_slots.add()
slot.texture = tex
slot.texture_coords = 'UV'

mat_cubo = bpy.data.materials.new('cubo')
mat_cubo.diffuse_color = (0.1, 0.8, 0.2)

bpy.ops.mesh.primitive_plane_add(radius=10, location=(0, 0, 0))
plano = scene.objects.active
plano.name = 'plano'
plano.data.materials.append(mat)
bpy.ops.mesh.uv_texture_add()

bpy.ops.mesh.primitive_cube_add(radius=1, location=(0, 0, 1))
scene.objects.active.data.materials.append(mat_cubo)

lamp = bpy.data.lamps.new('sol', 'SUN')
lamp.use_shadow = True
lamp.shadow_method = 'RAY_SHADOW'
lamp.shadow_buffer_size = 2048
sol = bpy.data.objects.new('sol', lamp)
sol.location = (6, -6, 10)
scene.objects.link(sol)
sol.rotation_euler = (-Vector(sol.location)).to_track_quat('-Z', 'Y').to_euler()

cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
cam.location = (0, -14, 9)
cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 16
scene.objects.link(cam)
scene.camera = cam

world = bpy.data.worlds.new('mundo')
world.mist_settings.use_mist = False
scene.world = world

codigo = r'''
import os
import bgl
import Range

GL_TEXTURE_MIN_FILTER = 0x2801
GL_TEXTURE_MAG_FILTER = 0x2800
GL_TEXTURE_MAX_ANISOTROPY = 0x84FE

state = {"frame": 0, "lines": []}


def log(msg):
    state["lines"].append(msg)


def tex_info():
    plano = Range.logic.getCurrentScene().objects["plano"]
    t = plano.meshes[0].materials[0].textures[0]
    buf = bgl.Buffer(bgl.GL_INT, 1)
    fbuf = bgl.Buffer(bgl.GL_FLOAT, 1)
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, t.bindCode)
    bgl.glGetTexLevelParameteriv(bgl.GL_TEXTURE_2D, 0, bgl.GL_TEXTURE_WIDTH, buf)
    w = buf[0]
    bgl.glGetTexParameteriv(bgl.GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, buf)
    mn = buf[0]
    bgl.glGetTexParameteriv(bgl.GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, buf)
    mg = buf[0]
    bgl.glGetTexParameterfv(bgl.GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY, fbuf)
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)
    return "bind=%d w=%d min=0x%04x mag=0x%04x aniso=%.0f" % (t.bindCode, w, mn, mg, fbuf[0])


def sol():
    return Range.logic.getCurrentScene().objects["sol"]


def tick(cont):
    f = state["frame"]
    state["frame"] = f + 1
    r = Range.render
    if f == 5:
        log("inicio quality=%d aniso=%d mip=%d | %s" % (r.getTextureQuality(), r.getAnisotropicFiltering(), r.getMipmapping(), tex_info()))
        log("sombra inicial=%d" % sol().shadowMapSize)
        r.setTextureQuality(1)
    elif f == 10:
        log("quality=1 | %s" % tex_info())
        r.setTextureQuality(2)
    elif f == 15:
        log("quality=2 | %s" % tex_info())
        r.setTextureQuality(0)
    elif f == 20:
        log("quality=0 | %s" % tex_info())
        r.setAnisotropicFiltering(16)
        log("aniso16 mesmo frame (sem recarga) | %s" % tex_info())
        r.setMipmapping(r.RAS_MIPMAP_NEAREST)
        log("mip nearest | %s" % tex_info())
        r.setMipmapping(r.RAS_MIPMAP_NONE)
        log("mip none | %s" % tex_info())
        r.setMipmapping(r.RAS_MIPMAP_LINEAR)
    elif f == 25:
        log("mip linear (recarregou) | %s" % tex_info())
        sol().shadowMapSize = 512
        log("sombra apos set 512=%d" % sol().shadowMapSize)
        r.setGLSLMaterialSetting("shadows", 0)
        r.setGLSLMaterialSetting("shadows", 1)
    elif f == 30:
        log("sombra apos recriar lampada=%d" % sol().shadowMapSize)
        sol().shadowMapSize = 1024
        log("sombra apos set 1024=%d" % sol().shadowMapSize)
    elif f == 35:
        path = os.environ.get("RANGE_TEXQ_OUT") or Range.logic.expandPath("//texq.txt")
        with open(path, "w") as fh:
            fh.write("\n".join(state["lines"]) + "\n# fim\n")
        Range.logic.endGame()
'''
txt = bpy.data.texts.new('texq.py')
txt.write(codigo)

scene.objects.active = cam
bpy.ops.logic.sensor_add(type='ALWAYS', object=cam.name)
bpy.ops.logic.controller_add(type='PYTHON', object=cam.name)
sens = cam.game.sensors[-1]
sens.use_pulse_true_level = True
ctrl = cam.game.controllers[-1]
ctrl.mode = 'MODULE'
ctrl.module = 'texq.tick'
sens.link(ctrl)

scene.render.resolution_x = 960
scene.render.resolution_y = 540
bpy.ops.wm.save_as_mainfile(filepath=out)
