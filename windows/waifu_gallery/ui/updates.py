import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

import requests
from PySide6.QtCore import QObject, QPoint, QRunnable, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
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
WINDOWS_INSTALLER = "WaifuGallery-Setup-x64.exe"
MAX_UPDATE_SIZE = 512 * 1024 * 1024


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
        top_offset = 20
        bottom_offset = 6
        right_offset = 24
        available_height = max(100, self.height() - top_offset - bottom_offset)
        target_height = available_height
        target_width = round(target_height * (self._pixmap.width() / self._pixmap.height()))
        pixmap = self._pixmap.scaled(
            QSize(target_width, target_height),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = self.width() - pixmap.width() - right_offset
        y = top_offset
        painter = QPainter(self)
        painter.drawPixmap(QPoint(x, y), pixmap)


class UpdateCheckSignals(QObject):
    finished = Signal(str, str, str, str, str, str)


class UpdateCheckTask(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = UpdateCheckSignals()

    def run(self) -> None:
        try:
            with requests.get(
                GITHUB_LATEST_RELEASE,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Waifu-Gallery"},
                timeout=(5, 12),
            ) as response:
                response.raise_for_status()
                release = response.json()
            tag = str(release.get("tag_name", "")).strip()
            url = str(release.get("html_url", "")).strip()
            notes = str(release.get("body", "")).strip()
            installer = next(
                (
                    asset
                    for asset in release.get("assets", [])
                    if asset.get("name") == WINDOWS_INSTALLER
                ),
                {},
            )
            download_url = str(installer.get("browser_download_url", "")).strip()
            digest = str(installer.get("digest", "")).strip()
            if (
                not tag
                or not url.startswith("https://github.com/")
                or not download_url.startswith(
                    "https://github.com/calestinfisalia/WaifuGallery/releases/download/"
                )
                or not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest)
            ):
                raise ValueError("The latest release is missing a verified Windows installer.")
            self.signals.finished.emit(tag, url, notes, download_url, digest[7:], "")
        except Exception as error:
            self.signals.finished.emit("", "", "", "", "", str(error))


class UpdateDownloadSignals(QObject):
    progress = Signal(int)
    finished = Signal(str, str)


class UpdateDownloadTask(QRunnable):
    def __init__(self, version: str, url: str, expected_sha256: str) -> None:
        super().__init__()
        self.version = version
        self.url = url
        self.expected_sha256 = expected_sha256
        self.signals = UpdateDownloadSignals()

    def run(self) -> None:
        temporary_path: Path | None = None
        try:
            if not re.fullmatch(r"v?\d+(?:\.\d+){0,3}", self.version):
                raise ValueError("The update version is invalid.")
            if not re.fullmatch(r"[a-fA-F0-9]{64}", self.expected_sha256):
                raise ValueError("The installer checksum is invalid.")
            if not self.url.startswith(
                "https://github.com/calestinfisalia/WaifuGallery/releases/download/"
            ):
                raise ValueError("The installer URL is not a trusted GitHub release URL.")

            local_app_data = Path(
                os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
            )
            destination_dir = (
                local_app_data
                / "WaifuGallery"
                / "updates"
                / self.version.lstrip("vV")
            )
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / WINDOWS_INSTALLER
            temporary_path = destination_dir / f".{uuid4().hex}.download"
            digest = hashlib.sha256()
            downloaded = 0
            with requests.get(
                self.url,
                headers={"User-Agent": "Waifu-Gallery"},
                stream=True,
                timeout=(10, 60),
            ) as response:
                response.raise_for_status()
                if not response.url.startswith("https://"):
                    raise ValueError("The installer download did not remain on HTTPS.")
                content_length = int(response.headers.get("Content-Length", "0") or 0)
                if content_length < 0 or content_length > MAX_UPDATE_SIZE:
                    raise ValueError("The installer is larger than the allowed download size.")
                with temporary_path.open("wb") as installer_file:
                    for chunk in response.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        downloaded += len(chunk)
                        if downloaded > MAX_UPDATE_SIZE:
                            raise ValueError("The installer is larger than the allowed download size.")
                        digest.update(chunk)
                        installer_file.write(chunk)
                        if content_length:
                            self.signals.progress.emit(
                                min(100, downloaded * 100 // content_length)
                            )
                    installer_file.flush()
                    os.fsync(installer_file.fileno())

            if downloaded == 0:
                raise ValueError("The installer download was empty.")
            if digest.hexdigest().casefold() != self.expected_sha256.casefold():
                raise ValueError("The downloaded installer failed its SHA-256 integrity check.")
            os.replace(temporary_path, destination)
            temporary_path = None
            self.signals.progress.emit(100)
            self.signals.finished.emit(str(destination), "")
        except Exception as error:
            if temporary_path is not None and temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError as cleanup_error:
                    error = OSError(
                        f"{error} Temporary download cleanup also failed: {cleanup_error}"
                    )
            self.signals.finished.emit("", str(error))


def version_parts(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    return tuple(int(number) for number in numbers) or (0,)


class ReleaseNotesDialog(FramelessResizableDialog):
    download_requested = Signal()
    install_requested = Signal(str)

    def __init__(
        self,
        tag: str,
        url: str,
        notes: str,
        download_url: str,
        sha256: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("releaseNotesDialog")
        self.setWindowTitle("Update available")
        self.setMinimumSize(800, 540)
        self.resize(1024, 730)

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
        content_layout.setContentsMargins(22, 90, 22, 6)
        content_layout.setSpacing(14)

        notes_card = QFrame()
        notes_card.setObjectName("releaseNotesCard")
        notes_card.setStyleSheet(
            "QFrame#releaseNotesCard { background: #383d5b; border: 0; "
            "border-radius: 34px; }"
        )
        card_layout = QVBoxLayout(notes_card)
        card_layout.setContentsMargins(36, 30, 36, 24)
        card_layout.setSpacing(0)

        heading = QLabel(f"Waifu Gallery {tag} is available")
        heading.setObjectName("releaseNotesHeading")
        heading.setWordWrap(True)
        heading.setStyleSheet(
            "font-size: 13pt; font-weight: 500; color: #f0f1f7; background: transparent;"
        )
        card_layout.addWidget(heading)

        card_layout.addSpacing(42)

        what_is_new = QLabel(f"What's New in {tag}:")
        what_is_new.setObjectName("releaseNotesSubheading")
        what_is_new.setStyleSheet(
            "font-weight: 600; font-size: 10pt; color: #a6acc8; background: transparent;"
        )
        card_layout.addWidget(what_is_new)

        card_layout.addSpacing(10)

        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(False)
        self.notes.setOpenLinks(False)
        self.notes.anchorClicked.connect(QDesktopServices.openUrl)
        self.notes.setMarkdown(notes or "This release does not include release notes.")
        self.notes.setMinimumHeight(120)
        self.notes.setMaximumWidth(380)
        self.notes.setFrameShape(QFrame.Shape.NoFrame)
        self.notes.setStyleSheet(
            "QTextBrowser { background: transparent; color: #f0f1f7; "
            "border: 0; padding: 0; selection-background-color: #586080; font-size: 10pt; }"
        )
        card_layout.addWidget(self.notes, 1, Qt.AlignmentFlag.AlignLeft)

        card_layout.addStretch(1)

        download_status_row = QHBoxLayout()
        download_status_row.setContentsMargins(0, 0, 0, 0)
        download_status_row.setSpacing(16)
        self.download_percentage = QLabel()
        self.download_percentage.setObjectName("releaseDownloadPercentage")
        self.download_percentage.setStyleSheet(
            "color: #f0f1f7; font-weight: 700; font-size: 10pt; background: transparent;"
        )
        self.download_percentage.hide()
        self.download_status = QLabel()
        self.download_status.setObjectName("releaseDownloadStatus")
        self.download_status.setStyleSheet("color: #c8cce0; font-size: 10pt; background: transparent;")
        self.download_status.hide()
        download_status_row.addWidget(self.download_percentage)
        download_status_row.addWidget(self.download_status)
        download_status_row.addStretch(1)
        card_layout.addLayout(download_status_row)

        card_layout.addSpacing(6)

        self.download_progress = QProgressBar()
        self.download_progress.setObjectName("releaseDownloadProgress")
        self.download_progress.setRange(0, 100)
        self.download_progress.setFixedHeight(5)
        self.download_progress.setMaximumWidth(480)
        self.download_progress.setTextVisible(False)
        self.download_progress.setStyleSheet(
            "QProgressBar#releaseDownloadProgress { background: #222638; border: 0; border-radius: 2px; } "
            "QProgressBar#releaseDownloadProgress::chunk { background: #bb9af7; border-radius: 2px; }"
        )
        self.download_progress.hide()
        card_layout.addWidget(self.download_progress)

        content_layout.addWidget(notes_card, 1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 4, 16, 2)
        bottom_bar.setSpacing(8)
        bottom_bar.addStretch(3)

        later = QPushButton("Later")
        later.setObjectName("laterUpdateButton")
        later.clicked.connect(self.reject)
        open_release = QPushButton("View update")
        open_release.setObjectName("openUpdateButton")
        open_release.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(url or RELEASE_PAGE))
        )
        self.download_button = QPushButton("Download update")
        self.download_button.setObjectName("downloadUpdateButton")
        self.version = tag
        self.download_url = download_url
        self.sha256 = sha256
        self._installer_path = ""
        self.download_button.clicked.connect(self._download_or_install)

        for button in (later, open_release, self.download_button):
            button.setFixedHeight(26)
            button.setStyleSheet(
                "QPushButton { background: #202538; color: #c9cde0; "
                "border: 1px solid #353b58; border-radius: 9px; "
                "padding: 2px 14px; font-size: 9pt; }"
                "QPushButton:hover { background: #2a3048; }"
            )
            bottom_bar.addWidget(button)

        bottom_bar.addStretch(2)

        description = QLabel(f"Installed version: {__version__}")
        description.setObjectName("releaseNotesVersion")
        description.setStyleSheet("color: #7982a9; font-size: 9pt; background: transparent;")
        bottom_bar.addWidget(description)

        content_layout.addLayout(bottom_bar)
        body_stack.addWidget(content)

        mascot = _UpdateMascotOverlay(body)
        body_stack.addWidget(mascot)
        body_stack.setCurrentWidget(mascot)
        layout.addWidget(body, 1)
        outer.addWidget(surface)
        mascot.raise_()

    def _download_or_install(self) -> None:
        if self._installer_path:
            self.install_requested.emit(self._installer_path)
        else:
            self.download_requested.emit()

    def begin_download(self) -> None:
        self.download_button.setEnabled(False)
        self.download_button.setText("Downloading...")
        self.download_status.setText("Downloading the verified Windows installer...")
        self.download_status.show()
        self.download_percentage.setText("0%")
        self.download_percentage.show()
        self.download_progress.setValue(0)
        self.download_progress.show()

    def set_download_progress(self, progress: int) -> None:
        progress = max(0, min(progress, 100))
        self.download_progress.setValue(progress)
        self.download_percentage.setText(f"{progress}%")

    def set_download_error(self, error: str) -> None:
        self.download_button.setEnabled(True)
        self.download_button.setText("Retry download")
        self.download_status.setText(f"Download failed: {error}")
        self.download_status.show()
        self.download_percentage.hide()
        self.download_progress.hide()

    def set_installer_ready(self, installer_path: str) -> None:
        self._installer_path = installer_path
        self.download_button.setEnabled(True)
        self.download_button.setText("Install now")
        self.download_status.setText(
            "Download verified. Choose Install now to open the installer."
        )
        self.download_status.show()
        self.download_percentage.setText("100%")
        self.download_percentage.show()
        self.download_progress.setValue(100)
