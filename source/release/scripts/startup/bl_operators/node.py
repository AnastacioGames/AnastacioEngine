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

# <pep8-80 compliant>
from __future__ import annotations

import bpy
import nodeitems_utils
from bpy.types import (
    Operator,
    PropertyGroup,
)
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)


class NodeSetting(PropertyGroup):
    value: StringProperty(
        name="Value",
        description="Python expression to be evaluated "
        "as the initial node setting",
        default="",
    )


# Base class for node 'Add' operators
class NodeAddOperator:

    type: StringProperty(
        name="Node Type",
        description="Node type",
    )
    use_transform: BoolProperty(
        name="Use Transform",
        description="Start transform operator after inserting the node",
        default=False,
    )
    settings: CollectionProperty(
        name="Settings",
        description="Settings to be applied on the newly created node",
        type=NodeSetting,
        options={'SKIP_SAVE'},
    )

    @staticmethod
    def store_mouse_cursor(context, event):
        space = context.space_data
        tree = space.edit_tree

        # convert mouse position to the View2D for later node placement
        if context.region.type == 'WINDOW':
            # convert mouse position to the View2D for later node placement
            space.cursor_location_from_region(
                event.mouse_region_x, event.mouse_region_y)
        else:
            space.cursor_location = tree.view_center

    # XXX explicit node_type argument is usually not necessary,
    # but required to make search operator work:
    # add_search has to override the 'type' property
    # since it's hardcoded in bpy_operator_wrap.c ...
    def create_node(self, context, node_type=None):
        space = context.space_data
        tree = space.edit_tree

        if node_type is None:
            node_type = self.type

        # select only the new node
        for n in tree.nodes:
            n.select = False

        node = tree.nodes.new(type=node_type)

        for setting in self.settings:
            # XXX catch exceptions here?
            value = eval(setting.value)

            try:
                setattr(node, setting.name, value)
            except AttributeError as e:
                self.report(
                    {'ERROR_INVALID_INPUT'},
                    "Node has no attribute " + setting.name)
                print(str(e))
                # Continue despite invalid attribute

        node.select = True
        tree.nodes.active = node
        node.location = space.cursor_location
        return node

    @classmethod
    def poll(cls, context):
        space = context.space_data
        # needs active node editor and a tree to add nodes to
        return ((space.type == 'NODE_EDITOR') and
                space.edit_tree and not space.edit_tree.library)

    # Default execute simply adds a node
    def execute(self, context):
        if self.properties.is_property_set("type"):
            self.create_node(context)
            return {'FINISHED'}
        else:
            return {'CANCELLED'}

    # Default invoke stores the mouse position to place the node correctly
    # and optionally invokes the transform operator
    def invoke(self, context, event):
        self.store_mouse_cursor(context, event)
        result = self.execute(context)

        if self.use_transform and ('FINISHED' in result):
            # removes the node again if transform is canceled
            bpy.ops.node.translate_attach_remove_on_cancel('INVOKE_DEFAULT')

        return result


# Simple basic operator for adding a node
class NODE_OT_add_node(NodeAddOperator, Operator):
    '''Add a node to the active tree'''
    bl_idname = "node.add_node"
    bl_label = "Add Node"
    bl_options = {'REGISTER', 'UNDO'}


# Add a node and link it to an existing socket
class NODE_OT_add_and_link_node(NodeAddOperator, Operator):
    '''Add a node to the active tree and link to an existing socket'''
    bl_idname = "node.add_and_link_node"
    bl_label = "Add and Link Node"
    bl_options = {'REGISTER', 'UNDO'}

    link_socket_index: IntProperty(
        name="Link Socket Index",
        description="Index of the socket to link",
    )

    def execute(self, context):
        space = context.space_data
        ntree = space.edit_tree

        node = self.create_node(context)
        if not node:
            return {'CANCELLED'}

        to_socket = getattr(context, "link_to_socket", None)
        if to_socket:
            ntree.links.new(node.outputs[self.link_socket_index], to_socket)

        from_socket = getattr(context, "link_from_socket", None)
        if from_socket:
            ntree.links.new(from_socket, node.inputs[self.link_socket_index])

        return {'FINISHED'}


