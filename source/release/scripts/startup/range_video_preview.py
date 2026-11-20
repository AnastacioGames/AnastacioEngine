# Prévia do Video Player na 3D View (Game Preview > Video Player): mostra o 1º quadro do vídeo
# onde o jogo o toca. Cutscene em tela cheia: dentro do quadro da câmera. "On Material": na malha do objeto,
# com o UV do material. Só visual: sem tocar, som, fade nem legendas.

import os

import bpy
from bpy.props import BoolProperty

MODULE = "anastacio_video"
COMPONENT = "VideoPlayer"
MAX_POLYS = 4000

_handles = []
_images = {}      # caminho absoluto -> nome do Image carregado só para a prévia
_geometry = {}    # nome do objeto -> (chave, triângulos)


def _component(ob):
    return next((c for c in ob.game.components if c.module == MODULE and c.name == COMPONENT), None)


def _video_path(ob, props):
    value = props["File"].value if "File" in props else ""
    if not value:
        return ""
    path = bpy.path.abspath(value, library=ob.library)
    if os.path.isfile(path):
        return path
    exported = bpy.path.abspath("//videos/" + os.path.basename(value.replace("\\", "/")))
    return exported if os.path.isfile(exported) else ""


def _frame_image(path):
    """Image (fonte MOVIE) do vídeo, o 1º quadro; carregado uma vez e removido ao desligar."""
    if path in _images and _images[path] is None:
        return None  # a carga falhou: não tenta de novo a cada desenho
    name = _images.get(path)
    image = bpy.data.images.get(name) if name else None
    if image is None:
        try:
            image = bpy.data.images.load(path)
        except RuntimeError:
            _images[path] = None
            return None
        image.name = "__video_preview__"
        _images[path] = image.name
    return image


def _bind(image):
    """Código GL do quadro, ou 0."""
    if image is None or image.gl_load():
        return 0
    return image.bindcode[0]


def _program():
    import bgl
    prog = bgl.Buffer(bgl.GL_INT, 1)
    bgl.glGetIntegerv(bgl.GL_CURRENT_PROGRAM, prog)
    return prog[0]


def _clear():
    for name in list(_images.values()):
        image = bpy.data.images.get(name) if name else None
        if image is not None and image.users == 0:
            bpy.data.images.remove(image)
    _images.clear()
    _geometry.clear()


def _material_index(ob, props):
    name = props["Material"].value if "Material" in props else ""
    mats = ob.data.materials
    if name:
        for i, m in enumerate(mats):
            if m is not None and m.name == name:
                return i, m
    i = ob.active_material_index
    return (i, mats[i]) if 0 <= i < len(mats) else (-1, None)


def _triangles(ob, index, mat):
    """Triângulos (posição, uv) das faces do material do vídeo; em cache por malha."""
    me = ob.data
    slot = next((s for s in mat.texture_slots if s and s.texture and s.texture.type == 'IMAGE'), None)
    layer = None
    if slot is not None and slot.uv_layer:
        layer = me.uv_layers.get(slot.uv_layer)
    layer = layer or me.uv_layers.active
    if layer is None or len(me.polygons) > MAX_POLYS:
        return []
    key = (me.name, len(me.vertices), len(me.polygons), len(me.loops), index, layer.name, ob.mode)
    cached = _geometry.get(ob.name)
    if cached and cached[0] == key:
        return cached[1]
    tris = []
    verts = me.vertices
    for poly in me.polygons:
        if poly.material_index != index:
            continue
        loops = list(poly.loop_indices)
        for k in range(1, len(loops) - 1):
            for li in (loops[0], loops[k], loops[k + 1]):
                tris.append((tuple(verts[me.loops[li].vertex_index].co), tuple(layer.data[li].uv)))
    _geometry[ob.name] = (key, tris)
    return tris


def _videos(scene):
    """(objeto, props, caminho) de cada Video Player da cena com o arquivo no disco."""
    for ob in scene.objects:
        comp = _component(ob)
        if comp is None:
            continue
        path = _video_path(ob, comp.properties)
        if path:
            yield ob, comp.properties, path


