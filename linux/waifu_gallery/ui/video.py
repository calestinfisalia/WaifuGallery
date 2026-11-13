from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRectF, QSize, QSizeF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QStyleOptionSlider,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from .indicators import CircularProgressIndicator


class VideoControlsFrame(QFrame):
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1c1e28"))
        bounds = self.rect().adjusted(0, 0, -1, -1)
        radius = min(24.0, bounds.height() / 2)
        painter.drawRoundedRect(bounds, radius, radius)


class BufferedVideoSlider(QSlider):
    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._buffer_progress = 0.0
        self._track_color = QColor("#292b32")
        self._buffer_color = QColor("#E2D3FF")
        self._played_color = QColor("#BB9AF7")

    def set_buffer_progress(self, progress: float) -> None:
        progress = round(max(0.0, min(1.0, float(progress))) * 100) / 100
        if progress == self._buffer_progress:
            return
        self._buffer_progress = progress
        self.update()

    def set_progress_colors(self, played: str, buffered: str) -> None:
        self._played_color = QColor(played)
        self._buffer_color = QColor(buffered)
        self.update()

    def paintEvent(self, event) -> None:
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        style = self.style()
        groove = style.subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderGroove,
            self,
        )
        handle = style.subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderHandle,
            self,
        )
        if not groove.isValid() or not handle.isValid():
            return

        slider_start = groove.left() + handle.width() / 2
        slider_end = groove.right() - handle.width() / 2
        if slider_end <= slider_start:
            slider_start, slider_end = groove.left(), groove.right()
        span = round(slider_end - slider_start)

        def slider_x(value: int) -> float:
            offset = QStyle.sliderPositionFromValue(
                option.minimum,
                option.maximum,
                value,
                span,
                option.upsideDown,
            )
            return slider_start + offset

        start_x = slider_x(option.minimum)
        buffer_x = slider_x(
            round(option.minimum + (option.maximum - option.minimum) * self._buffer_progress)
        )
        played_x = handle.center().x()
        center_y = groove.center().y()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        track = QRectF(groove.left(), center_y - 2.5, groove.width(), 5)
        painter.setBrush(self._track_color)
        painter.drawRoundedRect(track, 2.5, 2.5)
        painter.setBrush(self._buffer_color)
        painter.drawRoundedRect(
            QRectF(min(start_x, buffer_x), center_y - 2.5, abs(buffer_x - start_x), 5),
            2.5,
            2.5,
        )
        painter.setBrush(self._played_color)
        painter.drawRoundedRect(
            QRectF(min(start_x, played_x), center_y - 2.5, abs(played_x - start_x), 5),
            2.5,
            2.5,
        )
        option.subControls = QStyle.SubControl.SC_SliderHandle
        style.drawComplexControl(QStyle.ComplexControl.CC_Slider, option, painter, self)


