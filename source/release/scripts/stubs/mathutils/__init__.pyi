"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar

from . import bvhtree as bvhtree
from . import geometry as geometry
from . import interpolate as interpolate
from . import kdtree as kdtree
from . import noise as noise

class Color:
    def __init__(self, rgb: Any = ...) -> None: ...
    def __getitem__(self, index: int) -> float: ...
    def __setitem__(self, index: int, value: float) -> None: ...

class Euler:
    def copy(self) -> Euler:
        """Returns a copy of this euler."""
    def freeze(self) -> Any:
        """Make this object immutable."""
    is_frozen: bool
    """True when this object has been frozen (read-only)."""
    is_wrapped: bool
    """True when this object wraps external data (read-only)."""
    def make_compatible(self, other) -> Any:
        """Make this euler compatible with another, so interpolating between them works as intended."""
    order: str
    """Euler rotation order."""
    owner: Any
    """The item this is wrapping or None  (read-only)."""
    def rotate(self, other) -> Any:
        """Rotates the euler by another mathutils value."""
    def rotate_axis(self, axis, angle) -> Any:
        """Rotates the euler a certain amount and returning a unique euler rotation (no 720 degree pitches)."""
    def to_matrix(self) -> Matrix:
        """Return a matrix representation of the euler."""
    def to_quaternion(self) -> Quaternion:
        """Return a quaternion representation of the euler."""
    x: float
    """Euler axis angle in radians."""
    y: float
    """Euler axis angle in radians."""
    z: float
    """Euler axis angle in radians."""
    def zero(self) -> Any:
        """Set all values to zero."""
    def __init__(self, angles: Any = ..., order: str = ...) -> None: ...
    def __getitem__(self, index: int) -> float: ...
    def __setitem__(self, index: int, value: float) -> None: ...

class Matrix:
    def Identity(self, size) -> Matrix:
        """Create an identity matrix."""
    def OrthoProjection(self, axis, size) -> Matrix:
        """Create a matrix to represent an orthographic projection."""
    def Rotation(self, angle, size, axis) -> Matrix:
        """Create a matrix representing a rotation."""
    def Scale(self, factor, size, axis) -> Matrix:
        """Create a matrix representing a scaling."""
    def Shear(self, plane, size, factor) -> Matrix:
        """Create a matrix to represent an shear transformation."""
    def Translation(self, vector) -> Matrix:
        """Create a matrix representing a translation."""
    def adjugate(self) -> Any:
        """Set the matrix to its adjugate."""
    def adjugated(self) -> Matrix:
        """Return an adjugated copy of the matrix."""
    col: Matrix
    """Access the matrix by columns, 3x3 and 4x4 only, (read-only)."""
    def copy(self) -> Matrix:
        """Returns a copy of this matrix."""
    def decompose(self) -> Vector:
        """Return the translation, rotation, and scale components of this matrix."""
    def determinant(self) -> float:
        """Return the determinant of a matrix."""
    def freeze(self) -> Any:
        """Make this object immutable."""
    def identity(self) -> Any:
        """Set the matrix to the identity matrix."""
    def invert(self, fallback=None) -> Any:
        """Set the matrix to its inverse."""
    def invert_safe(self) -> Any:
        """Set the matrix to its inverse, will never error. If degenerated (e.g. zero scale on an axis), add some epsilon to its diagonal, to get an invertible one. If tweaked matrix is still degenerated, set to the identity matrix instead."""
    def inverted(self, fallback=None) -> Matrix:
        """Return an inverted copy of the matrix."""
    def inverted_safe(self) -> Matrix:
        """Return an inverted copy of the matrix, will never error. If degenerated (e.g. zero scale on an axis), add some epsilon to its diagonal, to get an invertible one. If tweaked matrix is still degenerated, return the identity matrix instead."""
    is_frozen: bool
    """True when this object has been frozen (read-only)."""
    is_negative: bool
    """True if this matrix results in a negative scale, 3x3 and 4x4 only, (read-only)."""
    is_orthogonal: bool
    """True if this matrix is orthogonal, 3x3 and 4x4 only, (read-only)."""
    is_orthogonal_axis_vectors: bool
    """True if this matrix has got orthogonal axis vectors, 3x3 and 4x4 only, (read-only)."""
    is_wrapped: bool
    """True when this object wraps external data (read-only)."""
    def lerp(self, other, factor) -> Matrix:
        """Returns the interpolation of two matrices. Uses polar decomposition, see   "Matrix Animation and Polar Decomposition", Shoemake and Duff, 1992."""
    median_scale: float
    """The average scale applied to each axis (read-only)."""
    def normalize(self) -> Any:
        """Normalize each of the matrix columns."""
    def normalized(self) -> Matrix:
        """Return a column normalized matrix"""
    owner: Any
    """The item this is wrapping or None  (read-only)."""
    def resize_4x4(self) -> Any:
        """Resize the matrix to 4x4."""
    def rotate(self, other) -> Any:
        """Rotates the matrix by another mathutils value."""
    row: Matrix
    """Access the matrix by rows (default), (read-only)."""
    def to_3x3(self) -> Matrix:
        """Return a 3x3 copy of this matrix."""
    def to_4x4(self) -> Matrix:
        """Return a 4x4 copy of this matrix."""
    def to_euler(self, order, euler_compat) -> Euler:
        """Return an Euler representation of the rotation matrix (3x3 or 4x4 matrix only)."""
    def to_quaternion(self) -> Quaternion:
        """Return a quaternion representation of the rotation matrix."""
    def to_scale(self) -> Vector:
        """Return the scale part of a 3x3 or 4x4 matrix."""
    def to_translation(self) -> Vector:
        """Return the translation part of a 4 row matrix."""
    translation: Vector
    """The translation component of the matrix."""
    def transpose(self) -> Any:
        """Set the matrix to its transpose."""
    def transposed(self) -> Matrix:
        """Return a new, transposed matrix."""
    def zero(self) -> Matrix:
        """Set all the matrix values to zero."""
    def __init__(self, rows: Any = ...) -> None: ...
    def __mul__(self, other: Any) -> Any: ...
    def __matmul__(self, other: Any) -> Any: ...
    def __getitem__(self, index: int) -> Vector: ...
    def __iter__(self) -> Iterator[Vector]: ...
    def __len__(self) -> int: ...

