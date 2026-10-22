# SPDX-License-Identifier: GPL-2.0-or-later
"""Desktop asset transformations shared by runtime and RangeArmor exports.

Each project file is opened in a separate background process. Source projects are
never saved: only a snapshot of the active editor and copies in the staging tree.
"""
import contextlib
import importlib
import json
import hashlib
import os
import shutil
import subprocess
import tempfile

import bpy


def _textures():
    # Audio can be merged into main independently of the DDS feature branch.
    try:
        return importlib.import_module('bl_operators.anastacio_prepare_textures')
    except ModuleNotFoundError as error:
        if error.name != 'bl_operators.anastacio_prepare_textures':
            raise
        return None


@contextlib.contextmanager
def export_prepared_assets():
    """One transaction for image and sound transformations, including rollback."""
    from bl_operators import anastacio_prepare_audio as audio
    with contextlib.ExitStack() as stack:
        textures = _textures()
        if textures:
            stack.enter_context(textures.export_prepared_textures())
        mapping = stack.enter_context(audio.export_prepared_audio())
        yield mapping


def enabled():
    from bl_operators import anastacio_prepare_audio as audio
    textures = _textures()
    return (any(audio.KEY in scene for scene in bpy.data.scenes) or
            bool(textures and any(textures.KEY in image for image in bpy.data.images)))


def _inside(path, root):
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) == os.path.realpath(root)
    except ValueError:  # Separate Windows drives cannot contain one another.
        return False


@contextlib.contextmanager
def _without_save_handlers():
    handlers = [(group, list(group)) for group in
                (bpy.app.handlers.save_pre, bpy.app.handlers.save_post)]
    try:
        for group, values in handlers:
            group.clear()
        yield
    finally:
        for group, values in handlers:
            group[:] = values


