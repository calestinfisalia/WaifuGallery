from html import escape
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..models import ImagePost
from .scrollbars import CAPSULE_SCROLLBAR_STYLE


class MediaInfoTitleBar(QWidget):
    def __init__(self, dialog: QDialog) -> None:
        super().__init__(dialog)
        self._drag_offset = None
        self.setObjectName("mediaInfoTitleBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 0, 0)
        title = QLabel("Media Info")
        title.setObjectName("mediaInfoWindowTitle")
        layout.addWidget(title)
        layout.addStretch(1)
        close = QPushButton()
        icon_factory = getattr(dialog.parent(), "_icon", None)
        icon = icon_factory("close") if callable(icon_factory) else QIcon(
            str(Path(__file__).resolve().parent.parent / "assets" / "close.svg")
        )
        close.setIcon(icon)
        close.setIconSize(QSize(16, 16))
        close.setObjectName("mediaInfoCloseButton")
        close.setFixedSize(30, 30)
        close.setToolTip("Close media info")
        close.setAccessibleName("Close media info")
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


class ImageCreditsDialog(QDialog):
    def __init__(self, post: ImagePost, parent=None) -> None:
        super().__init__(parent)
        self.post = post
        self.selected_tag = ""
        self.setObjectName("mediaInfoDialog")
        self.setWindowTitle("Media Info")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(520, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("mediaInfoSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(16, 6, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(MediaInfoTitleBar(self))

        artists = ", ".join(post.artists) if post.artists else "Not provided"
        artist_label = QLabel(f"Artist: {artists}")
        artist_label.setTextFormat(Qt.TextFormat.PlainText)
        artist_label.setWordWrap(True)
        layout.addWidget(artist_label)

        source = post.source.strip()
        source_label = QLabel()
        source_label.setTextFormat(Qt.TextFormat.RichText)
        if source:
            escaped_source = escape(source)
            source_url = QUrl(source)
            if source_url.isValid() and source_url.scheme().lower() in ("http", "https"):
                source_label.setText(f'Source: <a href="{escaped_source}">{escaped_source}</a>')
                source_label.setOpenExternalLinks(True)
                source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
                source_label.setStyleSheet("QLabel a { color: #7aa2f7; text-decoration: none; }")
            else:
                source_label.setText(f"Source: {escaped_source}")
        else:
            source_label.setText("Source: Not provided")
        source_label.setWordWrap(True)
        layout.addWidget(source_label)

        tags_heading = QLabel(f"Tags ({len(post.tags)}) - Select a tag to find similar media")
        tags_heading.setStyleSheet("font-weight: 600; margin-top: 4px;")
        layout.addWidget(tags_heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("mediaInfoScrollArea")
        scroll.verticalScrollBar().setObjectName("mediaInfoVerticalScrollBar")
        scroll.horizontalScrollBar().setObjectName("mediaInfoHorizontalScrollBar")
        scroll.verticalScrollBar().setStyleSheet(CAPSULE_SCROLLBAR_STYLE)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tag_container = QWidget()
        tags_layout = QGridLayout(tag_container)
        tags_layout.setContentsMargins(0, 0, 4, 2)
        tags_layout.setHorizontalSpacing(6)
        tags_layout.setVerticalSpacing(1)
        tags_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        columns = 3
        for index, tag in enumerate(sorted(post.tags, key=str.casefold)):
            button = QToolButton()
            button.setText(tag.replace("_", " "))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setAutoRaise(True)
            button.setToolTip(f"Search tag: {tag}")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QToolButton { border: 0; background: transparent; color: #7aa2f7; "
                "padding: 2px 2px; text-align: left; }"
                "QToolButton:hover { color: #bb9af7; text-decoration: underline; }"
            )
            button.clicked.connect(lambda _checked=False, value=tag: self._select_tag(value))
            tags_layout.addWidget(
                button, index // columns, index % columns, Qt.AlignmentFlag.AlignLeft
            )
        if not post.tags:
            empty = QLabel("No tags were supplied by this provider.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tags_layout.addWidget(empty, 0, 0, 1, columns)
        scroll.setWidget(tag_container)
        layout.addWidget(scroll, 1)

        outer.addWidget(surface)

    def _select_tag(self, tag: str) -> None:
        self.selected_tag = tag
        self.accept()
