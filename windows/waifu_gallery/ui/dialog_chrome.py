from pathlib import Path

from PySide6.QtCore import QEvent, QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QWidget


class FramelessResizableDialog(QDialog):
    _BORDER_WIDTH = 8
    _REMEMBERED_SIZES = {
        "favoritesDialog",
        "downloadsDialog",
        "settingsDialog",
        "mediaInfoDialog",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._size_restored = False
        self._resize_filter_widgets: set[int] = set()
        self._show_animation: QPropertyAnimation | None = None
        self.finished.connect(self._save_remembered_size)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._size_restored:
            self._restore_remembered_size()
            self._size_restored = True
        self._install_resize_filters()
        if self.objectName() in {
            "favoritesDialog",
            "settingsDialog",
            "mediaInfoDialog",
        }:
            if self._show_animation is not None:
                self._show_animation.stop()
            self.setWindowOpacity(0.0)
            self._show_animation = QPropertyAnimation(self, b"windowOpacity", self)
            self._show_animation.setDuration(160)
            self._show_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._show_animation.setStartValue(0.0)
            self._show_animation.setEndValue(1.0)
            self._show_animation.start()

    def _remembered_size_key(self) -> str | None:
        if self.objectName() not in self._REMEMBERED_SIZES:
            return None
        return f"windows/{self.objectName()}/size"

    def _restore_remembered_size(self) -> None:
        key = self._remembered_size_key()
        settings = getattr(self.parentWidget(), "settings", None)
        if key is None or settings is None:
            return
        size = settings.get(key)
        if isinstance(size, QSize) and size.isValid():
            self.resize(size.expandedTo(self.minimumSize()))

    def _save_remembered_size(self, *_args) -> None:
        key = self._remembered_size_key()
        settings = getattr(self.parentWidget(), "settings", None)
        if key is None or settings is None:
            return
        size = self.normalGeometry().size() if self.isMaximized() else self.size()
        if size.isValid():
            settings.set(key, size)

    def childEvent(self, event) -> None:
        super().childEvent(event)
        if (
            event.added()
            and isinstance(event.child(), QWidget)
            and hasattr(self, "_resize_filter_widgets")
        ):
            self._install_resize_filter(event.child())

    def _install_resize_filters(self) -> None:
        self._install_resize_filter(self)
        for widget in self.findChildren(QWidget):
            self._install_resize_filter(widget)

    def _install_resize_filter(self, widget: QWidget) -> None:
        widget_id = id(widget)
        if widget_id in self._resize_filter_widgets:
            return
        self._resize_filter_widgets.add(widget_id)
        widget.destroyed.connect(
            lambda _object=None, current_id=widget_id:
            self._resize_filter_widgets.discard(current_id)
        )
        widget.setMouseTracking(True)
        widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if not isinstance(watched, QWidget) or (
            watched is not self and watched.window() is not self
        ):
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.Enter:
            watched.setMouseTracking(True)
        elif event.type() == QEvent.Type.MouseMove:
            edges = self._resize_edges(event.globalPosition().toPoint())
            cursor = self._resize_cursor(edges)
            if cursor is None:
                watched.unsetCursor()
            else:
                watched.setCursor(QCursor(cursor))
        elif (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and not self.isMaximized()
            and not self.isFullScreen()
        ):
            edges = self._resize_edges(event.globalPosition().toPoint())
            handle = self.windowHandle()
            if edges and self._show_animation is not None:
                if self._show_animation.state() == QPropertyAnimation.State.Running:
                    self._show_animation.stop()
                    self.setWindowOpacity(1.0)
            if edges and handle is not None and handle.startSystemResize(edges):
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _resize_edges(self, global_position: QPoint) -> Qt.Edge:
        local = self.mapFromGlobal(global_position)
        if not self.rect().contains(local):
            return Qt.Edge(0)
        edges = Qt.Edge(0)
        if local.x() < self._BORDER_WIDTH:
            edges |= Qt.Edge.LeftEdge
        elif local.x() >= self.width() - self._BORDER_WIDTH:
            edges |= Qt.Edge.RightEdge
        if local.y() < self._BORDER_WIDTH:
            edges |= Qt.Edge.TopEdge
        elif local.y() >= self.height() - self._BORDER_WIDTH:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _resize_cursor(edges: Qt.Edge) -> Qt.CursorShape | None:
        has_left = bool(edges & Qt.Edge.LeftEdge)
        has_right = bool(edges & Qt.Edge.RightEdge)
        has_top = bool(edges & Qt.Edge.TopEdge)
        has_bottom = bool(edges & Qt.Edge.BottomEdge)
        if (has_left and has_top) or (has_right and has_bottom):
            return Qt.CursorShape.SizeFDiagCursor
        if (has_right and has_top) or (has_left and has_bottom):
            return Qt.CursorShape.SizeBDiagCursor
        if has_left or has_right:
            return Qt.CursorShape.SizeHorCursor
        if has_top or has_bottom:
            return Qt.CursorShape.SizeVerCursor
        return None


class DialogTitleBar(QWidget):
    def __init__(
        self,
        dialog: QDialog,
        title_text: str,
        trailing_widget: QWidget | None = None,
        *,
        show_minimize: bool = False,
    ) -> None:
        super().__init__(dialog)
        self._drag_offset: QPoint | None = None
        self.setObjectName("dialogTitleBar")
        self.setFixedHeight(38)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(8)
        title = QLabel(title_text)
        title.setObjectName("downloadsWindowTitle")
        layout.addWidget(title)
        layout.addStretch(1)
        if trailing_widget is not None:
            layout.addWidget(trailing_widget)
        if show_minimize:
            layout.addWidget(create_minimize_button(dialog, title_text))
        close = QPushButton()
        icon_factory = getattr(dialog.parent(), "_icon", None)
        icon = icon_factory("close") if callable(icon_factory) else QIcon(
            str(Path(__file__).resolve().parent.parent / "assets" / "close.svg")
        )
        close.setIcon(icon)
        close.setIconSize(QSize(16, 16))
        close.setObjectName("downloadsCloseButton")
        close.setFixedSize(30, 30)
        close.setToolTip(f"Close {title_text.lower()}")
        close.setAccessibleName(f"Close {title_text.lower()}")
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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

def create_minimize_button(dialog: QDialog, title_text: str) -> QPushButton:
    button = QPushButton()
    icon_factory = getattr(dialog.parent(), "_icon", None)
    icon = icon_factory("minimize") if callable(icon_factory) else QIcon(
        str(Path(__file__).resolve().parent.parent / "assets" / "minimize.svg")
    )
    button.setIcon(icon)
    button.setIconSize(QSize(16, 16))
    button.setObjectName("dialogMinimizeButton")
    button.setFixedSize(30, 30)
    button.setToolTip(f"Minimize {title_text.lower()}")
    button.setAccessibleName(f"Minimize {title_text.lower()}")
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.clicked.connect(dialog.showMinimized)
    return button
