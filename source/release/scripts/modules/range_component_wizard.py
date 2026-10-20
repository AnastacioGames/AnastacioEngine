# Smart Component Wizard: turns a list of fields (+ a recipe) into the
# source code of a Smart Component (Range.args + optional Editor class).
#
# Pure Python, no bpy: the panel (startup/smart_component_wizard.py) fills
# plain dicts and calls generate(). Easy to test from the command line.
#
# A field is a dict:
#   name     str   label shown in the box and key of args[...]
#   kind     str   FLOAT INT BOOL TEXT CHOICE OBJECT SCENE COLOR HEADER
#   default        float/int/bool/str/(r, g, b, a) depending on kind
#   min, max       numbers or None (both set = slider)
#   tip      str   tooltip
#   items    list  CHOICE options (default must be one of them)
#   icon     str   HEADER icon;  open bool: HEADER starts open
#   gizmo    str   NONE, LINE (OBJECT: line to it), CIRCLE (FLOAT: radius)
#   required bool  OBJECT/SCENE: warning when empty
#   warn_above     FLOAT/INT: warning when the value is bigger (None = off)
#   auto     str   OBJECT: on attach, pick the first object whose name
#                  starts with this text ("" = off)
#   create   bool  OBJECT: button that creates an Empty and puts it here

import keyword
import re
import unicodedata

KINDS = ("FLOAT", "INT", "BOOL", "TEXT", "CHOICE", "OBJECT", "SCENE", "COLOR", "HEADER")

_ARG_CLASS = {
    "FLOAT": "Float", "INT": "Int", "BOOL": "Bool", "TEXT": "Text", "CHOICE": "Choice",
    "OBJECT": "Object", "SCENE": "Scene", "COLOR": "Color", "HEADER": "Header",
}


def field(name, kind, default=None, **kw):
    """Field dict with every key filled."""
    f = dict(name=name, kind=kind, default=default, min=None, max=None, tip="",
             items=[], icon="FULLSCREEN", open=True, gizmo="NONE", required=False,
             warn_above=None, auto="", create=False)
    f.update(kw)
    if f["default"] is None:
        f["default"] = {"FLOAT": 0.0, "INT": 0, "BOOL": False, "COLOR": (1.0, 1.0, 1.0, 1.0)}.get(kind, "")
    return f


# ----------------------------------------------------------------------------
# Names

