"""Estiliza os glifos de uma pasta de atlas (gerada por text_atlas.py init).

Cada glifo branco vira uma letra pintada (madeira, arcade, boxed, doce...).
Rode o init com --padding grande (>= 10) para caber contorno e sombra.

Uso:
  python tools/text_atlas.py init PASTA --font C:/Windows/Fonts/impact.ttf --size 64 --padding 12
  python tools/text_atlas_style.py PASTA --style madeira
  python tools/text_atlas.py build PASTA --text "Jogar  Opções\\nSair do Jogo"

Os PNGs estilizados substituem glyphs/*.png; os originais brancos ficam em glyphs_base/
(re-estilizar sempre parte da base, então dá para trocar de estilo à vontade).
No jogo, deixe a cor do objeto Text branca: a cor multiplica o atlas.
"""

import argparse
import math
import os
import random
import shutil

from PIL import Image, ImageChops, ImageDraw, ImageFilter


def dilate(mask, r):
    return mask.filter(ImageFilter.MaxFilter(r * 2 + 1)) if r > 0 else mask


def erode(mask, r):
    return mask.filter(ImageFilter.MinFilter(r * 2 + 1)) if r > 0 else mask


def shift(img, dx, dy):
    out = Image.new(img.mode, img.size, 0)
    out.paste(img, (dx, dy))
    return out


def solid(size, color):
    return Image.new("RGBA", size, color)


def vgradient(size, top, bottom, y0=0, y1=None):
    w, h = size
    y1 = h if y1 is None else y1
    img = Image.new("RGBA", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = min(1.0, max(0.0, (y - y0) / max(1, y1 - y0)))
        d.line((0, y, w, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def layer(base, color_img, mask):
    """Compõe color_img recortado por mask sobre base."""
    rgba = color_img.copy()
    rgba.putalpha(ImageChops.multiply(mask, color_img.getchannel("A")))
    base.alpha_composite(rgba)


def wood_texture(size, seed):
    w, h = size
    rnd = random.Random(seed)
    img = vgradient(size, (232, 160, 78, 255), (176, 98, 40, 255))
    px = img.load()
    phase = rnd.uniform(0, 6.28)
    freq = rnd.uniform(0.18, 0.26)
    for y in range(h):
        for x in range(w):
            # veios horizontais ondulados
            g = math.sin(y * freq + math.sin(x * 0.07 + phase) * 2.2 + phase)
            k = 1.0 - 0.18 * max(0.0, g) ** 3 - 0.06 * (rnd.random())
            r, gg, b, a = px[x, y]
            px[x, y] = (int(r * k), int(gg * k), int(b * k), a)
    return img


def style_madeira(mask, cell, baseline, seed):
    size = mask.size
    out = solid(size, (0, 0, 0, 0))
    outline = dilate(mask, 3)
    shadow = shift(dilate(mask, 3), 3, 4).filter(ImageFilter.GaussianBlur(2))
    layer(out, solid(size, (0, 0, 0, 150)), shadow)
    layer(out, solid(size, (58, 30, 12, 255)), outline)
    layer(out, wood_texture(size, seed), mask)
    # bisel: luz em cima/esquerda, sombra embaixo/direita
    inner = erode(mask, 1)
    hi = ImageChops.subtract(inner, shift(inner, 2, 2))
    lo = ImageChops.subtract(inner, shift(inner, -2, -2))
    layer(out, solid(size, (255, 222, 160, 170)), hi)
    layer(out, solid(size, (90, 45, 15, 140)), lo)
    return out


def style_arcade(mask, cell, baseline, seed, pixel=4):
    size = mask.size
    small = mask.resize((size[0] // pixel, size[1] // pixel), Image.BILINEAR)
    small = small.point(lambda v: 255 if v > 100 else 0)
    m = small.resize(size, Image.NEAREST)
    out = solid(size, (0, 0, 0, 0))
    layer(out, solid(size, (25, 18, 40, 255)), shift(dilate(m, pixel), pixel, pixel))
    layer(out, solid(size, (25, 18, 40, 255)), dilate(m, pixel))
    split = baseline - int(cell * 0.28)
    fill = solid(size, (250, 206, 60, 255))
    ImageDraw.Draw(fill).rectangle((0, split, size[0], size[1]), fill=(226, 64, 32, 255))
    layer(out, fill, m)
    return out


def style_boxed(mask, cell, baseline, seed):
    size = mask.size
    out = solid(size, (0, 0, 0, 0))
    ext = mask
    for i in range(1, 7):  # extrusão diagonal roxa
        ext = ImageChops.lighter(ext, shift(mask, i, i))
    layer(out, solid(size, (40, 16, 60, 255)), dilate(ext, 2))
    layer(out, solid(size, (92, 40, 120, 255)), ext)
    layer(out, vgradient(size, (255, 214, 70, 255), (240, 160, 30, 255), 0, baseline), mask)
    return out


def style_doce(mask, cell, baseline, seed):
    size = mask.size
    rnd = random.Random(seed)
    out = solid(size, (0, 0, 0, 0))
    layer(out, solid(size, (150, 20, 40, 255)), dilate(mask, 3))
    layer(out, solid(size, (250, 214, 160, 255)), mask)
    # cobertura escorrendo na parte de cima
    bbox = mask.getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        cover = Image.new("L", size, 0)
        d = ImageDraw.Draw(cover)
        top = y0 + (y1 - y0) * 0.38
        d.rectangle((0, 0, size[0], top), fill=255)
        x = x0
        while x < x1:
            r = rnd.randint(3, 5)
            d.ellipse((x - r, top - r, x + r, top + rnd.randint(r, r * 4)), fill=255)
            x += rnd.randint(7, 12)
        icing = ImageChops.multiply(erode(mask, 2), cover)
        color = rnd.choice([(255, 120, 170), (250, 210, 60), (150, 220, 90), (190, 150, 255)])
        layer(out, solid(size, color + (255,)), icing)
        hi = ImageChops.subtract(icing, shift(icing, 0, 2))
        layer(out, solid(size, (255, 255, 255, 160)), hi)
    return out


STYLES = {"madeira": style_madeira, "arcade": style_arcade, "boxed": style_boxed, "doce": style_doce}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--style", choices=sorted(STYLES), default="madeira")
    args = ap.parse_args()
    import json
    man = json.load(open(os.path.join(args.folder, "manifest.json"), encoding="utf-8"))
    gdir = os.path.join(args.folder, "glyphs")
    bdir = os.path.join(args.folder, "glyphs_base")
    if not os.path.isdir(bdir):
        shutil.copytree(gdir, bdir)
    fn = STYLES[args.style]
    n = 0
    for name in sorted(os.listdir(bdir)):
        if not name.lower().endswith(".png"):
            continue
        mask = Image.open(os.path.join(bdir, name)).convert("RGBA").getchannel("A")
        img = fn(mask, man["cell"], man["baseline"], seed=name)
        img.save(os.path.join(gdir, name))
        n += 1
    print("style %s: %d glifos" % (args.style, n))


if __name__ == "__main__":
    main()
