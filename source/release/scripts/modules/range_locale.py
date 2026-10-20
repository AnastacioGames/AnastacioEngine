# Range.locale: game localization (translation table + language font/atlas).
#
# Project files (next to the .range):
#   locale/translations.csv   key,en,pt-BR,es,ru,...   (UTF-8; one row per key, one column per language)
#   locale/locale.json        optional: base language, language names, font/atlas per language
#
# Text objects with a Translation Key show the current language by themselves; texts with
# "Language Font" on also take the font/atlas of the language. In scripts:
#   Range.locale.language = "ru"
#   Range.locale.tr("hud.lap", lap=2, total=3)     # "Volta {lap} de {total}" -> "Volta 2 de 3"

import csv
import json
import os
import sys
import types

CSV_PATH = "//locale/translations.csv"
CONFIG_PATH = "//locale/locale.json"
SAVE_KEY = "locale.language"  # in Range.logic.globalDict, saved with it by the game

_IGNORED_COLUMNS = {"context", "note", "notes", "comment", "comments"}

# native names used when locale.json does not give one
NATIVE_NAMES = {
    "en": "English", "en-US": "English (US)", "en-GB": "English (UK)",
    "pt": "Português", "pt-BR": "Português (Brasil)", "pt-PT": "Português (Portugal)",
    "es": "Español", "es-419": "Español (Latinoamérica)", "fr": "Français", "de": "Deutsch",
    "it": "Italiano", "ru": "Русский", "uk": "Українська", "pl": "Polski", "tr": "Türkçe",
    "nl": "Nederlands", "sv": "Svenska", "cs": "Čeština", "ja": "日本語", "ko": "한국어",
    "zh": "中文", "zh-CN": "简体中文", "zh-TW": "繁體中文", "zh-Hans": "简体中文",
    "zh-Hant": "繁體中文", "ar": "العربية", "hi": "हिन्दी", "id": "Bahasa Indonesia",
    "th": "ไทย", "vi": "Tiếng Việt", "el": "Ελληνικά", "hu": "Magyar", "ro": "Română",
}


def native_name(code):
    code = normalize(code)
    return NATIVE_NAMES.get(code) or NATIVE_NAMES.get(code.split("-")[0]) or code

_state = {
    "base": "en",
    "languages": [],      # column order of the CSV
    "names": {},          # code -> native name
    "fonts": {},          # code -> {"font": str, "atlas": str}
    "rows": {},           # key -> {code: text}
    "language": "",
    "loaded": False,
}
onChange = []  # callbacks fn(code) after the language changes


def _logic():
    import Range
    return Range.logic


def _path(rel):
    try:
        return _logic().expandPath(rel)
    except Exception:
        return rel


def normalize(code):
    """'pt_br' / 'PT-BR' -> 'pt-BR' (BCP 47 style)."""
    parts = str(code).replace("_", "-").split("-")
    out = [parts[0].lower()]
    for p in parts[1:]:
        out.append(p.upper() if len(p) == 2 else p.title() if len(p) == 4 else p)
    return "-".join(p for p in out if p)


def _read_csv(path):
    rows, languages = {}, []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = None
        for row in reader:
            if not row or not row[0].strip() or row[0].lstrip().startswith("#"):
                continue
            if header is None:
                header = [c.strip() for c in row]
                for c in header[1:]:
                    if c and not c.startswith("_") and c.lower() not in _IGNORED_COLUMNS:
                        languages.append(normalize(c))
                    else:
                        languages.append(None)
                continue
            key = row[0].strip()
            texts = rows.setdefault(key, {})
            for code, text in zip(languages, row[1:]):
                if code and text != "":
                    texts[code] = text.replace("\\n", "\n")
    return rows, [c for c in languages if c]


def reload():
    """Read locale/translations.csv and locale/locale.json again."""
    s = _state
    s["rows"], s["languages"] = {}, []
    path = _path(CSV_PATH)
    if os.path.isfile(path):
        try:
            s["rows"], s["languages"] = _read_csv(path)
        except Exception as ex:
            print("Range.locale: could not read %s: %s" % (path, ex))
    cfg = {}
    path = _path(CONFIG_PATH)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8-sig") as f:
                cfg = json.load(f)
        except Exception as ex:
            print("Range.locale: could not read %s: %s" % (path, ex))
    langs = {normalize(k): v for k, v in (cfg.get("languages") or {}).items()}
    s["base"] = normalize(cfg.get("base") or (s["languages"][0] if s["languages"] else "en"))
    s["names"] = {k: v.get("name") for k, v in langs.items() if isinstance(v, dict) and v.get("name")}
    s["fonts"] = {k: {"font": v.get("font", ""), "atlas": v.get("atlas", "")}
                  for k, v in langs.items() if isinstance(v, dict)}
    default = cfg.get("default") or {}
    s["fonts"]["*"] = {"font": default.get("font", ""), "atlas": default.get("atlas", "")}
    for code in langs:
        if code not in s["languages"]:
            s["languages"].append(code)
    s["loaded"] = True


