import ctypes
from ctypes import wintypes
import re
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QByteArray, QEvent, QPoint, Qt, QThreadPool, QSize, QTimer, QUrl
from PySide6.QtGui import QActionGroup, QColor, QCursor, QDesktopServices, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
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
    QProgressBar,
    QMenu,
    QSizeGrip,
    QGraphicsDropShadowEffect,
    QGraphicsBlurEffect,
    QApplication,
)

from ..models import ImagePost, SearchPage
from ..providers import BooruCatalog, ProviderError
from ..settings import AppSettings
from .downloads import DownloadsDialog
from .favorites import FavoritesDialog, favorite_key
from .preferences import PreferencesDialog
from .video import VideoPlayerWidget
from .viewer import ZoomImage
from .workers import BackgroundTask, FileDownloadTask


class GalleryTitleBar(QWidget):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
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

        self.search_input = QLineEdit()
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
        button.setIcon(self.window._icon(icon))
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
        central = self.window.centralWidget()
        search_width = min(560, max(280, round(self.window.width() * 0.42)))
        center_in_window = central.mapTo(self.window, QPoint(central.width() // 2, 0)).x()
        title_left_in_window = self.mapTo(self.window, QPoint(0, 0)).x()
        search_x = center_in_window - title_left_in_window - search_width // 2
        self.search_input.setGeometry(search_x, 4, search_width, 34)
        self.home_button.move(search_x - self.home_button.width() - 8, 4)

    def add_navigation_action(self, button: QPushButton) -> None:
        self.navigation_layout.addWidget(button)

    def refresh_search_icon(self) -> None:
        self.search_action.setIcon(self.window._icon("search"))

    def toggle_maximize(self) -> None:
        if self.window.isMaximized():
            self.window.showNormal()
            icon = "maximize"
            tooltip = "Maximize"
        else:
            self.window.showMaximized()
            icon = "restore"
            tooltip = "Restore"
        self.maximize_button.setIcon(self.window._icon(icon))
        self.maximize_button.setToolTip(tooltip)

    def refresh_icons(self) -> None:
        for button, name in (
            (self.minimize_button, "minimize"),
            (self.maximize_button, "restore" if self.window.isMaximized() else "maximize"),
            (self.close_button, "close"),
        ):
            button.setIcon(self.window._icon(name))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window.windowHandle()
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
        self.card_frames: dict[str, QWidget] = {}
        self.active_detail_id = ""
        self.detail_post: ImagePost | None = None
        self.favorites_dialog: FavoritesDialog | None = None
        self.favorites_dialog_token = ""
        self._opening_favorite = False
        self._fullscreen_active = False
        self._was_maximized_before_fullscreen = False
        self._ambient_preview_enabled: bool | None = None
        self.card_buttons: dict[str, QPushButton] = {}
        self.current_theme = str(self.settings.get("appearance/theme", "Dark"))
        if self.current_theme not in ("Dark", "Light", "System"):
            self.current_theme = "Dark"
        self._icon_cache: dict[tuple[str, str], QIcon] = {}
        self._icon_buttons: list[QPushButton] = []
        self.downloads = DownloadsDialog(self)
        self._fullscreen_idle_timer = QTimer(self)
        self._fullscreen_idle_timer.setSingleShot(True)
        self._fullscreen_idle_timer.setInterval(1800)
        self._fullscreen_idle_timer.timeout.connect(self._hide_fullscreen_controls)
        self.setWindowTitle("Waifu Gallery")
        self.setWindowIcon(self._app_icon())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(860, 600)
        self.resize(1180, 820)
        self._build_ui()
        app = QApplication.instance()
        if app:
            # Catch mouse presses on child widgets too, so every window edge
            # can start the native Windows resize operation.
            app.installEventFilter(self)
        self._apply_theme(self.current_theme)
        QTimer.singleShot(0, self.show_random)

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
        self.settings_button = self._icon_button("menu", "Settings and options")
        self.fullscreen_button = self._icon_button("expand", "Fullscreen")
        self.fullscreen_button.hide()
        self.favorite_button = self._icon_button("heart", "Add to favorites")
        self.favorite_button.hide()
        self.favorite_button.clicked.connect(self.toggle_favorite)
        self._build_filter_menu()
        self.refresh_button = self._icon_button("refresh-cw", "Refresh current view")
        self.download_button = self._icon_button("download", "Download current image")
        self.title_bar.add_action(self.refresh_button)
        self.title_bar.add_action(self.download_button)
        self.title_bar.add_action(self.settings_button)

        self.progress = QProgressBar()
        self.progress.setObjectName("loadProgress")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.hide()

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
                       self.random_video, self.random_media_stack, self.random_video.video,
                       self.random_video.play_overlay, self.random_video.play_pause):
            widget.setMouseTracking(True)
            widget.installEventFilter(self)
        self.pages.addWidget(self.random_page)

        self.gallery_page = QWidget()
        gallery_layout = QVBoxLayout(self.gallery_page)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_status = QLabel("")
        gallery_layout.addWidget(self.gallery_status)
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.gallery_content = QWidget()
        self.gallery_grid = QGridLayout(self.gallery_content)
        self.gallery_grid.setContentsMargins(2, 2, 2, 2)
        self.gallery_grid.setSpacing(10)
        self.gallery_scroll.setWidget(self.gallery_content)
        gallery_layout.addWidget(self.gallery_scroll, 1)
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
        detail_header = QHBoxLayout()
        self.detail_title = QLabel("")
        self.detail_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_header.addStretch(1)
        detail_header.addWidget(self.detail_title)
        detail_header.addStretch(1)
        detail_layout.addLayout(detail_header)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(False)
        self.detail_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
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
            button.setObjectName("detailNavigation")
            button.setFixedSize(42, 42)
        self.detail_previous_button.clicked.connect(lambda: self._swipe_detail(-1))
        self.detail_next_button.clicked.connect(lambda: self._swipe_detail(1))
        detail_view_layout = QHBoxLayout()
        detail_view_layout.setContentsMargins(12, 0, 12, 0)
        detail_view_layout.setSpacing(12)
        detail_view_layout.addWidget(self.detail_previous_button, 0, Qt.AlignmentFlag.AlignVCenter)
        detail_view_layout.addWidget(self.detail_media_stack, 1)
        detail_view_layout.addWidget(self.detail_next_button, 0, Qt.AlignmentFlag.AlignVCenter)
        detail_layout.addLayout(detail_view_layout, 1)
        self.detail_previous_button.hide()
        self.detail_next_button.hide()

        self.fullscreen_toolbar = QFrame(self.detail_page)
        self.fullscreen_toolbar.setObjectName("fullscreenToolbar")
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
        self.detail_video_previous_action = self._icon_button("chevron-left", "Previous result")
        self.detail_video_favorite_action = self._icon_button("heart", "Add to favorites")
        self.detail_video_download_action = self._icon_button("download", "Download video")
        self.detail_video_next_action = self._icon_button("chevron-right", "Next result")
        self.detail_video_exit_action = self._icon_button("restore", "Exit fullscreen")
        for action in (
            self.detail_video_previous_action,
            self.detail_video_favorite_action,
            self.detail_video_download_action,
            self.detail_video_next_action,
            self.detail_video_exit_action,
        ):
            self.detail_video.add_fullscreen_action(action)
        self.detail_video_previous_action.clicked.connect(lambda: self._swipe_detail(-1))
        self.detail_video_favorite_action.clicked.connect(self.toggle_favorite)
        self.detail_video_download_action.clicked.connect(self.download_active_image)
        self.detail_video_next_action.clicked.connect(lambda: self._swipe_detail(1))
        self.detail_video_exit_action.clicked.connect(self._exit_fullscreen)
        self.fullscreen_toolbar.hide()

        for widget in (
            self.detail_page, self.detail_scroll, self.detail_scroll.viewport(), self.detail_image,
            self.detail_video, self.detail_media_stack, self.detail_video.video,
            self.detail_video.play_overlay, self.detail_video.play_pause,
            self.fullscreen_toolbar, self.fullscreen_previous_button, self.fullscreen_favorite_button,
            self.fullscreen_download_button, self.fullscreen_next_button, self.fullscreen_exit_button,
        ):
            widget.setMouseTracking(True)
            widget.installEventFilter(self)
        self.pages.addWidget(self.detail_page)
        content_layout.addWidget(self.pages, 1)
        body_layout.addWidget(content, 1)
        root_layout.addWidget(body, 1)
        root_layout.addWidget(self.progress)

        self.setCentralWidget(root)
        status = QStatusBar()
        status.setObjectName("statusBar")
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        self.footer_meta = QLabel("Ready")
        self.footer_meta.setObjectName("footerMeta")
        status.addPermanentWidget(self.footer_meta, 1)
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
        self.provider_actions = {}
        provider_group = QActionGroup(menu)
        provider_group.setExclusive(True)
        provider_menu = menu.addMenu("Provider")
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
        for theme in ("Dark", "Light", "System"):
            action = theme_menu.addAction(theme)
            action.setCheckable(True)
            action.setChecked(theme == self.current_theme)
            theme_group.addAction(action)
            action.triggered.connect(
                lambda checked, selected=theme: self.change_theme(selected) if checked else None
            )
            self.theme_actions[theme] = action

        self.image_credits_menu = menu.addMenu("Image credits")
        self.image_credits_menu.menuAction().setVisible(False)
        self.credit_artist_action = self.image_credits_menu.addAction("Artist: not provided")
        self.credit_source_action = self.image_credits_menu.addAction("Source: not provided")
        self.credit_artist_action.setEnabled(False)
        self.credit_source_action.setEnabled(False)
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
        tooltip = f"Settings · {self.selected_provider} · {rating_names[self.selected_rating]}"
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
        } for post in posts])

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
        posts = self._favorite_posts()
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
                self._submit(f"favorite-thumbnail:{token}/{key}", self._fetch_preview, candidates)
        dialog.exec()

    def _clear_favorites_dialog(self, token: str) -> None:
        if self.favorites_dialog_token == token:
            self.favorites_dialog = None
            self.favorites_dialog_token = ""

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
        dialog = self.favorites_dialog
        if dialog:
            self._favorite_navigation_posts = list(dialog.posts)
            dialog.accept()
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
        if theme not in ("Dark", "Light", "System"):
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
        else:
            palette = {
                "BG": "#000000", "SIDEBAR": "#101116", "PANEL": "#000000",
                "TEXT": "#A9B1D6", "STRONG": "#C0CAF5", "MUTED": "#7982A9",
                "BORDER": "#343A55", "HOVER": "#2D334B", "ACCENT": "#BB9AF7",
                "BLUE": "#7AA2F7", "ACTIVE": "#292E46", "PRESSED": "#202438",
                "DISABLED": "#202230", "MENU_SELECTED": "#343B58",
                "SEARCH_BG": "#050508", "SEARCH_BORDER": "#D7D9E2",
            }

        stylesheet = """
            * { font-family: "Inter", "Segoe UI", sans-serif; font-size: 10pt; }
            QMainWindow { background: transparent; border: 1px solid __BORDER__; border-radius: 12px; }
            QDialog, QWidget#appRoot, QWidget#contentArea { background: __BG__; color: __TEXT__; }
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
                border-radius: 10px; padding: 9px 12px; selection-background-color: __BLUE__;
            }
            QLineEdit:hover, QComboBox:hover, QListWidget:hover { border-color: __MUTED__; }
            QLineEdit:focus, QComboBox:focus { border: 1px solid __ACCENT__; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid __MUTED__; border-radius: 4px; background: __PANEL__; }
            QCheckBox::indicator:hover { border-color: __ACCENT__; }
            QCheckBox::indicator:checked { image: url("__CHECKMARK__"); background: __ACCENT__; border-color: __ACCENT__; }
            QComboBox { padding-right: 28px; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 26px; border: 0; }
            QComboBox QAbstractItemView { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; selection-background-color: __ACTIVE__; outline: 0; padding: 4px; }
            QPushButton { background: __PANEL__; color: __TEXT__; border: 1px solid __BORDER__; border-radius: 9px; padding: 8px 12px; }
            QPushButton:hover { background: __HOVER__; border-color: __MUTED__; color: __STRONG__; }
            QPushButton:pressed { background: __PRESSED__; }
            QPushButton:disabled { background: __DISABLED__; color: __MUTED__; border-color: __BORDER__; }
            QPushButton[iconAction="true"] { background: transparent; border: 0; padding: 0; }
            QPushButton[iconAction="true"]:hover { background: __HOVER__; }
            QPushButton#action_search { background: __BLUE__; border-color: __BLUE__; color: __BG__; }
            QPushButton#action_search:hover { background: __ACCENT__; border-color: __ACCENT__; }
            QPushButton#closeWindowButton:hover { background: #F7768E; border-color: #F7768E; }
            QMenu { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; padding: 5px; }
            QMenu::item { padding: 7px 24px 7px 10px; border-radius: 5px; }
            QMenu::item:selected { background: __MENU_SELECTED__; }
            QMenu::separator { height: 1px; background: __BORDER__; margin: 5px 4px; }
            QStatusBar#statusBar { background: __SIDEBAR__; color: __MUTED__; border: 0; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }
            QStatusBar#statusBar::item { border: 0; }
            QLabel#footerMeta { color: __MUTED__; padding-left: 8px; }
            QProgressBar { border: 0; background: __PANEL__; border-radius: 1px; }
            QProgressBar::chunk { background: __ACCENT__; border-radius: 1px; }
            QProgressBar#loadProgress { background: transparent; border: 0; border-radius: 0; }
            QProgressBar#loadProgress::chunk { background: __ACCENT__; border-radius: 0; }
            QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }
            QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
            QScrollBar::handle:vertical { background: __BORDER__; border-radius: 4px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: __MUTED__; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QStackedWidget, QWidget#randomPage, QWidget#detailPage { background: transparent; border: 0; }
            QLabel#randomImage, QLabel#detailImage { background: transparent; border: 0; }
            QFrame#fullscreenToolbar { background: rgba(22, 23, 34, 225); border: 1px solid __BORDER__; border-radius: 14px; }
            QPushButton#detailNavigation { background: __PANEL__; color: __TEXT__; border: 1px solid __BORDER__; border-radius: 21px; padding: 0; }
            QPushButton#detailNavigation:disabled { background: __PANEL__; color: __MUTED__; border-color: __BORDER__; }
            QPushButton#detailNavigation:hover, QFrame#fullscreenToolbar QPushButton:hover { background: __HOVER__; }
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

    def _catalog(self) -> BooruCatalog:
        return BooruCatalog(
            self.settings.gelbooru_credentials,
            bool(self.settings.get("search/exclude_male", True)),
            self.settings.use_doh,
            self.settings.rule34_credentials,
            bool(self.settings.get("search/filter_gore", True)),
            tuple(self.settings.get("search/custom_block_tags", []) or []),
            str(self.settings.get("search/media_filter", "image")),
            self.settings.doh_endpoint,
        )

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
        if self._ambient_preview_enabled is not None:
            return self._ambient_preview_enabled
        value = self.settings.get("view/ambient_mode", True)
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes", "on"}
        return bool(value)

    def _preview_ambient_mode(self, enabled: bool) -> None:
        self._ambient_preview_enabled = bool(enabled)
        self._apply_ambient_mode()

    def _apply_ambient_mode(self) -> None:
        enabled = self._ambient_mode_enabled()
        for label, page in ((self.random_ambient, self.random_page), (self.detail_ambient, self.detail_page)):
            label.setGeometry(page.rect())
            pixmap = label.pixmap()
            has_image = pixmap is not None and not pixmap.isNull()
            label.setVisible(enabled and has_image)
            label.lower()

    @staticmethod
    def _set_zoom_scrollbars(scroll_area: QScrollArea, zoomed: bool) -> None:
        """Keep the image pannable while hiding scrollbars in zoomed view."""
        policy = (
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            if zoomed
            else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll_area.setHorizontalScrollBarPolicy(policy)
        scroll_area.setVerticalScrollBarPolicy(policy)

    def _submit(self, key: str, operation, *args, progress_callback=None) -> None:
        task = BackgroundTask(key, operation, *args)
        task.signals.result.connect(self._task_succeeded)
        task.signals.error.connect(self._task_failed)
        if progress_callback:
            task.signals.progress.connect(progress_callback)
            task.kwargs["report_progress"] = lambda value: task.signals.progress.emit(key, value)
        self.tasks[key] = task
        self.pool.start(task)

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
                self._show_random_image(self.random_content)
            self._sync_favorite_buttons()
        elif category == "post-detail" and identifier == self.active_detail_id:
            pixmap = QPixmap()
            if pixmap.loadFromData(result):
                self.detail_media_stack.setCurrentWidget(self.detail_scroll)
                self.detail_video.clear()
                self.detail_image.set_image(pixmap)
                self._set_image_credits_visible(True)
                self._set_ambient_image(self.detail_ambient, pixmap, self.detail_page)
                self.fullscreen_button.setVisible(not self._fullscreen_active)
                self._sync_favorite_buttons()
                self.footer_meta.setText(
                    f"{self.detail_post.provider} · {self.detail_post.rating.upper()} · "
                    f"{pixmap.width()} × {pixmap.height()}"
                )
            else:
                self.fullscreen_button.hide()
                self.detail_image.set_placeholder("The provider returned an unsupported image format.")
            self._finish_loading()
            self.statusBar().showMessage("Image loaded", 3000)
        elif category == "random-video" and int(identifier) == self.request_id:
            self.random_video.set_source(str(result))
            self._set_image_credits_visible(True)
            self._finish_loading()
            self.statusBar().showMessage("Video ready · Press Play to watch", 4000)
        elif category == "post-detail-video" and identifier == self.active_detail_id:
            self.detail_video.set_source(str(result))
            self._set_image_credits_visible(True)
            self._finish_loading()
            self.statusBar().showMessage("Video ready · Press Play to watch", 4000)
        elif category == "random-video-preview" and int(identifier) == self.request_id:
            pixmap = QPixmap()
            if pixmap.loadFromData(result):
                self.random_video.set_poster(pixmap)
                self._set_ambient_image(self.random_ambient, pixmap, self.random_page)
        elif category == "detail-video-preview" and identifier == self.active_detail_id:
            pixmap = QPixmap()
            if pixmap.loadFromData(result):
                self.detail_video.set_poster(pixmap)
                self._set_ambient_image(self.detail_ambient, pixmap, self.detail_page)
        elif category == "thumbnail":
            generation, index = map(int, identifier.split("/"))
            if generation != self.gallery_generation or index >= len(self.posts):
                return
            pixmap = QPixmap()
            if pixmap.loadFromData(result):
                post = self.posts[index]
                self.thumbnail_cache[post.post_id] = pixmap
                self._set_card_image(index, post, pixmap)
        elif category == "favorite-thumbnail":
            token, favorite_id = identifier.split("/", 1)
            if token != self.favorites_dialog_token or not self.favorites_dialog:
                return
            pixmap = QPixmap()
            if pixmap.loadFromData(result):
                self.favorites_dialog.set_thumbnail(favorite_id, pixmap)
            else:
                self.favorites_dialog.set_thumbnail_error(favorite_id)
        elif category == "download":
            self.downloads.update_download(identifier, f"Saved: {result}")
            self.statusBar().showMessage(f"Saved image to {result}", 5000)

    def _task_failed(self, key: str, error: str) -> None:
        self.tasks.pop(key, None)
        category, _, identifier = key.partition(":")
        if category == "search" and int(identifier) == self.request_id:
            self._set_image_credits_visible(False)
            pending_detail = self._open_detail_after_page is not None
            self._open_detail_after_page = None
            self._finish_loading()
            self.gallery_status.setText(f"Search failed: {error}")
            self.page_label.setText(f"Page {self.current_page} · Failed")
            if pending_detail:
                if self._fullscreen_active:
                    self._exit_fullscreen()
                self.pages.setCurrentWidget(self.gallery_page)
                self.back_button.hide()
            self.statusBar().showMessage(f"Search failed: {error}")
        elif category in {"random", "random-image"} and int(identifier) == self.request_id:
            self._finish_loading()
            self.random_media_stack.setCurrentWidget(self.random_scroll)
            self.random_video.clear()
            self.fullscreen_button.hide()
            self.random_image.set_placeholder(f"Could not load an image\n{error}")
            self.statusBar().showMessage(f"Could not load image: {error}")
        elif category == "random-video" and int(identifier) == self.request_id:
            self._finish_loading()
            self.random_video.message.setText(f"Could not prepare video: {error}")
            self.statusBar().showMessage(f"Could not prepare video: {error}")
        elif category == "post-detail" and identifier == self.active_detail_id:
            self._finish_loading()
            self.detail_media_stack.setCurrentWidget(self.detail_video if self.detail_post and self.detail_post.media_type == "video" else self.detail_scroll)
            self.detail_image.set_image(QPixmap())
            self.detail_image.set_placeholder(f"Could not load image\n{error}")
            self.statusBar().showMessage(f"Could not load image: {error}")
        elif category == "post-detail-video" and identifier == self.active_detail_id:
            self._finish_loading()
            self.detail_video.message.setText(f"Could not prepare video: {error}")
            self.statusBar().showMessage(f"Could not prepare video: {error}")
        elif category == "thumbnail":
            generation, index = map(int, identifier.split("/"))
            if generation == self.gallery_generation and index < len(self.posts):
                button = self.card_buttons.get(self.posts[index].post_id)
                if button:
                    button.setText("Preview unavailable")
        elif category == "favorite-thumbnail":
            token, favorite_id = identifier.split("/", 1)
            if token == self.favorites_dialog_token and self.favorites_dialog:
                self.favorites_dialog.set_thumbnail_error(favorite_id)
        elif category == "download":
            self.downloads.update_download(identifier, f"Failed: {error}")

    def _begin_loading(self, message: str) -> None:
        # Keep the bar empty while the provider is searching. It becomes
        # determinate only after image bytes start arriving.
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.show()
        self.footer_meta.setText(message)
        self.statusBar().showMessage(message)

    def _finish_loading(self) -> None:
        self.progress.hide()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    def _update_load_progress(self, key: str, value: int) -> None:
        category, _, identifier = key.partition(":")
        if category in {"random", "random-video", "random-video-preview"} and identifier != str(self.request_id):
            return
        if category in {"post-detail", "post-detail-video", "detail-video-preview"} and identifier != self.active_detail_id:
            return
        if value < 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        else:
            self.progress.setValue(max(0, min(100, value)))

    def _active_rating(self) -> str:
        return self.selected_rating

    def _rating_allowed(self) -> bool:
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
        self.random_pixmap = None
        self.random_media_stack.setCurrentWidget(self.random_scroll)
        self._set_image_credits_visible(False)
        self._update_image_credits(None)
        self.random_image.set_image(QPixmap())
        self.fullscreen_button.hide()
        self.random_image.set_placeholder("Loading an image…")
        self._begin_loading("Finding an image…")
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

    def _show_random_image(self, content: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(content):
            self._finish_loading()
            self.random_image.set_placeholder("The provider returned an unsupported image format.")
            return
        self.random_pixmap = pixmap
        self.random_content = content
        self.random_media_stack.setCurrentWidget(self.random_scroll)
        self.random_video.clear()
        self.random_image.set_image(pixmap)
        self._set_image_credits_visible(True)
        self._set_ambient_image(self.random_ambient, pixmap, self.random_page)
        self.fullscreen_button.setVisible(not self._fullscreen_active)
        self._sync_favorite_buttons()
        post = getattr(self, "random_post", None)
        if post:
            self.footer_meta.setText(
                f"{post.provider} · {post.rating.upper()} · {pixmap.width()} × {pixmap.height()}"
            )
        self._finish_loading()
        self.statusBar().showMessage("Image loaded", 3000)

    def _show_random_video(self, post: ImagePost) -> None:
        self.random_video.clear()
        self.random_media_stack.setCurrentWidget(self.random_video)
        self.random_video.message.setText("Preparing video…")
        self._submit(
            f"random-video:{self.request_id}", self._catalog().cache_video, post,
            progress_callback=self._update_load_progress,
        )
        if post.preview_urls:
            self._submit(f"random-video-preview:{self.request_id}", self._fetch_preview, post.preview_urls)
        self.fullscreen_button.setVisible(not self._fullscreen_active)
        self._sync_favorite_buttons()
        self.footer_meta.setText(f"{post.provider} · {post.rating.upper()} · VIDEO")
        self._begin_loading("Preparing video…")

    def _render_random_image(self) -> None:
        self.random_image._fit_to_viewport()

    def start_search(self) -> None:
        if not self._rating_allowed():
            return
        query = self.search_input.text().strip()
        if not query:
            self.go_home()
            return
        self.current_query = query
        self.title_bar.home_button.show()
        self.footer_meta.setText(f"Searching · {query}")
        self.current_page = 1
        self.load_page(1)

    def load_page(self, page: int, detail_index: int | None = None) -> None:
        if not self.current_query or not self._rating_allowed():
            return
        self.random_video.clear()
        self.detail_video.clear()
        self._open_detail_after_page = detail_index
        if detail_index is None:
            self._set_image_credits_visible(False)
            if self._fullscreen_active:
                self._exit_fullscreen()
            self.pages.setCurrentWidget(self.gallery_page)
            self.back_button.hide()
            self.fullscreen_button.hide()
            self._sync_favorite_buttons()
            self.title_bar.home_button.show()
            self.detail_previous_button.hide()
            self.detail_next_button.hide()
        else:
            self.detail_image.set_image(QPixmap())
            self.detail_image.set_placeholder("Loading next image...")
        self.current_page = max(1, page)
        self.request_id = self._new_request()
        identifier = self.request_id
        self.gallery_generation += 1
        self.posts = ()
        self._clear_gallery()
        self.gallery_status.setText("Loading results…")
        self.page_label.setText(f"Page {self.current_page} · Loading")
        self.previous_button.setEnabled(False)
        self.next_button.setEnabled(False)
        if detail_index is not None:
            self.fullscreen_previous_button.setEnabled(False)
            self.fullscreen_next_button.setEnabled(False)
            self.detail_previous_button.setEnabled(False)
            self.detail_next_button.setEnabled(False)
        self.gallery_scroll.verticalScrollBar().setValue(0)
        self._begin_loading("Searching providers…")
        self._submit(f"search:{identifier}", self._catalog().search, self.current_query, self._active_rating(),
                     self.selected_provider, self.current_page, 50)

    def _show_search_results(self, page: SearchPage) -> None:
        self.posts = page.posts
        self._page_has_more = page.has_more
        self.footer_meta.setText(f"Search · {len(self.posts)} images · Page {self.current_page}")
        self._clear_gallery()
        for index, post in enumerate(self.posts):
            self._add_card(index, post)
            self._submit_thumbnail(index, post)
        self.page_label.setText(f"Page {self.current_page} · {len(self.posts)} images")
        self.previous_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(page.has_more)
        if page.fallback_from and page.posts:
            message = f"No results from {page.fallback_from}; automatically showing {page.posts[0].provider} results."
            if page.provider_errors:
                message += " Some providers were unavailable: " + " | ".join(page.provider_errors)
            self.gallery_status.setText(message)
        elif page.provider_errors and page.posts:
            self.gallery_status.setText("Some providers could not be reached: " + " | ".join(page.provider_errors))
        elif page.posts:
            self.gallery_status.setText(f'Results for “{self.current_query}”')
        else:
            self.gallery_status.setText(f'No images found for “{self.current_query}”.')
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

    def _clear_gallery(self) -> None:
        self.card_buttons.clear()
        self.card_frames.clear()
        while self.gallery_grid.count():
            entry = self.gallery_grid.takeAt(0)
            widget = entry.widget()
            if widget:
                widget.deleteLater()

    def _add_card(self, index: int, post: ImagePost) -> None:
        frame = QWidget()
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(4)
        button = QPushButton("Loading preview…")
        button.setObjectName("previewImage")
        button.setMinimumSize(190, 225)
        button.clicked.connect(lambda _checked=False, selected=post: self.open_post(selected))
        card_layout.addWidget(button)
        if post.title:
            title = QLabel(post.title)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setWordWrap(True)
            card_layout.addWidget(title)
        columns = max(2, self.gallery_scroll.viewport().width() // 225)
        self.gallery_grid.addWidget(frame, index // columns, index % columns)
        self.card_buttons[post.post_id] = button
        self.card_frames[post.post_id] = frame
        if post.post_id in self.thumbnail_cache:
            self._set_card_image(index, post, self.thumbnail_cache[post.post_id])

    def _submit_thumbnail(self, index: int, post: ImagePost) -> None:
        if post.post_id in self.thumbnail_cache:
            return
        key = f"thumbnail:{self.gallery_generation}/{index}"
        self._submit(key, self._fetch_preview, post.preview_urls)

    def _fetch_preview(self, candidates: tuple[str, ...]) -> bytes:
        failures = []
        for url in candidates:
            try:
                return self._catalog().fetch_image(url)
            except ProviderError as error:
                failures.append(str(error))
        raise ProviderError(failures[-1] if failures else "No thumbnail URL was supplied.")

    def _set_card_image(self, index: int, post: ImagePost, pixmap: QPixmap) -> None:
        if index >= len(self.posts) or self.posts[index].post_id != post.post_id:
            return
        button = self.card_buttons.get(post.post_id)
        if button:
            button.setText("")
            button.setIcon(QIcon(pixmap))
            button.setIconSize(QSize(175, 195))

    def open_post(self, post: ImagePost) -> None:
        self.random_video.clear()
        self.detail_video.clear()
        self._set_ambient_image(self.detail_ambient, QPixmap(), self.detail_page)
        self.detail_post = post
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
        self.detail_previous_button.setVisible(show_navigation and not self._fullscreen_active)
        self.detail_next_button.setVisible(show_navigation and not self._fullscreen_active)
        self.fullscreen_previous_button.setVisible(show_navigation)
        self.fullscreen_next_button.setVisible(show_navigation)
        self._update_detail_navigation()
        self.active_detail_id = str(uuid4())
        self.detail_title.setText(post.title or f"{post.provider} | {post.rating.upper()}")
        self._update_image_credits(post)
        self.detail_image.set_image(QPixmap())
        self.pages.setCurrentWidget(self.detail_page)
        self._sync_favorite_buttons()
        self.back_button.show()
        if post.media_type == "video":
            self.detail_media_stack.setCurrentWidget(self.detail_video)
            self.detail_video.message.setText("Preparing video…")
            self._submit(
                f"post-detail-video:{self.active_detail_id}", self._catalog().cache_video, post,
                progress_callback=self._update_load_progress,
            )
            preview = self.thumbnail_cache.get(post.post_id)
            if preview:
                self.detail_video.set_poster(preview)
                self._set_ambient_image(self.detail_ambient, preview, self.detail_page)
            elif post.preview_urls:
                self._submit(f"detail-video-preview:{self.active_detail_id}", self._fetch_preview, post.preview_urls)
            else:
                self._set_ambient_image(self.detail_ambient, QPixmap(), self.detail_page)
            self.footer_meta.setText(f"{post.provider} · {post.rating.upper()} · VIDEO")
            self._begin_loading("Preparing video…")
        else:
            self.detail_media_stack.setCurrentWidget(self.detail_scroll)
            self.detail_image.set_placeholder("Loading image...")
            self._begin_loading("Loading image...")
            self._submit(
                f"post-detail:{self.active_detail_id}", self._catalog().fetch_image, post.image_url,
                progress_callback=self._update_load_progress,
            )

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
        for button in (self.detail_previous_button, self.fullscreen_previous_button):
            button.setEnabled(previous_available)
        for button in (self.detail_next_button, self.fullscreen_next_button):
            button.setEnabled(next_available)
        show_navigation = self._detail_has_navigation()
        self.detail_previous_button.setVisible(show_navigation and not self._fullscreen_active)
        self.detail_next_button.setVisible(show_navigation and not self._fullscreen_active)
        self.fullscreen_previous_button.setVisible(show_navigation)
        self.fullscreen_next_button.setVisible(show_navigation)

    def _update_image_credits(self, post: ImagePost | None) -> None:
        artists = ", ".join(post.artists) if post and post.artists else "not provided"
        source = post.source if post and post.source else "not provided"
        artist_label = artists if len(artists) <= 72 else artists[:69] + "..."
        source_label = source if len(source) <= 72 else source[:69] + "..."
        self.credit_artist_action.setText(f"Artist: {artist_label}")
        self.credit_artist_action.setToolTip(artists)
        self.credit_source_action.setText(f"Source: {source_label}")
        source_url = QUrl(source)
        can_open_source = source_url.isValid() and source_url.scheme().lower() in ("http", "https")
        self.credit_source_action.setEnabled(can_open_source)
        self.credit_source_action.setToolTip(
            f"Open source: {source}" if can_open_source else source
        )
        try:
            self.credit_source_action.triggered.disconnect()
        except RuntimeError:
            pass
        if can_open_source:
            self.credit_source_action.triggered.connect(
                lambda _checked=False, url=source_url: QDesktopServices.openUrl(url)
            )

    def _set_image_credits_visible(self, visible: bool) -> None:
        """Expose credits only when a full image or video is currently loaded."""
        self.image_credits_menu.menuAction().setVisible(visible)

    def back_to_results(self) -> None:
        if self._fullscreen_active:
            self._exit_fullscreen()
        self._set_image_credits_visible(False)
        self.back_button.hide()
        self.detail_previous_button.hide()
        self.detail_next_button.hide()
        self.fullscreen_button.hide()
        self._sync_favorite_buttons()
        if self.detail_origin == "favorites":
            self.title_bar.home_button.show()
            self.show_favorites()
        elif self.detail_origin == "search":
            self.pages.setCurrentWidget(self.gallery_page)
            self.title_bar.home_button.show()
        else:
            self.go_home()

    def _toggle_fullscreen(self) -> None:
        if self._fullscreen_active:
            self._exit_fullscreen()
            return
        current_page = self.pages.currentWidget()
        if current_page not in (self.random_page, self.detail_page):
            return
        self._fullscreen_source = "random" if current_page is self.random_page else "detail"
        self._was_maximized_before_fullscreen = self.isMaximized()
        self._fullscreen_active = True
        self.random_video.set_fullscreen_toggle_visible(False)
        self.detail_video.set_fullscreen_toggle_visible(False)
        self.title_bar.hide()
        self.statusBar().hide()
        self.fullscreen_button.hide()
        if self._fullscreen_source != "random":
            self.detail_title.hide()
        self.detail_previous_button.hide()
        self.detail_next_button.hide()
        self.showFullScreen()
        self._sync_favorite_buttons()
        self._show_fullscreen_controls()
        image = self.random_image if self._fullscreen_source == "random" else self.detail_image
        QTimer.singleShot(0, image._fit_to_viewport)

    def _exit_fullscreen(self) -> None:
        if not self._fullscreen_active:
            return
        self._fullscreen_active = False
        self._fullscreen_idle_timer.stop()
        self.fullscreen_toolbar.hide()
        self.random_fullscreen_toolbar.hide()
        self.random_video.set_fullscreen_actions_visible(False)
        self.detail_video.set_fullscreen_actions_visible(False)
        if self._was_maximized_before_fullscreen:
            self.showMaximized()
        else:
            self.showNormal()
        self.title_bar.show()
        self.statusBar().show()
        self.random_video.set_fullscreen_toggle_visible(self.pages.currentWidget() is self.random_page)
        self.detail_video.set_fullscreen_toggle_visible(self.pages.currentWidget() is self.detail_page)
        if getattr(self, "_fullscreen_source", "detail") != "random":
            self.detail_title.show()
        image_page = self.pages.currentWidget()
        image_ready = (
            (image_page is self.random_page and not self.random_image.original.isNull())
            or (image_page is self.detail_page and not self.detail_image.original.isNull())
        )
        self.fullscreen_button.setVisible(image_ready)
        show_detail_navigation = self.pages.currentWidget() is self.detail_page and self._detail_has_navigation()
        self.detail_previous_button.setVisible(show_detail_navigation)
        self.detail_next_button.setVisible(show_detail_navigation)
        self.fullscreen_previous_button.setVisible(show_detail_navigation)
        self.fullscreen_next_button.setVisible(show_detail_navigation)
        self._sync_favorite_buttons()
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
            self.random_video.set_fullscreen_actions_visible(source == "random")
            self.detail_video.set_fullscreen_actions_visible(source != "random")
            favorite = any(favorite_key(item) == favorite_key(post) for item in self._favorite_posts())
            if source == "random":
                self.random_video_favorite_action.setIcon(self._icon("heart-filled" if favorite else "heart"))
            else:
                self.detail_video_favorite_action.setIcon(self._icon("heart-filled" if favorite else "heart"))
                can_navigate = self._detail_has_navigation()
                self.detail_video_previous_action.setVisible(can_navigate)
                self.detail_video_next_action.setVisible(can_navigate)
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

    def open_preferences(self) -> None:
        previous_provider = self.selected_provider
        previous_rating = self.selected_rating
        previous_media = str(self.settings.get("search/media_filter", "image"))
        previous_filter_settings = (
            bool(self.settings.get("search/exclude_male", True)),
            bool(self.settings.get("search/filter_gore", True)),
            tuple(self.settings.get("search/custom_block_tags", []) or []),
        )
        dialog = PreferencesDialog(self.settings, self)
        dialog.ambient_mode.toggled.connect(self._preview_ambient_mode)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._ambient_preview_enabled = None
            provider = str(self.settings.get("search/provider", "All"))
            rating = str(self.settings.get("search/rating", "sfw"))
            if provider in self.provider_actions:
                self.selected_provider = provider
                self.provider_actions[provider].setChecked(True)
            if rating in self.rating_actions:
                self.selected_rating = rating
                self.rating_actions[rating].setChecked(True)
            self._update_filter_tooltip()
            self._apply_ambient_mode()
            media_changed = str(self.settings.get("search/media_filter", "image")) != previous_media
            current_filter_settings = (
                bool(self.settings.get("search/exclude_male", True)),
                bool(self.settings.get("search/filter_gore", True)),
                tuple(self.settings.get("search/custom_block_tags", []) or []),
            )
            filters_changed = current_filter_settings != previous_filter_settings
            if (self.selected_provider != previous_provider or self.selected_rating != previous_rating or media_changed or filters_changed) and self._rating_allowed():
                if self.current_query:
                    self.load_page(self.current_page)
                else:
                    self.show_random()
        else:
            self._ambient_preview_enabled = None
            self._apply_ambient_mode()

    def queue_download(self, post: ImagePost) -> None:
        folder = str(self.settings.get("downloads/folder", "")).strip()
        if not folder:
            folder = str(Path.home() / "Pictures" / "Waifu Gallery")
        extension = Path(post.image_url.split("?", 1)[0]).suffix or ".jpg"
        suggested = str(Path(folder) / f"waifu_{post.post_id}{extension}")
        filename, _ = QFileDialog.getSaveFileName(self, "Save image", suggested, "Images (*.jpg *.jpeg *.png *.webp *.gif);;All files (*.*)")
        if not filename:
            return
        key = str(uuid4())
        path = Path(filename)
        self.downloads.add_download(key, path.name)
        task = FileDownloadTask(key, self._catalog(), post, path)
        task.signals.result.connect(lambda download_key, result: self._task_succeeded(f"download:{download_key}", result))
        task.signals.error.connect(lambda download_key, error: self._task_failed(f"download:{download_key}", error))
        task.signals.progress.connect(lambda download_key, value: self.downloads.update_download(
            download_key, f"Downloading: {path.name}", value))
        self.tasks[f"download:{key}"] = task
        self.pool.start(task)

    def eventFilter(self, watched, event):
        if (
            isinstance(watched, QWidget)
            and (watched is self or self.isAncestorOf(watched))
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
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
        if self._fullscreen_active and event.type() == QEvent.Type.MouseMove:
            self._show_fullscreen_controls()
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
        if hasattr(self, "random_ambient"):
            self.random_ambient.setGeometry(self.random_page.rect())
            source = getattr(self.random_ambient, "_ambient_source", QPixmap())
            if not source.isNull():
                self._set_ambient_image(self.random_ambient, source, self.random_page)
            self.random_ambient.lower()
        if hasattr(self, "detail_ambient"):
            self.detail_ambient.setGeometry(self.detail_page.rect())
            source = getattr(self.detail_ambient, "_ambient_source", QPixmap())
            if not source.isNull():
                self._set_ambient_image(self.detail_ambient, source, self.detail_page)
            self.detail_ambient.lower()
        self._render_random_image()
        if hasattr(self, "detail_image"):
            self.detail_image._fit_to_viewport()
            if self._fullscreen_active and (
                self.fullscreen_toolbar.isVisible() or self.random_fullscreen_toolbar.isVisible()
            ):
                self._show_fullscreen_controls()
        if self.posts:
            columns = max(2, self.gallery_scroll.viewport().width() // 225)
            while self.gallery_grid.count():
                self.gallery_grid.takeAt(0)
            for index, post in enumerate(self.posts):
                frame = self.card_frames.get(post.post_id)
                if frame:
                    self.gallery_grid.addWidget(frame, index // columns, index % columns)