class NODE_OT_add_search(NodeAddOperator, Operator):
    '''Add a node to the active tree'''
    bl_idname = "node.add_search"
    bl_label = "Search and Add Node"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "node_item"

    _enum_item_hack = []

    # Create an enum list from node items
    def node_enum_items(self, context):
        enum_items = NODE_OT_add_search._enum_item_hack
        enum_items.clear()

        for index, item in enumerate(nodeitems_utils.node_items_iter(context)):
            if isinstance(item, nodeitems_utils.NodeItem):
                nodetype = getattr(bpy.types, item.nodetype, None)
                if nodetype:
                    enum_items.append(
                        (str(index),
                         item.label,
                         nodetype.bl_rna.description,
                         index,
                         ))
        return enum_items

    # Look up the item based on index
    def find_node_item(self, context):
        node_item = int(self.node_item)
        for index, item in enumerate(nodeitems_utils.node_items_iter(context)):
            if index == node_item:
                return item
        return None

    node_item: EnumProperty(
        name="Node Type",
        description="Node type",
        items=NODE_OT_add_search.node_enum_items,
    )

    def execute(self, context):
        item = self.find_node_item(context)

        # no need to keep
        self._enum_item_hack.clear()

        if item:
            # apply settings from the node item
            for setting in item.settings.items():
                ops = self.settings.add()
                ops.name = setting[0]
                ops.value = setting[1]

            self.create_node(context, item.nodetype)

            if self.use_transform:
                bpy.ops.node.translate_attach_remove_on_cancel(
                    'INVOKE_DEFAULT')

            return {'FINISHED'}
        else:
            return {'CANCELLED'}

    def invoke(self, context, event):
        self.store_mouse_cursor(context, event)
        # Delayed execution in the search popup
        context.window_manager.invoke_search_popup(self)
        return {'CANCELLED'}


class NODE_OT_collapse_hide_unused_toggle(Operator):
    '''Toggle collapsed nodes and hide unused sockets'''
    bl_idname = "node.collapse_hide_unused_toggle"
    bl_label = "Collapse and Hide Unused Sockets"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        # needs active node editor and a tree
        return ((space.type == 'NODE_EDITOR') and
                (space.edit_tree and not space.edit_tree.library))

    def execute(self, context):
        space = context.space_data
        tree = space.edit_tree

        for node in tree.nodes:
            if node.select:
                hide = (not node.hide)

                node.hide = hide
                # Note: connected sockets are ignored internally
                for socket in node.inputs:
                    socket.hide = hide
                for socket in node.outputs:
                    socket.hide = hide

        return {'FINISHED'}


class NODE_OT_tree_path_parent(Operator):
    '''Go to parent node tree'''
    bl_idname = "node.tree_path_parent"
    bl_label = "Parent Node Tree"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        # needs active node editor and a tree
        return (space.type == 'NODE_EDITOR' and len(space.path) > 1)

    def execute(self, context):
        space = context.space_data

        space.path.pop()

        return {'FINISHED'}


class NODE_OT_damage_mix_add(Operator):
    """Mix the material's surface with bare/rusty metal where the object """ \
        """was hit (Damage node mask, game engine)"""
    bl_idname = "node.damage_mix_add"
    bl_label = "Add Damage Mix"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob is not None and ob.active_material is not None

    def execute(self, context):
        mat = context.object.active_material
        mat.use_nodes = True
        tree = mat.node_tree
        nodes, links = tree.nodes, tree.links

        output = None
        for node in nodes:
            if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
                output = node
                break
        if output is None:
            output = nodes.new("ShaderNodeOutputMaterial")
            output.location = (300.0, 0.0)
        surface = output.inputs["Surface"]

        if surface.is_linked:
            paint_socket = surface.links[0].from_socket
            if paint_socket.node.bl_idname == "ShaderNodeMixShader" and \
                    paint_socket.node.label == "Damage Mix":
                self.report({'INFO'}, "The material already has a Damage Mix")
                return {'CANCELLED'}
        else:
            paint = nodes.new("ShaderNodeBsdfPrincipled")
            paint.location = output.location.x - 600.0, output.location.y
            paint_socket = paint.outputs[0]

        x, y = output.location
        output.location = x + 200.0, y

        damage = nodes.new("ShaderNodeDamage")
        damage.location = x - 400.0, y + 300.0
        damage.inputs["Softness"].default_value = 0.5

        metal = nodes.new("ShaderNodeBsdfPrincipled")
        metal.label = "Damaged Metal"
        metal.location = x - 400.0, y - 250.0
        metal.inputs["Base Color"].default_value = (0.32, 0.13, 0.05, 1.0)
        metal.inputs["Metallic"].default_value = 1.0
        metal.inputs["Roughness"].default_value = 0.65

        mix = nodes.new("ShaderNodeMixShader")
        mix.label = "Damage Mix"
        mix.location = x, y

        links.new(damage.outputs["Mask"], mix.inputs["Fac"])
        links.new(paint_socket, mix.inputs[1])
        links.new(metal.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], surface)
        return {'FINISHED'}


