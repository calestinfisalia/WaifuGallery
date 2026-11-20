from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QPushButton,
    QSizeGrip,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
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


class FavoritesModel(QAbstractListModel):
    KEY_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    POST_ROLE = int(Qt.ItemDataRole.UserRole) + 2

    def __init__(self, dialog, parent=None) -> None:
        super().__init__(parent)
        self.dialog = dialog
        self.posts: list[ImagePost] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.posts)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.posts):
            return None
        post = self.posts[index.row()]
        if role == self.KEY_ROLE:
            return favorite_key(post)
        if role == self.POST_ROLE:
            return post
        return None

    def set_posts(self, posts: list[ImagePost]) -> None:
        self.beginResetModel()
        self.posts = list(posts)
        self.endResetModel()


class FavoritesDelegate(QStyledItemDelegate):
    def __init__(self, dialog, parent=None) -> None:
        super().__init__(parent)
        self.dialog = dialog
        self.heart_icon = QIcon(
            str(Path(__file__).resolve().parent.parent / "assets" / "heart-filled.svg")
        )
        icon_factory = getattr(dialog.parent(), "_icon", None)
        self.play_icon = icon_factory("play") if callable(icon_factory) else QIcon(
            str(Path(__file__).resolve().parent.parent / "assets" / "play.svg")
        )

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        dialog = self.dialog
        key = index.data(FavoritesModel.KEY_ROLE)
        post = index.data(FavoritesModel.POST_ROLE)
        rect = option.rect.adjusted(3, 3, -3, -3)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(132, 136, 148, 42))
            painter.drawRoundedRect(rect, 8, 8)

        pixmap = dialog.thumbnail_cache.get(key)
        image_rect = rect.adjusted(3, 3, -3, -3)
        if pixmap is not None and not pixmap.isNull():
            source = pixmap.rect()
            fitted = QSize(source.size()).scaled(
                image_rect.size(), Qt.AspectRatioMode.KeepAspectRatio
            )
            target = QRect(
                image_rect.center().x() - fitted.width() // 2,
                image_rect.center().y() - fitted.height() // 2,
                fitted.width(),
                fitted.height(),
            )
            painter.setRenderHint(
                QPainter.RenderHint.SmoothPixmapTransform,
                not dialog._resize_in_progress,
            )
            painter.drawPixmap(target, pixmap, source)
            if post.media_type == "video":
                badge = QRect(target.center().x() - 23, target.center().y() - 23, 46, 46)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(option.palette.color(QPalette.ColorRole.Window).darker(140))
                painter.drawEllipse(badge)
                self.play_icon.paint(
                    painter,
                    badge.adjusted(12, 12, -12, -12),
                    Qt.AlignmentFlag.AlignCenter,
                )
        elif key in dialog.thumbnail_errors:
            painter.setPen(option.palette.color(QPalette.ColorRole.Text))
            painter.drawText(
                image_rect,
                Qt.AlignmentFlag.AlignCenter,
                f"!\n{dialog._thumbnail_error_summary(dialog.thumbnail_error_details.get(key, 'Unavailable'))}",
            )
        else:
            painter.setPen(option.palette.color(QPalette.ColorRole.Mid))
            painter.drawText(image_rect, Qt.AlignmentFlag.AlignCenter, "···")

        self.heart_icon.paint(
            painter,
            QRect(rect.right() - 23, rect.top() + 4, 20, 20),
            Qt.AlignmentFlag.AlignCenter,
        )
        if dialog._selection_mode:
            check_rect = QRect(rect.left() + 7, rect.top() + 7, 22, 22)
            painter.setPen(option.palette.color(QPalette.ColorRole.Mid))
            painter.setBrush(option.palette.color(QPalette.ColorRole.Window))
            painter.drawRoundedRect(check_rect, 4, 4)
            if key in dialog._selected_favorites:
                painter.setPen(option.palette.color(QPalette.ColorRole.HighlightedText))
                painter.drawText(check_rect, Qt.AlignmentFlag.AlignCenter, "✓")
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return self.dialog.grid_size


