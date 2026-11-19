"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar


class Device:
    channels: Any
    """The channel count of the device."""
    distance_model: Any
    """The distance model of the device."""
    doppler_factor: Any
    """The doppler factor of the device. This factor is a scaling factor for the velocity vectors in doppler calculation. So a value bigger than 1 will exaggerate the effect as it raises the velocity."""
    format: Any
    """The native sample format of the device."""
    listener_location: Any
    """The listeners's location in 3D space, a 3D tuple of floats."""
    listener_orientation: Any
    """The listener's orientation in 3D space as quaternion, a 4 float tuple."""
    listener_velocity: Any
    """The listener's velocity in 3D space, a 3D tuple of floats."""
    def lock(self) -> Any:
        """Locks the device so that it's guaranteed, that no samples are read from the streams until :meth:`unlock` is called. This is useful if you want to do start/stop/pause/resume some sounds at the same time."""
    def play(self, sound, keep=False) -> Handle:
        """Plays a sound."""
    rate: Any
    """The sampling rate of the device in Hz."""
    speed_of_sound: Any
    """The speed of sound of the device. The speed of sound in air is typically 343.3 m/s."""
    def stopAll(self) -> Any:
        """Stops all playing and paused sounds."""
    def unlock(self) -> Any:
        """Unlocks the device after a lock call, see :meth:`lock` for details."""
    volume: Any
    """The overall volume of the device."""

class DynamicMusic:
    def addScene(self, scene) -> int:
        """Adds a new scene."""
    def addTransition(self, ini, end, transition) -> bool:
        """Adds a new scene."""
    fadeTime: Any
    """The length in seconds of the crossfade transition"""
    def pause(self) -> bool:
        """Pauses playback of the scene."""
    position: Any
    """The playback position of the scene in seconds."""
    def resume(self) -> bool:
        """Resumes playback of the scene."""
    scene: Any
    """The current scene"""
    status: Any
    """Whether the scene is playing, paused or stopped (=invalid)."""
    def stop(self) -> bool:
        """Stops playback of the scene."""
    volume: Any
    """The volume of the scene."""

class Handle:
    attenuation: Any
    """This factor is used for distance based attenuation of the source."""
    cone_angle_inner: Any
    """The opening angle of the inner cone of the source. If the cone values of a source are set there are two (audible) cones with the apex at the :attr:`location` of the source and with infinite height, heading in the direction of the source's :attr:`orientation`. In the inner cone the volume is normal."""
    cone_angle_outer: Any
    """The opening angle of the outer cone of the source."""
    cone_volume_outer: Any
    """The volume outside the outer cone of the source."""
    distance_maximum: Any
    """The maximum distance of the source. If the listener is further away the source volume will be 0."""
    distance_reference: Any
    """The reference distance of the source. At this distance the volume will be exactly :attr:`volume`."""
    keep: Any
    """Whether the sound should be kept paused in the device when its end is reached. This can be used to seek the sound to some position and start playback again."""
    location: Any
    """The source's location in 3D space, a 3D tuple of floats."""
    loop_count: Any
    """The (remaining) loop count of the sound. A negative value indicates infinity."""
    orientation: Any
    """The source's orientation in 3D space as quaternion, a 4 float tuple."""
    def pause(self) -> bool:
        """Pauses playback."""
    pitch: Any
    """The pitch of the sound."""
    position: Any
    """The playback position of the sound in seconds."""
    relative: Any
    """Whether the source's location, velocity and orientation is relative or absolute to the listener."""
    def resume(self) -> bool:
        """Resumes playback."""
    status: Any
    """Whether the sound is playing, paused or stopped (=invalid)."""
    def stop(self) -> bool:
        """Stops playback."""
    velocity: Any
    """The source's velocity in 3D space, a 3D tuple of floats."""
    volume: Any
    """The volume of the sound."""
    volume_maximum: Any
    """The maximum volume of the source."""
    volume_minimum: Any
    """The minimum volume of the source."""

