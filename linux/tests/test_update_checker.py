import unittest
from unittest.mock import patch

from waifu_gallery.ui import updates


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class LinuxUpdateCheckerTests(unittest.TestCase):
    def test_selects_linux_release_independently(self):
        manifest = {
            "schema_version": 1,
            "platforms": {
                "windows": {"version": "0.1.99", "release_tag": "windows-v0.1.99"},
                "linux": {"version": "0.1.13", "release_tag": "linux-v0.1.13"},
                "android": {"version": "0.1.99", "release_tag": "android-v0.1.99"},
            },
        }
        release = {
            "tag_name": "linux-v0.1.13",
            "html_url": "https://github.com/calestinfisalia/WaifuGallery/releases/tag/linux-v0.1.13",
            "body": "Linux fixes",
            "assets": [{"name": "Waifu-Gallery-0.1.13-x86_64.AppImage"}],
        }
        results = []
        task = updates.UpdateCheckTask()
        task.signals.finished.connect(lambda *args: results.append(args))
        with (
            patch.object(updates, "__version__", "0.1.12"),
            patch.object(
                updates.requests,
                "get",
                side_effect=[FakeResponse(manifest), FakeResponse(release)],
            ) as get,
        ):
            task.run()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], ("0.1.13", release["html_url"], "Linux fixes", ""))
        self.assertEqual(get.call_count, 2)
        self.assertIn("linux-v0.1.13", get.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
