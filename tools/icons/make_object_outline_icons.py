"""Redesenha os ícones de tipo de objeto do estilo Range (OUTLINER_OB_*) como contorno.

As silhuetas cheias ficavam pesadas com a cor de tema "Object" (laranja). Aqui cada silhueta vira
um traço: a forma é ampliada, binarizada, erodida e o miolo é removido, preservando furos e
detalhes internos. O ícone de Mesh já era contorno.

Lê e grava blender_icons16/32/*.dat (recompile depois). Com --preview só gera uma imagem de
comparação em vez de gravar.

Uso: python tools/icons/make_object_outline_icons.py [--preview saida.png]
"""
import os
import struct
import sys

from PIL import Image, ImageChops, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
import make_cut_icon as cut  # noqa: E402  (write_dat, DATAFILES)

# Só as silhuetas largas; as que já são traço (Empty, Curve, Armature, Font, Force Field) e a
# câmera, cheia de detalhes internos, ficam como estão.
ICONS = (
    "OUTLINER_OB_LATTICE", "OUTLINER_OB_META", "OUTLINER_OB_LAMP", "OUTLINER_OB_SURFACE",
    "OUTLINER_OB_SPEAKER", "OUTLINER_OB_GROUP_INSTANCE",
)
SS = 8
# Espessura do traço em pixels finais por tamanho.
STROKE = {16: 1.25, 32: 2.4}


def dat_path(name, size):
    return os.path.join(cut.DATAFILES, "blender_icons%d" % size, "icon%d_%s.dat" % (size, name.lower()))


def read_dat(path):
    with open(path, "rb") as fh:
        data = fh.read()
    size, _, x, y_bottom, _, _ = struct.unpack("<6I", data[:24])
    img = Image.frombytes("RGBA", (size, size), data[24:]).transpose(Image.FLIP_TOP_BOTTOM)
    return img, x, y_bottom, size


def outline(img, size):
    n = size * SS
    alpha = img.getchannel("A").resize((n, n), Image.BICUBIC)
    solid = alpha.point(lambda v: 255 if v >= 128 else 0)
    # Erosão com um disco aproximado (MinFilter só aceita tamanhos ímpares).
    r = int(round(STROKE[size] * SS))
    inner = solid
    step = 5
    while r > 0:
        k = min(step, 2 * r + 1)
        k -= (k + 1) % 2
        inner = inner.filter(ImageFilter.MinFilter(k))
        r -= k // 2
    ring = ImageChops.subtract(solid, inner)
    ring = ring.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    out.putalpha(ring)
    return out


def main():
    preview = None
    if "--preview" in sys.argv:
        preview = sys.argv[sys.argv.index("--preview") + 1]
    rows = []
    for name in ICONS:
        for size in (16, 32):
            img, x, y_bottom, size = read_dat(dat_path(name, size))
            new = outline(img, size)
            if preview:
                rows.append((img, new))
            else:
                cut.write_dat(dat_path(name, size), new, x, y_bottom, size)
        print(name)
    if preview:
        tint = (232, 128, 32, 255)
        sheet = Image.new("RGBA", (4 * 40, 36 * len(ICONS)), (40, 40, 40, 255))
        for i, (old, new) in enumerate(rows):
            sz = old.width
            for k, im in enumerate((old, new)):
                colored = Image.new("RGBA", im.size, tint)
                colored.putalpha(im.getchannel("A"))
                sheet.alpha_composite(colored, ((0 if sz == 16 else 80) + k * 40, (i // 2) * 36 + 2))
        sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
        sheet.save(preview)


if __name__ == "__main__":
    main()
