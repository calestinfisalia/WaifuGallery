import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QAbstractAnimation, QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from waifu_gallery.models import ImagePost
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
        self.layer.setPixmap(pixmap)
        self.layer._set_ambient_opacity(1.0)
        self.layer.show()

    def test_new_ambient_image_fades_in(self):
        source = self._pixmap("#ff0000")
        self.layer._ambient_source = source

        self.layer.set_ambient_image(source, visible=True, changed=True)

        self.assertTrue(self.layer._animation.state())
        self._finish_fade_in()
        self.assertAlmostEqual(self.layer.ambient_opacity, 1.0)

    def test_ambient_opacity_is_applied_when_painted(self):
        self.parent.setStyleSheet("background-color: #000000;")
        self.layer.setGeometry(self.parent.rect())
        self.layer.setPixmap(self._pixmap("#ff0000"))
        self.layer._set_ambient_opacity(0.5)
        self.parent.show()
        self.layer.show()
        self.app.processEvents()

        rendered = QImage(self.parent.size(), QImage.Format.Format_ARGB32)
        rendered.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rendered)
        self.parent.render(painter, QPoint())
        painter.end()
        pixel = rendered.pixelColor(self.parent.width() // 2, self.parent.height() // 2)

        self.assertGreater(pixel.red(), 80)
        self.assertLess(pixel.red(), 180)
        self.assertLess(pixel.green(), 20)
        self.assertLess(pixel.blue(), 20)

    def test_image_change_updates_immediately_without_animation(self):
        first = self._pixmap("#ff0000")
        second = self._pixmap("#0000ff")
        self._install_visible_image(first)
        self.layer._ambient_source = second

        self.layer.set_ambient_image(second, visible=True, changed=True)

        self.assertEqual(self.layer.pixmap().cacheKey(), second.cacheKey())
        self.assertEqual(self.layer._animation.state(), QAbstractAnimation.State.Stopped)
        self.assertAlmostEqual(self.layer.ambient_opacity, 1.0)

    def test_hidden_ambient_fades_in_when_shown_again(self):
        source = self._pixmap("#ff0000")
        self._install_visible_image(source)
        self.layer.set_ambient_visible(False)

        self.layer.set_ambient_visible(True)

        self.assertTrue(self.layer.isVisible())
        self.assertTrue(self.layer._animation.state())
        self._finish_fade_in()
        self.assertAlmostEqual(self.layer.ambient_opacity, 1.0)

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
            _set_ambient_visibility=MainWindow._set_ambient_visibility,
        )

        MainWindow._on_image_zoom_changed(
            window,
            QScrollArea(),
            self.layer,
            self.parent,
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
        self.assertAlmostEqual(self.layer.ambient_opacity, 1.0)

    def test_ambient_clears_during_loading_and_recovers_after_images(self):
        class MemorySettings:
            use_doh = False
            doh_endpoint = "https://cloudflare-dns.com/dns-query"
            gelbooru_credentials = ("", "")
            rule34_credentials = ("", "")

            def __init__(self):
                self.ambient_mode = True

            def get(self, _key, default=None):
                return default

            def get_bool(self, _key, default=False):
                return default

            def set(self, _key, _value):
                pass

        settings = MemorySettings()
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
        window.resize(1000, 700)
        window.show()
        QTest.qWait(250)
        window.pages.setCurrentWidget(window.random_page)
        previous_random_ambient = self._pixmap("#00ff00")
        window._set_ambient_image(
            window.random_ambient, previous_random_ambient, window.random_page
        )
        window.show_random()
        self.assertTrue(window.random_ambient.isHidden())
        self.assertTrue(window.random_ambient.pixmap().isNull())
        window.random_post = ImagePost(
            "1", "test", "https://example.invalid/image", (), "s", frozenset()
        )
        preview = self._pixmap("#ff0000")
        window._show_random_image(preview)

        QTest.qWait(AmbientLayer._FADE_DURATION_MS + 50)

        def ambient_pixel(x, y):
            page = window.random_page
            rendered = QImage(page.size(), QImage.Format.Format_ARGB32)
            rendered.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rendered)
            page.render(painter, QPoint())
            painter.end()
            return rendered.pixelColor(x, y)

        page = window.random_page
        preview_background = ambient_pixel(10, page.height() // 2)
        self.assertGreater(preview_background.red(), 0)
        self.assertLess(preview_background.red(), 255)

        viewport = window.random_scroll.viewport()
        full_image = QImage(
            viewport.width() * 2,
            viewport.height() * 2,
            QImage.Format.Format_RGB32,
        )
        full_image.fill(QColor("#00ff00"))
        window._task_succeeded(
            f"full-image:random/{window.request_id}",
            full_image,
        )
        QTest.qWait(50)

        self.assertEqual(window.random_image.size(), viewport.size())

        window.show_random()
        window.random_post = ImagePost(
            "2", "test", "https://example.invalid/next-image", (), "s", frozenset()
        )
        next_image = QPixmap(viewport.width() * 2, viewport.height())
        next_image.fill(QColor("#0000ff"))
        window._show_random_image(next_image)
        QTest.qWait(AmbientLayer._FADE_DURATION_MS + 50)

        next_background_pixel = ambient_pixel(
            window.random_page.width() // 2, 10
        )
        self.assertGreater(next_background_pixel.blue(), 0)
        self.assertLess(next_background_pixel.blue(), 255)
        self.assertEqual(window.random_image.width(), viewport.width())
        self.assertLess(window.random_image.height(), viewport.height())

        settings.ambient_mode = False
        window._apply_ambient_mode()
        settings.ambient_mode = True
        window._apply_ambient_mode()
        QTest.qWait(AmbientLayer._FADE_DURATION_MS + 50)

        toggled_background_pixel = ambient_pixel(
            window.random_page.width() // 2, 10
        )
        self.assertGreater(toggled_background_pixel.blue(), 0)
        self.assertLess(toggled_background_pixel.blue(), 255)

        previous_detail_ambient = self._pixmap("#ffff00")
        window._set_ambient_image(
            window.detail_ambient, previous_detail_ambient, window.detail_page
        )
        detail_post = ImagePost(
            "3", "test", "https://example.invalid/detail", (), "s", frozenset()
        )
        with patch.object(window, "_submit"):
            window.open_post(detail_post)

        self.assertTrue(window.detail_ambient.isHidden())
        self.assertTrue(window.detail_ambient.pixmap().isNull())


if __name__ == "__main__":
    unittest.main()
