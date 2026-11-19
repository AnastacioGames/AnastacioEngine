"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar

from bge.types import EXP_PyObjectPlus
from bgl import Buffer

class DeckLink:
    def close(self) -> Any:
        """Close the DeckLink device and release all resources. After calling this method, the object cannot be reactivated, it must be destroyed and a new DeckLink object created from fresh to restart the output."""
    extend: bool
    """Determines how the image source should be mapped if the size does not fit the video frame size. * False (the default): map the image pixel by pixel. If the image size is smaller than the frame size, extra space around the image is filled with 0-alpha black. If it is larger, the image is cropped to fit the frame size."""
    keying: bool
    """Specify if keying is enabled. False (default): the output frame is sent unmodified on the output interface (in that case no input video is required). True: the output frame is mixed with the input video, using the alpha channel to blend the two images and the combination is sent on the output interface."""
    level: int
    """If keying is enabled, sets the keying level from 0 to 255. This value is a global alpha value that multiplies the alpha channel of the image source. Use 255 (the default) to keep the alpha channel unmodified, 0 to make the output frame totally transparent."""
    def refresh(self, refresh_source, ts) -> Any:
        """This method must be called frequently to update the output frame in the DeckLink device.

        :param refresh_source: True if the source objects image buffer should be invalidated after being

        :param ts: The timestamp value passed to the image source object to compute the image.
        """
    right: Any
    """If the video format is stereo 3D, this attribute should be set to an image source object that will produce the right eye images."""
    source: Any
    """This attribute must be set to one of the image sources. If the image size does not fit exactly the frame size, the extend attribute determines what to do."""

class FilterBGR24:
    ...

class FilterBlueScreen:
    color: Any
    """Reference color."""
    limits: Any
    """Reference color limits."""
    previous: Any
    """Previous pixel filter."""

class FilterColor:
    matrix: Any
    """Matrix [4][5] for color calculation."""
    previous: Any
    """Previous pixel filter."""

class FilterGray:
    previous: Any
    """Previous pixel filter."""

class FilterLevel:
    levels: Any
    """Levels matrix [4] (min, max)."""
    previous: Any
    """Previous pixel filter."""

class FilterNormal:
    colorIdx: int
    """Index of color used to calculate normal (0 - red, 1 - green, 2 - blue, 3 - alpha)."""
    depth: float
    """Depth of relief."""
    previous: Any
    """Previous pixel filter."""

class FilterRGB24:
    ...

class FilterRGBA32:
    ...

class ImageBuff:
    filter: Any
    """Pixel filter."""
    flip: bool
    """Flip image vertically."""
    image: Buffer
    """Image data. (readonly)"""
    def load(self, imageBuffer, width, height) -> Any:
        """Load image from buffer.

        :param height: Height of the image to load.

        :param imageBuffer: Buffer to load the image from.

        :param width: Width of the image to load.
        """
    def plot(self, imageBuffer, width, height, positionX, positionY, mode=...) -> Any:
        """Update image buffer.

        :param height: Height of the data to load.

        :param imageBuffer: Buffer to load the new data from.

        :param mode: Drawing mode, see Image Blending Modes.

        :param positionX: Left boundary of the region to be drawn on.

        :param positionY: Upper boundary of the region to be drawn on.

        :param width: Width of the data to load.
        """
    scale: bool
    """Fast scale of image (near neighbour)."""
    size: tuple
    """Image size. (readonly)"""
    valid: bool
    """Tells if an image is available. (readonly)"""

class ImageFFmpeg:
    filter: Any
    """Pixel filter."""
    flip: bool
    """Flip image vertically."""
    image: Buffer
    """Image data. (readonly)"""
    def refresh(self, buffer=None, format="RGBA") -> int:
        """Refresh image, get its status and optionally copy the frame to an external buffer.

        :param buffer: An optional object that implements the buffer protocol.

        :param format: An optional image format specifier for the image that will be copied to the buffer.
        """
    def reload(self, newname=None) -> Any:
        """Reload image, i.e. reopen it.

        :param newname: Path to a new image. (optional)
        """
    scale: bool
    """Fast scale of image (near neighbour)."""
    size: tuple
    """Image size. (readonly)"""
    status: int
    """Image status. (readonly)"""
    valid: bool
    """Tells if an image is available. (readonly)"""

class ImageMirror:
    alpha: bool
    """Use alpha in texture."""
    background: float
    """horizon color"""
    capsize: Any
    """Size of render area."""
    clip: float
    """Clipping distance."""
    depth: Any
    """get depth information from z-buffer using unsigned int precision"""
    filter: Any
    """Pixel filter."""
    flip: bool
    """Flip image vertically."""
    horizon: float
    """Horizon color."""
    image: Buffer
    """Image data. (readonly)"""
    def refresh(self, buffer=None, format="RGBA") -> Any:
        """Refresh image - render and copy the image to an external buffer (optional) then invalidate its current content.

        :param buffer: An optional object that implements the buffer protocol.

        :param format: An optional image format specifier for the image that will be copied to the buffer.
        """
    def render(self) -> Any:
        """Render scene - run before refresh() to performs asynchronous render"""
    scale: bool
    """Fast scale of image (near neighbour)."""
    size: tuple
    """Image size (readonly)."""
    updateShadow: bool
    """Choose to force shadow buffer update if there is a gap beetween image rendered and shadows."""
    valid: bool
    """Tells if an image is available. (readonly)"""
    whole: bool
    """Use whole viewport to render."""
    zbuff: Any
    """use depth buffer as texture"""
    zenith: float
    """Zenith color."""

