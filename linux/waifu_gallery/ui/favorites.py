from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from ..models import ImagePost
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
        layout.addStretch(1)
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
        self.thumbnail_buttons: dict[str, QPushButton] = {}
        self.thumbnail_indicators: dict[str, CircularProgressIndicator] = {}
        self.remove_buttons: dict[str, QPushButton] = {}
        self.play_badges: dict[str, QLabel] = {}
        self.tiles: list[tuple[str, QWidget]] = []
        self.thumbnail_cache: dict[str, QPixmap] = {}
        self.thumbnail_errors: set[str] = set()
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.setInterval(55)
        self._layout_timer.timeout.connect(self._layout_tiles)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("favoritesSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(4)
        layout.addWidget(FavoritesTitleBar(self))
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

    def _rebuild(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.thumbnail_buttons.clear()
        self.thumbnail_indicators.clear()
        self.remove_buttons.clear()
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
            preview.clicked.connect(lambda _checked=False, item=post: self._open_post(item))
            key = favorite_key(post)
            self.thumbnail_buttons[key] = preview
            if key not in self.thumbnail_cache and key not in self.thumbnail_errors:
                indicator = CircularProgressIndicator(preview_area, size=28)
                indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                indicator.set_active(True)
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
                preview.setText("Preview unavailable")
        self._layout_tiles()

    def _layout_tiles(self) -> None:
        if not self.tiles:
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
            self.remove_buttons[key].setGeometry(tile_width - 40, 8, 32, 32)
            self.remove_buttons[key].raise_()
            self.grid.addWidget(tile, index // columns, index % columns)

    def _confirm_remove(self, post_id: str) -> None:
        answer = QMessageBox.question(
            self,
            "Remove favorite",
            "Remove this image from your favorites?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._remove_post(post_id)

    def set_thumbnail(self, post_id: str, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        self.thumbnail_cache[post_id] = pixmap
        self.thumbnail_errors.discard(post_id)
        button = self.thumbnail_buttons.get(post_id)
        indicator = self.thumbnail_indicators.get(post_id)
        if indicator:
            indicator.set_active(False)
        if button:
            button.setText("")
            button.setIcon(QIcon(pixmap))
        play_badge = self.play_badges.get(post_id)
        if play_badge:
            play_badge.show()

    def set_thumbnail_error(self, post_id: str) -> None:
        self.thumbnail_errors.add(post_id)
        indicator = self.thumbnail_indicators.get(post_id)
        if indicator:
            indicator.set_active(False)
        button = self.thumbnail_buttons.get(post_id)
        if button:
            button.setText("Preview unavailable")
        play_badge = self.play_badges.get(post_id)
        if play_badge:
            play_badge.hide()

    def remove_favorite(self, post_id: str) -> None:
        self.posts = [post for post in self.posts if favorite_key(post) != post_id]
        self._rebuild()
