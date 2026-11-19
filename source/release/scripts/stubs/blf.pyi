"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar


CLIPPING: int
KERNING_DEFAULT: int
MONOCHROME: int
ROTATION: int
SHADOW: int
WORD_WRAP: int
def aspect(fontid, aspect) -> Any:
    """Set the aspect for drawing text."""
def blur(fontid, radius) -> Any:
    """Set the blur radius for drawing text."""
def clipping(fontid, xmin, ymin, xmax, ymax) -> Any:
    """Set the clipping, enable/disable using CLIPPING."""
def dimensions(fontid, text) -> tuple:
    """Return the width and height of the text."""
def disable(fontid, option) -> Any:
    """Disable option."""
def draw(fontid, text) -> Any:
    """Draw text in the current context."""
def enable(fontid, option) -> Any:
    """Enable option."""
def load(filename) -> int:
    """Load a new font."""
def position(fontid, x, y, z) -> Any:
    """Set the position for drawing text."""
def rotation(fontid, angle) -> Any:
    """Set the text rotation angle, enable/disable using ROTATION."""
def shadow(fontid, level, r, g, b, a) -> Any:
    """Shadow options, enable/disable using SHADOW ."""
def shadow_offset(fontid, x, y) -> Any:
    """Set the offset for shadow text."""
def size(fontid, size, dpi) -> Any:
    """Set the size and dpi for drawing text."""
def unload(filename) -> Any:
    """Unload an existing font."""
def word_wrap(fontid, wrap_width) -> Any:
    """Set the wrap width, enable/disable using WORD_WRAP."""
