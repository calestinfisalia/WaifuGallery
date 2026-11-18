from pathlib import Path
from urllib.parse import urlparse

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
from .dialog_chrome import FramelessResizableDialog, create_minimize_button
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
        sort_button = QPushButton()
        icon = icon_factory("filter") if callable(icon_factory) else QIcon(
            str(Path(__file__).resolve().parent.parent / "assets" / "filter.svg")
        )
        sort_button.setIcon(icon)
        sort_button.setIconSize(QSize(16, 16))
        sort_button.setObjectName("favoritesSortButton")
        sort_button.setFixedSize(30, 30)
        sort_button.setToolTip("Filter and sort favorites")
        sort_button.setAccessibleName("Filter and sort favorites")
        sort_button.clicked.connect(dialog._show_sort_menu)
        layout.addWidget(sort_button)
        self.sort_button = sort_button
        layout.addWidget(create_minimize_button(dialog, "Favorites"))
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
    _TILE_BUILD_BATCH_SIZE = 16

    thumbnailRequested = Signal(str)
    downloadRequested = Signal(str)
    deleteSelectedRequested = Signal(object)
    downloadSelectedRequested = Signal(object)
    sortOrderChanged = Signal(str)
    mediaFilterChanged = Signal(str)

    def __init__(
        self,
        posts: list[ImagePost],
        open_post,
        remove_post,
        parent=None,
        sort_order: str = "newest",
        media_filter: str = "all",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("favoritesDialog")
        self.setWindowTitle("Favorites")
        self.setWindowIcon(parent.windowIcon() if parent else QIcon())
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(820, 620)
        self.sort_order = sort_order if sort_order in {"newest", "oldest"} else "newest"
        self.media_filter = media_filter if media_filter in {"all", "image", "video", "png"} else "all"
        self.all_posts = list(posts)
        self.posts = self._ordered_posts(self._filtered_posts())
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
        self._layout_columns = 0
        self._layout_tile_size: QSize | None = None
        self._layout_tile_count = 0
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.setInterval(16)
        self._layout_timer.timeout.connect(self._layout_tiles_after_resize)
        self._thumbnail_timer = QTimer(self)
        self._thumbnail_timer.setSingleShot(True)
        self._thumbnail_timer.setInterval(50)
        self._thumbnail_timer.timeout.connect(self._request_visible_thumbnails)
        self._tile_build_timer = QTimer(self)
        self._tile_build_timer.setSingleShot(True)
        self._tile_build_timer.setInterval(1)
        self._tile_build_timer.timeout.connect(self._build_next_tile_batch)
        self._pending_tile_posts: list[ImagePost] = []
        self._next_tile_index = 0

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
        self.sort_button = title_bar.sort_button
        layout.addWidget(title_bar)
        self.count_label = QLabel()
        self.count_label.setObjectName("favoritesCountLabel")
        self.count_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

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
        self.loading_indicator = CircularProgressIndicator(
            self.scroll.viewport(), size=36
        )
        self.loading_indicator.setObjectName("favoritesLoadingIndicator")
        self.loading_indicator.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.loading_indicator.hide()
        layout.addWidget(self.scroll, 1)
        self.footer = QWidget(surface)
        self.footer.setObjectName("favoritesFooter")
        footer = QHBoxLayout(self.footer)
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addWidget(self.count_label)
        footer.addStretch(1)
        footer.addWidget(QSizeGrip(surface))
        layout.addWidget(self.footer)
        outer.addWidget(surface)
        self._rebuild()

    def _ordered_posts(self, posts: list[ImagePost]) -> list[ImagePost]:
        ordered = list(posts)
        if self.sort_order == "newest":
            ordered.reverse()
        return ordered

    def _filtered_posts(self) -> list[ImagePost]:
        if self.media_filter == "video":
            return [post for post in self.all_posts if post.media_type == "video"]
        if self.media_filter in {"image", "png"}:
            posts = [post for post in self.all_posts if post.media_type != "video"]
            if self.media_filter == "png":
                posts = [
                    post for post in posts
                    if "transparent_png" in {tag.casefold() for tag in post.tags}
                    and urlparse(post.image_url).path.casefold().endswith(".png")
                ]
            return posts
        return list(self.all_posts)

    def set_posts(self, posts: list[ImagePost]) -> None:
        self.all_posts = list(posts)
        self.posts = self._ordered_posts(self._filtered_posts())
        self._rebuild()

    def _set_media_filter(self, media_filter: str) -> None:
        if media_filter not in {"all", "image", "video", "png"} or media_filter == self.media_filter:
            return
        self.media_filter = media_filter
        self.posts = self._ordered_posts(self._filtered_posts())
        self._rebuild()
        self.mediaFilterChanged.emit(media_filter)

    def _set_sort_order(self, sort_order: str) -> None:
        if sort_order not in {"newest", "oldest"} or sort_order == self.sort_order:
            return
        self.sort_order = sort_order
        self.posts.reverse()
        self._rebuild()
        self.sortOrderChanged.emit(sort_order)

    def _show_sort_menu(self) -> None:
        menu = QMenu(self)
        media_menu = menu.addMenu("Media type")
        media_actions = {}
        for label, value in (("Show All", "all"), ("Image Only", "image"), ("Video Only", "video"), ("PNG Only", "png")):
            action = media_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.media_filter == value)
            media_actions[action] = value
        menu.addSeparator()
        menu.addSection("Time")
        newest = menu.addAction("Newest first")
        newest.setCheckable(True)
        newest.setChecked(self.sort_order == "newest")
        oldest = menu.addAction("Oldest first")
        oldest.setCheckable(True)
        oldest.setChecked(self.sort_order == "oldest")
        selected = menu.exec(self.sort_button.mapToGlobal(
            QPoint(0, self.sort_button.height())
        ))
        if selected == newest:
            self._set_sort_order("newest")
        elif selected == oldest:
            self._set_sort_order("oldest")
        elif selected in media_actions:
            self._set_media_filter(media_actions[selected])

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._layout_timer.isActive():
            self._layout_timer.start()
        self._position_loading_indicator()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.content.isVisible() and not self._pending_tile_posts:
            self._thumbnail_timer.start(0)
        if self._pending_tile_posts:
            self._tile_build_timer.start(0)

    def _schedule_thumbnail_scan(self, *_args) -> None:
        self._thumbnail_timer.start()

    def _rebuild(self) -> None:
        self._tile_build_timer.stop()
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
        self._layout_columns = 0
        self._layout_tile_size = None
        self._layout_tile_count = 0
        videos = sum(post.media_type == "video" for post in self.posts)
        images = len(self.posts) - videos
        self.count_label.setText(
            f"{len(self.posts)} media · {images} images · {videos} videos"
        )
        self.empty_label.setVisible(not self.posts)
        self.empty_label.setText(
            "No favorite images yet." if not self.all_posts else "No favorites match the current filters."
        )
        self.scroll.setVisible(bool(self.posts))

        self._pending_tile_posts = list(self.posts)
        self._next_tile_index = 0
        self.content.hide()
        self.loading_indicator.setVisible(bool(self._pending_tile_posts))
        self.loading_indicator.set_active(bool(self._pending_tile_posts))
        self._position_loading_indicator()
        if 0 < len(self._pending_tile_posts) <= self._TILE_BUILD_BATCH_SIZE:
            for post in self._pending_tile_posts:
                self._create_favorite_tile(post)
            self._pending_tile_posts.clear()
            self.content.show()
            self.loading_indicator.set_active(False)
            self.loading_indicator.hide()
            self._layout_tiles()
            self.grid.invalidate()
            self.grid.activate()
        elif self._pending_tile_posts and self.isVisible():
            self._tile_build_timer.start(0)
        elif not self._pending_tile_posts:
            self._update_selection_toolbar()

    def _build_next_tile_batch(self) -> None:
        if not self.isVisible() or not self._pending_tile_posts:
            return
        end = min(
            self._next_tile_index + self._TILE_BUILD_BATCH_SIZE,
            len(self._pending_tile_posts),
        )
        for post in self._pending_tile_posts[self._next_tile_index:end]:
            self._create_favorite_tile(post)
        self._next_tile_index = end
        if end < len(self._pending_tile_posts):
            self._tile_build_timer.start()
            return
        self._pending_tile_posts.clear()
        self._next_tile_index = 0
        self._layout_tiles()
        self.content.show()
        self.grid.invalidate()
        self.grid.activate()
        self.loading_indicator.set_active(False)
        self.loading_indicator.hide()
        self._thumbnail_timer.start()

    def _create_favorite_tile(self, post: ImagePost) -> None:
        preview_area = QWidget()
        preview_area.setMinimumSize(160, 180)
        preview_area.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        preview = QPushButton(preview_area)
        preview.setObjectName("previewImage")
        key = favorite_key(post)
        preview.setProperty(
            "favoritesThumbnailPending",
            key not in self.thumbnail_cache and key not in self.thumbnail_errors,
        )
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

    def _position_loading_indicator(self) -> None:
        if not hasattr(self, "loading_indicator"):
            return
        viewport = self.scroll.viewport()
        self.loading_indicator.move(
            max(0, (viewport.width() - self.loading_indicator.width()) // 2),
            max(0, (viewport.height() - self.loading_indicator.height()) // 2),
        )

    def _layout_tiles(self) -> None:
        self._layout_tiles_impl(update_toolbar=True)

    def _layout_tiles_after_resize(self) -> None:
        self._layout_tiles_impl(update_toolbar=False)

    def _layout_tiles_impl(self, *, update_toolbar: bool) -> None:
        if self._pending_tile_posts:
            return
        if not self.tiles:
            if update_toolbar:
                self._update_selection_toolbar()
            return
        spacing = self.grid.spacing()
        available = max(160, self.scroll.viewport().width() - 8)
        columns = max(1, (available + spacing) // (180 + spacing))
        tile_width = max(160, (available - spacing * (columns - 1)) // columns)
        tile_height = max(180, round(tile_width * 205 / 180))
        tile_size = QSize(tile_width, tile_height)
        columns_changed = columns != self._layout_columns
        size_changed = tile_size != self._layout_tile_size
        count_changed = len(self.tiles) != self._layout_tile_count
        if not (columns_changed or size_changed or count_changed):
            return

        if columns_changed or count_changed:
            while self.grid.count():
                self.grid.takeAt(0)
        for index, (key, tile) in enumerate(self.tiles):
            if tile.minimumSize() != tile_size or tile.maximumSize() != tile_size:
                tile.setFixedSize(tile_size)
            preview = self.thumbnail_buttons[key]
            preview_geometry = QRect(0, 0, tile_width, tile_height)
            if preview.geometry() != preview_geometry:
                preview.setGeometry(preview_geometry)
            icon_size = QSize(tile_width - 10, tile_height - 10)
            if preview.iconSize() != icon_size:
                preview.setIconSize(icon_size)
            indicator = self.thumbnail_indicators.get(key)
            if indicator:
                indicator_position = QPoint(
                    (tile_width - indicator.width()) // 2,
                    (tile_height - indicator.height()) // 2,
                )
                if indicator.pos() != indicator_position:
                    indicator.move(indicator_position)
                    indicator.raise_()
            play_badge = self.play_badges.get(key)
            if play_badge:
                badge_position = QPoint(
                    (tile_width - play_badge.width()) // 2,
                    (tile_height - play_badge.height()) // 2,
                )
                if play_badge.pos() != badge_position:
                    play_badge.move(badge_position)
                    if key in self.thumbnail_cache:
                        play_badge.raise_()
            error_view = self.thumbnail_error_views.get(key)
            if error_view:
                if error_view.geometry() != preview_geometry:
                    error_view.setGeometry(preview_geometry)
                    error_view.raise_()
            if columns_changed or count_changed:
                self.grid.addWidget(tile, index // columns, index % columns)
            remove_geometry = QRect(tile_width - 40, 8, 32, 32)
            remove_button = self.remove_buttons[key]
            if remove_button.geometry() != remove_geometry:
                remove_button.setGeometry(remove_geometry)
                remove_button.raise_()
        self._layout_columns = columns
        self._layout_tile_size = tile_size
        self._layout_tile_count = len(self.tiles)
        if update_toolbar:
            self._update_selection_toolbar()
        if self.content.isVisible() and not self._pending_tile_posts:
            self._thumbnail_timer.start()

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
        if selected and BackupMessageDialog.ask(
            self,
            "Download selected favorites",
            f"Add all {len(selected)} selected media to the download queue?",
            ("No", "Yes"),
            default_button="No",
        ) == "Yes":
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
        if not self.isVisible() or not self.content.isVisible():
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
            button.setProperty("favoritesThumbnailPending", False)
            button.style().unpolish(button)
            button.style().polish(button)
            button.setToolTip("")
            button.setText("")
            button.setIcon(QIcon(pixmap))
            button.update()
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
            button.setProperty("favoritesThumbnailPending", False)
            button.style().unpolish(button)
            button.style().polish(button)
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
