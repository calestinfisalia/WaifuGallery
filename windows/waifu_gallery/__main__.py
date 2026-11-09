import os
import sys

# Prefer Windows hardware video decoders when Qt's FFmpeg backend supports
# them. setdefault keeps an explicit user/system choice intact.
if sys.platform == "win32":
    os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "d3d11va,dxva2")

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Waifu Gallery")
    app.setOrganizationName("Fisalia Cantarella")
    window_monitor = None
    if sys.platform == "win32":
        from .window_diagnostics import WindowsWindowMonitor

        try:
            monitor = WindowsWindowMonitor()
            monitor.start()
            try:
                monitor.install_qt_widget_probe(app)
            except Exception:
                monitor.stop()
                raise
            window_monitor = monitor
        except (OSError, RuntimeError) as error:
            print(f"Windows window diagnostics could not start: {error}", file=sys.stderr)
            window_monitor = None
    if window_monitor is not None:
        app.aboutToQuit.connect(window_monitor.stop)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
