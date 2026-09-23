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

import bpy, os, json
from bpy.types import Menu, Operator
from bpy.props import StringProperty, BoolProperty

class AddPresetBase:
    """Base preset class, only for subclassing
    subclasses must define
     - preset_values
     - preset_subdir """
    # bl_idname = "script.preset_base_add"
    # bl_label = "Add a Python Preset"

    # only because invoke_props_popup requires. Also do not add to search menu.
    bl_options = {'REGISTER', 'INTERNAL'}

    name: StringProperty(
        name="Name",
        description="Name of the preset, used to make the path name",
        maxlen=64,
        options={'SKIP_SAVE'},
    )
    remove_active: BoolProperty(
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    @staticmethod
    def as_filename(name):  # could reuse for other presets

        # lazy init maketrans
        def maketrans_init():
            cls = AddPresetBase
            attr = "_as_filename_trans"

            trans = getattr(cls, attr, None)
            if trans is None:
                trans = str.maketrans({char: "_" for char in " !@#$%^&*(){}:\";'[]<>,.\\/?"})
                setattr(cls, attr, trans)
            return trans

        name = name.lower().strip()
        name = bpy.path.display_name_to_filepath(name)
        trans = maketrans_init()
        return name.translate(trans)

    def execute(self, context):
        import os

        if hasattr(self, "pre_cb"):
            self.pre_cb(context)

        preset_menu_class = getattr(bpy.types, self.preset_menu)

        is_xml = getattr(preset_menu_class, "preset_type", None) == 'XML'

        if is_xml:
            ext = ".xml"
        else:
            ext = ".py"

        if not self.remove_active:
            name = self.name.strip()
            if not name:
                return {'FINISHED'}

            filename = self.as_filename(name)

            target_path = os.path.join("presets", self.preset_subdir)
            target_path = bpy.utils.user_resource('SCRIPTS',
                                                  target_path,
                                                  create=True)

            if not target_path:
                self.report({'WARNING'}, "Failed to create presets path")
                return {'CANCELLED'}

            filepath = os.path.join(target_path, filename) + ext

            try:
                if hasattr(self, "add"):
                    self.add(context, filepath)
                else:
                    print("Writing Preset: %r" % filepath)

                    if is_xml:
                        import rna_xml
                        rna_xml.xml_file_write(context,
                                               filepath,
                                               preset_menu_class.preset_xml_map,
                                               skip_typemap=getattr(self, "preset_xml_skip_typemap", None))
                    else:

                        def rna_recursive_attr_expand(value, rna_path_step, level):
                            if isinstance(value, bpy.types.PropertyGroup):
                                for sub_value_attr in value.bl_rna.properties.keys():
                                    if sub_value_attr == "rna_type":
                                        continue
                                    sub_value = getattr(value, sub_value_attr)
                                    rna_recursive_attr_expand(sub_value, "%s.%s" % (rna_path_step, sub_value_attr), level)
                            elif type(value).__name__ == "bpy_prop_collection_idprop":  # could use nicer method
                                file_preset.write("%s.clear()\n" % rna_path_step)
                                for sub_value in value:
                                    file_preset.write("item_sub_%d = %s.add()\n" % (level, rna_path_step))
                                    rna_recursive_attr_expand(sub_value, "item_sub_%d" % level, level + 1)
                            else:
                                # convert thin wrapped sequences
                                # to simple lists to repr()
                                try:
                                    value = value[:]
                                except:
                                    pass

                                file_preset.write("%s = %r\n" % (rna_path_step, value))

                        file_preset = open(filepath, 'w', encoding="utf-8")
                        file_preset.write("import bpy\n")

                        if hasattr(self, "preset_defines"):
                            for rna_path in self.preset_defines:
                                exec(rna_path)
                                file_preset.write("%s\n" % rna_path)
                            file_preset.write("\n")

                        for rna_path in self.preset_values:
                            value = eval(rna_path)
                            rna_recursive_attr_expand(value, rna_path, 1)

                        file_preset.close()
            except Exception as ex:
                self.report({'ERROR'}, "Unable to save preset: %s" % ex)
                import traceback
                traceback.print_exc()
                if is_xml:
                    try:
                        with open(filepath + ".error.log", "w", encoding="utf-8") as file_error:
                            traceback.print_exc(file=file_error)
                    except OSError:
                        pass
                return {'CANCELLED'}

            preset_menu_class.bl_label = bpy.path.display_name(filename)

        else:
            preset_active = preset_menu_class.bl_label

            # fairly sloppy but convenient.
            filepath = bpy.utils.preset_find(preset_active,
                                             self.preset_subdir,
                                             ext=ext)

            if not filepath:
                filepath = bpy.utils.preset_find(preset_active,
                                                 self.preset_subdir,
                                                 display_name=True,
                                                 ext=ext)

            if not filepath:
                return {'CANCELLED'}

            try:
                if hasattr(self, "remove"):
                    self.remove(context, filepath)
                else:
                    os.remove(filepath)
            except Exception as e:
                self.report({'ERROR'}, "Unable to remove preset: %r" % e)
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}

            # XXX, stupid!
            preset_menu_class.bl_label = "Presets"

        if hasattr(self, "post_cb"):
            self.post_cb(context)

        return {'FINISHED'}

    def check(self, context):
        self.name = self.as_filename(self.name.strip())

    def invoke(self, context, event):
        if not self.remove_active:
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
        else:
            return self.execute(context)


