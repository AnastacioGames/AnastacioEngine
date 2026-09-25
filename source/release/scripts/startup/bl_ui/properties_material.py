# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>
import bpy
from bpy.types import Menu, Panel, UIList
from rna_prop_ui import PropertyPanel
from bpy.app.translations import pgettext_iface as iface_


def active_node_mat(mat):
    # TODO, 2.4x has a pipeline section, for 2.5 we need to communicate
    # which settings from node-materials are used
    if mat is not None:
        mat_node = mat.active_node_material
        if mat_node:
            return mat_node
        else:
            return mat

    return None


def check_material(mat):
    if mat is not None:
        if mat.use_nodes:
            if mat.active_node_material is not None:
                return True
            return False
        return True
    return False


def simple_material(mat):
    if (mat is not None) and (not mat.use_nodes):
        return True
    return False


class MATERIAL_MT_sss_presets(Menu):
    bl_label = "SSS Presets"
    preset_subdir = "sss"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


class MATERIAL_MT_specials(Menu):
    bl_label = "Material Specials"

    def draw(self, context):
        layout = self.layout

        layout.operator("object.material_slot_copy", icon='COPY_ID')
        layout.operator("material.copy", icon='COPYDOWN')
        layout.operator("material.paste", icon='PASTEDOWN')


