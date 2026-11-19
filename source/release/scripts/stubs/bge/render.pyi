"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar


HDR_FULL_FLOAT: int
"""Use 32 bit float per channel image format."""
HDR_HALF_FLOAT: int
"""Use 16 bit float per channel image format."""
HDR_NONE: int
"""Use 8 bit per channel image format."""
KX_BLENDER_GLSL_MATERIAL: int
"""Deprecated."""
KX_BLENDER_MULTITEX_MATERIAL: int
"""Deprecated."""
LEFT_EYE: int
"""Left eye being used during stereoscopic rendering."""
RAS_MIPMAP_LINEAR: int
RAS_MIPMAP_NEAREST: int
RAS_MIPMAP_NONE: int
RIGHT_EYE: int
"""Right eye being used during stereoscopic rendering."""
STEREO_ABOVEBELOW: int
STEREO_ANAGLYPH: int
STEREO_INTERLACED: int
STEREO_NOSTEREO: int
STEREO_SIDEBYSIDE: int
VSYNC_ADAPTIVE: int
VSYNC_OFF: int
VSYNC_ON: int
def autoDebugList(enable) -> Any:
    """Enable or disable auto adding debug properties to the debug list."""
def clearDebugList() -> Any:
    """Clears the debug property list."""
def disableMotionBlur() -> Any:
    """Disable the motion blur effect."""
def drawLine(fromVec, toVec, color) -> Any:
    """Draw a line in the 3D scene.

    :param color: the color of the line

    :param fromVec: the origin of the line

    :param toVec: the end of the line
    """
def enableMotionBlur(factor) -> Any:
    """Enable the motion blur effect.

    :param factor: the ammount of motion blur to display.
    """
def enableVisibility(visible) -> Any:
    """Deprecated; doesn't do anything."""
error: str
def getAnisotropicFiltering() -> int:
    """Get the anisotropic filtering level used for textures."""
def getAntiAliasing() -> int:
    """Get the anti aliasing level setting."""
def getDisplayDimensions() -> tuple:
    """Get the display dimensions, in pixels, of the display (e.g., the monitor). Can return the size of the entire view, so the combination of all monitors; for example, (3840, 1080) for two side-by-side 1080p monitors."""
def getEyeSeparation() -> float:
    """Gets the current eye separation for stereo mode."""
def getFocalLength() -> float:
    """Gets the current focal length for stereo mode."""
def getFullScreen() -> bool:
    """Returns whether or not the window is fullscreen."""
def getGLSLMaterialSetting(setting) -> bool:
    """Get the state of a GLSL material setting."""
def getMasterVolume() -> Any:
    ...
def getMaterialMode(mode) -> Any:
    """Deprecated and no longer functional."""
def getMipmapping() -> Any:
    """Get the current mipmapping setting."""
def getRenderScale() -> float:
    """Current render scale, 1.0 = full resolution."""
def getStereoEye() -> Any:
    """Gets the current stereoscopy eye being rendered. This function is mainly used in a bge.types.KX_Scene.pre_draw callback function to customize the camera projection matrices for each stereoscopic eye."""
def getStereoMode() -> Any:
    """get the stereo mode"""
def getTextureQuality() -> int:
    ...
def getVRChromaticAberration() -> Any:
    """get the VR lens chromatic aberration correction"""
def getVRLensStrength() -> Any:
    """get the VR lens distortion strength"""
def getVsync() -> Any:
    """Get the current vsync value"""
def getWindowHeight() -> int:
    """Gets the height of the window (in pixels)"""
def getWindowWidth() -> int:
    """Gets the width of the window (in pixels)"""
def makeScreenshot(filename) -> Any:
    """Writes an image file with the displayed image at the frame end.

    :param filename: path and name of the file to write
    """
def setAnisotropicFiltering(level) -> Any:
    """Set the anisotropic filtering level for textures.

    :param level: The new anisotropic filtering level to use
    """
def setAntiAliasing(level) -> Any:
    """Set the anti aliasing level.

    :param level: The new anti aliasing level to use
    """
def setBackgroundColor(rgba) -> Any:
    """Deprecated and no longer functional. Use bge.types.KX_WorldInfo.horizonColor or bge.types.KX_WorldInfo.zenithColor instead."""
def setCustomMouse() -> Any:
    ...
def setDynamicResolution(enabled, targetFPS=60, minScale=50, maxScale=100, step=5) -> Any:
    """Runtime version of the scene's Dynamic Resolution settings. The 3D scene is rendered at a scale of the window size and stretched to the screen; the window itself does not change. With dynamic resolution the scale goes down by step when the GPU time of a frame is above the target and back up when there is time left.

    :param enabled: False renders at 100%.

    :param maxScale: Highest scale, in percent (25-100).

    :param minScale: Lowest scale, in percent (25-100).

    :param step: Scale change per adjustment, in percent (1-25).

    :param targetFPS: Frame rate the GPU time is compared to.
    """
def setEyeSeparation(eyesep) -> Any:
    """Sets the eye separation for stereo mode. Usually Focal Length/30 provides a confortable value.

    :param eyesep: The distance between the left and right eye.
    """
def setFocalLength(focallength) -> Any:
    """Sets the focal length for stereo mode. It uses the current camera focal length as initial value.

    :param focallength: The focal length.
    """
def setFullScreen(enable) -> Any:
    """Set whether or not the window should be fullscreen.

    :param enable: True to set full screen, False to set windowed.
    """
def setGLSLMaterialSetting(setting, enable) -> Any:
    """Enables or disables a GLSL material setting."""
def setMasterVolume() -> Any:
    ...
def setMaterialMode(mode) -> Any:
    """Deprecated and no longer functional.

    :param mode: material mode
    """
def setMipmapping(value) -> Any:
    """Change how to use mipmapping."""
def setMousePosition(x, y) -> Any:
    """Sets the mouse cursor position.

    :param x: X-coordinate in screen pixel coordinates.

    :param y: Y-coordinate in screen pixel coordinates.
    """
def setStereoMode() -> Any:
    """set the stereo mode (STEREO_* constants)"""
def setTextureQuality(level) -> Any:
    """Texture quality of a graphics menu: keep only the high resolution texture in the project and drop its largest mipmap levels when it is sent to the graphics card.

    :param level: 0, 1 or 2
    """
def setVRChromaticAberration() -> Any:
    """set the VR lens chromatic aberration correction (0..0.1, default 0.01)"""
def setVRLensStrength() -> Any:
    """set the VR lens distortion strength (0..1, default 0.3)"""
def setVsync(value) -> Any:
    """Set the vsync value

    :param value: One of VSYNC_OFF, VSYNC_ON, VSYNC_ADAPTIVE
    """
def setWindowSize(width, height) -> Any:
    """Set the width and height of the window (in pixels). This also works for fullscreen applications.

    :param height: height in pixels

    :param width: width in pixels
    """
def showDebugPhysics() -> Any:
    ...
def showFramerate(enable) -> Any:
    """Show or hide the framerate."""
def showMouse(visible) -> Any:
    """Enables or disables the operating system mouse cursor."""
def showProfile(enable) -> Any:
    """Show or hide the profile."""
def showProperties(enable) -> Any:
    """Show or hide the debug properties."""
