"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar

from bge.types import KX_InputSystem, KX_LibLoadStatus, KX_PythonKeyboard, KX_PythonMotion, KX_PythonMouse, KX_Scene, SCA_PythonController

BL_DST_ALPHA: int
BL_DST_COLOR: int
BL_ONE: int
BL_ONE_MINUS_DST_ALPHA: int
BL_ONE_MINUS_DST_COLOR: int
BL_ONE_MINUS_SRC_ALPHA: int
BL_ONE_MINUS_SRC_COLOR: int
BL_SRC_ALPHA: int
BL_SRC_ALPHA_SATURATE: int
BL_SRC_COLOR: int
BL_ZERO: int
CAM_POS: int
"""Current camera position"""
CONSTANT_TIMER: int
CONSTRAINT_IK_COPYPOSE: int
"""constraint is trying to match the position and eventually the rotation of the target."""
CONSTRAINT_IK_DISTANCE: int
"""Constraint is maintaining a certain distance to target subject to ik_mode"""
CONSTRAINT_IK_FLAG_POS: int
"""Set when the constraint tries to match the position of the target."""
CONSTRAINT_IK_FLAG_ROT: int
"""Set when the constraint tries to match the orientation of the target"""
CONSTRAINT_IK_FLAG_STRETCH: int
"""Set when the armature is allowed to stretch (only the bones with stretch factor > 0.0)"""
CONSTRAINT_IK_FLAG_TIP: int
"""Set when the constraint operates on the head of the bone and not the tail"""
CONSTRAINT_IK_MODE_INSIDE: int
"""The constraint tries to keep the bone within ik_dist of target"""
CONSTRAINT_IK_MODE_ONSURFACE: int
"""The constraint tries to keep the bone exactly at ik_dist of the target."""
CONSTRAINT_IK_MODE_OUTSIDE: int
"""The constraint tries to keep the bone outside ik_dist of the target"""
CONSTRAINT_TYPE_CLAMPTO: int
CONSTRAINT_TYPE_DISTLIMIT: int
CONSTRAINT_TYPE_KINEMATIC: int
CONSTRAINT_TYPE_LOCKTRACK: int
CONSTRAINT_TYPE_LOCLIKE: int
CONSTRAINT_TYPE_MINMAX: int
CONSTRAINT_TYPE_ROTLIKE: int
CONSTRAINT_TYPE_SIZELIKE: int
CONSTRAINT_TYPE_STRETCHTO: int
CONSTRAINT_TYPE_TRACKTO: int
CONSTRAINT_TYPE_TRANSFORM: int
EYE: int
"""User a timer for the uniform value."""
KX_ACTIONACT_FLIPPER: int
KX_ACTIONACT_LOOPEND: int
KX_ACTIONACT_LOOPSTOP: int
KX_ACTIONACT_PINGPONG: int
KX_ACTIONACT_PLAY: int
KX_ACTIONACT_PROPERTY: int
KX_ACTION_BLEND_ADD: int
"""Adds the layers together"""
KX_ACTION_BLEND_BLEND: int
"""Blend layers using linear interpolation"""
KX_ACTION_MODE_LOOP: int
"""Loop the action (repeat it)."""
KX_ACTION_MODE_PING_PONG: int
"""Play the action one direct then back the other way when it has completed."""
KX_ACTION_MODE_PLAY: int
"""Play the action once."""
KX_ACT_ARMATURE_DISABLE: int
"""Disable the constraint (runtime constraint values are not updated)."""
KX_ACT_ARMATURE_ENABLE: int
"""Enable the constraint."""
KX_ACT_ARMATURE_RUN: int
"""Just make sure the armature will be updated on the next graphic frame. This is the only persistent mode of the actuator: it executes automatically once per frame until stopped by a controller"""
KX_ACT_ARMATURE_SETINFLUENCE: int
"""Change influence of constraint."""
KX_ACT_ARMATURE_SETTARGET: int
"""Change target and subtarget of constraint."""
KX_ACT_ARMATURE_SETWEIGHT: int
"""Change weight of constraint (IK only)."""
KX_ACT_MOUSE_OBJECT_AXIS_X: int
KX_ACT_MOUSE_OBJECT_AXIS_Y: int
KX_ACT_MOUSE_OBJECT_AXIS_Z: int
KX_ARMSENSOR_LIN_ERROR_ABOVE: int
"""Detect that the constraint linear error is below a threshold"""
KX_ARMSENSOR_LIN_ERROR_BELOW: int
"""Detect that the constraint linear error is above a threshold"""
KX_ARMSENSOR_ROT_ERROR_ABOVE: int
"""Detect that the constraint rotation error is below a threshold"""
KX_ARMSENSOR_ROT_ERROR_BELOW: int
"""Detect that the constraint rotation error is above a threshold"""
KX_ARMSENSOR_STATE_CHANGED: int
"""Detect that the constraint is changing state (active/inactive)"""
KX_CONSTRAINTACT_DIRNX: int
"""Set distance along negative X axis"""
KX_CONSTRAINTACT_DIRNY: int
"""Set distance along negative Y axis"""
KX_CONSTRAINTACT_DIRNZ: int
"""Set distance along negative Z axis"""
KX_CONSTRAINTACT_DIRPX: int
"""Set distance along positive X axis"""
KX_CONSTRAINTACT_DIRPY: int
"""Set distance along positive Y axis"""
KX_CONSTRAINTACT_DIRPZ: int
"""Set distance along positive Z axis"""
KX_CONSTRAINTACT_DISTANCE: int
"""Activate distance control"""
KX_CONSTRAINTACT_DOROTFH: int
"""Force field act on rotation as well"""
KX_CONSTRAINTACT_FHNX: int
"""Set force field along negative X axis"""
KX_CONSTRAINTACT_FHNY: int
"""Set force field along negative Y axis"""
KX_CONSTRAINTACT_FHNZ: int
"""Set force field along negative Z axis"""
KX_CONSTRAINTACT_FHPX: int
"""Set force field along positive X axis"""
KX_CONSTRAINTACT_FHPY: int
"""Set force field along positive Y axis"""
KX_CONSTRAINTACT_FHPZ: int
"""Set force field along positive Z axis"""
KX_CONSTRAINTACT_LOCAL: int
"""Direction of the ray is along the local axis"""
KX_CONSTRAINTACT_LOCX: int
"""Limit X coord."""
KX_CONSTRAINTACT_LOCY: int
"""Limit Y coord"""
KX_CONSTRAINTACT_LOCZ: int
"""Limit Z coord"""
KX_CONSTRAINTACT_MATERIAL: int
"""Detect material rather than property"""
KX_CONSTRAINTACT_NORMAL: int
"""Activate alignment to surface"""
KX_CONSTRAINTACT_ORIX: int
"""Set orientation of X axis"""
KX_CONSTRAINTACT_ORIY: int
"""Set orientation of Y axis"""
KX_CONSTRAINTACT_ORIZ: int
"""Set orientation of Z axis"""
KX_CONSTRAINTACT_PERMANENT: int
"""No deactivation if ray does not hit target"""
KX_CONSTRAINTACT_ROTX: int
"""Limit X rotation"""
KX_CONSTRAINTACT_ROTY: int
"""Limit Y rotation"""
KX_CONSTRAINTACT_ROTZ: int
"""Limit Z rotation"""
KX_DYN_DISABLE_DYNAMICS: int
KX_DYN_DISABLE_RIGID_BODY: int
KX_DYN_ENABLE_RIGID_BODY: int
KX_DYN_RESTORE_DYNAMICS: int
KX_DYN_SET_MASS: int
KX_FALSE: int
"""False value used by some modules."""
KX_GAME_LOAD: int
KX_GAME_LOADCFG: int
KX_GAME_QUIT: int
KX_GAME_RESTART: int
KX_GAME_SAVECFG: int
KX_GAME_SCREENSHOT: int
KX_GAME_START: int
KX_INPUT_ACTIVE: int
KX_INPUT_JUST_ACTIVATED: int
KX_INPUT_JUST_RELEASED: int
KX_INPUT_NONE: int
KX_JOYSTICK_BUT_A: int
KX_JOYSTICK_BUT_B: int
KX_JOYSTICK_BUT_BACK: int
KX_JOYSTICK_BUT_GUIDE: int
KX_JOYSTICK_BUT_LEFTSHOUDER: int
KX_JOYSTICK_BUT_LEFTSTICK: int
KX_JOYSTICK_BUT_PADDOWN: int
KX_JOYSTICK_BUT_PADLEFT: int
KX_JOYSTICK_BUT_PADRIGHT: int
KX_JOYSTICK_BUT_PADUP: int
KX_JOYSTICK_BUT_RIGHTSHOUDER: int
KX_JOYSTICK_BUT_RIGHTSTICK: int
KX_JOYSTICK_BUT_X: int
KX_JOYSTICK_BUT_Y: int
KX_MOUSESENSORMODE_BUTTON6: int
KX_MOUSESENSORMODE_BUTTON7: int
KX_MOUSESENSORMODE_LEFTBUTTON: int
KX_MOUSESENSORMODE_LEFTTHUMBMOUSE: int
KX_MOUSESENSORMODE_MIDDLEBUTTON: int
KX_MOUSESENSORMODE_MOVEMENT: int
KX_MOUSESENSORMODE_RIGHTBUTTON: int
KX_MOUSESENSORMODE_RIGHTTHUMBMOUSE: int
KX_MOUSESENSORMODE_WHEELDOWN: int
KX_MOUSESENSORMODE_WHEELUP: int
KX_MOUSE_BUT_BUTTON6: int
KX_MOUSE_BUT_BUTTON7: int
KX_MOUSE_BUT_LEFT: int
KX_MOUSE_BUT_LEFTTHUMBMOUSE: int
KX_MOUSE_BUT_MIDDLE: int
KX_MOUSE_BUT_RIGHT: int
KX_MOUSE_BUT_RIGHTTHUMBMOUSE: int
KX_MOVEMENT_ALL_AXIS: int
KX_MOVEMENT_AXIS_NEG_X: int
KX_MOVEMENT_AXIS_NEG_Y: int
KX_MOVEMENT_AXIS_NEG_Z: int
KX_MOVEMENT_AXIS_POS_X: int
KX_MOVEMENT_AXIS_POS_Y: int
KX_MOVEMENT_AXIS_POS_Z: int
KX_PARENT_REMOVE: int
KX_PARENT_SET: int
KX_PROPSENSOR_CHANGED: int
"""Activate when the property changes"""
KX_PROPSENSOR_EQUAL: int
"""Activate when the property is equal to the sensor value."""
KX_PROPSENSOR_EXPRESSION: int
"""Activate when the expression matches"""
KX_PROPSENSOR_GREATERTHAN: int
"""Activate when the property is greater than the sensor value"""
KX_PROPSENSOR_INTERVAL: int
"""Activate when the property is between the specified limits."""
KX_PROPSENSOR_LESSTHAN: int
"""Activate when the property is less than the sensor value"""
KX_PROPSENSOR_NOTEQUAL: int
"""Activate when the property is not equal to the sensor value."""
KX_RADAR_AXIS_NEG_X: int
KX_RADAR_AXIS_NEG_Y: int
KX_RADAR_AXIS_NEG_Z: int
KX_RADAR_AXIS_POS_X: int
KX_RADAR_AXIS_POS_Y: int
KX_RADAR_AXIS_POS_Z: int
KX_RANDOMACT_BOOL_BERNOUILLI: int
KX_RANDOMACT_BOOL_CONST: int
KX_RANDOMACT_BOOL_UNIFORM: int
KX_RANDOMACT_FLOAT_CONST: int
KX_RANDOMACT_FLOAT_NEGATIVE_EXPONENTIAL: int
KX_RANDOMACT_FLOAT_NORMAL: int
KX_RANDOMACT_FLOAT_UNIFORM: int
KX_RANDOMACT_INT_CONST: int
KX_RANDOMACT_INT_POISSON: int
KX_RANDOMACT_INT_UNIFORM: int
KX_RAY_AXIS_NEG_X: int
KX_RAY_AXIS_NEG_Y: int
KX_RAY_AXIS_NEG_Z: int
KX_RAY_AXIS_POS_X: int
KX_RAY_AXIS_POS_Y: int
KX_RAY_AXIS_POS_Z: int
KX_SCENE_ADD_BACK_SCENE: int
KX_SCENE_ADD_FRONT_SCENE: int
KX_SCENE_REMOVE_SCENE: int
KX_SCENE_RESTART: int
KX_SCENE_RESUME: int
KX_SCENE_SET_CAMERA: int
KX_SCENE_SET_SCENE: int
KX_SCENE_SUSPEND: int
KX_SENSOR_ACTIVE: int
KX_SENSOR_INACTIVE: int
KX_SENSOR_JUST_ACTIVATED: int
KX_SENSOR_JUST_DEACTIVATED: int
KX_SOUNDACT_LOOPBIDIRECTIONAL: int
KX_SOUNDACT_LOOPBIDIRECTIONAL_STOP: int
KX_SOUNDACT_LOOPEND: int
KX_SOUNDACT_LOOPSTOP: int
KX_SOUNDACT_PLAYEND: int
KX_SOUNDACT_PLAYSTOP: int
KX_STATE1: int
KX_STATE10: int
KX_STATE11: int
KX_STATE12: int
KX_STATE13: int
KX_STATE14: int
KX_STATE15: int
KX_STATE16: int
KX_STATE17: int
KX_STATE18: int
KX_STATE19: int
KX_STATE2: int
KX_STATE20: int
KX_STATE21: int
KX_STATE22: int
KX_STATE23: int
KX_STATE24: int
KX_STATE25: int
KX_STATE26: int
KX_STATE27: int
KX_STATE28: int
KX_STATE29: int
KX_STATE3: int
KX_STATE30: int
KX_STATE4: int
KX_STATE5: int
KX_STATE6: int
KX_STATE7: int
KX_STATE8: int
KX_STATE9: int
KX_STATE_OP_CLR: int
"""Substract bits to state mask"""
KX_STATE_OP_CPY: int
"""Copy state mask"""
KX_STATE_OP_NEG: int
"""Invert bits to state mask"""
KX_STATE_OP_SET: int
"""Add bits to state mask"""
KX_STEERING_FLEE: int
KX_STEERING_PATHFOLLOWING: int
KX_STEERING_SEEK: int
KX_TRACK_TRAXIS_NEG_X: int
KX_TRACK_TRAXIS_NEG_Y: int
KX_TRACK_TRAXIS_NEG_Z: int
KX_TRACK_TRAXIS_POS_X: int
KX_TRACK_TRAXIS_POS_Y: int
KX_TRACK_TRAXIS_POS_Z: int
KX_TRACK_UPAXIS_POS_X: int
KX_TRACK_UPAXIS_POS_Y: int
KX_TRACK_UPAXIS_POS_Z: int
KX_TRUE: int
"""True value used by some modules."""
def LibFree(name) -> Any:
    """Frees a library, removing all objects and meshes from the currently active scenes.

    :param name: The name of the library to free (the name used in LibNew)
    """
