"""Desenho dos botões da UI Tree, comum ao editor (prévia) e ao jogo.

Só usa bgl/blf, sem bpy nem Range.  Os tamanhos do estilo são frações da
altura do botão, então a prévia e o jogo ficam proporcionais em qualquer
escala.
"""

import math

STATES = ("NORMAL", "HOVER", "PRESSED")

# Transparência geral multiplicada em todas as cores (fade das telas).
_alpha = 1.0


def set_alpha(alpha):
    global _alpha
    _alpha = max(0.0, min(1.0, alpha))


def _color(bgl, c):
    bgl.glColor4f(c[0], c[1], c[2], c[3] * _alpha)


ANCHOR_POINTS = {
    "TOP_LEFT": (0.0, 0.0), "TOP": (0.5, 0.0), "TOP_RIGHT": (1.0, 0.0),
    "LEFT": (0.0, 0.5), "CENTER": (0.5, 0.5), "RIGHT": (1.0, 0.5),
    "BOTTOM_LEFT": (0.0, 1.0), "BOTTOM": (0.5, 1.0), "BOTTOM_RIGHT": (1.0, 1.0),
}


def place(rect, mode, design, anchor, width, height):
    """Retângulo normalizado da tela (x, y do topo) -> pixels (x, y de baixo, w, h).

    STRETCH estica tudo com a janela.  KEEP usa uma escala só (a menor das
    duas), e o widget mantém a distância até o ponto âncora da janela."""
    x, y, w, h = rect
    if mode != "KEEP":
        return x * width, height - (y + h) * height, w * width, h * height
    dw, dh = design
    s = min(width / dw, height / dh)
    ax, ay = ANCHOR_POINTS.get(anchor, (0.5, 0.5))
    px = (x - ax) * dw * s + ax * width
    top = (y - ay) * dh * s + ay * height
    pw, ph = w * dw * s, h * dh * s
    return px, height - top - ph, pw, ph


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
    if state == "DISABLED":
        return style.get("disabled", style["color"]), 1.0
    if state in ("HOVER", "SELECTED"):
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
        _color(bgl, (0.0, 0.0, 0.0, 0.35))
        _rounded_polygon(bgl, bgl.GL_TRIANGLE_FAN, x + off, y - off, w, h, radius)
    _color(bgl, color)
    _rounded_polygon(bgl, bgl.GL_TRIANGLE_FAN, x, y, w, h, radius)
    border = style["border"] * h
    if state == "SELECTED":
        border = max(border, 2.0)
    if border > 0.0:
        bgl.glLineWidth(max(1.0, border))
        _color(bgl, style["border_color"])
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
    _color(bgl, style["text_color"])
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
    _color(bgl, data["bg"])
    _rounded_polygon(bgl, bgl.GL_TRIANGLE_FAN, x, y, w, h, radius)
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
    _color(bgl, color)
    _rounded_polygon(bgl, bgl.GL_TRIANGLE_FAN, fx, fy, fw, fh, max(0.0, radius - pad))


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
        _color(bgl, (0.0, 0.0, 0.0, 0.8 * data["color"][3]))
        blf.position(0, tx + off, ty - off, 0)
        blf.draw(0, text)
    _color(bgl, data["color"])
    blf.position(0, tx, ty, 0)
    blf.draw(0, text)


def _text(bgl, blf, text, color, size, x, y, w, h, align="CENTER", shadow=False):
    size = max(6, int(size))
    blf.size(0, size, 72)
    tw = blf.dimensions(0, text)[0]
    if align == "LEFT":
        tx = x
    elif align == "RIGHT":
        tx = x + w - tw
    else:
        tx = x + (w - tw) / 2
    ty = y + (h - size * 0.7) / 2
    if shadow:
        off = max(1, size // 14)
        _color(bgl, (0.0, 0.0, 0.0, 0.8 * color[3]))
        blf.position(0, tx + off, ty - off, 0)
        blf.draw(0, text)
    _color(bgl, color)
    blf.position(0, tx, ty, 0)
    blf.draw(0, text)


def _blend(bgl):
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)


def draw_panel(bgl, data, x, y, w, h):
    radius = data["radius"] * min(w, h) * 0.5
    _blend(bgl)
    _color(bgl, data["color"])
    _rounded_polygon(bgl, bgl.GL_TRIANGLE_FAN, x, y, w, h, radius)
    border = data["border"] * min(w, h)
    if border > 0.0:
        bgl.glLineWidth(max(1.0, border))
        _color(bgl, data["border_color"])
        _rounded_polygon(bgl, bgl.GL_LINE_LOOP, x, y, w, h, radius)
        bgl.glLineWidth(1.0)


