# SPDX-License-Identifier: GPL-2.0-or-later
"""KTX2 metadata test: normal map mark and orientation, in the background (no window).
  AnastacioEngine -b --python this.py -- write <dir>   writes colour, alpha and normal files
  AnastacioEngine -b --python this.py -- check <dir>   loads them, and <dir>/externo.ktx2 if present

The source image: red at the bottom, blue at the top, green growing to the right.
externo.ktx2 is a colour UASTC file in KTX2 row order (top first) with no Anastacio mark, written by
ktx2_externo.cpp. After loading, every file must read the same way, whatever its order on disk.
"""
import os
import sys
import bpy

mode, folder = sys.argv[sys.argv.index('--') + 1:][:2]
SIZE = 64


def source(name, normal=False, alpha=False):
    image = bpy.data.images.new(name, SIZE, SIZE, alpha=True)
    px = []
    for y in range(SIZE):
        v = y / (SIZE - 1)
        for x in range(SIZE):
            u = x / (SIZE - 1)
            if normal:
                px += [0.25 + 0.5 * u, 0.25 + 0.5 * v, 0.9, 1.0]
            else:
                px += [1.0 - v, u, v, 0.25 + 0.75 * v if alpha else 1.0]
    image.pixels = px
    return image


def at(px, x, y):
    i = (y * SIZE + x) * 4
    return px[i:i + 4]


def near(a, b, tol=0.14):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


def load(name):
    image = bpy.data.images.load(os.path.join(folder, name), check_existing=False)
    assert tuple(image.size) == (SIZE, SIZE), image.size
    return list(image.pixels)


if mode == 'write':
    for name, normal, alpha in (('cor', False, False), ('alfa', False, True), ('normal', True, False)):
        source(name, normal, alpha).save_ktx2(filepath=os.path.join(folder, name + '.ktx2'), normal=normal,
                                              max_size=0, quality=75, srgb=False)
    print('KTX2_MARK_WRITTEN')
else:
    fails = []

    def check(label, px, x, y, want):
        got = at(px, x, y)
        ok = near(got, want)
        print('%-22s (%2d,%2d) %s want %s %s' % (label, x, y, ['%.2f' % c for c in got], want, 'ok' if ok else 'FAIL'))
        if not ok:
            fails.append(label)

    top, right = SIZE - 2, SIZE - 2
    for name in ('cor', 'externo'):
        if not os.path.isfile(os.path.join(folder, name + '.ktx2')):
            print('missing', name)
            fails.append(name)
            continue
        px = load(name + '.ktx2')
        check(name + ' bottom', px, 1, 1, [1, 0, 0, 1])
        check(name + ' top', px, 1, top, [0, 0, 1, 1])
        check(name + ' right', px, right, 1, [1, 1, 0, 1])
    px = load('alfa.ktx2')
    check('alpha bottom', px, 1, 1, [1, 0, 0, 0.25])
    check('alpha top', px, 1, top, [0, 0, 1, 1])
    px = load('normal.ktx2')
    # stored X/Y comes back as X, Y and a rebuilt Z, alpha 1
    check('normal low', px, 1, 1, [0.25, 0.25, 0.85, 1])
    check('normal high', px, right, top, [0.75, 0.75, 0.85, 1])
    print('KTX2_MARK_RESULT', 'FAIL ' + ','.join(fails) if fails else 'OK')
