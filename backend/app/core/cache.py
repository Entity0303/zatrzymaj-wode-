"""Prosty cache w pamięci z czasem ważności (TTL) – wspólny dla źródeł danych.

Źródła publiczne bywają wolne i mają limity zapytań, dlatego każde źródło trzyma
ostatnie odpowiedzi przez określony czas. TODO: trwały cache w SQLite (CLAUDE.md – Stack).
"""

import time
from collections import OrderedDict
from typing import Generic, Hashable, TypeVar

V = TypeVar("V")


class TTLCache(Generic[V]):
    def __init__(self, ttl_s: float, max_items: int = 512):
        self.ttl_s = ttl_s
        self.max_items = max_items
        self._data: OrderedDict[Hashable, tuple[float, V]] = OrderedDict()

    def get(self, key: Hashable) -> V | None:
        hit = self._data.get(key)
        if hit is None:
            return None
        stored_at, value = hit
        if time.monotonic() - stored_at >= self.ttl_s:
            del self._data[key]
            return None
        return value

    def set(self, key: Hashable, value: V) -> None:
        self._data[key] = (time.monotonic(), value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_items:
            self._data.popitem(last=False)  # najstarszy wpis

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
