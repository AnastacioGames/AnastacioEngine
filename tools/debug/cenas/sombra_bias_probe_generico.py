"""Variante generica de sombra_bias_probe.py: em vez de um cubo e amostras fixas, le
qualquer cena ja existente. Convencao: o objeto receptor (chao) e o mesh com o centro Z
mais baixo; todo outro mesh e tratado como ocludor (AABB). Amostra uma grade sobre a area
do receptor e compara luminancia renderizada contra o gabarito geometrico (raio ate a
luz Sun cruza algum ocludor?). Pensado para sombra_bias_suggest.py, que roda a mesma cena
varias vezes com bias/slopebias diferentes e sugere o melhor -- nunca escreve na cena
original.
"""
import Range
import json
import os
import ctypes

_state = {}
GRID = 8  # 8x8 amostras sobre a area do receptor


def _write(data):
    path = os.environ.get('SOMBRA_TEST_LOG')
    if path:
        with open(path, 'a') as handle:
            handle.write(json.dumps(data) + '\n')


def _ray_hits_aabb(origin, direction, box_min, box_max):
    tmin, tmax = 0.0, 1.0
    for i in range(3):
        o, d = origin[i], direction[i]
        lo, hi = box_min[i], box_max[i]
        if abs(d) < 1e-9:
            if o < lo or o > hi:
                return False
            continue
        t1 = (lo - o) / d
        t2 = (hi - o) / d
        if t1 > t2:
            t1, t2 = t2, t1
        tmin = max(tmin, t1)
        tmax = min(tmax, t2)
        if tmin > tmax:
            return False
    return True


def _expected_shadow(point, light_dir_to_source, occluders):
    far = tuple(d * 1000.0 for d in light_dir_to_source)
    origin = tuple(point[i] + light_dir_to_source[i] * 1e-3 for i in range(3))
    return any(_ray_hits_aabb(origin, far, lo, hi) for lo, hi in occluders)


def _luminance(pixel):
    return 0.2126 * pixel[0] + 0.7152 * pixel[1] + 0.0722 * pixel[2]


def _read_pixel(screen_xy, width, height):
    gl = ctypes.WinDLL('opengl32.dll') if os.name == 'nt' else ctypes.CDLL('libGL.so.1')
    gl.glReadPixels.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
    px = max(0, min(width - 1, int(screen_xy[0] * width)))
    py = max(0, min(height - 1, int((1.0 - screen_xy[1]) * height)))
    pixel = (ctypes.c_ubyte * 3)()
    gl.glReadPixels(px, py, 1, 1, 0x1907, 0x1401, pixel)
    return (pixel[0] / 255.0, pixel[1] / 255.0, pixel[2] / 255.0)


_aabb_cache = {}


def _world_aabb(obj):
    """AABB real a partir dos vertices (world space), nao da convencao sintetica
    worldPosition +/- worldScale (so valida para meshes com meia-extensao 1 local, usada
    pelos geradores de cena de teste deste repo -- malhas reais de jogo nao seguem isso)."""
    cached = _aabb_cache.get(obj.name)
    if cached is not None:
        return cached
    lo = [float('inf')] * 3
    hi = [float('-inf')] * 3
    transform = obj.worldTransform
    for mesh in obj.meshes:
        for matid in range(len(mesh.materials)):
            for i in range(mesh.getVertexArrayLength(matid)):
                local = mesh.getVertex(matid, i).XYZ
                world = transform * local
                for k in range(3):
                    v = world[k]
                    if v < lo[k]:
                        lo[k] = v
                    if v > hi[k]:
                        hi[k] = v
    result = (tuple(lo), tuple(hi))
    _aabb_cache[obj.name] = result
    return result


def _footprint_area(obj):
    lo, hi = _world_aabb(obj)
    return (hi[0] - lo[0]) * (hi[1] - lo[1])


