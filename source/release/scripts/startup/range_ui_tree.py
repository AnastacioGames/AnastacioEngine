"""UI Tree (protótipo): menus 2D montados no Node Editor.

Cada Frame é uma tela do jogo; os nós Button dentro dele são os botões, na
mesma posição relativa.  As saídas do Button são eventos (mouse enter/exit,
press, release, click) e se ligam a nós de ação.  "Bake UI" grava tudo no
texto ui_tree_data.py, que o módulo range_ui_tree lê no runtime.
"""

import bpy
import nodeitems_utils
from bpy.props import FloatVectorProperty, StringProperty
from bpy.types import Node, NodeSocket, NodeTree, Operator, Panel
from nodeitems_utils import NodeCategory, NodeItem


DATA_TEXT = "ui_tree_data.py"
EVENTS = ("On Enter", "On Exit", "On Over", "On Press", "On Release", "On Click")


class UITree(NodeTree):
    """Menu 2D desenhado por cima do render do jogo"""
    bl_idname = "RangeUITree"
    bl_label = "UI Tree"
    bl_icon = "MENU_PANEL"


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


class UIButtonNode(UINode, Node):
    bl_idname = "RangeUIButton"
    bl_label = "Button"

    text = StringProperty(name="Text", default="Button")
    color = _color("Color", (0.20, 0.22, 0.26, 0.90))
    hover_color = _color("Hover", (0.30, 0.45, 0.75, 0.95))
    press_color = _color("Pressed", (0.15, 0.30, 0.55, 1.0))
    text_color = _color("Text Color", (1.0, 1.0, 1.0, 1.0))

    def init(self, context):
        self.width = 160
        for name in EVENTS:
            self.outputs.new(UIEventSocket.bl_idname, name)

    def draw_buttons(self, context, layout):
        layout.prop(self, "text", text="")

    def draw_buttons_ext(self, context, layout):
        layout.prop(self, "text")
        for prop in ("color", "hover_color", "press_color", "text_color"):
            layout.prop(self, prop)

    def draw_label(self):
        return self.text or "Button"


class UIActionNode(UINode):
    """Base das ações: uma entrada de evento e um parâmetro de texto."""
    param_label = ""

    value = StringProperty(name="Value")

    def init(self, context):
        self.inputs.new(UIEventSocket.bl_idname, "Event")

    def draw_buttons(self, context, layout):
        if self.param_label:
            layout.prop(self, "value", text=self.param_label)


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
    param_label = "Frame"


class UISceneNode(UIActionNode, Node):
    bl_idname = "RangeUIScene"
    bl_label = "Change Scene"
    action = "SCENE"
    param_label = "Scene"


class UIQuitNode(UIActionNode, Node):
    bl_idname = "RangeUIQuit"
    bl_label = "Quit Game"
    action = "QUIT"


ACTION_NODES = (UIPrintNode, UIMessageNode, UIScreenNode, UISceneNode, UIQuitNode)


def _abs_location(node):
    x, y = node.location
    parent = node.parent
    while parent is not None:
        x += parent.location.x
        y += parent.location.y
        parent = parent.parent
    return x, y


def _node_size(node, default_height):
    # dimensions vem em pixels de tela (com escala da UI); width em unidades
    # da view.  Sem desenho (modo -b) dimensions fica zerado.
    w, h = node.dimensions
    if w > 0 and node.width > 0:
        return node.width, h * node.width / w
    return node.width, default_height


def _actions_for(socket):
    actions = []
    for link in socket.links:
        target = link.to_node
        if getattr(target, "action", None):
            actions.append((target.action, target.value))
    return actions


def bake_tree(tree):
    screens = []
    for frame in tree.nodes:
        if frame.bl_idname != "NodeFrame":
            continue
        fx, fy = _abs_location(frame)
        fw, fh = frame.width, frame.height
        if fw <= 0 or fh <= 0:
            continue
        buttons = []
        for node in tree.nodes:
            if node.bl_idname != UIButtonNode.bl_idname or node.parent != frame:
                continue
            nx, ny = _abs_location(node)
            w, h = _node_size(node, 30.0)
            buttons.append({
                "name": node.name,
                "text": node.text,
                # Retângulo normalizado na tela: x da esquerda, y do topo.
                "rect": ((nx - fx) / fw, (fy - ny) / fh, w / fw, h / fh),
                "color": tuple(node.color),
                "hover": tuple(node.hover_color),
                "press": tuple(node.press_color),
                "text_color": tuple(node.text_color),
                "events": {s.name: _actions_for(s) for s in node.outputs if s.is_linked},
            })
        screens.append({"name": frame.label or frame.name, "location": (fx, fy),
                        "buttons": buttons})
    # A tela inicial é o Frame mais acima e à esquerda no editor.
    screens.sort(key=lambda s: (-s["location"][1], s["location"][0]))
    return {"tree": tree.name, "screens": screens}


class RANGE_OT_ui_tree_bake(Operator):
    """Grava os menus da UI Tree no texto ui_tree_data.py para o jogo"""
    bl_idname = "node.range_ui_tree_bake"
    bl_label = "Bake UI"

    @classmethod
    def poll(cls, context):
        tree = getattr(context.space_data, "edit_tree", None)
        return tree is not None and tree.bl_idname == UITree.bl_idname

    def execute(self, context):
        data = bake_tree(context.space_data.edit_tree)
        text = bpy.data.texts.get(DATA_TEXT) or bpy.data.texts.new(DATA_TEXT)
        text.from_string("# Gerado por Bake UI (UI Tree). Não editar.\nDATA = %r\n" % data)
        count = sum(len(s["buttons"]) for s in data["screens"])
        self.report({'INFO'}, "UI: %d tela(s), %d botão(ões)" % (len(data["screens"]), count))
        return {'FINISHED'}


class NODE_PT_range_ui_tree(Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_label = "UI Tree"

    @classmethod
    def poll(cls, context):
        return RANGE_OT_ui_tree_bake.poll(context)

    def draw(self, context):
        layout = self.layout
        layout.operator(RANGE_OT_ui_tree_bake.bl_idname, icon="FILE_REFRESH")
        layout.label("Jogo: Always (pulso) + Python")
        layout.label("Module: range_ui_tree.main")


class UICategory(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == UITree.bl_idname


CATEGORIES = [
    UICategory("RANGE_UI_WIDGETS", "Widgets", items=[
        NodeItem(UIButtonNode.bl_idname),
        NodeItem("NodeFrame"),
    ]),
    UICategory("RANGE_UI_ACTIONS", "Actions",
               items=[NodeItem(cls.bl_idname) for cls in ACTION_NODES]),
]

CLASSES = (UITree, UIEventSocket, UIButtonNode) + ACTION_NODES + (
    RANGE_OT_ui_tree_bake, NODE_PT_range_ui_tree)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    nodeitems_utils.register_node_categories("RANGE_UI_TREE", CATEGORIES)


def unregister():
    nodeitems_utils.unregister_node_categories("RANGE_UI_TREE")
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
