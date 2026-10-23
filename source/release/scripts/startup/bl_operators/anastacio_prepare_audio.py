# SPDX-License-Identifier: GPL-2.0-or-later
"""Prepare immutable Vorbis derivatives and apply them only during desktop export."""
import contextlib
import ctypes
import ctypes.util
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

import aud
import bpy
from bpy.props import CollectionProperty, IntProperty, StringProperty
from bpy.types import Operator, PropertyGroup, UIList

KEY = 'anastacio_audio_v1'
VERSION = 'vorbis-quality-v1'
LONG_SECONDS = 25.0
LARGE_WAV_BYTES = 1024 * 1024


def _hash(path):
    result = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


class _Info(ctypes.Structure):
    _fields_ = [('frames', ctypes.c_longlong), ('samplerate', ctypes.c_int),
                ('channels', ctypes.c_int), ('format', ctypes.c_int),
                ('sections', ctypes.c_int), ('seekable', ctypes.c_int)]


def _library():
    """Use a real Vorbis quality API; aud.write's bitrate is not a quality setting."""
    candidates = [os.environ.get('ANASTACIO_SNDFILE_LIBRARY')]
    roots = [os.path.dirname(bpy.app.binary_path), bpy.utils.resource_path('LOCAL')]
    for root in roots:
        for name in ('libsndfile-1.dll', 'sndfile.dll', 'libsndfile.so.1', 'libsndfile.dylib'):
            candidates.extend([os.path.join(root, name), os.path.join(root, 'lib', name)])
    candidates.append(ctypes.util.find_library('sndfile'))
    errors = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            lib = ctypes.CDLL(candidate)
            lib.sf_open.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(_Info)]
            lib.sf_open.restype = ctypes.c_void_p
            lib.sf_close.argtypes = [ctypes.c_void_p]
            lib.sf_close.restype = ctypes.c_int
            lib.sf_command.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
            lib.sf_command.restype = ctypes.c_int
            lib.sf_writef_float.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_longlong]
            lib.sf_writef_float.restype = ctypes.c_longlong
            lib.sf_strerror.argtypes = [ctypes.c_void_p]
            lib.sf_strerror.restype = ctypes.c_char_p
            lib.sf_format_check.argtypes = [ctypes.POINTER(_Info)]
            lib.sf_format_check.restype = ctypes.c_int
            if os.name == 'nt':
                lib.sf_wchar_open.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.POINTER(_Info)]
                lib.sf_wchar_open.restype = ctypes.c_void_p
            probe = _Info(0, 48000, 1, 0x200000 | 0x0060, 0, 0)
            if lib.sf_format_check(ctypes.byref(probe)):
                return lib
            errors.append('OGG Vorbis is not enabled in ' + candidate)
        except (OSError, AttributeError) as error:
            errors.append(str(error))
    raise RuntimeError('Vorbis quality encoder unavailable. Install libsndfile alongside the engine '
                       'or set ANASTACIO_SNDFILE_LIBRARY. ' + '; '.join(errors))


def _encode(source, target, quality):
    try:
        return _encode_native(source, target, quality)
    except RuntimeError as native_error:
        ffmpeg = os.environ.get('ANASTACIO_FFMPEG') or shutil.which('ffmpeg')
        if not ffmpeg or not os.path.isfile(ffmpeg):
            # The native error lists every library path tried: console only, the report stays short.
            print('Prepare Audio: libsndfile unavailable:', native_error)
            raise RuntimeError('No Vorbis encoder found: pick an installed ffmpeg.exe (with libvorbis) '
                               'in Vorbis Encoder, or set ANASTACIO_FFMPEG')
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        process = subprocess.run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error',
                                  '-y', '-i', source, '-vn', '-c:a', 'libvorbis', '-q:a',
                                  str(quality), target], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, creationflags=flags)
        if process.returncode:
            raise RuntimeError('Vorbis encoder failed: ' + process.stderr.decode('utf8', 'replace'))
        original, decoded = aud.Sound(source), aud.Sound(target)
        if decoded.specs != original.specs or abs(decoded.length - original.length) > 2:
            raise RuntimeError('Vorbis verification changed audio duration or channels')


