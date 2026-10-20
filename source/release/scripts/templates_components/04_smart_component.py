"""Smart Component: o jeito novo de fazer um componente.

Um componente comum só tem "args" e o código do jogo. O Smart Component é o
mesmo componente com dois recursos novos, todos opcionais:

1. Campos melhores (Range.args): slider com limite, dica ao passar o mouse,
   seções, lista em ordem, e escolher um objeto ou uma cena com o mouse.
2. Uma classe "Editor" que roda só no editor (o jogo ignora): arruma o objeto
   ao adicionar, mostra avisos nos campos, cria botões na caixa do componente
   e desenha guias na viewport (raio, linha até o alvo).

Nada muda no jogo: args["Velocidade"] continua sendo um float, e o jogo
exportado roda sem bpy. Os componentes antigos continuam funcionando igual.

Como usar:
1. Renomeie este texto para "perseguidor.py" (o nome vira o módulo) ou salve
   o arquivo com esse nome ao lado do .blend.
2. Crie uma esfera chamada "Jogador" (o on_attach a escolhe sozinho como alvo).
3. Selecione outro objeto e, em Game Components > Add, digite
   perseguidor.Perseguidor
4. Passe o mouse nos campos (dicas), mude a Velocidade para mais de 15
   (aviso) e use os botões no fim da caixa. Depois dê Play: ele persegue o alvo.
   (O pisca-pisca usa a cor do objeto: ligue Object Color no material.)

Campos de Range.args (no jogo cada um chega como o tipo normal):
    Float(2.0, min=0, max=20, tip="...")   -> float (slider se tiver min e max)
    Int(3, min=1, max=10, tip="...")       -> int
    Bool(True, tip="...")                  -> bool
    Text("Oi", tip="...")                  -> str
    Choice("Andar", "Andar", "Correr")     -> str (o 1º é o padrão, depois as opções)
    Object(tip="...")                      -> KX_GameObject, ou None
    Scene(tip="...")                       -> str com o nome da cena ("" se vazio)
    Header("Seção", icon="AUTO", open=True) -> título que abre e fecha
"""

from collections import OrderedDict
import math

from mathutils import Vector
from Range import types, logic
from Range.args import Float, Int, Bool, Text, Choice, Object, Scene, Header


