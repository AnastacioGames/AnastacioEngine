"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar

from mathutils import Color, Matrix, Vector
from mathutils.bvhtree import BVHTree

_T = TypeVar('_T')

class EXP_PyObjectPlus:
    invalid: bool
    """Test if the object has been freed by the game engine and is no longer valid."""

class EXP_Value(EXP_PyObjectPlus):
    name: str
    """The name of this EXP_Value derived object (read-only)."""

class SCA_ILogicBrick(EXP_Value):
    executePriority: Any
    """This determines the order controllers are evaluated, and actuators are activated (lower priority is executed first)."""
    fireCount: Any
    owner: KX_GameObject
    """The game object this logic brick is attached to (read-only)."""

class BL_ActionActuator(SCA_ILogicBrick):
    action: str
    """The name of the action to set as the current action."""
    blendIn: float
    """Specifies the number of frames of animation to generate when making transitions between actions."""
    frame: float
    """Sets the current frame for the animation."""
    frameEnd: float
    """Specifies the ending frame of the animation."""
    framePropName: str
    """The name of the property that is set to the current frame number."""
    frameStart: float
    """Specifies the starting frame of the animation."""
    layer: Any
    layerWeight: Any
    mode: int
    """The operation mode of the actuator. Can be one of these constants."""
    priority: int
    """Sets the priority of this actuator. Actuators will lower priority numbers will override actuators with higher numbers."""
    propName: str
    """Sets the property to be used in FromProp playback mode."""
    useContinue: bool
    """The actions continue option, True or False. When True, the action will always play from where last left off, otherwise negative events to this actuator will reset it to its start frame."""

class BL_ArmatureActuator(SCA_ILogicBrick):
    constraint: BL_ArmatureConstraint
    """The constraint object this actuator is controlling."""
    influence: float
    """The influence this actuator will set on the constraint it controls."""
    subtarget: KX_GameObject
    """The object that this actuator will set as secondary target to the constraint it controls."""
    target: KX_GameObject
    """The object that this actuator will set as primary target to the constraint it controls."""
    type: int
    """The type of action that the actuator executes when it is active."""
    weight: float
    """The weight this actuator will set on the constraint it controls."""

class BL_ArmatureBone(EXP_Value):
    arm_head: Vector
    """location of head end of the bone in armature space."""
    arm_mat: Matrix
    """matrix of the bone head in armature space."""
    arm_tail: Vector
    """location of tail end of the bone in armature space."""
    bbone_segments: int
    """number of B-bone segments."""
    bone_mat: Matrix
    """rotation matrix of the bone in parent bone space."""
    children: list[BL_ArmatureBone]
    """list of bone's children."""
    connected: bool
    """true when the bone head is struck to the parent's tail."""
    head: Vector
    """location of head end of the bone in parent bone space."""
    hinge: bool
    """true when bone doesn't inherit rotation or scale from parent bone."""
    inherit_scale: bool
    """true when bone inherits scaling from parent bone."""
    length: float
    """bone length."""
    name: str
    """bone name."""
    parent: BL_ArmatureBone
    """parent bone, or None for root bone."""
    roll: float
    """bone rotation around head-tail axis."""
    tail: Vector
    """location of head end of the bone in parent bone space."""

class BL_ArmatureChannel(EXP_Value):
    bone: BL_ArmatureBone
    """return the bone object corresponding to this pose channel, read-only."""
    channel_matrix: Matrix
    """pose matrix in bone space (deformation of the bone due to action, constraint, etc), Read-only. This field is updated after the graphic render, it represents the current pose."""
    has_ik: bool
    """true if the bone is part of an active IK chain, read-only. This flag is not set when an IK constraint is defined but not enabled (miss target information for example)."""
    ik_dof_x: bool
    """true if the bone is free to rotation in the X axis, read-only."""
    ik_dof_y: bool
    """true if the bone is free to rotation in the Y axis, read-only."""
    ik_dof_z: bool
    """true if the bone is free to rotation in the Z axis, read-only."""
    ik_limit_x: bool
    """true if a limit is imposed on X rotation, read-only."""
    ik_limit_y: bool
    """true if a limit is imposed on Y rotation, read-only."""
    ik_limit_z: bool
    """true if a limit is imposed on Z rotation, read-only."""
    ik_lin_control: bool
    """true if channel size should applied as IK constraint, read-only."""
    ik_lin_weight: float
    """weight of size constraint when ik_lin_control is set, read-write."""
    ik_max_x: float
    """maximum value of X rotation in degree (>= 0) when X rotation is limited (see ik_limit_x), read-only."""
    ik_max_y: float
    """maximum value of Y rotation in degree (>= 0) when Y rotation is limited (see ik_limit_y), read-only."""
    ik_max_z: float
    """maximum value of Z rotation in degree (>= 0) when Z rotation is limited (see ik_limit_z), read-only."""
    ik_min_x: float
    """minimum value of X rotation in degree (<= 0) when X rotation is limited (see ik_limit_x), read-only."""
    ik_min_y: float
    """minimum value of Y rotation in degree (<= 0) when Y rotation is limited (see ik_limit_y), read-only."""
    ik_min_z: float
    """minimum value of Z rotation in degree (<= 0) when Z rotation is limited (see ik_limit_z), read-only."""
    ik_rot_control: bool
    """true if channel rotation should applied as IK constraint, read-only."""
    ik_rot_weight: float
    """weight of rotation constraint when ik_rot_control is set, read-write."""
    ik_stiffness_x: float
    """bone rotation stiffness in X axis, read-only."""
    ik_stiffness_y: float
    """bone rotation stiffness in Y axis, read-only."""
    ik_stiffness_z: float
    """bone rotation stiffness in Z axis, read-only."""
    ik_stretch: float
    """ratio of scale change that is allowed, 0=bone can't change size, read-only."""
    joint_rotation: Vector
    """Control bone rotation in term of joint angle (for robotic applications), read-write."""
    location: Vector
    """displacement of the bone head in armature local space, read-write."""
    name: str
    """channel name (=bone name), read-only."""
    parent: BL_ArmatureChannel
    """return the parent channel object, None if root channel, read-only."""
    pose_head: Vector
    """position of bone head in armature space, read-only."""
    pose_matrix: Matrix
    """pose matrix in armature space, read-only, This field is updated after the graphic render, it represents the current pose."""
    pose_tail: Vector
    """position of bone tail in armature space, read-only."""
    rotation_euler: Vector
    """rotation of the bone relative to its parent expressed as a set of euler angles, read-write."""
    rotation_mode: int
    """Method of updating the bone rotation, read-write."""
    rotation_quaternion: Vector
    """rotation of the bone relative to its parent expressed as a quaternion, read-write."""
    scale: Vector
    """scale of the bone relative to its parent, read-write."""

class BL_ArmatureConstraint(EXP_Value):
    active: bool
    """True if the constraint is active."""
    enforce: float
    """fraction of constraint effect that is enforced. Between 0 and 1."""
    headtail: float
    """Position of target between head and tail of the target bone: 0=head, 1=tail."""
    ik_dist: float
    """Distance the constraint is trying to maintain with target, only used when ik_type=CONSTRAINT_IK_DISTANCE."""
    ik_flag: int
    """Combination of IK constraint option flags, read-only."""
    ik_mode: int
    """Use one of these constants."""
    ik_type: int
    """Type of IK constraint, (read-only)."""
    ik_weight: float
    """Weight of the IK constraint between 0 and 1."""
    lin_error: float
    """runtime linear error (in Blender units) on constraint at the current frame."""
    name: str
    """Name of constraint constructed as <bone_name>:<constraint_name>. constraints list."""
    rot_error: float
    """Runtime rotation error (in radiant) on constraint at the current frame."""
    subtarget: KX_GameObject
    """Secondary target object for the constraint. The position of this object in the GE will be used as secondary target for the constraint."""
    target: KX_GameObject
    """Primary target object for the constraint. The position of this object in the GE will be used as target for the constraint."""
    type: int
    """Type of constraint, (read-only)."""

class SCA_IObject(EXP_Value):
    ...

