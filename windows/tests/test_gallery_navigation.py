import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from waifu_gallery.ui.main_window import MainWindow


class MemorySettings:
    def get(self, key, default=None):
        return default

    def get_bool(self, key, default=False):
        return default

    def set(self, key, value):
        pass

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


class GalleryNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_pagination_label_and_controls_fit_at_minimum_window_size(self):
        with (
            patch("waifu_gallery.ui.main_window.AppSettings", return_value=MemorySettings()),
            patch.object(MainWindow, "_check_for_startup_update"),
            patch.object(MainWindow, "_submit"),
        ):
            window = MainWindow()
        self.addCleanup(window.close)
        window.resize(860, 600)
        window.page_label.setText("Page 123 | 50 results")
        window.show()
        self.app.processEvents()
        window.pages.setCurrentWidget(window.gallery_page)
        self.app.processEvents()

        self.assertGreaterEqual(
            window.page_label.width(),
            window.page_label.sizeHint().width(),
        )
        self.assertGreaterEqual(
            window.page_label.height(),
            window.page_label.sizeHint().height(),
        )
        status_bar = window.statusBar()
        self.assertIs(window.footer_widget.parentWidget(), status_bar)
        self.assertIs(window.page_navigation.parentWidget(), window.footer_widget)
        self.assertTrue(window.footer_widget.rect().contains(window.page_navigation.geometry()))
        center_offset = abs(
            window.footer_widget.x()
            + window.page_navigation.geometry().center().x()
            - status_bar.width() // 2
        )
        self.assertLessEqual(center_offset, 12)
        self.assertLessEqual(window.page_navigation.height(), window.footer_widget.height())
        self.assertTrue(window.page_navigation.isVisible())

        window.pages.setCurrentWidget(window.random_page)
        self.assertTrue(window.page_navigation.isHidden())
        window.pages.setCurrentWidget(window.gallery_page)
        self.assertFalse(window.page_navigation.isHidden())

    def test_footer_height_stays_stable_when_image_status_message_shows(self):
        with (
            patch("waifu_gallery.ui.main_window.AppSettings", return_value=MemorySettings()),
            patch.object(MainWindow, "_check_for_startup_update"),
            patch.object(MainWindow, "_submit"),
        ):
            window = MainWindow()
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window.pages.setCurrentWidget(window.gallery_page)
        self.app.processEvents()
        footer_height = window.statusBar().height()
        window.pages.setCurrentWidget(window.detail_page)
        window.statusBar().showMessage("Image loaded", 3000)
        self.app.processEvents()

        self.assertEqual(window.statusBar().height(), footer_height)
        self.assertEqual(
            window.footer_widget.height(),
            window.page_navigation.minimumHeight(),
        )


if __name__ == "__main__":
    unittest.main()