class ExecutePreset(Operator):
    """Execute a preset"""
    bl_idname = "script.execute_preset"
    bl_label = "Execute a Python Preset"

    filepath: StringProperty(
        subtype='FILE_PATH',
        options={'SKIP_SAVE'},
    )
    menu_idname: StringProperty(
        name="Menu ID Name",
        description="ID name of the menu this was called from",
        options={'SKIP_SAVE'},
    )

    def execute(self, context):
        from os.path import basename, splitext
        filepath = self.filepath

        # change the menu title to the most recently chosen option
        preset_class = getattr(bpy.types, self.menu_idname)
        preset_class.bl_label = bpy.path.display_name(basename(filepath))

        ext = splitext(filepath)[1].lower()

        if ext not in {".py", ".xml"}:
            self.report({'ERROR'}, "unknown filetype: %r" % ext)
            return {'CANCELLED'}

        if hasattr(preset_class, "reset_cb"):
            preset_class.reset_cb(context)

        # execute the preset using script.python_file_run
        if ext == ".py":
            bpy.ops.script.python_file_run(filepath=filepath)
        elif ext == ".xml":
            import rna_xml
            rna_xml.xml_file_run(context,
                                 filepath,
                                 preset_class.preset_xml_map)

        if hasattr(preset_class, "post_cb"):
            preset_class.post_cb(context)

        return {'FINISHED'}


class AddPresetRender(AddPresetBase, Operator):
    """Add or remove a Render Preset"""
    bl_idname = "render.preset_add"
    bl_label = "Add Render Preset"
    preset_menu = "RENDER_MT_presets"

    preset_defines = [
        "scene = bpy.context.scene"
    ]

    preset_values = [
        "scene.render.field_order",
        "scene.render.fps",
        "scene.render.fps_base",
        "scene.render.pixel_aspect_x",
        "scene.render.pixel_aspect_y",
        "scene.render.resolution_percentage",
        "scene.render.resolution_x",
        "scene.render.resolution_y",
        "scene.render.use_fields",
        "scene.render.use_fields_still",
    ]

    preset_subdir = "render"


class AddPresetCamera(AddPresetBase, Operator):
    """Add or remove a Camera Preset"""
    bl_idname = "camera.preset_add"
    bl_label = "Add Camera Preset"
    preset_menu = "CAMERA_MT_presets"

    preset_defines = [
        "cam = bpy.context.camera"
    ]

    preset_subdir = "camera"

    use_focal_length: BoolProperty(
        name="Include Focal Length",
        description="Include focal length into the preset",
        options={'SKIP_SAVE'},
    )

    @property
    def preset_values(self):
        preset_values = [
            "cam.sensor_width",
            "cam.sensor_height",
            "cam.sensor_fit"
        ]
        if self.use_focal_length:
            preset_values.append("cam.lens")
            preset_values.append("cam.lens_unit")
        return preset_values


