# Smart Component Wizard: turns a list of fields (+ a recipe) into the
# source code of a Smart Component (Range.args, plus an Editor class only
# when a field asks for on_attach).
#
# Pure Python, no bpy: the panel (startup/smart_component_wizard.py) fills
# plain dicts and calls generate(). add_field() inserts one field into the
# args of code that already exists.
#
# A field is a dict (field() fills the missing keys):
#   name      label shown in the box and key of args[...]
#   kind      FLOAT INT BOOL TEXT CHOICE OBJECT OBJECTLIST POINT SCENE COLOR HEADER
#   default   float/int/bool/str/(r, g, b, a)/(x, y, z) depending on kind
#   min, max  numbers or None (both set = slider)
#   tip       tooltip
#   items     CHOICE options
#   icon, open            HEADER icon and if it starts open
#   line      OBJECT: arrow to it; OBJECTLIST: path through them; POINT: line to it
#   circle    FLOAT: circle with this radius
#   required  warning while empty
#   warn_above  FLOAT/INT: warning when bigger (None = off)
#   filter    OBJECT/OBJECTLIST: "", "MESH", "LAMP", "CAMERA", "EMPTY", "ARMATURE"...
#   create    OBJECT/OBJECTLIST: "+" button that creates an object for the field
#   auto      OBJECT: on attach, pick the first object whose name starts with this
#   show_if   None, "Field" (a Bool) or ("Field", "value")

import keyword
import re
import unicodedata

KINDS = ("FLOAT", "INT", "BOOL", "TEXT", "CHOICE", "OBJECT", "OBJECTLIST", "POINT", "SCENE",
         "COLOR", "HEADER")

_ARG_CLASS = {
    "FLOAT": "Float", "INT": "Int", "BOOL": "Bool", "TEXT": "Text", "CHOICE": "Choice",
    "OBJECT": "Object", "OBJECTLIST": "ObjectList", "POINT": "Point", "SCENE": "Scene",
    "COLOR": "Color", "HEADER": "Header",
}

_DEFAULTS = {"FLOAT": 0.0, "INT": 0, "BOOL": False, "COLOR": (1.0, 1.0, 1.0, 1.0),
             "POINT": (0.0, 0.0, 0.0)}


def field(name, kind, default=None, **kw):
    """Field dict with every key filled."""
    f = dict(name=name, kind=kind, default=default, min=None, max=None, tip="", items=[],
             icon="FULLSCREEN", open=True, line=False, circle=False, required=False,
             warn_above=None, filter="", create=False, auto="", show_if=None)
    f.update(kw)
    if f["default"] is None:
        f["default"] = _DEFAULTS.get(kind, "")
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
    if keyword.iskeyword(text) or text in ("self", "args", "object", "dt"):
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
        errors.append("Invalid file name: use letters, numbers and _ (e.g. magic_door)")
    if not classname or not classname.isidentifier() or keyword.iskeyword(classname):
        errors.append("Invalid class name (e.g. MagicDoor)")
    seen = set()
    for f in fields:
        if f["kind"] == "HEADER":
            continue
        n = f["name"].strip()
        if not n:
            errors.append("A field has no name")
        elif n in seen:
            errors.append("Repeated field: %s" % n)
        elif n.startswith("C_"):
            errors.append("Field name can't start with C_: %s" % n)
        elif len(n) > 63:
            errors.append("Field name too long: %s" % n)
        seen.add(n)
        if f["kind"] == "CHOICE" and not [i for i in f["items"] if i.strip()]:
            errors.append("Choice without options: %s" % n)
    names = {f["name"].strip(): f for f in fields if f["kind"] != "HEADER"}
    for f in fields:
        cond = f.get("show_if")
        other = cond if isinstance(cond, str) else (cond[0] if cond else None)
        if other and other not in names:
            errors.append("%s: 'show if' uses a field that doesn't exist (%s)" % (f["name"], other))
    return errors


