# Inspecao em background da cena gerada por criar_cena_smart_node_choice.py.
# Uso: AnastacioEngine.exe -b cena.range --python inspecionar_cena_smart_node_choice.py -- evidencia.txt
import sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out_path = argv[0]

scene = bpy.context.scene
result = []
result.append("scene=%s engine=%s" % (scene.name, scene.render.engine))
result.append("camera=%s" % (scene.camera.name if scene.camera else "NONE"))
for object_name, expected_text, expected_link in (
        ("LegacyRaw", "choice_legacy_raw.glsl", False),
        ("ChoiceLocal", "choice_modes.glsl", False),
        ("ChoiceLinked", "choice_modes.glsl", True)):
    obj = scene.objects.get(object_name)
    if obj is None or not obj.data.materials:
        raise RuntimeError("object or material missing: %s" % object_name)
    nodes = obj.data.materials[0].node_tree.nodes
    script = next((node for node in nodes if node.bl_idname == "ShaderNodeGLSLScript"), None)
    if script is None or script.script is None:
        raise RuntimeError("GLSL Script missing: %s" % object_name)
    sock = script.inputs.get("u_mode")
    if sock is None:
        raise RuntimeError("u_mode missing: %s" % object_name)
    if script.script.name != expected_text or bool(sock.is_linked) != expected_link:
        raise RuntimeError("unexpected script/link on %s" % object_name)
    result.append("%s text=%s value=%s linked=%s" %
                  (object_name, script.script.name, sock.default_value, sock.is_linked))

with open(out_path, "w") as handle:
    handle.write("\n".join(result) + "\n")

