import base64
import hashlib
import json
import os
from collections.abc import Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


SCHEMA = "waifu-gallery-user-data"
FORMAT_VERSION = 2
SUPPORTED_FORMAT_VERSIONS = {1, FORMAT_VERSION}
KDF_ITERATIONS = 600_000
AAD_BY_VERSION = {
    1: b"waifu-gallery-backup:v1",
    FORMAT_VERSION: b"waifu-gallery-backup:v2",
}
MAX_BACKUP_BYTES = 32 * 1024 * 1024
BACKUP_SECTIONS = ("favorites", "providers", "theme", "settings")
LEGACY_BACKUP_SECTIONS = ("favorites", "providers", "settings")
_PROVIDERS = {"All", "Auto", "Danbooru", "yande.re", "Gelbooru", "Rule34.xxx"}
_DOH_PROVIDERS = {
    "Cloudflare",
    "Cloudflare Security",
    "Cloudflare Family",
    "Google Public DNS",
    "AdGuard DNS",
    "Custom",
}


def _strings(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Backup field '{field}' must be a list of strings.")
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Backup field '{field}' must be a boolean.")
    return value


def normalize_payload(payload: object) -> dict:
    if not isinstance(payload, Mapping):
        raise ValueError("The backup data is not a JSON object.")
    version = payload.get("version")
    if (
        payload.get("schema") != SCHEMA
        or type(version) is not int
        or version not in SUPPORTED_FORMAT_VERSIONS
    ):
        raise ValueError("This backup format is unsupported.")
    if "sections" in payload:
        sections = _strings(payload["sections"], "sections")
        if (
            not sections
            or len(sections) != len(set(sections))
            or any(section not in BACKUP_SECTIONS for section in sections)
        ):
            raise ValueError("The backup contains an invalid section selection.")
    elif version == 1:
        sections = list(LEGACY_BACKUP_SECTIONS)
        if "theme" in payload:
            sections.append("theme")
    else:
        raise ValueError("The backup is missing its included data sections.")
    if "theme" in sections:
        theme = _optional_string(payload.get("theme"), "theme")
        if not theme.strip():
            raise ValueError("The backup contains an invalid theme.")
    else:
        theme = "Dark"

    favorites = payload.get("favorites")
    if not isinstance(favorites, list):
        raise ValueError("Backup favorites must be a list.")
    normalized_favorites = []
    for favorite in favorites:
        if not isinstance(favorite, Mapping):
            raise ValueError("A favorite in this backup is invalid.")
        post_id = favorite.get("post_id")
        provider = favorite.get("provider")
        image_url = favorite.get("image_url")
        if not all(isinstance(item, str) and item.strip() for item in (post_id, provider, image_url)):
            raise ValueError("A favorite is missing its ID, provider, or image URL.")
        variants = favorite.get("video_variants", [])
        if not isinstance(variants, list):
            raise ValueError("A favorite has invalid video variants.")
        normalized_variants = []
        for variant in variants:
            if (
                not isinstance(variant, list)
                or len(variant) != 3
                or not isinstance(variant[0], str)
                or not variant[0].strip()
                or not all(isinstance(value, int) and not isinstance(value, bool) for value in variant[1:])
                or any(value < 0 for value in variant[1:])
            ):
                raise ValueError("A favorite has invalid video variants.")
            normalized_variants.append([variant[0], variant[1], variant[2]])
        dimensions = (favorite.get("width", 0), favorite.get("height", 0))
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in dimensions):
            raise ValueError("A favorite has invalid dimensions.")
        media_type = _optional_string(favorite.get("media_type", "image"), "favorite.media_type")
        if media_type not in {"image", "video"}:
            raise ValueError("A favorite has an unsupported media type.")
        normalized_favorites.append({
            "post_id": post_id,
            "provider": provider,
            "image_url": image_url,
            "preview_urls": _strings(favorite.get("preview_urls", []), "favorite.preview_urls"),
            "rating": _optional_string(favorite.get("rating", "q"), "favorite.rating"),
            "tags": _strings(favorite.get("tags", []), "favorite.tags"),
            "artists": _strings(favorite.get("artists", []), "favorite.artists"),
            "source": _optional_string(favorite.get("source", ""), "favorite.source"),
            "checksum": _optional_string(favorite.get("checksum", ""), "favorite.checksum"),
            "title": _optional_string(favorite.get("title", ""), "favorite.title"),
            "media_type": media_type,
            "width": dimensions[0],
            "height": dimensions[1],
            "video_variants": normalized_variants,
            "thumbnail_url": _optional_string(favorite.get("thumbnail_url", ""), "favorite.thumbnail_url"),
            "extension": _optional_string(favorite.get("extension", ""), "favorite.extension"),
            "dedupe_key": _optional_string(favorite.get("dedupe_key", ""), "favorite.dedupe_key"),
        })

    providers = payload.get("providers")
    if not isinstance(providers, Mapping):
        raise ValueError("Backup provider credentials are invalid.")
    credentials = {}
    for provider_name in ("gelbooru", "rule34"):
        entry = providers.get(provider_name)
        if not isinstance(entry, Mapping):
            raise ValueError(f"Backup credentials for {provider_name} are invalid.")
        user_id = _optional_string(entry.get("user_id", ""), f"{provider_name}.user_id").strip()
        api_key = _optional_string(entry.get("api_key", ""), f"{provider_name}.api_key").strip()
        if bool(user_id) != bool(api_key):
            raise ValueError(f"Backup credentials for {provider_name} are incomplete.")
        credentials[provider_name] = {"user_id": user_id, "api_key": api_key}

    settings = payload.get("settings")
    if not isinstance(settings, Mapping):
        raise ValueError("Backup preferences are invalid.")
    provider = settings.get("provider")
    rating = settings.get("rating")
    media_filter = settings.get("media_filter")
    doh_provider = settings.get("doh_provider")
    video_height = settings.get("video_max_height")
    if provider not in _PROVIDERS:
        raise ValueError("The backup contains an unsupported provider setting.")
    if (
        "providers" in sections
        and provider == "Gelbooru"
        and not credentials["gelbooru"]["user_id"]
    ):
        raise ValueError("The selected provider is missing its backup credentials.")
    if (
        "providers" in sections
        and provider == "Rule34.xxx"
        and not credentials["rule34"]["user_id"]
    ):
        raise ValueError("The selected provider is missing its backup credentials.")
    if rating not in {"sfw", "nsfw", "all"}:
        raise ValueError("The backup contains an unsupported rating setting.")
    if media_filter not in {"image", "video", "all"}:
        raise ValueError("The backup contains an unsupported media filter.")
    if doh_provider not in _DOH_PROVIDERS:
        raise ValueError("The backup contains an unsupported DNS provider.")
    if not isinstance(video_height, int) or isinstance(video_height, bool) or video_height not in {0, 480, 720, 1080, 2160}:
        raise ValueError("The backup contains an unsupported video resolution.")
    normalized_settings = {
        "provider": provider,
        "rating": rating,
        "allow_nsfw": _boolean(settings.get("allow_nsfw"), "settings.allow_nsfw"),
        "custom_terms": _strings(settings.get("custom_terms"), "settings.custom_terms"),
        "exclude_male": _boolean(settings.get("exclude_male"), "settings.exclude_male"),
        "filter_gore": _boolean(settings.get("filter_gore"), "settings.filter_gore"),
        "custom_block_tags": _strings(settings.get("custom_block_tags"), "settings.custom_block_tags"),
        "media_filter": media_filter,
        "use_doh": _boolean(settings.get("use_doh"), "settings.use_doh"),
        "doh_provider": doh_provider,
        "doh_custom_endpoint": _optional_string(settings.get("doh_custom_endpoint", ""), "settings.doh_custom_endpoint"),
        "ambient_mode": _boolean(settings.get("ambient_mode"), "settings.ambient_mode"),
        "video_max_height": video_height,
    }
    return {
        "schema": SCHEMA,
        "version": version,
        "sections": sections,
        "theme": theme,
        "favorites": normalized_favorites,
        "providers": credentials,
        "settings": normalized_settings,
    }


