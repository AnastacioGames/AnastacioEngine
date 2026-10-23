"""UI Tree (protótipo): menus 2D montados no Node Editor.

Cada Screen (um Frame marcado com ui_screen) é uma tela do jogo; os nós
Button dentro dele são os botões, na mesma posição relativa.  Frames comuns
continuam servindo só para organizar.  As saídas do Button são eventos (mouse enter/exit,
press, release, click) e se ligam a nós de ação.  "Bake UI" grava tudo no
texto ui_tree_data.py, que o módulo range_ui_runtime lê no runtime.
"""

import bpy
import nodeitems_utils
from bpy.props import (BoolProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, StringProperty)
from bpy.types import Node, NodeSocket, NodeTree, Operator, Panel
from nodeitems_utils import NodeCategory, NodeItem


DATA_TEXT = "ui_tree_data.py"
EVENTS = ("On Enter", "On Exit", "On Over", "On Press", "On Release", "On Click")


class UITree(NodeTree):
    """Menu 2D desenhado por cima do render do jogo"""
    bl_idname = "RangeUITree"
    bl_label = "UI Tree"
    bl_icon = "MENU_PANEL"

    preview_state = EnumProperty(
        name="Preview", default="NORMAL",
        description="State shown on the selected buttons in the editor",
        items=(("NORMAL", "Normal", ""), ("HOVER", "Hover", ""), ("PRESSED", "Pressed", "")),
        update=lambda self, context: _redraw_node_editors(context))


def _redraw_node_editors(context):
    for area in context.screen.areas:
        if area.type == "NODE_EDITOR":
            area.tag_redraw()


class UIEventSocket(NodeSocket):
    bl_idname = "RangeUIEventSocket"
    bl_label = "Event"

    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        return (1.0, 0.6, 0.1, 1.0)


class UINode:
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == UITree.bl_idname


def _color(name, default):
    return FloatVectorProperty(name=name, subtype="COLOR", size=4,
                               min=0.0, max=1.0, default=default)


# Ordem da grade 3x3 (como aparece no painel).
ANCHORS = ("TOP_LEFT", "TOP", "TOP_RIGHT", "LEFT", "CENTER", "RIGHT",
           "BOTTOM_LEFT", "BOTTOM", "BOTTOM_RIGHT")


class UIWidgetNode(UINode):
    """Base dos widgets: o nó fica recolhido e serve de alça; o widget é a
    prévia desenhada embaixo dele, com largura = largura do nó e altura =
    Height."""
    bl_width_min = 20.0  # deixa a alça recolhida (width_hidden) estreita

    button_height = FloatProperty(name="Height", default=40.0, min=8.0, soft_max=200.0,
                                  description="Widget height (the width is the node's)")
    anchor = EnumProperty(
        name="Anchor", default="CENTER",
        description="Window point the widget follows when the Screen keeps its aspect",
        items=[(a, a.replace("_", " ").title(), "") for a in ANCHORS])

    def init(self, context):
        self.width = 200
        self.hide = True
        self.width_hidden = 20.0

    def draw_label(self):
        # Recolhido, o nó é só a alça: sem texto para não cobrir a prévia.
        return " " if self.hide else self.bl_label


class UIButtonNode(UIWidgetNode, Node):
    bl_idname = "RangeUIButton"
    bl_label = "Button"

    text = StringProperty(name="Text", default="Button")
    color = _color("Color", (0.20, 0.22, 0.26, 0.90))
    hover_color = _color("Hover", (0.30, 0.45, 0.75, 0.95))
    press_color = _color("Pressed", (0.15, 0.30, 0.55, 1.0))
    text_color = _color("Text Color", (1.0, 1.0, 1.0, 1.0))
    radius = FloatProperty(name="Roundness", default=1.0, min=0.0, max=1.0,
                           subtype="FACTOR", description="0 = square, 1 = capsule")
    border = FloatProperty(name="Border", default=0.0, min=0.0, max=0.3,
                           description="Border thickness, as a fraction of the height")
    border_color = _color("Border Color", (1.0, 1.0, 1.0, 0.8))
    text_size = FloatProperty(name="Text Size", default=0.45, min=0.1, max=1.0,
                              description="Text size, as a fraction of the height")
    align = EnumProperty(name="Align", default="CENTER", items=(
        ("LEFT", "Left", ""), ("CENTER", "Center", ""), ("RIGHT", "Right", "")))
    shadow = BoolProperty(name="Shadow", default=False)
    disabled_color = _color("Disabled", (0.25, 0.25, 0.25, 0.6))
    enabled_prop = StringProperty(
        name="Enabled If", description="Bool property of the script owner; false = button disabled (gray, no events). Empty = always enabled")
    selected_prop = StringProperty(
        name="Selected If", description="Bool property of the script owner; true = button highlighted (e.g. chosen option)")
    hover_scale = FloatProperty(name="Hover Scale", default=1.06, min=0.5, max=2.0,
                                description="Button scale with the mouse over it")
    press_scale = FloatProperty(name="Press Scale", default=0.95, min=0.5, max=2.0,
                                description="Button scale while pressed (sinks)")
    anim_time = FloatProperty(name="Anim Time", default=0.12, min=0.0, max=2.0,
                              description="Color and scale transition time, in seconds (0 = instant)")

    def init(self, context):
        UIWidgetNode.init(self, context)
        for name in EVENTS:
            self.outputs.new(UIEventSocket.bl_idname, name)

    def draw_buttons(self, context, layout):
        layout.prop(self, "text", text="")

    def draw_buttons_ext(self, context, layout):
        layout.prop(self, "text")
        layout.prop(self, "button_height")
        col = layout.column(align=True)
        for prop in ("color", "hover_color", "press_color", "text_color"):
            col.prop(self, prop)
        layout.prop(self, "radius", slider=True)
        row = layout.row(align=True)
        row.prop(self, "border")
        row.prop(self, "border_color", text="")
        layout.prop(self, "text_size", slider=True)
        layout.row().prop(self, "align", expand=True)
        layout.prop(self, "shadow")
        col = layout.column(align=True)
        col.label("Animation:")
        col.prop(self, "hover_scale")
        col.prop(self, "press_scale")
        col.prop(self, "anim_time")

    def style(self):
        return {
            "color": tuple(self.color), "hover": tuple(self.hover_color),
            "press": tuple(self.press_color), "text_color": tuple(self.text_color),
            "radius": self.radius, "border": self.border,
            "border_color": tuple(self.border_color), "text_size": self.text_size,
            "align": self.align, "shadow": self.shadow,
            "disabled": tuple(self.disabled_color),
            "hover_scale": self.hover_scale, "press_scale": self.press_scale,
            "anim_time": self.anim_time,
        }