# ----------------------------------------------------------------------------
# Pieces of code

def _num(v, kind="FLOAT"):
    return str(int(v)) if kind == "INT" else repr(float(v))


def arg_expr(f):
    """'Float(2.0, min=0.0, tip="...")' for one field (not HEADER)."""
    k = f["kind"]
    head, extra = [], []
    if k in ("FLOAT", "INT"):
        head = [_num(f["default"], k)]
        if f["min"] is not None:
            extra.append("min=%s" % _num(f["min"], k))
        if f["max"] is not None:
            extra.append("max=%s" % _num(f["max"], k))
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
        head = [_num(c) for c in tuple(f["default"])[:4]]
    elif k == "POINT":
        head = [_num(c) for c in (tuple(f["default"]) + (0.0, 0.0, 0.0))[:3]]

    tip = f["tip"].strip()
    if tip:
        extra.append("tip=%r" % tip)
    if k in ("OBJECT", "OBJECTLIST") and f["filter"]:
        extra.append("filter=%r" % f["filter"])
    if k in ("OBJECT", "OBJECTLIST", "POINT") and f["line"]:
        extra.append("line=True")
    if k in ("OBJECT", "OBJECTLIST") and f["create"]:
        extra.append("create=True")
    if k == "FLOAT" and f["circle"]:
        extra.append("circle=True")
    if k in ("FLOAT", "INT") and f["warn_above"] is not None:
        extra.append("warn_above=%s" % _num(f["warn_above"], k))
    if f["required"] and k in ("OBJECT", "OBJECTLIST", "SCENE", "TEXT"):
        extra.append("required=True")
    cond = f.get("show_if")
    if cond:
        extra.append("show_if=%r" % ((cond if isinstance(cond, str) else tuple(cond)),))
    return "%s(%s)" % (_ARG_CLASS[k], ", ".join(head + extra))


def arg_line(f):
    """One item of the args list."""
    if f["kind"] == "HEADER":
        return "Header(%r, icon=%r%s)," % (f["name"] or "Section", f["icon"] or "FULLSCREEN",
                                           "" if f["open"] else ", open=False")
    return "(%r, %s)," % (f["name"], arg_expr(f))


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


def _editor(fields):
    """Editor class lines (only when a field auto-picks an object)."""
    on_attach = []
    for f in fields:
        if f["kind"] == "OBJECT" and f["auto"].strip():
            on_attach += [
                "for o in obj.users_scene[0].objects:",
                "    if o != obj and o.name.startswith(%r):" % f["auto"].strip(),
                "        self.args[%r] = o" % f["name"],
                "        break",
            ]
    if not on_attach:
        return []
    body = ["def on_attach(self, obj):",
            "    # Roda uma vez, quando o componente entra no objeto."] + _indent(on_attach, 4)
    return (["# ------------------------------------------------------------------",
             "# Lado de editor (o jogo nunca roda esta classe). Avisos, linhas e",
             "# botões dos campos já vêm das opções em Range.args.",
             "class Editor:"] + _indent(body, 4))


# ----------------------------------------------------------------------------
# Recipes: fields + game code. The code uses self.<field as identifier>.

