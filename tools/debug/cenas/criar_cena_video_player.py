# Gera tools/debug/cenas/video_player/: teste.mp4 (H.264 + AAC, 4 s, renderizado aqui) e video_player.range
# com um plano tocando o video no material via componente Video Player.
# Uso: AnastacioEngine.exe -b --factory-startup -P tools/debug/cenas/criar_cena_video_player.py
import bpy, os, math, struct, wave

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_player")
os.makedirs(OUT, exist_ok=True)
FPS, SECONDS = 24, 4

def limpar():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

# --- 1) som: bipe a cada segundo -----------------------------------------
wav = os.path.join(OUT, "bipe.wav")
rate = 44100
with wave.open(wav, "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    data = bytearray()
    for i in range(rate * SECONDS):
        t = i / rate
        amp = 0.4 if (t % 1.0) < 0.15 else 0.0
        data += struct.pack("<h", int(32767 * amp * math.sin(2 * math.pi * 660 * t)))
    w.writeframes(bytes(data))

# --- 2) video: cubo girando com fundo mudando de cor ----------------------
scn = bpy.context.scene
scn.render.engine = 'BLENDER_RENDER'
limpar()
bpy.ops.mesh.primitive_cube_add()
cubo = bpy.context.object
mat = bpy.data.materials.new("Cubo"); mat.diffuse_color = (1.0, 0.6, 0.1); cubo.data.materials.append(mat)
bpy.ops.object.lamp_add(type='SUN', location=(2, -3, 5))
bpy.ops.object.camera_add(location=(0, -6, 2), rotation=(math.radians(75), 0, 0))
scn.camera = bpy.context.object
scn.frame_start, scn.frame_end = 1, FPS * SECONDS
scn.render.fps = FPS
scn.world = scn.world or bpy.data.worlds.new("W")
for f, cor in ((1, (0.1, 0.2, 0.8)), (FPS * 2, (0.8, 0.1, 0.3)), (FPS * SECONDS, (0.1, 0.7, 0.2))):
    scn.world.horizon_color = cor; scn.world.keyframe_insert("horizon_color", frame=f)
cubo.rotation_euler = (0, 0, 0); cubo.keyframe_insert("rotation_euler", frame=1)
cubo.rotation_euler = (math.radians(90), 0, math.radians(360)); cubo.keyframe_insert("rotation_euler", frame=FPS * SECONDS)
scn.sequence_editor_create()
scn.sequence_editor.sequences.new_sound("bipe", wav, 1, 1)
r = scn.render
r.resolution_x, r.resolution_y, r.resolution_percentage = 640, 360, 100
r.image_settings.file_format = 'FFMPEG'
r.ffmpeg.format = 'MPEG4'
r.ffmpeg.codec = 'H264'
r.ffmpeg.audio_codec = 'AAC'
mp4 = os.path.join(OUT, "teste.mp4")
r.filepath = mp4
r.use_file_extension = False
bpy.ops.render.render(animation=True)
print("video:", mp4, os.path.getsize(mp4))

# --- 3) cena do jogo ------------------------------------------------------
limpar()
scn.sequence_editor_clear()
scn.render.engine = 'BLENDER_GAME'
bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0), rotation=(math.radians(90), 0, 0))
tela = bpy.context.object
tela.name = "Tela"
tela.scale = (1.6, 0.9, 1)
# UV ja vem do plano; o material precisa de uma textura de imagem para o video substituir
mat = bpy.data.materials.new("Tela")
mat.use_shadeless = True
img = bpy.data.images.new("placeholder", 16, 16)
tex = bpy.data.textures.new("Tela", 'IMAGE'); tex.image = img
slot = mat.texture_slots.add(); slot.texture = tex; slot.texture_coords = 'UV'
tela.data.materials.append(mat)
bpy.ops.object.camera_add(location=(0, -4, 0), rotation=(math.radians(90), 0, 0))
scn.camera = bpy.context.object
scn.world.horizon_color = (0.05, 0.05, 0.05)
scn.world.animation_data_clear()

bpy.context.scene.objects.active = tela
tela.select = True
ov = bpy.context.copy(); ov.update(object=tela, active_object=tela)
bpy.ops.logic.python_component_register(ov, component_name="anastacio_video.VideoPlayer")
comp = next(c for c in tela.game.components if c.module == "anastacio_video")
comp.properties["File"].value = "//teste.mp4"
comp.properties["Material"].value = "Tela"
comp.properties["Loop"].value = True
# Controle so com Logic Bricks: Keyboard -> And -> Message (assuntos video_*)
TECLAS = (
    ("SPACE", "video_toggle", ""),
    ("S", "video_stop", ""),
    ("RIGHT_ARROW", "video_seek", "+2"),
    ("LEFT_ARROW", "video_seek", "-2"),
    ("HOME", "video_restart", ""),
)
for tecla, assunto, corpo in TECLAS:
    nome = tecla.lower()
    bpy.ops.logic.sensor_add(ov, type='KEYBOARD', name=nome, object=tela.name)
    bpy.ops.logic.controller_add(ov, type='LOGIC_AND', name=nome, object=tela.name)
    bpy.ops.logic.actuator_add(ov, type='MESSAGE', name=nome, object=tela.name)
    sens, ctrl, act = tela.game.sensors[-1], tela.game.controllers[-1], tela.game.actuators[-1]
    sens.key = tecla
    act.subject = assunto
    act.body_message = corpo
    sens.link(ctrl)
    act.link(ctrl)

# Ao terminar (Loop desligado) o player manda video_finished: aqui so imprime no console
bpy.ops.logic.sensor_add(ov, type='MESSAGE', name="fim", object=tela.name)
bpy.ops.logic.controller_add(ov, type='PYTHON', name="fim", object=tela.name)
sens, ctrl = tela.game.sensors[-1], tela.game.controllers[-1]
sens.subject = "video_finished"
txt = bpy.data.texts.new("fim_video.py")
txt.write("print('[video] video_finished recebido')\n")
ctrl.text = txt
sens.link(ctrl)

for s in list(bpy.data.sounds):
    bpy.data.sounds.remove(s)
dest = os.path.join(OUT, "video_player.range")
bpy.ops.wm.save_as_mainfile(filepath=dest)
os.remove(wav)
print("cena:", dest)
