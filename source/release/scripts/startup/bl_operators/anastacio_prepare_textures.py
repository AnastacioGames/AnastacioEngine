# SPDX-License-Identifier: GPL-2.0-or-later
"""Prepare immutable desktop DDS derivatives; originals remain the authoring source."""
import contextlib
import hashlib
import json
import os
import re
import struct
import tempfile

import bpy
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator, PropertyGroup, UIList

KEY = 'anastacio_dds_v1'
VERSION = 'rgbcx-f66c2e4-mips-linear-straight-v1'
SIZE_ITEMS = [('0', 'Original', 'Keep original dimensions'), ('4096', '4096', ''),
              ('2048', '2048', ''), ('1024', '1024', ''), ('512', '512', '')]
QUALITY_ITEMS = [('0', 'Fast', 'Low encoder effort'), ('10', 'High', 'Higher encoder effort')]


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _source_hash(image, options, content_hash=None):
    """Hash bytes actually used, including packed sources and interpretation."""
    if image.is_dirty:
        raise ValueError('Save the edited image before preparing textures')
    digest = hashlib.sha256()
    if content_hash is None:
        if image.packed_file:
            content_hash = hashlib.sha256(bytes(image.packed_file.data)).hexdigest()
        else:
            path = bpy.path.abspath(image.filepath, library=image.library)
            content_hash = _hash_file(path)
    digest.update(content_hash.encode('ascii'))
    metadata = [VERSION, list(image.size), image.colorspace_settings.name,
                image.alpha_mode, image.use_alpha, options]
    digest.update(json.dumps(metadata, sort_keys=True).encode('utf-8'))
    return digest.hexdigest()


def _walk_nodes(tree, seen=None):
    seen = set() if seen is None else seen
    if not tree or tree.as_pointer() in seen:
        return
    seen.add(tree.as_pointer())
    for node in tree.nodes:
        yield node
        if node.type == 'GROUP':
            yield from _walk_nodes(node.node_tree, seen)


def color_usage():
    """Only known color uses are automatic. Mixed/data/unknown uses stay original."""
    uses, blocked = set(), set()
    for mat in bpy.data.materials:
        for slot in mat.texture_slots:
            if slot and slot.texture and slot.texture.type == 'IMAGE' and slot.texture.image:
                image = slot.texture.image.name
                # Texture slots also expose volume/particle aliases of the same bits.
                # Inspect surface mappings explicitly, not every RNA use_map_* property.
                data_use = any(getattr(slot, attr, False) for attr in (
                    'use_map_normal', 'use_map_parallax', 'use_map_color_spec', 'use_map_mirror',
                    'use_map_diffuse', 'use_map_specular', 'use_map_ambient', 'use_map_hardness',
                    'use_map_raymir', 'use_map_emit', 'use_map_translucency', 'use_map_displacement',
                    'use_map_warp', 'use_map_roughness', 'use_map_metallic', 'use_map_sss'))
                if slot.use_map_color_diffuse and not data_use and not slot.texture.use_normal_map:
                    uses.add(image)
                else:
                    blocked.add(image)
        for node in _walk_nodes(mat.node_tree):
            image = getattr(node, 'image', None)
            if image is None:
                continue
            if getattr(node, 'color_space', 'COLOR') == 'NONE':
                blocked.add(image.name)
                continue
            found = False
            for output in node.outputs:
                for link in output.links:
                    found = True
                    if (link.to_node.type in {'BSDF_PRINCIPLED', 'BSDF_DIFFUSE', 'EMISSION'} and
                            link.to_socket.name in {'Base Color', 'Color', 'Emission'}):
                        uses.add(image.name)
                    elif output.name == 'Alpha' and link.to_socket.name == 'Alpha':
                        uses.add(image.name)
                    else:
                        blocked.add(image.name)
            if not found:
                blocked.add(image.name)
    return uses - blocked