class UIHudNode(UIWidgetNode):
    """Widget de HUD: mostra propriedades de jogo de um objeto."""
    object_name = StringProperty(
        name="Object", description="Object with the properties (empty = script owner)")

    def draw_buttons(self, context, layout):
        layout.prop_search(self, "object_name", context.scene, "objects", text="")


class UIProgressBarNode(UIHudNode, Node):
    bl_idname = "RangeUIProgressBar"
    bl_label = "Progress Bar"

    prop_name = StringProperty(name="Property", default="vida")
    min_value = FloatProperty(name="Min", default=0.0)
    max_value = FloatProperty(name="Max", default=100.0)
    bg_color = _color("Background", (0.0, 0.0, 0.0, 0.55))
    fill_color = _color("Fill", (0.25, 0.85, 0.35, 1.0))
    use_low_color = BoolProperty(name="Low Color", default=True,
                                 description="Blends toward this color as the bar empties")
    low_color = _color("Low", (0.9, 0.15, 0.1, 1.0))
    direction = EnumProperty(name="Direction", default="RIGHT", items=(
        ("RIGHT", "Right", ""), ("LEFT", "Left", ""), ("UP", "Up", ""), ("DOWN", "Down", "")))
    radius = FloatProperty(name="Roundness", default=0.4, min=0.0, max=1.0, subtype="FACTOR")

    def init(self, context):
        UIWidgetNode.init(self, context)
        self.button_height = 24.0

    def draw_buttons_ext(self, context, layout):
        layout.prop_search(self, "object_name", context.scene, "objects")
        layout.prop(self, "prop_name")
        row = layout.row(align=True)
        row.prop(self, "min_value")
        row.prop(self, "max_value")
        layout.prop(self, "button_height")
        col = layout.column(align=True)
        col.prop(self, "bg_color")
        col.prop(self, "fill_color")
        row = layout.row(align=True)
        row.prop(self, "use_low_color")
        row.prop(self, "low_color", text="")
        layout.row().prop(self, "direction", expand=True)
        layout.prop(self, "radius", slider=True)

    def widget(self):
        return {
            "kind": "BAR", "property": self.prop_name,
            "min": self.min_value, "max": self.max_value,
            "bg": tuple(self.bg_color), "fill": tuple(self.fill_color),
            "use_low": self.use_low_color, "low": tuple(self.low_color),
            "direction": self.direction, "radius": self.radius,
        }

    def preview_values(self):
        return {self.prop_name: self.min_value + 0.7 * (self.max_value - self.min_value)}


class UILabelNode(UIHudNode, Node):
    bl_idname = "RangeUILabel"
    bl_label = "Label"

    text_format = StringProperty(
        name="Format", default="{velocidade:.0f} km/h",
        description="Text with properties in braces, e.g. {vida:.0f}, Lap {volta}/3")
    text_color = _color("Color", (1.0, 1.0, 1.0, 1.0))
    text_size = FloatProperty(name="Text Size", default=0.8, min=0.1, max=1.0)
    align = EnumProperty(name="Align", default="LEFT", items=(
        ("LEFT", "Left", ""), ("CENTER", "Center", ""), ("RIGHT", "Right", "")))
    shadow = BoolProperty(name="Shadow", default=True)

    def draw_buttons_ext(self, context, layout):
        layout.prop_search(self, "object_name", context.scene, "objects")
        layout.prop(self, "text_format")
        layout.prop(self, "button_height")
        layout.prop(self, "text_color")
        layout.prop(self, "text_size", slider=True)
        layout.row().prop(self, "align", expand=True)
        layout.prop(self, "shadow")

    def widget(self):
        return {
            "kind": "LABEL", "format": self.text_format, "color": tuple(self.text_color),
            "text_size": self.text_size, "align": self.align, "shadow": self.shadow,
        }

    def preview_values(self):
        return {}


class UIPanelNode(UIHudNode, Node):
    """Retângulo de fundo (atrás dos botões, caixa de diálogo...)."""
    bl_idname = "RangeUIPanel"
    bl_label = "Panel"

    color = _color("Color", (0.05, 0.06, 0.08, 0.75))
    radius = FloatProperty(name="Roundness", default=0.1, min=0.0, max=1.0, subtype="FACTOR")
    border = FloatProperty(name="Border", default=0.0, min=0.0, max=0.1,
                           description="Border thickness, as a fraction of the shorter side")
    border_color = _color("Border Color", (1.0, 1.0, 1.0, 0.5))

    def init(self, context):
        UIWidgetNode.init(self, context)
        self.button_height = 200.0

    def draw_buttons(self, context, layout):
        layout.prop(self, "color", text="")

    def draw_buttons_ext(self, context, layout):
        layout.prop(self, "button_height")
        layout.prop(self, "color")
        layout.prop(self, "radius", slider=True)
        row = layout.row(align=True)
        row.prop(self, "border")
        row.prop(self, "border_color", text="")

    def widget(self):
        return {"kind": "PANEL", "color": tuple(self.color), "radius": self.radius,
                "border": self.border, "border_color": tuple(self.border_color)}

    def preview_values(self):
        return {}


