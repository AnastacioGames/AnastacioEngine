"""Prévia do Video Player na 3D View: o primeiro quadro do vídeo no material do objeto, sem dar Play.

No jogo o componente VideoPlayer (anastacio_video) troca a imagem do primeiro slot de textura de imagem do
material pelo vídeo.  Com Scene.range_video_poster_preview ligado, o editor troca essa imagem por um Image de
filme (primeiro quadro) e guarda a original na própria textura (propriedade "range_video_orig").  A troca é
desfeita ao desligar, ao salvar e ao iniciar o jogo: o arquivo nunca guarda o vídeo no lugar da textura, e o
toggle volta desligado.  Só vídeo em material; Fullscreen, reprodução e som são do jogo."""

import os

import bpy
from bpy.props import BoolProperty

KEY = "range_video_orig"


def _video_path(ob, props):
    """Caminho do vídeo como o runtime resolve (anastacio_video.resolve_path): o escrito, senão //videos/."""
    value = props["File"].value
    if not value:
        return ""
    full = bpy.path.abspath(value, library=ob.library)
    if os.path.isfile(full):
        return full
    exported = bpy.path.abspath("//videos/" + os.path.basename(value.replace("\\", "/")), library=ob.library)
    return exported if os.path.isfile(exported) else ""


def _target_texture(ob, props):
    from bl_ui.properties_video_player import video_texture_slot
    if ob.type != 'MESH':
        return None
    name = props["Material"].value if "Material" in props else ""
    mat = bpy.data.materials.get(name) if name else ob.active_material
    slot = video_texture_slot(mat)
    return slot.texture if slot is not None else None


def restore():
    for tex in bpy.data.textures:
        if KEY in tex:
            tex.image = bpy.data.images.get(tex[KEY]) if tex[KEY] else None
            del tex[KEY]
            tex.update_tag()


def apply(scene):
    from bl_ui.properties_video_player import video_component
    for ob in scene.objects:
        component = video_component(ob)
        if component is None:
            continue
        props = component.properties
        if "File" not in props or "Fullscreen" not in props or props["Fullscreen"].value:
            continue
        path = _video_path(ob, props)
        tex = _target_texture(ob, props) if path else None
        if tex is None:
            continue
        try:
            movie = bpy.data.images.load(path, check_existing=True)
        except RuntimeError:
            continue
        if KEY not in tex:
            tex[KEY] = tex.image.name if tex.image else ""
        tex.image = movie
        tex.update_tag()


def _update(self, context):
    restore()
    if self.range_video_poster_preview:
        apply(self)
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


@bpy.app.handlers.persistent
def _off(_arg=None):
    """Antes de salvar e de jogar: texturas como o usuário as deixou, toggle desligado."""
    restore()
    for scene in bpy.data.scenes:
        if scene.range_video_poster_preview:
            scene.range_video_poster_preview = False


def register():
    bpy.types.Scene.range_video_poster_preview = BoolProperty(
        name="Video Poster",
        description="Show the first frame of the Video Players on their materials in the 3D View "
                    "(turns off when saving or playing)",
        default=False, update=_update)
    for handlers in (bpy.app.handlers.save_pre, bpy.app.handlers.game_pre):
        if _off not in handlers:
            handlers.append(_off)


def unregister():
    restore()
    for handlers in (bpy.app.handlers.save_pre, bpy.app.handlers.game_pre):
        if _off in handlers:
            handlers.remove(_off)
    del bpy.types.Scene.range_video_poster_preview