def _encode_native(source, target, quality):
    """Bound decoded memory with aud.limit; preserve source rate and channel layout."""
    lib = _library()
    sound = aud.Sound(source)
    rate, channels = sound.specs
    frames = sound.length
    if frames <= 0 or rate <= 0 or not 1 <= channels <= 8:
        raise ValueError('Unknown duration or unsupported channel layout')
    info = _Info(0, int(rate), channels, 0x200000 | 0x0060, 0, 0)
    handle = (lib.sf_wchar_open(target, 0x20, ctypes.byref(info)) if os.name == 'nt'
              else lib.sf_open(os.fsencode(target), 0x20, ctypes.byref(info)))
    if not handle:
        raise RuntimeError('Cannot write Vorbis: ' + lib.sf_strerror(None).decode('utf8', 'replace'))
    try:
        value = ctypes.c_double(quality / 10.0)
        if lib.sf_command(handle, 0x1300, ctypes.byref(value), ctypes.sizeof(value)) != 1:
            raise RuntimeError('libsndfile rejected Vorbis quality q%d' % quality)
        offset = 0
        while offset < frames:
            count = min(int(rate) * 4, frames - offset)
            data = sound.limit(offset / rate, (offset + count) / rate).data()
            if not len(data):
                raise RuntimeError('Decoder ended before advertised audio duration')
            data = data.astype('float32', copy=False)
            pointer = data.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            if lib.sf_writef_float(handle, pointer, len(data)) != len(data):
                raise RuntimeError('Vorbis encoder failed while writing samples')
            offset += len(data)
    finally:
        close_error = lib.sf_close(handle)
    if close_error:
        raise RuntimeError('Vorbis encoder failed while finalizing output')
    decoded = aud.Sound(target)
    if decoded.specs != sound.specs or abs(decoded.length - frames) > 2:
        raise RuntimeError('Vorbis verification changed audio duration or channels')


def probe_encoder(directory=None):
    """Exercise actual q5 encoding and the installed engine decoder before preparing."""
    with tempfile.TemporaryDirectory(dir=directory) as folder:
        source, target = os.path.join(folder, 'probe.wav'), os.path.join(folder, 'probe.ogg')
        aud.Sound.sine(440, 48000).limit(0, .1).write(source)
        _encode(source, target, 5)
        data = aud.Sound(target).data()
        if not len(data) or float(abs(data).max()) < .01:
            raise RuntimeError('Vorbis round trip produced empty or silent audio')
    return True


def _targets():
    uses = {}
    for ob in bpy.data.objects:
        for actuator in ob.game.actuators:
            if actuator.type == 'SOUND' and actuator.sound:
                uses.setdefault(actuator.sound.as_pointer(), []).append('Sound actuator: %s/%s' % (ob.name, actuator.name))
        if ob.type == 'SPEAKER' and ob.data.sound:
            uses.setdefault(ob.data.sound.as_pointer(), []).append('Speaker: ' + ob.name)
    for sound in bpy.data.sounds:
        yield ('SOUND:' + sound.name + ('@' + sound.library.filepath if sound.library else ''), 'SOUND', sound, uses.get(sound.as_pointer(), ['Sound datablock']))
    for world in bpy.data.worlds:
        for mi, module in enumerate(world.sound_modules):
            for si, entry in enumerate(module.sounds):
                if entry.filepath:
                    yield ('WORLD:%s:%d:%d' % (world.name, mi, si) +
                           ('@' + world.library.filepath if world.library else ''), 'WORLD',
                           entry, ['World %s: %s/%s/%s' % (module.type, world.name, module.name, entry.name)])


def _source(target, kind):
    if kind == 'SOUND' and target.packed_file:
        data = bytes(target.packed_file.data)
        return hashlib.sha256(data).hexdigest(), len(data), None, data
    library = target.library if kind == 'SOUND' else target.id_data.library
    path = os.path.realpath(bpy.path.abspath(target.filepath, library=library))
    return _hash(path), os.path.getsize(path), path, None