class Microphone:
    active: Any
    """Whether the capture is open."""
    backend: Any
    """Backend in use."""
    def backends(self) -> list[Any]:
        """Lists the capture backends ("OpenAL", "WebAudio", "Test")."""
    channels: Any
    """Channel count."""
    def devices(self, backend=None) -> list[Any]:
        """Lists the capture devices of a backend (default: the best one)."""
    dropped: Any
    """How many times samples were lost."""
    error: Any
    """Last error message."""
    last_recording: Any
    """Last recording as a Sound, or None."""
    level: Any
    """RMS level of the last block (0..1)."""
    live: Any
    """A new Sound that plays the microphone live (silence when there is no data)."""
    peak: Any
    """Peak level with smooth fall (0..1)."""
    pitch: Any
    """(frequency in Hz, confidence); frequency is 0 with no clear note."""
    def poll(self) -> Any:
        """Pulls new samples, updating :attr:`level`, :attr:`peak` and the recording. Call it once per frame/timer tick. Live sounds also poll by themselves."""
    rate: Any
    """Real sample rate."""
    def record_start(self) -> Any:
        """Starts recording from now on."""
    def record_stop(self) -> Sound:
        """Stops recording and returns what was recorded."""
    recording: Any
    """Whether it is recording."""
    recording_seconds: Any
    """Length of the current recording."""
    def save_wav(self, path) -> Any:
        """Saves the last recording as a 16 bit WAV file."""
    def start(self) -> bool:
        """Opens the capture. Returns False on error (see :attr:`error`). On the Web it returns True while the permission is still pending."""
    state: Any
    """'closed', 'pending', 'granted', 'denied' or 'error'."""
    def stop(self) -> Any:
        """Closes the capture."""

class PlaybackManager:
    def addCategory(self, volume) -> int:
        """Adds a category with a custom volume."""
    def clean(self) -> Any:
        """Cleans all the invalid and finished sound from the playback manager."""
    def getVolume(self, catKey) -> float:
        """Retrieves the volume of a category."""
    def pause(self, catKey) -> bool:
        """Pauses playback of the category."""
    def play(self) -> Handle:
        """Plays a sound through the playback manager and assigns it to a category."""
    def resume(self, catKey) -> bool:
        """Resumes playback of the catgory."""
    def setVolume(self, volume, catKey) -> int:
        """Changes the volume of a category."""
    def stop(self, catKey) -> bool:
        """Stops playback of the category."""

