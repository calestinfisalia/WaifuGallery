from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal

from ..providers import BooruCatalog


class TaskSignals(QObject):
    result = Signal(str, object)
    error = Signal(str, str)
    progress = Signal(str, int)


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
            self.signals.result.emit(self.key, self.operation(*self.args, **self.kwargs))
        except Exception as error:
            self.signals.error.emit(self.key, str(error))


class FileDownloadTask(QRunnable):
    def __init__(self, key, catalog: BooruCatalog, post, destination) -> None:
        super().__init__()
        self.key = key
        self.catalog = catalog
        self.post = post
        self.destination = destination
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            result = self.catalog.save_image(
                self.post,
                self.destination,
                lambda percentage: self.signals.progress.emit(self.key, percentage),
            )
            self.signals.result.emit(self.key, result)
        except Exception as error:
            self.signals.error.emit(self.key, str(error))
