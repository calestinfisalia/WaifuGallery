import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QStackedWidget

from waifu_gallery.ui.preferences import PreferencesDialog


class MemorySettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, _key, default=None):
        return self.values.get(_key, default)

    def get_bool(self, key, default=False):
        value = self.get(key, default)
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes", "on"}
        return bool(value)

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


class BackupSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_backup_restore_has_separate_export_and_import_pages(self):
        dialog = PreferencesDialog(MemorySettings())
        self.addCleanup(dialog.close)

        page_index = next(
            index
            for index, button in enumerate(dialog.nav_buttons)
            if button.text().replace("&&", "&").strip() == "Backup & Restore"
        )
        page = dialog.pages.widget(page_index)
        stack = page.findChild(QStackedWidget, "settingsSubpages")
        self.assertIsNotNone(stack)
        self.assertEqual(stack.count(), 3)

        import_menu_button = next(
            button
            for button in stack.widget(0).findChildren(QPushButton)
            if button.text().strip().startswith("Import\n")
        )
        import_menu_button.click()

        self.assertEqual(stack.currentIndex(), 2)
        self.assertTrue(
            any(
                "Restore or merge a saved backup" in label.text()
                for label in stack.widget(2).findChildren(QLabel)
            )
        )

    def test_filters_separate_custom_tags_and_parse_saved_false_values(self):
        settings = MemorySettings({
            "search/exclude_male": "false",
            "search/allow_nsfw": "false",
            "search/filter_gore": "false",
            "search/filter_ai_generated": "false",
        })
        dialog = PreferencesDialog(settings)
        self.addCleanup(dialog.close)

        page_index = next(
            index
            for index, button in enumerate(dialog.nav_buttons)
            if button.text().strip() == "Filters"
        )
        stack = dialog.pages.widget(page_index).findChild(
            QStackedWidget, "settingsSubpages"
        )
        self.assertIsNotNone(stack)
        self.assertEqual(stack.count(), 4)
        self.assertFalse(dialog.exclude_male.isChecked())
        self.assertFalse(dialog.allow_nsfw.isChecked())
        self.assertFalse(dialog.filter_gore.isChecked())
        self.assertFalse(dialog.filter_ai_generated.isChecked())
