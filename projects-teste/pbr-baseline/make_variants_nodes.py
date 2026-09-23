# Teste: registra um RenderEngine Python com bl_use_shading_nodes=True, escolhe-o na cena e salva.
import bpy, os
here = os.path.dirname(os.path.abspath(__file__))

class RangePBREngine(bpy.types.RenderEngine):
    bl_idname = "RANGE_PBR"
    bl_label = "Range PBR (teste)"
    bl_use_shading_nodes = True
    def render(self, scene):
        pass

bpy.utils.register_class(RangePBREngine)
bpy.ops.wm.open_mainfile(filepath=os.path.join(here, "pbr_variants.blend"))
bpy.context.scene.render.engine = "RANGE_PBR"
print("ENGINE", bpy.context.scene.render.engine)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(here, "pbr_variants_nodes.blend"))
