"""Operadores do diálogo sem código do objeto Text (painel Game Text >
Text Box).  O runtime é o módulo range_text_dialogue."""

import bpy
from bpy.props import EnumProperty
from bpy.types import Operator

MODULE = "range_text_dialogue.main"
PROPS = (("td_speed", "FLOAT", 40.0), ("td_end", "STRING", "HIDE"), ("td_message", "STRING", ""))


def dialogue_controller(obj):
    return next((c for c in obj.game.controllers
                 if c.type == "PYTHON" and c.mode == "MODULE" and c.module == MODULE), None)


class OBJECT_OT_range_text_dialogue_setup(Operator):
    """Typewriter and pages without code: Enter/Space/click completes the page, then goes to the next one"""
    bl_idname = "object.range_text_dialogue_setup"
    bl_label = "Setup Dialogue"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "FONT"

    def execute(self, context):
        obj = context.object
        if dialogue_controller(obj) is None:
            bpy.ops.logic.sensor_add(type="ALWAYS", name="Dialogue", object=obj.name)
            bpy.ops.logic.controller_add(type="PYTHON", name="Dialogue", object=obj.name)
            sensor, controller = obj.game.sensors[-1], obj.game.controllers[-1]
            sensor.use_pulse_true_level = True
            controller.mode = "MODULE"
            controller.module = MODULE
            sensor.link(controller)
        for name, kind, value in PROPS:
            if name not in obj.game.properties:
                # game_property_new age no objeto ativo, que é o do painel.
                bpy.ops.object.game_property_new(type=kind, name=name)
                obj.game.properties[name].value = value
        # Sem altura não há páginas: começa com 3 linhas.
        tbox = obj.data.text_boxes[0]
        if tbox.height <= 0.0:
            tbox.height = 3 * obj.data.size * obj.data.space_line
        if tbox.width <= 0.0:
            tbox.width = 8.0 * obj.data.size
        return {'FINISHED'}


class OBJECT_OT_range_text_dialogue_remove(Operator):
    """Remove the dialogue logic and its properties from this Text object"""
    bl_idname = "object.range_text_dialogue_remove"
    bl_label = "Remove Dialogue"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and dialogue_controller(obj) is not None

    def execute(self, context):
        obj = context.object
        controller = dialogue_controller(obj)
        for sensor in list(obj.game.sensors):
            if sensor.name == "Dialogue" and sensor.type == "ALWAYS":
                bpy.ops.logic.sensor_remove(sensor=sensor.name, object=obj.name)
        bpy.ops.logic.controller_remove(controller=controller.name, object=obj.name)
        for name, _kind, _value in PROPS:
            index = obj.game.properties.find(name)
            if index >= 0:
                bpy.ops.object.game_property_remove(index=index)
        return {'FINISHED'}


class OBJECT_OT_range_text_dialogue_end(Operator):
    """What happens after the last page"""
    bl_idname = "object.range_text_dialogue_end"
    bl_label = "Dialogue End"
    bl_options = {'REGISTER', 'UNDO'}

    end = EnumProperty(items=(
        ("HIDE", "Hide", "Hides the text object"),
        ("RESTART", "Restart", "Goes back to the first page"),
        ("KEEP", "Keep", "Keeps the last page on screen")))

    def execute(self, context):
        prop = context.object.game.properties.get("td_end")
        if prop is None:
            return {'CANCELLED'}
        prop.value = self.end
        return {'FINISHED'}


classes = (OBJECT_OT_range_text_dialogue_setup, OBJECT_OT_range_text_dialogue_remove,
           OBJECT_OT_range_text_dialogue_end)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