class AddPresetSafeAreas(AddPresetBase, Operator):
    """Add or remove a Safe Areas Preset"""
    bl_idname = "safe_areas.preset_add"
    bl_label = "Add Safe Area Preset"
    preset_menu = "SAFE_AREAS_MT_presets"

    preset_defines = [
        "safe_areas = bpy.context.scene.safe_areas"
    ]

    preset_values = [
        "safe_areas.title",
        "safe_areas.action",
        "safe_areas.title_center",
        "safe_areas.action_center",
    ]

    preset_subdir = "safe_areas"


class AddPresetSSS(AddPresetBase, Operator):
    """Add or remove a Subsurface Scattering Preset"""
    bl_idname = "material.sss_preset_add"
    bl_label = "Add SSS Preset"
    preset_menu = "MATERIAL_MT_sss_presets"

    preset_defines = [
        ("material = "
         "bpy.context.material.active_node_material "
         "if bpy.context.material.active_node_material "
         "else bpy.context.material")
    ]

    preset_values = [
        "material.subsurface_scattering.back",
        "material.subsurface_scattering.color",
        "material.subsurface_scattering.color_factor",
        "material.subsurface_scattering.error_threshold",
        "material.subsurface_scattering.front",
        "material.subsurface_scattering.ior",
        "material.subsurface_scattering.radius",
        "material.subsurface_scattering.scale",
        "material.subsurface_scattering.texture_factor",
    ]

    preset_subdir = "sss"


class AddPresetCloth(AddPresetBase, Operator):
    """Add or remove a Cloth Preset"""
    bl_idname = "cloth.preset_add"
    bl_label = "Add Cloth Preset"
    preset_menu = "CLOTH_MT_presets"

    preset_defines = [
        "cloth = bpy.context.cloth"
    ]

    preset_values = [
        "cloth.settings.air_damping",
        "cloth.settings.bending_stiffness",
        "cloth.settings.mass",
        "cloth.settings.quality",
        "cloth.settings.spring_damping",
        "cloth.settings.structural_stiffness",
    ]

    preset_subdir = "cloth"


class AddPresetFluid(AddPresetBase, Operator):
    """Add or remove a Fluid Preset"""
    bl_idname = "fluid.preset_add"
    bl_label = "Add Fluid Preset"
    preset_menu = "FLUID_MT_presets"

    preset_defines = [
        "fluid = bpy.context.fluid"
    ]

    preset_values = [
        "fluid.settings.viscosity_base",
        "fluid.settings.viscosity_exponent",
    ]

    preset_subdir = "fluid"


class AddPresetHairDynamics(AddPresetBase, Operator):
    """Add or remove a Hair Dynamics Preset"""
    bl_idname = "particle.hair_dynamics_preset_add"
    bl_label = "Add Hair Dynamics Preset"
    preset_menu = "PARTICLE_MT_hair_dynamics_presets"

    preset_defines = [
        "psys = bpy.context.particle_system",
        "cloth = bpy.context.particle_system.cloth",
        "settings = bpy.context.particle_system.cloth.settings",
        "collision = bpy.context.particle_system.cloth.collision_settings",
    ]

    preset_subdir = "hair_dynamics"

    preset_values = [
        "settings.quality",
        "settings.mass",
        "settings.bending_stiffness",
        "psys.settings.bending_random",
        "settings.bending_damping",
        "settings.air_damping",
        "settings.internal_friction",
        "settings.density_target",
        "settings.density_strength",
        "settings.voxel_cell_size",
        "settings.pin_stiffness",
    ]


class AddPresetSunSky(AddPresetBase, Operator):
    """Add or remove a Sky & Atmosphere Preset"""
    bl_idname = "lamp.sunsky_preset_add"
    bl_label = "Add Sunsky Preset"
    preset_menu = "LAMP_MT_sunsky_presets"

    preset_defines = [
        "sky = bpy.context.lamp.sky"
    ]

    preset_values = [
        "sky.atmosphere_extinction",
        "sky.atmosphere_inscattering",
        "sky.atmosphere_turbidity",
        "sky.backscattered_light",
        "sky.horizon_brightness",
        "sky.spread",
        "sky.sun_brightness",
        "sky.sun_intensity",
        "sky.sun_size",
        "sky.sky_blend",
        "sky.sky_blend_type",
        "sky.sky_color_space",
        "sky.sky_exposure",
    ]

    preset_subdir = "sunsky"


