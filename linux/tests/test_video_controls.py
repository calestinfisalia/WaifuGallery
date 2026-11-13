import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QPushButton, QStyle, QStyleOptionSlider

from waifu_gallery.ui.video import BufferedVideoSlider, VideoPlayerWidget


class VideoControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.player = VideoPlayerWidget()
        self.addCleanup(self.player.close)

    def test_control_background_has_rounded_transparent_corners(self):
        self.player.controls_frame.resize(820, 48)
        self.player.show()
        self.player.controls_frame.show()
        self.app.processEvents()

        image = self.player.controls_frame.grab().toImage()
        corner = image.pixelColor(0, 0)
        center = image.pixelColor(image.width() // 2, image.height() // 2)

        self.assertLess(corner.alpha(), center.alpha())

    def test_seek_track_has_no_gradient(self):
        slider = BufferedVideoSlider()
        self.addCleanup(slider.close)
        slider.setRange(0, 100)
        slider.resize(300, 28)
        style_before = slider.styleSheet()
        slider.set_buffer_progress(0.7)
        slider.show()
        self.app.processEvents()

        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        groove = slider.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderGroove,
            slider,
        )
        image = slider.grab().toImage()
        buffered = image.pixelColor(
            groove.left() + round(groove.width() * 0.5),
            groove.center().y(),
        )
        unbuffered = image.pixelColor(
            groove.left() + round(groove.width() * 0.8),
            groove.center().y(),
        )

        self.assertEqual(slider.styleSheet(), style_before)
        self.assertEqual(buffered.name(), "#e2d3ff")
        self.assertEqual(unbuffered.name(), "#292b32")

    def test_fullscreen_control_bar_stays_compact(self):
        self.player.resize(1920, 1080)
        self.player.video_canvas.resize(1920, 1080)
        self.player.set_fullscreen_mode(True)
        self.player._update_stage_geometry()
        self.player._position_controls_overlay()

        self.assertEqual(self.player.controls_frame.width(), 820)

    def test_poster_is_not_rescaled_when_video_surface_is_active(self):
        self.player._poster = QPixmap(100, 100)
        self.player.preview_page.resize(100, 100)
        self.player._render_poster()
        rendered_target = self.player._rendered_poster_target
        self.player.stage.setCurrentWidget(self.player.video_canvas)
        self.player.preview_page.resize(300, 300)

        self.player._render_poster()

        self.assertEqual(self.player._rendered_poster_target, rendered_target)

    def test_control_visibility_does_not_schedule_video_reflow(self):
        self.player._reflow_timer.stop()
        self.player._has_started = True
        self.player.set_controls_visible(False)
        self.player.set_controls_visible(True)
        action = QPushButton()
        self.player.add_fullscreen_action(action)
        self.player.set_fullscreen_actions_visible(True)
        self.player.set_fullscreen_actions_visible(False)

        self.assertFalse(self.player._reflow_timer.isActive())

    def test_video_view_uses_partial_viewport_updates(self):
        self.assertEqual(
            self.player.video.viewportUpdateMode(),
            self.player.video.ViewportUpdateMode.MinimalViewportUpdate,
        )


if __name__ == "__main__":
    unittest.main()
