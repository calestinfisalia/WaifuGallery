import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from waifu_gallery.models import ImagePost
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

    def test_search_history_appears_when_the_user_clicks_the_search_bar(self):
        settings = MemorySettings()
        settings.set("search/recent_queries", ["rei_ayanami", "asuka"])
        window = self._create_window(settings)
        window.search_input.setFocus()
        self.app.processEvents()
        self.assertFalse(window.search_suggestion_panel.isVisible())

        QTest.mouseClick(
            window.search_input,
            Qt.MouseButton.LeftButton,
            pos=QPoint(window.search_input.width() // 2, window.search_input.height() // 2),
        )
        self.app.processEvents()
        self.assertTrue(window.search_suggestion_panel.isVisible())
        self.assertEqual(window._search_suggestion_model.rowCount(), 2)

        window.search_input.setText("a")
        window._on_search_query_edited("a")
        self.assertTrue(window.search_suggestion_panel.isVisible())
        self.assertEqual(window._search_suggestion_model.rowCount(), 1)
        self.assertEqual(window._search_suggestion_model.item(0).text(), "asuka")

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

    def test_clicking_history_x_removes_only_that_entry(self):
        settings = MemorySettings()
        settings.set("search/recent_queries", ["rei_ayanami", "rei_hino"])
        window = self._create_window(settings)
        window.search_input.setText("rei")
        window._on_search_query_edited("rei")
        popup = window._search_suggestion_view
        self.app.processEvents()
        row = popup.visualRect(popup.model().index(0, 0))
        point = QPoint(row.right() - 23, row.center().y())
        selected_query = popup.indexAt(point).data(HISTORY_QUERY_ROLE)
        self.assertIn(selected_query, {"rei_ayanami", "rei_hino"})

        QTest.mouseClick(popup.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.app.processEvents()

        remaining = [
            item for item in ("rei_ayanami", "rei_hino")
            if item != selected_query
        ]
        self.assertEqual(settings.get("search/recent_queries"), remaining)
        self.assertEqual(window._search_suggestion_model.rowCount(), 1)

    def test_clicking_suggestion_starts_search(self):
        window = self._create_window()
        window.search_input.setText("1girl, rei aya")
        window._on_search_query_edited("1girl, rei aya")
        window._refresh_search_completion_model(
            "1girl, rei aya", ["rei_ayanami"]
        )
        completion = window._search_suggestion_model.item(0).data(
            Qt.ItemDataRole.UserRole
        )
        with patch.object(window, "load_page") as load_page:
            window._search_completer.activated.emit(completion)
        self.assertEqual(window.current_query, "1girl, rei_ayanami")
        load_page.assert_called_once_with(1)

    def test_suggestion_cache_is_used_without_an_api_request(self):
        window = self._create_window()
        window._suggestion_cache.set("All", "rei_aya", ["rei_ayanami"])
        window.search_input.setText("rei aya")
        window._on_search_query_edited("rei aya")
        with patch.object(window, "_submit") as submit:
            window._request_search_suggestions()
        submit.assert_not_called()
        self.assertEqual(window._search_suggestion_model.rowCount(), 1)

    def test_suggestion_popup_colors_follow_the_theme(self):
        window = self._create_window()
        popup = window.search_suggestion_panel
        window.change_theme("Light")
        self.assertIn("background-color: #FFFFFF", popup.styleSheet())
        window.change_theme("OLED Dark")
        self.assertIn("background-color: #101116", popup.styleSheet())

    def test_main_window_size_is_restored_and_saved_on_close(self):
        settings = MemorySettings()
        settings.set("windows/main/size", QSize(1040, 720))
        window = self._create_window(settings)
        self.assertEqual(window.size(), QSize(1040, 720))

        window.resize(1080, 760)
        window.close()

        self.assertEqual(settings.get("windows/main/size"), QSize(1080, 760))

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
