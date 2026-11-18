import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QStackedWidget

from waifu_gallery.ui.preferences import PreferencesDialog


class MemorySettings:
    def get(self, key, default=None):
        if key == "search/custom_block_tags":
            return [f"tag_{index}" for index in range(12)]
        return default

    def get_bool(self, _key, default=False):
        return default

    def set(self, _key, _value):
        pass

    def set_many(self, _values):
        pass

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


class SettingsLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_custom_blocked_tags_list_expands_with_settings_window(self):
        dialog = PreferencesDialog(MemorySettings())
        self.addCleanup(dialog.close)
        dialog.resize(960, 640)
        dialog.show()
        self.app.processEvents()

        filters_button = next(
            button for button in dialog.nav_buttons
            if button.text().strip() == "Filters"
        )
        filters_button.click()
        stack = dialog.pages.currentWidget().findChild(
            QStackedWidget, "settingsSubpages"
        )
        custom_tags_button = next(
            button for button in stack.widget(0).findChildren(QPushButton)
            if button.text().strip().startswith("Custom blocked tags\n")
        )
        custom_tags_button.click()
        self.app.processEvents()

        initial_height = dialog.filter_list.height()
        self.assertEqual(dialog.filter_list.verticalScrollBar().maximum(), 0)
        dialog.resize(dialog.width(), dialog.height() + 120)
        self.app.processEvents()

        self.assertGreater(dialog.filter_list.height(), initial_height)
