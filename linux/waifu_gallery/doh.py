"""Cloudflare DNS-over-HTTPS lookup used by the optional network setting."""

import ipaddress
import socket
import threading
import time

import requests


_SYSTEM_GETADDRINFO = socket.getaddrinfo
_CLOUDFLARE_HOST = "cloudflare-dns.com"
_STATE_LOCK = threading.RLock()
_ACTIVE_RESOLVER = None
_HOOK_INSTALLED = False


class CloudflareResolver:
    endpoint = "https://cloudflare-dns.com/dns-query"

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, tuple[str, ...]]] = {}
        self._lock = threading.Lock()
        self._sessions = threading.local()

    def resolve(self, hostname: str) -> tuple[str, ...]:
        name = hostname.rstrip(".").encode("idna").decode("ascii").casefold()
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(name)
            if cached and cached[0] > now:
                return cached[1]

        session = getattr(self._sessions, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"Accept": "application/dns-json"})
            self._sessions.session = session

        addresses: list[str] = []
        ttls: list[int] = []
        for record_type in ("A", "AAAA"):
            try:
                response = session.get(
                    self.endpoint,
                    params={"name": name, "type": record_type},
                    timeout=(3, 8),
                )
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as error:
                raise socket.gaierror(f"Cloudflare DoH lookup failed for {name}: {type(error).__name__}") from error

            if payload.get("Status") != 0:
                continue
            for answer in payload.get("Answer", []):
                value = str(answer.get("data", "")).rstrip(".")
                try:
                    ipaddress.ip_address(value)
                except ValueError:
                    continue
                addresses.append(value)
                try:
                    ttls.append(int(answer.get("TTL", 60)))
                except (TypeError, ValueError):
                    pass

        unique = tuple(dict.fromkeys(addresses))
        if not unique:
            raise socket.gaierror(f"Cloudflare DoH returned no addresses for {name}")
        ttl = max(30, min(600, min(ttls) if ttls else 60))
        with self._lock:
            self._cache[name] = (now + ttl, unique)
        return unique


def _doh_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    with _STATE_LOCK:
        resolver = _ACTIVE_RESOLVER
    if resolver is None or host is None:
        return _SYSTEM_GETADDRINFO(host, port, family, type, proto, flags)

    hostname = host.decode() if isinstance(host, bytes) else str(host)
    if hostname.rstrip(".").casefold() == _CLOUDFLARE_HOST:
        # Bootstrap the DoH endpoint through the OS resolver to avoid recursion.
        return _SYSTEM_GETADDRINFO(host, port, family, type, proto, flags)
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return _SYSTEM_GETADDRINFO(host, port, family, type, proto, flags)

    answers = []
    for address in resolver.resolve(hostname):
        address_family = socket.AF_INET6 if ":" in address else socket.AF_INET
        if family not in (0, socket.AF_UNSPEC, address_family):
            continue
        answers.extend(_SYSTEM_GETADDRINFO(
            address,
            port,
            address_family,
            type,
            proto,
            flags | socket.AI_NUMERICHOST,
        ))
    if not answers:
        raise socket.gaierror(f"DoH returned no address matching the requested family for {hostname}")
    return answers


def set_doh_enabled(enabled: bool) -> None:
    """Enable DoH for this process's requests without changing Windows settings."""
    global _ACTIVE_RESOLVER, _HOOK_INSTALLED
    with _STATE_LOCK:
        if enabled:
            if not _HOOK_INSTALLED:
                socket.getaddrinfo = _doh_getaddrinfo
                _HOOK_INSTALLED = True
            if _ACTIVE_RESOLVER is None:
                _ACTIVE_RESOLVER = CloudflareResolver()
        else:
            _ACTIVE_RESOLVER = None
