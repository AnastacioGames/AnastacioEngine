#!/usr/bin/env python3
"""Gera os atlas de ícones no estilo UPBGE para o layout de ícones da Range.

A UPBGE 0.2.5b (Blender 2.79) embute os atlas `blender_icons16.png` (602x640) e
`blender_icons32.png` (1204x1280) no executável. A grade é a mesma da Range
(26x30 células de 32px com margem de 10px no atlas de 32), mas a ordem dos
ícones segue o `UI_icons.h` da 2.79. Este script:

1. extrai os dois PNGs do `blender.exe` da UPBGE (`tools/upbge-0.2.5b/Release`);
2. lê a ordem da 2.79 (`UI_icons_upbge.h`, cópia do Blender v2.79b) e a ordem
   da Range (`source/source/blender/editors/include/UI_icons.h`);
3. copia cada ícone, pelo nome, da célula da UPBGE para a célula da Range;
4. ícones que só existem na Range usam o desenho da própria Range.

Saída: `source/release/datafiles/icons_upbge/blender_icons{16,32}.png`.

Uso: python tools/upbge_icons/build_upbge_icon_atlas.py [--report]
"""

import io
import os
import re
import struct
import sys

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UPBGE_EXE = os.path.join(ROOT, "tools", "upbge-0.2.5b", "Release", "blender.exe")
UPBGE_HEADER = os.path.join(ROOT, "tools", "upbge_icons", "UI_icons_upbge.h")
RANGE_HEADER = os.path.join(ROOT, "source", "source", "blender", "editors", "include", "UI_icons.h")
RANGE_ICON_DIRS = {
    16: os.path.join(ROOT, "source", "release", "datafiles", "blender_icons16"),
    32: os.path.join(ROOT, "source", "release", "datafiles", "blender_icons32"),
}
OUT_DIR = os.path.join(ROOT, "source", "release", "datafiles", "icons_upbge")

GRID_COLS = 26
GRID_ROWS = 30
ATLAS_SIZES = {16: (602, 640), 32: (1204, 1280)}

# Nomes renomeados entre a 2.79 e o layout 2.8 da Range: nome Range -> nome 2.79.
ALIASES = {
    "ADD": "ZOOMIN",
    "REMOVE": "ZOOMOUT",
    "HIDE_ON": "RESTRICT_VIEW_ON",
    "HIDE_OFF": "RESTRICT_VIEW_OFF",
    "FILE_NEW": "NEW",
    "FILEBROWSER": "FILESEL",
    "SELECT_SET": "BORDER_RECT",
    "TOOL_SETTINGS": "SCRIPTWIN",
    "HAND": "HAND",
    "OBJECT_DATAMODE": "OBJECT_DATAMODE",
    "SNAP_FACE": "SNAP_FACE",
    "SNAP_VOLUME": "SNAP_VOLUME",
    "TRIA_DOWN_BAR": "TRIA_DOWN_BAR",
    "SEQ_STRIP_META": "NLA",
    "PREFERENCES": "PREFERENCES",
    "LIGHT": "LAMP",
    "LIGHT_DATA": "LAMP_DATA",
    "OUTLINER_OB_LIGHT": "OUTLINER_OB_LAMP",
    "OUTLINER_DATA_LIGHT": "OUTLINER_DATA_LAMP",
    "LIGHT_POINT": "LAMP_POINT",
    "LIGHT_SUN": "LAMP_SUN",
    "LIGHT_SPOT": "LAMP_SPOT",
    "LIGHT_HEMI": "LAMP_HEMI",
    "LIGHT_AREA": "LAMP_AREA",
    "OUTLINER_OB_GREASEPENCIL": "GREASEPENCIL",
    "GREASEPENCIL": "GREASEPENCIL",
    "SHADING_SOLID": "SOLID",
    "SHADING_WIRE": "WIRE",
    "SHADING_TEXTURE": "TEXTURE_SHADED",
    "SHADING_RENDERED": "SMOOTH",
    "SHADING_BBOX": "BBOX",
    "DUPLICATE": "GHOST",
    "PROPERTIES": "BUTS",
    "TOPBAR": "INFO",
    "TIME": "TIME",
    "CON_ACTION": "ACTION",
    "RESTRICT_INSTANCED_OFF": "RESTRICT_VIEW_OFF",
    "RESTRICT_INSTANCED_ON": "RESTRICT_VIEW_ON",
    "EXPERIMENTAL": "ERROR",
    "PREVIEW_RANGE": "PREVIEW_RANGE",
    "WORKSPACE": "SPLITSCREEN",
    "FAKE_USER_ON": "PINNED",
    "FAKE_USER_OFF": "UNPINNED",
    "MOUSE_LMB": "HAND",
    "EVENT_A": "KEY_HLT",
}

