"""Background integration: staged main + LibLoad copies, clean archive and rollback.

Run: AnastacioEngine -b --factory-startup --python this.py -- OUTPUT
Requires the DDS feature installed to exercise the shared image/sound transaction.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

import aud
import bpy
from bl_operators import anastacio_prepare_audio as audio
from bl_operators import anastacio_prepare_textures as dds
from bl_operators import anastacio_export_assets as assets

output = os.path.abspath(sys.argv[sys.argv.index('--') + 1])
os.makedirs(output, exist_ok=True)


def inspect(tree):
    results = []
    playback = []
    for relative in ('main.range', 'levels/library.range'):
        bpy.ops.wm.open_mainfile(filepath=os.path.join(tree, relative), use_scripts=False)
        sound = bpy.data.sounds['Music']
        assert bytes(sound.packed_file.data)[:4] == b'OggS'
        assert not sound.use_memory_cache
        image = bpy.data.images['Color']
        assert bytes(image.packed_file.data)[:4] == b'DDS '
        entry = next(entry for module in bpy.context.scene.world.sound_modules
                     for entry in module.sounds if entry.name == 'Theme')
        path = bpy.path.abspath(entry.filepath)
        assert os.path.commonpath([os.path.realpath(path), tree]) == tree, path
        decoded = aud.Sound(path).limit(0, .1)
        assert float(abs(decoded.data()).max()) > .1
        playback.append(decoded)
        results.append(relative)
    device = aud.Device('OpenAL')
    for decoded in playback:
        handle = device.play(decoded)
        assert handle.status
        handle.stop()
    return results


if '--inspect' in sys.argv:
    validated = inspect(output)
    with open(os.path.join(output, 'inspection.json'), 'w') as stream:
        json.dump(dict(ok=True, files=validated, playback='OpenAL null backend'), stream)
    print('CLEAN_AUDIO_DDS_PACKAGE_OK')
else:
    root = os.path.join(output, 'source', 'data')
    originals = os.path.join(output, 'originals')
    os.makedirs(os.path.join(root, 'levels'), exist_ok=True)
    os.makedirs(originals, exist_ok=True)
    wav = os.path.join(originals, 'music.wav')
    aud.Sound.sine(440, 48000).limit(0, 26).write(wav)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_GAME'
    sound = bpy.data.sounds.load(wav)
    sound.name = 'Music'
    sound.use_fake_user = True
    sound.use_memory_cache = True
    sound.pack()
    image = bpy.data.images.new('Color', 128, 128, alpha=True)
    image.pixels = [1.0, .25, .1, 1.0] * (128 * 128)
    image.filepath_raw = os.path.join(originals, 'color.png')
    image.file_format = 'PNG'
    image.save()
    image.reload()
    texture = bpy.data.textures.new('Color', type='IMAGE')
    texture.image = image
    mat = bpy.data.materials.new('Color')
    slot = mat.texture_slots.add()
    slot.texture = texture
    mat.use_fake_user = True
    module = scene.world.sound_modules.new('Music', type='MUSIC')
    entry = module.sounds.new('Theme', filepath=wav)
    # The library is deliberately unprepared: the worker must apply the main policy.
    library = os.path.join(root, 'levels', 'library.range')
    bpy.ops.wm.save_as_mainfile(filepath=library)
    main = os.path.join(root, 'main.range')
    bpy.ops.wm.save_as_mainfile(filepath=main)
    dds.prepare_image(image, 128, 0)
    audio.prepare_audio()
    bpy.ops.wm.save_as_mainfile(filepath=main)
    before = {path: audio._hash(path) for path in (main, library, wav, bpy.path.abspath(image.filepath_raw))}
    packed = bytes(sound.packed_file.data)
    original_paths = (sound.filepath, entry.filepath, image.filepath)
    # Compare full trees with the same archive settings, not sum of references.
    baseline = os.path.join(output, 'before.zip')
    with zipfile.ZipFile(baseline, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(main, 'main.range')
        archive.write(library, 'levels/library.range')
        archive.write(wav, 'music.wav')
    tree = os.path.join(output, 'prepared')
    def forbidden_save_handler(*args):
        raise AssertionError('Export ran an authoring save handler')
    bpy.app.handlers.save_pre.append(forbidden_save_handler)
    try:
        report = assets.build_export_tree(tree)
        assert forbidden_save_handler in bpy.app.handlers.save_pre
    finally:
        bpy.app.handlers.save_pre.remove(forbidden_save_handler)
    assert len(report['files']) == 2, report
    assert bpy.data.filepath == main
    assert (sound.filepath, entry.filepath, image.filepath) == original_paths
    assert bytes(sound.packed_file.data) == packed and sound.use_memory_cache
    assert {path: audio._hash(path) for path in before} == before
    archive = shutil.make_archive(os.path.join(output, 'after'), 'zip', tree)
    clean = os.path.join(output, 'clean')
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(clean)
    # Hide every authoring dependency. Run a fresh editor with autoexec disabled.
    hidden = []
    try:
        for path in (os.path.join(output, 'source'), originals, tree):
            hidden_path = path + '-hidden'
            os.rename(path, hidden_path)
            hidden.append((path, hidden_path))
        command = [bpy.app.binary_path, '-b', '--factory-startup', '--disable-autoexec',
                   '--python-exit-code', '1', '--python', os.path.abspath(__file__),
                   '--', clean, '--inspect']
        with open(os.path.join(output, 'clean.log'), 'w') as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                     env=dict(os.environ, ALSOFT_DRIVERS='null'),
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        assert process.returncode == 0, 'See clean.log'
    finally:
        for path, hidden_path in reversed(hidden):
            os.rename(hidden_path, path)
    before_size, after_size = os.path.getsize(baseline), os.path.getsize(archive)
    assert after_size < before_size, (before_size, after_size)
    with open(os.path.join(output, 'results.json'), 'w') as stream:
        json.dump(dict(ok=True, archive_before=before_size, archive_after=after_size,
                       source_unchanged=True, main_and_libload=True, clean_playback='OpenAL null backend'), stream, indent=2)
    print('AUDIO_EXPORT_TESTS_OK', before_size, after_size)