def LibList() -> list[Any]:
    """Returns a list of currently loaded libraries."""
def LibLoad(blend, type, data, load_actions=False, verbose=False, load_scripts=True, asynchronous=False, scene=None) -> KX_LibLoadStatus:
    """Converts the all of the datablocks of the given type from the given blend.

    :param asynchronous: Whether or not to do the loading asynchronously (in another thread). Only the "Scene" type is currently supported for this feature.

    :param blend: The path to the blend file (or the name to use for the library if data is supplied)

    :param data: Binary data from a blend file (optional)

    :param load_actions: Search for and load all actions in a given Scene and not just the "active" actions (Scene type only)

    :param load_scripts: Whether or not to load text datablocks as well (can be disabled for some extra security)

    :param scene: Scene to merge loaded data to, if None use the current scene.

    :param type: The datablock type (currently only "Action", "Mesh" and "Scene" are supported)

    :param verbose: Whether or not to print debugging information (e.g., "SceneName: Scene")
    """
def LibNew(name, type, data) -> Any:
    """Uses existing datablock data and loads in as a new library.

    :param data: A list of names of the datablocks to load

    :param name: A unique library name used for removal later

    :param type: The datablock type (currently only "Mesh" is supported)
    """
MODELMATRIX: int
MODELMATRIX_INVERSE: int
MODELMATRIX_INVERSETRANSPOSE: int
MODELMATRIX_TRANSPOSE: int
MODELVIEWMATRIX: int
MODELVIEWMATRIX_INVERSE: int
MODELVIEWMATRIX_INVERSETRANSPOSE: int
MODELVIEWMATRIX_TRANSPOSE: int
def NextFrame() -> Any:
    """Render next frame (if Python has control)"""
