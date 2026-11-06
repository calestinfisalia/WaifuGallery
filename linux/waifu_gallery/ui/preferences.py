from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..settings import AppSettings


class PreferencesDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Waifu Gallery Settings")
        self.setMinimumWidth(470)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(["All", *["Danbooru", "yande.re", "Gelbooru"]])
        self.provider.setCurrentText(str(settings.get("search/provider", "All")))
        self.default_rating = QComboBox()
        self.default_rating.addItem("Only SFW", "sfw")
        self.default_rating.addItem("Only NSFW", "nsfw")
        self.default_rating.addItem("Show All", "all")
        rating = str(settings.get("search/rating", "sfw"))
        self.default_rating.setCurrentIndex(max(0, self.default_rating.findData(rating)))
        self.gelbooru_user = QLineEdit(str(settings.get("gelbooru/user_id", "")))
        self.gelbooru_key = QLineEdit(str(settings.get("gelbooru/api_key", "")))
        self.gelbooru_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.save_folder = QLineEdit(str(settings.get("downloads/folder", "")))
        self.save_folder.setReadOnly(True)
        choose_folder = QPushButton("Browse…")
        choose_folder.clicked.connect(self.choose_save_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.save_folder, 1)
        folder_row.addWidget(choose_folder)
        form.addRow("Default provider", self.provider)
        form.addRow("Default rating", self.default_rating)
        form.addRow("Gelbooru user ID", self.gelbooru_user)
        form.addRow("Gelbooru API key", self.gelbooru_key)
        form.addRow("Download folder", folder_row)
        layout.addLayout(form)

        layout.addWidget(QLabel("Saved search terms"))
        self.terms = QListWidget()
        self.terms.addItems(self._saved_terms())
        layout.addWidget(self.terms)
        add_row = QHBoxLayout()
        self.new_term = QLineEdit()
        self.new_term.setPlaceholderText("Add a search term for Random")
        add_term = QPushButton("Add")
        remove_term = QPushButton("Remove selected")
        add_term.clicked.connect(self.add_term)
        remove_term.clicked.connect(self.remove_term)
        add_row.addWidget(self.new_term, 1)
        add_row.addWidget(add_term)
        add_row.addWidget(remove_term)
        layout.addLayout(add_row)

        self.exclude_male = QCheckBox("Exclude posts tagged as male-only")
        self.exclude_male.setChecked(bool(settings.get("search/exclude_male", True)))
        layout.addWidget(self.exclude_male)
        self.allow_nsfw = QCheckBox("Allow NSFW results")
        self.allow_nsfw.setChecked(bool(settings.get("search/allow_nsfw", False)))
        layout.addWidget(self.allow_nsfw)
        layout.addWidget(QLabel("Network"))
        self.use_doh = QCheckBox("Use DNS over HTTPS (Cloudflare)")
        self.use_doh.setChecked(settings.use_doh)
        layout.addWidget(self.use_doh)
        doh_note = QLabel("Resolve provider hostnames through Cloudflare DNS without changing Windows network settings.")
        doh_note.setWordWrap(True)
        doh_note.setStyleSheet("color: #a7a7b0;")
        layout.addWidget(doh_note)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _saved_terms(self) -> list[str]:
        values = self.settings.get("search/custom_terms", [])
        return [str(value) for value in values] if isinstance(values, (list, tuple)) else []

    def choose_save_folder(self) -> None:
        current = self.save_folder.text() or str(Path.home() / "Pictures")
        folder = QFileDialog.getExistingDirectory(self, "Select download folder", current)
        if folder:
            self.save_folder.setText(folder)

    def add_term(self) -> None:
        value = self.new_term.text().strip()
        existing = {self.terms.item(index).text().casefold() for index in range(self.terms.count())}
        if value and value.casefold() not in existing:
            self.terms.addItem(value)
        self.new_term.clear()

    def remove_term(self) -> None:
        row = self.terms.currentRow()
        if row >= 0:
            self.terms.takeItem(row)

    def save(self) -> None:
        provider = self.provider.currentText()
        user_id = self.gelbooru_user.text().strip()
        api_key = self.gelbooru_key.text().strip()
        if provider == "Gelbooru" and not (user_id and api_key):
            QMessageBox.warning(self, "Gelbooru credentials", "Enter both a Gelbooru user ID and API key to select Gelbooru.")
            return
        self.settings.set("search/provider", provider)
        self.settings.set("search/rating", self.default_rating.currentData())
        self.settings.set("gelbooru/user_id", user_id)
        self.settings.set("gelbooru/api_key", api_key)
        self.settings.set("downloads/folder", self.save_folder.text())
        self.settings.set("search/custom_terms", [self.terms.item(index).text() for index in range(self.terms.count())])
        self.settings.set("search/exclude_male", self.exclude_male.isChecked())
        self.settings.set("search/allow_nsfw", self.allow_nsfw.isChecked())
        self.settings.set("network/use_doh", self.use_doh.isChecked())
        self.accept()