def normal_usage():
    """Images used only as tangent-space normal maps: these become BC5 (X/Y, Z rebuilt)."""
    uses, blocked = set(), set()
    for mat in bpy.data.materials:
        for slot in mat.texture_slots:
            if slot and slot.texture and slot.texture.type == 'IMAGE' and slot.texture.image:
                image = slot.texture.image.name
                tex = slot.texture
                other = any(getattr(slot, attr, False) for attr in (
                    'use_map_color_diffuse', 'use_map_parallax', 'use_map_color_spec', 'use_map_mirror',
                    'use_map_diffuse', 'use_map_specular', 'use_map_ambient', 'use_map_hardness',
                    'use_map_raymir', 'use_map_emit', 'use_map_translucency', 'use_map_displacement',
                    'use_map_warp', 'use_map_roughness', 'use_map_metallic', 'use_map_sss', 'use_map_alpha'))
                if (slot.use_map_normal and tex.use_normal_map and not other and
                        getattr(slot, 'normal_map_space', 'TANGENT') == 'TANGENT'):
                    uses.add(image)
                else:
                    blocked.add(image)
        for node in _walk_nodes(mat.node_tree):
            image = getattr(node, 'image', None)
            if image is None:
                continue
            found = False
            for output in node.outputs:
                for link in output.links:
                    found = True
                    if (output.name == 'Color' and link.to_node.type == 'NORMAL_MAP' and
                            link.to_node.space == 'TANGENT'):
                        uses.add(image.name)
                    else:
                        blocked.add(image.name)
            if not found:
                blocked.add(image.name)
    return uses - blocked


def image_format(image, colors=None, normals=None):
    """'BC5' for tangent-space normal maps, 'AUTO' (BC1/BC3) for colors, None otherwise."""
    if image.name in (normal_usage() if normals is None else normals):
        return 'BC5'
    if image.name in (color_usage() if colors is None else colors):
        return 'AUTO'
    return None


def skip_reason(image, colors=None, normals=None):
    if image.library:
        return 'Linked library (prepare in its source project)'
    if image.source != 'FILE' or image.type != 'IMAGE':
        return 'Only single file images are supported'
    if image.is_dirty:
        return 'Save edited pixels first'
    if image.is_float:
        return 'Float / HDR image'
    if image.use_fields or image.use_multiview or image.use_tiles or image.use_animation:
        return 'Fields / multiview / tiled / animated image'
    w, h = image.size
    if not w or not h:
        return 'Missing image data'
    if max(w, h) <= 64:
        return 'Small image (64 px or less)'
    if w & (w - 1) or h & (h - 1):
        return 'Non power-of-two (resize explicitly first)'
    if os.path.splitext(image.filepath)[1].lower() not in {'.png', '.jpg', '.jpeg', '.tga', '.bmp'}:
        return 'Source format excluded'
    if image.name in (normal_usage() if normals is None else normals):
        if image.name in (color_usage() if colors is None else colors):
            return 'Used as color and normal map'
        if re.search(r'(^|[_ .-])(lightmap|rgbm)([_ .-]|$)', image.name.lower()):
            return 'Lightmap'
        return ''
    if image.colorspace_settings.name != 'sRGB':
        return 'Data / non-sRGB image'
    if re.search(r'(^|[_ .-])(n|normal|normals|lightmap|rgbm)([_ .-]|$)', image.name.lower()):
        return 'Normal map / lightmap'
    if any(getattr(curve, 'atlas_image', None) == image for curve in bpy.data.curves):
        return 'Bitmap font atlas'
    if any(getattr(scene, 'ae_lightmap', '') == image.name for scene in bpy.data.scenes):
        return 'Baked lightmap'
    if image.name not in (color_usage() if colors is None else colors):
        return 'Usage is not exclusively a known material color'
    return ''


