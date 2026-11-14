import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap

from waifu_gallery.ui.main_window import MainWindow


class RandomDownloadVisibilityTests(unittest.TestCase):
    def _window(self):
        status_bar = Mock()
        window = SimpleNamespace(
            _fullscreen_active=False,
            statusBar=Mock(return_value=status_bar),
            random_pixmap=None,
            _full_image_loaded=True,
            random_content=b"old",
            random_media_stack=Mock(),
            random_scroll=object(),
            random_video=Mock(),
            random_image=Mock(),
            full_image_button=Mock(),
            _set_image_credits_visible=Mock(),
            _set_ambient_image=Mock(),
            random_ambient=Mock(),
            random_page=Mock(),
            fullscreen_button=Mock(),
            _sync_favorite_buttons=Mock(),
            random_post=None,
            _set_random_image_footer=Mock(),
            _finish_loading=Mock(),
            download_button=Mock(),
        )
        window.download_button.hide()
        return window

    def test_random_image_restores_download_button(self):
        window = self._window()
        pixmap = Mock(spec=QPixmap)
        pixmap.isNull.return_value = False

        MainWindow._show_random_image(window, pixmap)

        window.download_button.show.assert_called_once()

