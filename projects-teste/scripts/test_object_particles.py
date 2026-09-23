"""
Teste rapido da API object.particles (Fase I.2) - AnastacioEngine.

Uso: Python Controller em modo "Script", ligado a um sensor Always (frequencia
1 ou mais), no objeto que tem "Use GPU Particles" ligado no painel Particle.
Roda uma vez (imprime status e confirma leitura/escrita), depois so fica
girando a cor pra deixar visualmente obvio que esta vivo.
"""

import Range

cont = Range.logic.getCurrentController()
own = cont.owner

particles = own.particles

if particles is None:
    print("[test_object_particles] %s.particles == None -- 'Use GPU Particles' esta desligado no painel Particle deste objeto?" % own.name)
else:
    if "particles_tested" not in own:
        own["particles_tested"] = False

    if not own["particles_tested"]:
        print("[test_object_particles] OK -- %s.particles existe." % own.name)
        print("  particleCount =", particles.particleCount)
        print("  lifetime =", particles.lifetime)
        print("  emitterPosition (offset local) =", list(particles.emitterPosition))
        print("  gravity =", list(particles.gravity))
        print("  color =", list(particles.color))

        # Testa escrita: dobra o tamanho da partícula e confirma que voltou o novo valor.
        old_size = particles.size
        particles.size = old_size * 2.0
        print("  size: %.3f -> %.3f (escrita OK: %s)" % (old_size, particles.size, particles.size == old_size * 2.0))

        own["particles_tested"] = True

    # Roda todo frame: varia a cor pra confirmar visualmente que o objeto certo esta emitindo.
    import math
    t = Range.logic.getFrameTime()
    particles.color = [
        0.5 + 0.5 * math.sin(t * 2.0),
        0.5 + 0.5 * math.sin(t * 2.0 + 2.094),
        0.5 + 0.5 * math.sin(t * 2.0 + 4.189),
        1.0,
    ]
