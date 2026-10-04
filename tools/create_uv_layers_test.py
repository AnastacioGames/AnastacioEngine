"""Multiple UV maps test (tangents per UV map, transformUV).

Run with:  RangeEngine -b --python tools/create_uv_layers_test.py -- <output.range>
Then:      RangeRuntime <output.range>

Two planes with identical geometry and two UV maps: "UVMap" (u along +X, active) and "UV2" (u along +Y).
- PlaneUV2: Normal Map node with UV Map = "UV2" -> tangents must follow +Y.
- PlaneActive: Normal Map node with empty UV Map -> tangents follow the active map, +X.
Same geometry on both also checks the loop data cache keeps them apart.
The game script checks the tangents and mesh.transformUV() and prints UV_LAYERS_TEST ok/FAIL, then quits.
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
output = argv[0] if argv else "uv_layers_test.range"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_GAME'


def link(ob):
    scene.objects.link(ob)
    ob.layers = [i == 0 for i in range(20)]
    return ob


def normal_map_material(name, uv_map):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    for node in list(tree.nodes):
        tree.nodes.remove(node)
    out = tree.nodes.new('ShaderNodeOutput')
    shade = tree.nodes.new('ShaderNodeMaterial')
    shade.material = bpy.data.materials.new(name + "Base")
    nmap = tree.nodes.new('ShaderNodeNormalMap')
    nmap.space = 'TANGENT'
    nmap.uv_map = uv_map
    nmap.inputs['Color'].default_value = (0.8, 0.5, 1.0, 1.0)
    tree.links.new(nmap.outputs['Normal'], shade.inputs['Normal'])
    tree.links.new(shade.outputs['Color'], out.inputs['Color'])
    return mat


def plane(name, x, uv_map):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [], [(0, 1, 2, 3)])
    me.update()
    uv1 = me.uv_textures.new("UVMap")
    uv2 = me.uv_textures.new("UV2")
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        me.uv_layers["UVMap"].data[loop.index].uv = (co.x * 0.5 + 0.5, co.y * 0.5 + 0.5)
        me.uv_layers["UV2"].data[loop.index].uv = (co.y * 0.5 + 0.5, -co.x * 0.5 + 0.5)
    me.uv_textures.active = uv1
    me.materials.append(normal_map_material(name + "Mat", uv_map))
    ob = link(bpy.data.objects.new(name, me))
    ob.location = (x, 0, 0)
    return ob


plane("PlaneUV2", -1.5, "UV2")
plane("PlaneActive", 1.5, "")

lamp = link(bpy.data.objects.new("Sun", bpy.data.lamps.new("Sun", 'SUN')))
lamp.location = (0, 0, 5)

text = bpy.data.texts.new("check.py")
text.write('''
from bge import logic
import mathutils

own = logic.getCurrentController().owner
own['frames'] = own.get('frames', 0) + 1
log = []


def report(line):
    print(line)
    log.append(line)


def run():
    scene = logic.getCurrentScene()
    errors = []

    def tangent_axis(name):
        mesh = scene.objects[name].meshes[0]
        axes = set()
        for i in range(mesh.getVertexArrayLength(0)):
            t = mesh.getVertex(0, i).tangent
            axes.add('X' if abs(t[0]) > 0.9 else 'Y' if abs(t[1]) > 0.9 else 'other %s' % (tuple(round(c, 2) for c in t),))
        return axes

    for name, expected in (('PlaneUV2', {'Y'}), ('PlaneActive', {'X'})):
        axes = tangent_axis(name)
        report('UV_LAYERS_TEST %s tangents %s (expected %s)' % (name, sorted(axes), sorted(expected)))
        if axes != expected:
            errors.append(name + ' tangents')

    mesh = scene.objects['PlaneActive'].meshes[0]
    ident = mathutils.Matrix.Identity(4)
    for args in ((0, ident, 8), (0, ident, 0, 8)):
        try:
            mesh.transformUV(*args)
            errors.append('transformUV%s accepted' % (args[2:],))
        except ValueError:
            pass
    mesh.transformUV(0, ident, -1, 1)  # Copy without single destination: ignored, used to write layer -1.
    mesh.transformUV(0, ident, 1, 0)   # Copy UVMap into UV2.
    for i in range(mesh.getVertexArrayLength(0)):
        vertex = mesh.getVertex(0, i)
        uvs = vertex.uvs
        if (uvs[0] - uvs[1]).length > 1e-5:
            errors.append('transformUV copy')
            break

    report('UV_LAYERS_TEST ' + ('ok' if not errors else 'FAIL ' + ', '.join(errors)))


if own['frames'] == 5:
    try:
        run()
    except Exception:
        import traceback
        report('UV_LAYERS_TEST FAIL exception ' + traceback.format_exc())
    with open(logic.expandPath('//uv_layers_test.log'), 'w') as f:
        f.write('\\n'.join(log) + '\\n')
    logic.endGame()
''')
bpy.context.scene.objects.active = lamp
bpy.ops.logic.sensor_add(type='ALWAYS', object=lamp.name)
bpy.ops.logic.controller_add(type='PYTHON', object=lamp.name)
sens = lamp.game.sensors[-1]
sens.use_pulse_true_level = True
cont = lamp.game.controllers[-1]
cont.text = text
sens.link(cont)

cam = link(bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")))
cam.location = (0, 0, 6)
scene.camera = cam

scene.layers = [i == 0 for i in range(20)]
bpy.ops.wm.save_as_mainfile(filepath=output)
print("UV_LAYERS_TEST saved", output)
