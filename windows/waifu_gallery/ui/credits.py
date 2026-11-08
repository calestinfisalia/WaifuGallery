from html import escape

from PySide6.QtCore import Qt, QUrl
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


class ImageCreditsDialog(QDialog):
    def __init__(self, post: ImagePost, parent=None) -> None:
        super().__init__(parent)
        self.post = post
        self.selected_tag = ""
        self.setWindowTitle("Media Info")
        self.resize(520, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(9)

        title = QLabel("Media Info")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

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

        tags_heading = QLabel(f"Tags ({len(post.tags)}) · Select a tag to find similar media")
        tags_heading.setStyleSheet("font-weight: 600; margin-top: 4px;")
        layout.addWidget(tags_heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        tag_container = QWidget()
        tags_layout = QGridLayout(tag_container)
        tags_layout.setContentsMargins(0, 2, 4, 2)
        tags_layout.setHorizontalSpacing(12)
        tags_layout.setVerticalSpacing(5)
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
                "padding: 4px 2px; text-align: left; }"
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

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        footer.addWidget(close_button)
        layout.addLayout(footer)

    def _select_tag(self, tag: str) -> None:
        self.selected_tag = tag
        self.accept()
