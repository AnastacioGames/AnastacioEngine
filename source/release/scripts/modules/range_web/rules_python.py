# Analise estatica de scripts Python para o alvo Web (WEB-PY-001..009, WEB-PKG-007).
# Usa somente ast.parse: o script analisado nunca e importado, executado nem compilado para
# execucao. Limites declarados (plano, secao 6): aliases simples, guards de plataforma
# resolviveis e nada alem disso; qualquer coisa dinamica vira aviso de cobertura parcial.
#
# Politica de gravidade: ERROR/CONFIRMED so quando o chamador declara o script como
# necessario (`required`) E o uso esta no nivel do modulo (roda no import), sem guard
# desconhecido nem try/except ImportError. Fora disso, WARNING/POTENTIAL.
# O parse usa a gramatica do Python que executa o analisador; rode-o com o mesmo minor
# do runtime Web (o manifesto declara python.version).

import ast

from .results import (
    EVIDENCE_CONFIRMED, EVIDENCE_POTENTIAL, SEVERITY_ERROR, SEVERITY_WARNING, Finding,
)

TARGET_PLATFORM = "emscripten"
TARGET_OS_NAME = "posix"
TARGET_PLATFORM_SYSTEM = "Emscripten"

EDITOR_MODULES = frozenset(("bpy", "bpy_extras", "bl_ui", "bl_operators", "addon_utils"))

_OS_PROCESS = frozenset(("os.system", "os.fork", "os.forkpty", "os.popen", "os.startfile",
                         "os.posix_spawn", "os.posix_spawnp"))
_OS_PROCESS_PREFIXES = ("os.exec", "os.spawn", "subprocess.")
_DLL_CALLS = frozenset(("ctypes.CDLL", "ctypes.PyDLL", "ctypes.WinDLL", "ctypes.OleDLL",
                        "ctypes.cdll.LoadLibrary", "ctypes.windll.LoadLibrary",
                        "ctypes.pydll.LoadLibrary", "ctypes.oledll.LoadLibrary"))
_THREAD_CALLS = frozenset(("threading.Thread", "threading.Timer", "_thread.start_new_thread",
                           "_thread.start_new", "multiprocessing.Process", "multiprocessing.Pool",
                           "concurrent.futures.ThreadPoolExecutor",
                           "concurrent.futures.ProcessPoolExecutor"))
_BLOCKING_CALLS = frozenset(("time.sleep", "input"))
_EVAL_CALLS = frozenset(("eval", "exec"))
_IMPORT_CALLS = frozenset(("__import__", "importlib.import_module", "importlib.__import__"))
_IMPORT_ERRORS = frozenset(("ImportError", "ModuleNotFoundError", "Exception", "BaseException"))


class AnalysisResult:
    def __init__(self):
        self.findings = []
        self.imports = []      # (nome_do_modulo, linha, protegido_por_try)
        self.has_dynamic = False


def analyze_source(source, filename, required=True, available_modules=None):
    """Analisa um script. `available_modules`: nomes de topo resolviveis (stdlib do manifesto +
    modulos do projeto). None desliga WEB-PY-001, pois sem manifesto nao ha o que comparar."""
    result = AnalysisResult()
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        result.findings.append(Finding(
            "WEB-PY-008", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
            "Erro de sintaxe: %s" % (e.msg,),
            fix="Corrigir a sintaxe (o runtime usa a gramática do Python do manifesto).",
            location={"source": filename, "line": e.lineno}))
        return result
    except (ValueError, RecursionError) as e:
        result.findings.append(Finding(
            "WEB-PY-008", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
            "Script não pôde ser analisado: %s" % (e,),
            fix="Verificar codificação e conteúdo do arquivo.",
            location={"source": filename}))
        return result
    _Analyzer(result, filename, required, available_modules).visit(tree)
    return result


def check_python_main_loop(text_name, adapter_validated=False):
    """WEB-PY-005: main loop Python configurado na cena. E enquanto nao houver adaptador validado."""
    if not text_name or adapter_validated:
        return []
    return [Finding("WEB-PY-005", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                    "Main loop Python personalizado (%s) sem adaptador Web validado." % text_name,
                    fix="Usar controllers/components executados por frame.",
                    location={"source": text_name})]