class AddPresetInteraction(AddPresetBase, Operator):
    """Add or remove an Application Interaction Preset"""
    bl_idname = "wm.interaction_preset_add"
    bl_label = "Add Interaction Preset"
    preset_menu = "USERPREF_MT_interaction_presets"

    preset_defines = [
        "user_preferences = bpy.context.user_preferences"
    ]

    preset_values = [
        "user_preferences.edit.use_drag_immediately",
        "user_preferences.edit.use_insertkey_xyz_to_rgb",
        "user_preferences.inputs.invert_mouse_zoom",
        "user_preferences.inputs.select_mouse",
        "user_preferences.inputs.use_emulate_numpad",
        "user_preferences.inputs.use_mouse_continuous",
        "user_preferences.inputs.use_mouse_emulate_3_button",
        "user_preferences.inputs.view_rotate_method",
        "user_preferences.inputs.view_zoom_axis",
        "user_preferences.inputs.view_zoom_method",
    ]

    preset_subdir = "interaction"
    
############################ Input System #####################################
def update_userprefs():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'USER_PREFERENCES':
                area.tag_redraw()

class AddInputMap(AddPresetBase, Operator):
    """Add an Input Map"""
    bl_idname = "wm.input_map_save"
    bl_label = "Add Input Map"
    
    def execute(self, context):
        if self.name == "":
            self.report({'WARNING'}, "AddInputMap Failed! name is missing")
            return {'CANCELLED'}
    
        wm = context.window_manager
        path = bpy.path.abspath("//KeyMapping/")
        
        input_map_data = {}
        
        wm.input_map_index = -1 # Force Input Map Update
        update_userprefs() # so the interface updates immediately after adding the new input
        
        if bpy.data.is_saved:
            # Make dir or remove Input Map
            if not os.path.exists(path):
                os.makedirs(path)
                    
            # Save Input Map in JSON Format
            filepath = os.path.join(path, "{}.json".format(self.name))
            with open(filepath, 'w') as file:
                json.dump(input_map_data, file, indent=4)
                
            self.report({'INFO'}, "Input map saved to {}".format(filepath))
            
        else:
            self.report({'ERROR'}, "You need to save the .range file first!")
        return {'FINISHED'}
        
class AddInputMap_Rename(AddPresetBase, Operator):
    """Rename an Input Map"""
    bl_idname = "wm.input_map_rename"
    bl_label = "Rename Input Map"

    input_map_name: StringProperty(default="", options={'HIDDEN'})
    
    def execute(self, context):
        if self.name == "":
            self.report({'WARNING'}, "Rename failed! name is missing")
            return {'CANCELLED'}
            
        if self.name == self.input_map_name:
            self.report({'WARNING'}, "Rename failed! name is the same")
            return {'CANCELLED'}
        
        wm = context.window_manager
        path = bpy.path.abspath("//KeyMapping/")
        
        wm.input_map_index = -1 # Force Input Table Update
        update_userprefs()
        
        old_filepath = os.path.join(path, self.input_map_name + ".json")
        new_filepath = os.path.join(path, self.name + ".json")
        
        os.rename(old_filepath, new_filepath)
        
        return {'FINISHED'}
        
class AddInputTable(AddPresetBase, Operator):
    """Add an Input Table"""
    bl_idname = "wm.input_table_save"
    bl_label = "Add Input Table"

    input_map_name: StringProperty(default="", options={'HIDDEN'})
    
    def execute(self, context):
        if self.name == "":
            self.report({'WARNING'}, "AddInputTable Failed! name is missing")
            return {'CANCELLED'}
            
        if self.input_map_name == "":
            self.report({'WARNING'}, "AddInputTable Failed! input map is missing")
            return {'CANCELLED'}
    
        wm = context.window_manager
        path = bpy.path.abspath("//KeyMapping/")
        filepath = os.path.join(path, self.input_map_name)
        
        wm.input_table_index = -1 # Force Input Table Update
        update_userprefs()
        
        with open(filepath, 'r+') as file: 
            input_table_list = json.load(file)
            
            # Save Table
            input_table_list[self.name] = {
            "Type": "BUTTON",
            "ControlType": "VECTOR1D", # Only used if type "VALUE" selected
            "Bindings": {},
            "Processors": {}
            }
            self.report({'INFO'}, "Input Table Added")
            
            # Save
            file.seek(0)
            json.dump(input_table_list, file, indent=4)
            file.truncate()
        return {'FINISHED'}
        
