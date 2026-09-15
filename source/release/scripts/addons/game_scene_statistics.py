import bpy

bl_info = {
    "name": "Game Engine Scene Statistics",
    "description": "Displays detailed scene statistics focused on performance for the Range Engine",
    "author": "AnastacioGames",
    "version": (1, 0),
    "blender": (2, 79, 0),
    "location": "Properties > Render Layers",
    "category": "Game Engine"
}

class GAME_STATS_OT_update(bpy.types.Operator):
    bl_idname = "scene.game_stats_update"
    bl_label = "Update Global Stats"
    bl_description = "Calculates total triangles, objects, and physics in the scene"

    def execute(self, context):
        scene = context.scene
        
        objs = 0
        meshes = 0
        verts = 0
        faces = 0
        tris = 0
        lights = 0
        cameras = 0
        empties = 0
        physics = 0
        scene_mats = set()
        
        # Variáveis para a Camada Ativa (Layers)
        l_objs = 0
        l_meshes = 0
        l_verts = 0
        l_faces = 0
        l_tris = 0
        l_lights = 0
        l_cameras = 0
        l_empties = 0
        l_physics = 0
        l_mats = set()
        
        # Novas variáveis de performance da camada
        l_tex_memory_bytes = 0
        l_image_count = 0
        l_heavy_physics = 0
        l_bones = 0
        l_images_set = set() # Usamos um set para evitar contar a mesma imagem duas vezes na mesma camada
        
        # Novas variáveis de performance
        tex_memory_bytes = 0
        image_count = 0
        heavy_physics = 0
        bones = 0
        
        # Novas variáveis de performance sugeridas
        logic_bricks = 0
        active_modifiers = 0
        hidden_objects = 0
        
        l_logic_bricks = 0
        l_active_modifiers = 0
        l_hidden_objects = 0
        
        
        # Calcula a memória de texturas estimadas (VRAM)
        for img in bpy.data.images:
            # Evita imagens vazias ou render results
            if img.type == 'IMAGE' and img.size[0] > 0 and img.size[1] > 0:
                image_count += 1
                if img.filepath.lower().endswith('.dds'):
                    bpp = 1 # Arquivos DDS compactados
                else:
                    # Verifica RGB (3 bytes) ou RGBA (4 bytes) para JPG, PNG, etc.
                    bpp = (img.depth // 8) if getattr(img, "depth", 0) > 0 else 4
                    
                tex_memory_bytes += (img.size[0] * img.size[1] * bpp)

        for obj in scene.objects:
            # Verifica se o objeto está visível em qualquer uma das camadas ativas no momento
            in_layer = any(obj.layers[i] and scene.layers[i] for i in range(20))
            
            objs += 1
            if in_layer: l_objs += 1
            
            if obj.type == 'MESH':
                meshes += 1
                if in_layer: l_meshes += 1
                
                mesh = obj.data
                if mesh:
                    v_count = len(mesh.vertices)
                    f_count = len(mesh.polygons)
                    t_count = sum(len(p.vertices) - 2 for p in mesh.polygons)
                    
                    verts += v_count
                    faces += f_count
                    tris += t_count
                    if in_layer:
                        l_verts += v_count
                        l_faces += f_count
                        l_tris += t_count
                        
                    # Adiciona os materiais únicos ao set
                    for mat in mesh.materials:
                        if mat:
                            scene_mats.add(mat.name)
                            if in_layer: 
                                l_mats.add(mat.name)
                                # Coleta imagens dos slots de textura
                                if hasattr(mat, "texture_slots") and mat.texture_slots:
                                    for slot in mat.texture_slots:
                                        if slot and slot.texture and slot.texture.type == 'IMAGE':
                                            img = slot.texture.image
                                            if img and img.size[0] > 0 and img.size[1] > 0:
                                                l_images_set.add(img)
                            
            elif obj.type == 'ARMATURE':
                if obj.data:
                    bones += len(obj.data.bones)
                    if in_layer: l_bones += len(obj.data.bones)
                    
            elif obj.type == 'LAMP':
                lights += 1
                if in_layer: l_lights += 1
            elif obj.type == 'CAMERA':
                cameras += 1
                if in_layer: l_cameras += 1
            elif obj.type == 'EMPTY':
                empties += 1
                if in_layer: l_empties += 1
            
            # Verifica se tem física ativa (Dynamic ou Rigid Body)
            if hasattr(obj, "game") and obj.game.physics_type in {'DYNAMIC', 'RIGID_BODY'}:
                physics += 1
                if in_layer: l_physics += 1
                
                # Detecta colisões pesadas atreladas a corpos dinâmicos
                if obj.game.use_collision_bounds and obj.game.collision_bounds_type in {'TRIANGLE_MESH', 'CONVEX_HULL'}:
                    heavy_physics += 1
                    if in_layer: l_heavy_physics += 1
                
            # Contagem de Logic Bricks / Python Controllers
            if hasattr(obj, "game"):
                lb_count = len(obj.game.sensors) + len(obj.game.controllers) + len(obj.game.actuators)
                logic_bricks += lb_count
                if in_layer: l_logic_bricks += lb_count
            
            # Contagem de Modificadores Ativos
            active_modifiers += len(obj.modifiers)
            if in_layer: l_active_modifiers += len(obj.modifiers)
            
            # Contagem de Objetos Ocultos
            if obj.hide:
                hidden_objects += 1
                if in_layer: l_hidden_objects += 1
                    
        # Calcula VRAM apenas das imagens usadas nos layers ativos
        for img in l_images_set:
            l_image_count += 1
            if img.filepath.lower().endswith('.dds'):
                bpp = 1
            else:
                bpp = (img.depth // 8) if getattr(img, "depth", 0) > 0 else 4
            l_tex_memory_bytes += (img.size[0] * img.size[1] * bpp)

        # Salva na Cena para não recalcular toda vez
        scene.stats_global_objs = objs
        scene.stats_global_meshes = meshes
        scene.stats_global_verts = verts
        scene.stats_global_faces = faces
        scene.stats_global_tris = tris
        scene.stats_global_lights = lights
        scene.stats_global_cameras = cameras
        scene.stats_global_empties = empties
        scene.stats_global_physics = physics
        scene.stats_global_mats = len(scene_mats)
        
        scene.stats_tex_mb = tex_memory_bytes / (1024 * 1024) # Converte para MB
        scene.stats_image_count = image_count
        scene.stats_heavy_physics = heavy_physics
        scene.stats_bones = bones
        scene.stats_global_logic_bricks = logic_bricks
        scene.stats_global_active_modifiers = active_modifiers
        scene.stats_global_hidden_objects = hidden_objects
        
        scene.stats_layer_objs = l_objs
        scene.stats_layer_meshes = l_meshes
        scene.stats_layer_verts = l_verts
        scene.stats_layer_faces = l_faces
        scene.stats_layer_tris = l_tris
        scene.stats_layer_lights = l_lights
        scene.stats_layer_cameras = l_cameras
        scene.stats_layer_empties = l_empties
        scene.stats_layer_physics = l_physics
        scene.stats_layer_mats = len(l_mats)
        
        scene.stats_layer_tex_mb = l_tex_memory_bytes / (1024 * 1024)
        scene.stats_layer_image_count = l_image_count
        scene.stats_layer_heavy_physics = l_heavy_physics
        scene.stats_layer_bones = l_bones
        scene.stats_layer_logic_bricks = l_logic_bricks
        scene.stats_layer_active_modifiers = l_active_modifiers
        scene.stats_layer_hidden_objects = l_hidden_objects
        
        scene.stats_updated = True

        return {'FINISHED'}

class GAME_STATS_PT_panel(bpy.types.Panel):
    bl_label = "Game Engine: Scene Statistics"
    bl_idname = "GAME_STATS_PT_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render_layer"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # --- ACTIVE OBJECT STATS (Automático em tempo real) ---
        obj = context.active_object
        if obj:
            box2 = layout.box()
            row2 = box2.row(align=True)
            icon_obj = 'TRIA_DOWN' if scene.stats_show_active_obj else 'TRIA_RIGHT'
            row2.prop(scene, "stats_show_active_obj", text="", icon=icon_obj, emboss=False)
            row2.label(text=f"Active Object: {obj.name}", icon='OBJECT_DATAMODE')
            
            if scene.stats_show_active_obj:
                split2 = box2.split()
                col_cpu_obj = split2.column(align=True)
                col_gpu_obj = split2.column(align=True)
                
                # Coleta dados de Logic e Physics (CPU)
                logic_count = 0
                phys_type = "None"
                heavy_phys = False
                
                if hasattr(obj, "game"):
                    logic_count = len(obj.game.sensors) + len(obj.game.controllers) + len(obj.game.actuators)
                    phys_type = obj.game.physics_type
                    if phys_type in {'DYNAMIC', 'RIGID_BODY'} and obj.game.use_collision_bounds:
                        if obj.game.collision_bounds_type in {'TRIANGLE_MESH', 'CONVEX_HULL'}:
                            heavy_phys = True
                            
                bones = 0
                if obj.type == 'ARMATURE' and obj.data:
                    bones = len(obj.data.bones)
                elif obj.parent and obj.parent.type == 'ARMATURE' and obj.parent.data:
                    bones = len(obj.parent.data.bones)
                
                # Desenha CPU Info
                col_cpu_obj.label(text="CPU (Logic/Physics)", icon='OUTLINER_OB_ARMATURE')
                col_cpu_obj.separator()
                col_cpu_obj.label(text=f"Logic Bricks: {logic_count}", icon='LOGIC')
                
                phys_row = col_cpu_obj.row()
                phys_row.label(text=f"Physics: {phys_type.replace('_', ' ').title()}", icon='PHYSICS')
                if heavy_phys:
                    phys_row.label(text="(Heavy!)", icon='ERROR')
                    
                if bones > 0:
                    col_cpu_obj.separator()
                    col_cpu_obj.label(text=f"Bones: {bones}", icon='BONE_DATA')
                
                # Desenha GPU Info
                col_gpu_obj.label(text="GPU (Rasterizer)", icon='RESTRICT_RENDER_OFF')
                col_gpu_obj.separator()
                
                if obj.type == 'MESH' and obj.data:
                    mesh = obj.data
                    verts = len(mesh.vertices)
                    faces = len(mesh.polygons)
                    tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
                    mats = len(obj.material_slots)
                    
                    # Coleta dados de Textura do objeto
                    img_set = set()
                    for mat_slot in obj.material_slots:
                        mat = mat_slot.material
                        if mat and hasattr(mat, "texture_slots"):
                            for slot in mat.texture_slots:
                                if slot and slot.texture and slot.texture.type == 'IMAGE':
                                    img = slot.texture.image
                                    if img and img.size[0] > 0 and img.size[1] > 0:
                                        img_set.add(img)
                    
                    img_count = len(img_set)
                    
                    vram_mb = 0
                    for img in img_set:
                        if img.filepath.lower().endswith('.dds'):
                            vram_mb += (img.size[0] * img.size[1] * 1)
                        else:
                            vram_mb += (img.size[0] * img.size[1] * ((img.depth // 8) if getattr(img, "depth", 0) > 0 else 4))
                    vram_mb /= (1024 * 1024)
                    
                    col_gpu_obj.label(text=f"Vertices: {verts}", icon='VERTEXSEL')
                    col_gpu_obj.label(text=f"Faces: {faces}", icon='FACESEL')
                    
                    tri_row = col_gpu_obj.row()
                    tri_row.label(text=f"Tris: {tris}", icon='MESH_ICOSPHERE')
                    if tris > 5000:
                        tri_row.label(text="(High!)", icon='ERROR')
                    
                    mat_row = col_gpu_obj.row()
                    mat_row.label(text=f"Mats: {mats}", icon='MATERIAL_DATA')
                    if mats > 3:
                        mat_row.label(text="(Optimize)", icon='ERROR')
                        
                    col_gpu_obj.separator()
                    col_gpu_obj.label(text=f"Images: {img_count}", icon='IMAGE_DATA')
                    tex_row = col_gpu_obj.row()
                    tex_row.label(text=f"VRAM (Est.): {vram_mb:.1f} MB", icon='TEXTURE')
                    if vram_mb > 32.0:
                        tex_row.label(text="(High!)", icon='ERROR')
                else:
                    col_gpu_obj.label(text="Not a Mesh object.", icon='INFO')

        # --- GLOBAL STATS (Atualizado por botão) ---
        box = layout.box()
        row = box.row(align=True)
        icon_global = 'TRIA_DOWN' if scene.stats_show_global else 'TRIA_RIGHT'
        row.prop(scene, "stats_show_global", text="", icon=icon_global, emboss=False)
        row.label(text="Global Scene Stats:", icon='SCENE_DATA')
        
        if scene.stats_show_global:
            box.operator("scene.game_stats_update", text="Calculate / Update Stats", icon='FILE_REFRESH')
            
            if scene.stats_updated:
                split = box.split()
                col_cpu = split.column(align=True)
                col_gpu = split.column(align=True)
                
                # --- CPU / LOGIC ---
                col_cpu.label(text="CPU (Logic/Physics)", icon='OUTLINER_OB_ARMATURE')
                col_cpu.separator()
                col_cpu.label(text=f"Objects: {scene.stats_global_objs}", icon='OBJECT_DATA')
                col_cpu.label(text=f"Lights: {scene.stats_global_lights}", icon='LAMP_DATA')
                col_cpu.label(text=f"Cameras: {scene.stats_global_cameras}", icon='CAMERA_DATA')
                col_cpu.label(text=f"Empties: {scene.stats_global_empties}", icon='EMPTY_DATA')
                col_cpu.label(text=f"Physics: {scene.stats_global_physics}", icon='PHYSICS')
                
                col_cpu.separator()
                col_cpu.label(text=f"Bones: {scene.stats_bones}", icon='BONE_DATA')
                phys_row = col_cpu.row()
                col_cpu.label(text=f"Logic Bricks: {scene.stats_global_logic_bricks}", icon='LOGIC')
                col_cpu.label(text=f"Active Modifiers: {scene.stats_global_active_modifiers}", icon='MODIFIER')
                col_cpu.label(text=f"Hidden Objects: {scene.stats_global_hidden_objects}", icon='RESTRICT_VIEW_OFF' if scene.stats_global_hidden_objects == 0 else 'RESTRICT_VIEW_ON')
                phys_row.label(text=f"Heavy Physics: {scene.stats_heavy_physics}", icon='ERROR' if scene.stats_heavy_physics > 0 else 'PHYSICS')
                
                # --- GPU / RENDER ---
                col_gpu.label(text="GPU (Rasterizer)", icon='RESTRICT_RENDER_OFF')
                col_gpu.separator()
                col_gpu.label(text=f"Meshes: {scene.stats_global_meshes}", icon='MESH_DATA')
                col_gpu.label(text=f"Vertices: {scene.stats_global_verts}", icon='VERTEXSEL')
                col_gpu.label(text=f"Faces: {scene.stats_global_faces}", icon='FACESEL')
                
                # Alerta de performance se passar de 50 mil triângulos
                tris = scene.stats_global_tris
                tri_row = col_gpu.row()
                tri_row.label(text=f"Tris: {tris}", icon='MESH_ICOSPHERE')
                if tris > 50000:
                    tri_row.label(text="(High!)", icon='ERROR')
                    
                col_gpu.label(text=f"Materials: {scene.stats_global_mats}", icon='MATERIAL_DATA')
                
                col_gpu.separator()
                col_gpu.label(text=f"Images: {scene.stats_image_count}", icon='IMAGE_DATA')
                tex_row = col_gpu.row()
                tex_row.label(text=f"VRAM (Est.): {scene.stats_tex_mb:.1f} MB", icon='TEXTURE')
                if scene.stats_tex_mb > 256: # Alerta se as texturas passarem de 256MB brutas
                    tex_row.label(text="(High!)", icon='ERROR')
            else:
                box.label(text="Click to calculate scene stats.", icon='INFO')
        
        # --- LAYERS INFO ---
        box3 = layout.box()
        row3 = box3.row(align=True)
        icon_layer = 'TRIA_DOWN' if scene.stats_show_layers else 'TRIA_RIGHT'
        row3.prop(scene, "stats_show_layers", text="", icon=icon_layer, emboss=False)
        row3.label(text="Active Layers Info:", icon='RENDERLAYERS')
        
        if scene.stats_show_layers:
            active_layers = [str(i + 1) for i, state in enumerate(scene.layers) if state]
            box3.label(text=f"Layers: {', '.join(active_layers)}")
            
            if scene.stats_updated:
                split3 = box3.split()
                col_cpu_l = split3.column(align=True)
                col_gpu_l = split3.column(align=True)
                
                # --- CPU / LOGIC (Layers) ---
                col_cpu_l.label(text="CPU (Logic/Physics)", icon='OUTLINER_OB_ARMATURE')
                col_cpu_l.separator()
                col_cpu_l.label(text=f"Objects: {scene.stats_layer_objs}", icon='OBJECT_DATA')
                col_cpu_l.label(text=f"Lights: {scene.stats_layer_lights}", icon='LAMP_DATA')
                col_cpu_l.label(text=f"Cameras: {scene.stats_layer_cameras}", icon='CAMERA_DATA')
                col_cpu_l.label(text=f"Empties: {scene.stats_layer_empties}", icon='EMPTY_DATA')
                col_cpu_l.label(text=f"Physics: {scene.stats_layer_physics}", icon='PHYSICS')
                
                col_cpu_l.separator()
                col_cpu_l.label(text=f"Bones: {scene.stats_layer_bones}", icon='BONE_DATA')
                phys_row_l = col_cpu_l.row()
                col_cpu_l.label(text=f"Logic Bricks: {scene.stats_layer_logic_bricks}", icon='LOGIC')
                col_cpu_l.label(text=f"Active Modifiers: {scene.stats_layer_active_modifiers}", icon='MODIFIER')
                col_cpu_l.label(text=f"Hidden Objects: {scene.stats_layer_hidden_objects}", icon='RESTRICT_VIEW_OFF' if scene.stats_layer_hidden_objects == 0 else 'RESTRICT_VIEW_ON')
                phys_row_l.label(text=f"Heavy Physics: {scene.stats_layer_heavy_physics}", icon='ERROR' if scene.stats_layer_heavy_physics > 0 else 'PHYSICS')
                
                # --- GPU / RENDER (Layers) ---
                col_gpu_l.label(text="GPU (Rasterizer)", icon='RESTRICT_RENDER_OFF')
                col_gpu_l.separator()
                col_gpu_l.label(text=f"Meshes: {scene.stats_layer_meshes}", icon='MESH_DATA')
                col_gpu_l.label(text=f"Vertices: {scene.stats_layer_verts}", icon='VERTEXSEL')
                col_gpu_l.label(text=f"Faces: {scene.stats_layer_faces}", icon='FACESEL')
                
                tris_l = scene.stats_layer_tris
                tri_row_l = col_gpu_l.row()
                tri_row_l.label(text=f"Tris: {tris_l}", icon='MESH_ICOSPHERE')
                if tris_l > 50000:
                    tri_row_l.label(text="(High!)", icon='ERROR')
                    
                col_gpu_l.label(text=f"Materials: {scene.stats_layer_mats}", icon='MATERIAL_DATA')
                
                col_gpu_l.separator()
                col_gpu_l.label(text=f"Images: {scene.stats_layer_image_count}", icon='IMAGE_DATA')
                tex_row_l = col_gpu_l.row()
                tex_row_l.label(text=f"VRAM (Est.): {scene.stats_layer_tex_mb:.1f} MB", icon='TEXTURE')
                if scene.stats_layer_tex_mb > 256:
                    tex_row_l.label(text="(High!)", icon='ERROR')
            else:
                box3.label(text="Click 'Calculate' to see layer stats.", icon='INFO')

def register():
    bpy.types.Scene.stats_global_objs = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_meshes = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_verts = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_faces = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_tris = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_lights = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_cameras = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_empties = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_physics = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_mats = bpy.props.IntProperty(default=0)
    
    bpy.types.Scene.stats_tex_mb = bpy.props.FloatProperty(default=0.0)
    bpy.types.Scene.stats_image_count = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_heavy_physics = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_bones = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_logic_bricks = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_active_modifiers = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_global_hidden_objects = bpy.props.IntProperty(default=0)
    
    bpy.types.Scene.stats_layer_objs = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_meshes = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_verts = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_faces = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_tris = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_lights = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_cameras = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_empties = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_physics = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_mats = bpy.props.IntProperty(default=0)
    
    bpy.types.Scene.stats_layer_tex_mb = bpy.props.FloatProperty(default=0.0)
    bpy.types.Scene.stats_layer_image_count = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_heavy_physics = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_bones = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_logic_bricks = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_active_modifiers = bpy.props.IntProperty(default=0)
    bpy.types.Scene.stats_layer_hidden_objects = bpy.props.IntProperty(default=0)
    
    bpy.types.Scene.stats_updated = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.stats_show_layers = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.stats_show_global = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.stats_show_active_obj = bpy.props.BoolProperty(default=False)
    
    bpy.utils.register_class(GAME_STATS_OT_update)
    bpy.utils.register_class(GAME_STATS_PT_panel)

def unregister():
    bpy.utils.unregister_class(GAME_STATS_OT_update)
    bpy.utils.unregister_class(GAME_STATS_PT_panel)
    
    # Limpeza de memória
    del bpy.types.Scene.stats_global_objs
    del bpy.types.Scene.stats_global_meshes
    del bpy.types.Scene.stats_global_verts
    del bpy.types.Scene.stats_global_faces
    del bpy.types.Scene.stats_global_tris
    del bpy.types.Scene.stats_global_lights
    del bpy.types.Scene.stats_global_cameras
    del bpy.types.Scene.stats_global_empties
    del bpy.types.Scene.stats_global_physics
    del bpy.types.Scene.stats_global_mats
    
    del bpy.types.Scene.stats_tex_mb
    del bpy.types.Scene.stats_image_count
    del bpy.types.Scene.stats_heavy_physics
    del bpy.types.Scene.stats_global_logic_bricks
    del bpy.types.Scene.stats_global_active_modifiers
    del bpy.types.Scene.stats_global_hidden_objects
    del bpy.types.Scene.stats_bones
    
    del bpy.types.Scene.stats_layer_objs
    del bpy.types.Scene.stats_layer_meshes
    del bpy.types.Scene.stats_layer_verts
    del bpy.types.Scene.stats_layer_faces
    del bpy.types.Scene.stats_layer_tris
    del bpy.types.Scene.stats_layer_lights
    del bpy.types.Scene.stats_layer_cameras
    del bpy.types.Scene.stats_layer_empties
    del bpy.types.Scene.stats_layer_physics
    del bpy.types.Scene.stats_layer_mats
    
    del bpy.types.Scene.stats_layer_tex_mb
    del bpy.types.Scene.stats_layer_image_count
    del bpy.types.Scene.stats_layer_heavy_physics
    del bpy.types.Scene.stats_layer_logic_bricks
    del bpy.types.Scene.stats_layer_active_modifiers
    del bpy.types.Scene.stats_layer_hidden_objects
    del bpy.types.Scene.stats_layer_bones
    
    del bpy.types.Scene.stats_updated
    del bpy.types.Scene.stats_show_layers
    del bpy.types.Scene.stats_show_global
    del bpy.types.Scene.stats_show_active_obj

if __name__ == "__main__":
    register()
