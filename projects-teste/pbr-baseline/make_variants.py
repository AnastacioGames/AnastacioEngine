# Diagnostico: esferas com nos diferentes, para achar qual quebra (branco) no runtime.
import bpy, math, os
here = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(here, "pbr_test_legacy.blend"))
for o in [o for o in bpy.data.objects if o.name.startswith("S_")]:
    bpy.data.objects.remove(o, True)

def node_mat(name, kind, **inputs):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    nt.links.new(n.outputs[0], out.inputs['Surface'])
    return m

col = (0.8, 0.35, 0.2, 1.0)
variants = [
    ("legado", None),
    ("diffuse", node_mat("v_diffuse", 'ShaderNodeBsdfDiffuse', Color=col)),
    ("glossy", node_mat("v_glossy", 'ShaderNodeBsdfGlossy', Color=col, Roughness=0.3)),
    ("emission", node_mat("v_emission", 'ShaderNodeEmission', Color=col)),
    ("principled", node_mat("v_principled", 'ShaderNodeBsdfPrincipled', **{'Base Color': col, 'Metallic': 0.0, 'Roughness': 0.5})),
]
for i, (name, mat) in enumerate(variants):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, size=0.45, location=((i - 2) * 1.1, 0, 0.9))
    o = bpy.context.object
    o.name = "S_" + name
    bpy.ops.object.shade_smooth()
    if mat is None:
        mat = bpy.data.materials.new("v_legado"); mat.diffuse_color = (0.8, 0.35, 0.2)
    o.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(here, "pbr_variants.blend"))
print("SALVO variants")
