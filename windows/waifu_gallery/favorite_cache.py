import hashlib
import logging
import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QImage


_LOGGER = logging.getLogger(__name__)


def _cache_directory() -> Path:
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    if not location:
        raise OSError("The application cache directory is unavailable.")
    return Path(location) / "favorite-thumbnails"


def _cache_path(favorite_id: str, source_url: str) -> Path:
    cache_key = hashlib.sha256(
        f"{favorite_id}\n{source_url}".encode("utf-8")
    ).hexdigest()
    return _cache_directory() / f"{cache_key}.png"


def load_favorite_thumbnail(favorite_id: str, source_url: str) -> QImage | None:
    try:
        path = _cache_path(favorite_id, source_url)
        if not path.is_file():
            return None
        image = QImage(str(path))
    except OSError:
        _LOGGER.warning("Could not read favorite thumbnail cache.", exc_info=True)
        return None
    if image.isNull():
        _LOGGER.warning("Ignoring unreadable favorite thumbnail cache file: %s", path)
        return None
    return image


def save_favorite_thumbnail(
    favorite_id: str, source_url: str, image: QImage
) -> None:
    if image.isNull():
        return
    temporary_path = None
    try:
        directory = _cache_directory()
        directory.mkdir(parents=True, exist_ok=True)
        path = _cache_path(favorite_id, source_url)
        with tempfile.NamedTemporaryFile(
            dir=directory, suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        if not image.save(str(temporary_path), "PNG"):
            raise OSError("Could not encode the favorite thumbnail cache image.")
        os.replace(temporary_path, path)
    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                _LOGGER.warning(
                    "Could not remove temporary favorite thumbnail cache file: %s",
                    temporary_path,
                    exc_info=True,
                )
        _LOGGER.warning("Could not save favorite thumbnail cache file.", exc_info=True)


def remove_favorite_thumbnail(favorite_id: str, source_url: str) -> None:
    try:
        path = _cache_path(favorite_id, source_url)
        path.unlink(missing_ok=True)
    except OSError:
        _LOGGER.warning("Could not remove favorite thumbnail cache file.", exc_info=True)


def favorite_thumbnail_cache_size() -> int:
    directory = _cache_directory()
    if not directory.exists():
        return 0
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def clear_favorite_thumbnail_cache() -> None:
    directory = _cache_directory()
    if not directory.exists():
        return
    paths = sorted(directory.rglob("*"), key=lambda path: len(path.parts), reverse=True)
    for path in paths:
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    directory.rmdir()
