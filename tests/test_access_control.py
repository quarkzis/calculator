"""Independent password vectors and real AppTest access-boundary checks.

All credentials in this file are deliberately public test fixtures. Every test
overrides Streamlit secrets so a developer's local configuration is never read.
"""

from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import access_control
import eudr_model


ROOT = Path(__file__).resolve().parents[1]
TEST_PASSWORD = "Contraseña para pruebas 🔒"
TEST_SALT = bytes.fromhex("00112233445566778899aabbccddeeff")
# Independently calculated PBKDF2-HMAC-SHA256 known-answer vector: UTF-8, 600000 iterations.
TEST_HASH = (
    "pbkdf2_sha256$600000$00112233445566778899aabbccddeeff$"
    "a6f7eba8762b50fb319b7eb8101847f6aa4a2951fba5a8f687938057b5f7cbf3"
)
MISSING = object()


def new_app(encoded=TEST_HASH):
    at = AppTest.from_file(ROOT / "calculator.py", default_timeout=30)
    # AppTest only isolates secrets when this mapping is non-empty.
    at.secrets["test_configuration_marker"] = "isolated-test-secrets"
    if encoded is not MISSING:
        at.secrets["app_password_hash"] = encoded
    at.run()
    assert not at.exception
    return at


def submit(at, password):
    at.text_input(key="_access_password").set_value(password)
    at.button(key="_access_submit").click().run()
    assert not at.exception
    return at


def assert_protected_content_hidden(at):
    assert not at.exception
    assert len(at.metric) == 0
    assert len(at.dataframe) == 0
    assert len(at.number_input) == 0
    assert len(at.get("download_button")) == 0
    assert "task_inputs" not in at.session_state
    assert "company_group" not in at.session_state


def test_password_encoding_matches_independent_unicode_vector():
    assert access_control.hash_password(TEST_PASSWORD, salt=TEST_SALT) == TEST_HASH
    assert access_control.verify_password(TEST_PASSWORD, TEST_HASH) is True
    assert access_control.verify_password("Contraseña para pruebas 🔓", TEST_HASH) is False
    assert access_control.verify_password(TEST_PASSWORD + " ", TEST_HASH) is False


def test_random_salts_produce_distinct_valid_hashes():
    first = access_control.hash_password(TEST_PASSWORD)
    second = access_control.hash_password(TEST_PASSWORD)
    assert first != second
    for encoded in (first, second):
        assert re.fullmatch(r"pbkdf2_sha256\$600000\$[0-9a-f]{32}\$[0-9a-f]{64}", encoded)
        assert TEST_PASSWORD not in encoded
        assert access_control.verify_password(TEST_PASSWORD, encoded) is True
        assert access_control.verify_password("wrong test password", encoded) is False


@pytest.mark.parametrize("encoded", [
    "", "plain-test-password", None, 123,
    TEST_HASH.replace("pbkdf2_sha256", "sha256"),
    TEST_HASH.replace("600000", "1"),
    TEST_HASH.replace("600000", "99999999999999999999"),
    TEST_HASH.replace("00112233445566778899aabbccddeeff", "001122"),
    TEST_HASH[:-1], TEST_HASH + "$trailing", TEST_HASH[:-1] + "g",
])
def test_malformed_or_unsupported_hashes_fail_closed(encoded):
    assert access_control.verify_password(TEST_PASSWORD, encoded) is False


def test_login_gate_has_no_task_data_results_or_downloads(monkeypatch):
    def forbidden_calculation(*args, **kwargs):
        pytest.fail("The calculator executed before authentication")

    monkeypatch.setattr(eudr_model, "calculate", forbidden_calculation)
    at = new_app()
    assert_protected_content_hidden(at)
    password = at.text_input(key="_access_password")
    # TextInputProto.PASSWORD = 1; this checks the actual rendered widget type.
    assert password.proto.type == 1
    assert password.value == ""


@pytest.mark.parametrize("encoded", [MISSING, "", "not-a-password-hash", None, TEST_HASH[:-1]])
def test_missing_or_malformed_configuration_blocks_the_application(encoded, monkeypatch):
    def forbidden_calculation(*args, **kwargs):
        pytest.fail("The calculator executed with missing/invalid access configuration")

    monkeypatch.setattr(eudr_model, "calculate", forbidden_calculation)
    at = new_app(encoded)
    assert_protected_content_hidden(at)
    assert len(at.error) > 0
    assert not at.text_input


def test_wrong_password_is_cleared_then_unicode_login_opens_calculator():
    at = new_app()
    submit(at, "incorrect public test password")
    assert_protected_content_hidden(at)
    assert at.text_input(key="_access_password").value == ""
    assert at.error
    submit(at, TEST_PASSWORD)
    assert len(at.metric) > 0
    assert len(at.dataframe) > 0
    assert len(at.get("download_button")) == 2
    assert not at.text_input
    state = at.session_state.to_dict()
    assert TEST_PASSWORD not in state.values()
    assert "_access_password" not in state or state["_access_password"] == ""
    assert at.button(key="_access_logout")


def test_logout_clears_task_edits_and_a_new_login_starts_clean():
    at = submit(new_app(), TEST_PASSWORD)
    edited = next(widget for widget in at.number_input if widget.key.startswith("_days:"))
    key, original = edited.key, edited.value
    edited.set_value(original + 7).run()
    assert at.number_input(key=key).value == original + 7
    at.session_state["arbitrary_private_session_value"] = "must be cleared"
    at.button(key="_access_logout").click().run()
    assert_protected_content_hidden(at)
    assert "arbitrary_private_session_value" not in at.session_state
    submit(at, TEST_PASSWORD)
    assert at.number_input(key=key).value == original


def test_secret_rotation_revokes_existing_session_and_old_password():
    at = submit(new_app(), TEST_PASSWORD)
    assert at.metric
    replacement_password = "Replacement public test password 2"
    at.secrets["app_password_hash"] = access_control.hash_password(replacement_password, salt=b"rotation-test-16")
    at.run()
    assert_protected_content_hidden(at)
    submit(at, TEST_PASSWORD)
    assert_protected_content_hidden(at)
    submit(at, replacement_password)
    assert at.metric
    del at.secrets["app_password_hash"]
    at.run()
    assert_protected_content_hidden(at)
    assert at.error


def test_fifth_wrong_attempt_starts_only_a_session_cooldown(monkeypatch):
    clock = [1000.0]
    # Replace this module's clock only, not Streamlit's timeout clock.
    monkeypatch.setattr(access_control, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    at = new_app()
    for attempt in range(5):
        submit(at, "incorrect test password")
        assert_protected_content_hidden(at)
        if attempt < 4:
            assert at.text_input(key="_access_password").value == ""
    assert at.session_state["_access_blocked_until"] > clock[0]
    assert at.info
    assert at.text_input(key="_access_password").disabled
    assert at.button(key="_access_submit").disabled
    # Model a client that ignores disabled controls. The server must still refuse it.
    at.text_input(key="_access_password").proto.disabled = False
    at.button(key="_access_submit").proto.disabled = False
    submit(at, TEST_PASSWORD)
    assert_protected_content_hidden(at)
    # A separate visitor is not locked out by this browser session's failures.
    other = submit(new_app(), TEST_PASSWORD)
    assert other.metric
    clock[0] += 31
    at.run()
    submit(at, TEST_PASSWORD)
    assert at.metric
