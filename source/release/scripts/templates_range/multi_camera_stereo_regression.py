"""Regression test for multiple cameras/viewports/stereo drawing (Ketsji Plan 3).

Attach an Always sensor (pulse enabled) to a Python controller in Module mode:
    multi_camera_stereo_regression.main

Companion of drawing_callbacks_regression.py, which covers the single
camera/mono case. Use a controlled file with exactly one running scene and:

- the active camera, plus at least one additional camera with
  ``useViewport = True`` (KX_KetsjiEngine.cpp only renders a non-active
  camera when it has a viewport enabled, see GetRenderData()); or
- any camera setup with a stereo mode enabled in the render settings
  (side-by-side/anaglyph/interlaced/etc).

Both can be combined (several viewport cameras with stereo on). The script
does not configure viewports or stereo itself -- that is scene/file setup,
done by the user before running the test.

The script auto-detects, from the events it observes, which cameras and
eyes are actually driven by the engine; it does not assume mono or a fixed
camera count in advance. It validates:

- pre_draw_setup and pre_draw always agree on camera and eye;
- every camera rendered this frame is one that exists in scene.cameras and
  is either the active camera or has useViewport == True;
- the same set of (camera, eye) pairs repeats identically across logical
  game frames once the configuration stabilizes.

KX_KetsjiEngine::GetRenderData() renders each eye inside the same off-screen
for most stereo modes (one post_draw group carries both eyes), but splits
interlaced/vinterlace/anaglyph modes into one off-screen per eye (two
post_draw groups per logical game frame, each with a single eye). The script
does not assume either shape: it buffers raw post_draw-delimited groups and,
once it has seen two of them, detects whether they pair up into one logical
frame (same cameras, every eye complementary) or each already is a complete
logical frame on its own. That detection runs once per test run and is then
applied consistently.

Do not suspend, replace or end the test scene while this script is running.
The script appends its own callbacks without replacing callbacks already
registered by the game, and removes only the occurrences it added.
"""

import Range as bge


TARGET_FRAMES = 5
MAX_IDLE_PULSES = 600

_events = []
_registered_scene = None
_finished = False
_idle_pulses = 0
_frames_checked = 0
_reference_signature = None
_signature_buffer = []
_pair_mode = None  # None: undetected, True: two raw groups per logical frame, False: one


def _camera_name(camera):
    # Stereo cameras (and the mono case too) can be temporary proxies handed
    # to the callback. Copy only the name while it is valid; never retain the
    # proxy itself past this call.
    return None if camera is None else camera.name


def _camera_event(kind, camera, eye):
    _events.append((kind, _camera_name(camera), eye))


def _on_pre_draw_setup(camera):
    _camera_event("setup", camera, None)


def _on_pre_draw(camera):
    _camera_event("pre", camera, bge.render.getStereoEye())


def _on_post_draw(*args):
    # *args instead of a fixed arity so an unexpected future argument shows
    # up as a wrong length instead of being silently swallowed.
    _events.append(("post", None, len(args)))


def _register(scene):
    global _registered_scene

    scene.pre_draw_setup.append(_on_pre_draw_setup)
    scene.pre_draw.append(_on_pre_draw)
    scene.post_draw.append(_on_post_draw)
    _registered_scene = scene


def _remove_added_callback(callbacks, callback):
    for index in range(len(callbacks) - 1, -1, -1):
        if callbacks[index] is callback:
            del callbacks[index]
            return


def _unregister():
    global _registered_scene

    if _registered_scene is None:
        return None

    try:
        _remove_added_callback(_registered_scene.pre_draw_setup, _on_pre_draw_setup)
        _remove_added_callback(_registered_scene.pre_draw, _on_pre_draw)
        _remove_added_callback(_registered_scene.post_draw, _on_post_draw)
    except Exception as error:
        return str(error)
    finally:
        _registered_scene = None

    return None


def _split_frames(events):
    """Split complete setup/pre groups terminated by a post-draw."""
    frames = []
    current = []

    for event in events:
        current.append(event)
        if event[0] == "post":
            frames.append(current)
            current = []

    return frames, current


def _valid_camera_names(scene):
    active = scene.active_camera
    names = set()
    for camera in scene.cameras:
        if camera == active or camera.useViewport:
            names.add(camera.name)
    return names


def _validate_frame(frame, frame_number, valid_camera_names):
    errors = []
    prefix = "frame " + str(frame_number) + ": "

    if frame[-1][0] != "post" or frame[-1][2] != 0:
        errors.append(prefix + "grupo nao termina em post_draw com zero argumentos: " + str(frame))
        return errors, None

    body = frame[:-1]
    # KX_KetsjiEngine runs every pre_draw_setup up front while building the
    # render data (GetCameraRenderData, one call per camera), then runs every
    # pre_draw later during the actual per-camera render pass (RenderCamera).
    # With N cameras that yields "setup" x N followed by "pre" x N, not a
    # strict setup/pre alternation -- pair them up positionally instead.
    setups = [event for event in body if event[0] == "setup"]
    pres = [event for event in body if event[0] == "pre"]
    if len(setups) + len(pres) != len(body):
        errors.append(prefix + "evento inesperado fora de setup/pre/post: " + str(body))
        return errors, None
    if len(setups) != len(pres):
        errors.append(prefix + "numero de setup e pre nao corresponde: " + str(body))
        return errors, None

    signature = []
    for setup_event, pre_event in zip(setups, pres):
        _, setup_camera, _ = setup_event
        _, pre_camera, pre_eye = pre_event

        if setup_camera is None or pre_camera is None:
            errors.append(prefix + "camera nula em setup ou pre_draw")
            continue
        if setup_camera != pre_camera:
            errors.append(
                prefix + "camera divergente entre setup (" + str(setup_camera) +
                ") e pre_draw (" + str(pre_camera) + ")"
            )
            continue
        if setup_camera not in valid_camera_names:
            errors.append(
                prefix + "camera '" + setup_camera +
                "' nao e a ativa nem tem useViewport=True"
            )
            continue

        signature.append((setup_camera, pre_eye))

    if errors:
        return errors, None

    return [], tuple(sorted(signature))