class ImageMix:
    filter: Any
    """Pixel filter."""
    flip: bool
    """Flip image vertically."""
    def getSource(self, id) -> Any:
        """Get image source.

        :param id: Identifier of the source to get.
        """
    def getWeight(self, id) -> int:
        """Get image source weight.

        :param id: Identifier of the source.
        """
    image: Buffer
    """Image data. (readonly)"""
    def refresh(self, buffer=None, format="RGBA") -> Any:
        """Refresh image - calculate and copy the image to an external buffer (optional) then invalidate its current content.

        :param buffer: An optional object that implements the buffer protocol.

        :param format: An optional image format specifier for the image that will be copied to the buffer.
        """
    scale: bool
    """Fast scale of image (near neighbour)."""
    def setSource(self, id, image) -> Any:
        """Set image source - all sources must have the same size.

        :param id: Identifier of the source to set.

        :param image: Image source of type...
        """
    def setWeight(self, id, weight) -> Any:
        """Set image source weight - the sum of the weights should be 256 to get full color intensity in the output.

        :param id: Identifier of the source.

        :param weight: Weight of the source.
        """
    size: tuple
    """Image size. (readonly)"""
    valid: bool
    """Tells if an image is available. (readonly)"""

class ImageRender:
    alpha: bool
    """Use alpha in texture."""
    background: float
    """Background color."""
    capsize: Any
    """Size of render area."""
    colorBindCode: int
    """Off-screen color texture bind code."""
    depth: bool
    """Use depth component of render as array of float - not suitable for texture source, should only be used with bge.texture.imageToArray(mode='F')."""
    filter: Any
    """Pixel filter."""
    flip: bool
    """Flip image vertically."""
    horizon: float
    """Horizon color."""
    image: Buffer
    """Image data. (readonly)"""
    def refresh(self, buffer, format="RGBA") -> bool:
        """Refresh video - render and optionally copy the image to an external buffer then invalidate its current content. The render may have been started earlier with the render method, in which case this function simply waits for the render operations to complete.

        :param buffer: An object that implements the buffer protocol.

        :param format: An optional image format specifier for the image that will be copied to the buffer.
        """
    def render(self) -> bool:
        """Render the scene but do not extract the pixels yet. The function returns as soon as the render commands have been send to the GPU. The render will proceed asynchronously in the GPU while the host can perform other tasks."""
    scale: bool
    """Fast scale of image (near neighbour)."""
    size: tuple
    """Image size. (readonly)"""
    updateShadow: bool
    """Choose to force shadow buffer update if there is a gap beetween image rendered and shadows."""
    valid: bool
    """Tells if an image is available. (readonly)"""
    whole: bool
    """Use whole viewport to render."""
    zbuff: bool
    """Use depth component of render as grayscale color - suitable for texture source."""
    zenith: float
    """Zenith color."""

class ImageViewport:
    alpha: bool
    """Use alpha in texture."""
    capsize: Any
    """Size of viewport area being captured."""
    depth: bool
    """Use depth component of viewport as array of float - not suitable for texture source, should only be used with bge.texture.imageToArray(mode='F')."""
    filter: Any
    """Pixel filter."""
    flip: bool
    """Flip image vertically."""
    image: Buffer
    """Image data. (readonly)"""
    position: Any
    """Upper left corner of the captured area."""
    def refresh(self, buffer=None, format="RGBA") -> Any:
        """Refresh video - copy the viewport to an external buffer (optional) then invalidate its current content.

        :param buffer: An optional object that implements the buffer protocol. If specified,

        :param format: An optional image format specifier for the image that will be copied to the buffer.
        """
    scale: bool
    """Fast scale of image (near neighbour)."""
    size: tuple
    """Image size. (readonly)"""
    valid: bool
    """Tells if an image is available. (readonly)"""
    whole: bool
    """Use whole viewport to capture."""
    zbuff: bool
    """Use depth component of viewport as grayscale color - suitable for texture source."""

class Texture(EXP_PyObjectPlus):
    bindId: int
    """OpenGL Bind Name. (readonly)"""
    def close(self) -> Any:
        """Close dynamic texture and restore original."""
    mipmap: bool
    """Mipmap texture."""
    def refresh(self, refresh_source, timestamp=-1.0) -> Any:
        """Refresh texture from source.

        :param refresh_source: Whether to also refresh the image source of the texture.

        :param timestamp: If the texture controls a VideoFFmpeg object:
        """
    source: Any
    """Source of texture."""

