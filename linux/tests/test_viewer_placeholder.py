import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from waifu_gallery.ui.viewer import ZoomImage


class ViewerPlaceholderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_long_placeholder_wraps_to_available_width(self):
        viewer = ZoomImage()
        viewer.resize(320, 120)
        viewer.set_placeholder(
            "Could not load image\n" + "Provider failure | " * 16
        )
        self.app.processEvents()

        self.assertTrue(viewer.wordWrap())
        self.assertGreater(
            viewer.heightForWidth(viewer.width()),
            viewer.fontMetrics().height(),
        )