DEF_RE = re.compile(r"^\s*DEF_ICON(\w*)\((\w+)\)")


def parse_header(path):
    """Ordem dos ícones no enum (índice = posição na grade)."""
    names = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = DEF_RE.match(line)
            if not m:
                continue
            kind, name = m.groups()
            if kind == "_BLANK":
                name = "BLANK_" + name
            names.append((kind, name))
    return names


def extract_upbge_atlases():
    data = open(UPBGE_EXE, "rb").read()
    found = {}
    pos = 0
    sig = b"\x89PNG\r\n\x1a\n"
    while True:
        pos = data.find(sig, pos)
        if pos < 0:
            break
        w, h = struct.unpack(">II", data[pos + 16:pos + 24])
        end = data.find(b"IEND", pos) + 8
        for size, dims in ATLAS_SIZES.items():
            if (w, h) == dims:
                found[size] = Image.open(io.BytesIO(data[pos:end])).convert("RGBA")
        pos += 8
    missing = set(ATLAS_SIZES) - set(found)
    if missing:
        sys.exit("Atlas UPBGE não encontrado no executável: %s" % sorted(missing))
    return found


def cell_box(index, size, atlas_h):
    """Caixa PIL (origem no topo) da célula `index`; a grade conta linhas de baixo para cima."""
    margin = 10 * size // 32
    col = index % GRID_COLS
    row = index // GRID_COLS
    x = col * (size + margin) + margin
    y_bottom = row * (size + margin) + margin
    y = atlas_h - y_bottom - size
    return (x, y, x + size, y + size)


def build_range_atlas(size):
    """Monta o atlas da Range a partir dos `.dat` (mesmo processo do datatoc_icon)."""
    canvas = None
    folder = RANGE_ICON_DIRS[size]
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith(".dat"):
            continue
        raw = open(os.path.join(folder, fname), "rb").read()
        icon_w, icon_h, orig_x, orig_y, canvas_w, canvas_h = struct.unpack("<6I", raw[:24])
        if canvas is None:
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        icon = Image.frombytes("RGBA", (icon_w, icon_h), raw[24:24 + icon_w * icon_h * 4])
        canvas.paste(icon, (orig_x, orig_y))
    # O datatoc grava as linhas de baixo para cima (convenção do ImBuf).
    return canvas.transpose(Image.FLIP_TOP_BOTTOM)


def main():
    report = "--report" in sys.argv
    upbge_names = parse_header(UPBGE_HEADER)
    range_names = parse_header(RANGE_HEADER)
    upbge_index = {}
    for i, (kind, name) in enumerate(upbge_names):
        if kind not in ("_VECTOR",) and i < GRID_COLS * GRID_ROWS:
            upbge_index.setdefault(name, i)

    atlases = extract_upbge_atlases()
    mapped, fallback, empty = [], [], []

    outputs = {}
    for size, src in atlases.items():
        range_atlas = build_range_atlas(size)
        out = Image.new("RGBA", src.size, (0, 0, 0, 0))
        for i, (kind, name) in enumerate(range_names):
            if i >= GRID_COLS * GRID_ROWS or kind in ("_VECTOR", "_BLANK"):
                continue
            src_name = name if name in upbge_index else ALIASES.get(name)
            dst = cell_box(i, size, src.height)
            if src_name in upbge_index:
                out.paste(src.crop(cell_box(upbge_index[src_name], size, src.height)), dst[:2])
                if size == 32:
                    mapped.append(name)
                continue
            own = range_atlas.crop(cell_box(i, size, range_atlas.height))
            if own.getbbox() is not None:
                out.paste(own, dst[:2])
                if size == 32:
                    fallback.append(name)
            elif size == 32:
                empty.append(name)
        outputs[size] = out

    os.makedirs(OUT_DIR, exist_ok=True)
    for size, img in outputs.items():
        img.save(os.path.join(OUT_DIR, "blender_icons%d.png" % size), optimize=True)

    print("UPBGE: %d ícones, desenho da Range: %d, vazios: %d" % (len(mapped), len(fallback), len(empty)))
    if report:
        print("Desenho da Range:", " ".join(fallback))
        print("Vazios:", " ".join(empty))


if __name__ == "__main__":
    main()
