import json
import unittest
from unittest.mock import patch

from waifu_gallery.suggestion_cache import SuggestionCache


class MemorySettings:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class SuggestionCacheTests(unittest.TestCase):
    def test_persists_suggestions_by_provider_and_prefix(self):
        settings = MemorySettings()
        cache = SuggestionCache(settings)
        with patch("waifu_gallery.suggestion_cache.time.time", return_value=1000):
            cache.set("Danbooru", "rei aya", ["rei_ayanami"])

        restored_cache = SuggestionCache(settings)
        with patch("waifu_gallery.suggestion_cache.time.time", return_value=1001):
            self.assertEqual(
                restored_cache.get("danbooru", "rei_aya"),
                (["rei_ayanami"], True),
            )
            self.assertIsNone(restored_cache.get("yande.re", "rei_aya"))

        saved = json.loads(settings.get(SuggestionCache.SETTING_KEY))
        self.assertEqual(len(saved), 1)

    def test_expired_suggestions_remain_available_for_offline_fallback(self):
        settings = MemorySettings()
        cache = SuggestionCache(settings)
        with patch("waifu_gallery.suggestion_cache.time.time", return_value=1000):
            cache.set("All", "rei", ["rei_ayanami"])
        with patch(
            "waifu_gallery.suggestion_cache.time.time",
            return_value=1000 + SuggestionCache.TTL_SECONDS,
        ):
            self.assertEqual(cache.get("All", "rei"), (["rei_ayanami"], False))


if __name__ == "__main__":
    unittest.main()
