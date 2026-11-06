from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImagePost:
    post_id: str
    provider: str
    image_url: str
    preview_urls: tuple[str, ...]
    rating: str
    tags: frozenset[str]
    artists: tuple[str, ...] = ()
    source: str = ""
    checksum: str = ""
    title: str = ""


@dataclass(frozen=True, slots=True)
class SearchPage:
    posts: tuple[ImagePost, ...]
    has_more: bool
    provider_errors: tuple[str, ...] = ()
    fallback_from: str = ""
