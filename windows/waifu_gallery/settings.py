from collections.abc import Mapping

from PySide6.QtCore import QSettings

from .doh import DOH_ENDPOINTS


def _setting_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


class AppSettings:
    """Small settings facade; values are stored per-user through QSettings."""

    def __init__(self) -> None:
        self._store = QSettings()

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
    def ambient_mode(self) -> bool:
        return _setting_bool(self.get("view/ambient_mode", True))

    @property
    def doh_endpoint(self) -> str:
        provider = str(self.get("network/doh_provider", "Cloudflare"))
        if provider == "Custom":
            return str(self.get("network/doh_custom_endpoint", "")).strip()
        return DOH_ENDPOINTS.get(provider, DOH_ENDPOINTS["Cloudflare"])
