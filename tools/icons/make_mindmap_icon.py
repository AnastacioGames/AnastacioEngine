"""Desenha o ícone MINDMAP (ideia central ligada a três ideias) nos três estilos de ícone da engine.

Mesmo fluxo de make_cut_icon.py: .dat da Range (recompile depois) e células dos atlas UPBGE e
Blender 5, com cópias em tools/upbge_icons/extra e tools/blender5_icons/extra.

Uso: python tools/icons/make_mindmap_icon.py
"""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_cut_icon as base  # noqa: E402  (write_dat, atlas, DATAFILES, ROOT)

NAME = "MINDMAP"
SS = base.SS

CENTER = (5.2, 8.0, 2.6, 1.9)  # x, y, meia largura, meia altura (grade 16x16)
LEAVES = [(13.2, 2.9), (13.6, 8.0), (13.2, 13.1)]
LEAF = (1.9, 1.35)


def mindmap(size, style):
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def p(x, y):
        return (x * n / 16.0, y * n / 16.0)

    def w(v):
        return max(1, int(round(v * n / 16.0)))

    def box(cx, cy, hw, hh, grow=0.0):
        return [p(cx - hw - grow, cy - hh - grow), p(cx + hw + grow, cy + hh + grow)]

    def branch(leaf, width, color):
        # curva suave da borda da ideia central até a folha
        x0, y0 = CENTER[0] + CENTER[2] - 0.3, CENTER[1]
        x1, y1 = leaf[0] - LEAF[0] + 0.2, leaf[1]
        pts = []
        for i in range(17):
            t = i / 16.0
            pts.append(p(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t * t * (3 - 2 * t)))
        d.line(pts, fill=color, width=width, joint="curve")

    if style == "range":
        white = (255, 255, 255, 255)
        for leaf in LEAVES:
            branch(leaf, w(1.15), white)
        d.rounded_rectangle(box(*CENTER), radius=w(1.1), fill=white)
        for leaf in LEAVES:
            d.rounded_rectangle(box(leaf[0], leaf[1], *LEAF), radius=w(0.7), fill=white)

    elif style == "blender5":
        white = (255, 255, 255, 255)
        stroke = w(1.0)
        for leaf in LEAVES:
            branch(leaf, stroke, white)
        d.rounded_rectangle(box(*CENTER, grow=-0.3), radius=w(1.0), outline=white, width=stroke)
        for leaf in LEAVES:
            d.rounded_rectangle(box(leaf[0], leaf[1], *LEAF, grow=-0.3), radius=w(0.6), fill=white)

    else:  # upbge: colorido
        dark = (26, 26, 26, 255)
        line = (200, 200, 200, 255)
        center_fill, center_hi = (232, 128, 32, 255), (255, 176, 84, 255)
        leaf_colors = [(90, 170, 240, 255), (110, 200, 120, 255), (240, 200, 70, 255)]
        for leaf in LEAVES:
            branch(leaf, w(2.0), dark)
        for leaf in LEAVES:
            branch(leaf, w(0.9), line)
        d.rounded_rectangle(box(*CENTER, grow=0.5), radius=w(1.4), fill=dark)
        d.rounded_rectangle(box(*CENTER), radius=w(1.1), fill=center_fill)
        d.line([p(CENTER[0] - 1.5, CENTER[1] - 1.1), p(CENTER[0] + 1.5, CENTER[1] - 1.1)],
               fill=center_hi, width=w(0.5))
        for leaf, color in zip(LEAVES, leaf_colors):
            d.rounded_rectangle(box(leaf[0], leaf[1], *LEAF, grow=0.5), radius=w(0.9), fill=dark)
            d.rounded_rectangle(box(leaf[0], leaf[1], *LEAF), radius=w(0.6), fill=color)

    return img.resize((size, size), Image.LANCZOS)


def main():
    atlas = base.atlas
    names = atlas.parse_header(atlas.RANGE_HEADER)
    index = next(i for i, (kind, name) in enumerate(names) if name == NAME)
    for size in (16, 32):
        margin = 10 * size // 32
        col, row = index % atlas.GRID_COLS, index // atlas.GRID_COLS
        x = col * (size + margin) + margin
        y_bottom = row * (size + margin) + margin

        base.write_dat(os.path.join(base.DATAFILES, "blender_icons%d" % size, "icon%d_mindmap.dat" % size),
                       mindmap(size, "range"), x, y_bottom, size)

        for style, folder, extra in (("upbge", "icons_upbge", "upbge_icons"),
                                     ("blender5", "icons_blender5", "blender5_icons")):
            img = mindmap(size, style)
            extra_dir = os.path.join(base.ROOT, "tools", extra, "extra")
            os.makedirs(extra_dir, exist_ok=True)
            img.save(os.path.join(extra_dir, "%s_%d.png" % (NAME.lower(), size)))
            png = os.path.join(base.DATAFILES, folder, "blender_icons%d.png" % size)
            sheet = Image.open(png).convert("RGBA")
            cell = atlas.cell_box(index, size, sheet.height)
            sheet.paste(Image.new("RGBA", (size, size), (0, 0, 0, 0)), cell[:2])
            sheet.paste(img, cell[:2])
            sheet.save(png, optimize=True)
        print("MINDMAP %dpx: célula %d (x=%d, y=%d)" % (size, index, x, y_bottom))

    # prévia ampliada para conferir
    prev = Image.new("RGBA", (3 * 136, 136), (60, 60, 60, 255))
    for i, style in enumerate(("range", "upbge", "blender5")):
        prev.paste(mindmap(32, style).resize((128, 128), Image.NEAREST), (i * 136 + 4, 4),
                   mindmap(32, style).resize((128, 128), Image.NEAREST))
    prev.save(os.path.join(os.environ.get("MINDMAP_PREVIEW_DIR", "."), "mindmap_icon_preview.png"))


if __name__ == "__main__":
    main()