def _recipes():
    R = {}
    F = field

    R["EMPTY"] = dict(
        label="Vazio", tip="Só a estrutura: você monta os campos",
        fields=[F("Velocidade", "FLOAT", 1.0, min=0.0, max=10.0, tip="Exemplo: apague ou troque")],
        start=[], update=["# Escreva aqui o que roda a cada quadro.",
                          "# Ex.: self.object.applyRotation((0, 0, self.velocidade * dt), False)",
                          "pass"],
    )

    R["CHASER"] = dict(
        label="Perseguidor", tip="Vai atrás de um alvo e para perto dele", physics="NO_COLLISION",
        fields=[
            F("Alvo", "OBJECT", tip="Objeto que ele persegue", line=True, required=True,
              auto="Jogador", create=True),
            F("Velocidade", "FLOAT", 3.0, min=0.0, max=20.0, tip="Metros por segundo", warn_above=15.0),
            F("Distancia de parada", "FLOAT", 1.5, min=0.0, max=10.0,
              tip="Para quando chega a essa distância", circle=True),
            F("Pular", "BOOL", False, tip="Vai pulando"),
            F("Altura do pulo", "FLOAT", 0.8, min=0.0, max=3.0, show_if="Pular"),
        ],
        start=["self.chao = self.object.worldPosition.z",
               "self.tempo = 0.0"],
        update=[
            "self.tempo += dt",
            "if self.alvo is None or self.alvo.invalid:",
            "    return",
            "para_alvo = self.alvo.worldPosition - self.object.worldPosition",
            "para_alvo.z = 0.0",
            "dist = para_alvo.length",
            "if dist > self.distancia_de_parada:",
            "    passo = min(self.velocidade * dt, dist - self.distancia_de_parada)",
            "    self.object.worldPosition += para_alvo.normalized() * passo",
            "    self.object.alignAxisToVect(para_alvo, 1, 0.2)   # eixo Y olha para o alvo",
            "if self.pular:",
            "    self.object.worldPosition.z = self.chao + abs(math.sin(self.tempo * 4.0)) * self.altura_do_pulo",
        ],
        imports=["import math"],
    )

    R["PATROL"] = dict(
        label="Patrulha", tip="Anda por uma lista de pontos, com pausa em cada um", physics="NO_COLLISION",
        fields=[
            F("Pontos", "OBJECTLIST", tip="Pontos do caminho, em ordem", line=True, required=True,
              create=True),
            F("Velocidade", "FLOAT", 2.0, min=0.0, max=20.0, tip="Metros por segundo"),
            F("Espera", "FLOAT", 1.0, min=0.0, max=10.0, tip="Segundos parado em cada ponto"),
            F("Caminho", "CHOICE", "Circular", items=["Circular", "Ida e volta"],
              tip="Circular: volta ao 1º. Ida e volta: faz o caminho ao contrário"),
        ],
        start=["self.atual = 0",
               "self.sentido = 1",
               "self.parado = 0.0"],
        update=[
            "if not self.pontos:",
            "    return",
            "if self.parado > 0.0:",
            "    self.parado -= dt",
            "    return",
            "alvo = self.pontos[self.atual]",
            "falta = alvo.worldPosition - self.object.worldPosition",
            "falta.z = 0.0",
            "if falta.length < 0.1:",
            "    self.parado = self.espera",
            "    if self.caminho == \"Circular\":",
            "        self.atual = (self.atual + 1) % len(self.pontos)",
            "    else:",
            "        if not 0 <= self.atual + self.sentido < len(self.pontos):",
            "            self.sentido = -self.sentido",
            "        self.atual = max(0, min(len(self.pontos) - 1, self.atual + self.sentido))",
            "    return",
            "self.object.worldPosition += falta.normalized() * min(self.velocidade * dt, falta.length)",
            "self.object.alignAxisToVect(falta, 1, 0.2)",
        ],
    )

    R["PICKUP"] = dict(
        label="Coletável", tip="Gira, e quando o jogador encosta soma pontos e some",
        fields=[
            F("Jogador", "OBJECT", tip="Quem pega", line=True, required=True, auto="Jogador"),
            F("Raio", "FLOAT", 1.0, min=0.1, max=10.0, tip="Distância para pegar", circle=True),
            F("Pontos", "INT", 1, min=0, max=100, tip="Quanto soma na propriedade"),
            F("Propriedade", "TEXT", "pontos", tip="Propriedade do jogador que recebe os pontos",
              required=True),
            F("Girar", "BOOL", True, tip="Fica girando para chamar atenção"),
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
            F("Modelos", "OBJECTLIST", required=True,
              tip="O que ele cria, sorteando um (deixe numa camada escondida)"),
            F("Onde", "CHOICE", "Aqui", items=["Aqui", "No ponto"], tip="Onde as cópias aparecem"),
            F("Ponto", "POINT", (0.0, 0.0, 2.0), tip="Lugar das cópias", line=True,
              show_if=("Onde", "No ponto")),
            F("Intervalo", "FLOAT", 2.0, min=0.1, max=30.0, tip="Segundos entre um e outro"),
            F("Maximo", "INT", 5, min=1, max=100, tip="Quantos podem existir ao mesmo tempo"),
            F("Vida", "INT", 0, min=0, max=10000, tip="Quadros até sumir (0 = para sempre)"),
        ],
        start=["self.tempo = 0.0",
               "self.criados = []"],
        update=[
            "if not self.modelos:",
            "    return",
            "self.criados = [o for o in self.criados if not o.invalid]",
            "self.tempo += dt",
            "if self.tempo >= self.intervalo and len(self.criados) < self.maximo:",
            "    self.tempo = 0.0",
            "    novo = self.object.scene.addObject(random.choice(self.modelos), self.object, self.vida)",
            "    if self.onde == \"No ponto\":",
            "        novo.worldPosition = self.ponto",
            "    self.criados.append(novo)",
        ],
        imports=["import random"],
    )

    R["DOOR"] = dict(
        label="Porta", tip="Sobe quando o jogador chega perto e desce quando ele sai",
        fields=[
            F("Jogador", "OBJECT", tip="Quem abre", line=True, required=True, auto="Jogador"),
            F("Raio", "FLOAT", 3.0, min=0.1, max=20.0, tip="Distância para abrir", circle=True),
            F("Altura", "FLOAT", 3.0, min=0.0, max=20.0, tip="Quanto ela sobe"),
            F("Velocidade", "FLOAT", 2.0, min=0.1, max=20.0, tip="Metros por segundo"),
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
            F("Jogador", "OBJECT", tip="Quem ativa", line=True, required=True, auto="Jogador"),
            F("Raio", "FLOAT", 2.0, min=0.1, max=50.0, tip="Tamanho da zona", circle=True),
            F("Mensagem", "TEXT", "entrou", tip="Mensagem enviada (o sensor Message pega)"),
            F("Abrir cena", "BOOL", False, tip="Abre uma cena por cima ao entrar"),
            F("Cena", "SCENE", tip="Cena aberta por cima", required=True, show_if="Abrir cena"),
            F("Uma vez", "BOOL", True, tip="Só funciona na primeira vez"),
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
            "    if self.abrir_cena and self.cena and self.cena not in [s.name for s in logic.getSceneList()]:",
            "        logic.addScene(self.cena, 1)   # 1 = por cima",
            "self.dentro = dentro",
        ],
    )

    R["HEALTH"] = dict(
        label="Vida", tip="Guarda a vida numa propriedade e decide o que fazer quando acaba",
        fields=[
            F("Vida maxima", "INT", 100, min=1, max=1000, tip="Vida ao começar"),
            F("Propriedade", "TEXT", "vida", required=True,
              tip="Propriedade do objeto com a vida (outros scripts tiram dela)"),
            F("Ao morrer", "CHOICE", "Sumir", items=["Sumir", "Reiniciar cena", "Abrir cena"],
              tip="O que acontece quando a vida chega a 0"),
            F("Cena", "SCENE", tip="Cena aberta ao morrer", required=True,
              show_if=("Ao morrer", "Abrir cena")),
            F("Mensagem", "TEXT", "morreu", tip="Mensagem enviada ao morrer (vazio = nenhuma)"),
        ],
        start=["self.object[self.propriedade] = self.vida_maxima",
               "self.morto = False"],
        update=[
            "if self.morto or self.object.get(self.propriedade, 1) > 0:",
            "    return",
            "self.morto = True",
            "if self.mensagem:",
            "    logic.sendMessage(self.mensagem)",
            "if self.ao_morrer == \"Sumir\":",
            "    self.object.endObject()",
            "elif self.ao_morrer == \"Reiniciar cena\":",
            "    self.object.scene.restart()",
            "elif self.cena:",
            "    logic.addScene(self.cena, 1)",
        ],
    )

    R["CAMERA"] = dict(
        label="Câmera seguidora", tip="Fica atrás e acima do alvo, com movimento suave",
        fields=[
            F("Alvo", "OBJECT", tip="Quem a câmera segue", line=True, required=True, auto="Jogador"),
            F("Distancia", "FLOAT", 8.0, min=1.0, max=50.0, tip="Metros atrás do alvo"),
            F("Altura", "FLOAT", 4.0, min=0.0, max=30.0, tip="Metros acima do alvo"),
            F("Suavidade", "FLOAT", 0.1, min=0.01, max=1.0, tip="1 = gruda no alvo, perto de 0 = bem suave"),
        ],
        start=[],
        update=[
            "if self.alvo is None or self.alvo.invalid:",
            "    return",
            "atras = self.alvo.worldOrientation.col[1] * -self.distancia",
            "destino = self.alvo.worldPosition + atras + Vector((0, 0, self.altura))",
            "self.object.worldPosition = self.object.worldPosition.lerp(destino, self.suavidade)",
            "olhar = self.alvo.worldPosition - self.object.worldPosition",
            "self.object.alignAxisToVect(-olhar, 2, 1.0)    # câmera olha pelo -Z",
            "self.object.alignAxisToVect(Vector((0, 0, 1)), 1, 0.5)",
        ],
        imports=["from mathutils import Vector"],
    )

    R["LIGHT"] = dict(
        label="Luz piscando", tip="Faz uma luz tremer como fogo ou lâmpada com defeito",
        fields=[
            F("Luz", "OBJECT", tip="A luz que pisca", filter="LAMP", required=True, create=True,
              line=True),
            F("Minimo", "FLOAT", 0.3, min=0.0, max=10.0, tip="Energia mais fraca"),
            F("Maximo", "FLOAT", 1.5, min=0.0, max=10.0, tip="Energia mais forte"),
            F("Trocas por segundo", "FLOAT", 12.0, min=0.5, max=60.0, tip="Quantas vezes muda"),
        ],
        start=["self.tempo = 0.0"],
        update=[
            "if self.luz is None or self.luz.invalid:",
            "    return",
            "self.tempo += dt",
            "if self.tempo >= 1.0 / self.trocas_por_segundo:",
            "    self.tempo = 0.0",
            "    self.luz.energy = random.uniform(self.minimo, self.maximo)",
        ],
        imports=["import random"],
    )

    R["ROTATOR"] = dict(
        label="Girador", tip="Gira sem parar, ou balança de um lado para o outro",
        fields=[
            F("Eixo", "CHOICE", "Z", items=["X", "Y", "Z"], tip="Em volta de qual eixo"),
            F("Velocidade", "FLOAT", 90.0, min=-720.0, max=720.0, tip="Graus por segundo"),
            F("Balancar", "BOOL", False, tip="Vai e volta em vez de girar sem parar"),
            F("Angulo", "FLOAT", 30.0, min=0.0, max=180.0, tip="Até quantos graus balança",
              show_if="Balancar"),
        ],
        start=["self.tempo = 0.0",
               "self.eixo_i = \"XYZ\".index(self.eixo)",
               "self.inicio = self.object.localOrientation.copy()"],
        update=[
            "self.tempo += dt",
            "giro = [0.0, 0.0, 0.0]",
            "if self.balancar:",
            "    graus = math.sin(self.tempo * math.radians(self.velocidade)) * self.angulo",
            "    giro[self.eixo_i] = math.radians(graus)",
            "    self.object.localOrientation = self.inicio",
            "else:",
            "    giro[self.eixo_i] = math.radians(self.velocidade) * dt",
            "self.object.applyRotation(giro, True)",
        ],
        imports=["import math"],
    )
    return R


