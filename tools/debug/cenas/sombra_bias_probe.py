"""Embedded by criar_cena_sombra_bias.py. Compara a sombra renderizada contra o gabarito
geometrico (raio luz->ponto cruza a AABB do cubo?) em uma faixa de pontos no chao, do centro
do cubo para fora. Loga cada amostra em SOMBRA_TEST_LOG, depois fecha o jogo.
"""
import Range
import json
import math
import os
import ctypes

_state = {}


def _samples_for(angle_deg, scale):
    """Mesma formula de criar_cena_sombra_bias.py -- evita serializar a lista de
    pontos numa Game Property STRING (limite curto, ~128 chars, nao cabe a lista)."""
    elevation = math.radians(angle_deg)
    dx, dz = math.cos(elevation), -math.sin(elevation)
    shadow_dir_x = -dx
    length = abs(shadow_dir_x)
    if length < 1e-6:
        shadow_dir_x = 1.0
    else:
        shadow_dir_x /= length
    return [(shadow_dir_x * (i * 0.3) * scale, 0.0, 0.02) for i in range(20)]


def _write(data):
    path = os.environ.get('SOMBRA_TEST_LOG')
    if path:
        with open(path, 'a') as handle:
            handle.write(json.dumps(data) + '\n')


def _ray_hits_aabb(origin, direction, box_min, box_max):
    """Slab test. origin/direction/box_min/box_max sao tuplas (x, y, z)."""
    tmin, tmax = 0.0, 1.0  # so nos interessa o segmento origin -> origin+direction (t em [0,1])
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


def _expected_shadow(point, light_dir_to_source, cube_min, cube_max):
    """light_dir_to_source: direcao unitaria do chao ate a fonte (raios paralelos --
    Sun nao tem posicao real, so direcao). Estende bem alem da cena (raio ~infinito)."""
    far = tuple(d * 1000.0 for d in light_dir_to_source)
    # Afasta a origem da propria superficie do chao para nao bater nela mesma.
    origin = tuple(point[i] + light_dir_to_source[i] * 1e-3 for i in range(3))
    return _ray_hits_aabb(origin, far, cube_min, cube_max)


def _luminance(pixel):
    r, g, b = pixel[0], pixel[1], pixel[2]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _read_pixel(screen_xy, width, height):
    gl = ctypes.WinDLL('opengl32.dll') if os.name == 'nt' else ctypes.CDLL('libGL.so.1')
    gl.glReadPixels.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
    px = max(0, min(width - 1, int(screen_xy[0] * width)))
    # Y da tela cresce para baixo; GL le o framebuffer de baixo para cima.
    py = max(0, min(height - 1, int((1.0 - screen_xy[1]) * height)))
    pixel = (ctypes.c_ubyte * 3)()
    gl.glReadPixels(px, py, 1, 1, 0x1907, 0x1401, pixel)  # GL_RGB, GL_UNSIGNED_BYTE
    return (pixel[0] / 255.0, pixel[1] / 255.0, pixel[2] / 255.0)


def tick(cont):
    if not os.environ.get('SOMBRA_TEST_LOG'):
        return
    frame = _state.get('frame', 0) + 1
    _state['frame'] = frame
    scene = Range.logic.getCurrentScene()
    cam = scene.active_camera
    # 15 frames de aquecimento: shadow buffer e cascatas precisam estabilizar.
    if frame < 15:
        return
    try:
        if frame == 15:
            cube = scene.objects['Cube']
            light = scene.objects['Sun']
            samples = _samples_for(cam['ae_angle'], cam['ae_scale'])
            cube_min = tuple(cube.worldPosition[i] - cube.worldScale[i] for i in range(3))
            cube_max = tuple(cube.worldPosition[i] + cube.worldScale[i] for i in range(3))
            # Direcao do chao at a fonte = oposto de para onde a luz "aponta" (-Z local).
            light_dir_to_source = tuple(-c for c in light.getAxisVect((0.0, 0.0, -1.0)))
            width, height = Range.render.getWindowWidth(), Range.render.getWindowHeight()
            rows = []
            for point in samples:
                point = tuple(point)
                expected_dark = _expected_shadow(point, light_dir_to_source, cube_min, cube_max)
                screen = cam.getScreenPosition(list(point))
                pixel = _read_pixel(screen, width, height)
                rows.append(dict(point=point, expectedDark=expected_dark, luminance=_luminance(pixel)))
            _write(dict(event='samples', rows=rows,
                         config=dict(bias=cam['ae_bias'], slopebias=cam['ae_slopebias'],
                                     angle=cam['ae_angle'], scale=cam['ae_scale'])))
        if frame == 16:
            _write(dict(event='finished'))
            Range.logic.endGame()
    except Exception as error:
        _write(dict(event='failure', frame=frame, error=repr(error)))
        Range.logic.endGame()
