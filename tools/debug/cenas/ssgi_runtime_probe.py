"""Embedded by criar_cena_ssgi.py. Diagnostic readback of five tiny textures, never a visual screenshot."""
import Range
import os
import json
import ctypes
import time

_state = {}


def _libgl():
    return ctypes.WinDLL('opengl32.dll') if os.name == 'nt' else ctypes.CDLL('libGL.so.1')
_shader = r'''
#ifdef USE_CORE_PROFILE
#define texture2D texture
in vec2 texCoordVarying;
layout(location=0) out vec4 outputs[5];
#define gl_FragData outputs
#endif
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DataTextures[7];
void main() {
#ifdef USE_CORE_PROFILE
    vec2 uv = texCoordVarying;
#else
    vec2 uv = gl_TexCoord[0].xy;
#endif
    gl_FragData[0] = texture2D(bgl_DataTextures[0], uv);
    gl_FragData[1] = texture2D(bgl_DataTextures[1], uv);
    gl_FragData[2] = texture2D(bgl_DataTextures[2], uv);
    gl_FragData[3] = texture2D(bgl_DataTextures[3], uv);
    gl_FragData[4] = texture2D(bgl_RenderedTexture, uv);
}
'''


def _write(data):
    path = os.environ.get('SSGI_TEST_LOG')
    if path:
        with open(path, 'a') as handle:
            handle.write(json.dumps(data) + '\n')


def _readback():
    gl = _libgl()
    gl.glGetTexImage.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
    previous = ctypes.c_int()
    gl.glGetIntegerv(0x8069, ctypes.byref(previous))  # GL_TEXTURE_BINDING_2D
    result = []
    for index in range(5):
        code = _state['probe'].offScreen.colorBindCodes[index]
        if code < 0:
            raise AssertionError('Diagnostic attachment %d was not allocated' % index)
        gl.glBindTexture(0x0DE1, code)
        pixels = (ctypes.c_float * (80 * 60 * 4))()
        gl.glGetTexImage(0x0DE1, 0, 0x1908, 0x1406, pixels)
        result.append(list(pixels))
    gl.glBindTexture(0x0DE1, previous.value)
    return result, gl.glGetError()


def _summary(frame):
    values, error = _readback()
    if len(values) != 5:
        raise AssertionError('Expected five diagnostic attachments')
    geom, albedo, direct, linear, display = values
    valid = [i for i in range(0, len(geom), 4) if geom[i + 3] > 0.99 and sum(v * v for v in geom[i:i + 3]) > 0.5]
    report = dict(frame=frame, glError=error, validPixels=len(valid),
                  eligiblePixels=sum(albedo[i + 3] > 0.99 for i in valid),
                  radiance=sum(sum(direct[i:i + 3]) for i in valid),
                  metallicPixels=sum(sum(albedo[i:i + 3]) < 1e-5 for i in valid),
                  displaySum=sum(display), stats=Range.logic.getRenderStats())
    if frame == 40:
        _state['on'] = display
    if frame == 80 and 'on' in _state:
        report['onOffDifference'] = sum(abs(a - b) for a, b in zip(_state['on'], display))
        red = [i for i in valid if albedo[i] > 0.5 and albedo[i + 1] < 0.1]
        report['redReceiverDelta'] = [sum(_state['on'][i + c] - display[i + c] for i in red) for c in range(3)]
        # Emission sources deliberately have ineligible albedo alpha, so this
        # mask reads only the diffuse white wall in the emissive fixture.
        white = [i for i in valid if albedo[i + 3] > 0.99 and min(albedo[i:i + 3]) > 0.5]
        report['whiteReceiverPixels'] = len(white)
        report['whiteReceiverDelta'] = [sum(_state['on'][i + c] - display[i + c] for i in white) for c in range(3)]
    _write(report)


