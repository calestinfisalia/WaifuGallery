from collections.abc import Callable
from threading import Event

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QRunnable, QSize, Signal
from PySide6.QtGui import QImage, QImageReader
from shiboken6 import isValid

from ..providers import BooruCatalog, DownloadCancelled


class TaskSignals(QObject):
    result = Signal(str, object)
    error = Signal(str, str)
    progress = Signal(str, int)
    cancelled = Signal(str)


def _emit_if_valid(signals: TaskSignals, name: str, *args) -> None:
    if not isValid(signals):
        return
    try:
        getattr(signals, name).emit(*args)
    except RuntimeError:
        if isValid(signals):
            raise


def decode_image_bytes(content: bytes, max_dimension: int | None = 2560) -> QImage:
    """Decode off the GUI thread and cap display images to a practical size."""
    buffer = QBuffer()
    buffer.setData(QByteArray(content))
    if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
        raise ValueError("Could not open image data.")
    reader = QImageReader(buffer)
    reader.setAutoTransform(True)
    size = reader.size()
    if max_dimension and size.isValid() and max(size.width(), size.height()) > max_dimension:
        scale = max_dimension / max(size.width(), size.height())
        reader.setScaledSize(QSize(
            max(1, round(size.width() * scale)),
            max(1, round(size.height() * scale)),
        ))
    image = reader.read()
    buffer.close()
    if image.isNull():
        raise ValueError(reader.errorString() or "Unsupported image format.")
    return image


class BackgroundTask(QRunnable):
    def __init__(self, key: str, operation: Callable, *args, **kwargs) -> None:
        super().__init__()
        self.key = key
        self.operation = operation
        self.args = args
        self.kwargs = kwargs
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            result = self.operation(*self.args, **self.kwargs)
        except Exception as error:
            _emit_if_valid(self.signals, "error", self.key, str(error))
        else:
            _emit_if_valid(self.signals, "result", self.key, result)


class FileDownloadTask(QRunnable):
    def __init__(self, key, catalog: BooruCatalog, post, destination) -> None:
        super().__init__()
        self.key = key
        self.catalog = catalog
        self.post = post
        self.destination = destination
        self.signals = TaskSignals()
        self._cancel_event = Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        try:
            result = self.catalog.save_image(
                self.post,
                self.destination,
                lambda percentage: _emit_if_valid(
                    self.signals, "progress", self.key, percentage
                ),
                self._cancel_event.is_set,
            )
        except DownloadCancelled:
            _emit_if_valid(self.signals, "cancelled", self.key)
        except Exception as error:
            _emit_if_valid(self.signals, "error", self.key, str(error))
        else:
            _emit_if_valid(self.signals, "result", self.key, result)