class KX_GameObject(SCA_IObject):
    activitycullingdistance: Any
    actuators: list[Any]
    """a list of SCA_IActuator with string/index lookups and iterator support."""
    def addDebugProperty(self) -> Any:
        """Adds a single debug property to the debug list.

        :param debug: the debug state, default to True is no value passed.

        :param name: name of the property that added to the debug list.
        """
    def alignAxisToVect(self, vect, axis=2, factor=1.0) -> Any:
        """Aligns any of the game object's axis along the given vector.

        :param axis: The axis you want to align

        :param factor: Only rotate a feaction of the distance to the target vector (0.0 - 1.0)

        :param vect: a vector to align the axis.
        """
    angularDamping: float
    """The object's angular damping, also known as rotationation damping. Can be set simultaneously with linear damping using the :pysetDamping method."""
    angularVelocity: Any
    angularVelocityMax: Any
    """Clamp the maximum angular velocity to prevent objects rotating beyond a set speed. A value of 0.0 disables clamping; it does not stop rotation."""
    angularVelocityMin: Any
    """Enforces the object keeps rotating at a minimum velocity. A value of 0.0 disables this."""
    animationEventManager: Any
    anisotropicFriction: Any
    anisotropicFrictionCoefficients: Any
    def applyForce(self, force, local=...) -> Any:
        """Sets the game object's force.

        :param force: force vector.

        :param local: False: get the "global" force ie: relative to world orientation.
        """
    def applyImpulse(self, point, impulse, local=...) -> Any:
        """Applies an impulse to the game object.

        :param impulse: impulse vector.

        :param local: False: get the "global" impulse ie: relative to world coordinates with world orientation.

        :param point: the point to apply the impulse to (in world or local coordinates)
        """
    def applyMovement(self, movement, local=...) -> Any:
        """Sets the game object's movement.

        :param local: boolean

        :param movement: movement vector.
        """
    def applyRotation(self, rotation, local=...) -> Any:
        """Sets the game object's rotation.

        :param local: boolean

        :param rotation: rotation vector.
        """
    def applyTorque(self, torque, local=...) -> Any:
        """Sets the game object's torque.

        :param local: False: get the "global" torque ie: relative to world orientation.

        :param torque: torque vector.
        """
    attrDict: dict
    """get the objects internal python attribute dictionary for direct (faster) access."""
    batchGroup: KX_BatchGroup
    """The object batch group containing the batched mesh."""
    bendAngle: Any
    bendAxis: Any
    bendMaxAngle: Any
    blastSpeed: float
    """How hard the particles are thrown out, relative to the size preset (0.2 to 4)."""
    breakImpulse: float
    """The impulse that breaks this destructible object, from a collision or from KX_Scene.explode. Starts with the panel's Break Impulse; changing it affects only this instance. Reads 0.0 on objects that are not destructible, and setting it on them raises AttributeError."""
    burstSpeed: Any
    children: EXP_ListValue[KX_GameObject]
    """direct children of this object, (read-only)."""
    childrenRecursive: EXP_ListValue[KX_GameObject]
    """all children of this object including children's children, (read-only)."""
    def collide(self, obj) -> KX_CollisionContactPoint:
        """Test if this object collides object obj.

        :param obj: the object to test collision with
        """
    collisionCallbacks: list[Any]
    """A list of functions to be called when a collision occurs."""
    collisionGroup: Any
    """The object's collision group."""
    collisionMask: Any
    """The object's collision mask."""
    color: Vector
    """The object color of the object. [r, g, b, a]"""
    components: EXP_ListValue[KX_PythonComponent]
    """All python components."""
    controllers: list[SCA_ISensor]
    """a sequence of SCA_IController objects with string/index lookups and iterator support."""
    culled: bool
    """Returns True if the object is culled, else False."""
    cullingBox: KX_BoundingBox
    """The object's bounding volume box used for culling."""
    currentLodLevel: int
    """The index of the level of detail (LOD) currently used by this object (read-only)."""
    debrisLifetime: Any
    debug: bool
    """If true, the object's debug properties will be displayed on screen."""
    debugRecursive: bool
    """If true, the object's and children's debug properties will be displayed on screen."""
    decal: Any
    decalLife: Any
    decalSize: Any
    def dent(self, point, direction, impulse) -> bool:
        """Dent this deformable object (Deformation panel) as a hit of the given strength: the vertices within the panel's Radius of point move along direction (into the object) by (impulse - Dent Impulse) * Depth, limited by Max Depth. Only this instance changes, other objects sharing the mesh keep their shape.

        :param direction: hit direction in world space, flipped to point into the object.

        :param impulse: hit strength (N*s), compared with Dent Impulse.

        :param point: hit point in world space.
        """
    dentImpulse: Any
    def detonate(self) -> bool:
        """Make this explosive object explode now: a blast like KX_Scene.explode with the panel's settings, the Effect object, and the removal of the object. A destructible explosive breaks as well."""
    def disableRigidBody(self) -> Any:
        """Disables rigid body physics for this object."""
    effectLife: float
    """Seconds explosionEffect lives (0 = until its own logic removes it)."""
    def enableRigidBody(self) -> Any:
        """Enables rigid body physics for this object."""
    def endObject(self) -> Any:
        """Delete this object, can be used in place of the EndObject Actuator."""
    explosionEffect: KX_GameObject
    """Object of an inactive layer added at the blast (fire, smoke, a sound). It must be an object of the scene file."""
    explosionForce: float
    """Impulse of the blast at its center; it falls to 0 at explosionRadius."""
    explosionRadius: float
    """Radius of the blast of this explosive object, in meters. Like every attribute of the Explosive panel below, setting it on an object that is not explosive raises AttributeError."""
    fireAmount: float
    """How many core particles, relative to the size preset (0 to 4, 0 = none)."""
    fireColor: Vector
    """Tint of the core of the particle explosion (white = the natural colors of the style)."""
    fragments: Any
    friction: float
    """The object's friction"""
    fuse: float
    """Seconds left before this explosive object detonates. The fuse counts from the moment the object enters the game (scene start or KX_Scene.addObject). 0.0 means no fuse; setting a value lights it. Setting it on an object that is not explosive raises AttributeError."""
    def get(self, key, default=...) -> Any:
        """Return the value matching key, or the default value if its not found.

        :param default: optional default value is the key isn't matching, defaults to None if no value passed.

        :param key: the matching key
        """
    def getActionFrame(self, layer=...) -> float:
        """Gets the current frame of the action playing in the supplied layer.

        :param layer: The layer that you want to get the frame from, defaults to 0 if no value passed.
        """
    def getActionName(self, layer=...) -> str:
        """Gets the name of the current action playing in the supplied layer.

        :param layer: The layer that you want to get the action name from, defaults to 0 if no value passed.
        """
    def getAngularVelocity(self, local=...) -> Vector:
        """Gets the game object's angular velocity.

        :param local: False: get the "global" velocity ie: relative to world orientation.
        """
    def getAxisVect(self, vect) -> Any:
        """Returns the axis vector rotates by the object's worldspace orientation. This is the equivalent of multiplying the vector by the orientation matrix.

        :param vect: a vector to align the axis.
        """
    def getBoundBoxCorners(self, space='WORLD') -> list[Vector]:
        """The 8 corners of the bounding box. Corner i uses the max X when bit 0 is set, max Y for bit 1 and max Z for bit 2, so [0] is the minimum corner and [7] the maximum one.

        :param space: 'WORLD' (positions in the world), 'OFFSET' (from worldPosition, with
        """
    def getBoundBoxSize(self) -> Vector:
        """Size of the bounding box (cullingBox) along the object's own axes, with its world scale."""
    def getBoundBoxVolume(self) -> list[Any]:
        """Compatibility with Range 1.x scripts: returns [volume, corner1, ..., corner8]. The volume uses the world scale and the corners are the 'OFFSET' ones of getBoundBoxCorners, so obj.worldPosition + box[i] is a corner in the world."""
    def getCurvePoints(self) -> Any:
        ...
    def getDistanceTo(self, other) -> float:
        """:param other: a point or another KX_GameObject to measure the distance to."""
    def getLinearVelocity(self, local=...) -> Vector:
        """Gets the game object's linear velocity.

        :param local: False: get the "global" velocity ie: relative to world orientation.
        """
    def getNLAFrame(self) -> float:
        ...
    def getPhysicsId(self) -> Any:
        """Returns the user data object associated with this game object's physics controller."""
    def getPropertyNames(self) -> list[Any]:
        """Gets a list of all property names."""
    def getReactionForce(self) -> Vector:
        """Gets the game object's reaction force."""
    def getTurnTo(self) -> Any:
        ...
    def getVectTo(self, other) -> Any:
        """Returns the vector and the distance to another object or point. The vector is normalized unless the distance is 0, in which a zero length vector is returned.

        :param other: a point or another KX_GameObject to get the vector and distance to.
        """
    def getVehicle(self) -> Any:
        ...
    def getVehicleGearRatios(self) -> Any:
        ...
    def getVehicleGearboxType(self) -> Any:
        ...
    def getVehicleMaxRPM(self) -> Any:
        ...
    def getVehicleMaxTorque(self) -> Any:
        ...
    def getVehicleSteeringWheel(self) -> Any:
        ...
    def getVelocity(self, point=...) -> Vector:
        """Gets the game object's velocity at the specified point.

        :param point: optional point to return the velocity for, in local coordinates, defaults to (0, 0, 0) if no value passed.
        """
    gravity: Vector
    """The object's gravity. [x, y, z]"""
    groundMark: KX_GameObject
    """Mesh object of an inactive layer whose material is the ground mark. It must be an object of the scene file."""
    groupMembers: EXP_ListValue[KX_GameObject]
    """Returns the list of group members if the object is a group object (dupli group instance), otherwise None is returned."""
    groupObject: KX_GameObject
    """Returns the group object (dupli group instance) that the object belongs to or None if the object is not part of a group."""
    hiddenFromCamera: Any
    impactImpulse: Any
    isDeformable: Any
    isDestructible: bool
    """True if Physics > Destruction is enabled on this object, also for objects on an inactive layer (read-only)."""
    isExplosive: bool
    """True if Physics > Explosive is enabled on this object, also for objects on an inactive layer (read-only)."""
    def isPlayingAction(self, layer=...) -> bool:
        """Checks to see if there is an action playing in the given layer.

        :param layer: The layer to check for a playing action, defaults to 0 if no value passed.
        """
    def isPlayingNLA(self) -> bool:
        ...
    isSuspendDynamics: bool
    """The object's dynamic state (read-only)."""
    def is_playing_take(self) -> Any:
        ...
    layer: Any
    """The layer mask used for shadow and real-time cube map render."""
    life: float
    """The number of frames until the object ends, assumes one frame is 1/50 second (read-only)."""
    linVelocityMax: float
    """Clamp the maximum linear velocity to prevent objects moving beyond a set speed."""
    linVelocityMin: float
    """Enforces the object keeps moving at a minimum velocity."""
    linearDamping: float
    """The object's linear damping, also known as translational damping. Can be set simultaneously with angular damping using the :pysetDamping method."""
    linearVelocity: Any
    localAngularVelocity: Vector
    """The object's local angular velocity. [x, y, z]"""
    localInertia: Vector
    """the object's inertia vector in local coordinates. Read only."""
    localLinearVelocity: Vector
    """The object's local linear velocity. [x, y, z]"""
    localOrientation: Matrix
    """The object's local orientation. 3x3 Matrix. You can also write a Quaternion or Euler vector."""
    localPosition: Vector
    """The object's local position. [x, y, z]"""
    localScale: Vector
    """The object's local scaling factor. [sx, sy, sz]"""
    localTransform: Matrix
    """The object's local space transform matrix. 4x4 Matrix."""
    lodLevelMax: int
    """Highest level of detail (LOD) index this object may switch to; -1 (default) means no limit. Farther levels are skipped while it is set, e.g. a ragdoll character keeps a mesh level instead of a sitting impostor card."""
    lodManager: KX_LodManager
    """Return the lod manager of this object. Needed to access to lod manager to set attributes of levels of detail of this object. The lod manager is shared between instance objects and can be changed to use the lod levels of an other object."""
    logicCulling: bool
    """True if the object suspends its logic and animation depending on its nearest distance to any camera."""
    logicCullingComponents: bool
    """No Suspend execution of object components."""
    logicCullingRadius: float
    """Suspend object's logic and animation if this radius is smaller than its nearest distance to any camera and logicCulling set to True."""
    def lookAt(self) -> Any:
        ...
    markLife: float
    """Seconds the ground mark stays (0 = forever)."""
    markSize: float
    """Size of the ground mark, relative to particleSize (0.1 to 4)."""
    mass: float
    """The object's mass"""
    maxDecals: Any
    meshes: list[KX_Mesh]
    """a list meshes for this object."""
    name: str
    """The object's name."""
    net: Any
    occlusion: bool
    """occlusion capability flag."""
    onBreak: list[Any]
    """A list of functions called when this object breaks, with the arguments (object, fragments). They run right after the fragments enter the scene, before any explosion pushes them. Callbacks set on an object of an inactive layer are copied to every object added from it."""
    onDent: list[Any]
    """A list of functions called when this deformable object dents (collision, explosion or"""
    onExplode: list[Any]
    """A list of functions called when this object explodes, with the arguments (object, position). On an object that is both destructible and explosive, they run after onBreak. Callbacks set on an object of an inactive layer are copied to every object added from it."""
    orientation: Matrix
    """The object's orientation. 3x3 Matrix. You can also write a Quaternion or Euler vector. On write: local orientation, on read: world orientation"""
    parent: KX_GameObject
    """The object's parent object. (read-only)."""
    parentRecursive: Any
    particleSize: str
    """Size preset of the particle explosion: 'TINY', 'SMALL', 'MEDIUM', 'LARGE' or 'HUGE'. It also scales the ground mark."""
    particleStyle: str
    """What the particle explosion is made of: 'FIRE', 'ELECTRIC', 'CONCRETE' or 'WATER'. Setting it resets fireColor, smokeColor and sparkColor to the colors of the style."""
    particles: Any
    particlesMix: Any
    passIndex: Any
    physicsCulling: bool
    """True if the object suspends its physics depending on its nearest distance to any camera."""
    physicsCullingRadius: float
    """Suspend object's physics if this radius is smaller than its nearest distance to any camera and physicsCulling set to True."""
    physicsCullingVelocity: bool
    """Stop physics after the object stops."""
    def playAction(self, name, start_frame, end_frame, layer=0, priority=0, blendin=0, play_mode=..., layer_weight=0.0, ipo_flags=0, speed=1.0, blend_mode=...) -> Any:
        """Plays an action.

        :param blend_mode: how to blend this layer with previous layers

        :param blendin: the amount of blending between this animation and the previous one on this layer

        :param end: the end frame of the action

        :param ipo_flags: flags for the old IPO behaviors (force, etc)

        :param layer: the layer the action will play in (actions in different layers are added/blended together)

        :param layer_weight: how much of the previous layer to use for blending

        :param name: the name of the action

        :param play_mode: the play mode

        :param priority: only play this action if there isn't an action currently playing in this layer with a higher (lower number) priority

        :param speed: the playback speed of the action as a factor (1.0 = normal speed, 2.0 = 2x speed, etc)

        :param start: the start frame of the action
        """
    def playNLA(self, speed=1.0, loop=True) -> bool:
        """Plays the NLA tracks of an armature, like the NLA Editor does. Muted tracks and strips are skipped, Solo is respected and the tracks are blended from the bottom up (Replace and Add, influence, blend in/out, repeat, scale, reverse and extrapolation). Actions played with playAction are blended on top of the NLA result.

        :param loop: Restart from the first strip after the last one ends, else hold the last frame.

        :param speed: Playback speed (1.0 = scene animation frame rate, 0.0 = stopped, use setNLAFrame; negative plays backwards from the last frame).
        """
    def play_take(self) -> Any:
        ...
    position: Vector
    """The object's position. [x, y, z] On write: local position, on read: world position"""
    def rayCast(self, objto, objfrom=None, dist=0, prop="", face=False, xray=False, poly=0, mask=0xFFFF) -> Any:
        """Look from a point/object to another point/object and find first object hit within dist that matches prop. if poly is 0, returns a 3-tuple with object reference, hit point and hit normal or (None, None, None) if no hit. if poly is 1, returns a 4-tuple with in addition a KX_PolyProxy as 4th element.

        :param dist: max distance to look (can be negative => look behind); 0 or omitted => detect up to to

        :param face: normal option: 1=>return face normal; 0 or omitted => normal is oriented towards origin

        :param mask: collision mask: The collision mask (16 layers mapped to a 16-bit integer) is combined with each object's collision group, to hit only a subset of the objects...

        :param objfrom: [x, y, z] or object from which the ray is casted; None or omitted => use self object center

        :param objto: [x, y, z] or object to which the ray is casted

        :param poly: polygon option: 0, 1 or 2 to return a 3-, 4- or 5-tuple with information on the face hit.

        :param prop: property name that object must have; can be omitted or "" => detect any object

        :param xray: X-ray option: 1=>skip objects that don't match prop; 0 or omitted => stop on first object
        """
    def rayCastTo(self, other, dist=0, prop="") -> KX_GameObject:
        """Look towards another point/object and find first object hit within dist that matches prop.

        :param dist: max distance to look (can be negative => look behind); 0 or omitted => detect up to other

        :param other: [x, y, z] or object towards which the ray is casted

        :param prop: property name that object must have; can be omitted => detect any object
        """
    def reinstancePhysicsMesh(self, gameObject, meshObject, dupli) -> bool:
        """Updates the physics system with the changed mesh.

        :param dupli: optional argument, duplicate the physics shape.

        :param gameObject: optional argument, set the physics shape from this gameObjets mesh.

        :param meshObject: optional argument, set the physics shape from this mesh.
        """
    def removeParent(self) -> Any:
        """Removes this objects parent."""
    def replaceMesh(self, mesh, useDisplayMesh=True, usePhysicsMesh=False) -> Any:
        """Replace the mesh of this object with a new mesh. This works the same was as the actuator.

        :param mesh: mesh to replace or the meshes name.

        :param useDisplayMesh: when enabled the display mesh will be replaced (optional argument).

        :param usePhysicsMesh: when enabled the physics mesh will be replaced (optional argument).
        """
    def replacePhysicsShape(self, gameObject) -> bool:
        """Replace the current physics shape.

        :param gameObject: set the physics shape from this gameObjets.
        """
    def resetDent(self) -> bool:
        """Restore the shape of a dented object."""
    def restoreDynamics(self) -> Any:
        """Resumes dynamics physics for this object. Also reinstates collisions; the object will no longer be a ghost."""
    def restorePhysics(self) -> Any:
        """Resumes physics for this object. Also reinstates collisions."""
    def resumeAnimations(self) -> Any:
        ...
    scaling: Vector
    """The object's scaling factor. [sx, sy, sz] On write: local scaling, on read: world scaling"""
    scene: KX_Scene
    """The object's scene. (read-only)."""
    def sendMessage(self, subject, body="", to="") -> Any:
        """Sends a message.

        :param body: The body of the message (optional)

        :param subject: The subject of the message

        :param to: The name of the object to send the message to (optional)
        """
    sensors: list[Any]
    """a sequence of SCA_ISensor objects with string/index lookups and iterator support."""
    def setActionFrame(self, frame, layer=...) -> Any:
        """Set the current frame of the action playing in the supplied layer.

        :param frame: The frame to set the action to

        :param layer: The layer where you want to set the frame, default to 0 if no value passed.
        """
    def setActionLayerSpeed(self) -> Any:
        ...
    def setActionLayerWeight(self) -> Any:
        ...
    def setAngularVelocity(self, velocity, local=...) -> Any:
        """Sets the game object's angular velocity.

        :param local: False: get the "global" velocity ie: relative to world orientation.

        :param velocity: angular velocity vector.
        """
    def setCcdMotionThreshold(self) -> Any:
        ...
    def setCcdSweptSphereRadius(self) -> Any:
        ...
    def setCollisionMargin(self, margin) -> Any:
        """Set the objects collision margin.

        :param margin: the collision margin distance in blender units.
        """
    def setDamping(self, linear_damping, angular_damping) -> Any:
        """Sets both the :pylinearDamping and :pyangularDamping simultaneously. This is more efficient than setting both properties individually.

        :param angular_damping: Angular ("rotational") damping factor.

        :param linear_damping: Linear ("translational") damping factor.
        """
    def setHalfAnimations(self) -> Any:
        ...
    def setLinearVelocity(self, velocity, local=...) -> Any:
        """Sets the game object's linear velocity.

        :param local: False: get the "global" velocity ie: relative to world orientation.

        :param velocity: linear velocity vector.
        """
    def setNLAFrame(self, frame) -> Any:
        """Jumps the NLA to the given frame, clamped to the range of the strips.

        :param frame: The NLA frame.
        """
    def setOcclusion(self, occlusion, recursive=...) -> Any:
        """Sets the game object's occlusion capability.

        :param occlusion: the state to set the occlusion to.

        :param recursive: optional argument to set all childrens occlusion flag too, defaults to False if no value passed.
        """
    def setParent(self, parent, compound=True, ghost=True) -> Any:
        """Sets this object's parent. Control the shape status with the optional compound and ghost parameters:

        :param compound: whether the shape should be added to the parent compound shape.

        :param ghost: whether the object should be ghost while parented.

        :param parent: new parent object.
        """
    def setSoftAnchorsHardness(self) -> Any:
        ...
    def setSoftAngularStiffness(self) -> Any:
        ...
    def setSoftClusterSolverIterations(self) -> Any:
        ...
    def setSoftContactsHardness(self) -> Any:
        ...
    def setSoftDampingCoefficient(self) -> Any:
        ...
    def setSoftDragCoefficient(self) -> Any:
        ...
    def setSoftDriftSolverIterations(self) -> Any:
        ...
    def setSoftDynamicFrictionCoefficient(self) -> Any:
        ...
    def setSoftKineticContactsHardness(self) -> Any:
        ...
    def setSoftLiftCoefficient(self) -> Any:
        ...
    def setSoftLinearStiffness(self) -> Any:
        ...
    def setSoftPoseMatching(self) -> Any:
        ...
    def setSoftPoseMatchingCoefficient(self) -> Any:
        ...
    def setSoftPositionSolverIterations(self) -> Any:
        ...
    def setSoftPressureCoefficient(self) -> Any:
        ...
    def setSoftRigidContactsHardness(self) -> Any:
        ...
    def setSoftVelocitiesCorrectionFactor(self) -> Any:
        ...
    def setSoftVelocitySolverIterations(self) -> Any:
        ...
    def setSoftVolume(self) -> Any:
        ...
    def setSoftVolumeConversationCoefficient(self) -> Any:
        ...
    def setSoftVsKineticHardness(self) -> Any:
        ...
    def setSoftVsKineticImpulseSplitCluster(self) -> Any:
        ...
    def setSoftVsRigidHardness(self) -> Any:
        ...
    def setSoftVsRigidImpulseSplitCluster(self) -> Any:
        ...
    def setSoftVsSoftHardness(self) -> Any:
        ...
    def setSoftVsSoftImpulseSplitCluster(self) -> Any:
        ...
    def setVehicleGearRatios(self) -> Any:
        ...
    def setVehicleMaxRPM(self) -> Any:
        ...
    def setVehicleMaxTorque(self) -> Any:
        ...
    def setVisible(self, visible, recursive=...) -> Any:
        """Sets the game object's visible flag.

        :param recursive: optional argument to set all childrens visibility flag too, defaults to False if no value passed.

        :param visible: the visible state to set.
        """
    def shatter(self, origin=None, burst=None) -> list[KX_GameObject]:
        """Break this destructible object now, replacing it by the pieces of its Fragments group. On an object that is also explosive, it detonates as well.

        :param burst: The speed given to the pieces away from origin, the panel's Burst Speed by default.

        :param origin: The point the pieces fly away from, the object's position by default.
        """
    smokeAmount: float
    """How much smoke, relative to the size preset (0 to 4, 0 = none)."""
    smokeColor: Vector
    """Color of the smoke (dust cloud, mist) of the particle explosion when it is born."""
    smokeDuration: float
    """How long the smoke lasts, relative to the style (0.2 to 4)."""
    sparkAmount: float
    """How many sparks, relative to the size preset (0 to 4, 0 = none)."""
    sparkColor: Vector
    """Color of the sparks (debris, droplets) of the particle explosion."""
    state: int
    """the game object's state bitmask, using the first 30 bits, one bit must always be set."""
    def stopAction(self, layer=...) -> Any:
        """Stop playing the action on the given layer.

        :param layer: The layer to stop playing, defaults to 0 if no value passed.
        """
    def stopNLA(self) -> Any:
        """Stops the NLA playback. The armature keeps its current pose."""
    def stop_take(self) -> Any:
        ...
    def strikeLightning(self) -> Any:
        ...
    def suspendAnimations(self) -> Any:
        ...
    def suspendDynamics(self, ghost=...) -> Any:
        """Suspends dynamics physics for this object.

        :param ghost: When set to True, collisions with the object will be ignored, similar to the "ghost" checkbox in
        """
    def suspendPhysics(self, freeConstraints=...) -> Any:
        """Suspends physics for this object.

        :param freeConstraints: When set to True physics constraints used by the object are deleted.
        """
    timeOffset: float
    """adjust the slowparent delay at runtime."""
    upBias: float
    """Extra upward push of the blast (0 to 5), so objects fly up instead of sliding on the floor."""
    useBreakOnCollision: Any
    useChainReaction: Any
    useDentOnCollision: Any
    useExplodeOnImpact: Any
    useGroundMark: bool
    """Paint the material of groundMark on the static surface under the blast."""
    useInheritVelocity: Any
    useMarkNearby: bool
    """With useGroundMark: also paint a smaller mark on the objects around the blast (12 closest)."""
    useOcclusion: bool
    """Static geometry between the blast and an object shields it."""
    useParticleExplosion: bool
    """Built-in GPU particle explosion (core, smoke and debris) at the blast."""
    visible: bool
    """visibility flag."""
    worldAngularVelocity: Vector
    """The object's world angular velocity. [x, y, z]"""
    worldLinearVelocity: Vector
    """The object's world linear velocity. [x, y, z]"""
    worldOrientation: Matrix
    """The object's world orientation. 3x3 Matrix."""
    worldPosition: Vector
    """The object's world position. [x, y, z]"""
    worldScale: Vector
    """The object's world scaling factor. [sx, sy, sz]"""
    worldTransform: Matrix
    """The object's world space transform matrix. 4x4 Matrix."""
    def __getitem__(self, key: str) -> Any: ...
    def __setitem__(self, key: str, value: Any) -> None: ...
    def __delitem__(self, key: str) -> None: ...
    def __contains__(self, key: str) -> bool: ...

