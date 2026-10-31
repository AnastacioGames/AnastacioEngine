"""Verificador da cascata de uma propriedade nova (física, logic bricks, API).

Quando entra um campo novo (ex.: postura do Character), ele precisa aparecer
em várias camadas. Este script lê o diff, acha o que foi criado e mostra em
qual camada cada coisa ainda falta.

O que ele detecta no diff:
  - RNA_def_property(srna, "id", ...) novo em makesrna/intern/rna_*.c
  - EXP_PYATTRIBUTE_*("nome", ...) novo no gameengine (API Python do jogo)

Camadas conferidas para cada propriedade RNA (pelo id RNA e pelo campo DNA):
  DNA        campo existe em makesdna/DNA_*.h
  versioning padrão não-zero tem do_versions (versioning_upbge.c)  [aviso]
  UI         painel (bl_ui/properties_*.py, logic_window.c ou FlowMenu)
  FlowMenu   flowmenu/custom_pt_*.py                     (só física)
  conversor  campo DNA lido no gameengine (C++)
  bricks→py  bl_operators/logic_to_python.py             (só bricks)
  LogicTree  range_logic_tree.py                         (só bricks)
  tradução   nome/descrição em range_web/translations_*.py
  changelog  docs/changelog.md cita o id ou o nome

Para atributos Python do jogo:
  API docs   D:\\AnastacioDocs\\inventario\\api_inventario.json (se existir)
  logic→py   logic_to_python.py usa o atributo (aviso, nem todo atributo precisa)

Uso:
    python tools/check_cascata.py                 # último commit + mudanças locais
    python tools/check_cascata.py HEAD~5          # tudo desde HEAD~5
    python tools/check_cascata.py --prop crouch_speed --prop character_posture
    python tools/check_cascata.py --selftest
No final roda tools/check_docs.py (mapas com linha velha); --no-docs pula.
Saída: 0 = tudo coberto; 1 = falta camada obrigatória ou erro no check_docs.
"""
import argparse
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "source")
SCRIPTS = os.path.join(ROOT, "source", "release", "scripts")
DOCS_REPO = r"D:\AnastacioDocs"

BRICK_RNA = ("rna_actuator.c", "rna_sensor.c", "rna_controller.c")
PHYS_FUNCS = re.compile(r"game|physics|character|soft_body|collision|rigid", re.I)


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


class Corpus:
    """Textos de cada camada, lidos uma vez."""

    def __init__(self):
        def cat(pattern):
            return "\n".join(read(p) for p in glob.glob(os.path.join(ROOT, pattern), recursive=True))

        self.dna = cat("source/source/blender/makesdna/DNA_*.h")
        self.versioning = read(os.path.join(SRC, "blender/blenloader/intern/versioning_upbge.c"))
        self.ui_py = cat("source/release/scripts/startup/bl_ui/properties_*.py")
        self.logic_window = read(os.path.join(SRC, "blender/editors/space_logic/logic_window.c"))
        self.flowmenu = cat("source/release/scripts/startup/flowmenu/*.py")
        self.gameengine = cat("source/source/gameengine/**/*.cpp") + cat("source/source/gameengine/**/*.h")
        self.logic_to_python = read(os.path.join(SCRIPTS, "startup/bl_operators/logic_to_python.py"))
        self.logic_tree = read(os.path.join(SCRIPTS, "startup/range_logic_tree.py"))
        self.translations = cat("source/release/scripts/modules/range_web/translations_*.py")
        self.changelog = read(os.path.join(ROOT, "docs/changelog.md"))
        inv = os.path.join(DOCS_REPO, "inventario", "api_inventario.json")
        self.api_docs = read(inv) if os.path.exists(inv) else None


def word(name, text):
    return re.search(r"(?<![\w])" + re.escape(name) + r"(?![\w])", text) is not None


def quoted(name, text):
    return ('"%s"' % name) in text or ("'%s'" % name) in text


# ---------------------------------------------------------------- diff

def git(*args):
    return subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def diff_text(base, include_worktree):
    out = git("diff", "-U40", "--function-context", base, "HEAD", "--",
              "source/source/blender/makesrna", "source/source/gameengine")
    if include_worktree:
        out += git("diff", "-U40", "--function-context", "HEAD", "--",
                   "source/source/blender/makesrna", "source/source/gameengine")
    return out


