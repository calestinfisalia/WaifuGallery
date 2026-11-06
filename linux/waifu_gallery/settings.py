from PySide6.QtCore import QSettings


class AppSettings:
    """Small settings facade; values are stored per-user through QSettings."""

    def __init__(self) -> None:
        self._store = QSettings()

    def get(self, key: str, default=None):
        return self._store.value(key, default)

    def set(self, key: str, value) -> None:
        self._store.setValue(key, value)
        self._store.sync()

    @property
    def gelbooru_credentials(self) -> tuple[str, str]:
        return str(self.get("gelbooru/user_id", "")).strip(), str(self.get("gelbooru/api_key", "")).strip()

    @property
    def use_doh(self) -> bool:
        return bool(self.get("network/use_doh", False))