class BL_ArmatureObject(KX_GameObject):
    channels: list[BL_ArmatureChannel]
    """The list of armature channels. Elements of the list can be accessed by index or name the bone."""
    def clearBoneRotationOffset(self) -> Any:
        ...
    constraints: list[BL_ArmatureConstraint]
    """The list of armature constraint defined on this armature. Elements of the list can be accessed by index or string. The key format for string access is '<bone_name>:<constraint_name>'."""
    def draw(self) -> Any:
        """Draw Debug Armature"""
    def setBoneRotationOffset(self) -> Any:
        ...
    def update(self) -> Any:
        """Ensures that the armature will be updated on next graphic frame."""

class BL_Shader(EXP_PyObjectPlus):
    bindCallbacks: list[Any]
    """The list of python callbacks executed when the shader is begin used to render."""
    def delSource(self) -> Any:
        """Clear the shader. Use this method before the source is changed with setSource."""
    enabled: bool
    """Set shader enabled to use."""
    def getFragmentProg(self) -> str:
        """Returns the fragment program."""
    def getVertexProg(self) -> str:
        """Get the vertex program."""
    def isValid(self) -> bool:
        """Check if the shader is valid."""
    objectCallbacks: list[Any]
    """The list of python callbacks executed when the shader is used to render an object. All the functions can expect as argument the object currently rendered."""
    def setAttrib(self, enum) -> Any:
        """Set attribute location. (The parameter is ignored a.t.m. and the value of "tangent" is always used.)

        :param enum: attribute location value
        """
    def setSampler(self, name, index) -> Any:
        """Set uniform texture sample index.

        :param index: Texture sample index.

        :param name: Uniform name
        """
    def setSource(self, vertexProgram, fragmentProgram, apply) -> Any:
        """Set the vertex and fragment programs

        :param apply: Enable the shader.

        :param fragmentProgram: Fragment program

        :param vertexProgram: Vertex program
        """
    def setSourceList(self, sources, apply) -> Any:
        """Set the vertex, fragment and geometry shader programs.

        :param apply: Enable the shader.

        :param sources: Dictionary of all programs. The keys vertex, fragment and geometry represent shader programs of the same name.
        """
    def setUniform1f(self, name, fx) -> Any:
        """Set a uniform with 1 float value.

        :param fx: Uniform value

        :param name: the uniform name
        """
    def setUniform1i(self, name, ix) -> Any:
        """Set a uniform with an integer value.

        :param ix: the uniform value

        :param name: the uniform name
        """
    def setUniform2f(self, name, fx, fy) -> Any:
        """Set a uniform with 2 float values

        :param fx: first float value

        :param fy: second float value

        :param name: the uniform name
        """
    def setUniform2i(self, name, ix, iy) -> Any:
        """Set a uniform with 2 integer values

        :param ix: first integer value

        :param iy: second integer value

        :param name: the uniform name
        """
    def setUniform3f(self, name, fx, fy, fz) -> Any:
        """Set a uniform with 3 float values.

        :param fx: first float value

        :param fy: second float value

        :param fz: third float value

        :param name: the uniform name
        """
    def setUniform3i(self, name, ix, iy, iz) -> Any:
        """Set a uniform with 3 integer values

        :param ix: first integer value

        :param iy: second integer value

        :param iz: third integer value

        :param name: the uniform name
        """
    def setUniform4f(self, name, fx, fy, fz, fw) -> Any:
        """Set a uniform with 4 float values.

        :param fw: fourth float value

        :param fx: first float value

        :param fy: second float value

        :param fz: third float value

        :param name: the uniform name
        """
    def setUniform4i(self, name, ix, iy, iz, iw) -> Any:
        """Set a uniform with 4 integer values

        :param iw: fourth integer value

        :param ix: first integer value

        :param iy: second integer value

        :param iz: third integer value

        :param name: the uniform name
        """
    def setUniformDef(self, name, type) -> Any:
        """Define a new uniform

        :param name: the uniform name

        :param type: uniform type, one of these constants
        """
    def setUniformEyef(self, name) -> Any:
        """Set a uniform with a float value that reflects the eye being render in stereo mode: 0.0 for the left eye, 0.5 for the right eye. In non stereo mode, the value of the uniform is fixed to 0.0.

        :param name: the uniform name
        """
    def setUniformMatrix3(self, name, mat, transpose) -> Any:
        """Set a uniform with a 3x3 matrix value

        :param mat: A 3x3 matrix [[f, f, f], [f, f, f], [f, f, f]]

        :param name: the uniform name

        :param transpose: set to True to transpose the matrix
        """
    def setUniformMatrix4(self, name, mat, transpose) -> Any:
        """Set a uniform with a 4x4 matrix value

        :param mat: A 4x4 matrix [[f, f, f, f], [f, f, f, f], [f, f, f, f], [f, f, f, f]]

        :param name: the uniform name

        :param transpose: set to True to transpose the matrix
        """
    def setUniformfv(self, name, fList) -> Any:
        """Set a uniform with a list of float values

        :param fList: a list (2, 3 or 4 elements) of float values

        :param name: the uniform name
        """
    def setUniformiv(self, name, iList) -> Any:
        """Set a uniform with a list of integer values

        :param iList: a list (2, 3 or 4 elements) of integer values

        :param name: the uniform name
        """
    def validate(self) -> Any:
        ...

class BL_Texture(EXP_Value):
    alpha: float
    """Amount texture affects alpha."""
    bindCode: int
    """Texture bind code/Id/number."""
    diffuseFactor: float
    """Amount texture affects diffuse color."""
    diffuseIntensity: float
    """Amount texture affects diffuse reflectivity."""
    emit: float
    """Amount texture affects emission."""
    hardness: float
    """Amount texture affects hardness."""
    ior: float
    """Index Of Refraction used to compute refraction."""
    lodBias: float
    """Amount bias on mipmapping."""
    mirror: float
    """Amount texture affects mirror color."""
    normal: float
    """Amount texture affects normal values."""
    parallaxBump: float
    """Height of parallax occlusion mapping."""
    parallaxStep: float
    """Number of steps to achieve parallax effect."""
    refractionRatio: float
    """Amount refraction mixed with reflection."""
    renderer: KX_CubeMap
    """Texture renderer of this texture."""
    specularFactor: float
    """Amount texture affects specular color."""
    specularIntensity: float
    """Amount texture affects specular reflectivity."""
    uvOffset: Vector
    """Offset applied to texture UV coordinates (mainly translation on U and V axis)."""
    uvRotation: float
    """Rotation applied to texture UV coordinates."""
    uvSize: Vector
    """Scale applied to texture UV coordinates."""

class EXP_ListValue(EXP_Value, Generic[_T]):
    def append(self, val) -> Any:
        """Add an item to the list (like pythons append)"""
    def count(self, val) -> int:
        """Count the number of instances of a value in the list."""
    def filter(self, name, prop) -> Any:
        """Return a list of items with name matching name regex and with a property matching prop regex. If name is empty every items are checked, if prop is empty no property check is proceeded."""
    def from_id(self, id) -> Any:
        """This is a funtion especially for the game engine to return a value with a spesific id."""
    def index(self, val) -> int:
        """Return the index of a value in the list."""
    def reverse(self) -> Any:
        """Reverse the order of the list."""
    def __getitem__(self, key: int | str) -> _T: ...
    def __iter__(self) -> Iterator[_T]: ...
    def __len__(self) -> int: ...
    def __contains__(self, key: Any) -> bool: ...
    def get(self, key: str, default: Any = None) -> _T: ...

class EXP_ListWrapper(EXP_Value):
    def get(self) -> Any:
        ...

