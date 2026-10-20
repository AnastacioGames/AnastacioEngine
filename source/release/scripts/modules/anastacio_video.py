# -*- coding: utf-8 -*-
"""Video Player: video on an object's material or as a fullscreen cutscene, with the video's own sound.

Configured by the Video Player panel (Object tab). From a script:

    vp = obj.components["VideoPlayer"]
    vp.play(); vp.pause(); vp.stop(); vp.seek(5.0)
    vp.playing, vp.time, vp.duration, vp.finished
    vp.on_finished = callback   # called with the component when a non looping video ends

From Logic Bricks, with a Message actuator (To empty = every Video Player, or the object's name):

    video_play, video_pause, video_toggle, video_stop, video_restart
    video_seek  body "5" jumps to 5 s, "+2" / "-2" moves from the current time

A video that ends (not looping) sends video_finished, with the object's name as body.

Subtitles: a .srt file (the Subtitles field, or one with the video's name next to it) is drawn
at the bottom of the screen in sync with the video.
"""
from collections import OrderedDict
import os
import re

import Range
from Range import logic, texture

RUNTIME_VERSION = (0, 1, 0)
# Folder next to the exported game where the export copies the videos.
EXPORT_FOLDER = "videos"
# Filter pass of the fullscreen video: after the user's own passes.
FULLSCREEN_PASS = 120
# Subjects the player answers to (Message actuator) and the one it sends at the end.
MESSAGE_PREFIX = "video_"
FINISHED_SUBJECT = "video_finished"
# Audio is moved back onto the video clock when they drift further apart than this (seconds).
AUDIO_DRIFT = 0.08

FULLSCREEN_SHADER = """
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D video_tex;
uniform float bgl_RenderedTextureWidth;
uniform float bgl_RenderedTextureHeight;
uniform float video_aspect;
uniform float video_fill;
uniform float video_alpha;

void main()
{
	vec2 uv = gl_TexCoord[0].st;
	vec4 scene = texture2D(bgl_RenderedTexture, uv);
	float screen_aspect = bgl_RenderedTextureWidth / max(bgl_RenderedTextureHeight, 1.0);
	// scale of the video rectangle on screen: Fit keeps it inside (black bars), Fill covers it (crop)
	vec2 scale = vec2(1.0);
	float ratio = video_aspect / screen_aspect;
	if ((ratio > 1.0) == (video_fill < 0.5)) {
		scale.y = 1.0 / ratio;
	}
	else {
		scale.x = ratio;
	}
	vec2 vuv = (uv - 0.5) / scale + 0.5;
	vec4 video = vec4(0.0, 0.0, 0.0, 1.0);
	if (all(greaterThanEqual(vuv, vec2(0.0))) && all(lessThanEqual(vuv, vec2(1.0)))) {
		video = vec4(texture2D(video_tex, vuv).rgb, 1.0);
	}
	gl_FragColor = mix(scene, video, video_alpha);
}
"""


SRT_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
SRT_COLOR = re.compile(r'<font\s+color\s*=\s*"?#?([0-9a-fA-F]{6})"?', re.I)
SRT_TAG = re.compile(r"<[^>]*>|\{\\[^}]*\}")


def subtitle_path(video_path, subtitles=""):
    """The .srt of a video: the given file, else one with the video's name next to it."""
    if subtitles:
        return resolve_path(subtitles)
    path = os.path.splitext(video_path)[0] + ".srt"
    return path if os.path.isfile(path) else ""