class UIImageNode(UIHudNode, Node):
    """Imagem (logo, ícone).  No jogo é lida do arquivo: use caminho
    relativo (//) e não deixe a imagem só empacotada."""
    bl_idname = "RangeUIImage"
    bl_label = "Image"

    image_name = StringProperty(name="Image")
    tint = _color("Tint", (1.0, 1.0, 1.0, 1.0))

    def init(self, context):
        UIWidgetNode.init(self, context)
        self.button_height = 100.0

    def draw_buttons(self, context, layout):
        layout.prop_search(self, "image_name", bpy.data, "images", text="")

    def draw_buttons_ext(self, context, layout):
        layout.prop_search(self, "image_name", bpy.data, "images")
        layout.prop(self, "button_height")
        layout.prop(self, "tint")
        layout.operator(RANGE_OT_ui_tree_image_aspect.bl_idname, icon="IMAGE_COL")

    def image(self):
        return bpy.data.images.get(self.image_name) if self.image_name else None

    def widget(self):
        image = self.image()
        return {"kind": "IMAGE", "path": image.filepath if image else "",
                "tint": tuple(self.tint)}

    def preview_values(self):
        return {}


class UIGaugeNode(UIHudNode, Node):
    """Velocímetro circular ligado a uma propriedade."""
    bl_idname = "RangeUIGauge"
    bl_label = "Gauge"

    prop_name = StringProperty(name="Property", default="velocidade")
    min_value = FloatProperty(name="Min", default=0.0)
    max_value = FloatProperty(name="Max", default=200.0)
    arc = FloatProperty(name="Arc", default=270.0, min=30.0, max=360.0,
                        description="Arc opening, in degrees")
    thickness = FloatProperty(name="Thickness", default=0.18, min=0.02, max=1.0, subtype="FACTOR")
    bg_color = _color("Background", (0.0, 0.0, 0.0, 0.55))
    fill_color = _color("Fill", (1.0, 0.55, 0.1, 1.0))
    use_low_color = BoolProperty(name="Low Color", default=False)
    low_color = _color("Low", (0.25, 0.85, 0.35, 1.0))
    needle = BoolProperty(name="Needle", default=True)
    needle_color = _color("Needle Color", (1.0, 1.0, 1.0, 1.0))
    text_format = StringProperty(name="Format", default="{velocidade:.0f}")
    text_color = _color("Text Color", (1.0, 1.0, 1.0, 1.0))

    def init(self, context):
        UIWidgetNode.init(self, context)
        self.width = 160
        self.button_height = 160.0

    def draw_buttons_ext(self, context, layout):
        layout.prop_search(self, "object_name", context.scene, "objects")
        layout.prop(self, "prop_name")
        row = layout.row(align=True)
        row.prop(self, "min_value")
        row.prop(self, "max_value")
        layout.prop(self, "button_height")
        layout.prop(self, "arc")
        layout.prop(self, "thickness", slider=True)
        col = layout.column(align=True)
        col.prop(self, "bg_color")
        col.prop(self, "fill_color")
        row = layout.row(align=True)
        row.prop(self, "use_low_color")
        row.prop(self, "low_color", text="")
        row = layout.row(align=True)
        row.prop(self, "needle")
        row.prop(self, "needle_color", text="")
        layout.prop(self, "text_format")
        layout.prop(self, "text_color")

    def widget(self):
        return {
            "kind": "GAUGE", "property": self.prop_name,
            "min": self.min_value, "max": self.max_value, "arc": self.arc,
            "thickness": self.thickness, "bg": tuple(self.bg_color),
            "fill": tuple(self.fill_color), "use_low": self.use_low_color,
            "low": tuple(self.low_color), "needle": self.needle,
            "needle_color": tuple(self.needle_color), "format": self.text_format,
            "text_color": tuple(self.text_color),
        }

    def preview_values(self):
        return {self.prop_name: self.min_value + 0.6 * (self.max_value - self.min_value)}


class UIControlNode(UIHudNode):
    """Controle que o jogador mexe e que grava numa propriedade de jogo;
    a saída On Change dispara quando o valor muda."""

    def init(self, context):
        UIWidgetNode.init(self, context)
        self.button_height = 30.0
        self.outputs.new(UIEventSocket.bl_idname, "On Change")


class UIToggleNode(UIControlNode, Node):
    bl_idname = "RangeUIToggle"
    bl_label = "Toggle"

    prop_name = StringProperty(name="Property", default="som",
                               description="Bool property toggled by the click")
    text = StringProperty(name="Text", default="Som")
    color = _color("Color", (0.20, 0.22, 0.26, 0.90))
    on_color = _color("On Color", (0.30, 0.65, 1.0, 1.0))
    text_color = _color("Text Color", (1.0, 1.0, 1.0, 1.0))
    radius = FloatProperty(name="Roundness", default=0.3, min=0.0, max=1.0, subtype="FACTOR")
    text_size = FloatProperty(name="Text Size", default=0.6, min=0.1, max=1.0)
    audio = EnumProperty(name="Audio", default="NONE", items=(
        ("NONE", "None", "Only writes the property"),
        ("SOUND", "Sound On/Off", "On = game sound on; off = muted")))

    def draw_buttons(self, context, layout):
        layout.prop(self, "text", text="")

    def draw_buttons_ext(self, context, layout):
        layout.prop_search(self, "object_name", context.scene, "objects")
        layout.prop(self, "prop_name")
        layout.prop(self, "text")
        layout.prop(self, "audio")
        layout.prop(self, "button_height")
        col = layout.column(align=True)
        for prop in ("color", "on_color", "text_color"):
            col.prop(self, prop)
        layout.prop(self, "radius", slider=True)
        layout.prop(self, "text_size", slider=True)

    def widget(self):
        return {"kind": "TOGGLE", "property": self.prop_name, "text": self.text,
                "color": tuple(self.color), "on_color": tuple(self.on_color),
                "text_color": tuple(self.text_color), "radius": self.radius,
                "text_size": self.text_size, "audio": self.audio}

    def preview_values(self):
        return {self.prop_name: True}