class KX_2DFilter(BL_Shader):
    activeUniforms: Any
    def addOffScreen(self, slots, depth=False, width=-1, height=-1, hdr=..., mipmap=False) -> Any:
        """Register a custom off screen to render the filter to.

        :param depth: True of the off screen use a depth texture (optional).

        :param hdr: The image quality HDR of the color textures (optional).

        :param height: The off screen height, -1 if it can be resized dynamically when the viewport dimensions changed (optional).

        :param mipmap: True if the color texture generate mipmap at the end of the filter rendering (optional).

        :param slots: The number of color texture attached to the off screen, between 0 and 8 excluded.

        :param width: The off screen width, -1 if it can be resized dynamically when the viewport dimensions changed (optional).
        """
    compileLog: Any
    mipmap: bool
    """Request mipmap generation of the render bgl_RenderedTexture texture. Accessing mipmapping level is similar to:"""
    offScreen: KX_2DFilterOffScreen
    """The custom off screen the filter render to (read-only)."""
    def recompile(self) -> Any:
        ...
    def removeOffScreen(self) -> Any:
        ...
    def setCubeMap(self, index, bindCode, samplerName="") -> Any:
        """Set specified cube map texture bind code bindCode in specified slot index. Any call to setCubeMap should be followed by a call to BL_Shader.setSampler with the same index if sampleName is not specified.

        :param bindCode: The cube map texture bind code/Id.

        :param index: The texture slot.

        :param samplerName: The shader sampler name set to index if samplerName is passed in the function. (optional)
        """
    def setTexture(self, index, bindCode, samplerName="") -> Any:
        """Set specified texture bind code bindCode in specified slot index. Any call to setTexture should be followed by a call to BL_Shader.setSampler with the same index if sampleName is not specified.

        :param bindCode: The texture bind code/Id.

        :param index: The texture slot.

        :param samplerName: The shader sampler name set to index if samplerName is passed in the function. (optional)
        """
    def setUniform(self) -> Any:
        ...
    sourceName: Any
    sourcePath: Any

class KX_2DFilterManager(EXP_PyObjectPlus):
    def addFilter(self, index, type, fragmentProgram="", owner=None, mipmap=False) -> KX_2DFilter:
        """Add a filter to the pass index index, type type and fragment program if custom filter.

        :param fragmentProgram: The filter shader fragment program.

        :param index: The filter pass index.

        :param mipmap: Generate mipmaps of the filter input. (optional)

        :param owner: Object whose game properties feed the uniforms of the same name, like the Filter 2D actuator. (optional)

        :param type: The filter type, one of:
        """
    def changeBloomValues(self) -> Any:
        ...
    def changeFxaaValues(self) -> Any:
        ...
    def changeGrainValues(self) -> Any:
        ...
    def changeLightScatterValues(self) -> Any:
        ...
    def changeSSAOValues(self) -> Any:
        ...
    def changeSSGIValues(self) -> Any:
        ...
    def changeSSRValues(self) -> Any:
        ...
    def changeTonemapValues(self) -> Any:
        ...
    compositor: Any
    fxaaEdgeThreshold: Any
    fxaaEdgeThresholdMin: Any
    fxaaEnabled: Any
    fxaaSearchSteps: Any
    fxaaSubpix: Any
    def getFilter(self, index) -> KX_2DFilter:
        """Return filter to the pass index index.

        :param index: The filter pass index.
        """
    grainEnabled: Any
    grainStrength: Any
    def removeFilter(self, index) -> Any:
        """Remove filter to the pass index index.

        :param index: The filter pass index.
        """
    def setBuiltinFilterEnabled(self, type, enabled=True) -> bool:
        """Turn a built-in filter on or off with its current values, like the Filter 2D actuator.

        :param enabled: The new state.

        :param type: bge.logic.RAS_2DFILTER_FXAA, RAS_2DFILTER_BLOOM, RAS_2DFILTER_TONEMAP, RAS_2DFILTER_SSAO,
        """
    taaEnabled: Any
    taaSharpen: Any
    taaUpscale: Any

class KX_2DFilterOffScreen(EXP_Value):
    colorBindCodes: list[Any]
    """The bind code of the color textures attached to the off screen (read-only)."""
    depthBindCode: int
    """The bind code of the depth texture attached to the off screen (read-only)."""
    height: int
    """The off screen height, -1 if the off screen can be resized dynamically (read-only)."""
    width: int
    """The off screen width, -1 if the off screen can be resized dynamically (read-only)."""

class KX_AddObjectActuator(SCA_ILogicBrick):
    angularVelocity: Any
    def instantAddObject(self) -> Any:
        ...
    linearVelocity: Any
    object: Any
    objectLastCreated: Any
    time: Any

class KX_AnimationEvent(EXP_Value):
    def getFireCount(self) -> Any:
        ...
    triggers: Any

class KX_AnimationEventManager(EXP_Value):
    events: Any

class SCA_ISensor(SCA_ILogicBrick):
    frequency: int
    """The frequency for pulse mode sensors. (Deprecated: use SCA_ISensor.skippedTicks)"""
    invert: bool
    """Flag to set if this sensor activates on positive or negative events."""
    level: bool
    """level Option whether to detect level or edge transition when entering a state. It makes a difference only in case of logic state transition (state actuator). A level detector will immediately generate a pulse, negative or positive depending on the sensor condition, as soon as the state is activated."""
    neg_ticks: int
    """The number of ticks since the last negative pulse (read-only)."""
    pos_ticks: int
    """The number of ticks since the last positive pulse (read-only)."""
    positive: bool
    """True if this sensor brick is in a positive state. (read-only)."""
    def reset(self) -> Any:
        """Reset sensor internal state, effect depends on the type of sensor and settings."""
    skippedTicks: int
    """Number of logic ticks skipped between 2 active pulses"""
    status: int
    """The status of the sensor (read-only): can be one of these constants."""
    tap: bool
    """When enabled only sensors that are just activated will send a positive event, after this they will be detected as negative by the controllers. This will make a key thats held act as if its only tapped for an instant. note: mutually exclusive with level, enabling will disable level."""
    triggered: bool
    """True if this sensor brick is in a positive state. (read-only)."""
    useDeltaTime: Any
    useNegPulseMode: bool
    """Flag to turn negative pulse mode on and off."""
    usePosPulseMode: bool
    """Flag to turn positive pulse mode on and off."""

class KX_ArmatureSensor(SCA_ISensor):
    constraint: BL_ArmatureConstraint
    """The constraint object this sensor is watching."""
    type: int
    """The type of measurement that the sensor make when it is active."""
    value: float
    """The threshold used in the comparison with the constraint error The linear error is only updated on CopyPose/Distance IK constraint with iTaSC solver The rotation error is only updated on CopyPose+rotation IK constraint with iTaSC solver The linear error on CopyPose is always >= 0: it is the norm of the distance betw..."""

class KX_BatchGroup(EXP_PyObjectPlus):
    def destruct(self) -> Any:
        ...
    def merge(self, objects) -> Any:
        """Merge meshes using the transformation of the objects using them.

        :param objects: The objects to merge.
        """
    objects: EXP_ListValue[KX_GameObject]
    """The list of the objects merged. (read only)"""
    referenceObject: Any
    """The object used for object rendering settings (layer, color...)."""
    def split(self, objects) -> Any:
        """Split the meshes of the objects using them and restore their original meshes.

        :param objects: The objects to unmerge.
        """

class KX_BlenderMaterial(EXP_Value):
    alpha: float
    """The material's alpha transparency."""
    ambient: float
    """Amount of ambient light on the material."""
    blending: Any
    """Ints used for pixel blending, (src, dst), matching the setBlending method."""
    diffuseColor: Color
    """The material's diffuse color."""
    diffuseIntensity: float
    """The material's amount of diffuse reflection."""
    emit: float
    """Amount of light to emit."""
    def getScriptUniform(self, name) -> Any:
        """Current value of a u_ uniform of the GLSL Script nodes of this material.

        :param name: Name of the uniform.
        """
    def getShader(self) -> BL_Shader:
        """Returns the material's shader."""
    def getTextureBindcode(self, textureslot) -> int:
        """Returns the material's texture OpenGL bind code/id/number/name.

        :param textureslot: Specifies the texture slot number
        """
    hardness: int
    """How hard (sharp) the material's specular reflection is."""
    passIndex: Any
    def setBlending(self, src, dest) -> Any:
        """Set the pixel color arithmetic functions.

        :param dest: Specifies how the red, green, blue, and alpha destination blending factors are computed, one of...

        :param src: Specifies how the red, green, blue, and alpha source blending factors are computed, one of...
        """
    def setScriptUniform(self, name, value) -> bool:
        """Set a u_ uniform declared in the Text of the GLSL Script nodes of this material (uniform float u_speed;). The value is sent to the GPU on the next draw, the shader is not compiled again. A uniform whose socket is linked to another node is not affected.

        :param name: Name of the uniform, as written in the Text ("u_speed").

        :param value: A number, or a sequence of up to 4 numbers for vec2/vec3/vec4.
        """
    shader: BL_Shader
    """The material's shader."""
    specularAlpha: float
    """Alpha transparency for specular areas."""
    specularColor: Color
    """The material's specular color."""
    specularIntensity: float
    """How intense (bright) the material's specular reflection is."""
    textures: list[BL_Texture]
    """List of all material's textures."""

class KX_BoundingBox(EXP_PyObjectPlus):
    autoUpdate: bool
    """Allow to update the bounding box if the mesh is modified."""
    center: Vector
    """The center of the bounding box. (read only)"""
    max: Vector
    """The maximal point in x, y and z axis of the bounding box."""
    min: Vector
    """The minimal point in x, y and z axis of the bounding box."""
    radius: float
    """The radius of the bounding box. (read only)"""
    volume: Any

class KX_Camera(KX_GameObject):
    INSIDE: Any
    """See sphereInsideFrustum and boxInsideFrustum"""
    INTERSECT: Any
    """See sphereInsideFrustum and boxInsideFrustum"""
    OUTSIDE: Any
    """See sphereInsideFrustum and boxInsideFrustum"""
    activityCulling: bool
    """True if this camera is used to compute object distance for object activity culling."""
    def boxInsideFrustum(self, box) -> Any:
        """Tests the given box against the view frustum.

        :param box: Eight (8) corner points of the box (in world coordinates), or a
        """
    cameraSpeed: Any
    camera_to_world: Matrix
    """This camera's camera to world transform. (read-only)."""
    catEyeStrength: Any
    chromaticStrength: Any
    directionalBlurMax: Any
    directionalBlurStrength: Any
    dofBlur: Any
    dofQuality: Any
    droneAmplitude: Any
    droneFrequency: Any
    far: float
    """The camera's far clip distance."""
    fisheyeStrength: Any
    focusDistance: Any
    focusManualDistance: Any
    focusMode: Any
    focusObject: Any
    focusPosition: Any
    focusProperty: Any
    focusRange: Any
    focusScreenPosition: Any
    focusSmooth: Any
    focusTarget: Any
    focusValid: Any
    fov: float
    """The camera's field of view value."""
    frustum_culling: bool
    """True if this camera is frustum culling."""
    gazeDirection: Any
    def getCameraToWorld(self) -> Matrix:
        """Returns the camera-to-world transform."""
    def getScreenPosition(self, object) -> list[Any]:
        """Gets the position of an object projected on screen space.

        :param object: object name or list [x, y, z]
        """
    def getScreenRay(self, x, y, dist, property="", xray=False, mask=0xFFFF) -> KX_GameObject:
        """Look towards a screen coordinate (x, y) and find first object hit within dist that matches prop. The ray is similar to KX_GameObject->rayCastTo.

        :param dist: max distance to look (can be negative => look behind); 0 or omitted => detect up to other

        :param mask: collision mask, only objects of these collision groups are hit

        :param property: property name that object must have; can be omitted => detect any object

        :param x: X Axis

        :param xray: the ray goes through objects without the property, like the X-Ray option of the Mouse sensor

        :param y: Y Axis
        """
    def getScreenVect(self, x, y) -> Any:
        """Gets the vector from the camera position in the screen coordinate direction.

        :param x: X Axis

        :param y: Y Axis
        """
    def getWorldToCamera(self) -> Matrix:
        """Returns the world-to-camera transform."""
    lens: float
    """The camera's lens value."""
    lodDistanceFactor: float
    """The factor to multiply distance to camera to adjust levels of detail. A float < 1.0f will make the distance to camera used to compute levels of detail decrease."""
    modelview_matrix: Matrix
    """This camera's 4x4 model view matrix. (read-only)."""
    near: float
    """The camera's near clip distance."""
    ortho_scale: float
    """The camera's view scale when in orthographic mode."""
    perspective: bool
    """True if this camera has a perspective transform, False for an orthographic projection."""
    def pointInsideFrustum(self, point) -> bool:
        """Tests the given point against the view frustum.

        :param point: The point to test (in world coordinates.)
        """
    projectionMatrixLeft: Matrix
    """This camera's 4x4 left eye projection matrix."""
    projectionMatrixRight: Matrix
    """This camera's 4x4 right eye projection matrix."""
    projection_matrix: Matrix
    """This camera's 4x4 projection matrix."""
    def setOnTop(self) -> Any:
        """Set this cameras viewport ontop of all other viewport."""
    def setViewport(self, left, bottom, right, top) -> Any:
        """Sets the region of this viewport on the screen in pixels.

        :param bottom: bottom pixel coordinate of this viewport

        :param left: left pixel coordinate of this viewport

        :param right: right pixel coordinate of this viewport

        :param top: top pixel coordinate of this viewport
        """
    def shake(self) -> Any:
        ...
    shakeAmplitude: Any
    shakeDecay: Any
    shakeFrequency: Any
    shakeTrauma: Any
    shift_x: float
    """The camera's horizontal shift."""
    shift_y: float
    """The camera's vertical shift."""
    speedBlurMaxSpeed: Any
    speedBlurStrength: Any
    speedOverride: Any
    def sphereInsideFrustum(self, centre, radius) -> int:
        """Tests the given sphere against the view frustum.

        :param centre: The centre of the sphere (in world coordinates.)

        :param radius: the radius of the sphere
        """
    trackBank: Any
    trackDeadzone: Any
    trackLimit: Any
    trackMode: Any
    trackOrientation: Any
    trackScreenOffset: Any
    trackSpeed: Any
    useBlurProtect: Any
    useCatEye: Any
    useChromatic: Any
    useChromaticSpeed: Any
    useDirectionalBlur: Any
    useDof: Any
    useShakeRoll: Any
    useSpeedBlur: Any
    useTrackUpLock: Any
    useViewport: bool
    """True when the camera is used as a viewport, set True to enable a viewport for this camera."""
    useVignette: Any
    viewport: list[Any]
    """The viewport rectangle used for the last render of this camera, in pixels (read-only). Ratios set in the editor are already resolved against the window."""
    vignetteRadius: Any
    vignetteStrength: Any
    world_to_camera: Matrix
    """This camera's world to camera transform. (read-only)."""