def PrintGLInfo() -> Any:
    """Prints GL Extension Info into the console"""
def PrintMemInfo() -> Any:
    """Prints engine statistics into the console"""
RAS_2DFILTER_BLOOM: int
RAS_2DFILTER_BLUR: int
RAS_2DFILTER_CUSTOMFILTER: int
"""Customer filter, the code code is set via shaderText property."""
RAS_2DFILTER_DILATION: int
RAS_2DFILTER_DISABLED: int
"""Disable the filter that is currently active"""
RAS_2DFILTER_ENABLED: int
"""Enable the filter that was previously disabled"""
RAS_2DFILTER_EROSION: int
RAS_2DFILTER_FXAA: int
RAS_2DFILTER_GRAYSCALE: int
RAS_2DFILTER_INVERT: int
RAS_2DFILTER_LAPLACIAN: int
RAS_2DFILTER_LIGHTSCATTER: int
RAS_2DFILTER_MOTIONBLUR: int
"""Create and enable preset filters"""
RAS_2DFILTER_NOFILTER: int
"""Disable and destroy the filter that is currently active"""
RAS_2DFILTER_OUTLINE: int
RAS_2DFILTER_PREWITT: int
RAS_2DFILTER_SEPIA: int
RAS_2DFILTER_SHARPEN: int
RAS_2DFILTER_SOBEL: int
RAS_2DFILTER_SSAO: int
RAS_2DFILTER_SSR: int
RAS_2DFILTER_TONEMAP: int
RM_POLYS: int
"""Draw only polygons."""
RM_TRIS: int
"""Draw triangle mesh."""
RM_WALLS: int
"""Draw only the walls."""
ROT_MODE_QUAT: int
"""Use quaternion in rotation attribute to update bone rotation."""
ROT_MODE_XYZ: int
"""Use euler_rotation and apply angles on bone's Z, Y, X axis successively."""
ROT_MODE_XZY: int
"""Use euler_rotation and apply angles on bone's Y, Z, X axis successively."""
ROT_MODE_YXZ: int
"""Use euler_rotation and apply angles on bone's Z, X, Y axis successively."""
ROT_MODE_YZX: int
"""Use euler_rotation and apply angles on bone's X, Z, Y axis successively."""
ROT_MODE_ZXY: int
"""Use euler_rotation and apply angles on bone's Y, X, Z axis successively."""
ROT_MODE_ZYX: int
"""Use euler_rotation and apply angles on bone's X, Y, Z axis successively."""
SHD_TANGENT: int
VIEWMATRIX: int
VIEWMATRIX_INVERSE: int
VIEWMATRIX_INVERSETRANSPOSE: int
VIEWMATRIX_TRANSPOSE: int
def addScene(name, overlay=1, asynchronous=False) -> Any:
    """Loads a scene into the game engine.

    :param asynchronous: Compile the scene shaders a few per frame (budget of setLibLoadFrameBudget)

    :param name: The name of the scene

    :param overlay: Overlay or underlay (optional)
    """
