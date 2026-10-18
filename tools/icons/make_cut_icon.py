"""Desenha o ícone CUT (tesoura) nos três estilos de ícone da engine e grava nos atlas.

- Range (padrão): silhueta branca cheia, tingida pelo tema -> blender_icons16/32/*.dat (atlas embutido,
  entra no build pelo datatoc; recompile depois).
- UPBGE: colorido no estilo 2.79 (lâminas cinza metálico, cabos laranja, contorno escuro).
- Blender 5: traço fino monocromático, como os ícones do Blender 5.0.

Os PNGs de UPBGE e Blender 5 são atualizados no lugar (célula do CUT) e as imagens ficam também em
tools/upbge_icons/extra e tools/blender5_icons/extra, que os scripts de montagem dos atlas usam no
lugar do desenho da Range para ícones que só existem aqui.

Uso: python tools/icons/make_cut_icon.py
"""
import math
import os
import struct
import sys

from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATAFILES = os.path.join(ROOT, "source", "release", "datafiles")
sys.path.insert(0, os.path.join(ROOT, "tools", "upbge_icons"))
import build_upbge_icon_atlas as atlas  # noqa: E402  (parse_header, cell_box, GRID_COLS)

NAME = "CUT"
SS = 8  # supersampling
CANVAS = {16: (602, 640), 32: (1204, 1280)}


def scissors(size, style):
    """Imagem RGBA size x size da tesoura no estilo pedido."""
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def p(x, y):  # coordenadas numa grade 16x16
        return (x * n / 16.0, y * n / 16.0)

    def w(v):
        return max(1, int(round(v * n / 16.0)))

    pivot = (8.0, 7.6)
    tips = [(3.2, 1.0), (12.8, 1.0)]
    rings = [(4.4, 12.1), (11.6, 12.1)]

    def blade(tip, width):
        # lâmina afinando da base (no pivô) até a ponta
        ang = math.atan2(tip[1] - pivot[1], tip[0] - pivot[0])
        nx, ny = -math.sin(ang), math.cos(ang)
        base = (pivot[0] + 0.6 * math.cos(ang + math.pi), pivot[1] + 0.6 * math.sin(ang + math.pi))
        return [p(base[0] + nx * width, base[1] + ny * width), p(tip[0], tip[1]),
                p(base[0] - nx * width, base[1] - ny * width)]

    if style == "range":
        white = (255, 255, 255, 255)
        for tip in tips:
            d.polygon(blade(tip, 1.25), fill=white)
        for ring in rings:
            d.line([p(*pivot), p(*ring)], fill=white, width=w(1.6))
            r_out, r_in = 2.5, 1.25
            d.ellipse([p(ring[0] - r_out, ring[1] - r_out), p(ring[0] + r_out, ring[1] + r_out)], fill=white)
            d.ellipse([p(ring[0] - r_in, ring[1] - r_in), p(ring[0] + r_in, ring[1] + r_in)], fill=(0, 0, 0, 0))
        r = 0.55
        d.ellipse([p(pivot[0] - r, pivot[1] - r), p(pivot[0] + r, pivot[1] + r)], fill=(0, 0, 0, 0))

    elif style == "blender5":
        white = (255, 255, 255, 255)
        stroke = w(1.05)
        for tip in tips:
            d.line(blade(tip, 0.95) + [blade(tip, 0.95)[0]], fill=white, width=stroke, joint="curve")
        for ring in rings:
            ang = math.atan2(ring[1] - pivot[1], ring[0] - pivot[0])
            edge = (ring[0] - 2.2 * math.cos(ang), ring[1] - 2.2 * math.sin(ang))
            d.line([p(*pivot), p(*edge)], fill=white, width=stroke)
            r = 2.2
            d.ellipse([p(ring[0] - r, ring[1] - r), p(ring[0] + r, ring[1] + r)], outline=white, width=stroke)
        r = 0.7
        d.ellipse([p(pivot[0] - r, pivot[1] - r), p(pivot[0] + r, pivot[1] + r)], fill=white)

    else:  # upbge: colorido
        dark = (26, 26, 26, 255)
        steel = (214, 218, 224, 255)
        steel_hi = (250, 250, 252, 255)
        orange = (232, 128, 32, 255)
        orange_hi = (255, 176, 84, 255)
        for tip in tips:
            d.polygon(blade(tip, 1.55), fill=dark)
        for tip in tips:
            d.polygon(blade(tip, 1.0), fill=steel)
            d.line([p(*pivot), p(*tip)], fill=steel_hi, width=w(0.45))
        for ring in rings:
            d.line([p(*pivot), p(*ring)], fill=dark, width=w(2.3))
            d.line([p(*pivot), p(*ring)], fill=orange, width=w(1.3))
            r_out, r_in = 2.75, 1.05
            d.ellipse([p(ring[0] - r_out, ring[1] - r_out), p(ring[0] + r_out, ring[1] + r_out)], fill=dark)
            r = r_out - 0.55
            d.ellipse([p(ring[0] - r, ring[1] - r), p(ring[0] + r, ring[1] + r)], fill=orange)
            r = r_out - 1.1
            d.arc([p(ring[0] - r, ring[1] - r), p(ring[0] + r, ring[1] + r)], 200, 290,
                  fill=orange_hi, width=w(0.5))
            d.ellipse([p(ring[0] - r_in - 0.45, ring[1] - r_in - 0.45),
                       p(ring[0] + r_in + 0.45, ring[1] + r_in + 0.45)], fill=dark)
            d.ellipse([p(ring[0] - r_in, ring[1] - r_in), p(ring[0] + r_in, ring[1] + r_in)], fill=(0, 0, 0, 0))
        r = 0.75
        d.ellipse([p(pivot[0] - r, pivot[1] - r), p(pivot[0] + r, pivot[1] + r)], fill=dark)
        r = 0.4
        d.ellipse([p(pivot[0] - r, pivot[1] - r), p(pivot[0] + r, pivot[1] + r)], fill=steel_hi)

    return img.resize((size, size), Image.LANCZOS)