class Sound:
    def ADSR(self, attack, decay, sustain, release) -> Sound:
        """Attack-Decay-Sustain-Release envelopes the volume of a sound. Note: there is currently no way to trigger the release with this API."""
    def accumulate(self, additive=False) -> Sound:
        """Accumulates a sound by summing over positive input differences thus generating a monotonic sigal. If additivity is set to true negative input differences get added too, but positive ones with a factor of two."""
    def addSound(self, sound) -> Any:
        """Adds a new sound to a sound list."""
    def buffer(self, data, rate) -> Sound:
        """Creates a sound from a data buffer."""
    def cache(self) -> Sound:
        """Caches a sound into RAM."""
    def data(self) -> Any:
        """Retrieves the data of the sound as numpy array."""
    def delay(self, time) -> Sound:
        """Delays by playing adding silence in front of the other sound's data."""
    def envelope(self, attack, release, threshold, arthreshold) -> Sound:
        """Delays by playing adding silence in front of the other sound's data."""
    def fadein(self, start, length) -> Sound:
        """Fades a sound in by raising the volume linearly in the given time interval."""
    def fadeout(self, start, length) -> Sound:
        """Fades a sound in by lowering the volume linearly in the given time interval."""
    def file(self, filename) -> Sound:
        """Creates a sound object of a sound file."""
    def filter(self, b, a=1) -> Sound:
        """Filters a sound with the supplied IIR filter coefficients. Without the second parameter you'll get a FIR filter."""
    def highpass(self, frequency, Q=0.5) -> Sound:
        """Creates a second order highpass filter based on the transfer function :math:`H(s) = s^2 / (s^2 + s/Q + 1)`"""
    def join(self, sound) -> Sound:
        """Plays two factories in sequence."""
    length: Any
    """The sample specification of the sound as a tuple with rate and channel count."""
    def limit(self, start, end) -> Sound:
        """Limits a sound within a specific start and end time."""
    def list(self) -> Sound:
        """Creates an empty sound list that can contain several sounds."""
    def loop(self, count) -> Sound:
        """Loops a sound."""
    def lowpass(self, frequency, Q=0.5) -> Sound:
        """Creates a second order lowpass filter based on the transfer    function :math:`H(s) = 1 / (s^2 + s/Q + 1)`"""
    def mix(self, sound) -> Sound:
        """Mixes two factories."""
    def modulate(self, sound) -> Sound:
        """Modulates two factories."""
    def mutable(self) -> Sound:
        """Creates a sound that will be restarted when sought backwards. If the original sound is a sound list, the playing sound can change."""
    def pingpong(self) -> Sound:
        """Plays a sound forward and then backward. This is like joining a sound with its reverse."""
    def pitch(self, factor) -> Sound:
        """Changes the pitch of a sound with a specific factor."""
    def rechannel(self, channels) -> Sound:
        """Rechannels the sound."""
    def resample(self, rate, high_quality) -> Sound:
        """Resamples the sound."""
    def reverse(self) -> Sound:
        """Plays a sound reversed."""
    def sawtooth(self, frequency, rate=48000) -> Sound:
        """Creates a sawtooth sound which plays a sawtooth wave."""
    def silence(self, rate=48000) -> Sound:
        """Creates a silence sound which plays simple silence."""
    def sine(self, frequency, rate=48000) -> Sound:
        """Creates a sine sound which plays a sine wave."""
    specs: Any
    """The sample specification of the sound as a tuple with rate and channel count."""
    def square(self, frequency, rate=48000) -> Sound:
        """Creates a square sound which plays a square wave."""
    def sum(self) -> Sound:
        """Sums the samples of a sound."""
    def threshold(self, threshold=0) -> Sound:
        """Makes a threshold wave out of an audio wave by setting all samples with a amplitude >= threshold to 1, all <= -threshold to -1 and all between to 0."""
    def triangle(self, frequency, rate=48000) -> Sound:
        """Creates a triangle sound which plays a triangle wave."""
    def volume(self, volume) -> Sound:
        """Changes the volume of a sound."""
    def write(self, filename, rate, channels, format, container, codec, bitrate, buffersize) -> Any:
        """Writes the sound to a file."""

class Sequence(Sound):
    def add(self) -> SequenceEntry:
        """Adds a new entry to the sequence."""
    channels: Any
    """The channel count of the sequence."""
    distance_model: Any
    """The distance model of the sequence."""
    doppler_factor: Any
    """The doppler factor of the sequence. This factor is a scaling factor for the velocity vectors in doppler calculation. So a value bigger than 1 will exaggerate the effect as it raises the velocity."""
    fps: Any
    """The listeners's location in 3D space, a 3D tuple of floats."""
    muted: Any
    """Whether the whole sequence is muted."""
    rate: Any
    """The sampling rate of the sequence in Hz."""
    def remove(self) -> Any:
        """Removes an entry from the sequence."""
    def setAnimationData(self) -> Any:
        """Writes animation data to a sequence."""
    speed_of_sound: Any
    """The speed of sound of the sequence. The speed of sound in air is typically 343.3 m/s."""

class SequenceEntry:
    attenuation: Any
    """This factor is used for distance based attenuation of the source."""
    cone_angle_inner: Any
    """The opening angle of the inner cone of the source. If the cone values of a source are set there are two (audible) cones with the apex at the :attr:`location` of the source and with infinite height, heading in the direction of the source's :attr:`orientation`. In the inner cone the volume is normal."""
    cone_angle_outer: Any
    """The opening angle of the outer cone of the source."""
    cone_volume_outer: Any
    """The volume outside the outer cone of the source."""
    distance_maximum: Any
    """The maximum distance of the source. If the listener is further away the source volume will be 0."""
    distance_reference: Any
    """The reference distance of the source. At this distance the volume will be exactly :attr:`volume`."""
    def move(self) -> Any:
        """Moves the entry."""
    muted: Any
    """Whether the entry is muted."""
    relative: Any
    """Whether the source's location, velocity and orientation is relative or absolute to the listener."""
    def setAnimationData(self) -> Any:
        """Writes animation data to a sequenced entry."""
    sound: Any
    """The sound the entry is representing and will be played in the sequence."""
    volume_maximum: Any
    """The maximum volume of the source."""
    volume_minimum: Any
    """The minimum volume of the source."""

