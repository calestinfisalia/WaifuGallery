import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QApplication, QDialog

from waifu_gallery.models import ImagePost
from waifu_gallery.ui.main_window import MainWindow


class MemorySettings:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def get_bool(self, key, default=False):
        return bool(self.get(key, default))

    def set(self, key, value):
        self.values[key] = value

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

    @property
    def ambient_mode(self):
        return True


class WindowFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create_window(self, settings=None):
        settings = settings or MemorySettings()
        with (
            patch(
                "waifu_gallery.ui.main_window.AppSettings",
                return_value=settings,
            ),
            patch.object(MainWindow, "_check_for_startup_update"),
            patch.object(MainWindow, "_submit"),
        ):
            window = MainWindow()
        self.addCleanup(window.close)
        window.show()
        return window

    def test_main_window_size_is_restored_and_saved_on_close(self):
        settings = MemorySettings()
        settings.set("windows/main/size", QSize(1040, 720))
        window = self._create_window(settings)
        self.assertEqual(window.size(), QSize(1040, 720))

        window.resize(1080, 760)
        window.close()

        self.assertEqual(settings.get("windows/main/size"), QSize(1080, 760))

    def test_main_image_rescales_while_window_is_being_resized(self):
        window = self._create_window()
        self.app.processEvents()
        window.pages.setCurrentWidget(window.random_page)
        window._resize_preview_timer.stop()
        window._resize_settle_timer.stop()

        with patch.object(window.random_image, "_fit_to_viewport") as fit_image:
            current_size = window.size()
            next_size = QSize(current_size.width() + 40, current_size.height() + 40)
            window.resizeEvent(QResizeEvent(next_size, current_size))
            self.assertTrue(window._resize_preview_timer.isActive())
            window._resize_preview_timer.stop()
            window._refresh_resize_preview()

        fit_image.assert_called_once_with(fast=True)

    def test_closing_main_window_closes_visible_dialog_children(self):
        window = self._create_window()
        dialog = QDialog(window)
        dialog.show()
        self.addCleanup(dialog.close)
        self.app.processEvents()
        self.assertTrue(dialog.isVisible())

        window.close()
        self.app.processEvents()

        self.assertFalse(dialog.isVisible())

    def test_active_dialog_and_main_window_are_raised_without_lowering_siblings(self):
        window = self._create_window()
        first_dialog = QDialog(window)
        second_dialog = QDialog(window)
        first_dialog.show()
        second_dialog.show()

        with (
            patch.object(first_dialog, "isActiveWindow", return_value=True),
            patch.object(window, "isActiveWindow", return_value=False),
            patch.object(first_dialog, "raise_") as raise_dialog,
            patch.object(window, "lower") as lower_window,
            patch.object(second_dialog, "lower") as lower_sibling,
        ):
            window._raise_active_app_window(first_dialog)

        raise_dialog.assert_called_once()
        lower_window.assert_not_called()
        lower_sibling.assert_not_called()

        with (
            patch.object(window, "isActiveWindow", return_value=True),
            patch.object(window, "raise_") as raise_window,
            patch.object(first_dialog, "lower") as lower_first,
            patch.object(second_dialog, "lower") as lower_second,
        ):
            window._raise_active_app_window(window)

        raise_window.assert_called_once()
        lower_first.assert_not_called()
        lower_second.assert_not_called()

    def test_favorite_selection_raises_main_window_and_restores_it_from_minimized(self):
        window = self._create_window()
        post = ImagePost(
            "1", "provider", "https://example.invalid/1.jpg", (), "safe", frozenset()
        )
        events = []
        with (
            patch.object(window, "_parent_allows_post", return_value=True),
            patch.object(
                window,
                "open_post",
                side_effect=lambda _post: events.append("open"),
            ),
            patch.object(window, "windowState", return_value=Qt.WindowState.WindowMinimized),
            patch.object(window, "setWindowState") as set_window_state,
            patch.object(window, "raise_", side_effect=lambda: events.append("raise")),
            patch.object(window, "activateWindow", side_effect=lambda: events.append("activate")),
        ):
            window._open_favorite(post)

        self.assertEqual(events, ["open", "raise", "activate"])
        set_window_state.assert_called_once_with(Qt.WindowState.WindowNoState)
        self.assertFalse(window._opening_favorite)

    def test_modeless_dialog_activation_removes_transient_owner(self):
        window = self._create_window()
        dialog = QDialog(window)
        dialog.show()
        self.addCleanup(dialog.close)
        self.app.processEvents()

        handle = dialog.windowHandle()
        handle.setTransientParent(window.windowHandle())
        self.assertIs(handle.transientParent(), window.windowHandle())

        window.eventFilter(dialog, QEvent(QEvent.Type.WindowActivate))

        self.assertIsNone(handle.transientParent())


if __name__ == "__main__":
    unittest.main()
