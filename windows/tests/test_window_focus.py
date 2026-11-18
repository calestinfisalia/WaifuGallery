import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog
from waifu_gallery.models import ImagePost
from waifu_gallery.ui.workers import FileDownloadTask

from waifu_gallery.ui.main_window import HISTORY_QUERY_ROLE, MainWindow


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

    def test_search_tag_fragment_only_replaces_last_comma_separated_term(self):
        prefix, fragment = MainWindow._search_tag_fragment("1girl, rei ayaami")

        self.assertEqual(prefix, "1girl, ")
        self.assertEqual(fragment, "rei_ayaami")

    def test_search_completion_preserves_preceding_terms(self):
        window = self._create_window()
        window.search_input.setText("1girl, rei aya")
        window._on_search_query_edited("1girl, rei aya")
        window._refresh_search_completion_model(
            "1girl, rei aya", ["rei_ayanami"]
        )
        completion = window._search_suggestion_model.item(0).data(
            Qt.ItemDataRole.UserRole
        )
        self.assertEqual(completion, "1girl, rei_ayanami")
        window._search_completer.setCompletionPrefix("1girl, rei_aya")
        self.assertEqual(window._search_completer.completionCount(), 1)
        self.assertEqual(window._search_completer.currentCompletion(), completion)
        with patch.object(window, "load_page") as load_page:
            window._search_completer.activated.emit(completion)

        self.assertEqual(window.search_input.text(), "1girl, rei_ayanami")
        self.assertEqual(window.current_query, "1girl, rei_ayanami")
        load_page.assert_called_once_with(1)

    def test_recent_searches_are_shown_and_repeated_search_moves_to_top(self):
        settings = MemorySettings()
        settings.set(
            "search/recent_queries", ["1girl, rei_ayanami", "asuka"]
        )
        window = self._create_window(settings)
        window.search_input.setFocus()
        self.app.processEvents()

        self.assertEqual(window._search_suggestion_model.rowCount(), 0)
        self.assertFalse(window.search_suggestion_panel.isVisible())
        QTest.mouseClick(
            window.search_input, Qt.MouseButton.LeftButton,
            pos=QPoint(window.search_input.width() // 2, window.search_input.height() // 2),
        )
        self.app.processEvents()
        self.assertEqual(window._search_suggestion_model.rowCount(), 2)
        self.assertTrue(window.search_suggestion_panel.isVisible())

        window.search_input.setText("a")
        window._on_search_query_edited("a")
        self.assertEqual(window._search_suggestion_model.rowCount(), 1)
        self.assertTrue(window.search_suggestion_panel.isVisible())
        self.assertEqual(
            window._search_suggestion_model.item(0).text(), "asuka"
        )
        self.assertFalse(window._search_suggestion_model.item(0).icon().isNull())
        self.assertIn(
            ("history", window.current_theme), window._icon_cache
        )

        window.search_input.setText("asuka")
        with patch.object(window, "load_page"):
            window.start_search()

        self.assertEqual(
            settings.get("search/recent_queries"),
            ["asuka", "1girl, rei_ayanami"],
        )

    def test_search_history_matches_every_query_containing_typed_text(self):
        settings = MemorySettings()
        settings.set(
            "search/recent_queries",
            ["firefly_(honkai_star_rail)", "fischl", "asuka"],
        )
        window = self._create_window(settings)
        window.search_input.setText("f")
        window._on_search_query_edited("f")

        self.assertEqual(window._search_suggestion_model.rowCount(), 2)
        values = {
            window._search_suggestion_model.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(window._search_suggestion_model.rowCount())
        }
        self.assertEqual(values, {"firefly_(honkai_star_rail)", "fischl"})

    def test_suggestion_popup_tracks_the_active_theme_colors(self):
        window = self._create_window()
        popup = window.search_suggestion_panel

        window.change_theme("Light")
        self.assertIn("background-color: #FFFFFF", popup.styleSheet())
        self.assertIn("color: #252B40", popup.styleSheet())

        window.change_theme("OLED Dark")
        self.assertIn("background-color: #101116", popup.styleSheet())

    def test_history_x_button_removes_only_the_clicked_search(self):
        settings = MemorySettings()
        settings.set("search/recent_queries", ["rei_ayanami", "rei_hino"])
        window = self._create_window(settings)
        window.search_input.setText("rei")
        window._on_search_query_edited("rei")
        popup = window._search_suggestion_view
        self.app.processEvents()
        first_row = popup.visualRect(popup.model().index(0, 0))
        remove_point = first_row.topRight() + QPoint(-16, first_row.height() // 2)
        clicked_query = popup.indexAt(remove_point).data(HISTORY_QUERY_ROLE)
        self.assertIn(clicked_query, {"rei_ayanami", "rei_hino"})

        QTest.mouseClick(
            popup.viewport(), Qt.MouseButton.LeftButton, pos=remove_point
        )
        self.app.processEvents()

        self.assertEqual(
            settings.get("search/recent_queries"),
            [query for query in ("rei_ayanami", "rei_hino") if query != clicked_query],
        )
        self.assertEqual(window._search_suggestion_model.rowCount(), 1)
        self.assertEqual(
            window._search_suggestion_model.item(0).data(Qt.ItemDataRole.UserRole),
            settings.get("search/recent_queries")[0],
        )

    def test_async_search_suggestions_open_popup_with_search_icon(self):
        window = self._create_window()
        window.pages.setCurrentWidget(window.random_page)
        self.assertIs(window.pages.currentWidget(), window.random_page)
        window.search_input.setFocus()
        self.app.processEvents()
        window.search_input.setText("charlotta")
        window._on_search_query_edited("charlotta")
        generation = window._search_suggestion_generation

        window._task_succeeded(
            f"tag-suggestions:{generation}",
            ["charlotta_(granblue_fantasy)"],
        )
        self.app.processEvents()

        self.assertEqual(window._search_suggestion_model.rowCount(), 1)
        self.assertTrue(window.search_suggestion_panel.isVisible())
        item = window._search_suggestion_model.item(0)
        self.assertEqual(
            item.data(Qt.ItemDataRole.UserRole),
            "charlotta_(granblue_fantasy)",
        )
        self.assertFalse(item.icon().isNull())
        self.assertIn(("search", window.current_theme), window._icon_cache)
        self.assertEqual(
            window.search_suggestion_panel.width(),
            window.search_input.width(),
        )
        input_bottom = window.search_input.mapToGlobal(
            window.search_input.rect().bottomLeft()
        ).y()
        self.assertGreaterEqual(
            window.search_suggestion_panel.mapToGlobal(QPoint(0, 0)).y(),
            input_bottom + 4,
        )

    def test_empty_search_results_hide_previous_completion_popup(self):
        settings = MemorySettings()
        settings.set("search/recent_queries", ["rei_ayanami"])
        window = self._create_window(settings)
        with patch.object(window.search_input, "hasFocus", return_value=True):
            window._search_suggestions_suppressed = False
            window.search_input.setText("rei")
            window._refresh_search_completion_model("rei", [])
            window._show_search_completion_popup()
            self.app.processEvents()
            self.assertTrue(window.search_suggestion_panel.isVisible())

            query = "eika_(trick_or_treat)_(strinova)"
            window.search_input.setText(query)
            window._on_search_query_edited(query)

        self.assertEqual(window._search_suggestion_model.rowCount(), 0)
        self.assertFalse(window.search_suggestion_panel.isVisible())

    def test_typing_unmatched_query_does_not_leave_blank_popup(self):
        settings = MemorySettings()
        settings.set("search/recent_queries", ["rei_ayanami"])
        window = self._create_window(settings)
        QTest.mouseClick(window.search_input, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        QTest.keyClick(window.search_input, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(window.search_input, "toxikasi kurumi")
        QTest.qWait(20)

        self.assertEqual(window._search_suggestion_model.rowCount(), 0)
        self.assertFalse(window.search_suggestion_panel.isVisible())

    def test_fresh_suggestion_cache_is_shown_without_an_api_request(self):
        settings = MemorySettings()
        window = self._create_window(settings)
        window.search_input.setText("rei aya")
        window._on_search_query_edited("rei aya")
        window._suggestion_cache.set("All", "rei_aya", ["rei_ayanami"])

        with patch.object(window, "_submit") as submit:
            window._request_search_suggestions()

        submit.assert_not_called()
        self.assertEqual(window._search_suggestion_model.rowCount(), 1)
        self.assertEqual(
            window._search_suggestion_model.item(0).data(Qt.ItemDataRole.UserRole),
            "rei_ayanami",
        )
        self.assertEqual(window._search_suggestion_view.sizeHintForRow(0), 34)
        window._dismiss_search_suggestions()
        window.close()
        self.app.processEvents()

    def test_opening_a_search_result_dismisses_suggestion_popup(self):
        window = self._create_window()
        window.search_input.setFocus()
        window._search_suggestions_suppressed = False
        self.app.processEvents()
        window._refresh_search_completion_model("rei", ["rei_ayanami"])
        window._show_search_completion_popup()
        self.assertTrue(window.search_suggestion_panel.isVisible())

        with (
            patch.object(window, "_parent_allows_post", return_value=False),
            patch("waifu_gallery.ui.main_window.BackupMessageDialog.notify"),
        ):
            window.open_post(object())

        self.assertFalse(window.search_suggestion_panel.isVisible())
        self.assertEqual(window._search_suggestion_model.rowCount(), 0)
        window.close()
        self.app.processEvents()

    def test_media_shortcuts_are_enabled_only_for_navigable_detail_view(self):
        window = self._create_window()
        window.search_input.clearFocus()
        window.pages.setCurrentWidget(window.detail_page)

        with patch.object(window, "_detail_has_navigation", return_value=True):
            window._update_keyboard_shortcuts()
            self.assertTrue(window.previous_media_shortcut.isEnabled())
            self.assertTrue(window.next_media_shortcut.isEnabled())
            with patch.object(window, "_swipe_detail") as swipe:
                window._navigate_detail_media(-1)
            swipe.assert_called_once_with(-1)

        window.search_input.setFocus()
        self.app.processEvents()
        self.assertTrue(window.search_input.hasFocus())
        self.assertFalse(window.refresh_shortcut.isEnabled())
        self.assertFalse(window.previous_media_shortcut.isEnabled())

        window.pages.setCurrentWidget(window.random_page)
        window._update_keyboard_shortcuts()
        self.assertFalse(window.previous_media_shortcut.isEnabled())
        self.assertFalse(window.next_media_shortcut.isEnabled())

    def test_typo_correction_is_explicit_and_preserves_other_terms(self):
        window = self._create_window()
        window._show_tag_correction(
            "1girl, rei ayaami", ["rei_ayanami"]
        )

        self.assertTrue(window.search_correction_button.isVisible())
        self.assertEqual(
            window.search_correction_button.text(), "You mean 'rei ayanami'?"
        )
        with patch.object(window, "load_page") as load_page:
            window._apply_search_correction()

        self.assertEqual(window.search_input.text(), "1girl, rei_ayanami")
        self.assertEqual(window.current_query, "1girl, rei_ayanami")
        load_page.assert_called_once_with(1)

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

    def test_main_image_rescales_after_window_resize_settles(self):
        window = self._create_window()
        self.app.processEvents()
        window.pages.setCurrentWidget(window.random_page)
        window._resize_settle_timer.stop()

        with patch.object(window.random_image, "_fit_to_viewport_async") as render_image:
            current_size = window.size()
            next_size = QSize(current_size.width() + 40, current_size.height() + 40)
            window.resizeEvent(QResizeEvent(next_size, current_size))
            self.assertTrue(window._resize_settle_timer.isActive())
            render_image.assert_not_called()
            window._finish_resize_settle()

        render_image.assert_called_once_with(fast=False)

    def test_resize_settle_only_renders_visible_image_page(self):
        window = self._create_window()
        self.app.processEvents()
        window.pages.setCurrentWidget(window.detail_page)

        with (
            patch.object(window, "_refresh_ambient_for_page") as refresh_ambient,
            patch.object(window.random_image, "_fit_to_viewport_async") as fit_random,
            patch.object(window.detail_image, "_fit_to_viewport_async") as fit_detail,
        ):
            window._finish_resize_settle()

        refresh_ambient.assert_called_once_with(window.detail_page, fast=True)
        fit_random.assert_not_called()
        fit_detail.assert_called_once_with(fast=False)

        window.pages.setCurrentWidget(window.gallery_page)
        with (
            patch.object(window, "_refresh_ambient_for_page") as refresh_ambient,
            patch.object(window.random_image, "_fit_to_viewport_async") as fit_random,
            patch.object(window.detail_image, "_fit_to_viewport_async") as fit_detail,
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