class VideoDeckLink:
    filter: Any
    """Not used in this object."""
    flip: bool
    """Not used in this object."""
    framerate: float
    """Capture frame rate as computed from the video format."""
    image: Buffer
    """The image data. Always None in this implementation."""
    def pause(self) -> bool:
        """Temporary stops the capture. Use play() to restart it."""
    def play(self) -> bool:
        """Kick-off the capture after creation of the object."""
    def refresh(self) -> Any:
        """Refresh video - get its status"""
    scale: bool
    """Not used in this object."""
    size: Any
    """The size of the frame in pixel. Stereo frames have double the height of the video frame, i.e. 3D is delivered to the GPU as a single image in top-bottom order, left eye on top."""
    status: int
    """Status of the capture: 1=ready to use, 2=capturing, 3=stopped"""
    def stop(self) -> bool:
        """Stops the capture."""
    valid: bool
    """Tells if the image attribute can be used to retrieve the image. Always False in this implementation (the image is not available at python level)"""

class VideoFFmpeg:
    deinterlace: bool
    """Deinterlace image."""
    filter: Any
    """An additional filter that is applied on the video before sending it to the GPU."""
    flip: bool
    """If True the imaged will be flipped vertically. FFmpeg always delivers the image upside down, so this attribute is set to True by default."""
    framerate: float
    """Relative frame rate, <1.0 for slow, >1.0 for fast."""
    image: Buffer
    """Image data. (readonly)"""
    def pause(self) -> bool:
        """Pause video."""
    def play(self) -> bool:
        """Play (restart) video."""
    preseek: int
    """Number of frames of preseek."""
    range: Any
    """The start and stop time of the video playback, expressed in seconds from beginning. By default the entire video."""
    def refresh(self, buffer=None, format="RGBA", timestamp=-1.0) -> int:
        """Refresh video - get its status and optionally copy the frame to an external buffer.

        :param buffer: An optional object that implements the buffer protocol.

        :param format: An optional image format specifier for the image that will be copied to the buffer.

        :param timestamp: An optional timestamp (in seconds from the start of the movie)
        """
    repeat: int
    """Number of times to replay the video, -1 for infinite repeat."""
    scale: bool
    """Set to True to activate fast nearest neighbor scaling algorithm. Texture width and height must be a power of 2. If the video picture size is not a power of 2, rescaling is required. By default bge.texture uses the precise but slow gluScaleImage() function."""
    def seek(self) -> Any:
        ...
    size: tuple
    """Image size. (readonly)"""
    status: int
    """Video status. (readonly)"""
    def stop(self) -> bool:
        """Stop video (play will replay it from start)."""
    time: Any
    """time of the frame shown in seconds, -1 before the first one"""
    valid: bool
    """Tells if an image is available. (readonly)"""

IMB_BLEND_ADD: int
IMB_BLEND_ADD_ALPHA: int
IMB_BLEND_COLOR: int
IMB_BLEND_COLORBURN: int
IMB_BLEND_COLORDODGE: int
IMB_BLEND_COPY: int
IMB_BLEND_COPY_ALPHA: int
IMB_BLEND_COPY_RGB: int
IMB_BLEND_DARKEN: int
IMB_BLEND_DIFFERENCE: int
IMB_BLEND_ERASE_ALPHA: int
IMB_BLEND_EXCLUSION: int
IMB_BLEND_HARDLIGHT: int
IMB_BLEND_HUE: int
IMB_BLEND_LIGHTEN: int
IMB_BLEND_LINEARBURN: int
IMB_BLEND_LINEARLIGHT: int
IMB_BLEND_LUMINOSITY: int
IMB_BLEND_MIX: int
IMB_BLEND_MUL: int
IMB_BLEND_OVERLAY: int
IMB_BLEND_PINLIGHT: int
IMB_BLEND_SATURATION: int
IMB_BLEND_SCREEN: int
IMB_BLEND_SOFTLIGHT: int
IMB_BLEND_SUB: int
IMB_BLEND_VIVIDLIGHT: int
SOURCE_EMPTY: int
SOURCE_ERROR: int
SOURCE_PLAYING: int
SOURCE_READY: int
SOURCE_STOPPED: int
def getLastError() -> str:
    """Last error that occurred in a bge.texture function."""
def imageToArray(image, mode) -> Buffer:
    """Returns a bgl.Buffer corresponding to the current image stored in a texture source object.

    :param image: Image source object of type:

    :param mode: Optional argument representing the pixel format.
    """
def materialID(object, name) -> int:
    """Returns a numeric value that can be used in Texture to create a dynamic texture.

    :param name: Name of the texture/material you want to make dynamic.

    :param object: The game object that uses the texture you want to make dynamic.
    """
def setLogFile(filename) -> int:
    """Sets the name of a text file in which runtime error messages will be written, in addition to the printing of the messages on the Python console. Only the runtime errors specific to the VideoTexture module are written in that file, ordinary runtime time errors are not written.

    :param filename: Name of the error log file.
    """