def load_srt(path):
    """[(start, end, [lines])] of a .srt file, in seconds."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(path, encoding=encoding) as handle:
                text = handle.read()
            break
        except UnicodeDecodeError:
            continue
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        lines = block.strip().split("\n")
        for i, line in enumerate(lines):
            match = SRT_TIME.search(line)
            if match:
                g = [int(v) for v in match.groups()]
                start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
                end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
                raw = [l for l in lines[i + 1:] if l.strip()]
                body = [SRT_TAG.sub("", l).strip() for l in raw]
                # <font color="#RRGGBB"> paints the line, {n8} puts the subtitle at the top
                colors = []
                for l in raw:
                    c = SRT_COLOR.search(l)
                    colors.append(tuple(int(c.group(1)[k:k + 2], 16) / 255.0 for k in (0, 2, 4)) if c
                                  else (1.0, 1.0, 1.0))
                top = any("{\\an8}" in l for l in raw)
                keep = [k for k, l in enumerate(body) if l]
                if keep:
                    cues.append((start, end, [body[k] for k in keep], [colors[k] for k in keep], top))
                break
    cues.sort(key=lambda cue: cue[0])
    return cues


def resolve_path(path):
    """Absolute path of a video: as written, else in the videos folder the export fills."""
    full = logic.expandPath(path) if path else ""
    if full and os.path.isfile(full):
        return full
    exported = logic.expandPath("//" + EXPORT_FOLDER + "/" + os.path.basename(path.replace("\\", "/")))
    if os.path.isfile(exported):
        return exported
    return full


class VideoPlayer(Range.types.KX_PythonComponent):
    args = OrderedDict([
        ("File", ""),
        ("Fullscreen", False),
        ("Material", ""),
        ("Autoplay", True),
        ("Loop", False),
        ("Speed", 1.0),
        ("Play Sound", True),
        ("Volume", 1.0),
        ("3D Sound", False),
        ("Skippable", True),
        ("Skip Key", "ESCKEY"),
        ("Pause Scene", False),
        ("Fill Screen", False),
        ("Fade", 0.5),
        ("Subtitles", ""),
        ("Subtitle Size", 1.0),
    ])
    anastacio_video = True
    runtime_version = RUNTIME_VERSION

    # Editor side (Smart Component): the Game Components box draws the same UI
    # as the Object > Video Player panel. Never runs in the game.
    class Editor:
        fields = False

        def draw_ui(self, layout, obj, comp):
            from bl_ui.properties_video_player import draw_video_player
            draw_video_player(layout, obj, comp)

    def start(self, args):
        self.on_finished = None
        self.error = ""
        self.finished = False
        self._video = None
        self._tex = None
        self._filter = None
        self._gltex = None
        self._size = None
        self._uploaded = None
        self._sound = None
        self._handle = None
        self._playing = False
        self._time_scale = None
        self._seeked = False
        self._alpha = 0.0
        self._fade_dir = 0
        self._fade_clock = None
        self._cues = []
        self._draw_registered = False

        self.fullscreen = bool(args.get("Fullscreen", False))
        self.loop = bool(args.get("Loop", False))
        self.speed = max(0.01, float(args.get("Speed", 1.0)))
        self.volume = max(0.0, float(args.get("Volume", 1.0)))
        self.sound_3d = bool(args.get("3D Sound", False)) and not self.fullscreen
        self.skippable = bool(args.get("Skippable", True))
        self.pause_scene = bool(args.get("Pause Scene", False))
        self.fill_screen = bool(args.get("Fill Screen", False))
        self.fade = max(0.0, float(args.get("Fade", 0.5)))
        self.skip_key = getattr(Range.events, str(args.get("Skip Key", "ESCKEY")).upper(), Range.events.ESCKEY)
        self.path = resolve_path(args.get("File", ""))
        try:
            if not os.path.isfile(self.path):
                raise FileNotFoundError("Video Player: file not found: %r" % args.get("File", ""))
            self._video = texture.VideoFFmpeg(self.path)
            self._video.repeat = -1 if self.loop else 0
            self._video.framerate = self.speed
            if not self.fullscreen:
                self._tex = texture.Texture(self.object, self._material_id(args.get("Material", "")))
                self._tex.source = self._video
            if args.get("Play Sound", True):
                self._open_sound()
            # Decode the first frame now, while the scene loads, so play() does not hitch.
            self._video.play()
            self._update_image()
            if self.fullscreen:
                self._ensure_filter()
            subs = subtitle_path(self.path, args.get("Subtitles", ""))
            if subs:
                if not os.path.isfile(subs):
                    print("Video Player: subtitles not found: %r" % args.get("Subtitles", ""))
                else:
                    self._cues = load_srt(subs)
                    self.subtitle_size = max(0.1, float(args.get("Subtitle Size", 1.0)))
                    self.object.scene.post_draw.append(self._draw_subtitles)
                    self._draw_registered = True
            if args.get("Autoplay", True):
                self._start_playing()
            else:
                self._video.pause()
        except Exception as exc:
            self.error = str(exc)
            print(self.error)

    # ---------------------------------------------------------------- API

    @property
    def playing(self):
        return self._playing

    @property
    def duration(self):
        return self._video.range[1] if self._video else 0.0

    @property
    def time(self):
        return max(0.0, self._video.time) if self._video else 0.0

    def play(self):
        if self._video is None or self._playing:
            return
        if self.finished:
            self.seek(0.0)
        self._video.play()
        self._start_playing()

    def pause(self):
        if not self._playing:
            return
        self._video.pause()
        self._playing = False
        if self._handle:
            self._handle.pause()
        self._restore_scene()

    def stop(self):
        """Stop and go back to the start; a fullscreen video is hidden."""
        if self._video is None:
            return
        self.pause()
        self.seek(0.0)
        self._hide()

    def seek(self, seconds):
        if self._video is None:
            return
        self.finished = False
        self._video.seek(float(seconds))
        # paused: VideoFFmpeg decoded the target, update() uploads it once
        self._seeked = not self._playing
        if self._handle:
            self._handle.position = float(seconds)

    # ------------------------------------------------------------ internal

    def _material_id(self, name):
        if name:
            for prefix in ("MA", ""):
                mat_id = texture.materialID(self.object, prefix + name)
                if mat_id >= 0:
                    return mat_id
            raise ValueError("Video Player: material %r not found on %s" % (name, self.object.name))
        return 0

    def _open_sound(self):
        try:
            import aud
            self._sound = aud.Sound.file(self.path)
        except Exception as exc:
            # no audio track, or a format audaspace cannot read: play silent
            print("Video Player: no sound in %r (%s)" % (self.path, exc))
            self._sound = None

    def _play_sound(self, position):
        if self._sound is None:
            return
        import aud
        try:
            if self._handle is None or self._handle.status == aud.STATUS_INVALID:
                self._handle = aud.Device().play(self._sound)
                self._handle.volume = self.volume
                self._handle.pitch = self.speed
                if self.sound_3d:
                    self._handle.relative = False
                    self._handle.location = self.object.worldPosition
            else:
                self._handle.resume()
            self._handle.position = position
        except aud.error as exc:
            # no audio device (server, muted system): the video plays on without sound
            print("Video Player: sound disabled (%s)" % exc)
            self._sound = None
            self._handle = None

    def _start_playing(self):
        self._playing = True
        self.finished = False
        if self.fullscreen:
            self._ensure_filter()
            self._set_fade(1)
            if self.pause_scene and self._time_scale is None:
                self._time_scale = logic.getTimeScale()
                logic.setTimeScale(0.0)
        self._play_sound(self.time)

    def _restore_scene(self):
        if self._time_scale is not None:
            logic.setTimeScale(self._time_scale)
            self._time_scale = None

    def _hide(self):
        if self._filter is not None:
            self._set_fade(-1)

    def _set_fade(self, direction):
        """Fade the fullscreen video in (1) or out (-1); without Fade it switches at once."""
        if self.fade <= 0.0:
            self._alpha = 1.0 if direction > 0 else 0.0
            self._fade_dir = 0
            self._filter.setUniform("video_alpha", self._alpha)
            return
        self._fade_dir = direction
        self._fade_clock = None

    def _step_fade(self):
        # real time: Pause Scene stops the game clock while the cutscene plays
        import time
        now = time.perf_counter()
        last, self._fade_clock = self._fade_clock, now
        if last is None:
            return
        self._alpha = min(1.0, max(0.0, self._alpha + self._fade_dir * (now - last) / self.fade))
        self._filter.setUniform("video_alpha", self._alpha)
        if self._alpha in (0.0, 1.0):
            self._fade_dir = 0

    def _ensure_filter(self):
        if self._filter is not None:
            return
        manager = self.object.scene.filterManager
        if manager.getFilter(FULLSCREEN_PASS) is not None:
            manager.removeFilter(FULLSCREEN_PASS)
        self._filter = manager.addFilter(FULLSCREEN_PASS, logic.RAS_2DFILTER_CUSTOMFILTER, FULLSCREEN_SHADER)
        if self._gltex is not None:
            self._filter.setTexture(0, self._gltex, "video_tex")
        if self._size:
            self._filter.setUniform("video_aspect", self._size[0] / max(self._size[1], 1))
        self._filter.setUniform("video_fill", 1.0 if self.fill_screen else 0.0)
        self._filter.setUniform("video_alpha", 0.0)

    def _update_image(self):
        if self._tex is not None:
            self._tex.refresh(True)
            return
        # fullscreen: own GL texture, filled from the video image (a bgl.Buffer) when the frame changes
        import bgl
        image = self._video.image
        shown = self._video.time
        self._video.refresh()
        if image is None or not len(image) or shown == self._uploaded:
            return
        self._uploaded = shown
        if self._gltex is None:
            self._size = tuple(self._video.size)
            ids = bgl.Buffer(bgl.GL_INT, 1)
            bgl.glGenTextures(1, ids)
            self._gltex = ids[0]
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, self._gltex)
            bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
            bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
            bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_S, bgl.GL_CLAMP_TO_EDGE)
            bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_T, bgl.GL_CLAMP_TO_EDGE)
            bgl.glTexImage2D(bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA8, self._size[0], self._size[1], 0,
                             bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, image)
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)
            if self._filter is not None:
                self._filter.setTexture(0, self._gltex, "video_tex")
                self._filter.setUniform("video_aspect", self._size[0] / max(self._size[1], 1))
            return
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, self._gltex)
        bgl.glTexSubImage2D(bgl.GL_TEXTURE_2D, 0, 0, 0, self._size[0], self._size[1],
                            bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, image)
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)

    def _finish(self):
        self._playing = False
        self.finished = True
        if self._handle:
            self._handle.stop()
            self._handle = None
        self._restore_scene()
        if self.fullscreen:
            self._hide()
        logic.sendMessage(FINISHED_SUBJECT, self.object.name, "", self.object)
        if self.on_finished:
            self.on_finished(self)

    def _read_messages(self):
        for subject, body in logic.getMessages(self.object.name):
            if not subject.startswith(MESSAGE_PREFIX) or subject == FINISHED_SUBJECT:
                continue
            command = subject[len(MESSAGE_PREFIX):]
            if command == "play":
                self.play()
            elif command == "pause":
                self.pause()
            elif command == "toggle":
                self.pause() if self._playing else self.play()
            elif command == "stop":
                self.stop()
            elif command == "restart":
                self.seek(0.0)
                self.play()
            elif command == "seek":
                text = body.strip()
                try:
                    value = float(text)
                except ValueError:
                    print("Video Player: video_seek needs seconds in the body, got %r" % body)
                    continue
                if text[:1] in "+-":
                    value += self.time
                self.seek(min(max(0.0, value), self.duration or value))

    def update(self):
        if self._video is None:
            return
        self._read_messages()
        if self._fade_dir and self._filter is not None:
            self._step_fade()
        if not self._playing:
            if self._seeked:
                self._seeked = False
                self._update_image()
            return
        if self.fullscreen and self.skippable and logic.keyboard.inputs[self.skip_key].activated:
            self._video.pause()
            self._finish()
            return
        self._update_image()
        # status 3 without pause(): the video reached its end (looping videos never do)
        if self._video.status == 3:
            self._finish()
            return
        if self._handle is not None:
            import aud
            target = self.time
            try:
                if self._handle.status == aud.STATUS_INVALID:
                    # sound ended before a looping video came back to its start
                    if target < AUDIO_DRIFT:
                        self._handle = None
                        self._play_sound(target)
                elif abs(self._handle.position - target) > AUDIO_DRIFT:
                    self._handle.position = target
                if self.sound_3d and self._handle is not None:
                    self._handle.location = self.object.worldPosition
            except aud.error:
                self._handle = None

    @property
    def subtitle(self):
        """Lines of the subtitle shown now, [] when none."""
        cue = self._cue_now()
        return cue[2] if cue else []

    def _cue_now(self):
        t = self.time
        for cue in self._cues:
            if cue[0] > t:
                break
            if t < cue[1]:
                return cue
        return None

    def _draw_subtitles(self, *args):
        if not (self._playing or self._seeked or (self.fullscreen and self._alpha > 0.0)):
            return
        if self.fullscreen and self._alpha <= 0.0:
            return
        cue = self._cue_now()
        if cue is None:
            return
        lines, colors, top = cue[2], cue[3], cue[4]
        import bgl
        import blf
        width = Range.render.getWindowWidth()
        height = Range.render.getWindowHeight()
        size = max(8, int(height * 0.045 * self.subtitle_size))
        alpha = self._alpha if self.fullscreen else 1.0
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glPushMatrix()
        bgl.glLoadIdentity()
        bgl.glOrtho(0, width, 0, height, -1, 1)
        bgl.glMatrixMode(bgl.GL_MODELVIEW)
        bgl.glPushMatrix()
        bgl.glLoadIdentity()
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        bgl.glEnable(bgl.GL_BLEND)
        font = 0
        blf.size(font, size, 72)
        shadow = max(1, size // 14)
        step = size * 1.25
        y = height * 0.94 - size - step * (len(lines) - 1) if top else height * 0.06
        for line, color in zip(reversed(lines), reversed(colors)):
            x = (width - blf.dimensions(font, line)[0]) / 2
            bgl.glColor4f(0.0, 0.0, 0.0, 0.85 * alpha)
            for dx, dy in ((shadow, -shadow), (-shadow, -shadow), (shadow, shadow), (-shadow, shadow)):
                blf.position(font, x + dx, y + dy, 0)
                blf.draw(font, line)
            bgl.glColor4f(color[0], color[1], color[2], alpha)
            blf.position(font, x, y, 0)
            blf.draw(font, line)
            y += step
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glPopMatrix()
        bgl.glMatrixMode(bgl.GL_MODELVIEW)
        bgl.glPopMatrix()

    def dispose(self):
        if not hasattr(self, "_handle"):  # the game ended before start()
            return
        if self._draw_registered:
            try:
                self.object.scene.post_draw.remove(self._draw_subtitles)
            except (ValueError, SystemError):
                pass
        if self._handle:
            self._handle.stop()
        self._restore_scene()
        if self._filter is not None:
            try:
                self.object.scene.filterManager.removeFilter(FULLSCREEN_PASS)
            except Exception:
                pass
