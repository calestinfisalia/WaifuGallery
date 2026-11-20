from html import escape
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..models import ImagePost
from .dialog_chrome import FramelessResizableDialog, create_minimize_button
from .scrollbars import CAPSULE_SCROLLBAR_STYLE


def rating_label(rating: str) -> str:
    labels = {"s": "Safe", "q": "Questionable", "e": "Explicit"}
    value = rating.strip().casefold()
    return labels.get(value, value.capitalize() if value else "Unknown")


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
        layout.addWidget(create_minimize_button(dialog, "Media Info"))
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


class ImageCreditsDialog(FramelessResizableDialog):
    def __init__(self, post: ImagePost, parent=None) -> None:
        super().__init__(parent)
        self.post = post
        self.selected_tag = ""
        self.setObjectName("mediaInfoDialog")
        self.setWindowTitle("Media Info")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(400, 320)
        self.resize(520, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("mediaInfoSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(16, 6, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(MediaInfoTitleBar(self))

        media_details = QGridLayout()
        media_details.setContentsMargins(0, 0, 0, 0)
        media_details.setHorizontalSpacing(10)
        media_details.setVerticalSpacing(6)
        provider_heading = QLabel("Provider")
        provider_heading.setObjectName("mediaInfoFieldLabel")
        provider_label = QLabel(post.provider)
        provider_label.setTextFormat(Qt.TextFormat.PlainText)
        rating_heading = QLabel("Rating")
        rating_heading.setObjectName("mediaInfoFieldLabel")
        rating_label_widget = QLabel(rating_label(post.rating))
        rating_label_widget.setTextFormat(Qt.TextFormat.PlainText)
        media_details.addWidget(provider_heading, 0, 0)
        media_details.addWidget(provider_label, 0, 1)
        media_details.addWidget(rating_heading, 1, 0)
        media_details.addWidget(rating_label_widget, 1, 1)
        media_details.setColumnStretch(1, 1)
        layout.addLayout(media_details)

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
        tags_heading.setWordWrap(True)
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
        tag_list = QListWidget()
        tag_list.setObjectName("mediaInfoTagList")
        tag_list.setFrameShape(QFrame.Shape.NoFrame)
        tag_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        tag_list.setUniformItemSizes(True)
        tag_list.setSpacing(1)
        tag_list.setStyleSheet(
            "QListWidget { background: transparent; border: 0; outline: 0; }"
            "QListWidget::item { color: #7aa2f7; padding: 4px 6px; border-radius: 5px; }"
            "QListWidget::item:hover { color: #bb9af7; background: rgba(122, 162, 247, 28); }"
        )
        for tag in sorted(post.tags, key=str.casefold):
            item = QListWidgetItem(tag.replace("_", " "))
            item.setData(Qt.ItemDataRole.UserRole, tag)
            item.setToolTip(f"Search tag: {tag}")
            tag_list.addItem(item)
        if not post.tags:
            empty = QListWidgetItem("No tags were supplied by this provider.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tag_list.addItem(empty)
        tag_list.itemClicked.connect(
            lambda item: self._select_tag(item.data(Qt.ItemDataRole.UserRole))
            if item.data(Qt.ItemDataRole.UserRole)
            else None
        )
        scroll.setWidget(tag_list)
        layout.addWidget(scroll, 1)

        outer.addWidget(surface)

    def _select_tag(self, tag: str) -> None:
        self.selected_tag = tag
        self.accept()
