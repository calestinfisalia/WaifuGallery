import ctypes
import logging
import logging.handlers
import os
import queue
import threading
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication, QWidget


_EVENT_NAMES = {
    0x8000: "create",
    0x8001: "destroy",
    0x8002: "show",
    0x8003: "hide",
}
_WIN_EVENT_PROC = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.HWND,
    wintypes.LONG,
    wintypes.LONG,
    wintypes.DWORD,
    wintypes.DWORD,
)


class WindowsWindowMonitor:
    """Record this application's dialogs and transient windows in a local log."""

    def __init__(self, log_path: Path | None = None) -> None:
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        self.log_path = log_path or (
            local_app_data / "WaifuGallery" / "logs" / "window-events.log"
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self._log_queue: queue.Queue = queue.Queue()
        self._logger = logging.getLogger(
            f"waifu_gallery.window_diagnostics.{id(self)}"
        )
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._queue_handler = logging.handlers.QueueHandler(self._log_queue)
        self._logger.addHandler(self._queue_handler)
        self._file_handler = logging.handlers.RotatingFileHandler(
            self.log_path,
            maxBytes=2 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        self._file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        self._listener = logging.handlers.QueueListener(
            self._log_queue, self._file_handler, respect_handler_level=True
        )
        self._thread = threading.Thread(
            target=self._run, name="WaifuGalleryWindowMonitor", daemon=True
        )
        self._widget_probe = None
        self._ready = threading.Event()
        self._thread_id = 0
        self._callback = None
        self._hooks: list[int] = []
        self._tracked_windows: dict[
            int, tuple[int, int, str, str, str, tuple[int, int, int, int]]
        ] = {}
        self._startup_error: Exception | None = None
        self._listener_started = False

    def start(self) -> None:
        self._listener.start()
        self._listener_started = True
        self._logger.info(
            "window_monitor_started pid=%d log_file=%r",
            os.getpid(),
            self.log_path.name,
        )
        self._thread.start()
        if not self._ready.wait(timeout=5):
            self.stop()
            raise RuntimeError("Timed out while starting the Windows window monitor.")
        if self._startup_error is not None:
            self.stop()
            raise RuntimeError("Could not start the Windows window monitor.") from self._startup_error

    def install_qt_widget_probe(self, app: QApplication) -> None:
        if self._widget_probe is not None:
            raise RuntimeError("The Qt widget probe is already installed.")
        self._widget_probe = _QtWidgetProbe(self._logger)
        app.installEventFilter(self._widget_probe)

    def stop(self) -> None:
        app = QApplication.instance()
        if app is not None and self._widget_probe is not None:
            app.removeEventFilter(self._widget_probe)
        self._widget_probe = None
        if self._thread.is_alive():
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW.argtypes = [
                wintypes.DWORD,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            user32.PostThreadMessageW.restype = wintypes.BOOL
            if not user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0):
                error = ctypes.get_last_error()
                self._logger.error(
                    "Could not stop the Windows window monitor: %s",
                    ctypes.WinError(error),
                )
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                self._logger.error("Windows window monitor did not stop within 3 seconds.")
        if self._listener_started:
            self._logger.info("window_monitor_stopped")
            self._listener.stop()
            self._listener_started = False
        self._logger.removeHandler(self._queue_handler)
        self._file_handler.close()

    def _run(self) -> None:
        user32 = None
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._user32 = user32
            self._kernel32 = kernel32
            self._configure_apis(user32, kernel32)
            self._thread_id = kernel32.GetCurrentThreadId()

            message = wintypes.MSG()
            user32.PeekMessageW(
                ctypes.byref(message), None, 0x0400, 0x0400, 0
            )
            self._callback = _WIN_EVENT_PROC(self._on_window_event)

            for event_id in _EVENT_NAMES:
                hook = user32.SetWinEventHook(
                    event_id,
                    event_id,
                    None,
                    self._callback,
                    0,
                    0,
                    0,
                )
                if not hook:
                    raise ctypes.WinError(ctypes.get_last_error())
                self._hooks.append(hook)

            self._ready.set()
            while True:
                result = user32.GetMessageW(
                    ctypes.byref(message), None, 0, 0
                )
                if result <= 0:
                    if result < 0:
                        raise ctypes.WinError(ctypes.get_last_error())
                    break
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        except Exception as error:
            self._startup_error = error
            self._logger.exception("Windows window monitor failed.")
            self._ready.set()
        finally:
            for hook in self._hooks:
                if user32 is not None and not user32.UnhookWinEvent(hook):
                    self._logger.error(
                        "Could not remove Windows event hook %s: %s",
                        hook,
                        ctypes.WinError(ctypes.get_last_error()),
                    )

    @staticmethod
    def _configure_apis(user32, kernel32) -> None:
        user32.SetWinEventHook.argtypes = [
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HMODULE,
            _WIN_EVENT_PROC,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        user32.SetWinEventHook.restype = wintypes.HANDLE
        user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
        user32.UnhookWinEvent.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetMessageW.restype = ctypes.c_int
        user32.PeekMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowRect.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.RECT),
        ]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.GetWindowTextW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetClassNameW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        user32.GetClassNameW.restype = ctypes.c_int
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenThread.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.OpenThread.restype = wintypes.HANDLE
        kernel32.GetProcessIdOfThread.argtypes = [wintypes.HANDLE]
        kernel32.GetProcessIdOfThread.restype = wintypes.DWORD
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

    def _on_window_event(
        self,
        _hook,
        event_id: int,
        hwnd,
        object_id: int,
        child_id: int,
        event_thread_id: int,
        _event_time: int,
    ) -> None:
        if not hwnd or object_id != 0 or child_id != 0:
            return
        try:
            self._record_window_event(event_id, hwnd, event_thread_id)
        except Exception:
            self._logger.exception(
                "Could not inspect Windows event %s for hwnd=%s.",
                _EVENT_NAMES.get(event_id, hex(event_id)),
                hwnd,
            )

    def _record_window_event(
        self, event_id: int, hwnd, event_thread_id: int
    ) -> None:
        window_id = int(hwnd)
        previous = self._tracked_windows.get(window_id)
        if int(self._user32.GetAncestor(hwnd, 2) or 0) != window_id:
            if previous is not None and event_id in {0x8001, 0x8003}:
                self._log_record(event_id, hwnd, previous)
                if event_id == 0x8001:
                    self._tracked_windows.pop(window_id, None)
            return

        record = self._read_window(hwnd, event_thread_id)
        if record is None:
            if event_id in {0x8001, 0x8003} and previous is not None:
                self._log_record(event_id, hwnd, previous)
                if event_id == 0x8001:
                    self._tracked_windows.pop(window_id, None)
            return

        process_id, _window_thread_id, process_name, class_name, title, bounds = record
        is_app_window = process_id == os.getpid()

        if event_id in {0x8000, 0x8002} and is_app_window:
            self._tracked_windows[window_id] = record
            self._log_record(event_id, hwnd, record)
        elif event_id in {0x8001, 0x8003} and window_id in self._tracked_windows:
            self._log_record(event_id, hwnd, record)
            if event_id == 0x8001:
                self._tracked_windows.pop(window_id, None)

    def _read_window(self, hwnd, event_thread_id: int):
        user32 = self._user32
        kernel32 = self._kernel32
        if not user32.IsWindowVisible(hwnd):
            return None

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        bounds = (
            rect.left,
            rect.top,
            rect.right - rect.left,
            rect.bottom - rect.top,
        )
        class_name = ctypes.create_unicode_buffer(256)
        title = ctypes.create_unicode_buffer(512)
        user32.GetClassNameW(hwnd, class_name, len(class_name))
        user32.GetWindowTextW(hwnd, title, len(title))

        process_id = wintypes.DWORD()
        window_thread_id = user32.GetWindowThreadProcessId(
            hwnd, ctypes.byref(process_id)
        )
        if not process_id.value and event_thread_id:
            window_thread_id = event_thread_id
            thread = kernel32.OpenThread(0x0800, False, event_thread_id)
            if thread:
                try:
                    process_id.value = kernel32.GetProcessIdOfThread(thread)
                finally:
                    kernel32.CloseHandle(thread)
        process_name = "<unavailable>"
        process = kernel32.OpenProcess(0x1000, False, process_id.value)
        if process:
            try:
                path = ctypes.create_unicode_buffer(1024)
                path_length = wintypes.DWORD(len(path))
                if kernel32.QueryFullProcessImageNameW(
                    process, 0, path, ctypes.byref(path_length)
                ):
                    process_name = Path(path.value).name
            finally:
                kernel32.CloseHandle(process)

        return (
            process_id.value,
            window_thread_id,
            process_name,
            class_name.value,
            title.value,
            bounds,
        )

    def _log_record(self, event_id: int, hwnd, record) -> None:
        process_id, thread_id, process_name, class_name, title, bounds = record
        self._logger.info(
            "window_event=%s pid=%d thread_id=%d process=%r hwnd=%s "
            "class=%r title=%r bounds=%r",
            _EVENT_NAMES.get(event_id, hex(event_id)),
            process_id,
            thread_id,
            process_name,
            int(hwnd),
            class_name,
            title,
            bounds,
        )


class _QtWidgetProbe(QObject):
    _MAX_WIDTH = 220
    _MAX_HEIGHT = 160

    def __init__(self, logger: logging.Logger) -> None:
        super().__init__()
        self._logger = logger

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() not in {QEvent.Type.Show, QEvent.Type.Hide}
            or not isinstance(watched, (QWidget, QWindow))
        ):
            return False
        width, height = watched.width(), watched.height()
        if width <= 0 or height <= 0 or width > self._MAX_WIDTH or height > self._MAX_HEIGHT:
            return False
        if isinstance(watched, QWidget) and not watched.isWindow():
            root = watched.window()
            top_left = watched.mapToGlobal(QPoint(0, 0))
        else:
            root = self._find_main_window(watched, width, height)
            if isinstance(watched, QWidget):
                top_left = watched.frameGeometry().topLeft()
            else:
                top_left = watched.geometry().topLeft()
        if root is None or root is watched or root.width() <= 0 or root.height() <= 0:
            return False

        center_x = top_left.x() + width / 2
        center_y = top_left.y() + height / 2
        root_rect = root.frameGeometry()
        if not (
            root_rect.left() + root.width() * 0.2
            <= center_x
            <= root_rect.left() + root.width() * 0.8
            and root_rect.top() + root.height() * 0.2
            <= center_y
            <= root_rect.top() + root.height() * 0.8
        ):
            return False

        parents = []
        parent = (
            watched.parentWidget()
            if isinstance(watched, QWidget)
            else watched.parent()
        )
        while parent is not None and len(parents) < 5:
            parents.append(
                f"{type(parent).__name__}#{parent.objectName()}"
            )
            parent = (
                parent.parentWidget()
                if isinstance(parent, QWidget)
                else parent.parent()
            )
        self._logger.info(
            "qt_popup_event=%s class=%r object=%r bounds=%r root=%r parents=%r",
            "show" if event.type() == QEvent.Type.Show else "hide",
            type(watched).__name__,
            watched.objectName(),
            (top_left.x(), top_left.y(), width, height),
            root.windowTitle(),
            parents,
        )
        return False

    @classmethod
    def _find_main_window(cls, watched, width: int, height: int) -> QWidget | None:
        app = QApplication.instance()
        if app is None:
            return None
        top_left = (
            watched.frameGeometry().topLeft()
            if isinstance(watched, QWidget)
            else watched.geometry().topLeft()
        )
        center_x = top_left.x() + width / 2
        center_y = top_left.y() + height / 2
        for candidate in app.topLevelWidgets():
            if (
                candidate is watched
                or not candidate.isVisible()
                or candidate.windowTitle() != app.applicationName()
                or candidate.width() <= cls._MAX_WIDTH
                or candidate.height() <= cls._MAX_HEIGHT
            ):
                continue
            rect = candidate.frameGeometry()
            if (
                rect.left() + candidate.width() * 0.2
                <= center_x
                <= rect.left() + candidate.width() * 0.8
                and rect.top() + candidate.height() * 0.2
                <= center_y
                <= rect.top() + candidate.height() * 0.8
            ):
                return candidate
        return None
