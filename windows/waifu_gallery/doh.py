"""Process-local DNS-over-HTTPS resolver for provider HTTP requests."""

import base64
import ipaddress
import secrets
import socket
import struct
import threading
import time
from urllib.parse import urlsplit

import requests


DOH_ENDPOINTS = {
    "Cloudflare": "https://cloudflare-dns.com/dns-query",
    "Cloudflare Security (malware filtering)": "https://security.cloudflare-dns.com/dns-query",
    "Cloudflare Family (adult filtering)": "https://family.cloudflare-dns.com/dns-query",
    "Google Public DNS": "https://dns.google/dns-query",
    "AdGuard DNS": "https://dns.adguard-dns.com/dns-query",
}

_SYSTEM_GETADDRINFO = socket.getaddrinfo
_STATE_LOCK = threading.RLock()
_ACTIVE_RESOLVER = None
_HOOK_INSTALLED = False


def validate_doh_endpoint(endpoint: str) -> str:
    """Return a normalized HTTPS endpoint or raise ValueError."""
    value = endpoint.strip()
    parsed = urlsplit(value)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise ValueError("The DoH endpoint must be a valid HTTPS URL.")
    if parsed.username or parsed.password:
        raise ValueError("DoH endpoints must not contain embedded credentials.")
    if parsed.fragment:
        raise ValueError("DoH endpoints must not contain a URL fragment.")
    return value


def _encode_query(hostname: str, record_type: int, query_id: int) -> bytes:
    ascii_name = hostname.rstrip(".").encode("idna").decode("ascii")
    labels = ascii_name.split(".")
    if not ascii_name or any(not label or len(label) > 63 for label in labels):
        raise socket.gaierror(f"Invalid DNS hostname: {hostname}")
    qname = b"".join(bytes((len(label),)) + label.encode("ascii") for label in labels) + b"\0"
    header = struct.pack("!HHHHHH", query_id, 0x0100, 1, 0, 0, 0)
    return header + qname + struct.pack("!HH", record_type, 1)


def _read_name(packet: bytes, offset: int) -> tuple[str, int]:
    labels: list[str] = []
    cursor = offset
    next_offset = None
    visited: set[int] = set()
    while True:
        if cursor >= len(packet):
            raise ValueError("Truncated DNS name")
        length = packet[cursor]
        if length & 0xC0 == 0xC0:
            if cursor + 1 >= len(packet):
                raise ValueError("Truncated DNS compression pointer")
            pointer = ((length & 0x3F) << 8) | packet[cursor + 1]
            if pointer in visited:
                raise ValueError("DNS compression pointer loop")
            visited.add(pointer)
            if next_offset is None:
                next_offset = cursor + 2
            cursor = pointer
            continue
        if length & 0xC0:
            raise ValueError("Invalid DNS label encoding")
        cursor += 1
        if length == 0:
            return ".".join(labels), next_offset if next_offset is not None else cursor
        end = cursor + length
        if end > len(packet):
            raise ValueError("Truncated DNS label")
        labels.append(packet[cursor:end].decode("ascii"))
        cursor = end


def _parse_response(packet: bytes, query_id: int, expected_type: int) -> tuple[list[str], list[int]]:
    if len(packet) < 12:
        raise ValueError("The DoH resolver returned a truncated DNS response")
    response_id, flags, question_count, answer_count, _, _ = struct.unpack_from("!HHHHHH", packet)
    if response_id != query_id or not flags & 0x8000:
        raise ValueError("The DoH resolver returned an invalid DNS response")
    response_code = flags & 0x000F
    if response_code:
        if response_code == 3:
            return [], []
        raise socket.gaierror(f"DoH resolver returned DNS response code {response_code}")

    offset = 12
    for _ in range(question_count):
        _, offset = _read_name(packet, offset)
        if offset + 4 > len(packet):
            raise ValueError("Truncated DNS question")
        offset += 4

    addresses: list[str] = []
    ttls: list[int] = []
    for _ in range(answer_count):
        _, offset = _read_name(packet, offset)
        if offset + 10 > len(packet):
            raise ValueError("Truncated DNS answer")
        record_type, record_class, ttl, data_length = struct.unpack_from("!HHIH", packet, offset)
        offset += 10
        end = offset + data_length
        if end > len(packet):
            raise ValueError("Truncated DNS address record")
        if record_class == 1 and record_type == expected_type:
            expected_length = 4 if record_type == 1 else 16
            if data_length == expected_length:
                addresses.append(str(ipaddress.ip_address(packet[offset:end])))
                ttls.append(ttl)
        offset = end
    return addresses, ttls


class DoHResolver:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = validate_doh_endpoint(endpoint)
        self.host = (urlsplit(self.endpoint).hostname or "").rstrip(".").casefold()
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
            session.headers.update({"Accept": "application/dns-message"})
            self._sessions.session = session

        addresses: list[str] = []
        ttls: list[int] = []
        for record_type in (1, 28):
            query_id = secrets.randbits(16)
            message = _encode_query(name, record_type, query_id)
            encoded = base64.urlsafe_b64encode(message).rstrip(b"=").decode("ascii")
            try:
                response = session.get(
                    self.endpoint,
                    params={"dns": encoded},
                    headers={"Accept": "application/dns-message"},
                    timeout=(4, 8),
                )
                response.raise_for_status()
                record_addresses, record_ttls = _parse_response(response.content, query_id, record_type)
            except (requests.RequestException, ValueError, OSError) as error:
                raise socket.gaierror(
                    f"DoH lookup failed for {name}: {type(error).__name__}"
                ) from error
            addresses.extend(record_addresses)
            ttls.extend(record_ttls)

        unique = tuple(dict.fromkeys(addresses))
        if not unique:
            raise socket.gaierror(f"DoH returned no addresses for {name}")
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
    normalized = hostname.rstrip(".").casefold()
    if normalized == resolver.host:
        # Resolve the DoH server using the system resolver to avoid recursion.
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


def set_doh_enabled(enabled: bool, endpoint: str | None = None) -> None:
    """Enable DoH for this process without changing system DNS settings."""
    global _ACTIVE_RESOLVER, _HOOK_INSTALLED
    with _STATE_LOCK:
        if not enabled:
            _ACTIVE_RESOLVER = None
            return
        if endpoint is not None:
            normalized_endpoint = validate_doh_endpoint(endpoint)
            if _ACTIVE_RESOLVER is None or _ACTIVE_RESOLVER.endpoint != normalized_endpoint:
                _ACTIVE_RESOLVER = DoHResolver(normalized_endpoint)
        elif _ACTIVE_RESOLVER is None:
            _ACTIVE_RESOLVER = DoHResolver(DOH_ENDPOINTS["Cloudflare"])
        if not _HOOK_INSTALLED:
            socket.getaddrinfo = _doh_getaddrinfo
            _HOOK_INSTALLED = True