def _optional_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Backup field '{field}' must be text.")
    return value


def create_payload(settings, sections: tuple[str, ...] | None = None) -> dict:
    selected_sections = BACKUP_SECTIONS if sections is None else tuple(sections)
    included = set(selected_sections)
    allow_nsfw = bool(settings.get("search/allow_nsfw", False))
    theme = str(settings.get("appearance/theme", "Dark"))
    if theme not in {"Dark", "Light", "System"}:
        theme = "Dark"
    payload = {
        "schema": SCHEMA,
        "version": FORMAT_VERSION,
        "sections": list(selected_sections),
        "theme": theme if "theme" in included else "Dark",
        "favorites": settings.get("favorites/posts", []) if "favorites" in included else [],
        "providers": {
            "gelbooru": {
                "user_id": str(settings.get("gelbooru/user_id", "")).strip() if "providers" in included else "",
                "api_key": str(settings.get("gelbooru/api_key", "")).strip() if "providers" in included else "",
            },
            "rule34": {
                "user_id": str(settings.get("rule34/user_id", "")).strip() if "providers" in included else "",
                "api_key": str(settings.get("rule34/api_key", "")).strip() if "providers" in included else "",
            },
        },
        "settings": {
            "provider": str(settings.get("search/provider", "All")) if "settings" in included else "All",
            "rating": str(settings.get("search/rating", "sfw")) if "settings" in included else "sfw",
            "allow_nsfw": allow_nsfw if "settings" in included else False,
            "custom_terms": settings.get("search/custom_terms", []) if "settings" in included else [],
            "exclude_male": bool(settings.get("search/exclude_male", True)) if "settings" in included else True,
            "filter_gore": bool(settings.get("search/filter_gore", True)) if "settings" in included else True,
            "custom_block_tags": settings.get("search/custom_block_tags", []) if "settings" in included else [],
            "media_filter": str(settings.get("search/media_filter", "image")) if "settings" in included else "image",
            "use_doh": settings.use_doh if "settings" in included else False,
            "doh_provider": str(settings.get("network/doh_provider", "Cloudflare")) if "settings" in included else "Cloudflare",
            "doh_custom_endpoint": str(settings.get("network/doh_custom_endpoint", "")) if "settings" in included else "",
            "ambient_mode": bool(settings.get("view/ambient_mode", True)) if "settings" in included else True,
            "video_max_height": int(settings.get("video/max_height", 0) or 0) if "settings" in included else 0,
        },
    }
    return normalize_payload(payload)