def _merge_pair(first, second):
    """Combine two complementary single-eye raw groups into one logical frame."""
    return tuple(sorted(first + second))


def _detect_pair_mode(first, second):
    first_map = dict(first)
    second_map = dict(second)
    if set(first_map) != set(second_map):
        return False
    return all(first_map[camera] != second_map[camera] for camera in first_map)


def _drain_logical_frames():
    """Consume _signature_buffer, yielding (logical_signature, errors) pairs."""
    global _pair_mode

    results = []
    while True:
        if _pair_mode is None:
            if len(_signature_buffer) < 2:
                break
            _pair_mode = _detect_pair_mode(_signature_buffer[0], _signature_buffer[1])
            continue

        if _pair_mode:
            if len(_signature_buffer) < 2:
                break
            first = _signature_buffer.pop(0)
            second = _signature_buffer.pop(0)
            if not _detect_pair_mode(first, second):
                results.append((None, [
                    "par de olhos incompleto ou inconsistente: " + str(first) + " / " + str(second)
                ]))
                continue
            results.append((_merge_pair(first, second), []))
        else:
            if not _signature_buffer:
                break
            results.append((_signature_buffer.pop(0), []))

    return results


def _finish(owner, passed, messages):
    global _finished

    messages = list(messages)
    cleanup_error = _unregister()
    if cleanup_error is not None:
        passed = False
        messages.append("falha ao remover callbacks: " + cleanup_error)

    _finished = True
    owner["multi_camera_stereo_done"] = True
    owner["multi_camera_stereo_failed"] = not passed
    owner["multi_camera_stereo_frames"] = _frames_checked

    if passed:
        print(
            "[multi_camera_stereo_regression] PASS: " +
            str(_frames_checked) + " frames validados, assinatura " +
            str(_reference_signature),
            flush=True
        )
    else:
        for message in messages:
            print("[multi_camera_stereo_regression] detalhe: " + message, flush=True)
        print("[multi_camera_stereo_regression] FAIL", flush=True)


def main(cont):
    global _frames_checked, _idle_pulses, _reference_signature

    owner = cont.owner
    if _finished:
        return

    if _registered_scene is None:
        owner["multi_camera_stereo_done"] = False
        owner["multi_camera_stereo_failed"] = False
        owner["multi_camera_stereo_frames"] = 0

        scenes = bge.logic.getSceneList()
        scene = bge.logic.getCurrentScene()
        if len(scenes) != 1:
            _finish(owner, False, ["o teste exige exatamente uma cena ativa"])
            return
        if scene.active_camera is None:
            _finish(owner, False, ["a cena de teste nao possui camera ativa"])
            return

        _register(scene)
        print("[multi_camera_stereo_regression] iniciado", flush=True)
        return

    if not _events:
        _idle_pulses += 1
        if _idle_pulses >= MAX_IDLE_PULSES:
            _finish(
                owner,
                False,
                ["nenhum callback recebido em " + str(MAX_IDLE_PULSES) +
                 " pulsos; confirme camera ativa e render habilitado"]
            )
        return

    _idle_pulses = 0
    events = list(_events)
    del _events[:]

    scene = bge.logic.getCurrentScene()
    valid_camera_names = _valid_camera_names(scene)

    frames, incomplete = _split_frames(events)
    if incomplete:
        _finish(owner, False, ["grupo incompleto sem post_draw: " + str(incomplete)])
        return

    errors = []
    for offset, frame in enumerate(frames):
        frame_number = _frames_checked + len(_signature_buffer) + offset + 1
        frame_errors, signature = _validate_frame(frame, frame_number, valid_camera_names)
        errors.extend(frame_errors)
        if frame_errors:
            continue
        if not signature:
            errors.append("frame " + str(frame_number) + ": nenhuma camera renderizada")
            continue
        _signature_buffer.append(signature)

    if errors:
        _finish(owner, False, errors)
        return

    for logical_signature, logical_errors in _drain_logical_frames():
        if logical_errors:
            errors.extend(logical_errors)
            continue

        _frames_checked += 1
        if _reference_signature is None:
            _reference_signature = logical_signature
        elif logical_signature != _reference_signature:
            errors.append(
                "frame " + str(_frames_checked) + ": assinatura camera/olho mudou de " +
                str(_reference_signature) + " para " + str(logical_signature)
            )

    if errors:
        _finish(owner, False, errors)
        return

    owner["multi_camera_stereo_frames"] = _frames_checked
    if _frames_checked >= TARGET_FRAMES:
        _finish(owner, True, [])