class AddInputTable_Rename(AddPresetBase, Operator):
    """Rename an Input Table"""
    bl_idname = "wm.input_table_rename"
    bl_label = "Rename Input Table"

    input_map_name: StringProperty(default="", options={'HIDDEN'})
    input_table_name: StringProperty(default="", options={'HIDDEN'})
    
    def execute(self, context):
        if self.name == "":
            self.report({'WARNING'}, "Rename failed! name is missing")
            return {'CANCELLED'}
            
        if self.name == self.input_table_name:
            self.report({'WARNING'}, "Rename failed! name is the same")
            return {'CANCELLED'}
    
        wm = context.window_manager
        path = bpy.path.abspath("//KeyMapping/")
        filepath = os.path.join(path, self.input_map_name)
        
        wm.input_table_index = -1 # Force Input Table Update
        update_userprefs()
        
        with open(filepath, 'r+') as file: 
            input_table_list = json.load(file)
            
            input_table_list[self.name] = input_table_list[self.input_table_name]
            del input_table_list[self.input_table_name]
            self.report({'INFO'}, "Input Table Renamed!")
            
            # Save
            file.seek(0)
            json.dump(input_table_list, file, indent=4)
            file.truncate()
        return {'FINISHED'}
        
class AddInputBinding(AddPresetBase, Operator):
    """Add an Input Binding"""
    bl_idname = "wm.input_binding_save"
    bl_label = "Add Input Binding"
    
    table_type: bpy.props.EnumProperty(
        name="Binding Type",
        description="Binding type",
        items=[
            ("BINDING", "Binding", "Add a simple button binding"),
            ("COMPOSITEPADS", "Up\Down\Left\Right Composite", "Add a Up\Down\Left\Right Composite"),
            ("COMPOSITEPADS3D", "Up\Down\Left\Right\Forward\Backward Composite", "Add a Up\Down\Left\Right\FORWARD\BACKWARD Composite")
        ]
    )
    
    table_format = {
    "BINDING" : {
        "BUTTON" : "0"
        },
    "COMPOSITEPADS" : {
        "UP" : "0",
        "DOWN" : "0",
        "LEFT" : "0",
        "RIGHT" : "0"
        },
    "COMPOSITEPADS3D" : {
        "UP" : "0",
        "DOWN" : "0",
        "LEFT" : "0",
        "RIGHT" : "0",
        "FORWARD" : "0",
        "BACKWARD" : "0",
        },
    }
    
    input_map_name: StringProperty(default="", options={'HIDDEN'})
    input_table_name: StringProperty(default="", options={'HIDDEN'})
    
    def execute(self, context):
        if self.name == "":
            self.report({'WARNING'}, "AddInputBinding Failed! name is missing")
            return {'CANCELLED'}
    
        wm = context.window_manager
        path = bpy.path.abspath("//KeyMapping/")
        filepath = os.path.join(path, self.input_map_name)
        
        wm.update_binding_properties = True # Update Bindings
        update_userprefs()
        
        with open(filepath, 'r+') as file: 
            input_table_list = json.load(file)
            #print(self.table_format[self.table_type])
            # Save Table
            input_table_list[self.input_table_name]["Bindings"][self.name] = {
                "PERIPHERALTYPE" : { "TYPE": "KEYBOARD", "INDEX" : "0", "SENSITIVITY" : 1.0 },
                self.table_type : self.table_format[self.table_type]
            }

            self.report({'INFO'}, "Input Binding Added")
            #print(input_table_list)
            
            # Save
            file.seek(0)
            json.dump(input_table_list, file, indent=4)
            file.truncate()
            
        return {'FINISHED'}
        
