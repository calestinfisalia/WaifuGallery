import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QImage

from waifu_gallery import favorite_cache


class FavoriteThumbnailCacheTests(unittest.TestCase):
    def test_saves_loads_sizes_removes_and_clears_cached_images(self):
        image = QImage(12, 8, QImage.Format.Format_ARGB32)
        image.fill(0xFF336699)
        with TemporaryDirectory() as directory:
            with patch.object(
                QStandardPaths, "writableLocation", return_value=directory
            ):
                favorite_cache.save_favorite_thumbnail(
                    "Danbooru:123", "https://example.invalid/preview.jpg", image
                )
                loaded = favorite_cache.load_favorite_thumbnail(
                    "Danbooru:123", "https://example.invalid/preview.jpg"
                )
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.size(), image.size())
                self.assertGreater(favorite_cache.favorite_thumbnail_cache_size(), 0)
                self.assertIsNone(favorite_cache.load_favorite_thumbnail(
                    "Danbooru:123", "https://example.invalid/changed.jpg"
                ))

                favorite_cache.remove_favorite_thumbnail(
                    "Danbooru:123", "https://example.invalid/preview.jpg"
                )
                self.assertEqual(favorite_cache.favorite_thumbnail_cache_size(), 0)
                favorite_cache.save_favorite_thumbnail(
                    "yande.re:456", "https://example.invalid/other.jpg", image
                )
                favorite_cache.clear_favorite_thumbnail_cache()
                self.assertEqual(favorite_cache.favorite_thumbnail_cache_size(), 0)
                self.assertFalse(
                    (Path(directory) / "favorite-thumbnails").exists()
                )
