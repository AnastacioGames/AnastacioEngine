"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar

from bge.types import KX_CharacterWrapper, KX_ConstraintWrapper, KX_VehicleWrapper

ANGULAR_CONSTRAINT: int
CONETWIST_CONSTRAINT: int
DBG_DISABLEBULLETLCP: int
"""Disable Bullet LCP."""
DBG_DRAWAABB: int
"""Draw Axis Aligned Bounding Box in debug."""
DBG_DRAWCONSTRAINTLIMITS: int
"""Draw constraint limits in debug."""
DBG_DRAWCONSTRAINTS: int
"""Draw constraints in debug."""
DBG_DRAWCONTACTPOINTS: int
"""Draw contact points in debug."""
DBG_DRAWFREATURESTEXT: int
"""Draw features text in debug."""
DBG_DRAWTEXT: int
"""Draw text in debug."""
DBG_DRAWWIREFRAME: int
"""Draw wireframe in debug."""
DBG_ENABLECCD: int
"""Enable Continous Collision Detection in debug."""
DBG_ENABLESATCOMPARISION: int
"""Enable sat comparision in debug."""
DBG_FASTWIREFRAME: int
"""Draw a fast wireframe in debug."""
DBG_NODEBUG: int
"""No debug."""
DBG_NOHELPTEXT: int
"""Debug without help text."""
DBG_PROFILETIMINGS: int
"""Draw profile timings in debug."""
GENERIC_6DOF_CONSTRAINT: int
LINEHINGE_CONSTRAINT: int
POINTTOPOINT_CONSTRAINT: int
VEHICLE_CONSTRAINT: int
def createConstraint() -> KX_ConstraintWrapper:
    """physicsid_1, physicsid_2, constraint_type, \\ pivot_x=0.0, pivot_y=0.0, pivot_z=0.0, \\ axis_x=0.0, axis_y=0.0, axis_z=0.0, flag=0)

    :param axis_x: X axis angle in degrees. (optional)

    :param axis_y: Y axis angle in degrees. (optional)

    :param axis_z: Z axis angle in degrees. (optional)

    :param constraint_type: The type of the constraint, see Create Constraint Constants.

    :param flag: 128 to disable collision between linked bodies. (optional)

    :param physicsid_1: The physics id of the first object in constraint.

    :param physicsid_2: The physics id of the second object in constraint.

    :param pivot_x: Pivot X position. (optional)

    :param pivot_y: Pivot Y position. (optional)

    :param pivot_z: Pivot Z position. (optional)
    """
def createVehicle(physicsid) -> KX_VehicleWrapper:
    """Creates a vehicle constraint.

    :param physicsid: The physics id of the chassis object in constraint.
    """
error: str
"""Symbolic constant string that indicates error."""
def exportBulletFile(filename) -> Any:
    """Exports a file representing the dynamics world (usually using .bullet extension).

    :param filename: File path.
    """
def getAppliedImpulse(constraintId) -> float:
    """:param constraintId: The id of the constraint."""
def getCharacter(gameobj) -> KX_CharacterWrapper:
    """:param gameobj: The game object with the character physics."""
def getVehicleConstraint(constraintId) -> KX_VehicleWrapper:
    """:param constraintId: The id of the vehicle constraint."""
def removeConstraint(constraintId) -> Any:
    """Removes a constraint.

    :param constraintId: The id of the constraint to be removed.
    """
def setCcdMode(ccdMode) -> Any:
    """:param ccdMode: The new CCD mode."""
def setContactBreakingTreshold(breakingTreshold) -> Any:
    """:param breakingTreshold: The new contact breaking treshold."""
def setDeactivationAngularTreshold(angularTreshold) -> Any:
    """Sets the angular velocity treshold.

    :param angularTreshold: New deactivation angular treshold.
    """
def setDeactivationLinearTreshold(linearTreshold) -> Any:
    """Sets the linear velocity treshold.

    :param linearTreshold: New deactivation linear treshold.
    """
def setDeactivationTime(time) -> Any:
    """Sets the time after which a resting rigidbody gets deactived.

    :param time: The deactivation time.
    """
def setDebugMode(mode) -> Any:
    """Sets the debug mode.

    :param mode: The new debug mode, see Debug Mode Constants.
    """
def setErp() -> Any:
    ...
def setErp2() -> Any:
    ...
def setGlobalCfm() -> Any:
    ...
def setGravity(x, y, z) -> Any:
    """Sets the gravity force.

    :param x: Gravity X force.

    :param y: Gravity Y force.

    :param z: Gravity Z force.
    """
def setLinearAirDamping(damping) -> Any:
    ...
def setLinearSlop(slop) -> Any:
    """Sets the contact penetration tolerance for the active physics scene. A positive value allows objects to overlap by up to slop Blender units before the Bullet solver applies positional correction. The default is 0.0.

    :param slop: Penetration tolerance in Blender units. Use a finite,
    """
def setMaxGyroscopicForce() -> Any:
    ...
def setNumIterations(numiter) -> Any:
    """Sets the number of iterations for an iterative constraint solver.

    :param numiter: New number of iterations.
    """
def setNumTimeSubSteps(numsubstep) -> Any:
    """Sets the number of substeps for each physics proceed. Tradeoff quality for performance.

    :param numsubstep: New number of substeps.
    """
def setSolverDamping(damping) -> Any:
    """setDamping(float damping) Very experimental, not recommended

    :param damping: New damping for the solver.
    """
def setSolverTau(tau) -> Any:
    """setTau(float tau) Very experimental, not recommended

    :param tau: New tau for the solver.
    """
def setSolverType(solverType) -> Any:
    """:param solverType: The new type of the solver."""
def setSorConstant(sor) -> Any:
    """:param sor: New sor value."""
def setSplitImpulse() -> Any:
    ...
def setSplitImpulsePenetrationThreshold() -> Any:
    ...
def setSplitImpulseTurnErp() -> Any:
    ...
def setUseEpa(epa) -> Any:
    ...
def setWarmstartingFactor() -> Any:
    ...
