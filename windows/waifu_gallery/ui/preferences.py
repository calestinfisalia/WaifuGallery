from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QPoint,
    QObject,
    QRunnable,
    QSignalBlocker,
    QSize,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QIcon,
    QPaintEvent,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QAbstractItemView,
    QFrame,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLayout,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStackedLayout,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..data_backup import create_payload, decrypt_payload, encrypt_payload
from ..doh import DOH_ENDPOINTS, set_doh_enabled, validate_doh_endpoint
from ..settings import AppSettings
from ..pin_security import has_pin, set_pin, verify_pin
from ..providers import BooruCatalog, PROVIDERS
from .backup_prompts import (
    BackupMessageDialog,
    BackupPassphraseDialog,
    BackupSectionsDialog,
)
from .dialog_chrome import FramelessResizableDialog
from .pin_prompts import PinPromptDialog
from .scrollbars import CAPSULE_SCROLLBAR_STYLE
from .updates import UpdateCheckTask, version_parts
from .themes import THEME_DESCRIPTIONS, THEME_NAMES, THEME_PALETTES, THEME_SAMPLE_COLORS


def _themed_icon(widget: QWidget, name: str) -> QIcon:
    icon_factory = getattr(widget.parent(), "_icon", None)
    if callable(icon_factory):
        return icon_factory(name)
    return QIcon(str(Path(__file__).resolve().parent.parent / "assets" / f"{name}.svg"))


class ProviderConnectionSignals(QObject):
    finished = Signal(str, str)


class ProviderConnectionTask(QRunnable):
    def __init__(self, provider: str, catalog: BooruCatalog) -> None:
        super().__init__()
        self.provider = provider
        self.catalog = catalog
        self.signals = ProviderConnectionSignals()

    def run(self) -> None:
        self.signals.finished.emit(
            self.provider,
            self.catalog.check_provider_connection(self.provider),
        )


class SafetySwitch(QCheckBox):
    def __init__(self, accessible_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsSafetyToggle")
        self.setAccessibleName(accessible_name)
        self.setToolTip(accessible_name)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, position: QPoint) -> bool:
        return self.rect().contains(position)

    def paintEvent(self, _: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        enabled = self.isEnabled()
        checked = self.isChecked()
        track = QColor("#BB9AF7" if checked else "#454B61")
        thumb = QColor("#FFFFFF" if enabled else "#A4A8B5")
        if not enabled:
            track.setAlpha(110)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(2, 3, 42, 20, 10, 10)
        painter.setBrush(thumb)
        painter.drawEllipse(24 if checked else 6, 6, 14, 14)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor("#D2B8FF"))
            painter.drawRoundedRect(0, 1, 45, 24, 12, 12)


class _AboutMascotOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("aboutMascot")
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
        )

    def sizeHint(self) -> QSize:
        return QSize(0, 0)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def paintEvent(self, _event) -> None:
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.drawPixmap(self.width() - 190, 26, self._pixmap)


def _settings_from_backup(payload: dict, settings: AppSettings, *, merge: bool) -> dict[str, object]:
    sections = set(payload["sections"])
    values: dict[str, object] = {}
    if "favorites" in sections:
        favorites = list(payload["favorites"])
        if merge:
            existing = settings.get("favorites/posts", [])
            merged = list(existing) if isinstance(existing, (list, tuple)) else []
            identities = {
                (str(item.get("provider", "")), str(item.get("post_id", "")))
                for item in merged
                if isinstance(item, dict)
            }
            for item in favorites:
                identity = (item["provider"], item["post_id"])
                if identity not in identities:
                    merged.append(item)
                    identities.add(identity)
            favorites = merged
        values["favorites/posts"] = favorites

    if "providers" in sections:
        providers = {
            "gelbooru": dict(payload["providers"]["gelbooru"]),
            "rule34": dict(payload["providers"]["rule34"]),
        }
        if merge:
            for prefix, current in (
                ("gelbooru", settings.gelbooru_credentials),
                ("rule34", settings.rule34_credentials),
            ):
                if all(current):
                    providers[prefix].update(user_id=current[0], api_key=current[1])
        for prefix, credentials in providers.items():
            values[f"{prefix}/user_id"] = credentials["user_id"]
            values[f"{prefix}/api_key"] = credentials["api_key"]

    if "settings" in sections:
        imported = payload["settings"]
        provider = imported["provider"]
        values.update({
            "search/provider": "All" if provider == "Auto" else provider,
            "search/rating": imported["rating"],
            "search/allow_nsfw": imported["allow_nsfw"],
            "search/custom_terms": imported["custom_terms"],
            "search/exclude_male": imported["exclude_male"],
            "search/filter_gore": imported["filter_gore"],
            "search/custom_block_tags": imported["custom_block_tags"],
            "search/media_filter": imported["media_filter"],
            "network/use_doh": imported["use_doh"],
            "network/doh_provider": imported["doh_provider"],
            "network/doh_custom_endpoint": imported["doh_custom_endpoint"],
            "view/ambient_mode": imported["ambient_mode"],
            "video/max_height": imported["video_max_height"],
        })

    if "theme" in sections:
        theme = payload["theme"]
        if theme in THEME_NAMES:
            values["appearance/theme"] = theme
    return values


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
            BackupMessageDialog.notify(
                self,
                "Incomplete credentials",
                "Enter both fields, or clear both fields to sign out.",
            )
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