def deltaTime() -> Any:
    """Get deltaTime"""
def endGame() -> Any:
    """Ends the current game."""
error: str
def expandPath(path) -> str:
    """Converts a blender internal path into a proper file system path.

    :param path: The path string to be converted/expanded.
    """
def freeUnconvertedData() -> Any:
    ...
def getAnimationRate() -> Any:
    """Gets the animation tic rate"""
def getAnimationsUseTimeScale() -> bool:
    """True if animations follow the time scale"""
def getAverageFrameRate() -> float:
    """Gets the estimated/average framerate for all the active scenes, not only the current scene."""
def getBlendFileList(path="//") -> list[Any]:
    """Returns a list of blend files in the same directory as the open blend file, or from using the option argument.

    :param path: Optional directory argument, will be expanded (like expandPath) into the full path.
    """
def getClockTime() -> float:
    """Get the current BGE render time, in seconds. The BGE render time is the simulation time corresponding to the next scene that will be rendered."""
def getCurrentController() -> SCA_PythonController:
    """Gets the Python controller associated with this Python script."""
def getCurrentScene() -> KX_Scene:
    """Gets the current Scene."""
def getExitKey() -> int:
    """Gets the key used to exit the game engine"""
def getFrameTime() -> float:
    """Get the current BGE frame time, in seconds. The BGE frame time is the simulation time corresponding to the current call of the logic system. Generally speaking, it is what the user is interested in."""