class VideoPlayerWidget(QWidget):
    """Video surface with a poster/play affordance and one compact control bar."""

    bufferingChanged = Signal(bool)
    playRequested = Signal()
    playbackActiveChanged = Signal(bool)
    playbackStatusChanged = Signal(str)
    resolutionChanged = Signal(int)
    volumeChanged = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(1, 1)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.has_source = False
        self._has_started = False
        self._poster = None
        self._rendered_poster_target: QSize | None = None
        self._fullscreen_actions: list[QPushButton] = []
        self._fullscreen_mode = False
        self._asset_dir = Path(__file__).resolve().parent.parent / "assets"
        self._pending_source: str | None = None
        self._loading_requested = False
        self._seek_pending = False
        self._slider_dragging = False
        self._slider_target = 0
        self._stream_proxy = None
        self._controls_visible = True
        self._buffering_backdrop_active = False
        self._buffering_active = False
        self._has_video_frame = False
        self._accent_color = "#BB9AF7"
        self._buffered_color = "#E2D3FF"
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.setInterval(55)
        self._reflow_timer.timeout.connect(self._reflow)

        self.video_canvas = QWidget()
        self.video_canvas.setStyleSheet("background: transparent;")
        self.video_canvas.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        video_layout = QVBoxLayout(self.video_canvas)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)
        # Render into a graphics item instead of QVideoWidget's native child
        # window. Native video child windows can escape QStackedWidget clipping
        # on Windows and leave stale, offset copies over the poster/footer.
        # QGraphicsVideoItem still receives frames directly from Qt Multimedia;
        # no per-frame Python/QImage copy is made.
        self.video_scene = QGraphicsScene(self.video_canvas)
        self.video_scene.setBackgroundBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.video_scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.video_item = QGraphicsVideoItem()
        self.video_item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video_item.videoSink().videoFrameChanged.connect(self._on_video_frame)
        self.video_scene.addItem(self.video_item)
        self.video = QGraphicsView(self.video_scene, self.video_canvas)
        self.video.setFrameShape(QFrame.Shape.NoFrame)
        self.video.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setInteractive(False)
        self.video.setStyleSheet("QGraphicsView { background: transparent; border: 0; }")
        self.video.setBackgroundBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.video.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Use Qt's raster viewport for reliable stacking and screen capture on
        # Windows. A translucent OpenGL child surface can retain stale frames
        # when another top-level window covers or activates over the player.
        raster_viewport = QWidget(self.video)
        raster_viewport.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        raster_viewport.setAutoFillBackground(False)
        self.video.setViewport(raster_viewport)
        self._video_viewport = raster_viewport
        raster_viewport.installEventFilter(self)
        self.video.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate
        )
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video.setMinimumSize(1, 1)
        video_layout.addWidget(self.video)

        self.preview_page = QWidget()
        self.preview_page.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        preview_stack = QGridLayout(self.preview_page)
        preview_stack.setContentsMargins(0, 0, 0, 0)
        preview_stack.setRowStretch(0, 1)
        preview_stack.setColumnStretch(0, 1)
        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.preview_image.setStyleSheet("background: transparent; border: 0;")
        preview_stack.addWidget(self.preview_image, 0, 0)
        self.play_overlay = QPushButton()
        self.play_overlay.setObjectName("videoPlayOverlay")
        self.play_overlay.setFixedSize(76, 76)
        self.play_overlay.setIcon(self._icon("play.svg"))
        self.play_overlay.setIconSize(QSize(34, 34))
        self.play_overlay.setToolTip("Play video")
        self.play_overlay.clicked.connect(self.toggle_playback)
        preview_stack.addWidget(self.play_overlay, 0, 0, Qt.AlignmentFlag.AlignCenter)

        self.video_play_overlay = QPushButton(self.video_canvas)
        self.video_play_overlay.setObjectName("videoPlayOverlay")
        self.video_play_overlay.setFixedSize(76, 76)
        self.video_play_overlay.setIcon(self._icon("play.svg"))
        self.video_play_overlay.setIconSize(QSize(34, 34))
        self.video_play_overlay.setToolTip("Play video")
        self.video_play_overlay.clicked.connect(self.toggle_playback)
        self.video_play_overlay.hide()

        self.stage = QStackedWidget()
        self.stage.setStyleSheet("background: transparent; border: 0;")
        self.stage.addWidget(self.video_canvas)
        self.stage.addWidget(self.preview_page)
        self.stage.setCurrentWidget(self.preview_page)
        self.video.hide()
        self._layout.addWidget(self.stage, 1)

        self.play_pause = QPushButton()
        self.play_pause.setObjectName("videoPlayPause")
        self.play_pause.setFixedSize(38, 32)
        self.play_pause.setIcon(self._icon("play.svg"))
        self.play_pause.setIconSize(QSize(18, 18))
        self.play_pause.setToolTip("Play")
        self.play_pause.clicked.connect(self.toggle_playback)
        self.resolution_button = QPushButton("⋮")
        self.resolution_button.setObjectName("videoResolutionButton")
        self.resolution_button.setFixedSize(30, 32)
        self.resolution_button.setToolTip("Video resolution")
        self.resolution_button.setAccessibleName("Video resolution")
        self.resolution_button.clicked.connect(self._show_resolution_menu)
        self._resolution_limit = 0
        self.volume_button = QPushButton()
        self.volume_button.setObjectName("videoVolumeButton")
        self.volume_button.setFixedSize(30, 30)
        self.volume_button.setIconSize(QSize(17, 17))
        self.volume_button.clicked.connect(self._toggle_mute)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("videoVolumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(76)
        self.volume_slider.setToolTip("Volume")
        self.volume_slider.valueChanged.connect(self._volume_changed)
        self.audio.setVolume(0.7)
        self._update_volume_button()
        self.position = BufferedVideoSlider()
        self.position.setObjectName("videoPositionSlider")
        self.position.setRange(0, 0)
        self.position.set_buffer_progress(0.0)
        self.position.sliderMoved.connect(self._slider_moved)
        self.time_label = QLabel("00:00 / 00:00")
        self.message = QLabel("")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.message.hide()

        self.buffering_overlay = QFrame(self.video_canvas)
        self.buffering_overlay.setObjectName("videoBufferingOverlay")
        buffering_layout = QVBoxLayout(self.buffering_overlay)
        buffering_layout.setContentsMargins(0, 0, 0, 0)
        buffering_layout.setSpacing(0)
        self.buffering_bar = CircularProgressIndicator(size=28)
        self.buffering_bar.setObjectName("videoBufferingIndicator")
        buffering_layout.addWidget(self.buffering_bar, 0, Qt.AlignmentFlag.AlignHCenter)
        self.buffering_overlay.hide()

        self.controls_frame = VideoControlsFrame()
        self.controls_frame.setObjectName("videoControls")
        controls = QHBoxLayout(self.controls_frame)
        controls.setContentsMargins(12, 6, 12, 6)
        controls.setSpacing(10)
        controls.addWidget(self.play_pause)
        controls.addWidget(self.position, 1)
        controls.addWidget(self.time_label)
        controls.addWidget(self.volume_button)
        controls.addWidget(self.volume_slider)
        controls.addWidget(self.resolution_button)
        self.controls_layout = controls
        self.controls_frame.hide()
        # Controls float over the video canvas instead of taking a row from
        # the layout; the video therefore keeps the full available height.
        self.controls_frame.setParent(self.video_canvas)

        # Keep the status label in this widget's layout too; video controls
        # are ordinary child widgets layered above the graphics view.
        self.message.setParent(self)
        self._layout.addWidget(self.message, 0, Qt.AlignmentFlag.AlignHCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")

        self.player.playbackStateChanged.connect(self._update_controls)
        self.player.positionChanged.connect(self._position_changed)
        self.player.positionChanged.connect(self._update_time)
        self.player.durationChanged.connect(self._update_duration)
        self.player.bufferProgressChanged.connect(self._update_buffer_progress)
        self.player.errorOccurred.connect(self._show_error)
        self.player.mediaStatusChanged.connect(self._media_status_changed)
        self.position.sliderPressed.connect(self._slider_pressed)
        self.position.sliderReleased.connect(self._slider_released)
        self.setStyleSheet("""
            QPushButton#videoPlayOverlay { border: 0; border-radius: 38px; background: rgba(28, 30, 44, 225); color: white; font-size: 30px; }
            QPushButton#videoPlayOverlay:hover { background: rgba(122, 94, 230, 245); }
            QPushButton#videoPlayPause { padding: 0; }
            QPushButton#videoResolutionButton { border: 0; background: transparent; color: #c8cce0; font-size: 22px; padding: 0; }
            QPushButton#videoResolutionButton:hover { background: rgba(122, 94, 230, 120); border-radius: 8px; }
            QPushButton#videoVolumeButton { padding: 0; border: 0; background: transparent; }
            QSlider#videoVolumeSlider { min-height: 18px; }
            QSlider#videoVolumeSlider::groove:horizontal {
                height: 5px;
                background: #292b32;
                border-radius: 2px;
            }
            QSlider#videoPositionSlider::sub-page:horizontal,
            QSlider#videoVolumeSlider::sub-page:horizontal {
                background: #8b909b;
                border-radius: 2px;
            }
            QSlider#videoVolumeSlider::add-page:horizontal {
                background: #292b32;
                border-radius: 2px;
            }
            QSlider#videoPositionSlider::handle:horizontal,
            QSlider#videoVolumeSlider::handle:horizontal {
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
                background: #a0a5af;
            }
            QLabel { color: #c8cce0; }
        """)
        self._update_buffer_indicator(False)
        self.controls_frame.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.buffering_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.buffering_overlay.setStyleSheet(
            "QFrame#videoBufferingOverlay { background: transparent; border: 0; }"
        )
        self.controls_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.controls_frame.setAutoFillBackground(False)
        self.set_accent_color(self._accent_color)

    def _icon(self, name: str) -> QIcon:
        return QIcon(str(self._asset_dir / name))

    def set_poster(self, pixmap) -> None:
        self._poster = pixmap
        self._rendered_poster_target = None
        self._schedule_reflow()
        if self.has_source and not self._has_started:
            self._show_preview_surface()

    def set_poster_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        self.preview_image.setAlignment(alignment)
        self._schedule_reflow()

    def _render_poster(self) -> None:
        if self.stage.currentWidget() is not self.preview_page:
            return
        if self._poster is None or self._poster.isNull():
            self.preview_image.clear()
            self._rendered_poster_target = None
            return
        # Keep the poster label stretched to the full viewport so alignment is
        # based on the current page, not the old size hint of its pixmap.
        target = self.preview_page.rect().size().expandedTo(QSize(1, 1))
        current_pixmap = self.preview_image.pixmap()
        if (
            self._rendered_poster_target == target
            and current_pixmap is not None
            and not current_pixmap.isNull()
        ):
            return
        scaled = self._poster.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_image.setGeometry(self.preview_page.rect())
        self.preview_image.setPixmap(scaled)
        self._rendered_poster_target = QSize(target)

    def add_fullscreen_action(self, button: QPushButton, index: int | None = None) -> None:
        button.setVisible(False)
        if index is None:
            self.controls_layout.addWidget(button)
        else:
            self.controls_layout.insertWidget(index, button)
        self._fullscreen_actions.append(button)

    def add_control_action(self, button: QPushButton, index: int | None = None) -> None:
        button.hide()
        if index is None:
            self.controls_layout.addWidget(button)
        else:
            self.controls_layout.insertWidget(index, button)

    def set_volume(self, value: int) -> None:
        self.volume_slider.setValue(max(0, min(100, int(value))))

    def set_resolution_limit(self, height: int) -> None:
        self._resolution_limit = height if height in {0, 480, 720, 1080, 2160} else 0

    def _show_resolution_menu(self) -> None:
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        for height, label in (
            (0, "Auto"),
            (2160, "Up to 2160p"),
            (1080, "Up to 1080p"),
            (720, "Up to 720p"),
            (480, "Up to 480p"),
        ):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(height == self._resolution_limit)
            action.triggered.connect(
                lambda _checked=False, selected=height: self._select_resolution(selected)
            )
        menu.exec(self.resolution_button.mapToGlobal(QPoint(0, -menu.sizeHint().height())))

    def _select_resolution(self, height: int) -> None:
        if height == self._resolution_limit:
            return
        self._resolution_limit = height
        self.resolutionChanged.emit(height)

    def _volume_changed(self, value: int) -> None:
        self.audio.setVolume(value / 100.0)
        if value > 0 and self.audio.isMuted():
            self.audio.setMuted(False)
        self._update_volume_button()
        self.volumeChanged.emit(value)

    def _toggle_mute(self) -> None:
        self.audio.setMuted(not self.audio.isMuted())
        self._update_volume_button()

    def _update_volume_button(self) -> None:
        muted = self.audio.isMuted() or self.volume_slider.value() == 0
        icon_name = "volume-x.svg" if muted else "volume.svg"
        self.volume_button.setIcon(self._icon(icon_name))
        self.volume_button.setToolTip("Unmute" if muted else "Mute")

    def set_fullscreen_toggle_visible(self, visible: bool) -> None:
        if hasattr(self, "fullscreen_toggle"):
            self.fullscreen_toggle.setVisible(visible and self._has_started and self.has_source)

    def set_fullscreen_mode(self, enabled: bool) -> None:
        if self._fullscreen_mode == enabled:
            return
        self._fullscreen_mode = enabled
        self._controls_visible = True
        self.controls_frame.setVisible(self._has_started)
        self._schedule_reflow()

    def set_fullscreen_controls_visible(self, visible: bool) -> None:
        self.set_controls_visible(visible)

    def set_controls_visible(self, visible: bool) -> None:
        self._controls_visible = visible
        self.controls_frame.setVisible(self._has_started and visible)
        if visible:
            self.controls_frame.raise_()

    def set_fullscreen_actions_visible(self, visible: bool) -> None:
        changed = False
        for button in self._fullscreen_actions:
            if button.isHidden() == visible:
                button.setVisible(visible)
                changed = True
        if changed:
            self.controls_layout.activate()
            self._position_controls_overlay()

    def set_source(self, url: str, autoplay: bool = False, stream_proxy=None) -> None:
        self.audio.setMuted(False)
        self.player.stop()
        self._close_stream_proxy()
        self._has_video_frame = False
        self._stream_proxy = stream_proxy
        self.player.setPosition(0)
        self.position.setRange(0, 0)
        self.position.setValue(0)
        self._update_buffer_progress(0.0)
        self.time_label.setText("00:00 / 00:00")
        self._pending_source = None
        self._loading_requested = False
        self._seek_pending = False
        source = QUrl(url) if url.startswith(("http://", "https://", "file://")) else QUrl.fromLocalFile(str(Path(url).resolve()))
        self.has_source = True
        self._has_started = autoplay
        self._controls_visible = True
        self.controls_frame.setVisible(autoplay)
        self.message.clear()
        self.message.hide()
        if not autoplay:
            self.buffering_overlay.hide()
        if autoplay:
            self._show_video_surface()
        else:
            self._show_preview_surface()
        self.play_overlay.setEnabled(True)
        self.play_overlay.setVisible(not autoplay)
        self._update_stage_geometry()
        self.player.setSource(source)
        if autoplay:
            self._set_buffering(True)
            self.player.play()
        self._schedule_reflow()
        self._update_controls(self.player.playbackState())

    def set_deferred_source(self, url: str) -> None:
        """Keep the remote URL pending until Play requests an app-managed buffer."""
        self.audio.setMuted(True)
        self.player.stop()
        self.player.setVideoOutput(None)
        self.player.setSource(QUrl())
        self._close_stream_proxy()
        self._pending_source = url
        self._loading_requested = False
        self._seek_pending = False
        self._has_video_frame = False
        self.has_source = bool(url)
        self._has_started = False
        self._controls_visible = True
        self.controls_frame.hide()
        self.message.clear()
        self.message.hide()
        self.buffering_overlay.hide()
        self.bufferingChanged.emit(False)
        self._poster = None
        self._rendered_poster_target = None
        self.preview_image.clear()
        self._show_preview_surface()
        self.play_overlay.setEnabled(self.has_source)
        self.play_overlay.show()
        self.position.setRange(0, 0)
        self.position.setValue(0)
        self._update_buffer_progress(0.0)
        self.time_label.setText("00:00 / 00:00")
        self._schedule_reflow()
        self._update_controls(self.player.playbackState())

    def clear(self) -> None:
        # Mute first so audio stops immediately even if the backend is still
        # draining a decoder/audio buffer while stop() and setSource() settle.
        self.audio.setMuted(True)
        self.player.pause()
        self.player.stop()
        self.player.setVideoOutput(None)
        self.player.setSource(QUrl())
        self._close_stream_proxy()
        self._pending_source = None
        self._loading_requested = False
        self._seek_pending = False
        self._has_video_frame = False
        self.has_source = False
        self._has_started = False
        self._set_buffering(False)
        self._controls_visible = False
        self.controls_frame.hide()
        self._poster = None
        self._rendered_poster_target = None
        self.preview_image.clear()
        self.position.setRange(0, 0)
        self.position.setValue(0)
        self._update_buffer_progress(0.0)
        self.time_label.setText("00:00 / 00:00")
        self.message.clear()
        self.message.hide()
        self.buffering_overlay.hide()
        self.bufferingChanged.emit(False)
        self._show_preview_surface()
        self.play_overlay.show()
        self.set_fullscreen_toggle_visible(False)
        self.set_fullscreen_actions_visible(False)
        self._update_controls(self.player.playbackState())

    def _close_stream_proxy(self) -> None:
        stream, self._stream_proxy = self._stream_proxy, None
        if stream is not None:
            stream.close()

    def _show_preview_surface(self) -> None:
        self.player.setVideoOutput(None)
        self.video_canvas.hide()
        self.stage.setCurrentWidget(self.preview_page)
        self.preview_page.show()

    def _show_video_surface(self) -> None:
        self.stage.setCurrentWidget(self.video_canvas)
        self.video_canvas.show()
        self.video.show()
        self.player.setVideoOutput(self.video_item)

    def toggle_playback(self) -> None:
        if not self.has_source:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            if self._loading_requested:
                return
            self._has_started = True
            self._controls_visible = True
            self.controls_frame.show()
            self._show_video_surface()
            self._schedule_reflow()
            if self._pending_source is not None:
                self._loading_requested = True
                self.message.clear()
                self.message.hide()
                self._set_buffering(True)
                self.bufferingChanged.emit(True)
                self.playRequested.emit()
                return
            if (
                self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia
                or (
                    self.player.duration() > 0
                    and self.player.position() >= self.player.duration()
                )
            ):
                self.player.setPosition(0)
            self.player.play()

    def set_accent_color(self, color: str) -> None:
        accent = QColor(color)
        if not accent.isValid():
            return
        self._accent_color = accent.name()
        self._buffered_color = accent.lighter(150).name()
        self.position.setStyleSheet(
            "QSlider#videoPositionSlider { min-height: 18px; }"
            "QSlider#videoPositionSlider::handle:horizontal { "
            f"width: 12px; margin: -4px 0; border-radius: 6px; background: {self._buffered_color}; }}"
        )
        self.position.set_progress_colors(self._accent_color, self._buffered_color)
        self.volume_slider.setStyleSheet(
            "QSlider#videoVolumeSlider::groove:horizontal { height: 5px; background: #292b32; border-radius: 2px; }"
            "QSlider#videoVolumeSlider::sub-page:horizontal { "
            f"background: {self._accent_color}; border-radius: 2px; }}"
            "QSlider#videoVolumeSlider::add-page:horizontal { background: #292b32; border-radius: 2px; }"
            "QSlider#videoVolumeSlider::handle:horizontal { "
            f"width: 12px; margin: -4px 0; border-radius: 6px; background: {self._buffered_color}; }}"
        )

    def _update_buffer_progress(self, progress: float) -> None:
        self.position.set_buffer_progress(progress)
    def _update_buffer_indicator(self, active: bool) -> None:
        self.buffering_bar.set_active(active)

    def show_prepare_error(self, message: str) -> None:
        self.audio.setMuted(True)
        self.player.pause()
        self.player.stop()
        self._close_stream_proxy()
        self._loading_requested = False
        self._has_started = False
        self.controls_frame.hide()
        self._set_buffering(False)
        self._show_preview_surface()
        self.message.setText(message)
        self.message.show()
        self._schedule_reflow()

    def _set_buffering(self, buffering: bool) -> None:
        visible = (
            buffering
            and self._has_started
            and self.player.playbackState() != QMediaPlayer.PlaybackState.PausedState
        )
        changed = self._buffering_active != visible
        self._buffering_active = visible
        # A transparent OpenGL viewport reveals the desktop until the decoder
        # submits its first frame. Paint an opaque black scene while buffering
        # or seeking, then restore transparency so ambient mode can show again.
        opaque_backdrop = visible or (self._has_started and not self._has_video_frame)
        if self._buffering_backdrop_active != opaque_backdrop:
            brush = (
                QBrush(Qt.GlobalColor.black)
                if opaque_backdrop
                else QBrush(Qt.BrushStyle.NoBrush)
            )
            self.video_scene.setBackgroundBrush(brush)
            self.video.setBackgroundBrush(brush)
            self._buffering_backdrop_active = opaque_backdrop
            self.video.viewport().update()
        self.buffering_overlay.setVisible(visible)
        self._update_buffer_indicator(visible)
        show_center_play = (
            self._has_started
            and self.has_source
            and self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
            and not visible
        )
        self.video_play_overlay.setVisible(show_center_play)
        if show_center_play:
            self.video_play_overlay.raise_()
        if visible:
            self._position_overlay_widgets()
            self.buffering_overlay.raise_()
        if changed:
            self._emit_playback_status()

    def _on_video_frame(self, frame) -> None:
        if not frame.isValid():
            return
        self._has_video_frame = True
        if not self._buffering_active:
            return
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            return
        if self._seek_pending and abs(self.player.position() - self._slider_target) > 1500:
            return
        self._seek_pending = False
        self._set_buffering(False)
        self.bufferingChanged.emit(False)

    def _slider_pressed(self) -> None:
        self._slider_dragging = True

    def _slider_moved(self, position: int) -> None:
        self._slider_target = position
        duration = self.player.duration()
        self.time_label.setText(f"{self._format_time(position)} / {self._format_time(duration)}")

    def _slider_released(self) -> None:
        self._slider_dragging = False
        if not self.has_source or not self._has_started:
            return
        self._slider_target = self.position.sliderPosition()
        self._seek_pending = True
        self._has_video_frame = False
        self._set_buffering(True)
        self.bufferingChanged.emit(True)
        self.player.setPosition(self._slider_target)
        QTimer.singleShot(100, self._finish_seek_if_ready)

    def _position_changed(self, position: int) -> None:
        if not self._slider_dragging and not self.position.isSliderDown():
            self.position.setValue(position)
            self._update_time(position)
        if self._seek_pending and abs(position - self._slider_target) <= 1500:
            QTimer.singleShot(250, self._finish_seek_if_ready)

    def _finish_seek_if_ready(self) -> None:
        if not self._seek_pending:
            return
        if self.player.mediaStatus() in {
            QMediaPlayer.MediaStatus.LoadingMedia,
            QMediaPlayer.MediaStatus.BufferingMedia,
            QMediaPlayer.MediaStatus.StalledMedia,
        }:
            return
        if abs(self.player.position() - self._slider_target) > 1500:
            QTimer.singleShot(150, self._finish_seek_if_ready)
            return
        if (
            self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            and not self._has_video_frame
        ):
            return
        self._seek_pending = False
        self._set_buffering(False)
        self.bufferingChanged.emit(False)

    def _media_status_changed(self, status) -> None:
        if not self._has_started:
            self._set_buffering(False)
            return
        if status in {
            QMediaPlayer.MediaStatus.LoadingMedia,
            QMediaPlayer.MediaStatus.BufferingMedia,
            QMediaPlayer.MediaStatus.StalledMedia,
        }:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
                self._set_buffering(False)
                self.bufferingChanged.emit(False)
                return
            if not self._buffering_active:
                self._has_video_frame = False
            self._set_buffering(True)
            self.bufferingChanged.emit(True)
        elif status in {
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        }:
            seek_ready = (
                not self._seek_pending
                or abs(self.player.position() - self._slider_target) <= 1500
            )
            if self._has_video_frame and seek_ready and (
                self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                or self._seek_pending
            ):
                self._seek_pending = False
                self._set_buffering(False)
                self.bufferingChanged.emit(False)
        elif status in {QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia}:
            self._seek_pending = False
            self._set_buffering(False)
            self.bufferingChanged.emit(False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_reflow()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._schedule_reflow()

    def eventFilter(self, watched, event) -> bool:
        if watched is self._video_viewport and event.type() == QEvent.Type.Resize:
            self._schedule_reflow()
        return super().eventFilter(watched, event)

    def _schedule_reflow(self) -> None:
        # Coalesce bursts of resize/fullscreen events. Resizing the video item
        # several times per transition can stall the decoder and redraw path.
        self._reflow_timer.start()

    def _reflow(self) -> None:
        self._update_stage_geometry()
        self._render_poster()
        self._fit_video_surface()
        self._position_overlay_widgets()

    def _update_stage_geometry(self) -> None:
        width, height = self.width(), self.height()
        if width <= 0 or height <= 0:
            return
        fullscreen = self._fullscreen_mode or self.window().isFullScreen()
        self.controls_frame.setMaximumWidth(16777215 if fullscreen else max(1, width - 24))
        self.message.setMaximumWidth(max(1, width - 32))
        self._position_controls_overlay()

    def _position_controls_overlay(self) -> None:
        canvas_width, canvas_height = self.video_canvas.width(), self.video_canvas.height()
        if canvas_width <= 0 or canvas_height <= 0:
            return
        bar_height = self.controls_frame.sizeHint().height()
        available_width = max(1, canvas_width - 48)
        bar_width = min(available_width, 820)
        bar_x = (canvas_width - bar_width) // 2
        bar_y = canvas_height - bar_height - 28
        self.controls_frame.setGeometry(
            bar_x,
            max(8, min(canvas_height - bar_height - 8, bar_y)),
            bar_width,
            bar_height,
        )
        self.controls_frame.raise_()

    def _position_overlay_widgets(self) -> None:
        width, height = self.video_canvas.width(), self.video_canvas.height()
        if width <= 0 or height <= 0:
            return
        overlay_width = min(self.buffering_bar.width(), width)
        overlay_height = min(self.buffering_bar.height(), height)
        self.buffering_overlay.setGeometry(
            (width - overlay_width) // 2,
            (height - overlay_height) // 2,
            overlay_width,
            overlay_height,
        )
        self.video_play_overlay.move(
            (width - self.video_play_overlay.width()) // 2,
            (height - self.video_play_overlay.height()) // 2,
        )

    def _fit_video_surface(self) -> None:
        viewport = self.video.viewport().size()
        width, height = max(1, viewport.width()), max(1, viewport.height())
        # Fullscreen/restore may leave a stale scene transform or scroll offset.
        # Refit against the live viewport while preserving the video's aspect.
        if not self.video.transform().isIdentity():
            self.video.resetTransform()
        self.video.horizontalScrollBar().setValue(0)
        self.video.verticalScrollBar().setValue(0)
        scene_rect = self.video_scene.sceneRect()
        if scene_rect.width() != width or scene_rect.height() != height:
            self.video_scene.setSceneRect(0, 0, width, height)
        target_size = QSizeF(width, height)
        if self.video_item.pos().x() != 0 or self.video_item.pos().y() != 0:
            self.video_item.setPos(0, 0)
        if self.video_item.size() != target_size:
            self.video_item.setSize(target_size)

    def _update_controls(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.playbackActiveChanged.emit(playing)
        if state == QMediaPlayer.PlaybackState.PausedState:
            # A pause must never leave the buffering veil/status active.
            self._seek_pending = False
            self._set_buffering(False)
        seek_ready = (
            not self._seek_pending
            or abs(self.player.position() - self._slider_target) <= 1500
        )
        if playing and seek_ready and self._has_video_frame:
            self._seek_pending = False
            self._has_started = True
            self._set_buffering(False)
            self.bufferingChanged.emit(False)
        self.controls_frame.setVisible(
            self._has_started and self._controls_visible
        )
        self.resolution_button.setVisible(self._has_started and self.has_source)
        self.play_pause.setIcon(self._icon("pause.svg" if playing else "play.svg"))
        self.play_pause.setToolTip("Pause" if playing else "Play")
        self.play_pause.setEnabled(self.has_source)
        self.play_overlay.setEnabled(self.has_source)
        self.play_overlay.setIcon(self._icon("pause.svg" if playing else "play.svg"))
        self.play_overlay.setToolTip("Pause video" if playing else "Play video")
        show_center_play = (
            self._has_started
            and self.has_source
            and not playing
            and not self._buffering_active
        )
        self.video_play_overlay.setVisible(show_center_play)
        if show_center_play:
            self.video_play_overlay.raise_()
        self.set_fullscreen_toggle_visible(self._has_started and self.has_source and not self._fullscreen_mode)
        self._emit_playback_status(state)

    def _emit_playback_status(self, state=None) -> None:
        if state is None:
            state = self.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            text = "Playing"
        elif state == QMediaPlayer.PlaybackState.PausedState:
            text = "Paused"
        elif self._has_started and self.has_source:
            text = "Stopped"
        else:
            text = "Ready"
        self.playbackStatusChanged.emit(text)

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
        self.bufferingChanged.emit(False)
        self._set_buffering(False)
        self._close_stream_proxy()
        if message:
            self.message.setText(f"Could not play video: {message}")
            self.message.show()
        self._has_started = True
        self.controls_frame.show()
        self._show_preview_surface()

    def closeEvent(self, event) -> None:
        self.player.stop()
        self._close_stream_proxy()
        super().closeEvent(event)
