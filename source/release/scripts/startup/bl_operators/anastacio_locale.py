# Editor side of Range.locale (scripts/modules/range_locale.py): translation table in
# //locale/translations.csv, per-language font/atlas in //locale/locale.json.

import csv
import json
import os
import re

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, StringProperty

import range_locale

CSV_REL = "//locale/translations.csv"
CONFIG_REL = "//locale/locale.json"
ATLAS_PREFIX = "LocaleAtlas_"
# always baked with each language: digits and common punctuation (scores, timers, names)
ATLAS_BASE_CHARS = " 0123456789.,:;!?%+-/()'\"#*&@<>=_[]"


def csv_path():
    return bpy.path.abspath(CSV_REL)


def config_path():
    return bpy.path.abspath(CONFIG_REL)


def read_table():
    """(header, rows) of the CSV as lists of strings; empty table when the file is missing."""
    path = csv_path()
    if not os.path.isfile(path):
        return [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f)]
    header, body = [], []
    for r in rows:
        if not header:
            if r and r[0].strip() and not r[0].lstrip().startswith("#"):
                header = [c.strip() for c in r]
            continue
        body.append(r)
    return header, body


def write_table(header, rows):
    path = csv_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # utf-8 with BOM: Excel opens the accents and Cyrillic right
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    _refresh_text_block(path)


def read_config():
    path = config_path()
    if os.path.isfile(path):
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


def write_config(cfg):
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    _refresh_text_block(path)


def _refresh_text_block(path):
    for t in bpy.data.texts:
        if t.filepath and os.path.normcase(bpy.path.abspath(t.filepath)) == os.path.normcase(path):
            with open(path, encoding="utf-8-sig") as f:
                t.from_string(f.read())


def language_columns(header):
    """[(column index, code)] of the language columns."""
    out = []
    for i, c in enumerate(header[1:], 1):
        if c and not c.startswith("_") and c.lower() not in range_locale._IGNORED_COLUMNS:
            out.append((i, range_locale.normalize(c)))
    return out


def slug(text):
    s = text.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\w.]+", "", s)
    return s[:60] or "text"


def _game_texts(context, selected_only):
    obs = context.selected_objects if selected_only else context.scene.objects
    seen = set()
    for ob in obs:
        if ob.type == 'FONT' and ob.data not in seen:
            seen.add(ob.data)
            yield ob


def _need_saved(op):
    if not bpy.data.filepath:
        op.report({'ERROR'}, "Save the .range first: the table lives in the locale/ folder next to it")
        return True
    return False


def show_in_text_editor(context, path):
    text = next((t for t in bpy.data.texts
                 if t.filepath and os.path.normcase(bpy.path.abspath(t.filepath)) == os.path.normcase(path)), None)
    if text is None:
        text = bpy.data.texts.load(path)
    for area in context.screen.areas:
        if area.type == 'TEXT_EDITOR':
            area.spaces.active.text = text
            return text, True
    return text, False


class LOCALE_OT_table_create(Operator):
    """Create locale/translations.csv (or add missing keys to it) from the Translation Keys of the texts"""
    bl_idname = "locale.table_create"
    bl_label = "Create / Update Translation Table"
    bl_options = {'REGISTER', 'UNDO'}

    languages = StringProperty(name="Languages", default="en, pt-BR, es",
                               description="Language codes for a new table (BCP 47: en, pt-BR, es, ru, ja...)")

    def invoke(self, context, event):
        if os.path.isfile(csv_path()):
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if _need_saved(self):
            return {'CANCELLED'}
        header, rows = read_table()
        if not header:
            codes = [range_locale.normalize(c) for c in self.languages.replace(";", ",").split(",") if c.strip()]
            header = ["key"] + (codes or ["en"]) + ["context"]
        known = {r[0].strip() for r in rows if r}
        base_col = language_columns(header)[0][0] if language_columns(header) else 1
        added = 0
        for ob in _game_texts(context, False):
            key = ob.data.locale_key.strip()
            if key and key not in known:
                row = [""] * len(header)
                row[0] = key
                row[base_col] = ob.data.body.replace("\n", "\\n")
                rows.append(row)
                known.add(key)
                added += 1
        write_table(header, rows)
        self.report({'INFO'}, "%s: %d keys (%d new)" % (CSV_REL, len(known), added))
        return {'FINISHED'}


