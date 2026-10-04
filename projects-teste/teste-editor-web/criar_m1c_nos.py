"""Gera m1c-nos-<modo>.range: cubo com material de NÓS (Shading Nodes) cujo shader gerado falha no Web.
Uso: RangeEngine.exe -b --python criar_m1c_nos.py [-- fragment|vertex|link]   (padrão: fragment; grava ao lado
deste arquivo).

A falha entra pelo GLSL de usuário do material (`Material.script_frag`/`script_vert`, painel Shading > Shader
Sources). `gpu_material_construct_end` passa esses Texts a `GPU_generate_pass`, que os acrescenta ao fragment e
ao vertex GERADOS a partir do grafo de nós (`code_generate_fragment`/`code_generate_vertex` em gpu_codegen.c).
Não há controller Python: a falha acontece ao converter o material no carregamento da cena, e a origem esperada
no relatório é o nome do ID, `MAMatNosQuebrado`.
- fragment: script_frag com sintaxe inválida -> operation "compile", stage "fragment";
- vertex: script_vert com sintaxe inválida -> operation "compile", stage "vertex";
- link: os dois estágios compilam, mas declaram o mesmo varying com tipos diferentes -> operation "link",
  stage "". O fragment() do usuário não é chamado em material de nós (só o caminho BI liga `user_get`), então
  o varying do fragment pode ser considerado sem uso estático; se o navegador não reprovar o link, anote isso.
"""
import os
import sys

import bpy

MODOS = ("fragment", "vertex", "link")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODO = argv[0] if argv else "fragment"
if MODO not in MODOS:
    raise SystemExit("modo desconhecido %r; use um de %s" % (MODO, ", ".join(MODOS)))

FRAG_INVALIDO = """
void fragment() {
    vec4 m1c_quebrado = ;   // sintaxe invalida de proposito
}
"""

VERT_INVALIDO = """
void vertex() {
    VERTEX = VERTEX +;   // sintaxe invalida de proposito
}
"""

# Link: cada estágio é válido sozinho; o varying m1c_conflito é vec4 no vertex e vec3 no fragment.
VERT_LINK = """
out vec4 m1c_conflito;
void vertex() {
    m1c_conflito = vec4(VERTEX, 1.0);
}
"""

FRAG_LINK = """
in vec3 m1c_conflito;
void fragment() {
    vec3 m1c_uso = m1c_conflito;
}
"""

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "m1c-nos-%s.range" % MODO)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'
scene.game_settings.use_shading_nodes = True
scene.game_settings.use_glsl_lights = True

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
scene.objects.link(cam)
cam.location = (0, -6, 2)
cam.rotation_euler = (1.3, 0, 0)
scene.camera = cam
sun = bpy.data.objects.new('Sun', bpy.data.lamps.new('Sun', 'SUN'))
scene.objects.link(sun)

me = bpy.data.meshes.new('Cubo')
me.from_pydata([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], [],
               [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
me.uv_textures.new('UVMap')
me.update()

# Grafo real (Image Texture -> Diffuse BSDF -> Material Output), para o shader sair do codegen de nós.
mat = bpy.data.materials.new('MatNosQuebrado')
mat.use_nodes = True
tree = mat.node_tree
img = bpy.data.images.new('m1c_xadrez', 8, 8)
img.generated_type = 'UV_GRID'
tex = tree.nodes.new('ShaderNodeTexImage')
tex.image = img
tree.links.new(tex.outputs['Color'], tree.nodes['Diffuse BSDF'].inputs['Color'])

if MODO == 'fragment':
    mat.script_frag = bpy.data.texts.new('m1c_frag_invalido.glsl')
    mat.script_frag.write(FRAG_INVALIDO)
elif MODO == 'vertex':
    mat.script_vert = bpy.data.texts.new('m1c_vert_invalido.glsl')
    mat.script_vert.write(VERT_INVALIDO)
else:
    mat.script_vert = bpy.data.texts.new('m1c_vert_link.glsl')
    mat.script_vert.write(VERT_LINK)
    mat.script_frag = bpy.data.texts.new('m1c_frag_link.glsl')
    mat.script_frag.write(FRAG_LINK)

me.materials.append(mat)
ob = bpy.data.objects.new('Cubo', me)
scene.objects.link(ob)
scene.objects.active = ob

bpy.ops.wm.save_as_mainfile(filepath=out)
print("gravado", out, "modo", MODO)
