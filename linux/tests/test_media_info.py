import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QGridLayout, QScrollArea, QToolButton

from waifu_gallery.models import ImagePost
from waifu_gallery.ui.credits import ImageCreditsDialog


class MediaInfoTagLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_tags_are_arranged_in_two_columns(self):
        tags = frozenset(f"tag_{index}" for index in range(5))
        post = ImagePost(
            post_id="1",
            provider="danbooru",
            image_url="",
            preview_urls=(),
            rating="s",
            tags=tags,
        )
        dialog = ImageCreditsDialog(post)
        self.addCleanup(dialog.close)

        scroll = dialog.findChild(QScrollArea, "mediaInfoScrollArea")
        self.assertIsNotNone(scroll)
        layout = scroll.widget().layout()
        self.assertIsInstance(layout, QGridLayout)
        buttons = scroll.widget().findChildren(QToolButton)

        self.assertEqual(layout.columnCount(), 2)
        self.assertEqual(
            [
                layout.getItemPosition(layout.indexOf(button))[:2]
                for button in buttons
            ],
            [(index // 2, index % 2) for index in range(len(tags))],
        )
