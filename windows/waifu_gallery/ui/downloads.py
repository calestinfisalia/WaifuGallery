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
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("downloadsDialog")
        self.setWindowTitle("Downloads")
        self.setMinimumSize(420, 280)
        self.resize(560, 380)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("downloadsSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(10, 4, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(DialogTitleBar(self, "Downloads"))
        self.items = QListWidget()
        layout.addWidget(self.items, 1)
        row = QHBoxLayout()
        clear = QPushButton("Clear history")
        clear.clicked.connect(self.clear_history)
        row.addStretch(1)
        row.addWidget(clear)
        layout.addLayout(row)
        outer.addWidget(surface)
        self.records: dict[str, tuple[QLabel, QProgressBar]] = {}

    def clear_history(self) -> None:
        self.items.clear()
        self.records.clear()

    def add_download(self, key: str, filename: str) -> None:
        item = QListWidgetItem()
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        label = QLabel(f"{filename} — Queued")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setFixedHeight(5)
        bar.setTextVisible(False)
        layout.addWidget(label)
        layout.addWidget(bar)
        item.setSizeHint(row.sizeHint())
        self.items.addItem(item)
        self.items.setItemWidget(item, row)
        self.records[key] = (label, bar)

    def update_download(self, key: str, state: str, progress: int | None = None) -> None:
        record = self.records.get(key)
        if not record:
            return
        label, bar = record
        label.setText(state)
        if progress is not None:
            bar.setRange(0, 0) if progress < 0 else bar.setRange(0, 100)
            if progress >= 0:
                bar.setValue(progress)
