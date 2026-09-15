bl_info = {
    "name": "Automate Atlas Bake (UPBGE / Range Engine)",
    "author": "AnastacioGames & Gemini AI",
    "version": (1, 3),
    "blender": (2, 79, 0),
    "location": "Properties > Material > Automate Atlas Bake",
    "description": "Automates UV unwrap and texture baking using Blender Render for UPBGE and Range Engine.",
    "category": "Object",
}

import bpy
import os
import time
from bpy.props import IntProperty, StringProperty, EnumProperty, BoolProperty, FloatProperty

# ==============================================================================
# UTILITÁRIOS
# ==============================================================================
def ensure_bake_texture_slots(obj, uv_name):
    """Garante que todo material do objeto tenha ao menos um texture slot de
    Image ativo, mapeado pela UV do atlas. Sem isso o Blender Internal falha
    ao fazer bake (não sabe de onde tirar a cor difusa / onde escrever)."""
    if not obj.data.materials:
        mat = bpy.data.materials.new(name=obj.name + "_AtlasMat")
        obj.data.materials.append(mat)

    for mat in obj.data.materials:
        if mat is None:
            continue

        has_image_slot = any(
            slot and slot.texture and slot.texture.type == 'IMAGE'
            for slot in mat.texture_slots
        )
        if has_image_slot:
            continue

        tex = bpy.data.textures.new(name=mat.name + "_AtlasTex", type='IMAGE')
        slot = mat.texture_slots.add()
        slot.texture = tex
        slot.texture_coords = 'UV'
        slot.uv_layer = uv_name
        slot.use_map_color_diffuse = True

