import hashlib
import hmac
import secrets
import time


_PBKDF2_ITERATIONS = 310_000
_MIN_PIN_LENGTH = 4
_MAX_PIN_LENGTH = 12


def valid_pin(pin: str) -> bool:
    return pin.isascii() and pin.isdigit() and _MIN_PIN_LENGTH <= len(pin) <= _MAX_PIN_LENGTH


def set_pin(settings, prefix: str, pin: str) -> None:
    if not valid_pin(pin):
        raise ValueError("PIN must contain 4 to 12 digits.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("ascii"), salt, _PBKDF2_ITERATIONS)
    settings.set_many({
        f"{prefix}/pin_salt": salt.hex(),
        f"{prefix}/pin_hash": digest.hex(),
        f"{prefix}/pin_failures": 0,
        f"{prefix}/pin_locked_until": 0,
    })


def has_pin(settings, prefix: str) -> bool:
    return bool(settings.get(f"{prefix}/pin_salt", "")) and bool(settings.get(f"{prefix}/pin_hash", ""))


def verify_pin(settings, prefix: str, pin: str) -> tuple[bool, int]:
    now = time.time()
    try:
        locked_until = float(settings.get(f"{prefix}/pin_locked_until", 0) or 0)
    except (TypeError, ValueError):
        locked_until = now
    if locked_until > now:
        return False, max(1, int(locked_until - now))

    salt_value = str(settings.get(f"{prefix}/pin_salt", ""))
    digest_value = str(settings.get(f"{prefix}/pin_hash", ""))
    try:
        salt = bytes.fromhex(salt_value)
        expected = bytes.fromhex(digest_value)
    except ValueError:
        return False, 0
    if not salt or len(expected) != hashlib.sha256().digest_size:
        return False, 0

    candidate = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    if hmac.compare_digest(candidate, expected):
        settings.set_many({
            f"{prefix}/pin_failures": 0,
            f"{prefix}/pin_locked_until": 0,
        })
        return True, 0

    try:
        failures = int(settings.get(f"{prefix}/pin_failures", 0) or 0) + 1
    except (TypeError, ValueError):
        failures = 1
    delay = min(3600, 30 * (2 ** min(failures - 1, 7)))
    settings.set_many({
        f"{prefix}/pin_failures": failures,
        f"{prefix}/pin_locked_until": now + delay,
    })
    return False, delay