class Quaternion:
    angle: float
    """Angle of the quaternion."""
    axis: Vector
    """Quaternion axis as a vector."""
    def conjugate(self) -> Any:
        """Set the quaternion to its conjugate (negate x, y, z)."""
    def conjugated(self) -> Quaternion:
        """Return a new conjugated quaternion."""
    def copy(self) -> Quaternion:
        """Returns a copy of this quaternion."""
    def cross(self, other) -> Quaternion:
        """Return the cross product of this quaternion and another."""
    def dot(self, other) -> Quaternion:
        """Return the dot product of this quaternion and another."""
    def freeze(self) -> Any:
        """Make this object immutable."""
    def identity(self) -> Quaternion:
        """Set the quaternion to an identity quaternion."""
    def invert(self) -> Any:
        """Set the quaternion to its inverse."""
    def inverted(self) -> Quaternion:
        """Return a new, inverted quaternion."""
    is_frozen: bool
    """True when this object has been frozen (read-only)."""
    is_wrapped: bool
    """True when this object wraps external data (read-only)."""
    magnitude: float
    """Size of the quaternion (read-only)."""
    def negate(self) -> Quaternion:
        """Set the quaternion to its negative."""
    def normalize(self) -> Any:
        """Normalize the quaternion."""
    def normalized(self) -> Quaternion:
        """Return a new normalized quaternion."""
    owner: Any
    """The item this is wrapping or None  (read-only)."""
    def rotate(self, other) -> Any:
        """Rotates the quaternion by another mathutils value."""
    def rotation_difference(self, other) -> Quaternion:
        """Returns a quaternion representing the rotational difference."""
    def slerp(self, other, factor) -> Quaternion:
        """Returns the interpolation of two quaternions."""
    def to_axis_angle(self) -> Vector:
        """Return the axis, angle representation of the quaternion."""
    def to_euler(self, order, euler_compat) -> Euler:
        """Return Euler representation of the quaternion."""
    def to_exponential_map(self) -> Vector:
        """Return the exponential map representation of the quaternion."""
    def to_matrix(self) -> Matrix:
        """Return a matrix representation of the quaternion."""
    w: float
    """Quaternion axis value."""
    x: float
    """Quaternion axis value."""
    y: float
    """Quaternion axis value."""
    z: float
    """Quaternion axis value."""
    def __init__(self, seq: Any = ..., angle: float = ...) -> None: ...
    def __mul__(self, other: Any) -> Any: ...
    def __matmul__(self, other: Any) -> Any: ...
    def __getitem__(self, index: int) -> float: ...

