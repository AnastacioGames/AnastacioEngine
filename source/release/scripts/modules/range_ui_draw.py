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


def state_target(style, state):
    """Cor e escala que o botão busca em cada estado."""
    if state == "PRESSED":
        return style["press"], style.get("press_scale", 1.0)
    if state == "HOVER":
        return style["hover"], style.get("hover_scale", 1.0)
    return style["color"], 1.0


def draw_button(bgl, blf, style, text, x, y, w, h, state="NORMAL", color=None, scale=None):
    """Desenha o botão com canto inferior esquerdo em (x, y), em pixels.

    color/scale substituem os do estado (o jogo passa os valores animados);
    a escala cresce a partir do centro do botão."""
    target_color, target_scale = state_target(style, state)
    color = target_color if color is None else color
    scale = target_scale if scale is None else scale
    if scale != 1.0:
        x -= w * (scale - 1.0) * 0.5
        y -= h * (scale - 1.0) * 0.5
        w *= scale
        h *= scale
    radius = style["radius"] * min(w, h) * 0.5
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    if style["shadow"]:
        off = max(1.0, h * 0.08)
        bgl.glColor4f(0.0, 0.0, 0.0, 0.35)
        _rounded_polygon(bgl, bgl.GL_POLYGON, x + off, y - off, w, h, radius)
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


# -- HUD ----------------------------------------------------------------------

class _Values(dict):
    """Propriedades para o format do Label; nome que falta vira 0."""

    def __missing__(self, key):
        return 0


def format_label(fmt, values):
    try:
        return fmt.format_map(_Values(values))
    except (ValueError, TypeError, IndexError, AttributeError):
        return fmt


def bar_fraction(data, values):
    span = data["max"] - data["min"]
    try:
        value = float(values.get(data["property"], data["min"]))
    except (TypeError, ValueError):
        value = data["min"]
    return 0.0 if span == 0 else max(0.0, min(1.0, (value - data["min"]) / span))


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def draw_bar(bgl, data, frac, x, y, w, h):
    radius = data["radius"] * min(w, h) * 0.5
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    bgl.glColor4f(*data["bg"])
    _rounded_polygon(bgl, bgl.GL_POLYGON, x, y, w, h, radius)
    if frac <= 0.0:
        return
    # Barra vazia = cor Low, cheia = cor Fill.
    color = _mix(data["low"], data["fill"], frac) if data["use_low"] else data["fill"]
    pad = min(w, h) * 0.12
    fx, fy, fw, fh = x + pad, y + pad, w - 2 * pad, h - 2 * pad
    direction = data["direction"]
    if direction == "RIGHT":
        fw *= frac
    elif direction == "LEFT":
        fx += fw * (1.0 - frac)
        fw *= frac
    elif direction == "UP":
        fh *= frac
    else:  # DOWN
        fy += fh * (1.0 - frac)
        fh *= frac
    bgl.glColor4f(*color)
    _rounded_polygon(bgl, bgl.GL_POLYGON, fx, fy, fw, fh, max(0.0, radius - pad))


def draw_label(bgl, blf, data, text, x, y, w, h):
    size = max(6, int(h * data["text_size"]))
    blf.size(0, size, 72)
    tw = blf.dimensions(0, text)[0]
    if data["align"] == "LEFT":
        tx = x
    elif data["align"] == "RIGHT":
        tx = x + w - tw
    else:
        tx = x + (w - tw) / 2
    ty = y + (h - size * 0.7) / 2
    bgl.glEnable(bgl.GL_BLEND)
    if data["shadow"]:
        off = max(1, size // 14)
        bgl.glColor4f(0.0, 0.0, 0.0, 0.8 * data["color"][3])
        blf.position(0, tx + off, ty - off, 0)
        blf.draw(0, text)
    bgl.glColor4f(*data["color"])
    blf.position(0, tx, ty, 0)
    blf.draw(0, text)


def draw_widget(bgl, blf, data, values, x, y, w, h):
    """Desenha um widget de HUD (Progress Bar ou Label) com os valores dados."""
    if data["kind"] == "BAR":
        draw_bar(bgl, data, bar_fraction(data, values), x, y, w, h)
    elif data["kind"] == "LABEL":
        draw_label(bgl, blf, data, format_label(data["format"], values), x, y, w, h)