def draw_image(bgl, data, bindcode, x, y, w, h):
    """bindcode = textura GL já carregada; sem ela desenha um quadro vazio."""
    _blend(bgl)
    if not bindcode:
        _color(bgl, (1.0, 0.0, 1.0, 0.5))
        _rounded_polygon(bgl, bgl.GL_LINE_LOOP, x, y, w, h, 0.0)
        return
    bgl.glEnable(bgl.GL_TEXTURE_2D)
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, bindcode)
    _color(bgl, data["tint"])
    bgl.glBegin(bgl.GL_QUADS)
    for u, v, px, py in ((0, 0, x, y), (1, 0, x + w, y), (1, 1, x + w, y + h), (0, 1, x, y + h)):
        bgl.glTexCoord2f(u, v)
        bgl.glVertex2f(px, py)
    bgl.glEnd()
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)
    bgl.glDisable(bgl.GL_TEXTURE_2D)


def _arc(bgl, cx, cy, r0, r1, a0, a1, steps):
    bgl.glBegin(bgl.GL_TRIANGLE_STRIP)
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        ca, sa = math.cos(a), math.sin(a)
        bgl.glVertex2f(cx + ca * r1, cy + sa * r1)
        bgl.glVertex2f(cx + ca * r0, cy + sa * r0)
    bgl.glEnd()


def draw_gauge(bgl, blf, data, frac, values, x, y, w, h):
    """Velocímetro circular: arco de fundo, arco cheio até o valor, ponteiro
    e o texto no centro.  O arco abre por baixo (Arc graus no total)."""
    _blend(bgl)
    r1 = min(w, h) * 0.5
    r0 = r1 * (1.0 - data["thickness"])
    cx, cy = x + w * 0.5, y + h * 0.5
    span = math.radians(data["arc"])
    start = math.pi * 0.5 + span * 0.5  # do lado esquerdo, sentido horário
    _color(bgl, data["bg"])
    _arc(bgl, cx, cy, r0, r1, start, start - span, 48)
    if frac > 0.0:
        color = _mix(data["low"], data["fill"], frac) if data["use_low"] else data["fill"]
        _color(bgl, color)
        _arc(bgl, cx, cy, r0, r1, start, start - span * frac, max(2, int(48 * frac)))
    if data["needle"]:
        a = start - span * frac
        bgl.glLineWidth(max(1.0, r1 * 0.04))
        _color(bgl, data["needle_color"])
        bgl.glBegin(bgl.GL_LINES)
        bgl.glVertex2f(cx, cy)
        bgl.glVertex2f(cx + math.cos(a) * r1 * 0.95, cy + math.sin(a) * r1 * 0.95)
        bgl.glEnd()
        bgl.glLineWidth(1.0)
    if data["format"]:
        text = format_label(data["format"], values)
        _text(bgl, blf, text, data["text_color"], r1 * 0.35, x, cy - r1 * 0.55, w, r1 * 0.4)


def draw_toggle(bgl, blf, data, on, x, y, w, h, hover=False):
    """Caixa de marcar com o texto ao lado; hover clareia a caixa."""
    _blend(bgl)
    box = h * 0.8
    bx, by = x + (h - box) * 0.5, y + (h - box) * 0.5
    color = data["color"]
    if hover:
        color = _mix(color, (1.0, 1.0, 1.0, color[3]), 0.2)
    radius = data["radius"] * box * 0.5
    _color(bgl, color)
    _rounded_polygon(bgl, bgl.GL_TRIANGLE_FAN, bx, by, box, box, radius)
    if on:
        pad = box * 0.22
        _color(bgl, data["on_color"])
        _rounded_polygon(bgl, bgl.GL_TRIANGLE_FAN, bx + pad, by + pad, box - 2 * pad, box - 2 * pad,
                         max(0.0, radius - pad))
    if data["text"]:
        _text(bgl, blf, data["text"], data["text_color"], h * data["text_size"],
              x + h * 1.2, y, w - h * 1.2, h, align="LEFT")


def draw_slider(bgl, blf, data, frac, values, x, y, w, h, hover=False):
    """Trilho, parte cheia e o puxador redondo na posição do valor."""
    _blend(bgl)
    track = h * 0.3
    knob = h * 0.8
    tx0, tx1 = x + knob * 0.5, x + w - knob * 0.5
    ty = y + (h - track) * 0.5
    _color(bgl, data["bg"])
    _rounded_polygon(bgl, bgl.GL_TRIANGLE_FAN, tx0, ty, tx1 - tx0, track, track * 0.5)
    kx = tx0 + (tx1 - tx0) * frac
    if frac > 0.0:
        _color(bgl, data["fill"])
        _rounded_polygon(bgl, bgl.GL_TRIANGLE_FAN, tx0, ty, kx - tx0, track, track * 0.5)
    color = data["knob"]
    if hover:
        color = _mix(color, (1.0, 1.0, 1.0, color[3]), 0.3)
    _color(bgl, color)
    _rounded_polygon(bgl, bgl.GL_TRIANGLE_FAN, kx - knob * 0.5, y + (h - knob) * 0.5, knob, knob, knob * 0.5)