class KX_CameraActuator(SCA_ILogicBrick):
    axis: int
    """The camera axis (0, 1, 2) for positive XYZ, (3, 4, 5) for negative XYZ."""
    damping: float
    """strength of of the camera following movement."""
    height: float
    """height to stay above the target object."""
    max: float
    """maximum distance to stay from the target object."""
    min: float
    """minimum distance to the target object maintained by the actuator."""
    object: KX_GameObject
    """the object this actuator tracks."""

class KX_ChangeColorActuator(SCA_ILogicBrick):
    color: Any
    lerp: Any
    useLerp: Any

class KX_CharacterWrapper(EXP_PyObjectPlus):
    canStand: bool
    """True when there is room to stand up from the current posture."""
    fallSpeed: float
    """The character falling speed."""
    gravity: float
    """The gravity value used for the character."""
    def jump(self) -> Any:
        """The character jumps based on it's jump speed."""
    jumpCount: int
    """The current jump count. This can be used to have different logic for a single jump versus a double jump. For example, a different animation for the second jump."""
    jumpDirection: Vector
    """The direction the character is jumping."""
    jumpSpeed: float
    """The character jumping speed."""
    maxJumps: int
    """The maximum number of jumps a character can perform before having to touch the ground. By default this is set to 1. 2 allows for a double jump, etc."""
    maxSlope: float
    """The maximum slope which the character can climb."""
    onGround: bool
    """Whether or not the character is on the ground. (read-only)"""
    posture: str
    """Current posture (the collision shape in use). Setting it asks for a new posture; standing up waits until there is room above the character (see canStand)."""
    def reset(self) -> Any:
        ...
    running: bool
    """Run mode: while True the character walks with the object's Run Speed factor."""
    def setVelocity(self, velocity, time, local=False) -> Any:
        """Sets the character's linear velocity for a given period.

        :param local: False: you get the "global" velocity ie: relative to world orientation.

        :param time: Period while applying linear velocity.

        :param velocity: Linear velocity vector.
        """
    smoothMovement: float
    """Smooth movement caused by walking direction."""
    walkDirection: Vector
    """The speed and direction the character is traveling in using world coordinates. This should be used instead of applyMovement() to properly move the character."""

class KX_CollisionContactPoint(EXP_Value):
    appliedImpulse: float
    """The applied impulse to the owner object."""
    combinedFriction: float
    """The combined friction of the owner and collider object."""
    combinedRestitution: float
    """The combined restitution of the owner and collider object."""
    combinedRollingFriction: float
    """The combined rolling friction of the owner and collider object."""
    localPointA: Vector
    """The contact point in the owner object space."""
    localPointB: Vector
    """The contact point in the collider object space."""
    normal: Vector
    """The contact normal in owner object space."""
    worldPoint: Vector
    """The contact point in world space."""

class KX_CollisionSensor(SCA_ISensor):
    hitMaterial: str
    """The material of the object in the face hit by the ray. (read-only)."""
    hitObject: KX_GameObject
    """The last collided object. (read-only)."""
    hitObjectList: EXP_ListValue[KX_GameObject]
    """A list of colliding objects. (read-only)."""
    propName: str
    """The property or material to collide with."""
    useMaterial: bool
    """Determines if the sensor is looking for a property or material. KX_True = Find material; KX_False = Find property."""
    usePulseCollision: bool
    """When enabled, changes to the set of colliding objects generate a pulse."""

class KX_ConstraintActuator(SCA_ILogicBrick):
    damp: int
    """Time constant of the constraint expressed in frame (not use by Force field constraint)."""
    direction: Vector
    """The reference direction in world coordinate for the orientation constraint."""
    distance: float
    """the target distance of the distance constraint."""
    limit: int
    """type of constraint. Use one of the these constants"""
    max: float
    """the upper bound of the constraint. For rotation and orientation constraints, it represents radiant."""
    min: float
    """The lower bound of the constraint. For the rotation and orientation constraint, it represents radiant."""
    option: int
    """Binary combination of these constants"""
    propName: str
    """the name of the property or material for the ray detection of the distance constraint."""
    rayLength: float
    """the length of the ray of the distance constraint."""
    rotDamp: int
    """Time constant for the rotation expressed in frame (only for the distance constraint), 0 = use damp for rotation as well."""
    time: int
    """activation time of the actuator. The actuator disables itself after this many frame. If set to 0, the actuator is not limited in time."""

class KX_ConstraintWrapper(EXP_PyObjectPlus):
    breakingThreshold: float
    """The impulse threshold breaking the constraint, if the constraint is broken enabled is set to False."""
    constraint_id: int
    """Returns the contraint ID (read only)"""
    constraint_type: int
    """Returns the contraint type (read only)"""
    enabled: bool
    """The status of the constraint. Set to True to restore a constraint after breaking."""
    def getConstraintId(self, val) -> int:
        """Returns the contraint ID"""
    def getParam(self, axis) -> float:
        """Get the contraint position or euler angle of a generic 6DOF constraint"""
    def setParam(self, axis, value0, value1) -> Any:
        """Set the contraint limits"""

class KX_TextureRenderer(EXP_Value):
    autoUpdate: bool
    """Choose to update automatically each frame the texture renderer or not."""
    clipEnd: float
    """The projection view matrix far plane, used for culling."""
    clipStart: float
    """The projection view matrix near plane, used for culling."""
    enabled: bool
    """Enable the texture renderer to render the scene."""
    ignoreLayers: Any
    """The layers to ignore when rendering."""
    lodDistanceFactor: float
    """The factor to multiply distance to camera to adjust levels of detail. A float < 1.0f will make the distance to camera used to compute levels of detail decrease."""
    def update(self) -> Any:
        ...
    viewpointObject: KX_GameObject
    """The object where the texture renderer will render the scene."""

class KX_CubeMap(KX_TextureRenderer):
    ...

class KX_DynamicActuator(SCA_ILogicBrick):
    mass: Any
    mode: Any

class KX_EndObjectActuator(SCA_ILogicBrick):
    ...

class KX_FontObject(KX_GameObject):
    atlas: Any
    characterCount: Any
    dimensions: Vector
    """The size (width and height) of the current text in Blender Units."""
    font: Any
    lines: Any
    page: Any
    pageCount: Any
    resolution: float
    """The resolution of the font police."""
    shadowColor: Any
    shadowOffset: Any
    size: float
    """The size (scale factor) of the font object, scaled from font object origin (affects text resolution)."""
    text: str
    """The text displayed by this Font object."""
    textBox: Any
    translationKey: Any
    useLanguageFont: Any
    useShadows: Any
    visibleCharacters: Any

class KX_GameActuator(SCA_ILogicBrick):
    extensionName: Any
    fileName: str
    """the new .blend file to load."""
    mode: int
    """The mode of this actuator. Can be on of these constants"""
    saveLocation: Any

class KX_InputSystem(EXP_PyObjectPlus):
    def changeJoystickIndex(self) -> Any:
        ...
    def changeKeyMap(self) -> Any:
        ...
    def changeSensitivity(self) -> Any:
        ...
    inputMaps: Any
    def reloadInputMaps(self) -> Any:
        ...

class KX_InputTable(EXP_PyObjectPlus):
    activated: Any
    active: Any
    released: Any
    values: Any

class KX_LibLoadStatus(EXP_PyObjectPlus):
    finished: bool
    """The current status of the lib load."""
    libraryName: str
    """The name of the library being loaded (the first argument to LibLoad)."""
    onFinish: Any
    """A callback that gets called when the lib load is done."""
    progress: float
    """The current progress of the lib load as a normalized value from 0.0 to 1.0."""
    timeTaken: float
    """The amount of time, in seconds, the lib load took (0 until the operation is complete)."""

class KX_LightObject(KX_GameObject):
    HEMI: Any
    """A hemi light source. See attribute type"""
    NORMAL: Any
    """A point light source. See attribute type"""
    SPOT: Any
    """A spot light source. See attribute type"""
    SUN: Any
    """A point light source with no attenuation. See attribute type"""
    autoShadowUpdate: Any
    color: list[Any]
    """The color of this light. Black = [0.0, 0.0, 0.0], White = [1.0, 1.0, 1.0]."""
    distance: float
    """The maximum distance this light can illuminate. (SPOT and NORMAL lights only)."""
    energy: float
    """The brightness of this light."""
    lin_attenuation: float
    """The linear component of this light's attenuation. (SPOT and NORMAL lights only)."""
    quad_attenuation: float
    """The quadratic component of this light's attenuation (SPOT and NORMAL lights only)."""
    shadowBias: float
    """The shadow buffer sampling bias."""
    shadowBindId: int
    """The OpenGL shadow texture bind number/id."""
    shadowBleedBias: float
    """The bias for reducing light-bleed on variance shadow maps."""
    shadowClipEnd: float
    """The shadowmap clip end, beyond which objects will not generate shadows."""
    shadowClipStart: float
    """The shadowmap clip start, below which objects will not generate shadows."""
    shadowColor: Color
    """The color of this light shadows. Black = (0.0, 0.0, 0.0), White = (1.0, 1.0, 1.0)."""
    shadowFrustumSize: float
    """Size of the frustum used for creating the shadowmap."""
    shadowMapSize: int
    """Shadow map resolution in pixels (the lamp's Size). Setting it resizes the shadow buffer on the fly without recompiling shaders, for a shadow quality option (e.g. 512 / 1024 / 2048). Cascaded shadow maps keep their ratio to it. Reads 0 when the lamp has no shadow buffer. Point lamps keep their own size."""
    shadowMapType: int
    """The shadow shadow map type (0 -> Simple; 1 -> Variance)"""
    shadowMatrix: Any
    """Matrix that converts a vector in camera space to shadow buffer depth space."""
    spotblend: float
    """Specifies the intensity distribution of the spot light (SPOT lights only)."""
    spotsize: float
    """The cone angle of the spot light, in degrees (SPOT lights only)."""
    staticShadow: bool
    """Enables static shadows. By default (staticShadow=False) the shadow cast by the lamp is recalculated every frame. When this is not needed, set staticShadow=True. In that case, call :pyupdateShadow to request a shadow update."""
    type: Any
    """The type of light - must be SPOT, SUN or NORMAL"""
    def updateShadow(self) -> Any:
        ...
    useShadow: bool
    """Returns True if the light has Shadow option activated, else returns False."""

class KX_LightningActuator(SCA_ILogicBrick):
    bolt: Any

class KX_LodLevel(EXP_Value):
    distance: float
    """Distance to begin using this level of detail. (read only)"""
    hysteresis: float
    """Minimum distance factor change required to transition to the previous level of detail in percent. (read only)"""
    level: int
    """The number of the lod level. (read only)"""
    mesh: Any
    """The mesh used for this lod level. (read only)"""
    useHysteresis: bool
    """Return true if the lod level uses hysteresis override. (read only)"""
    useMaterial: bool
    """Return True if the lod level uses a different material than the original object mesh material. (read only)"""
    useMesh: bool
    """Return True if the lod level uses a different mesh than the original object mesh. (read only)"""

class KX_LodManager(EXP_Value):
    distanceFactor: float
    """Method to multiply the distance to the camera."""
    levels: list[KX_LodLevel]
    """Return the list of all levels of detail of the lod manager."""
    updatePhysics: Any

class KX_Mesh(EXP_Value):
    def constructBvh(self, transform=..., epsilon=0) -> BVHTree:
        """Return a BVH tree based on mesh geometry. Indices of tree elements match polygons indices.

        :param epsilon: The tree distance epsilon.

        :param transform: The transform 4x4 matrix applied to vertices.
        """
    def copy(self) -> KX_Mesh:
        """Return a duplicated mesh."""
    def destruct(self) -> Any:
        ...
    def getMaterialName(self, matid) -> str:
        """Gets the name of the specified material.

        :param matid: the specified material.
        """
    def getPolygon(self, index) -> KX_PolyProxy:
        """Gets the specified polygon from the mesh.

        :param index: polygon number
        """
    def getTextureName(self, matid) -> str:
        """Gets the name of the specified material's texture.

        :param matid: the specified material
        """
    def getVertex(self, matid, index) -> KX_VertexProxy:
        """Gets the specified vertex from the mesh object.

        :param index: the index into the vertex array.

        :param matid: the specified material
        """
    def getVertexArrayLength(self, matid) -> int:
        """Gets the length of the vertex array associated with the specified material.

        :param matid: the specified material
        """
    materials: list[KX_BlenderMaterial]
    numMaterials: int
    numPolygons: int
    polygons: KX_PolyProxy
    """Returns the list of polygons of this mesh."""
    def replaceMaterial(self, matid, material) -> Any:
        """Replace the material in slot matid by the material material.

        :param material: The material replacement.

        :param matid: The material index.
        """
    def transform(self, matid, matrix) -> Any:
        """Transforms the vertices of a mesh.

        :param matid: material index, -1 transforms all.

        :param matrix: transformation matrix.
        """
    def transformUV(self, matid, matrix, uv_index=-1, uv_index_from=-1) -> Any:
        """Transforms the vertices UV's of a mesh.

        :param matid: material index, -1 transforms all.

        :param matrix: transformation matrix.

        :param uv_index: optional uv index, -1 for all, otherwise 0 or 1.

        :param uv_index_from: optional uv index to copy from, -1 to transform the current uv.
        """

class KX_MeshBuilder(EXP_PyObjectPlus):
    def FromMesh(self) -> Any:
        """staticmethod(function) -> method"""
    def addSlot(self) -> Any:
        ...
    def finish(self) -> Any:
        ...
    slots: Any

class KX_MeshBuilderSlot(EXP_Value):
    def addIndex(self) -> Any:
        ...
    def addPrimitiveIndex(self) -> Any:
        ...
    def addTriangleIndex(self) -> Any:
        ...
    def addVertex(self) -> Any:
        ...
    colorCount: Any
    indices: Any
    material: Any
    primitive: Any
    def recalculateNormals(self) -> Any:
        ...
    def removePrimitiveIndex(self) -> Any:
        ...
    def removeTriangleIndex(self) -> Any:
        ...
    def removeVertex(self) -> Any:
        ...
    triangleIndices: Any
    uvCount: Any
    vertices: Any

class KX_MicrophoneSensor(SCA_ISensor):
    hold: Any
    level: Any
    mode: Any
    peak: Any
    propName: Any
    threshold: Any

