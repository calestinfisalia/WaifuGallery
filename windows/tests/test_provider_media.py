import unittest
from threading import Event, Thread
from unittest.mock import call, patch

import requests

from waifu_gallery.providers import BooruCatalog, ProviderError


class XmlDapiResponse:
    ok = True
    status_code = 200
    text = (
        '<posts count="1" offset="0">'
        '<post id="90210" file_url="https://img3.gelbooru.com/images/a/b/post.jpg" '
        'preview_url="https://img3.gelbooru.com/thumbnails/a/b/thumbnail.jpg" '
        'sample_url="https://img3.gelbooru.com/samples/a/b/sample.jpg" '
        'rating="explicit" tags="1girl" width="2400" height="3600" />'
        '</posts>'
    )

    def json(self):
        raise requests.exceptions.JSONDecodeError("Expecting value", self.text, 0)


class XmlDapiSession:
    def __init__(self, response):
        self.response = response
        self.request = None

    def get(self, endpoint, **kwargs):
        self.request = (endpoint, kwargs)
        return self.response


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
    def test_suggest_tags_uses_provider_prefix_and_popularity(self):
        catalog = BooruCatalog()
        payload = [
            {"name": "rei_ayanami", "post_count": 42, "category": 4},
            {"name": "rei", "post_count": 500, "category": 0},
            {"name": "rei_channel", "count": 70, "type": 3},
            {"name": "rei_ayanami_(plug_suit)", "post_count": 7, "category": 4},
            {"name": "asuka", "post_count": 1000, "category": 4},
            {"name": "rei_artist", "post_count": 900, "category": 1},
            {"name": "", "post_count": 10, "category": 4},
        ]

        with patch.object(catalog, "_request_provider_json", return_value=payload) as request:
            suggestions = catalog.suggest_tags("Rei", "Danbooru", limit=2)

        self.assertEqual(suggestions, ["rei_channel", "rei_ayanami"])
        endpoint, params = request.call_args.args[1:3]
        self.assertEqual(endpoint, "https://danbooru.donmai.us/tags.json")
        self.assertEqual(params["search[name_matches]"], "rei*")
        self.assertEqual(params["search[category]"], "3,4")
        self.assertEqual(params["limit"], 8)

    def test_yande_suggest_tags_queries_character_and_series_categories(self):
        catalog = BooruCatalog()

        def request(_provider, _endpoint, params, _headers):
            if params["type"] == "3":
                return [{"name": "rei_channel", "type": 3, "count": 18}]
            return [{"name": "rei_ayanami", "type": 4, "count": 42}]

        with patch.object(catalog, "_request_provider_json", side_effect=request) as api:
            suggestions = catalog.suggest_tags("rei", "yande.re")

        self.assertEqual(suggestions, ["rei_ayanami", "rei_channel"])
        self.assertEqual(
            [call.args[2]["type"] for call in api.call_args_list], ["3", "4"]
        )

    def test_suggest_tags_all_combines_provider_popularity(self):
        catalog = BooruCatalog()

        def provider_tags(provider, _prefix, _limit):
            return {
                "yande.re": [("rei_ayanami", 10), ("rei", 5)],
                "Danbooru": [("rei_ayanami", 20), ("rei", 1)],
            }[provider]

        with (
            patch.object(catalog, "_available_providers", return_value=["yande.re", "Danbooru"]),
            patch.object(catalog, "_suggest_provider_tags", side_effect=provider_tags),
        ):
            suggestions = catalog.suggest_tags("rei", "All", limit=2)

        self.assertEqual(suggestions, ["rei_ayanami", "rei"])

    def test_suggest_tags_reports_failure_when_no_provider_returns_data(self):
        catalog = BooruCatalog()
        with (
            patch.object(catalog, "_available_providers", return_value=["Danbooru"]),
            patch.object(
                catalog,
                "_suggest_provider_tags",
                side_effect=ProviderError("offline"),
            ),
            self.assertRaises(ProviderError),
        ):
            catalog.suggest_tags("rei", "All")

    def test_suggest_tags_accepts_legacy_dapi_xml(self):
        for provider in ("Gelbooru", "Rule34.xxx"):
            with self.subTest(provider=provider):
                response = XmlDapiResponse()
                response.text = (
                    '<tags count="2">'
                    '<tag name="rei_ayanami" count="42" type="4" />'
                    '<tag name="rei_channel" count="7" type="3" />'
                    "</tags>"
                )
                session = XmlDapiSession(response)
                catalog = BooruCatalog(
                    credentials=("test-user", "test-key"),
                    rule34_credentials=("test-user", "test-key"),
                )
                with patch.object(catalog, "_session", return_value=session):
                    suggestions = catalog.suggest_tags("rei", provider)

                self.assertEqual(suggestions, ["rei_ayanami", "rei_channel"])

    def test_ai_generated_filter_hides_tagged_posts_when_enabled(self):
        catalog = BooruCatalog(filter_ai_generated=True)
        payload = [
            {
                "id": 901,
                "file_url": "https://danbooru.donmai.us/data/ai.jpg",
                "rating": "s",
                "tags": "1girl ai-generated",
            },
            {
                "id": 902,
                "file_url": "https://danbooru.donmai.us/data/assisted.jpg",
                "rating": "s",
                "tags": "1girl ai_assisted",
            },
            {
                "id": 903,
                "file_url": "https://danbooru.donmai.us/data/handmade.jpg",
                "rating": "s",
                "tags": "1girl",
            },
        ]

        default_catalog = BooruCatalog()
        with patch.object(default_catalog, "_request_provider_json", return_value=payload):
            default_posts, _has_more = default_catalog._search_provider(
                "Danbooru", "", "sfw", 1, 10
            )

        with patch.object(catalog, "_request_provider_json", return_value=payload):
            posts, _has_more = catalog._search_provider("Danbooru", "", "sfw", 1, 10)

        self.assertEqual(len(default_posts), 3)
        self.assertEqual([post.post_id for post in posts], ["danbooru-903"])

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

    def test_random_danbooru_prefers_sample_for_sharper_first_render(self):
        post = BooruCatalog._normalize(
            {
                "id": 123,
                "file_url": "https://danbooru.donmai.us/data/original/image.jpg",
                "large_file_url": "https://danbooru.donmai.us/data/sample/large.jpg",
                "sample_url": "https://danbooru.donmai.us/data/sample/small.jpg",
                "preview_file_url": "https://danbooru.donmai.us/180x180/preview.jpg",
                "rating": "e",
                "width": 2400,
                "height": 3600,
            },
            "Danbooru",
        )
        self.assertIsNotNone(post)
        catalog = BooruCatalog()
        fetched_urls = []
        with patch.object(
            catalog,
            "fetch_image",
            side_effect=lambda url, _progress=None, **_kwargs: fetched_urls.append(url) or b"image",
        ):
            content = catalog.fetch_post_preview(post)

        self.assertEqual(content, b"image")
        self.assertEqual(
            fetched_urls[0],
            "https://danbooru.donmai.us/data/sample/small.jpg",
        )

    def test_video_preview_keeps_lightweight_candidate_first(self):
        post = BooruCatalog._normalize(
            {
                "id": 123,
                "file_url": "https://danbooru.donmai.us/data/video.webm",
                "file_ext": "webm",
                "sample_url": "https://danbooru.donmai.us/data/sample.jpg",
                "preview_file_url": "https://danbooru.donmai.us/180x180/preview.jpg",
                "rating": "e",
            },
            "Danbooru",
        )
        self.assertIsNotNone(post)
        catalog = BooruCatalog()
        fetched_urls = []
        with patch.object(
            catalog,
            "fetch_image",
            side_effect=lambda url, _progress=None, **_kwargs: fetched_urls.append(url) or b"image",
        ):
            catalog.fetch_post_preview(post)

        self.assertEqual(
            fetched_urls[0],
            "https://danbooru.donmai.us/180x180/preview.jpg",
        )

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

    def test_gelbooru_random_accepts_legacy_dapi_xml(self):
        response = XmlDapiResponse()
        session = XmlDapiSession(response)
        catalog = BooruCatalog(credentials=("test-user", "test-key"))
        with (
            patch.object(catalog, "_session", return_value=session),
            patch.object(catalog, "fetch_image", return_value=b"preview"),
            patch("waifu_gallery.providers.random.randint", return_value=1),
        ):
            post, image = catalog.random_image("all", "Gelbooru")

        self.assertEqual(post.provider, "Gelbooru")
        self.assertEqual(post.post_id, "gelbooru-90210")
        self.assertEqual(image, b"preview")
        self.assertEqual(session.request[1]["params"]["page"], "dapi")
        self.assertEqual(session.request[1]["params"]["json"], 1)

    def test_gelbooru_html_challenge_has_provider_error(self):
        response = XmlDapiResponse()
        response.text = "<html><title>Access denied</title></html>"
        session = XmlDapiSession(response)
        catalog = BooruCatalog(credentials=("test-user", "test-key"))
        with patch.object(catalog, "_session", return_value=session):
            with self.assertRaisesRegex(ProviderError, "Gelbooru returned an HTML page"):
                catalog._request_provider_json("Gelbooru", "https://gelbooru.com/index.php", {}, {})


if __name__ == "__main__":
    unittest.main()
