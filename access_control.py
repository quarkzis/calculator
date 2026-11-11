"""Shared-password access for Streamlit, with no plaintext password in code.

The attempt cooldown is local to one Streamlit session. It is not a global
rate limit and does not prevent attempts from another browser session.
"""

import hashlib
import hmac
import math
import re
import secrets
import time

import streamlit as st


ITERATIONS = 600_000
SALT_BYTES = 16
KEY_BYTES = 32
MAX_PASSWORD_BYTES = 4096
MAX_ATTEMPTS = 5
COOLDOWN_SECONDS = 30
SECRET_KEY = "app_password_hash"

PASSWORD_KEY = "_access_password"
AUTH_KEY = "_access_authenticated_hash"
ATTEMPTS_KEY = "_access_attempts"
BLOCKED_UNTIL_KEY = "_access_blocked_until"
ERROR_KEY = "_access_error"

_ENCODED_HASH = re.compile(
    r"pbkdf2_sha256\$600000\$([0-9a-fA-F]{32})\$([0-9a-fA-F]{64})"
)


def _password_bytes(password: str) -> bytes:
    if not isinstance(password, str):
        raise TypeError("Password must be text.")
    if not password or len(password) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must contain 1 to {MAX_PASSWORD_BYTES} UTF-8 bytes.")
    try:
        value = password.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("Password must be valid Unicode text.") from error
    if not value or len(value) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must contain 1 to {MAX_PASSWORD_BYTES} UTF-8 bytes.")
    return value


def _parse_hash(encoded):
    # Bound the input and accept only the one supported work factor. A value
    # from configuration can never request an unbounded iteration count.
    if not isinstance(encoded, str) or len(encoded) > 160:
        return None
    match = _ENCODED_HASH.fullmatch(encoded)
    if match is None:
        return None
    return bytes.fromhex(match[1]), bytes.fromhex(match[2])


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Return a salted PBKDF2-SHA256 hash suitable for app_password_hash.

    A supplied salt must contain exactly 16 bytes. Omitting it uses a fresh
    cryptographically random salt. Password whitespace is preserved.
    """
    value = _password_bytes(password)
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTES)
    elif not isinstance(salt, bytes):
        raise TypeError("Salt must be bytes.")
    if len(salt) != SALT_BYTES:
        raise ValueError(f"Salt must contain exactly {SALT_BYTES} bytes.")
    digest = hashlib.pbkdf2_hmac("sha256", value, salt, ITERATIONS, dklen=KEY_BYTES)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, encoded) -> bool:
    """Return False for an incorrect password or malformed configuration."""
    parsed = _parse_hash(encoded)
    if parsed is None:
        return False
    try:
        value = _password_bytes(password)
    except (TypeError, ValueError):
        return False
    salt, expected = parsed
    candidate = hashlib.pbkdf2_hmac("sha256", value, salt, ITERATIONS, dklen=KEY_BYTES)
    return hmac.compare_digest(candidate, expected)


def _configured_hash():
    try:
        encoded = st.secrets[SECRET_KEY]
    except Exception:
        # Missing or unreadable secrets must not expose the app or configuration.
        return None
    return encoded if _parse_hash(encoded) is not None else None


def _fingerprint(encoded: str) -> str:
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def _cooldown_remaining() -> int:
    blocked_until = st.session_state.get(BLOCKED_UNTIL_KEY, 0)
    if not isinstance(blocked_until, (int, float)) or not math.isfinite(blocked_until):
        blocked_until = 0
    remaining = math.ceil(blocked_until - time.monotonic())
    if remaining > 0:
        return remaining
    if BLOCKED_UNTIL_KEY in st.session_state:
        st.session_state.pop(BLOCKED_UNTIL_KEY, None)
        st.session_state.pop(ATTEMPTS_KEY, None)
        st.session_state.pop(ERROR_KEY, None)
    return 0


def _submit_password():
    # Form callbacks run before the next render, so the submitted password is
    # removed even when verification fails or the session is in cooldown.
    password = st.session_state.pop(PASSWORD_KEY, "")
    encoded = _configured_hash()
    if encoded is None:
        st.session_state.clear()
        return
    if _cooldown_remaining():
        return
    if verify_password(password, encoded):
        st.session_state.clear()
        st.session_state[AUTH_KEY] = _fingerprint(encoded)
        return
    attempts = st.session_state.get(ATTEMPTS_KEY, 0) + 1
    st.session_state[ATTEMPTS_KEY] = attempts
    st.session_state[ERROR_KEY] = "Incorrect password."
    if attempts >= MAX_ATTEMPTS:
        st.session_state[BLOCKED_UNTIL_KEY] = time.monotonic() + COOLDOWN_SECONDS


def _logout():
    st.session_state.clear()


def require_access():
    """Render sign-in and stop execution until this session authenticates.

    Changing or removing the configured hash invalidates an existing login on
    the next rerun. Sign-out removes calculator inputs as well as login state.
    """
    encoded = _configured_hash()
    if encoded is None:
        st.session_state.clear()
        st.error("Access is not configured. Please contact the app owner.")
        st.stop()

    configured_fingerprint = _fingerprint(encoded)
    authenticated = st.session_state.get(AUTH_KEY)
    is_authenticated = (
        isinstance(authenticated, str)
        and len(authenticated) == 64
        and hmac.compare_digest(authenticated.encode("utf-8"), configured_fingerprint.encode("ascii"))
    )
    if authenticated is not None and not is_authenticated:
        st.session_state.clear()
    if is_authenticated:
        st.sidebar.button("Sign out", key="_access_logout", on_click=_logout)
        return

    st.title("Sign in")
    remaining = _cooldown_remaining()
    if remaining:
        st.info(f"Too many attempts in this session. Try again in {remaining} seconds.")
        st.caption("This cooldown applies only to the current session.")
        st.button("Check again", key="_access_check")
    elif st.session_state.get(ERROR_KEY):
        st.error(st.session_state[ERROR_KEY])

    with st.form("_access_login_form", clear_on_submit=True):
        st.text_input(
            "Password", type="password", key=PASSWORD_KEY,
            max_chars=MAX_PASSWORD_BYTES, disabled=bool(remaining),
        )
        st.form_submit_button(
            "Sign in", key="_access_submit", on_click=_submit_password,
            disabled=bool(remaining),
        )
    st.stop()
