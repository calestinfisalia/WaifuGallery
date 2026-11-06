from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)

from ..models import ImagePost


class ZoomImage(QLabel):
    zoomChanged = Signal(bool)
    swipeRequested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(1, 1)
        self.original = QPixmap()
        self.factor = 1.0
        self.base_scale = 1.0
        self.viewport = None
        self.scroll_area = None
        self._drag_position = None
        self._swipe_start = None

    def set_image(self, pixmap: QPixmap) -> None:
        self.original = pixmap
        self.factor = 1.0
        self.zoomChanged.emit(False)
        if self.scroll_area is not None:
            self.scroll_area.setWidgetResizable(False)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMinimumSize(1, 1)
        if pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        self.setCursor(Qt.CursorShape.OpenHandCursor if self.factor > 1.0 else Qt.CursorShape.ArrowCursor)
        self._fit_to_viewport()

    def set_placeholder(self, message: str) -> None:
        """Show loading/error text across the scroll area's full viewport."""
        self.original = QPixmap()
        self.factor = 1.0
        self.setPixmap(QPixmap())
        self.setText(message)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if self.scroll_area is not None:
            self.scroll_area.setWidgetResizable(True)

    def _fit_to_viewport(self) -> None:
        if self.original.isNull():
            return
        available = self.viewport.size() if self.viewport else self.size()
        if available.width() < 50 or available.height() < 50:
            available = self.size()
        if available.width() < 50 or available.height() < 50:
            available = self.original.size()
        self.base_scale = min(available.width() / self.original.width(),
                              available.height() / self.original.height(), 1.0)
        self._render()

    def _render(self) -> None:
        if self.original.isNull():
            return
        scale = self.base_scale * self.factor
        target = QSize(max(1, round(self.original.width() * scale)),
                       max(1, round(self.original.height() * scale)))
        self.setPixmap(self.original.scaled(target, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        self.adjustSize()

    def wheelEvent(self, event) -> None:
        if self.original.isNull():
            event.ignore()
            return
        old_width = max(1, self.width())
        old_height = max(1, self.height())
        viewport_point = None
        horizontal = vertical = None
        if self.viewport is not None and self.scroll_area is not None:
            viewport_point = self.mapTo(self.viewport, event.position().toPoint())
            horizontal = self.scroll_area.horizontalScrollBar()
            vertical = self.scroll_area.verticalScrollBar()
            content_x = horizontal.value() + viewport_point.x()
            content_y = vertical.value() + viewport_point.y()
            ratio_x = content_x / old_width
            ratio_y = content_y / old_height
        multiplier = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        previous = self.factor
        self.factor = min(6.0, max(1.0, self.factor * multiplier))
        self._render()
        self.zoomChanged.emit(self.factor > 1.0)
        self.setCursor(Qt.CursorShape.OpenHandCursor if self.factor > 1.0 else Qt.CursorShape.ArrowCursor)
        if self.factor != previous and viewport_point is not None:
            new_width = max(1, round(old_width * self.factor / previous))
            new_height = max(1, round(old_height * self.factor / previous))
            QTimer.singleShot(0, lambda: self._keep_zoom_anchor(
                horizontal, vertical, round(ratio_x * new_width - viewport_point.x()),
                round(ratio_y * new_height - viewport_point.y())))
        event.accept()

    @staticmethod
    def _keep_zoom_anchor(horizontal, vertical, x: int, y: int) -> None:
        horizontal.setValue(x)
        vertical.setValue(y)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.factor > 1.0 and self.scroll_area is not None:
            self._drag_position = event.globalPosition().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.factor <= 1.0:
            self._swipe_start = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_position is not None and self.scroll_area is not None:
            current = event.globalPosition().toPoint()
            delta = current - self._drag_position
            self._drag_position = current
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x())
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_position is not None:
            self._drag_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._swipe_start is not None:
            start = self._swipe_start
            self._swipe_start = None
            delta = event.globalPosition().toPoint() - start
            if abs(delta.x()) >= 75 and abs(delta.x()) > abs(delta.y()) * 1.25:
                self.swipeRequested.emit(1 if delta.x() < 0 else -1)
                event.accept()
                return
        super().mouseReleaseEvent(event)


class ImageViewer(QDialog):
    downloadRequested = Signal(object)

    def __init__(self, post: ImagePost, parent=None) -> None:
        super().__init__(parent)
        self.post = post
        self.setWindowTitle(f"{post.provider} · {post.rating.upper()}")
        self.resize(950, 720)
        layout = QVBoxLayout(self)
        self.image = ZoomImage()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.image)
        self.image.viewport = self.scroll.viewport()
        self.image.scroll_area = self.scroll
        layout.addWidget(self.scroll, 1)
        metadata = QLabel(self._metadata_text())
        metadata.setWordWrap(True)
        layout.addWidget(metadata)
        self.status = QLabel("Loading image…")
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("Close")
        save = QPushButton("Download")
        save.clicked.connect(lambda: self.downloadRequested.emit(self.post))
        close.clicked.connect(self.close)
        buttons.addWidget(close)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        self.save_button = save
        self.save_button.setEnabled(False)

    def set_image_bytes(self, content: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(content):
            self.show_error("The provider returned an unsupported image format.")
            return
        self.image.set_image(pixmap)
        self.status.setText("Image ready · Original available to download")
        self.save_button.setEnabled(True)

    def show_error(self, message: str) -> None:
        self.status.setText(f"Could not load image: {message}")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.image._fit_to_viewport)

    def _metadata_text(self) -> str:
        details = [self.post.provider, self.post.rating.upper()]
        if self.post.artists:
            details.append("Artists: " + ", ".join(self.post.artists))
        if self.post.source:
            details.append("Source: " + self.post.source)
        return " · ".join(details)
