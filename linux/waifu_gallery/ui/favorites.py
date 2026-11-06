from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..models import ImagePost


def favorite_key(post: ImagePost) -> str:
    return f"{post.provider}:{post.post_id}"


class FavoritesDialog(QDialog):
    def __init__(self, posts: list[ImagePost], open_post, remove_post, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Favorites")
        self.resize(820, 620)
        self.posts = list(posts)
        self._open_post = open_post
        self._remove_post = remove_post
        self.thumbnail_buttons: dict[str, QPushButton] = {}
        self.remove_buttons: dict[str, QPushButton] = {}
        self.tiles: list[tuple[str, QWidget]] = []
        self.thumbnail_cache: dict[str, QPixmap] = {}
        self.thumbnail_errors: set[str] = set()

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.count_label = QLabel()
        header.addWidget(self.count_label)
        header.addStretch(1)
        layout.addLayout(header)

        self.empty_label = QLabel("No favorite images yet.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll, 1)
        self._rebuild()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._layout_tiles)

    def _rebuild(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.thumbnail_buttons.clear()
        self.remove_buttons.clear()
        self.tiles.clear()
        self.count_label.setText(f"Favorites · {len(self.posts)} images")
        self.empty_label.setVisible(not self.posts)
        self.scroll.setVisible(bool(self.posts))

        for post in self.posts:
            preview_area = QWidget()
            preview_area.setMinimumSize(160, 180)
            preview_area.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            preview = QPushButton("Loading preview...", preview_area)
            preview.setObjectName("previewImage")
            preview.clicked.connect(lambda _checked=False, item=post: self._open_post(item))
            key = favorite_key(post)
            self.thumbnail_buttons[key] = preview
            remove = QPushButton(preview_area)
            remove.setObjectName("favoriteRemoveButton")
            remove.setIcon(QIcon(str(Path(__file__).resolve().parent.parent / "assets" / "heart-filled.svg")))
            remove.setIconSize(QSize(18, 18))
            remove.resize(32, 32)
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
        if button:
            button.setText("")
            button.setIcon(QIcon(pixmap))

    def set_thumbnail_error(self, post_id: str) -> None:
        self.thumbnail_errors.add(post_id)
        button = self.thumbnail_buttons.get(post_id)
        if button:
            button.setText("Preview unavailable")

    def remove_favorite(self, post_id: str) -> None:
        self.posts = [post for post in self.posts if favorite_key(post) != post_id]
        self._rebuild()