RECIPES = _recipes()
RECIPE_ORDER = ("EMPTY", "CHASER", "PATROL", "PICKUP", "SPAWNER", "DOOR", "TRIGGER", "HEALTH",
                "CAMERA", "LIGHT", "ROTATOR")


def recipe_fields(key):
    return [dict(f, items=list(f["items"])) for f in RECIPES[key]["fields"]]


def recipe_missing(key, fields):
    """Fields of the recipe code that are no longer in the list."""
    have = {(f["name"], f["kind"]) for f in fields}
    return [f["name"] for f in RECIPES[key]["fields"] if (f["name"], f["kind"]) not in have]


# ----------------------------------------------------------------------------
# The file

def generate(module, classname, fields, recipe="EMPTY", physics="", label=""):
    """Source code of the component. Fields keep the order given."""
    rec = RECIPES.get(recipe, RECIPES["EMPTY"])
    varnames = _var_names(fields)
    kinds = {f["kind"] for f in fields}
    rec_ok = recipe != "EMPTY" and not recipe_missing(recipe, fields)
    used = [_ARG_CLASS[k] for k in KINDS if k in kinds]
    if "OBJECTLIST" in kinds:
        used.append("objects")

    out = ['"""%s' % (label or classname), "",
           "Feito com o Smart Component Wizard. Para usar: selecione um objeto e, em",
           "Game Components > Add, digite %s.%s" % (module, classname),
           '"""', "",
           "from collections import OrderedDict"]
    if rec_ok:
        out += rec.get("imports", [])
    out += ["", "from Range import types, logic"]
    if used:
        out.append("from Range.args import " + ", ".join(used))
    out += ["", "", "class %s(types.KX_PythonComponent):" % classname]

    body = ["args = OrderedDict(["] + ["    " + arg_line(f) for f in fields] + ["])"]
    if physics:
        body += ["", "# Ao adicionar o componente, o editor já deixa o objeto assim.",
                 "requires = {\"physics\": %r}" % physics]

    editor = _editor(fields)
    if editor:
        body += [""] + editor

    body += ["", "# ------------------------------------------------------------------",
             "# Lado do jogo.", "def start(self, args):"]
    starts = []
    for f in fields:
        k = f["kind"]
        if k == "HEADER":
            continue
        var, key = varnames[f["name"]], f["name"]
        if k == "OBJECTLIST":
            starts.append("self.%s = objects(self.object.scene, args[%r])   # lista de KX_GameObject"
                          % (var, key))
            continue
        note = {"OBJECT": "   # KX_GameObject ou None", "SCENE": "   # nome da cena, ou \"\"",
                "POINT": "   # Vector (posição no mundo)"}.get(k, "")
        starts.append("self.%s = args[%r]%s" % (var, key, note))
    if rec_ok:
        starts += rec["start"]
    body += _indent(starts or ["pass"], 4)

    body += ["", "def update(self):",
             "    dt = 1.0 / logic.getLogicTicRate()   # segundos por quadro"]
    body += _indent(rec["update"] if rec_ok else RECIPES["EMPTY"]["update"], 4)

    out += _indent(body, 4)
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# Add Field: one more item in the args of existing code