def write_dat(path, img, x, y_bottom, size):
    canvas_w, canvas_h = CANVAS[size]
    head = struct.pack("<6I", size, size, x, y_bottom, canvas_w, canvas_h)
    # datatoc: linhas de baixo para cima
    pixels = img.transpose(Image.FLIP_TOP_BOTTOM).tobytes()
    with open(path, "wb") as fh:
        fh.write(head + pixels)


def main():
    names = atlas.parse_header(atlas.RANGE_HEADER)
    index = next(i for i, (kind, name) in enumerate(names) if name == NAME)
    for size in (16, 32):
        margin = 10 * size // 32
        col, row = index % atlas.GRID_COLS, index // atlas.GRID_COLS
        x = col * (size + margin) + margin
        y_bottom = row * (size + margin) + margin

        write_dat(os.path.join(DATAFILES, "blender_icons%d" % size, "icon%d_cut.dat" % size),
                  scissors(size, "range"), x, y_bottom, size)

        for style, folder, extra in (("upbge", "icons_upbge", "upbge_icons"),
                                     ("blender5", "icons_blender5", "blender5_icons")):
            img = scissors(size, style)
            extra_dir = os.path.join(ROOT, "tools", extra, "extra")
            os.makedirs(extra_dir, exist_ok=True)
            img.save(os.path.join(extra_dir, "%s_%d.png" % (NAME.lower(), size)))
            png = os.path.join(DATAFILES, folder, "blender_icons%d.png" % size)
            sheet = Image.open(png).convert("RGBA")
            box = atlas.cell_box(index, size, sheet.height)
            sheet.paste(Image.new("RGBA", (size, size), (0, 0, 0, 0)), box[:2])
            sheet.paste(img, box[:2])
            sheet.save(png, optimize=True)
        print("CUT %dpx: célula %d (x=%d, y=%d)" % (size, index, x, y_bottom))


if __name__ == "__main__":
    main()
