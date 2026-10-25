"""Ícone MATERIAL_NODES (botão Material com PBR ligado): o MATERIAL_DATA de cada estilo com o
cinza de dentro levemente amarelado. Grava nos três estilos, como o add_b5_header_icons.py.

Uso: python tools/icons/make_material_pbr_icon.py
"""
import os
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_cut_icon as cut  # noqa: E402

atlas = cut.atlas
SRC, DST = "MATERIAL_DATA", "MATERIAL_NODES"
YELLOW = (255, 200, 60)


def read_dat(path):
    with open(path, "rb") as fh:
        data = fh.read()
    w, h = struct.unpack("<2I", data[:8])
    img = Image.frombytes("RGBA", (w, h), data[24:24 + w * h * 4])
    return img.transpose(Image.FLIP_TOP_BOTTOM)


def tint(img):
    # mesmo desenho e degradê; só o cinza de dentro puxa para o amarelo (o branco do contorno fica branco)
    out = img.copy()
    px = out.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b, a = px[x, y]
            # o cinza vem de branco translúcido (Range) ou de cor escura (outros estilos)
            lum = (r + g + b) / 3.0
            t = max(min(max((245.0 - lum) / 50.0, 0.0), 1.0), min(max((235.0 - a) / 60.0, 0.0), 1.0)) * 0.75
            k = lum / 255.0
            px[x, y] = (int(r + (255 * k - r) * t), int(g + (225 * k - g) * t), int(b + (70 * k - b) * t), a)
    return out


def main():
    header = atlas.parse_header(atlas.RANGE_HEADER)
    src_i = next(i for i, (k, n) in enumerate(header) if n == SRC)
    dst_i = next(i for i, (k, n) in enumerate(header) if n == DST)
    for size in (16, 32):
        folder = os.path.join(cut.DATAFILES, "blender_icons%d" % size)
        img = tint(read_dat(os.path.join(folder, "icon%d_%s.dat" % (size, SRC.lower()))))
        margin = 10 * size // 32
        x = (dst_i % atlas.GRID_COLS) * (size + margin) + margin
        y_bottom = (dst_i // atlas.GRID_COLS) * (size + margin) + margin
        cut.write_dat(os.path.join(folder, "icon%d_%s.dat" % (size, DST.lower())), img, x, y_bottom, size)

        for style, extra in (("icons_upbge", "upbge_icons"), ("icons_blender5", "blender5_icons")):
            png = os.path.join(cut.DATAFILES, style, "blender_icons%d.png" % size)
            sheet = Image.open(png).convert("RGBA")
            sbox = atlas.cell_box(src_i, size, sheet.height)
            img = tint(sheet.crop(sbox))
            img.save(os.path.join(cut.ROOT, "tools", extra, "extra", "%s_%d.png" % (DST.lower(), size)))
            box = atlas.cell_box(dst_i, size, sheet.height)
            sheet.paste(Image.new("RGBA", (size, size), (0, 0, 0, 0)), box[:2])
            sheet.paste(img, box[:2])
            sheet.save(png, optimize=True)
        print("%d px ok" % size)


if __name__ == "__main__":
    main()
