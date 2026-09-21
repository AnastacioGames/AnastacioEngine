# Coletor bpy do perfil Web (marco C, parte editor). Le o estado do .blend e monta o Snapshot
# consumido por collect.resolve. So le: nao altera dados, nao importa nem executa scripts.
# Roda no thread principal do editor; nao chamar de draw() (plano, secao 7).

import hashlib
import os

import bpy

from . import collect
from . import rules_files
from .results import Report

ASSET_IMAGE = "Imagem"
ASSET_SOUND = "Som"
ASSET_FONT = "Fonte"
ASSET_LIBRARY = "Biblioteca"


def project_root():
    """Pasta do .blend; o motor a coloca no sys.path. Vazio se o arquivo nunca foi salvo."""
    path = bpy.data.filepath
    return os.path.dirname(os.path.abspath(path)) if path else ""


def _abs(path):
    return os.path.normpath(bpy.path.abspath(path)) if path else ""


def _project_tops(root):
    if not root or not os.path.isdir(root):
        return set()
    tops = set()
    for entry in os.listdir(root):
        full = os.path.join(root, entry)
        if entry.endswith(".py"):
            tops.add(entry[:-3])
        elif os.path.isfile(os.path.join(full, "__init__.py")):
            tops.add(entry)
    return tops


def make_finder(root, seen_hashes):
    """find_module(nome) sobre a pasta do projeto: nome/__init__.py ou nome.py. Le como texto
    (nunca importa). `seen_hashes` acumula {caminho: sha256} para o hash do snapshot."""
    def find(name):
        if not root:
            return None
        rel = name.replace(".", os.sep)
        for candidate in (rel + ".py", os.path.join(rel, "__init__.py")):
            path = os.path.join(root, candidate)
            if os.path.isfile(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                except OSError:
                    return None
                seen_hashes[path] = hashlib.sha256(data).hexdigest()
                return path, data.decode("utf-8", errors="replace")
        return None
    return find


def _scene_objects(scenes):
    """(cena, objeto) para toda cena; depois objetos sem cena (pool de spawn). Nada e excluido
    por estar oculto ou inativo no frame inicial."""
    placed = set()
    for scene in scenes:
        for ob in scene.objects:
            placed.add(ob.name)
            yield scene.name, ob
    for ob in bpy.data.objects:
        if ob.name not in placed:
            yield "", ob


def _object_references(scene_name, ob):
    where = [scene_name or "(fora de cena)", ob.name]
    lib = getattr(ob, "library", None)
    lib_path = lib.filepath if lib else ""
    for c in ob.game.controllers:
        if c.type != 'PYTHON':
            continue
        chain = where + [c.name]
        if c.mode == 'MODULE':
            yield collect.Reference(collect.KIND_MODULE, c.module, chain, scene_name, ob.name,
                                    "Controller:%s%s" % (c.name, " @ " + lib_path if lib_path else ""))
        else:
            yield collect.Reference(collect.KIND_TEXT, c.text.name if c.text else "", chain,
                                    scene_name, ob.name,
                                    "Controller:%s%s" % (c.name, " @ " + lib_path if lib_path else ""))
    for comp in ob.game.components:
        yield collect.Reference(collect.KIND_MODULE, comp.module, where + [comp.name],
                                scene_name, ob.name, "Component:%s" % comp.name, is_module=True)


def collect_references(scenes):
    refs = []
    for scene_name, ob in _scene_objects(scenes):
        refs.extend(_object_references(scene_name, ob))
    return refs


def collect_assets():
    """[(tipo, caminho_absoluto, origem)] de arquivos externos referenciados. Ignora dados
    empacotados, gerados e sem uso (nao sobrevivem ao salvar)."""
    assets = []
    for img in bpy.data.images:
        if img.packed_file or img.source not in {'FILE', 'SEQUENCE', 'MOVIE'} or not img.filepath:
            continue
        if img.users == 0:
            continue
        assets.append((ASSET_IMAGE, _abs(img.filepath), {"datablock": "Image:" + img.name,
                                                          "chain": "Imagem > " + img.name}))
    for snd in bpy.data.sounds:
        if snd.packed_file or not snd.filepath or snd.users == 0:
            continue
        assets.append((ASSET_SOUND, _abs(snd.filepath), {"datablock": "Sound:" + snd.name,
                                                          "chain": "Som > " + snd.name}))
    for font in bpy.data.fonts:
        if font.packed_file or not font.filepath or font.filepath.startswith("<"):
            continue
        assets.append((ASSET_FONT, _abs(font.filepath), {"datablock": "Font:" + font.name,
                                                          "chain": "Fonte > " + font.name}))
    for lib in bpy.data.libraries:
        assets.append((ASSET_LIBRARY, _abs(lib.filepath), {"datablock": "Library:" + lib.name,
                                                            "chain": "Biblioteca > " + lib.name}))
    return assets


def build_snapshot(scenes, stdlib=None):
    """Retorna (Snapshot, assets, hashes_de_arquivos)."""
    root = project_root()
    seen = {}
    texts = {t.name: t.as_string() for t in bpy.data.texts}
    snapshot = collect.Snapshot(collect_references(scenes), texts=texts,
                                find_module=make_finder(root, seen),
                                project_tops=_project_tops(root), stdlib=stdlib)
    return snapshot, collect_assets(), seen


def snapshot_hash(snapshot, assets, file_hashes):
    h = hashlib.sha256()
    for ref in snapshot.references:
        h.update(repr((ref.kind, ref.target, ref.scene, ref.object)).encode("utf-8"))
    for name in sorted(snapshot.texts):
        h.update(name.encode("utf-8"))
        h.update(snapshot.texts[name].encode("utf-8"))
    for path in sorted(file_hashes):
        h.update(("%s:%s" % (path, file_hashes[path])).encode("utf-8"))
    for kind, path, _origin in assets:
        h.update(("%s:%s" % (kind, path)).encode("utf-8"))
    return h.hexdigest()


def collect_extra_files(scenes=None, stdlib=None):
    """Arquivos do projeto para o `--extra` do empacotador: modulos .py alcancados pelos
    controllers e assets externos, desde que estejam dentro da pasta do projeto (o caminho
    relativo e mantido via --extra-root). Fora dela nao ha caminho estavel no pacote."""
    scenes = list(scenes if scenes is not None else bpy.data.scenes)
    snapshot, assets, seen = build_snapshot(scenes, stdlib=stdlib)
    collect.resolve(snapshot)
    root = project_root()
    prefix = root + os.sep
    paths = set(seen) | {p for _kind, p, _origin in assets if os.path.isfile(p)}
    return sorted(p for p in paths if p.startswith(prefix))


def collect_report(scenes=None, stdlib=None):
    """Coleta e resolve. `scenes` None = todas as cenas do arquivo. Retorna Report (sem regras
    de renderizacao/midia, que pertencem a marcos posteriores)."""
    scenes = list(scenes if scenes is not None else bpy.data.scenes)
    snapshot, assets, file_hashes = build_snapshot(scenes, stdlib=stdlib)
    # Referencia do runtime a um Text/modulo so e "necessaria" se o objeto existe no pacote;
    # como nada e excluido por estar oculto, todas contam como requeridas.
    report = Report(snapshot_hash(snapshot, assets, file_hashes))
    findings, _visited = collect.resolve(snapshot)
    report.extend(findings)
    # Asset fora da pasta do projeto (ou symlink que escapa) nao entra no pacote: PKG-005.
    report.extend(collect.check_assets(assets, os.path.isfile, roots=(project_root(),)))
    report.extend(_check_package_files(project_root(), assets, file_hashes))
    return report


def _check_package_files(root, assets, module_files):
    """Destinos virtuais (colisao/caixa: PKG-005/006) e tipo de arquivo (PKG-008/009) do que
    entra no pacote: modulos alcancados e assets dentro da pasta do projeto."""
    if not root:
        return []
    prefix = root + os.sep
    paths = set(module_files) | {p for _kind, p, _origin in assets if os.path.isfile(p)}
    inside = sorted(p for p in paths if p.startswith(prefix))
    findings = rules_files.check_destinations(
        [(p[len(prefix):].replace(os.sep, "/"), p) for p in inside])
    for p in inside:
        try:
            with open(p, "rb") as f:
                head = f.read(4)
        except OSError:
            continue  # ilegivel: o empacotador reporta
        findings.extend(rules_files.check_file_kind(os.path.basename(p), head, source=p))
    return findings
