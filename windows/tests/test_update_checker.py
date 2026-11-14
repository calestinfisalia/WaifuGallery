import unittest
from unittest.mock import patch

from waifu_gallery.ui import updates


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class WindowsUpdateCheckerTests(unittest.TestCase):
    def test_selects_windows_release_independently(self):
        manifest = {
            "schema_version": 1,
            "platforms": {
                "windows": {"version": "0.1.17", "release_tag": "windows-v0.1.17"},
                "linux": {"version": "0.1.99", "release_tag": "linux-v0.1.99"},
                "android": {"version": "0.1.99", "release_tag": "android-v0.1.99"},
            },
        }
        release = {
            "tag_name": "windows-v0.1.17",
            "html_url": "https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.17",
            "body": "Windows fixes",
            "assets": [
                {
                    "name": updates.WINDOWS_INSTALLER,
                    "browser_download_url": (
                        "https://github.com/calestinfisalia/WaifuGallery/releases/download/"
                        "windows-v0.1.17/WaifuGallery-Setup-x64.exe"
                    ),
                    "digest": "sha256:" + "a" * 64,
                }
            ],
        }
        results = []
        task = updates.UpdateCheckTask()
        task.signals.finished.connect(lambda *args: results.append(args))
        with (
            patch.object(updates, "__version__", "0.1.16"),
            patch.object(
                updates.requests,
                "get",
                side_effect=[FakeResponse(manifest), FakeResponse(release)],
            ) as get,
        ):
            task.run()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "0.1.17")
        self.assertEqual(results[0][1], release["html_url"])
        self.assertEqual(results[0][4], "a" * 64)
        self.assertEqual(get.call_count, 2)
        self.assertIn("windows-v0.1.17", get.call_args_list[1].args[0])

    def test_equal_windows_version_does_not_fetch_any_release(self):
        manifest = {
            "schema_version": 1,
            "platforms": {
                "windows": {"version": "0.1.13", "release_tag": "windows-v0.1.13"},
                "linux": {"version": "0.1.14", "release_tag": "linux-v0.1.14"},
                "android": {"version": "0.1.12", "release_tag": "android-v0.1.12"},
            },
        }
        results = []
        task = updates.UpdateCheckTask()
        task.signals.finished.connect(lambda *args: results.append(args))
        with (
            patch.object(updates, "__version__", "0.1.13"),
            patch.object(updates.requests, "get", return_value=FakeResponse(manifest)) as get,
        ):
            task.run()

        self.assertEqual(results[0][0], "0.1.13")
        self.assertEqual(results[0][-1], "")
        get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
