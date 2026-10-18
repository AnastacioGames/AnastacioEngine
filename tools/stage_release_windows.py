"""Monta o pacote Windows portatil da AnastacioEngine em build/release-staging/.

Copia build/bin/ para uma pasta limpa, excluindo logs, arquivos de debug/link
(.pdb/.map/.lib/.exp), ferramentas internas de build (datatoc/makesdna/makesrna/msgfmt),
cenas de teste, a RangeArmor (asset separado) e o cache local do ImGui. Depois zipa
preservando separadores "/" (ZIP extraido no Linux depende disso).

Uso:
    python tools/stage_release_windows.py 0.5.2
"""
import hashlib
import ast
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = ROOT / "build" / "bin"
STAGING_ROOT = ROOT / "build" / "release-staging"
DIST_DIR = ROOT / "build" / "dist"

EXCLUDE_DIR_NAMES = {"__pycache__", "rangearmor", "demos", "Release"}

EXCLUDE_FILE_SUFFIXES = (".pdb", ".map", ".lib", ".exp", ".err")

EXCLUDE_FILE_NAMES = {
    "imgui.ini",
    "untitled.range",
    "untitled.range1",
    "bug_b_depth_padding_test.err",
}

EXCLUDE_FILE_PREFIXES = ("datatoc", "makesdna", "makesrna", "msgfmt")

# Variantes de benchmark do runtime (layer-cache-*, probe-cache-*) e o AnastacioEngine_BakeTest: nao fazem parte do pacote.
EXCLUDE_EXE_SUBSTRINGS = ("layer-cache-", "probe-cache-", "_baketest")


def should_skip(path: Path) -> bool:
    name = path.name
    if path.is_dir():
        return name in EXCLUDE_DIR_NAMES
    if name in EXCLUDE_FILE_NAMES:
        return True
    if path.suffix.lower() in EXCLUDE_FILE_SUFFIXES:
        return True
    lower = name.lower()
    if lower.startswith(EXCLUDE_FILE_PREFIXES):
        return True
    # Keep build logs without catching valid scripts such as logic_to_python.py.
    if lower == "log.txt" or lower.startswith("log_") or (
        lower.startswith("log") and len(lower) > 3 and lower[3].isdigit()
    ):
        return True
    if any(tag in lower for tag in EXCLUDE_EXE_SUBSTRINGS):
        return True
    return False


def copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for entry in sorted(src.iterdir()):
        if should_skip(entry):
            print(f"  skip  {entry.relative_to(BIN_DIR)}")
            continue
        target = dst / entry.name
        if entry.is_dir():
            copy_tree(entry, target)
        else:
            shutil.copy2(entry, target)


def startup_modules(init_py: Path) -> list[str]:
    """Return the literal ``_modules`` list declared by a startup package."""
    tree = ast.parse(init_py.read_text(encoding="utf-8"), filename=str(init_py))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_modules"
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            if not isinstance(value, list) or not all(isinstance(name, str) for name in value):
                break
            return value
    raise RuntimeError(f"Nao foi possivel ler a lista _modules em {init_py}")


def validate_startup_scripts(package_dir: Path) -> None:
    """Reject a package whose startup package imports a missing Python module.

    A missing entry here does not stop the executable from opening, but aborts
    registration of all operators and leaves the splash UI half initialized.
    """
    operators = package_dir / "2.79" / "scripts" / "startup" / "bl_operators"
    init_py = operators / "__init__.py"
    if not init_py.is_file():
        raise RuntimeError(f"Startup bl_operators ausente: {init_py}")
    missing = [name for name in startup_modules(init_py) if not (operators / f"{name}.py").is_file()]
    if missing:
        raise RuntimeError(
            "Pacote incompleto: bl_operators/__init__.py importa modulo(s) ausente(s): "
            + ", ".join(missing)
        )


def validate_ragdoll_scripts(package_dir: Path) -> None:
    """Ensure the bundled Anastacio Ragdoll addon and runtime travel together."""
    scripts = package_dir / "2.79" / "scripts"
    required = (
        scripts / "addons" / "anastacio_ragdoll.py",
        scripts / "modules" / "anastacio_ragdoll_runtime.py",
    )
    missing = [str(path.relative_to(package_dir)) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Pacote incompleto: arquivos do Anastacio Ragdoll ausentes: "
            + ", ".join(missing)
        )


def zip_dir(src: Path, zip_path: Path, arc_root: str) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(src).as_posix()
            arcname = f"{arc_root}/{rel}"
            zf.write(path, arcname)
    for name in zip_path_namelist_with_backslash(zip_path):
        raise SystemExit(f"ERRO: entrada com '\\' no zip: {name}")


def zip_path_namelist_with_backslash(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        return [n for n in zf.namelist() if "\\" in n]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    args = sys.argv[1:]
    no_zip = "--no-zip" in args
    if no_zip:
        args.remove("--no-zip")
    zip_only = "--zip-only" in args
    if zip_only:
        args.remove("--zip-only")
    if len(args) != 1:
        raise SystemExit(
            "uso: python tools/stage_release_windows.py <versao> [--no-zip | --zip-only], ex: 0.5.2"
        )
    version = args[0]

    pkg_name = f"AnastacioEngine-{version}-windows-x64"
    staging_dir = STAGING_ROOT / pkg_name

    if not zip_only:
        if not BIN_DIR.exists():
            raise SystemExit(f"build/bin/ nao existe ({BIN_DIR}); compile RangeEngine primeiro.")
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        print(f"Copiando build/bin/ -> {staging_dir}")
        copy_tree(BIN_DIR, staging_dir)

        if no_zip:
            print(f"--no-zip: pasta pronta em {staging_dir}. Rode stage_release_web.py nela e depois")
            print(f"          este script de novo com --zip-only {version}.")
            return
    elif not staging_dir.exists():
        raise SystemExit(f"{staging_dir} nao existe; rode sem --zip-only primeiro.")

    zip_path = DIST_DIR / f"{pkg_name}.zip"
    try:
        validate_startup_scripts(staging_dir)
        validate_ragdoll_scripts(staging_dir)
    except (OSError, SyntaxError, ValueError, RuntimeError) as ex:
        raise SystemExit(f"ERRO: {ex}")
    if zip_path.exists():
        zip_path.unlink()
    print(f"Compactando {staging_dir} -> {zip_path}")
    zip_dir(staging_dir, zip_path, pkg_name)

    digest = sha256_of(zip_path)
    sums_path = DIST_DIR / "SHA256SUMS.txt"
    line = f"{digest}  {zip_path.name}\n"
    existing = []
    if sums_path.exists():
        existing = [
            l for l in sums_path.read_text(encoding="utf-8").splitlines(keepends=True)
            if not l.strip().endswith(zip_path.name)
        ]
    sums_path.write_text("".join(existing) + line, encoding="utf-8")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"OK: {zip_path} ({size_mb:.1f} MiB)")
    print(f"SHA256: {digest}")
    print(f"Hash gravado em {sums_path}")


if __name__ == "__main__":
    main()