def _draw_material():
    context = bpy.context
    scene = context.scene
    if not getattr(scene, "range_video_preview", False):
        return
    import bgl
    for ob, props, path in _videos(scene):
        if props["Fullscreen"].value or ob.type != 'MESH' or not ob.is_visible(scene):
            continue
        index, mat = _material_index(ob, props)
        if mat is None:
            continue
        try:
            tris = _triangles(ob, index, mat)
            code = _bind(_frame_image(path)) if tris else 0
            if not code:
                continue
            m = ob.matrix_world.transposed()
            flat = bgl.Buffer(bgl.GL_FLOAT, 16, [v for row in m for v in row])
            program = _program()
            bgl.glPushAttrib(bgl.GL_ALL_ATTRIB_BITS)
            bgl.glPushMatrix()
            try:
                bgl.glMultMatrixf(flat)
                bgl.glUseProgram(0)
                bgl.glDisable(bgl.GL_LIGHTING)
                bgl.glEnable(bgl.GL_TEXTURE_2D)
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, code)
                bgl.glEnable(bgl.GL_DEPTH_TEST)
                bgl.glDepthFunc(bgl.GL_LEQUAL)
                bgl.glEnable(bgl.GL_POLYGON_OFFSET_FILL)
                bgl.glPolygonOffset(-1.0, -1.0)
                bgl.glColor4f(1.0, 1.0, 1.0, 1.0)
                bgl.glBegin(bgl.GL_TRIANGLES)
                for co, uv in tris:
                    bgl.glTexCoord2f(uv[0], uv[1])
                    bgl.glVertex3f(co[0], co[1], co[2])
                bgl.glEnd()
            finally:
                bgl.glPopMatrix()
                bgl.glPopAttrib()
                bgl.glUseProgram(program)
        except Exception as exc:  # a prévia nunca derruba o desenho da viewport
            print("[Video Player] preview failed: %s" % exc)


def _draw_fullscreen():
    context = bpy.context
    scene = context.scene
    if not getattr(scene, "range_video_preview", False):
        return
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return
    chosen = None
    for ob, props, path in _videos(scene):
        if props["Fullscreen"].value:
            chosen = (props, path)
    if chosen is None:
        return
    props, path = chosen
    import bgl
    import range_ui_tree
    try:
        image = _frame_image(path)
        code = _bind(image)
        if not code:
            return
        left, bottom, width, height = range_ui_tree._hud_frame_rect(context, region, rv3d)
        iw, ih = image.size
        aspect = (iw / ih) if iw and ih else 16.0 / 9.0
        fill = props["Fill Screen"].value if "Fill Screen" in props else False
        # Fill Screen cobre o quadro (corta); senão cabe inteiro, com barras.
        box = width / height
        u0, v0, u1, v1 = 0.0, 0.0, 1.0, 1.0
        x, y, w, h = left, bottom, width, height
        if fill:
            if aspect > box:
                crop = (1.0 - box / aspect) / 2.0
                u0, u1 = crop, 1.0 - crop
            else:
                crop = (1.0 - aspect / box) / 2.0
                v0, v1 = crop, 1.0 - crop
        elif aspect > box:
            h = width / aspect
            y = bottom + (height - h) / 2.0
        else:
            w = height * aspect
            x = left + (width - w) / 2.0
        program = _program()
        bgl.glPushAttrib(bgl.GL_ALL_ATTRIB_BITS)
        try:
            bgl.glUseProgram(0)
            bgl.glDisable(bgl.GL_LIGHTING)
            bgl.glDisable(bgl.GL_DEPTH_TEST)
            bgl.glEnable(bgl.GL_SCISSOR_TEST)
            bgl.glScissor(int(region.x + max(left, 0.0)), int(region.y + max(bottom, 0.0)),
                          max(int(min(left + width, region.width) - max(left, 0.0)) + 1, 1),
                          max(int(min(bottom + height, region.height) - max(bottom, 0.0)) + 1, 1))
            # fundo preto do quadro (as barras), como a cutscene no jogo
            bgl.glDisable(bgl.GL_TEXTURE_2D)
            bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
            bgl.glRectf(left, bottom, left + width, bottom + height)
            bgl.glEnable(bgl.GL_TEXTURE_2D)
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, code)
            bgl.glColor4f(1.0, 1.0, 1.0, 1.0)
            bgl.glBegin(bgl.GL_QUADS)
            for u, v, px, py in ((u0, v0, x, y), (u1, v0, x + w, y), (u1, v1, x + w, y + h), (u0, v1, x, y + h)):
                bgl.glTexCoord2f(u, v)
                bgl.glVertex2f(px, py)
            bgl.glEnd()
        finally:
            bgl.glPopAttrib()
            bgl.glUseProgram(program)
    except Exception as exc:
        print("[Video Player] preview failed: %s" % exc)


def _update(self, context):
    if not self.range_video_preview:
        _clear()
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def register():
    bpy.types.Scene.range_video_preview = BoolProperty(
        name="Video Player", default=False, update=_update,
        description="Show the first frame of Video Players in the 3D View: on the material or as a cutscene "
                    "inside the camera frame")
    _handles.append(bpy.types.SpaceView3D.draw_handler_add(_draw_material, (), "WINDOW", "POST_VIEW"))
    _handles.append(bpy.types.SpaceView3D.draw_handler_add(_draw_fullscreen, (), "WINDOW", "POST_PIXEL"))


def unregister():
    while _handles:
        bpy.types.SpaceView3D.draw_handler_remove(_handles.pop(), "WINDOW")
    _clear()
    del bpy.types.Scene.range_video_preview
