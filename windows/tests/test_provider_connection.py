import unittest
from unittest.mock import patch

import requests

from waifu_gallery.providers import BooruCatalog, PROVIDERS


class StatusResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.reason = "Service Unavailable"


class StatusSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.request = None

    def get(self, endpoint, **kwargs):
        self.request = (endpoint, kwargs)
        if self.error:
            raise self.error
        return self.response


class ProviderConnectionTests(unittest.TestCase):
    def test_connection_check_probes_each_provider_api(self):
        endpoints = {
            "Danbooru": "https://danbooru.donmai.us/posts.json",
            "yande.re": "https://yande.re/post.json",
            "Gelbooru": "https://gelbooru.com/index.php",
            "Rule34.xxx": "https://api.rule34.xxx/index.php",
        }
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                session = StatusSession(StatusResponse(200))
                catalog = BooruCatalog(
                    credentials=("gel-user", "gel-key"),
                    rule34_credentials=("r34-user", "r34-key"),
                )
                with patch.object(catalog, "_session", return_value=session) as get_session:
                    status = catalog.check_provider_connection(provider)

                self.assertEqual(status, "HTTP 200 - Connection healthy")
                self.assertEqual(session.request[0], endpoints[provider])
                self.assertEqual(session.request[1]["timeout"], (4, 10))
                get_session.assert_called_once_with(retry=False)

    def test_connection_timeout_reports_rto_code_and_description(self):
        session = StatusSession(error=requests.Timeout())
        catalog = BooruCatalog()

        with patch.object(catalog, "_session", return_value=session):
            status = catalog.check_provider_connection("yande.re")

        self.assertEqual(
            status,
            "TIMEOUT (RTO) - Request timed out before an HTTP response.",
        )

    def test_http_error_reports_code_and_description(self):
        session = StatusSession(StatusResponse(503))
        catalog = BooruCatalog()

        with patch.object(catalog, "_session", return_value=session):
            status = catalog.check_provider_connection("Danbooru")

        self.assertEqual(status, "HTTP 503 - Provider temporarily unavailable")


if __name__ == "__main__":
    unittest.main()