RNA_DEF = re.compile(r'RNA_def_property\(\s*\w+\s*,\s*"(\w+)"')
SDNA = re.compile(r'RNA_def_property_\w*sdna\(\s*\w+\s*,\s*\w+\s*,\s*"(\w+)"')
UI_TEXT = re.compile(r'RNA_def_property_ui_text\(\s*\w+\s*,\s*"([^"]*)"\s*,\s*"([^"]*)')
DEFAULT = re.compile(r'RNA_def_property_\w+_default\(\s*\w+\s*,\s*([^)]+)\)')
PYATTR = re.compile(r'EXP_PYATTRIBUTE_\w+\(\s*"(\w+)"\s*,\s*(\w+)')
FUNC = re.compile(r'^\s*(?:static\s+)?void\s+(rna_def_\w+)\s*\(')


def parse_diff(text):
    """Devolve (props, pyattrs). props: dicts com id, dna, ui, desc, default, file, func."""
    props, pyattrs = [], []
    cur_file, cur_func, cur, stmt = None, None, None, ""
    for line in text.splitlines():
        if line.startswith("+++ "):
            cur_file = os.path.basename(line[6:].strip())
            cur_func, cur = None, None
            continue
        if line.startswith("@@"):
            m = re.search(r"@@.*@@\s*(.*)", line)
            fm = FUNC.match(m.group(1)) if m else None
            if fm:
                cur_func = fm.group(1)
            continue
        body = line[1:] if line[:1] in "+- " else line
        fm = FUNC.match(body)
        if fm:
            cur_func = fm.group(1)
        added = line.startswith("+")
        m = RNA_DEF.search(body)
        if m:
            stmt = ""
            cur = {"id": m.group(1), "dna": None, "ui": None, "desc": None, "default": None,
                   "file": cur_file, "func": cur_func or ""} if added else None
            if cur:
                props.append(cur)
            continue
        if cur and added:
            stmt += body.strip() + " "
            if ";" not in body:
                continue  # chamada em várias linhas
            stmt = re.sub(r'"\s+"', "", stmt)  # junta "a" "b"
            if SDNA.search(stmt):
                cur["dna"] = SDNA.search(stmt).group(1)
            elif UI_TEXT.search(stmt):
                cur["ui"], cur["desc"] = UI_TEXT.search(stmt).groups()
            elif DEFAULT.search(stmt):
                cur["default"] = DEFAULT.search(stmt).group(1).strip()
            stmt = ""
        if added:
            for m in PYATTR.finditer(body):
                pyattrs.append({"name": m.group(1), "cls": m.group(2), "file": cur_file})
    seen, uniq = set(), []
    for p in props:
        if p["id"] not in seen:
            seen.add(p["id"])
            uniq.append(p)
    return uniq, pyattrs


def find_prop_in_rna(prop_id):
    """Para --prop: acha a definição no código atual."""
    for path in glob.glob(os.path.join(SRC, "blender/makesrna/intern/rna_*.c")):
        lines = read(path).splitlines()
        func = ""
        for i, l in enumerate(lines):
            fm = FUNC.match(l)
            if fm:
                func = fm.group(1)
            m = RNA_DEF.search(l)
            if m and m.group(1) == prop_id:
                chunk = "\n".join("+" + x for x in lines[i:i + 12])
                p, _ = parse_diff("+++ b/" + os.path.basename(path) + "\n@@ @@ void %s(\n" % func + chunk)
                if p:
                    p[0]["func"] = func
                    return p[0]
    return {"id": prop_id, "dna": None, "ui": None, "desc": None, "default": None, "file": "?", "func": ""}


# ---------------------------------------------------------------- checks

def kind_of(p):
    if p["file"] in BRICK_RNA:
        return "brick"
    if PHYS_FUNCS.search(p["func"] or ""):
        return "physics"
    return "other"


def nonzero_default(d):
    if d is None:
        return False
    d = d.replace("f", "").strip()
    return d not in ("0", "0.0", "false", "FALSE", "NULL", "\"\"")


def check_prop(p, c):
    k = kind_of(p)
    pid, dna = p["id"], p["dna"]
    rows = []  # (camada, estado, obrigatório)  estado: True/False/None(n/a)

    rows.append(("DNA", bool(dna) and word(dna, c.dna) if dna else None, True))
    if nonzero_default(p["default"]) and dna:
        rows.append(("versioning", word(dna, c.versioning), False))
    ui = quoted(pid, c.ui_py) or quoted(pid, c.logic_window) or quoted(pid, c.flowmenu)
    rows.append(("UI", ui, True))
    if k == "physics":
        rows.append(("FlowMenu", quoted(pid, c.flowmenu) or word(pid, c.flowmenu), True))
    if dna:
        rows.append(("conversor", word(dna, c.gameengine), True))
    if k == "brick":
        rows.append(("bricks→py", word(pid, c.logic_to_python), True))
        rows.append(("LogicTree", quoted(pid, c.logic_tree), False))
    if p["ui"]:
        tr = quoted(p["ui"], c.translations)
        if p["desc"]:
            tr = tr and (p["desc"][:40] in c.translations)
        rows.append(("tradução", tr, True))
    rows.append(("changelog", word(pid, c.changelog) or bool(p["ui"] and p["ui"] in c.changelog), False))
    return k, rows


