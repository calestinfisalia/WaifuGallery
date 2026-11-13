import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from waifu_gallery.models import ImagePost
from waifu_gallery.ui.favorites import FavoritesDialog
from waifu_gallery.ui.main_window import MainWindow


class FavoritesLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_only_visible_favorites_request_thumbnails(self):
        posts = [
            ImagePost(
                str(index),
                "provider",
                f"https://example.invalid/{index}.jpg",
                (f"https://example.invalid/{index}-preview.jpg",),
                "safe",
                frozenset(),
            )
            for index in range(60)
        ]
        dialog = FavoritesDialog(posts, lambda _post: None, lambda _key: None)
        requested = []
        dialog.thumbnailRequested.connect(requested.append)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        dialog.show()
        QTest.qWait(120)
        initial_count = len(requested)

        self.assertGreater(initial_count, 0)
        self.assertLess(initial_count, len(posts))
        self.assertEqual(
            sum(indicator._timer.isActive() for indicator in dialog.thumbnail_indicators.values()),
            initial_count,
        )

        dialog.scroll.verticalScrollBar().setValue(
            dialog.scroll.verticalScrollBar().maximum()
        )
        QTest.qWait(120)

        self.assertGreater(len(requested), initial_count)
        dialog.close()
        QTest.qWait(0)

    def test_thumbnail_failure_shows_reason_under_warning_icon(self):
        post = ImagePost(
            "1",
            "provider",
            "https://example.invalid/1.jpg",
            ("https://example.invalid/1-preview.jpg",),
            "safe",
            frozenset(),
        )
        dialog = FavoritesDialog([post], lambda _post: None, lambda _key: None)
        key = "provider:1"

        dialog.set_thumbnail_error(key, "The provider request timed out.")

        self.assertIn(key, dialog.thumbnail_errors)
        self.assertEqual(
            dialog.thumbnail_error_views[key].findChild(
                QLabel, "favoriteThumbnailErrorIcon"
            ).text(),
            "!",
        )
        self.assertEqual(dialog.thumbnail_error_labels[key].text(), "Timeout")
        self.assertEqual(
            dialog.thumbnail_error_labels[key].toolTip(),
            "The provider request timed out.",
        )
        dialog.set_thumbnail_error(key, "DNS lookup failed for the provider.")
        self.assertEqual(dialog.thumbnail_error_labels[key].text(), "Network error")
        dialog.close()
        QTest.qWait(0)

    def test_checklist_selects_all_and_emits_bulk_actions(self):
        posts = [
            ImagePost(
                str(index),
                "provider",
                f"https://example.invalid/{index}.jpg",
                (),
                "safe",
                frozenset(),
            )
            for index in range(2)
        ]
        dialog = FavoritesDialog(posts, lambda _post: None, lambda _key: None)
        deleted = []
        downloaded = []
        dialog.deleteSelectedRequested.connect(deleted.append)
        dialog.downloadSelectedRequested.connect(downloaded.append)
        self.assertIsNone(
            dialog.findChild(QPushButton, "favoritesDoneButton")
        )
        dialog._set_selection_mode(True)
        dialog._set_favorite_selected("provider:0", True)

        with patch(
            "waifu_gallery.ui.favorites.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dialog._delete_selected_favorites()
        dialog._download_selected_favorites()

        self.assertEqual(deleted, [["provider:0"]])
        self.assertEqual(downloaded, [["provider:0"]])
        QTest.mouseClick(dialog.select_all_button, Qt.MouseButton.LeftButton)
        self.assertEqual(dialog._selected_favorite_keys(), ["provider:0", "provider:1"])
        self.assertEqual(dialog.selection_count_label.text(), "2 selected")
        self.assertFalse(dialog.delete_selected_button.isHidden())
        self.assertFalse(dialog.download_selected_button.isHidden())
        QTest.mouseClick(dialog.select_all_button, Qt.MouseButton.LeftButton)
        self.assertFalse(dialog._selected_favorites)
        self.assertTrue(dialog.select_all_button.isHidden())
        self.assertTrue(dialog.delete_selected_button.isHidden())
        dialog._set_selection_mode(False)
        self.assertFalse(dialog._selected_favorites)
        dialog.close()
        QTest.qWait(0)

    def test_right_click_menu_downloads_selects_and_removes_favorite(self):
        class FakeAction:
            def __init__(self, text):
                self.text = text

        class FakeMenu:
            selected_index = 1
            last_actions = []

            def __init__(self, _parent):
                self.actions = []
                FakeMenu.last_actions = self.actions

            def addAction(self, text):
                action = FakeAction(text)
                self.actions.append(action)
                return action

            def exec(self, _position):
                return self.actions[self.selected_index]

        post = ImagePost(
            "1",
            "provider",
            "https://example.invalid/1.jpg",
            (),
            "safe",
            frozenset(),
        )
        dialog = FavoritesDialog([post], lambda _post: None, lambda _key: None)
        downloaded = []
        dialog.downloadRequested.connect(downloaded.append)

        with patch("waifu_gallery.ui.favorites.QMenu", FakeMenu):
            self.assertTrue(dialog.select_all_button.isHidden())
            dialog._show_favorite_context_menu("provider:1", QPoint())
            self.assertEqual(FakeMenu.selected_index, 1)
            self.assertEqual(
                [action.text for action in FakeMenu.last_actions],
                ["Download", "Select image", "Remove from favorites"],
            )
            self.assertIn("provider:1", dialog._selected_favorites)
            self.assertFalse(dialog.select_all_button.isHidden())
            self.assertFalse(dialog.selection_checks["provider:1"].isHidden())
            FakeMenu.selected_index = 0
            dialog._show_favorite_context_menu("provider:1", QPoint())
            self.assertEqual(FakeMenu.last_actions[1].text, "Deselect image")

        self.assertEqual(downloaded, ["provider:1"])
        FakeMenu.selected_index = 1
        with patch("waifu_gallery.ui.favorites.QMenu", FakeMenu):
            dialog._show_favorite_context_menu("provider:1", QPoint())
        self.assertFalse(dialog._selected_favorites)
        self.assertTrue(dialog.select_all_button.isHidden())
        removed = []
        with patch.object(dialog, "_confirm_remove", side_effect=removed.append):
            FakeMenu.selected_index = 2
            with patch("waifu_gallery.ui.favorites.QMenu", FakeMenu):
                dialog._show_favorite_context_menu("provider:1", QPoint())
        self.assertEqual(removed, ["provider:1"])
        dialog.close()
        QTest.qWait(0)

    def test_bulk_favorite_download_skips_existing_and_duplicate_paths(self):
        class FakeSettings:
            def __init__(self, folder):
                self.folder = folder

            def get(self, _key, _default=None):
                return self.folder

        class FakeDownloads:
            def show(self):
                pass

            def raise_(self):
                pass

        class FakeStatusBar:
            def showMessage(self, message, _duration):
                self.message = message

        class FakeWindow:
            def __init__(self, folder):
                self.settings = FakeSettings(folder)
                self.tasks = {}
                self.downloads = FakeDownloads()
                self.status_bar = FakeStatusBar()
                self.queued = []

            def _parent_allows_post(self, _post):
                return True

            def _catalog(self):
                return object()

            def _start_download(self, post, path, _catalog):
                self.queued.append((post, path))

            def _default_download_path(self, post):
                return MainWindow._default_download_path(self, post)

            def statusBar(self):
                return self.status_bar

        with TemporaryDirectory() as folder:
            existing = ImagePost(
                "provider-1",
                "provider",
                "https://example.invalid/1.jpg",
                (),
                "safe",
                frozenset(),
            )
            new_post = ImagePost(
                "provider-2",
                "provider",
                "https://example.invalid/2.png",
                (),
                "safe",
                frozenset(),
            )
            (Path(folder) / "waifu_provider-1.jpg").write_bytes(b"already downloaded")
            window = FakeWindow(folder)

            MainWindow._queue_favorite_downloads(
                window, [existing, new_post, new_post]
            )

        self.assertEqual(len(window.queued), 1)
        self.assertEqual(window.queued[0][0], new_post)
        self.assertEqual(window.queued[0][1].name, "waifu_provider-2.png")
        self.assertIn("skipped 1 existing or queued files", window.status_bar.message)


if __name__ == "__main__":
    unittest.main()
