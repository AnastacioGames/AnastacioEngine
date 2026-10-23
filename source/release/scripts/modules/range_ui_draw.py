"""Desenho dos botões da UI Tree, comum ao editor (prévia) e ao jogo.

Só usa bgl/blf, sem bpy nem Range.  Os tamanhos do estilo são frações da
altura do botão, então a prévia e o jogo ficam proporcionais em qualquer
escala.
"""

import math

STATES = ("NORMAL", "HOVER", "PRESSED")


def _rounded_polygon(bgl, mode, x, y, w, h, r, steps=8):
    r = max(0.0, min(r, w * 0.5, h * 0.5))
    corners = ((x + w - r, y + h - r, 0), (x + r, y + h - r, 1),
               (x + r, y + r, 2), (x + w - r, y + r, 3))
    bgl.glBegin(mode)
    for cx, cy, quarter in corners:
        for i in range(steps + 1):
            a = (quarter + i / steps) * math.pi / 2
            bgl.glVertex2f(cx + math.cos(a) * r, cy + math.sin(a) * r)
    bgl.glEnd()


def draw_button(bgl, blf, style, text, x, y, w, h, state="NORMAL"):
    """Desenha o botão com canto inferior esquerdo em (x, y), em pixels."""
    radius = style["radius"] * min(w, h) * 0.5
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    if style["shadow"]:
        off = max(1.0, h * 0.08)
        bgl.glColor4f(0.0, 0.0, 0.0, 0.35)
        _rounded_polygon(bgl, bgl.GL_POLYGON, x + off, y - off, w, h, radius)
    color = {"HOVER": style["hover"], "PRESSED": style["press"]}.get(state, style["color"])
    bgl.glColor4f(*color)
    _rounded_polygon(bgl, bgl.GL_POLYGON, x, y, w, h, radius)
    border = style["border"] * h
    if border > 0.0:
        bgl.glLineWidth(max(1.0, border))
        bgl.glColor4f(*style["border_color"])
        _rounded_polygon(bgl, bgl.GL_LINE_LOOP, x, y, w, h, radius)
        bgl.glLineWidth(1.0)
    if not text:
        return
    size = max(6, int(h * style["text_size"]))
    blf.size(0, size, 72)
    tw = blf.dimensions(0, text)[0]
    pad = max(radius, h * 0.2)
    align = style["align"]
    if align == "LEFT":
        tx = x + pad
    elif align == "RIGHT":
        tx = x + w - pad - tw
    else:
        tx = x + (w - tw) / 2
    bgl.glColor4f(*style["text_color"])
    blf.position(0, tx, y + (h - size * 0.7) / 2, 0)
    blf.draw(0, text)