# ==============================================================================
# OPERADOR PRINCIPAL
# ==============================================================================
class OBJECT_OT_upbge_atlas_bake(bpy.types.Operator):
    """Executes automatic baking using Blender Render for UPBGE / Range Engine"""
    bl_idname = "object.upbge_atlas_bake"
    bl_label = "Execute Bake"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        
        # Lendo os valores diretamente da cena (Forma mais segura no 2.79)
        bake_res = int(scene.upbge_atlas_res)
        new_uv_name = str(scene.upbge_atlas_uv)
        image_name = str(scene.upbge_atlas_img)
        unwrap_type = scene.upbge_atlas_unwrap
        uv_margin = scene.upbge_atlas_uv_margin
        bake_mode = scene.upbge_atlas_bake_mode
        
        bake_diffuse = scene.upbge_atlas_bake_diffuse
        bake_ao = scene.upbge_atlas_bake_ao
        bake_normal = scene.upbge_atlas_bake_normal
        bake_specular = scene.upbge_atlas_bake_specular
        bake_alpha = scene.upbge_atlas_bake_alpha
        bake_combined = scene.upbge_atlas_bake_combined
        
        if not any([bake_diffuse, bake_ao, bake_normal, bake_specular, bake_alpha, bake_combined]):
            self.report({'ERROR'}, "Please select at least one map to bake (Diffuse/Full, AO, Normal, Specular, Alpha, or Combined).")
            return {'CANCELLED'}

        margin = scene.upbge_atlas_margin
        ao_samples = scene.upbge_atlas_ao_samples
        auto_save = scene.upbge_atlas_auto_save
        ao_strength = scene.upbge_atlas_ao_strength

        obj = context.active_object

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select an active MESH object before running the script.")
            return {'CANCELLED'}

        self.report({'INFO'}, "Preparing Bake for: " + obj.name)

        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        # 1. Usa o motor padrão da UPBGE e Range Engine (Blender Render) só durante o bake
        original_engine = scene.render.engine
        scene.render.engine = 'BLENDER_RENDER'

        world = context.scene.world
        original_use_ao = world.light_settings.use_ambient_occlusion if world else None
        original_ao_samples = world.light_settings.samples if world else None

        try:
            # 2. Criar novo UV Map
            uv_texture_names = [uv.name for uv in obj.data.uv_textures]
            if new_uv_name not in uv_texture_names:
                obj.data.uv_textures.new(name=new_uv_name)

            for uv in obj.data.uv_textures:
                is_target = (uv.name == new_uv_name)
                uv.active = is_target
                uv.active_render = is_target

            # 3. Fazer o Unwrap (De acordo com a escolha do usuário)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')

            if unwrap_type == 'SMART':
                bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=uv_margin)
            elif unwrap_type == 'LIGHTMAP':
                bpy.ops.uv.lightmap_pack(PREF_CONTEXT='ALL_FACES', PREF_MARGIN_DIV=uv_margin)
            elif unwrap_type == 'UNWRAP':
                bpy.ops.uv.unwrap(margin=uv_margin)
            bpy.ops.object.mode_set(mode='OBJECT')

            # 3.5. Garante material + texture slot de Image antes do bake
            ensure_bake_texture_slots(obj, new_uv_name)

            # 4. Configurações gerais e de AO
            scene.render.bake_margin = margin
            scene.render.use_bake_selected_to_active = False
            uv_layer = obj.data.uv_textures[new_uv_name]

            if bake_ao or bake_combined or bake_mode == 'FULL':
                if world:
                    world.light_settings.use_ambient_occlusion = True
                    world.light_settings.samples = ao_samples

            # Se o modo Combinado estiver ativo, forçamos o Bake do Diffuse e AO
            if bake_combined:
                bake_diffuse = True
                bake_ao = True

            # 5. Dicionário de tarefas (Bakes selecionados)
            bake_tasks = {}
            if bake_diffuse:
                bake_tasks[bake_mode] = image_name + ("_Full" if bake_mode == 'FULL' else "_Diffuse")
            if bake_ao:
                bake_tasks['AO'] = image_name + "_AO"
            if bake_normal:
                bake_tasks['NORMALS'] = image_name + "_Normal"
            if bake_specular:
                bake_tasks['SPEC_COLOR'] = image_name + "_Specular"
            if bake_alpha:
                bake_tasks['ALPHA'] = image_name + "_Alpha"

            total_tasks = len(bake_tasks) + (1 if bake_combined else 0)
            current_task = 0

            if total_tasks > 0:
                context.window_manager.progress_begin(0, total_tasks)

            # 6. Executar Bakes em sequência
            for b_type, img_name in bake_tasks.items():
                self.report({'INFO'}, "Starting Bake for " + b_type + "...")
                print("Starting Bake for " + b_type + "...")

                if img_name in bpy.data.images:
                    img = bpy.data.images[img_name]
                    if img.size[0] != bake_res or img.size[1] != bake_res:
                        img.scale(bake_res, bake_res)
                else:
                    use_alpha = (b_type == 'ALPHA')
                    img = bpy.data.images.new(img_name, width=bake_res, height=bake_res, alpha=use_alpha)

                for poly in uv_layer.data:
                    poly.image = img

                scene.render.bake_type = b_type
                if b_type == 'NORMALS':
                    scene.render.bake_normal_space = 'TANGENT'

                try:
                    start_time = time.time()
                    bpy.ops.object.bake_image()
                    duration = time.time() - start_time

                    msg = "Bake completed in " + str(round(duration, 2)) + "s! Image '" + img_name + "' generated."
                    self.report({'INFO'}, msg)
                    print(msg)

                    # Aplica a força do AO diretamente na textura de AO gerada
                    if b_type == 'AO':
                        p_o = list(img.pixels)
                        for i in range(0, len(p_o), 4):
                            p_o[i]   = 1.0 - (1.0 - p_o[i]) * ao_strength
                            p_o[i+1] = 1.0 - (1.0 - p_o[i+1]) * ao_strength
                            p_o[i+2] = 1.0 - (1.0 - p_o[i+2]) * ao_strength
                        img.pixels = p_o

                    # Salvar automaticamente se ativado
                    if auto_save:
                        blend_path = bpy.data.filepath
                        if blend_path:
                            save_dir = os.path.dirname(blend_path)
                            save_path = os.path.join(save_dir, img_name + ".png")
                            img.filepath_raw = save_path
                            img.file_format = 'PNG'
                            img.save()
                        else:
                            self.report({'WARNING'}, "Blend file not saved! Cannot auto-save " + img_name)
                except Exception as e:
                    self.report({'ERROR'}, "Error during " + b_type + " bake: " + str(e))
                    print("Error during " + b_type + " bake: " + str(e))

                current_task += 1
                if total_tasks > 0:
                    context.window_manager.progress_update(current_task)

            # 7. Gerar textura combinada (Mix Matemático de Pixels)
            if bake_combined:
                self.report({'INFO'}, "Merging textures (Diffuse + AO + Alpha)...")
                print("Merging textures (Diffuse + AO + Alpha)...")
                start_time = time.time()
                img_d = bpy.data.images.get(image_name + ("_Full" if bake_mode == 'FULL' else "_Diffuse"))
                img_o = bpy.data.images.get(image_name + "_AO")
                img_a = bpy.data.images.get(image_name + "_Alpha") if bake_alpha else None

                if img_d and img_o and len(img_d.pixels) == len(img_o.pixels):
                    comb_name = image_name + "_Combined"
                    if comb_name in bpy.data.images:
                        img_c = bpy.data.images[comb_name]
                        if img_c.size[0] != bake_res or img_c.size[1] != bake_res:
                            img_c.scale(bake_res, bake_res)
                    else:
                        img_c = bpy.data.images.new(comb_name, width=bake_res, height=bake_res, alpha=True)

                    # Convertendo para lista Python nativa (muito mais rápido para processar)
                    p_d = list(img_d.pixels)
                    p_o = list(img_o.pixels)
                    p_a = list(img_a.pixels) if img_a else None

                    for i in range(0, len(p_d), 4):
                        ao = p_o[i]          # O canal Vermelho (R) do AO (Já com a força aplicada)

                        p_d[i]   *= ao       # Multiplica a cor Vermelha do Diffuse
                        p_d[i+1] *= ao       # Multiplica a cor Verde do Diffuse
                        p_d[i+2] *= ao       # Multiplica a cor Azul do Diffuse
                        p_d[i+3] = p_a[i] if p_a else 1.0 # Injeta o Alpha se existir

                    img_c.pixels = p_d
                    duration = time.time() - start_time
                    msg = "Combined Texture '" + comb_name + "' generated successfully in " + str(round(duration, 2)) + "s!"
                    self.report({'INFO'}, msg)
                    print(msg)

                    # Salvar a combinada
                    if auto_save:
                        blend_path = bpy.data.filepath
                        if blend_path:
                            save_dir = os.path.dirname(blend_path)
                            save_path = os.path.join(save_dir, comb_name + ".png")
                            img_c.filepath_raw = save_path
                            img_c.file_format = 'PNG'
                            img_c.save()

                current_task += 1
                if total_tasks > 0:
                    context.window_manager.progress_update(current_task)

            if total_tasks > 0:
                context.window_manager.progress_end()

            self.report({'INFO'}, "Baking process finished successfully!")
            print("=== Baking process finished successfully! ===")

            return {'FINISHED'}
        finally:
            # 8. Restaura o motor de render e as configurações de AO do world,
            # mesmo se algo acima lançar uma exceção não tratada.
            scene.render.engine = original_engine
            if world:
                world.light_settings.use_ambient_occlusion = original_use_ao
                world.light_settings.samples = original_ao_samples


