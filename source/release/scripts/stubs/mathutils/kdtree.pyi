"""Stubs gerados de text_autocomplete_api.json (tools/autocomplete/gerar_stubs.py). Nao edite."""
from typing import Any, Generic, Iterator, TypeVar


class KDTree:
    def balance(self) -> Any:
        """Balance the tree."""
    def find(self, co, filter=None) -> tuple:
        """Find nearest point to ``co``."""
    def find_n(self, co, n) -> Any:
        """Find nearest ``n`` points to ``co``."""
    def find_range(self, co, radius) -> Any:
        """Find all points within ``radius`` of ``co``."""
    def insert(self, co, index) -> Any:
        """Insert a point into the KDTree."""