def getGraphicsCardRenderer() -> Any:
    """Gets graphics card renderer name"""
def getGraphicsCardVendor() -> Any:
    """Gets graphics card vendor name"""
def getInactiveSceneNames() -> list[Any]:
    """Gets a list of the scene's names not loaded in the game engine."""
def getLoadLog() -> Any:
    ...
def getLogicTicRate() -> float:
    """Gets the logic update frequency."""
def getMaxLogicFrame() -> int:
    """Gets the maximum number of logic frames per render frame."""
def getMaxPhysicsFrame() -> int:
    """Deprecated, has no effect on the engine: no scheduler consumes this limit. Kept only for file/script compatibility"""
def getMessages() -> Any:
    ...
def getObjectConvert() -> Any:
    ...
def getPhysicsTicRate() -> float:
    """Gets the physics update frequency"""
def getProcessorName() -> Any:
    """Gets processor name"""
def getProfileInfo() -> Any:
    """Returns a Python dictionary that contains the same information as the on screen profiler. The keys are the profiler categories and the values are tuples with the first element being time taken (in ms) and the second element being the percentage of total time."""
def getRandomFloat() -> Any:
    """Returns a random floating point value in the range [0 - 1)"""
def getRangeFileList() -> Any:
    """Gets a list of range files in the same directory as the current range file"""