def dds_info(path):
    with open(path, 'rb') as stream:
        header = stream.read(128)
    if len(header) != 128 or header[:4] != b'DDS ':
        raise ValueError('Invalid DDS header')
    values = struct.unpack('<32I', header)
    if values[1] != 124 or header[84:88] not in (b'DXT1', b'DXT5', b'ATI2'):
        raise ValueError('Unsupported DDS format')
    w, h, levels = values[4], values[3], values[7]
    if not w or not h or w & (w - 1) or h & (h - 1) or levels != max(w, h).bit_length():
        raise ValueError('Invalid DDS dimensions or incomplete mip chain')
    block = 8 if header[84:88] == b'DXT1' else 16
    size, mw, mh = 128, w, h
    for _ in range(levels):
        size += ((mw + 3) // 4) * ((mh + 3) // 4) * block
        mw, mh = max(1, mw // 2), max(1, mh // 2)
    if os.path.getsize(path) != size:
        raise ValueError('DDS payload size mismatch')
    return w, h, header[84:88].decode('ascii'), size - 128


def _convert(image, options, fingerprint, path, write):
    """Convert an immutable snapshot of the source and publish it at path only after success."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.prepare-', suffix=os.path.splitext(path)[1], dir=folder)
    os.close(fd)
    snapshot = None
    source_image = None
    try:
        # Decode an immutable snapshot, rather than an old editor pixel cache after
        # an external paint application changed the source file on disk.
        suffix = os.path.splitext(image.filepath)[1]
        source_fd, snapshot = tempfile.mkstemp(prefix='.source-', suffix=suffix, dir=folder)
        with os.fdopen(source_fd, 'wb') as stream:
            if image.packed_file:
                stream.write(bytes(image.packed_file.data))
            else:
                import shutil
                with open(bpy.path.abspath(image.filepath), 'rb') as original:
                    shutil.copyfileobj(original, stream)
        if _source_hash(image, options, _hash_file(snapshot)) != fingerprint:
            raise ValueError('Source changed while taking the conversion snapshot')
        source_image = bpy.data.images.load(snapshot, check_existing=False)
        source_image.colorspace_settings.name = image.colorspace_settings.name
        source_image.alpha_mode = image.alpha_mode
        source_image.use_alpha = image.use_alpha
        source_image.reload()
        if tuple(source_image.size) != tuple(image.size):
            raise ValueError('Source dimensions changed: reload the original image first')
        write(source_image, temporary)
        if _source_hash(image, options) != fingerprint:
            raise ValueError('Source changed during preparation')
        os.replace(temporary, path)
    finally:
        if source_image is not None:
            bpy.data.images.remove(source_image)
        if snapshot and os.path.exists(snapshot):
            os.remove(snapshot)
        if os.path.exists(temporary):
            os.remove(temporary)


def prepare_image(image, max_size=2048, quality=10):
    if not bpy.data.filepath:
        raise ValueError('Save the project first')
    reason = skip_reason(image)
    if reason:
        raise ValueError(reason)
    fmt = image_format(image)
    options = {'max_size': max_size, 'quality': quality, 'format': fmt}
    fingerprint = _source_hash(image, options)
    folder = os.path.join(os.path.dirname(bpy.data.filepath), 'textures_dds')
    name = bpy.path.clean_name(image.name)[:40] or 'image'
    path = os.path.join(folder, '%s_%s.dds' % (name, fingerprint[:24]))
    record = _record(image)
    valid = (record.get('fingerprint') == fingerprint and os.path.isfile(path) and
             record.get('dds_sha256') == _hash_file(path))
    if not valid:
        def write(source_image, temporary):
            source_image.save_dds(filepath=temporary, format=fmt, max_size=max_size, quality=quality,
                                  srgb=fmt != 'BC5')
            dds_info(temporary)
        _convert(image, options, fingerprint, path, write)
    w, h, fmt, size = dds_info(path)
    image[KEY] = json.dumps({'version': VERSION, 'path': bpy.path.relpath(path),
                            'fingerprint': fingerprint, 'options': options,
                            'dds_sha256': _hash_file(path), 'format': fmt})
    return w, h, fmt, size


def _record(image):
    try:
        record = json.loads(image.get(KEY, '{}'))
        return record if isinstance(record, dict) else {}
    except (ValueError, TypeError):
        return {}


def prepared_path(image, colors=None, normals=None):
    record = _record(image)
    if record.get('version') != VERSION:
        raise ValueError('Prepare textures again (cache version changed)')
    reason = skip_reason(image, colors, normals)
    if reason:
        raise ValueError(reason)
    if record['options'].get('format') != image_format(image, colors, normals):
        raise ValueError('Image usage changed (color / normal map): prepare textures again')
    if _source_hash(image, record['options']) != record['fingerprint']:
        raise ValueError('Source or settings changed: prepare textures again')
    path = bpy.path.abspath(record['path'])
    if _hash_file(path) != record['dds_sha256']:
        raise ValueError('Prepared DDS is missing or changed')
    dds_info(path)
    return path


KTX2_VERSION = 'basisu-073eb6a0-etc1s-uastc-v2'
KTX2_QUALITY = 75
KTX2_ID = b'\xabKTX 20\xbb\r\n\x1a\n'
KTX2_HIGH_QUALITY = 'range_ktx2_high_quality'  # image property: colour in UASTC


def ktx2_path(image, colors=None, normals=None):
    """KTX2 (Basis Universal) copy of a prepared image, for the Web/Android package.

    Same eligibility, size limit and colour / normal choice as the prepared DDS; cached in
    //textures_ktx2/ by source hash. ETC1S for colour, UASTC for tangent-space normal maps.
    """
    prepared_path(image, colors, normals)
    record = _record(image)
    fmt = record['options'].get('format')
    max_size = record['options'].get('max_size', 2048)
    high_quality = bool(image.get(KTX2_HIGH_QUALITY)) and fmt != 'BC5'
    options = {'container': KTX2_VERSION, 'max_size': max_size, 'quality': KTX2_QUALITY, 'format': fmt}
    if high_quality:
        options['high_quality'] = True
    fingerprint = _source_hash(image, options)
    folder = os.path.join(os.path.dirname(bpy.data.filepath), 'textures_ktx2')
    name = bpy.path.clean_name(image.name)[:40] or 'image'
    path = os.path.join(folder, '%s_%s.ktx2' % (name, fingerprint[:24]))
    valid = False
    if os.path.isfile(path):
        with open(path, 'rb') as stream:
            valid = stream.read(12) == KTX2_ID
    if not valid:
        def write(source_image, temporary):
            source_image.save_ktx2(filepath=temporary, normal=fmt == 'BC5', max_size=max_size,
                                   quality=KTX2_QUALITY, srgb=fmt != 'BC5', high_quality=high_quality)
            with open(temporary, 'rb') as stream:
                if stream.read(12) != KTX2_ID:
                    raise ValueError('KTX2 encoder produced an invalid file')
        _convert(image, options, fingerprint, path, write)
    return path


@contextlib.contextmanager
def export_prepared_textures(container='DDS'):
    """Remap users to temporary packed DDS copies only while saving desktop exports.

    The original Image, its pixels, packed bytes, filepath and metadata are untouched.
    Linked libraries and external LibLoad files must be prepared/exported separately.
    """
    swaps = []
    colors, normals = color_usage(), normal_usage()
    try:
        for original in list(bpy.data.images):
            if KEY not in original or original.library:
                continue
            try:
                path = (ktx2_path if container == 'KTX2' else prepared_path)(original, colors, normals)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
                # A stale texture keeps its original in the export instead of stopping it.
                print('Export: %s keeps its original image (%s)' % (original.name, error))
                continue
            # Fresh load avoids inheriting PNG packed bytes or old pixel buffers.
            image = bpy.data.images.load(path, check_existing=False)
            name, fake = original.name, original.use_fake_user
            swaps.append((original, image, name, fake))
            image.colorspace_settings.name = original.colorspace_settings.name
            # Byte imbufs are internally straight even for premultiplied source files.
            # DDS/KTX2 blocks must match the decoded fallback: export normalized straight alpha.
            image.alpha_mode = 'STRAIGHT'
            image.use_alpha = original.use_alpha
            image.use_clamp_x = original.use_clamp_x
            image.use_clamp_y = original.use_clamp_y
            image.mapping = original.mapping
            image.display_aspect = original.display_aspect
            image.use_fake_user = fake
            image.pack()
            original.use_fake_user = False
            original.name = '__anastacio_dds_source__'
            image.name = name
            original.user_remap(image)
        yield
    finally:
        for original, image, name, fake in reversed(swaps):
            image.user_remap(original)
            image.name = '__anastacio_dds_export__'
            original.name = name
            original.use_fake_user = fake
            bpy.data.images.remove(image)


class AnastacioTextureEntry(PropertyGroup):
    image_name: StringProperty()
    selected: BoolProperty(default=False)
    status: StringProperty()
    eligible: BoolProperty(default=False)
    width: IntProperty()
    height: IntProperty()
    format: StringProperty()
    high_quality: BoolProperty(name='KTX2 HQ', default=False,
                               description='Web and Android: smoother gradients in a larger file, same GPU cost. '
                                           'For UI, sky and skin')


class ANASTACIO_UL_prepared_textures(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        row.enabled = item.eligible
        row.prop(item, 'selected', text='')
        row.label(text=item.image_name, icon='IMAGE_DATA')
        if item.eligible:
            w, h = item.width, item.height
            limit = int(data.max_size)
            while limit and max(w, h) > limit:
                w, h = max(1, w // 2), max(1, h // 2)
            old = item.width * item.height * 4 * 4 / 3 / 1048576
            size, mw, mh = 0, w, h
            while True:
                size += ((mw + 3) // 4) * ((mh + 3) // 4) * (8 if item.format == 'DXT1' else 16)
                if mw == mh == 1:
                    break
                mw, mh = max(1, mw // 2), max(1, mh // 2)
            row.label(text='%d x %d | %.1f -> %.2f MiB | %s %s' % (
                w, h, old, size / 1048576, item.format, item.status))
            if item.format != 'BC5':
                row.prop(item, 'high_quality')
        else:
            row.label(text=item.status)


class GAME_OT_prepare_textures(Operator):
    """Prepare desktop DDS textures, keeping original images for authoring and Web"""
    bl_idname = 'game.prepare_textures'
    bl_label = 'Prepare Textures (DDS)'
    entries: CollectionProperty(type=AnastacioTextureEntry)
    max_size: EnumProperty(name='Maximum size', items=SIZE_ITEMS, default='2048')
    quality: EnumProperty(name='Quality', items=QUALITY_ITEMS, default='10')
    _timer = None

    @classmethod
    def poll(cls, context):
        return bool(bpy.data.filepath)

    def invoke(self, context, event):
        self.entries.clear()
        colors, normals = color_usage(), normal_usage()
        for image in bpy.data.images:
            reason = skip_reason(image, colors, normals)
            entry = self.entries.add()
            entry.image_name = image.name
            entry.eligible = not reason
            entry.selected = not reason
            if reason:
                entry.status = reason
            else:
                entry.width, entry.height = image.size
                # Estimate only: reading every pixel is too slow here, save_dds(AUTO) decides.
                entry.format = ('BC5' if image.name in normals else
                                'DXT5' if image.depth == 32 and image.use_alpha else 'DXT1')
                entry.status = '(Prepared)' if KEY in image else ''
                entry.high_quality = bool(image.get(KTX2_HIGH_QUALITY))
        return context.window_manager.invoke_props_dialog(self, width=820)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text='Images')
        box.label(text='Originals stay editable. Desktop exports embed the prepared DDS copies.', icon='INFO')
        box.template_list('ANASTACIO_UL_prepared_textures', '', self, 'entries', self, 'active_index', rows=10)
        box = layout.box()
        box.label(text='Settings')
        box.prop(self, 'max_size')
        box.prop(self, 'quality')
        box = layout.box()
        box.label(text='Expected texture VRAM: BC1 ~1/8, BC3 ~1/4 at equal resolution, with mipmaps.')
        box.label(text='Escape cancels between images; completed textures remain prepared.')
        box.operator('game.revert_prepared_textures', text='Revert All Prepared Textures', icon='LOOP_BACK')

    active_index: IntProperty(default=0)

    def execute(self, context):
        for entry in self.entries:
            image = bpy.data.images.get(entry.image_name)
            if image and entry.eligible:
                if entry.high_quality:
                    image[KTX2_HIGH_QUALITY] = True
                elif KTX2_HIGH_QUALITY in image:
                    del image[KTX2_HIGH_QUALITY]
        self._pending = [entry.image_name for entry in self.entries if entry.selected and entry.eligible]
        self._done = 0
        self._total = len(self._pending)
        if not self._pending:
            self.report({'WARNING'}, tip_('No textures selected'))
            return {'CANCELLED'}
        if bpy.app.background:
            for name in self._pending:
                prepare_image(bpy.data.images[name], int(self.max_size), int(self.quality))
            return {'FINISHED'}
        context.window_manager.progress_begin(0, self._total)
        self._timer = context.window_manager.event_timer_add(0.1, context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        context.window_manager.progress_end()

    def cancel(self, context):
        self._finish(context)

    def modal(self, context, event):
        if event.type == 'ESC':
            self._finish(context)
            self.report({'INFO'}, tip_('Cancelled; %d textures prepared') % self._done)
            return {'CANCELLED'}
        if event.type != 'TIMER':
            return {'RUNNING_MODAL'}
        try:
            image = bpy.data.images.get(self._pending.pop(0))
            if image is None:
                raise ValueError('Selected image was removed')
            prepare_image(image, int(self.max_size), int(self.quality))
        except Exception as error:
            self._finish(context)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self._done += 1
        context.window_manager.progress_update(self._done)
        if not self._pending:
            self._finish(context)
            self.report({'INFO'}, tip_('%d textures prepared. Save the project to keep export settings.') % self._done)
            return {'FINISHED'}
        return {'RUNNING_MODAL'}


class GAME_OT_revert_prepared_textures(Operator):
    """Stop using prepared copies in future exports; cached files are retained"""
    bl_idname = 'game.revert_prepared_textures'
    bl_label = 'Revert Prepared Textures'

    def execute(self, context):
        count = 0
        for image in bpy.data.images:
            if not image.library and KEY in image:
                del image[KEY]
                count += 1
        self.report({'INFO'}, tip_('%d textures reverted; originals preserved') % count)
        return {'FINISHED'}


classes = (AnastacioTextureEntry, ANASTACIO_UL_prepared_textures,
           GAME_OT_prepare_textures, GAME_OT_revert_prepared_textures)
