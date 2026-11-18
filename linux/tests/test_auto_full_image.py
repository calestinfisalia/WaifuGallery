import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from waifu_gallery.models import ImagePost
from waifu_gallery.ui.main_window import MainWindow
from waifu_gallery.ui.preferences import PreferencesDialog


class MemorySettings:
    def __init__(self, auto_load=False):
        self.values = {"view/auto_load_full_image": auto_load}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def get_bool(self, key, default=False):
        return bool(self.get(key, default))

    def set(self, key, value):
        self.values[key] = value

    def set_many(self, values):
        self.values.update(values)

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


class AutoFullImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _create_window(self, settings):
        with (
            patch("waifu_gallery.ui.main_window.AppSettings", return_value=settings),
            patch.object(MainWindow, "_check_for_startup_update"),
            patch.object(MainWindow, "_submit"),
        ):
            window = MainWindow()
        self.addCleanup(window.close)
        return window

    @staticmethod
    def _post():
        return ImagePost(
            "1",
            "provider",
            "https://example.invalid/original.jpg",
            ("https://example.invalid/preview.jpg",),
            "s",
            frozenset(),
        )

    def test_auto_load_setting_is_saved_and_defaults_off(self):
        settings = MemorySettings()
        dialog = PreferencesDialog(settings)
        self.addCleanup(dialog.close)

        self.assertFalse(dialog.auto_load_full_image.isChecked())
        dialog.auto_load_full_image.setChecked(True)
        self.assertTrue(settings.get_bool("view/auto_load_full_image"))

    def test_image_size_footer_uses_load_full_size_label_and_dimensions_only(self):
        post = ImagePost(
            "1",
            "provider",
            "https://example.invalid/original.jpg",
            ("https://example.invalid/preview.jpg",),
            "s",
            frozenset(),
            width=1754,
            height=1240,
        )
        preview = QPixmap(640, 480)
        full = QPixmap(1754, 1240)

        self.assertEqual(
            MainWindow._image_size_text(post, preview),
            "Preview 640 x 480",
        )
        self.assertEqual(
            MainWindow._image_size_text(post, preview, auto_load=True),
            "Preview 640 x 480 | Load full size...",
        )
        self.assertEqual(
            MainWindow._image_size_text(post, full, full=True),
            "1754 x 1240",
        )

    def test_manual_footer_shows_only_preview_resolution(self):
        settings = MemorySettings()
        window = self._create_window(settings)
        post = ImagePost(
            "1",
            "provider",
            "https://example.invalid/original.jpg",
            ("https://example.invalid/preview.jpg",),
            "s",
            frozenset(),
            width=1754,
            height=1240,
        )
        window.random_post = post
        window.pages.setCurrentWidget(window.random_page)
        preview = QPixmap(640, 480)

        window._set_random_image_footer(post, preview)
        self.assertEqual(
            window.footer_meta.text(),
            "provider | Safe | Preview 640 x 480",
        )
        self.assertFalse(window._full_image_loading_timer.isActive())

        settings.set("view/auto_load_full_image", True)
        window._set_random_image_footer(post, preview)
        self.assertNotIn("1754 x 1240", window.footer_meta.text())

    def test_manual_load_shows_loading_text_then_original_resolution(self):
        window = self._create_window(MemorySettings())
        window.random_post = ImagePost(
            "1",
            "provider",
            "https://example.invalid/original.jpg",
            ("https://example.invalid/preview.jpg",),
            "s",
            frozenset(),
            width=1754,
            height=1240,
        )
        window.pages.setCurrentWidget(window.random_page)
        preview = QPixmap(640, 480)
        preview.fill()

        with patch.object(window, "_submit"):
            window._show_random_image(preview)
            self.assertEqual(
                window.footer_meta.text(),
                "provider | Safe | Preview 640 x 480",
            )
            window.load_full_image()

        self.assertEqual(
            window.footer_meta.text(),
            "provider | Safe | Load Full Image.",
        )
        window._update_full_image_loading_text()
        self.assertEqual(window.footer_meta.text(), "provider | Safe | Load Full Image..")
        window._update_full_image_loading_text()
        self.assertEqual(window.footer_meta.text(), "provider | Safe | Load Full Image...")
        loaded = QPixmap(1754, 1240)
        window._full_image_loaded = True
        window._set_random_image_footer(window.random_post, loaded)
        self.assertEqual(window.footer_meta.text(), "provider | Safe | 1754 x 1240")
        self.assertFalse(window._full_image_loading_timer.isActive())

    def test_failed_manual_load_restores_preview_resolution(self):
        window = self._create_window(MemorySettings())
        window.random_post = self._post()
        window.pages.setCurrentWidget(window.random_page)
        preview = QPixmap(640, 480)
        preview.fill()

        with patch.object(window, "_submit"):
            window._show_random_image(preview)
            window.load_full_image()

        window._task_failed(f"full-image:random/{window.request_id}", "network error")

        self.assertEqual(
            window.footer_meta.text(),
            "provider | Safe | Preview 640 x 480",
        )

    def test_random_preview_stays_visible_while_full_image_loads(self):
        settings = MemorySettings(auto_load=True)
        window = self._create_window(settings)
        window.random_post = self._post()
        window.pages.setCurrentWidget(window.random_page)
        pixmap = QPixmap(32, 24)
        pixmap.fill()

        with patch.object(window, "_submit") as submit:
            window._show_random_image(pixmap)

        self.assertEqual(window.random_image.original.size(), pixmap.size())
        self.assertEqual(
            window.footer_meta.text(),
            "provider | Safe | Load Full Image.",
        )
        self.assertTrue(window.full_image_button.isHidden())
        self.assertFalse(window.full_image_button.isEnabled())
        self.assertTrue(window._full_image_loading_timer.isActive())
        self.assertEqual(submit.call_args.args[0], f"full-image:random/{window.request_id}")
        self.assertNotIn("progress_callback", submit.call_args.kwargs)

    def test_enabling_auto_load_hides_button_on_current_preview(self):
        settings = MemorySettings()
        window = self._create_window(settings)
        window.random_post = self._post()
        window.pages.setCurrentWidget(window.random_page)
        pixmap = QPixmap(32, 24)
        pixmap.fill()
        with patch.object(window, "_submit"):
            window._show_random_image(pixmap)
            self.assertFalse(window.full_image_button.isHidden())

            window.open_preferences()
            dialog = window.preferences_dialog
            dialog.auto_load_full_image.setChecked(True)

        self.addCleanup(dialog.close)
        self.assertTrue(window.full_image_button.isHidden())

    def test_manual_full_image_button_remains_available_when_auto_load_is_off(self):
        window = self._create_window(MemorySettings())
        window.random_post = self._post()
        window.pages.setCurrentWidget(window.random_page)
        pixmap = QPixmap(32, 24)
        pixmap.fill()

        with patch.object(window, "_submit") as submit:
            window._show_random_image(pixmap)

        self.assertFalse(window.full_image_button.isHidden())
        self.assertTrue(window.full_image_button.isEnabled())
        submit.assert_not_called()

    def test_detail_preview_stays_visible_while_full_image_loads(self):
        settings = MemorySettings(auto_load=True)
        window = self._create_window(settings)
        window.pages.setCurrentWidget(window.random_page)
        with patch.object(window, "_submit"):
            window.open_post(self._post())
        preview = QImage(32, 24, QImage.Format.Format_ARGB32)
        preview.fill(0xFF336699)

        with patch.object(window, "_submit") as submit:
            window._task_succeeded(f"post-detail:{window.active_detail_id}", preview)

        self.assertEqual(window.detail_image.original.size(), preview.size())
        self.assertTrue(window.full_image_button.isHidden())
        self.assertFalse(window.full_image_button.isEnabled())
        self.assertEqual(
            submit.call_args.args[0],
            f"full-image:detail/{window.active_detail_id}",
        )
        self.assertNotIn("progress_callback", submit.call_args.kwargs)