class Source:
    azimuth: Any
    """The azimuth angle."""
    distance: Any
    """The distance value. 0 is min, 1 is max."""
    elevation: Any
    """The elevation angle."""

class ThreadPool:
    ...

class error:
    ...

AP_LOCATION: int
AP_ORIENTATION: int
AP_PANNING: int
AP_PITCH: int
AP_VOLUME: int
AUDIO_EFFECT_INVALID: int
AUDIO_EFFECT_REVERB: int
AUDIO_FILTER_BANDPASS: int
AUDIO_FILTER_HIGHPASS: int
AUDIO_FILTER_INVALID: int
AUDIO_FILTER_LOWPASS: int
CHANNELS_INVALID: int
CHANNELS_MONO: int
CHANNELS_STEREO: int
CHANNELS_STEREO_LFE: int
CHANNELS_SURROUND4: int
CHANNELS_SURROUND5: int
CHANNELS_SURROUND51: int
CHANNELS_SURROUND61: int
CHANNELS_SURROUND71: int
CODEC_AAC: int
CODEC_AC3: int
CODEC_FLAC: int
CODEC_INVALID: int
CODEC_MP2: int
CODEC_MP3: int
CODEC_OPUS: int
CODEC_PCM: int
CODEC_VORBIS: int
CONTAINER_AC3: int
CONTAINER_FLAC: int
CONTAINER_INVALID: int
CONTAINER_MATROSKA: int
CONTAINER_MP2: int
CONTAINER_MP3: int
CONTAINER_OGG: int
CONTAINER_WAV: int
DISTANCE_MODEL_EXPONENT: int
DISTANCE_MODEL_EXPONENT_CLAMPED: int
DISTANCE_MODEL_INVALID: int
DISTANCE_MODEL_INVERSE: int
DISTANCE_MODEL_INVERSE_CLAMPED: int
DISTANCE_MODEL_LINEAR: int
DISTANCE_MODEL_LINEAR_CLAMPED: int
FORMAT_FLOAT32: int
FORMAT_FLOAT64: int
FORMAT_INVALID: int
FORMAT_S16: int
FORMAT_S24: int
FORMAT_S32: int
FORMAT_U8: int
RATE_11025: int
RATE_16000: int
RATE_192000: int
RATE_22050: int
RATE_32000: int
RATE_44100: int
RATE_48000: int
RATE_8000: int
RATE_88200: int
RATE_96000: int
RATE_INVALID: int
STATUS_INVALID: int
STATUS_PAUSED: int
STATUS_PLAYING: int
STATUS_STOPPED: int
def duration(sound) -> float:
    """Length in seconds, or -1 if unknown/infinite."""
def edit(sound, start=0.0, end=-1.0, fade_in=0.0, fade_out=0.0, normalize=False) -> Sound:
    """Non-destructive cut, fades and peak normalization (end < 0 = until the end)."""
def peak(sound, max_seconds=600.0) -> float:
    """Largest absolute sample of the sound (0..1 for normal audio)."""
def save_wav(sound, path, max_seconds=600.0) -> Any:
    """Writes the sound as 16-bit PCM WAV (works on the Web too, unlike Sound.write)."""
def voice_fx(sound, preset, amount=1.0) -> Sound:
    """Applies a voice preset: NONE, CHIPMUNK, GIANT, ROBOT, RADIO, ECHO, CAVE, REVERSE. amount goes from 0 (dry) to 1 (full effect). REVERSE needs a recorded sound."""
def voice_presets(live=False) -> list[Any]:
    """Preset names for voice_fx. With live=True, leaves out the ones that need a recorded sound."""
Factory = Sound
