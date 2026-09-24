# Resolucao de dependencias do snapshot (marco C, parte pura). Nao importa bpy: o adaptador
# collect_bpy monta o Snapshot; aqui so se percorre o grafo. Scripts nunca sao importados nem
# executados: so lidos e analisados por AST (rules_python).
#
# Limites: imports relativos nao sao seguidos (o analisador
# registra so o modulo nomeado); import dinamico vira WEB-PKG-007/WEB-PY-009 (aviso).

from .i18n import Msg
from .results import EVIDENCE_CONFIRMED, SEVERITY_ERROR, Finding
from . import rules_files
from . import rules_python

KIND_TEXT = "text"      # controller em modo Script: nome do Text datablock
KIND_MODULE = "module"  # controller em modo Module / component: "pacote.modulo.simbolo"


class Reference:
    """Uma referencia do runtime a um script. `chain` = cadeia legivel ate a origem (Localizar)."""

    __slots__ = ("kind", "target", "chain", "scene", "object", "datablock", "required", "is_module")

    def __init__(self, kind, target, chain, scene="", object="", datablock="", required=True, is_module=False):
        self.kind = kind
        self.target = target
        self.chain = list(chain)
        self.scene = scene
        self.object = object
        self.datablock = datablock
        self.required = required
        self.is_module = is_module  # alvo ja e o modulo (import), nao "modulo.funcao"

    def location(self, **extra):
        d = {"chain": " > ".join(self.chain), "scene": self.scene, "object": self.object,
             "datablock": self.datablock}
        d.update(extra)
        return d


class Snapshot:
    """Entrada da resolucao.

    texts: {nome: fonte} dos Text datablocks.
    find_module: callable(nome_pontilhado) -> (caminho, fonte) | None, para arquivos do projeto.
    project_tops: nomes de topo resolviveis no projeto (pastas/arquivos .py).
    stdlib: nomes de topo do manifesto do runtime; None desliga WEB-PY-001.
    """

    def __init__(self, references, texts=None, find_module=None, project_tops=(), stdlib=None):
        self.references = list(references)
        self.texts = dict(texts or {})
        self.find_module = find_module or (lambda name: None)
        self.project_tops = frozenset(project_tops)
        self.stdlib = None if stdlib is None else frozenset(stdlib)

    def available(self):
        if self.stdlib is None:
            return None
        tops = set(self.stdlib) | self.project_tops
        for name in self.texts:
            tops.add(name[:-3] if name.endswith(".py") else name)
        return tops


def _module_of(target):
    """'pkg.mod.func' -> 'pkg.mod'. Sem ponto, o alvo ja e o modulo."""
    return target.rsplit(".", 1)[0] if "." in target else target


def _missing(ref, what, name):
    message = (Msg("%s was not found: %s.", what, name) if name
               else Msg("Reference without %s set.", what))
    return Finding("WEB-PKG-003", SEVERITY_ERROR, EVIDENCE_CONFIRMED, message,
                   fix="Include the file in the project or fix the controller/component reference.",
                   location=ref.location(source=name))


def _lookup(snapshot, name):
    """Resolve um nome de modulo: Text datablock primeiro (como o motor), depois arquivo do projeto.
    Retorna (rotulo_da_origem, fonte) ou None."""
    for key in (name, name + ".py"):
        if key in snapshot.texts:
            return "Text:" + key, snapshot.texts[key]
    found = snapshot.find_module(name)
    return None if found is None else (found[0], found[1])


def resolve(snapshot):
    """Percorre referencias e imports transitivos. Retorna (findings, visitados), onde visitados
    mapeia chave -> origem, util para o empacotamento (marco F)."""
    findings = []
    visited = {}
    available = snapshot.available()
    queue = []
    for ref in snapshot.references:
        queue.append(ref)

    while queue:
        ref = queue.pop(0)
        if ref.kind == KIND_TEXT:
            name = ref.target
            key = ("text", name)
            found = ("Text:" + name, snapshot.texts[name]) if name in snapshot.texts else None
            what = "Text"
        else:
            name = ref.target if ref.is_module else _module_of(ref.target)
            key = ("module", name)
            found = _lookup(snapshot, name)
            what = Msg("Module")
        if key in visited:
            continue  # ciclo ou alcancado por outro caminho: analisado uma vez
        if found is None:
            top = name.split(".")[0]
            if ref.kind == KIND_MODULE and snapshot.stdlib is not None and top in snapshot.stdlib:
                visited[key] = "runtime"
                continue
            visited[key] = None
            findings.append(_missing(ref, what, name))
            continue
        origin, source = found
        visited[key] = origin
        found_here, imports = _analyze(source, origin, ref, available)
        findings.extend(found_here)
        for imp, _line, guarded in imports:
            # So segue o que existe no projeto; import nao resolvido ja e WEB-PY-001.
            if guarded or _lookup(snapshot, imp) is None:
                continue
            sub = Reference(KIND_MODULE, imp, ref.chain + [imp], ref.scene, ref.object,
                            ref.datablock, ref.required, is_module=True)
            queue.append(sub)
    return findings, visited


def _analyze(source, origin, ref, available):
    result = rules_python.analyze_source(source, origin, required=ref.required,
                                         available_modules=available)
    extra = ref.location()
    for f in result.findings:
        for k, v in extra.items():
            if not f.location.get(k):
                f.location[k] = v
    return result.findings, result.imports


def check_assets(assets, exists, roots=()):
    """WEB-PKG-003/004/005 sobre assets referenciados: [(tipo, caminho_absoluto, origem_dict)].
    `exists(path)` injeta o acesso ao disco; `roots` (opcional) confere symlinks (PKG-005)."""
    findings = []
    for kind, path, origin in assets:
        if not exists(path):
            findings.append(Finding("WEB-PKG-003", SEVERITY_ERROR, EVIDENCE_CONFIRMED,
                                    Msg("%s not found: %s.", kind, path),
                                    fix="Include/replace the asset or fix the reference.",
                                    location=dict(origin, source=path)))
        elif roots:
            findings.extend(rules_files.check_within_roots(path, roots, source=origin.get("chain") or path))
    return findings