class UISliderNode(UIControlNode, Node):
    bl_idname = "RangeUISlider"
    bl_label = "Slider"

    prop_name = StringProperty(name="Property", default="volume",
                               description="Numeric property set by dragging")
    min_value = FloatProperty(name="Min", default=0.0)
    max_value = FloatProperty(name="Max", default=1.0)
    bg_color = _color("Track", (0.0, 0.0, 0.0, 0.55))
    fill_color = _color("Fill", (0.30, 0.65, 1.0, 1.0))
    knob_color = _color("Knob", (0.9, 0.9, 0.95, 1.0))
    audio = EnumProperty(name="Audio", default="NONE", items=(
        ("NONE", "None", "Only writes the property"),
        ("VOLUME", "Master Volume", "The value (between Min and Max) becomes the game's master volume")))

    def draw_buttons_ext(self, context, layout):
        layout.prop_search(self, "object_name", context.scene, "objects")
        layout.prop(self, "prop_name")
        row = layout.row(align=True)
        row.prop(self, "min_value")
        row.prop(self, "max_value")
        layout.prop(self, "audio")
        layout.prop(self, "button_height")
        col = layout.column(align=True)
        for prop in ("bg_color", "fill_color", "knob_color"):
            col.prop(self, prop)

    def widget(self):
        return {"kind": "SLIDER", "property": self.prop_name,
                "min": self.min_value, "max": self.max_value,
                "bg": tuple(self.bg_color), "fill": tuple(self.fill_color),
                "knob": tuple(self.knob_color), "audio": self.audio}

    def preview_values(self):
        return {self.prop_name: self.min_value + 0.5 * (self.max_value - self.min_value)}


HUD_NODES = (UIProgressBarNode, UILabelNode, UIPanelNode, UIImageNode, UIGaugeNode,
             UIToggleNode, UISliderNode)


class UIActionNode(UINode):
    """Base das ações: uma entrada de evento e um parâmetro de texto."""
    param_label = ""

    value = StringProperty(name="Value")

    def init(self, context):
        # Vários botões podem disparar a mesma ação (ex.: um som de hover).
        self.inputs.new(UIEventSocket.bl_idname, "Event").link_limit = 4095

    def draw_buttons(self, context, layout):
        if self.param_label:
            layout.prop(self, "value", text=self.param_label)

    def payload(self):
        return self.value


class UIPrintNode(UIActionNode, Node):
    bl_idname = "RangeUIPrint"
    bl_label = "Print"
    action = "PRINT"
    param_label = "Text"


class UIMessageNode(UIActionNode, Node):
    bl_idname = "RangeUIMessage"
    bl_label = "Send Message"
    action = "MESSAGE"
    param_label = "Subject"


class UIScreenNode(UIActionNode, Node):
    bl_idname = "RangeUIScreen"
    bl_label = "Go To Screen"
    action = "SCREEN"
    param_label = "Screen"  # vazio esconde o menu


class UISceneNode(UIActionNode, Node):
    bl_idname = "RangeUIScene"
    bl_label = "Change Scene"
    action = "SCENE"
    param_label = "Scene"


class UIQuitNode(UIActionNode, Node):
    bl_idname = "RangeUIQuit"
    bl_label = "Quit Game"
    action = "QUIT"


class UISetPropertyNode(UIActionNode, Node):
    bl_idname = "RangeUISetProperty"
    bl_label = "Set Property"
    action = "SET_PROP"

    prop_name = StringProperty(name="Property", description="Game property of the script owner")

    def draw_buttons(self, context, layout):
        layout.prop(self, "prop_name", text="")
        layout.prop(self, "value", text="=")

    def payload(self):
        return (self.prop_name, self.value)


class UISoundNode(UIActionNode, Node):
    bl_idname = "RangeUISound"
    bl_label = "Play Sound"
    action = "SOUND"

    filepath = StringProperty(name="File", subtype="FILE_PATH",
                              description="Sound played on the event (// = the .range folder)")
    volume = FloatProperty(name="Volume", default=1.0, min=0.0, soft_max=2.0)

    def draw_buttons(self, context, layout):
        layout.prop(self, "filepath", text="")
        layout.prop(self, "volume")

    def payload(self):
        return (self.filepath, self.volume)


class UIAddPropertyNode(UIActionNode, Node):
    bl_idname = "RangeUIAddProperty"
    bl_label = "Add Property"
    action = "ADD_PROP"

    prop_name = StringProperty(name="Property", description="Numeric property of the script owner")

    def draw_buttons(self, context, layout):
        layout.prop(self, "prop_name", text="")
        layout.prop(self, "value", text="+")

    def payload(self):
        return (self.prop_name, self.value)


class UITogglePropertyNode(UIActionNode, Node):
    bl_idname = "RangeUIToggleProperty"
    bl_label = "Toggle Property"
    action = "TOGGLE_PROP"
    param_label = "Property"


class UIRunPythonNode(UIActionNode, Node):
    """Chama modulo.funcao(ui); ui.owner é o dono do script."""
    bl_idname = "RangeUIRunPython"
    bl_label = "Run Python"
    action = "PYTHON"
    param_label = "Function"


ACTION_NODES = (UIPrintNode, UIMessageNode, UIScreenNode, UISceneNode, UIQuitNode,
                UISoundNode, UISetPropertyNode, UIAddPropertyNode, UITogglePropertyNode,
                UIRunPythonNode)