def getRasecFileList() -> Any:
    """Gets a list of rasec files in the same directory as the current range file"""
def getRealTime() -> float:
    """Get the number of real (system-clock) seconds elapsed since the beginning of the simulation."""
def getRender() -> bool:
    """Get the current value of the global render flag"""
def getRenderRate() -> Any:
    """Gets the render tic rate"""
def getRenderStats() -> Any:
    """Returns a Python dictionary of integer counters from the last completed frame, the same numbers the Debug Mode render queries show. Unlike the frame times from getProfileInfo, these do not depend on the hardware or the clock, so they are what A/B tests should compare."""
def getSceneList() -> list[KX_Scene]:
    """Gets a list of the current scenes loaded in the game engine."""
def getSpectrum(*args: Any, **kwargs: Any) -> list[Any]:
    """Returns a 512 point list from the sound card. This only works if the fmod sound driver is being used."""
def getTimeScale() -> float:
    """Get the time multiplier between real-time and simulation time. The default value is 1.0. A value greater than 1.0 means that the simulation is going faster than real-time, a value lower than 1.0 means that the simulation is going slower than real-time."""
def getUseExternalClock() -> bool:
    """Deprecated: returns the stored flag, which has no effect"""
globalDict: dict
"""A dictionary that is saved between loading blend files so you can use it to store inventory and other variables you want to store between scenes and blend files. It can also be written to a file and loaded later on with the game load/save actuators."""
inputSystem: KX_InputSystem
"""The input maps of the game, a bge.types.KX_InputSystem. They are loaded from the JSON files in the KeyMapping folder, next to the game file."""
joysticks: list[Any]
"""A list of attached bge.types.SCA_PythonJoystick. The list size is the maximum number of supported joysticks. If no joystick is available for a given slot, the slot is set to None."""
keyboard: KX_PythonKeyboard
"""The current keyboard wrapped in an bge.types.SCA_PythonKeyboard object."""
def loadGlobalDict() -> Any:
    """Loads bge.logic.globalDict from a file."""
