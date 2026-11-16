import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from waifu_gallery.models import ImagePost
from waifu_gallery.ui.downloads import DownloadsDialog


class MemorySettings:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class DownloadsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_compact_download_row_keeps_app_icon_and_opens_saved_folder(self):
        parent = QWidget()
        icon_pixmap = QPixmap(32, 32)
        icon_pixmap.fill(Qt.GlobalColor.white)
        parent._icon = lambda _name: QIcon(icon_pixmap)
        dialog = DownloadsDialog(parent)
        cancelled = []
        dialog.cancel_requested.connect(cancelled.append)

        with TemporaryDirectory() as folder:
            path = Path(folder) / "media.mp4"
            path.write_bytes(b"data")
            dialog.add_download("download-1", path.name, str(path), "Downloading: media.mp4")

            row = dialog.items.itemWidget(dialog.items.item(0))
            app_icon = row.findChild(QLabel, "downloadItemIcon")
            self.assertIsNotNone(app_icon.pixmap())
            filename, status, progress, action = dialog.records["download-1"]
            self.assertEqual(filename.text(), path.name)
            self.assertEqual(status.text(), "Downloading")
            self.assertFalse(progress.isHidden())
            self.assertEqual(action.objectName(), "downloadCancelButton")
            QTest.mouseClick(action, Qt.MouseButton.LeftButton)
            self.assertEqual(cancelled, ["download-1"])

            dialog.update_download("download-1", f"Saved: {path}")
            self.assertEqual(status.text(), "Saved · 4.0 B")
            self.assertTrue(progress.isHidden())
            self.assertEqual(action.objectName(), "downloadOpenFolderButton")
            with patch(
                "waifu_gallery.ui.downloads.QDesktopServices.openUrl",
                return_value=True,
            ) as open_url:
                QTest.mouseClick(action, Qt.MouseButton.LeftButton)
            self.assertEqual(
                Path(open_url.call_args.args[0].toLocalFile()), Path(folder)
            )

        dialog.close()
        QTest.qWait(0)

    def test_new_download_is_inserted_at_the_top(self):
        dialog = DownloadsDialog()
        self.assertIsNone(dialog.menu_button.menu())
        self.assertEqual((dialog.menu_button.width(), dialog.menu_button.height()), (30, 30))
        dialog.add_download("older", "older.mp4")
        dialog.add_download("newer", "newer.mp4")

        top_row = dialog.items.itemWidget(dialog.items.item(0))
        top_filename = top_row.findChild(QLabel, "downloadFilename")
        self.assertEqual(top_filename.text(), "newer.mp4")

        dialog.close()
        QTest.qWait(0)

    def test_failed_download_can_be_retried_after_restoring_history(self):
        parent = QWidget()
        parent.settings = MemorySettings()
        dialog = DownloadsDialog(parent)
        post = ImagePost(
            post_id="post-1",
            provider="yande.re",
            image_url="https://example.com/image.jpg",
            preview_urls=(),
            rating="s",
            tags=frozenset(),
        )
        dialog.add_download(
            "download-1",
            "image.jpg",
            "image.jpg",
            "Failed: network error",
            post=post,
        )
        retried = []
        dialog.retry_requested.connect(retried.append)
        retry_all = []
        dialog.retry_all_requested.connect(lambda: retry_all.append(True))

        action = dialog.records["download-1"][3]
        self.assertEqual(action.objectName(), "downloadRetryButton")
        QTest.mouseClick(action, Qt.MouseButton.LeftButton)
        self.assertEqual(retried, ["download-1"])
        dialog._update_menu_actions()
        self.assertTrue(dialog.retry_all_action.isVisible())
        dialog.retry_all_action.trigger()
        self.assertEqual(retry_all, [True])

        restored = DownloadsDialog(parent)
        retryable = restored.retryable_downloads()
        self.assertEqual(len(retryable), 1)
        self.assertEqual(retryable[0][0], "download-1")
        self.assertEqual(retryable[0][1].image_url, post.image_url)
        self.assertEqual(str(retryable[0][2]), "image.jpg")

        dialog.close()
        restored.close()
        QTest.qWait(0)


if __name__ == "__main__":
    unittest.main()
