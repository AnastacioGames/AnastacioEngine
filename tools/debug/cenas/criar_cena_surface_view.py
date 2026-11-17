"""Cena de teste do surface(uv).view do nó GLSL @surface (plano-imposter-caixa.md, Etapa 1).

Plano de frente para a câmera (câmera em -Y olhando +Y). O nó pinta view*0.5+0.5: no centro da tela
a direção é ~(0,1,0) -> verde-claro (0.5, 1, 0.5); para a direita X cresce (mais vermelho), para cima
Z cresce (mais azul). Com Ortho ligado a tela inteira fica uniforme (0.5, 1, 0.5).

Uso (editor aberto, ex. por tools/testes_engine/controle.py py):
    exec(open(r"D:/AnastacioEngine/tools/debug/cenas/criar_cena_surface_view.py").read())
    montar(ortho=False)
"""
import bpy
from math import radians

CODIGO = """// @name Surface View Debug
// @surface

vec4 node(vec2 uv)
{
    return vec4(surface(uv).view * 0.5 + 0.5, 1.0);
}
"""


def montar(ortho=False):
    scene = bpy.context.scene
    for ob in list(scene.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    bpy.ops.mesh.primitive_plane_add(radius=2.0, location=(0, 0, 0), rotation=(radians(90), 0, 0))
    plano = bpy.context.object
    plano.name = "PlanoView"

    mat = bpy.data.materials.new("MatView")
    mat.use_nodes = True
    tree = mat.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
    saida = tree.nodes.new("ShaderNodeOutput")
    text = bpy.data.texts.get("surface_view.glsl") or bpy.data.texts.new("surface_view.glsl")
    text.from_string(CODIGO)
    node = tree.nodes.new("ShaderNodeGLSLScript")
    node.script = text
    tree.interface_update(bpy.context)
    tree.links.new(node.outputs[0], saida.inputs["Color"])
    plano.data.materials.append(mat)

    cam_data = bpy.data.cameras.new("CamView")
    cam_data.type = 'ORTHO' if ortho else 'PERSP'
    cam_data.ortho_scale = 5.0
    cam = bpy.data.objects.new("CamView", cam_data)
    scene.objects.link(cam)
    cam.location = (0, -5, 0)
    cam.rotation_euler = (radians(90), 0, 0)
    scene.camera = cam
    return node
