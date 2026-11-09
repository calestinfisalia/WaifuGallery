from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import random
import hashlib
import secrets
import threading
import tempfile
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import ImagePost, SearchPage
from .doh import set_doh_enabled


class ProviderError(RuntimeError):
    pass


class DownloadCancelled(RuntimeError):
    pass


PROVIDERS = ("Danbooru", "yande.re", "Gelbooru", "Rule34.xxx")
MALE_TAGS = frozenset({"1boy", "2boys", "3boys", "4boys", "5boys", "6+boys", "male_focus", "male_only"})
SFW_BLOCK_TAGS = frozenset({
    "anal", "blowjob", "cum", "cum_in_pussy", "cum_on_body", "cum_on_face",
    "cumshot", "ejaculation", "explicit", "fellatio", "genital", "hentai",
    "intercourse", "masturbation", "naked", "nipple", "nipples", "nudity",
    "nude", "oral", "penis", "pussy", "sex", "sex_toy", "uncensored",
    "vagina", "vaginal", "vaginal_penetration",
})
GORE_BLOCK_TAGS = frozenset({
    "amputation", "blood", "blood_from_mouth", "blood_on_clothes", "blood_on_face",
    "blood_splatter", "bleeding", "body_horror", "decapitation", "dismembered",
    "dismemberment", "disembowelment", "evisceration", "exposed_organs", "gore",
    "guro", "intestines", "mutilation", "open_wound", "organs", "severed_arm",
    "severed_foot", "severed_hand", "severed_head", "severed_leg", "wound",
})
VIDEO_EXTENSIONS = frozenset({".mp4", ".m4v", ".webm", ".mov", ".mkv", ".avi"})
_RANDOM_HISTORY: dict[tuple[str, str, str, str], deque[str]] = {}
_RANDOM_HISTORY_LOCK = threading.Lock()
# The initial segment is about four to five seconds for typical 25-30 Mbps
# clips. The remainder is streamed directly to Qt as it is requested.
VIDEO_PREBUFFER_BYTES = 16 * 1024 * 1024
VIDEO_SEEK_PREBUFFER_BYTES = 512 * 1024


class VideoStreamProxy:
    """Local range-capable HTTP bridge that streams a provider URL via requests."""

    def __init__(self, catalog: "BooruCatalog", post: ImagePost, remote_url: str | None = None) -> None:
        self._closed = False
        self._active_responses = set()
        self._responses_lock = threading.Lock()
        token = secrets.token_urlsafe(24)
        remote_url = remote_url or post.image_url
        catalog_ref = catalog
        prebuffer_bytes = VIDEO_PREBUFFER_BYTES

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, _format, *_args):
                return

            def _is_authorized_path(self) -> bool:
                return self.path.partition("?")[0] == f"/{token}"

            def _request_headers(self) -> dict[str, str]:
                headers = catalog_ref._image_headers(remote_url)
                headers.update({"Accept": "*/*", "Accept-Encoding": "identity"})
                requested_range = self.headers.get("Range")
                if requested_range:
                    headers["Range"] = requested_range
                if self.headers.get("If-Range"):
                    headers["If-Range"] = self.headers["If-Range"]
                return headers

            def do_HEAD(self):
                if not self._is_authorized_path():
                    self.send_error(404)
                    return
                try:
                    response = catalog_ref._session().head(
                        remote_url, headers=self._request_headers(), timeout=(8, 30),
                    )
                    with proxy_ref._responses_lock:
                        proxy_ref._active_responses.add(response)
                    self.send_response(response.status_code)
                    for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                        if name in response.headers:
                            self.send_header(name, response.headers[name])
                    self.send_header("Connection", "close")
                    self.end_headers()
                except requests.RequestException:
                    self.send_error(502, "Provider stream unavailable")
                finally:
                    if "response" in locals():
                        with proxy_ref._responses_lock:
                            proxy_ref._active_responses.discard(response)
                        response.close()

            def do_GET(self):
                if not self._is_authorized_path():
                    self.send_error(404)
                    return
                response = None
                headers_sent = False
                try:
                    response = catalog_ref._session().get(
                        remote_url,
                        headers=self._request_headers(),
                        timeout=(8, 90),
                        stream=True,
                    )
                    with proxy_ref._responses_lock:
                        proxy_ref._active_responses.add(response)
                    if response.status_code not in (200, 206):
                        self.send_error(response.status_code, "Provider rejected the media request")
                        return

                    total = int(response.headers.get("Content-Length", "0") or 0)
                    requested_range = self.headers.get("Range", "")
                    # Only hold the initial request long enough to build a
                    # startup buffer. Seeks should remain responsive.
                    initial_request = not requested_range or requested_range.startswith("bytes=0-")
                    target = (
                        prebuffer_bytes if initial_request else VIDEO_SEEK_PREBUFFER_BYTES
                    )
                    target = min(target, total) if total else target
                    iterator = response.iter_content(chunk_size=256 * 1024)
                    initial: list[bytes] = []
                    buffered = 0
                    while buffered < target:
                        block = next(iterator, b"")
                        if not block:
                            break
                        initial.append(block)
                        buffered += len(block)

                    self.send_response(response.status_code)
                    for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                        if name in response.headers:
                            self.send_header(name, response.headers[name])
                    self.send_header("Connection", "close")
                    self.end_headers()
                    headers_sent = True
                    for block in initial:
                        self.wfile.write(block)
                    for block in iterator:
                        if block:
                            self.wfile.write(block)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    # The player closes its request when the user changes media.
                    pass
                except requests.RequestException:
                    if not self.wfile.closed and not headers_sent:
                        try:
                            self.send_error(502, "Provider stream interrupted")
                        except OSError:
                            pass
                finally:
                    if response is not None:
                        with proxy_ref._responses_lock:
                            proxy_ref._active_responses.discard(response)
                        response.close()

        proxy_ref = self

        class LocalStreamServer(ThreadingHTTPServer):
            daemon_threads = True
            block_on_close = False
            allow_reuse_address = True

        self._server = LocalStreamServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}/{token}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Closing upstream responses interrupts a pending read immediately,
        # so changing videos cannot keep downloading the previous clip.
        with self._responses_lock:
            responses, self._active_responses = self._active_responses, set()
        for response in responses:
            response.close()

        def stop_server() -> None:
            self._server.shutdown()
            self._server.server_close()

        threading.Thread(target=stop_server, daemon=True).start()


