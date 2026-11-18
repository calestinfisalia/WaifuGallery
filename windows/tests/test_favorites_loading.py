import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from waifu_gallery.models import ImagePost
from waifu_gallery.ui.favorites import FavoritesDialog
from waifu_gallery.ui.main_window import MainWindow


class FavoritesLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _wait_until(self, predicate, timeout_ms=2000):
        for _ in range(timeout_ms // 20):
            if predicate():
                return True
            QTest.qWait(20)
        return predicate()

    def test_large_favorites_list_builds_after_dialog_is_shown(self):
        posts = [
            ImagePost(
                str(index),
                "provider",
                f"https://example.invalid/{index}.jpg",
                (),
                "safe",
                frozenset(),
            )
            for index in range(70)
        ]
        dialog = FavoritesDialog(posts, lambda _post: None, lambda _key: None)
        self.addCleanup(dialog.close)

        self.assertEqual(dialog.tiles, [])
        dialog.show()
        self.assertTrue(dialog.loading_indicator.isVisible())

        self.assertTrue(self._wait_until(lambda: len(dialog.tiles) == len(posts)))
        self.assertFalse(dialog.loading_indicator.isVisible())

    def test_large_favorites_tiles_are_laid_out_after_build_finishes(self):
        posts = [
            ImagePost(
                str(index),
                "provider",
                f"https://example.invalid/{index}.jpg",
                (),
                "safe",
                frozenset(),
            )
            for index in range(70)
        ]
        dialog = FavoritesDialog(posts, lambda _post: None, lambda _key: None)
        self.addCleanup(dialog.close)
        dialog.show()
        dialog._tile_build_timer.stop()
        dialog._layout_timer.stop()

        with patch.object(dialog, "_layout_tiles", wraps=dialog._layout_tiles) as layout:
            dialog._build_next_tile_batch()
            self.assertTrue(dialog._pending_tile_posts)
            layout.assert_not_called()

            while dialog._pending_tile_posts:
                dialog._build_next_tile_batch()

        layout.assert_called_once_with()
        self.assertEqual(len(dialog.tiles), len(posts))

    def test_favorite_tiles_adapt_to_resized_dialog_width(self):
        posts = [
            ImagePost(
                str(index),
                "provider",
                f"https://example.invalid/{index}.jpg",
                (),
                "safe",
                frozenset(),
            )
            for index in range(8)
        ]
        dialog = FavoritesDialog(posts, lambda _post: None, lambda _key: None)
        self.addCleanup(dialog.close)
        dialog.show()
        self.assertTrue(self._wait_until(lambda: bool(dialog.tiles)))
        first_tile = dialog.tiles[0][1]
        initial_width = first_tile.width()

        dialog.resize(dialog.width() + 100, dialog.height())

        self.assertTrue(
            self._wait_until(lambda: first_tile.width() > initial_width)
        )
        self.assertEqual(dialog.grid.count(), len(posts))
        self.assertIs(dialog.grid.itemAtPosition(0, 0).widget(), first_tile)

    def test_favorite_media_count_is_in_the_footer(self):
        posts = [
            ImagePost(
                "image",
                "provider",
                "https://example.invalid/image.jpg",
                (),
                "safe",
                frozenset(),
            ),
            ImagePost(
                "video",
                "provider",
                "https://example.invalid/video.mp4",
                (),
                "safe",
                frozenset(),
                media_type="video",
            ),
        ]
        dialog = FavoritesDialog(posts, lambda _post: None, lambda _key: None)
        self.addCleanup(dialog.close)

        self.assertEqual(dialog.count_label.text(), "2 media · 1 images · 1 videos")
        self.assertIs(dialog.count_label.parentWidget(), dialog.footer)

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
        self.assertTrue(self._wait_until(lambda: len(requested) > 0))
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
        self.assertTrue(self._wait_until(lambda: len(requested) > initial_count))
        dialog.close()
        QTest.qWait(0)

    def test_favorites_can_switch_between_newest_and_oldest_order(self):
        posts = [
            ImagePost(
                str(index),
                "provider",
                f"https://example.invalid/{index}.jpg",
                (),
                "safe",
                frozenset(),
            )
            for index in range(3)
        ]
        dialog = FavoritesDialog(posts, lambda _post: None, lambda _key: None)
        changed = []
        dialog.sortOrderChanged.connect(changed.append)

        self.assertEqual([post.post_id for post in dialog.posts], ["2", "1", "0"])
        self.assertFalse(dialog.sort_button.isHidden())
        dialog._set_sort_order("oldest")
        self.assertEqual([post.post_id for post in dialog.posts], ["0", "1", "2"])
        self.assertEqual(changed, ["oldest"])
        dialog.set_posts(posts[:2])
        self.assertEqual([post.post_id for post in dialog.posts], ["0", "1"])
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
            "waifu_gallery.ui.favorites.BackupMessageDialog.confirm",
            return_value=True,
        ):
            dialog._delete_selected_favorites()
        with patch(
            "waifu_gallery.ui.favorites.BackupMessageDialog.ask",
            return_value="No",
        ) as confirm_download:
            dialog._download_selected_favorites()
        self.assertEqual(downloaded, [])
        confirm_download.assert_called_once_with(
            dialog,
            "Download selected favorites",
            "Add all 1 selected media to the download queue?",
            ("No", "Yes"),
            default_button="No",
        )
        with patch(
            "waifu_gallery.ui.favorites.BackupMessageDialog.ask",
            return_value="Yes",
        ):
            dialog._download_selected_favorites()

        self.assertEqual(deleted, [["provider:0"]])
        self.assertEqual(downloaded, [["provider:0"]])
        QTest.mouseClick(dialog.select_all_button, Qt.MouseButton.LeftButton)
        self.assertEqual(dialog._selected_favorite_keys(), ["provider:1", "provider:0"])
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
            def __init__(self):
                self.show_calls = 0
                self.raise_calls = 0

            def show(self):
                self.show_calls += 1

            def raise_(self):
                self.raise_calls += 1

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

            def show_downloads(self):
                self.downloads.show()
                self.downloads.raise_()

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
        self.assertEqual(window.downloads.show_calls, 0)
        self.assertEqual(window.downloads.raise_calls, 0)
        self.assertIn("skipped 1 existing or queued files", window.status_bar.message)


if __name__ == "__main__":
    unittest.main()