class Perseguidor(types.KX_PythonComponent):
    args = OrderedDict([
        Header("Alvo", icon="OBJECT_DATA"),
        ("Alvo", Object(tip="Objeto que ele persegue. Clique e escolha na lista")),
        ("Distancia de parada", Float(1.5, min=0, max=10, tip="Para quando chega a essa distância do alvo")),

        Header("Movimento", icon="AUTO"),
        ("Velocidade", Float(3.0, min=0, max=20, tip="Metros por segundo. Tente digitar 50: fica em 20")),
        ("Modo", Choice("Andar", "Andar", "Correr", "Pular", tip="Andar: normal. Correr: 2x. Pular: dá saltos")),
        ("Altura do pulo", Float(0.8, min=0, max=3, tip="Só vale no modo Pular")),
        ("Olhar para o alvo", Bool(True, tip="Gira o corpo na direção do alvo")),

        Header("Alerta", icon="COLOR", open=False),
        ("Agressivo", Bool(True, tip="Pisca e cresce quando está perto")),
        ("Piscadas por segundo", Int(4, min=1, max=12, tip="Velocidade do pisca-pisca")),
        ("Cor de alerta", [1.0, 0.1, 0.1, 1.0]),    # jeito antigo: também vale, sem dica
        ("Nome", Text("Inimigo", tip="Aparece no console quando ele te pega")),
        ("Cena ao pegar", Scene(tip="Cena que aparece por cima quando ele te pega (opcional)")),
    ])

    # Ao adicionar o componente, o editor já deixa o objeto assim.
    # Também dá para pedir outros componentes: "components": ["vida.Vida"]
    requires = {"physics": "NO_COLLISION"}

    # ------------------------------------------------------------------
    # Lado de editor. O jogo nunca roda esta classe.
    # Aqui dentro pode usar bpy, mas importe só dentro dos métodos.
    # self.object = o objeto, self.args["Campo"] lê e grava os campos.
    class Editor:
        # Botões no fim da caixa do componente: (texto, método, ícone).
        buttons = [
            ("Criar alvo na frente", "criar_alvo", "PLUS"),
            ("Colocar no chão", "colocar_no_chao", "TRIA_DOWN_BAR"),
        ]

        def on_attach(self, obj):
            # Roda uma vez, logo que o componente entra no objeto.
            self.args["Nome"] = obj.name
            for o in obj.users_scene[0].objects:
                if o.name.startswith("Jogador"):
                    self.args["Alvo"] = o
                    break

        def on_change(self, obj, nome, valor):
            # Quando qualquer campo muda (e ao abrir o arquivo), roda uma vez
            # para cada campo. Devolver um texto mostra um aviso embaixo dele.
            if nome == "Alvo":
                if valor is None:
                    return "Sem alvo: ele vai ficar parado"
                if valor == obj:
                    return "O alvo é ele mesmo"
            if nome == "Cena ao pegar" and valor is not None and valor in obj.users_scene:
                return "É a cena do próprio objeto: escolha outra"
            if nome == "Velocidade" and valor > 15:
                return "Muito rápido: pode atravessar paredes"
            if nome == "Altura do pulo" and valor > 0 and self.args["Modo"] != "Pular":
                return "Só vale no modo Pular"

        def criar_alvo(self, obj, context):
            import bpy
            alvo = bpy.data.objects.new("Alvo de " + obj.name, None)
            alvo.empty_draw_type = 'SPHERE'
            alvo.location = obj.matrix_world * Vector((0, 4, 0))
            context.scene.objects.link(alvo)
            self.args["Alvo"] = alvo

        def draw_gizmo(self, obj, args, g, selected):
            # Desenho na viewport (não aparece no jogo). Por padrão só roda
            # com o objeto selecionado; Overlay > Component Gizmos muda isso.
            # g: line, path, circle, sphere, box, arrow, text. Cor: "YELLOW",
            # "RED", ... ou (r, g, b). Posições em coordenadas do mundo.
            pos = obj.matrix_world.translation
            g.circle(pos, args["Distancia de parada"], "GREEN")
            if args["Agressivo"]:
                g.circle(pos, args["Distancia de parada"] * 3.0, "RED")
            alvo = args["Alvo"]                        # Object do editor, ou None
            if alvo is not None:
                g.arrow(pos, alvo.matrix_world.translation, "YELLOW", width=2)
            g.text(pos, args["Nome"])

        def colocar_no_chao(self, obj, context):
            context.scene.update()   # matriz do objeto em dia
            menor_z = min((obj.matrix_world * v.co).z for v in obj.data.vertices)
            obj.location.z -= menor_z

    # ------------------------------------------------------------------
    # Lado do jogo: igual a qualquer componente.
    def start(self, args):
        self.alvo = args["Alvo"]                   # KX_GameObject ou None
        self.parada = args["Distancia de parada"]
        self.velocidade = args["Velocidade"] * (2.0 if args["Modo"] == "Correr" else 1.0)
        self.pular = args["Modo"] == "Pular"
        self.altura = args["Altura do pulo"]
        self.olhar = args["Olhar para o alvo"]
        self.agressivo = args["Agressivo"]
        self.piscadas = args["Piscadas por segundo"]
        self.cor_alerta = list(args["Cor de alerta"])
        self.nome = args["Nome"]
        self.cena = args["Cena ao pegar"]          # nome da cena, ou ""

        self.cor_normal = list(self.object.color)
        self.chao = self.object.worldPosition.z
        self.tempo = 0.0
        self.pegou = False

        if self.alvo is None:
            print("[%s] sem Alvo escolhido: fica parado" % self.nome)

    def update(self):
        dt = 1.0 / logic.getLogicTicRate()
        self.tempo += dt
        if self.alvo is None or self.alvo.invalid:
            return

        pos = self.object.worldPosition
        para_alvo = self.alvo.worldPosition - pos
        para_alvo.z = 0.0
        dist = para_alvo.length

        if dist > self.parada:
            passo = para_alvo.normalized() * min(self.velocidade * dt, dist - self.parada)
            pos.x += passo.x
            pos.y += passo.y
            self.pegou = False
        elif not self.pegou:
            self.pegou = True
            print("[%s] te pegou!" % self.nome)
            if self.cena and self.cena not in [c.name for c in logic.getSceneList()]:
                logic.addScene(self.cena, 1)       # 1 = por cima da cena atual

        if self.pular:
            pos.z = self.chao + abs(math.sin(self.tempo * 4.0)) * self.altura

        if self.olhar and dist > 0.01:
            self.object.alignAxisToVect(para_alvo, 1, 0.2)   # eixo Y aponta para o alvo
            self.object.alignAxisToVect(Vector((0, 0, 1)), 2, 1.0)

        if self.agressivo and dist < self.parada * 3.0:
            liga = int(self.tempo * self.piscadas * 2) % 2 == 0
            self.object.color = self.cor_alerta if liga else self.cor_normal
            self.object.localScale = [1.25] * 3
        else:
            self.object.color = self.cor_normal
            self.object.localScale = [1.0] * 3
