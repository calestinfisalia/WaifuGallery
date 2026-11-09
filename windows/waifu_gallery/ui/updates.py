import re
from pathlib import Path

import requests
from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
    QStackedLayout,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from .dialog_chrome import DialogTitleBar, FramelessResizableDialog


GITHUB_LATEST_RELEASE = "https://api.github.com/repos/calestinfisalia/WaifuGallery/releases/latest"
RELEASE_PAGE = "https://github.com/calestinfisalia/WaifuGallery/releases"


class _UpdateMascotOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("updateMascot")
        self.setAccessibleName("Iro-chan mascot")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        image_path = Path(__file__).resolve().parents[1] / "assets" / "waifumascot-Iro-chan.png"
        self._pixmap = QPixmap(str(image_path)).scaled(
            QSize(320, 480),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ).transformed(QTransform().scale(-1, 1))

    def sizeHint(self) -> QSize:
        return QSize(0, 0)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def paintEvent(self, _event) -> None:
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.drawPixmap(self.width() - 200, 0, self._pixmap)


class UpdateCheckSignals(QObject):
    finished = Signal(str, str, str, str)


class UpdateCheckTask(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = UpdateCheckSignals()

    def run(self) -> None:
        try:
            response = requests.get(
                GITHUB_LATEST_RELEASE,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Waifu-Gallery"},
                timeout=(5, 12),
            )
            response.raise_for_status()
            release = response.json()
            tag = str(release.get("tag_name", "")).strip()
            url = str(release.get("html_url", "")).strip()
            notes = str(release.get("body", "")).strip()
            if not tag or not url:
                raise ValueError("The latest release response is missing its tag or URL.")
            self.signals.finished.emit(tag, url, notes, "")
        except Exception as error:
            self.signals.finished.emit("", "", "", str(error))


def version_parts(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    return tuple(int(number) for number in numbers) or (0,)


class ReleaseNotesDialog(FramelessResizableDialog):
    def __init__(self, tag: str, url: str, notes: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("releaseNotesDialog")
        self.setWindowTitle("Update available")
        self.setMinimumSize(440, 320)
        self.resize(570, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("releaseNotesSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(10, 4, 10, 10)
        layout.setSpacing(0)
        layout.addWidget(DialogTitleBar(self, "Update available"))

        body = QWidget(surface)
        body.setObjectName("releaseNotesBody")
        body_stack = QStackedLayout(body)
        body_stack.setContentsMargins(0, 0, 0, 0)
        body_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 8, 4, 0)
        content_layout.setSpacing(0)
        introduction = QVBoxLayout()
        introduction.setContentsMargins(0, 0, 0, 0)
        introduction.setSpacing(2)
        heading = QLabel(f"Waifu Gallery {tag} is available")
        heading.setObjectName("releaseNotesHeading")
        heading.setWordWrap(True)
        heading.setStyleSheet("font-size: 12pt; font-weight: 500;")
        introduction.addWidget(heading)
        description = QLabel(f"Installed version: {__version__}")
        description.setObjectName("releaseNotesVersion")
        introduction.addWidget(description)
        content_layout.addLayout(introduction)
        content_layout.addSpacing(50)

        notes_card = QFrame()
        notes_card.setObjectName("releaseNotesCard")
        notes_card.setMaximumHeight(246)
        notes_card.setStyleSheet(
            "QFrame#releaseNotesCard { background: #383d5b; border: 0; "
            "border-radius: 34px; }"
        )
        card_layout = QVBoxLayout(notes_card)
        card_layout.setContentsMargins(24, 16, 20, 16)
        card_layout.setSpacing(8)
        what_is_new = QLabel(f"What's New in {tag}:")
        what_is_new.setObjectName("releaseNotesSubheading")
        what_is_new.setStyleSheet("font-weight: 600; background: transparent;")
        card_layout.addWidget(what_is_new)

        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(False)
        self.notes.setOpenLinks(False)
        self.notes.anchorClicked.connect(QDesktopServices.openUrl)
        self.notes.setMarkdown(notes or "This release does not include release notes.")
        self.notes.setMinimumHeight(130)
        self.notes.setMaximumWidth(360)
        self.notes.setFrameShape(QFrame.Shape.NoFrame)
        self.notes.setStyleSheet(
            "QTextBrowser { background: transparent; color: #f0f1f7; "
            "border: 0; padding: 0; selection-background-color: #586080; }"
        )
        card_layout.addWidget(self.notes, 1, Qt.AlignmentFlag.AlignLeft)
        card_inset = QWidget()
        card_inset.setStyleSheet("background: transparent;")
        card_inset_layout = QHBoxLayout(card_inset)
        card_inset_layout.setContentsMargins(8, 0, 0, 0)
        card_inset_layout.addWidget(notes_card)
        content_layout.addWidget(card_inset, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 7, 0, 4)
        actions.setSpacing(6)
        actions.addStretch(1)
        later = QPushButton("Later")
        later.setObjectName("laterUpdateButton")
        later.clicked.connect(self.reject)
        open_release = QPushButton("View update")
        open_release.setObjectName("openUpdateButton")
        open_release.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(url or RELEASE_PAGE))
        )
        for button in (later, open_release):
            button.setFixedHeight(24)
            button.setStyleSheet(
                "QPushButton { background: #202538; color: #c9cde0; "
                "border: 1px solid #353b58; border-radius: 9px; "
                "padding: 2px 9px; font-size: 9pt; }"
                "QPushButton:hover { background: #2a3048; }"
            )
            actions.addWidget(button)
        actions.addStretch(1)
        content_layout.addLayout(actions)
        body_stack.addWidget(content)

        mascot = _UpdateMascotOverlay(body)
        body_stack.addWidget(mascot)
        body_stack.setCurrentWidget(mascot)
        layout.addWidget(body, 1)
        outer.addWidget(surface)
