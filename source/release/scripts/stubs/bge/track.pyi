"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar

from mathutils import Vector

class Track:
    def bankAt(self, s) -> float:
        """Banking at s in radians (positive: the left edge is lower)."""
    count: int
    """Number of baked samples."""
    cyclic: bool
    """True for a closed circuit."""
    def edgeAt(self, s) -> tuple:
        """Lateral distance of the outer border band (wall, guard rail) at s."""
    def isOnRoad(self, pos) -> bool:
        """True when pos is over the asphalt (inside the half widths) and up to 3 m from the surface (height ignored without z). Past the start or the end of an open track: False."""
    def lateralAt(self, s) -> Vector:
        """Horizontal unit vector to the left at s."""
    length: float
    """Track length in meters."""
    name: str
    """Track name."""
    def pointAt(self, s) -> Vector:
        """Center line point at s."""
    def project(self, pos, near=None) -> tuple:
        """Projection of a position on the track."""
    def racingLine(self, s) -> Vector:
        """Racing line point at s, on the banked surface."""
    def surfaceAt(self, s) -> str:
        """Surface name of the sample that starts the stretch at s ("" when the track has no surface names)."""
    surfaces: list[Any]
    """Surface names."""
    def tangentAt(self, s) -> Vector:
        """Unit 3D direction of travel at s."""
    def widthAt(self, s) -> tuple:
        """Asphalt half widths at s."""

def fromJson(text, name="") -> Track:
    """Track built from a JSON string in the baked format (version 1), for data kept elsewhere.

    :param name: name used when the JSON has no name.

    :param text: JSON text.
    """
def get(name) -> Track:
    """Track baked in the Text TRACK_<name>.json of the game file or of a LibLoaded file. The Text name itself ("TRACK_Pista_4.json") is accepted too. Read once and cached; the cache follows LibLoad/LibFree and is cleared when the game ends.

    :param name: track name (the name of the track layout object).
    """
def names() -> list[Any]:
    """Names of the tracks available in the loaded files (Texts TRACK_*.json)."""
def reload() -> Any:
    """Forget the cached tracks: the next get reads the Text again."""