# -- Dialogue Box -------------------------------------------------------------

def wrap_text(blf, text, width):
    """Quebra nas palavras (blf.size já ajustado); palavra maior que a
    largura é cortada entre letras."""
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = line + " " + word if line else word
            if blf.dimensions(0, candidate)[0] <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
            while len(word) > 1 and blf.dimensions(0, word)[0] > width:
                cut = len(word) - 1
                while cut > 1 and blf.dimensions(0, word[:cut])[0] > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            line = word
        lines.append(line)
    return lines


def dialogue_metrics(data, h):
    """Tamanhos em pixels: os do nó são unidades do editor, escalados pela
    altura colocada (h) contra a altura do nó."""
    s = h / max(1e-6, data["design_h"])
    size = max(6, int(data["text_size"] * s))
    pad = data["padding"] * s
    return size, pad, size * data["line_spacing"]


def dialogue_pages(blf, data, text, speaker, w, h):
    """Páginas (listas de linhas): "|" força página nova, o resto quebra na
    largura e pagina pela altura."""
    size, pad, line_h = dialogue_metrics(data, h)
    top = pad + (line_h if speaker else 0.0)
    per_page = max(1, int((h - top - pad) / line_h + 1e-4))
    blf.size(0, size, 72)
    pages = []
    # "\n" digitado no campo de texto (não dá para digitar Enter nele).
    for chunk in text.replace("\\n", "\n").split("|"):
        lines = wrap_text(blf, chunk.strip(), w - 2.0 * pad)
        pages.extend(lines[i:i + per_page] for i in range(0, len(lines), per_page))
    return pages or [[]]


def page_length(page):
    return sum(len(line) for line in page)


def draw_dialogue(bgl, blf, data, speaker, page, visible, x, y, w, h, show_next):
    """Fundo, nome de quem fala, as linhas da página até visible letras e a
    seta de "próximo" quando a página terminou."""
    draw_panel(bgl, data, x, y, w, h)
    size, pad, line_h = dialogue_metrics(data, h)
    blf.size(0, size, 72)
    ty = y + h - pad - size * 0.8
    if speaker:
        _color(bgl, data["speaker_color"])
        blf.position(0, x + pad, ty, 0)
        blf.draw(0, speaker)
        ty -= line_h
    left = visible
    for line in page:
        if left <= 0:
            break
        part = line[:left]
        left -= len(line)
        if data["shadow"]:
            off = max(1, size // 14)
            _color(bgl, (0.0, 0.0, 0.0, 0.8 * data["text_color"][3]))
            blf.position(0, x + pad + off, ty - off, 0)
            blf.draw(0, part)
        _color(bgl, data["text_color"])
        blf.position(0, x + pad, ty, 0)
        blf.draw(0, part)
        ty -= line_h
    if show_next:
        a = size * 0.35
        cx, cy = x + w - pad - a, y + pad + a * 0.5
        _blend(bgl)
        _color(bgl, data["speaker_color"])
        bgl.glBegin(bgl.GL_TRIANGLES)
        bgl.glVertex2f(cx - a, cy + a * 0.6)
        bgl.glVertex2f(cx + a, cy + a * 0.6)
        bgl.glVertex2f(cx, cy - a * 0.6)
        bgl.glEnd()


def draw_widget(bgl, blf, data, values, x, y, w, h, bindcode=0, hover=False):
    """Desenha um widget (HUD ou controle) com os valores dados."""
    kind = data["kind"]
    if kind == "BAR":
        draw_bar(bgl, data, bar_fraction(data, values), x, y, w, h)
    elif kind == "LABEL":
        draw_label(bgl, blf, data, format_label(data["format"], values), x, y, w, h)
    elif kind == "PANEL":
        draw_panel(bgl, data, x, y, w, h)
    elif kind == "IMAGE":
        draw_image(bgl, data, bindcode, x, y, w, h)
    elif kind == "GAUGE":
        draw_gauge(bgl, blf, data, bar_fraction(data, values), values, x, y, w, h)
    elif kind == "TOGGLE":
        draw_toggle(bgl, blf, data, bool(values.get(data["property"], False)), x, y, w, h, hover)
    elif kind == "DIALOGUE":
        # Prévia do editor: 1ª página inteira (o jogo usa range_ui_runtime.Dialogue).
        text = format_label(data["text"], values) if not data["property"] else             "Text from the property '%s'" % data["property"]
        speaker = format_label(data["speaker"], values)
        page = dialogue_pages(blf, data, text, speaker, w, h)[0]
        draw_dialogue(bgl, blf, data, speaker, page, page_length(page), x, y, w, h, True)
    elif kind == "SLIDER":
        draw_slider(bgl, blf, data, bar_fraction(data, values), values, x, y, w, h, hover)