class AddInputBinding_Rename(AddPresetBase, Operator):
    """Rename an Binding"""
    bl_idname = "wm.input_binding_rename"
    bl_label = "Rename Input Binding"

    input_map_name: StringProperty(default="", options={'HIDDEN'})
    input_table_name: StringProperty(default="", options={'HIDDEN'})
    input_binding_name: StringProperty(default="", options={'HIDDEN'})
    
    def execute(self, context):
        if self.name == "":
            self.report({'WARNING'}, "Rename failed! name is missing")
            return {'CANCELLED'}
            
        if self.name == self.input_binding_name:
            self.report({'WARNING'}, "Rename failed! name is the same")
            return {'CANCELLED'}
    
        wm = context.window_manager
        path = bpy.path.abspath("//KeyMapping/")
        filepath = os.path.join(path, self.input_map_name)
        
        wm.update_binding_properties = True # Update bindings
        update_userprefs()
        
        with open(filepath, 'r+') as file: 
            input_table_list = json.load(file)
            
            input_table_list[self.input_table_name]["Bindings"][self.name] = input_table_list[self.input_table_name]["Bindings"][self.input_binding_name]
            del input_table_list[self.input_table_name]["Bindings"][self.input_binding_name]
            self.report({'INFO'}, "Input Binding Renamed!")
            
            # Save
            file.seek(0)
            json.dump(input_table_list, file, indent=4)
            file.truncate()
        return {'FINISHED'}
        
class AddProcessor(AddPresetBase, Operator):
    """Add an Processor"""
    bl_idname = "wm.input_add_processor"
    bl_label = "Add Processor"
    
    table_processor_type: bpy.props.EnumProperty(
        name="Processor",
        description="Binding type",
        items=[
            ("INVERTVALUES", "Invert", "Add a Invert Processor"),
            ("INVERTVALUES2D", "Invert Vector2D", "Add a Invert Processor 2D"),
            ("INVERTVALUES3D", "Invert Vector3D", "Add a Invert Processor 3D"),
            
            ("SCALEVALUES", "Scale", "Add a Scale Values Processor"),
            ("SCALEVALUES2D", "Scale Vector2D", "Add a Scale Values Processor 2D"),
            ("SCALEVALUES3D", "Scale Vector3D", "Add a Scale Values Processor 3D"),
            
            ("LERPVALUES", "Lerp", "Add a Lerp Values Processor"),
            ("DEADZONE", "Axis Deadzone", "Add a Lerp Values Processor"),
        ]
    )
    
    table_processor_format = {
    "INVERTVALUES" : {
        "X" : 0
        },
    "INVERTVALUES2D" : {
        "X" : 0,
        "Y" : 0
        },
    "INVERTVALUES3D" : {
        "X" : 0,
        "Y" : 0,
        "Z" : 0
        },
        
    "SCALEVALUES" : {
        "X" : 0.0
        },
    "SCALEVALUES2D" : {
        "X" : 0.0,
        "Y" : 0.0
        },
    "SCALEVALUES3D" : {
        "X" : 0.0,
        "Y" : 0.0,
        "Z" : 0.0
        },
        
    "LERPVALUES" : {
        "X" : 0.0 # value
        },
    "DEADZONE" : {
        "X" : 0.125, # min
        "Y" : 0.925 # max
        },
    }
    
    name: StringProperty(default="", options={'HIDDEN'}) # Hide default name property
    input_map_name: StringProperty(default="", options={'HIDDEN'})
    input_table_name: StringProperty(default="", options={'HIDDEN'})
    
    def execute(self, context):
        wm = context.window_manager
        path = bpy.path.abspath("//KeyMapping/")
        filepath = os.path.join(path, self.input_map_name)
        
        wm.update_binding_properties = True # Update Bindings
        update_userprefs()
        
        with open(filepath, 'r+') as file: 
            input_table_list = json.load(file)
            #print(self.table_processor_format[self.table_processor_type])
            # Save Table
            input_table_list[self.input_table_name]["Processors"][self.table_processor_type] = self.table_processor_format[self.table_processor_type]

            self.report({'INFO'}, "Processor Added")
            #print(input_table_list)
            
            # Save
            file.seek(0)
            json.dump(input_table_list, file, indent=4)
            file.truncate()
            
        return {'FINISHED'}
        
