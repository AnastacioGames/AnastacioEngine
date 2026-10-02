#!/usr/bin/env python3
"""Gera os atlas de ícones no estilo Blender 5.0 para o layout de ícones da Range.

Fonte: `tools/blender5_icons/icons_svg/` (cópia de `release/datafiles/icons_svg` do branch
`blender-v5.0-release`). Cada SVG é rasterizado em 16 e 32 px pelo `render_svgs.cjs`
(`@resvg/resvg-js`, via npm) e colocado, pelo nome, na célula do `UI_icons.h` da Range.
Ícones sem par no Blender 5.0 usam o desenho da própria Range.

Saída: `source/release/datafiles/icons_blender5/blender_icons{16,32}.png`.

Uso:
    npm install --prefix <pasta> @resvg/resvg-js
    python tools/blender5_icons/build_blender5_icon_atlas.py --node-modules <pasta>/node_modules [--report]
"""

import os
import subprocess
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "upbge_icons"))
import build_upbge_icon_atlas as common  # noqa: E402

SVG_DIR = os.path.join(HERE, "icons_svg")
OUT_DIR = os.path.join(common.ROOT, "source", "release", "datafiles", "icons_blender5")

# Nome na Range -> nome do SVG no Blender 5.0.
ALIASES = {
    "GO_LEFT": "BACK",
    "PLUG": "PLUGIN",
    "UI": "WINDOW",
    "FULLSCREEN": "FULLSCREEN_ENTER",
    "SPLITSCREEN": "WORKSPACE",
    "ZOOMIN": "ADD",
    "ZOOMOUT": "REMOVE",
    "LINK_AREA": "LINKED",
    "DOTSUP": "THREE_DOTS",
    "DOTSDOWN": "THREE_DOTS",
    "LINK": "LINKED",
    "INLINK": "LINKED",
    "RENDER_REGION": "SELECT_SET",
    "BORDER_RECT": "SELECT_SET",
    "BORDER_LASSO": "SELECT_SET",
    "NEW": "FILE_NEW",
    "LAMP": "LIGHT",
    "EDIT": "EDITMODE_HLT",
    "RADIO": "RADIOBUT_ON",
    "TEXTURE_SHADED": "SHADING_TEXTURE",
    "IPO": "GRAPH",
    "OOPS": "OUTLINER",
    "BUTS": "PROPERTIES",
    "FILESEL": "FILEBROWSER",
    "IMAGE_COL": "IMAGE",
    "IMASEL": "IMAGE",
    "SCRIPTWIN": "PREFERENCES",
    "CLIP": "TRACKER",
    "FACESEL_HLT": "FACESEL",
    "LIGHTPAINT": "BRUSH_DATA",
    "LAMP_DATA": "LIGHT_DATA",
    "POSE_DATA": "ARMATURE_DATA",
    "LIBRARY_DATA_INDIRECT": "LIBRARY_DATA_DIRECT",
    "RNA_ADD": "RNA",
    "OUTLINER_OB_LAMP": "OUTLINER_OB_LIGHT",
    "OUTLINER_DATA_LAMP": "OUTLINER_DATA_LIGHT",
    "OUTLINER_DATA_POSE": "ARMATURE_DATA",
    "LAMP_POINT": "LIGHT_POINT",
    "LAMP_SUN": "LIGHT_SUN",
    "LAMP_SPOT": "LIGHT_SPOT",
    "LAMP_HEMI": "LIGHT_HEMI",
    "LAMP_AREA": "LIGHT_AREA",
    "META_EMPTY": "EMPTY_DATA",
    "FORCE_SMOKEFLOW": "FORCE_FLUIDFLOW",
    "CONSTRAINT_DATA": "CONSTRAINT",
    "MOD_SMOKE": "MOD_FLUID",
    "PLAY_AUDIO": "PLAY_SOUND",
    "VISIBLE_IPO_OFF": "HIDE_ON",
    "VISIBLE_IPO_ON": "HIDE_OFF",
    "LOOPSEL": "EDGESEL",
    "ROTATE": "ORIENTATION_GIMBAL",
    "ROTATECOLLECTION": "PIVOT_INDIVIDUAL",
    "ROTATECENTER": "PIVOT_MEDIAN",
    "ROTACTIVE": "PIVOT_ACTIVE",
    "ALIGN": "ALIGN_CENTER",
    "SCULPT_DYNTOPO": "SCULPTMODE_HLT",
    "MAN_TRANS": "OBJECT_ORIGIN",
    "MAN_ROT": "ORIENTATION_GIMBAL",
    "MAN_SCALE": "FULLSCREEN_ENTER",
    "MANIPUL": "GIZMO",
    "SNAP_SURFACE": "SNAP_FACE",
    "RETOPO": "MOD_SHRINKWRAP",
    "BBOX": "SHADING_BBOX",
    "WIRE": "SHADING_WIRE",
    "SOLID": "SHADING_SOLID",
    "SMOOTH": "SHADING_RENDERED",
    "ORTHO": "VIEW_ORTHO",
    "NDOF_DOM": "VIEW_PAN",
    "NDOF_TURN": "ORIENTATION_GIMBAL",
    "NDOF_FLY": "VIEW_CAMERA",
    "NDOF_TRANS": "VIEW_PAN",
    "GHOST": "DUPLICATE",
    "SAVE_AS": "CURRENT_FILE",
    "SAVE_COPY": "DUPLICATE",
    "OPEN_RECENT": "TIME",
    "RECOVER_AUTO": "FILE_BACKUP",
    "SAVE_PREFS": "HOME",
    "EXTERNAL_DATA": "EXTERNAL_DRIVE",
    "LOAD_FACTORY": "FILE_REFRESH",
    "HAIR": "CURVES",
    "IMAGEFILE": "FILE_IMAGE",
}


