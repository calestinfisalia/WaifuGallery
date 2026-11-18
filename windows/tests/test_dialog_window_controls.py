import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from waifu_gallery.models import ImagePost
from waifu_gallery.ui.credits import ImageCreditsDialog
from waifu_gallery.ui.dialog_chrome import FramelessResizableDialog
from waifu_gallery.ui.downloads import DownloadsDialog
from waifu_gallery.ui.favorites import FavoritesDialog
from waifu_gallery.ui.preferences import PreferencesDialog


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
    def ambient_mode(self):
        return True

    @property
    def doh_endpoint(self):
        return "https://cloudflare-dns.com/dns-query"


class DialogWindowControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_primary_dialogs_have_working_minimize_buttons(self):
        parent = QWidget()
        parent.settings = MemorySettings()
        parent.show()
        self.addCleanup(parent.close)
        post = ImagePost("1", "test", "", (), "s", frozenset())
        dialogs = [
            FavoritesDialog([], lambda _post: None, lambda _post: None, parent),
            DownloadsDialog(parent),
            PreferencesDialog(parent.settings, parent),
            ImageCreditsDialog(post, parent),
        ]
        for dialog in dialogs:
            self.addCleanup(dialog.close)
            dialog.show()
            self.app.processEvents()
            minimize = dialog.findChild(QPushButton, "dialogMinimizeButton")
            self.assertIsNotNone(minimize)
            minimize.click()
            self.app.processEvents()
            self.assertTrue(dialog.isMinimized(), dialog.windowTitle())

    def test_remembered_dialog_size_restores_after_recreation(self):
        parent = QWidget()
        parent.settings = MemorySettings()
        parent.show()
        self.addCleanup(parent.close)
        key = "windows/favoritesDialog/size"
        first = FramelessResizableDialog(parent)
        first.setObjectName("favoritesDialog")
        first.resize(900, 700)
        first.show()
        self.app.processEvents()
        first.reject()
        self.app.processEvents()

        self.assertEqual(parent.settings.get(key), QSize(900, 700))

        second = FramelessResizableDialog(parent)
        second.setObjectName("favoritesDialog")
        second.resize(820, 620)
        second.show()
        self.app.processEvents()
        self.addCleanup(second.close)

        self.assertEqual(second.size(), QSize(900, 700))

    def test_dynamic_children_get_resize_tracking_without_rescanning_the_dialog(self):
        dialog = FramelessResizableDialog()
        dialog.show()
        self.app.processEvents()
        self.addCleanup(dialog.close)

        with patch.object(dialog, "_install_resize_filters") as rescan:
            child = QWidget(dialog)
            self.app.processEvents()

        rescan.assert_not_called()
        self.assertTrue(child.hasMouseTracking())


if __name__ == "__main__":
    unittest.main()
