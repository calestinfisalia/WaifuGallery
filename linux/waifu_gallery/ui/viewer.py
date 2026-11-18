from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from .indicators import CircularProgressIndicator


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
        self._pending_zoom_state: tuple[float, float, float] | None = None
        self.viewport = None
        self.scroll_area = None
        self._drag_position = None
        self._swipe_start = None
        self.loading_bar = CircularProgressIndicator(self)
        self.loading_bar.setObjectName("centerLoadIndicator")
        self.loading_bar.hide()

    def set_image(self, pixmap: QPixmap, *, preserve_zoom: bool = False) -> None:
        zoom_state = self._pending_zoom_state
        if preserve_zoom and zoom_state is None:
            zoom_state = self._capture_zoom_state()
        self._pending_zoom_state = None
        self.original = pixmap
        self.factor = (
            zoom_state[0]
            if preserve_zoom and zoom_state and not pixmap.isNull()
            else 1.0
        )
        self.zoomChanged.emit(self.factor > 1.0)
        if self.scroll_area is not None:
            self.scroll_area.setWidgetResizable(False)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMinimumSize(1, 1)
        if pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.loading_bar.set_active(False)
            return
        self.loading_bar.set_active(False)
        self.setCursor(Qt.CursorShape.OpenHandCursor if self.factor > 1.0 else Qt.CursorShape.ArrowCursor)
        self._fit_to_viewport()
        if preserve_zoom and zoom_state:
            QTimer.singleShot(
                0,
                lambda state=zoom_state: self._restore_scroll_position(
                    state[1], state[2]
                ),
            )

    def set_placeholder(self, message: str) -> None:
        """Show an error message across the scroll area's full viewport."""
        self._pending_zoom_state = None
        self._prepare_placeholder()
        self.setWordWrap(True)
        self.setText(message)
        self.loading_bar.set_active(False)

    def set_loading(self, *, preserve_zoom: bool = False) -> None:
        """Show an indeterminate indicator across the full viewport."""
        self._pending_zoom_state = (
            self._capture_zoom_state()
            if preserve_zoom and not self.original.isNull()
            else None
        )
        self._prepare_placeholder()
        self.setText("")
        self.loading_bar.set_active(True)

    def _capture_zoom_state(self) -> tuple[float, float, float]:
        horizontal_fraction = 0.0
        vertical_fraction = 0.0
        if self.scroll_area is not None:
            horizontal = self.scroll_area.horizontalScrollBar()
            vertical = self.scroll_area.verticalScrollBar()
            if horizontal.maximum():
                horizontal_fraction = horizontal.value() / horizontal.maximum()
            if vertical.maximum():
                vertical_fraction = vertical.value() / vertical.maximum()
        return self.factor, horizontal_fraction, vertical_fraction

    def _restore_scroll_position(
        self,
        horizontal_fraction: float,
        vertical_fraction: float,
    ) -> None:
        if self.scroll_area is None:
            return
        horizontal = self.scroll_area.horizontalScrollBar()
        vertical = self.scroll_area.verticalScrollBar()
        horizontal.setValue(round(horizontal_fraction * horizontal.maximum()))
        vertical.setValue(round(vertical_fraction * vertical.maximum()))

    def _prepare_placeholder(self) -> None:
        self.original = QPixmap()
        self.factor = 1.0
        self.setPixmap(QPixmap())
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if self.scroll_area is not None:
            self.scroll_area.setWidgetResizable(True)

    def set_loading_progress(self, value: int) -> None:
        """Show byte-download progress without a text label."""
        self.setText("")
        self.loading_bar.set_progress(None if value < 0 else value / 100)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.loading_bar.move(
            max(0, (self.width() - self.loading_bar.width()) // 2),
            max(0, (self.height() - self.loading_bar.height()) // 2),
        )

    def _fit_to_viewport(self, *, fast: bool = False) -> None:
        if self.original.isNull():
            return
        available = self.viewport.size() if self.viewport else self.size()
        if available.width() < 50 or available.height() < 50:
            available = self.size()
        if available.width() < 50 or available.height() < 50:
            available = self.original.size()
        # Scale the displayed preview to the available viewer area even when
        # the provider's sample is smaller than the window. The explicit
        # original-resolution action remains available for pixel-level detail.
        self.base_scale = min(available.width() / self.original.width(),
                              available.height() / self.original.height())
        self._render(fast=fast)

    def _render(self, *, fast: bool = False) -> None:
        if self.original.isNull():
            return
        scale = self.base_scale * self.factor
        target = QSize(max(1, round(self.original.width() * scale)),
                       max(1, round(self.original.height() * scale)))
        self.setPixmap(self.original.scaled(target, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.FastTransformation
                                            if fast
                                            else Qt.TransformationMode.SmoothTransformation))
        self.adjustSize()

    def wheelEvent(self, event) -> None:
        if self.original.isNull():
            event.ignore()
            return
        old_width = max(1, self.width())
        old_height = max(1, self.height())
        viewport_point = None
        horizontal = vertical = None
        ratio_x = ratio_y = 0.5
        if self.viewport is not None and self.scroll_area is not None:
            image_point = event.position().toPoint()
            viewport_point = self.mapTo(self.viewport, image_point)
            horizontal = self.scroll_area.horizontalScrollBar()
            vertical = self.scroll_area.verticalScrollBar()
            # Keep the pointer anchored to the same point inside the image.
            # Using scroll value + viewport coordinates double-counted the
            # centered offset when a portrait image was narrower than its view.
            ratio_x = min(1.0, max(0.0, image_point.x() / old_width))
            ratio_y = min(1.0, max(0.0, image_point.y() / old_height))
        multiplier = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        previous = self.factor
        self.factor = min(6.0, max(1.0, self.factor * multiplier))
        self._render()
        self.zoomChanged.emit(self.factor > 1.0)
        self.setCursor(Qt.CursorShape.OpenHandCursor if self.factor > 1.0 else Qt.CursorShape.ArrowCursor)
        if self.factor != previous and viewport_point is not None:
            QTimer.singleShot(0, lambda: self._keep_zoom_anchor(
                horizontal, vertical, self, self.viewport, ratio_x, ratio_y, viewport_point))
        event.accept()

    @staticmethod
    def _keep_zoom_anchor(horizontal, vertical, image, viewport, ratio_x: float, ratio_y: float, point) -> None:
        # QScrollArea centers an image while that axis is smaller than the
        # viewport, then switches to scroll coordinates after it grows larger.
        # Account for both states so zooming doesn't jump/crop sideways.
        x_offset = max(0, (viewport.width() - image.width()) // 2)
        y_offset = max(0, (viewport.height() - image.height()) // 2)
        horizontal.setValue(round(x_offset + ratio_x * image.width() - point.x()))
        vertical.setValue(round(y_offset + ratio_y * image.height() - point.y()))

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
        if (
            self._drag_position is not None
            and self.scroll_area is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            current = event.globalPosition().toPoint()
            delta = current - self._drag_position
            self._drag_position = current
            horizontal = self.scroll_area.horizontalScrollBar()
            vertical = self.scroll_area.verticalScrollBar()
            horizontal.setValue(horizontal.value() - delta.x())
            vertical.setValue(vertical.value() - delta.y())
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
