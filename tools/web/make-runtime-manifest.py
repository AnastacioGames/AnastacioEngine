#!/usr/bin/env python3
"""Gera RangeRuntime.manifest.json ao lado de RangeRuntime.{js,wasm,data} (marco D).

O manifesto descreve o que o RUNTIME comprova (docs/web-profile-validation-plan.md, secao 5);
nao confundir com o manifest.json do pacote gerado por package-web.py.

Fontes, todas do build (nada e executado):
  - hashes e tamanhos dos artefatos;
  - modulos Python: stdlib do python311.zip usado no build (PYTHON_ROOT_DIR do CMakeCache),
    modulos C linkados em libpython3.11.a (simbolos PyInit_*) e modulos internos da engine;
  - capacidades: todas 'unvalidated' ou 'disabled' conforme o preset. Nenhuma vira 'validated'
    aqui: isso exige evidencia de teste (--evidence capacidade=texto).

Uso:
  python tools/web/make-runtime-manifest.py --runtime-dir build-web-release/bin
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "source" / "release" / "scripts" / "modules"))
from range_web import manifest as mf  # noqa: E402

RUNTIME_FILES = ("RangeRuntime.js", "RangeRuntime.wasm", "RangeRuntime.data")
RUNTIME_ID = "web-runtime-release"
PYTHON_VERSION = "3.11"
PYC_MAGIC_3_11 = "a70d0d0a"  # importlib.util.MAGIC_NUMBER do CPython 3.11

# Modulos que existem sem PyInit_* proprio (Modules/config.c e nucleo do interpretador).
CORE_BUILTINS = ("sys", "builtins", "marshal", "_warnings", "_frozen_importlib",
                 "_frozen_importlib_external", "zipimport", "_imp")
# KX_PythonInit.cpp sempre instala ``bge`` como alias de ``Range``. ``aud`` e
# condicionado por WITH_AUDASPACE, portanto nao pode ficar numa lista fixa.
ENGINE_MODULES = ("Range", "bge", "mathutils", "bgl", "blf")

# Estados que independem das opcoes do build. Audio e derivado do CMakeCache.
CAPABILITIES = {
    "threads": ("disabled", "preset sem pthreads; TaskScheduler roda serial"),
    "touch": ("disabled", "sem suporte a toque no runtime atual"),
    "gamepad": ("unvalidated", None),
    "save": ("unvalidated", None),
    "video": ("disabled", "FFmpeg desligado no preset"),
    "network": ("disabled", "sem adapter de rede"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmake_cache_value(build_dir, key):
    cache = build_dir / "CMakeCache.txt"
    if not cache.is_file():
        return None
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(key + ":"):
            return line.split("=", 1)[1].strip()
    return None


def cmake_cache_enabled(build_dir, key):
    """Retorna a opcao booleana do CMake, ou None quando o cache nao a registra."""
    value = cmake_cache_value(build_dir, key)
    if value is None:
        return None
    return value.upper() in ("1", "ON", "TRUE", "YES")


def engine_modules(build_dir):
    modules = set(ENGINE_MODULES)
    if cmake_cache_enabled(build_dir, "WITH_AUDASPACE"):
        modules.add("aud")
    return modules


def capabilities(build_dir):
    caps = {}
    for name, (state, why) in CAPABILITIES.items():
        entry = {"state": state}
        if why:
            entry["note"] = why
        caps[name] = entry

    audaspace = cmake_cache_enabled(build_dir, "WITH_AUDASPACE")
    if audaspace:
        caps["audio"] = {"state": "unvalidated",
                         "note": "Audaspace habilitado no build (WITH_AUDASPACE)."}
    elif audaspace is False:
        caps["audio"] = {"state": "disabled",
                         "note": "Audaspace desabilitado no build (WITH_AUDASPACE=OFF)."}
    else:
        caps["audio"] = {"state": "unvalidated",
                         "note": "CMakeCache nao informa WITH_AUDASPACE; requer teste no navegador."}
    return caps


def stdlib_modules(zip_path):
    tops = set()
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            head = name.split("/")[0]
            if head.endswith((".pyc", ".py")):
                head = head.rsplit(".", 1)[0]
            if head.isidentifier():
                tops.add(head)
    return tops


def linked_c_modules(libpython):
    data = Path(libpython).read_bytes()
    return {m.decode() for m in re.findall(rb"PyInit_([A-Za-z0-9_]+)", data)}


def git_revision():
    try:
        rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                             cwd=REPO_ROOT, text=True).strip())
        return rev, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True


def build(runtime_dir, python_root, evidence):
    for name in RUNTIME_FILES:
        if not (runtime_dir / name).is_file():
            sys.exit("erro: artefato ausente: %s" % (runtime_dir / name))
    root = Path(python_root) if python_root else None
    if root is None:
        found = cmake_cache_value(runtime_dir.parent, "PYTHON_ROOT_DIR")
        root = Path(found) if found else None
    if root is None or not (root / "lib" / "python311.zip").is_file():
        sys.exit("erro: informe --python-root (CPython wasm com lib/python311.zip)")

    build_dir = runtime_dir.parent
    modules = (stdlib_modules(root / "lib" / "python311.zip")
               | linked_c_modules(root / "lib" / "libpython3.11.a")
               | set(CORE_BUILTINS) | engine_modules(build_dir))

    caps = capabilities(build_dir)
    for item in evidence:
        name, _, text = item.partition("=")
        if name not in caps or not text:
            sys.exit("erro: --evidence invalido: %r" % item)
        caps[name] = {"state": "validated", "evidence": text}

    rev, dirty = git_revision()
    return {
        "schema": mf.MANIFEST_SCHEMA,
        "schema_version": mf.MANIFEST_SCHEMA_VERSION,
        "runtime_id": RUNTIME_ID,
        "engine_revision": rev + ("+dirty" if dirty else ""),
        "python": {"version": PYTHON_VERSION, "pyc_magic": PYC_MAGIC_3_11, "modules": sorted(modules)},
        "artifacts": {n: {"bytes": (runtime_dir / n).stat().st_size, "sha256": sha256(runtime_dir / n)}
                      for n in RUNTIME_FILES},
        "capabilities": caps,
        "notes": ["engine_revision e o HEAD ao gerar o manifesto, nao prova qual fonte gerou o wasm.",
                  "python.modules e derivado do python311.zip e dos simbolos PyInit_* de libpython; "
                  "nao foi confirmado por import no navegador."],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runtime-dir", required=True, type=Path)
    ap.add_argument("--python-root", help="raiz do CPython wasm (default: PYTHON_ROOT_DIR do CMakeCache)")
    ap.add_argument("--evidence", action="append", default=[], metavar="CAPACIDADE=TEXTO",
                    help="marca a capacidade como validated citando o teste (repetivel)")
    args = ap.parse_args()

    runtime_dir = args.runtime_dir.resolve()
    data = build(runtime_dir, args.python_root, args.evidence)
    problems = mf.validate_manifest(data)
    if problems:
        sys.exit("erro: manifesto gerado invalido: %s" % problems)
    out = runtime_dir / mf.MANIFEST_FILENAME
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("ok: %s (%d modulos Python)" % (out, len(data["python"]["modules"])))


if __name__ == "__main__":
    main()
