# Track Tool: converte uma pista feita com Curve + Array (Fit Curve) + Curve modifier.
#
# convert_curve_array(track_mesh_obj) -> curve_obj:
#   - a curva vem do Curve modifier (ou do Array, se não houver);
#   - cria/refaz o perfil "<malha> perfil" com uma faixa MESH ("Secao") apontando para uma CÓPIA
#     da malha (sem modificadores, com Fake User), mais Talude e Morro para o terreno;
#   - radius de cada ponto vira width_left/right = radius * meia largura do asfalto da seção
#     (medida no primeiro degrau vertical, a guia);
#   - liga range_track (enabled, inclinação Auto, torção Z Up);
#   - esconde a malha original (viewport e render/jogo) e tira a colisão dela, sem apagar.
import bpy

from . import layout
from . import props


def _find_mods(ob):
    arr = None
    cmod = None
    for m in ob.modifiers:
        if m.type == 'ARRAY' and arr is None:
            arr = m
        elif m.type == 'CURVE' and cmod is None:
            cmod = m
    return arr, cmod


def find_source_curve(track_mesh_obj):
    arr, cmod = _find_mods(track_mesh_obj)
    curve = None
    if cmod is not None and cmod.object is not None:
        curve = cmod.object
    elif arr is not None and arr.fit_type == 'FIT_CURVE' and arr.curve is not None:
        curve = arr.curve
    return curve, arr, cmod


def _section_copy(track_mesh_obj, cmod):
    name = track_mesh_obj.name + "_Secao"
    old = bpy.data.objects.get(name)
    if old is not None and old.users <= 1 and not old.users_scene:
        oldme = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if oldme is not None and oldme.users == 0:
            bpy.data.meshes.remove(oldme)
    me = track_mesh_obj.data.copy()
    me.name = name
    axis = cmod.deform_axis if cmod is not None else 'POS_X'
    if axis in ('POS_Y', 'NEG_Y', 'POS_Z', 'NEG_Z'):
        # deixa o eixo da curva em X (Y vira lateral)
        for v in me.vertices:
            x, y, z = v.co
            if axis in ('POS_Y', 'NEG_Y'):
                v.co = (y, -x, z) if axis == 'POS_Y' else (-y, x, z)
            else:
                v.co = (z, y, -x) if axis == 'POS_Z' else (-z, y, x)
    elif axis == 'NEG_X':
        for v in me.vertices:
            x, y, z = v.co
            v.co = (-x, -y, z)
    sec = bpy.data.objects.new(name, me)
    sec.scale = track_mesh_obj.scale
    sec.use_fake_user = True
    sec.game.physics_type = 'NO_COLLISION'
    return sec


def convert_curve_array(track_mesh_obj):
    props.register()
    curve, arr, cmod = find_source_curve(track_mesh_obj)
    if curve is None or curve.type != 'CURVE':
        raise ValueError("%s has no Array (Fit Curve) / Curve modifier with a curve"
                         % track_mesh_obj.name)
    scene = props.track_scene(track_mesh_obj)

    sec = _section_copy(track_mesh_obj, cmod)
    section = layout.mesh_section(sec)
    w0 = 0.5 * (section.riser_offset(1) + section.riser_offset(-1))

    pname = track_mesh_obj.name + " perfil"
    profs = scene.range_track_profiles
    prof = None
    for p in profs:
        if p.name == pname:
            prof = p
            break
    if prof is None:
        prof = profs.add()
        prof.name = pname
    prof.bands.clear()
    prof.symmetric = True
    props.add_band(prof, "Secao", 'MESH', w0, mesh_object=sec, collision=True)
    props.add_band(prof, "Talude", 'SLOPE', 4.0, material=props.ensure_material('slope'),
                   slope_deg=-15.0)
    props.add_band(prof, "Morro", 'HILL', 200.0, 28.0, material=props.ensure_material('grass'))

    st = curve.range_track
    st.enabled = True
    st.profile = pname
    st.bank_auto = True
    st.points.clear()
    sp = None
    for s in curve.data.splines:
        if s.type == 'BEZIER' and len(s.bezier_points) >= 2:
            sp = s
            break
    if sp is not None:
        use_r = getattr(curve.data, "use_radius", True)
        for k, bp in enumerate(sp.bezier_points):
            p = st.points.add()
            p.index = k
            r = bp.radius if use_r else 1.0
            p.width_left = r * w0
            p.width_right = r * w0
            p.bank_mode = 'AUTO'
    curve.data.twist_mode = 'Z_UP'

    track_mesh_obj.hide = True
    track_mesh_obj.hide_render = True
    track_mesh_obj.game.physics_type = 'NO_COLLISION'
    track_mesh_obj["range_track_converted_to"] = curve.name
    return curve
