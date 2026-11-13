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

from waifu_gallery.ui.downloads import DownloadsDialog


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
        dialog.add_download("older", "older.mp4")
        dialog.add_download("newer", "newer.mp4")

        top_row = dialog.items.itemWidget(dialog.items.item(0))
        top_filename = top_row.findChild(QLabel, "downloadFilename")
        self.assertEqual(top_filename.text(), "newer.mp4")

        dialog.close()
        QTest.qWait(0)


if __name__ == "__main__":
    unittest.main()
