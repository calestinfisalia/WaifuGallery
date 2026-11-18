import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QAbstractAnimation
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from waifu_gallery.ui.main_window import AmbientLayer, MainWindow


class AmbientTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = QWidget()
        self.parent.resize(320, 240)
        self.layer = AmbientLayer(self.parent)
        self.layer.resize(self.parent.size())
        self.parent.show()
        self.layer.show()
        self.addCleanup(self.parent.close)

    @staticmethod
    def _pixmap(color):
        pixmap = QPixmap(32, 24)
        pixmap.fill(QColor(color))
        return pixmap

    def _finish_fade_in(self):
        self.layer._animation.setCurrentTime(self.layer._animation.duration())
        self.app.processEvents()

    def _install_visible_image(self, pixmap):
        self.layer._ambient_source = pixmap
        self.layer._image_label.setPixmap(pixmap)
        self.layer._opacity.setOpacity(1.0)
        self.layer.show()

    def test_new_ambient_image_fades_in(self):
        source = self._pixmap("#ff0000")
        self.layer._ambient_source = source

        self.layer.set_ambient_image(source, visible=True, changed=True)

        self.assertTrue(self.layer._animation.state())
        self._finish_fade_in()
        self.assertAlmostEqual(self.layer._opacity.opacity(), 1.0)

    def test_image_change_updates_immediately_without_animation(self):
        first = self._pixmap("#ff0000")
        second = self._pixmap("#0000ff")
        self._install_visible_image(first)
        self.layer._ambient_source = second

        self.layer.set_ambient_image(second, visible=True, changed=True)

        self.assertEqual(self.layer.pixmap().cacheKey(), second.cacheKey())
        self.assertEqual(self.layer._animation.state(), QAbstractAnimation.State.Stopped)
        self.assertAlmostEqual(self.layer._opacity.opacity(), 1.0)

    def test_hidden_ambient_fades_in_when_shown_again(self):
        source = self._pixmap("#ff0000")
        self._install_visible_image(source)
        self.layer.set_ambient_visible(False)

        self.layer.set_ambient_visible(True)

        self.assertTrue(self.layer.isVisible())
        self.assertTrue(self.layer._animation.state())
        self._finish_fade_in()
        self.assertAlmostEqual(self.layer._opacity.opacity(), 1.0)

    def test_clearing_ambient_hides_immediately(self):
        self._install_visible_image(self._pixmap("#ff0000"))
        self.layer._ambient_source = QPixmap()

        self.layer.set_ambient_image(QPixmap(), visible=False, changed=True)

        self.assertTrue(self.layer.isHidden())
        self.assertTrue(self.layer.pixmap().isNull())
        self.assertEqual(self.layer._animation.state(), QAbstractAnimation.State.Stopped)

    def test_zooming_out_restores_ambient_visibility(self):
        source = self._pixmap("#ff0000")
        self.layer._ambient_source = source
        self.layer.set_ambient_image(source, visible=False, changed=True)
        window = SimpleNamespace(
            _set_zoom_scrollbars=MainWindow._set_zoom_scrollbars,
            _ambient_mode_enabled=lambda: True,
        )

        MainWindow._on_image_zoom_changed(
            window,
            QScrollArea(),
            self.layer,
            False,
        )

        self.assertFalse(self.layer.isHidden())
        self.assertTrue(self.layer._animation.state())

    def test_image_change_interrupts_in_progress_fade_and_updates_immediately(self):
        first = self._pixmap("#ff0000")
        second = self._pixmap("#0000ff")
        self.layer._ambient_source = first
        self.layer.set_ambient_image(first, visible=True, changed=True)
        self.assertTrue(self.layer._animation.state())

        self.layer._ambient_source = second
        self.layer.set_ambient_image(second, visible=True, changed=True)

        self.assertEqual(self.layer.pixmap().cacheKey(), second.cacheKey())
        self.assertEqual(self.layer._animation.state(), QAbstractAnimation.State.Stopped)
        self.assertAlmostEqual(self.layer._opacity.opacity(), 1.0)


if __name__ == "__main__":
    unittest.main()