############################ End Input System #####################################

class AddPresetTrackingCamera(AddPresetBase, Operator):
    """Add or remove a Tracking Camera Intrinsics Preset"""
    bl_idname = "clip.camera_preset_add"
    bl_label = "Add Camera Preset"
    preset_menu = "CLIP_MT_camera_presets"

    preset_defines = [
        "camera = bpy.context.edit_movieclip.tracking.camera"
    ]

    preset_subdir = "tracking_camera"

    use_focal_length: BoolProperty(
        name="Include Focal Length",
        description="Include focal length into the preset",
        options={'SKIP_SAVE'},
        default=True
    )

    @property
    def preset_values(self):
        preset_values = [
            "camera.sensor_width",
            "camera.pixel_aspect",
            "camera.k1",
            "camera.k2",
            "camera.k3"
        ]
        if self.use_focal_length:
            preset_values.append("camera.units")
            preset_values.append("camera.focal_length")
        return preset_values


class AddPresetTrackingTrackColor(AddPresetBase, Operator):
    """Add or remove a Clip Track Color Preset"""
    bl_idname = "clip.track_color_preset_add"
    bl_label = "Add Track Color Preset"
    preset_menu = "CLIP_MT_track_color_presets"

    preset_defines = [
        "track = bpy.context.edit_movieclip.tracking.tracks.active"
    ]

    preset_values = [
        "track.color",
        "track.use_custom_color"
    ]

    preset_subdir = "tracking_track_color"


class AddPresetTrackingSettings(AddPresetBase, Operator):
    """Add or remove a motion tracking settings preset"""
    bl_idname = "clip.tracking_settings_preset_add"
    bl_label = "Add Tracking Settings Preset"
    preset_menu = "CLIP_MT_tracking_settings_presets"

    preset_defines = [
        "settings = bpy.context.edit_movieclip.tracking.settings"
    ]

    preset_values = [
        "settings.default_correlation_min",
        "settings.default_pattern_size",
        "settings.default_search_size",
        "settings.default_frames_limit",
        "settings.default_pattern_match",
        "settings.default_margin",
        "settings.default_motion_model",
        "settings.use_default_brute",
        "settings.use_default_normalization",
        "settings.use_default_mask",
        "settings.use_default_red_channel",
        "settings.use_default_green_channel",
        "settings.use_default_blue_channel"
        "settings.default_weight"
    ]

    preset_subdir = "tracking_settings"


class AddPresetNodeColor(AddPresetBase, Operator):
    """Add or remove a Node Color Preset"""
    bl_idname = "node.node_color_preset_add"
    bl_label = "Add Node Color Preset"
    preset_menu = "NODE_MT_node_color_presets"

    preset_defines = [
        "node = bpy.context.active_node"
    ]

    preset_values = [
        "node.color",
        "node.use_custom_color"
    ]

    preset_subdir = "node_color"


class AddPresetInterfaceTheme(AddPresetBase, Operator):
    """Add or remove a theme preset"""
    bl_idname = "wm.interface_theme_preset_add"
    bl_label = "Add Theme Preset"
    preset_menu = "USERPREF_MT_interface_theme_presets"
    preset_subdir = "interface_theme"

class AddPresetKeyconfig(AddPresetBase, Operator):
    """Add or remove a Key-config Preset"""
    bl_idname = "wm.keyconfig_preset_add"
    bl_label = "Add Keyconfig Preset"
    preset_menu = "USERPREF_MT_keyconfigs"
    preset_subdir = "keyconfig"

    def add(self, context, filepath):
        bpy.ops.wm.keyconfig_export(filepath=filepath)
        bpy.utils.keyconfig_set(filepath)

    def pre_cb(self, context):
        keyconfigs = bpy.context.window_manager.keyconfigs
        if self.remove_active:
            preset_menu_class = getattr(bpy.types, self.preset_menu)
            preset_menu_class.bl_label = keyconfigs.active.name

    def post_cb(self, context):
        keyconfigs = bpy.context.window_manager.keyconfigs
        if self.remove_active:
            keyconfigs.remove(keyconfigs.active)