def inventory(cache_dir=None):
    """Return JSON-compatible records, including unsupported/missing sound diagnostics."""
    result = []
    for identity, kind, target, uses in _targets():
        row = dict(id=identity, kind=kind, name=target.name, path=target.filepath,
                   size=0, duration=None, usage=uses, action='KEEP', quality=4, stream=False)
        result.append(row)
        try:
            digest, size, path, packed = _source(target, kind)
            row.update(source_hash=digest, size=size, source_path=path)
            if packed is not None:
                with tempfile.TemporaryDirectory(dir=cache_dir) as folder:
                    temp = os.path.join(folder, 'source' + os.path.splitext(target.filepath)[1])
                    with open(temp, 'wb') as stream:
                        stream.write(packed)
                    sound = aud.Sound(temp)
                    rate, channels = sound.specs
                    frames = sound.length
            else:
                sound = aud.Sound(path)
                rate, channels = sound.specs
                frames = sound.length
            if frames <= 0 or rate <= 0:
                raise ValueError('Unknown or empty duration')
            duration = frames / rate
            row.update(duration=duration, rate=rate, channels=channels, stream=duration > LONG_SECONDS)
            row['quality'] = 5 if any('World MUSIC:' in use for use in uses) else 4
            # Unclassified long audio defaults to music quality rather than losing detail.
            if row['stream'] and kind == 'SOUND':
                row['quality'] = 5
            if row['stream'] or (os.path.splitext(target.filepath)[1].lower() == '.wav' and size >= LARGE_WAV_BYTES):
                row['action'] = 'CONVERT' if os.path.splitext(target.filepath)[1].lower() not in {'.ogg', '.oga'} else 'CACHE_POLICY'
            else:
                row['action'] = 'CACHE_POLICY'
            if (target.library if kind == 'SOUND' else target.id_data.library):
                row.update(action='KEEP', reason='Linked library: prepare the exported library copy')
        except (OSError, ValueError, RuntimeError, aud.error) as error:
            row.update(action='KEEP', reason=str(error))
    return result


def _cache_dir():
    if not bpy.data.filepath:
        raise ValueError('Save the project before preparing audio')
    return os.path.join(os.path.dirname(bpy.data.filepath), '.anastacio_cache', 'audio')


def configured_encoder():
    """Remember a user-selected encoder so export subprocesses can prepare libraries."""
    scenes = [bpy.context.scene] + [scene for scene in bpy.data.scenes
                                    if scene != bpy.context.scene]
    for scene in scenes:
        try:
            saved = json.loads(scene.get(KEY, '{}')).get('encoder_path', '')
        except (ValueError, TypeError):
            saved = ''
        if saved:
            return saved
    return os.environ.get('ANASTACIO_FFMPEG', '') or shutil.which('ffmpeg') or ''


@contextlib.contextmanager
def _encoder_environment(path):
    previous = os.environ.get('ANASTACIO_FFMPEG')
    try:
        if path:
            os.environ['ANASTACIO_FFMPEG'] = bpy.path.abspath(path)
        yield
    finally:
        if previous is None:
            os.environ.pop('ANASTACIO_FFMPEG', None)
        else:
            os.environ['ANASTACIO_FFMPEG'] = previous


def prepare_audio(cache_dir=None, encoder_path=None):
    path = configured_encoder() if encoder_path is None else encoder_path
    with _encoder_environment(path):
        report = _prepare_audio(cache_dir)
    if path:
        report['encoder_path'] = bpy.path.abspath(path)
        bpy.context.scene[KEY] = json.dumps(report, sort_keys=True)
    return report


