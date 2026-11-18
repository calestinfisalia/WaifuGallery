import ctypes
import os
import unittest
from ctypes import wintypes
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

from waifu_gallery.ui.main_window import MainWindow


class MemorySettings:
    def get(self, key, default=None):
        return default

    def get_bool(self, key, default=False):
        return default

    def set(self, key, value):
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

    @property
    def ambient_mode(self):
        return True


class WindowSnapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create_window(self):
        with (
            patch(
                "waifu_gallery.ui.main_window.AppSettings",
                return_value=MemorySettings(),
            ),
            patch.object(MainWindow, "_check_for_startup_update"),
            patch.object(MainWindow, "_enable_windows_snap"),
            patch.object(MainWindow, "_submit"),
        ):
            window = MainWindow()
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()
        return window

    def test_native_window_style_enables_resize_and_maximize_snap(self):
        window = self._create_window()
        user32 = Mock()
        user32.GetWindowLongPtrW.return_value = 0
        user32.SetWindowLongPtrW.return_value = 1
        user32.SetWindowPos.return_value = 1

        with (
            patch.object(window, "_uses_native_windows_api", return_value=True),
            patch("waifu_gallery.ui.main_window.ctypes.WinDLL", return_value=user32),
        ):
            window._enable_windows_snap()

        style_args = user32.SetWindowLongPtrW.call_args.args
        self.assertEqual(style_args[1], MainWindow._GWL_STYLE)
        self.assertEqual(
            style_args[2],
            MainWindow._WS_THICKFRAME | MainWindow._WS_MAXIMIZEBOX,
        )
        self.assertEqual(
            user32.SetWindowPos.call_args.args[-1],
            MainWindow._SWP_NOMOVE
            | MainWindow._SWP_NOSIZE
            | MainWindow._SWP_NOZORDER
            | MainWindow._SWP_NOACTIVATE
            | MainWindow._SWP_FRAMECHANGED,
        )

    def test_maximize_button_uses_native_snap_layout_hit_test(self):
        window = self._create_window()
        message = wintypes.MSG()
        message.message = 0x0084
        point = window.title_bar.maximize_button.mapToGlobal(QPoint(3, 3))

        with patch.object(QCursor, "pos", return_value=point):
            handled, hit_test = window.nativeEvent(
                b"windows_generic_MSG",
                ctypes.addressof(message),
            )

        self.assertTrue(handled)
        self.assertEqual(hit_test, MainWindow._HTMAXBUTTON)


if __name__ == "__main__":
    unittest.main()
