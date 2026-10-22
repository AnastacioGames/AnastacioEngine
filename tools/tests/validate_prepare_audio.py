"""Run with AnastacioEngine -b --factory-startup --python this.py -- REPO OUTPUT."""
import importlib.util
import json
import os
import shutil
import sys

import aud
import bpy

args = sys.argv[sys.argv.index('--') + 1:]
repo, output = args[:2]
os.makedirs(output, exist_ok=True)
spec = importlib.util.spec_from_file_location('prepare_audio_test', os.path.join(
    repo, 'source/release/scripts/startup/bl_operators/anastacio_prepare_audio.py'))
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)
assert audio.probe_encoder(output)
for cls in audio.classes:
    if not hasattr(bpy.types, cls.__name__):
        bpy.utils.register_class(cls)
assert 'ffmpeg_path' in bpy.ops.game.prepare_audio.get_rna_type().properties

bpy.context.scene.render.engine = 'BLENDER_GAME'
source = os.path.join(output, 'music.wav')
short_path = os.path.join(output, 'effect.wav')
aud.Sound.sine(440, 48000).limit(0, 26).write(source)
aud.Sound.sine(880, 48000).limit(0, .1).write(short_path)
sound = bpy.data.sounds.load(source)
sound.name = 'LongMusic'
sound.pack()
sound.use_memory_cache = True
short = bpy.data.sounds.load(short_path)
short.name = 'ShortEffect'
short.use_memory_cache = False
short.pack()
cube = bpy.data.objects['Cube']
bpy.ops.logic.actuator_add(type='SOUND', name='ShortSound', object=cube.name)
actuator = cube.game.actuators['ShortSound']
actuator.sound = short
speaker = bpy.data.speakers.new('MusicSpeaker')
speaker.sound = sound
speaker.cache = True
obj = bpy.data.objects.new('MusicSpeaker', speaker)
bpy.context.scene.objects.link(obj)
world = bpy.data.worlds.new('AudioWorld')
bpy.context.scene.world = world
music = world.sound_modules.new('Music', type='MUSIC')
entry = music.sounds.new('Theme', filepath=source)
ambient = world.sound_modules.new('Ambient', type='AMBIENT')
ambient_path = os.path.join(output, 'ambient.wav')
aud.Sound.sine(220, 48000).limit(0, 26).write(ambient_path)
ambient.sounds.new('Wind', filepath=ambient_path)
effects = world.sound_modules.new('Effects', type='EFFECTS')
world_short = os.path.join(output, 'world-effect.wav')
shutil.copyfile(short_path, world_short)
effects.sounds.new('Hit', filepath=world_short)
missing = effects.sounds.new('Missing', filepath=os.path.join(output, 'missing.wav'))
original_hash = audio._hash(source)
packed = bytes(sound.packed_file.data)
encoder = os.environ.pop('ANASTACIO_FFMPEG', None)
selected_encoder = encoder or audio.configured_encoder() or None
try:
    report = audio.prepare_audio(os.path.join(output, 'cache'), encoder_path=selected_encoder)
    assert os.environ.get('ANASTACIO_FFMPEG') is None
    if selected_encoder:
        assert report['encoder_path'] == selected_encoder
    # A later export preparation resolves the stored encoder, without a persistent env change.
    report = audio.prepare_audio(os.path.join(output, 'cache'))
    assert os.environ.get('ANASTACIO_FFMPEG') is None
finally:
    if encoder is not None:
        os.environ['ANASTACIO_FFMPEG'] = encoder