class MATERIAL_UL_matslots(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # assert(isinstance(item, bpy.types.MaterialSlot)
        # ob = data
        slot = item
        ma = slot.material
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if ma:
                layout.prop(ma, "name", text="", emboss=False, icon_value=icon)
            else:
                layout.label(text="", icon_value=icon)
            if ma and not context.scene.render.use_shading_nodes:
                manode = ma.active_node_material
                if manode:
                    layout.label(text=iface_("Node %s") % manode.name, translate=False, icon_value=layout.icon(manode))
                elif ma.use_nodes:
                    layout.label(text="Node <none>")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


class MaterialButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    # COMPAT_ENGINES must be defined in each subclass, external engines can add themselves here

    @classmethod
    def poll(cls, context):
        return context.material and (context.scene.render.engine in cls.COMPAT_ENGINES)


class MATERIAL_PT_context_material(MaterialButtonsPanel, Panel):
    bl_label = ""
    bl_options = {'HIDE_HEADER'}
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        # An exception, don't call the parent poll func because
        # this manages materials for all engine types

        engine = context.scene.render.engine
        return (context.material or context.object) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = context.material
        ob = context.object
        slot = context.material_slot
        space = context.space_data

        if ob:
            is_sortable = (len(ob.material_slots) > 1)

            rows = 1
            if is_sortable:
                rows = 4

            row = layout.row()

            row.template_list("MATERIAL_UL_matslots", "", ob, "material_slots", ob, "active_material_index", rows=rows)

            col = row.column(align=True)
            col.operator("object.material_slot_add", icon='ZOOMIN', text="")
            col.operator("object.material_slot_remove", icon='ZOOMOUT', text="")

            col.menu("MATERIAL_MT_specials", icon='DOWNARROW_HLT', text="")

            if is_sortable:
                col.separator(factor=1)

                col.operator("object.material_slot_move", icon='TRIA_UP', text="").direction = 'UP'
                col.operator("object.material_slot_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

            if ob.mode == 'EDIT':
                row = layout.row(align=True)
                row.operator("object.material_slot_assign", text="Assign")
                row.operator("object.material_slot_select", text="Select")
                row.operator("object.material_slot_deselect", text="Deselect")

        split = layout.split(factor=0.65)

        if ob:
            split.template_ID(ob, "active_material", new="material.new")
            row = split.row()
            if mat:
                row.prop(mat, "use_nodes", icon='NODETREE', text="")

            if slot:
                row.prop(slot, "link", text="")
            else:
                row.label()
        elif mat:
            split.template_ID(space, "pin_id")
            split.separator(factor=1)

        if mat:
            layout.row().prop(mat, "type", expand=True)
            if mat.use_nodes:
                row = layout.row()
                row.label(text="", icon='NODETREE')
                if mat.active_node_material:
                    row.prop(mat.active_node_material, "name", text="")
                else:
                    row.label(text="No material node selected")


class MATERIAL_PT_preview(MaterialButtonsPanel, Panel):
    bl_label = "Material Preview"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    def draw(self, context):
        self.layout.template_preview(context.material)


class MATERIAL_PT_pipeline(MaterialButtonsPanel, Panel):
    bl_label = "Render Pipeline Options"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return mat and (not simple_material(mat)) and (mat.type in {'SURFACE', 'WIRE', 'VOLUME'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self. layout

        mat = context.material
        mat_type = mat.type in {'SURFACE', 'WIRE'}

        box = layout.box()
        box.label(text="Transparency:", icon="IMAGE_RGB_ALPHA")
        row = box.row()
        row.active = mat_type
        row.prop(mat, "use_transparency")
        sub = row.column()
        sub.prop(mat, "offset_z")

        sub.active = mat_type and mat.use_transparency and mat.transparency_method == 'Z_TRANSPARENCY'

        row = box.row()
        row.active = mat.use_transparency or not mat_type
        row.prop(mat, "transparency_method", expand=True)

        layout.separator(factor=1)

        split = layout.split()
        box = split.box()
        box.label(text="Render:", icon="RENDER_STILL")
        col = box.column()

        col.prop(mat, "use_raytrace")
        col.prop(mat, "use_full_oversampling")
        sub = col.column()
        sub.active = mat_type
        sub.prop(mat, "use_sky")
        sub.prop(mat, "invert_z")
        col.prop(mat, "pass_index")

        box = split.box()
        box.label(text="Shadows:", icon="LAMP_SUN")
        col = box.column()
        col.active = mat_type

        col.prop(mat, "use_cast_shadows", text="Cast")
        col.prop(mat, "use_cast_shadows_only", text="Cast Only")
        col.prop(mat, "use_cast_buffer_shadows")
        sub = col.column()
        sub.active = mat.use_cast_buffer_shadows
        sub.prop(mat, "shadow_cast_alpha", text="Casting Alpha")
        col.prop(mat, "use_cast_approximate")


class MATERIAL_PT_diffuse(MaterialButtonsPanel, Panel):
    bl_label = "Diffuse"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type in {'SURFACE', 'WIRE', 'HALO'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = active_node_mat(context.material)

        box = layout.box()
        box.label(text="Diffuse:", icon="COLOR")
        split = box.split()

        col = split.column()
        col.prop(mat, "diffuse_color", text="")
        col = split.column()
        col.active = (not mat.use_shadeless)
        col.prop(mat, "diffuse_shader", text="", icon="BRUSH_TEXFILL")
        col = split.column()
        col.active = (not mat.use_shadeless)
        col.prop(mat, "use_diffuse_ramp", text="Ramp")

        col = box.column()
        col.active = (not mat.use_shadeless)
        row = col.row()
        row.prop(mat, "diffuse_intensity", text="Intensity")
        row.prop(mat, "translucency")

        if mat.diffuse_shader == 'MINNAERT':
            col.prop(mat, "darkness")
        elif mat.diffuse_shader == 'TOON':
            row = col.row()
            row.prop(mat, "diffuse_toon_size", text="Size")
            row.prop(mat, "diffuse_toon_smooth", text="Smooth")
        if mat.diffuse_shader in {'FRESNEL', 'LAMBERT_CUSTOM', 'MINNAERT'}:
            row = col.row()
            row.prop(mat, "diffuse_fresnel", text="Size")
            row.prop(mat, "diffuse_fresnel_factor", text="Blend")

        if mat.use_diffuse_ramp:
            ramp_box = layout.box()
            ramp_box.label(text="Ramp:", icon="RNDCURVE")
            col = ramp_box.column()
            col.active = (not mat.use_shadeless)
            col.separator(factor=1)
            col.template_color_ramp(mat, "diffuse_ramp", expand=True)
            col.separator(factor=1)

            row = col.row()
            row.prop(mat, "diffuse_ramp_input", text="Input")
            row.prop(mat, "diffuse_ramp_blend", text="Blend")

            col.prop(mat, "diffuse_ramp_factor", text="Factor")


class MATERIAL_PT_specular(MaterialButtonsPanel, Panel):
    bl_label = "Specular"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type in {'SURFACE', 'WIRE', 'HALO'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = active_node_mat(context.material)

        layout.active = (not mat.use_shadeless)

        box = layout.box()
        box.label(text="Specular:", icon="COLOR")
        split = box.split()

        col = split.column()
        col.prop(mat, "specular_color", text="")
        col = split.column()
        col.prop(mat, "specular_shader", text="", icon="BRUSH_SOFTEN")
        col = split.column()
        col.prop(mat, "use_specular_ramp", text="Ramp")

        col = box.column()
        row = col.row()
        row.prop(mat, "specular_intensity", text="Intensity")
        row.prop(mat, "specular_hardness", text="Hardness")

        col = box.column()

        if mat.specular_shader == 'TOON':
            row = col.row()
            row.prop(mat, "specular_toon_size", text="Size")
            row.prop(mat, "specular_toon_smooth", text="Smooth")
        elif mat.specular_shader == 'WARDISO':
            row = col.row()
            row.prop(mat, "specular_anisotropy", text="Anisotropy")

        if mat.use_specular_ramp:
            ramp_box = layout.box()
            ramp_box.label(text="Ramp:", icon="RNDCURVE")
            ramp_box.separator(factor=1)
            ramp_box.template_color_ramp(mat, "specular_ramp", expand=True)
            ramp_box.separator(factor=1)

            row = ramp_box.row()
            row.prop(mat, "specular_ramp_input", text="Input")
            row.prop(mat, "specular_ramp_blend", text="Blend")

            ramp_box.prop(mat, "specular_ramp_factor", text="Factor")


class MATERIAL_PT_shading(MaterialButtonsPanel, Panel):
    bl_label = "Shading"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type in {'SURFACE', 'WIRE', 'HALO'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = active_node_mat(context.material)
        engine = context.scene.render.engine

        if mat.type in {'SURFACE', 'WIRE', 'HALO'}:
            box = layout.box()
            box.label(text="Shading:", icon="SETTINGS")
            split = box.split()

            col = split.column()
            col.prop(mat, "use_shadeless")
            sub = col.column()
            sub.active = not mat.use_shadeless
            sub.prop(mat, "use_cubic")
            sub.prop(mat, "specular_roughness_bsdf", text="Roughness")
            sub.prop(mat, "specular_metallic_bsdf", text="Metallic")
            sub.prop(mat, "alpha", text="Opacity")
            sub.prop(mat, "specular_ior", text="IOR")
            col = split.column()
            sub = col.column()
            sub.active = not mat.use_shadeless
            sub.prop(mat, "use_tangent_shading")
            sub.prop(mat, "use_energy_conservation", text="Energy Conservation")
            sub.prop(mat, "emit")
            sub.prop(mat, "ambient")
            sub.prop(mat, "specular_slope", text="Slope")
            col.prop(mat, "roughness", text="Turbidity")

            # One row per label/field pair keeps them aligned at any UI scale.
            # The user GLSL is compiled even when Shadeless, so it is never greyed out.
            col = box.column()
            col.label(text="Shader Sources:")
            for label, attr in (("Vertex:", "script_vert"), ("Fragment:", "script_frag")):
                row = col.split()
                row.label(text=label)
                row.template_ID(mat, attr, new="text.new", open="text.open")


class MATERIAL_PT_transp(MaterialButtonsPanel, Panel):
    bl_label = "Transparency"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type in {'SURFACE', 'WIRE'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        base_mat = context.material
        mat = active_node_mat(context.material)
        rayt = mat.raytrace_transparency

        if simple_material(base_mat):
            layout.prop(base_mat, "use_transparency", text="Enabled")

        box = layout.box()
        box.label(text="Alpha:", icon="IMAGE_RGB_ALPHA")

        if simple_material(base_mat):
            row = box.row()
            row.active = mat.use_transparency
            row.prop(mat, "transparency_method", expand=True)

        split = box.split()
        split.active = base_mat.use_transparency

        col = split.column()
        col.prop(mat, "alpha")
        row = col.row()
        row.active = (base_mat.transparency_method != 'MASK') and (not mat.use_shadeless)
        row.prop(mat, "specular_alpha", text="Specular")

        col = split.column()
        col.active = (not mat.use_shadeless)
        col.prop(rayt, "fresnel")
        sub = col.column()
        sub.active = (rayt.fresnel > 0.0)
        sub.prop(rayt, "fresnel_factor", text="Blend")

        if base_mat.transparency_method == 'RAYTRACE':
            box = layout.box()
            box.label(text="Raytrace:", icon="MOD_MIRROR")
            split = box.split()
            split.active = base_mat.use_transparency

            col = split.column()
            col.prop(rayt, "ior")
            col.prop(rayt, "filter")
            col.prop(rayt, "falloff")
            col.prop(rayt, "depth_max")
            col.prop(rayt, "depth")

            col = split.column()
            col.label(text="Gloss:")
            col.prop(rayt, "gloss_factor", text="Amount")
            sub = col.column()
            sub.active = rayt.gloss_factor < 1.0
            sub.prop(rayt, "gloss_threshold", text="Threshold")
            sub.prop(rayt, "gloss_samples", text="Samples")


class MATERIAL_PT_mirror(MaterialButtonsPanel, Panel):
    bl_label = "Mirror"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type in {'SURFACE', 'WIRE'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = active_node_mat(context.material)
        raym = mat.raytrace_mirror

        layout.prop(raym, "use", text="Enabled")
        layout = layout.column()
        layout.active = raym.use

        box = layout.box()
        box.label(text="Reflection:", icon="MOD_MIRROR")
        split = box.split()

        col = split.column()
        col.prop(raym, "reflect_factor")
        col.prop(mat, "mirror_color", text="")

        col = split.column()
        col.prop(raym, "fresnel")
        sub = col.column()
        sub.active = (raym.fresnel > 0.0)
        sub.prop(raym, "fresnel_factor", text="Blend")

        box = layout.box()
        box.label(text="Falloff & Gloss:", icon="FILTER")
        split = box.split()

        col = split.column()
        col.separator(factor=1)
        col.prop(raym, "depth")
        col.prop(raym, "distance", text="Max Dist")
        col.separator(factor=1)
        sub = col.split(factor=0.4)
        sub.active = (raym.distance > 0.0)
        sub.label(text="Fade To:")
        sub.prop(raym, "fade_to", text="")

        col = split.column()
        col.label(text="Gloss:")
        col.prop(raym, "gloss_factor", text="Amount")
        sub = col.column()
        sub.active = (raym.gloss_factor < 1.0)
        sub.prop(raym, "gloss_threshold", text="Threshold")
        sub.prop(raym, "gloss_samples", text="Samples")
        sub.prop(raym, "gloss_anisotropic", text="Anisotropic")


class MATERIAL_PT_sss(MaterialButtonsPanel, Panel):
    bl_label = "Subsurface Scattering"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type in {'SURFACE', 'WIRE', 'HALO'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = active_node_mat(context.material)
        sss = mat.subsurface_scattering

        row = layout.row()
        row.active = (not mat.use_shadeless)
        row.prop(sss, "use", text="Enabled")
        layout = layout.column()
        layout.active = (sss.use) and (not mat.use_shadeless)

        row = layout.row().split()
        sub = row.row(align=True).split(align=True, factor=0.75)
        sub.menu("MATERIAL_MT_sss_presets", text=bpy.types.MATERIAL_MT_sss_presets.bl_label)
        sub.operator("material.sss_preset_add", text="", icon='ZOOMIN')
        sub.operator("material.sss_preset_add", text="", icon='ZOOMOUT').remove_active = True

        box = layout.box()
        box.label(text="Scattering:", icon="STRANDS")
        split = box.split()

        if context.scene.render.engine != 'BLENDER_GAME':
            col = split.column()
            col.prop(sss, "ior")
            col.prop(sss, "scale")
            col.prop(sss, "color", text="")
            col.prop(sss, "radius", text="RGB Radius", expand=True)
            col = split.column()
            sub = col.column(align=True)
            sub.label(text="Blend:")
            sub.prop(sss, "color_factor", text="Color")
            sub.prop(sss, "texture_factor", text="Texture")
            sub.label(text="Scattering Weight:")
            sub.prop(sss, "front")
            sub.prop(sss, "back")
            col.separator(factor=1)
            col.prop(sss, "error_threshold", text="Error")
        else:
            col = split.column()
            col.prop(sss, "scale")
            col.prop(sss, "radius", text="RGB Radius", expand=True)


class MATERIAL_PT_halo(MaterialButtonsPanel, Panel):
    bl_label = "Halo"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return mat and (mat.type == 'HALO') and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = context.material  # don't use node material
        halo = mat.halo

        def number_but(layout, toggle, number, name, color):
            row = layout.row(align=True)
            row.prop(halo, toggle, text="")
            sub = row.column(align=True)
            sub.active = getattr(halo, toggle)
            sub.prop(halo, number, text=name, translate=False)
            if not color == "":
                sub.prop(mat, color, text="")

        box = layout.box()
        box.label(text="Halo:", icon="MATERIAL")
        split = box.split()

        col = split.column()
        col.prop(mat, "alpha")
        col.prop(mat, "diffuse_color", text="")
        col.prop(halo, "seed")

        col = split.column()
        col.prop(halo, "size")
        col.prop(halo, "hardness")
        col.prop(halo, "add")

        box = layout.box()
        box.label(text="Options:", icon="SETTINGS")

        split = box.split()
        col = split.column()
        col.prop(halo, "use_texture")
        col.prop(halo, "use_vertex_normal")
        col.prop(halo, "use_extreme_alpha")
        col.prop(halo, "use_shaded")
        col.prop(halo, "use_soft")

        col = split.column()
        number_but(col, "use_ring", "ring_count", iface_("Rings"), "mirror_color")
        number_but(col, "use_lines", "line_count", iface_("Lines"), "specular_color")
        number_but(col, "use_star", "star_tip_count", iface_("Star Tips"), "")


class MATERIAL_PT_flare(MaterialButtonsPanel, Panel):
    bl_label = "Flare"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return mat and (mat.type == 'HALO') and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = context.material  # don't use node material
        halo = mat.halo

        layout.prop(halo, "use_flare_mode", text="Enabled")
        layout = layout.column()
        layout.active = halo.use_flare_mode

        box = layout.box()
        box.label(text="Flare:", icon="LAMP_SUN")
        split = box.split()

        col = split.column()
        col.prop(halo, "flare_size", text="Size")
        col.prop(halo, "flare_boost", text="Boost")
        col.prop(halo, "flare_seed", text="Seed")

        col = split.column()
        col.prop(halo, "flare_subflare_count", text="Subflares")
        col.prop(halo, "flare_subflare_size", text="Subsize")


class MATERIAL_PT_game_settings(MaterialButtonsPanel, Panel):
    bl_label = "Game Settings"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        return context.material and (context.scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        mat = context.material
        game = mat.game_settings  # don't use node material

        split = layout.split()

        box = split.box()
        box.label(text="Rendering:", icon="GAME")
        col = box.column()
        col.prop(game, "use_backface_culling")
        col.prop(game, "invisible")
        col.prop(game, "physics")
        col.label(text="Face Orientation:")
        col.prop(game, "face_orientation", text="")
        col.label(text="Alpha Blend:")
        col.prop(game, "alpha_blend", text="")

        box = split.box()
        box.label(text="Constant Values:", icon="SETTINGS")
        col = box.column()
        col.prop(mat, "use_constant_material")
        col.prop(mat, "use_constant_lamp")
        col.prop(mat, "use_constant_texture")
        col.prop(mat, "use_constant_texture_uv")
        col.prop(mat, "use_constant_world")
        col.prop(mat, "use_constant_mist")


class MATERIAL_PT_game_foliage(MaterialButtonsPanel, Panel):
    bl_label = "Foliage Shader"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        return context.material and (context.scene.render.engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        mat = context.material

        layout.prop(mat, "use_foliage", text="Enabled")
        layout = layout.column()
        layout.active = mat.use_foliage

        box = layout.box()
        box.label(text="Wind:", icon="FORCE_WIND")
        col = box.column()
        col.prop(mat, "foliage_grass")
        col.prop(mat, "foliage_strength", text="Strength")
        col.prop(mat, "foliage_turbulence", text="Turbulence")

        box = layout.box()
        box.label(text="Optimization:", icon="CAMERA_DATA")
        col = box.column()
        col.prop(mat, "use_foliage_optimization", text="Stop Beyond Distance")
        row = col.row()
        row.active = mat.use_foliage_optimization
        row.prop(mat, "foliage_distance")


class MATERIAL_PT_strand(MaterialButtonsPanel, Panel):
    bl_label = "Strand"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return mat and (mat.type in {'SURFACE', 'WIRE', 'HALO'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = context.material  # don't use node material
        tan = mat.strand

        split = layout.split()

        box = split.box()
        box.label(text="Size:", icon="STRANDS")
        col = box.column()
        sub = col.column(align=True)
        sub.prop(tan, "root_size", text="Root")
        sub.prop(tan, "tip_size", text="Tip")
        sub.prop(tan, "size_min", text="Minimum")
        sub.prop(tan, "use_blender_units")
        sub = col.column()
        sub.active = (not mat.use_shadeless)
        sub.prop(tan, "use_tangent_shading")
        col.prop(tan, "shape")

        box = split.box()
        box.label(text="Shading:", icon="SETTINGS")
        col = box.column()
        col.prop(tan, "width_fade")
        ob = context.object
        if ob and ob.type == 'MESH':
            col.prop_search(tan, "uv_layer", ob.data, "uv_textures", text="")
        else:
            col.prop(tan, "uv_layer", text="")
        col.separator(factor=1)
        sub = col.column()
        sub.active = (not mat.use_shadeless)
        sub.label("Surface diffuse:")
        sub = col.column()
        sub.prop(tan, "blend_distance", text="Distance")


class MATERIAL_PT_options(MaterialButtonsPanel, Panel):
    bl_label = "Options"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type in {'SURFACE', 'WIRE'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        base_mat = context.material
        mat = active_node_mat(base_mat)

        split = layout.split()

        box = split.box()
        box.label(text="Render:", icon="RENDER_STILL")
        col = box.column()
        if simple_material(base_mat):
            col.prop(mat, "use_raytrace")
            col.prop(mat, "use_full_oversampling")
            col.prop(mat, "use_sky")
        col.prop(mat, "use_mist")
        if simple_material(base_mat):
            col.prop(mat, "invert_z")
            sub = col.row()
            sub.prop(mat, "offset_z")
            sub.active = mat.use_transparency and mat.transparency_method == 'Z_TRANSPARENCY'
        sub = col.column(align=True)
        sub.label(text="Light Group:")
        sub.prop(mat, "light_group", text="")
        row = sub.row(align=True)
        row.active = bool(mat.light_group)
        row.prop(mat, "use_light_group_exclusive", text="Exclusive")
        row.prop(mat, "use_light_group_local", text="Local")

        box = split.box()
        box.label(text="Object:", icon="OBJECT_DATA")
        col = box.column()
        col.prop(mat, "use_face_texture")
        sub = col.column()
        sub.active = mat.use_face_texture
        sub.prop(mat, "use_face_texture_alpha")
        col.separator(factor=1)
        col.prop(mat, "use_vertex_color_paint")
        col.prop(mat, "use_vertex_color_light")
        col.prop(mat, "use_object_color")
        col.prop(mat, "use_uv_project")
        if simple_material(base_mat):
            col.prop(mat, "pass_index")

class MATERIAL_PT_game_options(MaterialButtonsPanel, Panel):
    bl_label = "Options"
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type in {'SURFACE', 'WIRE', 'HALO'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        base_mat = context.material
        mat = active_node_mat(base_mat)

        split = layout.split()

        box = split.box()
        box.label(text="Render:", icon="RENDER_STILL")
        col = box.column()
        if simple_material(base_mat):
            col.prop(mat, "invert_z")
            sub = col.row()
            sub.prop(mat, "offset_z")
            sub.active = mat.use_transparency and mat.transparency_method == 'Z_TRANSPARENCY'
        sub = col.column(align=True)

        sub.separator(factor=1.4)

        sub.label(text="Light Group:")
        sub.prop(mat, "light_group", text="")
        row = sub.row(align=True)
        row.active = bool(mat.light_group)
        row.prop(mat, "use_light_group_exclusive", text="Exclusive")
        row.prop(mat, "use_light_group_local", text="Local")

        sub.active = (mat.type == "HALO")
        sub.label(text="Halo Options:")
        sub.prop(mat, "point_size", text="Point Size")

        box = split.box()
        box.label(text="Object:", icon="OBJECT_DATA")
        col = box.column()
        col.prop(mat, "use_mist")
        col.prop(mat, "use_full_sky", text="Use Full Sky")
        col.prop(mat, "use_vertex_color_paint")
        col.prop(mat, "use_vertex_color_light")
        col.prop(mat, "use_object_color")
        col.prop(mat, "use_instancing")
        col.prop(mat, "use_gpu_skinning")
        col.prop(mat, "pass_index")

class MATERIAL_PT_shadow(MaterialButtonsPanel, Panel):
    bl_label = "Shadow"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type in {'SURFACE', 'WIRE'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        base_mat = context.material
        mat = active_node_mat(base_mat)

        box = layout.box()
        box.label(text="Shadow:", icon="LAMP_SUN")
        split = box.split()

        col = split.column()
        col.prop(mat, "use_shadows", text="Receive")
        col.prop(mat, "use_transparent_shadows", text="Receive Transparent")
        col.prop(mat, "use_only_shadow", text="Shadows Only")
        sub = col.column()
        sub.active = mat.use_only_shadow
        sub.prop(mat, "shadow_only_type", text="")

        if not simple_material(base_mat):
            col = split.column()

        col.prop(mat, "use_ray_shadow_bias", text="Auto Ray Bias")
        sub = col.column()
        sub.active = (not mat.use_ray_shadow_bias)
        sub.prop(mat, "shadow_ray_bias", text="Ray Bias")

        if simple_material(base_mat):
            col = split.column()

            col.prop(mat, "use_cast_shadows", text="Cast")
            col.prop(mat, "use_cast_shadows_only", text="Cast Only")
            col.prop(mat, "use_cast_buffer_shadows")
        sub = col.column()
        sub.active = mat.use_cast_buffer_shadows
        if simple_material(base_mat):
            sub.prop(mat, "shadow_cast_alpha", text="Casting Alpha")
        sub.prop(mat, "shadow_buffer_bias", text="Buffer Bias")
        if simple_material(base_mat):
            col.prop(mat, "use_cast_approximate")

class MATERIAL_PT_game_shadow(MaterialButtonsPanel, Panel):
    bl_label = "Shadow"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type in {'SURFACE', 'WIRE', 'HALO'}) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        base_mat = context.material
        mat = active_node_mat(base_mat)

        box = layout.box()
        box.label(text="Shadow:", icon="LAMP_SUN")
        split = box.split()

        if simple_material(base_mat):
            col = split.column()

            col.prop(mat, "use_cast_shadows", text="Cast")
            col.prop(mat, "use_cast_shadows_only", text="Cast Only")

        col = split.column()
        col.prop(mat, "use_shadows", text="Receive")
        col.prop(mat, "use_two_sided_shadows")

class MATERIAL_PT_transp_game(MaterialButtonsPanel, Panel):
    bl_label = "Transparency"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_GAME'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout
        base_mat = context.material
        mat = active_node_mat(base_mat)
        game = base_mat.game_settings  # the converter reads these from the base material
        simple = simple_material(base_mat)

        # Mirrors KX_BlenderMaterial: Alpha Blend picks the render pass; Z Transparency only
        # turns an Opaque material into (unsorted) Alpha Blend, Mask/Raytrace never do.
        use_transp = base_mat.use_transparency
        method = base_mat.transparency_method
        blend = game.alpha_blend
        if use_transp and method == 'Z_TRANSPARENCY' and blend == 'OPAQUE':
            blend = 'ALPHA'
        blended = blend in {'ADD', 'ALPHA', 'ALPHA_SORT'}

        if simple:
            layout.prop(base_mat, "use_transparency", text="Enabled")

        box = layout.box()
        box.label(text="Alpha:", icon="IMAGE_ALPHA")
        col = box.column()
        col.prop(game, "alpha_blend", text="Blend")
        if simple:
            row = col.row()
            row.active = use_transp
            row.prop(base_mat, "transparency_method", expand=True)
            if use_transp and method != 'Z_TRANSPARENCY' and game.alpha_blend == 'OPAQUE':
                col.label(text="Opaque blends without sorting: use Z Transparency", icon='ERROR')

        # Alpha still reaches the shader with Enabled off when Blend is not Opaque.
        col = box.column()
        col.active = use_transp or game.alpha_blend != 'OPAQUE'
        col.prop(mat, "alpha")
        row = col.row()
        row.active = use_transp and method != 'MASK' and not mat.use_shadeless
        row.prop(mat, "specular_alpha", text="Specular")

        box = layout.box()
        box.prop(mat, "use_depth_transparency")
        col = box.column()
        col.active = mat.use_depth_transparency and use_transp and blended
        col.prop(mat, "depth_transp_factor", text="Fade Distance")
        if mat.use_depth_transparency and not (use_transp and blended):
            box.label(text="No effect: needs Enabled and a blending mode", icon='ERROR')


class VolumeButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return mat and (mat.type == 'VOLUME') and (engine in cls.COMPAT_ENGINES)


class MATERIAL_PT_volume_density(VolumeButtonsPanel, Panel):
    bl_label = "Density"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    def draw(self, context):
        layout = self.layout

        vol = context.material.volume  # don't use node material

        box = layout.box()
        box.label(text="Density:", icon="MOD_FLUIDSIM")
        row = box.row()
        row.prop(vol, "density")
        row.prop(vol, "density_scale")


class MATERIAL_PT_volume_shading(VolumeButtonsPanel, Panel):
    bl_label = "Shading"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    def draw(self, context):
        layout = self.layout

        vol = context.material.volume  # don't use node material

        box = layout.box()
        box.label(text="Shading:", icon="MOD_SMOKE")
        split = box.split()

        col = split.column()
        col.prop(vol, "scattering")
        col.prop(vol, "asymmetry")
        col.prop(vol, "transmission_color")

        col = split.column()
        sub = col.column(align=True)
        sub.prop(vol, "emission")
        sub.prop(vol, "emission_color", text="")
        sub = col.column(align=True)
        sub.prop(vol, "reflection")
        sub.prop(vol, "reflection_color", text="")


class MATERIAL_PT_volume_lighting(VolumeButtonsPanel, Panel):
    bl_label = "Lighting"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    def draw(self, context):
        layout = self.layout

        vol = context.material.volume  # don't use node material

        box = layout.box()
        box.label(text="Lighting:", icon="LAMP_SUN")
        split = box.split()

        col = split.column()
        col.prop(vol, "light_method", text="")

        col = split.column()

        if vol.light_method == 'SHADED':
            col.prop(vol, "use_external_shadows")
            col.prop(vol, "use_light_cache")
            sub = col.column()
            sub.active = vol.use_light_cache
            sub.prop(vol, "cache_resolution")
        elif vol.light_method in {'MULTIPLE_SCATTERING', 'SHADED_PLUS_MULTIPLE_SCATTERING'}:
            sub = col.column()
            sub.enabled = True
            sub.active = False
            sub.label("Light Cache Enabled")
            col.prop(vol, "cache_resolution")

            sub = col.column(align=True)
            sub.prop(vol, "ms_diffusion")
            sub.prop(vol, "ms_spread")
            sub.prop(vol, "ms_intensity")


class MATERIAL_PT_volume_transp(VolumeButtonsPanel, Panel):
    bl_label = "Transparency"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return mat and simple_material(mat) and (mat.type == 'VOLUME') and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = context.material  # don't use node material

        box = layout.box()
        box.label(text="Transparency:", icon="IMAGE_ALPHA")
        box.row().prop(mat, "transparency_method", expand=True)


class MATERIAL_PT_volume_integration(VolumeButtonsPanel, Panel):
    bl_label = "Integration"
    COMPAT_ENGINES = {'BLENDER_RENDER'}

    def draw(self, context):
        layout = self.layout

        vol = context.material.volume  # don't use node material

        box = layout.box()
        box.label(text="Integration:", icon="SETTINGS")
        split = box.split()

        col = split.column()
        col.label(text="Step Calculation:")
        col.prop(vol, "step_method", text="")
        col = col.column(align=True)
        col.prop(vol, "step_size")

        col = split.column()
        col.label()
        col.prop(vol, "depth_threshold")


class MATERIAL_PT_volume_options(VolumeButtonsPanel, Panel):
    bl_label = "Options"
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        mat = context.material
        engine = context.scene.render.engine
        return check_material(mat) and (mat.type == 'VOLUME') and (engine in cls.COMPAT_ENGINES)

    def draw(self, context):
        layout = self.layout

        mat = active_node_mat(context.material)

        box = layout.box()
        box.label(text="Options:", icon="SETTINGS")
        split = box.split()

        col = split.column()
        if simple_material(context.material):
            col.prop(mat, "use_raytrace")
            col.prop(mat, "use_full_oversampling")
        col.prop(mat, "use_mist")

        col = split.column()
        col.label(text="Light Group:")
        col.prop(mat, "light_group", text="")
        row = col.row()
        row.active = bool(mat.light_group)
        row.prop(mat, "use_light_group_exclusive", text="Exclusive")


class MATERIAL_PT_custom_props(MaterialButtonsPanel, PropertyPanel, Panel):
    COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_GAME'}
    _context_path = "material"
    _property_type = bpy.types.Material


classes = (
    MATERIAL_MT_sss_presets,
    MATERIAL_MT_specials,
    MATERIAL_UL_matslots,
    MATERIAL_PT_context_material,
    MATERIAL_PT_preview,
    MATERIAL_PT_pipeline,
    MATERIAL_PT_diffuse,
    MATERIAL_PT_specular,
    MATERIAL_PT_shading,
    MATERIAL_PT_transp,
    MATERIAL_PT_mirror,
    MATERIAL_PT_sss,
    MATERIAL_PT_halo,
    MATERIAL_PT_flare,
    MATERIAL_PT_game_settings,
    MATERIAL_PT_game_foliage,
    MATERIAL_PT_strand,
    MATERIAL_PT_options,
    MATERIAL_PT_game_options,
    MATERIAL_PT_shadow,
    MATERIAL_PT_game_shadow,
    MATERIAL_PT_transp_game,
    MATERIAL_PT_volume_density,
    MATERIAL_PT_volume_shading,
    MATERIAL_PT_volume_lighting,
    MATERIAL_PT_volume_transp,
    MATERIAL_PT_volume_integration,
    MATERIAL_PT_volume_options,
    # MATERIAL_PT_custom_props,  # disabled: Custom Properties panel unused
)

if __name__ == "__main__":  # only for live edit.
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