# ==============================================================================
# MENU DE RESOLUÇÕES (PRESETS)
# ==============================================================================
class VIEW3D_MT_atlas_res_menu(bpy.types.Menu):
    bl_label = "Texture Resolution Presets"
    bl_idname = "VIEW3D_MT_atlas_res_menu"
    
    def draw(self, context):
        layout = self.layout
        resolutions = [
            ("16 x 16", 16), ("32 x 32", 32), ("64 x 64", 64),
            ("128 x 128", 128), ("256 x 256", 256), ("512 x 512", 512),
            ("1024 x 1024", 1024), ("2048 x 2048", 2048)
        ]
        for name, res_val in resolutions:
            op = layout.operator("wm.context_set_int", text=name)
            op.data_path = "scene.upbge_atlas_res"
            op.value = res_val
            
        layout.separator()
        layout.label(text="Custom Resolution:")
        layout.prop(context.scene, "upbge_atlas_res", text="Size")

# ==============================================================================
# PAINEL DE INTERFACE
# ==============================================================================
class MATERIAL_PT_upbge_atlas_bake(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_label = "Automate Atlas Bake"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # 1. Output Settings Group (Configurações de Saída)
        layout.label(text="Output Settings:")
        box_out = layout.box()
        
        split = box_out.split(factor=0.35)
        split.label(text="Resolution:")
        row_res = split.row(align=True)
        row_res.prop(scene, "upbge_atlas_res", text="")
        row_res.menu(VIEW3D_MT_atlas_res_menu.bl_idname, icon='DOWNARROW_HLT', text="")
        
        split = box_out.split(factor=0.35)
        split.label(text="Image Name:")
        split.prop(scene, "upbge_atlas_img", text="")
        
        split = box_out.split(factor=0.35)
        split.label(text="UV Name:")
        split.prop(scene, "upbge_atlas_uv", text="")
        
        layout.separator()
        
        # 2. Bake Settings Group (Configurações de Bake)
        layout.label(text="Bake Settings:")
        box_bake = layout.box()
        
        split = box_bake.split(factor=0.35)
        split.label(text="Bake Mode:")
        split.prop(scene, "upbge_atlas_bake_mode", text="")
        
        split = box_bake.split(factor=0.35)
        split.label(text="UV Method:")
        split.prop(scene, "upbge_atlas_unwrap", text="")
        
        split = box_bake.split(factor=0.35)
        split.label(text="UV Margin:")
        split.prop(scene, "upbge_atlas_uv_margin", text="")
        
        split = box_bake.split(factor=0.35)
        split.label(text="Bake Margin:")
        split.prop(scene, "upbge_atlas_margin", text="")
        
        if scene.upbge_atlas_bake_ao or scene.upbge_atlas_bake_combined or scene.upbge_atlas_bake_mode == 'FULL':
            split = box_bake.split(factor=0.35)
            split.label(text="AO Samples:")
            split.prop(scene, "upbge_atlas_ao_samples", text="")
        
        layout.separator()
        
        # 3. Maps to Generate Grid (Grade de Mapas)
        layout.label(text="Maps to generate:")
        box_maps = layout.box()
        split = box_maps.split()
        
        col1 = split.column()
        col1.prop(scene, "upbge_atlas_bake_diffuse")
        col1.prop(scene, "upbge_atlas_bake_normal")
        col1.prop(scene, "upbge_atlas_bake_alpha")
        
        col2 = split.column()
        col2.prop(scene, "upbge_atlas_bake_ao")
        col2.prop(scene, "upbge_atlas_bake_specular")
        col2.prop(scene, "upbge_atlas_bake_combined")
        
        if scene.upbge_atlas_bake_combined or scene.upbge_atlas_bake_ao:
            split_ao = box_maps.split(factor=0.35)
            split_ao.label(text="AO Strength:")
            split_ao.prop(scene, "upbge_atlas_ao_strength", text="")
        
        layout.separator()
        
        # 4. Finalização (Salvar e Botão com destaque)
        layout.prop(scene, "upbge_atlas_auto_save", icon='FILE_TICK')
        
        layout.separator()
        row_exec = layout.row()
        row_exec.scale_y = 1.5  # Aumenta a altura para maior destaque visual
        row_exec.operator(OBJECT_OT_upbge_atlas_bake.bl_idname, icon='RENDER_STILL')


# ==============================================================================
# REGISTRO
# ==============================================================================
def register():
    # Registrando as propriedades DIRETAMENTE na Scene global
    bpy.types.Scene.upbge_atlas_res = IntProperty(
        name="Resolution",
        default=2048,
        min=16,
        max=8192
    )
    bpy.types.Scene.upbge_atlas_uv = StringProperty(
        name="UV Name",
        default="UV_Atlas"
    )
    bpy.types.Scene.upbge_atlas_img = StringProperty(
        name="Image Name",
        default="Baked_Texture"
    )
    bpy.types.Scene.upbge_atlas_bake_mode = EnumProperty(
        name="Bake Mode",
        description="Choose whether to bake only textures or full scene lighting",
        items=[
            ('TEXTURE', "Textures Only", "Bake only the base colors (flat)"),
            ('FULL', "Full Render", "Bake colors, scene lighting, and shadows"),
        ],
        default='TEXTURE'
    )
    bpy.types.Scene.upbge_atlas_unwrap = EnumProperty(
        name="UV Method",
        description="Choose the unwrap method for the new UV",
        items=[
            ('SMART', "Smart UV Project", "Smart Projection (Ideal for Atlas)"),
            ('LIGHTMAP', "Lightmap Pack", "Lightmap Packing"),
            ('UNWRAP', "Standard Unwrap", "Standard Unwrap (Requires marked Seams)"),
        ],
        default='SMART'
    )
    bpy.types.Scene.upbge_atlas_uv_margin = FloatProperty(
        name="UV Margin",
        description="Distance between UV islands during unwrap",
        default=0.01,
        min=0.0,
        max=1.0,
        precision=3
    )
    bpy.types.Scene.upbge_atlas_bake_diffuse = BoolProperty(
        name="Diffuse / Full",
        description="Generates the base color or full render map (depending on Bake Mode)",
        default=True
    )
    bpy.types.Scene.upbge_atlas_bake_ao = BoolProperty(
        name="AO",
        description="Generates the Ambient Occlusion map",
        default=False
    )
    bpy.types.Scene.upbge_atlas_bake_normal = BoolProperty(
        name="Normal",
        description="Generates the Normal map",
        default=False
    )
    bpy.types.Scene.upbge_atlas_bake_specular = BoolProperty(
        name="Specular",
        description="Generates the Specular map",
        default=False
    )
    bpy.types.Scene.upbge_atlas_bake_alpha = BoolProperty(
        name="Alpha",
        description="Generates the Transparency/Alpha map",
        default=False
    )
    bpy.types.Scene.upbge_atlas_bake_combined = BoolProperty(
        name="Combined (Diff+AO+Alpha)",
        description="Generates a final texture multiplying Diffuse x AO, and inserting Alpha (if enabled)",
        default=False
    )
    bpy.types.Scene.upbge_atlas_auto_save = BoolProperty(
        name="Auto-Save Textures",
        description="Automatically saves generated textures in the same folder as the .blend file",
        default=True
    )
    bpy.types.Scene.upbge_atlas_margin = IntProperty(
        name="Bake Margin",
        description="Texture bleed margin in pixels",
        default=2,
        min=0,
        max=64
    )
    bpy.types.Scene.upbge_atlas_ao_samples = IntProperty(
        name="AO Samples",
        description="Ambient Occlusion quality (higher = less noise, slower bake)",
        default=10,
        min=1,
        max=128
    )
    bpy.types.Scene.upbge_atlas_ao_strength = FloatProperty(
        name="AO Strength",
        description="Controls how dark the Ambient Occlusion is (affects AO and Combined maps)",
        default=0.5,
        min=0.0,
        max=1.0
    )
    
    bpy.utils.register_class(OBJECT_OT_upbge_atlas_bake)
    bpy.utils.register_class(MATERIAL_PT_upbge_atlas_bake)
    bpy.utils.register_class(VIEW3D_MT_atlas_res_menu)

def unregister():
    bpy.utils.unregister_class(VIEW3D_MT_atlas_res_menu)
    bpy.utils.unregister_class(MATERIAL_PT_upbge_atlas_bake)
    bpy.utils.unregister_class(OBJECT_OT_upbge_atlas_bake)
    
    del bpy.types.Scene.upbge_atlas_res
    del bpy.types.Scene.upbge_atlas_uv
    del bpy.types.Scene.upbge_atlas_img
    del bpy.types.Scene.upbge_atlas_bake_mode
    del bpy.types.Scene.upbge_atlas_unwrap
    del bpy.types.Scene.upbge_atlas_uv_margin
    del bpy.types.Scene.upbge_atlas_bake_diffuse
    del bpy.types.Scene.upbge_atlas_bake_ao
    del bpy.types.Scene.upbge_atlas_bake_normal
    del bpy.types.Scene.upbge_atlas_bake_specular
    del bpy.types.Scene.upbge_atlas_bake_alpha
    del bpy.types.Scene.upbge_atlas_bake_combined
    del bpy.types.Scene.upbge_atlas_auto_save
    del bpy.types.Scene.upbge_atlas_margin
    del bpy.types.Scene.upbge_atlas_ao_samples
    del bpy.types.Scene.upbge_atlas_ao_strength

if __name__ == "__main__":
    register()
