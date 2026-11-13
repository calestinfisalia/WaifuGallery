from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from ..models import ImagePost
from .backup_prompts import BackupMessageDialog
from .dialog_chrome import FramelessResizableDialog
from .indicators import CircularProgressIndicator
from .scrollbars import CAPSULE_SCROLLBAR_STYLE


def favorite_key(post: ImagePost) -> str:
    return f"{post.provider}:{post.post_id}"


class FavoritesTitleBar(QWidget):
    def __init__(self, dialog: QDialog) -> None:
        super().__init__(dialog)
        self._drag_offset = None
        self.setObjectName("favoritesTitleBar")
        self.setFixedHeight(38)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(8)
        title = QLabel("Favorites")
        title.setObjectName("favoritesWindowTitle")
        layout.addWidget(title)
        self.selection_count_label = QLabel("0 selected")
        self.selection_count_label.setObjectName("favoritesSelectionCount")
        self.selection_count_label.setVisible(False)
        layout.addWidget(self.selection_count_label)
        layout.addStretch(1)
        select_all = QPushButton()
        icon_factory = getattr(dialog.parent(), "_icon", None)
        icon = icon_factory("select-all") if callable(icon_factory) else QIcon(
            str(Path(__file__).resolve().parent.parent / "assets" / "select-all.svg")
        )
        select_all.setIcon(icon)
        select_all.setIconSize(QSize(16, 16))
        select_all.setObjectName("favoritesSelectAllButton")
        select_all.setFixedSize(30, 30)
        select_all.setCheckable(True)
        select_all.setToolTip("Select all favorites")
        select_all.setAccessibleName("Select all favorites")
        select_all.setVisible(False)
        select_all.clicked.connect(dialog._select_all_favorites)
        layout.addWidget(select_all)
        self.select_all_button = select_all
        delete_selected = QPushButton()
        icon = icon_factory("archive") if callable(icon_factory) else QIcon(
            str(Path(__file__).resolve().parent.parent / "assets" / "archive.svg")
        )
        delete_selected.setIcon(icon)
        delete_selected.setIconSize(QSize(16, 16))
        delete_selected.setObjectName("favoritesDeleteSelectedButton")
        delete_selected.setFixedSize(30, 30)
        delete_selected.setToolTip("Delete selected favorites")
        delete_selected.setAccessibleName("Delete selected favorites")
        delete_selected.setVisible(False)
        delete_selected.clicked.connect(dialog._delete_selected_favorites)
        layout.addWidget(delete_selected)
        self.delete_selected_button = delete_selected
        download_selected = QPushButton()
        icon = icon_factory("download") if callable(icon_factory) else QIcon(
            str(Path(__file__).resolve().parent.parent / "assets" / "download.svg")
        )
        download_selected.setIcon(icon)
        download_selected.setIconSize(QSize(16, 16))
        download_selected.setObjectName("favoritesDownloadSelectedButton")
        download_selected.setFixedSize(30, 30)
        download_selected.setToolTip("Download selected favorites")
        download_selected.setAccessibleName("Download selected favorites")
        download_selected.setVisible(False)
        download_selected.clicked.connect(dialog._download_selected_favorites)
        layout.addWidget(download_selected)
        self.download_selected_button = download_selected
        close = QPushButton()
        icon_factory = getattr(dialog.parent(), "_icon", None)
        icon = icon_factory("close") if callable(icon_factory) else QIcon(
            str(Path(__file__).resolve().parent.parent / "assets" / "close.svg")
        )
        close.setIcon(icon)
        close.setIconSize(QSize(16, 16))
        close.setObjectName("favoritesCloseButton")
        close.setFixedSize(30, 30)
        close.setToolTip("Close favorites")
        close.setAccessibleName("Close favorites")
        close.clicked.connect(dialog.reject)
        layout.addWidget(close)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle and handle.startSystemMove():
                event.accept()
                return
            self._drag_offset = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class FavoritesDialog(FramelessResizableDialog):
    thumbnailRequested = Signal(str)
    downloadRequested = Signal(str)
    deleteSelectedRequested = Signal(object)
    downloadSelectedRequested = Signal(object)

    def __init__(self, posts: list[ImagePost], open_post, remove_post, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("favoritesDialog")
        self.setWindowTitle("Favorites")
        self.setWindowIcon(parent.windowIcon() if parent else QIcon())
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(820, 620)
        self.posts = list(posts)
        self._open_post = open_post
        self._remove_post = remove_post
        self._selection_mode = False
        self._selected_favorites: set[str] = set()
        self.thumbnail_buttons: dict[str, QPushButton] = {}
        self.thumbnail_indicators: dict[str, CircularProgressIndicator] = {}
        self.remove_buttons: dict[str, QPushButton] = {}
        self.selection_checks: dict[str, QCheckBox] = {}
        self.play_badges: dict[str, QLabel] = {}
        self.tiles: list[tuple[str, QWidget]] = []
        self.thumbnail_cache: dict[str, QPixmap] = {}
        self.thumbnail_errors: set[str] = set()
        self.thumbnail_error_details: dict[str, str] = {}
        self.thumbnail_error_views: dict[str, QWidget] = {}
        self.thumbnail_error_labels: dict[str, QLabel] = {}
        self._thumbnail_requested: set[str] = set()
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.setInterval(55)
        self._layout_timer.timeout.connect(self._layout_tiles)
        self._thumbnail_timer = QTimer(self)
        self._thumbnail_timer.setSingleShot(True)
        self._thumbnail_timer.setInterval(50)
        self._thumbnail_timer.timeout.connect(self._request_visible_thumbnails)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("favoritesSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(4)
        title_bar = FavoritesTitleBar(self)
        self.selection_count_label = title_bar.selection_count_label
        self.select_all_button = title_bar.select_all_button
        self.delete_selected_button = title_bar.delete_selected_button
        self.download_selected_button = title_bar.download_selected_button
        layout.addWidget(title_bar)
        header = QHBoxLayout()
        self.count_label = QLabel()
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addStretch(1)
        header.addWidget(self.count_label)
        header.addStretch(1)
        layout.addLayout(header)

        self.empty_label = QLabel("No favorite images yet.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setObjectName("favoritesScrollArea")
        self.scroll.verticalScrollBar().setObjectName("favoritesVerticalScrollBar")
        self.scroll.horizontalScrollBar().setObjectName("favoritesHorizontalScrollBar")
        self.scroll.verticalScrollBar().setStyleSheet(CAPSULE_SCROLLBAR_STYLE)
        self.scroll.verticalScrollBar().valueChanged.connect(self._schedule_thumbnail_scan)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll, 1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(QSizeGrip(surface))
        layout.addLayout(footer)
        outer.addWidget(surface)
        self._rebuild()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_timer.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._thumbnail_timer.start(0)

    def _schedule_thumbnail_scan(self, *_args) -> None:
        self._thumbnail_timer.start()

    def _rebuild(self) -> None:
        self._selected_favorites.intersection_update(
            favorite_key(post) for post in self.posts
        )
        if self._selection_mode and not self._selected_favorites:
            self._set_selection_mode(False)
        self._thumbnail_requested.intersection_update(
            favorite_key(post) for post in self.posts
        )
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.thumbnail_buttons.clear()
        self.thumbnail_indicators.clear()
        self.thumbnail_error_views.clear()
        self.thumbnail_error_labels.clear()
        self.remove_buttons.clear()
        self.selection_checks.clear()
        self.play_badges.clear()
        self.tiles.clear()
        videos = sum(post.media_type == "video" for post in self.posts)
        images = len(self.posts) - videos
        self.count_label.setText(
            f"{len(self.posts)} media · {images} images · {videos} videos"
        )
        self.empty_label.setVisible(not self.posts)
        self.scroll.setVisible(bool(self.posts))

        for post in self.posts:
            preview_area = QWidget()
            preview_area.setMinimumSize(160, 180)
            preview_area.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            preview = QPushButton(preview_area)
            preview.setObjectName("previewImage")
            key = favorite_key(post)
            preview.clicked.connect(
                lambda _checked=False, item=post, favorite_id=key:
                self._activate_favorite(item, favorite_id)
            )
            preview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            preview.customContextMenuRequested.connect(
                lambda position, favorite_id=key, button=preview:
                self._show_favorite_context_menu(
                    favorite_id, button.mapToGlobal(position)
                )
            )
            self.thumbnail_buttons[key] = preview
            if key not in self.thumbnail_cache and key not in self.thumbnail_errors:
                indicator = CircularProgressIndicator(preview_area, size=28)
                indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                indicator.set_active(key in self._thumbnail_requested)
                self.thumbnail_indicators[key] = indicator
            if post.media_type == "video":
                play_badge = QLabel(preview_area)
                icon_factory = getattr(self.parent(), "_icon", None)
                play_icon = (
                    icon_factory("play")
                    if callable(icon_factory)
                    else QIcon(str(Path(__file__).resolve().parent.parent / "assets" / "play.svg"))
                )
                play_badge.setPixmap(play_icon.pixmap(QSize(22, 22)))
                play_badge.setFixedSize(46, 46)
                play_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                play_badge.setStyleSheet(
                    "background: rgba(16, 17, 24, 190); border-radius: 23px; padding: 12px;"
                )
                play_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                play_badge.setVisible(key in self.thumbnail_cache)
                self.play_badges[key] = play_badge
            selection_check = QCheckBox(preview_area)
            selection_check.setObjectName("favoritesChecklistCheckBox")
            selection_check.setFixedSize(28, 28)
            selection_check.setToolTip("Select image")
            selection_check.setAccessibleName(f"Select {post.provider} favorite {post.post_id}")
            selection_check.setChecked(key in self._selected_favorites)
            selection_check.setVisible(self._selection_mode)
            selection_check.toggled.connect(
                lambda checked, favorite_id=key:
                self._set_favorite_selected(favorite_id, checked)
            )
            self.selection_checks[key] = selection_check
            remove = QPushButton(preview_area)
            remove.setObjectName("favoriteRemoveButton")
            remove.setIcon(QIcon(str(Path(__file__).resolve().parent.parent / "assets" / "heart-filled.svg")))
            remove.setIconSize(QSize(18, 18))
            remove.resize(32, 32)
            remove.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            remove.setToolTip("Remove from favorites")
            remove.clicked.connect(lambda _checked=False, post_key=key: self._confirm_remove(post_key))
            remove.raise_()
            self.remove_buttons[key] = remove
            self.tiles.append((key, preview_area))
            if key in self.thumbnail_cache:
                preview.setText("")
                preview.setIcon(QIcon(self.thumbnail_cache[key]))
            elif key in self.thumbnail_errors:
                preview.setToolTip(
                    self.thumbnail_error_details.get(key, "Preview could not be loaded.")
                )
                self._create_thumbnail_error_view(preview_area, key)
        self._layout_tiles()

    def _layout_tiles(self) -> None:
        if not self.tiles:
            self._update_selection_toolbar()
            return
        spacing = self.grid.spacing()
        available = max(160, self.scroll.viewport().width() - 8)
        columns = max(1, (available + spacing) // (180 + spacing))
        tile_width = max(160, (available - spacing * (columns - 1)) // columns)
        tile_height = max(180, round(tile_width * 205 / 180))

        while self.grid.count():
            self.grid.takeAt(0)
        for index, (key, tile) in enumerate(self.tiles):
            tile.setFixedSize(tile_width, tile_height)
            preview = self.thumbnail_buttons[key]
            preview.setGeometry(0, 0, tile_width, tile_height)
            preview.setIconSize(QSize(tile_width - 10, tile_height - 10))
            indicator = self.thumbnail_indicators.get(key)
            if indicator:
                indicator.move(
                    (tile_width - indicator.width()) // 2,
                    (tile_height - indicator.height()) // 2,
                )
                indicator.raise_()
            play_badge = self.play_badges.get(key)
            if play_badge:
                play_badge.move((tile_width - play_badge.width()) // 2, (tile_height - play_badge.height()) // 2)
                if key in self.thumbnail_cache:
                    play_badge.raise_()
            error_view = self.thumbnail_error_views.get(key)
            if error_view:
                error_view.setGeometry(0, 0, tile_width, tile_height)
                error_view.raise_()
            selection_check = self.selection_checks[key]
            selection_check.move(8, 8)
            selection_check.setVisible(self._selection_mode)
            if self._selection_mode:
                selection_check.raise_()
            self.remove_buttons[key].setGeometry(tile_width - 40, 8, 32, 32)
            self.remove_buttons[key].raise_()
            self.grid.addWidget(tile, index // columns, index % columns)
        self._update_selection_toolbar()
        self._thumbnail_timer.start(0)

    def _activate_favorite(self, post: ImagePost, key: str) -> None:
        if self._selection_mode:
            self._set_favorite_selected(key, key not in self._selected_favorites)
        else:
            self._open_post(post)

    def _show_favorite_context_menu(self, key: str, position: QPoint) -> None:
        menu = QMenu(self)
        download_action = menu.addAction("Download")
        checklist_action = menu.addAction(
            "Deselect image"
            if key in self._selected_favorites
            else "Select image"
        )
        remove_action = menu.addAction("Remove from favorites")
        selected_action = menu.exec(position)
        if selected_action == download_action:
            self.downloadRequested.emit(key)
        elif selected_action == checklist_action:
            self._set_selection_mode(True)
            self._set_favorite_selected(
                key, key not in self._selected_favorites
            )
        elif selected_action == remove_action:
            self._confirm_remove(key)

    def _set_selection_mode(self, enabled: bool) -> None:
        self._selection_mode = enabled
        if not enabled:
            self._selected_favorites.clear()
        for checkbox in self.selection_checks.values():
            checkbox.setVisible(enabled)
        self._update_selection_toolbar()

    def _set_favorite_selected(self, key: str, selected: bool) -> None:
        if selected:
            self._selected_favorites.add(key)
        else:
            self._selected_favorites.discard(key)
            if not self._selected_favorites:
                self._set_selection_mode(False)
                return
        self._update_selection_toolbar()

    def _select_all_favorites(self, selected: bool) -> None:
        if selected:
            self._set_selection_mode(True)
            self._selected_favorites = {
                favorite_key(post) for post in self.posts
            }
        else:
            self._set_selection_mode(False)
            return
        self._update_selection_toolbar()

    def _selected_favorite_keys(self) -> list[str]:
        return [
            favorite_key(post)
            for post in self.posts
            if favorite_key(post) in self._selected_favorites
        ]

    def _update_selection_toolbar(self) -> None:
        selected = self._selected_favorite_keys()
        total = len(self.posts)
        all_selected = total > 0 and len(selected) == total
        self.select_all_button.setEnabled(total > 0)
        self.select_all_button.setToolTip(
            "Clear selection" if all_selected else "Select all favorites"
        )
        self.select_all_button.setAccessibleName(
            "Clear selection" if all_selected else "Select all favorites"
        )
        blocked = self.select_all_button.blockSignals(True)
        self.select_all_button.setChecked(all_selected)
        self.select_all_button.blockSignals(blocked)
        for key, checkbox in self.selection_checks.items():
            is_selected = key in self._selected_favorites
            checkbox.setToolTip(
                "Deselect image" if is_selected else "Select image"
            )
            if checkbox.isChecked() != is_selected:
                blocked = checkbox.blockSignals(True)
                checkbox.setChecked(is_selected)
                checkbox.blockSignals(blocked)
        self.selection_count_label.setText(f"{len(selected)} selected")
        has_selection = self._selection_mode and bool(selected)
        self.selection_count_label.setVisible(has_selection)
        self.select_all_button.setVisible(has_selection)
        self.delete_selected_button.setVisible(has_selection)
        self.download_selected_button.setVisible(has_selection)

    def _delete_selected_favorites(self) -> None:
        selected = self._selected_favorite_keys()
        if not selected:
            return
        if BackupMessageDialog.confirm(
            self,
            "Remove selected favorites",
            f"Remove {len(selected)} selected media from your favorites?",
        ):
            self.deleteSelectedRequested.emit(selected)

    def _download_selected_favorites(self) -> None:
        selected = self._selected_favorite_keys()
        if selected:
            self.downloadSelectedRequested.emit(selected)

    @staticmethod
    def _thumbnail_error_summary(error: str) -> str:
        message = error.casefold()
        if "timeout" in message or "timed out" in message:
            return "Timeout"
        if any(value in message for value in ("dns", "connection", "network", "tls", "ssl")):
            return "Network error"
        if "http " in message or "server" in message:
            return "Server error"
        if "image" in message or "format" in message:
            return "Invalid media"
        return "Unavailable"

    def _create_thumbnail_error_view(self, area: QWidget, post_id: str) -> QWidget:
        view = QWidget(area)
        view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        details = self.thumbnail_error_details.get(post_id, "Preview could not be loaded.")
        view.setToolTip(details)
        layout = QVBoxLayout(view)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)
        layout.addStretch(1)
        icon = QLabel("!")
        icon.setObjectName("favoriteThumbnailErrorIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_font = icon.font()
        icon_font.setPointSize(30)
        icon_font.setBold(True)
        icon.setFont(icon_font)
        layout.addWidget(icon)
        message = QLabel(self._thumbnail_error_summary(details))
        message.setObjectName("favoriteThumbnailErrorMessage")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)
        message.setToolTip(details)
        self.thumbnail_error_views[post_id] = view
        self.thumbnail_error_labels[post_id] = message
        layout.addWidget(message)
        layout.addStretch(1)
        return view

    def _request_visible_thumbnails(self) -> None:
        if not self.isVisible():
            return
        viewport = self.scroll.viewport()
        if viewport.width() <= 0 or viewport.height() <= 0:
            return
        prefetch_height = self.tiles[0][1].height() if self.tiles else 0
        visible_area = viewport.rect().adjusted(0, 0, 0, prefetch_height)
        for key, tile in self.tiles:
            if (
                key in self.thumbnail_cache
                or key in self.thumbnail_errors
                or key in self._thumbnail_requested
            ):
                continue
            tile_rect = QRect(tile.mapTo(viewport, QPoint(0, 0)), tile.size())
            if not visible_area.intersects(tile_rect):
                continue
            self._thumbnail_requested.add(key)
            indicator = self.thumbnail_indicators.get(key)
            if indicator:
                indicator.set_active(True)
            self.thumbnailRequested.emit(key)

    def _confirm_remove(self, post_id: str) -> None:
        confirmed = BackupMessageDialog.confirm(
            self,
            "Remove favorite",
            "Remove this image from your favorites?",
        )
        if confirmed:
            self._remove_post(post_id)

    def set_thumbnail(self, post_id: str, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        self._thumbnail_requested.discard(post_id)
        self.thumbnail_cache[post_id] = pixmap
        self.thumbnail_errors.discard(post_id)
        self.thumbnail_error_details.pop(post_id, None)
        error_view = self.thumbnail_error_views.pop(post_id, None)
        self.thumbnail_error_labels.pop(post_id, None)
        if error_view:
            error_view.deleteLater()
        button = self.thumbnail_buttons.get(post_id)
        indicator = self.thumbnail_indicators.get(post_id)
        if indicator:
            indicator.set_active(False)
        if button:
            button.setToolTip("")
            button.setText("")
            button.setIcon(QIcon(pixmap))
        play_badge = self.play_badges.get(post_id)
        if play_badge:
            play_badge.show()

    def set_thumbnail_error(self, post_id: str, error: str = "") -> None:
        self._thumbnail_requested.discard(post_id)
        self.thumbnail_errors.add(post_id)
        details = error.strip() or "Preview could not be loaded."
        self.thumbnail_error_details[post_id] = details
        indicator = self.thumbnail_indicators.get(post_id)
        if indicator:
            indicator.set_active(False)
        error_view = self.thumbnail_error_views.get(post_id)
        if error_view is None:
            area = next((tile for key, tile in self.tiles if key == post_id), None)
            if area:
                error_view = self._create_thumbnail_error_view(area, post_id)
                error_view.setGeometry(area.rect())
                error_view.raise_()
        message = self.thumbnail_error_labels.get(post_id)
        if message:
            message.setText(self._thumbnail_error_summary(details))
            message.setToolTip(details)
        button = self.thumbnail_buttons.get(post_id)
        if button:
            button.setToolTip(details)
        if error_view:
            error_view.setToolTip(details)
        play_badge = self.play_badges.get(post_id)
        if play_badge:
            play_badge.hide()

    def remove_favorite(self, post_id: str) -> None:
        self.posts = [post for post in self.posts if favorite_key(post) != post_id]
        self.thumbnail_cache.pop(post_id, None)
        self.thumbnail_errors.discard(post_id)
        self.thumbnail_error_details.pop(post_id, None)
        self._thumbnail_requested.discard(post_id)
        self._rebuild()
