import re
from pathlib import Path
from urllib.parse import quote

import requests
from PySide6.QtCore import QObject, QPoint, QRunnable, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QTextBrowser,
    QHBoxLayout,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from .dialog_chrome import DialogTitleBar, FramelessResizableDialog


UPDATE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/calestinfisalia/WaifuGallery/main/updates.json"
)
GITHUB_RELEASE_API = "https://api.github.com/repos/calestinfisalia/WaifuGallery/releases/tags/"
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
                UPDATE_MANIFEST_URL,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Waifu-Gallery"},
                timeout=(5, 12),
            )
            response.raise_for_status()
            manifest = response.json()
            if manifest.get("schema_version") != 1:
                raise ValueError("The update manifest version is not supported.")
            entry = manifest.get("platforms", {}).get("linux", {})
            version = str(entry.get("version", "")).strip()
            tag = str(entry.get("release_tag", "")).strip()
            if not re.fullmatch(r"\d+(?:\.\d+){1,3}", version):
                raise ValueError("The Linux update version is invalid.")
            if not re.fullmatch(r"[A-Za-z0-9._-]+", tag):
                raise ValueError("The Linux release tag is invalid.")
            if version_parts(version) <= version_parts(__version__):
                self.signals.finished.emit(version, "", "", "")
                return

            response = requests.get(
                f"{GITHUB_RELEASE_API}{quote(tag, safe='')}",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Waifu-Gallery"},
                timeout=(5, 12),
            )
            response.raise_for_status()
            release = response.json()
            if (
                str(release.get("tag_name", "")).strip() != tag
                or release.get("draft")
                or release.get("prerelease")
            ):
                raise ValueError("The Linux release is unavailable or unstable.")
            url = str(release.get("html_url", "")).strip()
            notes = str(release.get("body", "")).strip()
            release_assets = {
                str(asset.get("name", ""))
                for asset in release.get("assets", [])
                if isinstance(asset, dict)
            }
            expected_assets = {
                f"Waifu-Gallery-{version}-x86_64.AppImage",
                f"Waifu-Gallery-{version}-x86_64.flatpak",
            }
            if not url.startswith(
                "https://github.com/calestinfisalia/WaifuGallery/releases/tag/"
            ):
                raise ValueError("The Linux release URL is invalid.")
            if not release_assets.intersection(expected_assets):
                raise ValueError("The Linux release is missing an AppImage or Flatpak package.")
            self.signals.finished.emit(version, url, notes, "")
        except Exception as error:
            self.signals.finished.emit("", "", "", str(error))


class _UpdateMascotOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("updateMascot")
        self.setAccessibleName("Iro-chan mascot")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        image_path = Path(__file__).resolve().parents[1] / "assets" / "Iro-chan-update-pose.png"
        self._pixmap = QPixmap(str(image_path))

    def sizeHint(self) -> QSize:
        return QSize(0, 0)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def paintEvent(self, _event) -> None:
        if self._pixmap.isNull():
            return
        top_offset = 18
        right_offset = 18
        available_height = max(100, self.height() - top_offset - 8)
        target_height = available_height
        target_width = round(target_height * (self._pixmap.width() / self._pixmap.height()))
        pixmap = self._pixmap.scaled(
            QSize(target_width, target_height),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter = QPainter(self)
        painter.drawPixmap(self.width() - pixmap.width() - right_offset, top_offset, pixmap)


def version_parts(value: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(?:\.\d+){0,3}", value.strip()):
        return (0,)
    return tuple(int(number) for number in value.strip().split("."))


class ReleaseNotesDialog(FramelessResizableDialog):
    def __init__(self, tag: str, url: str, notes: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("releaseNotesDialog")
        self.setWindowTitle("Update available")
        self.setMinimumSize(760, 520)
        self.resize(940, 680)

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
        content_layout.setContentsMargins(20, 78, 20, 8)
        content_layout.setSpacing(10)

        notes_card = QFrame()
        notes_card.setObjectName("releaseNotesCard")
        card_layout = QVBoxLayout(notes_card)
        card_layout.setContentsMargins(28, 24, 28, 20)
        card_layout.setSpacing(8)
        heading = QLabel(f"Waifu Gallery {tag} is available")
        heading.setObjectName("releaseNotesHeading")
        heading.setWordWrap(True)
        card_layout.addWidget(heading)
        subheading = QLabel(f"What's New in {tag}:")
        subheading.setObjectName("releaseNotesSubheading")
        card_layout.addWidget(subheading)

        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(False)
        self.notes.setOpenLinks(False)
        self.notes.anchorClicked.connect(QDesktopServices.openUrl)
        self.notes.setMarkdown(notes or "This release does not include release notes.")
        self.notes.setMinimumHeight(140)
        self.notes.setMaximumWidth(420)
        self.notes.setFrameShape(QFrame.Shape.NoFrame)
        self.notes.setStyleSheet("QTextBrowser { background: transparent; border: 0; padding: 0; }")
        card_layout.addWidget(self.notes, 1, Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(notes_card, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 8, 0)
        actions.addStretch(3)
        later = QPushButton("Later")
        later.setObjectName("laterUpdateButton")
        later.clicked.connect(self.reject)
        open_release = QPushButton("View update")
        open_release.setObjectName("openUpdateButton")
        open_release.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url or RELEASE_PAGE)))
        actions.addWidget(later)
        actions.addWidget(open_release)
        actions.addStretch(2)
        description = QLabel(f"Installed version: {__version__}")
        description.setObjectName("releaseNotesVersion")
        actions.addWidget(description)
        content_layout.addLayout(actions)
        body_stack.addWidget(content)
        mascot = _UpdateMascotOverlay(body)
        body_stack.addWidget(mascot)
        body_stack.setCurrentWidget(mascot)
        mascot.raise_()
        layout.addWidget(body, 1)
        outer.addWidget(surface)