class KX_MouseActuator(SCA_ILogicBrick):
    angle: Vector
    """The current rotational offset caused by the mouse actuator in degrees."""
    limit_x: Vector
    """The minimum and maximum angle of rotation caused by mouse movement along the x axis in degrees. limit_x[0] is minimum, limit_x[1] is maximum."""
    limit_y: Vector
    """The minimum and maximum angle of rotation caused by mouse movement along the y axis in degrees. limit_y[0] is minimum, limit_y[1] is maximum."""
    local_x: bool
    """Rotation caused by mouse movement along the x axis is local."""
    local_y: bool
    """Rotation caused by mouse movement along the y axis is local."""
    object_axis: list[Any]
    """The object's 3D axis to rotate with the mouse movement. ([x, y])"""
    def reset(self) -> Any:
        """Undoes the rotation caused by the mouse actuator."""
    reset_x: bool
    """Mouse is locked to the center of the screen on the x axis."""
    reset_y: bool
    """Mouse is locked to the center of the screen on the y axis."""
    sensitivity: Vector
    """The amount of rotation caused by mouse movement along the x and y axis."""
    threshold: Vector
    """Amount of movement from the mouse required before rotation is triggered."""
    use_axis_x: bool
    """Mouse movement along the x axis effects object rotation."""
    use_axis_y: bool
    """Mouse movement along the y axis effects object rotation."""
    visible: bool
    """The visibility of the mouse cursor."""

class SCA_MouseSensor(SCA_ISensor):
    def getButtonStatus(self, button) -> int:
        """Get the mouse button status.

        :param button: The code that represents the key you want to get the state of, use one of these constants
        """
    holdTime: Any
    mode: int
    """sensor mode."""
    position: Any
    """current [x, y] coordinates of the mouse, in frame coordinates (pixels)."""

class KX_MouseFocusSensor(SCA_MouseSensor):
    hitNormal: list[Any]
    """the worldspace normal from the face at point of intersection."""
    hitObject: KX_GameObject
    """the last object the mouse was over."""
    hitPosition: list[Any]
    """The worldspace position of the ray intersecton."""
    hitUV: list[Any]
    """the UV coordinates at the point of intersection."""
    mask: Any
    """The collision mask (16 layers mapped to a 16-bit integer) combined with each object's collision group, to hit only a subset of the objects in the scene. Only those objects for which collisionGroup & mask is true can be hit."""
    propName: str
    """The property or material the sensor is looking for."""
    rayDirection: list[Any]
    """The rayTarget - raySource normalized."""
    raySource: list[Any]
    """The worldspace source of the ray (the view position)."""
    rayTarget: list[Any]
    """The worldspace target of the ray."""
    useMaterial: bool
    """Determines if the sensor is looking for a property or material. KX_True = Find material; KX_False = Find property."""
    usePulseFocus: bool
    """When enabled, moving the mouse over a different object generates a pulse. (only used when the 'Mouse Over Any' sensor option is set)."""
    useXRay: bool
    """If enabled it allows the sensor to see through game objects that don't have the selected property or material."""

class KX_MovementSensor(SCA_ISensor):
    axis: Any
    threshold: Any

class KX_NavMeshObject(KX_GameObject):
    def addObstacle(self, object, radius=0.0) -> Any:
        """Makes the object carve every dynamic navigation mesh of its scene, following it when it moves. Calling it again changes the radius. It has no effect on static navigation meshes.

        :param object: the obstacle, in the same scene as the navigation mesh

        :param radius: the world radius of the obstacle cylinder, 0.0 uses the object "Create Obstacle" radius
        """
    def draw(self, mode) -> Any:
        """Draws a debug mesh for the navigation mesh. On a dynamic navigation mesh, the obstacle cylinders are drawn in yellow.

        :param mode: integer
        """
    dynamic: bool
    """True when the navigation mesh was built in tiles and obstacles can carve it (read-only)."""
    def findPath(self, start, goal) -> list[Any]:
        """Finds the path from start to goal points.

        :param goal: the goal point

        :param start: 3D Vector
        """
    def raycast(self, start, goal) -> float:
        """Raycast from start to goal points.

        :param goal: the goal point

        :param start: 3D Vector
        """
    def rebuild(self) -> Any:
        """Rebuild the navigation mesh."""
    def removeObstacle(self, object) -> Any:
        """Stops the object carving the dynamic navigation meshes, including objects with "Create Obstacle".

        :param object: the obstacle
        """
    version: int
    """Incremented when the navigation mesh is rebuilt or finishes changing because of obstacles (read-only). Paths found with an older version may cross new obstacles."""

class KX_NearSensor(KX_CollisionSensor):
    distance: float
    """The near sensor activates when an object is within this distance."""
    resetDistance: float
    """The near sensor deactivates when the object exceeds this distance."""

class KX_NetworkMessageActuator(SCA_ILogicBrick):
    body: str
    """The body of the message."""
    propName: str
    """Messages will only be sent to objects with the given property name."""
    subject: str
    """The subject field of the message."""
    usePropBody: bool
    """Send a property instead of a regular body message."""

class KX_NetworkMessageSensor(SCA_ISensor):
    bodies: list[Any]
    """The list of message bodies received. (read-only)."""
    frameMessageCount: int
    """The number of messages received since the last frame. (read-only)."""
    subject: str
    """The subject the sensor is looking for."""
    subjects: list[Any]
    """The list of message subjects received. (read-only)."""

class KX_ObjectActuator(SCA_ILogicBrick):
    angV: Vector
    """The angular velocity applied by the actuator."""
    dLoc: Vector
    """The displacement vector applied by the actuator."""
    dRot: Vector
    """The angular displacement vector applied by the actuator"""
    damping: Any
    """The damping parameter of the servo controller."""
    force: Vector
    """The force applied by the actuator."""
    forceLimitX: list[Any]
    """The min/max force limit along the X axis and activates or deactivates the limits in the servo controller."""
    forceLimitY: list[Any]
    """The min/max force limit along the Y axis and activates or deactivates the limits in the servo controller."""
    forceLimitZ: list[Any]
    """The min/max force limit along the Z axis and activates or deactivates the limits in the servo controller."""
    linV: Vector
    """The linear velocity applied by the actuator."""
    pid: list[Any]
    """The PID coefficients of the servo controller."""
    reference: KX_GameObject
    """The object that is used as reference to compute the velocity for the servo controller."""
    torque: Vector
    """The torque applied by the actuator."""
    useLocalAngV: bool
    """A flag specifying if the angular velocity is local."""
    useLocalDLoc: bool
    """A flag specifying if the dLoc is local."""
    useLocalDRot: bool
    """A flag specifying if the dRot is local."""
    useLocalForce: bool
    """A flag specifying if the force is local."""
    useLocalLinV: bool
    """A flag specifying if the linear velocity is local."""
    useLocalTorque: bool
    """A flag specifying if the torque is local."""

class KX_ParentActuator(SCA_ILogicBrick):
    compound: bool
    """Whether the object shape should be added to the parent compound shape when parenting."""
    ghost: bool
    """Whether the object should be made ghost when parenting Effective only if the shape is not added to the parent compound shape."""
    mode: int
    """The mode of this actuator."""
    object: KX_GameObject
    """the object this actuator sets the parent too."""

class KX_ParticleSystem(EXP_PyObjectPlus):
    billboardMode: Any
    blendMode: Any
    def burst(self) -> Any:
        ...
    burstInterval: Any
    burstMode: Any
    collisionBounce: Any
    collisionFriction: Any
    collisionHeight: Any
    collisionMode: Any
    color: Any
    debugUI: Any
    drag: Any
    emissionAngle: Any
    emissionDirection: Any
    emissionMode: Any
    emitterPosition: Any
    emitterRadius: Any
    enabled: Any
    endColor: Any
    endSize: Any
    flipbook: Any
    fragmentShaderPath: Any
    gravity: Any
    lifetime: Any
    particleCount: Any
    size: Any
    texture: Any
    useBackfaceCulling: Any
    useDebugUi: Any
    useObjectRotation: Any
    useVortex: Any
    velocity: Any
    velocityRandomness: Any
    vortexHeight: Any
    vortexRadiusTop: Any
    vortexRotationSpeed: Any

class KX_PlanarMap(KX_TextureRenderer):
    normal: Vector
    """Plane normal used to compute the reflection or refraction orientation of the render camera."""

class KX_PolyProxy(EXP_Value):
    collide: int
    """collide state of the polygon: 1=receives collision, 0=collision free."""
    def getMaterial(self) -> KX_BlenderMaterial:
        ...
    def getMaterialIndex(self) -> int:
        """Returns the material bucket index of the polygon. This index and the ones returned by getVertexIndex() are needed to retrieve the vertex proxy from MeshProxy."""
    def getMaterialName(self) -> str:
        """Returns the polygon material name with MA prefix"""
    def getMesh(self) -> Any:
        """Returns a mesh proxy"""
    def getNumVertex(self) -> int:
        """Returns the number of vertex of the polygon."""
    def getTextureName(self) -> str:
        """getTexturelName() : returns the polygon texture name, "" if no texture"""
    def getVertexIndex(self, vertex) -> int:
        """Returns the mesh vertex index of a polygon vertex This index and the one returned by getMaterialIndex() are needed to retrieve the vertex proxy from MeshProxy.

        :param vertex: integer
        """
    def isCollider(self) -> int:
        """Returns whether the polygon is receives collision or not"""
    def isVisible(self) -> bool:
        """Returns whether the polygon is visible or not"""
    material: KX_BlenderMaterial
    """The material of the polygon."""
    material_id: int
    """The material index of the polygon, use this to retrieve vertex proxy from mesh proxy."""
    material_name: str
    """The name of polygon material, empty if no material."""
    texture_name: str
    """The texture name of the polygon."""
    v1: int
    """vertex index of the first vertex of the polygon, use this to retrieve vertex proxy from mesh proxy."""
    v2: int
    """vertex index of the second vertex of the polygon, use this to retrieve vertex proxy from mesh proxy."""
    v3: int
    """vertex index of the third vertex of the polygon, use this to retrieve vertex proxy from mesh proxy."""
    v4: int
    vertices: KX_VertexProxy
    """Returns the list of vertices of this polygon."""
    visible: int
    """visible state of the polygon: 1=visible, 0=invisible."""

class KX_PythonComponent(EXP_PyObjectPlus):
    object: KX_GameObject
    """The object owner of the component."""

class KX_PythonJoystick(EXP_PyObjectPlus):
    activeButtons: Any
    axisValues: Any
    duration: Any
    hasVibration: Any
    hatValues: Any
    inputs: Any
    isVibrating: Any
    name: Any
    numAxis: Any
    numButtons: Any
    numHats: Any
    def startVibration(self) -> Any:
        ...
    def stopVibration(self) -> Any:
        """StopVibration() Stops the joystick vibration."""
    strengthLeft: Any
    strengthRight: Any

class KX_PythonKeyboard(EXP_PyObjectPlus):
    active_events: Any
    events: Any
    def getClipboard(self) -> Any:
        """getCliboard doc"""
    def setClipboard(self) -> Any:
        """setCliboard doc"""
    text: Any
    inputs: dict[int, SCA_InputEvent]
    activeInputs: dict[int, SCA_InputEvent]

class KX_PythonMotion(EXP_PyObjectPlus):
    accelerometer: Vector
    """Acceleration including gravity, in m/s². With the device lying still, face up, it is close to (0, 0, 9.8). (read-only)."""
    available: bool
    """True while the sensors are sending data. It becomes False when no reading arrived in the last second (no sensor, desktop browser, page in background). (read-only)."""
    def calibrate(self) -> bool:
        """Take the current position as neutral for tilt, so the player can hold the device the way they like."""
    gravity: Vector
    """Gravity alone, in m/s², pointing up as in accelerometer. When the device does not report acceleration without gravity, it is estimated from accelerometer with a low-pass filter. (read-only)."""
    gyroscope: Vector
    """Rotation speed around each screen axis, in radians per second. (read-only)."""
    headOrientation: Any
    orientation: Vector
    """Device orientation angles (alpha, beta, gamma) in degrees, exactly as given by the browser. They follow the device axes, not the screen axes. (read-only)."""
    def recenter(self) -> Any:
        ...
    recenterTime: Any
    smoothing: Any
    tilt: tuple
    """How far the device is tilted from its neutral position, from -1.0 to 1.0 on each axis: the screen direction a ball would roll to. x is positive when the right edge of the screen goes down, y when the top edge goes down. The neutral position is the device lying flat until calibrate is called. (read-only)."""

class KX_PythonMouse(EXP_PyObjectPlus):
    active_events: Any
    deltaPosition: Any
    events: Any
    position: Any
    def reCenter(self) -> Any:
        ...
    visible: Any
    inputs: dict[int, SCA_InputEvent]
    activeInputs: dict[int, SCA_InputEvent]

class KX_RadarSensor(KX_NearSensor):
    angle: float
    """The angle of the cone (in degrees) with which to test."""
    axis: int
    """The axis on which the radar cone is cast."""
    coneOrigin: Vector
    """The origin of the cone with which to test. The origin is in the middle of the cone. (read-only)."""
    coneTarget: Vector
    """The center of the bottom face of the cone with which to test. (read-only)."""
    distance: float
    """The height of the cone with which to test."""

class KX_RaySensor(SCA_ISensor):
    axis: int
    """The axis the ray is pointing on."""
    gazeAngle: Any
    gazeProgress: Any
    gazeTime: Any
    hitMaterial: str
    """The material of the object in the face hit by the ray. (read-only)."""
    hitNormal: Vector
    """The normal (in worldcoordinates) of the object at the location where the object was hit by the ray. (read-only)."""
    hitObject: KX_GameObject
    """The game object that was hit by the ray. (read-only)."""
    hitPosition: Vector
    """The position (in worldcoordinates) where the object was hit by the ray. (read-only)."""
    mask: Any
    """The collision mask (16 layers mapped to a 16-bit integer) combined with each object's collision group, to hit only a subset of the objects in the scene. Only those objects for which collisionGroup & mask is true can be hit."""
    propName: str
    """The property the ray is looking for."""
    range: float
    """The distance of the ray."""
    rayDirection: Vector
    """The direction from the ray (in worldcoordinates). (read-only)."""
    useMaterial: bool
    """Whether or not to look for a material (false = property)."""
    useXRay: bool
    """Whether or not to use XRay."""

