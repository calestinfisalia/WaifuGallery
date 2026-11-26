import unittest

from waifu_gallery.data_backup import create_payload, normalize_payload


class BackupSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    @property
    def use_doh(self):
        return False


class BackupNsfwRatingTests(unittest.TestCase):
    def test_nsfw_rating_level_round_trips_and_old_backups_default_to_both(self):
        payload = create_payload(
            BackupSettings({"search/nsfw_rating": "e"}),
            sections=("settings",),
        )

        self.assertEqual(normalize_payload(payload)["settings"]["nsfw_rating"], "e")

        legacy_payload = dict(payload)
        legacy_payload["settings"] = dict(payload["settings"])
        del legacy_payload["settings"]["nsfw_rating"]
        self.assertEqual(
            normalize_payload(legacy_payload)["settings"]["nsfw_rating"],
            "q_e",
        )

    def test_backup_rejects_unknown_nsfw_rating_level(self):
        payload = create_payload(BackupSettings(), sections=("settings",))
        payload["settings"]["nsfw_rating"] = "unknown"

        with self.assertRaisesRegex(ValueError, "unsupported NSFW rating level"):
            normalize_payload(payload)


if __name__ == "__main__":
    unittest.main()
