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
        with patch("waifu_gallery.suggestion_cache.time.time", return_value=1000):
            SuggestionCache(settings).set("Danbooru", "rei aya", ["rei_ayanami"])
        with patch("waifu_gallery.suggestion_cache.time.time", return_value=1001):
            cache = SuggestionCache(settings)
            self.assertEqual(cache.get("danbooru", "rei_aya"), (["rei_ayanami"], True))
            self.assertIsNone(cache.get("yande.re", "rei_aya"))
        self.assertEqual(len(json.loads(settings.get(SuggestionCache.SETTING_KEY))), 1)

    def test_expired_entries_remain_available_for_offline_use(self):
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
