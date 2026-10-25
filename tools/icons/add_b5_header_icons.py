"""Ícones dos menus da barra da 3D View vindos do Blender 5 (orientações, falloff, snap de aresta).

Rasteriza os SVGs de tools/blender5_icons/icons_svg nas células do UI_icons.h e grava nos três
estilos, como o make_cut_icon.py:
- Range: blender_icons16/32/icon*_<nome>.dat (entra no build pelo datatoc; recompile depois);
- UPBGE e Blender 5: extra/<nome>_<size>.png + célula do atlas atualizada no lugar.

Uso: python tools/icons/add_b5_header_icons.py --node-modules <pasta>/node_modules
"""
import argparse
import os
import subprocess
import sys
import tempfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_cut_icon as cut  # noqa: E402  (atlas, write_dat, ROOT, DATAFILES)

atlas = cut.atlas
SVG_DIR = os.path.join(cut.ROOT, "tools", "blender5_icons", "icons_svg")
RENDER = os.path.join(cut.ROOT, "tools", "blender5_icons", "render_svgs.cjs")

NAMES = (
    "INVERSESQUARECURVE",
    "ORIENTATION_GLOBAL",
    "ORIENTATION_LOCAL",
    "ORIENTATION_NORMAL",
    "ORIENTATION_GIMBAL",
    "ORIENTATION_VIEW",
    "SNAP_MIDPOINT",
    "SNAP_PERPENDICULAR",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node-modules", required=True)
    args = parser.parse_args()

    header = atlas.parse_header(atlas.RANGE_HEADER)
    with tempfile.TemporaryDirectory() as tmp:
        listing = os.path.join(tmp, "names.txt")
        with open(listing, "w") as fh:
            fh.write("\n".join(n.lower() for n in NAMES))
        env = dict(os.environ, NODE_PATH=args.node_modules)
        subprocess.check_call(["node", RENDER, SVG_DIR, listing, tmp], env=env)

        for name in NAMES:
            index = next(i for i, (kind, n) in enumerate(header) if n == name)
            for size in (16, 32):
                img = Image.open(os.path.join(tmp, str(size), name.lower() + ".png")).convert("RGBA")
                img = img.crop((0, 0, size, size)) if img.size != (size, size) else img
                margin = 10 * size // 32
                x = (index % atlas.GRID_COLS) * (size + margin) + margin
                y_bottom = (index // atlas.GRID_COLS) * (size + margin) + margin
                cut.write_dat(os.path.join(cut.DATAFILES, "blender_icons%d" % size,
                                           "icon%d_%s.dat" % (size, name.lower())), img, x, y_bottom, size)

                for folder, extra in (("icons_upbge", "upbge_icons"), ("icons_blender5", "blender5_icons")):
                    extra_dir = os.path.join(cut.ROOT, "tools", extra, "extra")
                    os.makedirs(extra_dir, exist_ok=True)
                    img.save(os.path.join(extra_dir, "%s_%d.png" % (name.lower(), size)))
                    png = os.path.join(cut.DATAFILES, folder, "blender_icons%d.png" % size)
                    sheet = Image.open(png).convert("RGBA")
                    box = atlas.cell_box(index, size, sheet.height)
                    sheet.paste(Image.new("RGBA", (size, size), (0, 0, 0, 0)), box[:2])
                    sheet.paste(img, box[:2])
                    sheet.save(png, optimize=True)
            print("%s: célula %d" % (name, index))


if __name__ == "__main__":
    main()