class _Analyzer(ast.NodeVisitor):
    def __init__(self, result, filename, required, available):
        self.result = result
        self.filename = filename
        self.required = required
        self.available = None if available is None else frozenset(available)
        self.aliases = {}
        self.shadowed = set()  # nomes reatribuidos: nao resolver como modulo
        self.func_depth = 0
        self.conditional = 0
        self.import_guard = 0

    # -- utilidades -------------------------------------------------------
    def _hard(self):
        return self.required and self.func_depth == 0 and self.conditional == 0

    def _emit(self, rule_id, node, message, fix, hard=None, capability=""):
        if hard is None:
            hard = self._hard()
        severity, evidence = ((SEVERITY_ERROR, EVIDENCE_CONFIRMED) if hard
                              else (SEVERITY_WARNING, EVIDENCE_POTENTIAL))
        self.result.findings.append(Finding(
            rule_id, severity, evidence, message, fix=fix,
            location={"source": self.filename, "line": getattr(node, "lineno", None)},
            capability=capability))

    def _resolve(self, node):
        if isinstance(node, ast.Name):
            if node.id in self.shadowed:
                return None
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = self._resolve(node.value)
            return None if base is None else base + "." + node.attr
        return None

    # -- guards de plataforma ---------------------------------------------
    def _const(self, node):
        return node.value if isinstance(node, ast.Constant) else None

    def _guard(self, test):
        """True/False = valor no alvo Web quando resolvivel; None = desconhecido."""
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            v = self._guard(test.operand)
            return None if v is None else not v
        if isinstance(test, ast.BoolOp):
            vals = [self._guard(v) for v in test.values]
            if isinstance(test.op, ast.And):
                if any(v is False for v in vals):
                    return False
                return True if all(v is True for v in vals) else None
            if any(v is True for v in vals):
                return True
            return False if all(v is False for v in vals) else None
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], (ast.Eq, ast.NotEq)):
            left, right = test.left, test.comparators[0]
            for a, b in ((left, right), (right, left)):
                actual = self._target_value(self._resolve(a) if not isinstance(a, ast.Call) else self._call_name(a))
                lit = self._const(b)
                if actual is not None and isinstance(lit, str):
                    same = actual == lit
                    return same if isinstance(test.ops[0], ast.Eq) else not same
            return None
        if (isinstance(test, ast.Call) and isinstance(test.func, ast.Attribute)
                and test.func.attr == "startswith" and len(test.args) == 1
                and self._resolve(test.func.value) == "sys.platform"):
            lit = self._const(test.args[0])
            if isinstance(lit, str):
                return TARGET_PLATFORM.startswith(lit)
            if isinstance(test.args[0], ast.Tuple):
                lits = [self._const(e) for e in test.args[0].elts]
                if all(isinstance(x, str) for x in lits):
                    return any(TARGET_PLATFORM.startswith(x) for x in lits)
        return None

    def _call_name(self, node):
        if node.args or node.keywords:
            return None
        name = self._resolve(node.func)
        return None if name is None else name + "()"

    @staticmethod
    def _target_value(name):
        return {"sys.platform": TARGET_PLATFORM, "os.name": TARGET_OS_NAME,
                "platform.system()": TARGET_PLATFORM_SYSTEM}.get(name)

    # -- estrutura --------------------------------------------------------
    def visit_If(self, node):
        g = self._guard(node.test)
        if g is True:
            for s in node.body:
                self.visit(s)
        elif g is False:
            for s in node.orelse:
                self.visit(s)
        else:
            self.visit(node.test)
            self.conditional += 1
            for s in node.body + node.orelse:
                self.visit(s)
            self.conditional -= 1

    def visit_Try(self, node):
        guarded = any(self._catches_import_error(h) for h in node.handlers)
        if guarded:
            self.import_guard += 1
        for s in node.body:
            self.visit(s)
        if guarded:
            self.import_guard -= 1
        for h in node.handlers:
            self.conditional += 1
            for s in h.body:
                self.visit(s)
            self.conditional -= 1
        for s in node.orelse + node.finalbody:
            self.visit(s)

    visit_TryStar = visit_Try

    def _catches_import_error(self, handler):
        t = handler.type
        if t is None:
            return True
        names = t.elts if isinstance(t, ast.Tuple) else [t]
        return any(isinstance(n, ast.Name) and n.id in _IMPORT_ERRORS for n in names)

    def _visit_function(self, node):
        args = node.args
        for d in node.decorator_list + args.defaults + [d for d in args.kw_defaults if d]:
            self.visit(d)
        saved = (dict(self.aliases), set(self.shadowed))
        for a in args.posonlyargs + args.args + args.kwonlyargs + [x for x in (args.vararg, args.kwarg) if x]:
            self._shadow(a.arg)
        self.func_depth += 1
        for s in node.body:
            self.visit(s)
        self.func_depth -= 1
        self.aliases, self.shadowed = saved

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Lambda(self, node):
        self.func_depth += 1
        self.visit(node.body)
        self.func_depth -= 1

    def _shadow(self, name):
        self.aliases.pop(name, None)
        self.shadowed.add(name)

    def _bind(self, name, target):
        self.shadowed.discard(name)
        self.aliases[name] = target

    def _rebind(self, target):
        for n in ast.walk(target):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                self._shadow(n.id)

    def visit_Assign(self, node):
        self.visit(node.value)
        for t in node.targets:
            self._rebind(t)

    def visit_AugAssign(self, node):
        self.visit(node.value)
        self._rebind(node.target)

    def visit_AnnAssign(self, node):
        if node.value:
            self.visit(node.value)
        self._rebind(node.target)

    def visit_For(self, node):
        self.visit(node.iter)
        self._rebind(node.target)
        for s in node.body + node.orelse:
            self.visit(s)

    def visit_While(self, node):
        infinite = isinstance(node.test, ast.Constant) and bool(node.test.value)
        if infinite and not _has_exit(node.body):
            self._emit("WEB-PY-006", node,
                       "Loop sem saída aparente; pode travar o navegador.",
                       "Executar por frame (controller/component) em vez de um laço bloqueante.",
                       hard=False)
        self.generic_visit(node)

    # -- imports ----------------------------------------------------------
    def visit_Import(self, node):
        for a in node.names:
            top = a.name.split(".")[0]
            self._bind(a.asname or top, a.name if a.asname else top)
            self._check_import(a.name, node)

    def visit_ImportFrom(self, node):
        if node.level:  # relativo: resolvido no pacote do projeto pelo coletor
            return
        for a in node.names:
            self._bind(a.asname or a.name, "%s.%s" % (node.module, a.name))
        self._check_import(node.module, node)
        # `from pkg import util` pode ser submodulo: candidato para o coletor, que so segue
        # o que existe no projeto (nao gera WEB-PY-001 se for um atributo).
        for a in node.names:
            if a.name != "*":
                self.result.imports.append(("%s.%s" % (node.module, a.name),
                                            getattr(node, "lineno", None), self.import_guard > 0))

    def _check_import(self, name, node):
        self.result.imports.append((name, getattr(node, "lineno", None), self.import_guard > 0))
        top = name.split(".")[0]
        if self.import_guard:
            return  # import opcional protegido por try/except ImportError
        if top in EDITOR_MODULES:
            self._emit("WEB-PY-007", node, "Import de %s (API exclusiva do editor)." % top,
                       "Separar a ferramenta de autoria da lógica do jogo.")
        elif self.available is not None and top not in self.available:
            self._emit("WEB-PY-001", node, "Import não resolvido: %s." % name,
                       "Incluir o módulo no pacote ou usar um módulo presente no runtime.")

    # -- chamadas ---------------------------------------------------------
    def visit_Call(self, node):
        name = self._resolve(node.func)
        if name:
            self._check_call(name, node)
        self.generic_visit(node)

    def _check_call(self, name, node):
        if name in _OS_PROCESS or name.startswith(_OS_PROCESS_PREFIXES):
            self._emit("WEB-PY-002", node, "Execução de processo: %s." % name,
                       "Remover do caminho Web ou mover para um serviço externo.")
        elif name in _DLL_CALLS:
            self._emit("WEB-PY-003", node, "Carregamento de biblioteca nativa: %s." % name,
                       "Não há DLL/SO do host no navegador; usar módulo Wasm do runtime.")
        elif name in _THREAD_CALLS:
            self._emit("WEB-PY-004", node, "Criação de thread/processo: %s." % name,
                       "Distribuir o trabalho por frames ou por adaptador validado.")
        elif name in _BLOCKING_CALLS:
            self._emit("WEB-PY-006", node, "Chamada bloqueante em script: %s." % name,
                       "Evitar espera no frame; medir no navegador.", hard=False)
        elif name in _EVAL_CALLS:
            self.result.has_dynamic = True
            self._emit("WEB-PY-009", node, "%s: análise estática cobre só parte do código." % name,
                       "Validar esse caminho no navegador.", hard=False)
        elif name in _IMPORT_CALLS:
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                self._check_import(arg.value, node)
            else:
                self.result.has_dynamic = True
                self._emit("WEB-PY-009", node, "Import dinâmico: análise estática parcial.",
                           "Declarar o módulo explicitamente e validar no navegador.", hard=False)
                self._emit("WEB-PKG-007", node, "Módulo formado dinamicamente não é descoberto.",
                           "Declarar o conjunto adicional de módulos no pacote.", hard=False)


def _has_exit(body):
    """True se o corpo do laco tem break (do proprio laco), return ou raise, sem entrar em defs."""
    def walk(stmts, in_inner_loop):
        for s in stmts:
            if isinstance(s, (ast.Return, ast.Raise)):
                return True
            if isinstance(s, ast.Break) and not in_inner_loop:
                return True
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            inner = in_inner_loop or isinstance(s, (ast.For, ast.AsyncFor, ast.While))
            for field in ("body", "orelse", "finalbody"):
                if walk(getattr(s, field, None) or [], inner):
                    return True
            for h in getattr(s, "handlers", None) or []:
                if walk(h.body, inner):
                    return True
        return False
    return walk(body, False)