class KX_ReplaceMeshActuator(SCA_ILogicBrick):
    def instantReplaceMesh(self) -> Any:
        ...
    mesh: Any
    useDisplayMesh: Any
    usePhysicsMesh: Any

class KX_Scene(EXP_Value):
    active_camera: KX_Camera
    """The current active camera."""
    activityCulling: bool
    """True if the scene allow object activity culling."""
    def addObject(self, object, reference, time=0.0) -> KX_GameObject:
        """Adds an object to the scene like the Add Object Actuator would.

        :param object: The (name of the) object to add.

        :param reference: The (name of the) object which position, orientation, and scale to copy (optional), if the object to add is a light and there is not reference the light's la...

        :param time: The lifetime of the added object, in frames (assumes one frame is 1/50 second). A time of 0.0 means the object will last forever (optional).
        """
    cameras: EXP_ListValue[KX_Camera]
    """A list of cameras in the scene, (read-only)."""
    def convertObject(self) -> Any:
        ...
    dbvt_culling: bool
    """True when Dynamic Bounding box Volume Tree is set (read-only)."""
    def drawObstacleSimulation(self) -> Any:
        ...
    def end(self) -> Any:
        """Removes the scene from the game."""
    def explode(self, position, radius=5.0, force=20.0, upBias=0.3, occlusion=True, mask=0xFFFF, ignore=None) -> list[KX_GameObject]:
        """Radial impulse on the dynamic objects around position, falling to zero at radius (force * (1 - distance / radius)). Destructible objects hit above their KX_GameObject.breakImpulse break and their pieces are pushed, sharing the impulse by mass.

        :param force: The impulse at the center.

        :param ignore: An object or a list of objects left out.

        :param mask: The collision groups reached.

        :param occlusion: If True, static geometry between the center and an object shields it.

        :param position: The center of the blast.

        :param radius: The distance the blast reaches.

        :param upBias: How much the push is tilted upwards, 0.0 is straight away from the center.
        """
    filterManager: KX_2DFilterManager
    """The scene's 2D filter manager, (read-only)."""
    def get(self, key, default=None) -> Any:
        """Return the value matching key, or the default value if its not found."""
    def getQualityPreset(self) -> Any:
        ...
    gravity: Vector
    """The scene gravity using the world x, y and z axis."""
    lights: EXP_ListValue[KX_LightObject]
    """A list of lights in the scene, (read-only)."""
    maxDebris: int
    """The number of fragments of broken objects kept alive in the scene; past it the oldest are removed. Starts with Scene > Game Physics > Max Debris. 0 means no limit. Lowering it removes the extra pieces at once."""
    name: str
    """The scene's name, (read-only)."""
    objects: EXP_ListValue[KX_GameObject]
    """A list of objects in the scene, (read-only)."""
    objectsInactive: EXP_ListValue[KX_GameObject]
    """A list of objects on background layers (used for the addObject actuator), (read-only)."""
    onRemove: list[Any]
    """A list of callables to run when the scene is destroyed."""
    overrideCullingCamera: KX_Camera
    """The override camera used for scene culling, if set to None the culling is proceeded with the camera used to render."""
    def play_cutscene(self) -> Any:
        ...
    def play_take(self) -> Any:
        ...
    post_draw: list[Any]
    """A list of callables to be run after the render step."""
    pre_draw: list[Any]
    """A list of callables to be run before the render step. The callbacks can take as argument the rendered camera."""
    pre_draw_setup: list[Any]
    """A list of callables to be run before the drawing setup (i.e., before the model view and projection matrices are computed). The callbacks can take as argument the rendered camera, the camera could be temporary in case of stereo rendering."""
    def release_cutscene_trigger(self) -> Any:
        ...
    def replace(self, scene) -> bool:
        """Replaces this scene with another one.

        :param scene: The name of the scene to replace this scene with.
        """
    def restart(self) -> Any:
        """Restarts the scene."""
    def restart_cutscene(self) -> Any:
        ...
    def resume(self) -> Any:
        """Resume this scene."""
    def setQualityPreset(self) -> Any:
        ...
    def skip_cutscene(self) -> Any:
        ...
    speakers: Any
    def stop_cutscene(self) -> Any:
        ...
    def suspend(self) -> Any:
        """Suspends this scene."""
    suspended: bool
    """True if the scene is suspended, (read-only)."""
    takes: Any
    texts: EXP_ListValue[KX_FontObject]
    """A list of texts in the scene, (read-only)."""
    thread_logic_1: Any
    unconvertedObjects: Any
    visible: Any
    world: KX_WorldInfo
    """The current active world, (read-only)."""
    worldSun: Any

class KX_SceneActuator(SCA_ILogicBrick):
    camera: KX_Camera
    """the camera to change to."""
    mode: int
    """The mode of the actuator."""
    scene: str
    """the name of the scene to change to/overlay/underlay/remove/suspend/resume."""
    useRestart: bool
    """Set flag to True to restart the sene."""

class KX_SoundActuator(SCA_ILogicBrick):
    attenuation: float
    """The influence factor on volume depending on distance."""
    cone_angle_inner: float
    """The angle of the inner cone."""
    cone_angle_outer: float
    """The angle of the outer cone."""
    cone_volume_outer: float
    """The gain outside the outer cone (the gain in the outer cone will be interpolated between this value and the normal gain in the inner cone)."""
    distance_maximum: float
    """The maximum distance at which you can hear the sound."""
    distance_reference: float
    """The distance where the sound has a gain of 1.0."""
    is3D: bool
    """Whether or not the actuator should be using 3D sound. (read-only)"""
    mode: int
    """The operation mode of the actuator. Can be one of these constants"""
    def pauseSound(self) -> Any:
        """Pauses the sound."""
    pitch: float
    """The pitch of the sound."""
    sound: Any
    """The sound the actuator should play."""
    def startSound(self) -> Any:
        """Starts the sound."""
    def stopSound(self) -> Any:
        """Stops the sound."""
    time: float
    """The current position in the audio stream (in seconds)."""
    volume: float
    """The volume (gain) of the sound."""
    volume_maximum: float
    """The maximum gain of the sound, no matter how near it is."""
    volume_minimum: float
    """The minimum gain of the sound, no matter how far it is away."""

class KX_Speaker(KX_GameObject):
    def GetActiveEffect(self) -> Any:
        ...
    def GetActiveEffectFilter(self) -> Any:
        ...
    def Pause(self) -> Any:
        ...
    def Play(self) -> Any:
        ...
    def RemoveEffect(self) -> Any:
        ...
    def Restart(self) -> Any:
        ...
    def SetEffect(self) -> Any:
        ...
    def SetSound(self) -> Any:
        ...
    def Stop(self) -> Any:
        ...
    attenuation: Any
    catkey: Any
    cone_angle_inner: Any
    cone_angle_outer: Any
    cone_volume_outer: Any
    distance_maximum: Any
    distance_reference: Any
    filter_gain: Any
    filter_gainhf: Any
    filter_gainlf: Any
    is3D: Any
    mode: Any
    pitch: Any
    playbackManager: Any
    reverb_air_absorption_gain_hf: Any
    reverb_decay_hf_ratio: Any
    reverb_decay_limit_hf: Any
    reverb_decay_time: Any
    reverb_density: Any
    reverb_diffusion: Any
    reverb_gain: Any
    reverb_gain_hf: Any
    reverb_late_reverb_delay: Any
    reverb_late_reverb_gain: Any
    reverb_reflections_delay: Any
    reverb_reflections_gain: Any
    reverb_room_rolloff_factor: Any
    sound: Any
    time: Any
    volume: Any
    volume_maximum: Any
    volume_minimum: Any

class KX_StateActuator(SCA_ILogicBrick):
    mask: int
    """Value that defines the bits that will be modified by the operation."""
    operation: int
    """Type of bit operation to be applied on object state mask."""

class KX_SteeringActuator(SCA_ILogicBrick):
    acceleration: float
    """Max acceleration"""
    behavior: Any
    """The steering behavior to use."""
    distance: float
    """Relax distance"""
    enableVisualization: bool
    """Enable debug visualization"""
    facingMode: Any
    lockZVelocity: Any
    navmesh: KX_GameObject
    """Navigation mesh"""
    path: list[Vector]
    """Path point list."""
    pathUpdatePeriod: int
    """Path update period"""
    selfterminated: bool
    """Terminate when target is reached"""
    steeringVec: Any
    target: KX_GameObject
    """Target object"""
    turnspeed: float
    """Max turn speed"""
    velocity: float
    """Velocity magnitude"""

class KX_TrackToActuator(SCA_ILogicBrick):
    object: KX_GameObject
    """the object this actuator tracks."""
    time: int
    """the time in frames with which to delay the tracking motion."""
    trackAxis: int
    """The axis that points to the target object."""
    upAxis: int
    """The axis that points upward."""
    use3D: bool
    """the tracking motion to use 3D."""

class KX_VRHeadSensor(SCA_ISensor):
    angle: Any
    mode: Any
    pitch: Any
    roll: Any
    time: Any
    yaw: Any

class KX_VehicleWrapper(EXP_PyObjectPlus):
    def addWheel(self, wheel, attachPos, downDir, axleDir, suspensionRestLength, wheelRadius, hasSteering) -> Any:
        """Add a wheel to the vehicle

        :param attachPos: The position to attach the wheel, relative to the chassis object center.

        :param axleDir: The axis the wheel rotates around, relative to the chassis.

        :param downDir: The direction vector pointing down to where the vehicle should collide with the floor.

        :param hasSteering: True if the wheel should turn with steering, typically used in front wheels.

        :param suspensionRestLength: The length of the suspension when no forces are being applied.

        :param wheel: The object to use as a wheel.

        :param wheelRadius: The radius of the wheel (half the diameter).
        """
    def applyBraking(self, force, wheelIndex) -> Any:
        """Apply a braking force to the specified wheel

        :param force: the brake force

        :param wheelIndex: index of the wheel where the force needs to be applied
        """
    def applyEngineForce(self, force, wheelIndex) -> Any:
        """Apply an engine force to the specified wheel

        :param force: the engine force

        :param wheelIndex: index of the wheel where the force needs to be applied
        """
    constraint_id: Any
    constraint_type: Any
    def getConstraintId(self) -> int:
        """Get the constraint ID"""
    def getConstraintType(self) -> int:
        """Returns the constraint type."""
    def getCoordinateSystem(self) -> Any:
        ...
    def getCurrentSpeedKmh(self) -> Any:
        ...
    def getCurrentSpeedMps(self) -> Any:
        ...
    def getForwardVector(self) -> Any:
        ...
    def getNumWheels(self) -> int:
        """Returns the number of wheels."""
    def getWheelConfig(self) -> Any:
        ...
    def getWheelOrientationQuaternion(self, wheelIndex) -> Any:
        """Returns the wheel orientation as a quaternion.

        :param wheelIndex: the wheel index
        """
    def getWheelPosition(self, wheelIndex) -> list[Any]:
        """Returns the position of the specified wheel

        :param wheelIndex: the wheel index
        """
    def getWheelRotation(self, wheelIndex) -> float:
        """Returns the rotation of the specified wheel

        :param wheelIndex: the wheel index
        """
    def getWheelState(self) -> Any:
        ...
    def loadPreset(self) -> Any:
        ...
    rayMask: Any
    """Set ray cast mask."""
    def rebuildPreset(self) -> Any:
        ...
    def resetSuspension(self) -> Any:
        ...
    def savePreset(self) -> Any:
        ...
    def setCoordinateSystem(self) -> Any:
        ...
    def setRollInfluence(self, rollInfluece, wheelIndex) -> Any:
        """Set the specified wheel's roll influence. The higher the roll influence the more the vehicle will tend to roll over in corners.

        :param rollInfluece: the wheel roll influence

        :param wheelIndex: the wheel index
        """
    def setSteeringValue(self, steering, wheelIndex) -> Any:
        """Set the specified wheel's steering

        :param steering: the wheel steering

        :param wheelIndex: the wheel index
        """
    def setSuspensionCompression(self, compression, wheelIndex) -> Any:
        """Set the specified wheel's compression

        :param compression: the wheel compression

        :param wheelIndex: the wheel index
        """
    def setSuspensionDamping(self, damping, wheelIndex) -> Any:
        """Set the specified wheel's damping

        :param damping: the wheel damping

        :param wheelIndex: the wheel index
        """
    def setSuspensionRestLength(self) -> Any:
        ...
    def setSuspensionStiffness(self, stiffness, wheelIndex) -> Any:
        """Set the specified wheel's stiffness

        :param stiffness: the wheel stiffness

        :param wheelIndex: the wheel index
        """
    def setTyreFriction(self, friction, wheelIndex) -> Any:
        """Set the specified wheel's tyre friction

        :param friction: the tyre friction

        :param wheelIndex: the wheel index
        """
    def setWheelIsDriveWheel(self) -> Any:
        ...
    def setWheelRadius(self) -> Any:
        ...

class KX_VertexProxy(EXP_Value):
    UV: Vector
    """The texture coordinates of the vertex."""
    XYZ: Vector
    """The position of the vertex."""
    a: float
    """The alpha component of the vertex color. 0.0 <= a <= 1.0."""
    b: float
    """The blue component of the vertex color. 0.0 <= b <= 1.0."""
    color: Vector
    """The color of the vertex."""
    colors: list[Any]
    """The color list of the vertex."""
    g: float
    """The green component of the vertex color. 0.0 <= g <= 1.0."""
    def getNormal(self) -> Vector:
        """Gets the normal vector of this vertex."""
    def getRGBA(self) -> int:
        """Gets the color of this vertex."""
    def getUV(self) -> Vector:
        """Gets the UV (texture) coordinates of this vertex."""
    def getUV2(self) -> Vector:
        """Gets the 2nd UV (texture) coordinates of this vertex."""
    def getXYZ(self) -> Vector:
        """Gets the position of this vertex."""
    normal: Vector
    """The normal of the vertex."""
    r: float
    """The red component of the vertex color. 0.0 <= r <= 1.0."""
    def setNormal(self, normal) -> Any:
        """Sets the normal vector of this vertex.

        :param normal: the new normal of this vertex.
        """
    def setRGBA(self, col) -> Any:
        """Sets the color of this vertex.

        :param col: the new color of this vertex in packed RGBA format.
        """
    def setUV(self, uv) -> Vector:
        """Sets the UV (texture) coordinates of this vertex."""
    def setUV2(self, uv, unit) -> Vector:
        """Sets the 2nd UV (texture) coordinates of this vertex.

        :param unit: integer
        """
    def setXYZ(self, pos) -> Vector:
        """Sets the position of this vertex.

        :param pos: the new position for this vertex in local coordinates.
        """
    tangent: Vector
    """The tangent of the vertex (read-only), computed from the UV map used by the material's Normal Map or Tangent node (the active UV map by default). The w component holds the bitangent sign."""
    u: float
    """The u texture coordinate of the vertex."""
    u2: float
    """The second u texture coordinate of the vertex."""
    uvs: list[Any]
    """The texture coordinates list of the vertex."""
    v: float
    """The v texture coordinate of the vertex."""
    v2: float
    """The second v texture coordinate of the vertex."""
    x: float
    """The x coordinate of the vertex."""
    y: float
    """The y coordinate of the vertex."""
    z: float
    """The z coordinate of the vertex."""

