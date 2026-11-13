import unittest

from shiboken6 import delete

from waifu_gallery.ui.workers import BackgroundTask


class WorkerSignalTests(unittest.TestCase):
    def test_completed_task_ignores_deleted_signal_source(self):
        task = BackgroundTask("test", lambda: "finished")
        delete(task.signals)

        task.run()

    def test_failed_task_ignores_deleted_signal_source(self):
        def fail():
            raise ValueError("operation failed")

        task = BackgroundTask("test", fail)
        delete(task.signals)

        task.run()


if __name__ == "__main__":
    unittest.main()