def _chain(code):
    """Fallback order: pt-BR -> pt -> base language."""
    out = [code]
    if "-" in code:
        out.append(code.split("-")[0])
    if _state["base"] not in out:
        out.append(_state["base"])
    return out


def _lookup(key, code):
    texts = _state["rows"].get(key)
    if texts:
        for c in _chain(code):
            if c in texts:
                return texts[c]
        # region-less column for a regional request (pt -> pt-BR)
        prefix = code.split("-")[0]
        for c, t in texts.items():
            if c.split("-")[0] == prefix:
                return t
    return None


def tr(key, **fmt):
    """Text of key in the current language (falls back to the base language, then the key)."""
    text = _lookup(key, _state["language"])
    if text is None:
        text = key
    if fmt:
        try:
            text = text.format(**fmt)
        except (KeyError, IndexError, ValueError):
            pass
    return text


get = tr


def has(key):
    return key in _state["rows"]


def _push():
    code = _state["language"]
    table = {}
    for key in _state["rows"]:
        text = _lookup(key, code)
        if text is not None:
            table[key] = text
    fonts = _state["fonts"]
    entry = fonts.get(code) or fonts.get(code.split("-")[0]) or fonts.get("*") or {}
    try:
        _logic()._setLocale(table, entry.get("font", "") or "", entry.get("atlas", "") or "")
    except Exception as ex:
        print("Range.locale: %s" % ex)


def _match(code):
    """Best available language for code (exact, same language other region, or None)."""
    if not code:
        return None
    code = normalize(code)
    langs = _state["languages"]
    if code in langs:
        return code
    prefix = code.split("-")[0]
    for c in langs:
        if c.split("-")[0] == prefix:
            return c
    return None


def system_language():
    """Language of the operating system as BCP 47 ('pt-BR'), or '' when unknown."""
    try:
        if sys.platform == "win32":
            import ctypes
            import locale as _pylocale
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            name = _pylocale.windows_locale.get(lcid, "")
        else:
            name = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
        name = name.split(".")[0].split("@")[0]
        return normalize(name) if name and name not in ("C", "POSIX") else ""
    except Exception:
        return ""


def set_language(code, save=True):
    found = _match(code) or normalize(code)
    _state["language"] = found
    if save:
        try:
            _logic().globalDict[SAVE_KEY] = found
        except Exception:
            pass
    _push()
    for fn in list(onChange):
        try:
            fn(found)
        except Exception as ex:
            print("Range.locale.onChange: %s" % ex)
    return found


def name(code=None):
    """Native name of a language ('Português'), from locale.json, else the code."""
    code = normalize(code) if code else _state["language"]
    found = _state["names"].get(code)
    return found if found and found != code else native_name(code)


def step(offset=1):
    """Go to the next (1) or previous (-1) language of the table; returns the new code."""
    langs = _state["languages"]
    if not langs:
        return _state["language"]
    try:
        i = langs.index(_state["language"])
    except ValueError:
        i = 0 if offset > 0 else 1
    return set_language(langs[(i + offset) % len(langs)])


def _sensors_ok(cont):
    return all(s.positive for s in cont.sensors) if cont.sensors else True


# Python controller in Module mode, no script needed: range_locale.next / range_locale.previous
def next(cont=None):
    if cont is None or _sensors_ok(cont):
        return step(1)


def previous(cont=None):
    if cont is None or _sensors_ok(cont):
        return step(-1)


def _start():
    """Called by the engine when a game starts."""
    del onChange[:]
    reload()
    try:
        saved = _logic().globalDict.get(SAVE_KEY)
    except Exception:
        saved = None
    code = _match(saved) or _match(system_language()) or _match(_state["base"]) or _state["base"]
    _state["language"] = code
    if _state["rows"] or _state["fonts"]:
        _push()


class _LocaleModule(types.ModuleType):
    @property
    def language(self):
        """Current language code (BCP 47, e.g. 'pt-BR'). Setting it updates every translated text."""
        return _state["language"]

    @language.setter
    def language(self, code):
        set_language(code)

    @property
    def languages(self):
        """Language codes of the translation table, in column order."""
        return list(_state["languages"])

    @property
    def baseLanguage(self):
        return _state["base"]

    @property
    def systemLanguage(self):
        return system_language()

    @property
    def keys(self):
        return list(_state["rows"])


sys.modules[__name__].__class__ = _LocaleModule