class FavoritesGridView(QListView):
    favoriteActivated = Signal(str)
    removeRequested = Signal(str)
    selectionToggleRequested = Signal(str)
    contextRequested = Signal(str, QPoint)

    def __init__(self, dialog, parent=None) -> None:
        super().__init__(parent)
        self.dialog = dialog
        self.setObjectName("favoritesGridView")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        # Let the shared grid-size animation own reflow; QListView's automatic
        # adjust pass during native resize can otherwise race that animation.
        self.setResizeMode(QListView.ResizeMode.Fixed)
        self.setMovement(QListView.Movement.Static)
        self.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.setUniformItemSizes(True)
        # Cell widths cover the viewport; the delegate draws its own inset so
        # QListView spacing cannot leave an unused strip on the right edge.
        self.setSpacing(0)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(32)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    def mousePressEvent(self, event) -> None:
        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            super().mousePressEvent(event)
            return
        key = index.data(FavoritesModel.KEY_ROLE)
        if event.button() == Qt.MouseButton.RightButton:
            self.contextRequested.emit(key, event.globalPosition().toPoint())
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            rect = self.visualRect(index)
            point = event.position().toPoint()
            if QRect(rect.right() - 29, rect.top() + 1, 28, 28).contains(point):
                self.removeRequested.emit(key)
            elif self.dialog._selection_mode and QRect(
                rect.left() + 2, rect.top() + 2, 34, 34
            ).contains(point):
                self.selectionToggleRequested.emit(key)
            elif self.dialog._selection_mode:
                self.selectionToggleRequested.emit(key)
            else:
                self.favoriteActivated.emit(key)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        index = self.indexAt(event.position().toPoint())
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if index.isValid() else Qt.CursorShape.ArrowCursor
        )
        if index.isValid():
            key = index.data(FavoritesModel.KEY_ROLE)
            if key in self.dialog.thumbnail_errors:
                details = self.dialog.thumbnail_error_details.get(
                    key, "Preview could not be loaded."
                )
                self.setToolTip(
                    f"{self.dialog._thumbnail_error_summary(details)}: {details}"
                )
            else:
                self.setToolTip("Open favorite" if not self.dialog._selection_mode else "Select favorite")
        else:
            self.setToolTip("")
        super().mouseMoveEvent(event)


