"""UI Tree (protótipo): menus 2D montados no Node Editor.

Cada Frame é uma tela do jogo; os nós Button dentro dele são os botões, na
mesma posição relativa.  As saídas do Button são eventos (mouse enter/exit,
press, release, click) e se ligam a nós de ação.  "Bake UI" grava tudo no
texto ui_tree_data.py, que o módulo range_ui_tree lê no runtime.
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
        description="Estado mostrado nos botões selecionados no editor",
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


class UIButtonNode(UINode, Node):
    """O nó fica recolhido e serve de alça; o botão é a prévia desenhada
    embaixo dele, com largura = largura do nó e altura = Height."""
    bl_idname = "RangeUIButton"
    bl_label = "Button"

    text = StringProperty(name="Text", default="Button")
    button_height = FloatProperty(name="Height", default=40.0, min=8.0, soft_max=200.0,
                           description="Altura do botão (a largura é a do nó)")
    color = _color("Color", (0.20, 0.22, 0.26, 0.90))
    hover_color = _color("Hover", (0.30, 0.45, 0.75, 0.95))
    press_color = _color("Pressed", (0.15, 0.30, 0.55, 1.0))
    text_color = _color("Text Color", (1.0, 1.0, 1.0, 1.0))
    radius = FloatProperty(name="Roundness", default=1.0, min=0.0, max=1.0,
                           subtype="FACTOR", description="0 = quadrado, 1 = cápsula")
    border = FloatProperty(name="Border", default=0.0, min=0.0, max=0.3,
                           description="Espessura da borda, em fração da altura")
    border_color = _color("Border Color", (1.0, 1.0, 1.0, 0.8))
    text_size = FloatProperty(name="Text Size", default=0.45, min=0.1, max=1.0,
                              description="Tamanho do texto, em fração da altura")
    align = EnumProperty(name="Align", default="CENTER", items=(
        ("LEFT", "Left", ""), ("CENTER", "Center", ""), ("RIGHT", "Right", "")))
    shadow = BoolProperty(name="Shadow", default=False)

    def init(self, context):
        self.width = 200
        self.hide = True
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

    def draw_label(self):
        # Recolhido, o nó é só a alça: sem texto para não cobrir a prévia.
        return " " if self.hide else (self.text or "Button")

    def style(self):
        return {
            "color": tuple(self.color), "hover": tuple(self.hover_color),
            "press": tuple(self.press_color), "text_color": tuple(self.text_color),
            "radius": self.radius, "border": self.border,
            "border_color": tuple(self.border_color), "text_size": self.text_size,
            "align": self.align, "shadow": self.shadow,
        }


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
            buttons.append({
                "name": node.name,
                "text": node.text,
                # Retângulo normalizado na tela: x da esquerda, y do topo.
                "rect": ((nx - fx) / fw, (fy - ny) / fh, node.width / fw, node.button_height / fh),
                "style": node.style(),
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


def _active_frame(context):
    node = context.space_data.edit_tree.nodes.active
    return node if node is not None and node.bl_idname == "NodeFrame" else None


class RANGE_OT_ui_tree_capture(Operator):
    """Renderiza a câmera da cena e usa a imagem de fundo do Frame ativo"""
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
        # Trava a proporção do Frame na do jogo: a imagem nunca distorce.
        render = scene.render
        frame.shrink = False
        frame.height = frame.width * render.resolution_y / render.resolution_x
        return {'FINISHED'}


def _draw_backdrops():
    import bgl
    space = bpy.context.space_data
    tree = getattr(space, "edit_tree", None)
    if tree is None or tree.bl_idname != UITree.bl_idname:
        return
    for frame in tree.nodes:
        if frame.bl_idname != "NodeFrame" or not frame.ui_backdrop:
            continue
        image = bpy.data.images.get(frame.ui_backdrop)
        if image is None or image.gl_load():
            continue
        # A vista do Node Editor está em unidades * escala da UI.
        scale = bpy.context.user_preferences.system.ui_scale  # U.dpi_fac
        x, y = _abs_location(frame)
        x0, y1 = x * scale, y * scale
        x1, y0 = x0 + frame.width * scale, y1 - frame.height * scale
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
        if node.bl_idname != UIButtonNode.bl_idname:
            continue
        scale = bpy.context.user_preferences.system.ui_scale  # U.dpi_fac
        x, y = _abs_location(node)
        w, h = node.width * scale, node.button_height * scale
        x, y = x * scale, y * scale - h
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
        layout.row().prop(context.space_data.edit_tree, "preview_state", expand=True)
        frame = _active_frame(context)
        if frame is not None:
            box = layout.box()
            box.label("Fundo da tela: %s" % (frame.label or frame.name))
            box.prop_search(frame, "ui_backdrop", bpy.data, "images", text="")
            box.operator(RANGE_OT_ui_tree_capture.bl_idname, icon="RENDER_STILL")
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
    RANGE_OT_ui_tree_bake, RANGE_OT_ui_tree_capture, NODE_PT_range_ui_tree)

_draw_handle = None


def register():
    global _draw_handle
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.NodeFrame.ui_backdrop = StringProperty(
        name="Backdrop", description="Imagem de fundo desta tela no editor (não vai para o jogo)")
    nodeitems_utils.register_node_categories("RANGE_UI_TREE", CATEGORIES)
    _draw_handle = bpy.types.SpaceNodeEditor.draw_handler_add(
        _draw_editor, (), "WINDOW", "PRE_VIEW")


def unregister():
    bpy.types.SpaceNodeEditor.draw_handler_remove(_draw_handle, "WINDOW")
    del bpy.types.NodeFrame.ui_backdrop
    nodeitems_utils.unregister_node_categories("RANGE_UI_TREE")
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
