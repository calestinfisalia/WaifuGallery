import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from waifu_gallery.models import ImagePost
from waifu_gallery.ui.main_window import MainWindow


class MemorySettings:
    def __init__(self):
        self.values = {
            "appearance/theme": "Dark",
            "search/provider": "All",
            "search/rating": "sfw",
            "search/media_filter": "image",
            "search/exclude_male": False,
            "search/allow_nsfw": True,
            "search/filter_gore": False,
            "search/filter_ai_generated": False,
        }

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
    def ambient_mode(self):
        return True

    @property
    def doh_endpoint(self):
        return "https://cloudflare-dns.com/dns-query"


class AIBadgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_ai_badge_appears_in_random_detail_and_search_images(self):
        settings = MemorySettings()
        with (
            patch("waifu_gallery.ui.main_window.AppSettings", return_value=settings),
            patch.object(MainWindow, "_check_for_startup_update"),
        ):
            window = MainWindow()

        self.addCleanup(window.close)
        ai_post = ImagePost(
            post_id="ai-1",
            provider="danbooru",
            image_url="https://example.test/ai.jpg",
            preview_urls=("https://example.test/ai-preview.jpg",),
            rating="s",
            tags=frozenset({"ai-generated", "furry"}),
        )
        regular_post = ImagePost(
            post_id="regular-1",
            provider="danbooru",
            image_url="https://example.test/regular.jpg",
            preview_urls=("https://example.test/regular-preview.jpg",),
            rating="s",
            tags=frozenset({"furry"}),
        )
        ai_video = ImagePost(
            post_id="ai-video-1",
            provider="danbooru",
            image_url="https://example.test/ai.webm",
            preview_urls=("https://example.test/ai-poster.jpg",),
            rating="s",
            tags=frozenset({"ai-assisted"}),
            media_type="video",
        )

        window.pages.setCurrentWidget(window.random_page)
        window.random_post = ai_post
        window._show_random_image(QPixmap(80, 100))
        self.assertFalse(window.random_ai_badge.isHidden())
        self.assertIs(window.random_ai_badge.parentWidget(), window.random_scroll.viewport())

        window.pages.setCurrentWidget(window.detail_page)
        window.detail_post = ai_post
        window.detail_origin = "search"
        window.active_detail_id = "detail-ai"
        image = QImage(80, 100, QImage.Format.Format_RGB32)
        window._task_succeeded("post-detail:detail-ai", image)
        self.assertFalse(window.detail_ai_badge.isHidden())
        self.assertIs(window.detail_ai_badge.parentWidget(), window.detail_scroll.viewport())

        window._show_random_video(ai_video)
        self.assertTrue(window.random_ai_badge.isHidden())
        self.assertFalse(window.random_video_ai_badge.isHidden())

        window.open_post(ai_video)
        self.assertFalse(window.detail_video_ai_badge.isHidden())

        window.posts = (ai_post, regular_post, ai_video)
        window._add_card(0, ai_post)
        window._add_card(1, regular_post)
        window._add_card(2, ai_video)
        window._set_card_image(0, ai_post, QPixmap(80, 100))
        window._set_card_image(2, ai_video, QPixmap(80, 100))

        ai_badge = window.card_ai_badges[ai_post.post_id]
        video_badge = window.card_ai_badges[ai_video.post_id]
        self.assertFalse(ai_badge.isHidden())
        self.assertFalse(video_badge.isHidden())
        self.assertNotIn(regular_post.post_id, window.card_ai_badges)
        layout = ai_badge.parentWidget().layout()
        self.assertEqual(
            layout.itemAt(layout.indexOf(ai_badge)).alignment(),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
        )

    def test_fullscreen_image_uses_video_background_and_restores_ambient(self):
        settings = MemorySettings()
        with (
            patch("waifu_gallery.ui.main_window.AppSettings", return_value=settings),
            patch.object(MainWindow, "_check_for_startup_update"),
            patch.object(MainWindow, "_submit"),
        ):
            window = MainWindow()
            QTest.qWait(0)

        self.addCleanup(window.close)
        window.random_post = ImagePost(
            post_id="fullscreen-image",
            provider="danbooru",
            image_url="https://example.test/image.jpg",
            preview_urls=(),
            rating="s",
            tags=frozenset(),
        )
        window.pages.setCurrentWidget(window.random_page)
        window._set_ambient_image(
            window.random_ambient, QPixmap(80, 60), window.random_page
        )
        self.assertFalse(window.random_ambient.isHidden())

        window._toggle_fullscreen()
        self.assertTrue(window._fullscreen_active)
        self.assertTrue(window.random_ambient.isHidden())

        window._exit_fullscreen()
        QTest.qWait(150)
        self.assertFalse(window.random_ambient.isHidden())
