# Editor side of Range.locale (scripts/modules/range_locale.py): translation table in
# //locale/translations.csv, per-language font/atlas in //locale/locale.json.

import csv
import json
import os
import re

import bpy
from bpy.types import Operator
from bpy.app.handlers import persistent
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
    _stats_cache["key"] = None
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
    import unicodedata
    s = unicodedata.normalize("NFKD", text.strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
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
            "languages": {c: {"name": range_locale.native_name(c), "font": "", "atlas": ""} for c in codes},
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
            if cu is None or not isinstance(cu, bpy.types.TextCurve):
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


# ---------------------------------------------------------------------------
# Simple flow: Enable Languages -> Translate All Texts -> write the translations ->
# Language Button. Everything below works on the same CSV/JSON as the operators above.

COMMON_LANGUAGES = ["en", "pt-BR", "es", "fr", "de", "it", "ru", "ja", "ko", "zh-CN", "pl", "tr"]

_stats_cache = {"key": None, "value": None}


def table_stats():
    """{'languages', 'keys', 'missing': {code: n}, 'rows'} of the CSV (cached by mtime)."""
    path = csv_path()
    try:
        st = os.stat(path)
        key = (path, st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    if _stats_cache["key"] != key:
        rows, langs = range_locale._read_csv(path)
        missing = {c: sum(1 for t in rows.values() if not t.get(c)) for c in langs}
        _stats_cache["key"] = key
        _stats_cache["value"] = {"languages": langs, "keys": len(rows), "missing": missing,
                                 "rows": rows}
    return _stats_cache["value"]


def texts_without_key(scene):
    return [ob for ob in scene.objects
            if ob.type == 'FONT' and not ob.data.locale_key.strip() and ob.data.body.strip()
            and not any(c.module == "range_language" for c in ob.game.components)]


def _language_items(self, context):
    items = [(c, "%s (%s)" % (range_locale.native_name(c), c), "") for c in COMMON_LANGUAGES]
    return items + [('OTHER', "Other...", "Type any language code (BCP 47)")]


def _system_common():
    code = range_locale.system_language()
    if code in COMMON_LANGUAGES:
        return code
    prefix = code.split("-")[0]
    return next((c for c in COMMON_LANGUAGES if c.split("-")[0] == prefix), "en")


def _ensure_config_languages(codes):
    cfg = read_config() or {}
    langs = cfg.setdefault("languages", {})
    for c in codes:
        e = langs.setdefault(c, {})
        e.setdefault("name", range_locale.native_name(c))
        e.setdefault("font", "")
        e.setdefault("atlas", "")
    cfg.setdefault("base", codes[0] if codes else "en")
    cfg.setdefault("default", {"font": "", "atlas": ""})
    write_config(cfg)


class LOCALE_OT_enable(Operator):
    """Turn on game languages for this project: creates the locale folder with the """ \
        """translation table (one column per language) next to the .range"""
    bl_idname = "locale.enable"
    bl_label = "Enable Languages"
    bl_options = {'REGISTER', 'UNDO'}

    base = EnumProperty(name="Texts are written in", items=_language_items,
                        description="Language of the texts already in the scene")
    second = EnumProperty(name="Translate to", items=_language_items,
                          description="First translation; add more later with Add Language")
    translate_all = BoolProperty(name="Prepare all texts of the scene", default=True,
                                 description="Give every text a Translation Key and put it in the table")

    def invoke(self, context, event):
        self.base = _system_common()
        self.second = "en" if self.base != "en" else "pt-BR"
        return context.window_manager.invoke_props_dialog(self, width=320)

    def execute(self, context):
        if _need_saved(self):
            return {'CANCELLED'}
        codes = []
        for c in (self.base, self.second):
            if c != 'OTHER' and c not in codes:
                codes.append(c)
        header, rows = read_table()
        if not header:
            header = ["key"] + (codes or ["en"]) + ["context"]
            write_table(header, rows)
        _ensure_config_languages([c for _, c in language_columns(header)])
        if self.translate_all:
            bpy.ops.locale.translate_all()
        self.report({'INFO'}, "Languages on: %s" % ", ".join(c for _, c in language_columns(header)))
        return {'FINISHED'}


class LOCALE_OT_language_add(Operator):
    """Add a language column to the translation table"""
    bl_idname = "locale.language_add"
    bl_label = "Add Language"
    bl_options = {'REGISTER', 'UNDO'}

    language = EnumProperty(name="Language", items=_language_items)
    code = StringProperty(name="Code", description="Only for Other: e.g. nl, sv, pt-PT, es-419")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "language")
        if self.language == 'OTHER':
            self.layout.prop(self, "code")

    def execute(self, context):
        code = self.code.strip() if self.language == 'OTHER' else self.language
        if not code:
            self.report({'ERROR'}, "Type the language code")
            return {'CANCELLED'}
        code = range_locale.normalize(code)
        header, rows = read_table()
        if not header:
            self.report({'ERROR'}, "Press Enable Languages first")
            return {'CANCELLED'}
        cols = language_columns(header)
        if code in [c for _, c in cols]:
            self.report({'INFO'}, "%s is already in the table" % code)
            return {'CANCELLED'}
        # new column right after the last language (before context / notes)
        at = cols[-1][0] + 1 if cols else 1
        header.insert(at, code)
        for r in rows:
            while len(r) < at:
                r.append("")
            r.insert(at, "")
        write_table(header, rows)
        _ensure_config_languages([code])
        self.report({'INFO'}, "%s added: write its texts in the table" % range_locale.native_name(code))
        return {'FINISHED'}


class LOCALE_OT_language_remove(Operator):
    """Remove this language column (and its translations) from the table"""
    bl_idname = "locale.language_remove"
    bl_label = "Remove Language"
    bl_options = {'REGISTER', 'UNDO'}

    code = StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        header, rows = read_table()
        cols = dict((c, i) for i, c in language_columns(header))
        if self.code not in cols or len(cols) < 2:
            self.report({'WARNING'}, "The table needs at least one language")
            return {'CANCELLED'}
        i = cols[self.code]
        del header[i]
        for r in rows:
            if len(r) > i:
                del r[i]
        write_table(header, rows)
        cfg = read_config()
        if cfg.get("languages", {}).pop(self.code, None) is not None:
            write_config(cfg)
        return {'FINISHED'}


def _unique_key(base, used):
    key, n = base, 2
    while key in used:
        key = "%s_%d" % (base, n)
        n += 1
    used.add(key)
    return key


class LOCALE_OT_translate_all(Operator):
    """Prepare every text of the scene for translation in one click: gives each text """ \
        """without a key a Translation Key, turns on Language Font and puts its text in the table"""
    bl_idname = "locale.translate_all"
    bl_label = "Translate All Texts"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if _need_saved(self):
            return {'CANCELLED'}
        apply_preview('OFF')
        header, rows = read_table()
        if not header:
            self.report({'ERROR'}, "Press Enable Languages first")
            return {'CANCELLED'}
        cols = language_columns(header)
        base_col = cols[0][0] if cols else 1
        by_text = {}
        for r in rows:
            if r and len(r) > base_col and r[base_col]:
                by_text.setdefault(r[base_col], r[0].strip())
        used = {r[0].strip() for r in rows if r}
        keyed = 0
        for ob in texts_without_key(context.scene):
            cu = ob.data
            if cu.locale_key.strip():
                continue  # same data used by another object, done already
            cu.use_locale_font = True
            body = cu.body.replace("\n", "\\n")
            key = by_text.get(body)  # same text already in the table: one translation for both
            if key is None:
                key = _unique_key(slug(cu.body), used)
                row = [""] * len(header)
                row[0] = key
                row[base_col] = body
                rows.append(row)
                by_text[body] = key
            cu.locale_key = key
            keyed += 1
        for ob in _game_texts(context, False):
            if ob.data.locale_key:
                ob.data.use_locale_font = True
        write_table(header, rows)
        bpy.ops.locale.table_create()  # keys typed by hand that are not in the table yet
        context.scene.locale_preview = 'OFF'
        self.report({'INFO'}, "%d texts ready for translation" % keyed)
        return {'FINISHED'}


class LOCALE_OT_button_add(Operator):
    """Make the active object a language button: a click on it goes to the next language """ \
        """and, on a text, it shows the language name. No script needed"""
    bl_idname = "locale.button_add"
    bl_label = "Add Language Button"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        ob = context.object
        if any(c.module == "range_language" for c in ob.game.components):
            self.report({'INFO'}, "%s already has a Language Button" % ob.name)
            return {'CANCELLED'}
        override = context.copy()
        override.update(object=ob, active_object=ob)
        result = bpy.ops.logic.python_component_register(override,
                                                         component_name="range_language.LanguageButton")
        if 'FINISHED' not in result:
            self.report({'ERROR'}, "Could not add the Language Button")
            return {'CANCELLED'}
        if ob.type == 'FONT':
            # the button shows the language name, not a translated text
            ob.data.locale_key = ""
            ob.data.use_locale_font = True
        self.report({'INFO'}, "Language Button added: a click switches the language "
                              "(Game > Components to change it)")
        return {'FINISHED'}


GUIDE = """GAME LANGUAGES - quick guide
============================

1. Scene > Localization > Enable Languages
   Choose the language your texts are written in and the first translation.
   It creates the folder locale/ next to the .range with translations.csv
   and already prepares every text of the scene.

2. Translate All Texts
   Run it again after adding new texts: they get a Translation Key and go
   into the table. Texts with the same words share one translation.

3. Write the translations
   Open Table opens translations.csv here (Alt+S saves) - or open the file
   in Excel / LibreOffice / Google Sheets: one row per text, one column per
   language. Empty cell = shows the first language.
   Preview Language (in the panel) shows the texts in that language in the
   viewport; the file always keeps the original.

4. Language menu in the game
   Select a text and press Add Language Button: a click on it switches to
   the next language and it shows the language name. Nothing else to do.
   The choice is saved; the first time, the game uses the system language.

5. Letters the font does not have (Russian, Japanese...)
   Generate Atlases bakes the letters of each language. For another font in
   one language, set "font" in locale.json (Open Config).

In scripts (optional):
   Range.locale.language = "pt-BR"
   Range.locale.tr("hud.lap", lap=2, total=3)   # cell text "Lap {lap} of {total}"
   Range.locale.next()                          # next language
   Logic bricks: Python controller, Module mode: range_locale.next
"""


class LOCALE_OT_guide(Operator):
    """Show the step by step guide of game languages"""
    bl_idname = "locale.guide"
    bl_label = "Languages Guide"

    def execute(self, context):
        text = bpy.data.texts.get("Languages_Guide.txt") or bpy.data.texts.new("Languages_Guide.txt")
        text.from_string(GUIDE)
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.spaces.active.text = text
                return {'FINISHED'}

        # no Text Editor on screen: show it in a popup
        def draw(menu, ctx):
            for line in GUIDE.splitlines()[2:]:
                menu.layout.label(text=line)
        context.window_manager.popup_menu(draw, title="Game Languages", icon='WORLD')
        return {'FINISHED'}


# --- viewport preview: texts in one language; the .range always keeps the original ---

BASE_PROP = "_locale_base_body"


def _restore_bodies():
    for cu in bpy.data.curves:
        if isinstance(cu, bpy.types.TextCurve) and BASE_PROP in cu:
            cu.body = cu[BASE_PROP]
            del cu[BASE_PROP]


def apply_preview(code):
    _restore_bodies()
    stats = table_stats() if bpy.data.filepath else None
    if not code or code == 'OFF' or not stats:
        return 0
    rows = stats["rows"]
    count = 0
    for cu in bpy.data.curves:
        if not isinstance(cu, bpy.types.TextCurve) or not cu.locale_key or cu.locale_key not in rows:
            continue
        texts = rows[cu.locale_key]
        text = texts.get(code) or texts.get(code.split("-")[0])
        if text is None or text == cu.body:
            continue
        cu[BASE_PROP] = cu.body
        cu.body = text
        count += 1
    return count


def _preview_items(self, context):
    items = [('OFF', "Original", "Texts as written")]
    stats = table_stats() if bpy.data.filepath else None
    for c in (stats["languages"] if stats else []):
        items.append((c, range_locale.native_name(c), c))
    return items


def _preview_update(self, context):
    apply_preview(self.locale_preview)


_saved_preview = []


@persistent
def _save_pre(*args):
    # never save the preview text
    scene = bpy.context.scene
    _saved_preview[:] = [scene.locale_preview] if scene else []
    _restore_bodies()


@persistent
def _save_post(*args):
    if _saved_preview and _saved_preview[0] != 'OFF':
        apply_preview(_saved_preview[0])


@persistent
def _load_post(*args):
    _restore_bodies()
    for sc in bpy.data.scenes:
        if "locale_preview" in sc:
            del sc["locale_preview"]


_HANDLERS = (("save_pre", _save_pre), ("save_post", _save_post), ("load_post", _load_post))


def register_props():
    bpy.types.Scene.locale_preview = EnumProperty(
        name="Preview Language", items=_preview_items, update=_preview_update,
        description="Show the texts in this language in the viewport (the file keeps the original)")
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        if fn not in lst:
            lst.append(fn)


def unregister_props():
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        if fn in lst:
            lst.remove(fn)
    del bpy.types.Scene.locale_preview


classes = (
    LOCALE_OT_enable,
    LOCALE_OT_language_add,
    LOCALE_OT_language_remove,
    LOCALE_OT_translate_all,
    LOCALE_OT_button_add,
    LOCALE_OT_guide,
    LOCALE_OT_table_create,
    LOCALE_OT_keys_from_text,
    LOCALE_OT_table_open,
    LOCALE_OT_folder_open,
    LOCALE_OT_atlases_generate,
)
