import ctypes
import re
import sys
from pathlib import Path
from uuid import uuid4

if sys.platform == "win32":
    from ctypes import wintypes
else:
    wintypes = None

from PySide6.QtCore import (
    QByteArray,
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    Qt,
    QThreadPool,
    QSize,
    QTimer,
)
from PySide6.QtGui import QActionGroup, QColor, QCursor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QMenu,
    QSizeGrip,
    QGraphicsDropShadowEffect,
    QGraphicsBlurEffect,
    QGraphicsOpacityEffect,
    QApplication,
)

from .. import __version__
from ..models import ImagePost, SearchPage
from ..providers import BooruCatalog, ProviderError
from ..settings import AppSettings
from .backup_prompts import BackupMessageDialog
from .downloads import DownloadsDialog
from .credits import ImageCreditsDialog, rating_label
from .favorites import FavoritesDialog, favorite_key
from .indicators import CircularProgressIndicator
from ..pin_security import has_pin, verify_pin
from .pin_prompts import PinPromptDialog
from .preferences import PreferencesDialog
from .updates import ReleaseNotesDialog, UpdateCheckTask, version_parts
from .video import VideoPlayerWidget
from .viewer import ZoomImage
from .scrollbars import CAPSULE_SCROLLBAR_STYLE
from .workers import BackgroundTask, FileDownloadTask, decode_image_bytes


class SearchLineEdit(QLineEdit):
    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self._clear_automatic_selection)

    def _clear_automatic_selection(self) -> None:
        if self.text() and self.selectedText() == self.text():
            self.deselect()