def check_pyattr(a, c):
    rows = []
    if c.api_docs is not None:
        rows.append(("API docs", quoted(a["name"], c.api_docs) or word(a["name"], c.api_docs), True))
    rows.append(("logic→py", word(a["name"], c.logic_to_python), False))
    rows.append(("changelog", word(a["name"], c.changelog), False))
    return rows


def fmt(rows):
    parts = []
    for name, ok, req in rows:
        mark = "ok" if ok else ("FALTA" if req else "aviso")
        parts.append("%s:%s" % (name, mark))
    return "  ".join(parts)


def report(props, pyattrs, c):
    bad = False
    if not props and not pyattrs:
        print("Nada novo de RNA ou API Python no intervalo.")
        return 0
    for p in props:
        k, rows = check_prop(p, c)
        miss = [r for r in rows if not r[1] and r[2]]
        bad |= bool(miss)
        print("%-24s %-8s %s" % (p["id"], k, fmt(rows)))
    for a in pyattrs:
        rows = check_pyattr(a, c)
        bad |= any(not r[1] and r[2] for r in rows)
        print("%-24s %-8s %s" % ("%s.%s" % (a["cls"], a["name"]), "python", fmt(rows)))
    if c.api_docs is None:
        print("(D:\\AnastacioDocs não achado: camada 'API docs' pulada)")
    print("\nFALTA = obrigatória; aviso = confira se se aplica.")
    return 1 if bad else 0


def selftest(c):
    # Postura do Character: commits a6978945 (física) e d0ef39da/c9485774 (brick)
    names = ["crouch_speed", "crawl_speed", "use_auto_crouch", "posture_property", "character_posture"]
    props = [find_prop_in_rna(n) for n in names]
    ok = True
    for p in props:
        k, rows = check_prop(p, c)
        need = [r for r in rows if r[2]]
        print("%-20s %-8s %s" % (p["id"], k, fmt(rows)))
        if not p["dna"] or not all(r[1] for r in need):
            ok = False
    # sanidade do parser de diff
    sample = git("show", "--function-context", "-U40", "a6978945", "--",
                 "source/source/blender/makesrna")
    got = {p["id"] for p in parse_diff(sample)[0]}
    if not {"crouch_speed", "use_auto_crouch"} <= got:
        print("parser do diff não achou as props de a6978945:", got)
        ok = False
    # um caso que tem que falhar
    fake = {"id": "zz_inexistente", "dna": "zz_inexistente", "ui": "Zz Nada", "desc": None,
            "default": "1.0f", "file": "rna_actuator.c", "func": "rna_def_motion_actuator"}
    if all(r[1] for r in check_prop(fake, c)[1] if r[2]):
        print("caso falso passou (deveria falhar)")
        ok = False
    print("SELFTEST", "OK" if ok else "FALHOU")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", nargs="?", default="HEAD~1", help="commit base (padrão HEAD~1)")
    ap.add_argument("--prop", action="append", default=[], help="conferir um id RNA específico")
    ap.add_argument("--no-worktree", action="store_true", help="ignorar mudanças não commitadas")
    ap.add_argument("--no-docs", action="store_true", help="não rodar tools/check_docs.py no final")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    c = Corpus()
    if a.selftest:
        return selftest(c)
    if a.prop:
        return report([find_prop_in_rna(n) for n in a.prop], [], c)
    props, pyattrs = parse_diff(diff_text(a.base, not a.no_worktree))
    rc = report(props, pyattrs, c)
    if not a.no_docs:
        rc |= check_docs()
    return rc


def check_docs():
    """Roda tools/check_docs.py: mapas de código com linha velha, links quebrados."""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_docs.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    errs = [l for l in lines if l.startswith("ERRO")]
    print("\ncheck_docs: " + (lines[-1] if lines else "sem saída"))
    for l in errs[:10]:
        print("  " + l)
    if errs:
        print("  -> mapas: python tools/check_docs.py --fix")
    return 1 if errs or r.returncode else 0


if __name__ == "__main__":
    sys.exit(main())