rows = {row['id']: row for row in report['entries']}
assert rows['SOUND:LongMusic']['stream']
assert rows['SOUND:LongMusic']['quality'] == 5
assert rows['SOUND:ShortEffect']['action'] == 'CACHE_POLICY'
assert any('Sound actuator: Cube/ShortSound' == use for use in rows['SOUND:ShortEffect']['usage'])
assert any(row['quality'] == 4 and 'World AMBIENT:' in row['usage'][0] for row in report['entries'])
assert any(row['action'] == 'KEEP' and row['name'] == 'Missing' for row in report['entries'])
assert report['bytes_after'] < report['bytes_before']
assert sound.filepath == source and sound.use_memory_cache
assert bytes(sound.packed_file.data) == packed
assert entry.filepath == source and speaker.cache and not short.use_memory_cache
# Packed source remains usable without its external authoring file.
os.replace(short_path, short_path + '.hidden')

for fail in (False, True):
    try:
        with audio.export_prepared_audio() as mapping:
            assert mapping['applied'] >= 5
            transformed = speaker.sound
            assert transformed != sound and transformed.packed_file
            assert bytes(transformed.packed_file.data)[:4] == b'OggS'
            assert not transformed.use_memory_cache and not speaker.cache
            assert entry.filepath.endswith('.ogg')
            assert bpy.data.sounds['ShortEffect'].use_memory_cache
            assert actuator.sound == bpy.data.sounds['ShortEffect']
            assert actuator.sound.packed_file
            data = aud.Sound(entry.filepath).limit(0, .1).data()
            assert len(data) and float(abs(data).max()) > .1
            if fail:
                raise RuntimeError('injected export failure')
    except RuntimeError as error:
        assert fail and str(error) == 'injected export failure', str(error)
    assert speaker.sound == sound and speaker.cache
    assert sound.name == 'LongMusic' and short.name == 'ShortEffect'
    assert sound.filepath == source and sound.use_memory_cache
    assert not short.use_memory_cache and entry.filepath == source
    assert actuator.sound == short
    assert bytes(sound.packed_file.data) == packed
assert audio._hash(source) == original_hash

with open(source, 'rb') as stream:
    original_source = stream.read()
with open(source, 'ab') as stream:
    stream.write(b'changed')
try:
    audio.prepared_entries()
    raise AssertionError('Changed external source was accepted')
except ValueError as error:
    assert 'source changed' in str(error)
with open(source, 'wb') as stream:
    stream.write(original_source)
assert audio._hash(source) == original_hash

prepared = next(row for row in report['entries'] if row.get('prepared_path'))
with open(prepared['prepared_path'], 'ab') as stream:
    stream.write(b'changed')
try:
    audio.prepared_entries()
    raise AssertionError('Changed cache was accepted')
except ValueError as error:
    assert 'cache changed' in str(error)
# Preparing again repairs a modified derivative instead of blessing its new hash.
repaired = audio.prepare_audio(os.path.join(output, 'cache'))
with open(prepared['prepared_path'], 'rb') as stream:
    assert not stream.read().endswith(b'changed')
assert len(aud.Sound(prepared['prepared_path']).limit(0, .1).data())
assert audio.prepared_entries()
# Local and linked datablocks may legally have the same name.
library_path = os.path.join(output, 'linked.range')
bpy.ops.wm.save_as_mainfile(filepath=library_path, copy=True, check_existing=False)
with bpy.data.libraries.load(library_path, link=True) as (source_ids, linked_ids):
    linked_ids.sounds = ['LongMusic']
identities = [identity for identity, kind, target, uses in audio._targets()]
assert len(identities) == len(set(identities))
assert audio.prepared_entries()
# The selected encoder remains available after switching the active scene.
active = bpy.context.screen.scene
active[audio.KEY] = json.dumps(dict(encoder_path=selected_encoder))
other = bpy.data.scenes.new('OtherScene')
bpy.context.screen.scene = other
assert audio.configured_encoder() == selected_encoder
bpy.context.screen.scene = active
with open(os.path.join(output, 'results.json'), 'w') as stream:
    json.dump(dict(ok=True, before=report['bytes_before'], after=report['bytes_after'],
                   entries=len(report['entries']), exception_restore=True), stream, indent=2)
print('PREPARE_AUDIO_TESTS_OK', report['bytes_before'], report['bytes_after'])