def _abs_location(node):
    x, y = node.location
    parent = node.parent
    while parent is not None:
        x += parent.location.x
        y += parent.location.y
        parent = parent.parent
    return x, y


def _actions_for(socket):
    actions = []
    for link in socket.links:
        target = link.to_node
        if getattr(target, "action", None):
            actions.append((target.action, target.payload()))
    return actions


def _is_screen(node):
    return node.bl_idname == "NodeFrame" and node.ui_screen


def _canvas(frame, scene):
    """Retângulo da tela do jogo (x, y do topo, largura, altura), em unidades
    da view.  O desenho do Frame em C (drawnode.c) faz o mesmo: Screen não
    cresce com os filhos e a altura segue a proporção da resolução."""
    x, y = _abs_location(frame)
    render = scene.render
    return x, y, frame.width, frame.width * render.resolution_y / render.resolution_x


def bake_tree(tree, scene):
    screens = []
    for frame in tree.nodes:
        if not _is_screen(frame):
            continue
        fx, fy, fw, fh = _canvas(frame, scene)
        buttons = []
        widgets = []
        for node in tree.nodes:
            if node.parent != frame:
                continue
            nx, ny = _abs_location(node)
            # Retângulo normalizado na tela: x da esquerda, y do topo.
            rect = ((nx - fx) / fw, (fy - ny) / fh, node.width / fw, node.button_height / fh)
            if isinstance(node, UIHudNode):
                data = node.widget()
                data["rect"] = rect
                data["object"] = node.object_name
                data["anchor"] = node.anchor
                if isinstance(node, UIControlNode):
                    data["events"] = {s.name: _actions_for(s) for s in node.outputs if s.is_linked}
                widgets.append(data)
                continue
            if node.bl_idname != UIButtonNode.bl_idname:
                continue
            buttons.append({
                "name": node.text or node.name,
                "text": node.text,
                "rect": rect,
                "style": node.style(),
                "anchor": node.anchor,
                "enabled_prop": node.enabled_prop,
                "selected_prop": node.selected_prop,
                "events": {s.name: _actions_for(s) for s in node.outputs if s.is_linked},
            })
        screens.append({"name": frame.label or frame.name, "location": (fx, fy),
                        "hud": frame.ui_hud, "buttons": buttons, "widgets": widgets,
                        "fade": frame.ui_fade, "scale_mode": frame.ui_scale_mode,
                        "design": (fw, fh), "camera": frame.ui_camera if frame.ui_hud else "",
                        "sounds": {"hover": frame.ui_hover_sound, "click": frame.ui_click_sound}})
    # A tela inicial é a Screen mais acima e à esquerda no editor.
    screens.sort(key=lambda s: (-s["location"][1], s["location"][0]))
    return {"tree": tree.name, "screens": screens}


def write_bake(tree, scene):
    data = bake_tree(tree, scene)
    text = bpy.data.texts.get(DATA_TEXT) or bpy.data.texts.new(DATA_TEXT)
    text.from_string("# Gerado por Bake UI (UI Tree). Não editar.\nDATA = %r\n" % data)
    return data


def _baked_tree():
    """A UI Tree que vai para o jogo: a do último Bake ou, se ainda não houve
    Bake, a única UI Tree do arquivo."""
    text = bpy.data.texts.get(DATA_TEXT)
    if text is not None:
        import ast
        try:
            name = ast.literal_eval(text.as_string().split("DATA = ", 1)[1])["tree"]
        except (IndexError, KeyError, ValueError, SyntaxError):
            name = None
        tree = bpy.data.node_groups.get(name) if name else None
        if tree is not None and tree.bl_idname == UITree.bl_idname:
            return tree
    trees = [t for t in bpy.data.node_groups if t.bl_idname == UITree.bl_idname]
    return trees[0] if len(trees) == 1 else None


@bpy.app.handlers.persistent
def _auto_bake(_scene):
    """Bake automático ao apertar P e ao salvar (o export salva o arquivo):
    o jogo nunca roda com um menu velho."""
    tree = _baked_tree()
    if tree is None:
        return
    try:
        write_bake(tree, bpy.context.scene)
    except Exception as exc:  # um Bake quebrado não pode impedir de jogar/salvar
        print("[UI Tree] Bake automático falhou: %s" % exc)


class RANGE_OT_ui_tree_bake(Operator):
    """Write the UI Tree menus to the ui_tree_data.py text for the game"""
    bl_idname = "node.range_ui_tree_bake"
    bl_label = "Bake UI"

    @classmethod
    def poll(cls, context):
        tree = getattr(context.space_data, "edit_tree", None)
        return tree is not None and tree.bl_idname == UITree.bl_idname

    def execute(self, context):
        data = write_bake(context.space_data.edit_tree, context.scene)
        count = sum(len(s["buttons"]) for s in data["screens"])
        self.report({'INFO'}, "UI: %d tela(s), %d botão(ões)" % (len(data["screens"]), count))
        return {'FINISHED'}


def _active_frame(context):
    node = context.space_data.edit_tree.nodes.active
    return node if node is not None and _is_screen(node) else None


class RANGE_OT_ui_tree_image_aspect(Operator):
    """Fit the widget height to the image aspect"""
    bl_idname = "node.range_ui_tree_image_aspect"
    bl_label = "Fit Image Aspect"

    def execute(self, context):
        node = context.active_node
        image = node.image() if isinstance(node, UIImageNode) else None
        if image is None or not image.size[0]:
            return {'CANCELLED'}
        node.button_height = node.width * image.size[1] / image.size[0]
        return {'FINISHED'}