class KX_VideoActuator(SCA_ILogicBrick):
    mode: Any
    object: Any
    seconds: Any
    useRelative: Any

class KX_VisibilityActuator(SCA_ILogicBrick):
    useOcclusion: bool
    """whether the actuator makes its parent object an occluder or not."""
    useRecursion: bool
    """whether the visibility/occlusion should be propagated to all children of the object."""
    visibility: bool
    """whether the actuator makes its parent object visible or invisible."""

class KX_VoiceActuator(SCA_ILogicBrick):
    amount: Any
    effect: Any
    maxSeconds: Any
    mode: Any
    slot: Any
    useReverb: Any
    volume: Any

class KX_WorldInfo(EXP_PyObjectPlus):
    KX_MIST_INV_QUADRATIC: Any
    """Type of inverse quadratic attenuation used to fade mist."""
    KX_MIST_LINEAR: Any
    """Type of linear attenuation used to fade mist."""
    KX_MIST_QUADRATIC: Any
    """Type of quadratic attenuation used to fade mist."""
    ambientColor: Color
    """The color of the ambient light. Black = [0.0, 0.0, 0.0], White = [1.0, 1.0, 1.0]."""
    atmosphereAltitude: Any
    atmosphereIntensity: Any
    atmosphereMieDensity: Any
    atmosphereMieDirection: Any
    atmosphereRayleighColor: Any
    atmosphereRayleighDensity: Any
    auroraColors: Any
    backgroundColor: Any
    envLightColor: int
    """White: returns 0 SkyColor: returns 1 SkyTexture: returns 2"""
    envLightEnabled: bool
    """Returns True if Environment Lighting is enabled. Else returns False"""
    envLightEnergy: float
    """The environment light energy."""
    exposure: float
    """Amount of exponential color correction for light."""
    def getWeather(self) -> Any:
        ...
    horizonColor: Vector
    """The horizon color. Black = [0.0, 0.0, 0.0, 1.0], White = [1.0, 1.0, 1.0, 1.0]. Mist and horizon color should always be set to the same color."""
    mistColor: Color
    """The color of the mist. Black = [0.0, 0.0, 0.0], White = [1.0, 1.0, 1.0]. Mist and background color sould always set to the same color."""
    mistDistance: float
    """The mist distance fom the start point to reach 100% mist."""
    mistEnable: bool
    """Return the state of the mist."""
    mistIntensity: float
    """The mist intensity."""
    mistStart: float
    """The mist start point."""
    mistType: Any
    """The type of mist - must be KX_MIST_QUADRATIC, KX_MIST_LINEAR or KX_MIST_INV_QUADRATIC"""
    moonBrightness: Any
    moonSize: Any
    range: float
    """The color range that will be mapped to 0 - 1."""
    def setWeather(self, name, value) -> Any:
        """Changes a World weather setting at runtime (the "weather." prefix is optional). Booleans: rain, ripples, splash, puddles, puddle_ssr, ripple_puddle_only, splash_puddle_only (both also turn puddles on), aura, lightning, lightning_side, clouds, lens_flare, mist.

        :param name: setting name

        :param value: new value
        """
    skyType: Any
    starStyle: Any
    def strikeLightning(self, bolt=True) -> Any:
        """Strikes a lightning now (World > Rain must be on; automatic lightning can stay off).

        :param bolt: show a bolt; False gives only a far flash behind the clouds
        """
    sunSize: Any
    useSkyAurora: Any
    useSkyMoon: Any
    useSkyStars: Any
    zenithColor: Vector
    """The zenith color. Black = [0.0, 0.0, 0.0, 1.0], White = [1.0, 1.0, 1.0, 1.0]."""

class SCA_2DFilterActuator(SCA_ILogicBrick):
    disableMotionBlur: int
    """action on motion blur: 0=enable, 1=disable."""
    mode: int
    """Type of 2D filter, use one of these constants."""
    passNumber: int
    """order number of filter in the stack of 2D filters. Filters are executed in increasing order of passNb."""
    shaderText: str
    """shader source code for custom shader."""
    value: float
    """argument for motion blur filter."""

class SCA_IController(SCA_ILogicBrick):
    actuators: Any
    """A list of actuators linked to this controller."""
    sensors: Any
    """A list of sensors linked to this controller."""
    state: int
    """The controllers state bitmask. This can be used with the GameObject's state to test if the controller is active."""
    useHighPriority: Any
    """When set the controller executes always before all other controllers that dont have this set."""

class SCA_ANDController(SCA_IController):
    ...

class SCA_ActuatorSensor(SCA_ISensor):
    actuator: str
    """the name of the actuator that the sensor is monitoring."""
    mode: Any

class SCA_AlwaysSensor(SCA_ISensor):
    ...

class SCA_DelaySensor(SCA_ISensor):
    delay: int
    """length of the initial OFF period as number of frame, 0 for immediate trigger."""
    duration: int
    """length of the ON period in number of frame after the initial OFF period."""
    repeat: int
    """1 if the OFF-ON cycle should be repeated indefinately, 0 if it should run once."""
    repeatTimes: int
    """Number of times the actuator will repeat."""
    useDelta: Any

class SCA_InputEvent(EXP_PyObjectPlus):
    activated: bool
    """True if the input was activated from the last frame."""
    active: bool
    """True if the input was active from the last frame."""
    inactive: bool
    """True if the input was inactive from the last frame."""
    queue: list[Any]
    """A list of existing events of the input from the last frame. Can contain bge.logic.KX_INPUT_JUST_ACTIVATED and bge.logic.KX_INPUT_JUST_RELEASED. The list can be empty. (read-only)"""
    released: bool
    """True if the input was released from the last frame."""
    status: list[Any]
    """A list of existing status of the input from the last frame. Can contain bge.logic.KX_INPUT_NONE and bge.logic.KX_INPUT_ACTIVE. The list always contains one value. The first value of the list is the last value of the list in the last frame. (read-only)"""
    type: int
    """The type of the input. One of these constants"""
    values: list[Any]
    """A list of existing value of the input from the last frame. For keyboard it contains 1 or 0 and for mouse the coordinate of the mouse or the movement of the wheel mouse. The list contains always one value, the size of the list is the same than queue + 1 only for keyboard inputs."""

class SCA_JoystickSensor(SCA_ISensor):
    axis: Any
    """The axis this sensor reacts to, as a list of two values [axisIndex, axisDirection]"""
    axisSingle: int
    """like axisValues but returns a single axis value that is set by the sensor. (read-only)."""
    axisValues: list[Any]
    """The state of the joysticks axis as a list of values numAxis long. (read-only)."""
    button: int
    """The button index the sensor reacts to (first button = 0). When the "All Events" toggle is set, this option has no effect."""
    connected: bool
    """True if a joystick is connected at this joysticks index. (read-only)."""
    def getButtonActiveList(self) -> list[Any]:
        """getButtonActiveList Returns a list containing the indices of the button currently pressed."""
    def getButtonStatus(self, buttonIndex) -> bool:
        """:param buttonIndex: the button index, 0=first button"""
    hat: Any
    """The hat the sensor reacts to, as a list of two values: [hatIndex, hatDirection]"""
    hatSingle: int
    """Like hatValues but returns a single hat direction value that is set by the sensor. (read-only)."""
    hatValues: list[Any]
    """The state of the joysticks hats as a list of values numHats long. (read-only)."""
    index: int
    """The joystick index to use (from 0 to 7). The first joystick is always 0."""
    numAxis: int
    """The number of axes for the joystick at this index. (read-only)."""
    numButtons: int
    """The number of buttons for the joystick at this index. (read-only)."""
    numHats: int
    """The number of hats for the joystick at this index. (read-only)."""
    threshold: int
    """Axis threshold. Joystick axis motion below this threshold wont trigger an event. Use values between (0 and 32767), lower values are more sensitive."""

class SCA_KeyboardSensor(SCA_ISensor):
    events: list[Any]
    """a list of pressed keys that have either been pressed, or just released, or are active this frame. (read-only)."""
    def getKeyStatus(self, keycode) -> int:
        """Get the status of a key.

        :param keycode: The code that represents the key you want to get the state of, use one of these constants
        """
    hold1: Any
    """The key code for the first modifier this sensor is looking for."""
    hold2: Any
    """The key code for the second modifier this sensor is looking for."""
    inputs: SCA_InputEvent
    """A list of pressed input keys that have either been pressed, or just released, or are active this frame. (read-only)."""
    key: Any
    """The key code this sensor is looking for."""
    targetProperty: str
    """The name of the property that receives keystrokes in case in case a string is logged."""
    toggleProperty: str
    """The name of the property that indicates whether or not to log keystrokes as a string."""
    useAllKeys: bool
    """Flag to determine whether or not to accept all keys."""

class SCA_NANDController(SCA_IController):
    ...

class SCA_NORController(SCA_IController):
    ...

class SCA_ORController(SCA_IController):
    ...

class SCA_PropertyActuator(SCA_ILogicBrick):
    mode: int
    """TODO - add constants to game logic dict!."""
    propName: str
    """the property on which to operate."""
    value: str
    """the value with which the actuator operates."""

class SCA_PropertySensor(SCA_ISensor):
    max: str
    """the maximum value of the range used to evaluate the property when in interval mode."""
    min: str
    """the minimum value of the range used to evaluate the property when in interval mode."""
    mode: int
    """Type of check on the property. Can be one of these constants"""
    propName: str
    """the property the sensor operates."""
    value: str
    """the value with which the sensor compares to the value of the property."""

class SCA_PythonController(SCA_IController):
    def activate(self, actuator) -> Any:
        """Activates an actuator attached to this controller.

        :param actuator: The actuator to operate on.
        """
    def deactivate(self, actuator) -> Any:
        """Deactivates an actuator attached to this controller.

        :param actuator: The actuator to operate on.
        """
    mode: int
    """the execution mode for this controller (read-only)."""
    script: str
    """The value of this variable depends on the execution methid."""

class SCA_RandomActuator(SCA_ILogicBrick):
    distribution: int
    """Distribution type. (read-only). Can be one of these constants"""
    para1: float
    """the first parameter of the active distribution."""
    para2: float
    """the second parameter of the active distribution."""
    propName: str
    """the name of the property to set with the random value."""
    seed: int
    """Seed of the random number generator."""
    def setBoolBernouilli(self, value) -> Any:
        """Sets this generator to produce a Bernouilli distribution.

        :param value: Specifies the proportion of False values to produce.
        """
    def setBoolConst(self, value) -> Any:
        """Sets this generator to produce a constant boolean value.

        :param value: The value to return.
        """
    def setBoolUniform(self) -> Any:
        """Sets this generator to produce a uniform boolean distribution."""
    def setFloatConst(self, value) -> Any:
        """Always generate the given value."""
    def setFloatNegativeExponential(self, half_life) -> Any:
        """Generate negative-exponentially distributed numbers."""
    def setFloatNormal(self, mean, standard_deviation) -> Any:
        """Generates a random float from the given normal distribution.

        :param mean: The mean (average) value of the generated numbers

        :param standard_deviation: The standard deviation of the generated numbers.
        """
    def setFloatUniform(self, lower_bound, upper_bound) -> Any:
        """Generates a random float between lower_bound and upper_bound with a uniform distribution."""
    def setIntConst(self, value) -> Any:
        """Sets this generator to always produce the given value.

        :param value: the value this generator produces.
        """
    def setIntPoisson(self, value) -> Any:
        """Generate a Poisson-distributed number."""
    def setIntUniform(self, lower_bound, upper_bound) -> Any:
        """Sets this generator to produce a random value between the given lower and upper bounds (inclusive)."""

class SCA_RandomSensor(SCA_ISensor):
    lastDraw: int
    """The seed of the random number generator."""
    seed: int
    """The seed of the random number generator."""

class SCA_VibrationActuator(SCA_ILogicBrick):
    duration: int
    """Duration of the vibration in milliseconds."""
    hasVibration: bool
    """Check if the joystick supports vibration"""
    isVibrating: bool
    """Check status of joystick vibration"""
    joyindex: int
    """Joystick index."""
    def startVibration(self) -> Any:
        """Starts the vibration."""
    def stopVibration(self) -> Any:
        """Stops the vibration."""
    strengthLeft: float
    """Strength of the Low frequency joystick's motor (placed at left position usually)."""
    strengthRight: float
    """Strength of the High frequency joystick's motor (placed at right position usually)."""

class SCA_WaitActuator(SCA_ILogicBrick):
    duration: Any
    elapsed: Any
    useRestart: Any
    waiting: Any

class SCA_XNORController(SCA_IController):
    ...

class SCA_XORController(SCA_IController):
    ...

class TrackLine:
    length: float
    """Total length of the closed line, in meters (read-only)."""
    def locate(self, pos, seg=-1, back=0, ahead=0, lost=0.0) -> tuple:
        """Closest segment of the line to pos.

        :param ahead: segments to test ahead of seg.

        :param back: segments to test behind seg.

        :param lost: distance in meters that triggers the global search.

        :param pos: position in world coordinates.

        :param seg: segment from the previous call, -1 if unknown.
        """
    def point(self, s) -> Vector:
        """Point of the line s meters from the start."""
    def profile(self, name, s) -> float:
        """Value of the profile name interpolated at s meters."""
    def setProfile(self, name, values) -> Any:
        """Stores one value per point under name (curvature, safe speed, any number).

        :param name: profile name.

        :param values: one number per point of the line.
        """
    def side(self, s) -> Vector:
        """Horizontal unit vector pointing to the right of the line at s, or None where the line is vertical or degenerate."""