class GalleryTitleBar(QWidget):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.main_window = window
        self.setObjectName("titleBar")
        self.setFixedHeight(42)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(7)

        left_container = QWidget(self)
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(7)

        logo = QLabel()
        logo.setPixmap(window._app_icon().pixmap(QSize(22, 22)))
        logo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        left_layout.addWidget(logo)
        title = QLabel("Waifu Gallery")
        title.setObjectName("windowTitle")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        left_layout.addWidget(title)
        self.navigation_container = QWidget()
        self.navigation_layout = QHBoxLayout(self.navigation_container)
        self.navigation_layout.setContentsMargins(0, 0, 0, 0)
        self.navigation_layout.setSpacing(2)
        left_layout.addWidget(self.navigation_container)
        left_layout.addStretch(1)
        layout.addWidget(left_container)
        layout.addStretch(1)

        self.search_input = SearchLineEdit()
        self.search_input.setObjectName("mainSearchInput")
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setMinimumWidth(280)
        self.search_input.setMaximumWidth(560)
        self.search_input.setFixedHeight(34)
        self.search_input.setFrame(False)
        self.search_input.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.search_input.setParent(self)
        self.search_input.returnPressed.connect(window.start_search)
        self.home_button = window._icon_button("home", "Return to random images")
        self.home_button.setParent(self)
        self.home_button.setFixedSize(36, 34)
        self.home_button.hide()
        self.home_button.clicked.connect(window.go_home)
        self.search_action = self.search_input.addAction(
            window._icon("search"), QLineEdit.ActionPosition.TrailingPosition
        )
        self.search_action.triggered.connect(window.start_search)

        right_container = QWidget(self)
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        self.action_container = QWidget()
        self.action_layout = QHBoxLayout(self.action_container)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(2)
        right_layout.addWidget(self.action_container)

        self.minimize_button = self._control("minimize", "Minimize")
        self.maximize_button = self._control("maximize", "Maximize")
        self.close_button = self._control("close", "Close")
        self.close_button.setObjectName("closeWindowButton")
        right_layout.addWidget(self.minimize_button)
        right_layout.addWidget(self.maximize_button)
        right_layout.addWidget(self.close_button)
        layout.addStretch(1)
        layout.addWidget(right_container)

        self.minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button.clicked.connect(self.toggle_maximize)
        self.close_button.clicked.connect(window.close)

    def _control(self, icon: str, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setIcon(self.main_window._icon(icon))
        button.setProperty("iconAction", True)
        button.setProperty("iconName", icon)
        button.setIconSize(QSize(17, 17))
        button.setFixedSize(34, 34)
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def add_action(self, button: QPushButton) -> None:
        self.action_layout.addWidget(button)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        central = self.main_window.centralWidget()
        search_width = min(560, max(280, round(self.main_window.width() * 0.42)))
        center_in_window = central.mapTo(self.main_window, QPoint(central.width() // 2, 0)).x()
        title_left_in_window = self.mapTo(self.main_window, QPoint(0, 0)).x()
        search_x = center_in_window - title_left_in_window - search_width // 2
        self.search_input.setGeometry(search_x, 4, search_width, 34)
        self.home_button.move(search_x - self.home_button.width() - 8, 4)

    def add_navigation_action(self, button: QPushButton) -> None:
        self.navigation_layout.addWidget(button)

    def refresh_search_icon(self) -> None:
        self.search_action.setIcon(self.main_window._icon("search"))

    def toggle_maximize(self) -> None:
        if self.main_window.isMaximized():
            self.main_window.showNormal()
            icon = "maximize"
            tooltip = "Maximize"
        else:
            self.main_window.showMaximized()
            icon = "restore"
            tooltip = "Restore"
        self.maximize_button.setIcon(self.main_window._icon(icon))
        self.maximize_button.setToolTip(tooltip)

    def refresh_icons(self) -> None:
        for button, name in (
            (self.minimize_button, "minimize"),
            (self.maximize_button, "restore" if self.main_window.isMaximized() else "maximize"),
            (self.close_button, "close"),
        ):
            button.setIcon(self.main_window._icon(name))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.main_window.windowHandle()
            if handle and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()
        super().mouseDoubleClickEvent(event)



class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = AppSettings()
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(8)
        self.tasks = {}
        self._startup_update_task = None
        self._update_notice_dialog = None
        self.request_id = 0
        self.gallery_generation = 0
        self.current_query = ""
        self.current_page = 1
        self._page_has_more = False
        self._open_detail_after_page: int | None = None
        self.detail_from_search = False
        self.detail_origin = "random"
        self._favorite_navigation_posts: list[ImagePost] = []
        self.posts: tuple[ImagePost, ...] = ()
        self.thumbnail_cache: dict[str, QPixmap] = {}
        self.card_buttons: dict[str, QPushButton] = {}
        self.card_loading_indicators: dict[str, CircularProgressIndicator] = {}
        self.card_play_badges: dict[str, QLabel] = {}
        self.card_frames: dict[str, QWidget] = {}
        self.active_detail_id = ""
        self.detail_post: ImagePost | None = None
        self._full_image_loaded = False
        self.favorites_dialog: FavoritesDialog | None = None
        self.favorites_dialog_token = ""
        self.preferences_dialog: PreferencesDialog | None = None
        self._opening_favorite = False
        self._fullscreen_active = False
        self._was_maximized_before_fullscreen = False
        self._windowed_geometry = None
        self.card_buttons: dict[str, QPushButton] = {}
        self.current_theme = str(self.settings.get("appearance/theme", "Dark"))
        if self.current_theme not in ("Dark", "Light", "System", "OLED Dark"):
            self.current_theme = "Dark"
        self._icon_cache: dict[tuple[str, str], QIcon] = {}
        self._icon_buttons: list[QPushButton] = []
        self.downloads = DownloadsDialog(self)
        self.downloads.cancel_requested.connect(self._cancel_download)
        self._fullscreen_idle_timer = QTimer(self)
        self._fullscreen_idle_timer.setSingleShot(True)
        self._fullscreen_idle_timer.setInterval(1000)
        self._fullscreen_idle_timer.timeout.connect(self._hide_fullscreen_controls)
        self._media_controls_idle_timer = QTimer(self)
        self._media_controls_idle_timer.setSingleShot(True)
        self._media_controls_idle_timer.setInterval(1000)
        self._media_controls_idle_timer.timeout.connect(self._hide_windowed_video_controls)
        self._ambient_restore_timer = QTimer(self)
        self._ambient_restore_timer.setSingleShot(True)
        self._ambient_restore_timer.setInterval(120)
        self._ambient_restore_timer.timeout.connect(self._refresh_ambient_layers)
        # Avoid rebuilding image scaling, blurred backgrounds, and the search
        # grid for every intermediate WM_SIZE event while the user drags a
        # window edge. Those expensive layout updates run once after resizing.
        self._resize_settle_timer = QTimer(self)
        self._resize_settle_timer.setSingleShot(True)
        self._resize_settle_timer.setInterval(55)
        self._resize_settle_timer.timeout.connect(self._finish_resize_settle)
        self._resize_cursor_active = False
        self._gallery_notice_timer = QTimer(self)
        self._gallery_notice_timer.setSingleShot(True)
        self._gallery_notice_timer.setInterval(5000)
        self._gallery_notice_timer.timeout.connect(self._fade_out_gallery_notice)
        self._shown_provider_error_signatures: set[tuple[str, ...]] = set()
        self.setWindowTitle("Waifu Gallery")
        self.setWindowIcon(self._app_icon())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(860, 600)
        self.resize(1180, 820)
        self._build_ui()
        self.setMouseTracking(True)
        for widget in self.findChildren(QWidget):
            widget.setMouseTracking(True)
        app = QApplication.instance()
        if app:
            # Catch mouse presses on child widgets too, so every window edge
            # can start the native Windows resize operation.
            app.installEventFilter(self)
        self._apply_theme(self.current_theme)
        QTimer.singleShot(0, self.show_random)
        QTimer.singleShot(0, self._check_for_startup_update)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            QTimer.singleShot(0, self._raise_main_over_open_dialogs)

    def _raise_main_over_open_dialogs(self) -> None:
        if not self.isActiveWindow():
            return
        dialog_names = {
            "downloadsDialog",
            "favoritesDialog",
            "mediaInfoDialog",
            "releaseNotesDialog",
            "settingsDialog",
        }
        for dialog in self.findChildren(QDialog):
            if dialog.isVisible() and dialog.objectName() in dialog_names:
                dialog.lower()
        self.raise_()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.title_bar = GalleryTitleBar(self)
        root_layout.addWidget(self.title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.back_button = self._icon_button("chevron-left", "Back to results")
        self.back_button.hide()
        self.title_bar.add_navigation_action(self.back_button)
        self.search_input = self.title_bar.search_input
        self.search_input.installEventFilter(self)
        self.selected_provider = str(self.settings.get("search/provider", "All"))
        if self.selected_provider not in ("All", "Danbooru", "yande.re", "Gelbooru", "Rule34.xxx"):
            self.selected_provider = "All"
        self.selected_rating = str(self.settings.get("search/rating", "sfw"))
        if self.selected_rating not in ("sfw", "nsfw", "all"):
            self.selected_rating = "sfw"
        self.selected_media = str(self.settings.get("search/media_filter", "image"))
        if self.selected_media not in ("image", "video", "all"):
            self.selected_media = "image"
        self.settings_button = self._icon_button("menu", "Settings and options")
        self.fullscreen_button = self._icon_button("expand", "Fullscreen")
        self.fullscreen_button.hide()
        self.favorite_button = self._icon_button("heart", "Add to favorites")
        self.favorite_button.hide()
        self.favorite_button.clicked.connect(self.toggle_favorite)
        self.full_image_button = self._icon_button("images", "Load original-resolution image")
        self.full_image_button.setFixedSize(34, 26)
        self.full_image_button.setIconSize(QSize(17, 17))
        self.full_image_button.setToolTip("Load original-resolution image")
        self.full_image_button.hide()
        self.full_image_button.clicked.connect(self.load_full_image)
        self._build_filter_menu()
        self.refresh_button = self._icon_button("refresh-cw", "Refresh current view")
        self.download_button = self._icon_button("download", "Download current image")
        self.title_bar.add_action(self.refresh_button)
        self.title_bar.add_action(self.download_button)
        self.title_bar.add_action(self.settings_button)

        self.pages = QStackedWidget()
        self.random_page = QWidget()
        random_layout = QVBoxLayout(self.random_page)
        random_layout.setContentsMargins(0, 0, 0, 0)
        random_layout.setSpacing(6)
        self.random_ambient = self._create_ambient_layer(self.random_page)
        self.random_scroll = QScrollArea()
        self.random_scroll.setWidgetResizable(False)
        self.random_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.random_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.random_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.random_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.random_image = ZoomImage()
        self.random_image.setObjectName("randomImage")
        self.random_image.setMinimumSize(1, 1)
        self.random_scroll.setWidget(self.random_image)
        self.random_image.viewport = self.random_scroll.viewport()
        self.random_image.scroll_area = self.random_scroll
        self.random_image.zoomChanged.connect(
            lambda zoomed, area=self.random_scroll: self._set_zoom_scrollbars(area, zoomed)
        )
        self.random_image.setMouseTracking(True)
        self.random_video = VideoPlayerWidget()
        self.random_video.set_volume(self._saved_video_volume())
        self.random_video.set_resolution_limit(self._saved_video_resolution())
        self.random_video.volumeChanged.connect(self._save_video_volume)
        self.random_video.resolutionChanged.connect(
            lambda height: self._change_video_resolution("random", height)
        )
        self.random_video.bufferingChanged.connect(
            lambda buffering: self._on_video_buffering("random", buffering)
        )
        self.random_video.playbackStatusChanged.connect(
            lambda status: self._on_video_status("random", status)
        )
        self.random_video.playbackActiveChanged.connect(
            lambda playing: self._on_video_playback_active("random", playing)
        )
        self.random_video.playRequested.connect(self._play_random_video)
        self.random_media_stack = QStackedWidget()
        self.random_media_stack.setStyleSheet("background: transparent; border: 0;")
        self.random_media_stack.addWidget(self.random_scroll)
        self.random_media_stack.addWidget(self.random_video)
        random_layout.addWidget(self.random_media_stack, 1)
        self.random_video_fullscreen_button = self._icon_button("expand", "Fullscreen video")
        self.random_video.fullscreen_toggle = self.random_video_fullscreen_button
        self.random_video.add_control_action(self.random_video_fullscreen_button)
        self.random_video_fullscreen_button.clicked.connect(self._toggle_fullscreen)

        self.random_fullscreen_toolbar = QFrame(self.random_page)
        self.random_fullscreen_toolbar.setObjectName("fullscreenToolbar")
        self.random_fullscreen_toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        random_fullscreen_layout = QHBoxLayout(self.random_fullscreen_toolbar)
        random_fullscreen_layout.setContentsMargins(12, 6, 12, 6)
        random_fullscreen_layout.setSpacing(14)
        self.random_fullscreen_refresh_button = self._icon_button("refresh-cw", "Refresh random image")
        self.random_fullscreen_favorite_button = self._icon_button("heart", "Add to favorites")
        self.random_fullscreen_download_button = self._icon_button("download", "Download image")
        self.random_fullscreen_exit_button = self._icon_button("restore", "Exit fullscreen")
        for button in (
            self.random_fullscreen_refresh_button,
            self.random_fullscreen_favorite_button,
            self.random_fullscreen_download_button,
            self.random_fullscreen_exit_button,
        ):
            random_fullscreen_layout.addWidget(button)
            button.setMouseTracking(True)
            button.installEventFilter(self)
        self.random_fullscreen_refresh_button.clicked.connect(self.refresh)
        self.random_fullscreen_favorite_button.clicked.connect(self.toggle_favorite)
        self.random_fullscreen_download_button.clicked.connect(self.download_active_image)
        self.random_fullscreen_exit_button.clicked.connect(self._exit_fullscreen)
        self.random_video_refresh_action = self._icon_button("refresh-cw", "Refresh video")
        self.random_video_favorite_action = self._icon_button("heart", "Add to favorites")
        self.random_video_download_action = self._icon_button("download", "Download video")
        self.random_video_exit_action = self._icon_button("restore", "Exit fullscreen")
        for action in (
            self.random_video_refresh_action,
            self.random_video_favorite_action,
            self.random_video_download_action,
            self.random_video_exit_action,
        ):
            self.random_video.add_fullscreen_action(action)
        self.random_video_refresh_action.clicked.connect(self.refresh)
        self.random_video_favorite_action.clicked.connect(self.toggle_favorite)
        self.random_video_download_action.clicked.connect(self.download_active_image)
        self.random_video_exit_action.clicked.connect(self._exit_fullscreen)
        self.random_fullscreen_toolbar.hide()
        self.random_fullscreen_toolbar.setMouseTracking(True)
        self.random_fullscreen_toolbar.installEventFilter(self)
        for widget in (self.random_page, self.random_scroll, self.random_scroll.viewport(), self.random_image,
                       self.random_video, self.random_video.video_canvas, self.random_video.video,
                       self.random_video.controls_frame, self.random_video.position,
                       self.random_video.volume_button, self.random_video.volume_slider,
                       self.random_video.time_label, self.random_video.buffering_overlay,
                       self.random_video.buffering_bar,
                       self.random_video.play_overlay,
                       self.random_video.play_pause, self.random_media_stack,
                       self.random_video_fullscreen_button, self.random_video_refresh_action,
                       self.random_video_favorite_action, self.random_video_download_action,
                       self.random_video_exit_action):
            widget.setMouseTracking(True)
            widget.installEventFilter(self)
        self.pages.addWidget(self.random_page)

        self.gallery_page = QWidget()
        gallery_layout = QVBoxLayout(self.gallery_page)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        # Provider notices are short-lived overlays, so they do not reserve a
        # permanent row or push the search results down.
        self.gallery_status = QLabel(self.gallery_page)
        self.gallery_status.setObjectName("galleryNotice")
        self.gallery_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gallery_status.setWordWrap(True)
        self.gallery_status.setStyleSheet(
            "QLabel#galleryNotice { background: rgba(55, 56, 64, 245); "
            "color: #e2e2e6; border: 0; border-radius: 24px; "
            "padding: 8px 14px; }"
        )
        self._gallery_notice_opacity = QGraphicsOpacityEffect(self.gallery_status)
        self.gallery_status.setGraphicsEffect(self._gallery_notice_opacity)
        self._gallery_notice_animation = QPropertyAnimation(
            self._gallery_notice_opacity, b"opacity", self
        )
        self._gallery_notice_animation.setDuration(240)
        self._gallery_notice_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._gallery_notice_animation.finished.connect(self._finish_gallery_notice_fade)
        self.gallery_status.hide()
        self.gallery_body = QStackedWidget()
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.gallery_scroll.setObjectName("searchScrollArea")
        self.gallery_scroll.verticalScrollBar().setObjectName("searchVerticalScrollBar")
        self.gallery_scroll.horizontalScrollBar().setObjectName("searchHorizontalScrollBar")
        self.gallery_scroll.verticalScrollBar().setStyleSheet(CAPSULE_SCROLLBAR_STYLE)
        self.gallery_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery_content = QWidget()
        self.gallery_rows = QVBoxLayout(self.gallery_content)
        self.gallery_rows.setContentsMargins(0, 0, 0, 0)
        self.gallery_rows.setSpacing(4)
        self.gallery_scroll.setWidget(self.gallery_content)
        self.gallery_body.addWidget(self.gallery_scroll)
        self.gallery_loading = QWidget()
        self.gallery_loading.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.gallery_loading.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.gallery_loading.setStyleSheet("background: transparent;")
        loading_layout = QVBoxLayout(self.gallery_loading)
        loading_layout.addStretch(1)
        self.gallery_loading_indicator = CircularProgressIndicator(size=30)
        self.gallery_loading_indicator.setObjectName("galleryLoadingIndicator")
        loading_layout.addWidget(self.gallery_loading_indicator, 0, Qt.AlignmentFlag.AlignCenter)
        loading_layout.addStretch(1)
        self.gallery_body.addWidget(self.gallery_loading)
        gallery_layout.addWidget(self.gallery_body, 1)
        page_nav = QHBoxLayout()
        self.previous_button = self._icon_button("chevron-left", "Previous page")
        self.page_label = QLabel("Page 1")
        self.next_button = self._icon_button("chevron-right", "Next page")
        page_nav.addStretch(1)
        page_nav.addWidget(self.previous_button)
        page_nav.addWidget(self.page_label)
        page_nav.addWidget(self.next_button)
        page_nav.addStretch(1)
        gallery_layout.addLayout(page_nav)
        self.pages.addWidget(self.gallery_page)

        self.detail_page = QWidget()
        detail_layout = QVBoxLayout(self.detail_page)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)
        self.detail_ambient = self._create_ambient_layer(self.detail_page)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(False)
        self.detail_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_image = ZoomImage()
        self.detail_image.setObjectName("detailImage")
        self.detail_image.setMinimumSize(1, 1)
        self.detail_scroll.setWidget(self.detail_image)
        self.detail_image.viewport = self.detail_scroll.viewport()
        self.detail_image.scroll_area = self.detail_scroll
        self.detail_image.zoomChanged.connect(
            lambda zoomed, area=self.detail_scroll: self._set_zoom_scrollbars(area, zoomed)
        )
        self.detail_image.swipeRequested.connect(self._swipe_detail)
        self.detail_video = VideoPlayerWidget()
        self.detail_video.set_volume(self._saved_video_volume())
        self.detail_video.set_resolution_limit(self._saved_video_resolution())
        self.detail_video.volumeChanged.connect(self._save_video_volume)
        self.detail_video.resolutionChanged.connect(
            lambda height: self._change_video_resolution("detail", height)
        )
        self.detail_video.bufferingChanged.connect(
            lambda buffering: self._on_video_buffering("detail", buffering)
        )
        self.detail_video.playbackStatusChanged.connect(
            lambda status: self._on_video_status("detail", status)
        )
        self.detail_video.playbackActiveChanged.connect(
            lambda playing: self._on_video_playback_active("detail", playing)
        )
        self.detail_video.playRequested.connect(self._play_detail_video)
        self.detail_media_stack = QStackedWidget()
        self.detail_media_stack.setStyleSheet("background: transparent; border: 0;")
        self.detail_media_stack.addWidget(self.detail_scroll)
        self.detail_media_stack.addWidget(self.detail_video)
        self.detail_video_fullscreen_button = self._icon_button("expand", "Fullscreen video")
        self.detail_video.fullscreen_toggle = self.detail_video_fullscreen_button
        self.detail_video.add_control_action(self.detail_video_fullscreen_button)
        self.detail_video_fullscreen_button.clicked.connect(self._toggle_fullscreen)

        self.detail_previous_button = self._icon_button("chevron-left", "Previous image")
        self.detail_next_button = self._icon_button("chevron-right", "Next image")
        for button in (self.detail_previous_button, self.detail_next_button):
            button.setParent(self.detail_page)
            button.setObjectName("detailNavigation")
            button.setFixedSize(42, 42)
            button.setMouseTracking(True)
            button.installEventFilter(self)
        self.detail_previous_button.clicked.connect(lambda: self._swipe_detail(-1))
        self.detail_next_button.clicked.connect(lambda: self._swipe_detail(1))
        self.detail_video_previous_overlay = self._icon_button(
            "chevron-left", "Previous video"
        )
        self.detail_video_next_overlay = self._icon_button(
            "chevron-right", "Next video"
        )
        for button in (
            self.detail_video_previous_overlay,
            self.detail_video_next_overlay,
        ):
            button.setParent(self.detail_page)
            button.setObjectName("detailNavigation")
            button.setFixedSize(42, 42)
            button.hide()
            button.setMouseTracking(True)
            button.installEventFilter(self)
        self.detail_video_previous_overlay.clicked.connect(
            lambda: self._swipe_detail(-1)
        )
        self.detail_video_next_overlay.clicked.connect(lambda: self._swipe_detail(1))
        detail_view_layout = QHBoxLayout()
        detail_view_layout.setContentsMargins(0, 0, 0, 0)
        detail_view_layout.setSpacing(0)
        detail_view_layout.addWidget(self.detail_media_stack, 1)
        detail_layout.addLayout(detail_view_layout, 1)
        self.detail_previous_button.hide()
        self.detail_next_button.hide()

        self.fullscreen_toolbar = QFrame(self.detail_page)
        self.fullscreen_toolbar.setObjectName("fullscreenToolbar")
        self.fullscreen_toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fullscreen_layout = QHBoxLayout(self.fullscreen_toolbar)
        fullscreen_layout.setContentsMargins(12, 6, 12, 6)
        fullscreen_layout.setSpacing(14)
        self.fullscreen_previous_button = self._icon_button("chevron-left", "Previous image")
        self.fullscreen_favorite_button = self._icon_button("heart", "Add to favorites")
        self.fullscreen_download_button = self._icon_button("download", "Download image")
        self.fullscreen_next_button = self._icon_button("chevron-right", "Next image")
        self.fullscreen_exit_button = self._icon_button("restore", "Exit fullscreen")
        for button in (
            self.fullscreen_previous_button,
            self.fullscreen_favorite_button,
            self.fullscreen_download_button,
            self.fullscreen_next_button,
            self.fullscreen_exit_button,
        ):
            fullscreen_layout.addWidget(button)
        self.fullscreen_previous_button.clicked.connect(lambda: self._swipe_detail(-1))
        self.fullscreen_favorite_button.clicked.connect(self.toggle_favorite)
        self.fullscreen_download_button.clicked.connect(self.download_active_image)
        self.fullscreen_next_button.clicked.connect(lambda: self._swipe_detail(1))
        self.fullscreen_exit_button.clicked.connect(self._exit_fullscreen)
        self.detail_video_favorite_action = self._icon_button("heart", "Add to favorites")
        self.detail_video_download_action = self._icon_button("download", "Download video")
        self.detail_video_previous_action = self._icon_button("chevron-left", "Previous video")
        self.detail_video_next_action = self._icon_button("chevron-right", "Next video")
        self.detail_video_exit_action = self._icon_button("restore", "Exit fullscreen")
        for action in (
            self.detail_video_favorite_action,
            self.detail_video_download_action,
            self.detail_video_previous_action,
            self.detail_video_next_action,
            self.detail_video_exit_action,
        ):
            self.detail_video.add_fullscreen_action(action)
        self.detail_video_favorite_action.clicked.connect(self.toggle_favorite)
        self.detail_video_download_action.clicked.connect(self.download_active_image)
        self.detail_video_previous_action.clicked.connect(lambda: self._swipe_detail(-1))
        self.detail_video_next_action.clicked.connect(lambda: self._swipe_detail(1))
        self.detail_video_exit_action.clicked.connect(self._exit_fullscreen)
        self.fullscreen_toolbar.hide()

        for widget in (
            self.detail_page, self.detail_scroll, self.detail_scroll.viewport(), self.detail_image,
            self.detail_video, self.detail_video.video_canvas, self.detail_video.video,
            self.detail_video.controls_frame, self.detail_video.position,
            self.detail_video.volume_button, self.detail_video.volume_slider,
            self.detail_video.time_label, self.detail_video.buffering_overlay,
            self.detail_video.buffering_bar,
            self.detail_media_stack,
            self.detail_video.play_overlay, self.detail_video.play_pause,
            self.detail_video_fullscreen_button,
            self.detail_video_favorite_action, self.detail_video_download_action,
            self.detail_video_previous_action, self.detail_video_next_action,
            self.detail_video_exit_action,
            self.fullscreen_toolbar, self.fullscreen_previous_button, self.fullscreen_favorite_button,
            self.fullscreen_download_button, self.fullscreen_next_button, self.fullscreen_exit_button,
        ):
            widget.setMouseTracking(True)
            widget.installEventFilter(self)
        self.pages.addWidget(self.detail_page)
        content_layout.addWidget(self.pages, 1)
        body_layout.addWidget(content, 1)
        root_layout.addWidget(body, 1)

        self.setCentralWidget(root)
        status = QStatusBar()
        status.setObjectName("statusBar")
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        self.footer_meta = QLabel("")
        self.footer_meta.setObjectName("footerMeta")
        status.addPermanentWidget(self.footer_meta, 1)
        status.addPermanentWidget(self.full_image_button)
        for button in (self.favorite_button, self.fullscreen_button):
            button.setFixedSize(34, 26)
            button.setIconSize(QSize(17, 17))
            status.addPermanentWidget(button)
        status.addPermanentWidget(QSizeGrip(self))

        self.download_button.clicked.connect(self.download_active_image)
        self.fullscreen_button.clicked.connect(self._toggle_fullscreen)
        self.refresh_button.clicked.connect(self.refresh)
        self.back_button.clicked.connect(self.back_to_results)
        self.previous_button.clicked.connect(lambda: self.load_page(max(1, self.current_page - 1)))
        self.next_button.clicked.connect(lambda: self.load_page(self.current_page + 1))

    def _build_filter_menu(self) -> None:
        menu = QMenu(self)
        menu.setMinimumWidth(180)
        self.provider_actions = {}
        provider_group = QActionGroup(menu)
        provider_group.setExclusive(True)
        provider_menu = menu.addMenu("Provider")
        provider_menu.setMinimumWidth(180)
        for name in ("All", "Danbooru", "yande.re", "Gelbooru", "Rule34.xxx"):
            action = provider_menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == self.selected_provider)
            provider_group.addAction(action)
            action.triggered.connect(lambda checked, value=name: self.provider_changed(value) if checked else None)
            self.provider_actions[name] = action

        self.rating_actions = {}
        rating_group = QActionGroup(menu)
        rating_group.setExclusive(True)
        rating_menu = menu.addMenu("Rating")
        rating_menu.setMinimumWidth(180)
        for title, value in (("Only SFW", "sfw"), ("Only NSFW", "nsfw"), ("Show All", "all")):
            action = rating_menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(value == self.selected_rating)
            rating_group.addAction(action)
            action.triggered.connect(lambda checked, selected=value: self.rating_changed(selected) if checked else None)
            self.rating_actions[value] = action

        self.theme_actions = {}
        theme_group = QActionGroup(menu)
        theme_group.setExclusive(True)
        theme_menu = menu.addMenu("Theme")
        theme_menu.setMinimumWidth(180)
        for theme in ("Dark", "Light", "System", "OLED Dark"):
            action = theme_menu.addAction(theme)
            action.setCheckable(True)
            action.setChecked(theme == self.current_theme)
            theme_group.addAction(action)
            action.triggered.connect(
                lambda checked, selected=theme: self.change_theme(selected) if checked else None
            )
            self.theme_actions[theme] = action

        self.media_actions = {}
        media_group = QActionGroup(menu)
        media_group.setExclusive(True)
        media_menu = menu.addMenu("Media Type")
        media_menu.setObjectName("mediaTypeMenu")
        media_menu.setMinimumWidth(132)
        media_menu.setMaximumWidth(150)
        for title, value in (("Image Only", "image"), ("Video Only", "video"), ("Show All", "all")):
            action = media_menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(value == self.selected_media)
            media_group.addAction(action)
            action.triggered.connect(
                lambda checked, selected=value: self.media_changed(selected) if checked else None
            )
            self.media_actions[value] = action

        self.image_credits_action = menu.addAction("Media Info")
        self.image_credits_action.setVisible(False)
        self.image_credits_action.triggered.connect(self.show_image_credits)
        menu.addAction("Favorites", self.show_favorites)
        menu.addSeparator()
        menu.addAction("Downloads", self.downloads.show)
        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self.open_preferences)
        menu.addSeparator()
        self.settings_button.setMenu(menu)
        self._update_filter_tooltip()

    def _update_filter_tooltip(self) -> None:
        rating_names = {"sfw": "Only SFW", "nsfw": "Only NSFW", "all": "Show All"}
        media_names = {"image": "Image Only", "video": "Video Only", "all": "Show All"}
        tooltip = (
            f"Settings | {self.selected_provider} | {rating_names[self.selected_rating]}"
            f" | {media_names[self.selected_media]}"
        )
        self.settings_button.setToolTip(tooltip)
        self.settings_button.setAccessibleName(tooltip)

    def _favorite_posts(self) -> list[ImagePost]:
        saved = self.settings.get("favorites/posts", [])
        if not isinstance(saved, (list, tuple)):
            return []
        posts = []
        for value in saved:
            if not isinstance(value, dict):
                continue
            try:
                posts.append(ImagePost(
                    post_id=str(value["post_id"]),
                    provider=str(value["provider"]),
                    image_url=str(value["image_url"]),
                    preview_urls=tuple(map(str, value.get("preview_urls", []))),
                    rating=str(value.get("rating", "q")),
                    tags=frozenset(map(str, value.get("tags", []))),
                    artists=tuple(map(str, value.get("artists", []))),
                    source=str(value.get("source", "")),
                    checksum=str(value.get("checksum", "")),
                    title=str(value.get("title", "")),
                    media_type=str(value.get("media_type", "image")),
                    width=int(value.get("width", 0) or 0),
                    height=int(value.get("height", 0) or 0),
                    video_variants=tuple(
                        (str(item[0]), int(item[1] or 0), int(item[2] or 0))
                        for item in value.get("video_variants", [])
                        if isinstance(item, (list, tuple)) and len(item) == 3
                    ),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return posts

    def _save_favorite_posts(self, posts: list[ImagePost]) -> None:
        self.settings.set("favorites/posts", [{
            "post_id": post.post_id,
            "provider": post.provider,
            "image_url": post.image_url,
            "preview_urls": list(post.preview_urls),
            "rating": post.rating,
            "tags": sorted(post.tags),
            "artists": list(post.artists),
            "source": post.source,
            "checksum": post.checksum,
            "title": post.title,
            "media_type": post.media_type,
            "width": post.width,
            "height": post.height,
            "video_variants": [list(item) for item in post.video_variants],
        } for post in posts])

    @staticmethod
    def _image_size_text(post: ImagePost, pixmap: QPixmap, *, full: bool = False) -> str:
        displayed = f"{pixmap.width()} x {pixmap.height()}"
        if full:
            return f"Original {displayed}"
        if not post.width or not post.height:
            return f"Preview {displayed} | Original size not reported"
        original = f"{post.width} x {post.height}"
        if displayed == original:
            return f"Preview {displayed}"
        return f"Preview {displayed} | Original {original}"

    def _set_detail_image_footer(self, post: ImagePost | None, pixmap: QPixmap) -> None:
        if (
            post is None
            or pixmap.isNull()
            or self.pages.currentWidget() is not self.detail_page
            or self.detail_origin not in {"search", "favorites"}
            or self.detail_post is None
            or self.detail_post.post_id != post.post_id
            or post.media_type != "image"
        ):
            self.footer_meta.clear()
            return
        self.footer_meta.setText(
            f"{post.provider} | {rating_label(post.rating)} | "
            f"{self._image_size_text(post, pixmap, full=self._full_image_loaded)}"
        )

    def _set_random_image_footer(self, post: ImagePost | None, pixmap: QPixmap) -> None:
        random_post = getattr(self, "random_post", None)
        if (
            post is None
            or pixmap.isNull()
            or self.pages.currentWidget() is not self.random_page
            or random_post is None
            or random_post.post_id != post.post_id
            or post.media_type != "image"
        ):
            self.footer_meta.clear()
            return
        self.footer_meta.setText(
            f"{post.provider} | {rating_label(post.rating)} | "
            f"{self._image_size_text(post, pixmap, full=self._full_image_loaded)}"
        )

    def _set_search_footer_counts(self) -> None:
        if self.pages.currentWidget() is not self.gallery_page:
            return
        image_count = sum(post.media_type != "video" for post in self.posts)
        video_count = len(self.posts) - image_count
        if self.posts:
            image_label = "image" if image_count == 1 else "images"
            video_label = "video" if video_count == 1 else "videos"
            self.footer_meta.setText(
                f"{image_count} {image_label}, {video_count} {video_label}"
            )
        else:
            self.footer_meta.clear()

    def _active_post(self) -> ImagePost | None:
        if self.pages.currentWidget() is self.random_page:
            return getattr(self, "random_post", None)
        if self.pages.currentWidget() is self.detail_page:
            return self.detail_post
        return None

    def _sync_favorite_buttons(self) -> None:
        post = self._active_post()
        image_ready = bool(
            post
            and (
                (self.pages.currentWidget() is self.random_page and not self.random_image.original.isNull())
                or (self.pages.currentWidget() is self.detail_page and not self.detail_image.original.isNull())
                or (post.media_type == "video" and self.pages.currentWidget() in (self.random_page, self.detail_page))
            )
        )
        is_favorite = bool(post and any(favorite_key(item) == favorite_key(post)
                                        for item in self._favorite_posts()))
        icon_name = "heart-filled" if is_favorite else "heart"
        tooltip = "Remove from favorites" if is_favorite else "Add to favorites"
        for button in (
            self.favorite_button,
            self.random_fullscreen_favorite_button,
            self.fullscreen_favorite_button,
            self.random_video_favorite_action,
            self.detail_video_favorite_action,
        ):
            button.setIcon(self._icon(icon_name))
            button.setProperty("iconName", icon_name)
            button.setToolTip(tooltip)
            button.setEnabled(image_ready)
        in_image_view = self.pages.currentWidget() in (self.random_page, self.detail_page)
        self.favorite_button.setVisible(bool(image_ready and in_image_view and not self._fullscreen_active))

    def toggle_favorite(self) -> None:
        post = self._active_post()
        if post is None:
            return
        posts = self._favorite_posts()
        key = favorite_key(post)
        existing = next((saved for saved in posts if favorite_key(saved) == key), None)
        if existing:
            posts = [saved for saved in posts if favorite_key(saved) != key]
            if self.favorites_dialog:
                self.favorites_dialog.remove_favorite(key)
        else:
            posts.append(post)
        self._save_favorite_posts(posts)
        self._sync_favorite_buttons()
        if self.detail_origin == "favorites":
            self._update_detail_navigation()

    def show_favorites(self) -> None:
        if self.favorites_dialog and self.favorites_dialog.isVisible():
            self.favorites_dialog.raise_()
            self.favorites_dialog.activateWindow()
            return
        if self.settings.get_bool("favorites_lock/enabled"):
            if not has_pin(self.settings, "favorites_lock"):
                BackupMessageDialog.notify(
                    self, "Favorites locked",
                    "The Favorites PIN is unavailable. Reset it from Safety & Privacy.",
                )
                return
            pin_dialog = PinPromptDialog(
                title="Unlock Favorites",
                description="Enter your Favorites PIN to continue.",
                verify_current=lambda value: verify_pin(self.settings, "favorites_lock", value),
                parent=self,
            )
            if pin_dialog.exec() != QDialog.DialogCode.Accepted:
                return
        posts = [post for post in self._favorite_posts() if self._parent_allows_post(post)]
        token = str(uuid4())
        dialog = FavoritesDialog(posts, self._open_favorite, self._remove_favorite, self)
        self.favorites_dialog = dialog
        self.favorites_dialog_token = token
        dialog.finished.connect(lambda _result, current=token: self._clear_favorites_dialog(current))
        for post in posts:
            key = favorite_key(post)
            cached = self.thumbnail_cache.get(post.post_id)
            if cached:
                dialog.set_thumbnail(key, cached)
            else:
                candidates = post.preview_urls or (post.image_url,)
                self._submit(f"favorite-thumbnail:{token}/{key}", self._fetch_decoded_candidates, candidates)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _clear_favorites_dialog(self, token: str) -> None:
        if self.favorites_dialog_token == token:
            self.favorites_dialog = None
            self.favorites_dialog_token = ""

    def _refresh_favorites_dialog(self, posts: list[ImagePost]) -> None:
        posts = [post for post in posts if self._parent_allows_post(post)]
        self._favorite_navigation_posts = list(posts)
        dialog = self.favorites_dialog
        if dialog:
            dialog.posts = list(posts)
            keys = {favorite_key(post) for post in posts}
            dialog.thumbnail_cache = {
                key: pixmap for key, pixmap in dialog.thumbnail_cache.items() if key in keys
            }
            dialog.thumbnail_errors.intersection_update(keys)
            dialog._rebuild()
            for post in posts:
                key = favorite_key(post)
                cached = self.thumbnail_cache.get(post.post_id)
                if cached:
                    dialog.set_thumbnail(key, cached)
                elif key not in dialog.thumbnail_errors:
                    candidates = post.preview_urls or (post.image_url,)
                    self._submit(
                        f"favorite-thumbnail:{self.favorites_dialog_token}/{key}",
                        self._fetch_decoded_candidates,
                        candidates,
                    )
        self._sync_favorite_buttons()
        if self.detail_origin == "favorites":
            self._update_detail_navigation()

    def _remove_favorite(self, key: str) -> None:
        posts = [post for post in self._favorite_posts() if favorite_key(post) != key]
        self._save_favorite_posts(posts)
        self._favorite_navigation_posts = [post for post in self._favorite_navigation_posts if favorite_key(post) != key]
        if self.favorites_dialog:
            self.favorites_dialog.remove_favorite(key)
        self._sync_favorite_buttons()
        if self.detail_origin == "favorites":
            self._update_detail_navigation()

    def _open_favorite(self, post: ImagePost) -> None:
        if not self._parent_allows_post(post):
            BackupMessageDialog.notify(
                self, "Parental control",
                "This favorite is above the guardian's content limits.",
            )
            return
        dialog = self.favorites_dialog
        if dialog:
            self._favorite_navigation_posts = list(dialog.posts)
        self._opening_favorite = True
        try:
            self.open_post(post)
        finally:
            self._opening_favorite = False

    def _icon(self, name: str) -> QIcon:
        if self.current_theme == "System":
            system_window = QApplication.palette().color(QPalette.ColorRole.Window)
            resolved_theme = "Dark" if system_window.lightness() < 128 else "Light"
        else:
            resolved_theme = self.current_theme
        cache_key = (name, resolved_theme)
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        asset = Path(__file__).resolve().parent.parent / "assets" / f"{name}.svg"
        svg = asset.read_text(encoding="utf-8")
        stroke = "#515A78" if resolved_theme == "Light" else "#A9B1D6"
        svg = re.sub(r'stroke="#[0-9a-fA-F]{6}"', f'stroke="{stroke}"', svg)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon = QIcon(pixmap)
        self._icon_cache[cache_key] = icon
        return icon

    @staticmethod
    def _app_icon() -> QIcon:
        asset = Path(__file__).resolve().parent.parent / "assets" / "waifugallery.png"
        return QIcon(str(asset))

    def _icon_button(self, name: str, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName(f"action_{name}")
        button.setProperty("iconName", name)
        button.setProperty("iconAction", True)
        button.setIcon(self._icon(name))
        button.setIconSize(QSize(20, 20))
        button.setFixedSize(42, 36)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        self._icon_buttons.append(button)
        return button

    def change_theme(self, theme: str) -> None:
        if theme not in ("Dark", "Light", "System", "OLED Dark"):
            return
        self.current_theme = theme
        self.settings.set("appearance/theme", theme)
        self._icon_cache.clear()
        self._apply_theme(theme)
        for button in self._icon_buttons:
            icon_name = button.property("iconName")
            if icon_name:
                button.setIcon(self._icon(icon_name))
        self.title_bar.refresh_icons()
        self.title_bar.refresh_search_icon()
        for name, action in self.theme_actions.items():
            action.setChecked(name == theme)

    def _apply_theme(self, theme: str | None = None) -> None:
        theme = theme or self.current_theme
        if theme == "System":
            system_window = QApplication.palette().color(QPalette.ColorRole.Window)
            theme = "Dark" if system_window.lightness() < 128 else "Light"

        if theme == "Light":
            palette = {
                "BG": "#F4F6FB", "SIDEBAR": "#EAEEF7", "PANEL": "#FFFFFF",
                "TEXT": "#424B68", "STRONG": "#252B40", "MUTED": "#697491",
                "BORDER": "#D8DEED", "HOVER": "#EEF1F9", "ACCENT": "#7557D6",
                "BLUE": "#4F74DC", "ACTIVE": "#E5E9F6", "PRESSED": "#E0E5F1",
                "DISABLED": "#EEF0F6", "MENU_SELECTED": "#E5E9F6",
                "SEARCH_BG": "#FFFFFF", "SEARCH_BORDER": "#B9C1D5",
            }
        elif theme == "OLED Dark":
            palette = {
                "BG": "#000000", "SIDEBAR": "#08090D", "PANEL": "#101116",
                "TEXT": "#B6BCD2", "STRONG": "#E2E6F4", "MUTED": "#81879D",
                "BORDER": "#292B35", "HOVER": "#1A1B22", "ACCENT": "#C4A1FF",
                "BLUE": "#8DB4FF", "ACTIVE": "#171820", "PRESSED": "#101116",
                "DISABLED": "#111217", "MENU_SELECTED": "#252633",
                "SEARCH_BG": "#000000", "SEARCH_BORDER": "#41434F",
            }
        else:
            palette = {
                "BG": "#171923", "SIDEBAR": "#1B1D2A", "PANEL": "#222638",
                "TEXT": "#A9B1D6", "STRONG": "#C0CAF5", "MUTED": "#7982A9",
                "BORDER": "#343A55", "HOVER": "#2D334B", "ACCENT": "#BB9AF7",
                "BLUE": "#7AA2F7", "ACTIVE": "#292E46", "PRESSED": "#202438",
                "DISABLED": "#202230", "MENU_SELECTED": "#343B58",
                "SEARCH_BG": "#11131B", "SEARCH_BORDER": "#545B78",
            }

        stylesheet = """
            * { font-family: "Inter", "Segoe UI", sans-serif; font-size: 10pt; }
            QMainWindow { background: transparent; border: 1px solid __BORDER__; border-radius: 12px; }
            QDialog, QWidget#appRoot, QWidget#contentArea { background: __BG__; color: __TEXT__; }
            QDialog#settingsDialog { background: transparent; border: 0; }
            QDialog#pinPromptDialog { background: transparent; border: 0; }
            QWidget#pinPromptSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 12px; }
            QLineEdit#pinPromptCurrent, QLineEdit#pinPromptNew, QLineEdit#pinPromptConfirm { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; border-radius: 14px; padding: 8px 12px; }
            QLabel#pinPromptError { color: #F7768E; }
            QWidget#settingsSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 18px; }
            QDialog#backupFileDialog { background: transparent; border: 0; }
            QWidget#backupFileSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 12px; }
            QDialog#backupPromptDialog { background: transparent; border: 0; }
            QWidget#backupPromptSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 12px; }
            QLineEdit#backupPassphrase, QLineEdit#backupPassphraseConfirm { background: __PANEL__; color: __TEXT__; border: 1px solid __BORDER__; border-radius: 14px; padding: 8px 12px; }
            QLabel#backupPromptError { color: #F7768E; }
            QPushButton#backupDestructiveButton { color: #F7768E; }
            QWidget#settingsPage QFrame#backupNotice, QWidget#settingsPage QFrame#backupActionCard { background: __SIDEBAR__; border: 1px solid __BORDER__; border-radius: 12px; }
            QTreeView#backupFileTree { background: __PANEL__; color: __TEXT__; border: 1px solid __BORDER__; border-radius: 10px; outline: 0; }
            QTreeView#backupFileTree::item { padding: 5px 6px; border-radius: 5px; }
            QTreeView#backupFileTree::item:selected { background: __ACTIVE__; color: __STRONG__; }
            QDialog#favoritesDialog { background: transparent; border: 0; }
            QWidget#favoritesSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 12px; }
            QWidget#favoritesTitleBar { background: __SIDEBAR__; border-bottom: 1px solid __BORDER__; border-top-left-radius: 12px; border-top-right-radius: 12px; }
            QDialog#downloadsDialog, QDialog#releaseNotesDialog { background: transparent; border: 0; }
            QWidget#downloadsSurface, QWidget#releaseNotesSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 12px; }
            QWidget#dialogTitleBar { background: __SIDEBAR__; border-bottom: 1px solid __BORDER__; border-top-left-radius: 12px; border-top-right-radius: 12px; }
            QLabel#downloadsWindowTitle { color: __STRONG__; font-size: 11pt; font-weight: 650; }
            QPushButton#downloadsCloseButton { background: transparent; border: 0; border-radius: 7px; padding: 0; }
            QPushButton#downloadsCloseButton:hover { background: #F7768E; }
            QListWidget#downloadsList { background: transparent; border: 0; outline: 0; }
            QListWidget#downloadsList::item, QListWidget#downloadsList::item:selected { background: transparent; border: 0; padding: 0; }
            QWidget#downloadItemCard { background: __SIDEBAR__; border: 1px solid __BORDER__; border-radius: 12px; }
            QLabel#downloadItemIcon { background: __PANEL__; border-radius: 8px; }
            QLabel#downloadFilename { color: __STRONG__; font-size: 10pt; font-weight: 600; }
            QLabel#downloadStatus { color: __MUTED__; font-size: 9pt; }
            QProgressBar#downloadProgress { background: __PANEL__; border: 0; border-radius: 2px; }
            QProgressBar#downloadProgress::chunk { background: __ACCENT__; border-radius: 2px; }
            QPushButton#downloadCancelButton { background: transparent; border: 0; border-radius: 8px; }
            QPushButton#downloadCancelButton:hover { background: __ACTIVE__; }
            QPushButton#downloadCancelButton:disabled { background: transparent; }
            QLabel#releaseNotesHeading { color: __STRONG__; font-size: 15pt; font-weight: 700; }
            QLabel#releaseNotesVersion { color: __MUTED__; }
            QLabel#favoritesWindowTitle { color: __STRONG__; font-size: 11pt; font-weight: 650; }
            QPushButton#favoritesCloseButton { background: transparent; border: 0; border-radius: 7px; padding: 0; }
            QPushButton#favoritesCloseButton:hover { background: #F7768E; }
            QDialog#mediaInfoDialog { background: transparent; border: 0; }
            QWidget#mediaInfoSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 18px; }
            QWidget#mediaInfoTitleBar { background: transparent; }
            QLabel#mediaInfoWindowTitle { color: __STRONG__; font-size: 11pt; font-weight: 650; }
            QLabel#mediaInfoFieldLabel { color: __MUTED__; min-width: 62px; }
            QPushButton#mediaInfoCloseButton { background: transparent; border: 0; border-radius: 15px; padding: 0; }
            QPushButton#mediaInfoCloseButton:hover { background: #F7768E; }
            QWidget#settingsTitleBar { background: transparent; }
            QLabel#settingsWindowTitle { color: __STRONG__; font-size: 11pt; font-weight: 650; }
            QPushButton#settingsCloseButton { background: transparent; border: 0; border-radius: 15px; padding: 0; }
            QPushButton#settingsCloseButton:hover { background: #F7768E; }
            QWidget#settingsSidebar { background: __SIDEBAR__; border-radius: 16px; }
            QStackedWidget#settingsPages { background: transparent; border: 0; }
            QWidget#settingsPage { background: __PANEL__; color: __TEXT__; border-radius: 18px; }
            QWidget#settingsPage QLabel { background: transparent; }
            QWidget#settingsPage QFrame { background: transparent; border-color: __BORDER__; }
            QWidget#settingsPage QFrame#settingsSection { background: __SIDEBAR__; border: 1px solid __BORDER__; border-radius: 12px; }
            QLabel#settingsSectionTitle { color: __STRONG__; font-size: 11pt; font-weight: 650; }
            QLabel#settingsHelpText { color: __MUTED__; }
            QPushButton#settingsSubmenuButton, QPushButton#safetyMenuButton { text-align: left; background: __SIDEBAR__; border: 1px solid __BORDER__; border-radius: 10px; padding: 10px 14px; }
            QPushButton#settingsSubmenuButton:hover, QPushButton#safetyMenuButton:hover { background: __HOVER__; border-color: __MUTED__; }
            QPushButton#settingsBackButton { background: transparent; border: 0; border-radius: 17px; padding: 0; }
            QPushButton#settingsBackButton:hover { background: __HOVER__; }
            QPushButton#themePreviewCard { text-align: left; background: __PANEL__; border: 1px solid __BORDER__; border-radius: 8px; padding: 0; }
            QPushButton#themePreviewCard:hover { border-color: __MUTED__; }
            QPushButton#themePreviewCard[selectedTheme="true"] { border: 2px solid __ACCENT__; }
            QCheckBox#settingsSafetyToggle { spacing: 0; padding: 0; background: transparent; border: 0; }
            QCheckBox#settingsSafetyToggle::indicator { width: 0; height: 0; }
            QScrollArea#safetySettingsScroll { background: transparent; border: 0; }
            QWidget#aboutMascot, QWidget#updateMascot { background: transparent; }
            QFrame#releaseNotesCard { background: __SIDEBAR__; border: 1px solid __BORDER__; border-radius: 18px; }
            QLabel#releaseNotesSubheading { color: __MUTED__; font-weight: 600; }
            QWidget#customTermRow { background: transparent; border: 0; }
            QPushButton#removeCustomTermButton { background: transparent; border: 0; border-radius: 14px; padding: 0; }
            QPushButton#removeCustomTermButton:hover { background: #4A3042; }
            QPushButton#settingsNavButton { text-align: left; background: transparent; border: 0; border-radius: 10px; padding: 9px 11px; }
            QPushButton#settingsNavButton:hover { background: __HOVER__; }
            QPushButton#settingsNavButton:checked { background: __MENU_SELECTED__; color: __STRONG__; }
            QWidget#appRoot { border-radius: 12px; }
            QWidget#titleBar { background: __SIDEBAR__; border-bottom: 1px solid __BORDER__; border-top-left-radius: 12px; border-top-right-radius: 12px; }
            QLabel#windowTitle { color: __STRONG__; font-size: 10pt; font-weight: 650; }
            QWidget#titleBar QPushButton { background: transparent; border: 0; border-radius: 7px; padding: 0; }
            QWidget#titleBar QPushButton:hover { background: __HOVER__; }
            QWidget { color: __TEXT__; }
            QLineEdit#mainSearchInput { background: __SEARCH_BG__; color: __STRONG__; border: 1px solid __SEARCH_BORDER__; border-radius: 17px; padding: 5px 14px; }
            QLineEdit#mainSearchInput:hover { border-color: __MUTED__; }
            QLineEdit#mainSearchInput:focus { border: 1px solid __ACCENT__; }
            QLineEdit, QComboBox, QListWidget {
                background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__;
                border-radius: 16px; padding: 9px 12px; selection-background-color: __BLUE__;
            }
            QLineEdit:hover, QComboBox:hover, QListWidget:hover { border-color: __MUTED__; }
            QLineEdit:focus, QComboBox:focus { border: 1px solid __ACCENT__; }
            QLineEdit#customTermInput:focus, QLineEdit#customFilterInput:focus { border: 1px solid __BORDER__; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid __MUTED__; border-radius: 4px; background: __PANEL__; }
            QCheckBox::indicator:hover { border-color: __ACCENT__; }
            QCheckBox::indicator:checked { image: url("__CHECKMARK__"); background: __ACCENT__; border-color: __ACCENT__; }
            QComboBox { padding-right: 28px; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 26px; border: 0; }
            QComboBox QAbstractItemView { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; selection-background-color: __ACTIVE__; outline: 0; padding: 4px; }
            QPushButton { background: __PANEL__; color: __TEXT__; border: 1px solid __BORDER__; border-radius: 14px; padding: 8px 12px; }
            QPushButton:hover { background: __HOVER__; border-color: __MUTED__; color: __STRONG__; }
            QPushButton:pressed { background: __PRESSED__; }
            QPushButton:disabled { background: __DISABLED__; color: __MUTED__; border-color: __BORDER__; }
            QPushButton[iconAction="true"] { background: transparent; border: 0; padding: 0; }
            QPushButton[iconAction="true"]:hover { background: __HOVER__; }
            QPushButton#action_menu::menu-indicator { image: none; width: 0; }
            QPushButton#action_search { background: __BLUE__; border-color: __BLUE__; color: __BG__; }
            QPushButton#action_search:hover { background: __ACCENT__; border-color: __ACCENT__; }
            QPushButton#closeWindowButton:hover { background: #F7768E; border-color: #F7768E; }
            QMenu { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; padding: 5px; }
            QMenu#mediaTypeMenu { min-width: 132px; }
            QMenu::item { padding: 7px 24px 7px 10px; border-radius: 5px; }
            QMenu::item:selected { background: __MENU_SELECTED__; }
            QMenu::separator { height: 1px; background: __BORDER__; margin: 5px 4px; }
            QToolTip { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; border-radius: 8px; padding: 5px 8px; }
            QMessageBox { background: __BG__; color: __TEXT__; }
            QMessageBox QLabel { color: __TEXT__; }
            QGroupBox { background: __PANEL__; border: 1px solid __BORDER__; border-radius: 14px; margin-top: 12px; padding: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: __STRONG__; }
            QListWidget::item { padding: 7px 8px; border-radius: 7px; }
            QListWidget::item:selected { background: __ACTIVE__; color: __STRONG__; }
            QListWidget::item:focus { outline: 0; border: 0; }
            QSlider::groove:horizontal { height: 5px; background: __BORDER__; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; margin: -5px 0; border-radius: 7px; background: __ACCENT__; }
            QStatusBar#statusBar { background: __SIDEBAR__; color: __MUTED__; border: 0; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }
            QStatusBar#statusBar::item { border: 0; }
            QLabel#footerMeta { color: __MUTED__; padding-left: 8px; }
            QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }
            QScrollBar { background: transparent; border: 0; }
            QScrollBar:horizontal { height: 0; margin: 0; }
            QScrollBar:vertical { width: 0; margin: 0; }
            QScrollBar::handle:horizontal, QScrollBar::handle:vertical { background: transparent; border-radius: 3px; }
            QScrollBar::handle:horizontal { min-width: 0; height: 0; }
            QScrollBar::handle:vertical { min-height: 0; width: 0; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { width: 0; height: 0; }
            QStackedWidget, QWidget#randomPage, QWidget#detailPage { background: transparent; border: 0; }
            QLabel#randomImage, QLabel#detailImage { background: transparent; border: 0; }
            QFrame#fullscreenToolbar { background: #1c1e28; border: 0; border-radius: 9px; }
            QPushButton#detailNavigation { background: transparent; color: __TEXT__; border: 0; border-radius: 0; padding: 0; }
            QPushButton#detailNavigation:disabled { background: transparent; color: __MUTED__; }
            QPushButton#detailNavigation:hover { background: transparent; color: __STRONG__; }
            QFrame#fullscreenToolbar QPushButton:hover { background: __HOVER__; }
            QWidget#galleryContent { background: __BG__; }
            QPushButton#previewImage { background: transparent; border: 0; border-radius: 0; padding: 0; color: __MUTED__; }
            QPushButton#previewImage:hover { background: transparent; }
            QPushButton#favoriteRemoveButton { background: transparent; border: 0; border-radius: 8px; padding: 0; }
            QPushButton#favoriteRemoveButton:hover { background: __HOVER__; }
        """
        for token, color in palette.items():
            stylesheet = stylesheet.replace(f"__{token}__", color)
        checkmark = str(Path(__file__).resolve().parent.parent / "assets" / "check.svg").replace("\\", "/")
        stylesheet = stylesheet.replace("__CHECKMARK__", checkmark)
        self.setStyleSheet(stylesheet)
        for player in (
            getattr(self, "random_video", None),
            getattr(self, "detail_video", None),
        ):
            if player is not None:
                player.set_accent_color(palette["ACCENT"])

    def _catalog(self) -> BooruCatalog:
        parent_enabled = self.settings.get_bool("parent/enabled")
        allowed_tags = self.settings.get("parent/allowed_tags", []) if parent_enabled else []
        if isinstance(allowed_tags, str):
            allowed_tags = allowed_tags.split(",")
        return BooruCatalog(
            self.settings.gelbooru_credentials,
            bool(self.settings.get("search/exclude_male", True)),
            self.settings.use_doh,
            self.settings.rule34_credentials,
            bool(self.settings.get("search/filter_gore", True)),
            tuple(self.settings.get("search/custom_block_tags", []) or []),
            str(self.settings.get("search/media_filter", "image")),
            self.settings.doh_endpoint,
            str(self.settings.get("parent/max_rating", "s")) if parent_enabled else None,
            tuple(map(str, allowed_tags)) if isinstance(allowed_tags, (list, tuple)) else (),
        )

    def _parent_allows_post(self, post: ImagePost) -> bool:
        if not self.settings.get_bool("parent/enabled"):
            return True
        maximum = str(self.settings.get("parent/max_rating", "s"))
        rating_rank = {"s": 0, "q": 1, "e": 2}
        post_rank = rating_rank.get(post.rating)
        if post_rank is None or post_rank > rating_rank.get(maximum, 0):
            return False
        allowed_tags = self.settings.get("parent/allowed_tags", [])
        if isinstance(allowed_tags, str):
            allowed_tags = allowed_tags.split(",")
        allowed_tags = allowed_tags or []
        normalized = {
            str(value).strip().casefold().replace(" ", "_")
            for value in allowed_tags
            if str(value).strip()
        }
        return not normalized or bool(post.tags.intersection(normalized))

    @staticmethod
    def _create_ambient_layer(page: QWidget) -> QLabel:
        label = QLabel(page)
        label.setObjectName("ambientBackground")
        label.setGeometry(page.rect())
        label.setScaledContents(True)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        blur = QGraphicsBlurEffect(label)
        blur.setBlurRadius(42)
        label.setGraphicsEffect(blur)
        label.lower()
        return label

    def _set_ambient_image(self, label: QLabel, pixmap: QPixmap, page: QWidget) -> None:
        if pixmap.isNull():
            label._ambient_source = QPixmap()
            label.clear()
            label.hide()
            return
        label._ambient_source = pixmap
        size = page.size().expandedTo(QSize(1, 1))
        # Fill the ambient layer without distorting the artwork. Cropping the
        # overflow is preferable to leaving bars or stretching the image.
        scaled = pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
        crop_x = max(0, (scaled.width() - size.width()) // 2)
        crop_y = max(0, (scaled.height() - size.height()) // 2)
        background = scaled.copy(crop_x, crop_y, size.width(), size.height())
        tinted = QPixmap(background.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, background)
        painter.fillRect(tinted.rect(), QColor(0, 0, 0, 150))
        painter.end()
        label.setPixmap(tinted)
        label.setGeometry(page.rect())
        enabled = self._ambient_mode_enabled()
        label.setVisible(enabled)
        label.lower()

    def _ambient_mode_enabled(self) -> bool:
        value = self.settings.get("view/ambient_mode", True)
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes", "on"}
        return bool(value)

    def _apply_ambient_mode(self) -> None:
        enabled = self._ambient_mode_enabled()
        for label, page in ((self.random_ambient, self.random_page), (self.detail_ambient, self.detail_page)):
            label.setGeometry(page.rect())
            pixmap = label.pixmap()
            has_image = pixmap is not None and not pixmap.isNull()
            label.setVisible(enabled and has_image)
            label.lower()

    def _refresh_ambient_layers(self) -> None:
        """Recompose ambient artwork after the window has finished restoring."""
        for label, page in (
            (self.random_ambient, self.random_page),
            (self.detail_ambient, self.detail_page),
        ):
            source = getattr(label, "_ambient_source", QPixmap())
            if not source.isNull():
                self._set_ambient_image(label, source, page)
            else:
                label.setGeometry(page.rect())
                label.hide()
                label.lower()
            page.update()
        self.random_video._reflow()
        self.detail_video._reflow()
        self._position_detail_video_navigation()

    @staticmethod
    def _set_zoom_scrollbars(scroll_area: QScrollArea, _zoomed: bool) -> None:
        """Keep zoom panning available without showing native scrollbars."""
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _submit(self, key: str, operation, *args, progress_callback=None) -> None:
        task = BackgroundTask(key, operation, *args)
        task.signals.result.connect(self._task_succeeded)
        task.signals.error.connect(self._task_failed)
        if progress_callback:
            task.signals.progress.connect(progress_callback)
            task.kwargs["report_progress"] = lambda value: task.signals.progress.emit(key, value)
        self.tasks[key] = task
        self.pool.start(task)

    def _on_video_buffering(self, source: str, buffering: bool) -> None:
        player = self.random_video if source == "random" else self.detail_video
        if player is not None and buffering:
            player.set_controls_visible(True)
            if self._fullscreen_active:
                self._show_fullscreen_controls()
            else:
                self._media_controls_idle_timer.start()
    def _on_video_status(self, source: str, status: str) -> None:
        """Reflect the active player's actual state instead of leaving a stale buffer label."""
        if self._active_video_player() is None:
            return
        expected = "random" if self.pages.currentWidget() is self.random_page else "detail"
        if source != expected:
            return
        if status == "Ready":
            return
        self.footer_meta.clear()
        if not self._fullscreen_active:
            self.statusBar().showMessage(status, 0)

    def _on_video_playback_active(self, source: str, playing: bool) -> None:
        player = self.random_video if source == "random" else self.detail_video
        if playing:
            player.set_controls_visible(True)
            if self._fullscreen_active:
                self._show_fullscreen_controls()
            else:
                self._media_controls_idle_timer.start()
        else:
            self._media_controls_idle_timer.stop()
            player.set_controls_visible(True)
        # Keep the application's bottom status bar visible during playback.
        # Only fullscreen mode hides it, as part of the fullscreen layout.
        if not self._fullscreen_active:
            self.statusBar().show()

    def _active_video_player(self) -> VideoPlayerWidget | None:
        if self.pages.currentWidget() is self.random_page:
            post = getattr(self, "random_post", None)
            return self.random_video if post is not None and post.media_type == "video" else None
        if self.pages.currentWidget() is self.detail_page:
            return self.detail_video if self.detail_post and self.detail_post.media_type == "video" else None
        return None

    def _hide_windowed_video_controls(self) -> None:
        if self._fullscreen_active:
            return
        player = self._active_video_player()
        if (
            player is not None
            and player.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        ):
            player.set_controls_visible(False)

    def _start_video_stream(self, player: VideoPlayerWidget, post: ImagePost) -> None:
        self.footer_meta.clear()
        self.statusBar().clearMessage()
        try:
            max_height = int(self.settings.get("video/max_height", 0) or 0)
            stream = self._catalog().create_video_stream(post, max_height or None)
            player.set_source(stream.url, autoplay=True, stream_proxy=stream)
        except Exception as error:
            player.show_prepare_error(f"Could not start video stream: {error}")
            self.statusBar().showMessage(f"Could not start video stream: {error}")

    def _saved_video_volume(self) -> int:
        try:
            return max(0, min(100, int(self.settings.get("video/volume", 70))))
        except (TypeError, ValueError):
            return 70

    def _saved_video_resolution(self) -> int:
        try:
            value = int(self.settings.get("video/max_height", 0) or 0)
        except (TypeError, ValueError):
            return 0
        return value if value in {0, 480, 720, 1080, 2160} else 0

    def _change_video_resolution(self, source: str, height: int) -> None:
        self.settings.set("video/max_height", height)
        self.random_video.set_resolution_limit(height)
        self.detail_video.set_resolution_limit(height)
        post = getattr(self, "random_post", None) if source == "random" else self.detail_post
        player = self.random_video if source == "random" else self.detail_video
        if post is not None and player.has_source:
            self._start_video_stream(player, post)

    def _save_video_volume(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        self.settings.set("video/volume", value)
        for player in (
            getattr(self, "random_video", None),
            getattr(self, "detail_video", None),
        ):
            if player is not None and player.volume_slider.value() != value:
                player.set_volume(value)

    def _play_random_video(self) -> None:
        post = getattr(self, "random_post", None)
        if post is None or post.media_type != "video":
            return
        self._start_video_stream(self.random_video, post)

    def _play_detail_video(self) -> None:
        post = getattr(self, "detail_post", None)
        if post is None or post.media_type != "video":
            return
        self._start_video_stream(self.detail_video, post)

    def _cancel_download(self, download_key: str) -> None:
        task = self.tasks.get(f"download:{download_key}")
        if not isinstance(task, FileDownloadTask):
            return
        self.downloads.mark_cancelling(download_key)
        task.cancel()

    def _task_cancelled(self, download_key: str) -> None:
        self.tasks.pop(f"download:{download_key}", None)
        self.downloads.update_download(download_key, "Cancelled")

    def _task_succeeded(self, key: str, result) -> None:
        self.tasks.pop(key, None)
        category, _, identifier = key.partition(":")
        if category == "search" and int(identifier) == self.request_id:
            self._show_search_results(result)
        elif category == "random" and int(identifier) == self.request_id:
            self.random_post, self.random_content = result
            self._update_image_credits(self.random_post)
            if self.random_post.media_type == "video":
                self._show_random_video(self.random_post)
            else:
                self._submit(f"random-image:{identifier}", decode_image_bytes, self.random_content)
            self._sync_favorite_buttons()
        elif category == "random-image" and int(identifier) == self.request_id:
            self._show_random_image(QPixmap.fromImage(result))
        elif category == "post-detail" and identifier == self.active_detail_id:
            pixmap = QPixmap.fromImage(result)
            if not pixmap.isNull():
                self._full_image_loaded = False
                self.detail_media_stack.setCurrentWidget(self.detail_scroll)
                self.detail_video.clear()
                self.detail_image.set_image(pixmap)
                self._full_image_loaded = False
                self._set_image_credits_visible(True)
                self._set_ambient_image(self.detail_ambient, pixmap, self.detail_page)
                self.fullscreen_button.setVisible(not self._fullscreen_active)
                self._sync_favorite_buttons()
                self._set_detail_image_footer(self.detail_post, pixmap)
                self.full_image_button.setToolTip("Load original-resolution image")
                self.full_image_button.setEnabled(True)
                self.full_image_button.show()
            else:
                self.fullscreen_button.hide()
                self.detail_image.set_placeholder("The provider returned an unsupported image format.")
            self._finish_loading()
            self.statusBar().showMessage("Image loaded", 3000)
        elif category == "random-video" and int(identifier) == self.request_id:
            self.random_video.set_source(str(result), autoplay=True)
            self._set_image_credits_visible(True)
            self._finish_loading()
            self.statusBar().showMessage("Video playback started", 4000)
        elif category == "post-detail-video" and identifier == self.active_detail_id:
            self.detail_video.set_source(str(result), autoplay=True)
            self._set_image_credits_visible(True)
            self._finish_loading()
            self.statusBar().showMessage("Video playback started", 4000)
        elif category == "random-video-preview" and int(identifier) == self.request_id:
            pixmap = QPixmap.fromImage(result)
            if not pixmap.isNull():
                self.random_video.set_poster(pixmap)
                if self.random_post and self.random_post.media_type == "video":
                    self._set_ambient_image(self.random_ambient, pixmap, self.random_page)
        elif category == "detail-video-preview" and identifier == self.active_detail_id:
            pixmap = QPixmap.fromImage(result)
            if not pixmap.isNull():
                self.detail_video.set_poster(pixmap)
                if self.detail_post and self.detail_post.media_type == "video":
                    self._set_ambient_image(self.detail_ambient, pixmap, self.detail_page)
        elif category == "thumbnail":
            generation, index = map(int, identifier.split("/"))
            if generation != self.gallery_generation or index >= len(self.posts):
                return
            pixmap = QPixmap.fromImage(result)
            if not pixmap.isNull():
                post = self.posts[index]
                self.thumbnail_cache[post.post_id] = pixmap
                self._set_card_image(index, post, pixmap)
        elif category == "favorite-thumbnail":
            token, favorite_id = identifier.split("/", 1)
            if token != self.favorites_dialog_token or not self.favorites_dialog:
                return
            pixmap = QPixmap.fromImage(result)
            if not pixmap.isNull():
                self.favorites_dialog.set_thumbnail(favorite_id, pixmap)
            else:
                self.favorites_dialog.set_thumbnail_error(favorite_id)
        elif category == "download":
            self.downloads.update_download(identifier, f"Saved: {result}")
            self.statusBar().showMessage(f"Saved image to {result}", 5000)
        elif category == "full-image":
            view, token = identifier.split("/", 1)
            if view == "random":
                if token != str(self.request_id) or self.pages.currentWidget() is not self.random_page:
                    return
                full_pixmap = QPixmap.fromImage(result)
                self.random_image.set_image(full_pixmap)
                self._set_ambient_image(self.random_ambient, full_pixmap, self.random_page)
                post = self.random_post
            else:
                if token != self.active_detail_id or self.pages.currentWidget() is not self.detail_page:
                    return
                full_pixmap = QPixmap.fromImage(result)
                self.detail_image.set_image(full_pixmap)
                self._set_ambient_image(self.detail_ambient, full_pixmap, self.detail_page)
                post = self.detail_post
            self._full_image_loaded = True
            if view == "random":
                self._set_random_image_footer(post, full_pixmap)
            else:
                self._set_detail_image_footer(post, full_pixmap)
            self._full_image_previous = QPixmap()
            self._full_image_view = None
            self.full_image_button.hide()
            self.statusBar().showMessage("Original-resolution image loaded", 4000)

    def _task_failed(self, key: str, error: str) -> None:
        self.tasks.pop(key, None)
        category, _, identifier = key.partition(":")
        if category == "search" and int(identifier) == self.request_id:
            self._set_image_credits_visible(False)
            pending_detail = self._open_detail_after_page is not None
            self._open_detail_after_page = None
            self._finish_loading()
            self._show_gallery_notice(f"Search failed: {error}")
            self.page_label.setText(f"Page {self.current_page} | Failed")
            if pending_detail:
                if self._fullscreen_active:
                    self._exit_fullscreen()
                self.pages.setCurrentWidget(self.gallery_page)
                self.back_button.hide()
            self.statusBar().clearMessage()
        elif category in {"random", "random-image"} and int(identifier) == self.request_id:
            self._finish_loading()
            self.random_media_stack.setCurrentWidget(self.random_scroll)
            self.random_video.clear()
            self.fullscreen_button.hide()
            media_filter = str(self.settings.get("search/media_filter", "image"))
            media_name = {"image": "image", "video": "video", "all": "media"}.get(media_filter, "media")
            self.random_image.set_placeholder(f"Could not load {media_name}\n{error}")
            self.statusBar().showMessage(f"Could not load {media_name}: {error}")
        elif category == "random-video" and int(identifier) == self.request_id:
            self._finish_loading()
            self.random_video.show_prepare_error(f"Could not prepare video: {error}")
            self.statusBar().showMessage(f"Could not prepare video: {error}")
        elif category == "post-detail" and identifier == self.active_detail_id:
            self._finish_loading()
            self.detail_media_stack.setCurrentWidget(self.detail_video if self.detail_post and self.detail_post.media_type == "video" else self.detail_scroll)
            self.detail_image.set_image(QPixmap())
            self.detail_image.set_placeholder(f"Could not load image\n{error}")
            self.statusBar().showMessage(f"Could not load image: {error}")
        elif category == "post-detail-video" and identifier == self.active_detail_id:
            self._finish_loading()
            self.detail_video.show_prepare_error(f"Could not prepare video: {error}")
            self.statusBar().showMessage(f"Could not prepare video: {error}")
        elif category == "thumbnail":
            generation, index = map(int, identifier.split("/"))
            if generation == self.gallery_generation and index < len(self.posts):
                post_id = self.posts[index].post_id
                button = self.card_buttons.get(post_id)
                indicator = self.card_loading_indicators.get(post_id)
                if indicator:
                    indicator.set_active(False)
                if button:
                    button.setText("Preview unavailable")
        elif category == "favorite-thumbnail":
            token, favorite_id = identifier.split("/", 1)
            if token == self.favorites_dialog_token and self.favorites_dialog:
                self.favorites_dialog.set_thumbnail_error(favorite_id)
        elif category == "download":
            self.downloads.update_download(identifier, f"Failed: {error}")
        elif category == "full-image":
            view, token = identifier.split("/", 1)
            is_current = (
                view == "random"
                and token == str(self.request_id)
                and self.pages.currentWidget() is self.random_page
            ) or (
                view == "detail"
                and token == self.active_detail_id
                and self.pages.currentWidget() is self.detail_page
            )
            if not is_current:
                return
            previous = getattr(self, "_full_image_previous", QPixmap())
            image_state = getattr(self, "_full_image_view", None)
            if image_state and not previous.isNull():
                target_image, ambient, page = image_state
                target_image.set_image(previous)
                self._set_ambient_image(ambient, previous, page)
                if view == "detail":
                    self._set_detail_image_footer(self.detail_post, previous)
            self._full_image_previous = QPixmap()
            self._full_image_view = None
            self.full_image_button.setEnabled(True)
            self.full_image_button.setToolTip("Load original-resolution image")
            self.statusBar().showMessage(f"Could not load original image: {error}", 6000)

    def _begin_loading(self) -> None:
        if not self._fullscreen_active:
            self.statusBar().show()
            self.statusBar().raise_()
        self.statusBar().clearMessage()
        if self.pages.currentWidget() is self.gallery_page:
            self.gallery_loading_indicator.set_active(True)
            self.gallery_body.setCurrentWidget(self.gallery_loading)

    def _finish_loading(self) -> None:
        self.gallery_loading_indicator.set_active(False)
        if self.pages.currentWidget() is self.gallery_page:
            self.gallery_body.setCurrentWidget(self.gallery_scroll)

    def _ensure_status_bar_visible(self) -> None:
        if not self._fullscreen_active:
            self.statusBar().show()
            self.statusBar().raise_()

    def _update_load_progress(self, key: str, value: int) -> None:
        category, _, identifier = key.partition(":")
        if category in {"random", "random-video", "random-video-preview"} and identifier != str(self.request_id):
            return
        if category in {"post-detail", "post-detail-video", "detail-video-preview"} and identifier != self.active_detail_id:
            return
        if category == "full-image":
            view, _, token = identifier.partition("/")
            if view == "random":
                if token != str(self.request_id) or self.pages.currentWidget() is not self.random_page:
                    return
                target = self.random_image
            elif view == "detail":
                if token != self.active_detail_id or self.pages.currentWidget() is not self.detail_page:
                    return
                target = self.detail_image
            else:
                return
            target.set_loading_progress(value)
            return
        target = self.random_image if category in {"random", "random-image"} else (
            self.detail_image if category in {"post-detail"} else None
        )
        if target is not None:
            target.set_loading_progress(value)

    def _active_rating(self) -> str:
        if self.settings.get_bool("parent/enabled") and str(
            self.settings.get("parent/max_rating", "s")
        ) == "s":
            return "sfw"
        return self.selected_rating

    def _rating_allowed(self) -> bool:
        if self.settings.get_bool("parent/enabled"):
            maximum_rank = {"s": 0, "q": 1, "e": 2}.get(
                str(self.settings.get("parent/max_rating", "s")), 0
            )
            requested_rank = {"sfw": 0, "nsfw": 2, "all": 2}.get(self.selected_rating, 2)
            if requested_rank > maximum_rank:
                BackupMessageDialog.notify(
                    self, "Parental control",
                    "This rating is above the maximum selected by the guardian.",
                )
                replacement = "sfw" if maximum_rank == 0 else "all"
                self.selected_rating = replacement
                self.settings.set("search/rating", replacement)
                if replacement in self.rating_actions:
                    self.rating_actions[replacement].setChecked(True)
                self._update_filter_tooltip()
                return False
        if self._active_rating() == "sfw" or bool(self.settings.get("search/allow_nsfw", False)):
            return True
        QMessageBox.information(self, "NSFW filter", "Enable 'Allow NSFW results' in Settings before selecting this rating.")
        self.open_preferences()
        if bool(self.settings.get("search/allow_nsfw", False)):
            return True
        self.rating_changed("sfw")
        return False

    def _new_request(self) -> int:
        self.request_id += 1
        return self.request_id

    def show_random(self) -> None:
        if not self._rating_allowed():
            return
        if not self._fullscreen_active:
            self.statusBar().show()
        self._set_normal_video_actions("random", False)
        self._set_normal_video_actions("detail", False)
        self._set_ambient_image(self.random_ambient, QPixmap(), self.random_page)
        self.detail_video.clear()
        self.random_video.clear()
        self.pages.setCurrentWidget(self.random_page)
        self.back_button.hide()
        self.fullscreen_button.hide()
        self.title_bar.home_button.hide()
        self.detail_previous_button.hide()
        self.detail_next_button.hide()
        self.current_query = ""
        self.request_id = self._new_request()
        identifier = self.request_id
        provider = self.selected_provider
        terms = self.settings.get("search/custom_terms", [])
        query = self.search_input.text().strip()
        if not query and isinstance(terms, (list, tuple)) and terms:
            index = int(self.settings.get("search/custom_term_index", 0)) % len(terms)
            query = str(terms[index])
            self.settings.set("search/custom_term_index", index + 1)
        self.random_post = None
        self.random_content = None
        self._full_image_loaded = False
        self.footer_meta.clear()
        self.full_image_button.hide()
        self.full_image_button.setEnabled(True)
        self.full_image_button.setToolTip("Load original-resolution image")
        self.random_media_stack.setCurrentWidget(self.random_scroll)
        self._set_image_credits_visible(False)
        self._update_image_credits(None)
        self.random_image.set_image(QPixmap())
        self.fullscreen_button.hide()
        self.random_image.set_loading()
        self._begin_loading()
        self._sync_favorite_buttons()
        self._submit(
            f"random:{identifier}", self._catalog().random_image,
            self._active_rating(), provider, query,
            progress_callback=self._update_load_progress,
        )

    def go_home(self) -> None:
        """Clear the active tag and return to a random image."""
        if self._fullscreen_active:
            self._exit_fullscreen()
        self.search_input.clear()
        self.show_random()

    def _show_random_image(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            self._finish_loading()
            self.random_image.set_placeholder("The provider returned an unsupported image format.")
            return
        self._full_image_loaded = False
        if not self._fullscreen_active:
            self.statusBar().show()
        # The preview is now retained as a pixmap; do not keep a second copy
        # of the compressed response bytes in memory.
        self.random_content = None
        self.random_media_stack.setCurrentWidget(self.random_scroll)
        self.random_video.clear()
        self.random_image.set_image(pixmap)
        self.full_image_button.setToolTip("Load original-resolution image")
        self.full_image_button.setEnabled(True)
        self.full_image_button.show()
        self._set_image_credits_visible(True)
        self._set_ambient_image(self.random_ambient, pixmap, self.random_page)
        self.fullscreen_button.setVisible(not self._fullscreen_active)
        self._sync_favorite_buttons()
        post = getattr(self, "random_post", None)
        self._set_random_image_footer(post, pixmap)
        self._finish_loading()
        self.statusBar().showMessage("Image loaded", 3000)

    def _show_random_video(self, post: ImagePost) -> None:
        if not self._fullscreen_active:
            self.statusBar().show()
            self.statusBar().raise_()
        self.full_image_button.hide()
        self.random_video.clear()
        # Remove the previous media's ambient immediately; the new poster is
        # used to build its own blurred background after the preview arrives.
        self._set_ambient_image(self.random_ambient, QPixmap(), self.random_page)
        self.random_media_stack.setCurrentWidget(self.random_video)
        # Keep the random video poster centered in the available viewer area.
        self.random_video.set_poster_alignment(Qt.AlignmentFlag.AlignCenter)
        self.random_video.set_deferred_source(post.image_url)
        if not self._fullscreen_active:
            QTimer.singleShot(0, self._ensure_status_bar_visible)
        self._set_normal_video_actions("random", True)
        if post.preview_urls:
            self._submit(
                f"random-video-preview:{self.request_id}",
                self._fetch_decoded_video_preview,
                post,
            )
        self._set_image_credits_visible(True)
        self.fullscreen_button.setVisible(not self._fullscreen_active)
        self._sync_favorite_buttons()
        self.footer_meta.clear()
        self._finish_loading()
        self.statusBar().showMessage("Video ready | Press Play to stream", 4000)

    def _render_random_image(self) -> None:
        self.random_image._fit_to_viewport()

    def start_search(self) -> None:
        if not self._rating_allowed():
            return
        query = self.search_input.text().strip()
        if not query:
            self.go_home()
            return
        if not self._fullscreen_active:
            self.statusBar().show()
        self.current_query = query
        self.full_image_button.hide()
        self.title_bar.home_button.show()
        self.current_page = 1
        self.load_page(1)

    def load_page(self, page: int, detail_index: int | None = None) -> None:
        if not self.current_query or not self._rating_allowed():
            return
        self.full_image_button.hide()
        self.random_video.clear()
        self.detail_video.clear()
        self._open_detail_after_page = detail_index
        if detail_index is None:
            self._set_image_credits_visible(False)
            if self._fullscreen_active:
                self._exit_fullscreen()
            self.pages.setCurrentWidget(self.gallery_page)
            self.gallery_generation += 1
            self.posts = ()
            self._clear_gallery()
            self.back_button.hide()
            self.fullscreen_button.hide()
            self._sync_favorite_buttons()
            self.title_bar.home_button.show()
            self.detail_previous_button.hide()
            self.detail_next_button.hide()
        else:
            self.detail_image.set_image(QPixmap())
            self.detail_image.set_loading()
        self.current_page = max(1, page)
        self.request_id = self._new_request()
        identifier = self.request_id
        self._hide_gallery_notice()
        self.gallery_status.setText("")
        self.footer_meta.clear()
        self.page_label.setText(f"Page {self.current_page}")
        self.previous_button.setEnabled(False)
        self.next_button.setEnabled(False)
        if detail_index is not None:
            self.fullscreen_previous_button.setEnabled(False)
            self.fullscreen_next_button.setEnabled(False)
            self.detail_previous_button.setEnabled(False)
            self.detail_next_button.setEnabled(False)
        self.gallery_scroll.verticalScrollBar().setValue(0)
        self._begin_loading()
        self._submit(f"search:{identifier}", self._catalog().search, self.current_query, self._active_rating(),
                     self.selected_provider, self.current_page, 50)

    def _show_search_results(self, page: SearchPage) -> None:
        if not self._fullscreen_active:
            self.statusBar().show()
            self.statusBar().raise_()
        self.gallery_body.setCurrentWidget(self.gallery_scroll)
        self.posts = page.posts
        self._page_has_more = page.has_more
        self.gallery_generation += 1
        self._clear_footer_meta()
        self._set_search_footer_counts()
        self._clear_gallery()
        for index, post in enumerate(self.posts):
            self._add_card(index, post)
            self._submit_thumbnail(index, post)
        self._set_gallery_rows_top_aligned()
        self._update_card_icon_sizes()
        self.page_label.setText(f"Page {self.current_page} | {len(self.posts)} results")
        self.previous_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(page.has_more)
        if page.provider_errors:
            error_signature = tuple(sorted(set(page.provider_errors)))
            if page.fallback_from and page.posts:
                message = (
                    f"No results from {page.fallback_from}; showing "
                    f"{page.posts[0].provider}. "
                )
            else:
                message = "Some providers could not be reached. "
            message += " | ".join(page.provider_errors)
            if error_signature not in self._shown_provider_error_signatures:
                self._shown_provider_error_signatures.add(error_signature)
                self._show_gallery_notice(message)
        elif not page.posts:
            media_filter = str(self.settings.get("search/media_filter", "image"))
            media_name = {"image": "images", "video": "videos", "all": "media"}.get(media_filter, "images")
            self._show_gallery_notice(f'No {media_name} found for "{self.current_query}".')
        else:
            self._hide_gallery_notice()
        self._finish_loading()
        pending_index = self._open_detail_after_page
        self._open_detail_after_page = None
        if pending_index is not None:
            if self.posts:
                index = len(self.posts) - 1 if pending_index < 0 else min(pending_index, len(self.posts) - 1)
                self.open_post(self.posts[index])
            else:
                self.pages.setCurrentWidget(self.gallery_page)
                self.back_button.hide()

    def _clear_footer_meta(self) -> None:
        self.footer_meta.clear()

    def _clear_gallery(self) -> None:
        self.card_buttons.clear()
        self.card_loading_indicators.clear()
        self.card_play_badges.clear()
        self.card_frames.clear()
        while self.gallery_rows.count():
            entry = self.gallery_rows.takeAt(0)
            widget = entry.widget()
            if widget:
                widget.hide()
                widget.deleteLater()

    def _show_gallery_notice(self, message: str, duration_ms: int = 5000) -> None:
        self._gallery_notice_timer.stop()
        self._gallery_notice_animation.stop()
        self.gallery_status.setText(message)
        width = min(820, max(280, self.gallery_page.width() - 40))
        self.gallery_status.setFixedWidth(width)
        self.gallery_status.adjustSize()
        height = min(110, max(42, self.gallery_status.sizeHint().height()))
        self.gallery_status.setGeometry(
            (self.gallery_page.width() - width) // 2,
            12,
            width,
            height,
        )
        self._gallery_notice_opacity.setOpacity(0.0)
        self.gallery_status.show()
        self.gallery_status.raise_()
        self._gallery_notice_animation.setStartValue(0.0)
        self._gallery_notice_animation.setEndValue(1.0)
        self._gallery_notice_animation.start()
        self._gallery_notice_timer.start(max(1000, duration_ms))

    def _fade_out_gallery_notice(self) -> None:
        if not self.gallery_status.isVisible():
            return
        self._gallery_notice_animation.stop()
        self._gallery_notice_animation.setStartValue(self._gallery_notice_opacity.opacity())
        self._gallery_notice_animation.setEndValue(0.0)
        self._gallery_notice_animation.start()

    def _finish_gallery_notice_fade(self) -> None:
        if self._gallery_notice_opacity.opacity() <= 0.0:
            self.gallery_status.hide()

    def _hide_gallery_notice(self) -> None:
        self._gallery_notice_timer.stop()
        self._gallery_notice_animation.stop()
        self._gallery_notice_opacity.setOpacity(1.0)
        self.gallery_status.hide()

    def _set_gallery_rows_top_aligned(self) -> None:
        """Rebuild compact, centered rows and leave spare height below them."""
        while self.gallery_rows.count():
            entry = self.gallery_rows.takeAt(0)
            old_row = entry.widget()
            if old_row:
                # Keep card widgets alive while replacing only the row wrappers
                # after a window resize.
                for frame in self.card_frames.values():
                    if frame.parentWidget() is old_row:
                        frame.setParent(self.gallery_content)
                old_row.deleteLater()

        columns = self._gallery_column_count()
        self._gallery_columns = columns
        for start in range(0, len(self.posts), columns):
            row = QWidget(self.gallery_content)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            end = min(start + columns, len(self.posts))
            partial = end - start < columns
            if partial:
                row_layout.addStretch(1)
            for index in range(start, end):
                frame = self.card_frames.get(self.posts[index].post_id)
                if frame:
                    row_layout.addWidget(frame, 0 if partial else 1)
            if partial:
                row_layout.addStretch(1)
            self.gallery_rows.addWidget(row)
        self.gallery_rows.addStretch(1)

    def _update_card_icon_sizes(self) -> None:
        if not self.card_buttons:
            return
        columns = self._gallery_column_count()
        available = max(1, self.gallery_scroll.viewport().width())
        card_width = max(190, (available - 8 * (columns - 1)) // columns)
        icon_size = QSize(max(16, card_width - 12), 213)
        for button in self.card_buttons.values():
            button.setIconSize(icon_size)
        for index, post in enumerate(self.posts):
            pixmap = self.thumbnail_cache.get(post.post_id)
            if pixmap is not None:
                self._set_card_image(index, post, pixmap)

    def _gallery_column_count(self) -> int:
        capacity = max(1, self.gallery_scroll.viewport().width() // 225)
        return min(capacity, max(1, len(self.posts)))

    def _add_card(self, index: int, post: ImagePost) -> None:
        frame = QWidget()
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(2)
        preview_container = QWidget()
        preview_layout = QGridLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        if post.media_type == "video" and not post.preview_urls:
            button = QPushButton("Video preview unavailable")
            button.setIcon(self._icon("play"))
            button.setIconSize(QSize(28, 28))
        else:
            button = QPushButton()
        button.setObjectName("previewImage")
        button.setMinimumSize(190, 225)
        button.setIconSize(QSize(175, 213))
        button.clicked.connect(lambda _checked=False, selected=post: self.open_post(selected))
        preview_layout.addWidget(button, 0, 0)
        if post.preview_urls and post.post_id not in self.thumbnail_cache:
            indicator = CircularProgressIndicator(preview_container, size=28)
            indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            indicator.set_active(True)
            preview_layout.addWidget(indicator, 0, 0, Qt.AlignmentFlag.AlignCenter)
            self.card_loading_indicators[post.post_id] = indicator
        if post.media_type == "video":
            play_badge = QLabel()
            play_badge.setPixmap(self._icon("play").pixmap(QSize(22, 22)))
            play_badge.setFixedSize(46, 46)
            play_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            play_badge.setStyleSheet(
                "background: rgba(16, 17, 24, 190); border-radius: 23px; padding: 12px;"
            )
            play_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            play_badge.setVisible(post.post_id in self.thumbnail_cache)
            preview_layout.addWidget(play_badge, 0, 0, Qt.AlignmentFlag.AlignCenter)
            self.card_play_badges[post.post_id] = play_badge
        card_layout.addWidget(preview_container)
        self.card_buttons[post.post_id] = button
        self.card_frames[post.post_id] = frame
        if post.post_id in self.thumbnail_cache:
            self._set_card_image(index, post, self.thumbnail_cache[post.post_id])
        elif not post.preview_urls and not (post.media_type == "video"):
            button.setText("Preview unavailable")

    def _submit_thumbnail(self, index: int, post: ImagePost) -> None:
        if post.post_id in self.thumbnail_cache or not post.preview_urls:
            return
        key = f"thumbnail:{self.gallery_generation}/{index}"
        if post.media_type == "video":
            self._submit(key, self._fetch_decoded_video_preview, post)
        else:
            self._submit(key, self._fetch_decoded_candidates, post.preview_urls)

    def _fetch_preview(self, candidates: tuple[str, ...]) -> bytes:
        failures = []
        for url in candidates:
            try:
                return self._catalog().fetch_image(url)
            except ProviderError as error:
                failures.append(str(error))
        raise ProviderError(failures[-1] if failures else "No thumbnail URL was supplied.")

    def _fetch_decoded_preview(self, post: ImagePost, report_progress=None):
        content = self._catalog().fetch_post_preview(post, report_progress)
        return decode_image_bytes(content, max_dimension=2560)

    def _fetch_decoded_candidates(self, candidates: tuple[str, ...]):
        return decode_image_bytes(self._fetch_preview(candidates), max_dimension=560)

    def _fetch_decoded_video_preview(self, post: ImagePost):
        return decode_image_bytes(
            self._fetch_preview(post.preview_urls),
            max_dimension=1440,
        )

    def _fetch_decoded_original(self, post: ImagePost, report_progress=None):
        content = self._catalog().fetch_image(post.image_url, report_progress)
        return decode_image_bytes(content, max_dimension=None)

    def load_full_image(self) -> None:
        post = self._active_post()
        if post is None or post.media_type != "image" or self._full_image_loaded:
            return
        self.footer_meta.clear()
        if self.pages.currentWidget() is self.random_page:
            identifier = f"random/{self.request_id}"
            target_image = self.random_image
            ambient = self.random_ambient
            page = self.random_page
        elif self.pages.currentWidget() is self.detail_page:
            identifier = f"detail/{self.active_detail_id}"
            target_image = self.detail_image
            ambient = self.detail_ambient
            page = self.detail_page
        else:
            return
        self._full_image_previous = target_image.original
        self._full_image_view = (target_image, ambient, page)
        self._set_ambient_image(ambient, QPixmap(), page)
        target_image.set_loading()
        self.full_image_button.setEnabled(False)
        self.full_image_button.setToolTip("Load original-resolution image")
        self._submit(
            f"full-image:{identifier}", self._fetch_decoded_original, post,
            progress_callback=self._update_load_progress,
        )

    def _set_card_image(self, index: int, post: ImagePost, pixmap: QPixmap) -> None:
        if index >= len(self.posts) or self.posts[index].post_id != post.post_id:
            return
        button = self.card_buttons.get(post.post_id)
        indicator = self.card_loading_indicators.get(post.post_id)
        if indicator:
            indicator.set_active(False)
        if button:
            button.setText("")
            scaled = pixmap.scaled(
                button.iconSize(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            button.setIcon(QIcon(scaled))
        badge = self.card_play_badges.get(post.post_id)
        if badge:
            badge.show()

    def open_post(self, post: ImagePost) -> None:
        self._media_controls_idle_timer.stop()
        self.footer_meta.clear()
        self.random_video.clear()
        self.detail_video.clear()
        self._set_normal_video_actions("random", False)
        self._set_normal_video_actions("detail", False)
        self._set_ambient_image(self.detail_ambient, QPixmap(), self.detail_page)
        self.detail_post = post
        self._full_image_loaded = False
        self.full_image_button.hide()
        self.full_image_button.setEnabled(True)
        self.full_image_button.setToolTip("Load original-resolution image")
        if post.media_type == "video":
            if not self._fullscreen_active:
                self.statusBar().show()
                self.statusBar().raise_()
            self.full_image_button.hide()
            self._set_normal_video_actions("detail", True)
        elif not self._fullscreen_active:
            self.statusBar().show()
        self._set_image_credits_visible(False)
        self.detail_from_search = bool(
            not self._opening_favorite
            and self.current_query
            and any(item.post_id == post.post_id for item in self.posts)
        )
        self.detail_origin = "favorites" if self._opening_favorite else (
            "search" if self.detail_from_search else "random"
        )
        self.title_bar.home_button.setVisible(self.detail_origin in {"search", "favorites"})
        self.fullscreen_button.hide()
        show_navigation = self._detail_has_navigation()
        show_detail_arrows = (
            show_navigation
            and not self._fullscreen_active
            and post.media_type != "video"
        )
        self.detail_previous_button.setVisible(show_detail_arrows)
        self.detail_next_button.setVisible(show_detail_arrows)
        show_video_arrows = (
            show_navigation
            and not self._fullscreen_active
            and post.media_type == "video"
        )
        self.detail_video_previous_overlay.setVisible(show_video_arrows)
        self.detail_video_next_overlay.setVisible(show_video_arrows)
        self.fullscreen_previous_button.setVisible(show_navigation)
        self.fullscreen_next_button.setVisible(show_navigation)
        self._update_detail_navigation()
        self.active_detail_id = str(uuid4())
        self._update_image_credits(post)
        self.detail_image.set_image(QPixmap())
        self.pages.setCurrentWidget(self.detail_page)
        self._position_detail_video_navigation()
        self._sync_favorite_buttons()
        self.back_button.setVisible(self.detail_origin != "favorites")
        if post.media_type == "video":
            self.detail_media_stack.setCurrentWidget(self.detail_video)
            self.detail_video.set_poster_alignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_video.set_deferred_source(post.image_url)
            if not self._fullscreen_active:
                QTimer.singleShot(0, self._ensure_status_bar_visible)
            preview = self.thumbnail_cache.get(post.post_id)
            if preview:
                self.detail_video.set_poster(preview)
                self._set_ambient_image(self.detail_ambient, preview, self.detail_page)
            elif post.preview_urls:
                self._submit(
                    f"detail-video-preview:{self.active_detail_id}",
                    self._fetch_decoded_video_preview,
                    post,
                )
            self.footer_meta.clear()
            self._set_image_credits_visible(True)
            self._finish_loading()
            self.statusBar().showMessage("Video ready | Press Play to stream", 4000)
        else:
            self._full_image_loaded = False
            self.detail_media_stack.setCurrentWidget(self.detail_scroll)
            self.detail_image.set_loading()
            self._begin_loading()
            self._submit(
                f"post-detail:{self.active_detail_id}", self._fetch_decoded_preview, post,
                progress_callback=self._update_load_progress,
            )
        self._position_detail_video_navigation()

    def _swipe_detail(self, direction: int) -> None:
        """Browse adjacent search results or saved favorites."""
        if not self.detail_post:
            return
        favorites = self.detail_origin == "favorites"
        collection = self._favorite_navigation_posts if favorites else self.posts
        if not collection or (not favorites and not self.detail_from_search):
            return
        key = favorite_key(self.detail_post) if favorites else self.detail_post.post_id
        index = next(
            (i for i, post in enumerate(collection) if (favorite_key(post) if favorites else post.post_id) == key),
            -1,
        )
        if index < 0:
            return
        target = index + (1 if direction > 0 else -1)
        if 0 <= target < len(collection):
            self._opening_favorite = favorites
            try:
                self.open_post(collection[target])
            finally:
                self._opening_favorite = False
        elif not favorites and direction > 0 and self._page_has_more:
            self.load_page(self.current_page + 1, detail_index=0)
        elif not favorites and direction < 0 and self.current_page > 1:
            self.load_page(self.current_page - 1, detail_index=-1)

    def _detail_has_navigation(self) -> bool:
        if self.detail_origin == "favorites":
            return len(self._favorite_navigation_posts) > 1
        return self.detail_from_search

    def _update_detail_navigation(self) -> None:
        favorites = self.detail_origin == "favorites"
        collection = self._favorite_navigation_posts if favorites else self.posts
        key = favorite_key(self.detail_post) if favorites and self.detail_post else (
            self.detail_post.post_id if self.detail_post else None
        )
        index = next(
            (i for i, post in enumerate(collection)
             if (favorite_key(post) if favorites else post.post_id) == key),
            -1,
        )
        if favorites:
            previous_available = index > 0
            next_available = index >= 0 and index < len(collection) - 1
        else:
            previous_available = self.detail_from_search and (index > 0 or self.current_page > 1)
            next_available = self.detail_from_search and (
                (index >= 0 and index < len(collection) - 1) or self._page_has_more
            )
        for button in (
            self.detail_previous_button,
            self.detail_video_previous_overlay,
            self.fullscreen_previous_button,
            self.detail_video_previous_action,
        ):
            button.setEnabled(previous_available)
        for button in (
            self.detail_next_button,
            self.detail_video_next_overlay,
            self.fullscreen_next_button,
            self.detail_video_next_action,
        ):
            button.setEnabled(next_available)
        show_navigation = self._detail_has_navigation()
        show_detail_arrows = (
            show_navigation
            and not self._fullscreen_active
            and self.detail_post is not None
            and self.detail_post.media_type != "video"
        )
        self.detail_previous_button.setVisible(show_detail_arrows)
        self.detail_next_button.setVisible(show_detail_arrows)
        show_video_arrows = (
            show_navigation
            and not self._fullscreen_active
            and self.detail_post is not None
            and self.detail_post.media_type == "video"
        )
        self.detail_video_previous_overlay.setVisible(show_video_arrows)
        self.detail_video_next_overlay.setVisible(show_video_arrows)
        self.fullscreen_previous_button.setVisible(show_navigation)
        self.fullscreen_next_button.setVisible(show_navigation)
        show_fullscreen_video_navigation = (
            show_navigation
            and self._fullscreen_active
            and self.detail_post is not None
            and self.detail_post.media_type == "video"
        )
        self.detail_video_previous_action.setVisible(show_fullscreen_video_navigation)
        self.detail_video_next_action.setVisible(show_fullscreen_video_navigation)

    def _position_detail_video_navigation(self) -> None:
        if not hasattr(self, "detail_video_previous_overlay"):
            return
        page = self.detail_page
        button_height = self.detail_video_previous_overlay.height()
        center_y = max(0, (page.height() - button_height) // 2)
        self.detail_previous_button.move(12, center_y)
        self.detail_next_button.move(
            max(12, page.width() - self.detail_next_button.width() - 12),
            center_y,
        )
        self.detail_video_previous_overlay.move(12, center_y)
        self.detail_video_next_overlay.move(
            max(12, page.width() - self.detail_video_next_overlay.width() - 12),
            center_y,
        )
        if self.detail_previous_button.isVisible():
            self.detail_previous_button.raise_()
        if self.detail_next_button.isVisible():
            self.detail_next_button.raise_()
        if self.detail_video_previous_overlay.isVisible():
            self.detail_video_previous_overlay.raise_()
            self.detail_video_next_overlay.raise_()

    def _update_image_credits(self, post: ImagePost | None) -> None:
        self._credits_post = post

    def show_image_credits(self) -> None:
        post = getattr(self, "_credits_post", None)
        if post is None:
            return
        dialog = ImageCreditsDialog(post, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.accepted.connect(lambda current=dialog: self._search_credits_tag(current))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _search_credits_tag(self, dialog: ImageCreditsDialog) -> None:
        if dialog.selected_tag:
            self.search_input.setText(dialog.selected_tag)
            self.start_search()

    def _set_image_credits_visible(self, visible: bool) -> None:
        """Expose credits only when a full image or video is currently loaded."""
        self.image_credits_action.setVisible(visible)

    def back_to_results(self) -> None:
        if self._fullscreen_active:
            self._exit_fullscreen()
        self._media_controls_idle_timer.stop()
        self.footer_meta.clear()
        self.detail_video.clear()
        self._set_ambient_image(self.detail_ambient, QPixmap(), self.detail_page)
        self._set_image_credits_visible(False)
        self.back_button.hide()
        self.detail_previous_button.hide()
        self.detail_next_button.hide()
        self.fullscreen_button.hide()
        if self.detail_origin == "favorites":
            self.title_bar.home_button.show()
            self.show_favorites()
        elif self.detail_origin == "search":
            self.pages.setCurrentWidget(self.gallery_page)
            self.full_image_button.hide()
            self.title_bar.home_button.show()
            self._set_search_footer_counts()
            self.statusBar().clearMessage()
        else:
            self.go_home()
        self._sync_favorite_buttons()

    def _toggle_fullscreen(self) -> None:
        if self._fullscreen_active:
            self._exit_fullscreen()
            return
        current_page = self.pages.currentWidget()
        if current_page not in (self.random_page, self.detail_page):
            return
        self._fullscreen_source = "random" if current_page is self.random_page else "detail"
        fullscreen_post = (
            self.random_post
            if self._fullscreen_source == "random"
            else self.detail_post
        )
        self._was_maximized_before_fullscreen = self.isMaximized()
        self._windowed_geometry = self.geometry()
        self._fullscreen_active = True
        active_player = self.random_video if self._fullscreen_source == "random" else self.detail_video
        active_player.set_fullscreen_mode(True)
        if fullscreen_post is not None and fullscreen_post.media_type == "video":
            ambient = (
                self.random_ambient
                if self._fullscreen_source == "random"
                else self.detail_ambient
            )
            ambient.hide()
        self._update_detail_navigation()
        self.random_video.set_fullscreen_toggle_visible(False)
        self.detail_video.set_fullscreen_toggle_visible(False)
        self.title_bar.hide()
        self.statusBar().hide()
        self.fullscreen_button.hide()
        self.detail_previous_button.hide()
        self.detail_next_button.hide()
        # Use a borderless monitor-sized normal window instead of Qt's native
        # fullscreen state. On Windows the native state can composite video
        # above screenshot overlays and other top-level windows.
        screen = self.screen()
        if screen is None and self.windowHandle() is not None:
            screen = self.windowHandle().screen()
        self.showNormal()
        if screen is not None:
            self.setGeometry(screen.geometry())
        active_player._schedule_reflow()
        self._sync_favorite_buttons()
        self._show_fullscreen_controls()
        if fullscreen_post is None or fullscreen_post.media_type != "video":
            image = self.random_image if self._fullscreen_source == "random" else self.detail_image
            QTimer.singleShot(0, image._fit_to_viewport)

    def _set_normal_video_actions(self, source: str, visible: bool) -> None:
        if source == "random":
            actions = (
                self.random_video_refresh_action,
                self.random_video_download_action,
            )
            favorite_action = self.random_video_favorite_action
            exit_action = self.random_video_exit_action
            player = self.random_video
        else:
            actions = (
                self.detail_video_download_action,
            )
            favorite_action = self.detail_video_favorite_action
            exit_action = self.detail_video_exit_action
            player = self.detail_video
        for action in actions:
            action.setVisible(visible)
        favorite_action.hide()
        exit_action.hide()
        if visible:
            player.controls_frame.raise_()

    def _check_for_startup_update(self) -> None:
        if self._startup_update_task is not None:
            return
        task = UpdateCheckTask()
        self._startup_update_task = task
        task.signals.finished.connect(self._startup_update_checked)
        self.pool.start(task)

    def _startup_update_checked(
        self, tag: str, url: str, notes: str, error: str
    ) -> None:
        self._startup_update_task = None
        if error or version_parts(tag) <= version_parts(__version__):
            return
        dialog = ReleaseNotesDialog(tag, url, notes, self)
        dialog.finished.connect(
            lambda _result, current=dialog: self._clear_update_notice(current)
        )
        self._update_notice_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _clear_update_notice(self, dialog: ReleaseNotesDialog) -> None:
        if self._update_notice_dialog is dialog:
            self._update_notice_dialog = None

    def _exit_fullscreen(self) -> None:
        if not self._fullscreen_active:
            return
        self._fullscreen_active = False
        self._fullscreen_idle_timer.stop()
        self.fullscreen_toolbar.hide()
        self.random_fullscreen_toolbar.hide()
        self.random_video.set_fullscreen_actions_visible(False)
        self.detail_video.set_fullscreen_actions_visible(False)
        self.random_video.set_fullscreen_mode(False)
        self.detail_video.set_fullscreen_mode(False)
        if self._was_maximized_before_fullscreen:
            self.showMaximized()
        else:
            self.showNormal()
            if self._windowed_geometry is not None:
                self.setGeometry(self._windowed_geometry)
        self.random_video._schedule_reflow()
        self.detail_video._schedule_reflow()
        self._ambient_restore_timer.start()
        self.title_bar.show()
        current_page = self.pages.currentWidget()
        # Restore the app footer after leaving fullscreen, including for a
        # paused or buffering video.
        self.statusBar().show()
        self.random_video.set_fullscreen_toggle_visible(self.pages.currentWidget() is self.random_page)
        self.detail_video.set_fullscreen_toggle_visible(self.pages.currentWidget() is self.detail_page)
        current_page = self.pages.currentWidget()
        current_post = self.random_post if current_page is self.random_page else self.detail_post
        if current_post is not None and current_post.media_type == "video":
            self._set_normal_video_actions(
                "random" if current_page is self.random_page else "detail", True
            )
            player = self._active_video_player()
            if player and player.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                player.set_controls_visible(True)
                self._media_controls_idle_timer.start()
        image_page = self.pages.currentWidget()
        image_ready = (
            (image_page is self.random_page and not self.random_image.original.isNull())
            or (image_page is self.detail_page and not self.detail_image.original.isNull())
        )
        self.fullscreen_button.setVisible(image_ready)
        self._update_detail_navigation()
        self._sync_favorite_buttons()
        if current_post is None or current_post.media_type != "video":
            image = self.random_image if getattr(self, "_fullscreen_source", "detail") == "random" else self.detail_image
            QTimer.singleShot(0, image._fit_to_viewport)

    def _show_fullscreen_controls(self) -> None:
        if not self._fullscreen_active:
            return
        source = getattr(self, "_fullscreen_source", "detail")
        post = getattr(self, "random_post", None) if source == "random" else self.detail_post
        player = self.random_video if source == "random" else self.detail_video
        parent = self.random_page if source == "random" else self.detail_page
        toolbar = self.random_fullscreen_toolbar if source == "random" else self.fullscreen_toolbar
        if post is not None and post.media_type == "video":
            toolbar.hide()
            player.set_fullscreen_toggle_visible(False)
            player.set_fullscreen_controls_visible(True)
            self.random_video.set_fullscreen_actions_visible(source == "random")
            self.detail_video.set_fullscreen_actions_visible(source != "random")
            favorite = any(favorite_key(item) == favorite_key(post) for item in self._favorite_posts())
            if source == "random":
                self.random_video_favorite_action.setIcon(self._icon("heart-filled" if favorite else "heart"))
            else:
                self.detail_video_favorite_action.setIcon(self._icon("heart-filled" if favorite else "heart"))
            player.controls_frame.raise_()
            self._fullscreen_idle_timer.start()
            return
        self.random_video.set_fullscreen_actions_visible(False)
        self.detail_video.set_fullscreen_actions_visible(False)
        width, height = (230 if source == "random" else 280), 58
        toolbar.setGeometry(
            (parent.width() - width) // 2,
            parent.height() - height - 24,
            width,
            height,
        )
        toolbar.show()
        toolbar.raise_()
        self._fullscreen_idle_timer.start()

    def _hide_fullscreen_controls(self) -> None:
        if self._fullscreen_active:
            self.fullscreen_toolbar.hide()
            self.random_fullscreen_toolbar.hide()
            self.random_video.set_fullscreen_actions_visible(False)
            self.detail_video.set_fullscreen_actions_visible(False)
            source = getattr(self, "_fullscreen_source", "detail")
            post = getattr(self, "random_post", None) if source == "random" else self.detail_post
            if post is not None and post.media_type == "video":
                player = self.random_video if source == "random" else self.detail_video
                player.set_fullscreen_controls_visible(False)

    def download_active_image(self) -> None:
        if self.pages.currentWidget() is self.detail_page:
            post = self.detail_post
        elif self.pages.currentWidget() is self.random_page:
            post = getattr(self, "random_post", None)
        else:
            post = None
        if post:
            self.queue_download(post)
        else:
            self.statusBar().showMessage("Open an image before downloading.", 4000)

    def refresh(self) -> None:
        if self.pages.currentWidget() is self.gallery_page:
            self.load_page(self.current_page)
        elif self.pages.currentWidget() is self.detail_page and self.detail_post:
            self.open_post(self.detail_post)
        else:
            self.show_random()

    def provider_changed(self, provider: str) -> None:
        self.selected_provider = provider
        self.settings.set("search/provider", provider)
        self.provider_actions[provider].setChecked(True)
        self._update_filter_tooltip()
        if self.pages.currentWidget() is self.gallery_page and self.current_query:
            self.current_page = 1
            self.load_page(1)

    def rating_changed(self, rating: str) -> None:
        self.selected_rating = rating
        self.settings.set("search/rating", rating)
        self.rating_actions[rating].setChecked(True)
        self._update_filter_tooltip()
        # Changing the filter must also replace an already displayed random
        # image (or detail view). Otherwise the menu says "Only NSFW" while
        # the previous SFW image remains visible until the next manual refresh.
        if not self._rating_allowed():
            return
        if self.current_query:
            self.current_page = 1
            self.load_page(1)
        else:
            self.show_random()

    def media_changed(self, media: str) -> None:
        self.selected_media = media
        self.settings.set("search/media_filter", media)
        self.media_actions[media].setChecked(True)
        self._update_filter_tooltip()
        if not self._rating_allowed():
            return
        if self.current_query:
            self.current_page = 1
            self.load_page(1)
        else:
            self.show_random()

    def open_preferences(self) -> None:
        if self.preferences_dialog and self.preferences_dialog.isVisible():
            self.preferences_dialog.raise_()
            self.preferences_dialog.activateWindow()
            return
        previous_provider = self.selected_provider
        previous_rating = self.selected_rating
        previous_filter_settings = (
            bool(self.settings.get("search/exclude_male", True)),
            bool(self.settings.get("search/filter_gore", True)),
            tuple(self.settings.get("search/custom_block_tags", []) or []),
        )
        dialog = PreferencesDialog(self.settings, self)
        self.preferences_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        preference_state = {
            "provider": previous_provider,
            "rating": previous_rating,
            "filters": previous_filter_settings,
            "favorites": self._favorite_posts(),
            "parent_policy": (
                self.settings.get_bool("parent/enabled"),
                str(self.settings.get("parent/max_rating", "s")),
                tuple(self.settings.get("parent/allowed_tags", []) or []),
            ),
            "favorites_lock": self.settings.get_bool("favorites_lock/enabled"),
        }

        def preferences_changed() -> None:
            favorites = self._favorite_posts()
            parent_policy = (
                self.settings.get_bool("parent/enabled"),
                str(self.settings.get("parent/max_rating", "s")),
                tuple(self.settings.get("parent/allowed_tags", []) or []),
            )
            parent_policy_changed = parent_policy != preference_state["parent_policy"]
            preference_state["parent_policy"] = parent_policy
            favorites_lock_enabled = self.settings.get_bool("favorites_lock/enabled")
            favorites_lock_just_enabled = favorites_lock_enabled and not preference_state["favorites_lock"]
            preference_state["favorites_lock"] = favorites_lock_enabled
            imported_theme = str(self.settings.get("appearance/theme", self.current_theme))
            if imported_theme in {"Dark", "Light", "System", "OLED Dark"} and imported_theme != self.current_theme:
                self.change_theme(imported_theme)
            if favorites_lock_just_enabled and self.favorites_dialog:
                self.favorites_dialog.close()
            if favorites != preference_state["favorites"]:
                preference_state["favorites"] = favorites
                self._refresh_favorites_dialog(favorites)
            elif parent_policy_changed:
                self._refresh_favorites_dialog(favorites)
            self._preferences_updated(
                preference_state["provider"],
                preference_state["rating"],
                preference_state["filters"],
            )
            preference_state["provider"] = self.selected_provider
            preference_state["rating"] = self.selected_rating
            preference_state["filters"] = (
                bool(self.settings.get("search/exclude_male", True)),
                bool(self.settings.get("search/filter_gore", True)),
                tuple(self.settings.get("search/custom_block_tags", []) or []),
            )
            if parent_policy_changed:
                if self.current_query:
                    self.load_page(self.current_page)
                else:
                    self.show_random()

        dialog.settings_changed.connect(preferences_changed)
        dialog.finished.connect(
            lambda _result, current=dialog: self._clear_preferences_dialog(current)
        )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _clear_preferences_dialog(self, dialog: PreferencesDialog) -> None:
        if self.preferences_dialog is dialog:
            self.preferences_dialog = None

    def _preferences_updated(
        self,
        previous_provider: str,
        previous_rating: str,
        previous_filter_settings: tuple[bool, bool, tuple],
    ) -> None:
        provider = str(self.settings.get("search/provider", "All"))
        rating = str(self.settings.get("search/rating", "sfw"))
        if provider in self.provider_actions:
            self.selected_provider = provider
            self.provider_actions[provider].setChecked(True)
        if rating in self.rating_actions:
            self.selected_rating = rating
            self.rating_actions[rating].setChecked(True)
        previous_media = self.selected_media
        media = str(self.settings.get("search/media_filter", "image"))
        if media in self.media_actions:
            self.selected_media = media
            self.media_actions[media].setChecked(True)
        self._update_filter_tooltip()
        self._apply_ambient_mode()
        current_filter_settings = (
            bool(self.settings.get("search/exclude_male", True)),
            bool(self.settings.get("search/filter_gore", True)),
            tuple(self.settings.get("search/custom_block_tags", []) or []),
        )
        filters_changed = current_filter_settings != previous_filter_settings
        if (
            self.selected_provider != previous_provider
            or self.selected_rating != previous_rating
            or self.selected_media != previous_media
            or filters_changed
        ) and self._rating_allowed():
            if self.current_query:
                self.load_page(self.current_page)
            else:
                self.show_random()

    def queue_download(self, post: ImagePost) -> None:
        folder = str(self.settings.get("downloads/folder", "")).strip()
        if not folder:
            folder = str(Path.home() / "Pictures" / "Waifu Gallery")
        extension = Path(post.image_url.split("?", 1)[0]).suffix or ".jpg"
        suggested = str(Path(folder) / f"waifu_{post.post_id}{extension}")
        is_video = post.media_type == "video"
        title = "Save video" if is_video else "Save image"
        file_types = (
            "Videos (*.mp4 *.m4v *.webm *.mov *.mkv *.avi);;All files (*.*)"
            if is_video else "Images (*.jpg *.jpeg *.png *.webp *.gif);;All files (*.*)"
        )
        filename, _ = QFileDialog.getSaveFileName(self, title, suggested, file_types)
        if not filename:
            return
        key = str(uuid4())
        path = Path(filename)
        self.downloads.add_download(key, path.name, str(path))
        task = FileDownloadTask(key, self._catalog(), post, path)
        task.signals.result.connect(lambda download_key, result: self._task_succeeded(f"download:{download_key}", result))
        task.signals.error.connect(lambda download_key, error: self._task_failed(f"download:{download_key}", error))
        task.signals.cancelled.connect(self._task_cancelled)
        task.signals.progress.connect(lambda download_key, value: self.downloads.update_download(
            download_key, f"Downloading: {path.name}", value))
        self.tasks[f"download:{key}"] = task
        self.pool.start(task)

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.Enter
            and isinstance(watched, QWidget)
            and (watched is self or self.isAncestorOf(watched))
        ):
            # Search results and dialogs create child widgets after startup;
            # enable tracking as they appear so resize cursors still work over
            # those dynamically-created surfaces near the window edges.
            watched.setMouseTracking(True)
        if (
            event.type() == QEvent.Type.MouseMove
            and isinstance(watched, QWidget)
            and watched.window() is self
        ):
            self._update_resize_cursor(event.globalPosition().toPoint())
        elif (
            event.type() == QEvent.Type.Leave
            and watched is self
            and self._resize_cursor_active
        ):
            self._clear_resize_cursor()
        if (
            isinstance(watched, QWidget)
            and (watched is self or self.isAncestorOf(watched))
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and watched.window() is self
            and not self._fullscreen_active
            and not self.isMaximized()
        ):
            handle = self.windowHandle()
            if handle:
                point = event.globalPosition().toPoint()
                local = self.mapFromGlobal(point)
                border = 8
                if self.rect().contains(local):
                    edges = Qt.Edge(0)
                    if local.x() < border:
                        edges |= Qt.Edge.LeftEdge
                    elif local.x() >= self.width() - border:
                        edges |= Qt.Edge.RightEdge
                    if local.y() < border:
                        edges |= Qt.Edge.TopEdge
                    elif local.y() >= self.height() - border:
                        edges |= Qt.Edge.BottomEdge
                    if edges and handle.startSystemResize(edges):
                        event.accept()
                        return True
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.HoverMove):
            if self._fullscreen_active:
                self._show_fullscreen_controls()
            else:
                player = self._active_video_player()
                if (
                    player is not None
                    and isinstance(watched, QWidget)
                    and (watched is player or player.isAncestorOf(watched))
                ):
                    player.set_controls_visible(True)
                    if player.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                        self._media_controls_idle_timer.start()
        if watched is self.search_input:
            if event.type() == QEvent.Type.FocusIn:
                glow = QGraphicsDropShadowEffect(self.search_input)
                glow.setBlurRadius(18)
                glow.setColor(QColor(187, 154, 247, 115))
                glow.setOffset(0, 0)
                self.search_input.setGraphicsEffect(glow)
            elif event.type() == QEvent.Type.FocusOut:
                self.search_input.setGraphicsEffect(None)
        return super().eventFilter(watched, event)

    def _update_resize_cursor(self, global_point: QPoint) -> None:
        """Show the expected resize cursor over the frameless window edges."""
        local = self.mapFromGlobal(global_point)
        border = 8
        inside = self.rect().contains(local)
        cursor = None
        if inside and not self.isMaximized() and not self._fullscreen_active:
            left, right = local.x() < border, local.x() >= self.width() - border
            top, bottom = local.y() < border, local.y() >= self.height() - border
            if (left and top) or (right and bottom):
                cursor = Qt.CursorShape.SizeFDiagCursor
            elif (right and top) or (left and bottom):
                cursor = Qt.CursorShape.SizeBDiagCursor
            elif left or right:
                cursor = Qt.CursorShape.SizeHorCursor
            elif top or bottom:
                cursor = Qt.CursorShape.SizeVerCursor

        if cursor is not None:
            if self._resize_cursor_active:
                QApplication.changeOverrideCursor(QCursor(cursor))
            else:
                QApplication.setOverrideCursor(QCursor(cursor))
                self._resize_cursor_active = True
        else:
            self._clear_resize_cursor()

    def _clear_resize_cursor(self) -> None:
        if self._resize_cursor_active:
            QApplication.restoreOverrideCursor()
            self._resize_cursor_active = False

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self._fullscreen_active:
            self._exit_fullscreen()
            event.accept()
            return
        super().keyPressEvent(event)

    def nativeEvent(self, event_type, message):
        event_name = event_type.decode(errors="ignore") if isinstance(event_type, bytes) else str(event_type)
        if event_name == "windows_generic_MSG" and not self.isMaximized():
            try:
                native_message = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
                if native_message.message == 0x0084:  # WM_NCHITTEST
                    point = self.mapFromGlobal(QCursor.pos())
                    x, y = point.x(), point.y()
                    width, height, border = self.width(), self.height(), 7
                    left, right = x < border, x >= width - border
                    top, bottom = y < border, y >= height - border
                    hit = None
                    if top and left:
                        hit = 13  # HTTOPLEFT
                    elif top and right:
                        hit = 14  # HTTOPRIGHT
                    elif bottom and left:
                        hit = 16  # HTBOTTOMLEFT
                    elif bottom and right:
                        hit = 17  # HTBOTTOMRIGHT
                    elif left:
                        hit = 10  # HTLEFT
                    elif right:
                        hit = 11  # HTRIGHT
                    elif top:
                        hit = 12  # HTTOP
                    elif bottom:
                        hit = 15  # HTBOTTOM
                    if hit is not None:
                        return True, hit
            except (TypeError, ValueError, OSError):
                pass
        return super().nativeEvent(event_type, message)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_settle_timer.start()
        if hasattr(self, "gallery_status") and self.gallery_status.isVisible():
            width = min(820, max(280, self.gallery_page.width() - 40))
            self.gallery_status.setFixedWidth(width)
            self.gallery_status.adjustSize()
            height = min(110, max(42, self.gallery_status.sizeHint().height()))
            self.gallery_status.setGeometry((self.gallery_page.width() - width) // 2, 12, width, height)
        if hasattr(self, "random_ambient"):
            self.random_ambient.setGeometry(self.random_page.rect())
            self.random_ambient.lower()
        if hasattr(self, "detail_ambient"):
            self.detail_ambient.setGeometry(self.detail_page.rect())
            self.detail_ambient.lower()
        self._position_detail_video_navigation()

    def _finish_resize_settle(self) -> None:
        """Apply costly view reflows once the user finishes resizing."""
        if not self.isVisible():
            return
        current_page = self.pages.currentWidget()
        current_post = None
        if current_page is self.random_page:
            current_post = self.random_post
        elif current_page is self.detail_page:
            current_post = self.detail_post
        video_page = current_post is not None and current_post.media_type == "video"
        if not (self._fullscreen_active and video_page):
            self._refresh_ambient_layers()
            self._render_random_image()
            if hasattr(self, "detail_image"):
                self.detail_image._fit_to_viewport()
            if video_page and self._ambient_restore_timer.isActive():
                self._ambient_restore_timer.stop()
        if self.pages.currentWidget() is self.gallery_page and self.posts:
            columns = self._gallery_column_count()
            if columns != getattr(self, "_gallery_columns", None):
                self._set_gallery_rows_top_aligned()
            self._update_card_icon_sizes()
        if self._fullscreen_active and (
            self.fullscreen_toolbar.isVisible() or self.random_fullscreen_toolbar.isVisible()
        ):
            self._show_fullscreen_controls()