# Shader presets (game engine): each preset is an editable node group, open it (Tab) to see how
# it works. The groups only use nodes that exist in both shading systems and give plain values
# (Color, Alpha, Offset), so they plug into any material.

_SHADER_PRESETS = (
    ('FUR', "Fur", "Fur Shells strands with a root to tip color (Alpha Clip)"),
    ('GRASS', "Grass", "Long Fur Shells strands for grass on a ground mesh (Alpha Clip)"),
    ('TOON_RIM', "Toon + Rim", "Flat color with a rim light from the Fresnel"),
    ('TOON_OUTLINE', "Toon Outline", "Color with an inverted hull outline"),
    ('DISSOLVE', "Dissolve", "Noise dissolve with a glowing edge (Alpha Clip)"),
    ('WATER_WAVES', "Water Waves",
     "Vertex waves (Offset goes to the Material Output Vertex Offset) and a Fresnel tint"),
)


def shader_presets():
    return _SHADER_PRESETS


def _preset_group(name, inputs, outputs):
    group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    for socket_type, socket_name, value in inputs:
        socket = group.inputs.new(socket_type, socket_name)
        if value is not None:
            socket.default_value = value
    for socket_type, socket_name in outputs:
        group.outputs.new(socket_type, socket_name)
    gin = group.nodes.new("NodeGroupInput")
    gin.location = (-600.0, 0.0)
    gout = group.nodes.new("NodeGroupOutput")
    gout.location = (400.0, 0.0)
    return group, gin, gout


def _preset_node(group, idname, location, **values):
    node = group.nodes.new(idname)
    node.location = location
    for key, value in values.items():
        if key in node.inputs:
            node.inputs[key].default_value = value
        else:
            setattr(node, key, value)
    return node


def _build_fur(name, length, layers, density, root, tip):
    group, gin, gout = _preset_group(
        name,
        (('NodeSocketColor', "Root Color", root), ('NodeSocketColor', "Tip Color", tip)),
        (('NodeSocketColor', "Color"), ('NodeSocketFloat', "Alpha")))
    links = group.links
    # Length and Layers build the geometry stage: change them on the Fur Shells node itself.
    fur = _preset_node(group, "ShaderNodeFurShells", (-300.0, -150.0),
                       Length=length, Layers=layers, Density=density)
    mix = _preset_node(group, "ShaderNodeMixRGB", (100.0, 100.0))
    links.new(fur.outputs["Layer"], mix.inputs["Fac"])
    links.new(gin.outputs["Root Color"], mix.inputs["Color1"])
    links.new(gin.outputs["Tip Color"], mix.inputs["Color2"])
    links.new(mix.outputs["Color"], gout.inputs["Color"])
    links.new(fur.outputs["Alpha"], gout.inputs["Alpha"])
    return group


