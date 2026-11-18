"""Persistent, independent cache for provider tag suggestions."""

from __future__ import annotations

import json
import time
from hashlib import sha256


class SuggestionCache:
    """Store autocomplete results in the app's existing QSettings store."""

    SETTING_KEY = "search/suggestion_cache"
    TTL_SECONDS = 24 * 60 * 60
    MAX_ENTRIES = 256

    def __init__(self, settings) -> None:
        self.settings = settings

    @staticmethod
    def _entry_key(provider: str, prefix: str) -> str:
        identity = f"{provider.casefold()}\n{prefix.strip().replace(' ', '_').casefold()}"
        return sha256(identity.encode("utf-8")).hexdigest()

    def _read_entries(self) -> dict:
        raw = self.settings.get(self.SETTING_KEY, "{}")
        try:
            entries = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            return {}
        return entries if isinstance(entries, dict) else {}

    @staticmethod
    def _updated_at(entry) -> float:
        if not isinstance(entry, dict):
            return 0.0
        try:
            return float(entry.get("updated_at", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def get(self, provider: str, prefix: str) -> tuple[list[str], bool] | None:
        entry = self._read_entries().get(self._entry_key(provider, prefix))
        if not isinstance(entry, dict):
            return None
        suggestions = entry.get("suggestions")
        updated_at = entry.get("updated_at")
        if not isinstance(suggestions, list) or not all(
            isinstance(item, str) for item in suggestions
        ):
            return None
        try:
            age = time.time() - float(updated_at)
        except (TypeError, ValueError):
            return None
        return suggestions, 0 <= age < self.TTL_SECONDS

    def entries(self) -> list[dict]:
        values = [
            dict(entry, cache_key=key)
            for key, entry in self._read_entries().items()
            if isinstance(entry, dict)
            and isinstance(entry.get("prefix"), str)
            and isinstance(entry.get("provider"), str)
            and isinstance(entry.get("suggestions"), list)
        ]
        return sorted(values, key=self._updated_at, reverse=True)

    def set(self, provider: str, prefix: str, suggestions: list[str]) -> None:
        entries = self._read_entries()
        key = self._entry_key(provider, prefix)
        entries[key] = {
            "provider": provider,
            "prefix": prefix.strip().replace(" ", "_").casefold(),
            "suggestions": [item for item in suggestions if isinstance(item, str)],
            "updated_at": time.time(),
        }
        if len(entries) > self.MAX_ENTRIES:
            ordered = sorted(
                entries.items(),
                key=lambda item: self._updated_at(item[1]),
                reverse=True,
            )
            entries = dict(ordered[:self.MAX_ENTRIES])
        self.settings.set(self.SETTING_KEY, json.dumps(entries, ensure_ascii=False))

    def clear(self) -> None:
        self.settings.set(self.SETTING_KEY, "{}")
