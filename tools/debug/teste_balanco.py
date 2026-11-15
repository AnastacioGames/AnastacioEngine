# Teste fora do jogo de scripts/modules/anastacio_balanco.py (peças que balançam no carro).
# Precisa de mathutils: rode com o Python do editor
#   AnastacioEngine.exe -b --python tools/debug/teste_balanco.py
# ou com um Python que tenha `pip install mathutils`.
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "source", "release", "scripts", "modules"))

from mathutils import Matrix, Vector  # noqa: E402

import anastacio_balanco as ab  # noqa: E402

DT = 1.0 / 60.0
BAIXO = Vector((0, 0, -1))
falhas = []


def confere(nome, ok, detalhe=""):
    print(("ok    " if ok else "FALHA ") + nome + ("  " + detalhe if detalhe else ""))
    if not ok:
        falhas.append(nome)


def graus(a, b):
    return math.degrees(a.angle(b, 0.0))


def rodar(sim, segundos, posicao, repouso=BAIXO, dobra=None, t0=0.0):
    """posicao(t) -> Vector do pivô. Devolve a última direção e o maior ângulo visto."""
    d, maior = None, 0.0
    for i in range(int(segundos / DT)):
        d = sim.passo(DT, posicao(t0 + i * DT), repouso, dobra)
        maior = max(maior, graus(repouso, d))
    return d, maior


# 1. Parado: fica na pose do editor.
s = ab.Balanco()
d, maior = rodar(s, 3, lambda t: Vector((0, 0, 0)))
confere("parado fica em repouso", maior < 0.01, "%.3f graus" % maior)

# 2. Arrancada constante de 4 m/s² em +Y: soro vai para trás (-Y), assenta perto de atan(4/9.81).
s = ab.Balanco(limite_graus=80)
d, _ = rodar(s, 8, lambda t: Vector((0, 2.0 * t * t, 0)))
esperado = math.degrees(math.atan2(4.0, 9.81))
confere("arrancada joga o soro para trás", d.y < 0, "dir %s" % (tuple(round(c, 3) for c in d),))
confere("ângulo da arrancada ~ atan(a/g)", abs(graus(BAIXO, d) - esperado) < 3.0,
        "%.1f x %.1f" % (graus(BAIXO, d), esperado))

# 3. Velocidade constante depois da arrancada: volta para baixo (não fica arrastado).
s = ab.Balanco()
rodar(s, 2, lambda t: Vector((0, 2.0 * t * t, 0)))
d, _ = rodar(s, 10, lambda t: Vector((0, 8.0 + 8.0 * (t - 2.0), 0)), t0=2.0)
confere("velocidade constante volta ao repouso", graus(BAIXO, d) < 2.0, "%.2f graus" % graus(BAIXO, d))

# 4. Freada: depois de andar a 10 m/s, para de uma vez em 0,5 s: soro vai para a frente.
s = ab.Balanco(limite_graus=80)
rodar(s, 3, lambda t: Vector((0, 10.0 * t, 0)))
d, _ = rodar(s, 0.3, lambda t: Vector((0, 30 + 10 * (t - 3) - 10 * (t - 3) ** 2, 0)), t0=3.0)
confere("freada joga o soro para a frente", d.y > 0.1, "y=%.3f" % d.y)

# 5. Dobradiça em X: curva lateral (aceleração em X) não mexe; arrancada em Y mexe só no plano YZ.
aba = Vector((0, 0, 1))            # aba em pé, dobra no eixo X
s = ab.Balanco(gravidade=0.3, mola=2.5, amortecimento=3.0, limite_graus=35)
d, maior = rodar(s, 3, lambda t: Vector((1.5 * t * t, 0, 0)), repouso=aba, dobra=Vector((1, 0, 0)))
confere("dobradiça X ignora movimento em X", abs(d.x) < 1e-6 and maior < 0.5, "x=%.2e max %.2f" % (d.x, maior))
s = ab.Balanco(gravidade=0.3, mola=2.5, amortecimento=3.0, limite_graus=35, vento=0.4)
d, maior = rodar(s, 3, lambda t: Vector((0, 3.0 * t * t, 0)), repouso=aba, dobra=Vector((1, 0, 0)))
confere("dobradiça X: aba deita para trás com vento", d.y < 0 and abs(d.x) < 1e-6, "y=%.3f" % d.y)
confere("limite de 35 graus respeitado", maior <= 35.0 + 1e-3, "%.2f" % maior)

# 6. Vento tremula em velocidade constante (vai e volta, sem parar).
s = ab.Balanco(gravidade=0.3, mola=2.5, amortecimento=3.0, limite_graus=35, vento=0.4)
rodar(s, 2, lambda t: Vector((0, 15.0 * t, 0)), repouso=aba, dobra=Vector((1, 0, 0)))
angs = []
for i in range(120):
    t = 2 + i * DT
    angs.append(graus(aba, s.passo(DT, Vector((0, 15.0 * t, 0)), aba, Vector((1, 0, 0)))))
confere("vento faz a aba tremular", max(angs) - min(angs) > 0.5, "%.2f..%.2f" % (min(angs), max(angs)))

# 7. Teleporte (respawn): recomeça em repouso sem dar chicotada.
s = ab.Balanco()
rodar(s, 1, lambda t: Vector((0, 3.0 * t * t, 0)))
d = s.passo(DT, Vector((100, 100, 0)), BAIXO)
confere("respawn recomeça parado", graus(BAIXO, d) < 1e-6)

# 8. Carro inclinado (rampa de 20°) com o soro livre: continua apontando para o chão do mundo.
rot = Matrix.Rotation(math.radians(20), 3, 'X')
rep = ab._mv(rot, BAIXO)
s = ab.Balanco(mola=0.0, limite_graus=60)
d, _ = rodar(s, 8, lambda t: Vector((0, 0, 0)), repouso=rep)
confere("soro livre fica a prumo na rampa", graus(BAIXO, d) < 1.5, "%.2f graus do prumo" % graus(BAIXO, d))


# 9. Componente com objeto falso: a orientação local gira em volta da origem.
class Obj:
    def __init__(self, pai):
        self.name = "Soro"
        self.parent = pai
        self.localOrientation = Matrix.Identity(3)
        self.worldPosition = Vector((0, 0, 1))
        self.scene = type("S", (), {"active_camera": None})()
        self.escritas = 0

    def __setattr__(self, k, v):
        if k == "localOrientation" and "escritas" in self.__dict__:
            self.__dict__["escritas"] += 1
        object.__setattr__(self, k, v)


pai = type("P", (), {"worldOrientation": Matrix.Identity(3)})()
ab.Range = type("R", (), {"logic": type("L", (), {"getLogicTicRate": staticmethod(lambda: 60.0)})})
comp = ab.PecaBalanco()
comp.object = Obj(pai)
comp.start({k: v for k, v in ab.PecaBalanco.args.items()})
for i in range(120):
    comp.update()
confere("componente parado não reescreve orientação", comp.object.escritas == 0, "%d" % comp.object.escritas)
for i in range(240):
    t = i * DT
    comp.object.worldPosition = Vector((0, 2.0 * t * t, 1))
    comp.update()
ponta = ab._mv(comp.object.localOrientation, Vector((0, 0, -1)))
confere("componente inclina a peça na arrancada", ponta.y < -0.2, "ponta %s" % (tuple(round(c, 3) for c in ponta),))

print("\n%s: %d falha(s)" % ("PASSOU" if not falhas else "FALHOU", len(falhas)))
sys.exit(1 if falhas else 0)
