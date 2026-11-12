from collections.abc import Mapping
from pathlib import Path
import sys

from PySide6.QtCore import QSettings

from .doh import DOH_ENDPOINTS


def _setting_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def _merge_favorites(current, legacy) -> list:
    merged = []
    seen = set()
    for collection in (current, legacy):
        if not isinstance(collection, (list, tuple)):
            continue
        for item in collection:
            if isinstance(item, dict):
                identity = (str(item.get("provider", "")), str(item.get("post_id", "")))
                if identity in seen:
                    continue
                seen.add(identity)
            elif item in merged:
                continue
            merged.append(item)
    return merged


def migrate_legacy_settings(settings: QSettings, legacy_path: str | Path | None = None) -> bool:
    if not sys.platform.startswith("linux"):
        return False
    target_path = Path(settings.fileName()).expanduser()
    source_path = Path(legacy_path or (
        Path.home() / ".config" / "Fisalia Cantarella" / "Waifu Gallery.conf"
    )).expanduser()
    try:
        if not source_path.is_file() or source_path.resolve() == target_path.resolve():
            return False
    except OSError:
        return False

    migration_key = "migration/legacy_qsettings_v1"
    if _setting_bool(settings.value(migration_key, False)):
        return False

    legacy = QSettings(str(source_path), QSettings.Format.IniFormat)
    legacy.sync()
    if legacy.status() != QSettings.Status.NoError:
        return False

    changed = False
    for key in legacy.allKeys():
        legacy_value = legacy.value(key)
        current_value = settings.value(key, None)
        if key == "favorites/posts":
            merged = _merge_favorites(current_value, legacy_value)
            if merged != (current_value if isinstance(current_value, (list, tuple)) else []):
                settings.setValue(key, merged)
                changed = True
        elif current_value in (None, "", [], {}):
            if legacy_value not in (None, "", [], {}):
                settings.setValue(key, legacy_value)
                changed = True

    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        return False
    settings.setValue(migration_key, True)
    settings.sync()
    return changed and settings.status() == QSettings.Status.NoError


class AppSettings:
    """Small settings facade; values are stored per-user through QSettings."""

    def __init__(self) -> None:
        self._store = QSettings()
        migrate_legacy_settings(self._store)

    def get(self, key: str, default=None):
        return self._store.value(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        return _setting_bool(self.get(key, default))

    def set(self, key: str, value) -> None:
        self._store.setValue(key, value)
        self._store.sync()

    def set_many(self, values: Mapping[str, object]) -> None:
        for key, value in values.items():
            self._store.setValue(key, value)
        self._store.sync()

    @property
    def gelbooru_credentials(self) -> tuple[str, str]:
        return str(self.get("gelbooru/user_id", "")).strip(), str(self.get("gelbooru/api_key", "")).strip()

    @property
    def rule34_credentials(self) -> tuple[str, str]:
        return str(self.get("rule34/user_id", "")).strip(), str(self.get("rule34/api_key", "")).strip()

    @property
    def use_doh(self) -> bool:
        return _setting_bool(self.get("network/use_doh", False))

    @property
    def doh_endpoint(self) -> str:
        provider = str(self.get("network/doh_provider", "Cloudflare"))
        if provider == "Custom":
            return str(self.get("network/doh_custom_endpoint", "")).strip()
        return DOH_ENDPOINTS.get(provider, DOH_ENDPOINTS["Cloudflare"])
