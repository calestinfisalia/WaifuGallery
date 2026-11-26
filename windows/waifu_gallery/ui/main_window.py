import ctypes
from ctypes import wintypes
import difflib
import logging
import os
import re
from pathlib import Path
import subprocess
from uuid import uuid4

from PySide6.QtCore import (
    QByteArray,
    QEasingCurve,
    QEvent,
    QPoint,
    Property,
    QRect,
    QPropertyAnimation,
    Qt,
    QThreadPool,
    QSize,
    QTimer,
)
from PySide6.QtGui import (
    QActionGroup,
    QColor,
    QCursor,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPixmap,
    QRegion,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QDialog,
    QCompleter,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QListView,
    QMenu,
    QSizeGrip,
    QGraphicsDropShadowEffect,
    QGraphicsBlurEffect,
    QGraphicsOpacityEffect,
    QApplication,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from .. import __version__
from ..favorite_cache import load_favorite_thumbnail, remove_favorite_thumbnail, save_favorite_thumbnail
from ..models import ImagePost, SearchPage
from ..providers import AI_GENERATED_BLOCK_TAGS, BooruCatalog, ProviderError
from ..pin_security import has_pin, verify_pin
from ..settings import AppSettings
from ..suggestion_cache import SuggestionCache
from .downloads import DownloadsDialog
from .credits import ImageCreditsDialog, rating_label
from .favorites import FavoritesDialog, favorite_key
from .indicators import CircularProgressIndicator
from .preferences import PreferencesDialog
from .pin_prompts import PinPromptDialog
from .backup_prompts import BackupMessageDialog
from .themes import THEME_NAMES, THEME_PALETTES
from .updates import (
    WINDOWS_INSTALLER,
    ReleaseNotesDialog,
    UpdateCheckTask,
    UpdateDownloadTask,
    version_parts,
)
from .video import VideoPlayerWidget
from .viewer import ZoomImage
from .scrollbars import CAPSULE_SCROLLBAR_STYLE
from .workers import BackgroundTask, FileDownloadTask, decode_image_bytes


_LOGGER = logging.getLogger(__name__)
HISTORY_QUERY_ROLE = Qt.ItemDataRole.UserRole + 1


class SearchLineEdit(QLineEdit):
    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if event.reason() != Qt.FocusReason.MouseFocusReason:
            QTimer.singleShot(0, self._clear_automatic_selection)

    def _clear_automatic_selection(self) -> None:
        if self.text() and self.selectedText() == self.text():
            self.deselect()


class SearchSuggestionDelegate(QStyledItemDelegate):
    """Render a trailing remove control on search history rows."""

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window

    @staticmethod
    def remove_rect(row_rect: QRect) -> QRect:
        return QRect(row_rect.right() - 43, row_rect.top(), 40, row_rect.height())

    def paint(self, painter, option, index) -> None:
        is_history = bool(index.data(HISTORY_QUERY_ROLE))
        item_option = QStyleOptionViewItem(option)
        if is_history:
            text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
            item_option.text = QFontMetrics(item_option.font).elidedText(
                text,
                Qt.TextElideMode.ElideRight,
                max(0, item_option.rect.width() - 42),
            )
        super().paint(painter, item_option, index)
        if is_history:
            hit_rect = self.remove_rect(option.rect)
            icon_rect = QRect(0, 0, 16, 16)
            icon_rect.moveCenter(hit_rect.center())
            self.window._icon("x").paint(
                painter, icon_rect
            )


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
        self.left_container = left_container
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
        self.search_input.setMinimumWidth(220)
        self.search_input.setMaximumWidth(560)
        self.search_input.setFixedHeight(34)
        self.search_input.setFrame(False)
        self.search_input.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.search_input.setParent(self)
        self.search_input.returnPressed.connect(window.start_search)
        self.home_button = window._icon_button("home", "Return to random images")
        self.home_button.setFixedSize(36, 34)
        self.home_button.hide()
        self.home_button.installEventFilter(self)
        self.home_button.clicked.connect(window.go_home)
        self._search_target_geometry = QRect()
        self._search_geometry_initialized = False
        self._search_geometry_timer = QTimer(self)
        self._search_geometry_timer.setSingleShot(False)
        self._search_geometry_timer.setInterval(16)
        self._search_geometry_timer.timeout.connect(self._animate_search_geometry)
        self.search_action = self.search_input.addAction(
            window._icon("search"), QLineEdit.ActionPosition.TrailingPosition
        )
        self.search_action.triggered.connect(window.start_search)

        right_container = QWidget(self)
        self.right_container = right_container
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
        self._update_search_target_geometry()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.home_button and event.type() in (
            QEvent.Type.Show,
            QEvent.Type.Hide,
        ):
            QTimer.singleShot(0, self._update_search_target_geometry)
        return super().eventFilter(watched, event)

    def _update_search_target_geometry(self) -> None:
        if self.main_window.centralWidget() is None:
            return
        left_edge = self.left_container.geometry().right() + 8
        right_edge = self.right_container.geometry().left() - 8
        central = self.main_window.centralWidget()
        center_in_window = central.mapTo(
            self.main_window, QPoint(central.width() // 2, 0)
        ).x()
        title_left_in_window = self.mapTo(self.main_window, QPoint(0, 0)).x()
        center_x = center_in_window - title_left_in_window
        available_width = max(
            1,
            2 * min(center_x - left_edge, right_edge - center_x),
        )
        preferred_width = min(560, max(220, round(self.main_window.width() * 0.42)))
        search_width = min(preferred_width, available_width)
        self._search_target_geometry = QRect(
            center_x - search_width // 2, 4, search_width, 34
        )
        if not self._search_geometry_initialized:
            self._search_geometry_initialized = True
            self._apply_search_geometry(self._search_target_geometry)
        elif getattr(self.main_window, "_resize_in_progress", False):
            self._search_geometry_timer.stop()
            self._apply_search_geometry(self._search_target_geometry)
        elif not self._search_geometry_timer.isActive():
            self._search_geometry_timer.start()

    def _animate_search_geometry(self) -> None:
        current = self.search_input.geometry()
        target = self._search_target_geometry
        values = []
        for old, new in (
            (current.x(), target.x()),
            (current.y(), target.y()),
            (current.width(), target.width()),
            (current.height(), target.height()),
        ):
            values.append(
                new if abs(new - old) <= 1 else round(old + (new - old) * 0.32)
            )
        next_geometry = QRect(*values)
        self._apply_search_geometry(next_geometry)
        if next_geometry == target:
            self._search_geometry_timer.stop()
            self._sync_search_suggestion_sizes()

    def _apply_search_geometry(self, geometry: QRect) -> None:
        if self.search_input.geometry() != geometry:
            self.search_input.setGeometry(geometry)
        suggestion_panel = getattr(self.main_window, "search_suggestion_panel", None)
        if suggestion_panel is not None and suggestion_panel.isVisible():
            if suggestion_panel.width() != geometry.width():
                suggestion_panel.setFixedWidth(geometry.width())
            self.main_window._position_search_suggestion_panel()
    def _sync_search_overlay_geometry(self) -> None:
        panel = getattr(self.main_window, "search_suggestion_panel", None)
        if panel is not None:
            if panel.width() != self.search_input.width():
                panel.setFixedWidth(self.search_input.width())
            self.main_window._position_search_suggestion_panel()

    def _sync_search_suggestion_sizes(self) -> None:
        model = getattr(self.main_window, "_search_suggestion_model", None)
        if model is not None:
            row_width = max(100, self.search_input.width() - 8)
            for row in range(model.rowCount()):
                item = model.item(row)
                if item is not None and item.sizeHint().width() != row_width:
                    item.setSizeHint(QSize(row_width, 34))

    def add_navigation_action(self, button: QPushButton) -> None:
        self.navigation_layout.addWidget(button)
        if button is not self.home_button:
            self.navigation_layout.addWidget(self.home_button)

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


class AmbientLayer(QLabel):
    _FADE_DURATION_MS = 300

    def __init__(self, page: QWidget) -> None:
        super().__init__(page)
        self.setObjectName("ambientBackground")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setScaledContents(True)
        blur = QGraphicsBlurEffect(self)
        blur.setBlurRadius(42)
        self.setGraphicsEffect(blur)
        self._ambient_opacity = 1.0
        self._animation = QPropertyAnimation(self, b"ambientOpacity", self)
        self._animation.setDuration(self._FADE_DURATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.finished.connect(self._on_fade_in_finished)
        self._ambient_source = QPixmap()
        self.setGeometry(page.rect())

    def pixmap(self) -> QPixmap:
        pixmap = super().pixmap()
        return pixmap if pixmap is not None else QPixmap()

    @property
    def ambient_opacity(self) -> float:
        return self._ambient_opacity

    def _get_ambient_opacity(self) -> float:
        return self._ambient_opacity

    def _set_ambient_opacity(self, value: float) -> None:
        self._ambient_opacity = min(1.0, max(0.0, value))
        self.update()

    ambientOpacity = Property(float, _get_ambient_opacity, _set_ambient_opacity)

    def paintEvent(self, event) -> None:
        pixmap = self.pixmap()
        if pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setOpacity(self._ambient_opacity)
        painter.drawPixmap(self.rect(), pixmap)

    def set_ambient_visible(self, visible: bool) -> None:
        if not visible:
            self._animation.stop()
            self._set_ambient_opacity(1.0)
            self.hide()
            return
        if self.pixmap().isNull():
            self.hide()
            return
        if self.isHidden():
            self._fade_in()
        else:
            self._request_repaint()

    def set_ambient_image(
        self,
        pixmap: QPixmap,
        visible: bool,
        changed: bool,
    ) -> None:
        was_animating = self._animation.state() == QPropertyAnimation.State.Running
        if pixmap.isNull():
            self._animation.stop()
            self.clear()
            self._set_ambient_opacity(1.0)
            self.hide()
            return
        current_pixmap = self.pixmap()
        if visible and was_animating and not changed:
            self.setPixmap(pixmap)
            self._request_repaint()
            return
        self._animation.stop()
        self.setPixmap(pixmap)
        if not visible:
            self._set_ambient_opacity(1.0)
            self.hide()
            return
        if current_pixmap.isNull() or self.isHidden():
            self._fade_in()
        else:
            self._set_ambient_opacity(1.0)
            self.show()
            self._request_repaint()

    def _fade_in(self) -> None:
        self._animation.stop()
        self._set_ambient_opacity(0.0)
        self.show()
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.start()

    def _on_fade_in_finished(self) -> None:
        self._set_ambient_opacity(1.0)
        self._request_repaint()

    def _request_repaint(self) -> None:
        self.update()


class FullscreenToolbar(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("fullscreenToolbar")

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1c1e28"))
        radius = self.height() / 2
        painter.drawRoundedRect(self.rect(), radius, radius)


class MainWindow(QMainWindow):
    _GWLP_HWNDPARENT = -8
    _GWL_STYLE = -16
    _GWL_EXSTYLE = -20
    _WS_MAXIMIZEBOX = 0x00010000
    _WS_THICKFRAME = 0x00040000
    _WS_EX_APPWINDOW = 0x00040000
    _WS_EX_TOOLWINDOW = 0x00000080
    _HTMAXBUTTON = 9
    _SWP_NOSIZE = 0x0001
    _SWP_NOMOVE = 0x0002
    _SWP_NOZORDER = 0x0004
    _SWP_NOACTIVATE = 0x0010
    _SWP_FRAMECHANGED = 0x0020

    def __init__(self) -> None:
        super().__init__()
        self.settings = AppSettings()
        self._suggestion_cache = SuggestionCache(self.settings)
        self._suggestion_refreshing: set[tuple[str, str]] = set()
        self._suggestion_request_keys: dict[str, tuple[str, str]] = {}
        self._ignore_search_popup_release = False
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(8)
        self.tasks = {}
        self._startup_update_task = None
        self._update_download_task = None
        self._update_notice_dialog = None
        self.request_id = 0
        self._search_suggestion_generation = 0
        self._search_suggestions_suppressed = True
        self._search_suggestion_query = ""
        self._search_suggestion_fragment = ""
        self._typo_search_query = ""
        self._typo_search_request_id = -1
        self._suggested_search_query = ""
        self._random_provider = "All"
        self._random_rating = "sfw"
        self._random_query = ""
        self._random_failed_preview_providers: set[str] = set()
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
        self.card_ai_badges: dict[str, QLabel] = {}
        self.card_frames: dict[str, QWidget] = {}
        self.active_detail_id = ""
        self.detail_post: ImagePost | None = None
        self._full_image_loaded = False
        self.favorites_dialog: FavoritesDialog | None = None
        self.favorites_dialog_token = ""
        self._favorites_catalog: BooruCatalog | None = None
        self.preferences_dialog: PreferencesDialog | None = None
        self._opening_favorite = False
        self._fullscreen_active = False
        self._was_maximized_before_fullscreen = False
        self._windowed_geometry = None
        self.card_buttons: dict[str, QPushButton] = {}
        self.current_theme = str(self.settings.get("appearance/theme", "Dark"))
        if self.current_theme not in THEME_NAMES:
            self.current_theme = "Dark"
        self._icon_cache: dict[tuple[str, str], QIcon] = {}
        self._icon_buttons: list[QPushButton] = []
        self.downloads = DownloadsDialog(self)
        self.downloads.cancel_requested.connect(self._cancel_download)
        self.downloads.retry_requested.connect(self._retry_download)
        self.downloads.retry_all_requested.connect(self._retry_failed_downloads)
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
        # Keep low-cost previews responsive, then do final-quality reflow on settle.
        self._resize_settle_timer = QTimer(self)
        self._resize_settle_timer.setSingleShot(True)
        self._resize_settle_timer.setInterval(180)
        self._resize_settle_timer.timeout.connect(self._finish_resize_settle)
        self._resize_in_progress = False
        self._resize_cursor_active = False
        self._gallery_notice_timer = QTimer(self)
        self._gallery_notice_timer.setSingleShot(True)
        self._gallery_notice_timer.setInterval(5000)
        self._gallery_notice_timer.timeout.connect(self._fade_out_gallery_notice)
        self._full_image_loading_dots = 0
        self._full_image_loading_timer = QTimer(self)
        self._full_image_loading_timer.setInterval(450)
        self._full_image_loading_timer.timeout.connect(
            self._update_full_image_loading_text
        )
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
        self._restore_window_size()
        QTimer.singleShot(0, self.show_random)
        QTimer.singleShot(0, self._check_for_startup_update)

    def _restore_window_size(self) -> None:
        size = self.settings.get("windows/main/size")
        if isinstance(size, QSize) and size.isValid():
            self.resize(size.expandedTo(self.minimumSize()))
        if self.settings.get_bool("windows/main/maximized", False):
            self.showMaximized()
        else:
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                x = available.x() + max(0, (available.width() - self.width()) // 2)
                y = available.y() + max(0, (available.height() - self.height()) // 2)
                self.move(x, y)

    def closeEvent(self, event) -> None:
        dialogs = list(self.findChildren(QDialog))
        for dialog in dialogs:
            if dialog.isVisible():
                dialog.close()
        if any(dialog.isVisible() for dialog in dialogs):
            event.ignore()
            return
        for task in self.tasks.values():
            if isinstance(task, FileDownloadTask):
                task.cancel()
        self.pool.clear()
        if self._fullscreen_active and self._windowed_geometry is not None:
            size = self._windowed_geometry.size()
        elif self.isMaximized():
            size = self.normalGeometry().size()
        else:
            size = self.size()
        if size.isValid():
            self.settings.set("windows/main/size", size)
        maximized = self.isMaximized() or (
            self._fullscreen_active and self._was_maximized_before_fullscreen
        )
        self.settings.set("windows/main/maximized", maximized)
        super().closeEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not getattr(self, "_initial_focus_set", False):
            self._initial_focus_set = True
            self.pages.setFocus(Qt.FocusReason.OtherFocusReason)
        QTimer.singleShot(0, self._enable_windows_snap)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            title_bar = getattr(self, "title_bar", None)
            if title_bar is not None:
                title_bar.refresh_icons()
            if not self.isFullScreen():
                QTimer.singleShot(0, self._enable_windows_snap)

    def _belongs_to_main_window(self, window: QWidget) -> bool:
        parent = window
        while parent is not None:
            if parent is self:
                return True
            parent = parent.parentWidget()
        return False

    def _raise_active_app_window(self, active_window: QWidget) -> None:
        if not active_window.isVisible() or not active_window.isActiveWindow():
            return
        if isinstance(active_window, QDialog) and not active_window.isModal():
            self._prepare_windows_dialog(active_window)
        active_window.raise_()
        self._raise_native_window(active_window)

    def _prepare_windows_dialog(self, dialog: QDialog) -> None:
        if (
            not self._uses_native_windows_api()
            or bool(dialog.property("_windowsTaskbarConfigured"))
        ):
            return
        self._detach_native_dialog_owner(dialog)
        self._show_dialog_in_taskbar(dialog)
        dialog.setProperty("_windowsTaskbarConfigured", True)

    def _show_modeless_dialog(self, dialog: QDialog) -> None:
        if self._uses_native_windows_api():
            dialog.winId()
            self._prepare_windows_dialog(dialog)
        window_state = dialog.windowState()
        if window_state & Qt.WindowState.WindowMinimized:
            dialog.setWindowState(
                window_state & ~Qt.WindowState.WindowMinimized
            )
        if not dialog.isVisible():
            dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._raise_native_window(dialog)

    @staticmethod
    def _uses_native_windows_api() -> bool:
        return os.name == "nt" and QApplication.platformName().casefold() == "windows"

    @staticmethod
    def _user32_window_functions():
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_window_long_ptr = getattr(
            user32, "GetWindowLongPtrW", user32.GetWindowLongW
        )
        set_window_long_ptr = getattr(
            user32, "SetWindowLongPtrW", user32.SetWindowLongW
        )
        get_window_long_ptr.argtypes = (wintypes.HWND, ctypes.c_int)
        get_window_long_ptr.restype = ctypes.c_ssize_t
        set_window_long_ptr.argtypes = (
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_ssize_t,
        )
        set_window_long_ptr.restype = ctypes.c_ssize_t
        user32.SetWindowPos.argtypes = (
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        )
        user32.SetWindowPos.restype = wintypes.BOOL
        return user32, get_window_long_ptr, set_window_long_ptr

    def _detach_native_dialog_owner(self, dialog: QDialog) -> None:
        handle = dialog.windowHandle()
        if handle is not None and handle.transientParent() is not None:
            handle.setTransientParent(None)
        if not self._uses_native_windows_api():
            return
        _, get_window_long_ptr, set_window_long_ptr = self._user32_window_functions()
        hwnd = wintypes.HWND(int(dialog.winId()))
        ctypes.set_last_error(0)
        owner = get_window_long_ptr(hwnd, self._GWLP_HWNDPARENT)
        if owner:
            ctypes.set_last_error(0)
            previous_owner = set_window_long_ptr(
                hwnd, self._GWLP_HWNDPARENT, 0
            )
            if not previous_owner and ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())

    def _show_dialog_in_taskbar(self, dialog: QDialog) -> None:
        if not self._uses_native_windows_api():
            return
        user32, get_window_long_ptr, set_window_long_ptr = self._user32_window_functions()
        hwnd = wintypes.HWND(int(dialog.winId()))
        extended_style = get_window_long_ptr(hwnd, self._GWL_EXSTYLE)
        taskbar_style = (
            extended_style | self._WS_EX_APPWINDOW
        ) & ~self._WS_EX_TOOLWINDOW
        if taskbar_style == extended_style:
            return
        ctypes.set_last_error(0)
        previous_style = set_window_long_ptr(
            hwnd, self._GWL_EXSTYLE, taskbar_style
        )
        if not previous_style and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        flags = (
            self._SWP_NOMOVE
            | self._SWP_NOSIZE
            | self._SWP_NOZORDER
            | self._SWP_NOACTIVATE
            | self._SWP_FRAMECHANGED
        )
        if not user32.SetWindowPos(hwnd, wintypes.HWND(0), 0, 0, 0, 0, flags):
            raise ctypes.WinError(ctypes.get_last_error())

    def _raise_native_window(self, window: QWidget) -> None:
        if not self._uses_native_windows_api():
            return
        user32, _, _ = self._user32_window_functions()
        flags = self._SWP_NOSIZE | self._SWP_NOMOVE | self._SWP_NOACTIVATE
        succeeded = user32.SetWindowPos(
            wintypes.HWND(int(window.winId())),
            wintypes.HWND(0),
            0,
            0,
            0,
            0,
            flags,
        )
        if not succeeded:
            raise ctypes.WinError(ctypes.get_last_error())

    def _enable_windows_snap(self) -> None:
        if not self._uses_native_windows_api() or self.isFullScreen():
            return
        user32, get_window_long_ptr, set_window_long_ptr = (
            self._user32_window_functions()
        )
        hwnd = wintypes.HWND(int(self.winId()))
        style = get_window_long_ptr(hwnd, self._GWL_STYLE)
        snap_style = style | self._WS_THICKFRAME | self._WS_MAXIMIZEBOX
        if snap_style == style:
            return
        ctypes.set_last_error(0)
        previous_style = set_window_long_ptr(
            hwnd, self._GWL_STYLE, snap_style
        )
        if not previous_style and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        flags = (
            self._SWP_NOMOVE
            | self._SWP_NOSIZE
            | self._SWP_NOZORDER
            | self._SWP_NOACTIVATE
            | self._SWP_FRAMECHANGED
        )
        if not user32.SetWindowPos(hwnd, wintypes.HWND(0), 0, 0, 0, 0, flags):
            raise ctypes.WinError(ctypes.get_last_error())

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        self._root_widget = root
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.title_bar = GalleryTitleBar(self)
        root_layout.addWidget(self.title_bar)
        self.search_suggestion_panel = QFrame(root)
        self.search_suggestion_panel.setObjectName("searchSuggestionPanel")
        suggestion_panel_layout = QVBoxLayout(self.search_suggestion_panel)
        suggestion_panel_layout.setContentsMargins(5, 5, 5, 5)
        suggestion_panel_layout.setSpacing(0)
        self._search_suggestion_view = QListView(self.search_suggestion_panel)
        self._search_suggestion_view.setObjectName("searchSuggestionList")
        self._search_suggestion_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._search_suggestion_view.setCursor(Qt.CursorShape.PointingHandCursor)
        self._search_suggestion_view.setMouseTracking(True)
        self._search_suggestion_view.setUniformItemSizes(True)
        self._search_suggestion_view.setIconSize(QSize(16, 16))
        self._search_suggestion_view.setItemDelegate(SearchSuggestionDelegate(self))
        self._search_suggestion_view.clicked.connect(
            lambda index: self._apply_search_completion(
                str(index.data(Qt.ItemDataRole.UserRole) or "")
            )
        )
        self._search_suggestion_viewport = self._search_suggestion_view.viewport()
        self._search_suggestion_viewport.installEventFilter(self)
        suggestion_panel_layout.addWidget(self._search_suggestion_view)
        self._search_suggestion_row = self.search_suggestion_panel
        self.search_suggestion_panel.hide()
        self.search_correction_button = QPushButton(root)
        self.search_correction_button.setObjectName("searchCorrectionNotice")
        self.search_correction_button.setFixedHeight(30)
        self.search_correction_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_correction_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.search_correction_button.setStyleSheet(
            "QPushButton#searchCorrectionNotice {"
            "text-align: left; color: #b8a4ff; background: transparent;"
            "border: 0; padding: 3px 14px; }"
            "QPushButton#searchCorrectionNotice:hover { text-decoration: underline; }"
        )
        self.search_correction_button.clicked.connect(self._apply_search_correction)
        self.search_correction_button.hide()
        root_layout.addWidget(self.search_correction_button)

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
        self.search_input.textEdited.connect(self._on_search_query_edited)
        self._search_suggestion_model = QStandardItemModel(self)
        self._search_completer = QCompleter(self._search_suggestion_model, self)
        self._search_completer.setCompletionRole(Qt.ItemDataRole.UserRole)
        self._search_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._search_completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        self._search_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self._search_completer.setMaxVisibleItems(8)
        self._search_completer.activated.connect(self._apply_search_completion)
        self._search_suggestion_view.setModel(self._search_suggestion_model)
        self._search_suggestion_timer = QTimer(self)
        self._search_suggestion_timer.setSingleShot(True)
        self._search_suggestion_timer.setInterval(300)
        self._search_suggestion_timer.timeout.connect(
            self._request_search_suggestions
        )
        self.selected_provider = str(self.settings.get("search/provider", "All"))
        if self.selected_provider not in ("All", "Danbooru", "yande.re", "Gelbooru", "Rule34.xxx"):
            self.selected_provider = "All"
        self.selected_rating = str(self.settings.get("search/rating", "sfw"))
        if self.selected_rating not in ("sfw", "nsfw", "all"):
            self.selected_rating = "sfw"
        self.selected_media = str(self.settings.get("search/media_filter", "image"))
        if self.selected_media not in ("image", "video", "png", "all"):
            self.selected_media = "image"
        self.settings_button = self._icon_button("menu", "More option")
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
        self.full_image_button.clicked.connect(
            lambda _checked=False: self.load_full_image()
        )
        self._build_filter_menu()
        self.refresh_button = self._icon_button("refresh-cw", "Refresh current view")
        self.download_button = self._icon_button("download", "Download current image")
        self.title_bar.add_action(self.refresh_button)
        self.title_bar.add_action(self.download_button)
        self.title_bar.add_action(self.settings_button)

        self.pages = QStackedWidget()
        self.pages.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.random_page = QWidget()
        self.random_page.setObjectName("randomPage")
        self.random_page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        random_layout = QVBoxLayout(self.random_page)
        random_layout.setContentsMargins(0, 0, 0, 0)
        random_layout.setSpacing(6)
        self.random_ambient = self._create_ambient_layer(self.random_page)
        self.random_scroll = QScrollArea()
        self.random_scroll.setWidgetResizable(False)
        self.random_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.random_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.random_scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.random_scroll.setAutoFillBackground(False)
        self.random_scroll.viewport().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )
        self.random_scroll.viewport().setAutoFillBackground(False)
        self.random_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.random_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.random_image = ZoomImage()
        self.random_image.setObjectName("randomImage")
        self.random_image.setMinimumSize(1, 1)
        self.random_scroll.setWidget(self.random_image)
        self.random_image.viewport = self.random_scroll.viewport()
        self.random_image.viewport.installEventFilter(self.random_image)
        self.random_image.scroll_area = self.random_scroll
        self.random_ai_badge = self._create_ai_badge(self.random_scroll.viewport())
        self.random_image.zoomChanged.connect(
            lambda zoomed, area=self.random_scroll, ambient=self.random_ambient, page=self.random_page:
            self._on_image_zoom_changed(area, ambient, page, zoomed)
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
        self.random_video_ai_badge = self._create_ai_badge(self.random_media_stack)
        random_layout.addWidget(self.random_media_stack, 1)
        self.random_video_fullscreen_button = self._icon_button("expand", "Fullscreen video")
        self.random_video.fullscreen_toggle = self.random_video_fullscreen_button
        self.random_video.add_control_action(self.random_video_fullscreen_button, index=5)
        self.random_video_fullscreen_button.clicked.connect(self._toggle_fullscreen)

        self.random_fullscreen_toolbar = FullscreenToolbar(self.random_page)
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
        for action, index in (
            (self.random_video_refresh_action, 0),
            (self.random_video_favorite_action, 1),
            (self.random_video_download_action, 2),
            (self.random_video_exit_action, 9),
        ):
            self.random_video.add_fullscreen_action(action, index)
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
        self.gallery_status.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
        self.page_navigation = QWidget()
        self.page_navigation.setObjectName("pageNavigation")
        self.page_navigation.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True
        )
        self.page_navigation.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )
        self.page_navigation.setMinimumHeight(34)
        page_nav = QHBoxLayout(self.page_navigation)
        page_nav.setContentsMargins(8, 3, 8, 3)
        page_nav.setSpacing(4)
        self.previous_button = self._icon_button("chevron-left", "Previous page")
        self.previous_button.setObjectName("pageNavigationButton")
        self.previous_button.setFixedSize(28, 28)
        self.page_label = QLabel("Page 1")
        self.page_label.setObjectName("pageNavigationLabel")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setMinimumSize(140, 28)
        self.next_button = self._icon_button("chevron-right", "Next page")
        self.next_button.setObjectName("pageNavigationButton")
        self.next_button.setFixedSize(28, 28)
        page_nav.addStretch(1)
        page_nav.addWidget(self.previous_button)
        page_nav.addWidget(self.page_label)
        page_nav.addWidget(self.next_button)
        page_nav.addStretch(1)
        self.pages.addWidget(self.gallery_page)

        self.detail_page = QWidget()
        self.detail_page.setObjectName("detailPage")
        self.detail_page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        detail_layout = QVBoxLayout(self.detail_page)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)
        self.detail_ambient = self._create_ambient_layer(self.detail_page)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(False)
        self.detail_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.detail_scroll.setAutoFillBackground(False)
        self.detail_scroll.viewport().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )
        self.detail_scroll.viewport().setAutoFillBackground(False)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_image = ZoomImage()
        self.detail_image.setObjectName("detailImage")
        self.detail_image.setMinimumSize(1, 1)
        self.detail_scroll.setWidget(self.detail_image)
        self.detail_image.viewport = self.detail_scroll.viewport()
        self.detail_image.viewport.installEventFilter(self.detail_image)
        self.detail_image.scroll_area = self.detail_scroll
        self.detail_ai_badge = self._create_ai_badge(self.detail_scroll.viewport())
        self.detail_image.zoomChanged.connect(
            lambda zoomed, area=self.detail_scroll, ambient=self.detail_ambient, page=self.detail_page:
            self._on_image_zoom_changed(area, ambient, page, zoomed)
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
        self.detail_video_ai_badge = self._create_ai_badge(self.detail_media_stack)
        self.detail_video_fullscreen_button = self._icon_button("expand", "Fullscreen video")
        self.detail_video.fullscreen_toggle = self.detail_video_fullscreen_button
        self.detail_video.add_control_action(self.detail_video_fullscreen_button, index=5)
        self.detail_video_fullscreen_button.clicked.connect(self._toggle_fullscreen)

        self.detail_previous_button = self._icon_button("chevron-left", "Previous image")
        self.detail_next_button = self._icon_button("chevron-right", "Next image")
        for button in (self.detail_previous_button, self.detail_next_button):
            button.setParent(self.detail_media_stack)
            button.setObjectName("detailNavigation")
            button.setFixedSize(42, 42)
            button.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
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
            button.setParent(self.detail_media_stack)
            button.setObjectName("detailNavigation")
            button.setFixedSize(42, 42)
            button.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
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

        self.fullscreen_toolbar = FullscreenToolbar(self.detail_page)
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
            self.fullscreen_exit_button,
            self.fullscreen_next_button,
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
        for action, index in (
            (self.detail_video_previous_action, 0),
            (self.detail_video_favorite_action, 1),
            (self.detail_video_download_action, 2),
            (self.detail_video_exit_action, 9),
            (self.detail_video_next_action, 11),
        ):
            self.detail_video.add_fullscreen_action(action, index)
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
        self.refresh_shortcut = QShortcut(QKeySequence(Qt.Key.Key_R), self)
        self.refresh_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.refresh_shortcut.activated.connect(self.refresh)
        self.previous_media_shortcut = QShortcut(
            QKeySequence(Qt.Key.Key_Left), self
        )
        self.next_media_shortcut = QShortcut(
            QKeySequence(Qt.Key.Key_Right), self
        )
        self._media_navigation_shortcuts = (
            self.previous_media_shortcut,
            self.next_media_shortcut,
        )
        for shortcut in self._media_navigation_shortcuts:
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.previous_media_shortcut.activated.connect(
            lambda: self._navigate_detail_media(-1)
        )
        self.next_media_shortcut.activated.connect(
            lambda: self._navigate_detail_media(1)
        )
        self.pages.currentChanged.connect(self._update_keyboard_shortcuts)
        self.pages.currentChanged.connect(self._suppress_search_suggestions_on_page_change)
        self._update_keyboard_shortcuts()
        content_layout.addWidget(self.pages, 1)
        body_layout.addWidget(content, 1)
        root_layout.addWidget(body, 1)

        self.setCentralWidget(root)
        status = QStatusBar()
        status.setObjectName("statusBar")
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        self.footer_widget = QWidget(status)
        footer_layout = QGridLayout(self.footer_widget)
        footer_layout.setContentsMargins(4, 0, 4, 0)
        footer_layout.setHorizontalSpacing(4)
        footer_layout.setVerticalSpacing(0)
        self.footer_meta = QLabel("")
        self.footer_meta.setObjectName("footerMeta")
        footer_layout.addWidget(
            self.footer_meta,
            0,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        footer_layout.addWidget(
            self.page_navigation, 0, 1, Qt.AlignmentFlag.AlignCenter
        )
        footer_actions = QWidget(self.footer_widget)
        footer_actions_layout = QHBoxLayout(footer_actions)
        footer_actions_layout.setContentsMargins(0, 0, 0, 0)
        footer_actions_layout.setSpacing(2)
        footer_actions_layout.addWidget(self.full_image_button)
        for button in (self.favorite_button, self.fullscreen_button):
            button.setFixedSize(34, 26)
            button.setIconSize(QSize(17, 17))
            footer_actions_layout.addWidget(button)
        footer_actions_layout.addWidget(QSizeGrip(self))
        footer_layout.addWidget(
            footer_actions,
            0,
            2,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        footer_layout.setColumnStretch(0, 1)
        footer_layout.setColumnStretch(2, 1)
        status.addPermanentWidget(self.footer_widget, 1)
        status.setMinimumHeight(status.minimumSizeHint().height())
        self.pages.currentChanged.connect(self._update_page_navigation_visibility)
        self._update_page_navigation_visibility()

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
            if name == "All":
                action.setToolTip("Search combines provider results; Random uses the first provider response.")
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

        self.media_actions = {}
        media_group = QActionGroup(menu)
        media_group.setExclusive(True)
        media_menu = menu.addMenu("Media Type")
        media_menu.setObjectName("mediaTypeMenu")
        media_menu.setMinimumWidth(132)
        media_menu.setMaximumWidth(150)
        for title, value in (("Image Only", "image"), ("Video Only", "video"), ("PNG Only", "png"), ("Show All", "all")):
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
        menu.addAction("Downloads", self.show_downloads)
        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self.open_preferences)
        menu.addSeparator()
        self.settings_button.setMenu(menu)
        self._update_filter_tooltip()

    def _update_filter_tooltip(self) -> None:
        self.settings_button.setToolTip("More option")
        self.settings_button.setAccessibleName("More option")

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
                    checksum=str(value.get("checksum") or value.get("dedupe_key", "")),
                    title=str(value.get("title", "")),
                    media_type=str(value.get("media_type", "image")),
                    width=int(value.get("width", 0) or 0),
                    height=int(value.get("height", 0) or 0),
                    video_variants=tuple(
                        (str(item[0]), int(item[1] or 0), int(item[2] or 0))
                        for item in value.get("video_variants", [])
                        if isinstance(item, (list, tuple)) and len(item) == 3
                    ),
                    sample_url=str(value.get("sample_url", "")),
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
            "sample_url": post.sample_url,
        } for post in posts])

    @staticmethod
    def _image_size_text(
        post: ImagePost,
        pixmap: QPixmap,
        *,
        full: bool = False,
        auto_load: bool = False,
    ) -> str:
        displayed = f"{pixmap.width()} x {pixmap.height()}"
        if full:
            return displayed
        if not auto_load:
            return f"Preview {displayed}"
        if not post.width or not post.height:
            return f"Preview {displayed} | Load full size..."
        original = f"{post.width} x {post.height}"
        if displayed == original:
            return f"Preview {displayed}"
        return f"Preview {displayed} | Load full size..."

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
        if self._full_image_loaded:
            self._stop_full_image_loading_animation()
        image_size = self._image_size_text(
            post,
            pixmap,
            full=self._full_image_loaded,
            auto_load=self.settings.get_bool("view/auto_load_full_image", False),
        )
        self.footer_meta.setText(
            f"{post.provider} | {rating_label(post.rating)} | {image_size}"
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
        if self._full_image_loaded:
            self._stop_full_image_loading_animation()
        image_size = self._image_size_text(
            post,
            pixmap,
            full=self._full_image_loaded,
            auto_load=self.settings.get_bool("view/auto_load_full_image", False),
        )
        self.footer_meta.setText(
            f"{post.provider} | {rating_label(post.rating)} | {image_size}"
        )

    @staticmethod
    def _create_ai_badge(parent: QWidget) -> QLabel:
        badge = QLabel("AI", parent)
        badge.setObjectName("aiGeneratedBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        badge.setAccessibleName("AI-generated image")
        badge.setToolTip("Provider tagged this image as AI-generated or AI-assisted.")
        badge.setStyleSheet(
            "QLabel#aiGeneratedBadge {"
            "background: rgba(18, 20, 28, 220); color: #ffffff;"
            "border: 1px solid rgba(255, 255, 255, 90); border-radius: 9px;"
            "padding: 3px 8px; font-size: 11px; font-weight: 700;"
            "}"
        )
        badge.adjustSize()
        badge.hide()
        return badge

    @staticmethod
    def _is_ai_tagged_post(post: ImagePost | None) -> bool:
        return bool(
            post
            and post.tags.intersection(AI_GENERATED_BLOCK_TAGS)
        )

    @staticmethod
    def _position_corner_badge(badge: QLabel) -> None:
        parent = badge.parentWidget()
        if parent is None:
            return
        badge.adjustSize()
        margin = 12
        badge.move(
            max(margin, parent.width() - badge.width() - margin),
            max(margin, parent.height() - badge.height() - margin),
        )
        badge.raise_()

    def _update_media_ai_badge(self, badge: QLabel, post: ImagePost | None) -> None:
        visible = self._is_ai_tagged_post(post)
        badge.setVisible(visible)
        if visible:
            self._position_corner_badge(badge)

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
            source_url = next(
                (url for url in existing.preview_urls if url != existing.image_url),
                existing.image_url,
            )
            remove_favorite_thumbnail(key, source_url)
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
            self._show_modeless_dialog(self.favorites_dialog)
            return
        if self.settings.get_bool("favorites_lock/enabled"):
            if not has_pin(self.settings, "favorites_lock"):
                BackupMessageDialog.notify(
                    self,
                    "Favorites locked",
                    "The Favorites PIN is unavailable. Reset it from Safety & Privacy.",
                )
                return
            pin_dialog = PinPromptDialog(
                title="Unlock Favorites",
                description="Enter your Favorites PIN to continue.",
                verify_current=lambda value: verify_pin(
                    self.settings, "favorites_lock", value
                ),
                parent=self,
            )
            if pin_dialog.exec() != QDialog.DialogCode.Accepted:
                return
        posts = [post for post in self._favorite_posts() if self._parent_allows_post(post)]
        token = str(uuid4())
        dialog = FavoritesDialog(
            posts,
            self._open_favorite,
            self._remove_favorite,
            self,
            sort_order=str(self.settings.get("favorites/sort_order", "newest")),
            media_filter=str(self.settings.get("favorites/media_filter", "all")),
        )
        self.favorites_dialog = dialog
        self.favorites_dialog_token = token
        self._favorites_catalog = None
        dialog.downloadRequested.connect(self._download_favorite)
        dialog.deleteSelectedRequested.connect(self._remove_favorites)
        dialog.downloadSelectedRequested.connect(self._download_selected_favorites)
        dialog.sortOrderChanged.connect(
            lambda value: self.settings.set("favorites/sort_order", value)
        )
        dialog.mediaFilterChanged.connect(
            lambda value: self.settings.set("favorites/media_filter", value)
        )
        dialog.thumbnailRequested.connect(
            lambda favorite_id, current=token: self._request_favorite_thumbnail(
                current, favorite_id
            )
        )
        dialog.finished.connect(lambda _result, current=token: self._clear_favorites_dialog(current))
        for post in posts:
            key = favorite_key(post)
            cached = self.thumbnail_cache.get(post.post_id)
            if cached:
                dialog.set_thumbnail(key, cached)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._show_modeless_dialog(dialog)

    def show_downloads(self) -> None:
        self._show_modeless_dialog(self.downloads)

    def _clear_favorites_dialog(self, token: str) -> None:
        if self.favorites_dialog_token == token:
            self.favorites_dialog = None
            self.favorites_dialog_token = ""
            self._favorites_catalog = None

    def _refresh_favorites_dialog(self, posts: list[ImagePost]) -> None:
        posts = [post for post in posts if self._parent_allows_post(post)]
        self._favorite_navigation_posts = list(posts)
        dialog = self.favorites_dialog
        if dialog:
            keys = {favorite_key(post) for post in posts}
            dialog.thumbnail_cache = {
                key: pixmap for key, pixmap in dialog.thumbnail_cache.items() if key in keys
            }
            dialog.thumbnail_errors.intersection_update(keys)
            dialog.thumbnail_error_details = {
                key: details
                for key, details in dialog.thumbnail_error_details.items()
                if key in keys
            }
            dialog.set_posts(posts)
            self._favorite_navigation_posts = list(dialog.posts)
            for post in posts:
                key = favorite_key(post)
                cached = self.thumbnail_cache.get(post.post_id)
                if cached:
                    dialog.set_thumbnail(key, cached)
        self._sync_favorite_buttons()
        if self.detail_origin == "favorites":
            self._update_detail_navigation()

    def _request_favorite_thumbnail(self, token: str, favorite_id: str) -> None:
        dialog = self.favorites_dialog
        if token != self.favorites_dialog_token or dialog is None:
            return
        if favorite_id in dialog.thumbnail_cache or favorite_id in dialog.thumbnail_errors:
            return
        post = next(
            (item for item in dialog.posts if favorite_key(item) == favorite_id),
            None,
        )
        if post is None:
            return
        cached = self.thumbnail_cache.get(post.post_id)
        if cached:
            dialog.set_thumbnail(favorite_id, cached)
            return
        cache_enabled = self.settings.get_bool("favorites/image_cache_enabled", True)
        task_key = f"favorite-thumbnail:{token}/{favorite_id}"
        if task_key in self.tasks:
            return
        if self._favorites_catalog is None:
            self._favorites_catalog = self._catalog()
        catalog = self._favorites_catalog
        self._submit(
            task_key,
            self._fetch_decoded_favorite_thumbnail,
            post,
            catalog,
            cache_enabled,
        )

    def _remove_favorite(self, key: str) -> None:
        self._remove_favorites([key])

    def _remove_favorites(self, keys: list[str]) -> None:
        selected = set(keys)
        if not selected:
            return
        current_posts = self._favorite_posts()
        for post in current_posts:
            if favorite_key(post) in selected:
                source_url = next(
                    (url for url in post.preview_urls if url != post.image_url),
                    post.image_url,
                )
                remove_favorite_thumbnail(favorite_key(post), source_url)
        posts = [
            post for post in current_posts
            if favorite_key(post) not in selected
        ]
        if len(posts) == len(current_posts):
            return
        self._save_favorite_posts(posts)
        if self.favorites_dialog:
            self._refresh_favorites_dialog(posts)
        else:
            self._favorite_navigation_posts = [
                post for post in self._favorite_navigation_posts
                if favorite_key(post) not in selected
            ]
            self._sync_favorite_buttons()
            if self.detail_origin == "favorites":
                self._update_detail_navigation()

    def _download_favorite(self, key: str) -> None:
        post = next(
            (item for item in self._favorite_posts() if favorite_key(item) == key),
            None,
        )
        if post is not None:
            self._queue_favorite_downloads([post])

    def _download_selected_favorites(self, keys: list[str]) -> None:
        selected = set(keys)
        posts = [
            post for post in self._favorite_posts()
            if favorite_key(post) in selected
        ]
        self._queue_favorite_downloads(posts)

    def _queue_favorite_downloads(self, posts: list[ImagePost]) -> None:
        queued_paths = {
            os.path.normcase(os.path.abspath(os.fspath(task.destination)))
            for task in self.tasks.values()
            if isinstance(task, FileDownloadTask)
        }
        scheduled_paths = set(queued_paths)
        seen_favorites = set()
        queued = 0
        skipped = 0
        blocked = 0
        catalog = None
        for post in posts:
            favorite_id = favorite_key(post)
            if favorite_id in seen_favorites:
                continue
            seen_favorites.add(favorite_id)
            if not self._parent_allows_post(post):
                blocked += 1
                continue
            path = self._default_download_path(post)
            path_key = os.path.normcase(os.path.abspath(os.fspath(path)))
            if path.exists() or path_key in scheduled_paths:
                skipped += 1
                continue
            if catalog is None:
                catalog = self._catalog()
            self._start_download(post, path, catalog)
            scheduled_paths.add(path_key)
            queued += 1

        self.statusBar().showMessage(
            f"Queued {queued} favorite downloads; skipped {skipped} existing or queued files"
            + (f"; blocked {blocked} by parental controls." if blocked else "."),
            7000,
        )

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
        self._bring_main_window_to_front()

    def _bring_main_window_to_front(self) -> None:
        window_state = self.windowState()
        if window_state & Qt.WindowState.WindowMinimized:
            self.setWindowState(window_state & ~Qt.WindowState.WindowMinimized)
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
        self._raise_native_window(self)

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
        if theme not in THEME_NAMES:
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

    def _apply_theme(self, theme: str | None = None) -> None:
        theme = theme or self.current_theme
        if theme not in THEME_NAMES:
            theme = "Dark"
        if theme == "System":
            system_window = QApplication.palette().color(QPalette.ColorRole.Window)
            theme = "Dark" if system_window.lightness() < 128 else "Light"

        palette = dict(THEME_PALETTES[theme])
        content_surface = palette["BG"]
        title_surface = palette["SIDEBAR"]
        status_surface = palette["SIDEBAR"]

        stylesheet = """
            * { font-family: "Inter", "Segoe UI", sans-serif; font-size: 10pt; }
            QMainWindow { background: transparent; border: 1px solid __BORDER__; border-radius: 12px; }
            QDialog { background: __BG__; color: __TEXT__; }
            QWidget#appRoot { background: __BG__; color: __TEXT__; }
            QWidget#contentArea { background: __CONTENT_SURFACE__; color: __TEXT__; }
            QDialog#settingsDialog { background: transparent; border: 0; }
            QDialog#pinPromptDialog { background: transparent; border: 0; }
            QWidget#pinPromptSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 12px; }
            QLineEdit#pinPromptCurrent, QLineEdit#pinPromptNew, QLineEdit#pinPromptConfirm { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; border-radius: 14px; padding: 8px 12px; }
            QLabel#pinPromptError { color: #F7768E; }
            QWidget#settingsSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 18px; }
            QDialog#backupPromptDialog { background: transparent; border: 0; }
            QWidget#backupPromptSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 12px; }
            QLineEdit#backupPassphrase, QLineEdit#backupPassphraseConfirm { background: __PANEL__; color: __TEXT__; border: 1px solid __BORDER__; border-radius: 14px; padding: 8px 12px; }
            QLabel#backupPromptError { color: #F7768E; }
            QPushButton#backupDestructiveButton { color: #F7768E; }
            QWidget#settingsPage QFrame#backupNotice, QWidget#settingsPage QFrame#backupActionCard { background: __SIDEBAR__; border: 1px solid __BORDER__; border-radius: 12px; }
            QDialog#favoritesDialog { background: transparent; border: 0; }
            QWidget#favoritesSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 12px; }
            QLabel#favoritesCountLabel { color: __MUTED__; padding-left: 4px; }
            QWidget#favoritesTitleBar { background: __SIDEBAR__; border-bottom: 1px solid __BORDER__; border-top-left-radius: 12px; border-top-right-radius: 12px; }
            QDialog#downloadsDialog, QDialog#releaseNotesDialog { background: transparent; border: 0; }
            QWidget#downloadsSurface, QWidget#releaseNotesSurface { background: __BG__; border: 1px solid __BORDER__; border-radius: 12px; }
            QWidget#dialogTitleBar { background: __SIDEBAR__; border-bottom: 1px solid __BORDER__; border-top-left-radius: 12px; border-top-right-radius: 12px; }
            QLabel#downloadsWindowTitle { color: __STRONG__; font-size: 11pt; font-weight: 650; }
            QPushButton#dialogMinimizeButton { background: transparent; border: 0; border-radius: 15px; padding: 0; }
            QPushButton#dialogMinimizeButton:hover { background: __HOVER__; }
            QPushButton#downloadsCloseButton { background: transparent; border: 0; border-radius: 15px; padding: 0; }
            QPushButton#downloadsCloseButton:hover { background: #F7768E; }
            QListWidget#downloadsList { background: transparent; border: 0; outline: 0; }
            QListWidget#downloadsList::item, QListWidget#downloadsList::item:selected { background: transparent; border: 0; padding: 0; }
            QWidget#downloadItemRow { background: transparent; border-bottom: 1px solid __BORDER__; }
            QLabel#downloadItemIcon { background: transparent; }
            QLabel#downloadFilename { color: __ACCENT__; font-size: 10pt; font-weight: 500; }
            QLabel#downloadStatus { color: __MUTED__; font-size: 9pt; }
            QProgressBar#downloadProgress, QProgressBar#releaseDownloadProgress { background: __PANEL__; border: 0; border-radius: 2px; }
            QProgressBar#downloadProgress::chunk, QProgressBar#releaseDownloadProgress::chunk { background: __ACCENT__; border-radius: 2px; }
            QPushButton#downloadCancelButton, QPushButton#downloadOpenFolderButton, QPushButton#downloadRetryButton { background: transparent; border: 0; border-radius: 8px; padding: 2px; }
            QPushButton#downloadCancelButton:hover, QPushButton#downloadOpenFolderButton:hover, QPushButton#downloadRetryButton:hover { background: __ACTIVE__; }
            QPushButton#downloadCancelButton:disabled { background: transparent; }
            QToolButton#downloadsMenuButton { min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; background: transparent; border: 0; border-radius: 8px; padding: 0; }
            QToolButton#downloadsMenuButton:hover { background: __ACTIVE__; color: __STRONG__; }
            QLabel#releaseNotesHeading { color: __STRONG__; font-size: 15pt; font-weight: 700; }
            QLabel#releaseNotesVersion { color: __MUTED__; }
            QLabel#favoritesWindowTitle { color: __STRONG__; font-size: 11pt; font-weight: 650; }
            QPushButton#favoritesSelectAllButton, QPushButton#favoritesDeleteSelectedButton, QPushButton#favoritesDownloadSelectedButton { background: transparent; border: 0; border-radius: 15px; padding: 0; }
            QPushButton#favoritesSelectAllButton:hover, QPushButton#favoritesDeleteSelectedButton:hover, QPushButton#favoritesDownloadSelectedButton:hover { background: __HOVER__; }
            QPushButton#favoritesSelectAllButton:checked { background: __ACTIVE__; border: 1px solid __ACCENT__; }
            QPushButton#favoritesCloseButton { background: transparent; border: 0; border-radius: 15px; padding: 0; }
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
            QWidget#settingsPage QPushButton#themePreviewCard { text-align: left; background: __PANEL__; border: 1px solid __BORDER__; border-radius: 10px; padding: 2px; }
            QWidget#settingsPage QPushButton#themePreviewCard:hover { border-color: __ACCENT__; }
            QWidget#settingsPage QPushButton#themePreviewCard:checked { border: 1px solid __ACCENT__; }
            QLineEdit#parentAllowedTags, QComboBox#parentMaxRating { padding: 5px 10px; }
            QWidget#customTermRow { background: transparent; border: 0; }
            QPushButton#removeCustomTermButton { background: transparent; border: 0; border-radius: 14px; padding: 0; }
            QPushButton#removeCustomTermButton:hover { background: #4A3042; }
            QPushButton#settingsNavButton { text-align: left; background: transparent; border: 0; border-radius: 10px; padding: 9px 11px; }
            QPushButton#settingsNavButton:hover { background: __HOVER__; }
            QPushButton#settingsNavButton:checked { background: __MENU_SELECTED__; color: __STRONG__; }
            QWidget#appRoot { border-radius: 12px; }
            QWidget#titleBar { background: __TITLE_SURFACE__; border-bottom: 1px solid __BORDER__; border-top-left-radius: 12px; border-top-right-radius: 12px; }
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
            QCheckBox#settingsSafetyToggle { spacing: 0; padding: 0; background: transparent; border: 0; }
            QComboBox { padding-right: 28px; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 26px; border: 0; }
            QComboBox QAbstractItemView { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; selection-background-color: __ACTIVE__; outline: 0; padding: 4px; }
            QFrame#searchSuggestionPanel { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; border-radius: 12px; }
            QListView#searchSuggestionList { background: transparent; color: __STRONG__; border: 0; padding: 0; outline: 0; }
            QListView#searchSuggestionList::item { padding: 6px 10px; border-radius: 7px; }
            QListView#searchSuggestionList::item:hover { background: __HOVER__; color: __STRONG__; }
            QListView#searchSuggestionList::item:selected { background: __ACTIVE__; color: __STRONG__; }
            QPushButton { background: __PANEL__; color: __TEXT__; border: 1px solid __BORDER__; border-radius: 14px; padding: 8px 12px; }
            QPushButton:hover { background: __HOVER__; border-color: __MUTED__; color: __STRONG__; }
            QPushButton:pressed { background: __PRESSED__; }
            QPushButton:disabled { background: __DISABLED__; color: __MUTED__; border-color: __BORDER__; }
            QPushButton[iconAction="true"] { background: transparent; border: 0; padding: 0; }
            QPushButton[iconAction="true"]:hover { background: __HOVER__; }
            QPushButton#action_menu::menu-indicator { image: none; width: 0; }
            QPushButton#action_search { background: __BLUE__; border-color: __BLUE__; color: __BG__; }
            QPushButton#action_search:hover { background: __ACCENT__; border-color: __ACCENT__; }
            QPushButton#closeWindowButton { border-radius: 17px; }
            QPushButton#closeWindowButton:hover { background: #F7768E; border-color: #F7768E; }
            QMenu { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; padding: 5px; }
            QMenu#mediaTypeMenu { min-width: 132px; }
            QMenu::item { padding: 7px 24px 7px 10px; border-radius: 5px; }
            QMenu::item:selected { background: __MENU_SELECTED__; }
            QMenu::separator { height: 1px; background: __BORDER__; margin: 5px 4px; }
            QToolTip { background: __PANEL__; color: __STRONG__; border: 1px solid __BORDER__; border-radius: 8px; padding: 5px 8px; }
            QGroupBox { background: __PANEL__; border: 1px solid __BORDER__; border-radius: 14px; margin-top: 12px; padding: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: __STRONG__; }
            QListWidget::item { padding: 7px 8px; border-radius: 7px; }
            QListWidget::item:selected { background: __ACTIVE__; color: __STRONG__; }
            QListWidget::item:focus { outline: 0; border: 0; }
            QSlider::groove:horizontal { height: 5px; background: __BORDER__; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; margin: -5px 0; border-radius: 7px; background: __ACCENT__; }
            QStatusBar#statusBar { background: __STATUS_SURFACE__; color: __MUTED__; border: 0; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }
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
            QWidget#randomPage[ambientBackgroundVisible="true"],
            QWidget#detailPage[ambientBackgroundVisible="true"] { background: #000000; border: 0; }
            QLabel#randomImage, QLabel#detailImage { background: transparent; border: 0; }
            QFrame#fullscreenToolbar { background: transparent; border: 0; }
            QPushButton#detailNavigation, QPushButton#detailNavigation:hover,
            QPushButton#detailNavigation:pressed, QPushButton#detailNavigation:focus,
            QPushButton#detailNavigation:disabled { background: transparent; border: 0; border-radius: 0; padding: 0; }
            QPushButton#detailNavigation { color: __TEXT__; }
            QPushButton#detailNavigation:disabled { color: __MUTED__; }
            QPushButton#detailNavigation:hover, QPushButton#detailNavigation:pressed { color: __STRONG__; }
            QWidget#pageNavigation { background: rgba(24, 26, 34, 220); border: 1px solid rgba(255, 255, 255, 48); border-radius: 17px; }
            QLabel#pageNavigationLabel { background: transparent; color: __TEXT__; padding: 0 6px; }
            QPushButton#pageNavigationButton, QPushButton#pageNavigationButton:hover,
            QPushButton#pageNavigationButton:pressed, QPushButton#pageNavigationButton:focus,
            QPushButton#pageNavigationButton:disabled { background: transparent; border: 0; border-radius: 0; padding: 0; }
            QPushButton#pageNavigationButton { color: __TEXT__; }
            QPushButton#pageNavigationButton:disabled { color: __MUTED__; }
            QPushButton#pageNavigationButton:hover, QPushButton#pageNavigationButton:pressed { color: __STRONG__; }
            QFrame#fullscreenToolbar QPushButton:hover { background: transparent; color: __STRONG__; }
            QWidget#galleryContent { background: __BG__; }
            QPushButton#previewImage { background: transparent; border: 0; border-radius: 0; padding: 0; color: __MUTED__; }
            QPushButton#previewImage:hover { background: transparent; }
            QPushButton#previewImage[favoritesThumbnailPending="true"] { background: rgba(255, 255, 255, 14); border-radius: 6px; }
            QPushButton#previewImage[favoritesThumbnailPending="true"] { background: rgba(255, 255, 255, 14); border-radius: 6px; }
            QPushButton#favoriteRemoveButton { background: transparent; border: 0; border-radius: 8px; padding: 0; }
            QPushButton#favoriteRemoveButton:hover { background: __HOVER__; }
        """
        for token, color in palette.items():
            stylesheet = stylesheet.replace(f"__{token}__", color)
        stylesheet = stylesheet.replace("__CONTENT_SURFACE__", content_surface)
        stylesheet = stylesheet.replace("__TITLE_SURFACE__", title_surface)
        stylesheet = stylesheet.replace("__STATUS_SURFACE__", status_surface)
        checkmark = str(Path(__file__).resolve().parent.parent / "assets" / "check.svg").replace("\\", "/")
        stylesheet = stylesheet.replace("__CHECKMARK__", checkmark)
        self.setStyleSheet(stylesheet)
        suggestion_panel = getattr(self, "search_suggestion_panel", None)
        if suggestion_panel is not None:
            suggestion_panel.setStyleSheet(
                "QFrame#searchSuggestionPanel {"
                f"background-color: {palette['PANEL']}; color: {palette['STRONG']}; "
                f"border: 1px solid {palette['BORDER']}; border-radius: 12px; }}"
                "QListView#searchSuggestionList {"
                "background: transparent; border: 0; padding: 0; outline: 0; "
                f"color: {palette['STRONG']}; selection-background-color: {palette['ACTIVE']}; "
                f"selection-color: {palette['STRONG']}; }} "
                "QListView#searchSuggestionList::item {padding: 6px 10px; border-radius: 7px;}"
                f"QListView#searchSuggestionList::item:hover {{background: {palette['HOVER']}; color: {palette['STRONG']};}}"
            )
        for player in (
            getattr(self, "random_video", None),
            getattr(self, "detail_video", None),
        ):
            if player is not None:
                player.set_accent_color(palette["ACCENT"])
        if hasattr(self, "random_ambient"):
            self._refresh_ambient_layers()

    def _catalog(self) -> BooruCatalog:
        parent_enabled = self.settings.get_bool("parent/enabled")
        allowed_tags = self.settings.get("parent/allowed_tags", []) if parent_enabled else []
        if isinstance(allowed_tags, str):
            allowed_tags = allowed_tags.split(",")
        return BooruCatalog(
            self.settings.gelbooru_credentials,
            self.settings.get_bool("search/exclude_male", True),
            self.settings.use_doh,
            self.settings.rule34_credentials,
            self.settings.get_bool("search/filter_gore", True),
            tuple(self.settings.get("search/custom_block_tags", []) or []),
            str(self.settings.get("search/media_filter", "image")),
            self.settings.doh_endpoint,
            str(self.settings.get("parent/max_rating", "s")) if parent_enabled else None,
            tuple(map(str, allowed_tags)) if isinstance(allowed_tags, (list, tuple)) else (),
            self.settings.get_bool("search/filter_ai_generated", False),
            nsfw_rating=str(self.settings.get("search/nsfw_rating", "q_e")),
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
        if allowed_tags:
            normalized = {
                str(value).strip().casefold().replace(" ", "_")
                for value in allowed_tags
                if str(value).strip()
            }
            if not normalized or not post.tags.intersection(normalized):
                return False
        return True

    @staticmethod
    def _create_ambient_layer(page: QWidget) -> AmbientLayer:
        label = AmbientLayer(page)
        label.lower()
        return label

    def _set_ambient_image(
        self, label: AmbientLayer, pixmap: QPixmap, page: QWidget, *, fast: bool = False
    ) -> None:
        previous_source = getattr(label, "_ambient_source", QPixmap())
        changed = previous_source.cacheKey() != pixmap.cacheKey()
        if pixmap.isNull():
            label._ambient_source = QPixmap()
            self._set_ambient_page_background(page, False)
            label.set_ambient_image(
                QPixmap(),
                visible=False,
                changed=changed,
            )
            return
        label._ambient_source = pixmap
        size = page.size().expandedTo(QSize(1, 1))
        # Fill the ambient layer without distorting the artwork. Cropping the
        # overflow is preferable to leaving bars or stretching the image.
        scaled = pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.FastTransformation
            if fast
            else Qt.TransformationMode.SmoothTransformation,
        )
        crop_x = max(0, (scaled.width() - size.width()) // 2)
        crop_y = max(0, (scaled.height() - size.height()) // 2)
        background = scaled.copy(crop_x, crop_y, size.width(), size.height())
        tinted = QPixmap(background.size())
        tinted.fill(QColor(0, 0, 0))
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, background)
        painter.fillRect(tinted.rect(), QColor(0, 0, 0, 150))
        painter.end()
        label.setGeometry(page.rect())
        enabled = self._ambient_mode_enabled()
        self._set_ambient_page_background(page, enabled)
        label.set_ambient_image(tinted, visible=enabled, changed=changed)
        label.lower()

    @staticmethod
    def _set_ambient_page_background(page: QWidget, visible: bool) -> None:
        if page.property("ambientBackgroundVisible") == visible:
            return
        page.setProperty("ambientBackgroundVisible", visible)
        style = page.style()
        style.unpolish(page)
        style.polish(page)
        page.update()

    @staticmethod
    def _set_ambient_visibility(label: AmbientLayer, page: QWidget, visible: bool) -> None:
        MainWindow._set_ambient_page_background(page, visible)
        label.set_ambient_visible(visible)

    def _ambient_mode_enabled(self) -> bool:
        return self.settings.ambient_mode

    def _apply_ambient_mode(self) -> None:
        enabled = self._ambient_mode_enabled()
        for label, page in ((self.random_ambient, self.random_page), (self.detail_ambient, self.detail_page)):
            label.setGeometry(page.rect())
            has_image = not label._ambient_source.isNull()
            self._set_ambient_visibility(label, page, enabled and has_image)
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
                self._set_ambient_visibility(label, page, False)
            label.lower()
            page.update()
        self.random_video._reflow()
        self.detail_video._reflow()
        self._position_detail_video_navigation()

    def _refresh_ambient_for_page(self, page: QWidget, *, fast: bool = False) -> None:
        if page is self.random_page:
            label = self.random_ambient
        elif page is self.detail_page:
            label = self.detail_ambient
        else:
            return
        source = getattr(label, "_ambient_source", QPixmap())
        if not source.isNull():
            self._set_ambient_image(label, source, page, fast=fast)

    def _hide_ambient_during_resize(self) -> None:
        if not hasattr(self, "pages"):
            return
        page = self.pages.currentWidget()
        if page is self.random_page:
            self.random_ambient.hide()
        elif page is self.detail_page:
            self.detail_ambient.hide()

    def _on_image_zoom_changed(
        self,
        scroll_area: QScrollArea,
        ambient: AmbientLayer,
        page: QWidget,
        zoomed: bool,
    ) -> None:
        """Keep zoom panning available without showing native scrollbars."""
        self._set_zoom_scrollbars(scroll_area, zoomed)
        if not zoomed:
            has_image = not ambient._ambient_source.isNull()
            self._set_ambient_visibility(
                ambient,
                page,
                self._ambient_mode_enabled() and has_image,
            )
            ambient.lower()

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

    def _retry_download(self, download_key: str) -> None:
        retry = self.downloads.retryable_download(download_key)
        if retry is not None:
            post, path = retry
            self._start_download(post, path, download_key=download_key)

    def _retry_failed_downloads(self) -> None:
        for download_key, post, path in self.downloads.retryable_downloads():
            self._start_download(post, path, download_key=download_key)

    def _task_cancelled(self, download_key: str) -> None:
        self.tasks.pop(f"download:{download_key}", None)
        self.downloads.update_download(download_key, "Cancelled")

    def _task_succeeded(self, key: str, result) -> None:
        task = self.tasks.pop(key, None)
        category, _, identifier = key.partition(":")
        if category == "tag-suggestions":
            cache_key = self._suggestion_request_keys.pop(key, None)
            if cache_key is not None:
                self._suggestion_refreshing.discard(cache_key)
                self._suggestion_cache.set(cache_key[0], cache_key[1], result)
            if (
                (
                    int(identifier) == self._search_suggestion_generation
                    or cache_key == (
                        self.selected_provider.casefold(),
                        self._search_suggestion_fragment.casefold(),
                    )
                )
                and self.search_input.text().strip() == self._search_suggestion_query
            ):
                self._refresh_search_completion_model(
                    self._search_suggestion_query, result
                )
                if self.search_input.hasFocus():
                    self._show_search_completion_popup()
        elif category == "tag-correction":
            if (
                int(identifier) == self._typo_search_request_id == self.request_id
                and self.current_query == self._typo_search_query
                and self.search_input.text().strip() == self._typo_search_query
                and self.pages.currentWidget() is self.gallery_page
                and not self.posts
            ):
                self._show_tag_correction(self._typo_search_query, result)
        elif category == "search" and int(identifier) == self.request_id:
            self._show_search_results(result)
        elif category in {"random", "random-fallback"} and int(identifier) == self.request_id:
            self.random_post = result
            self.random_content = None
            self._update_image_credits(self.random_post)
            if self.random_post.media_type == "video":
                self._show_random_video(self.random_post)
            else:
                self._submit(
                    f"random-preview:{identifier}",
                    self._catalog().fetch_post_preview,
                    self.random_post,
                    progress_callback=self._update_load_progress,
                )
            self._sync_favorite_buttons()
        elif category == "random-preview" and int(identifier) == self.request_id:
            self.random_content = result
            self._submit(f"random-image:{identifier}", decode_image_bytes, result)
        elif category == "random-image" and int(identifier) == self.request_id:
            self._show_random_image(QPixmap.fromImage(result))
        elif category == "post-detail" and identifier == self.active_detail_id:
            pixmap = QPixmap.fromImage(result)
            auto_load_full_image = False
            if not pixmap.isNull():
                self._full_image_loaded = False
                self.detail_media_stack.setCurrentWidget(self.detail_scroll)
                self.detail_video.clear()
                self.detail_image.set_image(pixmap)
                self._update_media_ai_badge(self.detail_ai_badge, self.detail_post)
                self._full_image_loaded = False
                self._set_image_credits_visible(True)
                self._set_ambient_image(self.detail_ambient, pixmap, self.detail_page)
                self.fullscreen_button.setVisible(not self._fullscreen_active)
                self._sync_favorite_buttons()
                self._set_detail_image_footer(self.detail_post, pixmap)
                self.full_image_button.setToolTip("Load original-resolution image")
                self.full_image_button.setEnabled(True)
                auto_load_full_image = self.settings.get_bool(
                    "view/auto_load_full_image", False
                )
                self._sync_full_image_button_visibility()
            else:
                self.fullscreen_button.hide()
                self.detail_image.set_placeholder("The provider returned an unsupported image format.")
                self._set_ambient_image(
                    self.detail_ambient, QPixmap(), self.detail_page
                )
            self._finish_loading()
            self.statusBar().showMessage("Image loaded", 3000)
            if auto_load_full_image:
                self.load_full_image(keep_preview=True)
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
            pixmap = QPixmap.fromImage(result)
            post = (
                task.args[0]
                if isinstance(task, BackgroundTask)
                and task.args
                and isinstance(task.args[0], ImagePost)
                else None
            )
            if not pixmap.isNull() and post:
                self.thumbnail_cache[post.post_id] = pixmap
            if token != self.favorites_dialog_token or not self.favorites_dialog:
                return
            if not pixmap.isNull():
                self.favorites_dialog.set_thumbnail(favorite_id, pixmap)
            else:
                self.favorites_dialog.set_thumbnail_error(
                    favorite_id, "Preview contained invalid image data."
                )
        elif category == "download":
            self.downloads.update_download(identifier, f"Saved: {result}")
            self.statusBar().showMessage(f"Saved image to {result}", 5000)
        elif category == "full-image":
            self._stop_full_image_loading_animation()
            view, token = identifier.split("/", 1)
            if view == "random":
                if token != str(self.request_id) or self.pages.currentWidget() is not self.random_page:
                    return
                full_pixmap = QPixmap.fromImage(result)
                self.random_image.set_image(full_pixmap, preserve_zoom=True)
                self._set_ambient_image(self.random_ambient, full_pixmap, self.random_page)
                post = self.random_post
            else:
                if token != self.active_detail_id or self.pages.currentWidget() is not self.detail_page:
                    return
                full_pixmap = QPixmap.fromImage(result)
                self.detail_image.set_image(full_pixmap, preserve_zoom=True)
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
            self.statusBar().showMessage("Full-resolution image loaded", 4000)

    def _task_failed(self, key: str, error: str) -> None:
        self.tasks.pop(key, None)
        category, _, identifier = key.partition(":")
        if category == "tag-suggestions":
            cache_key = self._suggestion_request_keys.pop(key, None)
            if cache_key is not None:
                self._suggestion_refreshing.discard(cache_key)
            _LOGGER.debug("Optional tag lookup failed: %s", error)
            return
        if category == "tag-correction":
            _LOGGER.debug("Optional tag lookup failed: %s", error)
            return
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
        elif (
            category in {"random-preview", "random-image"}
            and int(identifier) == self.request_id
            and self._random_provider == "All"
            and self.random_post is not None
        ):
            self._random_failed_preview_providers.add(self.random_post.provider)
            self.statusBar().showMessage("Preview unavailable; trying another provider...")
            self._submit(
                f"random-fallback:{identifier}",
                self._catalog().random_post,
                self._random_rating,
                "All",
                self._random_query,
                frozenset(self._random_failed_preview_providers),
            )
        elif category in {"random", "random-preview", "random-image", "random-fallback"} and int(identifier) == self.request_id:
            self._finish_loading()
            self.random_media_stack.setCurrentWidget(self.random_scroll)
            self.random_video.clear()
            self._set_ambient_image(
                self.random_ambient, QPixmap(), self.random_page
            )
            self.fullscreen_button.hide()
            media_filter = str(self.settings.get("search/media_filter", "image"))
            media_name = {"image": "image", "video": "video", "png": "PNG image", "all": "media"}.get(media_filter, "media")
            self.random_image.set_placeholder(f"Could not load {media_name}\n{error}")
            self.statusBar().showMessage(f"Could not load {media_name}: {error}")
        elif category == "random-video" and int(identifier) == self.request_id:
            self._finish_loading()
            self.random_video.show_prepare_error(f"Could not prepare video: {error}")
            self.statusBar().showMessage(f"Could not prepare video: {error}")
        elif category == "post-detail" and identifier == self.active_detail_id:
            self._finish_loading()
            self.detail_media_stack.setCurrentWidget(self.detail_video if self.detail_post and self.detail_post.media_type == "video" else self.detail_scroll)
            self._set_ambient_image(
                self.detail_ambient, QPixmap(), self.detail_page
            )
            if self.detail_image.original.isNull():
                self.detail_image.set_placeholder(f"Could not load image\n{error}")
            self.statusBar().showMessage(f"Could not load image: {error}")
        elif category == "random-video-preview" and int(identifier) == self.request_id:
            self._set_ambient_image(
                self.random_ambient, QPixmap(), self.random_page
            )
        elif category == "detail-video-preview" and identifier == self.active_detail_id:
            self._set_ambient_image(
                self.detail_ambient, QPixmap(), self.detail_page
            )
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
                self.favorites_dialog.set_thumbnail_error(favorite_id, error)
        elif category == "download":
            self.downloads.update_download(identifier, f"Failed: {error}")
        elif category == "full-image":
            self._stop_full_image_loading_animation()
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
                target_image.set_image(previous, preserve_zoom=True)
                self._set_ambient_image(ambient, previous, page)
                if view == "detail":
                    self._set_detail_image_footer(self.detail_post, previous)
                else:
                    self._set_random_image_footer(self.random_post, previous)
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

    def _start_full_image_loading_animation(self) -> None:
        self._full_image_loading_dots = 0
        self._full_image_loading_timer.start()
        self._update_full_image_loading_text()

    def _stop_full_image_loading_animation(self) -> None:
        self._full_image_loading_timer.stop()

    def _update_full_image_loading_text(self) -> None:
        image_state = self._full_image_view
        post = self._active_post()
        if (
            image_state is None
            or post is None
            or self.pages.currentWidget() is not image_state[2]
        ):
            self._stop_full_image_loading_animation()
            return
        self._full_image_loading_dots = self._full_image_loading_dots % 3 + 1
        message = f"Load Full Image{'.' * self._full_image_loading_dots}"
        self.footer_meta.setText(
            f"{post.provider} | {rating_label(post.rating)} | {message}"
        )
        self.statusBar().showMessage(message)

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
            maximum = str(self.settings.get("parent/max_rating", "s"))
            maximum_rank = {"s": 0, "q": 1, "e": 2}.get(maximum, 0)
            nsfw_rating = str(self.settings.get("search/nsfw_rating", "q_e"))
            nsfw_rank = 1 if nsfw_rating == "q" else 2
            requested_rank = {
                "sfw": 0,
                "nsfw": nsfw_rank,
                "all": 2,
            }.get(self.selected_rating, 2)
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
        if self._active_rating() == "sfw" or self.settings.get_bool("search/allow_nsfw"):
            return True
        BackupMessageDialog.notify(
            self,
            "NSFW filter",
            "Enable 'Allow NSFW results' in Settings before selecting this rating.",
        )
        self.open_preferences()
        if self.settings.get_bool("search/allow_nsfw"):
            return True
        self.rating_changed("sfw")
        return False

    def _new_request(self) -> int:
        self.request_id += 1
        return self.request_id

    def show_random(self) -> None:
        self._stop_full_image_loading_animation()
        if not self._rating_allowed():
            return
        self._set_ambient_image(
            self.random_ambient, QPixmap(), self.random_page
        )
        self.random_ai_badge.hide()
        self.random_video_ai_badge.hide()
        if not self._fullscreen_active:
            self.statusBar().show()
        self._hide_normal_video_actions("random")
        self._hide_normal_video_actions("detail")
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
        self._random_provider = provider
        self._random_rating = self._active_rating()
        self._random_query = query
        self._random_failed_preview_providers.clear()
        self.random_pixmap = None
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
            f"random:{identifier}", self._catalog().random_post,
            self._random_rating, provider, query,
        )

    def go_home(self) -> None:
        """Clear the active tag and return to a random image."""
        if self._fullscreen_active:
            self._exit_fullscreen()
        self.search_input.clear()
        self.show_random()

    def _show_random_image(self, pixmap: QPixmap) -> None:
        self._stop_full_image_loading_animation()
        if pixmap.isNull():
            self._finish_loading()
            self.random_image.set_placeholder("The provider returned an unsupported image format.")
            return
        self.random_pixmap = pixmap
        self._full_image_loaded = False
        if not self._fullscreen_active:
            self.statusBar().show()
        # The preview is now retained as a pixmap; do not keep a second copy
        # of the compressed response bytes in memory.
        self.random_content = None
        self.random_media_stack.setCurrentWidget(self.random_scroll)
        self.random_video.clear()
        self.random_image.set_image(pixmap)
        self.random_video_ai_badge.hide()
        self._update_media_ai_badge(
            self.random_ai_badge, getattr(self, "random_post", None)
        )
        self.download_button.show()
        self.full_image_button.setToolTip("Load original-resolution image")
        self.full_image_button.setEnabled(True)
        auto_load_full_image = self.settings.get_bool(
            "view/auto_load_full_image", False
        )
        self._sync_full_image_button_visibility()
        self._set_image_credits_visible(True)
        self._set_ambient_image(self.random_ambient, pixmap, self.random_page)
        self.fullscreen_button.setVisible(not self._fullscreen_active)
        self._sync_favorite_buttons()
        post = getattr(self, "random_post", None)
        self._set_random_image_footer(post, pixmap)
        self._finish_loading()
        self.statusBar().showMessage("Image loaded", 3000)
        if auto_load_full_image:
            self.load_full_image(keep_preview=True)

    def _show_random_video(self, post: ImagePost) -> None:
        self.random_ai_badge.hide()
        self._update_media_ai_badge(self.random_video_ai_badge, post)
        if not self._fullscreen_active:
            self.statusBar().show()
            self.statusBar().raise_()
        self.full_image_button.hide()
        self.random_video.clear()
        self.random_media_stack.setCurrentWidget(self.random_video)
        # Keep the random video poster centered in the available viewer area.
        self.random_video.set_poster_alignment(Qt.AlignmentFlag.AlignCenter)
        self.random_video.set_deferred_source(post.image_url)
        self.download_button.show()
        if not self._fullscreen_active:
            QTimer.singleShot(0, self._ensure_status_bar_visible)
        if post.preview_urls:
            self._submit(
                f"random-video-preview:{self.request_id}",
                self._fetch_decoded_video_preview,
                post,
            )
        else:
            self._set_ambient_image(
                self.random_ambient, QPixmap(), self.random_page
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
        self._dismiss_search_suggestions()
        self.search_correction_button.hide()
        self._suggested_search_query = ""
        self._open_detail_after_page = None
        if not self._rating_allowed():
            return
        query = self.search_input.text().strip()
        if not query:
            self.go_home()
            return
        self._record_search(query)
        if not self._fullscreen_active:
            self.statusBar().show()
        self.current_query = query
        self.full_image_button.hide()
        self.title_bar.home_button.show()
        self.current_page = 1
        self.load_page(1)

    def _on_search_query_edited(self, _text: str) -> None:
        self._search_suggestions_suppressed = False
        self._open_detail_after_page = None
        self.search_correction_button.hide()
        self._suggested_search_query = ""
        self._search_suggestion_generation += 1
        self._search_suggestion_timer.stop()
        self.search_suggestion_panel.hide()
        self._search_suggestion_row.hide()
        query = _text.strip()
        fragment = self._search_tag_fragment(query)[1]
        self._search_suggestion_query = query
        self._search_suggestion_fragment = fragment.replace(" ", "_")
        cached = (
            self._suggestion_cache.get(
                self.selected_provider, self._search_suggestion_fragment
            )
            if len(fragment) >= 2 and not any(mark in fragment for mark in "*~():-")
            else None
        )
        self._refresh_search_completion_model(
            query, cached[0] if cached is not None else []
        )
        if self.search_input.hasFocus():
            self._show_search_completion_popup()
            QTimer.singleShot(0, self._sync_search_completion_popup)
        if (
            len(fragment) >= 2
            and not any(mark in fragment for mark in "*~():-")
        ):
            self._search_suggestion_timer.start()

    def _sync_search_completion_popup(self) -> None:
        if not self.search_input.hasFocus():
            self.search_suggestion_panel.hide()
            self._search_suggestion_row.hide()
            return
        self._show_search_completion_popup()

    def _show_search_suggestions_when_ready(self) -> None:
        if (
            self._search_suggestions_suppressed
            or not self.search_input.hasFocus()
        ):
            return
        query = self.search_input.text().strip()
        if query != self._search_suggestion_query or not self._search_suggestion_model.rowCount():
            fragment = self._search_tag_fragment(query)[1]
            prefix = fragment.replace(" ", "_")
            cached = (
                self._suggestion_cache.get(self.selected_provider, prefix)
                if len(fragment) >= 2 and not any(mark in fragment for mark in "*~():-")
                else None
            )
            self._search_suggestion_query = query
            self._search_suggestion_fragment = prefix
            self._refresh_search_completion_model(
                query, cached[0] if cached is not None else []
            )
        self._show_search_completion_popup()
        fragment = self._search_tag_fragment(query)[1]
        if len(fragment) >= 2 and not any(mark in fragment for mark in "*~():-"):
            self._search_suggestion_timer.start()

    def _show_search_completion_popup(self) -> None:
        panel = self.search_suggestion_panel
        if self._search_suggestions_suppressed:
            panel.hide()
            return
        if not self._search_suggestion_model.rowCount():
            panel.hide()
            self._search_suggestion_row.hide()
            return
        self._search_completer.setCompletionPrefix(
            self._search_completion_prefix(self.search_input.text().strip())
        )
        if self._search_completer.completionCount() <= 0:
            panel.hide()
            self._search_suggestion_row.hide()
            return
        row_count = min(8, self._search_suggestion_model.rowCount())
        panel.setFixedHeight(row_count * 34 + 12)
        self.title_bar._sync_search_suggestion_sizes()
        self.title_bar._sync_search_overlay_geometry()
        panel.raise_()
        panel.show()

    def _suppress_search_suggestions_on_page_change(self, *_args) -> None:
        self._search_suggestions_suppressed = True
        self.search_suggestion_panel.hide()
        if self.search_input.hasFocus():
            self.pages.setFocus(Qt.FocusReason.OtherFocusReason)

    def _position_search_suggestion_panel(self) -> None:
        panel = getattr(self, "search_suggestion_panel", None)
        search_input = getattr(self, "search_input", None)
        root = getattr(self, "_root_widget", None)
        if panel is None or search_input is None or root is None:
            return
        field_bottom = search_input.mapTo(root, QPoint(0, search_input.height()))
        target_position = QPoint(field_bottom.x(), field_bottom.y() + 6)
        if panel.pos() != target_position:
            panel.move(target_position)
        if panel.width() != search_input.width():
            panel.setFixedWidth(search_input.width())

    def _recent_search_queries(self) -> list[str]:
        value = self.settings.get("search/recent_queries", [])
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, (list, tuple)):
            values = value
        else:
            return []

        recent = []
        seen = set()
        for item in values:
            if not isinstance(item, str):
                continue
            query = item.strip()
            normalized = query.casefold()
            if query and normalized not in seen:
                recent.append(query)
                seen.add(normalized)
            if len(recent) == 10:
                break
        return recent

    def _record_search(self, query: str) -> None:
        recent = [item for item in self._recent_search_queries()
                  if item.casefold() != query.casefold()]
        self.settings.set("search/recent_queries", [query, *recent][:10])

    def _remove_recent_search(self, query: str) -> None:
        normalized = query.casefold()
        recent = [
            item for item in self._recent_search_queries()
            if item.casefold() != normalized
        ]
        self.settings.set("search/recent_queries", recent)
        current_query = self.search_input.text().strip()
        if current_query:
            self._on_search_query_edited(current_query)
        else:
            self._refresh_search_completion_model("", [])
            if self.search_input.hasFocus():
                self._show_search_completion_popup()

    def _matching_recent_searches(self, query: str) -> list[str]:
        recent = self._recent_search_queries()
        if not query:
            return recent
        needle = self._search_completion_prefix(query).casefold()
        return [
            item for item in recent
            if self._search_completion_prefix(item).casefold().startswith(needle)
        ]

    def _refresh_search_completion_model(
        self, query: str, tag_suggestions: list[str]
    ) -> None:
        self._search_suggestion_model.clear()
        recent = self._matching_recent_searches(query)
        recent_targets = {
            self._search_completion_prefix(item).casefold() for item in recent
        }
        prefix = self._search_tag_fragment(query)[0]

        for query in recent:
            item = QStandardItem(query.replace("_", " "))
            item.setIcon(self._icon("history"))
            item.setData(query, Qt.ItemDataRole.UserRole)
            item.setData(query, HISTORY_QUERY_ROLE)
            item.setSizeHint(QSize(max(100, self.search_input.width() - 8), 34))
            self._search_suggestion_model.appendRow(item)

        for tag in tag_suggestions:
            completion = f"{prefix}{tag}"
            if self._search_completion_prefix(completion).casefold() in recent_targets:
                continue
            item = QStandardItem(tag.replace("_", " "))
            item.setIcon(self._icon("search"))
            item.setData(completion, Qt.ItemDataRole.UserRole)
            item.setSizeHint(QSize(max(100, self.search_input.width() - 8), 34))
            self._search_suggestion_model.appendRow(item)

        self._search_completer.setCompletionPrefix(
            self._search_completion_prefix(query)
        )

    @staticmethod
    def _search_tag_fragment(query: str) -> tuple[str, str]:
        before, separator, fragment = query.rpartition(",")
        leading = fragment[:len(fragment) - len(fragment.lstrip())]
        return before + separator + leading, fragment.strip().replace(" ", "_")

    @classmethod
    def _search_completion_prefix(cls, query: str) -> str:
        prefix, fragment = cls._search_tag_fragment(query)
        return f"{prefix}{fragment}"

    def _request_search_suggestions(self) -> None:
        query = self._search_suggestion_query
        if (
            not query
            or query != self.search_input.text().strip()
            or len(self._search_suggestion_fragment) < 2
        ):
            return
        provider = self.selected_provider
        prefix = self._search_suggestion_fragment
        cache_key = (provider.casefold(), prefix.casefold())
        cached = self._suggestion_cache.get(provider, prefix)
        if cached is not None:
            suggestions, is_fresh = cached
            self._refresh_search_completion_model(query, suggestions)
            if self.search_input.hasFocus():
                self._show_search_completion_popup()
            if is_fresh:
                return
        if cache_key in self._suggestion_refreshing:
            return
        task_key = f"tag-suggestions:{self._search_suggestion_generation}"
        self._suggestion_refreshing.add(cache_key)
        self._suggestion_request_keys[task_key] = cache_key
        self._submit(
            task_key,
            self._catalog().suggest_tags,
            prefix,
            provider,
            12,
        )

    def _dismiss_search_suggestions(self) -> None:
        self._search_suggestions_suppressed = True
        self._search_suggestion_timer.stop()
        self._search_suggestion_generation += 1
        self._search_suggestion_query = ""
        self._search_suggestion_fragment = ""
        self._search_suggestion_model.clear()
        self.search_suggestion_panel.hide()
        self._search_suggestion_row.hide()

    def _apply_search_completion(self, query: str) -> None:
        self.search_input.setText(query)
        self.search_input.setCursorPosition(len(self.search_input.text()))
        self.start_search()

    def _request_tag_correction(self, query: str, request_id: int) -> None:
        fragment = self._search_tag_fragment(query)[1]
        if len(fragment) < 4 or any(mark in fragment for mark in "*~():-"):
            return
        self._typo_search_query = query
        self._typo_search_request_id = request_id
        self._submit(
            f"tag-correction:{request_id}",
            self._catalog().suggest_tags,
            fragment[:3],
            self.selected_provider,
            100,
        )

    def _show_tag_correction(self, query: str, candidates: list[str]) -> None:
        prefix, fragment = self._search_tag_fragment(query)
        matches = difflib.get_close_matches(
            fragment.casefold(), candidates, n=1, cutoff=0.78
        )
        if not matches or matches[0].casefold() == fragment.casefold():
            return
        self._suggested_search_query = f"{prefix}{matches[0]}"
        self.search_correction_button.setText(
            f"You mean '{matches[0].replace('_', ' ')}'?"
        )
        self.search_correction_button.setToolTip(
            f"Search for {matches[0].replace('_', ' ')}"
        )
        self.search_correction_button.show()

    def _apply_search_correction(self) -> None:
        if not self._suggested_search_query:
            return
        self.search_input.setText(self._suggested_search_query)
        self.search_input.setCursorPosition(len(self.search_input.text()))
        self.start_search()

    def load_page(self, page: int, detail_index: int | None = None) -> None:
        if not self.current_query or not self._rating_allowed():
            return
        self.search_correction_button.hide()
        self._suggested_search_query = ""
        self.full_image_button.hide()
        self.random_video.clear()
        self.detail_video.clear()
        self._open_detail_after_page = detail_index
        if detail_index is None:
            self.download_button.hide()
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
        self.download_button.hide()
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
            media_name = {"image": "images", "video": "videos", "png": "PNG images", "all": "media"}.get(media_filter, "images")
            self._show_gallery_notice(f'No {media_name} found for "{self.current_query}".')
            if not page.provider_errors:
                self._request_tag_correction(self.current_query, self.request_id)
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
        self.card_ai_badges.clear()
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
        self._update_gallery_notice_mask()
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

    def _update_gallery_notice_mask(self) -> None:
        width, height = self.gallery_status.width(), self.gallery_status.height()
        radius = min(24, width // 2, height // 2)
        if radius <= 0:
            self.gallery_status.clearMask()
            return
        diameter = radius * 2
        mask = QRegion(
            QRect(radius, 0, width - diameter, height),
            QRegion.RegionType.Rectangle,
        )
        mask |= QRegion(
            QRect(0, radius, width, height - diameter),
            QRegion.RegionType.Rectangle,
        )
        for x, y in (
            (0, 0),
            (width - diameter, 0),
            (0, height - diameter),
            (width - diameter, height - diameter),
        ):
            mask |= QRegion(
                QRect(x, y, diameter, diameter),
                QRegion.RegionType.Ellipse,
            )
        self.gallery_status.setMask(mask)

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

    def _update_card_icon_sizes(self, *, render_thumbnails: bool = True) -> None:
        if not self.card_buttons:
            return
        columns = self._gallery_column_count()
        available = max(1, self.gallery_scroll.viewport().width())
        card_width = max(190, (available - 8 * (columns - 1)) // columns)
        icon_size = QSize(max(16, card_width - 12), 213)
        changed = False
        for button in self.card_buttons.values():
            if button.iconSize() != icon_size:
                button.setIconSize(icon_size)
                changed = True
        if render_thumbnails and changed:
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
            play_badge = QLabel(preview_container)
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
        if self._is_ai_tagged_post(post):
            ai_badge = self._create_ai_badge(preview_container)
            preview_layout.addWidget(
                ai_badge, 0, 0,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
            )
            self.card_ai_badges[post.post_id] = ai_badge
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

    def _fetch_preview(
        self, candidates: tuple[str, ...], catalog: BooruCatalog | None = None
    ) -> bytes:
        failures = []
        catalog = catalog or self._catalog()
        for url in candidates:
            try:
                return catalog.fetch_image(url, timeout=(3, 8), retry=False)
            except ProviderError as error:
                failures.append(str(error))
        raise ProviderError(failures[-1] if failures else "No thumbnail URL was supplied.")

    def _fetch_decoded_preview(self, post: ImagePost, report_progress=None):
        content = self._catalog().fetch_post_preview(post, report_progress)
        return decode_image_bytes(content, max_dimension=2560)

    def _fetch_decoded_candidates(self, candidates: tuple[str, ...]):
        return decode_image_bytes(self._fetch_preview(candidates), max_dimension=560)

    def _fetch_decoded_favorite_thumbnail(
        self, post: ImagePost, catalog: BooruCatalog, cache_enabled: bool = True
    ):
        candidates = tuple(
            url for url in post.preview_urls if url != post.image_url
        )[:2] or (post.image_url,)
        if cache_enabled:
            cached = load_favorite_thumbnail(favorite_key(post), candidates[0])
            if cached is not None:
                return cached
        image = decode_image_bytes(
            self._fetch_preview(candidates, catalog),
            max_dimension=560,
        )
        if cache_enabled:
            save_favorite_thumbnail(favorite_key(post), candidates[0], image)
        return image

    def _fetch_decoded_video_preview(self, post: ImagePost):
        return decode_image_bytes(
            self._fetch_preview(post.preview_urls),
            max_dimension=1440,
        )

    def _fetch_decoded_original(self, post: ImagePost, report_progress=None):
        content = self._catalog().fetch_image(post.image_url, report_progress)
        return decode_image_bytes(content, max_dimension=None)

    def load_full_image(self, *, keep_preview: bool = False) -> None:
        post = self._active_post()
        if (
            post is None
            or post.media_type != "image"
            or self._full_image_loaded
            or not self.full_image_button.isEnabled()
        ):
            return
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
        if target_image.original.isNull():
            return
        self._full_image_previous = target_image.original
        self._full_image_view = (target_image, ambient, page)
        self._start_full_image_loading_animation()
        if not keep_preview:
            target_image.set_loading(preserve_zoom=True)
        self.full_image_button.setEnabled(False)
        self.full_image_button.setToolTip("Load original-resolution image")
        task_key = f"full-image:{identifier}"
        if keep_preview:
            self._submit(task_key, self._fetch_decoded_original, post)
        else:
            self._submit(
                task_key,
                self._fetch_decoded_original,
                post,
                progress_callback=self._update_load_progress,
            )

    def _sync_full_image_button_visibility(self) -> None:
        post = self._active_post()
        if post is None or post.media_type != "image" or self._full_image_loaded:
            self.full_image_button.hide()
            return
        if self.pages.currentWidget() is self.random_page:
            image = self.random_image
        elif self.pages.currentWidget() is self.detail_page:
            image = self.detail_image
        else:
            self.full_image_button.hide()
            return
        if image.original.isNull():
            self.full_image_button.hide()
            return
        self.full_image_button.setVisible(
            not self.settings.get_bool("view/auto_load_full_image", False)
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
        ai_badge = self.card_ai_badges.get(post.post_id)
        if ai_badge:
            ai_badge.show()
            ai_badge.raise_()

    def open_post(self, post: ImagePost) -> None:
        self._dismiss_search_suggestions()
        self._stop_full_image_loading_animation()
        if not self._parent_allows_post(post):
            BackupMessageDialog.notify(
                self, "Parental control",
                "This media is above the guardian's content limits.",
            )
            return
        self._media_controls_idle_timer.stop()
        self.footer_meta.clear()
        self.random_video.clear()
        self.detail_video.clear()
        self._hide_normal_video_actions("random")
        self._hide_normal_video_actions("detail")
        self.detail_ai_badge.hide()
        self._update_media_ai_badge(
            self.detail_video_ai_badge,
            post if post.media_type == "video" else None,
        )
        self.detail_post = post
        self._full_image_loaded = False
        self._set_ambient_image(
            self.detail_ambient, QPixmap(), self.detail_page
        )
        self.full_image_button.hide()
        self.full_image_button.setEnabled(True)
        self.full_image_button.setToolTip("Load original-resolution image")
        if post.media_type == "video":
            if not self._fullscreen_active:
                self.statusBar().show()
                self.statusBar().raise_()
            self.full_image_button.hide()
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
        self.download_button.show()
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
            else:
                self._set_ambient_image(
                    self.detail_ambient, QPixmap(), self.detail_page
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
        self._update_keyboard_shortcuts()
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
        page = self.detail_media_stack
        button_height = self.detail_video_previous_overlay.height()
        center_y = max(0, (page.height() - button_height) // 2)
        positions = (
            (self.detail_previous_button, QPoint(12, center_y)),
            (self.detail_next_button, QPoint(
                max(12, page.width() - self.detail_next_button.width() - 12), center_y
            )),
            (self.detail_video_previous_overlay, QPoint(12, center_y)),
            (self.detail_video_next_overlay, QPoint(
                max(12, page.width() - self.detail_video_next_overlay.width() - 12), center_y
            )),
        )
        for widget, position in positions:
            if widget.pos() != position:
                widget.move(position)
            # QStackedWidget raises its current media page above sibling
            # overlays when setCurrentWidget() changes. Re-raise visible
            # navigation controls even when their geometry stayed unchanged;
            # otherwise they remain visible through the transparent scroll
            # area but their clicks are intercepted by its viewport.
            if widget.isVisible():
                widget.raise_()

    def _update_page_navigation_visibility(self, *_args) -> None:
        self.page_navigation.setVisible(
            self.pages.currentWidget() is self.gallery_page
        )

    def _update_image_credits(self, post: ImagePost | None) -> None:
        self._credits_post = post

    def show_image_credits(self) -> None:
        post = getattr(self, "_credits_post", None)
        if post is None:
            return
        dialog = ImageCreditsDialog(post, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.accepted.connect(lambda current=dialog: self._search_credits_tag(current))
        self._show_modeless_dialog(dialog)

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
            self.download_button.hide()
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
        if fullscreen_post is not None:
            ambient = (
                self.random_ambient
                if self._fullscreen_source == "random"
                else self.detail_ambient
            )
            self._set_ambient_visibility(ambient, current_page, False)
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
        updates_were_enabled = self.updatesEnabled()
        self.setUpdatesEnabled(False)
        try:
            self.showNormal()
            if screen is not None:
                self.setGeometry(screen.geometry())
        finally:
            self.setUpdatesEnabled(updates_were_enabled)
        if updates_were_enabled:
            self.update()
        self._sync_favorite_buttons()
        self._show_fullscreen_controls()
        if fullscreen_post is not None and fullscreen_post.media_type == "video":
            active_player._reflow_timer.stop()
            active_player._reflow()
        else:
            active_player._schedule_reflow()
            image = self.random_image if self._fullscreen_source == "random" else self.detail_image
            QTimer.singleShot(0, image._fit_to_viewport)

    def _hide_normal_video_actions(self, source: str) -> None:
        if source == "random":
            actions = (
                self.random_video_refresh_action,
                self.random_video_download_action,
            )
            favorite_action = self.random_video_favorite_action
            exit_action = self.random_video_exit_action
        else:
            actions = (
                self.detail_video_download_action,
            )
            favorite_action = self.detail_video_favorite_action
            exit_action = self.detail_video_exit_action
        for action in actions:
            action.hide()
        favorite_action.hide()
        exit_action.hide()

    def _check_for_startup_update(self) -> None:
        if self._startup_update_task is not None:
            return
        task = UpdateCheckTask()
        self._startup_update_task = task
        task.signals.finished.connect(self._startup_update_checked)
        self.pool.start(task)

    def _startup_update_checked(
        self,
        tag: str,
        url: str,
        notes: str,
        download_url: str,
        sha256: str,
        error: str,
    ) -> None:
        self._startup_update_task = None
        if error or version_parts(tag) <= version_parts(__version__):
            return
        dialog = ReleaseNotesDialog(
            tag, url, notes, download_url, sha256, self
        )
        dialog.download_requested.connect(
            lambda current=dialog: self._download_update(current)
        )
        dialog.install_requested.connect(
            lambda installer, current=dialog: self._launch_update_installer(
                current, installer
            )
        )
        dialog.finished.connect(
            lambda _result, current=dialog: self._clear_update_notice(current)
        )
        self._update_notice_dialog = dialog
        self._show_modeless_dialog(dialog)

    def _download_update(self, dialog: ReleaseNotesDialog) -> None:
        if self._update_download_task is not None:
            return
        dialog.begin_download()
        task = UpdateDownloadTask(
            dialog.version,
            dialog.download_url,
            dialog.sha256,
        )
        task.signals.progress.connect(dialog.set_download_progress)
        task.signals.finished.connect(
            lambda path, error, current=dialog: self._update_download_finished(
                current, path, error
            )
        )
        self._update_download_task = task
        self.pool.start(task)

    def _update_download_finished(
        self, dialog: ReleaseNotesDialog, installer_path: str, error: str
    ) -> None:
        self._update_download_task = None
        if error:
            dialog.set_download_error(error)
        else:
            dialog.set_installer_ready(installer_path)

    def _launch_update_installer(
        self, dialog: ReleaseNotesDialog, installer_path: str
    ) -> None:
        installer = Path(installer_path)
        if installer.name != WINDOWS_INSTALLER or not installer.is_file():
            dialog.set_download_error("The downloaded installer could not be found.")
            return
        try:
            subprocess.Popen(
                [str(installer)],
                cwd=str(installer.parent),
                close_fds=True,
            )
        except OSError as error:
            dialog.set_download_error(f"Could not open the installer: {error}")

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
            if not toolbar.isHidden():
                toolbar.hide()
            player.set_fullscreen_toggle_visible(False)
            self.random_video.set_fullscreen_actions_visible(source == "random")
            self.detail_video.set_fullscreen_actions_visible(source != "random")
            controls_ready = (
                player._fullscreen_controls_visible
                and player._controls_visible
                and player.controls_frame.isVisible()
            )
            if not controls_ready:
                player.set_fullscreen_controls_visible(True)
                player.controls_frame.raise_()
            self._fullscreen_idle_timer.start()
            return
        self.random_video.set_fullscreen_actions_visible(False)
        self.detail_video.set_fullscreen_actions_visible(False)
        if toolbar.isHidden():
            width, height = toolbar.sizeHint().width(), 58
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

    def _update_keyboard_shortcuts(self, *_args) -> None:
        search_active = self._search_completion_active()
        self.refresh_shortcut.setEnabled(not search_active)
        can_navigate = (
            not search_active
            and self.pages.currentWidget() is self.detail_page
            and self._detail_has_navigation()
        )
        for shortcut in self._media_navigation_shortcuts:
            shortcut.setEnabled(can_navigate)

    def _search_completion_active(self) -> bool:
        return self.search_input.hasFocus() or (
            self.search_suggestion_panel.isVisible()
        )

    def _navigate_detail_media(self, direction: int) -> None:
        if (
            self._search_completion_active()
            or self.pages.currentWidget() is not self.detail_page
            or not self._detail_has_navigation()
        ):
            return
        self._swipe_detail(direction)

    def provider_changed(self, provider: str) -> None:
        self.selected_provider = provider
        self.settings.set("search/provider", provider)
        self.provider_actions[provider].setChecked(True)
        self._update_filter_tooltip()
        self._search_suggestion_timer.stop()
        self._search_suggestion_generation += 1
        self._search_suggestion_query = ""
        self._search_suggestion_model.clear()
        if self.search_input.hasFocus():
            self._on_search_query_edited(self.search_input.text())
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
            self._show_modeless_dialog(self.preferences_dialog)
            return
        previous_provider = self.selected_provider
        previous_rating = self.selected_rating
        previous_filter_settings = self._content_filter_settings()
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
            "auto_load_full_image": self.settings.get_bool("view/auto_load_full_image", False),
        }

        def preferences_changed() -> None:
            favorites = self._favorite_posts()
            imported_theme = str(self.settings.get("appearance/theme", self.current_theme))
            if imported_theme in THEME_NAMES and imported_theme != self.current_theme:
                self.change_theme(imported_theme)
            parent_policy = (
                self.settings.get_bool("parent/enabled"),
                str(self.settings.get("parent/max_rating", "s")),
                tuple(self.settings.get("parent/allowed_tags", []) or []),
            )
            auto_load_full_image = self.settings.get_bool(
                "view/auto_load_full_image", False
            )
            auto_load_just_enabled = (
                auto_load_full_image and not preference_state["auto_load_full_image"]
            )
            auto_load_changed = auto_load_full_image != preference_state["auto_load_full_image"]
            preference_state["auto_load_full_image"] = auto_load_full_image
            favorites_lock_enabled = self.settings.get_bool("favorites_lock/enabled")
            if favorites_lock_enabled and not preference_state["favorites_lock"] and self.favorites_dialog:
                self.favorites_dialog.close()
            if favorites != preference_state["favorites"] or parent_policy != preference_state["parent_policy"]:
                preference_state["favorites"] = favorites
                self._refresh_favorites_dialog(favorites)
            self._preferences_updated(
                preference_state["provider"],
                preference_state["rating"],
                preference_state["filters"],
            )
            preference_state["provider"] = self.selected_provider
            preference_state["rating"] = self.selected_rating
            preference_state["filters"] = self._content_filter_settings()
            preference_state["parent_policy"] = parent_policy
            preference_state["favorites_lock"] = favorites_lock_enabled
            if auto_load_changed:
                self._sync_full_image_button_visibility()
            if auto_load_just_enabled:
                self.load_full_image(keep_preview=True)

        dialog.settings_changed.connect(preferences_changed)
        dialog.finished.connect(
            lambda _result, current=dialog: self._clear_preferences_dialog(current)
        )
        self._show_modeless_dialog(dialog)

    def _clear_preferences_dialog(self, dialog: PreferencesDialog) -> None:
        if self.preferences_dialog is dialog:
            self.preferences_dialog = None

    def _content_filter_settings(self) -> tuple:
        return (
            self.settings.get_bool("search/exclude_male", True),
            self.settings.get_bool("search/allow_nsfw"),
            self.settings.get_bool("search/filter_gore", True),
            self.settings.get_bool("search/filter_ai_generated", False),
            str(self.settings.get("search/nsfw_rating", "q_e")),
            tuple(self.settings.get("search/custom_block_tags", []) or []),
            self.settings.get_bool("parent/enabled"),
            str(self.settings.get("parent/max_rating", "s")),
            tuple(self.settings.get("parent/allowed_tags", []) or []),
        )

    def _refresh_active_filter_view(self) -> None:
        current_page = self.pages.currentWidget()
        search_is_active = current_page is self.gallery_page or (
            current_page is self.detail_page and self.detail_origin == "search"
        )
        random_is_active = current_page is self.random_page or (
            current_page is self.detail_page and self.detail_origin == "random"
        )

        if search_is_active and self.current_query:
            self.current_page = 1
            self.load_page(1)
        elif random_is_active:
            self.show_random()

    def _preferences_updated(
        self,
        previous_provider: str,
        previous_rating: str,
        previous_filter_settings: tuple,
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
        current_filter_settings = self._content_filter_settings()
        filters_changed = current_filter_settings != previous_filter_settings
        settings_changed = (
            self.selected_provider != previous_provider
            or self.selected_rating != previous_rating
            or self.selected_media != previous_media
            or filters_changed
        )
        if settings_changed:
            self._rating_allowed()
            self._refresh_active_filter_view()

    def queue_download(self, post: ImagePost) -> None:
        if not self._parent_allows_post(post):
            BackupMessageDialog.notify(
                self, "Parental control",
                "This media is above the guardian's content limits.",
            )
            return
        suggested = str(self._default_download_path(post))
        is_video = post.media_type == "video"
        title = "Save video" if is_video else "Save image"
        file_types = (
            "Videos (*.mp4 *.m4v *.webm *.mov *.mkv *.avi);;All files (*.*)"
            if is_video else "Images (*.jpg *.jpeg *.png *.webp *.gif);;All files (*.*)"
        )
        filename, _ = QFileDialog.getSaveFileName(self, title, suggested, file_types)
        if not filename:
            return
        self._start_download(post, Path(filename))

    def _default_download_path(self, post: ImagePost) -> Path:
        folder = str(self.settings.get("downloads/folder", "")).strip()
        if not folder:
            folder = str(Path.home() / "Pictures" / "Waifu Gallery")
        extension = Path(post.image_url.split("?", 1)[0]).suffix or ".jpg"
        return Path(folder) / f"waifu_{post.post_id}{extension}"

    def _start_download(
        self,
        post: ImagePost,
        path: Path,
        catalog: BooruCatalog | None = None,
        *,
        download_key: str | None = None,
    ) -> None:
        key = download_key or str(uuid4())
        if download_key is None:
            self.downloads.add_download(key, path.name, str(path), post=post)
        else:
            self.downloads.update_download(key, "Queued", 0)
        task = FileDownloadTask(key, catalog or self._catalog(), post, path)
        task.signals.result.connect(lambda download_key, result: self._task_succeeded(f"download:{download_key}", result))
        task.signals.error.connect(lambda download_key, error: self._task_failed(f"download:{download_key}", error))
        task.signals.cancelled.connect(self._task_cancelled)
        task.signals.progress.connect(lambda download_key, value: self.downloads.update_download(
            download_key, f"Downloading: {path.name}", value))
        self.tasks[f"download:{key}"] = task
        self.pool.start(task)

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and self._ignore_search_popup_release
        ):
            self._ignore_search_popup_release = False
            return True
        if (
            watched is self._search_suggestion_viewport
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            point = event.position().toPoint()
            index = self._search_suggestion_view.indexAt(point)
            query = index.data(HISTORY_QUERY_ROLE) if index.isValid() else None
            if query and SearchSuggestionDelegate.remove_rect(
                self._search_suggestion_view.visualRect(index)
            ).contains(point):
                self._ignore_search_popup_release = True
                self._remove_recent_search(str(query))
                return True
        if (
            event.type() == QEvent.Type.WindowActivate
            and isinstance(watched, QWidget)
        ):
            active_window = watched.window()
            if (
                active_window is self
                or isinstance(active_window, QDialog)
                and self._belongs_to_main_window(active_window)
            ):
                QTimer.singleShot(
                    0,
                    lambda window=active_window: self._raise_active_app_window(window),
                )
        if event.type() == QEvent.Type.Resize:
            for badge in (
                getattr(self, "random_ai_badge", None),
                getattr(self, "detail_ai_badge", None),
                getattr(self, "random_video_ai_badge", None),
                getattr(self, "detail_video_ai_badge", None),
            ):
                if badge is not None and watched is badge.parentWidget():
                    self._position_corner_badge(badge)
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
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape and self.search_suggestion_panel.isVisible():
                    self.search_suggestion_panel.hide()
                    self._search_suggestion_row.hide()
                    return True
                if (
                    event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)
                    and self.search_suggestion_panel.isVisible()
                    and self._search_suggestion_model.rowCount()
                ):
                    current = self._search_suggestion_view.currentIndex().row()
                    step = -1 if event.key() == Qt.Key.Key_Up else 1
                    row = min(
                        self._search_suggestion_model.rowCount() - 1,
                        max(0, current + step),
                    )
                    index = self._search_suggestion_model.index(row, 0)
                    self._search_suggestion_view.setCurrentIndex(index)
                    self._search_suggestion_view.scrollTo(index)
                    return True
                if (
                    event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                    and self.search_suggestion_panel.isVisible()
                    and self._search_suggestion_view.currentIndex().isValid()
                ):
                    query = self._search_suggestion_view.currentIndex().data(
                        Qt.ItemDataRole.UserRole
                    )
                    if query:
                        self._apply_search_completion(str(query))
                        return True
            if event.type() == QEvent.Type.FocusIn:
                glow = QGraphicsDropShadowEffect(self.search_input)
                glow.setBlurRadius(18)
                glow.setColor(QColor(187, 154, 247, 115))
                glow.setOffset(0, 0)
                self.search_input.setGraphicsEffect(glow)
                self._update_keyboard_shortcuts()
                if event.reason() in (
                    Qt.FocusReason.TabFocusReason,
                    Qt.FocusReason.BacktabFocusReason,
                    Qt.FocusReason.ShortcutFocusReason,
                ):
                    QTimer.singleShot(0, self._show_search_suggestions_when_ready)
            elif event.type() == QEvent.Type.FocusOut:
                self.search_input.setGraphicsEffect(None)
                self.search_suggestion_panel.hide()
                self._update_keyboard_shortcuts()
            elif (
                event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton
                and event.position().x() < self.search_input.width() - 34
            ):
                self._search_suggestions_suppressed = False
                QTimer.singleShot(0, self._show_search_suggestions_when_ready)
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
        if event_name == "windows_generic_MSG":
            try:
                native_message = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
                if native_message.message == 0x0084:  # WM_NCHITTEST
                    maximize_button = getattr(
                        getattr(self, "title_bar", None),
                        "maximize_button",
                        None,
                    )
                    if (
                        maximize_button is not None
                        and maximize_button.isVisible()
                        and maximize_button.rect().contains(
                            maximize_button.mapFromGlobal(QCursor.pos())
                        )
                    ):
                        return True, self._HTMAXBUTTON
                    point = self.mapFromGlobal(QCursor.pos())
                    x, y = point.x(), point.y()
                    width, height, border = self.width(), self.height(), 7
                    left, right = x < border, x >= width - border
                    top, bottom = y < border, y >= height - border
                    hit = None
                    if self.isMaximized():
                        return super().nativeEvent(event_type, message)
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
        if not self._resize_in_progress:
            self._resize_in_progress = True
            self._ambient_restore_timer.stop()
            self._hide_ambient_during_resize()
        self._resize_settle_timer.start()
        if hasattr(self, "random_ambient") and self.random_ambient.geometry() != self.random_page.rect():
            self.random_ambient.setGeometry(self.random_page.rect())
        if hasattr(self, "detail_ambient") and self.detail_ambient.geometry() != self.detail_page.rect():
            self.detail_ambient.setGeometry(self.detail_page.rect())
        self._position_detail_video_navigation()

    def _finish_resize_settle(self) -> None:
        """Apply costly view reflows once the user finishes resizing."""
        if not self.isVisible():
            self._resize_in_progress = False
            return
        if hasattr(self, "gallery_status") and self.gallery_status.isVisible():
            width = min(820, max(280, self.gallery_page.width() - 40))
            self.gallery_status.setFixedWidth(width)
            self.gallery_status.adjustSize()
            height = min(110, max(42, self.gallery_status.sizeHint().height()))
            self.gallery_status.setGeometry((self.gallery_page.width() - width) // 2, 12, width, height)
            self._update_gallery_notice_mask()
        current_page = self.pages.currentWidget()
        current_post = None
        if current_page is self.random_page:
            current_post = self.random_post
        elif current_page is self.detail_page:
            current_post = self.detail_post
        video_page = current_post is not None and current_post.media_type == "video"
        image_page = current_page in (self.random_page, self.detail_page)
        if image_page and not (self._fullscreen_active and video_page):
            self._refresh_ambient_for_page(current_page, fast=True)
            if not video_page:
                if current_page is self.random_page:
                    self.random_image._fit_to_viewport_async(fast=False)
                else:
                    self.detail_image._fit_to_viewport_async(fast=False)
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
        self._resize_in_progress = False