class BooruCatalog:
    """Small API client written for Waifu Gallery's own data model."""

    def __init__(
        self,
        credentials: tuple[str, str] = ("", ""),
        exclude_male: bool = True,
        use_doh: bool = False,
        rule34_credentials: tuple[str, str] = ("", ""),
        filter_gore: bool = True,
        custom_block_tags: tuple[str, ...] = (),
        media_filter: str = "image",
        doh_endpoint: str | None = None,
    ) -> None:
        self.user_id, self.api_key = credentials
        self.rule34_user_id, self.rule34_api_key = rule34_credentials
        self.exclude_male = exclude_male
        self.use_doh = use_doh
        self.filter_gore = filter_gore
        block_tag_values = (custom_block_tags,) if isinstance(custom_block_tags, str) else custom_block_tags
        self.custom_block_tags = frozenset(
            tag.strip().casefold().replace(" ", "_")
            for value in block_tag_values
            for tag in str(value).replace(",", " ").split()
            if tag.strip()
        )
        self.media_filter = media_filter if media_filter in {"image", "video", "all"} else "image"
        self._sessions = threading.local()
        self.doh_endpoint = doh_endpoint
        set_doh_enabled(self.use_doh, self.doh_endpoint)

    def search(self, query: str, rating: str, provider: str, page: int, page_size: int = 50) -> SearchPage:
        if provider not in (*PROVIDERS, "All"):
            raise ProviderError(f"Unknown provider: {provider}")
        available = ["yande.re"]
        if self.user_id and self.api_key:
            available.append("Gelbooru")
        if self.rule34_user_id and self.rule34_api_key:
            available.append("Rule34.xxx")
        available.append("Danbooru")
        if provider == "Gelbooru" and "Gelbooru" not in available:
            raise ProviderError("Gelbooru needs your user ID and API key. Add them in Settings.")
        if provider == "Rule34.xxx" and "Rule34.xxx" not in available:
            raise ProviderError("Rule34.xxx needs your user ID and API key. Add them in Settings.")
        if provider == "All":
            return self._search_all(query, rating, available, page, page_size)

        # A manually selected provider stays selected. Cross-provider fallback
        # belongs to All so results never unexpectedly come from another board.
        posts, has_more = self._search_provider(provider, query, rating, page, page_size)
        return SearchPage(tuple(posts[:page_size]), has_more)

    def _search_all(self, query: str, rating: str, providers: list[str], page: int, page_size: int) -> SearchPage:
        results: dict[str, tuple[list[ImagePost], bool]] = {}
        errors: list[str] = []
        provider_limit = page_size
        with ThreadPoolExecutor(max_workers=len(providers)) as executor:
            jobs = {
                executor.submit(self._search_provider, name, query, rating, page, provider_limit): name
                for name in providers
            }
            for job in as_completed(jobs):
                name = jobs[job]
                try:
                    results[name] = job.result()
                except ProviderError as error:
                    errors.append(f"{name}: {error}")

        combined: list[ImagePost] = []
        seen: set[str] = set()
        available_posts = [results.get(name, ([], False))[0] for name in providers]
        for row in range(max((len(items) for items in available_posts), default=0)):
            for posts in available_posts:
                if row < len(posts):
                    item = posts[row]
                    key = item.checksum or item.image_url
                    if key not in seen:
                        seen.add(key)
                        combined.append(item)
                        if len(combined) >= page_size:
                            break
            if len(combined) >= page_size:
                break

        has_more = any(value[1] for value in results.values())
        if not combined and errors:
            raise ProviderError(" | ".join(errors))
        return SearchPage(tuple(combined), has_more, tuple(errors))

    def random_image(self, rating: str, provider: str, query: str = "", report_progress=None) -> tuple[ImagePost, bytes]:
        if provider == "Gelbooru" and not (self.user_id and self.api_key):
            raise ProviderError("Gelbooru needs your user ID and API key. Add them in Settings.")
        if provider == "Rule34.xxx" and not (self.rule34_user_id and self.rule34_api_key):
            raise ProviderError("Rule34.xxx needs your user ID and API key. Add them in Settings.")

        available = ["yande.re"]
        if self.user_id and self.api_key:
            available.append("Gelbooru")
        if self.rule34_user_id and self.rule34_api_key:
            available.append("Rule34.xxx")
        available.append("Danbooru")
        sources = available if provider == "All" else [provider]
        failures: list[str] = []

        for source in sources:
            try:
                history_key = (source, rating, query.strip().casefold(), self.media_filter)
                with _RANDOM_HISTORY_LOCK:
                    history = _RANDOM_HISTORY.setdefault(history_key, deque(maxlen=160))
                    recent = set(history)

                # A random page can contain only one matching video. Try several
                # independently sampled pages before considering a recently
                # shown post again; otherwise sparse video pages immediately
                # cycle back to the same clip.
                posts: list[ImagePost] = []
                candidates: list[ImagePost] = []
                pages_seen: set[int] = set()
                page_one_tried = False
                for _ in range(3):
                    if source in {"yande.re", "Gelbooru", "Rule34.xxx"}:
                        sample_page = random.randint(1, 120)
                        while sample_page in pages_seen and len(pages_seen) < 120:
                            sample_page = random.randint(1, 120)
                        pages_seen.add(sample_page)
                    else:
                        sample_page = 1

                    sampled, _ = self._search_provider(source, query, rating, sample_page, 100, random_order=True)
                    # For a sparse tag query, retry page one as a fallback, but
                    # keep sampling other pages on subsequent rounds.
                    if not sampled and sample_page != 1 and not page_one_tried:
                        page_one_tried = True
                        sampled, _ = self._search_provider(source, query, rating, 1, 100, random_order=True)
                    posts.extend(sampled)
                    unique_posts = list({post.post_id: post for post in posts}.values())
                    candidates = [post for post in unique_posts if post.post_id not in recent]
                    if candidates:
                        break

                if not posts:
                    media_name = {"image": "image", "video": "video", "all": "media"}[self.media_filter]
                    raise ProviderError(f"No matching {media_name} was returned.")

                if not candidates:
                    # If the sampled pool is exhausted, avoid an immediate
                    # repeat whenever there is any other item to choose from.
                    # Keep history intact so the next refresh can sample again.
                    with _RANDOM_HISTORY_LOCK:
                        last_post_id = history[-1] if history else None
                    candidates = [post for post in unique_posts if post.post_id != last_post_id]
                    if not candidates:
                        candidates = unique_posts

                with _RANDOM_HISTORY_LOCK:
                    post = random.choice(candidates)
                try:
                    if post.media_type == "video":
                        with _RANDOM_HISTORY_LOCK:
                            _RANDOM_HISTORY[history_key].append(post.post_id)
                        return post, b""
                    content = self.fetch_post_preview(post, report_progress)
                    with _RANDOM_HISTORY_LOCK:
                        _RANDOM_HISTORY[history_key].append(post.post_id)
                    return post, content
                except ProviderError:
                    raise
                except requests.RequestException as error:
                    raise ProviderError(self._request_error_message(error)) from error
            except ProviderError as error:
                if provider != "All":
                    raise
                failures.append(f"{source}: {error}")

        raise ProviderError("All providers failed: " + " | ".join(failures))

    def fetch_image(self, url: str, report_progress=None) -> bytes:
        with self._session().get(url, headers=self._image_headers(url), timeout=(5, 40), stream=True) as response:
            if not response.ok:
                raise ProviderError(f"Image server returned HTTP {response.status_code}.")
            kind = response.headers.get("Content-Type", "").lower()
            if kind and not (kind.startswith("image/") or "octet-stream" in kind):
                raise ProviderError("The provider returned a response that is not an image.")
            total = int(response.headers.get("Content-Length", "0") or 0)
            received = 0
            chunks = []
            if report_progress:
                report_progress(0 if total else -1)
            for block in response.iter_content(chunk_size=128 * 1024):
                if not block:
                    continue
                chunks.append(block)
                received += len(block)
                if report_progress:
                    report_progress(min(99, int(received * 100 / total)) if total else -1)
            if report_progress:
                report_progress(100)
            return b"".join(chunks)

    def fetch_post_preview(self, post: ImagePost, report_progress=None) -> bytes:
        """Fetch the provider's lightweight sample for on-screen display.

        The original URL remains on ImagePost and is used by downloads and the
        explicit full-resolution action.
        """
        # Provider metadata orders these as preview -> sample -> original.
        # Keep the original for the explicit full-resolution action whenever
        # a smaller preview variant is available, but prefer the sharper sample.
        candidates = [url for url in reversed(post.preview_urls) if url != post.image_url]
        if not candidates:
            candidates.append(post.image_url)
        failures = []
        for url in dict.fromkeys(candidates):
            try:
                return self.fetch_image(url, report_progress)
            except ProviderError as error:
                failures.append(str(error))
        raise ProviderError(failures[-1] if failures else "No image preview URL was supplied.")

    def save_image(
        self,
        post: ImagePost,
        destination: Path,
        report_progress,
        is_cancelled=None,
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".part")
        try:
            if is_cancelled and is_cancelled():
                raise DownloadCancelled()
            with self._session().get(post.image_url, headers=self._image_headers(post.image_url),
                                     timeout=(8, 40), stream=True) as response:
                if not response.ok:
                    raise ProviderError(f"Media server returned HTTP {response.status_code}.")
                total = int(response.headers.get("Content-Length", "0") or 0)
                received = 0
                with temporary.open("wb") as output:
                    for block in response.iter_content(chunk_size=128 * 1024):
                        if is_cancelled and is_cancelled():
                            raise DownloadCancelled()
                        if block:
                            output.write(block)
                            received += len(block)
                            report_progress(min(99, int(received * 100 / total)) if total else -1)
                if is_cancelled and is_cancelled():
                    raise DownloadCancelled()
                temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        report_progress(100)
        return destination

    def cache_video(self, post: ImagePost, report_progress=None) -> str:
        """Download a video to a local cache so playback uses the app's DoH route."""
        if post.media_type != "video":
            raise ProviderError("The selected post is not a video.")
        suffix = Path(urlparse(post.image_url).path).suffix or ".mp4"
        cache_dir = Path(tempfile.gettempdir()) / "WaifuGallery" / "video-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(post.image_url.encode("utf-8")).hexdigest() + suffix
        destination = cache_dir / name
        if destination.is_file() and destination.stat().st_size:
            if report_progress:
                report_progress(100)
            return str(destination)

        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            with self._session().get(
                post.image_url, headers=self._image_headers(post.image_url),
                timeout=(8, 90), stream=True,
            ) as response:
                if not response.ok:
                    raise ProviderError(f"Video server returned HTTP {response.status_code}.")
                content_type = response.headers.get("Content-Type", "").casefold()
                if content_type and not (content_type.startswith("video/") or "octet-stream" in content_type):
                    raise ProviderError("The provider returned a response that is not a video.")
                total = int(response.headers.get("Content-Length", "0") or 0)
                received = 0
                with temporary.open("wb") as output:
                    for block in response.iter_content(chunk_size=256 * 1024):
                        if not block:
                            continue
                        output.write(block)
                        received += len(block)
                        if report_progress:
                            report_progress(min(99, int(received * 100 / total)) if total else -1)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        if report_progress:
            report_progress(100)
        return str(destination)

    def create_video_stream(
        self, post: ImagePost, max_height: int | None = None
    ) -> VideoStreamProxy:
        """Stream the best available provider rendition under the requested height."""
        if post.media_type != "video":
            raise ProviderError("The selected post is not a video.")
        source_url = post.image_url
        if max_height:
            matching = [
                (url, width, height)
                for url, width, height in post.video_variants
                if height and height <= max_height
            ]
            if matching:
                source_url = max(matching, key=lambda item: item[2])[0]
        return VideoStreamProxy(self, post, source_url)

    def _search_provider(self, provider: str, query: str, rating: str, page: int, limit: int, random_order: bool = False):
        # Keep Only NSFW strict: questionable (Q) posts can appear fully
        # safe-looking, so this mode requests Explicit (E) only.
        rating_tags = {"sfw": ("s",), "nsfw": ("e",), "all": (None,)}.get(rating)
        if rating_tags is None:
            raise ProviderError(f"Unknown rating filter: {rating}")
        if provider not in PROVIDERS:
            raise ProviderError(f"Unknown provider: {provider}")

        # yande.re is an image-only board. For the booru APIs, request the
        # video's tag from the server so video posts are not hidden behind a
        # page of image posts and then discarded by the client-side filter.
        if self.media_filter == "video" and provider == "yande.re":
            return [], False

        queries = [self._booru_search_tags(query, prefix_match=True)]
        prefix_fallback = self._booru_prefix_fallback(query)
        if prefix_fallback and prefix_fallback not in queries:
            queries.append(prefix_fallback)

        failures: list[str] = []
        for tags in queries:
            posts: list[ImagePost] = []
            has_more = False
            for rating_tag in rating_tags:
                request_tags = list(tags)
                if self.media_filter == "video" and provider != "yande.re":
                    request_tags.append("video")
                if rating_tag:
                    rating_names = {
                        "Gelbooru": {"s": "general", "q": "questionable", "e": "explicit"},
                        # Rule34 documents the full rating tags (rating:safe,
                        # rating:questionable, rating:explicit); shorthand such
                        # as rating:e can be treated as an ordinary tag and yield
                        # an empty result set.
                        "Rule34.xxx": {"s": "safe", "q": "questionable", "e": "explicit"},
                    }
                    provider_rating = rating_names.get(provider, {}).get(rating_tag, rating_tag)
                    request_tags.append(f"rating:{provider_rating}")

                params = {"tags": " ".join(request_tags), "limit": min(limit + 1, 100), "page": page}
                headers = {"Accept": "application/json"}
                if provider == "Danbooru":
                    endpoint = "https://danbooru.donmai.us/posts.json"
                    headers["Accept-Version"] = "v7"
                    if random_order:
                        params["random"] = 1
                elif provider == "yande.re":
                    endpoint = "https://yande.re/post.json"
                    params["api_version"] = 2
                elif provider == "Gelbooru":
                    endpoint = "https://gelbooru.com/index.php"
                    params.pop("page", None)
                    params.update({"page": "dapi", "s": "post", "q": "index", "pid": max(0, page - 1), "json": 1})
                    params.update({"user_id": self.user_id, "api_key": self.api_key})
                else:
                    endpoint = "https://api.rule34.xxx/index.php"
                    params.pop("page", None)
                    params.update({"page": "dapi", "s": "post", "q": "index", "pid": max(0, page - 1), "json": 1})
                    params.update({"user_id": self.rule34_user_id, "api_key": self.rule34_api_key})

                try:
                    payload = self._request_provider_json(provider, endpoint, params, headers)
                except ProviderError as error:
                    failures.append(str(error))
                    break
                except requests.Timeout as error:
                    failures.append("The provider request timed out. Check the connection or retry shortly.")
                    break
                except requests.exceptions.SSLError as error:
                    failures.append("TLS certificate verification failed while connecting to the provider.")
                    break
                except requests.ConnectionError as error:
                    if self.use_doh:
                        failures.append("Could not connect using the selected DoH resolver. Check its endpoint or turn DoH off in Settings.")
                    else:
                        failures.append("Could not connect to the provider. Check DNS, firewall, or network access.")
                    break
                except requests.RequestException as error:
                    failures.append(self._request_error_message(error))
                    break
                except ValueError:
                    failures.append("The provider returned an unreadable response.")
                    break

                raw_posts = self._post_list(payload)
                has_more = has_more or len(raw_posts) > limit
                for raw in raw_posts[:limit]:
                    post = self._normalize(raw, provider)
                    if not post or not self._rating_matches(post.rating, rating):
                        continue
                    if self.media_filter != "all" and post.media_type != self.media_filter:
                        continue
                    if rating == "sfw" and post.tags.intersection(SFW_BLOCK_TAGS):
                        continue
                    if self.custom_block_tags.intersection(post.tags):
                        continue
                    if self.filter_gore and post.tags.intersection(GORE_BLOCK_TAGS):
                        continue
                    # Some sources, especially yande.re, do not tag posts with
                    # 1girl/female_focus. Exclude explicit male tags, but don't
                    # discard otherwise valid posts just because gender is untagged.
                    if self.exclude_male and post.tags.intersection(MALE_TAGS):
                        continue
                    posts.append(post)

            if posts:
                return posts[:limit], has_more
        if failures:
            raise ProviderError(failures[-1])
        return [], False

    def _request_provider_json(self, provider: str, endpoint: str, params: dict, headers: dict):
        uses_api_credentials = (
            provider == "Gelbooru" and bool(self.user_id and self.api_key)
        ) or (
            provider == "Rule34.xxx" and bool(self.rule34_user_id and self.rule34_api_key)
        )
        timeout = (4, 10)
        attempts = 1
        for attempt in range(attempts):
            try:
                response = self._session(retry=False).get(
                    endpoint, params=params, headers=headers, timeout=timeout
                )
                if not response.ok:
                    if uses_api_credentials and response.status_code in {401, 403}:
                        message = f"{provider} rejected API access. Check its user ID and API key in Settings."
                    else:
                        messages = {
                            403: "HTTP 403: access was denied by the provider or its network protection.",
                            429: "HTTP 429: the provider is rate limiting requests. Wait a moment and retry.",
                            500: "HTTP 500: the provider is having a server error.",
                            502: "HTTP 502: the provider gateway is temporarily unavailable.",
                            503: "HTTP 503: the provider is temporarily unavailable or under maintenance.",
                            504: "HTTP 504: the provider gateway timed out.",
                        }
                        message = messages.get(response.status_code, f"HTTP {response.status_code}: the provider rejected the request.")
                    raise ProviderError(message)
                try:
                    payload = response.json()
                except ValueError as error:
                    body_text = response.text.strip()
                    body = body_text.casefold()
                    if provider == "Rule34.xxx":
                        if any(message in body for message in ("missing authentication", "invalid api key", "invalid user_id")):
                            raise ProviderError("Rule34.xxx rejected API authentication. Check your user ID and API key in Settings.") from error
                        # Rule34's DAPI can return the legacy XML document even
                        # when json=1 is requested. Normalize its <post ... />
                        # elements to the same list shape as the JSON endpoint.
                        try:
                            root = ET.fromstring(body_text)
                            if root.tag.casefold() == "posts":
                                xml_status = " ".join(root.attrib.values()).casefold()
                                if root.attrib.get("success", "").casefold() in {"false", "0"} or "search down" in xml_status:
                                    raise ProviderError("Rule34.xxx search is temporarily unavailable. Retry in a little while.")
                                payload = [dict(post.attrib) for post in root.findall("post")]
                            else:
                                raise ValueError("Unexpected XML root")
                        except ET.ParseError:
                            raise ProviderError(
                                "Rule34.xxx returned neither JSON nor DAPI XML. Check the API credentials, "
                                "or retry later if the provider is having an issue."
                            ) from error
                    else:
                        raise
                if provider == "Rule34.xxx" and isinstance(payload, dict):
                    detail = " ".join(str(payload.get(key, "")) for key in ("success", "message", "error", "reason")).casefold()
                    if "missing authentication" in detail or "invalid api key" in detail:
                        raise ProviderError("Rule34.xxx rejected API authentication. Check your user ID and API key in Settings.")
                    if str(payload.get("success", "")).casefold() in {"false", "0"} or "search down" in detail:
                        raise ProviderError("Rule34.xxx search is temporarily unavailable. Retry in a little while.")
                return payload
            except requests.Timeout as error:
                if attempt + 1 < attempts:
                    time.sleep(0.8)
                    continue
                if uses_api_credentials:
                    raise ProviderError(
                        f"{provider} request timed out. Its API may be overloaded; retry later."
                    ) from error
                raise

    def _request_error_message(self, error: requests.RequestException) -> str:
        cause = getattr(error, "__cause__", None)
        if cause is None and getattr(error, "args", None):
            cause = getattr(error.args[0], "reason", None)
        detail = str(cause or error)
        lowered = detail.casefold()
        if "name resolution" in lowered or "getaddrinfo failed" in lowered or "name or service not known" in lowered:
            prefix = "DNS lookup failed"
            if self.use_doh:
                prefix = "DNS lookup failed, including the configured DoH resolver"
        elif "certificate verify failed" in lowered or "ssl" in lowered:
            prefix = "TLS certificate validation failed"
        elif "timed out" in lowered or "timeout" in lowered:
            prefix = "The provider request timed out"
        elif "connection" in lowered or "network is unreachable" in lowered:
            prefix = "Could not establish a network connection"
        else:
            prefix = f"Provider request failed ({type(error).__name__})"
        # Avoid showing request URLs because authenticated provider queries contain
        # account credentials. Keep the underlying exception class for diagnosis.
        reason_type = type(cause).__name__ if cause is not None else type(error).__name__
        return f"{prefix} ({reason_type}). Check the provider/network and retry."

    def _session(self, *, retry: bool = True) -> requests.Session:
        session_name = "client" if retry else "search_client"
        client = getattr(self._sessions, session_name, None)
        if client is None:
            client = requests.Session()
            retry_policy = (
                Retry(total=2, connect=2, read=1, status=0, backoff_factor=0.3,
                      allowed_methods=frozenset({"GET"}),
                      respect_retry_after_header=True)
                if retry else Retry(total=0)
            )
            client.mount("https://", HTTPAdapter(max_retries=retry_policy))
            client.headers.update({"User-Agent": "Waifu Gallery/0.1 (Windows desktop image browser)"})
            setattr(self._sessions, session_name, client)
        return client

    @staticmethod
    def _booru_search_tags(query: str, prefix_match: bool = False) -> list[str]:
        tags: list[str] = []
        for chunk in query.split(","):
            value = chunk.strip()
            if not value:
                continue
            if " " in value and "_" not in value:
                value = value.replace(" ", "_")
            chunk_tags = value.split()
            if prefix_match and len(chunk_tags) == 1:
                tag = chunk_tags[0]
                if tag and not any(mark in tag for mark in "*~()") and ":" not in tag and not tag.startswith("-"):
                    chunk_tags[0] = f"{tag}*"
            tags.extend(chunk_tags)
        return tags

    @staticmethod
    def _booru_prefix_fallback(query: str) -> list[str] | None:
        value = query.strip()
        if not value or "_" in value or any(mark in value for mark in "*~():"):
            return None
        first_chunk = value.split(",", 1)[0].strip().split()
        if len(first_chunk) != 1:
            return None
        first = first_chunk[0].casefold()
        if len(first) < 3:
            return None
        return [f"{first}*"]

    @staticmethod
    def _query_tags(query: str) -> list[str]:
        # Booru APIs treat whitespace as an AND between tags. Commas are accepted
        # too so the UI can present either separator without changing semantics.
        return [tag.strip() for chunk in query.split(",") for tag in chunk.split() if tag.strip()]

    @staticmethod
    def _post_list(payload) -> list[dict]:
        if isinstance(payload, dict):
            payload = payload.get("posts", payload.get("post", []))
        if isinstance(payload, dict):
            payload = [payload]
        return [post for post in payload if isinstance(post, dict)] if isinstance(payload, list) else []

    @classmethod
    def _normalize(cls, raw: dict, provider: str) -> ImagePost | None:
        # file_url is the original media. sample/jpeg URLs often point to a
        # still-image preview even when the post itself is a video.
        file_ext = str(raw.get("file_ext") or "").strip().casefold().lstrip(".")
        is_declared_video = f".{file_ext}" in VIDEO_EXTENSIONS
        media_urls = [
            cls._absolute(cls._first(raw, field))
            for field in ("file_url", "large_file_url", "jpeg_url", "sample_url")
        ]
        image_url = next(
            (url for url in media_urls
             if url and Path(urlparse(url).path).suffix.casefold() in VIDEO_EXTENSIONS),
            "",
        ) if is_declared_video else ""
        if not image_url:
            image_url = cls._first(raw, "file_url")
        if not image_url and raw.get("directory") and raw.get("image"):
            image_name = str(raw["image"])
            if provider == "Gelbooru":
                image_url = f"https://img3.gelbooru.com/images/{raw['directory']}/{image_name}"
            elif provider == "Rule34.xxx":
                image_url = f"https://img.rule34.xxx/images/{raw['directory']}/{image_name}"
        if not image_url:
            image_url = cls._first(raw, "large_file_url", "jpeg_url", "sample_url")
        image_url = cls._absolute(image_url)
        if not image_url.startswith(("https://", "http://")):
            return None
        suffix = Path(urlparse(image_url).path).suffix.casefold()
        is_video = suffix in VIDEO_EXTENSIONS or f".{file_ext}" in VIDEO_EXTENSIONS
        media_type = "video" if is_video else "image"
        preview_file_url = cls._absolute(cls._first(raw, "preview_file_url", "preview_url"))
        sample_url = cls._absolute(cls._first(raw, "sample_url", "jpeg_url"))
        preview_candidates = (
            (sample_url, preview_file_url, image_url)
            if is_video
            else (preview_file_url, sample_url, image_url)
        )
        previews = tuple(dict.fromkeys(
            url for url in preview_candidates
            if url and Path(urlparse(url).path).suffix.casefold() not in VIDEO_EXTENSIONS
        ))
        tag_data = [raw.get(key) for key in ("tags", "tag_string", "tag_string_general", "tag_string_character", "tag_string_copyright", "tag_string_artist")]
        tags = frozenset(tag for value in tag_data for tag in cls._tags(value))
        rating = str(raw.get("rating", "")).lower()
        rating = {"general": "s", "safe": "s", "sensitive": "q", "questionable": "q", "explicit": "e"}.get(rating, rating)
        commentary = raw.get("artist_commentary")
        commentary_title = ""
        if isinstance(commentary, dict):
            commentary_title = cls._first(commentary, "original_title", "translated_title", "title")
        title = cls._first(
            raw, "title", "post_title", "caption", "artist_commentary_title",
            "translated_commentary_title",
        ) or commentary_title
        artists = tuple(str(raw.get("tag_string_artist", "")).split())
        remote_id = str(raw.get("id") or raw.get("md5") or image_url)
        post_id = f"{provider.casefold()}-{remote_id}"
        try:
            width = max(0, int(raw.get("width") or 0))
            height = max(0, int(raw.get("height") or 0))
        except (TypeError, ValueError):
            width = height = 0
        video_variants = []
        variant_dimensions = {
            "file_url": (width, height),
            "large_file_url": (
                cls._safe_int(raw.get("large_width") or width),
                cls._safe_int(raw.get("large_height") or height),
            ),
            "sample_url": (
                cls._safe_int(raw.get("sample_width")),
                cls._safe_int(raw.get("sample_height")),
            ),
            "jpeg_url": (
                cls._safe_int(raw.get("jpeg_width")),
                cls._safe_int(raw.get("jpeg_height")),
            ),
        }
        for field, (variant_width, variant_height) in variant_dimensions.items():
            variant_url = cls._absolute(cls._first(raw, field))
            if (
                variant_url.startswith(("https://", "http://"))
                and Path(urlparse(variant_url).path).suffix.casefold() in VIDEO_EXTENSIONS
            ):
                video_variants.append((variant_url, variant_width, variant_height))
        if not any(url == image_url for url, _width, _height in video_variants):
            video_variants.insert(0, (image_url, width, height))
        video_variants = list(dict.fromkeys(video_variants))
        return ImagePost(post_id, provider, image_url, previews,
                         rating, tags, artists, str(raw.get("source") or ""), str(raw.get("md5") or ""),
                         title, media_type, width, height, tuple(video_variants))

    @staticmethod
    def _first(data: dict, *fields: str) -> str:
        for field in fields:
            value = data.get(field)
            if isinstance(value, str) and value and value != "null":
                return value
        return ""

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _absolute(url: str) -> str:
        return f"https:{url}" if url.startswith("//") else url

    @staticmethod
    def _tags(value) -> set[str]:
        if isinstance(value, str):
            return {part.lower() for part in value.split()}
        if isinstance(value, list):
            return {str(item.get("name") if isinstance(item, dict) else item).lower() for item in value if item}
        if isinstance(value, dict):
            return {str(name).lower() for name in value}
        return set()

    @staticmethod
    def _rating_matches(value: str, choice: str) -> bool:
        return choice == "all" or (choice == "sfw" and value == "s") or (choice == "nsfw" and value == "e")

    @staticmethod
    def _image_headers(url: str) -> dict[str, str]:
        host = (urlparse(url).hostname or "").lower()
        headers = {"Accept": "image/avif,image/webp,image/*,*/*;q=0.8"}
        if host == "gelbooru.com" or host.endswith(".gelbooru.com"):
            headers["Referer"] = "https://gelbooru.com/"
        elif host == "rule34.xxx" or host.endswith(".rule34.xxx"):
            headers["Referer"] = "https://rule34.xxx/"
        return headers