class RANGE_OT_ui_tree_capture(Operator):
    """Render the scene camera and use it as the active Frame's backdrop"""
    bl_idname = "node.range_ui_tree_capture"
    bl_label = "Capture Camera"

    @classmethod
    def poll(cls, context):
        return RANGE_OT_ui_tree_bake.poll(context) and _active_frame(context) is not None

    def execute(self, context):
        import os
        frame = _active_frame(context)
        scene = context.scene
        if scene.camera is None:
            self.report({'ERROR'}, "A cena não tem câmera")
            return {'CANCELLED'}
        bpy.ops.render.opengl()
        path = os.path.join(bpy.app.tempdir, "ui_backdrop_%s.png" % bpy.path.clean_name(frame.name))
        bpy.data.images["Render Result"].save_render(path)
        name = "UI Backdrop %s" % frame.name
        image = bpy.data.images.get(name)
        if image is None:
            image = bpy.data.images.load(path)
            image.name = name
        else:
            image.filepath = path
            image.reload()
        image.pack()
        frame.ui_backdrop = image.name
        return {'FINISHED'}


def add_template(tree, kind, origin=(0.0, 0.0)):
    """Monta uma tela pronta na UI Tree: MENU = Menu (Jogar/Opções/Sair) +
    Opcoes (Som, Volume, Voltar); HUD = vida e velocímetro.  Devolve os
    Frames criados."""
    ox, oy = origin

    def frame(name, x, y, hud=False):
        node = tree.nodes.new("NodeFrame")
        node.name = node.label = name
        node.ui_screen = True
        node.ui_hud = hud
        node.ui_scale_mode = "KEEP"
        node.shrink = False
        node.location = (ox + x, oy + y)
        node.width, node.height = 640, 360
        return node

    def widget(cls, parent, x, y, width, height=None):
        node = tree.nodes.new(cls.bl_idname)
        node.parent = parent
        node.location = (x, y)  # relativo ao Frame, y para baixo é negativo
        node.width = width
        if height is not None:
            node.button_height = height
        return node

    def action(cls, value, x, y, *sources):
        node = tree.nodes.new(cls.bl_idname)
        node.value = value
        node.location = (ox + x, oy + y)
        for source, event in sources:
            tree.links.new(source.outputs[event], node.inputs[0])
        return node

    if kind == "HUD":
        hud = frame("HUD", 0, 0, hud=True)
        bar = widget(UIProgressBarNode, hud, 20, -20, 220, 24)
        life = widget(UILabelNode, hud, 20, -48, 220, 24)
        life.text_format = "Vida {vida:.0f}"
        gauge = widget(UIGaugeNode, hud, 480, -190, 140, 140)
        unit = widget(UILabelNode, hud, 480, -330, 140, 24)
        unit.text_format = "km/h"
        unit.align = "CENTER"
        for node in (bar, life):
            node.anchor = "TOP_LEFT"
        for node in (gauge, unit):
            node.anchor = "BOTTOM_RIGHT"
        return [hud]

    menu = frame("Menu", 0, 0)
    options = frame("Opcoes", 0, -500)
    widget(UIPanelNode, menu, 200, -100, 240, 180).border = 0.01
    play = widget(UIButtonNode, menu, 220, -120, 200)
    play.text = "Jogar"
    opt = widget(UIButtonNode, menu, 220, -170, 200)
    opt.text = "Opções"
    quit_ = widget(UIButtonNode, menu, 220, -220, 200)
    quit_.text = "Sair"
    sound = widget(UIToggleNode, options, 200, -100, 240, 30)
    sound.audio = "SOUND"
    volume = widget(UISliderNode, options, 200, -160, 240, 30)
    volume.audio = "VOLUME"
    label = widget(UILabelNode, options, 200, -195, 240, 24)
    label.text_format = "Volume {volume:.0%}"
    label.align = "CENTER"
    back = widget(UIButtonNode, options, 220, -280, 200)
    back.text = "Voltar"
    for screen in (menu, options):
        screen.ui_fade = 0.25
    # Jogar esconde o menu e liga o HUD (se houver).
    action(UIScreenNode, "", 800, 0, (play, "On Click"))
    hud_on = action(UISetPropertyNode, "True", 800, -100, (play, "On Click"))
    hud_on.prop_name = "ui_hud"
    action(UIScreenNode, "Opcoes", 800, -200, (opt, "On Click"))
    action(UIQuitNode, "", 800, -300, (quit_, "On Click"))
    action(UIScreenNode, "Menu", 800, -600, (back, "On Click"))
    return [menu, options]


GAME_PROPS = (("ui_screen", "STRING", "Menu"), ("ui_hud", "BOOL", False),
              ("som", "BOOL", True), ("volume", "FLOAT", 0.8),
              ("vida", "FLOAT", 100.0), ("velocidade", "FLOAT", 0.0))


def setup_game_logic(obj):
    """Always (pulso) + Python Module range_ui_runtime.main no objeto, e as
    propriedades que o template usa.  Não repete o que já existe."""
    game = obj.game
    if not any(c.type == "PYTHON" and c.mode == "MODULE" and c.module == "range_ui_runtime.main"
               for c in game.controllers):
        bpy.ops.logic.sensor_add(type="ALWAYS", name="UI Tree", object=obj.name)
        bpy.ops.logic.controller_add(type="PYTHON", name="UI Tree", object=obj.name)
        sensor, controller = game.sensors[-1], game.controllers[-1]
        sensor.use_pulse_true_level = True
        controller.mode = "MODULE"
        controller.module = "range_ui_runtime.main"
        sensor.link(controller)
    scene = bpy.context.scene
    active = scene.objects.active
    scene.objects.active = obj  # game_property_new age no objeto ativo
    for name, kind, value in GAME_PROPS:
        if name not in game.properties:
            bpy.ops.object.game_property_new(type=kind, name=name)
            game.properties[name].value = value
    scene.objects.active = active