_ARGS_START = re.compile(r"^(\s*)args\s*=\s*(OrderedDict\s*\(\s*\[|\[|\{|dict\s*\()")
_IMPORT_LINE = re.compile(r"^from\s+Range\.args\s+import\s+(.+)$", re.M)


def add_field(source, classname, f):
    """Source with the field added at the end of the class args.
    Returns (new_source, error). Only the args block and the Range.args
    import are touched."""
    lines = source.split("\n")
    cls_re = re.compile(r"^(\s*)class\s+%s\b" % re.escape(classname))
    start = None
    for i, l in enumerate(lines):
        m = cls_re.match(l)
        if m:
            start = i
            cls_indent = len(m.group(1))
            break
    if start is None:
        return source, "Class %s not found in the code" % classname

    args_i = None
    for i in range(start + 1, len(lines)):
        l = lines[i]
        if l.strip() and (len(l) - len(l.lstrip())) <= cls_indent and not l.lstrip().startswith("#"):
            break   # left the class
        m = _ARGS_START.match(l)
        if m:
            args_i, opener = i, m.group(2)
            break
    if args_i is None:
        return source, "No 'args = OrderedDict([...])' in %s: add one first" % classname
    if not opener.startswith("OrderedDict") and not opener.startswith("["):
        return source, "args is a dict: turn it into OrderedDict([...]) to keep the order"

    # Find the line that closes the list: bracket counting from the opener.
    depth, end = 0, None
    text_from = "\n".join(lines[args_i:])
    pos_line = args_i
    in_str = None
    for ch_i, ch in enumerate(text_from):
        if ch == "\n":
            pos_line += 1
            continue
        if in_str:
            if ch == in_str and text_from[ch_i - 1] != "\\":
                in_str = None
            continue
        if ch in "\"'":
            in_str = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                end = pos_line
                break
    if end is None:
        return source, "Could not find the end of args"

    item_indent = " " * (len(lines[args_i]) - len(lines[args_i].lstrip()) + 4)
    for l in lines[args_i + 1:end]:
        if l.strip() and not l.strip().startswith("#"):
            item_indent = l[:len(l) - len(l.lstrip())]
            break
    new_item = item_indent + arg_line(f)

    if end == args_i:
        # One-line args: args = OrderedDict([...]) -> split before the closing ])
        l = lines[end]
        cut = l.rfind("]")
        head = l[:cut].rstrip()
        if head.endswith("["):
            lines[end:end + 1] = [head, new_item, item_indent[:-4] + l[cut:].strip()]
        else:
            lines[end:end + 1] = [head + ("" if head.endswith(",") else ","), new_item,
                                  item_indent[:-4] + l[cut:].strip()]
    else:
        close = lines[end]
        before = close[:len(close) - len(close.lstrip())]
        if close.strip().startswith(("]", ")")):
            # Previous item may lack a trailing comma.
            j = end - 1
            while j > args_i and (not lines[j].strip() or lines[j].strip().startswith("#")):
                j -= 1
            if j > args_i and not lines[j].rstrip().endswith((",", "[", "(")):
                lines[j] = lines[j].rstrip() + ","
            lines.insert(end, new_item)
        else:
            # Last item and closing on the same line: "    ("A", 1)])"
            idx = close.rfind("]")
            item = close[:idx].rstrip()
            lines[end:end + 1] = [item + ("" if item.endswith(",") else ","), new_item,
                                  before[:-4] + close[idx:].strip() if len(before) >= 4 else close[idx:].strip()]

    src = "\n".join(lines)
    # Import the helper class if needed.
    if True:  # import the helper class
        need = [_ARG_CLASS[f["kind"]]] + (["objects"] if f["kind"] == "OBJECTLIST" else [])
        m = _IMPORT_LINE.search(src)
        if m:
            names = [n.strip() for n in m.group(1).strip("() ").split(",") if n.strip()]
            missing = [n for n in need if n not in names and "*" not in names]
            if missing:
                src = src[:m.start(1)] + ", ".join(names + missing) + src[m.end(1):]
        else:
            # After the last top-level import, or at the start.
            ls = src.split("\n")
            last = -1
            for i, l in enumerate(ls):
                if l.startswith(("import ", "from ")):
                    last = i
                elif l.startswith("class "):
                    break
            ls.insert(last + 1, "from Range.args import " + ", ".join(need))
            src = "\n".join(ls)
    return src, None
