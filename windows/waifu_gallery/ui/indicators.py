from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class CircularProgressIndicator(QWidget):
    def __init__(self, parent=None, size: int = 30) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._active = False
        self._angle = 0
        self._progress: float | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(32)
        self._timer.timeout.connect(self._rotate)
        self.hide()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._progress = None if active else 0.0
        self.setVisible(active)
        if active:
            self._timer.start()
        else:
            self._timer.stop()
            self._angle = 0
        self.update()

    def set_progress(self, progress: float | None) -> None:
        if progress is None:
            self.set_active(True)
            return
        self._active = True
        self._progress = max(0.0, min(1.0, progress))
        self._timer.stop()
        self.setVisible(True)
        self.update()

    def _rotate(self) -> None:
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)
        track = QPen(QColor("#3b3e47"), 3)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track)
        painter.drawArc(rect, 0, 360 * 16)
        if self._active and self._progress is None:
            arc = QPen(QColor("#d1d5db"), 3)
            arc.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc)
            painter.drawArc(rect, -self._angle * 16, -100 * 16)
        elif self._active and self._progress is not None and self._progress > 0:
            arc = QPen(QColor("#d1d5db"), 3)
            arc.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc)
            painter.drawArc(rect, 90 * 16, -round(self._progress * 360 * 16))
        painter.end()
