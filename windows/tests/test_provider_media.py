import unittest
from unittest.mock import patch

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


class ProviderMediaTests(unittest.TestCase):
    def test_random_danbooru_prefers_large_variant_over_small_sample(self):
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
            side_effect=lambda url, _progress=None: fetched_urls.append(url) or b"image",
        ):
            content = catalog.fetch_post_preview(post)

        self.assertEqual(content, b"image")
        self.assertEqual(
            fetched_urls[0],
            "https://danbooru.donmai.us/data/sample/large.jpg",
        )

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
