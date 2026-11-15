import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from waifu_gallery.ui.main_window import MainWindow


class MemorySettings:
    def __init__(self):
        self.values = {
            "appearance/theme": "Dark",
            "search/provider": "All",
            "search/rating": "sfw",
            "search/media_filter": "image",
            "search/filter_ai_generated": False,
        }

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
    def ambient_mode(self):
        return True

    @property
    def doh_endpoint(self):
        return "https://cloudflare-dns.com/dns-query"


class FilterRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ai_filter_toggle_reloads_search_from_first_page(self):
        settings = MemorySettings()
        with (
            patch("waifu_gallery.ui.main_window.AppSettings", return_value=settings),
            patch.object(MainWindow, "show_random"),
            patch.object(MainWindow, "_check_for_startup_update"),
        ):
            window = MainWindow()

        self.addCleanup(window.close)
        window._submit = Mock()
        window.current_query = "cat"
        window.current_page = 3
        window.pages.setCurrentWidget(window.gallery_page)
        window.open_preferences()
        dialog = window.preferences_dialog
        self.addCleanup(dialog.close)

        filters_button = next(button for button in dialog.nav_buttons if button.text() == "Filters")
        filters_button.click()
        content_rules = next(
            button
            for button in dialog.findChildren(QPushButton, "settingsSubmenuButton")
            if button.text().strip().startswith("Content rules")
        )
        content_rules.click()

        dialog.filter_ai_generated.click()
        enabled_call = window._submit.call_args
        self.assertTrue(settings.get("search/filter_ai_generated"))
        self.assertEqual(window.current_page, 1)
        self.assertEqual(enabled_call.args[5], 1)
        self.assertTrue(enabled_call.args[1].__self__.filter_ai_generated)

        window.current_page = 4
        dialog.filter_ai_generated.click()
        disabled_call = window._submit.call_args
        self.assertFalse(settings.get("search/filter_ai_generated"))
        self.assertEqual(window.current_page, 1)
        self.assertEqual(disabled_call.args[5], 1)
        self.assertFalse(disabled_call.args[1].__self__.filter_ai_generated)

    def test_ai_filter_toggle_refreshes_random_with_current_filter(self):
        settings = MemorySettings()
        with (
            patch("waifu_gallery.ui.main_window.AppSettings", return_value=settings),
            patch.object(MainWindow, "show_random"),
            patch.object(MainWindow, "_check_for_startup_update"),
        ):
            window = MainWindow()

        self.addCleanup(window.close)
        window._submit = Mock()
        window.open_preferences()
        dialog = window.preferences_dialog
        self.addCleanup(dialog.close)

        filters_button = next(button for button in dialog.nav_buttons if button.text() == "Filters")
        filters_button.click()
        content_rules = next(
            button
            for button in dialog.findChildren(QPushButton, "settingsSubmenuButton")
            if button.text().strip().startswith("Content rules")
        )
        content_rules.click()

        dialog.filter_ai_generated.click()
        enabled_call = window._submit.call_args
        self.assertTrue(enabled_call.args[0].startswith("random:"))
        self.assertTrue(settings.get("search/filter_ai_generated"))
        self.assertTrue(enabled_call.args[1].__self__.filter_ai_generated)

        dialog.filter_ai_generated.click()
        disabled_call = window._submit.call_args
        self.assertEqual(window._submit.call_count, 2)
        self.assertFalse(settings.get("search/filter_ai_generated"))
        self.assertFalse(disabled_call.args[1].__self__.filter_ai_generated)
