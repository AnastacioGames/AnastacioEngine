"""Monta build/dist/RangeArmor-<versao>-windows-x64.zip a partir do zip da versão anterior.

Do zip anterior vêm os arquivos que não ficam no git: release/launcher/ (Launcher Linux, Launcher.exe e
launcher.py minificado), godot_backup/ e release/tools/ResourceHacker.ini. Do repositório vêm o painel
(tools/rangearmor/source/gui-rs, compilado com cargo build --release) e release/{scripts,data,icons,tools}.
Versão Linux: tools/linux/stage_rangearmor_linux.sh. Ver docs/releases.md.

Uso:
    python tools/stage_rangearmor_windows.py 0.6.1 build/dist/RangeArmor-0.5.4-windows-x64.zip
"""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RA = ROOT / "tools" / "rangearmor"
PANEL = RA / "source" / "gui-rs" / "target" / "release" / "rangearmor_panel.exe"
DIST = ROOT / "build" / "dist"
# Pastas de release/ que o git atualiza; o resto vem do zip anterior.
FROM_GIT = ("scripts", "data", "icons", "tools")
SKIP_NAMES = {"__pycache__", "test_universal_linux.py"}


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    version, previous = sys.argv[1], Path(sys.argv[2])
    if not PANEL.is_file():
        raise SystemExit("painel não compilado: %s" % PANEL)
    root = "RangeArmor-%s-windows-x64" % version
    out = DIST / ("%s.zip" % root)
    files = {}  # caminho dentro da raiz -> bytes
    with zipfile.ZipFile(previous) as old:
        old_root = old.namelist()[0].split("/")[0]
        for name in old.namelist():
            rel = name.split("/", 1)[1]
            if not rel or name.endswith("/"):
                continue
            parts = rel.split("/")
            if parts[0] == "release" and len(parts) > 2 and parts[1] in FROM_GIT and rel != "release/tools/ResourceHacker.ini":
                continue
            files[rel] = old.read(name)
    print("base: %s (%d arquivos de %s)" % (previous.name, len(files), old_root))
    for sub in FROM_GIT:
        for path in sorted((RA / "release" / sub).rglob("*")):
            if path.is_file() and not SKIP_NAMES.intersection(path.parts):
                files["release/%s" % path.relative_to(RA / "release").as_posix()] = path.read_bytes()
    files["RangeArmor Panel.exe"] = PANEL.read_bytes()
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in sorted(files):
            zf.writestr("%s/%s" % (root, rel), files[rel])
    with zipfile.ZipFile(out) as zf:
        bad = [n for n in zf.namelist() if "\\" in n]
    if bad:
        raise SystemExit("ERRO: entrada com '\\' no zip: %s" % bad[0])
    print("%s: %d arquivos" % (out, len(files)))
    print("%s  %s" % (hashlib.sha256(out.read_bytes()).hexdigest(), out.name))


if __name__ == "__main__":
    main()
