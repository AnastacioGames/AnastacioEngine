# -*- coding: utf-8 -*-
"""Peça que balança com o movimento do objeto pai (Smart Component).

Uso: separe a peça do carro (aba da caixa de papelão, bolsa de soro, antena,
pingente...), ponha a ORIGEM dela no ponto onde ela fica presa (dobradiça da
aba, gancho do soro), faça dela filha do chassi (Ctrl+P, Keep Transform),
física "No Collision" e adicione o componente ``anastacio_balanco.PecaBalanco``.

A ponta da peça é simulada como uma massa presa ao pivô por uma haste de
"Comprimento" metros: ela sente gravidade, a aceleração do carro (arranque,
freada, curva, pulo), uma mola que puxa de volta para a pose do editor,
amortecimento e, opcionalmente, vento proporcional à velocidade. A peça só
gira em volta da origem, nunca sai do lugar.

Valores sugeridos:

==================  =====  =========  =====  ====  =====  ======  =====
Peça                Eixo   Dobradiça  Grav.  Mola  Amort  Limite  Vento
==================  =====  =========  =====  ====  =====  ======  =====
Bolsa de soro       -Z     Livre      1.0    0.3   1.5    50      0.0
Aba de papelão      (*)    (**)       0.3    2.5   3.0    35      0.4
Antena / mola       Z      Livre      0.0    3.0   1.0    25      0.2
==================  =====  =========  =====  ====  =====  ======  =====

(*) eixo local que vai da dobra para a ponta da aba.
(**) eixo local da linha da dobra.

O cálculo fica em ``Balanco`` (Python puro + mathutils), testado fora do jogo
por ``tools/debug/teste_balanco.py``.
"""

from collections import OrderedDict
import math

from mathutils import Matrix, Quaternion, Vector

try:
    import Range
    from Range.args import Bool, Choice, Float
    _Base = Range.types.KX_PythonComponent
except ImportError:  # teste fora do jogo
    Range = None
    _Base = object

    def Float(value, **_):
        return float(value)

    def Bool(value, **_):
        return bool(value)

    def Choice(default, *_items, **_):
        return default


EIXOS = {"X": (1, 0, 0), "-X": (-1, 0, 0), "Y": (0, 1, 0), "-Y": (0, -1, 0),
         "Z": (0, 0, 1), "-Z": (0, 0, -1)}
GRAVIDADE = 9.81
ACEL_MAX = 80.0      # m/s²: corta picos de quadro (colisão, passo de física irregular)
TELEPORTE = 5.0      # m num quadro: respawn/reposicionamento, recomeça parado


# Produtos escritos à mão: Matrix * Vector é `*` no 2.79 e `@` no mathutils novo.
def _mv(m, v):
    return Vector((m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
                   m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
                   m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2]))


def _mm(a, b):
    return Matrix([[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)])


class Balanco:
    """Massa na ponta de uma haste presa no pivô, num referencial que acompanha o pivô.

    ``offset`` é a ponta menos o pivô, em eixos do mundo. A aceleração do pivô entra
    como força fictícia (-a * inercia), então velocidade constante não deixa a peça
    arrastada para trás; só arranque, freada, curva e pulo mexem nela."""

    def __init__(self, comprimento=0.3, gravidade=1.0, mola=0.3, amortecimento=1.5,
                 inercia=1.0, limite_graus=50.0, vento=0.0, fase=0.0):
        self.comprimento = max(0.01, comprimento)
        self.gravidade = gravidade
        self.mola = max(0.0, mola)
        self.amortecimento = max(0.0, amortecimento)
        self.inercia = inercia
        self.limite = math.radians(max(0.0, min(180.0, limite_graus)))
        self.vento = max(0.0, vento)
        self.fase = fase
        self.tempo = 0.0
        self.offset = None

    def reiniciar(self, pivo, repouso):
        self.offset = repouso * self.comprimento
        self.offset_ant = self.offset.copy()
        self.pivo_ant = pivo.copy()
        self.vel_pivo = Vector((0.0, 0.0, 0.0))
        self.acel_pivo = Vector((0.0, 0.0, 0.0))

    def passo(self, dt, pivo, repouso, dobradica=None):
        """Avança ``dt`` segundos. ``repouso``: direção pivô->ponta da pose do editor (mundo,
        unitária). ``dobradica``: eixo do mundo em que a peça gira, ou None (livre).
        Devolve a direção atual pivô->ponta (mundo, unitária)."""
        if self.offset is None or (pivo - self.pivo_ant).length > TELEPORTE:
            self.reiniciar(pivo, repouso)
            return repouso.copy()
        dt = max(1e-4, min(dt, 0.1))
        self.tempo += dt
        L = self.comprimento

        vel = (pivo - self.pivo_ant) / dt
        acel = (vel - self.vel_pivo) / dt
        if acel.length > ACEL_MAX:
            acel = acel.normalized() * ACEL_MAX
        # Média curta: a física entrega a posição em degraus, a derivada dupla tem ruído.
        self.acel_pivo = self.acel_pivo.lerp(acel, 0.5)
        self.vel_pivo = vel
        self.pivo_ant = pivo.copy()

        w = 2.0 * math.pi * self.mola
        forca = (repouso * L - self.offset) * (w * w)
        forca.z -= GRAVIDADE * self.gravidade
        forca -= self.acel_pivo * self.inercia
        rapidez = vel.length
        if self.vento > 0.0 and rapidez > 0.1:
            # Ar contra o movimento empurra a peça para trás; o tremor cresce com a velocidade.
            forca -= vel * (self.vento * 2.0)
            lado = dobradica.cross(repouso) if dobradica is not None else repouso.cross(vel)
            if lado.length > 1e-6:
                t = self.tempo + self.fase
                tremor = math.sin(t * 23.0) * 0.6 + math.sin(t * 37.0 + 1.3) * 0.4
                forca += lado.normalized() * (tremor * self.vento * rapidez * 1.5)

        # Verlet com amortecimento só no movimento relativo ao pivô.
        mov = (self.offset - self.offset_ant) * max(0.0, 1.0 - self.amortecimento * dt)
        novo = self.offset + mov + forca * (dt * dt)

        if dobradica is not None:
            novo -= dobradica * novo.dot(dobradica)
        if novo.length < 1e-6:
            novo = repouso * L
        direcao = novo.normalized()

        bateu = repouso.angle(direcao, 0.0) > self.limite
        if bateu:
            eixo = repouso.cross(direcao)
            if eixo.length < 1e-6:
                eixo = dobradica if dobradica is not None else repouso.orthogonal()
            direcao = _mv(Quaternion(eixo.normalized(), self.limite).to_matrix(), repouso)
        novo = direcao * L
        # Bateu no limite: perde a velocidade em vez de quicar.
        self.offset_ant = novo if bateu else self.offset
        self.offset = novo
        return direcao