class Vector:
    def Fill(self, size, fill=0.0) -> Any:
        """Create a vector of length size with all values set to fill."""
    def Linspace(self, start, stop, size) -> Any:
        """Create a vector of the specified size which is filled with linearly spaced values between start and stop values."""
    def Range(self, *args: Any, **kwargs: Any) -> Any:
        """Create a filled with a range of values."""
    def Repeat(self, vector, size) -> Any:
        """Create a vector by repeating the values in vector until the required size is reached."""
    def angle(self, other, fallback=None) -> float:
        """Return the angle between two vectors."""
    def angle_signed(self, other, fallback) -> float:
        """Return the signed angle between two 2D vectors (clockwise is positive)."""
    def copy(self) -> Vector:
        """Returns a copy of this vector."""
    def cross(self, other) -> Vector:
        """Return the cross product of this vector and another."""
    def dot(self, other) -> Vector:
        """Return the dot product of this vector and another."""
    def freeze(self) -> Any:
        """Make this object immutable."""
    is_frozen: bool
    """True when this object has been frozen (read-only)."""
    is_wrapped: bool
    """True when this object wraps external data (read-only)."""
    length: float
    """Vector Length."""
    length_squared: float
    """Vector length squared (v.dot(v))."""
    def lerp(self, other, factor) -> Vector:
        """Returns the interpolation of two vectors."""
    magnitude: float
    """Vector Length."""
    def negate(self) -> Any:
        """Set all values to their negative."""
    def normalize(self) -> Any:
        """Normalize the vector, making the length of the vector always 1.0."""
    def normalized(self) -> Vector:
        """Return a new, normalized vector."""
    def orthogonal(self) -> Vector:
        """Return a perpendicular vector."""
    owner: Any
    """The item this is wrapping or None  (read-only)."""
    def project(self, other) -> Vector:
        """Return the projection of this vector onto the *other*."""
    def reflect(self, mirror) -> Vector:
        """Return the reflection vector from the *mirror* argument."""
    def resize(self, size=3) -> Any:
        """Resize the vector to have size number of elements."""
    def resize_2d(self) -> Any:
        """Resize the vector to 2D  (x, y)."""
    def resize_3d(self) -> Any:
        """Resize the vector to 3D  (x, y, z)."""
    def resize_4d(self) -> Any:
        """Resize the vector to 4D (x, y, z, w)."""
    def resized(self, size=3) -> Vector:
        """Return a resized copy of the vector with size number of elements."""
    def rotate(self, other) -> Any:
        """Rotate the vector by a rotation value."""
    def rotation_difference(self, other) -> Quaternion:
        """Returns a quaternion representing the rotational difference between this vector and another."""
    def slerp(self, other, factor, fallback=None) -> Vector:
        """Returns the interpolation of two non-zero vectors (spherical coordinates)."""
    def to_2d(self) -> Vector:
        """Return a 2d copy of the vector."""
    def to_3d(self) -> Vector:
        """Return a 3d copy of the vector."""
    def to_4d(self) -> Vector:
        """Return a 4d copy of the vector."""
    def to_track_quat(self, track, up) -> Quaternion:
        """Return a quaternion rotation from the vector and the track and up axis."""
    def to_tuple(self, precision=-1) -> tuple:
        """Return this vector as a tuple with."""
    w: float
    """Vector W axis (4D Vectors only)."""
    x: float
    """Vector X axis."""
    xy: Any
    xyz: Any
    xyzw: Any
    y: float
    """Vector Y axis."""
    z: float
    """Vector Z axis (3D Vectors only)."""
    def zero(self) -> Any:
        """Set all values to zero."""
    def __init__(self, seq: Any = ...) -> None: ...
    def __add__(self, other: Vector) -> Vector: ...
    def __sub__(self, other: Vector) -> Vector: ...
    def __mul__(self, other: Any) -> Any: ...
    def __rmul__(self, other: Any) -> Any: ...
    def __matmul__(self, other: Any) -> Any: ...
    def __truediv__(self, other: float) -> Vector: ...
    def __neg__(self) -> Vector: ...
    def __getitem__(self, index: int) -> float: ...
    def __setitem__(self, index: int, value: float) -> None: ...
    def __iter__(self) -> Iterator[float]: ...
    def __len__(self) -> int: ...