def build_export_tree(destination, protected_main=False, keep_debug_overlays=False):
    """Stage the saved file's directory, preserving relative LibLoad paths.

    All .range/.blend files under that directory are exported, including dynamically
    named LibLoad files. Libraries outside this boundary are rejected explicitly.
    Loose assets are retained: their use by arbitrary scripts cannot be inferred.
    Caller owns the staging directory and publishes it only after this succeeds.
    """
    from bl_operators import anastacio_prepare_audio as audio
    if not bpy.data.filepath:
        raise ValueError('Save the project before exporting')
    source = os.path.realpath(bpy.data.filepath)
    root = os.path.dirname(source)
    destination = os.path.realpath(destination)
    if _inside(destination, root) or _inside(root, destination):
        raise ValueError('Export staging must be outside the source asset directory')
    textures = _textures()
    options = dict(audio=any(audio.KEY in scene for scene in bpy.data.scenes),
                   encoder=audio.configured_encoder(), textures=None,
                   keep_debug_overlays=keep_debug_overlays)
    if textures:
        for image in bpy.data.images:
            record = textures._record(image)
            if record:
                options['textures'] = {key: record['options'][key] for key in ('max_size', 'quality')}
                break
    excluded = {'.anastacio_cache', 'textures_dds', '__pycache__', '.git', 'build',
                'node_modules', 'exports', '.anastacio-export'}
    def ignore(folder, names):
        ignored = []
        for name in names:
            path = os.path.join(folder, name)
            if os.path.islink(path):
                raise ValueError('Export does not follow asset symlinks: ' + path)
            if name in excluded or name.endswith(('.cooked', '.range1', '.blend1', '.rasec')):
                ignored.append(name)
        return ignored
    shutil.copytree(root, destination, ignore=ignore)
    fd, snapshot = tempfile.mkstemp(prefix='.anastacio-export-', suffix='.range', dir=root)
    os.close(fd)
    try:
        # Export snapshots must not run authoring save handlers (weather auto-setup,
        # user callbacks, etc.) against the live scene.
        with _without_save_handlers():
            saved = bpy.ops.wm.save_as_mainfile(filepath=snapshot, copy=True, relative_remap=True,
                                              compress=False, check_existing=False)
        if 'FINISHED' not in saved:
            raise RuntimeError('Could not snapshot the active project')
        projects = []
        for folder, dirs, names in os.walk(destination):
            for name in names:
                if name.lower().endswith(('.range', '.blend')):
                    relative = os.path.relpath(os.path.join(folder, name), destination)
                    projects.append(relative)
        main = os.path.basename(source)
        if main not in projects:
            raise ValueError('Main file must be a saved .range or .blend')
        reports = []
        with tempfile.TemporaryDirectory(prefix='anastacio-export-job-') as jobdir:
            for index, relative in enumerate(sorted(projects)):
                original = os.path.join(root, relative)
                target = os.path.join(destination, relative)
                protected = relative == main and protected_main
                if protected:
                    target = os.path.splitext(target)[0] + '.rasec'
                job = dict(source=snapshot if relative == main else original,
                           target=target, root=root, destination=destination,
                           protected=protected, options=options)
                jobpath = os.path.join(jobdir, '%d.json' % index)
                with open(jobpath, 'w', encoding='utf-8') as stream:
                    json.dump(job, stream)
                logpath = os.path.join(jobdir, '%d.log' % index)
                command = [bpy.app.binary_path, '-b', '--factory-startup', '--disable-autoexec',
                           '--python-exit-code', '1', '--python', os.path.abspath(__file__), '--', jobpath]
                with open(logpath, 'w', encoding='utf-8') as log:
                    process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if process.returncode:
                    with open(logpath, encoding='utf-8', errors='replace') as log:
                        raise RuntimeError('Export copy failed for %s:\n%s' % (relative, log.read()[-6000:]))
                with open(jobpath + '.result', encoding='utf-8') as stream:
                    reports.append(json.load(stream))
                if protected:
                    os.remove(os.path.join(destination, relative))
        result = dict(main=os.path.splitext(main)[0] + '.rasec' if protected_main else main,
                      files=reports)
        with open(os.path.join(destination, 'anastacio-export-report.json'), 'w', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
        return result
    finally:
        for path in (snapshot, snapshot + '1'):
            if os.path.isfile(path):
                os.remove(path)


def _worker(jobpath):
    from bl_operators import anastacio_prepare_audio as audio
    from bl_operators.wm import export_debug_overlays_off
    with open(jobpath, encoding='utf-8') as stream:
        job = json.load(stream)
    bpy.ops.wm.open_mainfile(filepath=job['source'], load_ui=False, use_scripts=False)
    bpy.context.user_preferences.filepaths.save_version = 0
    options = job['options']
    # Process dependencies in their own copies; retain their relative layout.
    for library in bpy.data.libraries:
        path = os.path.realpath(bpy.path.abspath(library.filepath))
        if not _inside(path, job['root']):
            raise ValueError('Linked library outside the export asset directory: ' + path)
        relative = os.path.relpath(path, job['root'])
        library.filepath = os.path.join(job['destination'], relative)
    textures = _textures()
    if options['textures']:
        if not textures:
            raise RuntimeError('DDS export support is missing from this installation')
        for image in list(bpy.data.images):
            if image.library:
                continue
            if textures.KEY not in image and not textures.skip_reason(image):
                textures.prepare_image(image, **options['textures'])
    if options['audio']:
        # Preparation modifies only this worker's in-memory copy, including LibLoad files.
        audio.prepare_audio(encoder_path=options['encoder'])
    with export_prepared_assets() as mapping, export_debug_overlays_off(options['keep_debug_overlays']):
        # World audio slots are paths, not bSound: copy their derivatives beside the scene.
        assets = os.path.join(os.path.dirname(job['target']), 'audio_prepared')
        for world in bpy.data.worlds:
            if world.library:
                continue
            for module in world.sound_modules:
                for entry in module.sounds:
                    absolute = bpy.path.abspath(entry.filepath)
                    if absolute in mapping['files'] or (absolute and os.path.isfile(absolute)
                                                       and not _inside(absolute, job['root'])):
                        os.makedirs(assets, exist_ok=True)
                        with open(absolute, 'rb') as source_stream:
                            digest = hashlib.sha256(source_stream.read()).hexdigest()
                        target = os.path.join(assets, digest + os.path.splitext(absolute)[1])
                        shutil.copy2(absolute, target)
                        entry.filepath = target
                    elif absolute and _inside(absolute, job['root']):
                        entry.filepath = os.path.join(job['destination'], os.path.relpath(absolute, job['root']))
        # Pack ordinary file textures/sounds as well, making known references self contained.
        for image in bpy.data.images:
            if not image.library and image.source == 'FILE' and not image.packed_file:
                image.pack()
        for sound in bpy.data.sounds:
            if not sound.library and not sound.packed_file:
                sound.pack()
        save = bpy.ops.wm.save_as_mainfile_protected if job['protected'] else bpy.ops.wm.save_as_mainfile
        with _without_save_handlers():
            saved = save(filepath=job['target'], copy=True, relative_remap=True, check_existing=False)
        if 'FINISHED' not in saved:
            raise RuntimeError('Could not save export copy')
    with open(jobpath + '.result', 'w', encoding='utf-8') as stream:
        json.dump(dict(file=os.path.relpath(job['target'], job['destination']),
                       audio=options['audio'], bytes=os.path.getsize(job['target'])), stream)


if __name__ == '__main__':
    import sys
    _worker(sys.argv[sys.argv.index('--') + 1])
