import re

import requests
from PySide6.QtCore import QObject, QRunnable, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTextBrowser,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from .dialog_chrome import DialogTitleBar, FramelessResizableDialog


GITHUB_LATEST_RELEASE = "https://api.github.com/repos/calestinfisalia/WaifuGallery/releases/latest"
RELEASE_PAGE = "https://github.com/calestinfisalia/WaifuGallery/releases"


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
        self.resize(560, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("releaseNotesSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(10, 4, 10, 10)
        layout.setSpacing(10)
        layout.addWidget(DialogTitleBar(self, "Update available"))

        heading = QLabel(f"Waifu Gallery {tag} is available")
        heading.setObjectName("releaseNotesHeading")
        layout.addWidget(heading)
        description = QLabel(f"Installed version: {__version__}")
        description.setObjectName("releaseNotesVersion")
        layout.addWidget(description)

        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(False)
        self.notes.setOpenLinks(False)
        self.notes.anchorClicked.connect(QDesktopServices.openUrl)
        self.notes.setMarkdown(notes or "This release does not include release notes.")
        self.notes.setMinimumHeight(170)
        self.notes.setStyleSheet(
            "QTextBrowser { background: #1b1b24; color: #d7d9e8; "
            "border: 1px solid #35384c; border-radius: 10px; padding: 8px; }"
        )
        layout.addWidget(self.notes, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        later = QPushButton("Later")
        later.clicked.connect(self.reject)
        open_release = QPushButton("View update")
        open_release.setObjectName("openUpdateButton")
        open_release.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url or RELEASE_PAGE)))
        actions.addWidget(later)
        actions.addWidget(open_release)
        layout.addLayout(actions)
        outer.addWidget(surface)