def _pick_receiver_and_occluders(scene, receiver_name=None):
    meshes = [ob for ob in scene.objects if ob.meshes]
    if not meshes:
        return None, []
    if receiver_name:
        receiver = next((ob for ob in meshes if ob.name == receiver_name), None)
        if receiver is None:
            return None, []
    else:
        # Sem nome explicito: maior area XY como aproximacao de "piso/pista" -- heuristica
        # que falha se houver um ceu/nuvem gigante na cena (ver sombra_bias_probe_generico).
        receiver = max(meshes, key=_footprint_area)
    occluders = []
    for ob in meshes:
        if ob is receiver:
            continue
        occluders.append(_world_aabb(ob))
    return receiver, occluders


MAX_WAIT_FRAMES = 600  # ~10s a 60fps: algumas cenas so adicionam o grupo da luz depois
                       # que o piloto entra (AddObject tardio), nao no carregamento.


def tick(cont):
    if not os.environ.get('SOMBRA_TEST_LOG'):
        return
    frame = _state.get('frame', 0) + 1
    _state['frame'] = frame
    scene = Range.logic.getCurrentScene()
    if _state.get('done'):
        return
    try:
        cam = scene.active_camera
        light_name = cam['ae_light_name'] if 'ae_light_name' in cam else None
        if light_name:
            sun = scene.objects.get(light_name)
        else:
            # Sem nome explicito: primeiro objeto cujo nome sugere Sol -- ambiguo se
            # houver mais de um (ex.: uma luz "Sun" real e outra "Sun.001" decorativa).
            sun = next((ob for ob in scene.objects if ob.name.lower().startswith('sun')
                        or 'sol' in ob.name.lower()), None)
        if sun is None:
            if frame < MAX_WAIT_FRAMES:
                return  # ainda pode aparecer (grupo adicionado tardiamente) -- tenta de novo
            names = [ob.name for ob in scene.objects if 'sun' in ob.name.lower() or 'sol' in ob.name.lower()]
            _write(dict(event='failure', frame=frame,
                         error='luz Sun/Sol nao apareceu em %d frames (nome="%s") -- provavelmente '
                               'so e adicionada por fluxo de jogo (menu/selecao) que este probe passivo '
                               'nao reproduz' % (MAX_WAIT_FRAMES, light_name),
                         candidatosSun=names))
            _state['done'] = True
            Range.logic.endGame()
            return
        _state['done'] = True

        receiver_name = cam['ae_receiver_name'] if 'ae_receiver_name' in cam else None
        receiver, occluders = _pick_receiver_and_occluders(scene, receiver_name)
        if receiver is None or not occluders:
            _write(dict(event='failure', frame=frame,
                         error='sem receptor/ocludor identificavel na cena'))
            Range.logic.endGame()
            return
        light_dir_to_source = tuple(-c for c in sun.getAxisVect((0.0, 0.0, -1.0)))

        r_lo, r_hi = _world_aabb(receiver)
        width, height = Range.render.getWindowWidth(), Range.render.getWindowHeight()
        rows = []
        for ix in range(GRID):
            for iy in range(GRID):
                x = r_lo[0] + (r_hi[0] - r_lo[0]) * (ix + 0.5) / GRID
                y = r_lo[1] + (r_hi[1] - r_lo[1]) * (iy + 0.5) / GRID
                point = (x, y, r_hi[2] + 0.02)
                expected_dark = _expected_shadow(point, light_dir_to_source, occluders)
                screen = cam.getScreenPosition(list(point))
                if not (0.0 <= screen[0] <= 1.0 and 0.0 <= screen[1] <= 1.0):
                    continue  # fora da tela, nao avaliavel por leitura de pixel
                pixel = _read_pixel(screen, width, height)
                rows.append(dict(point=point, expectedDark=expected_dark, luminance=_luminance(pixel)))
        _write(dict(event='samples', rows=rows, receiver=receiver.name,
                     occluderCount=len(occluders), waitedFrames=frame))
        _write(dict(event='finished'))
        Range.logic.endGame()
    except Exception as error:
        _write(dict(event='failure', frame=frame, error=repr(error)))
        Range.logic.endGame()