def _prepare_audio(cache_dir=None):
    """Store preparation metadata only; never modify source files, paths or cache flags."""
    cache_dir = cache_dir or _cache_dir()
    os.makedirs(cache_dir, exist_ok=True)
    rows = inventory(cache_dir)
    # The encoder is needed only when something is converted.
    if any(row['action'] == 'CONVERT' for row in rows):
        probe_encoder()
    try:
        previous = json.loads(bpy.context.scene.get(KEY, '{}'))
    except (ValueError, TypeError):
        previous = {}
    verified = {row['prepared_path']: row.get('prepared_hash')
                for row in previous.get('entries', []) if row.get('prepared_path')}
    qualities = {}
    for row in rows:
        if row['action'] == 'CONVERT':
            digest = row['source_hash']
            qualities[digest] = max(qualities.get(digest, 0), row['quality'])
    for row in rows:
        if row['action'] == 'CONVERT':
            row['quality'] = qualities[row['source_hash']]
    targets = {identity: (kind, target) for identity, kind, target, uses in _targets()}
    for row in rows:
        if row['action'] == 'KEEP':
            continue
        if row['action'] == 'CONVERT':
            signature = hashlib.sha256(('%s:%s:q%d' % (VERSION, row['source_hash'], row['quality'])).encode('ascii')).hexdigest()[:24]
            path = os.path.join(cache_dir, signature + '.ogg')
            kind, target = targets[row['id']]
            if not (os.path.isfile(path) and verified.get(path) == _hash(path)):
                with tempfile.TemporaryDirectory(dir=cache_dir) as folder:
                    source = row['source_path']
                    if source is None:
                        source = os.path.join(folder, 'source' + os.path.splitext(target.filepath)[1])
                        with open(source, 'wb') as stream:
                            stream.write(bytes(target.packed_file.data))
                    partial = os.path.join(folder, 'encoded.ogg')
                    if _hash(source) != row['source_hash']:
                        raise ValueError('Audio source changed during preparation: ' + row['name'])
                    _encode(source, partial, row['quality'])
                    if _hash(source) != row['source_hash']:
                        raise ValueError('Audio source changed during preparation: ' + row['name'])
                    os.replace(partial, path)
            verified[path] = _hash(path)
            row.update(prepared_path=path, prepared_hash=_hash(path), prepared_size=os.path.getsize(path))
        else:
            row['prepared_size'] = row['size']
    report = dict(version=VERSION, entries=rows,
                  prepared=sum(row['action'] != 'KEEP' for row in rows),
                  skipped=sum(row['action'] == 'KEEP' for row in rows),
                  bytes_before=sum(row['size'] for row in rows),
                  bytes_after=sum(row.get('prepared_size', row['size']) for row in rows))
    bpy.context.scene[KEY] = json.dumps(report, sort_keys=True)
    return report


def prepared_entries():
    report = json.loads(bpy.context.scene.get(KEY, '{}'))
    if report and report.get('version') != VERSION:
        raise ValueError('Prepared audio metadata version changed; prepare audio again')
    targets = {identity: (kind, target, uses) for identity, kind, target, uses in _targets()}
    rows = []
    for row in report.get('entries', []):
        if row['action'] == 'KEEP':
            continue
        if row['id'] not in targets:
            raise ValueError('Prepared audio target is missing: ' + row['id'])
        kind, target, uses = targets[row['id']]
        if uses != row['usage']:
            raise ValueError('Prepared audio usage changed: ' + row['name'])
        if _source(target, kind)[0] != row['source_hash']:
            raise ValueError('Prepared audio source changed: ' + row['name'])
        if row.get('prepared_path') and _hash(row['prepared_path']) != row['prepared_hash']:
            raise ValueError('Prepared audio cache changed: ' + row['name'])
        rows.append(row)
    return rows


@contextlib.contextmanager
def export_prepared_audio():
    """Swap Sound users to temporary packed copies; restore all authoring state on exit."""
    rows = prepared_entries()
    targets = {identity: (kind, target) for identity, kind, target, uses in _targets()}
    swaps, worlds, speakers = [], [], []
    mapping = dict(sound_paths={}, world_paths={}, files=[], applied=0)
    try:
        for row in rows:
            kind, original = targets[row['id']]
            path = row.get('prepared_path')
            if kind == 'WORLD':
                if path:
                    worlds.append((original, original.filepath))
                    original.filepath = path
                    mapping['world_paths'][row['source_path']] = path
                    mapping['files'].append(path)
                mapping['applied'] += 1
                continue
            # Loading a fresh Sound never inherits packed bytes from the authoring WAV.
            sound = bpy.data.sounds.load(path or row['source_path']) if (path or row['source_path']) else original.copy()
            name, fake = original.name, original.use_fake_user
            swaps.append((original, sound, name, fake))
            sound.use_mono = original.use_mono
            sound.use_memory_cache = not row['stream']
            sound.use_fake_user = fake
            if path:
                sound.pack()
                mapping['files'].append(path)
                if row['source_path']:
                    mapping['sound_paths'][row['source_path']] = path
            original.use_fake_user = False
            original.name = '__anastacio_audio_source__'
            sound.name = name
            original.user_remap(sound)
            mapping['applied'] += 1
            for speaker in bpy.data.speakers:
                if speaker.sound == sound:
                    speakers.append((speaker, speaker.cache))
                    speaker.cache = not row['stream']
        yield mapping
    finally:
        for speaker, cache in reversed(speakers):
            speaker.cache = cache
        for entry, path in reversed(worlds):
            entry.filepath = path
        for original, sound, name, fake in reversed(swaps):
            sound.user_remap(original)
            sound.name = '__anastacio_audio_export__'
            original.name = name
            original.use_fake_user = fake
            bpy.data.sounds.remove(sound)