def _build_toon_rim(name):
    group, gin, gout = _preset_group(
        name,
        (('NodeSocketColor', "Color", (0.8, 0.3, 0.2, 1.0)),
         ('NodeSocketColor', "Rim Color", (1.0, 0.9, 0.7, 1.0)),
         ('NodeSocketFloat', "Rim Size", 0.6)),
        (('NodeSocketColor', "Color"),))
    links = group.links
    fresnel = _preset_node(group, "ShaderNodeFresnel", (-350.0, 150.0))
    step = _preset_node(group, "ShaderNodeMath", (-150.0, 150.0), operation='GREATER_THAN')
    mix = _preset_node(group, "ShaderNodeMixRGB", (100.0, 50.0))
    links.new(fresnel.outputs["Fac"], step.inputs[0])
    links.new(gin.outputs["Rim Size"], step.inputs[1])
    links.new(step.outputs[0], mix.inputs["Fac"])
    links.new(gin.outputs["Color"], mix.inputs["Color1"])
    links.new(gin.outputs["Rim Color"], mix.inputs["Color2"])
    links.new(mix.outputs["Color"], gout.inputs["Color"])
    return group


def _build_toon_outline(name):
    group, gin, gout = _preset_group(
        name,
        (('NodeSocketColor', "Color", (0.8, 0.8, 0.8, 1.0)),
         ('NodeSocketColor', "Outline Color", (0.0, 0.0, 0.0, 1.0))),
        (('NodeSocketColor', "Color"),))
    links = group.links
    outline = _preset_node(group, "ShaderNodeOutline", (-300.0, 150.0), Width=0.02)
    mix = _preset_node(group, "ShaderNodeMixRGB", (100.0, 50.0))
    links.new(outline.outputs["Fac"], mix.inputs["Fac"])
    links.new(gin.outputs["Color"], mix.inputs["Color1"])
    links.new(gin.outputs["Outline Color"], mix.inputs["Color2"])
    links.new(mix.outputs["Color"], gout.inputs["Color"])
    return group


def _build_dissolve(name):
    group, gin, gout = _preset_group(
        name,
        (('NodeSocketColor', "Color", (0.8, 0.8, 0.8, 1.0)),
         ('NodeSocketColor', "Edge Color", (1.0, 0.4, 0.0, 1.0)),
         ('NodeSocketFloat', "Amount", 0.5),
         ('NodeSocketFloat', "Edge Width", 0.05)),
        (('NodeSocketColor', "Color"), ('NodeSocketFloat', "Alpha")))
    links = group.links
    noise = _preset_node(group, "ShaderNodeTexNoise", (-400.0, 200.0))
    alpha = _preset_node(group, "ShaderNodeMath", (-150.0, 250.0), operation='GREATER_THAN')
    edge_level = _preset_node(group, "ShaderNodeMath", (-350.0, -100.0), operation='ADD')
    edge = _preset_node(group, "ShaderNodeMath", (-150.0, 0.0), operation='LESS_THAN')
    mix = _preset_node(group, "ShaderNodeMixRGB", (100.0, 50.0))
    links.new(noise.outputs["Fac"], alpha.inputs[0])
    links.new(gin.outputs["Amount"], alpha.inputs[1])
    links.new(gin.outputs["Amount"], edge_level.inputs[0])
    links.new(gin.outputs["Edge Width"], edge_level.inputs[1])
    links.new(noise.outputs["Fac"], edge.inputs[0])
    links.new(edge_level.outputs[0], edge.inputs[1])
    links.new(edge.outputs[0], mix.inputs["Fac"])
    links.new(gin.outputs["Color"], mix.inputs["Color1"])
    links.new(gin.outputs["Edge Color"], mix.inputs["Color2"])
    links.new(mix.outputs["Color"], gout.inputs["Color"])
    links.new(alpha.outputs[0], gout.inputs["Alpha"])
    return group


