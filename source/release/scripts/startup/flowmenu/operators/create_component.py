import os

from bpy.types import Operator
from bpy.props import StringProperty

from ..functions.set_scripts_dir import set_scripts_dir
from ..var_globals import template_component


class FLOWMENU_OT_create_component(Operator):
    bl_label = "Create Component"
    bl_idname = "wm.flowmenu_ot_create_component"

    new_module: StringProperty(default="")
    new_class: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def check(self, context):
        return True

    def draw(self, context):
        layout = self.layout.column()
        layout.prop(self, "new_module", text="New module folder (optional)")
        layout.prop(self, "new_class", text="Class")

        if ((self.new_module and not self.new_module.isidentifier()) or
                (self.new_class and not self.new_class.isidentifier())):
            layout.alert = True
            layout.label(text="Use valid Python identifiers")

    def execute(self, context):
        game_file_path = set_scripts_dir()
        if not game_file_path:
            self.report({'ERROR'}, "Save the .blend file before creating a component.")
            return {"CANCELLED"}

        if not self.new_class or not self.new_class.isidentifier():
            self.report({'ERROR'}, "Class name must be a valid Python identifier.")
            return {"CANCELLED"}
        if self.new_module and not self.new_module.isidentifier():
            self.report({'ERROR'}, "Module folder must be a valid Python identifier.")
            return {"CANCELLED"}

        scripts_dir = os.path.join(game_file_path, "scripts")
        target_parent = scripts_dir
        collection = context.window_manager.collection_modules
        active_index = context.window_manager.collection_modules_active
        if active_index < len(collection):
            selected_module = collection[active_index].value
            matches = []
            for root, dirs, files in os.walk(scripts_dir):
                if os.path.basename(root) == selected_module:
                    matches.append(root)
            if len(matches) == 1:
                target_parent = matches[0]
            elif len(matches) > 1:
                self.report({'ERROR'}, "Module folder is ambiguous; choose a unique module name.")
                return {"CANCELLED"}

        target_dir = os.path.join(target_parent, self.new_module) if self.new_module else target_parent
        filepath = os.path.join(target_dir, "{}.py".format(self.new_class))
        if os.path.exists(filepath):
            self.report({'ERROR'}, "Component file already exists: {}".format(filepath))
            return {"CANCELLED"}

        try:
            if not os.path.isdir(target_dir):
                os.makedirs(target_dir)
            with open(filepath, "w", encoding="utf-8") as fp:
                fp.write(template_component % self.new_class)
        except OSError as exc:
            self.report({'ERROR'}, "Could not create component: {}".format(exc))
            return {"CANCELLED"}

        self.new_module = ""
        self.new_class = ""
        self.report({'INFO'}, "Component created: {}".format(filepath))
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
