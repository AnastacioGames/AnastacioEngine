"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar

from mathutils import Vector

def cell(position) -> float:
    """Returns cell noise value at the specified position."""
def cell_vector(position) -> Vector:
    """Returns cell noise vector at the specified position."""
def fractal(position, H, lacunarity, octaves, noise_basis=...) -> float:
    """Returns the fractal Brownian motion (fBm) noise value from the noise basis at the specified position."""
def hetero_terrain(position, H, lacunarity, octaves, offset, noise_basis=...) -> float:
    """Returns the heterogeneous terrain value from the noise basis at the specified position."""
def hybrid_multi_fractal(position, H, lacunarity, octaves, offset, gain, noise_basis=...) -> float:
    """Returns hybrid multifractal value from the noise basis at the specified position."""
def multi_fractal(position, H, lacunarity, octaves, noise_basis=...) -> float:
    """Returns multifractal noise value from the noise basis at the specified position."""
def noise(position, noise_basis=...) -> float:
    """Returns noise value from the noise basis at the position specified."""
def noise_vector(position, noise_basis=...) -> Vector:
    """Returns the noise vector from the noise basis at the specified position."""
def random() -> float:
    """Returns a random number in the range [0, 1]."""
def random_unit_vector(size=3) -> Vector:
    """Returns a unit vector with random entries."""
def ridged_multi_fractal(position, H, lacunarity, octaves, offset, gain, noise_basis=...) -> float:
    """Returns ridged multifractal value from the noise basis at the specified position."""
def seed_set(seed) -> Any:
    """Sets the random seed used for random_unit_vector, random_vector and random."""
def turbulence(position, octaves, hard, noise_basis=..., amplitude_scale=0.5, frequency_scale=2.0) -> float:
    """Returns the turbulence value from the noise basis at the specified position."""
def turbulence_vector(position, octaves, hard, noise_basis=..., amplitude_scale=0.5, frequency_scale=2.0) -> Vector:
    """Returns the turbulence vector from the noise basis at the specified position."""
def variable_lacunarity(position, distortion, noise_type1=..., noise_type2=...) -> float:
    """Returns variable lacunarity noise value, a distorted variety of noise, from noise type 1 distorted by noise type 2 at the specified position."""
def voronoi(position, distance_metric=..., exponent=2.5) -> list[Vector]:
    """Returns a list of distances to the four closest features and their locations."""