class RANGE_OT_ui_tree_template(Operator):
    """Add ready-made screens to the UI Tree (menu with options or HUD)"""
    bl_idname = "node.range_ui_tree_template"
    bl_label = "Add Template"
    bl_options = {'REGISTER', 'UNDO'}

    kind = EnumProperty(name="Template", items=(
        ("MENU", "Menu + Options", "Play/Options/Quit menu and an options screen with sound and volume"),
        ("HUD", "HUD", "Health bar and speedometer")))

    @classmethod
    def poll(cls, context):
        return RANGE_OT_ui_tree_bake.poll(context)

    def execute(self, context):
        tree = context.space_data.edit_tree
        # Abaixo do que já existe, para não sobrepor.
        bottom = min((n.location.y - n.height for n in tree.nodes if n.parent is None), default=0.0)
        origin = (0.0, bottom - 150.0 if tree.nodes else 0.0)
        for node in tree.nodes:
            node.select = False
        frames = add_template(tree, self.kind, origin)
        tree.nodes.active = frames[0]
        self.report({'INFO'}, "UI: %d tela(s) adicionada(s)" % len(frames))
        return {'FINISHED'}


class RANGE_OT_ui_tree_setup_logic(Operator):
    """Hook the UI into the game: Always + Python (range_ui_runtime.main) and the properties ui_screen, ui_hud, som, volume, vida and velocidade on the scene camera"""
    bl_idname = "node.range_ui_tree_setup_logic"
    bl_label = "Setup Game Logic"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.camera is not None

    def execute(self, context):
        setup_game_logic(context.scene.camera)
        self.report({'INFO'}, "UI ligada na câmera %s" % context.scene.camera.name)
        return {'FINISHED'}


def _draw_backdrops():
    import bgl
    context = bpy.context
    tree = getattr(context.space_data, "edit_tree", None)
    if tree is None or tree.bl_idname != UITree.bl_idname:
        return
    # A vista do Node Editor está em unidades * escala da UI.
    scale = context.user_preferences.system.ui_scale  # U.dpi_fac
    for frame in tree.nodes:
        if not _is_screen(frame):
            continue
        x, y, w, h = (v * scale for v in _canvas(frame, context.scene))
        x0, x1, y0, y1 = x, x + w, y - h, y
        image = bpy.data.images.get(frame.ui_backdrop) if frame.ui_backdrop else None
        if image is not None and not image.gl_load():
            bgl.glEnable(bgl.GL_TEXTURE_2D)
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, image.bindcode[0])
            bgl.glColor4f(1.0, 1.0, 1.0, 1.0)
            bgl.glBegin(bgl.GL_QUADS)
            for u, v, px, py in ((0, 0, x0, y0), (1, 0, x1, y0), (1, 1, x1, y1), (0, 1, x0, y1)):
                bgl.glTexCoord2f(u, v)
                bgl.glVertex2f(px, py)
            bgl.glEnd()
            bgl.glDisable(bgl.GL_TEXTURE_2D)


def _draw_previews():
    import bgl
    import blf
    import range_ui_draw
    tree = getattr(bpy.context.space_data, "edit_tree", None)
    if tree is None or tree.bl_idname != UITree.bl_idname:
        return
    for node in tree.nodes:
        is_hud = isinstance(node, UIHudNode)
        if not is_hud and node.bl_idname != UIButtonNode.bl_idname:
            continue
        scale = bpy.context.user_preferences.system.ui_scale  # U.dpi_fac
        x, y = _abs_location(node)
        w, h = node.width * scale, node.button_height * scale
        x, y = x * scale, y * scale - h
        if is_hud:
            # Prévia com valor de exemplo (barra em 70%, propriedades = 0).
            bindcode = 0
            if isinstance(node, UIImageNode):
                image = node.image()
                if image is not None and not image.gl_load():
                    bindcode = image.bindcode[0]
            range_ui_draw.draw_widget(bgl, blf, node.widget(), node.preview_values(),
                                      x, y, w, h, bindcode=bindcode)
        else:
            state = tree.preview_state if node.select else "NORMAL"
            range_ui_draw.draw_button(bgl, blf, node.style(), node.text, x, y, w, h, state)
        if node.select:
            bgl.glColor4f(1.0, 0.6, 0.2, 1.0)
            bgl.glBegin(bgl.GL_LINE_LOOP)
            for px, py in ((x, y), (x + w, y), (x + w, y + h), (x, y + h)):
                bgl.glVertex2f(px, py)
            bgl.glEnd()


def _draw_editor():
    _draw_backdrops()
    _draw_previews()


class UITreePanel:
    bl_space_type = "NODE_EDITOR"
    bl_label = "UI Tree"

    @classmethod
    def poll(cls, context):
        return RANGE_OT_ui_tree_bake.poll(context)

    def draw(self, context):
        layout = self.layout
        layout.operator(RANGE_OT_ui_tree_bake.bl_idname, icon="FILE_REFRESH")
        row = layout.row(align=True)
        row.operator(RANGE_OT_ui_tree_template.bl_idname, text="Menu", icon="ZOOMIN").kind = "MENU"
        row.operator(RANGE_OT_ui_tree_template.bl_idname, text="HUD", icon="ZOOMIN").kind = "HUD"
        layout.operator(RANGE_OT_ui_tree_setup_logic.bl_idname, icon="LOGIC")
        layout.row().prop(context.space_data.edit_tree, "preview_state", expand=True)
        frame = _active_frame(context)
        if frame is not None:
            box = layout.box()
            box.label("Tela: %s" % (frame.label or frame.name))
            box.prop(frame, "ui_hud")
            if frame.ui_hud:
                box.prop_search(frame, "ui_camera", context.scene, "objects", text="Camera")
            box.prop(frame, "ui_scale_mode", text="")
            if not frame.ui_hud:
                box.prop(frame, "ui_fade")
                box.prop(frame, "ui_hover_sound", text="Hover")
                box.prop(frame, "ui_click_sound", text="Click")
            box.prop_search(frame, "ui_backdrop", bpy.data, "images", text="")
            box.operator(RANGE_OT_ui_tree_capture.bl_idname, icon="RENDER_STILL")
        node = context.active_node
        if isinstance(node, UIWidgetNode) and node.select:
            box = layout.box()
            box.label("Widget: %s" % node.bl_label)
            box.label("Anchor:")
            col = box.column(align=True)
            for i in range(0, 9, 3):
                row = col.row(align=True)
                for anchor in ANCHORS[i:i + 3]:
                    # TL, T, TR, L, C, R, BL, B, BR
                    row.prop_enum(node, "anchor", anchor,
                                  text="".join(part[0] for part in anchor.split("_")))
            if isinstance(node, UIButtonNode):
                box.prop(node, "enabled_prop")
                box.prop(node, "selected_prop")
                box.prop(node, "disabled_color")
        layout.label("Game: Always (pulse) + Python")
        layout.label("Module: range_ui_runtime.main")
        layout.label("Menu: ui_screen property")
        layout.label("HUD: ui_hud property (bool)")
        layout.label("Keyboard/gamepad: arrows + Enter")