def encrypt_payload(payload: Mapping, passphrase: str) -> str:
    _validate_passphrase(passphrase)
    normalized = normalize_payload(payload)
    normalized["version"] = FORMAT_VERSION
    plaintext = json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, KDF_ITERATIONS, dklen=32)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, AAD_BY_VERSION[FORMAT_VERSION])
    envelope = {
        "format": SCHEMA,
        "version": FORMAT_VERSION,
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": KDF_ITERATIONS,
        "cipher": "AES-256-GCM",
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }
    encoded = json.dumps(envelope, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_BACKUP_BYTES:
        raise ValueError("The user data is too large to fit in a backup file.")
    return encoded


def decrypt_payload(contents: str, passphrase: str) -> dict:
    _validate_passphrase(passphrase)
    if not isinstance(contents, str) or len(contents.encode("utf-8")) > MAX_BACKUP_BYTES:
        raise ValueError("The backup file is too large or invalid.")
    try:
        envelope = json.loads(contents)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError("The selected file is not a valid backup.") from error
    if (
        not isinstance(envelope, Mapping)
        or type(envelope.get("version")) is not int
        or envelope["version"] not in SUPPORTED_FORMAT_VERSIONS
    ):
        raise ValueError("This backup format or encryption configuration is unsupported.")
    version = envelope["version"]
    expected = {
        "format": SCHEMA,
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": KDF_ITERATIONS,
        "cipher": "AES-256-GCM",
    }
    if not isinstance(envelope, Mapping) or any(envelope.get(key) != value for key, value in expected.items()):
        raise ValueError("This backup format or encryption configuration is unsupported.")
    try:
        salt = base64.b64decode(envelope["salt"], validate=True)
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        if len(salt) != 16 or len(nonce) != 12 or not ciphertext:
            raise ValueError("The backup file is incomplete.")
        key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, KDF_ITERATIONS, dklen=32)
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, AAD_BY_VERSION[version])
        payload = normalize_payload(json.loads(plaintext.decode("utf-8")))
        if payload["version"] != version:
            raise ValueError("The backup payload and encryption versions do not match.")
        return payload
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("The passphrase is incorrect or the backup file is damaged.") from error


def _validate_passphrase(passphrase: str) -> None:
    if not isinstance(passphrase, str) or len(passphrase) < 8:
        raise ValueError("Use a backup passphrase with at least 8 characters.")
