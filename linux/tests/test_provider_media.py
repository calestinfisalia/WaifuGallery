import unittest
from threading import Event, Thread
from unittest.mock import call, patch

import requests

from waifu_gallery.providers import BooruCatalog, ProviderError


class ImageResponse:
    ok = True
    status_code = 200
    headers = {"Content-Type": "image/jpeg", "Content-Length": "7"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def iter_content(self, chunk_size):
        yield b"preview"


class ProviderMediaTests(unittest.TestCase):
    def test_all_search_merges_provider_results_in_round_robin_order(self):
        catalog = BooruCatalog()
        slow_started = Event()
        release_slow = Event()
        finished = Event()
        results = []
        errors = []
        yande_post = BooruCatalog._normalize(
            {
                "id": 234,
                "file_url": "https://yande.re/data/slow.jpg",
                "rating": "s",
                "tags": "1girl",
            },
            "yande.re",
        )
        danbooru_post = BooruCatalog._normalize(
            {
                "id": 239,
                "file_url": "https://danbooru.donmai.us/data/fast.jpg",
                "rating": "s",
                "tags": "1girl",
            },
            "Danbooru",
        )

        def search_provider(provider, *_args, **_kwargs):
            if provider == "yande.re":
                slow_started.set()
                release_slow.wait()
                return [yande_post], True
            return [danbooru_post], False

        def run_search():
            try:
                results.append(catalog._search_all("", "sfw", ["yande.re", "Danbooru"], 1, 50))
            except Exception as error:
                errors.append(error)
            finally:
                finished.set()

        with patch.object(catalog, "_search_provider", side_effect=search_provider):
            thread = Thread(target=run_search)
            thread.start()
            slow_provider_started = slow_started.wait(1)
            returned_before_slow_provider = finished.wait(0.05)
            release_slow.set()
            thread.join(1)

        self.assertTrue(slow_provider_started)
        self.assertFalse(returned_before_slow_provider)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual(
            [post.provider for post in results[0].posts],
            ["yande.re", "Danbooru"],
        )
        self.assertTrue(results[0].has_more)

    def test_all_random_returns_first_provider_with_media(self):
        catalog = BooruCatalog()
        slow_started = Event()
        release_slow = Event()
        finished = Event()
        results = []
        errors = []
        fast_post = BooruCatalog._normalize(
            {
                "id": 235,
                "file_url": "https://danbooru.donmai.us/data/fast.jpg",
                "rating": "s",
                "tags": "1girl",
            },
            "Danbooru",
        )

        def search_provider(provider, *_args, **_kwargs):
            if provider == "yande.re":
                slow_started.set()
                release_slow.wait()
                return [], False
            return [fast_post], False

        def run_random():
            try:
                results.append(catalog.random_image("sfw", "All"))
            except Exception as error:
                errors.append(error)
            finally:
                finished.set()

        with (
            patch.object(catalog, "_search_provider", side_effect=search_provider),
            patch.object(catalog, "fetch_post_preview", return_value=b"preview"),
        ):
            thread = Thread(target=run_random)
            thread.start()
            returned_before_slow_provider = finished.wait(1)
            release_slow.set()
            thread.join(1)

        self.assertTrue(slow_started.is_set())
        self.assertTrue(returned_before_slow_provider)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual(results[0][0].provider, "Danbooru")
        self.assertEqual(results[0][1], b"preview")

    def test_all_random_post_returns_first_api_result_without_waiting_for_preview(self):
        catalog = BooruCatalog()
        slow_started = Event()
        release_slow = Event()
        finished = Event()
        results = []
        errors = []
        yande_post = BooruCatalog._normalize(
            {
                "id": 236,
                "file_url": "https://yande.re/data/fast.jpg",
                "rating": "s",
                "tags": "1girl",
            },
            "yande.re",
        )
        danbooru_post = BooruCatalog._normalize(
            {
                "id": 237,
                "file_url": "https://danbooru.donmai.us/data/slow.jpg",
                "rating": "s",
                "tags": "1girl",
            },
            "Danbooru",
        )

        def random_post(_rating, provider, _query):
            if provider == "Danbooru":
                slow_started.set()
                release_slow.wait()
                return danbooru_post
            slow_started.wait(1)
            return yande_post

        def run_random():
            try:
                results.append(catalog.random_post("sfw", "All"))
            except Exception as error:
                errors.append(error)
            finally:
                finished.set()

        with (
            patch.object(catalog, "_random_post_from_provider", side_effect=random_post),
            patch.object(catalog, "fetch_post_preview") as fetch_preview,
        ):
            thread = Thread(target=run_random)
            thread.start()
            returned_before_slow_provider = finished.wait(1)
            release_slow.set()
            thread.join(1)

        self.assertTrue(slow_started.is_set())
        self.assertTrue(returned_before_slow_provider)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual(results[0].provider, "yande.re")
        fetch_preview.assert_not_called()

    def test_all_random_post_skips_providers_with_failed_previews(self):
        catalog = BooruCatalog()
        post = BooruCatalog._normalize(
            {
                "id": 238,
                "file_url": "https://danbooru.donmai.us/data/fallback.jpg",
                "rating": "s",
                "tags": "1girl",
            },
            "Danbooru",
        )
        requested_providers = []

        def random_post(_rating, provider, _query):
            requested_providers.append(provider)
            return post

        with patch.object(catalog, "_random_post_from_provider", side_effect=random_post):
            result = catalog.random_post("sfw", "All", "", frozenset({"yande.re"}))

        self.assertEqual(result.provider, "Danbooru")
        self.assertNotIn("yande.re", requested_providers)

    def test_preview_tries_next_url_after_network_error(self):
        post = BooruCatalog._normalize(
            {
                "id": 123,
                "file_url": "https://danbooru.donmai.us/data/original/image.jpg",
                "sample_url": "https://slow-preview.example/small.jpg",
                "preview_file_url": "https://backup-preview.example/preview.jpg",
                "rating": "e",
                "width": 2400,
                "height": 3600,
            },
            "Danbooru",
        )
        catalog = BooruCatalog()
        requested = []

        class Session:
            def get(self, url, **kwargs):
                requested.append((url, kwargs))
                if len(requested) == 1:
                    raise requests.ConnectionError("connection refused")
                return ImageResponse()

        with patch.object(catalog, "_session", return_value=Session()) as get_session:
            content = catalog.fetch_post_preview(post)

        self.assertEqual(content, b"preview")
        self.assertEqual(len(requested), 2)
        self.assertEqual(requested[0][0], "https://slow-preview.example/small.jpg")
        self.assertEqual(requested[1][0], "https://backup-preview.example/preview.jpg")
        self.assertEqual(requested[0][1]["timeout"], (3, 8))
        self.assertEqual(get_session.call_args_list, [call(retry=False)] * 2)

    def test_preview_host_failure_skips_repeated_requests_temporarily(self):
        catalog = BooruCatalog()

        class FailingSession:
            def get(self, *_args, **_kwargs):
                raise requests.ConnectionError("connection refused")

        url = "https://preview-circuit-test.invalid/image.jpg"

        with patch.object(
            catalog, "_session", return_value=FailingSession()
        ) as get_session:
            with self.assertRaisesRegex(ProviderError, "network connection"):
                catalog.fetch_image(url, timeout=(3, 8), retry=False)
            with self.assertRaisesRegex(ProviderError, "recent failure"):
                catalog.fetch_image(url, timeout=(3, 8), retry=False)

        self.assertEqual(get_session.call_count, 1)


if __name__ == "__main__":
    unittest.main()