class LOCALE_OT_keys_from_text(Operator):
    """Give each selected text without a key a Translation Key made from its text, """ \
        """and add it to the table with the text in the first language column"""
    bl_idname = "locale.keys_from_text"
    bl_label = "Keys from Selected Texts"
    bl_options = {'REGISTER', 'UNDO'}

    prefix = StringProperty(name="Prefix", default="",
                            description="Put before every new key, e.g. menu. or hud.")
    language_font = BoolProperty(name="Language Font", default=True,
                                 description="Also turn on Language Font (font/atlas follow the language)")

    @classmethod
    def poll(cls, context):
        return any(ob.type == 'FONT' for ob in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if _need_saved(self):
            return {'CANCELLED'}
        count = 0
        for ob in _game_texts(context, True):
            cu = ob.data
            if self.language_font:
                cu.use_locale_font = True
            if not cu.locale_key.strip() and cu.body.strip():
                cu.locale_key = self.prefix + slug(cu.body)
                count += 1
        bpy.ops.locale.table_create()
        self.report({'INFO'}, "%d new keys" % count)
        return {'FINISHED'}


class LOCALE_OT_table_open(Operator):
    """Open locale/translations.csv in the Text Editor (Alt+S there saves it). """ \
        """It also opens in Excel/LibreOffice/Google Sheets"""
    bl_idname = "locale.table_open"
    bl_label = "Open Translation Table"

    file = EnumProperty(items=[('CSV', "translations.csv", ""), ('CONFIG', "locale.json", "")], default='CSV')

    def execute(self, context):
        path = csv_path() if self.file == 'CSV' else config_path()
        if not os.path.isfile(path):
            if self.file == 'CONFIG' and bpy.data.filepath:
                write_config(_default_config())
            else:
                self.report({'WARNING'}, "%s not found: press Create first" % path)
                return {'CANCELLED'}
        text, shown = show_in_text_editor(context, path)
        self.report({'INFO'}, "%s %s" % (text.name, "open in the Text Editor" if shown
                                         else "loaded: open a Text Editor to see it"))
        return {'FINISHED'}


class LOCALE_OT_folder_open(Operator):
    """Open the locale folder of the project in the system file browser"""
    bl_idname = "locale.folder_open"
    bl_label = "Open Locale Folder"

    def execute(self, context):
        folder = os.path.dirname(csv_path())
        if not os.path.isdir(folder):
            self.report({'WARNING'}, "%s not found: press Create first" % folder)
            return {'CANCELLED'}
        bpy.ops.wm.path_open(filepath=folder)
        return {'FINISHED'}


def _default_config():
    header, _ = read_table()
    codes = [c for _, c in language_columns(header)] or ["en"]
    return {"base": codes[0],
            "languages": {c: {"name": c, "font": "", "atlas": ""} for c in codes},
            "default": {"font": "", "atlas": ""}}


class LOCALE_OT_atlases_generate(Operator):
    """Bake one bitmap atlas per language with only the letters its column uses """ \
        """(plus digits and punctuation), and set it in locale.json. """ \
        """Texts with Language Font on use it in game"""
    bl_idname = "locale.atlases_generate"
    bl_label = "Generate Language Atlases"
    bl_options = {'REGISTER', 'UNDO'}

    style = EnumProperty(name="Style", items=lambda self, ctx: _style_items())
    size = EnumProperty(
        name="Letter Size",
        items=[('32', "32 px", ""), ('64', "64 px", ""), ('128', "128 px", ""), ('256', "256 px", "")],
        default='64')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .anastacio_text_atlas import STYLE_PADDING, _apply_style
        import math
        if _need_saved(self):
            return {'CANCELLED'}
        header, rows = read_table()
        if not header:
            self.report({'ERROR'}, "No translation table: press Create first")
            return {'CANCELLED'}
        cfg = read_config() or _default_config()
        langs = cfg.setdefault("languages", {})
        ob = context.object
        model = ob.data if ob and ob.type == 'FONT' else None
        size = int(self.size)
        pad = int(math.ceil(STYLE_PADDING.get(self.style, 4) * size / 64.0)) + 2
        made = []
        for col, code in language_columns(header):
            chars = set(ATLAS_BASE_CHARS)
            for r in rows:
                if len(r) > col:
                    chars.update(r[col].replace("\\n", ""))
            chars.discard("\n")
            entry = langs.setdefault(code, {"name": code})
            vfont = bpy.data.fonts.get(entry.get("font") or "") or (model.vfont if model else None)
            name = ATLAS_PREFIX + code
            cu = bpy.data.curves.get(name)
            if cu is None or cu.type != 'FONT':
                cu = bpy.data.curves.new(name, 'FONT')
            cu.use_fake_user = True  # no object uses it: keep it in the .range
            if vfont:
                cu.font = vfont
            old = cu.atlas_image
            image = cu.atlas_bake_font(size=size, padding=pad, chars="".join(sorted(chars)))
            if image is None:
                self.report({'WARNING'}, "%s: could not bake" % code)
                continue
            image.name = "TextAtlas_" + name
            try:
                _apply_style(cu, image, self.style)
            except ImportError:
                pass
            image.pack(as_png=True)
            if old and old != image and old.users == 0:
                bpy.data.images.remove(old)
            if model:
                cu.use_atlas_hard_edge = model.use_atlas_hard_edge
            cu.use_bitmap_atlas = True
            entry["atlas"] = name
            made.append("%s (%d)" % (code, len(cu.atlas_glyphs)))
        write_config(cfg)
        self.report({'INFO'}, "Atlases: " + ", ".join(made))
        return {'FINISHED'}


def _style_items():
    from .anastacio_text_atlas import STYLES
    return [('NONE', "Plain (white)", "White letters, tinted by the object color")] + \
        [(key, v[0], v[1]) for key, v in STYLES.items()]


classes = (
    LOCALE_OT_table_create,
    LOCALE_OT_keys_from_text,
    LOCALE_OT_table_open,
    LOCALE_OT_folder_open,
    LOCALE_OT_atlases_generate,
)