class AddPresetOperator(AddPresetBase, Operator):
    """Add or remove an Operator Preset"""
    bl_idname = "wm.operator_preset_add"
    bl_label = "Operator Preset"
    preset_menu = "WM_MT_operator_presets"

    operator: StringProperty(
        name="Operator",
        maxlen=64,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    preset_defines = [
        "op = bpy.context.active_operator",
    ]

    @property
    def preset_subdir(self):
        return AddPresetOperator.operator_path(self.operator)

    @property
    def preset_values(self):
        properties_blacklist = Operator.bl_rna.properties.keys()

        prefix, suffix = self.operator.split("_OT_", 1)
        op = getattr(getattr(bpy.ops, prefix.lower()), suffix)
        operator_rna = op.get_rna_type()
        del op

        ret = []
        for prop_id, prop in operator_rna.properties.items():
            if not (prop.is_hidden or prop.is_skip_save):
                if prop_id not in properties_blacklist:
                    ret.append("op.%s" % prop_id)

        return ret

    @staticmethod
    def operator_path(operator):
        import os
        prefix, suffix = operator.split("_OT_", 1)
        return os.path.join("operator", "%s.%s" % (prefix.lower(), suffix))


class WM_MT_operator_presets(Menu):
    bl_label = "Operator Presets"

    def draw(self, context):
        self.operator = context.active_operator.bl_idname

        # dummy 'default' menu item
        layout = self.layout
        layout.operator("wm.operator_defaults")
        layout.separator()

        Menu.draw_preset(self, context)

    @property
    def preset_subdir(self):
        return AddPresetOperator.operator_path(self.operator)

    preset_operator = "script.execute_preset"


class AddPresetUnitsLength(AddPresetBase, Operator):
    """Add or remove length units preset"""
    bl_idname = "scene.units_length_preset_add"
    bl_label = "Add Length Units Preset"
    preset_menu = "SCENE_MT_units_length_presets"

    preset_defines = [
        "scene = bpy.context.scene"
    ]

    preset_values = [
        "scene.unit_settings.system",
        "scene.unit_settings.scale_length",
    ]

    preset_subdir = "units_length"


class AddPresetGPUParticle(AddPresetBase, Operator):
    """Add or remove a GPU Particle Preset"""
    bl_idname = "particle.gpu_particle_preset_add"
    bl_label = "Add GPU Particle Preset"
    preset_menu = "PARTICLE_MT_gpu_particle_presets"

    preset_defines = [
        "gp = bpy.context.object.gpu_particles"
    ]

    preset_values = [
        "gp.gravity",
        "gp.lifetime",
        "gp.emitter_position",
        "gp.emitter_radius",
        "gp.velocity",
        "gp.velocity_randomness",
        "gp.size",
        "gp.end_size",
        "gp.color",
        "gp.end_color",
        "gp.emission_direction",
        "gp.emission_angle",
        "gp.particle_count",
        "gp.texture",
        "gp.use_size_curve",
        "gp.use_color_curve",
        "gp.blend_mode",
    ]

    preset_subdir = "gpu_particle"

    def post_cb(self, context):
        preset_menu_class = getattr(bpy.types, self.preset_menu)
        if context.object is not None:
            context.object.gpu_particle_active_preset = preset_menu_class.bl_label


classes = (
    AddPresetCamera,
    AddPresetCloth,
    AddPresetFluid,
    AddPresetGPUParticle,
    AddPresetHairDynamics,
    AddPresetInteraction,
    AddInputMap,
    AddInputMap_Rename,
    AddInputTable,
    AddInputTable_Rename,
    AddInputBinding,
    AddInputBinding_Rename,
    AddProcessor,
    AddPresetInterfaceTheme,
    AddPresetKeyconfig,
    AddPresetNodeColor,
    AddPresetOperator,
    AddPresetRender,
    AddPresetSSS,
    AddPresetSafeAreas,
    AddPresetSunSky,
    AddPresetTrackingCamera,
    AddPresetTrackingSettings,
    AddPresetTrackingTrackColor,
    AddPresetUnitsLength,
    ExecutePreset,
    WM_MT_operator_presets,
)