def _compile_core_fragments():
    directory = os.environ.get('SSGI_SHADER_DIR')
    if not directory:
        return
    gl = _libgl()
    get_proc = gl.wglGetProcAddress if os.name == 'nt' else gl.glXGetProcAddressARB
    get_proc.argtypes = [ctypes.c_char_p]
    get_proc.restype = ctypes.c_void_p
    functype = ctypes.WINFUNCTYPE if os.name == 'nt' else ctypes.CFUNCTYPE
    def function(name, result, *args):
        address = get_proc(name.encode('ascii'))
        if not address:
            raise RuntimeError('Missing GL entry point ' + name)
        return functype(result, *args)(address)
    create = function('glCreateShader', ctypes.c_uint, ctypes.c_uint)
    source = function('glShaderSource', None, ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_char_p), ctypes.c_void_p)
    compile_shader = function('glCompileShader', None, ctypes.c_uint)
    get = function('glGetShaderiv', None, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_int))
    get_log = function('glGetShaderInfoLog', None, ctypes.c_uint, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
    delete = function('glDeleteShader', None, ctypes.c_uint)
    for name in ('RAS_SSGI2DFilter.glsl', 'RAS_SSGIImage2DFilter.glsl'):
        with open(os.path.join(directory, name), encoding='utf-8') as handle:
            code = ('#version 330 core\n#define USE_CORE_PROFILE\n#define SSGI_SLOT 0\n' + handle.read()).encode('utf-8')
        shader = create(0x8B30)
        try:
            string = ctypes.c_char_p(code)
            source(shader, 1, ctypes.byref(string), None)
            compile_shader(shader)
            success = ctypes.c_int()
            get(shader, 0x8B81, ctypes.byref(success))
            if not success.value:
                message = ctypes.create_string_buffer(8192)
                get_log(shader, len(message), None, message)
                raise AssertionError(name + ': ' + message.value.decode('utf-8', errors='replace'))
            _write(dict(event='coreFragmentCompiled', shader=name))
        finally:
            delete(shader)


def tick(cont):
    # Abrir a cena manualmente não deve alternar efeitos, câmera ou resolução.
    shot = os.environ.get('SSGI_SHOT')
    if not os.environ.get('SSGI_TEST_LOG') and not os.environ.get('SSGI_BENCH') and not shot:
        return
    frame = _state.get('frame', 0) + 1
    _state['frame'] = frame
    try:
        scene = Range.logic.getCurrentScene()
        manager = scene.filterManager
        if shot:
            # SSGI_SHOT=<path.png>, SSGI_SHOT_OFF=1 disables SSGI; Scene settings stay as saved.
            if frame == 1 and os.environ.get('SSGI_SHOT_OFF'):
                manager.changeSSGIValues(False)
            if frame == 45:
                Range.render.makeScreenshot(shot)
            if frame == 70:
                Range.logic.endGame()
            return
        benchmark = os.environ.get('SSGI_BENCH')
        if benchmark:
            if frame == 1:
                _state['start'] = time.perf_counter()
                try:
                    manager.changeSSGIValues(benchmark == 'on', 3.0, 1.0, 4, 8, 0.1)
                except RuntimeError:
                    if benchmark != 'off':
                        raise
                _write(dict(event='benchmark', enabled=benchmark == 'on'))
            if time.perf_counter() - _state['start'] >= 10.0:
                _write(dict(event='finished', frames=frame, seconds=time.perf_counter() - _state['start']))
                Range.logic.endGame()
            return
        if frame == 1:
            _state['start'] = time.perf_counter()
            _write(dict(event='start', objects=[ob.name for ob in scene.objects]))
            gl = _libgl()
            gl.glGetString.argtypes = [ctypes.c_uint]
            gl.glGetString.restype = ctypes.c_char_p
            _write(dict(event='gpu', renderer=gl.glGetString(0x1F01).decode('utf-8'), version=gl.glGetString(0x1F02).decode('utf-8')))
            try:
                manager.changeSSGIValues(True, 5.0, 1.0, 8, 16, 0.15)
            except RuntimeError as error:
                _state['disabled'] = True
                _write(dict(event='disabled', message=str(error)))
            if not _state.get('disabled'):
                probe = manager.addFilter(0, Range.logic.RAS_2DFILTER_CUSTOMFILTER, _shader)
                probe.addOffScreen(5, False, 80, 60, 1)
                _state['probe'] = probe
        if not _state.get('disabled'):
            if frame in (40, 80, 120, 160):
                _summary(frame)
            if frame == 60:
                manager.changeSSGIValues(False, 5.0, 1.0, 8, 16, 0.15)
            if frame == 90:
                manager.changeSSGIValues(True, 5.0, 1.0, 8, 16, 0.15)
                Range.render.setWindowSize(800, 600)
            if frame == 100:
                manager.changeSSGIValues(True, 5.0, 1.0, 8, 16, 0.15, 1)
            if frame == 110:
                # Built-in passes are private; subsequent frames verify the new buffer renders without GL errors.
                _write(dict(event='divisorChanged', divisor=1))
            if frame == 130:
                scene.active_camera = scene.objects['OrthoCamera']
            if frame == 170:
                _compile_core_fragments()
                try:
                    manager.changeSSGIValues(True, float('nan'))
                    raise AssertionError('NaN was accepted')
                except ValueError:
                    _write(dict(event='invalidParameterRejected'))
        if frame == 180:
            _write(dict(event='finished', frames=frame, seconds=time.perf_counter() - _state['start']))
            if os.environ.get('SSGI_TEST_LOG'):
                Range.logic.endGame()
    except Exception as error:
        _write(dict(event='failure', frame=frame, error=repr(error)))
        if os.environ.get('SSGI_TEST_LOG'):
            Range.logic.endGame()
        else:
            raise
