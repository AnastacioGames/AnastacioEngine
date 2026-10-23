"""Desenha os ícones das portas lógicas (AND, OR, NAND, NOR, XOR, XNOR) com a simbologia da
eletrônica digital, nos três estilos de ícone da engine, e grava nos atlas.

- Range (padrão): silhueta branca cheia -> blender_icons16/32/*.dat (recompile depois).
- UPBGE: corpo laranja com contorno escuro, como os ícones coloridos do 2.79.
- Blender 5: traço fino monocromático.

Mesmo esquema de tools/icons/make_cut_icon.py (as imagens de UPBGE e Blender 5 também vão para
tools/upbge_icons/extra e tools/blender5_icons/extra).

Uso: python tools/icons/make_logic_gate_icons.py
"""
import math
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import make_cut_icon as cut  # noqa: E402  (write_dat, atlas, DATAFILES, ROOT)

atlas = cut.atlas
SS = 8
GATES = ("AND", "OR", "NAND", "NOR", "XOR", "XNOR")

IN_Y = (5.5, 10.5)
OUT_Y = 8.0


def bezier(a, c, b, steps=24):
    return [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0],
             (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1])
            for t in (i / steps for i in range(steps + 1))]


def back_x(y, x0):
    """x da curva traseira da porta OR na altura y (bezier com bojo de 2 px para a direita)."""
    t = (y - 3.5) / 9.0
    return x0 + 4.0 * (1 - t) * t


def body(gate):
    """(polígono do corpo, x onde as entradas encostam, x da ponta) na grade 16x16."""
    if gate.startswith("AND") or gate == "NAND":
        x0, xc, r = 2.5, 7.0, 4.5
        arc = [(xc + r * math.cos(a), 8 + r * math.sin(a))
               for a in (math.radians(-90 + 180 * i / 24) for i in range(25))]
        return [(x0, 3.5)] + arc + [(x0, 12.5)], (x0, x0), xc + r
    x0 = 2.5
    top = bezier((x0, 3.5), (8.0, 3.5), (11.5, 8.0))
    bottom = bezier((11.5, 8.0), (8.0, 12.5), (x0, 12.5))
    back = bezier((x0, 12.5), (x0 + 2.0, 8.0), (x0, 3.5))
    return top + bottom[1:] + back[1:-1], (back_x(IN_Y[0], x0), back_x(IN_Y[1], x0)), 11.5


def gate_icon(gate, size, style):
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def p(pt):
        return (pt[0] * n / 16.0, pt[1] * n / 16.0)

    def w(v):
        return max(1, int(round(v * n / 16.0)))

    poly, in_x, tip = body(gate)
    negated = gate in ("NAND", "NOR", "XNOR")
    xor = gate in ("XOR", "XNOR")
    bubble_r = 1.1
    out_x0 = tip + (2 * bubble_r if negated else 0)

    if style == "upbge":
        fg, fill, edge = (26, 26, 26, 255), (232, 128, 32, 255), (26, 26, 26, 255)
    else:
        fg = fill = edge = (255, 255, 255, 255)

    wire = w(1.1 if style != "blender5" else 1.0)
    for y, x in zip(IN_Y, in_x):
        d.line([p((0.3, y)), p((x + 0.3, y))], fill=fg if style == "upbge" else edge, width=wire)
    d.line([p((out_x0 - 0.2, OUT_Y)), p((15.7, OUT_Y))], fill=fg if style == "upbge" else edge, width=wire)
    if xor:
        extra = bezier((0.9, 12.5), (2.9, 8.0), (0.9, 3.5))
        d.line([p(q) for q in extra], fill=edge, width=w(1.0), joint="curve")

    pts = [p(q) for q in poly]
    if style == "blender5":
        d.line(pts + [pts[0]], fill=edge, width=w(1.0), joint="curve")
    elif style == "upbge":
        d.polygon(pts, fill=fill, outline=edge)
        d.line(pts + [pts[0]], fill=edge, width=w(0.8), joint="curve")
    else:
        d.polygon(pts, fill=fill)

    if negated:
        c = (tip + bubble_r, OUT_Y)
        box = [p((c[0] - bubble_r, c[1] - bubble_r)), p((c[0] + bubble_r, c[1] + bubble_r))]
        if style == "upbge":
            d.ellipse(box, fill=fill, outline=edge, width=w(0.6))
        elif style == "blender5":
            d.ellipse(box, outline=edge, width=w(0.9))
        else:
            d.ellipse(box, outline=edge, width=w(0.9))

    return img.resize((size, size), Image.LANCZOS)


def main():
    names = atlas.parse_header(atlas.RANGE_HEADER)
    for gate in GATES:
        name = "GATE_" + gate
        index = next(i for i, (kind, nm) in enumerate(names) if nm == name)
        for size in (16, 32):
            margin = 10 * size // 32
            col, row = index % atlas.GRID_COLS, index // atlas.GRID_COLS
            x = col * (size + margin) + margin
            y_bottom = row * (size + margin) + margin
            cut.write_dat(os.path.join(cut.DATAFILES, "blender_icons%d" % size,
                                       "icon%d_%s.dat" % (size, name.lower())),
                          gate_icon(gate, size, "range"), x, y_bottom, size)
            for style, folder, extra in (("upbge", "icons_upbge", "upbge_icons"),
                                         ("blender5", "icons_blender5", "blender5_icons")):
                img = gate_icon(gate, size, style)
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
