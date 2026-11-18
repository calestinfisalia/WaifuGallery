import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QApplication, QDialog
from waifu_gallery.models import ImagePost
from waifu_gallery.ui.workers import FileDownloadTask

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

    def test_random_fullscreen_toolbar_renders_as_an_opaque_capsule(self):
        window = self._create_window()
        window._set_ambient_visibility(
            window.random_ambient, window.random_page, True
        )
        toolbar = window.random_fullscreen_toolbar
        toolbar.setGeometry(20, 20, 240, 58)
        toolbar.show()
        toolbar.raise_()
        self.app.processEvents()

        rendered = toolbar.grab().toImage()
        center = rendered.pixelColor(rendered.width() // 2, rendered.height() // 2)
        corner = rendered.pixelColor(0, 0)

        self.assertEqual(center.name(), "#1c1e28")
        self.assertEqual(center.alpha(), 255)
        self.assertLess(corner.alpha(), center.alpha())

    def test_closing_main_window_cancels_downloads_and_clears_queued_work(self):
        window = self._create_window()
        task = FileDownloadTask("download-1", object(), object(), object())
        cancel = Mock(wraps=task.cancel)
        task.cancel = cancel
        window.tasks["download:download-1"] = task
        pool = Mock()
        window.pool = pool

        window.close()

        cancel.assert_called_once_with()
        self.assertTrue(task._cancel_event.is_set())
        pool.clear.assert_called_once_with()

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

    def test_resize_settle_only_renders_visible_image_page(self):
        window = self._create_window()
        self.app.processEvents()
        window.pages.setCurrentWidget(window.detail_page)

        with (
            patch.object(window, "_refresh_ambient_layers") as refresh_ambient,
            patch.object(window.random_image, "_fit_to_viewport") as fit_random,
            patch.object(window.detail_image, "_fit_to_viewport") as fit_detail,
        ):
            window._finish_resize_settle()

        refresh_ambient.assert_called_once_with()
        fit_random.assert_not_called()
        fit_detail.assert_called_once_with()

        window.pages.setCurrentWidget(window.gallery_page)
        with (
            patch.object(window, "_refresh_ambient_layers") as refresh_ambient,
            patch.object(window.random_image, "_fit_to_viewport") as fit_random,
            patch.object(window.detail_image, "_fit_to_viewport") as fit_detail,
        ):
            window._finish_resize_settle()

        refresh_ambient.assert_not_called()
        fit_random.assert_not_called()
        fit_detail.assert_not_called()

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
            patch.object(window, "_detach_native_dialog_owner"),
            patch.object(window, "_raise_native_window"),
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
            patch.object(window, "_detach_native_dialog_owner"),
            patch.object(window, "_raise_native_window"),
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
            patch.object(window, "_raise_native_window") as raise_native,
        ):
            window._open_favorite(post)

        self.assertEqual(events, ["open", "raise", "activate"])
        set_window_state.assert_called_once_with(Qt.WindowState.WindowNoState)
        raise_native.assert_called_once_with(window)
        self.assertFalse(window._opening_favorite)

    def test_only_the_activated_dialog_gets_windows_taskbar_setup_once(self):
        window = self._create_window()
        active_dialog = QDialog(window)
        sibling_dialog = QDialog(window)
        active_dialog.show()
        sibling_dialog.show()

        with (
            patch.object(window, "_uses_native_windows_api", return_value=True),
            patch.object(window, "_detach_native_dialog_owner") as detach_owner,
            patch.object(window, "_show_dialog_in_taskbar") as set_taskbar,
            patch.object(window, "_raise_native_window"),
            patch.object(active_dialog, "isActiveWindow", return_value=True),
        ):
            window._raise_active_app_window(active_dialog)
            window._raise_active_app_window(active_dialog)

        detach_owner.assert_called_once_with(active_dialog)
        set_taskbar.assert_called_once_with(active_dialog)
        self.assertFalse(sibling_dialog.property("_windowsTaskbarConfigured"))

    def test_modeless_dialog_is_configured_before_show_and_restored_when_minimized(self):
        window = self._create_window()
        dialog = QDialog(window)
        events = []

        with (
            patch.object(window, "_uses_native_windows_api", return_value=True),
            patch.object(
                dialog,
                "winId",
                side_effect=lambda: events.append("create-native-window") or 1,
            ),
            patch.object(
                window,
                "_prepare_windows_dialog",
                side_effect=lambda _dialog: events.append("configure-taskbar"),
            ),
            patch.object(
                dialog,
                "windowState",
                return_value=Qt.WindowState.WindowMinimized,
            ),
            patch.object(
                dialog,
                "setWindowState",
                side_effect=lambda _state: events.append("restore"),
            ),
            patch.object(
                dialog,
                "isVisible",
                return_value=False,
            ),
            patch.object(dialog, "show", side_effect=lambda: events.append("show")),
            patch.object(dialog, "raise_", side_effect=lambda: events.append("raise")),
            patch.object(
                dialog,
                "activateWindow",
                side_effect=lambda: events.append("activate"),
            ),
            patch.object(
                window,
                "_raise_native_window",
                side_effect=lambda _window: events.append("raise-native"),
            ),
        ):
            window._show_modeless_dialog(dialog)

        self.assertEqual(
            events,
            [
                "create-native-window",
                "configure-taskbar",
                "restore",
                "show",
                "raise",
                "activate",
                "raise-native",
            ],
        )

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

        self.assertIs(handle.transientParent(), window.windowHandle())

        window._detach_native_dialog_owner(dialog)

        self.assertIsNone(handle.transientParent())

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

    def test_windows_dialog_style_adds_a_taskbar_preview_window(self):
        window = self._create_window()
        dialog = QDialog(window)
        dialog.show()
        self.app.processEvents()
        user32 = Mock()
        user32.GetWindowLongPtrW.return_value = MainWindow._WS_EX_TOOLWINDOW
        user32.SetWindowLongPtrW.return_value = MainWindow._WS_EX_TOOLWINDOW
        user32.SetWindowPos.return_value = 1

        with (
            patch.object(window, "_uses_native_windows_api", return_value=True),
            patch("waifu_gallery.ui.main_window.ctypes.WinDLL", return_value=user32),
        ):
            window._show_dialog_in_taskbar(dialog)

        self.assertEqual(
            user32.SetWindowLongPtrW.call_args.args[1:],
            (
                MainWindow._GWL_EXSTYLE,
                MainWindow._WS_EX_APPWINDOW,
            ),
        )
        self.assertEqual(
            user32.SetWindowPos.call_args.args[-1],
            MainWindow._SWP_NOMOVE
            | MainWindow._SWP_NOSIZE
            | MainWindow._SWP_NOZORDER
            | MainWindow._SWP_NOACTIVATE
            | MainWindow._SWP_FRAMECHANGED,
        )

    def test_windows_native_focus_clears_dialog_owner_and_raises_without_activation(self):
        window = self._create_window()
        dialog = QDialog(window)
        dialog.show()
        self.addCleanup(dialog.close)
        self.app.processEvents()
        user32 = Mock()
        user32.GetWindowLongPtrW.return_value = 456
        user32.SetWindowLongPtrW.return_value = 456
        user32.SetWindowPos.return_value = 1

        with (
            patch.object(window, "_uses_native_windows_api", return_value=True),
            patch("waifu_gallery.ui.main_window.ctypes.WinDLL", return_value=user32),
        ):
            window._detach_native_dialog_owner(dialog)
            window._raise_native_window(window)

        self.assertEqual(user32.SetWindowLongPtrW.call_args.args[1:], (-8, 0))
        raise_args = user32.SetWindowPos.call_args.args
        self.assertIsNone(raise_args[1].value)
        self.assertEqual(
            raise_args[-1],
            MainWindow._SWP_NOSIZE
            | MainWindow._SWP_NOMOVE
            | MainWindow._SWP_NOACTIVATE,
        )


if __name__ == "__main__":
    unittest.main()
