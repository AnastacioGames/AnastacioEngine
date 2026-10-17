"""Verificador estatico de trabalho repetido por frame no gameengine.

Procura a familia de bugs de 98f54d7f (marca de "mudou" ligada sempre) e lista
suspeitos com arquivo:linha. Heuristico: nao precisa ser perfeito, precisa
achar o caso antigo se ele for recolocado. Plano em docs/auditoria-trabalho-repetido.md.

Regras:
  FLAG  marca m_*modified/dirty/changed/invalid* = true no nivel de topo de uma
        funcao por frame (Update*, Tick*, Apply*, ...) que tem algum if antes:
        a marca deveria estar dentro do ramo que detectou a mudanca.
  CALL  NotifyUpdate/SetModified/Invalidate* no nivel de topo de funcao por frame,
        sem if no caminho.
  LOOP  laco sobre m_objectlist/m_renderlist/m_parentlist em funcao por frame.

Uso:
    python tools/check_trabalho_repetido.py            # varre source/source/gameengine
    python tools/check_trabalho_repetido.py --rules FLAG
    python tools/check_trabalho_repetido.py --selftest # precisa achar o bug de 98f54d7f
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEENGINE = os.path.join(ROOT, "source", "source", "gameengine")

PER_FRAME = re.compile(
    r"(Update|Tick|Apply|Sync|Render|Frame|Process|Calculate|Logic|Step|Refresh|Draw|Cull)",
    re.IGNORECASE)
FUNC_HEADER = re.compile(r"^[\w:<>,\*&\s~]*?\b([A-Za-z_]\w*)::(~?[A-Za-z_]\w*)\s*\([^;{}]*\)\s*(const)?\s*(override)?\s*(\{)?\s*$")
FLAG_SET = re.compile(r"\b(m_\w*(?:modified|dirty|changed|invalid)\w*)\s*=\s*true\s*;", re.IGNORECASE)
CALL = re.compile(r"\b(NotifyUpdate|SetModified|Invalidate\w*)\s*\(")
LOOP = re.compile(r"\bfor\s*\(.*\b(m_objectlist|m_renderlist|m_parentlist)\b")
COND = re.compile(r"\b(if|switch|while|for)\b|\?")


def strip_code(text):
    """Remove comentarios e strings preservando as quebras de linha."""
    def repl(m):
        s = m.group(0)
        if s.startswith("/"):
            return re.sub(r"[^\n]", " ", s)
        return '""'
    pattern = r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\''
    return re.sub(pattern, repl, text, flags=re.DOTALL)


def scan_text(path, text, rules):
    lines = strip_code(text).split("\n")
    findings = []
    depth = 0
    func = None  # (classe, nome, profundidade do corpo, viu_if)
    pending = None
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if depth == 0 and func is None:
            m = FUNC_HEADER.match(line)
            if m:
                pending = (m.group(1), m.group(2))
        opens = line.count("{")
        closes = line.count("}")

        if func is not None:
            cls, name, body_depth, seen_cond = func
            at_top = depth == body_depth
            per_frame = bool(PER_FRAME.search(name))
            if per_frame and at_top:
                if "FLAG" in rules:
                    m = FLAG_SET.search(stripped)
                    if m and seen_cond:
                        findings.append((path, idx, "FLAG", "%s::%s liga %s fora de qualquer if" % (cls, name, m.group(1))))
                if "CALL" in rules and not seen_cond:
                    m = CALL.search(stripped)
                    if m:
                        findings.append((path, idx, "CALL", "%s::%s chama %s sem comparar antes" % (cls, name, m.group(1))))
            if per_frame and "LOOP" in rules:
                m = LOOP.search(stripped)
                if m:
                    findings.append((path, idx, "LOOP", "%s::%s percorre %s" % (cls, name, m.group(1))))
            if COND.search(stripped):
                seen_cond = True
            func = (cls, name, body_depth, seen_cond)

        if pending is not None and opens:
            func = (pending[0], pending[1], depth + 1, False)
            pending = None
        elif pending is not None and stripped and not stripped.startswith(":") and stripped.endswith(";"):
            pending = None

        depth += opens - closes
        if func is not None and depth < func[2]:
            func = None
        if depth < 0:
            depth = 0
    return findings


def scan_tree(base, rules):
    findings = []
    for dirpath, _dirs, files in os.walk(base):
        for fn in files:
            if fn.endswith((".cpp", ".cc", ".c")):
                p = os.path.join(dirpath, fn)
                with open(p, encoding="utf-8", errors="replace") as f:
                    findings += scan_text(os.path.relpath(p, ROOT), f.read(), rules)
    return findings


def selftest():
    rel = "source/source/gameengine/Rasterizer/RAS_BoundingBox.cpp"
    old = subprocess.run(["git", "-C", ROOT, "show", "98f54d7f~1:" + rel],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as f:
        new = f.read()
    hit_old = [x for x in scan_text(rel, old, {"FLAG"}) if "RAS_MeshBoundingBox::Update" in x[3]]
    hit_new = [x for x in scan_text(rel, new, {"FLAG"}) if "RAS_MeshBoundingBox::Update" in x[3]]
    ok = bool(hit_old) and not hit_new
    print("antes de 98f54d7f: %d achado(s); atual: %d" % (len(hit_old), len(hit_new)))
    print("CHECK_TRABALHO_REPETIDO_SELFTEST", "ok" if ok else "FALHOU")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rules", default="FLAG,CALL,LOOP")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("path", nargs="?", default=GAMEENGINE)
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    rules = set(args.rules.upper().split(","))
    findings = scan_tree(args.path, rules)
    for path, line, rule, msg in sorted(findings):
        print("%s:%d: [%s] %s" % (path.replace("\\", "/"), line, rule, msg))
    print("%d suspeito(s)" % len(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
