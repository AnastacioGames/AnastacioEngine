"""Regression test for the GPU particle system Python API (Ketsji Plan 3).

Attach an Always sensor (pulse enabled) to a Python controller in Module mode:
    particle_system_regression.main

The controller's owner must have "Use GPU Particles" enabled so that
KX_GameObject.particles returns a live KX_ParticleSystem proxy instead of
None. Complements the drawing/camera regression tests: this one exercises the
particle system's Python attributes directly (KX_ParticleSystem.cpp) rather
than the render loop, since particle rendering itself fires no Python
callback (unlike scene.pre_draw/post_draw).

The script does not assume a specific emission rate or particle lifetime --
those are scene/file setup and vary per system. It only checks contract
properties that must hold regardless of tuning:

- ``particles.particleCount`` is always a non-negative integer;
- ``particles.enabled`` reads back exactly what was last written to it;
- once disabled, no new particles are spawned, so particleCount can only stay
  the same or fall (existing particles finishing their lifetime), never rise,
  until re-enabled.

Does not modify emitter/appearance parameters (gravity, lifetime, velocity,
etc.); those have their own dedicated tuning UI and are out of scope here.
"""

import Range as bge


TARGET_SAMPLES = 30
DISABLE_AT_SAMPLE = 15
ENABLE_AT_SAMPLE = 25

_finished = False
_sample_count = 0
_max_seen_while_disabled = None


def _finish(owner, passed, messages):
    global _finished

    _finished = True
    owner["particle_system_done"] = True
    owner["particle_system_failed"] = not passed
    owner["particle_system_samples"] = _sample_count

    if passed:
        print(
            "[particle_system_regression] PASS: " +
            str(_sample_count) + " amostras validadas",
            flush=True
        )
    else:
        for message in messages:
            print("[particle_system_regression] detalhe: " + message, flush=True)
        print("[particle_system_regression] FAIL", flush=True)


def main(cont):
    global _sample_count, _max_seen_while_disabled

    owner = cont.owner
    if _finished:
        return

    if _sample_count == 0:
        owner["particle_system_done"] = False
        owner["particle_system_failed"] = False
        owner["particle_system_samples"] = 0

        particles = owner.particles
        if particles is None:
            _finish(
                owner, False,
                ["o objeto do controlador precisa ter 'Use GPU Particles' habilitado"]
            )
            return
        if not particles.enabled:
            _finish(
                owner, False,
                ["o sistema de particulas deve comecar habilitado (enabled == True)"]
            )
            return

    particles = owner.particles
    if particles is None:
        _finish(owner, False, ["particles ficou None durante o teste"])
        return

    errors = []

    count = particles.particleCount
    if not isinstance(count, int) or count < 0:
        errors.append(
            "amostra " + str(_sample_count + 1) +
            ": particleCount invalido: " + repr(count)
        )

    if _sample_count == DISABLE_AT_SAMPLE:
        particles.enabled = False
        if particles.enabled is not False:
            errors.append("enabled nao retornou False logo apos ser desabilitado")
        _max_seen_while_disabled = count
    elif DISABLE_AT_SAMPLE < _sample_count < ENABLE_AT_SAMPLE:
        if not errors and particles.enabled:
            errors.append(
                "amostra " + str(_sample_count + 1) +
                ": enabled voltou a True sem reativacao explicita"
            )
        if not errors and _max_seen_while_disabled is not None and count > _max_seen_while_disabled:
            errors.append(
                "amostra " + str(_sample_count + 1) +
                ": particleCount subiu de " + str(_max_seen_while_disabled) +
                " para " + str(count) + " com o sistema desabilitado"
            )
        if not errors:
            _max_seen_while_disabled = min(_max_seen_while_disabled, count)
    elif _sample_count == ENABLE_AT_SAMPLE:
        particles.enabled = True
        if particles.enabled is not True:
            errors.append("enabled nao retornou True logo apos ser reabilitado")

    if errors:
        _finish(owner, False, errors)
        return

    _sample_count += 1
    owner["particle_system_samples"] = _sample_count
    if _sample_count >= TARGET_SAMPLES:
        _finish(owner, True, [])
