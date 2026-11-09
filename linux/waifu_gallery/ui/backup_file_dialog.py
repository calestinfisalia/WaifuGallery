from pathlib import Path

from PySide6.QtCore import QDir, Qt
from PySide6.QtWidgets import (
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from .dialog_chrome import DialogTitleBar, FramelessResizableDialog
from .backup_prompts import BackupMessageDialog


class BackupFileDialog(FramelessResizableDialog):
    def __init__(
        self,
        *,
        save_mode: bool,
        suggested_name: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.save_mode = save_mode
        self.selected_path: Path | None = None
        title = "Save encrypted backup" if save_mode else "Import encrypted backup"
        self.setObjectName("backupFileDialog")
        self.setWindowTitle(title)
        self.setMinimumSize(620, 420)
        self.resize(760, 500)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("backupFileSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(12, 4, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(DialogTitleBar(self, title))

        location_row = QHBoxLayout()
        location_row.addWidget(QLabel("Folder"))
        self.location = QLineEdit()
        self.location.setObjectName("backupLocation")
        self.location.returnPressed.connect(self._navigate_from_text)
        location_row.addWidget(self.location, 1)
        self.up_button = QPushButton("Up")
        self.up_button.clicked.connect(self._navigate_up)
        location_row.addWidget(self.up_button)
        go_button = QPushButton("Go")
        go_button.clicked.connect(self._navigate_from_text)
        location_row.addWidget(go_button)
        layout.addLayout(location_row)

        self.model = QFileSystemModel(self)
        self.model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot
        )
        self.model.setNameFilters(["*.wgbak", "*.json"])
        self.model.setNameFilterDisables(False)
        self.tree = QTreeView()
        self.tree.setObjectName("backupFileTree")
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.clicked.connect(self._select_item)
        self.tree.doubleClicked.connect(self._activate_item)
        layout.addWidget(self.tree, 1)

        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("File name"))
        self.file_name = QLineEdit(suggested_name)
        self.file_name.setObjectName("backupFileName")
        self.file_name.setPlaceholderText("Choose a backup file")
        self.file_name.returnPressed.connect(self._accept_selection)
        file_row.addWidget(self.file_name, 1)
        layout.addLayout(file_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.confirm_button = QPushButton("Save backup" if save_mode else "Open backup")
        self.confirm_button.setDefault(True)
        self.confirm_button.clicked.connect(self._accept_selection)
        buttons.addWidget(cancel)
        buttons.addWidget(self.confirm_button)
        layout.addLayout(buttons)
        outer.addWidget(surface)

        documents = Path.home() / "Documents"
        start_directory = documents if documents.is_dir() else Path.home()
        self._set_directory(start_directory)

    def _set_directory(self, directory: Path) -> None:
        self.current_directory = directory
        root_index = self.model.setRootPath(str(directory))
        self.tree.setRootIndex(root_index)
        self.location.setText(str(directory))
        self.up_button.setEnabled(directory.parent != directory)
        if not self.save_mode:
            self.file_name.clear()

    def _navigate_from_text(self) -> None:
        path = Path(self.location.text().strip()).expanduser()
        selected_name = ""
        if path.is_file():
            selected_name = path.name
            path = path.parent
        if not path.is_dir():
            BackupMessageDialog.ask(self, "Folder not found", "Choose an existing folder.", ("OK",))
            return
        self._set_directory(path)
        if selected_name:
            self.file_name.setText(selected_name)

    def _navigate_up(self) -> None:
        parent = self.current_directory.parent
        if parent != self.current_directory:
            self._set_directory(parent)

    def _select_item(self, index) -> None:
        path = Path(self.model.filePath(index))
        if path.is_file():
            self.file_name.setText(path.name)

    def _activate_item(self, index) -> None:
        path = Path(self.model.filePath(index))
        if path.is_dir():
            self._set_directory(path)
        else:
            self.file_name.setText(path.name)
            if not self.save_mode:
                self._accept_selection()

    def _accept_selection(self) -> None:
        name = self.file_name.text().strip()
        if not name or Path(name).name != name or name in {".", ".."}:
            BackupMessageDialog.ask(self, "Invalid file name", "Enter a backup file name.", ("OK",))
            return

        path = self.current_directory / name
        if self.save_mode:
            if path.suffix.lower() not in {".wgbak", ".json"}:
                path = path.with_suffix(".wgbak")
            if path.exists():
                answer = BackupMessageDialog.ask(
                    self,
                    "Replace backup?",
                    f"{path.name} already exists. Replace it?",
                    ("Replace", "Cancel"),
                    default_button="Cancel",
                )
                if answer != "Replace":
                    return
        elif not path.is_file() or path.suffix.lower() not in {".wgbak", ".json"}:
            BackupMessageDialog.ask(
                self,
                "Backup not found",
                "Select an existing .wgbak or .json backup file.",
                ("OK",),
            )
            return

        self.selected_path = path
        self.accept()
