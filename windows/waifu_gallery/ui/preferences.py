from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..doh import DOH_ENDPOINTS, set_doh_enabled, validate_doh_endpoint
from ..settings import AppSettings


class ProviderLoginDialog(QDialog):
    PROVIDER_INFO = {
        "Gelbooru": (
            "https://gelbooru.com/index.php?page=account&s=options",
            "Open your Gelbooru account options and copy your user ID and API key.",
            "Get Gelbooru API credentials",
        ),
        "Rule34.xxx": (
            "https://rule34.xxx/index.php?page=account&s=options",
            "Open Account Options, find API Access Credentials, generate a key if needed, and save it.",
            "Get Rule34.xxx API credentials",
        ),
    }

    def __init__(self, provider: str, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.settings = settings
        self.setWindowTitle(f"Sign in to {provider}")
        self.setMinimumWidth(430)
        prefix = "gelbooru" if provider == "Gelbooru" else "rule34"
        self.user_setting = f"{prefix}/user_id"
        self.key_setting = f"{prefix}/api_key"

        layout = QVBoxLayout(self)
        url, instructions, link_text = self.PROVIDER_INFO[provider]
        help_text = QLabel(instructions)
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        form = QFormLayout()
        self.user_id = QLineEdit(str(settings.get(self.user_setting, "")))
        self.api_key = QLineEdit(str(settings.get(self.key_setting, "")))
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.user_id.setPlaceholderText("User ID")
        self.api_key.setPlaceholderText("API key")
        form.addRow("User ID", self.user_id)
        form.addRow("API key", self.api_key)
        layout.addLayout(form)
        guide = QLabel(f'<a href="{url}">{link_text}</a>')
        guide.setOpenExternalLinks(True)
        layout.addWidget(guide)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def save(self) -> None:
        user_id = self.user_id.text().strip()
        api_key = self.api_key.text().strip()
        if bool(user_id) != bool(api_key):
            QMessageBox.warning(self, "Incomplete credentials", "Enter both fields, or clear both fields to sign out.")
            return
        self.settings.set(self.user_setting, user_id)
        self.settings.set(self.key_setting, api_key)
        self.accept()


class PreferencesDialog(QDialog):
    ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Waifu Gallery Settings")
        self.resize(760, 520)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        content = QHBoxLayout()
        content.setSpacing(8)
        self.sidebar = QWidget()
        self.sidebar.setObjectName("settingsSidebar")
        self.sidebar.setFixedWidth(142)
        self.sidebar.setStyleSheet("QWidget#settingsSidebar { background: transparent; }")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(2, 4, 2, 4)
        self.sidebar_layout.setSpacing(3)
        self.pages = QStackedWidget()
        content.addWidget(self.sidebar)
        content.addWidget(self.pages, 1)
        root.addLayout(content, 1)
        self.nav_buttons = []
        self._build_general_tab()
        self._build_provider_tab()
        self._build_storage_tab()
        self._build_filter_tab()
        self._build_network_tab()
        self._build_display_tab()
        self._build_about_tab()
        # Keep navigation items grouped at the top instead of spreading them
        # across the full height of the dialog.
        self.sidebar_layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _build_general_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Saved search terms used by Random"))
        self.terms = QListWidget()
        self.terms.addItems(self._saved_terms())
        layout.addWidget(self.terms, 1)
        row = QHBoxLayout()
        self.new_term = QLineEdit()
        self.new_term.setPlaceholderText("Add a search term")
        add = QPushButton("Add")
        remove = QPushButton("Remove selected")
        add.clicked.connect(self.add_term)
        remove.clicked.connect(self.remove_term)
        row.addWidget(self.new_term, 1)
        row.addWidget(add)
        row.addWidget(remove)
        layout.addLayout(row)
        self._add_page(page, "General", "dices")

    def _build_provider_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(["All", "Danbooru", "yande.re", "Gelbooru", "Rule34.xxx"])
        self.provider.setCurrentText(str(self.settings.get("search/provider", "All")))
        self.default_rating = QComboBox()
        self.default_rating.addItem("Only SFW", "sfw")
        self.default_rating.addItem("Only NSFW", "nsfw")
        self.default_rating.addItem("Show All", "all")
        rating = str(self.settings.get("search/rating", "sfw"))
        self.default_rating.setCurrentIndex(max(0, self.default_rating.findData(rating)))
        form.addRow("Default provider", self.provider)
        form.addRow("Default rating", self.default_rating)
        layout.addLayout(form)
        layout.addWidget(QLabel("Provider accounts"))
        self.provider_buttons = {}
        for name in ("Gelbooru", "Rule34.xxx"):
            row = QHBoxLayout()
            row.addWidget(QLabel(name), 1)
            button = QPushButton()
            button.clicked.connect(lambda checked=False, provider=name: self.manage_provider(provider))
            self.provider_buttons[name] = button
            row.addWidget(button)
            layout.addLayout(row)
            self._update_provider_button(name)
        layout.addStretch(1)
        self._add_page(page, "Providers", "images")

    def _build_storage_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.save_folder = QLineEdit(str(self.settings.get("downloads/folder", "")))
        self.save_folder.setReadOnly(True)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose_save_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.save_folder, 1)
        folder_row.addWidget(browse)
        form.addRow("Download folder", folder_row)
        layout.addLayout(form)
        layout.addStretch(1)
        self._add_page(page, "Storage", "download")

    def _build_filter_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.exclude_male = QCheckBox("Exclude posts tagged as male-only")
        self.exclude_male.setChecked(bool(self.settings.get("search/exclude_male", True)))
        self.allow_nsfw = QCheckBox("Allow NSFW results")
        self.allow_nsfw.setChecked(bool(self.settings.get("search/allow_nsfw", False)))
        self.filter_gore = QCheckBox("Filter posts tagged as gore")
        self.filter_gore.setChecked(bool(self.settings.get("search/filter_gore", True)))
        for control in (self.exclude_male, self.allow_nsfw, self.filter_gore):
            layout.addWidget(control)

        layout.addWidget(QLabel("Custom blocked tags"))
        self.filter_list = QListWidget()
        saved_tags = self.settings.get("search/custom_block_tags", [])
        if isinstance(saved_tags, str):
            saved_tags = saved_tags.replace(",", " ").split()
        self.filter_list.addItems([str(tag) for tag in saved_tags])
        layout.addWidget(self.filter_list, 1)
        add_row = QHBoxLayout()
        self.new_filter = QLineEdit()
        self.new_filter.setPlaceholderText("Tag(s), e.g. blood, guro, decapitation")
        add_button = QPushButton("Add filter")
        remove_button = QPushButton("Remove selected")
        add_button.clicked.connect(self.add_filter)
        remove_button.clicked.connect(self.remove_filter)
        add_row.addWidget(self.new_filter, 1)
        add_row.addWidget(add_button)
        add_row.addWidget(remove_button)
        layout.addLayout(add_row)
        layout.addWidget(QLabel("Built-in tag filters only match posts tagged by their provider."))
        self._add_page(page, "Filters", "settings-2")

    def _build_network_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.use_doh = QCheckBox("Use DNS over HTTPS")
        self.use_doh.setChecked(self.settings.use_doh)
        layout.addWidget(self.use_doh)
        form = QFormLayout()
        self.doh_provider = QComboBox()
        for name in (*DOH_ENDPOINTS.keys(), "Custom"):
            self.doh_provider.addItem(name, name)
        selected_doh = str(self.settings.get("network/doh_provider", "Cloudflare"))
        selected_index = self.doh_provider.findData(selected_doh)
        self.doh_provider.setCurrentIndex(max(0, selected_index))
        self.doh_custom_endpoint = QLineEdit(
            str(self.settings.get("network/doh_custom_endpoint", ""))
        )
        self.doh_custom_endpoint.setPlaceholderText("https://resolver.example/dns-query")
        self.doh_custom_label = QLabel("Custom HTTPS endpoint")
        form.addRow("DNS provider", self.doh_provider)
        form.addRow(self.doh_custom_label, self.doh_custom_endpoint)
        layout.addLayout(form)
        self.doh_provider.currentIndexChanged.connect(self._update_doh_controls)
        self._update_doh_controls()
        note = QLabel(
            "Uses encrypted DNS only for this app. Custom endpoints must support standard "
            "DNS-over-HTTPS (RFC 8484). The endpoint hostname itself is bootstrapped through system DNS."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        self._add_page(page, "Network", "info")

    def _update_doh_controls(self, *_args) -> None:
        custom = self.doh_provider.currentData() == "Custom"
        self.doh_custom_endpoint.setEnabled(custom)
        self.doh_custom_endpoint.setVisible(custom)
        self.doh_custom_label.setVisible(custom)

    def _build_display_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.ambient_mode = QCheckBox("Ambient mode (blur the current image behind the viewer)")
        self.ambient_mode.setChecked(bool(self.settings.get("view/ambient_mode", True)))
        layout.addWidget(self.ambient_mode)
        form = QFormLayout()
        self.media_filter = QComboBox()
        self.media_filter.addItem("Image only", "image")
        self.media_filter.addItem("Video only", "video")
        self.media_filter.addItem("View all", "all")
        media = str(self.settings.get("search/media_filter", "image"))
        self.media_filter.setCurrentIndex(max(0, self.media_filter.findData(media)))
        form.addRow("Media showing", self.media_filter)
        self.video_resolution = QComboBox()
        self.video_resolution.addItem("Auto (provider source)", 0)
        self.video_resolution.addItem("Up to 2160p", 2160)
        self.video_resolution.addItem("Up to 1080p", 1080)
        self.video_resolution.addItem("Up to 720p", 720)
        self.video_resolution.addItem("Up to 480p", 480)
        resolution = int(self.settings.get("video/max_height", 0) or 0)
        resolution_index = self.video_resolution.findData(resolution)
        self.video_resolution.setCurrentIndex(max(0, resolution_index))
        form.addRow("Video stream resolution", self.video_resolution)
        layout.addLayout(form)
        note = QLabel(
            "Resolution selects the closest provider video variant at or below this limit. "
            "If a provider supplies only one file, that source is used. Media selection "
            "applies to Random and Search results; playback also depends on installed codecs."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        self._add_page(page, "Display", "expand")

    def _build_about_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        logo = QLabel()
        pixmap = QPixmap(str(self.ASSET_DIR / "waifugallery.png"))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(
                QSize(96, 96),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        title = QLabel("Waifu Gallery")
        title.setStyleSheet("font-size: 22pt; font-weight: 700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        subtitle = QLabel("An independent Python image gallery\nCreated by calestinfisalia")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        license_note = QLabel(
            "Application source: MIT License.\n"
            "Bundled icons and image artwork retain their own licenses and creator rights."
        )
        license_note.setWordWrap(True)
        layout.addWidget(license_note)
        layout.addStretch(1)
        self._add_page(page, "About", "info")

    def _add_page(self, page: QWidget, title: str, icon_name: str) -> None:
        button = QPushButton(title)
        button.setObjectName("settingsNavButton")
        button.setCheckable(True)
        button.setMinimumHeight(38)
        # Use the main window's themed icon renderer when available so the
        # settings navigation matches the toolbar and menu icon color/style.
        icon_factory = getattr(self.parent(), "_icon", None)
        icon = icon_factory(icon_name) if callable(icon_factory) else QIcon(str(self.ASSET_DIR / f"{icon_name}.svg"))
        button.setIcon(icon)
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet("""
            QPushButton#settingsNavButton { text-align: left; background: transparent; border: 0; border-radius: 8px; padding: 8px 10px; }
            QPushButton#settingsNavButton:hover { background: #2d334b; }
            QPushButton#settingsNavButton:checked { background: #343b58; color: #c0caf5; }
        """)
        index = self.pages.addWidget(page)
        button.clicked.connect(lambda checked=False, page_index=index: self._select_page(page_index))
        self.sidebar_layout.addWidget(button)
        self.nav_buttons.append(button)
        if index == 0:
            button.setChecked(True)

    def _select_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        for position, button in enumerate(self.nav_buttons):
            button.setChecked(position == index)

    def _update_provider_button(self, provider: str) -> None:
        prefix = "gelbooru" if provider == "Gelbooru" else "rule34"
        connected = bool(
            str(self.settings.get(f"{prefix}/user_id", "")).strip()
            and str(self.settings.get(f"{prefix}/api_key", "")).strip()
        )
        button = self.provider_buttons[provider]
        button.setText("Logout" if connected else "Sign in")

    def manage_provider(self, provider: str) -> None:
        button = self.provider_buttons[provider]
        if button.text() == "Logout":
            confirm = QMessageBox.question(
                self,
                f"Log out of {provider}?",
                "This will delete the saved user ID and API key from this app.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                prefix = "gelbooru" if provider == "Gelbooru" else "rule34"
                self.settings.set(f"{prefix}/user_id", "")
                self.settings.set(f"{prefix}/api_key", "")
                self._update_provider_button(provider)
                if self.provider.currentText() == provider:
                    self.provider.setCurrentText("All")
            return
        dialog = ProviderLoginDialog(provider, self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._update_provider_button(provider)

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
        existing = {self.terms.item(i).text().casefold() for i in range(self.terms.count())}
        if value and value.casefold() not in existing:
            self.terms.addItem(value)
        self.new_term.clear()

    def remove_term(self) -> None:
        row = self.terms.currentRow()
        if row >= 0:
            self.terms.takeItem(row)

    def add_filter(self) -> None:
        existing = {self.filter_list.item(i).text().casefold() for i in range(self.filter_list.count())}
        for tag in self.new_filter.text().replace(",", " ").split():
            normalized = tag.strip().casefold().replace(" ", "_")
            if normalized and normalized not in existing:
                self.filter_list.addItem(normalized)
                existing.add(normalized)
        self.new_filter.clear()

    def remove_filter(self) -> None:
        row = self.filter_list.currentRow()
        if row >= 0:
            self.filter_list.takeItem(row)

    def save(self) -> None:
        provider = self.provider.currentText()
        if provider == "Gelbooru" and not all(self.settings.gelbooru_credentials):
            QMessageBox.warning(self, "Gelbooru credentials", "Use Sign in to add the Gelbooru user ID and API key first.")
            return
        if provider == "Rule34.xxx" and not all(self.settings.rule34_credentials):
            QMessageBox.warning(self, "Rule34.xxx credentials", "Use Sign in to add the Rule34.xxx user ID and API key first.")
            return
        doh_provider = str(self.doh_provider.currentData())
        doh_endpoint = (
            self.doh_custom_endpoint.text().strip()
            if doh_provider == "Custom"
            else DOH_ENDPOINTS[doh_provider]
        )
        if self.use_doh.isChecked():
            try:
                doh_endpoint = validate_doh_endpoint(doh_endpoint)
            except ValueError as error:
                QMessageBox.warning(self, "Invalid DoH endpoint", str(error))
                self._select_page(self.nav_buttons.index(next(
                    button for button in self.nav_buttons if button.text() == "Network"
                )))
                return
        self.settings.set("search/provider", provider)
        self.settings.set("search/rating", self.default_rating.currentData())
        self.settings.set("downloads/folder", self.save_folder.text())
        self.settings.set("search/custom_terms", [self.terms.item(i).text() for i in range(self.terms.count())])
        self.settings.set("search/exclude_male", self.exclude_male.isChecked())
        self.settings.set("search/allow_nsfw", self.allow_nsfw.isChecked())
        self.settings.set("search/filter_gore", self.filter_gore.isChecked())
        self.settings.set("search/custom_block_tags", [self.filter_list.item(i).text() for i in range(self.filter_list.count())])
        self.settings.set("network/use_doh", self.use_doh.isChecked())
        self.settings.set("network/doh_provider", doh_provider)
        self.settings.set("network/doh_custom_endpoint", self.doh_custom_endpoint.text().strip())
        self.settings.set("view/ambient_mode", self.ambient_mode.isChecked())
        self.settings.set("search/media_filter", self.media_filter.currentData())
        self.settings.set("video/max_height", self.video_resolution.currentData())
        set_doh_enabled(self.use_doh.isChecked(), doh_endpoint)
        self.accept()