class PreferencesDialog(FramelessResizableDialog):
    ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
    RELEASE_PAGE = "https://github.com/calestinfisalia/WaifuGallery/releases"
    settings_changed = Signal()

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._update_pool = QThreadPool.globalInstance()
        self._update_check_task = None
        self._provider_connection_tasks: dict[str, ProviderConnectionTask] = {}
        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(960, 640)
        self.setMinimumSize(860, 540)
        self._protected_page_buttons: dict[int, tuple[QPushButton, str]] = {}
        self._subpage_stacks: dict[int, QStackedWidget] = {}
        self._pending_protected_page: int | None = None
        self._safety_page_index = 0
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
        self._build_filter_tab()
        self._build_network_tab()
        self._build_display_tab()
        self._build_backup_tab()
        self._build_safety_tab()
        self._build_about_tab()
        self._build_update_tab()
        if self.settings.get_bool("parent/enabled"):
            self._select_page(self._safety_page_index)
        self._connect_auto_save()
        # Keep navigation items grouped at the top instead of spreading them
        # across the full height of the dialog.
        self.sidebar_layout.addStretch(1)
        outer.addWidget(surface)

    @staticmethod
    def _settings_section(title: str) -> tuple[QFrame, QVBoxLayout]:
        section = QFrame()
        section.setObjectName("settingsSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(14, 12, 14, 12)
        section_layout.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("settingsSectionTitle")
        section_layout.addWidget(heading)
        return section, section_layout

    @staticmethod
    def _take_section_heading(section_layout: QLayout) -> QLabel:
        item = section_layout.takeAt(0)
        heading = item.widget() if item is not None else None
        if not isinstance(heading, QLabel):
            raise RuntimeError("Settings section is missing its title label.")
        return heading

    @staticmethod
    def _settings_detail_header(
        title: QLabel,
        back: QPushButton,
        trailing: QWidget | None = None,
    ) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(back)
        layout.addWidget(title)
        layout.addStretch(1)
        if trailing is not None:
            layout.addWidget(trailing)
        return header

    def _section_menu_page(
        self,
        category: str,
        description: str,
        sections: tuple[tuple[str, str, str, QWidget], ...],
    ) -> QWidget:
        page = QWidget()
        page.setObjectName("settingsPage")
        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        stack = QStackedWidget()
        stack.setObjectName("settingsSubpages")
        outer_layout.addWidget(stack)

        menu_page = QWidget()
        menu_layout = QVBoxLayout(menu_page)
        menu_layout.setContentsMargins(16, 16, 16, 16)
        menu_layout.setSpacing(10)
        title = QLabel(category)
        title.setObjectName("settingsSectionTitle")
        menu_layout.addWidget(title)
        intro = QLabel(description)
        intro.setWordWrap(True)
        menu_layout.addWidget(intro)

        for index, (title, details, icon_name, section) in enumerate(sections, start=1):
            text_indent = "\u00a0\u00a0"
            button = QPushButton(f"{text_indent}{title}\n{text_indent}{details}")
            button.setObjectName("settingsSubmenuButton")
            button.setIcon(_themed_icon(self, icon_name))
            button.setIconSize(QSize(18, 18))
            button.setMinimumHeight(64)
            button.setStyleSheet("text-align: left; padding: 10px 14px;")
            button.clicked.connect(lambda _checked=False, target=index: stack.setCurrentIndex(target))
            menu_layout.addWidget(button)

            detail_page = QWidget()
            detail_layout = QVBoxLayout(detail_page)
            detail_layout.setContentsMargins(16, 12, 16, 16)
            detail_layout.setSpacing(8)
            back = QPushButton()
            back.setObjectName("settingsBackButton")
            back.setIcon(_themed_icon(self, "chevron-left"))
            back.setIconSize(QSize(16, 16))
            back.setFixedSize(34, 34)
            back.setToolTip(f"Back to {category}")
            back.setAccessibleName(f"Back to {category}")
            back.clicked.connect(lambda _checked=False: stack.setCurrentIndex(0))
            section_layout = section.layout()
            if section_layout is None:
                raise RuntimeError("Settings section is missing its layout.")
            heading = self._take_section_heading(section_layout)
            detail_layout.addWidget(self._settings_detail_header(heading, back))
            section.setParent(detail_page)
            detail_layout.addWidget(section)
            detail_layout.addStretch(1)
            stack.addWidget(detail_page)

        menu_layout.addStretch(1)
        stack.insertWidget(0, menu_page)
        stack.setCurrentIndex(0)
        return page

    def _build_general_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")

        search_section, search_layout = self._settings_section("Search terms")
        search_layout.addWidget(QLabel("Saved terms are used by Random when no search is entered."))
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
        search_layout.addWidget(self.terms, 1)
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
        search_layout.addLayout(row)
        download_section, download_layout = self._settings_section("Downloads")
        download_layout.addWidget(QLabel("Choose where downloaded media is saved."))
        download_layout.addWidget(QLabel("Save folder"))
        self.save_folder = QLineEdit(str(self.settings.get("downloads/folder", "")))
        self.save_folder.setReadOnly(True)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose_save_folder)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self.save_folder, 1)
        folder_row.addWidget(browse)
        download_layout.addLayout(folder_row)
        page = self._section_menu_page(
            "General",
            "Manage saved search terms and download location.",
            (
                ("Search terms", "Choose which saved terms Random can use.", "search", search_section),
                ("Downloads", "Choose where downloaded files are saved.", "download", download_section),
            ),
        )
        self._add_page(page, "General", "search")

    def _build_provider_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")

        default_section, default_layout = self._settings_section("Default provider")
        self.provider = QComboBox()
        self.provider.addItems(["All", "Danbooru", "yande.re", "Gelbooru", "Rule34.xxx"])
        self.provider.setCurrentText(str(self.settings.get("search/provider", "All")))
        self._last_provider = self.provider.currentText()
        default_layout.addWidget(QLabel("Search provider"))
        default_layout.addWidget(self.provider)
        account_section, account_layout = self._settings_section("Provider accounts")
        account_layout.addWidget(QLabel("Sign in to use providers that require an API account."))
        self.provider_buttons = {}
        for name in ("Gelbooru", "Rule34.xxx"):
            row = QHBoxLayout()
            row.setContentsMargins(0, 3, 0, 3)
            row.addWidget(QLabel(name), 1)
            button = QPushButton()
            button.setMinimumWidth(96)
            button.clicked.connect(lambda checked=False, provider=name: self.manage_provider(provider))
            self.provider_buttons[name] = button
            row.addWidget(button)
            account_layout.addLayout(row)
            self._update_provider_button(name)
        status_section, status_layout = self._settings_section("Status connection")
        status_section_description = QLabel(
            "Check the API connection and response status for each provider."
        )
        status_section_description.setWordWrap(True)
        status_layout.addWidget(status_section_description)
        self.provider_connection_button = QPushButton("Check connections")
        self.provider_connection_button.clicked.connect(self._check_provider_connections)
        self.provider_connection_status_labels = {}
        for name in PROVIDERS:
            row = QHBoxLayout()
            provider_label = QLabel(name)
            provider_label.setMinimumWidth(110)
            status_label = QLabel("Not checked")
            status_label.setObjectName("providerConnectionStatus")
            status_label.setWordWrap(True)
            self.provider_connection_status_labels[name] = status_label
            row.addWidget(provider_label)
            row.addWidget(status_label, 1)
            status_layout.addLayout(row)
        status_layout.addWidget(self.provider_connection_button)
        page = self._section_menu_page(
            "Providers",
            "Choose a provider, manage optional accounts, and check API availability.",
            (
                ("Default provider", "Select which source is used for browsing.", "images", default_section),
                ("Provider accounts", "Sign in to providers that require API credentials.", "settings-2", account_section),
                ("Status connection", "Check API response status for each provider.", "network", status_section),
            ),
        )
        self._add_page(page, "Providers", "cloud")

    def _check_provider_connections(self) -> None:
        if self._provider_connection_tasks:
            return
        catalog = BooruCatalog(
            credentials=self.settings.gelbooru_credentials,
            use_doh=self.settings.use_doh,
            rule34_credentials=self.settings.rule34_credentials,
            doh_endpoint=self.settings.doh_endpoint,
        )
        self.provider_connection_button.setEnabled(False)
        self.provider_connection_button.setText("Checking…")
        for provider in PROVIDERS:
            status_label = self.provider_connection_status_labels[provider]
            status_label.setText("Checking…")
            status_label.setStyleSheet("")
            task = ProviderConnectionTask(provider, catalog)
            task.signals.finished.connect(self._provider_connection_checked)
            self._provider_connection_tasks[provider] = task
            self._update_pool.start(task)

    def _provider_connection_checked(self, provider: str, status: str) -> None:
        status_label = self.provider_connection_status_labels[provider]
        status_label.setText(status)
        status_label.setStyleSheet(
            "color: #9ECE6A;" if status.startswith("HTTP 2") else "color: #F7768E;"
        )
        self._provider_connection_tasks.pop(provider, None)
        if not self._provider_connection_tasks:
            self.provider_connection_button.setEnabled(True)
            self.provider_connection_button.setText("Check connections")

    def _build_filter_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")

        rating_section, rating_layout = self._settings_section("Default rating")
        self.default_rating = QComboBox()
        self.default_rating.addItem("Only SFW", "sfw")
        self.default_rating.addItem("Only NSFW", "nsfw")
        self.default_rating.addItem("Show All", "all")
        rating = str(self.settings.get("search/rating", "sfw"))
        self.default_rating.setCurrentIndex(max(0, self.default_rating.findData(rating)))
        rating_layout.addWidget(QLabel("Search results"))
        rating_layout.addWidget(self.default_rating)
        rules_section, rules_layout = self._settings_section("Content rules")
        self.exclude_male = QCheckBox("Exclude posts tagged as male-only")
        self.exclude_male.setChecked(bool(self.settings.get("search/exclude_male", True)))
        self.allow_nsfw = QCheckBox("Allow NSFW results")
        self.allow_nsfw.setChecked(self.settings.get_bool("search/allow_nsfw"))
        self.filter_gore = QCheckBox("Filter posts tagged as gore")
        self.filter_gore.setChecked(bool(self.settings.get("search/filter_gore", True)))
        for control in (self.exclude_male, self.allow_nsfw, self.filter_gore):
            rules_layout.addWidget(control)
        tags_section, tags_layout = self._settings_section("Custom blocked tags")
        tags_layout.addWidget(QLabel("Posts containing these provider tags are hidden."))
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
        tags_layout.addWidget(self.filter_list, 1)
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
        tags_layout.addLayout(add_row)
        page = self._section_menu_page(
            "Filters",
            "Set the default rating and choose how content is filtered.",
            (
                ("Default rating", "Choose the rating shown by default.", "settings-2", rating_section),
                ("Content rules", "Configure rating and tag-based content rules.", "check", rules_section),
                ("Custom blocked tags", "Hide posts containing selected tags.", "x", tags_section),
            ),
        )
        self._add_page(page, "Filters", "filter")

    def _build_network_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        title = QLabel("Network")
        title.setObjectName("settingsSectionTitle")
        layout.addWidget(title)
        section, section_layout = self._settings_section("DNS over HTTPS")
        self.use_doh = QCheckBox("Use DNS over HTTPS")
        self.use_doh.setChecked(self.settings.use_doh)
        section_layout.addWidget(self.use_doh)
        section_layout.addWidget(QLabel("DNS provider"))
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
        section_layout.addWidget(self.doh_provider)
        section_layout.addWidget(self.doh_custom_label)
        section_layout.addWidget(self.doh_custom_endpoint)
        self.doh_provider.currentIndexChanged.connect(self._update_doh_controls)
        self._update_doh_controls()
        note = QLabel(
            "Uses encrypted DNS only for this app. Custom endpoints must support standard "
            "DNS-over-HTTPS (RFC 8484). The endpoint hostname itself is bootstrapped through system DNS."
        )
        note.setWordWrap(True)
        note.setObjectName("settingsHelpText")
        section_layout.addWidget(note)
        layout.addWidget(section)
        layout.addStretch(1)
        self._add_page(page, "Network", "network")

    def _update_doh_controls(self, *_args) -> None:
        custom = self.doh_provider.currentData() == "Custom"
        self.doh_custom_endpoint.setEnabled(custom)
        self.doh_custom_endpoint.setVisible(custom)
        self.doh_custom_label.setVisible(custom)

    def _update_theme_preview(self, theme: str) -> None:
        self.theme_description.setText(THEME_DESCRIPTIONS[theme])
        for name, card in self.theme_preview_cards.items():
            card.setProperty("selectedTheme", name == theme)
            card.setChecked(name == theme)
            card.style().unpolish(card)
            card.style().polish(card)

    def _change_theme(self, theme: str) -> None:
        if theme not in THEME_NAMES:
            return
        self._update_theme_preview(theme)
        change_theme = getattr(self.parent(), "change_theme", None)
        if callable(change_theme):
            change_theme(theme)
        else:
            self.settings.set("appearance/theme", theme)

    def _connect_auto_save(self) -> None:
        self.provider.currentTextChanged.connect(self._provider_changed)
        for control in (self.default_rating, self.video_resolution):
            control.currentIndexChanged.connect(self._persist_settings)
        for control in (
            self.exclude_male,
            self.allow_nsfw,
            self.filter_gore,
            self.ambient_mode,
        ):
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
            BackupMessageDialog.notify(self, "Invalid DoH endpoint", str(error))
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

    def _on_doh_configuration_changed(self, *_: object) -> None:
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
            BackupMessageDialog.notify(
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
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        title = QLabel("Display")
        title.setObjectName("settingsSectionTitle")
        layout.addWidget(title)

        appearance_section, appearance_layout = self._settings_section("Appearance")
        parent_theme = getattr(self.parent(), "current_theme", None)
        stored_theme = str(self.settings.get("appearance/theme", "Dark"))
        current_theme = parent_theme if parent_theme in THEME_NAMES else stored_theme
        if current_theme not in THEME_NAMES:
            current_theme = "Dark"
        self.theme_description = QLabel()
        self.theme_description.setObjectName("settingsHelpText")
        self.theme_description.setWordWrap(True)
        appearance_layout.addWidget(self.theme_description)
        preview_grid = QGridLayout()
        preview_grid.setContentsMargins(0, 2, 0, 0)
        preview_grid.setHorizontalSpacing(8)
        preview_grid.setVerticalSpacing(8)
        self.theme_preview_cards: dict[str, QPushButton] = {}
        for index, theme_name in enumerate(THEME_NAMES):
            card = QPushButton()
            card.setObjectName("themePreviewCard")
            card.setMinimumHeight(60)
            card.setCheckable(True)
            card.setChecked(theme_name == current_theme)
            card.setToolTip(f"Use the {theme_name} theme")
            card.setAccessibleName(f"{theme_name} theme")
            card.clicked.connect(
                lambda _checked=False, selected=theme_name: self._change_theme(selected)
            )
            card.setProperty("selectedTheme", theme_name == current_theme)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 6, 10, 8)
            card_layout.setSpacing(4)
            card_heading = QHBoxLayout()
            card_heading.setContentsMargins(0, 0, 0, 0)
            card_heading.setSpacing(4)
            name_label = QLabel(theme_name)
            name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            card_heading.addWidget(name_label)
            card_layout.addLayout(card_heading)
            samples = QHBoxLayout()
            samples.setContentsMargins(0, 0, 0, 0)
            samples.setSpacing(5)
            sample_theme = theme_name
            if theme_name == "System":
                system_window = QApplication.palette().color(QPalette.ColorRole.Window)
                sample_theme = "Dark" if system_window.lightness() < 128 else "Light"
            palette = THEME_PALETTES[sample_theme]
            for color_key in THEME_SAMPLE_COLORS:
                swatch = QFrame()
                swatch.setObjectName("themeColorSample")
                swatch.setFixedSize(32, 18)
                swatch.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                swatch.setToolTip(color_key.replace("_", " ").title())
                swatch.setStyleSheet(
                    f"background-color: {palette[color_key]}; "
                    "border: 1px solid rgba(180, 190, 220, 100); border-radius: 4px;"
                )
                samples.addWidget(swatch)
            samples.addStretch(1)
            card_layout.addLayout(samples)
            preview_grid.addWidget(card, index // 3, index % 3)
            self.theme_preview_cards[theme_name] = card
        appearance_layout.addLayout(preview_grid)
        self._update_theme_preview(current_theme)
        layout.addWidget(appearance_section)

        section, section_layout = self._settings_section("Display and playback")
        self.ambient_mode = QCheckBox("Ambient mode (blur the current image behind the viewer)")
        self.ambient_mode.setChecked(self.settings.ambient_mode)
        section_layout.addWidget(self.ambient_mode)
        section_layout.addWidget(QLabel("Video stream resolution"))
        self.video_resolution = QComboBox()
        self.video_resolution.addItem("Auto (provider source)", 0)
        self.video_resolution.addItem("Up to 2160p", 2160)
        self.video_resolution.addItem("Up to 1080p", 1080)
        self.video_resolution.addItem("Up to 720p", 720)
        self.video_resolution.addItem("Up to 480p", 480)
        resolution = int(self.settings.get("video/max_height", 0) or 0)
        resolution_index = self.video_resolution.findData(resolution)
        self.video_resolution.setCurrentIndex(max(0, resolution_index))
        section_layout.addWidget(self.video_resolution)
        note = QLabel(
            "Resolution selects the closest provider video variant at or below this limit. "
            "If a provider supplies only one file, that source is used. Playback also depends "
            "on installed codecs."
        )
        note.setWordWrap(True)
        note.setObjectName("settingsHelpText")
        section_layout.addWidget(note)
        layout.addWidget(section)
        layout.addStretch(1)
        self._add_page(page, "Display", "expand")

    def _build_backup_tab(self) -> None:
        export_section, export_layout = self._settings_section("Export encrypted backup")
        export_layout.addWidget(QLabel(
            "Create an encrypted backup containing favorites, provider credentials, and "
            "portable preferences. Device-specific settings and local safety PINs are not included."
        ))
        notice = QFrame()
        notice.setObjectName("backupNotice")
        notice_layout = QVBoxLayout(notice)
        notice_layout.setContentsMargins(14, 12, 14, 12)
        notice_layout.setSpacing(5)
        notice_title = QLabel("Keep your passphrase safe")
        notice_title.setStyleSheet("font-weight: 650;")
        notice_layout.addWidget(notice_title)
        warning = QLabel(
            "It cannot be recovered. Anyone with the backup file and its passphrase can "
            "access the included provider credentials."
        )
        warning.setWordWrap(True)
        notice_layout.addWidget(warning)
        export_layout.addWidget(notice)
        export_button = QPushButton("Export encrypted backup")
        export_button.clicked.connect(self.export_user_data)
        export_button.setMinimumHeight(38)
        export_layout.addWidget(export_button)

        import_section, import_layout = self._settings_section("Import backup")
        import_layout.addWidget(QLabel(
            "Restore or merge a saved backup. Merge keeps existing favorites and provider "
            "credentials where present; Replace uses the backup's favorites and credentials."
        ))
        import_button = QPushButton("Import backup")
        import_button.clicked.connect(self.import_user_data)
        import_button.setMinimumHeight(38)
        import_layout.addWidget(import_button)

        page = self._section_menu_page(
            "Backup & Restore",
            "Choose whether to export your data or import an existing backup.",
            (
                ("Export", "Create a passphrase-protected backup file.", "archive", export_section),
                ("Import", "Restore or merge data from a backup.", "restore", import_section),
            ),
        )
        self._add_page(page, "Backup & Restore", "archive")

    def _build_safety_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")
        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.safety_pages = QStackedWidget()
        self.safety_pages.setObjectName("settingsSubpages")
        outer_layout.addWidget(self.safety_pages)

        menu_page = QWidget()
        menu_layout = QVBoxLayout(menu_page)
        menu_layout.setContentsMargins(16, 16, 16, 16)
        menu_layout.setSpacing(10)
        title = QLabel("Safety & Privacy")
        title.setObjectName("settingsSectionTitle")
        menu_layout.addWidget(title)
        menu_layout.addWidget(QLabel("Choose a setting to manage."))

        menu_layout.addWidget(self._safety_menu_button(
            "Parental control",
            "Configure guardian PIN and content limits",
            "settings-2",
            self._open_parental_control_page,
        ))
        menu_layout.addWidget(self._safety_menu_button(
            "Favorites lock",
            "Require a separate PIN to open Favorites",
            "heart",
            self._open_favorites_lock_page,
        ))
        menu_layout.addStretch(1)
        self.safety_pages.addWidget(menu_page)

        parent_page = QWidget()
        parent_layout = QVBoxLayout(parent_page)
        parent_layout.setContentsMargins(16, 12, 16, 16)
        parent_layout.setSpacing(8)
        parent_section, parent_section_layout = self._settings_section("Parental control")
        parent_heading = self._take_section_heading(parent_section_layout)
        self.parent_toggle = SafetySwitch("Parental control")
        self.parent_toggle.setChecked(self.settings.get_bool("parent/enabled"))
        self.parent_toggle.toggled.connect(self.toggle_parental_control)
        parent_layout.addWidget(self._settings_detail_header(
            parent_heading,
            self._safety_back_button(),
            self.parent_toggle,
        ))
        parent_section_layout.addWidget(QLabel(
            "Set a maximum rating and optional allowed tags. Separate tags with commas; allowed tags use OR matching."
        ))
        limitation = QLabel(
            "These are in-app restrictions, not OS-level security. Provider tags may be missing or inaccurate."
        )
        limitation.setWordWrap(True)
        limitation.setObjectName("settingsHelpText")
        parent_section_layout.addWidget(limitation)
        self.parent_status = QLabel()
        self.parent_status.setWordWrap(True)
        parent_section_layout.addWidget(self.parent_status)

        policy_form = QFormLayout()
        self.parent_max_rating = QComboBox()
        self.parent_max_rating.setObjectName("parentMaxRating")
        self.parent_max_rating.setMinimumHeight(38)
        self.parent_max_rating.addItem("Safe", "s")
        self.parent_max_rating.addItem("Questionable", "q")
        self.parent_max_rating.addItem("Explicit", "e")
        max_rating = str(self.settings.get("parent/max_rating", "s"))
        self.parent_max_rating.setCurrentIndex(max(0, self.parent_max_rating.findData(max_rating)))
        self.parent_allowed_tags = QLineEdit()
        self.parent_allowed_tags.setObjectName("parentAllowedTags")
        self.parent_allowed_tags.setMinimumHeight(38)
        saved_allowed_tags = self.settings.get("parent/allowed_tags", [])
        if isinstance(saved_allowed_tags, (list, tuple)):
            self.parent_allowed_tags.setText(", ".join(map(str, saved_allowed_tags)))
        self.parent_allowed_tags.setPlaceholderText("Optional, e.g. landscape, animal_ears")
        policy_form.addRow("Maximum rating", self.parent_max_rating)
        policy_form.addRow("Allowed tags", self.parent_allowed_tags)
        policy_form.setHorizontalSpacing(14)
        policy_form.setVerticalSpacing(10)
        parent_section_layout.addLayout(policy_form)

        parent_actions = QHBoxLayout()
        self.parent_save_policy_button = QPushButton("Save policy")
        self.parent_save_policy_button.clicked.connect(self.save_parent_policy)
        parent_actions.addWidget(self.parent_save_policy_button)
        parent_section_layout.addLayout(parent_actions)
        parent_account_actions = QHBoxLayout()
        self.parent_change_pin_button = QPushButton("Set PIN")
        self.parent_change_pin_button.clicked.connect(self.change_parent_pin)
        parent_account_actions.addWidget(self.parent_change_pin_button)
        self.parent_remove_button = QPushButton("Remove PIN")
        self.parent_remove_button.clicked.connect(self.remove_parental_control)
        parent_account_actions.addWidget(self.parent_remove_button)
        parent_section_layout.addLayout(parent_account_actions)
        self.authorize_settings_button = QPushButton("Verify PIN to open selected settings")
        self.authorize_settings_button.hide()
        self.authorize_settings_button.clicked.connect(self._continue_to_protected_page)
        parent_section_layout.addWidget(self.authorize_settings_button)
        parent_scroll = QScrollArea()
        parent_scroll.setObjectName("safetySettingsScroll")
        parent_scroll.setFrameShape(QFrame.Shape.NoFrame)
        parent_scroll.setWidgetResizable(True)
        parent_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        parent_scroll.verticalScrollBar().setStyleSheet(CAPSULE_SCROLLBAR_STYLE)
        parent_content = QWidget()
        parent_content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        parent_content_layout = QVBoxLayout(parent_content)
        parent_content_layout.setContentsMargins(0, 0, 4, 0)
        parent_content_layout.addWidget(parent_section)
        parent_content_layout.addStretch(1)
        parent_scroll.setWidget(parent_content)
        parent_layout.addWidget(parent_scroll, 1)
        self.safety_pages.addWidget(parent_page)

        favorites_page = QWidget()
        favorites_layout = QVBoxLayout(favorites_page)
        favorites_layout.setContentsMargins(16, 12, 16, 16)
        favorites_layout.setSpacing(8)
        favorites_section, favorites_section_layout = self._settings_section("Favorites lock")
        favorites_heading = self._take_section_heading(favorites_section_layout)
        self.favorites_lock_toggle = SafetySwitch("Favorites lock")
        self.favorites_lock_toggle.setChecked(self.settings.get_bool("favorites_lock/enabled"))
        self.favorites_lock_toggle.toggled.connect(self.toggle_favorites_lock)
        favorites_layout.addWidget(self._settings_detail_header(
            favorites_heading,
            self._safety_back_button(),
            self.favorites_lock_toggle,
        ))
        favorites_section_layout.addWidget(QLabel(
            "Use a separate PIN to open Favorites. Removing the PIN does not delete saved favorites."
        ))
        self.favorites_lock_status = QLabel()
        self.favorites_lock_status.setWordWrap(True)
        favorites_section_layout.addWidget(self.favorites_lock_status)
        favorites_lock_actions = QHBoxLayout()
        self.favorites_change_pin_button = QPushButton("Set PIN")
        self.favorites_change_pin_button.clicked.connect(self.change_favorites_pin)
        favorites_lock_actions.addWidget(self.favorites_change_pin_button)
        self.favorites_remove_button = QPushButton("Remove PIN")
        self.favorites_remove_button.clicked.connect(self.remove_favorites_lock)
        favorites_lock_actions.addWidget(self.favorites_remove_button)
        favorites_section_layout.addLayout(favorites_lock_actions)
        favorites_scroll = QScrollArea()
        favorites_scroll.setObjectName("safetySettingsScroll")
        favorites_scroll.setFrameShape(QFrame.Shape.NoFrame)
        favorites_scroll.setWidgetResizable(True)
        favorites_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        favorites_scroll.verticalScrollBar().setStyleSheet(CAPSULE_SCROLLBAR_STYLE)
        favorites_content = QWidget()
        favorites_content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        favorites_content_layout = QVBoxLayout(favorites_content)
        favorites_content_layout.setContentsMargins(0, 0, 4, 0)
        favorites_content_layout.addWidget(favorites_section)
        favorites_content_layout.addStretch(1)
        favorites_scroll.setWidget(favorites_content)
        favorites_layout.addWidget(favorites_scroll, 1)
        self.safety_pages.addWidget(favorites_page)

        self._refresh_safety_status()
        self._safety_page_index = self._add_page(page, "Safety & Privacy", "shield")

    def _safety_menu_button(
        self,
        title: str,
        subtitle: str,
        icon_name: str,
        callback: Callable[[], None],
    ) -> QPushButton:
        button = QPushButton()
        button.setObjectName("safetyMenuButton")
        button.setMinimumHeight(64)
        button.setAccessibleName(f"{title}. {subtitle}")
        button.setStyleSheet("text-align: left; padding: 0;")

        content = QHBoxLayout(button)
        content.setContentsMargins(16, 8, 16, 8)
        content.setSpacing(16)

        icon = QLabel()
        icon.setPixmap(_themed_icon(self, icon_name).pixmap(QSize(20, 20)))
        icon.setFixedSize(20, 20)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        content.addWidget(icon)

        text = QLabel(f"{title}\n{subtitle}")
        text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        text.setWordWrap(True)
        text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        content.addWidget(text, 1)

        button.clicked.connect(callback)
        return button

    def _safety_back_button(self) -> QPushButton:
        button = QPushButton()
        button.setIcon(_themed_icon(self, "chevron-left"))
        button.setIconSize(QSize(16, 16))
        button.setObjectName("settingsBackButton")
        button.setFixedSize(34, 34)
        button.setToolTip("Back to Safety & Privacy")
        button.setAccessibleName("Back to Safety & Privacy")
        button.clicked.connect(self._return_to_safety_menu)
        return button

    def _reset_safety_inputs(self) -> None:
        self._pending_protected_page = None
        self._refresh_safety_status()

    def _return_to_safety_menu(self) -> None:
        self._reset_safety_inputs()
        self.safety_pages.setCurrentIndex(0)

    def _open_parental_control_page(self) -> None:
        self.safety_pages.setCurrentIndex(1)

    def _open_favorites_lock_page(self) -> None:
        self.safety_pages.setCurrentIndex(2)

    def _set_safety_status(self, field_name: str, message: str, *, error: bool = False) -> None:
        label = getattr(self, field_name)
        label.setText(message)
        label.setStyleSheet("color: #F7768E;" if error else "")

    def _prompt_pin(
        self,
        prefix: str,
        title: str,
        description: str,
        *,
        require_new: bool = False,
    ) -> str | None:
        has_existing_pin = has_pin(self.settings, prefix)
        if not has_existing_pin and not require_new:
            return None
        verify_current = (
            (lambda value: verify_pin(self.settings, prefix, value))
            if has_existing_pin else None
        )
        dialog = PinPromptDialog(
            title=title,
            description=description,
            verify_current=verify_current,
            require_new=require_new,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.new_pin if require_new else dialog.current_pin

    def _refresh_safety_status(self) -> None:
        parent_enabled = self.settings.get_bool("parent/enabled")
        parent_ready = has_pin(self.settings, "parent")
        parent_status = getattr(self, "parent_status", None)
        if parent_status is not None:
            parent_status.setText(
                (
                    "Enabled — guardian PIN and content policy are enforced."
                    if parent_ready
                    else "Enabled without a PIN. Turn it off or set a guardian PIN."
                )
                if parent_enabled else "Disabled — content is not restricted by parental control."
            )
        parent_toggle = getattr(self, "parent_toggle", None)
        if parent_toggle is not None:
            blocked = parent_toggle.blockSignals(True)
            parent_toggle.setChecked(parent_enabled)
            parent_toggle.blockSignals(blocked)
            parent_toggle.setEnabled(True)
        if hasattr(self, "parent_change_pin_button"):
            self.parent_change_pin_button.setText(
                "Change PIN" if parent_ready else "Set PIN"
            )
        if hasattr(self, "parent_remove_button"):
            self.parent_remove_button.setVisible(parent_ready)
        if hasattr(self, "authorize_settings_button"):
            self.authorize_settings_button.setVisible(self._pending_protected_page is not None)
        favorite_enabled = self.settings.get_bool("favorites_lock/enabled")
        favorite_ready = has_pin(self.settings, "favorites_lock")
        favorites_status = getattr(self, "favorites_lock_status", None)
        if favorites_status is not None:
            if favorite_enabled:
                status = (
                    "Enabled — opening Favorites requires its PIN."
                    if favorite_ready
                    else "Enabled without a PIN. Turn the lock off or set a PIN."
                )
            elif favorite_ready:
                status = "Disabled — Favorites opens without requiring its PIN."
            else:
                status = "No Favorites PIN is set."
            favorites_status.setText(status)
        favorites_toggle = getattr(self, "favorites_lock_toggle", None)
        if favorites_toggle is not None:
            blocked = favorites_toggle.blockSignals(True)
            favorites_toggle.setChecked(favorite_enabled)
            favorites_toggle.blockSignals(blocked)
            favorites_toggle.setEnabled(True)
        if hasattr(self, "favorites_change_pin_button"):
            self.favorites_change_pin_button.setText(
                "Change PIN" if favorite_ready else "Set PIN"
            )
        if hasattr(self, "favorites_remove_button"):
            self.favorites_remove_button.setVisible(favorite_ready)
        self._update_parent_guarded_navigation()

    def save_parent_policy(self) -> None:
        if self.settings.get_bool("parent/enabled"):
            if self._prompt_pin(
                "parent",
                "Verify guardian PIN",
                "Enter the guardian PIN to save these content rules.",
            ) is None:
                return
        tags = list(dict.fromkeys(
            tag.strip().casefold().replace(" ", "_")
            for tag in self.parent_allowed_tags.text().split(",")
            if tag.strip()
        ))
        self.settings.set_many({
            "parent/max_rating": self.parent_max_rating.currentData(),
            "parent/allowed_tags": tags,
        })
        self._set_safety_status("parent_status", "Parental policy saved.")
        self.settings_changed.emit()

    def toggle_parental_control(self, checked: bool | None = None) -> None:
        enabled = self.settings.get_bool("parent/enabled")
        requested = not enabled if checked is None else checked
        if requested == enabled:
            return
        pin_ready = has_pin(self.settings, "parent")
        pin = None
        if requested or pin_ready:
            pin = self._prompt_pin(
                "parent",
                "Enable parental control" if requested else "Disable parental control",
                (
                    "Create a guardian PIN to protect parental controls."
                    if requested and not pin_ready
                    else "Enter the guardian PIN to continue."
                ),
                require_new=requested and not pin_ready,
            )
            if pin is None:
                blocked = self.parent_toggle.blockSignals(True)
                self.parent_toggle.setChecked(enabled)
                self.parent_toggle.blockSignals(blocked)
                return
        if requested and not pin_ready:
            if pin is None:
                blocked = self.parent_toggle.blockSignals(True)
                self.parent_toggle.setChecked(enabled)
                self.parent_toggle.blockSignals(blocked)
                return
            set_pin(self.settings, "parent", pin)
        self.settings.set("parent/enabled", requested)
        self._refresh_safety_status()
        self._set_safety_status(
            "parent_status",
            "Parental control enabled." if requested else "Parental control disabled.",
        )
        self.settings_changed.emit()

    def change_parent_pin(self) -> None:
        creating = not has_pin(self.settings, "parent")
        pin = self._prompt_pin(
            "parent",
            "Set guardian PIN" if creating else "Change guardian PIN",
            (
                "Choose a 4–12 digit PIN for parental control."
                if creating
                else "Verify your current PIN and choose a new one."
            ),
            require_new=True,
        )
        if pin is None:
            return
        set_pin(self.settings, "parent", pin)
        self._refresh_safety_status()
        self._set_safety_status(
            "parent_status",
            "Guardian PIN created." if creating else "Guardian PIN changed.",
        )
        self.settings_changed.emit()

    def remove_parental_control(self) -> None:
        if not has_pin(self.settings, "parent"):
            self._set_safety_status("parent_status", "No parental control PIN is set.", error=True)
            return
        if self._prompt_pin(
            "parent",
            "Remove guardian PIN",
            "Verify the guardian PIN before removing it and disabling parental control.",
        ) is None:
            return
        confirmed = BackupMessageDialog.confirm(
            self,
            "Remove guardian PIN",
            "Remove the guardian PIN and disable parental control? Saved content rules will be kept.",
        )
        if not confirmed:
            return
        self.settings.set_many({
            "parent/enabled": False,
            "parent/pin_salt": "",
            "parent/pin_hash": "",
            "parent/pin_failures": 0,
            "parent/pin_locked_until": 0,
        })
        self._pending_protected_page = None
        self._refresh_safety_status()
        self._set_safety_status(
            "parent_status",
            "Guardian PIN removed and parental control disabled. Policy settings were kept.",
        )
        self.settings_changed.emit()

    def toggle_favorites_lock(self, checked: bool | None = None) -> None:
        enabled = self.settings.get_bool("favorites_lock/enabled")
        requested = not enabled if checked is None else checked
        if requested == enabled:
            return
        pin_ready = has_pin(self.settings, "favorites_lock")
        pin = None
        if requested or pin_ready:
            pin = self._prompt_pin(
                "favorites_lock",
                "Enable Favorites lock" if requested else "Disable Favorites lock",
                (
                    "Create a 4–12 digit PIN to protect Favorites."
                    if requested and not pin_ready
                    else "Enter the Favorites PIN to continue."
                ),
                require_new=requested and not pin_ready,
            )
            if pin is None:
                blocked = self.favorites_lock_toggle.blockSignals(True)
                self.favorites_lock_toggle.setChecked(enabled)
                self.favorites_lock_toggle.blockSignals(blocked)
                return
        if requested and not pin_ready:
            if pin is None:
                blocked = self.favorites_lock_toggle.blockSignals(True)
                self.favorites_lock_toggle.setChecked(enabled)
                self.favorites_lock_toggle.blockSignals(blocked)
                return
            set_pin(self.settings, "favorites_lock", pin)
        self.settings.set("favorites_lock/enabled", requested)
        self._refresh_safety_status()
        self._set_safety_status(
            "favorites_lock_status",
            "Favorites lock enabled." if requested else "Favorites lock disabled.",
        )
        self.settings_changed.emit()

    def change_favorites_pin(self) -> None:
        creating = not has_pin(self.settings, "favorites_lock")
        pin = self._prompt_pin(
            "favorites_lock",
            "Set Favorites PIN" if creating else "Change Favorites PIN",
            (
                "Choose a 4–12 digit PIN to protect Favorites."
                if creating
                else "Verify your current PIN and choose a new one."
            ),
            require_new=True,
        )
        if pin is None:
            return
        set_pin(self.settings, "favorites_lock", pin)
        self._refresh_safety_status()
        self._set_safety_status(
            "favorites_lock_status",
            "Favorites PIN created." if creating else "Favorites PIN changed.",
        )
        self.settings_changed.emit()

    def remove_favorites_lock(self) -> None:
        if not has_pin(self.settings, "favorites_lock"):
            self._set_safety_status("favorites_lock_status", "No Favorites PIN is set.", error=True)
            return
        if self._prompt_pin(
            "favorites_lock",
            "Remove Favorites PIN",
            "Verify the Favorites PIN before removing the lock. Saved favorites will remain.",
        ) is None:
            return
        confirmed = BackupMessageDialog.confirm(
            self,
            "Remove Favorites PIN",
            "Remove the Favorites PIN? Saved favorites will be kept.",
        )
        if not confirmed:
            return
        self.settings.set_many({
            "favorites_lock/enabled": False,
            "favorites_lock/pin_salt": "",
            "favorites_lock/pin_hash": "",
            "favorites_lock/pin_failures": 0,
            "favorites_lock/pin_locked_until": 0,
        })
        self._refresh_safety_status()
        self._set_safety_status(
            "favorites_lock_status",
            "Favorites lock removed. Saved favorites were kept.",
        )
        self.settings_changed.emit()

    def export_user_data(self) -> None:
        sections_dialog = BackupSectionsDialog(self)
        if sections_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        passphrase_dialog = BackupPassphraseDialog(
            title="Encrypt backup",
            description=(
                "Create a backup passphrase with at least 8 characters. "
                "This is separate from your app PIN."
            ),
            confirm_passphrase=True,
            parent=self,
        )
        if passphrase_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        passphrase = passphrase_dialog.passphrase
        try:
            contents = encrypt_payload(
                create_payload(self.settings, sections_dialog.selected_sections),
                passphrase,
            )
        except (TypeError, ValueError, OSError) as error:
            BackupMessageDialog.ask(self, "Could not create backup", str(error), ("OK",))
            return
        save_path = QFileDialog.getSaveFileName(
            self,
            "Save encrypted backup",
            str(Path.home() / "Documents" / "waifu-gallery-backup.wgbak"),
            "Waifu Gallery backups (*.wgbak *.json)",
        )[0]
        if not save_path:
            return
        backup_path = Path(save_path)
        if backup_path.suffix.lower() not in {".wgbak", ".json"}:
            backup_path = backup_path.with_suffix(".wgbak")
        try:
            with backup_path.open("w", encoding="utf-8") as backup_file:
                backup_file.write(contents)
        except OSError as error:
            BackupMessageDialog.ask(self, "Could not save backup", str(error), ("OK",))
            return
        BackupMessageDialog.ask(
            self, "Backup created", "Your encrypted backup was saved.", ("OK",)
        )

    def import_user_data(self) -> None:
        selected_path = QFileDialog.getOpenFileName(
            self,
            "Import encrypted backup",
            str(Path.home() / "Documents"),
            "Waifu Gallery backups (*.wgbak *.json)",
        )[0]
        if not selected_path:
            return
        passphrase_dialog = BackupPassphraseDialog(
            title="Decrypt backup",
            description="Enter the passphrase used when this backup was created.",
            parent=self,
        )
        if passphrase_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        passphrase = passphrase_dialog.passphrase
        try:
            with open(selected_path, "rb") as backup_file:
                raw_contents = backup_file.read(32 * 1024 * 1024 + 1)
            if len(raw_contents) > 32 * 1024 * 1024:
                raise ValueError("The backup file is too large.")
            contents = raw_contents.decode("utf-8")
            payload = decrypt_payload(contents, passphrase)
        except (OSError, UnicodeError, ValueError) as error:
            BackupMessageDialog.ask(self, "Could not import backup", str(error), ("OK",))
            return

        sections = set(payload["sections"])
        summary_parts = []
        if "favorites" in sections:
            summary_parts.append(f"{len(payload['favorites'])} favorites")
        if "providers" in sections:
            account_count = sum(
                bool(item["user_id"]) for item in payload["providers"].values()
            )
            summary_parts.append(f"{account_count} provider logins")
        if "theme" in sections:
            if payload["theme"] in THEME_NAMES:
                summary_parts.append(f"{payload['theme']} theme")
            else:
                summary_parts.append("theme (unsupported here; current theme will remain unchanged)")
        if "settings" in sections:
            summary_parts.append("portable settings")
        summary = ", ".join(summary_parts)
        choice = BackupMessageDialog.ask(
            self,
            "Import user data",
            f"Import {summary}\n\n"
            "Merge adds favorites and keeps existing provider logins. Replace replaces the "
            "included favorites and provider logins. Only the sections listed above are changed; "
            "other data stays as it is.",
            ("Merge", "Replace", "Cancel"),
            default_button="Merge",
        )
        if choice not in ("Merge", "Replace"):
            return

        try:
            values = _settings_from_backup(payload, self.settings, merge=choice == "Merge")
            if "settings" in sections:
                imported_settings = payload["settings"]
                endpoint = (
                    imported_settings["doh_custom_endpoint"]
                    if imported_settings["doh_provider"] == "Custom"
                    else DOH_ENDPOINTS[imported_settings["doh_provider"]]
                )
                if imported_settings["use_doh"]:
                    endpoint = validate_doh_endpoint(endpoint)
                set_doh_enabled(
                    imported_settings["use_doh"],
                    endpoint if imported_settings["use_doh"] else None,
                )
            self.settings.set_many(values)
        except (OSError, TypeError, ValueError) as error:
            BackupMessageDialog.ask(self, "Could not import backup", str(error), ("OK",))
            return
        self.settings_changed.emit()
        BackupMessageDialog.ask(
            self, "Backup imported", "Your user data was imported.", ("OK",)
        )
        self.accept()

    def _build_about_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")
        overlay = QStackedLayout(page)
        overlay.setContentsMargins(0, 0, 0, 0)
        overlay.setStackingMode(QStackedLayout.StackingMode.StackAll)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 20, 16, 20)
        content_layout.addStretch(1)
        app_info = QWidget()
        app_info.setMaximumWidth(420)
        app_layout = QVBoxLayout(app_info)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(4)
        logo = QLabel()
        pixmap = QPixmap(str(self.ASSET_DIR / "waifugallery.png"))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(
                QSize(42, 42),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        title = QLabel("Waifu Gallery")
        title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_layout.addWidget(title)
        version = QLabel(f"Version {__version__}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(
            "QLabel { color: #d8c9ff; background: #24283b; border: 1px solid #45415f; "
            "border-radius: 10px; padding: 4px 12px; }"
        )
        app_layout.addWidget(version, 0, Qt.AlignmentFlag.AlignHCenter)
        subtitle = QLabel(
            "An independent Python media gallery for discovering, viewing, and downloading "
            "images and videos.\nCreated by calestinfisalia"
        )
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(270)
        subtitle.setMinimumHeight(68)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #a9b1d6;")
        app_layout.addWidget(subtitle, 0, Qt.AlignmentFlag.AlignHCenter)
        content_layout.addWidget(app_info, 0, Qt.AlignmentFlag.AlignHCenter)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setMaximumWidth(360)
        separator.setStyleSheet("color: #303449;")
        content_layout.addWidget(separator, 0, Qt.AlignmentFlag.AlignHCenter)
        license_note = QLabel(
            "Source code: MIT License.\n"
            "Bundled icons and artwork retain their own licenses and creator rights."
        )
        license_note.setWordWrap(True)
        license_note.setMaximumWidth(340)
        license_note.setMinimumHeight(64)
        license_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_note.setStyleSheet("color: #a9b1d6;")
        content_layout.addWidget(license_note, 0, Qt.AlignmentFlag.AlignHCenter)
        content_layout.addStretch(2)
        overlay.addWidget(content)

        mascot = _AboutMascotOverlay(page)
        overlay.addWidget(mascot)
        overlay.setCurrentWidget(mascot)
        self._add_page(page, "About", "info")

    def _build_update_tab(self) -> None:
        page = QWidget()
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        title = QLabel("Updates")
        title.setObjectName("settingsSectionTitle")
        layout.addWidget(title)
        section, section_layout = self._settings_section("Application updates")
        description = QLabel(
            "Check the latest stable version published on GitHub Releases. "
            "The check runs in the background."
        )
        description.setWordWrap(True)
        section_layout.addWidget(description)
        current = QLabel(f"Installed version: {__version__}")
        current.setObjectName("currentAppVersion")
        section_layout.addWidget(current)
        self.update_status = QLabel("Check GitHub Releases for the latest version.")
        self.update_status.setWordWrap(True)
        self.update_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        section_layout.addWidget(self.update_status)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.check_update_button = QPushButton("Check for updates")
        self.check_update_button.clicked.connect(self.check_for_updates)
        actions.addWidget(self.check_update_button)
        self.open_release_button = QPushButton("Open release page")
        self.open_release_button.hide()
        self.open_release_button.clicked.connect(self._open_release_page)
        actions.addWidget(self.open_release_button)
        actions.addStretch(1)
        section_layout.addLayout(actions)
        layout.addWidget(section)
        update_note = QLabel(
            "Setup users: download and run the new setup to update the existing installation. "
            "Your settings and download folder are preserved. Portable users: replace the old "
            "executable with the new release. Packaged builds update as a complete release, "
            "not as individual .py files."
        )
        update_note.setWordWrap(True)
        update_note.setObjectName("settingsHelpText")
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

    def _update_check_finished(
        self,
        tag: str,
        url: str,
        _notes: str,
        _download_url: str,
        _sha256: str,
        error: str,
    ) -> None:
        self._update_check_task = None
        self.check_update_button.setEnabled(True)
        if error:
            self.update_status.setText(f"Could not check for updates: {error}")
            return
        latest_version = version_parts(tag)
        current_version = version_parts(__version__)
        self._release_url = url or self.RELEASE_PAGE
        self.open_release_button.setVisible(latest_version > current_version)
        if latest_version > current_version:
            self.update_status.setText(f"Version {tag} is available. You have {__version__}.")
        else:
            self.update_status.setText(f"You're up to date (version {__version__}).")

    def _open_release_page(self) -> None:
        QDesktopServices.openUrl(self._release_url)

    def _add_page(self, page: QWidget, title: str, icon_name: str) -> int:
        button = QPushButton(f"\u00a0{title.replace('&', '&&')}")
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
        subpage_stack = page.findChild(QStackedWidget, "settingsSubpages")
        if subpage_stack is not None:
            self._subpage_stacks[index] = subpage_stack
        button.clicked.connect(lambda checked=False, page_index=index: self._select_page(page_index))
        self.sidebar_layout.addWidget(button)
        self.nav_buttons.append(button)
        if title in {"General", "Providers", "Filters", "Backup & Restore"}:
            self._protected_page_buttons[index] = (button, title)
            self._update_parent_guarded_navigation()
        if index == 0:
            button.setChecked(True)
        return index

    def _select_page(self, index: int) -> None:
        if (
            index in self._protected_page_buttons
            and self.settings.get_bool("parent/enabled")
            and has_pin(self.settings, "parent")
            and self._pending_protected_page != index
        ):
            self._reset_safety_inputs()
            self._pending_protected_page = index
            self.pages.setCurrentIndex(self._safety_page_index)
            self.safety_pages.setCurrentIndex(1)
            self._set_safety_status(
                "parent_status",
                "Enter the guardian PIN, then select Verify PIN to open selected settings.",
            )
            self.authorize_settings_button.show()
            for position, button in enumerate(self.nav_buttons):
                button.setChecked(position == self._safety_page_index)
            return
        self.pages.setCurrentIndex(index)
        subpage_stack = self._subpage_stacks.get(index)
        if subpage_stack is not None:
            subpage_stack.setCurrentIndex(0)
            self._reset_safety_inputs()
        if index != self._safety_page_index:
            self._reset_safety_inputs()
            if hasattr(self, "authorize_settings_button"):
                self.authorize_settings_button.hide()
        for position, button in enumerate(self.nav_buttons):
            button.setChecked(position == index)

    def _continue_to_protected_page(self) -> None:
        target = self._pending_protected_page
        if target is None:
            return
        if self._prompt_pin(
            "parent",
            "Verify guardian PIN",
            "Enter the guardian PIN to open the selected settings.",
        ) is None:
            return
        self.authorize_settings_button.hide()
        self._select_page(target)

    def _update_parent_guarded_navigation(self) -> None:
        enabled = self.settings.get_bool("parent/enabled")
        for button, title in self._protected_page_buttons.values():
            button.setText((f"{title} [PIN]" if enabled else title).replace("&", "&&"))
            button.setToolTip(
                "Guardian PIN required while parental control is enabled."
                if enabled else ""
            )
            button.setAccessibleName(
                f"{title}, guardian PIN required" if enabled else title
            )

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
            confirmed = BackupMessageDialog.confirm(
                self,
                f"Log out of {provider}?",
                "This will delete the saved user ID and API key from this app.",
            )
            if confirmed:
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
            "video/max_height": self.video_resolution.currentData(),
        })
        self.settings_changed.emit()
