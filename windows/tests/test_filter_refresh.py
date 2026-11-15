import os
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from waifu_gallery.providers import BooruCatalog
from waifu_gallery.settings import AppSettings
from waifu_gallery.ui.main_window import MainWindow


class MemorySettings:
    def __init__(self):
        self.values = {
            "appearance/theme": "Dark",
            "search/provider": "All",
            "search/rating": "sfw",
            "search/media_filter": "image",
            "search/exclude_male": True,
            "search/allow_nsfw": False,
            "search/filter_gore": True,
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


class RegistryStyleSettings(MemorySettings):
    def __init__(self):
        super().__init__()
        self.values = {
            key: str(value).lower() if isinstance(value, bool) else value
            for key, value in self.values.items()
        }

    def get_bool(self, key, default=False):
        value = self.get(key, default)
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes", "on"}
        return bool(value)

    def set_many(self, values):
        self.values.update({
            key: str(value).lower() if isinstance(value, bool) else value
            for key, value in values.items()
        })


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
        window.current_query = "cat"
        window.pages.setCurrentWidget(window.random_page)
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

        for enabled in (True, False):
            if not enabled:
                window.current_query = "cat"
            call_count = window._submit.call_count
            dialog.filter_ai_generated.click()
            request = window._submit.call_args

            self.assertEqual(window._submit.call_count, call_count + 1)
            self.assertTrue(request.args[0].startswith("random:"))
            self.assertEqual(settings.get("search/filter_ai_generated"), enabled)
            self.assertEqual(request.args[1].__self__.filter_ai_generated, enabled)
            self.assertEqual(window.current_query, "")

    def test_content_rule_checkboxes_refresh_search(self):
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

        checkboxes = (
            (dialog.exclude_male, "search/exclude_male"),
            (dialog.allow_nsfw, "search/allow_nsfw"),
            (dialog.filter_gore, "search/filter_gore"),
            (dialog.filter_ai_generated, "search/filter_ai_generated"),
        )
        for checkbox, setting_key in checkboxes:
            with self.subTest(setting=setting_key):
                for _ in range(2):
                    call_count = window._submit.call_count
                    window.current_page = 4
                    checkbox.click()

                    self.assertEqual(window._submit.call_count, call_count + 1)
                    self.assertEqual(window.current_page, 1)
                    self.assertEqual(settings.get_bool(setting_key), checkbox.isChecked())
                    catalog = window._submit.call_args.args[1].__self__
                    self.assertEqual(catalog.exclude_male, settings.get_bool("search/exclude_male"))
                    self.assertEqual(catalog.filter_gore, settings.get_bool("search/filter_gore"))
                    self.assertEqual(
                        catalog.filter_ai_generated,
                        settings.get_bool("search/filter_ai_generated"),
                    )

        window.current_query = ""
        window.pages.setCurrentWidget(window.random_page)
        for checkbox, setting_key in checkboxes:
            with self.subTest(mode="random", setting=setting_key):
                for _ in range(2):
                    call_count = window._submit.call_count
                    checkbox.click()

                    self.assertEqual(window._submit.call_count, call_count + 1)
                    self.assertTrue(window._submit.call_args.args[0].startswith("random:"))
                    self.assertEqual(settings.get_bool(setting_key), checkbox.isChecked())

    def test_custom_block_tag_changes_refresh_the_active_mode(self):
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
        window.pages.setCurrentWidget(window.gallery_page)
        window.open_preferences()
        dialog = window.preferences_dialog
        self.addCleanup(dialog.close)

        filters_button = next(button for button in dialog.nav_buttons if button.text() == "Filters")
        filters_button.click()
        custom_filters = next(
            button
            for button in dialog.findChildren(QPushButton, "settingsSubmenuButton")
            if button.text().strip().startswith("Custom blocked tags")
        )
        custom_filters.click()

        dialog.new_filter.setText("ai-generated")
        dialog.add_filter()
        search_call = window._submit.call_args
        self.assertEqual(window._submit.call_count, 1)
        self.assertEqual(search_call.args[5], 1)
        self.assertEqual(search_call.args[1].__self__.custom_block_tags, {"ai-generated"})

        window.current_query = ""
        window.pages.setCurrentWidget(window.random_page)
        dialog._remove_chip_item(dialog.filter_list, dialog.filter_list.item(0))
        random_call = window._submit.call_args
        self.assertEqual(window._submit.call_count, 2)
        self.assertTrue(random_call.args[0].startswith("random:"))
        self.assertEqual(random_call.args[1].__self__.custom_block_tags, set())

    def test_unchecking_ai_filter_refreshes_using_qsettings_value(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = AppSettings.__new__(AppSettings)
            settings._store = QSettings(
                os.path.join(directory, "settings.ini"),
                QSettings.Format.IniFormat,
            )
            settings.set_many({
                "appearance/theme": "Dark",
                "search/provider": "Danbooru",
                "search/rating": "sfw",
                "search/media_filter": "image",
                "search/exclude_male": False,
                "search/allow_nsfw": True,
                "search/filter_gore": False,
                "search/filter_ai_generated": True,
                "search/custom_block_tags": [],
            })
            with (
                patch("waifu_gallery.ui.main_window.AppSettings", return_value=settings),
                patch.object(MainWindow, "_check_for_startup_update"),
            ):
                window = MainWindow()

            self.addCleanup(window.close)
            window._submit = Mock()
            window.current_query = "ai-generated"
            window.pages.setCurrentWidget(window.gallery_page)
            window.open_preferences()
            dialog = window.preferences_dialog
            self.addCleanup(dialog.close)

            filters_button = next(
                button for button in dialog.nav_buttons if button.text() == "Filters"
            )
            filters_button.click()
            content_rules = next(
                button
                for button in dialog.findChildren(QPushButton, "settingsSubmenuButton")
                if button.text().strip().startswith("Content rules")
            )
            content_rules.click()
            dialog.filter_ai_generated.click()

            self.assertFalse(settings.get_bool("search/filter_ai_generated"))
            self.assertEqual(window._submit.call_count, 1)
            request = window._submit.call_args
            self.assertEqual(request.args[0].split(":", 1)[0], "search")
            self.assertFalse(request.args[1].__self__.filter_ai_generated)

    def test_string_false_settings_stay_unchecked_and_disable_filters(self):
        settings = RegistryStyleSettings()
        settings.values.update({
            "search/exclude_male": "false",
            "search/filter_gore": "false",
            "search/filter_ai_generated": "true",
        })
        with (
            patch("waifu_gallery.ui.main_window.AppSettings", return_value=settings),
            patch.object(MainWindow, "_check_for_startup_update"),
        ):
            window = MainWindow()

        self.addCleanup(window.close)
        window._submit = Mock()
        window.current_query = "ai-generated"
        window.pages.setCurrentWidget(window.gallery_page)
        window.open_preferences()
        dialog = window.preferences_dialog

        filters_button = next(button for button in dialog.nav_buttons if button.text() == "Filters")
        filters_button.click()
        content_rules = next(
            button
            for button in dialog.findChildren(QPushButton, "settingsSubmenuButton")
            if button.text().strip().startswith("Content rules")
        )
        content_rules.click()

        self.assertFalse(dialog.exclude_male.isChecked())
        self.assertFalse(dialog.filter_gore.isChecked())
        self.assertTrue(dialog.filter_ai_generated.isChecked())

        dialog.filter_ai_generated.click()
        self.assertEqual(window._submit.call_count, 1)
        catalog = window._submit.call_args.args[1].__self__
        self.assertFalse(catalog.exclude_male)
        self.assertFalse(catalog.filter_gore)
        self.assertFalse(catalog.filter_ai_generated)
        self.assertEqual(settings.get("search/filter_ai_generated"), "false")

        dialog.close()
        QApplication.processEvents()
        window.open_preferences()
        reopened = window.preferences_dialog
        self.addCleanup(reopened.close)

        filters_button = next(button for button in reopened.nav_buttons if button.text() == "Filters")
        filters_button.click()
        content_rules = next(
            button
            for button in reopened.findChildren(QPushButton, "settingsSubmenuButton")
            if button.text().strip().startswith("Content rules")
        )
        content_rules.click()
        self.assertFalse(reopened.filter_ai_generated.isChecked())

    def test_unchecking_ai_filter_shows_matching_all_provider_results(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = AppSettings.__new__(AppSettings)
            settings._store = QSettings(
                os.path.join(directory, "settings.ini"),
                QSettings.Format.IniFormat,
            )
            settings.set_many({
                "appearance/theme": "Dark",
                "search/provider": "All",
                "search/rating": "sfw",
                "search/media_filter": "image",
                "search/exclude_male": False,
                "search/allow_nsfw": True,
                "search/filter_gore": False,
                "search/filter_ai_generated": True,
                "search/custom_block_tags": [],
            })
            with (
                patch("waifu_gallery.ui.main_window.AppSettings", return_value=settings),
                patch.object(MainWindow, "_check_for_startup_update"),
            ):
                window = MainWindow()

            self.addCleanup(window.close)
            payload = [{
                "id": 901,
                "file_url": "https://danbooru.donmai.us/data/furry-ai.jpg",
                "rating": "s",
                "tags": "1girl furry ai-generated",
            }]

            def submit_search(key, operation, *args, **kwargs):
                if key.startswith("search:"):
                    window._task_succeeded(key, operation(*args))

            window._submit = submit_search
            window.current_query = "furry"
            window.pages.setCurrentWidget(window.gallery_page)
            window.open_preferences()
            dialog = window.preferences_dialog
            self.addCleanup(dialog.close)

            filters_button = next(
                button for button in dialog.nav_buttons if button.text() == "Filters"
            )
            filters_button.click()
            content_rules = next(
                button
                for button in dialog.findChildren(QPushButton, "settingsSubmenuButton")
                if button.text().strip().startswith("Content rules")
            )
            content_rules.click()

            with patch.object(BooruCatalog, "_request_provider_json", return_value=payload):
                dialog.filter_ai_generated.click()
                self.assertEqual(len(window.posts), 1)
                self.assertIn("ai-generated", window.posts[0].tags)

                dialog.filter_ai_generated.click()
                self.assertEqual(window.posts, ())
