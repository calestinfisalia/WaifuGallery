from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class VideoPlayerWidget(QWidget):
    """Video surface with a poster/play affordance and one compact control bar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.has_source = False
        self._has_started = False
        self._poster = None
        self._fullscreen_actions: list[QPushButton] = []

        self.video_canvas = QWidget()
        self.video_canvas.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.video = QVideoWidget(self.video_canvas)
        self.video.setStyleSheet("background: transparent; border: 0;")
        self.player.setVideoOutput(self.video)
        self.video.videoSink().videoSizeChanged.connect(self._resize_video_surface)

        self.preview_page = QWidget()
        preview_stack = QGridLayout(self.preview_page)
        preview_stack.setContentsMargins(0, 0, 0, 0)
        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setStyleSheet("background: transparent; border: 0;")
        preview_stack.addWidget(self.preview_image, 0, 0)
        self.play_overlay = QPushButton("\u25b6")
        self.play_overlay.setObjectName("videoPlayOverlay")
        self.play_overlay.setFixedSize(76, 76)
        self.play_overlay.setToolTip("Play video")
        self.play_overlay.clicked.connect(self.toggle_playback)
        preview_stack.addWidget(self.play_overlay, 0, 0, Qt.AlignmentFlag.AlignCenter)

        self.stage = QStackedWidget()
        self.stage.setStyleSheet("background: transparent; border: 0;")
        self.stage.addWidget(self.video_canvas)
        self.stage.addWidget(self.preview_page)
        self.stage.setCurrentWidget(self.preview_page)

        self.play_pause = QPushButton("Play")
        self.play_pause.clicked.connect(self.toggle_playback)
        self.position = QSlider(Qt.Orientation.Horizontal)
        self.position.setRange(0, 0)
        self.position.sliderMoved.connect(self.player.setPosition)
        self.time_label = QLabel("00:00 / 00:00")
        self.message = QLabel("")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.message.hide()

        self.controls_frame = QFrame()
        self.controls_frame.setObjectName("videoControls")
        controls = QHBoxLayout(self.controls_frame)
        controls.setContentsMargins(12, 6, 12, 6)
        controls.setSpacing(10)
        controls.addWidget(self.play_pause)
        controls.addWidget(self.position, 1)
        controls.addWidget(self.time_label)
        self.controls_layout = controls
        self.controls_frame.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addStretch(1)
        layout.addWidget(self.stage, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.controls_frame, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.message, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")

        self.player.playbackStateChanged.connect(self._update_controls)
        self.player.positionChanged.connect(self.position.setValue)
        self.player.positionChanged.connect(self._update_time)
        self.player.durationChanged.connect(self._update_duration)
        self.player.errorOccurred.connect(self._show_error)
        self.setStyleSheet("""
            QFrame#videoControls { background: rgba(22, 23, 34, 235); border: 1px solid #35384c; border-radius: 13px; }
            QPushButton#videoPlayOverlay { border: 0; border-radius: 38px; background: rgba(28, 30, 44, 225); color: white; font-size: 30px; }
            QPushButton#videoPlayOverlay:hover { background: rgba(122, 94, 230, 245); }
            QLabel { color: #c8cce0; }
        """)

    def set_poster(self, pixmap) -> None:
        self._poster = pixmap
        self._schedule_reflow()
        if self.has_source and not self._has_started:
            self.stage.setCurrentWidget(self.preview_page)

    def _render_poster(self) -> None:
        if self._poster is None or self._poster.isNull():
            self.preview_image.clear()
            return
        target = self.preview_page.size().expandedTo(QSize(1, 1))
        scaled = self._poster.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_image.setPixmap(scaled)

    def add_fullscreen_action(self, button: QPushButton) -> None:
        button.setVisible(False)
        self.controls_layout.addWidget(button)
        self._fullscreen_actions.append(button)

    def add_control_action(self, button: QPushButton) -> None:
        self.controls_layout.addWidget(button)

    def set_fullscreen_toggle_visible(self, visible: bool) -> None:
        if hasattr(self, "fullscreen_toggle"):
            self.fullscreen_toggle.setVisible(visible and self._has_started and self.has_source)

    def set_fullscreen_actions_visible(self, visible: bool) -> None:
        for button in self._fullscreen_actions:
            button.setVisible(visible)

    def set_source(self, url: str) -> None:
        self.player.stop()
        source = QUrl(url) if url.startswith(("http://", "https://", "file://")) else QUrl.fromLocalFile(str(Path(url).resolve()))
        self.player.setSource(source)
        self.has_source = True
        self._has_started = False
        self.controls_frame.hide()
        self.message.clear()
        self.message.hide()
        self.stage.setCurrentWidget(self.preview_page)
        self.play_overlay.setEnabled(True)
        self.play_overlay.show()
        self._schedule_reflow()
        self._update_controls(self.player.playbackState())

    def clear(self) -> None:
        self.player.stop()
        self.player.setSource(QUrl())
        self.has_source = False
        self._has_started = False
        self.controls_frame.hide()
        self._poster = None
        self.preview_image.clear()
        self.position.setRange(0, 0)
        self.message.clear()
        self.message.hide()
        self.stage.setCurrentWidget(self.preview_page)
        self.play_overlay.show()
        self.set_fullscreen_actions_visible(False)
        self._update_controls(self.player.playbackState())

    def toggle_playback(self) -> None:
        if not self.has_source:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self._has_started = True
            self.controls_frame.show()
            self.stage.setCurrentWidget(self.video_canvas)
            self.player.play()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_reflow()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._schedule_reflow()

    def _schedule_reflow(self) -> None:
        QTimer.singleShot(0, self._reflow)
        # Stacked layouts can finish assigning the visible page's geometry on
        # the next event turn; run once more after that geometry settles.
        QTimer.singleShot(40, self._reflow)

    def _reflow(self) -> None:
        if not self.isVisible():
            return
        self._update_stage_geometry()
        self._render_poster()
        self._fit_video_surface()

    def _update_stage_geometry(self) -> None:
        width, height = self.width(), self.height()
        if width <= 0 or height <= 0:
            return
        fullscreen = self.window().isFullScreen()
        max_width = max(1, int(width * (0.98 if fullscreen else 0.88)))
        max_height = max(1, int(height * (0.86 if fullscreen else 0.72)))
        source = self.video.videoSink().videoSize()
        if source.width() <= 0 or source.height() <= 0:
            source = self._poster.size() if self._poster is not None else QSize(16, 9)
        if source.width() <= 0 or source.height() <= 0:
            source = QSize(16, 9)
        aspect = source.width() / source.height()
        stage_width = min(max_width, max(1, round(max_height * aspect)))
        stage_height = min(max_height, max(1, round(max_width / aspect)))
        self.stage.setFixedSize(stage_width, stage_height)
        controls_width = min(max_width, max(stage_width, min(580, max_width)))
        self.controls_frame.setFixedWidth(controls_width)
        self.message.setMaximumWidth(controls_width)

    def _resize_video_surface(self, *_args) -> None:
        self._update_stage_geometry()
        QTimer.singleShot(0, self._fit_video_surface)

    def _fit_video_surface(self) -> None:
        canvas = self.video_canvas.size()
        source = self.video.videoSink().videoSize()
        if canvas.width() <= 0 or canvas.height() <= 0:
            return
        if source.width() <= 0 or source.height() <= 0:
            self.video.setGeometry(0, 0, canvas.width(), canvas.height())
            return
        aspect = source.width() / source.height()
        width = min(canvas.width(), max(1, round(canvas.height() * aspect)))
        height = min(canvas.height(), max(1, round(canvas.width() / aspect)))
        self.video.setGeometry(
            (canvas.width() - width) // 2,
            (canvas.height() - height) // 2,
            width,
            height,
        )

    def _update_controls(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        if playing:
            self._has_started = True
        self.controls_frame.setVisible(self._has_started)
        self.play_pause.setText("Pause" if playing else "Play")
        self.play_pause.setEnabled(self.has_source)
        self.play_overlay.setEnabled(self.has_source)

    def _update_duration(self, duration: int) -> None:
        self.position.setRange(0, duration)
        self._update_time(self.player.position())

    def _update_time(self, position: int) -> None:
        duration = self.player.duration()
        self.time_label.setText(f"{self._format_time(position)} / {self._format_time(duration)}")

    @staticmethod
    def _format_time(milliseconds: int) -> str:
        seconds = max(0, milliseconds // 1000)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _show_error(self, _error, message: str) -> None:
        if message:
            self.message.setText(f"Could not play video: {message}")
            self.message.show()
        self._has_started = True
        self.controls_frame.show()
        self.stage.setCurrentWidget(self.preview_page)