def _build_water_waves(name):
    group, gin, gout = _preset_group(
        name,
        (('NodeSocketColor', "Shallow Color", (0.1, 0.5, 0.6, 1.0)),
         ('NodeSocketColor', "Deep Color", (0.0, 0.1, 0.25, 1.0)),
         ('NodeSocketFloat', "Amplitude", 0.15),
         ('NodeSocketFloat', "Wavelength", 3.0),
         ('NodeSocketFloat', "Speed", 1.5)),
        (('NodeSocketColor', "Color"), ('NodeSocketVector', "Offset")))
    links = group.links
    wave = _preset_node(group, "ShaderNodeVertexWave", (-250.0, -150.0))
    wave2 = _preset_node(group, "ShaderNodeVertexWave", (-250.0, -400.0),
                         Direction=(0.3, 1.0, 0.0))
    add = _preset_node(group, "ShaderNodeVectorMath", (50.0, -250.0), operation='ADD')
    fresnel = _preset_node(group, "ShaderNodeFresnel", (-250.0, 200.0))
    mix = _preset_node(group, "ShaderNodeMixRGB", (100.0, 150.0))
    for node in (wave, wave2):
        links.new(gin.outputs["Amplitude"], node.inputs["Amplitude"])
        links.new(gin.outputs["Wavelength"], node.inputs["Wavelength"])
        links.new(gin.outputs["Speed"], node.inputs["Speed"])
    links.new(wave.outputs["Offset"], add.inputs[0])
    links.new(wave2.outputs["Offset"], add.inputs[1])
    links.new(fresnel.outputs["Fac"], mix.inputs["Fac"])
    links.new(gin.outputs["Deep Color"], mix.inputs["Color1"])
    links.new(gin.outputs["Shallow Color"], mix.inputs["Color2"])
    links.new(mix.outputs["Color"], gout.inputs["Color"])
    links.new(add.outputs["Vector"], gout.inputs["Offset"])
    return group


_PRESET_BUILDERS = {
    'FUR': lambda name: _build_fur(name, 0.05, 12, 300.0,
                                   (0.25, 0.15, 0.08, 1.0), (0.8, 0.65, 0.45, 1.0)),
    'GRASS': lambda name: _build_fur(name, 0.3, 16, 60.0,
                                     (0.05, 0.2, 0.03, 1.0), (0.45, 0.75, 0.2, 1.0)),
    'TOON_RIM': _build_toon_rim,
    'TOON_OUTLINE': _build_toon_outline,
    'DISSOLVE': _build_dissolve,
    'WATER_WAVES': _build_water_waves,
}


def shader_preset_group(preset):
    """The node group of a preset, built the first time."""
    name = dict((p[0], p[1]) for p in _SHADER_PRESETS)[preset]
    group = bpy.data.node_groups.get(name)
    if group is None or group.bl_idname != 'ShaderNodeTree':
        group = _PRESET_BUILDERS[preset](name)
    return group


class NODE_OT_shader_preset_add(Operator):
    """Add a shader preset as an editable node group (game engine)"""
    bl_idname = "node.shader_preset_add"
    bl_label = "Add Shader Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(name="Preset", items=_SHADER_PRESETS)

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (space is not None and space.type == 'NODE_EDITOR' and
                space.tree_type == 'ShaderNodeTree' and space.edit_tree is not None)

    def execute(self, context):
        space = context.space_data
        tree = space.edit_tree
        group = shader_preset_group(self.preset)

        for node in tree.nodes:
            node.select = False
        node = tree.nodes.new("ShaderNodeGroup")
        node.node_tree = group
        node.location = space.cursor_location
        node.select = True
        tree.nodes.active = node

        # Offset goes to the Material Output "Vertex Offset" when it is free.
        if "Offset" in node.outputs:
            for output in tree.nodes:
                if output.type in {'OUTPUT_MATERIAL', 'OUTPUT'} and "Vertex Offset" in output.inputs:
                    socket = output.inputs["Vertex Offset"]
                    if not socket.is_linked:
                        tree.links.new(node.outputs["Offset"], socket)
                    break

        # Presets with an Alpha cut pixels out: the material needs Alpha Clip.
        mat = getattr(space, "id", None)
        if "Alpha" in node.outputs and isinstance(mat, bpy.types.Material):
            if mat.game_settings.alpha_blend == 'OPAQUE':
                mat.game_settings.alpha_blend = 'CLIP'
        return {'FINISHED'}


classes = (
    NodeSetting,

    NODE_OT_damage_mix_add,
    NODE_OT_shader_preset_add,

    NODE_OT_add_and_link_node,
    NODE_OT_add_node,
    NODE_OT_add_search,
    NODE_OT_collapse_hide_unused_toggle,
    NODE_OT_tree_path_parent,
)