class NODE_PT_range_ui_tree(UITreePanel, Panel):
    bl_region_type = "UI"


class NODE_PT_range_ui_tree_tools(UITreePanel, Panel):
    """Mesmo painel na prateleira T: vira um botão da barra flutuante
    (Horizontal Tabs, botão no cabeçalho)."""
    bl_region_type = "TOOLS"
    bl_category = "UI Tree"


class UICategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == UITree.bl_idname


CATEGORIES = [
    UICategory("RANGE_UI_WIDGETS", "Widgets", items=[
        NodeItem("NodeFrame", label="Screen", settings={
            "ui_screen": "True", "label": "'Screen'", "width": "640.0", "shrink": "False"}),
        NodeItem("NodeFrame", label="HUD Screen", settings={
            "ui_screen": "True", "ui_hud": "True", "label": "'HUD'", "width": "640.0",
            "shrink": "False"}),
        NodeItem(UIButtonNode.bl_idname),
        NodeItem(UIToggleNode.bl_idname),
        NodeItem(UISliderNode.bl_idname),
        NodeItem(UIPanelNode.bl_idname),
        NodeItem(UIImageNode.bl_idname),
        NodeItem("NodeFrame"),
    ]),
    UICategory("RANGE_UI_HUD", "HUD", items=[
        NodeItem(UIProgressBarNode.bl_idname),
        NodeItem(UILabelNode.bl_idname),
        NodeItem(UIGaugeNode.bl_idname),
    ]),
    UICategory("RANGE_UI_ACTIONS", "Actions",
               items=[NodeItem(cls.bl_idname) for cls in ACTION_NODES]),
]

CLASSES = (UITree, UIEventSocket, UIButtonNode) + HUD_NODES + ACTION_NODES + (
    RANGE_OT_ui_tree_bake, RANGE_OT_ui_tree_image_aspect, RANGE_OT_ui_tree_capture,
    RANGE_OT_ui_tree_template, RANGE_OT_ui_tree_setup_logic,
    NODE_PT_range_ui_tree,
    NODE_PT_range_ui_tree_tools)

_draw_handles = []


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.NodeFrame.ui_backdrop = StringProperty(
        name="Backdrop", description="Backdrop image of this screen in the editor (not used in the game)")
    bpy.types.NodeFrame.ui_screen = BoolProperty(
        name="Screen", description="In a UI Tree, this Frame is a game screen")
    bpy.types.NodeFrame.ui_hud = BoolProperty(
        name="HUD", description="HUD screen: always visible, under the menu")
    bpy.types.NodeFrame.ui_camera = StringProperty(
        name="Camera",
        description="HUD drawn only inside this camera's viewport (split screen); empty = whole window")
    bpy.types.NodeFrame.ui_scale_mode = EnumProperty(
        name="Scale Mode", default="STRETCH",
        description="How the screen adapts to a window with another aspect",
        items=(("STRETCH", "Stretch", "Stretches with the window (relative positions)"),
               ("KEEP", "Keep Aspect", "Keeps the aspect; each widget follows its anchor")))
    bpy.types.NodeFrame.ui_fade = FloatProperty(
        name="Fade", default=0.15, min=0.0, max=3.0,
        description="Fade time when showing/hiding this screen, in seconds")
    bpy.types.NodeFrame.ui_hover_sound = StringProperty(
        name="Hover Sound", subtype="FILE_PATH",
        description="Default sound for the mouse over any button on this screen")
    bpy.types.NodeFrame.ui_click_sound = StringProperty(
        name="Click Sound", subtype="FILE_PATH",
        description="Default sound for clicking any button on this screen")
    nodeitems_utils.register_node_categories("RANGE_UI_TREE", CATEGORIES)
    space = bpy.types.SpaceNodeEditor
    _draw_handles.append(space.draw_handler_add(_draw_editor, (), "WINDOW", "PRE_VIEW"))
    for handlers in (bpy.app.handlers.game_pre, bpy.app.handlers.save_pre):
        if _auto_bake not in handlers:
            handlers.append(_auto_bake)


def unregister():
    for handlers in (bpy.app.handlers.game_pre, bpy.app.handlers.save_pre):
        if _auto_bake in handlers:
            handlers.remove(_auto_bake)
    while _draw_handles:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_draw_handles.pop(), "WINDOW")
    del bpy.types.NodeFrame.ui_backdrop
    del bpy.types.NodeFrame.ui_screen
    del bpy.types.NodeFrame.ui_hud
    del bpy.types.NodeFrame.ui_fade
    del bpy.types.NodeFrame.ui_scale_mode
    del bpy.types.NodeFrame.ui_camera
    del bpy.types.NodeFrame.ui_hover_sound
    del bpy.types.NodeFrame.ui_click_sound
    nodeitems_utils.unregister_node_categories("RANGE_UI_TREE")
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
