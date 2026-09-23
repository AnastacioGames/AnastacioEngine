"""Regression test for scene drawing callbacks (Ketsji Plan 3).

Attach an Always sensor (pulse enabled) to a Python controller in Module mode:
    drawing_callbacks_regression.main

Use a controlled file with exactly one running scene, one camera and stereo
disabled.  Multiple cameras/viewports and stereo have a separate Plan 3 test.
Do not suspend, replace or end the test scene while this script is running.

The script appends its own callbacks without replacing callbacks already
registered by the game.  It checks five exact setup -> pre -> post groups,
prints PASS/FAIL in the console, then removes only the callback occurrences it
added.  Setup and pre-draw must receive the active camera; post-draw must
receive no argument.
"""

import Range as bge


TARGET_BATCHES = 5
MAX_IDLE_PULSES = 600

_events = []
_registered_scene = None
_expected_camera_name = None
_batches_checked = 0
_finished = False
_idle_pulses = 0


def _camera_name(camera):
    # Stereo cameras can be temporary.  Copy only the name while the callback
    # is running; never retain the proxy past this call.
    return None if camera is None else camera.name


def _camera_event(kind, camera, eye):
    # Compare identity while the proxy is valid, then retain only plain data.
    scene = bge.logic.getCurrentScene()
    is_active_camera = camera is not None and camera is scene.active_camera
    return (kind, _camera_name(camera), eye, is_active_camera, None)


def _on_pre_draw_setup(camera):
    _events.append(_camera_event("setup", camera, None))


def _on_pre_draw(camera):
    _events.append(_camera_event("pre", camera, bge.render.getStereoEye()))


def _on_post_draw(*args):
    # *args makes the dispatcher deliver every argument it offers.  Recording
    # the count detects a future accidental camera argument instead of letting
    # its arity adaptation hide the contract change.
    _events.append(("post", None, None, None, len(args)))


def _register(scene):
    global _registered_scene, _expected_camera_name

    scene.pre_draw_setup.append(_on_pre_draw_setup)
    scene.pre_draw.append(_on_pre_draw)
    scene.post_draw.append(_on_post_draw)
    _registered_scene = scene
    _expected_camera_name = scene.active_camera.name


def _remove_added_callback(callbacks, callback):
    # We append one occurrence.  Remove that occurrence from the end without
    # touching an identical registration that may predate this test.
    for index in range(len(callbacks) - 1, -1, -1):
        if callbacks[index] is callback:
            del callbacks[index]
            return


def _unregister():
    global _registered_scene, _expected_camera_name

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
        _expected_camera_name = None

    return None


def _split_groups(events):
    """Split complete single-scene/mono groups at each post-draw."""
    batches = []
    current = []

    for event in events:
        current.append(event)
        if event[0] == "post":
            batches.append(current)
            current = []

    return batches, current


def _validate_batch(batch, batch_number):
    errors = []
    phases = [event[0] for event in batch]
    if phases != ["setup", "pre", "post"]:
        errors.append("ordem esperada setup/pre/post, observada " + str(phases))
    else:
        setup_camera = batch[0][1]
        pre_camera = batch[1][1]
        pre_eye = batch[1][2]
        setup_is_active = batch[0][3]
        pre_is_active = batch[1][3]
        post_arg_count = batch[2][4]
        if setup_camera is None:
            errors.append("pre_draw_setup nao recebeu uma camera valida")
        if pre_camera is None:
            errors.append("pre_draw nao recebeu uma camera valida")
        if setup_camera != pre_camera:
            errors.append(
                "camera divergente: setup=" + str(setup_camera) +
                " pre=" + str(pre_camera)
            )
        if setup_camera != _expected_camera_name:
            errors.append(
                "camera esperada " + str(_expected_camera_name) +
                ", recebida " + str(setup_camera)
            )
        if not setup_is_active:
            errors.append("pre_draw_setup nao recebeu o objeto da camera ativa")
        if not pre_is_active:
            errors.append("pre_draw nao recebeu o objeto da camera ativa")
        if pre_eye != bge.render.LEFT_EYE:
            errors.append("estereo deve estar desabilitado; olho recebido=" + str(pre_eye))
        if post_arg_count != 0:
            errors.append("post_draw recebeu " + str(post_arg_count) + " argumento(s)")

    if errors:
        prefix = "batch " + str(batch_number) + ": "
        return [prefix + error for error in errors]

    return []


def _finish(owner, passed, messages):
    global _finished

    messages = list(messages)
    cleanup_error = _unregister()
    if cleanup_error is not None:
        passed = False
        messages.append("falha ao remover callbacks: " + cleanup_error)

    _finished = True
    owner["draw_callbacks_done"] = True
    owner["draw_callbacks_failed"] = not passed
    owner["draw_callbacks_batches"] = _batches_checked

    if passed:
        print(
            "[drawing_callbacks_regression] PASS: " +
            str(_batches_checked) + " grupos de callbacks validados",
            flush=True
        )
    else:
        for message in messages:
            print("[drawing_callbacks_regression] detalhe: " + message, flush=True)
        print("[drawing_callbacks_regression] FAIL", flush=True)


def main(cont):
    global _batches_checked, _idle_pulses

    owner = cont.owner
    if _finished:
        return

    if _registered_scene is None:
        owner["draw_callbacks_done"] = False
        owner["draw_callbacks_failed"] = False
        owner["draw_callbacks_batches"] = 0

        scenes = bge.logic.getSceneList()
        scene = bge.logic.getCurrentScene()
        if len(scenes) != 1:
            _finish(owner, False, ["o teste exige exatamente uma cena ativa"])
            return
        if scene.active_camera is None:
            _finish(owner, False, ["a cena de teste nao possui camera ativa"])
            return
        if len(scene.cameras) != 1:
            _finish(owner, False, ["o teste exige exatamente uma camera na cena"])
            return

        _register(scene)
        print("[drawing_callbacks_regression] iniciado", flush=True)
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

    errors = []
    batches, incomplete = _split_groups(events)
    if incomplete:
        errors.append("grupo incompleto sem post_draw: " + str(incomplete))

    for offset, batch in enumerate(batches):
        batch_number = _batches_checked + offset + 1
        errors.extend(_validate_batch(batch, batch_number))

    if errors:
        _finish(owner, False, errors)
        return

    _batches_checked += len(batches)
    owner["draw_callbacks_batches"] = _batches_checked
    if _batches_checked >= TARGET_BATCHES:
        _finish(owner, True, [])
