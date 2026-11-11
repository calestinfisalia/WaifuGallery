import json

from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .dialog_chrome import DialogTitleBar, FramelessResizableDialog


class DownloadsDialog(FramelessResizableDialog):
    cancel_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("downloadsDialog")
        self.setWindowTitle("Downloads")
        self.setMinimumSize(480, 340)
        self.resize(680, 500)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("downloadsSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(14, 4, 14, 14)
        layout.setSpacing(12)
        layout.addWidget(DialogTitleBar(self, "Downloads"))
        self.items = QListWidget()
        self.items.setObjectName("downloadsList")
        self.items.setSpacing(6)
        self.items.setContentsMargins(0, 2, 0, 2)
        layout.addWidget(self.items, 1)
        row = QHBoxLayout()
        clear = QPushButton("Clear history")
        clear.clicked.connect(self.clear_history)
        row.addStretch(1)
        row.addWidget(clear)
        layout.addLayout(row)
        outer.addWidget(surface)
        self.records: dict[str, tuple[QLabel, QLabel, QProgressBar, QPushButton]] = {}
        self.history: dict[str, dict[str, str]] = {}
        self.settings = getattr(parent, "settings", None)
        icon_factory = getattr(parent, "_icon", None)
        self.download_icon = icon_factory("download") if callable(icon_factory) else QIcon()
        self._restore_history()

    def clear_history(self) -> None:
        self.items.clear()
        self.records.clear()
        self.history.clear()
        self._save_history()

    def add_download(
        self,
        key: str,
        filename: str,
        path: str = "",
        status: str = "Queued",
        *,
        persist: bool = True,
    ) -> None:
        self.history[key] = {"filename": filename, "path": path, "status": status}
        item = QListWidgetItem()
        row = QWidget()
        row.setObjectName("downloadItemCard")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        icon = QLabel()
        icon.setObjectName("downloadItemIcon")
        icon.setFixedSize(30, 30)
        if not self.download_icon.isNull():
            icon.setPixmap(self.download_icon.pixmap(QSize(24, 24)))
        layout.addWidget(icon, 0)
        details = QVBoxLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(3)
        filename_label = QLabel(filename)
        filename_label.setObjectName("downloadFilename")
        filename_label.setToolTip(path or filename)
        status_label = QLabel(status)
        status_label.setObjectName("downloadStatus")
        status_label.setToolTip(status_label.text())
        details.addWidget(filename_label)
        details.addWidget(status_label)
        progress = QProgressBar()
        progress.setObjectName("downloadProgress")
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(False)
        progress.setFixedHeight(5)
        details.addWidget(progress)
        layout.addLayout(details, 1)
        cancel = QPushButton()
        cancel.setObjectName("downloadCancelButton")
        cancel.setIcon(self._icon("x"))
        cancel.setIconSize(QSize(14, 14))
        cancel.setFixedSize(28, 28)
        cancel.setToolTip("Cancel download")
        cancel.setAccessibleName("Cancel download")
        cancel.clicked.connect(lambda checked=False, download_key=key: self.cancel_requested.emit(download_key))
        layout.addWidget(cancel, 0, Qt.AlignmentFlag.AlignVCenter)
        row.setMinimumHeight(72)
        item.setSizeHint(QSize(0, 82))
        self.items.addItem(item)
        self.items.setItemWidget(item, row)
        self.records[key] = (filename_label, status_label, progress, cancel)
        self.update_download(key, status, persist=False)
        if persist:
            self._save_history()

    def update_download(
        self,
        key: str,
        state: str,
        progress: int | None = None,
        *,
        persist: bool = True,
    ) -> None:
        record = self.records.get(key)
        if record is None:
            return
        history_record = self.history.get(key)
        status_changed = history_record is not None and history_record["status"] != state
        if history_record is not None:
            history_record["status"] = state
        display_state = f"{state} | {progress}%" if progress is not None and progress >= 0 else state
        _, status_label, progress_bar, cancel_button = record
        status_label.setText(display_state)
        status_label.setToolTip(display_state)
        if progress is not None and progress < 0:
            progress_bar.setRange(0, 0)
        elif progress is not None:
            progress_bar.setRange(0, 100)
            progress_bar.setValue(progress)
        if state.startswith(("Saved:", "Failed:", "Cancelled", "Interrupted")):
            cancel_button.hide()
            progress_bar.hide()
        if persist and status_changed:
            self._save_history()

    def mark_cancelling(self, key: str) -> None:
        record = self.records.get(key)
        if record is None:
            return
        _, status_label, _, cancel_button = record
        status_label.setText("Cancelling...")
        status_label.setToolTip(status_label.text())
        cancel_button.setEnabled(False)

    def _icon(self, name: str) -> QIcon:
        parent = self.parent()
        icon_factory = getattr(parent, "_icon", None)
        if callable(icon_factory):
            return icon_factory(name)
        return QIcon()

    def _restore_history(self) -> None:
        if self.settings is None:
            return
        raw_history = self.settings.get("downloads/history", "[]")
        entries = json.loads(str(raw_history))
        if not isinstance(entries, list):
            raise ValueError("Saved download history must be a list.")
        changed = False
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("id", ""))
            filename = str(entry.get("filename", ""))
            if not key or not filename:
                continue
            status = str(entry.get("status", "Interrupted before completion"))
            if status == "Queued" or status.startswith("Downloading"):
                status = "Interrupted before completion"
                changed = True
            self.add_download(
                key,
                filename,
                str(entry.get("path", "")),
                status,
                persist=False,
            )
        if changed:
            self._save_history()

    def _save_history(self) -> None:
        if self.settings is None:
            return
        entries = [
            {"id": key, **record}
            for key, record in self.history.items()
        ]
        self.settings.set("downloads/history", json.dumps(entries))
