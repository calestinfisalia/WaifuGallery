import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QScrollArea

from waifu_gallery.ui.viewer import ZoomImage


class ViewerZoomPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create_viewer(self):
        area = QScrollArea()
        area.resize(420, 300)
        area.setWidgetResizable(False)
        viewer = ZoomImage()
        area.setWidget(viewer)
        viewer.viewport = area.viewport()
        viewer.scroll_area = area
        area.show()
        self.app.processEvents()
        self.addCleanup(area.close)
        return area, viewer

    def test_original_load_retains_zoom_and_pan_after_loading_placeholder(self):
        area, viewer = self._create_viewer()
        viewer.set_image(QPixmap(800, 600))
        viewer.factor = 2.4
        viewer._fit_to_viewport()
        self.app.processEvents()

        horizontal = area.horizontalScrollBar()
        vertical = area.verticalScrollBar()
        horizontal_fraction = 0.35
        vertical_fraction = 0.62
        horizontal.setValue(round(horizontal.maximum() * horizontal_fraction))
        vertical.setValue(round(vertical.maximum() * vertical_fraction))
        self.app.processEvents()

        viewer.set_loading(preserve_zoom=True)
        viewer.set_image(QPixmap(2400, 1800), preserve_zoom=True)
        self.app.processEvents()

        self.assertAlmostEqual(viewer.factor, 2.4)
        self.assertAlmostEqual(
            horizontal.value() / horizontal.maximum(),
            horizontal_fraction,
            delta=0.02,
        )
        self.assertAlmostEqual(
            vertical.value() / vertical.maximum(),
            vertical_fraction,
            delta=0.02,
        )

    def test_original_replacement_retains_zoom_without_loading_placeholder(self):
        area, viewer = self._create_viewer()
        viewer.set_image(QPixmap(800, 600))
        viewer.factor = 1.8
        viewer._fit_to_viewport()
        self.app.processEvents()
        area.verticalScrollBar().setValue(
            round(area.verticalScrollBar().maximum() * 0.4)
        )

        viewer.set_image(QPixmap(2400, 1800), preserve_zoom=True)
        self.app.processEvents()

        self.assertAlmostEqual(viewer.factor, 1.8)
        self.assertAlmostEqual(
            area.verticalScrollBar().value() / area.verticalScrollBar().maximum(),
            0.4,
            delta=0.02,
        )

    def test_identical_fast_resize_does_not_replace_the_rendered_pixmap(self):
        _area, viewer = self._create_viewer()
        viewer.set_image(QPixmap(800, 600))
        viewer._fit_to_viewport(fast=True)

        with patch.object(viewer, "setPixmap", wraps=viewer.setPixmap) as set_pixmap:
            viewer._fit_to_viewport(fast=True)

        set_pixmap.assert_not_called()


if __name__ == "__main__":
    unittest.main()