class AnastacioAudioEntry(PropertyGroup):
    name: StringProperty()
    size: StringProperty()
    duration: StringProperty()
    action: StringProperty()
    usage: StringProperty()
    reason: StringProperty()
    path: StringProperty()
    cache_policy: StringProperty()


class ANASTACIO_UL_prepared_audio(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.name, icon='ERROR' if item.reason else 'SOUND')
        row.label(text=item.size)
        row.label(text=item.duration)
        row.label(text=item.action)


class GAME_OT_prepare_audio(Operator):
    bl_idname = 'game.prepare_audio'
    bl_label = 'Prepare Audio'
    bl_description = 'Prepare Vorbis audio and streaming for desktop export without changing the originals'
    bl_options = {'REGISTER', 'UNDO'}

    entries: CollectionProperty(type=AnastacioAudioEntry, options={'SKIP_SAVE'})
    active_index: IntProperty(default=0, options={'SKIP_SAVE'})
    ffmpeg_path: StringProperty(
        name='Vorbis Encoder', subtype='FILE_PATH', options={'SKIP_SAVE'},
        description='Optional installed FFmpeg executable with libvorbis; used when libsndfile cannot encode Vorbis')

    def invoke(self, context, event):
        self.ffmpeg_path = self.ffmpeg_path or configured_encoder()
        self.entries.clear()
        for row in inventory():
            item = self.entries.add()
            item.name = row['name']
            item.size = '%.2f MiB' % (row['size'] / 1048576)
            item.duration = ('%.1f s' % row['duration']) if row['duration'] is not None else 'Unknown'
            item.action = ('OGG q%d' % row['quality'] if row['action'] == 'CONVERT'
                           else 'Skip' if row['action'] == 'KEEP' else 'Cache policy')
            item.usage = '; '.join(row['usage'])
            item.reason = row.get('reason', '')
            item.path = row['path']
            item.cache_policy = ('Stream' if row['stream'] else 'Decoded in memory') if row['kind'] == 'SOUND' else 'World Sound streams from file'
        return context.window_manager.invoke_props_dialog(self, width=760)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text='Sounds')
        box.label(text='Audio originals stay unchanged; prepared files are used during desktop export.', icon='INFO')
        box.template_list('ANASTACIO_UL_prepared_audio', '', self, 'entries',
                          self, 'active_index', rows=6)
        if self.entries:
            item = self.entries[min(self.active_index, len(self.entries) - 1)]
            box = layout.box()
            box.label(text='Selected Sound')
            box.label(text=item.path, icon='FILE_SOUND')
            box.label(text=item.usage)
            box.label(text=item.cache_policy)
            if item.reason:
                box.label(text=item.reason, icon='ERROR')
        box = layout.box()
        box.label(text='Encoder')
        box.prop(self, 'ffmpeg_path')
        box.label(text='An installed Vorbis encoder is required. Short sounds keep their original format.')

    def execute(self, context):
        try:
            report = prepare_audio(encoder_path=self.ffmpeg_path or None)
        except (OSError, ValueError, RuntimeError, aud.error) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Prepared %d sounds; %d skipped; audio %.2f to %.2f MiB' %
                    (report['prepared'], report['skipped'], report['bytes_before'] / 1048576,
                     report['bytes_after'] / 1048576))
        return {'FINISHED'}


classes = (AnastacioAudioEntry, ANASTACIO_UL_prepared_audio, GAME_OT_prepare_audio)
