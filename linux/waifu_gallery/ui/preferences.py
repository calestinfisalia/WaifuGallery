from pathlib import Path

import re

import requests
from PySide6.QtCore import QObject, QRunnable, QSignalBlocker, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QAbstractItemView,
    QFrame,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..doh import DOH_ENDPOINTS, set_doh_enabled, validate_doh_endpoint
from ..settings import AppSettings


GITHUB_LATEST_RELEASE = "https://api.github.com/repos/calestinfisalia/WaifuGallery/releases/latest"


def _themed_icon(widget: QWidget, name: str) -> QIcon:
    icon_factory = getattr(widget.parent(), "_icon", None)
    if callable(icon_factory):
        return icon_factory(name)
    return QIcon(str(Path(__file__).resolve().parent.parent / "assets" / f"{name}.svg"))


class UpdateCheckSignals(QObject):
    finished = Signal(str, str, str)


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
            if not tag or not url:
                raise ValueError("The latest release response is missing its tag or URL.")
            self.signals.finished.emit(tag, url, "")
        except Exception as error:
            self.signals.finished.emit("", "", str(error))


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


class SettingsTitleBar(QWidget):
    def __init__(self, parent: QDialog) -> None:
        super().__init__(parent)
        self._drag_offset = None
        self.setObjectName("settingsTitleBar")
        self.setFixedHeight(42)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        title = QLabel("Settings")
        title.setObjectName("settingsWindowTitle")
        layout.addWidget(title)
        layout.addStretch(1)
        close = QPushButton()
        close.setIcon(_themed_icon(parent, "close"))
        close.setIconSize(QSize(16, 16))
        close.setObjectName("settingsCloseButton")
        close.setFixedSize(30, 30)
        close.setToolTip("Close settings")
        close.setAccessibleName("Close settings")
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.clicked.connect(parent.reject)
        layout.addWidget(close)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle and handle.startSystemMove():
                event.accept()
                return
            self._drag_offset = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class PreferencesDialog(QDialog):
    ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
    RELEASE_PAGE = "https://github.com/calestinfisalia/WaifuGallery/releases"
    settings_changed = Signal()

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._update_pool = QThreadPool.globalInstance()
        self._update_check_task = None
        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(800, 560)
        self.setMinimumSize(720, 500)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        surface = QWidget(self)
        surface.setObjectName("settingsSurface")
        root = QVBoxLayout(surface)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(8)
        root.addWidget(SettingsTitleBar(self))
        content = QHBoxLayout()
        content.setSpacing(10)
        self.sidebar = QWidget()
        self.sidebar.setObjectName("settingsSidebar")
        self.sidebar.setFixedWidth(154)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(2, 4, 2, 4)
        self.sidebar_layout.setSpacing(3)
        self.pages = QStackedWidget()
        self.pages.setObjectName("settingsPages")
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
        self._build_update_tab()
        self._connect_auto_save()
        # Keep navigation items grouped at the top instead of spreading them
        # across the full height of the dialog.
        self.sidebar_layout.addStretch(1)
        outer.addWidget(surface)

    def _build_general_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Saved search terms used by Random"))
        self.terms = QListWidget()
        self.terms.setObjectName("customTermsList")
        self.terms.setFrameShape(QFrame.Shape.NoFrame)
        self.terms.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.terms.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.terms.setSpacing(2)
        self.terms.setStyleSheet(
            "QListWidget#customTermsList { background: transparent; border: 0; padding: 0; }"
        )
        for term in self._saved_terms():
            self._add_term_item(term)
        layout.addWidget(self.terms, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.new_term = QLineEdit()
        self.new_term.setObjectName("customTermInput")
        self.new_term.setPlaceholderText("Add a search term")
        add = QPushButton("Add")
        add.clicked.connect(self.add_term)
        self.new_term.returnPressed.connect(self.add_term)
        row.addWidget(self.new_term, 1)
        row.addWidget(add)
        layout.addLayout(row)
        self._add_page(page, "General", "dices")

    def _build_provider_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        self.provider = QComboBox()
        self.provider.addItems(["All", "Danbooru", "yande.re", "Gelbooru", "Rule34.xxx"])
        self.provider.setCurrentText(str(self.settings.get("search/provider", "All")))
        self._last_provider = self.provider.currentText()
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
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
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
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
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
        self.filter_list.setObjectName("customFilterList")
        self.filter_list.setFrameShape(QFrame.Shape.NoFrame)
        self.filter_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.filter_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.filter_list.setSpacing(2)
        self.filter_list.setStyleSheet(
            "QListWidget#customFilterList { background: transparent; border: 0; padding: 0; }"
        )
        saved_tags = self.settings.get("search/custom_block_tags", [])
        if isinstance(saved_tags, str):
            saved_tags = saved_tags.replace(",", " ").split()
        for tag in saved_tags:
            self._add_chip_item(self.filter_list, str(tag))
        layout.addWidget(self.filter_list, 1)
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.new_filter = QLineEdit()
        self.new_filter.setObjectName("customFilterInput")
        self.new_filter.setPlaceholderText("Tag(s), e.g. blood, guro, decapitation")
        add_button = QPushButton("Add filter")
        add_button.clicked.connect(self.add_filter)
        self.new_filter.returnPressed.connect(self.add_filter)
        add_row.addWidget(self.new_filter, 1)
        add_row.addWidget(add_button)
        layout.addLayout(add_row)
        layout.addWidget(QLabel("Built-in tag filters only match posts tagged by their provider."))
        self._add_page(page, "Filters", "settings-2")

    def _build_network_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        self.use_doh = QCheckBox("Use DNS over HTTPS")
        self.use_doh.setChecked(self.settings.use_doh)
        layout.addWidget(self.use_doh)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
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

    def _connect_auto_save(self) -> None:
        self.provider.currentTextChanged.connect(self._provider_changed)
        for control in (self.default_rating, self.media_filter, self.video_resolution):
            control.currentIndexChanged.connect(self._persist_settings)
        for control in (self.exclude_male, self.allow_nsfw, self.filter_gore, self.ambient_mode):
            control.toggled.connect(self._persist_settings)
        self.use_doh.toggled.connect(self._on_doh_toggled)
        self.doh_provider.currentIndexChanged.connect(self._on_doh_configuration_changed)
        self.doh_custom_endpoint.editingFinished.connect(self._on_doh_configuration_changed)

    def _doh_endpoint(self) -> str:
        provider = str(self.doh_provider.currentData())
        return (
            self.doh_custom_endpoint.text().strip()
            if provider == "Custom"
            else DOH_ENDPOINTS[provider]
        )

    def _validate_doh_configuration(self) -> bool:
        try:
            endpoint = validate_doh_endpoint(self._doh_endpoint())
        except ValueError as error:
            QMessageBox.warning(self, "Invalid DoH endpoint", str(error))
            self._select_page(self.nav_buttons.index(next(
                button for button in self.nav_buttons if button.text() == "Network"
            )))
            return False
        set_doh_enabled(True, endpoint)
        return True

    def _on_doh_toggled(self, enabled: bool) -> None:
        if enabled:
            if not self._validate_doh_configuration():
                blocker = QSignalBlocker(self.use_doh)
                self.use_doh.setChecked(False)
                del blocker
                set_doh_enabled(False)
        else:
            set_doh_enabled(False)
        self._persist_settings()

    def _on_doh_configuration_changed(self, *_args) -> None:
        if self.use_doh.isChecked() and not self._validate_doh_configuration():
            blocker = QSignalBlocker(self.use_doh)
            self.use_doh.setChecked(False)
            del blocker
            set_doh_enabled(False)
        self._persist_settings()

    def _provider_changed(self, provider: str) -> None:
        missing_credentials = (
            provider == "Gelbooru" and not all(self.settings.gelbooru_credentials)
        ) or (
            provider == "Rule34.xxx" and not all(self.settings.rule34_credentials)
        )
        if missing_credentials:
            QMessageBox.warning(
                self,
                f"{provider} credentials",
                f"Use Sign in to add the {provider} credentials first.",
            )
            blocker = QSignalBlocker(self.provider)
            self.provider.setCurrentText(self._last_provider)
            del blocker
            return
        self._last_provider = provider
        self._persist_settings()

    def _build_display_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        self.ambient_mode = QCheckBox("Ambient mode (blur the current image behind the viewer)")
        self.ambient_mode.setChecked(bool(self.settings.get("view/ambient_mode", True)))
        layout.addWidget(self.ambient_mode)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
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
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.addStretch(1)
        panel = QWidget()
        panel.setMaximumWidth(520)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 8, 16, 8)
        panel_layout.setSpacing(6)
        logo = QLabel()
        pixmap = QPixmap(str(self.ASSET_DIR / "waifugallery.png"))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(
                QSize(68, 68),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        logo.setFixedHeight(70)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(logo)
        title = QLabel("Waifu Gallery")
        title.setStyleSheet("font-size: 20pt; font-weight: 700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(title)
        version = QLabel(f"Version {__version__}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(
            "QLabel { color: #d8c9ff; background: #24283b; border: 1px solid #45415f; "
            "border-radius: 10px; padding: 4px 12px; }"
        )
        panel_layout.addWidget(version, 0, Qt.AlignmentFlag.AlignHCenter)
        subtitle = QLabel(
            "An independent Python media gallery for discovering, viewing, and downloading "
            "images and videos.\nCreated by calestinfisalia"
        )
        subtitle.setWordWrap(True)
        subtitle.setMinimumHeight(58)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #a9b1d6;")
        panel_layout.addWidget(subtitle)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #303449;")
        panel_layout.addWidget(separator)
        license_note = QLabel(
            "Source code: MIT License.\n"
            "Bundled icons and artwork retain their own licenses and creator rights."
        )
        license_note.setWordWrap(True)
        license_note.setMinimumHeight(64)
        license_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_note.setStyleSheet("color: #a9b1d6;")
        panel_layout.addWidget(license_note)
        layout.addWidget(panel, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        self._add_page(page, "About", "info")

    def _build_update_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("Application updates")
        title.setStyleSheet("font-size: 16pt; font-weight: 650;")
        layout.addWidget(title)
        description = QLabel(
            "Check the latest stable version published on GitHub Releases. "
            "The check runs in the background."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        current = QLabel(f"Installed version: {__version__}")
        current.setObjectName("currentAppVersion")
        layout.addWidget(current)
        self.update_status = QLabel("Check GitHub Releases for the latest version.")
        self.update_status.setWordWrap(True)
        self.update_status.setMinimumHeight(54)
        self.update_status.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.update_status)
        actions = QHBoxLayout()
        self.check_update_button = QPushButton("Check for updates")
        self.check_update_button.clicked.connect(self.check_for_updates)
        actions.addWidget(self.check_update_button)
        self.open_release_button = QPushButton("Open release page")
        self.open_release_button.hide()
        self.open_release_button.clicked.connect(self._open_release_page)
        actions.addWidget(self.open_release_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        update_note = QLabel(
            "Setup users: download and run the new setup to update the existing installation. "
            "Your settings and download folder are preserved. Portable users: replace the old "
            "executable with the new release. Packaged builds update as a complete release, "
            "not as individual .py files."
        )
        update_note.setWordWrap(True)
        update_note.setStyleSheet("color: #a9b1d6;")
        layout.addWidget(update_note)
        layout.addStretch(1)
        self._release_url = self.RELEASE_PAGE
        self._add_page(page, "Updates", "refresh-cw")

    def check_for_updates(self) -> None:
        if self._update_check_task is not None:
            return
        self.check_update_button.setEnabled(False)
        self.open_release_button.hide()
        self.update_status.setText("Checking for updates…")
        task = UpdateCheckTask()
        self._update_check_task = task
        task.signals.finished.connect(self._update_check_finished)
        self._update_pool.start(task)

    def _update_check_finished(self, tag: str, url: str, error: str) -> None:
        self._update_check_task = None
        self.check_update_button.setEnabled(True)
        if error:
            self.update_status.setText(f"Could not check for updates: {error}")
            return
        latest_version = self._version_parts(tag)
        current_version = self._version_parts(__version__)
        self._release_url = url or self.RELEASE_PAGE
        self.open_release_button.setVisible(latest_version > current_version)
        if latest_version > current_version:
            self.update_status.setText(f"Version {tag} is available. You have {__version__}.")
        else:
            self.update_status.setText(f"You're up to date (version {__version__}).")

    @staticmethod
    def _version_parts(value: str) -> tuple[int, ...]:
        numbers = re.findall(r"\d+", value)
        return tuple(int(number) for number in numbers) or (0,)

    def _open_release_page(self) -> None:
        QDesktopServices.openUrl(self._release_url)

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
            self._persist_settings()

    def add_term(self) -> None:
        values = [part.strip() for part in self.new_term.text().split(",") if part.strip()]
        existing = {self.terms.item(i).text().casefold() for i in range(self.terms.count())}
        changed = False
        for value in values:
            if value.casefold() not in existing:
                self._add_term_item(value)
                existing.add(value.casefold())
                changed = True
        self.new_term.clear()
        if changed:
            self._persist_settings()

    def _add_term_item(self, value: str) -> None:
        self._add_chip_item(self.terms, value)

    def _add_chip_item(self, target_list: QListWidget, value: str) -> None:
        item = QListWidgetItem(value)
        item.setSizeHint(QSize(0, 32))
        target_list.addItem(item)

        row = QWidget(target_list)
        row.setObjectName("customTermRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(2, 0, 2, 0)
        row_layout.setSpacing(8)
        row.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        label = QLabel(value)
        row_layout.addWidget(label)
        remove = QPushButton()
        remove.setIcon(_themed_icon(self, "x"))
        remove.setIconSize(QSize(14, 14))
        remove.setObjectName("removeCustomTermButton")
        remove.setFixedSize(22, 22)
        remove.setToolTip(f'Remove "{value}"')
        remove.setAccessibleName(f'Remove "{value}"')
        remove.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        remove.clicked.connect(
            lambda _checked=False, items=target_list, target=item: self._remove_chip_item(items, target)
        )
        row_layout.addWidget(remove)
        target_list.setItemWidget(item, row)

    def _remove_chip_item(self, target_list: QListWidget, item: QListWidgetItem) -> None:
        row = target_list.row(item)
        if row < 0:
            return
        widget = target_list.itemWidget(item)
        target_list.takeItem(row)
        if widget is not None:
            widget.deleteLater()
        if target_list in (self.terms, self.filter_list):
            self._persist_settings()

    def add_filter(self) -> None:
        existing = {self.filter_list.item(i).text().casefold() for i in range(self.filter_list.count())}
        changed = False
        for tag in self.new_filter.text().replace(",", " ").split():
            normalized = tag.strip().casefold().replace(" ", "_")
            if normalized and normalized not in existing:
                self._add_chip_item(self.filter_list, normalized)
                existing.add(normalized)
                changed = True
        self.new_filter.clear()
        if changed:
            self._persist_settings()

    def _persist_settings(self, *_: object) -> None:
        doh_provider = str(self.doh_provider.currentData())
        self.settings.set_many({
            "search/provider": self.provider.currentText(),
            "search/rating": self.default_rating.currentData(),
            "downloads/folder": self.save_folder.text(),
            "search/custom_terms": [self.terms.item(i).text() for i in range(self.terms.count())],
            "search/exclude_male": self.exclude_male.isChecked(),
            "search/allow_nsfw": self.allow_nsfw.isChecked(),
            "search/filter_gore": self.filter_gore.isChecked(),
            "search/custom_block_tags": [
                self.filter_list.item(i).text() for i in range(self.filter_list.count())
            ],
            "network/use_doh": self.use_doh.isChecked(),
            "network/doh_provider": doh_provider,
            "network/doh_custom_endpoint": self.doh_custom_endpoint.text().strip(),
            "view/ambient_mode": self.ambient_mode.isChecked(),
            "search/media_filter": self.media_filter.currentData(),
            "video/max_height": self.video_resolution.currentData(),
        })
        self.settings_changed.emit()