class PecaBalanco(_Base):
    args = OrderedDict([
        ("Eixo da Peca", Choice("-Z", "-Z", "Z", "-X", "X", "-Y", "Y",
                                tip="Eixo local que vai da origem (onde está presa) até a ponta da peça. Soro pendurado: -Z")),
        ("Dobradica", Choice("Livre", "Livre", "X", "Y", "Z",
                             tip="Livre balança para todo lado (soro). X/Y/Z gira só em volta desse eixo local (aba, porta)")),
        ("Comprimento", Float(0.3, min=0.01, max=5.0, tip="Distância em metros da origem até o meio do peso da peça")),
        ("Gravidade", Float(1.0, min=0.0, max=3.0, tip="Quanto a gravidade puxa. 1 = pendurada; 0 = só mola (aba dura, antena)")),
        ("Mola", Float(0.3, min=0.0, max=20.0, tip="Força que volta para a pose do editor (oscilações por segundo). 0 = solta")),
        ("Amortecimento", Float(1.5, min=0.0, max=30.0, tip="Quanto o balanço perde por segundo. Maior = para mais rápido")),
        ("Inercia", Float(1.0, min=0.0, max=5.0, tip="Quanto arranque, freada, curva e pulo do carro mexem a peça")),
        ("Limite", Float(50.0, min=0.0, max=180.0, tip="Ângulo máximo em graus a partir da pose do editor")),
        ("Vento", Float(0.0, min=0.0, max=3.0, tip="Ar com a velocidade: empurra para trás e faz tremular (abas de papelão)")),
        ("Distancia Maxima", Float(40.0, min=0.0, tip="Longe da câmera a peça para de simular (metros). 0 = sempre")),
    ])

    def start(self, args):
        obj = self.object
        self.eixo = Vector(EIXOS.get(str(args.get("Eixo da Peca", "-Z")), (0, 0, -1)))
        d = str(args.get("Dobradica", "Livre"))
        self.dobradica = Vector(EIXOS[d]) if d in EIXOS else None
        self.distancia = float(args.get("Distancia Maxima", 40.0))
        self.repouso_local = obj.localOrientation.copy()
        # Fase pelo nome: carros iguais lado a lado não tremulam em sincronia.
        fase = (sum(ord(c) for c in obj.name) % 97) * 0.37
        self.sim = Balanco(float(args.get("Comprimento", 0.3)), float(args.get("Gravidade", 1.0)),
                           float(args.get("Mola", 0.3)), float(args.get("Amortecimento", 1.5)),
                           float(args.get("Inercia", 1.0)), float(args.get("Limite", 50.0)),
                           float(args.get("Vento", 0.0)), fase)
        self.escrito = _mv(self.repouso_local, self.eixo)   # a pose do editor já está escrita

    def _rot_pai(self):
        pai = self.object.parent
        return pai.worldOrientation.normalized() if pai is not None else Matrix.Identity(3)

    def update(self):
        obj = self.object
        if self.distancia > 0.0:
            cam = obj.scene.active_camera
            if cam is not None and obj.getDistanceTo(cam) > self.distancia:
                self.sim.offset = None   # volta do repouso quando chegar perto
                return
        rot_pai = self._rot_pai()
        rep_pai = _mv(self.repouso_local, self.eixo)
        repouso = _mv(rot_pai, rep_pai).normalized()
        dobra = None
        if self.dobradica is not None:
            dobra = _mv(rot_pai, _mv(self.repouso_local, self.dobradica)).normalized()
        dt = 1.0 / Range.logic.getLogicTicRate()
        direcao = self.sim.passo(dt, obj.worldPosition.copy(), repouso, dobra)

        dir_pai = _mv(rot_pai.transposed(), direcao)
        # Parada: não reescreve a orientação (evita marcar o objeto como mudado todo quadro).
        if (dir_pai - self.escrito).length < 1e-4:
            return
        self.escrito = dir_pai
        giro = rep_pai.rotation_difference(dir_pai).to_matrix()
        obj.localOrientation = _mm(giro, self.repouso_local)
