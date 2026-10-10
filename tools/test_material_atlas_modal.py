"""Windowed native job test: early cancellation, late cancellation, failure and undo.

RangeEngine --factory-startup --python this_file -- --case cancel
Calls the same cancellation API used by Escape; no visual assertions.
"""
import os
import sys
import time
import traceback

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from test_material_atlas_integration import setup, check, maps, uvs

case = sys.argv[sys.argv.index('--case') + 1]


def cancel_late(scene):
    # Main-thread scene update during routing of the third pass, after two maps.
    if len([image for image in bpy.data.images if image.name.startswith('AnastacioAtlas_')]) >= 3:
        if bpy.ops.material.anastacio_atlas_cancel.poll():
            bpy.app.handlers.scene_update_post.remove(cancel_late)
            bpy.ops.material.anastacio_atlas_cancel()
            print('ANASTACIO_ATLAS_CANCEL_REQUESTED cancel-late', flush=True)


class ATLAS_OT_modal_test(bpy.types.Operator):
    bl_idname = 'wm.anastacio_atlas_modal_test'
    bl_label = 'Atlas modal test'

    def execute(self, context):
        scene, ob = setup()
        context.user_preferences.view.use_quit_dialog = False
        self.source_name = ob.data.name
        self.source_users = ob.data.users
        self.source_uv = uvs(ob, 'SourceUV')
        self.selection = {item.name: item.select for item in scene.objects}
        scene.cycles.samples = 13
        self.ids = (set(bpy.data.meshes.keys()), set(bpy.data.materials.keys()), set(bpy.data.images.keys()))
        self.material_users = {mat.name: mat.users for mat in bpy.data.materials}
        if case == 'error':
            mat = ob.data.materials[0]
            shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            math = mat.node_tree.nodes.new('ShaderNodeMath')
            math.inputs[0].default_value = 2
            mat.node_tree.links.new(math.outputs[0], shader.inputs['Metallic'])
        bpy.context.user_preferences.edit.use_global_undo = True
        bpy.ops.ed.undo_push(message='Atlas modal test baseline')
        self.timer = context.window_manager.event_timer_add(0.1, context.window)
        self.deadline = time.monotonic() + 90
        context.window_manager.modal_handler_add(self)
        if case == 'cancel-late':
            bpy.app.handlers.scene_update_post.append(cancel_late)
        result = bpy.ops.material.anastacio_atlas_bake('EXEC_DEFAULT', use_async=True,
                 resolution=512 if case.startswith('cancel') else 128,
                 samples=64 if case.startswith('cancel') else 1, margin=3)
        check(result == {'RUNNING_MODAL'}, 'Native atlas did not start a modal job')
        print('ANASTACIO_ATLAS_MODAL_STARTED ' + case, flush=True)
        if case == 'cancel':
            bpy.ops.material.anastacio_atlas_cancel()
            print('ANASTACIO_ATLAS_CANCEL_REQUESTED cancel', flush=True)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        try:
            # Only run checks once the atlas has unlocked the interface and poll.
            if not bpy.ops.material.anastacio_atlas_bake.poll():
                check(time.monotonic() < self.deadline, 'Native modal job did not terminate')
                return {'PASS_THROUGH'}
            ob = bpy.data.objects['IntegrationCube']
            scene = context.scene
            check(scene.render.engine == 'BLENDER_GAME' and scene.cycles.samples == 13 and
                  scene.cycles.device == 'CPU', 'Modal job did not restore render settings')
            check(self.selection == {item.name: item.select for item in scene.objects}, 'Selection changed')
            if case in ('cancel', 'cancel-late', 'error'):
                check(ob.data.name == self.source_name and ob.data.users == self.source_users,
                      'Cancelled job changed source mesh/users')
                check(self.ids == (set(bpy.data.meshes.keys()), set(bpy.data.materials.keys()),
                                   set(bpy.data.images.keys())), 'Cancelled job leaked IDs')
                check(self.material_users == {mat.name: mat.users for mat in bpy.data.materials},
                      'Cancelled job changed material users')
                check(uvs(ob, 'SourceUV') == self.source_uv and 'AnastacioAtlas' not in ob.data.uv_layers,
                      'Cancelled job changed original UVs')
            else:
                check(len(ob.data.materials) == 1 and len(maps(ob)) == 5, 'Async bake failed')
                check(all(image.packed_file for image in maps(ob).values()), 'Async maps not packed')
                image = maps(ob)['BaseColor']
                colors = [(0.7, 0.2, 0.1), (0.1, 0.5, 0.7)]
                for poly in ob.data.polygons:
                    coords = [ob.data.uv_layers['AnastacioAtlas'].data[i].uv for i in poly.loop_indices]
                    center = [sum(v[c] for v in coords)/len(coords) for c in range(2)]
                    x, y = [int(center[c]*image.size[c]) for c in range(2)]
                    offset = (y*image.size[0]+x)*4
                    check(max(abs(a-b) for a,b in zip(image.pixels[offset:offset+3],
                          colors[poly.index%2])) < 0.025, 'Async pixels differ')
                # Native operator completion pushes its own undo step, without a scripted push.
                check(bpy.ops.ed.undo() == {'FINISHED'}, 'Native completion Undo failed')
                ob = bpy.data.objects['IntegrationCube']
                check(len(ob.data.materials) == 2 and 'AnastacioAtlas' not in ob.data.uv_layers,
                      'Automatic undo step did not restore original mesh')
                check(bpy.ops.ed.redo() == {'FINISHED'}, 'Native completion Redo failed')
                ob = bpy.data.objects['IntegrationCube']
                check(len(maps(ob)) == 5 and ob.data.get('_anastacio_atlas_source'), 'Redo lost atlas backup')
            context.window_manager.event_timer_remove(self.timer)
            print('ANASTACIO_ATLAS_MODAL_PASS ' + case, flush=True)
            bpy.ops.wm.quit_blender()
            return {'FINISHED'}
        except Exception:
            traceback.print_exc()
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)


bpy.utils.register_class(ATLAS_OT_modal_test)
bpy.ops.wm.anastacio_atlas_modal_test()