def identifier(text, fallback="campo"):
    """'Distância de parada' -> 'distancia_de_parada'."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    if not text:
        text = fallback
    if text[0].isdigit():
        text = "_" + text
    if keyword.iskeyword(text) or text in ("self", "args", "object"):
        text += "_"
    return text


def class_name(module):
    """'porta_magica' -> 'PortaMagica'."""
    parts = identifier(module, "component").strip("_").split("_")
    name = "".join(p[:1].upper() + p[1:] for p in parts if p)
    return name or "Component"


def check(module, classname, fields):
    """List of problems (empty = ok)."""
    errors = []
    if not module or not module.isidentifier() or keyword.iskeyword(module):
        errors.append("Nome do arquivo inválido: use letras, números e _ (ex.: porta_magica)")
    if not classname or not classname.isidentifier() or keyword.iskeyword(classname):
        errors.append("Nome da classe inválido (ex.: PortaMagica)")
    seen = set()
    for f in fields:
        if f["kind"] == "HEADER":
            continue
        n = f["name"].strip()
        if not n:
            errors.append("Há um campo sem nome")
        elif n in seen:
            errors.append("Campo repetido: %s" % n)
        elif n.startswith("C_"):
            errors.append("Nome de campo não pode começar com C_: %s" % n)
        seen.add(n)
        if f["kind"] == "CHOICE" and not [i for i in f["items"] if i.strip()]:
            errors.append("Choice sem opções: %s" % n)
    return errors


# ----------------------------------------------------------------------------
# Pieces of code

def _num(v, kind):
    if kind == "INT":
        return str(int(v))
    s = repr(float(v))
    return s


def _arg_expr(f):
    k = f["kind"]
    cls = _ARG_CLASS[k]
    tip = f["tip"].strip()
    extra = []
    if k in ("FLOAT", "INT"):
        if f["min"] is not None:
            extra.append("min=%s" % _num(f["min"], k))
        if f["max"] is not None:
            extra.append("max=%s" % _num(f["max"], k))
    if tip:
        extra.append("tip=%r" % tip)
    if k == "FLOAT":
        head = [_num(f["default"], k)]
    elif k == "INT":
        head = [_num(f["default"], k)]
    elif k == "BOOL":
        head = [repr(bool(f["default"]))]
    elif k == "TEXT":
        head = [repr(str(f["default"]))]
    elif k == "CHOICE":
        items = [i.strip() for i in f["items"] if i.strip()]
        default = str(f["default"]).strip()
        if default not in items:
            default = items[0] if items else default
        head = [repr(default)] + [repr(i) for i in items]
    elif k == "COLOR":
        head = [_num(c, "FLOAT") for c in tuple(f["default"])[:4]]
    else:  # OBJECT, SCENE
        head = []
    return "%s(%s)" % (cls, ", ".join(head + extra))


def _var_names(fields):
    out, used = {}, set()
    for f in fields:
        if f["kind"] == "HEADER":
            continue
        base = identifier(f["name"])
        name, i = base, 2
        while name in used:
            name, i = "%s_%d" % (base, i), i + 1
        used.add(name)
        out[f["name"]] = name
    return out


def _indent(lines, n):
    pad = " " * n
    return [(pad + l) if l.strip() else "" for l in lines]


def _editor(fields, varnames):
    """Lines of the Editor class (without indentation), or [] when not needed."""
    on_attach, on_change, buttons, methods, gizmo = [], [], [], [], []

    for f in fields:
        k, n = f["kind"], f["name"]
        if k == "HEADER":
            continue
        var = varnames[n]
        if k == "OBJECT":
            if f["auto"].strip():
                on_attach += [
                    "for o in obj.users_scene[0].objects:",
                    "    if o != obj and o.name.startswith(%r):" % f["auto"].strip(),
                    "        self.args[%r] = o" % n,
                    "        break",
                ]
            cond = []
            if f["required"]:
                cond += ["if valor is None:",
                         "    return %r" % "Vazio: escolha um objeto"]
            cond += ["if valor == obj:",
                     "    return %r" % "É o próprio objeto: escolha outro"]
            on_change += ["if nome == %r:" % n] + _indent(cond, 4)
            if f["create"]:
                meth = "criar_" + var
                buttons.append("(%r, %r, \"PLUS\")," % ("Criar " + n, meth))
                methods += [
                    "def %s(self, obj, context):" % meth,
                    "    # Cria um Empty na frente do objeto e já põe no campo.",
                    "    import bpy",
                    "    from mathutils import Vector",
                    "    novo = bpy.data.objects.new(%r + \" de \" + obj.name, None)" % n,
                    "    novo.empty_draw_type = 'SPHERE'",
                    "    novo.location = obj.matrix_world * Vector((0, 4, 0))",
                    "    context.scene.objects.link(novo)",
                    "    self.args[%r] = novo" % n,
                    "",
                ]
            if f["gizmo"] == "LINE":
                gizmo += [
                    "if args[%r] is not None:" % n,
                    "    g.arrow(pos, args[%r].matrix_world.translation, \"YELLOW\", width=2)" % n,
                ]
        elif k == "SCENE" and f["required"]:
            on_change += ["if nome == %r and valor is None:" % n,
                          "    return %r" % "Vazio: escolha uma cena"]
        elif k in ("FLOAT", "INT"):
            if f["warn_above"] is not None:
                on_change += ["if nome == %r and valor > %s:" % (n, _num(f["warn_above"], k)),
                              "    return %r" % ("Acima de %s: confira se é isso mesmo" % _num(f["warn_above"], k))]
            if k == "FLOAT" and f["gizmo"] == "CIRCLE":
                gizmo.append("g.circle(pos, args[%r], \"GREEN\")" % n)

    if not (on_attach or on_change or buttons or gizmo):
        return []

    out = ["# ------------------------------------------------------------------",
           "# Lado de editor. O jogo nunca roda esta classe.",
           "# self.object = o objeto, self.args[\"Campo\"] lê e grava os campos.",
           "class Editor:"]
    body = []
    if buttons:
        body += ["# Botões no fim da caixa do componente: (texto, método, ícone).",
                 "buttons = ["] + _indent(buttons, 4) + ["]", ""]
    if on_attach:
        body += ["def on_attach(self, obj):",
                 "    # Roda uma vez, quando o componente entra no objeto."] + _indent(on_attach, 4) + [""]
    if on_change:
        body += ["def on_change(self, obj, nome, valor):",
                 "    # Roda para cada campo. Devolver um texto mostra um aviso nele."] + _indent(on_change, 4) + [""]
    if gizmo:
        body += ["def draw_gizmo(self, obj, args, g, selected):",
                 "    # Desenho na viewport (não aparece no jogo).",
                 "    pos = obj.matrix_world.translation"] + _indent(gizmo, 4) + [""]
    body += methods
    while body and not body[-1]:
        body.pop()
    return out + _indent(body, 4)


# ----------------------------------------------------------------------------
# Recipes: fields + game code. Field names are the keys used in the code.

def _recipes():
    R = {}

    R["EMPTY"] = dict(
        label="Vazio", tip="Só a estrutura: você monta os campos",
        fields=[field("Velocidade", "FLOAT", 1.0, min=0.0, max=10.0, tip="Exemplo: apague ou troque")],
        start=[], update=["# Escreva aqui o que roda a cada quadro.",
                          "# Ex.: self.object.applyRotation((0, 0, self.velocidade * dt), False)",
                          "pass"],
    )

    R["CHASER"] = dict(
        label="Perseguidor", tip="Vai atrás de um alvo e para perto dele",
        fields=[
            field("Alvo", "OBJECT", tip="Objeto que ele persegue", gizmo="LINE", required=True,
                  auto="Jogador", create=True),
            field("Velocidade", "FLOAT", 3.0, min=0.0, max=20.0, tip="Metros por segundo", warn_above=15.0),
            field("Distancia de parada", "FLOAT", 1.5, min=0.0, max=10.0,
                  tip="Para quando chega a essa distância", gizmo="CIRCLE"),
        ],
        start=[],
        update=[
            "if self.alvo is None or self.alvo.invalid:",
            "    return",
            "para_alvo = self.alvo.worldPosition - self.object.worldPosition",
            "para_alvo.z = 0.0",
            "dist = para_alvo.length",
            "if dist > self.distancia_de_parada:",
            "    passo = min(self.velocidade * dt, dist - self.distancia_de_parada)",
            "    self.object.worldPosition += para_alvo.normalized() * passo",
            "    self.object.alignAxisToVect(para_alvo, 1, 0.2)   # eixo Y olha para o alvo",
        ],
    )

    R["PATROL"] = dict(
        label="Patrulha", tip="Anda entre dois pontos, com pausa em cada um",
        fields=[
            field("Ponto A", "OBJECT", tip="Primeiro ponto", gizmo="LINE", required=True, create=True),
            field("Ponto B", "OBJECT", tip="Segundo ponto", gizmo="LINE", required=True, create=True),
            field("Velocidade", "FLOAT", 2.0, min=0.0, max=20.0, tip="Metros por segundo"),
            field("Espera", "FLOAT", 1.0, min=0.0, max=10.0, tip="Segundos parado em cada ponto"),
        ],
        start=["self.indo_para = self.ponto_a",
               "self.parado = 0.0"],
        update=[
            "if self.indo_para is None or self.indo_para.invalid:",
            "    return",
            "if self.parado > 0.0:",
            "    self.parado -= dt",
            "    return",
            "falta = self.indo_para.worldPosition - self.object.worldPosition",
            "falta.z = 0.0",
            "if falta.length < 0.1:",
            "    self.parado = self.espera",
            "    self.indo_para = self.ponto_b if self.indo_para == self.ponto_a else self.ponto_a",
            "    return",
            "self.object.worldPosition += falta.normalized() * min(self.velocidade * dt, falta.length)",
            "self.object.alignAxisToVect(falta, 1, 0.2)",
        ],
    )

    R["PICKUP"] = dict(
        label="Coletável", tip="Gira, e quando o jogador encosta soma pontos e some",
        fields=[
            field("Jogador", "OBJECT", tip="Quem pega", gizmo="LINE", required=True, auto="Jogador"),
            field("Raio", "FLOAT", 1.0, min=0.1, max=10.0, tip="Distância para pegar", gizmo="CIRCLE"),
            field("Pontos", "INT", 1, min=0, max=100, tip="Quanto soma na propriedade"),
            field("Propriedade", "TEXT", "pontos", tip="Propriedade do jogador que recebe os pontos"),
            field("Girar", "BOOL", True, tip="Fica girando para chamar atenção"),
        ],
        start=[],
        update=[
            "if self.girar:",
            "    self.object.applyRotation((0, 0, 2.0 * dt), False)",
            "if self.jogador is None or self.jogador.invalid:",
            "    return",
            "if self.object.getDistanceTo(self.jogador) < self.raio:",
            "    self.jogador[self.propriedade] = self.jogador.get(self.propriedade, 0) + self.pontos",
            "    self.object.endObject()",
        ],
    )

    R["SPAWNER"] = dict(
        label="Spawner", tip="Cria cópias de um objeto de tempos em tempos",
        fields=[
            field("Objeto", "OBJECT", tip="O que ele cria (deixe numa camada escondida)", required=True),
            field("Intervalo", "FLOAT", 2.0, min=0.1, max=30.0, tip="Segundos entre um e outro"),
            field("Maximo", "INT", 5, min=1, max=100, tip="Quantos podem existir ao mesmo tempo"),
            field("Vida", "INT", 0, min=0, max=10000, tip="Quadros até sumir (0 = para sempre)"),
        ],
        start=["self.tempo = 0.0",
               "self.criados = []"],
        update=[
            "if self.objeto is None:",
            "    return",
            "self.criados = [o for o in self.criados if not o.invalid]",
            "self.tempo += dt",
            "if self.tempo >= self.intervalo and len(self.criados) < self.maximo:",
            "    self.tempo = 0.0",
            "    novo = self.object.scene.addObject(self.objeto.name, self.object, self.vida)",
            "    self.criados.append(novo)",
        ],
    )

    R["DOOR"] = dict(
        label="Porta", tip="Sobe quando o jogador chega perto e desce quando ele sai",
        fields=[
            field("Jogador", "OBJECT", tip="Quem abre", gizmo="LINE", required=True, auto="Jogador"),
            field("Raio", "FLOAT", 3.0, min=0.1, max=20.0, tip="Distância para abrir", gizmo="CIRCLE"),
            field("Altura", "FLOAT", 3.0, min=0.0, max=20.0, tip="Quanto ela sobe"),
            field("Velocidade", "FLOAT", 2.0, min=0.1, max=20.0, tip="Metros por segundo"),
        ],
        start=["self.base = self.object.worldPosition.z"],
        update=[
            "if self.jogador is None or self.jogador.invalid:",
            "    return",
            "perto = self.object.getDistanceTo(self.jogador) < self.raio",
            "alvo_z = self.base + (self.altura if perto else 0.0)",
            "z = self.object.worldPosition.z",
            "passo = self.velocidade * dt",
            "self.object.worldPosition.z = min(z + passo, alvo_z) if z < alvo_z else max(z - passo, alvo_z)",
        ],
    )

    R["TRIGGER"] = dict(
        label="Zona de gatilho", tip="Quando o jogador entra: manda mensagem e/ou abre uma cena",
        fields=[
            field("Jogador", "OBJECT", tip="Quem ativa", gizmo="LINE", required=True, auto="Jogador"),
            field("Raio", "FLOAT", 2.0, min=0.1, max=50.0, tip="Tamanho da zona", gizmo="CIRCLE"),
            field("Mensagem", "TEXT", "entrou", tip="Mensagem enviada (sensor Message pega)"),
            field("Cena", "SCENE", tip="Cena aberta por cima ao entrar (opcional)"),
            field("Uma vez", "BOOL", True, tip="Só funciona na primeira vez"),
        ],
        start=["self.dentro = False",
               "self.usado = False"],
        update=[
            "if self.jogador is None or self.jogador.invalid or (self.uma_vez and self.usado):",
            "    return",
            "dentro = self.object.getDistanceTo(self.jogador) < self.raio",
            "if dentro and not self.dentro:",
            "    self.usado = True",
            "    if self.mensagem:",
            "        logic.sendMessage(self.mensagem)",
            "    if self.cena and self.cena not in [s.name for s in logic.getSceneList()]:",
            "        logic.addScene(self.cena, 1)   # 1 = por cima",
            "self.dentro = dentro",
        ],
    )
    return R


RECIPES = _recipes()
RECIPE_ORDER = ("EMPTY", "CHASER", "PATROL", "PICKUP", "SPAWNER", "DOOR", "TRIGGER")


def recipe_fields(key):
    return [dict(f, items=list(f["items"])) for f in RECIPES[key]["fields"]]


# ----------------------------------------------------------------------------
# The file

def generate(module, classname, fields, recipe="EMPTY", physics="", label=""):
    """Source code of the component. Fields keep the order given."""
    rec = RECIPES.get(recipe, RECIPES["EMPTY"])
    varnames = _var_names(fields)
    kinds = {f["kind"] for f in fields}
    used = [_ARG_CLASS[k] for k in KINDS if k in kinds]

    # The recipe code only works if its fields are still there.
    names = {f["name"] for f in fields}
    rec_ok = all(f["name"] in names for f in rec["fields"]) and recipe != "EMPTY"

    out = ['"""%s' % (label or classname), "",
           "Feito com o Smart Component Wizard. Para usar: selecione um objeto e, em",
           "Game Components > Add, digite %s.%s" % (module, classname),
           '"""', "",
           "from collections import OrderedDict", "",
           "from Range import types, logic"]
    if used:
        out.append("from Range.args import " + ", ".join(used))
    out += ["", "", "class %s(types.KX_PythonComponent):" % classname]

    body = ["args = OrderedDict(["]
    for f in fields:
        if f["kind"] == "HEADER":
            body.append("    Header(%r, icon=%r%s)," % (f["name"] or "Seção", f["icon"] or "FULLSCREEN",
                                                      "" if f["open"] else ", open=False"))
        else:
            body.append("    (%r, %s)," % (f["name"], _arg_expr(f)))
    body.append("])")
    if physics:
        body += ["", "# Ao adicionar o componente, o editor já deixa o objeto assim.",
                 "requires = {\"physics\": %r}" % physics]

    editor = _editor(fields, varnames)
    if editor:
        body += [""] + editor

    body += ["", "# ------------------------------------------------------------------",
             "# Lado do jogo.", "def start(self, args):"]
    starts = []
    for f in fields:
        if f["kind"] == "HEADER":
            continue
        note = {"OBJECT": "   # KX_GameObject ou None", "SCENE": "   # nome da cena, ou \"\""}.get(f["kind"], "")
        starts.append("self.%s = args[%r]%s" % (varnames[f["name"]], f["name"], note))
    if rec_ok:
        starts += rec["start"]
    body += _indent(starts or ["pass"], 4)

    body += ["", "def update(self):",
             "    dt = 1.0 / logic.getLogicTicRate()   # segundos por quadro"]
    if rec_ok:
        body += _indent(rec["update"], 4)
    else:
        body += _indent(RECIPES["EMPTY"]["update"], 4)

    out += _indent(body, 4)
    return "\n".join(out) + "\n"
