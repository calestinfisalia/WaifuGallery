import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QPushButton, QStackedWidget

from waifu_gallery.models import ImagePost
from waifu_gallery.ui.preferences import PreferencesDialog
from waifu_gallery.ui.main_window import MainWindow
from waifu_gallery.suggestion_cache import SuggestionCache


class MemorySettings:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def get_bool(self, key, default=False):
        return bool(self.get(key, default))

    def set(self, key, value):
        self.values[key] = value

    def set_many(self, values):
        self.values.update(values)

    @property
    def gelbooru_credentials(self):
        return "", ""

    @property
    def rule34_credentials(self):
        return "", ""

    @property
    def use_doh(self):
        return False

    @property
    def doh_endpoint(self):
        return "https://cloudflare-dns.com/dns-query"


class FavoriteCacheSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_general_cache_subpage_reports_and_clears_disk_usage(self):
        settings = MemorySettings()
        with patch(
            "waifu_gallery.ui.preferences.favorite_thumbnail_cache_size",
            side_effect=[1024, 0, 0],
        ):
            dialog = PreferencesDialog(settings)
        self.addCleanup(dialog.close)
        general_index = next(
            index for index, button in enumerate(dialog.nav_buttons)
            if button.text().strip() == "General"
        )
        general_page = dialog.pages.widget(general_index)
        stack = general_page.findChild(QStackedWidget, "settingsSubpages")
        cache_button = next(
            button for button in stack.widget(0).findChildren(QPushButton)
            if button.text().strip().startswith("Image cache\n")
        )
        cache_button.click()

        self.assertEqual(stack.currentIndex(), 3)
        self.assertTrue(dialog.image_cache_enabled.isChecked())
        dialog.image_cache_enabled.setChecked(False)
        self.assertFalse(settings.get_bool("favorites/image_cache_enabled", True))
        self.assertEqual(dialog.cache_size_label.text(), "Current image cache: 0.0 KB")
        self.assertFalse(dialog.cache_clear_button.isEnabled())
        with patch(
            "waifu_gallery.ui.preferences.clear_favorite_thumbnail_cache"
        ) as clear_cache:
            dialog._clear_image_cache()
        clear_cache.assert_called_once_with()

    def test_general_search_history_page_lists_and_clears_search_data(self):
        settings = MemorySettings()
        settings.set("search/recent_queries", ["rei_ayanami"])
        SuggestionCache(settings).set("Danbooru", "rei", ["rei_ayanami"])
        with patch(
            "waifu_gallery.ui.preferences.favorite_thumbnail_cache_size",
            return_value=0,
        ):
            dialog = PreferencesDialog(settings)
        self.addCleanup(dialog.close)
        general_index = next(
            index for index, button in enumerate(dialog.nav_buttons)
            if button.text().strip() == "General"
        )
        general_page = dialog.pages.widget(general_index)
        stack = general_page.findChild(QStackedWidget, "settingsSubpages")
        cache_button = next(
            button for button in stack.widget(0).findChildren(QPushButton)
            if button.text().strip().startswith("Keyword cache\n")
        )
        cache_button.click()
        self.assertEqual(dialog.suggestion_cache_list.count(), 1)
        self.assertIn("Danbooru", dialog.suggestion_cache_list.item(0).text())
        dialog.clear_suggestion_cache_button.click()
        self.assertEqual(SuggestionCache(settings).entries(), [])
        self.assertEqual(settings.get("search/recent_queries"), ["rei_ayanami"])

        history_button = next(
            button for button in stack.widget(0).findChildren(QPushButton)
            if button.text().strip().startswith("Search history\n")
        )
        history_button.click()
        self.assertEqual(dialog.recent_history_list.count(), 1)
        dialog.clear_search_history_button.click()
        self.assertEqual(settings.get("search/recent_queries"), [])

    def test_disabled_cache_skips_disk_reads_and_writes(self):
        settings = MemorySettings()
        settings.set("favorites/image_cache_enabled", False)
        with (
            patch("waifu_gallery.ui.main_window.AppSettings", return_value=settings),
            patch.object(MainWindow, "show_random"),
            patch.object(MainWindow, "_check_for_startup_update"),
        ):
            window = MainWindow()
        self.addCleanup(window.close)

        post = ImagePost(
            "1",
            "provider",
            "https://example.invalid/1.jpg",
            ("https://example.invalid/1-preview.jpg",),
            "safe",
            frozenset(),
        )
        dialog = Mock()
        dialog.posts = [post]
        dialog.thumbnail_cache = {}
        dialog.thumbnail_errors = {}
        window.favorites_dialog = dialog
        window.favorites_dialog_token = "test-token"
        window.thumbnail_cache = {}
        window.tasks = {}
        window._favorites_catalog = Mock()
        window._submit = Mock()

        with patch("waifu_gallery.ui.main_window.load_favorite_thumbnail") as load_cache:
            window._request_favorite_thumbnail("test-token", "provider:1")
        load_cache.assert_not_called()
        self.assertFalse(window._submit.call_args.args[-1])

        image = object()
        with (
            patch.object(window, "_fetch_preview", return_value=b"preview"),
            patch("waifu_gallery.ui.main_window.decode_image_bytes", return_value=image),
            patch("waifu_gallery.ui.main_window.save_favorite_thumbnail") as save_cache,
        ):
            result = window._fetch_decoded_favorite_thumbnail(
                post, window._favorites_catalog, cache_enabled=False
            )
        self.assertIs(result, image)
        save_cache.assert_not_called()

    def test_favorite_cache_is_loaded_in_the_thumbnail_worker(self):
        settings = MemorySettings()
        with (
            patch("waifu_gallery.ui.main_window.AppSettings", return_value=settings),
            patch.object(MainWindow, "show_random"),
            patch.object(MainWindow, "_check_for_startup_update"),
        ):
            window = MainWindow()
        self.addCleanup(window.close)

        post = ImagePost(
            "1",
            "provider",
            "https://example.invalid/1.jpg",
            ("https://example.invalid/1-preview.jpg",),
            "safe",
            frozenset(),
        )
        dialog = Mock()
        dialog.posts = [post]
        dialog.thumbnail_cache = {}
        dialog.thumbnail_errors = {}
        window.favorites_dialog = dialog
        window.favorites_dialog_token = "test-token"
        window.thumbnail_cache = {}
        window.tasks = {}
        window._favorites_catalog = Mock()
        window._submit = Mock()

        with patch("waifu_gallery.ui.main_window.load_favorite_thumbnail") as load_cache:
            window._request_favorite_thumbnail("test-token", "provider:1")
        load_cache.assert_not_called()

        cached_image = QImage(2, 2, QImage.Format.Format_ARGB32)
        with (
            patch(
                "waifu_gallery.ui.main_window.load_favorite_thumbnail",
                return_value=cached_image,
            ) as load_cache,
            patch.object(window, "_fetch_preview") as fetch_preview,
        ):
            result = window._fetch_decoded_favorite_thumbnail(
                post, window._favorites_catalog, cache_enabled=True
            )

        self.assertIs(result, cached_image)
        load_cache.assert_called_once_with(
            "provider:1", "https://example.invalid/1-preview.jpg"
        )
        fetch_preview.assert_not_called()
