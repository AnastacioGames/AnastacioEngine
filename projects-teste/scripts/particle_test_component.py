"""
Componente de teste do sistema de particulas GPU (Fases D-I.2) - AnastacioEngine.

Uso: adicione este componente ao PROPRIO objeto emissor (Fase I.2 tornou o
emissor por-objeto -- ligue "Use GPU Particles" no painel Particle do objeto).
Os campos ficam editaveis no painel de componentes do editor (args, com
cabecalhos/icones) e sao aplicados uma vez em update() sobre own.particles.

own.particles so deixa de ser None se o objeto tiver use_gpu_particles ligado
no DNA (painel Particle) -- o emissor e criado na conversao da cena, nao lazy
como na Fase B-H, mas os args ainda so sao aplicados no primeiro update() em
que ele deixar de ser None, pra tratar o caso do componente estar num objeto
sem a flag ligada.

"Emitter Position" agora e um offset local (soma a posicao mundial do objeto
a cada frame), nao mais uma posicao absoluta.
"""

import Range
from collections import OrderedDict
from mathutils import Color, Vector


class ParticleTestComponent(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("C_Icons", "PARTICLES"),

        ("C_Header /Emissor/PARTICLES", True),
        ("Emitter Position", Vector((0.0, 0.0, 0.0))),
        ("Emitter Radius", 1.0),
        ("Emission Direction", Vector((0.0, 0.0, 1.0))),
        ("Emission Angle", 180.0),

        ("C_Header /Fisica/PHYSICS", True),
        ("Gravity", Vector((0.0, 0.0, -9.8))),
        ("Lifetime", 3.0),
        ("Velocity", Vector((0.0, 0.0, 4.0))),
        ("Velocity Randomness", 2.0),
        ("Particle Count", 200),

        ("C_Header /Aparencia/COLOR", True),
        ("Size", 0.35),
        ("Color", Color((1.0, 0.2, 0.8, 1.0))),

        ("C_Header /Textura (caminho .png)/FILE_IMAGE", True),
        ("Texture Path", ""),

        ("C_Header /Gradiente (Fase G)/IPO_EASE_IN_OUT", True),
        ("End Size", 0.35),
        ("End Color", Color((1.0, 0.2, 0.8, 1.0))),
    ])

    def start(self, args):
        self._args = args
        self._applied = False

    def update(self):
        if self._applied:
            return

        particles = self.object.particles
        if particles is None:
            # Objeto sem "Use GPU Particles" ligado no painel Particle --
            # nao ha emissor pra configurar.
            return

        args = self._args
        particles.emitterPosition = args["Emitter Position"]
        particles.emitterRadius = args["Emitter Radius"]
        particles.emissionDirection = args["Emission Direction"]
        particles.emissionAngle = args["Emission Angle"]

        particles.gravity = args["Gravity"]
        particles.lifetime = args["Lifetime"]
        particles.velocity = args["Velocity"]
        particles.velocityRandomness = args["Velocity Randomness"]

        particle_count = args["Particle Count"]
        if particle_count and particle_count != particles.particleCount:
            particles.particleCount = int(particle_count)

        particles.size = args["Size"]
        particles.color = list(args["Color"])

        if args["Texture Path"]:
            particles.texture = args["Texture Path"]

        particles.endSize = args["End Size"]
        particles.endColor = list(args["End Color"])

        self._applied = True
        print("ParticleTestComponent: parametros aplicados a %s.particles (particleCount=%d)" % (self.object.name, particles.particleCount))


# Compatibilidade com o nome antigo usado por cenas ou dados salvos.
ParticleTestComp = ParticleTestComponent