class FavoritesDialog(FramelessResizableDialog):
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
        self.setMinimumSize(640, 420)
        self.resize(820, 620)
        self.sort_order = sort_order if sort_order in {"newest", "oldest"} else "newest"
        self.media_filter = media_filter if media_filter in {"all", "image", "video", "png"} else "all"
        self.all_posts = list(posts)
        self.posts = self._ordered_posts(self._filtered_posts())
        self._open_post = open_post
        self._remove_post = remove_post
        self._selection_mode = False
        self._selected_favorites: set[str] = set()
        self.tiles: list[tuple[str, ImagePost]] = []
        self.thumbnail_cache: dict[str, QPixmap] = {}
        self.thumbnail_errors: set[str] = set()
        self.thumbnail_error_details: dict[str, str] = {}
        self._thumbnail_requested: set[str] = set()
        self._row_by_key: dict[str, int] = {}
        self._resize_in_progress = False
        self.grid_size = QSize(180, 205)
        self._target_grid_size = self.grid_size
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        # Keep the grid responsive while resizing, but cap expensive relayouts
        # to about 30 FPS instead of running for every native resize event.
        self._layout_timer.setInterval(33)
        self._layout_timer.timeout.connect(self._layout_tiles_after_resize)
        self._grid_animation_timer = QTimer(self)
        self._grid_animation_timer.setInterval(16)
        self._grid_animation_timer.timeout.connect(self._animate_grid_size)
        self._resize_settle_timer = QTimer(self)
        self._resize_settle_timer.setSingleShot(True)
        self._resize_settle_timer.setInterval(140)
        self._resize_settle_timer.timeout.connect(self._finish_resize)
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

        self.model = FavoritesModel(self, self)
        self.content = FavoritesGridView(self, surface)
        self.content.setModel(self.model)
        self.content.setItemDelegate(FavoritesDelegate(self, self.content))
        self.content.setGridSize(self.grid_size)
        self.content.setSpacing(12)
        self.content.setFrameShape(QFrame.Shape.NoFrame)
        self.content.setStyleSheet(
            "QListView#favoritesGridView { background: transparent; border: 0; }"
        )
        self.content.verticalScrollBar().setObjectName("favoritesVerticalScrollBar")
        self.content.horizontalScrollBar().setObjectName("favoritesHorizontalScrollBar")
        self.content.verticalScrollBar().setStyleSheet(CAPSULE_SCROLLBAR_STYLE)
        self.content.verticalScrollBar().valueChanged.connect(self._schedule_thumbnail_scan)
        self.content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content.favoriteActivated.connect(self._open_favorite_key)
        self.content.removeRequested.connect(self._confirm_remove)
        self.content.selectionToggleRequested.connect(self._toggle_favorite_selection)
        self.content.contextRequested.connect(self._show_favorite_context_menu)
        self.scroll = self.content
        self.loading_indicator = CircularProgressIndicator(
            self.scroll.viewport(), size=36
        )
        self.loading_indicator.setObjectName("favoritesLoadingIndicator")
        self.loading_indicator.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.loading_indicator.hide()
        layout.addWidget(self.content, 1)
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
        time_menu = menu.addMenu("Time")
        newest = time_menu.addAction("Newest first")
        newest.setCheckable(True)
        newest.setChecked(self.sort_order == "newest")
        oldest = time_menu.addAction("Oldest first")
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
        self._resize_in_progress = True
        self._resize_settle_timer.start()
        if not self._layout_timer.isActive():
            self._layout_timer.start()
        self._position_loading_indicator()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._layout_tiles_after_resize()
        if self.posts:
            self._thumbnail_timer.start(0)

    def _finish_resize(self) -> None:
        self._resize_in_progress = False
        self.content.viewport().update()

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
        self.tiles = [(favorite_key(post), post) for post in self.posts]
        self._row_by_key = {key: row for row, (key, _post) in enumerate(self.tiles)}
        self.model.set_posts(self.posts)
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
        self.content.setVisible(bool(self.posts))
        self.loading_indicator.hide()
        self.loading_indicator.set_active(False)
        self._layout_tiles()
        self._update_selection_toolbar()

    def _position_loading_indicator(self) -> None:
        if not hasattr(self, "loading_indicator"):
            return
        viewport = self.scroll.viewport()
        self.loading_indicator.move(
            max(0, (viewport.width() - self.loading_indicator.width()) // 2),
            max(0, (viewport.height() - self.loading_indicator.height()) // 2),
        )

    def _layout_tiles(self) -> None:
        self._layout_tiles_after_resize()

    def _layout_tiles_after_resize(self) -> None:
        available = max(180, self.content.viewport().width())
        columns = max(1, available // 180)
        tile_width = max(160, available // columns)
        tile_width = max(160, (tile_width // 8) * 8)
        tile_height = max(180, round(tile_width * 205 / 180))
        new_size = QSize(tile_width, tile_height)
        if new_size != self._target_grid_size:
            self._target_grid_size = new_size
            if not self._grid_animation_timer.isActive():
                self._grid_animation_timer.start()
        if self.posts and self.content.isVisible():
            self._thumbnail_timer.start()

    def _animate_grid_size(self) -> None:
        current_width = self.grid_size.width()
        target_width = self._target_grid_size.width()
        delta = target_width - current_width
        if abs(delta) <= 1:
            self.grid_size = self._target_grid_size
            self._grid_animation_timer.stop()
        else:
            # Ease the shared grid cell size toward the live window width.
            # QListView performs item positioning in Qt, while the delegate
            # paints visible thumbnails only, so there is no per-card widget
            # animation or Python layout loop.
            width = round(current_width + delta * 0.32)
            height = max(180, round(width * 205 / 180))
            self.grid_size = QSize(width, height)
        self.content.setGridSize(self.grid_size)

    def _open_favorite_key(self, key: str) -> None:
        post = next((post for post in self.posts if favorite_key(post) == key), None)
        if post is None:
            return
        if self._selection_mode:
            self._toggle_favorite_selection(key)
        else:
            self._open_post(post)

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
        self._update_selection_toolbar()
        self.content.viewport().update()

    def _toggle_favorite_selection(self, key: str) -> None:
        self._set_selection_mode(True)
        self._set_favorite_selected(key, key not in self._selected_favorites)

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
        self.selection_count_label.setText(f"{len(selected)} selected")
        has_selection = self._selection_mode and bool(selected)
        self.selection_count_label.setVisible(has_selection)
        self.select_all_button.setVisible(has_selection)
        self.delete_selected_button.setVisible(has_selection)
        self.download_selected_button.setVisible(has_selection)
        self.content.viewport().update()

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

    def _request_visible_thumbnails(self) -> None:
        if not self.isVisible() or not self.posts or not self.content.isVisible():
            return
        view = self.content
        viewport = view.viewport()
        if viewport.width() <= 0 or viewport.height() <= 0:
            return
        first = view.indexAt(QPoint(2, 2))
        last = view.indexAt(QPoint(2, max(2, viewport.height() - 2)))
        if not first.isValid():
            first = view.indexAt(QPoint(view.gridSize().width() // 2, 2))
        if not last.isValid():
            last = first
        if not first.isValid():
            return
        columns = max(1, viewport.width() // max(1, view.gridSize().width()))
        start = max(0, first.row() - columns)
        end = min(len(self.posts) - 1, last.row() + columns)
        for row in range(start, end + 1):
            post = self.posts[row]
            key = favorite_key(post)
            if (
                key in self.thumbnail_cache
                or key in self.thumbnail_errors
                or key in self._thumbnail_requested
            ):
                continue
            item_rect = view.visualRect(self.model.index(row, 0))
            if not item_rect.intersects(viewport.rect().adjusted(0, -view.gridSize().height(), 0, view.gridSize().height())):
                continue
            self._thumbnail_requested.add(key)
            viewport.update(item_rect)
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
        self._update_favorite_paint(post_id)

    def set_thumbnail_error(self, post_id: str, error: str = "") -> None:
        self._thumbnail_requested.discard(post_id)
        self.thumbnail_errors.add(post_id)
        details = error.strip() or "Preview could not be loaded."
        self.thumbnail_error_details[post_id] = details
        self._update_favorite_paint(post_id)

    def _update_favorite_paint(self, key: str) -> None:
        row = self._row_by_key.get(key)
        if row is None:
            return
        index = self.model.index(row, 0)
        rect = self.content.visualRect(index)
        self.content.viewport().update(rect)

    def remove_favorite(self, post_id: str) -> None:
        self.posts = [post for post in self.posts if favorite_key(post) != post_id]
        self.all_posts = [post for post in self.all_posts if favorite_key(post) != post_id]
        self.thumbnail_cache.pop(post_id, None)
        self.thumbnail_errors.discard(post_id)
        self.thumbnail_error_details.pop(post_id, None)
        self._thumbnail_requested.discard(post_id)
        self._rebuild()
