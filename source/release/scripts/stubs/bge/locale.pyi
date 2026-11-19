"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar


CONFIG_PATH: str
CSV_PATH: str
NATIVE_NAMES: dict
SAVE_KEY: str
def get() -> Any:
    """Text of key in the current language (falls back to the base language, then the key)."""
def has() -> Any:
    ...
def name() -> Any:
    """Native name of a language ('Português'), from locale.json, else the code."""
def native_name() -> Any:
    ...
def next() -> Any:
    ...
def normalize() -> Any:
    """'pt_br' / 'PT-BR' -> 'pt-BR' (BCP 47 style)."""
onChange: list[Any]
def previous() -> Any:
    ...
def reload() -> Any:
    """Read locale/translations.csv and locale/locale.json again."""
def set_language() -> Any:
    ...
def step() -> Any:
    """Go to the next (1) or previous (-1) language of the table; returns the new code."""
def system_language() -> Any:
    """Language of the operating system as BCP 47 ('pt-BR'), or '' when unknown."""
def tr() -> Any:
    """Text of key in the current language (falls back to the base language, then the key)."""
