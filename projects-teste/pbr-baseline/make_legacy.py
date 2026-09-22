# Controle: mesma cena com materiais legados (sem nos), para separar falha do Principled de falha da captura.
import bpy, os
here = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(here, "pbr_test.blend"))
for m in bpy.data.materials:
    m.use_nodes = False
    m.diffuse_color = (0.8, 0.35, 0.2)
    m.specular_intensity = 0.5
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(here, "pbr_test_legacy.blend"))