motion: KX_PythonMotion
"""Device motion sensors (gyroscope, accelerometer, tilt) wrapped in a bge.types.KX_PythonMotion object."""
mouse: KX_PythonMouse
"""The current mouse wrapped in an bge.types.SCA_PythonMouse object."""
def preloadScene() -> Any:
    ...
def restartGame() -> Any:
    """Restarts the current game by reloading the .blend file (the last saved version, not what is currently running)."""
def saveGlobalDict() -> Any:
    """Saves bge.logic.globalDict to a file."""
def sendMessage(subject, body="", to="", message_from="") -> Any:
    """Sends a message to sensors in any active scene.

    :param body: The body of the message (optional)

    :param message_from: The name of the object that the message is coming from (optional)

    :param subject: The subject of the message

    :param to: The name of the object to send the message to (optional)
    """
def setAnimationRate() -> Any:
    """Sets the animation tic rate"""
def setAnimationsUseTimeScale(use) -> Any:
    """Choose whether actions follow setTimeScale. With False the animation clock advances by the unscaled logic step, so actions play at full speed while physics, timers and logic stay scaled. Default True.

    :param use: True to scale animations, False to keep them at full speed.
    """
def setClockTime(new_time) -> Any:
    """Set the next value of the simulation clock. It is preferable to use this method from a custom main function in python, as calling it in the logic block can easily lead to a blocked system (if the time does not advance enough to run at least the next logic step).

    :param new_time: the next value of the BGE clock (in second).
    """
def setExitKey(key) -> Any:
    """Sets the key used to exit the game engine

    :param key: A key constant from bge.events
    """
def setGravity(gravity) -> Any:
    """Sets the world gravity.

    :param gravity: gravity vector
    """
def setLibLoadFrameBudget(ms=...) -> float:
    """Time per frame, in milliseconds, that asynchronous LibLoad may spend merging loaded libraries into the scene (textures, shaders, objects). The default of 8 keeps the game frame rate; a loading screen can raise it (e.g. 30) to finish sooner at a lower frame rate, then set it back.

    :param ms: New budget; omitted, only returns the current one.
    """
def setLogicTicRate(ticrate) -> Any:
    """Sets the logic update frequency.

    :param ticrate: The new logic update frequency (in Hz).
    """
def setMaxLogicFrame(maxlogic) -> Any:
    """Sets the maximum number of logic frames that are executed per render frame. This does not affect the physic system that still runs at full frame rate.

    :param maxlogic: The new maximum number of logic frames per render frame. Valid values: 1..5
    """
def setMaxPhysicsFrame(maxphysics) -> Any:
    """Deprecated, has no effect on the engine: no scheduler consumes this limit, and it no longer controls shadow culling either. Kept only for file/script compatibility

    :param maxphysics: The new maximum number of physics timestep per render frame. Valid values: 1..5.
    """
def setNeedsParents() -> Any:
    """Sets parents update from 3 to 1"""
def setObjectConvert() -> Any:
    ...
def setPhysicsTicRate(ticrate) -> Any:
    """Sets the physics update frequency

    :param ticrate: The new update frequency (in Hz).
    """
def setRender(render) -> Any:
    """Sets the global flag that controls the render of the scene. If True, the render is done after the logic frame. If False, the render is skipped and another logic frame starts immediately.

    :param render: the render flag
    """
def setRenderRate() -> Any:
    """Sets the render tic rate"""
def setTimeScale(time_scale) -> Any:
    """Set the time multiplier between real-time and simulation time. A value greater than 1.0 means that the simulation is going faster than real-time, a value lower than 1.0 means that the simulation is going slower than real-time. Note that a too large value may lead to some physics instabilities.

    :param time_scale: The new time multiplier.
    """
def setUseExternalClock(use_external_clock) -> Any:
    """Deprecated: has no effect on the simulation

    :param use_external_clock: the new setting
    """
def startGame(blend) -> Any:
    """Loads the blend file.

    :param blend: The name of the blend file
    """