def render_svgs(names, node_modules, work):
    """Rasteriza `names` (sem extensão) em `work/<size>/<name>.png` para 16 e 32 px."""
    script = os.path.join(HERE, "render_svgs.cjs")
    listing = os.path.join(work, "names.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        fh.write("\n".join(names))
    env = dict(os.environ, NODE_PATH=node_modules)
    subprocess.check_call(["node", script, SVG_DIR, listing, work], env=env)


def fit_cell(img, size):
    """Centraliza o ícone (desenhado em escala fixa) numa célula size x size, cortando o excesso."""
    img = img.convert("RGBA")
    cell = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cell.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return cell


def main():
    report = "--report" in sys.argv
    if "--node-modules" not in sys.argv:
        sys.exit(__doc__)
    node_modules = os.path.abspath(sys.argv[sys.argv.index("--node-modules") + 1])

    available = {f[:-4].upper(): f[:-4] for f in os.listdir(SVG_DIR) if f.endswith(".svg")}
    range_names = common.parse_header(common.RANGE_HEADER)
    limit = common.GRID_COLS * common.GRID_ROWS

    plan = {}
    for i, (kind, name) in enumerate(range_names[:limit]):
        if kind in ("_VECTOR", "_BLANK"):
            continue
        src = name if name in available else ALIASES.get(name)
        plan[i] = (name, available.get(src))

    mapped = [n for n, s in plan.values() if s]
    fallback, empty = [], []

    with tempfile.TemporaryDirectory() as work:
        render_svgs(sorted({s for _, s in plan.values() if s}), node_modules, work)
        os.makedirs(OUT_DIR, exist_ok=True)
        for size, dims in common.ATLAS_SIZES.items():
            range_atlas = common.build_range_atlas(size)
            out = Image.new("RGBA", dims, (0, 0, 0, 0))
            for i, (name, src) in plan.items():
                dst = common.cell_box(i, size, dims[1])
                if src:
                    out.paste(fit_cell(Image.open(os.path.join(work, str(size), src + ".png")), size), dst[:2])
                    continue
                own = range_atlas.crop(common.cell_box(i, size, range_atlas.height))
                if own.getbbox() is not None:
                    out.paste(own, dst[:2])
                    if size == 32:
                        fallback.append(name)
                elif size == 32:
                    empty.append(name)
            out.save(os.path.join(OUT_DIR, "blender_icons%d.png" % size), optimize=True)

    print("Blender 5.0: %d ícones, desenho da Range: %d, vazios: %d" % (len(mapped), len(fallback), len(empty)))
    if report:
        print("Desenho da Range:", " ".join(fallback))
        print("Vazios:", " ".join(empty))


if __name__ == "__main__":
    main()
