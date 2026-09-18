"""Token lifecycle contract tests (pure unit tests — network-free).

Covers: the three auth-mode classifications, proactive refresh decision
(including the TOKEN_REFRESH_LEAD_SECONDS = 300 s boundary), malformed
expiry parsing, refresh rejection paths, the re-login fallback, and the
exact on_token_refreshed callback payload the HA config entry persists.

The datetime boundary tests freeze api.datetime with a stand-in exposing
only now()/fromisoformat(), so wall-clock time never enters the picture.
"""

import json
from datetime import datetime as _real_datetime
from datetime import timedelta, timezone
from unittest.mock import Mock, patch

import pytest
import requests

from custom_components.solar_of_things import api
from custom_components.solar_of_things.const import TOKEN_REFRESH_LEAD_SECONDS

FUTURE_ISO = "2099-01-01T00:00:00Z"
FUTURE_ISO_OFFSET = "2099-01-01T00:00:00+00:00"


class _FakeDatetime:
    """Minimal api.datetime stand-in: frozen now(), real parsing."""

    fixed_now: _real_datetime | None = None

    @classmethod
    def now(cls, tz=None):  # noqa: ANN001
        if cls.fixed_now is None:
            raise AssertionError("_FakeDatetime.fixed_now not set for this test")
        return cls.fixed_now

    @classmethod
    def fromisoformat(cls, value: str) -> _real_datetime:
        return _real_datetime.fromisoformat(value)


def _json_response(status: int = 200, payload: dict | None = None) -> Mock:
    resp = Mock()
    resp.status_code = status
    resp.raise_for_status = Mock()
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status} error")
    resp.json = Mock(return_value=payload if payload is not None else {})
    return resp


def _token_pair_api(**overrides):
    kwargs = {
        "iot_token": "tok_1",
        "refresh_token": "rt_1",
        "access_token_expires": FUTURE_ISO,
        "refresh_token_expires": FUTURE_ISO,
    }
    kwargs.update(overrides)
    return api.SolarOfThingsAPI(**kwargs)


# ── Auth-mode classification ─────────────────────────────────────────────────


def test_constructor_classifies_password_mode() -> None:
    api_instance = api.SolarOfThingsAPI(user_id="u", password="p")
    assert api_instance._auth_mode == "password"


def test_constructor_classifies_token_pair_mode() -> None:
    api_instance = _token_pair_api()
    assert api_instance._auth_mode == "token_pair"


def test_constructor_classifies_legacy_mode() -> None:
    api_instance = api.SolarOfThingsAPI(iot_token="tok_1")
    assert api_instance._auth_mode == "legacy"


def test_constructor_rejects_credentialless_mode() -> None:
    with pytest.raises(ValueError, match="Provide either"):
        api.SolarOfThingsAPI()


# ── Proactive refresh decision & 300 s boundary ──────────────────────────────


def test_valid_token_does_not_need_refresh() -> None:
    api_instance = _token_pair_api()
    assert api_instance._token_needs_refresh() is False


def test_ensure_token_valid_is_noop_when_token_valid() -> None:
    api_instance = _token_pair_api()
    with patch.object(api.requests, "post") as post:
        api_instance._ensure_token_valid()
    post.assert_not_called()
    assert api_instance.access_token == "tok_1"


def test_refresh_boundary_exactly_lead_seconds() -> None:
    """expiry == now + 300 s: refresh MUST trigger (>= comparison)."""
    base = _real_datetime(2033, 5, 4, 12, 0, 0, tzinfo=timezone.utc)
    _FakeDatetime.fixed_now = base

    expires = (base + timedelta(seconds=TOKEN_REFRESH_LEAD_SECONDS)).replace(microsecond=0)
    api_instance = _token_pair_api(access_token_expires=expires.isoformat())
    with patch.object(api, "datetime", _FakeDatetime):
        assert api_instance._token_needs_refresh() is True

    # One second past the lead window the token is still "fresh".
    expires = (base + timedelta(seconds=TOKEN_REFRESH_LEAD_SECONDS + 1)).replace(microsecond=0)
    api_instance = _token_pair_api(access_token_expires=expires.isoformat())
    with patch.object(api, "datetime", _FakeDatetime):
        assert api_instance._token_needs_refresh() is False


def test_boundary_triggers_actual_refresh_via_ensure() -> None:
    base = _real_datetime(2033, 5, 4, 12, 0, 0, tzinfo=timezone.utc)
    _FakeDatetime.fixed_now = base
    expires = (base + timedelta(seconds=TOKEN_REFRESH_LEAD_SECONDS)).replace(microsecond=0)
    api_instance = _token_pair_api(access_token_expires=expires.isoformat())

    ok = _json_response(
        200,
        payload={"code": 0, "data": {"accessToken": "fresh_at", "refreshToken": "rt_1"}},
    )
    with patch.object(api, "datetime", _FakeDatetime), patch.object(
        api.requests, "post", return_value=ok
    ) as post:
        api_instance._ensure_token_valid()
    post.assert_called_once()
    assert post.call_args.kwargs["json"]["refreshToken"] == "rt_1"
    assert api_instance.access_token == "fresh_at"


# ── Malformed / missing expiry ───────────────────────────────────────────────


def test_malformed_expiry_parses_to_none_and_still_refreshes() -> None:
    """Garbage expiry must not crash the constructor and must force refresh."""
    api_instance = _token_pair_api(access_token_expires="not-a-date")
    assert api_instance._access_expires is None
    assert api_instance._token_needs_refresh() is True

    ok = _json_response(
        200,
        payload={"code": 0, "data": {"accessToken": "recovered_at", "refreshToken": "rt_2"}},
    )
    with patch.object(api.requests, "post", return_value=ok):
        api_instance._ensure_token_valid()
    assert api_instance.access_token == "recovered_at"


def test_legacy_unknown_expiry_does_not_proactively_refresh() -> None:
    """Legacy mode keeps clear of refresh without a refresh token.

    NOTE: this exact mechanism is the root cause of KNOWN_DEFECTS.md defect
    #1 (second 401 surfaces as HTTPError instead of TokenExpiredError).
    The test below pins the *mechanism*; the wrong-outer-behaviour is
    documented there rather than being promoted into a contract.
    """
    api_instance = api.SolarOfThingsAPI(
        iot_token="tok_1", access_token_expires="not-a-date"
    )
    assert api_instance._access_expires is None
    assert api_instance._token_needs_refresh() is False


def test_empty_expiry_fields_yield_empty_iso_properties() -> None:
    api_instance = _token_pair_api(access_token_expires="", refresh_token_expires=None)
    assert api_instance.access_token_expires_iso == ""
    assert api_instance.refresh_token_expires_iso == ""


# ── Refresh rejection paths ──────────────────────────────────────────────────


def test_refresh_without_refresh_token_raises() -> None:
    api_instance = api.SolarOfThingsAPI(iot_token="tok_1")
    with pytest.raises(api.TokenExpiredError, match="No refresh token available"):
        api_instance.refresh_access_token()


def test_refresh_401_rejection_raises_token_expired() -> None:
    api_instance = _token_pair_api()
    with patch.object(api.requests, "post", return_value=_json_response(401)):
        with pytest.raises(api.TokenExpiredError, match="rejected"):
            api_instance.refresh_access_token()


def test_refresh_403_rejection_raises_token_expired() -> None:
    api_instance = _token_pair_api()
    with patch.object(api.requests, "post", return_value=_json_response(403)):
        with pytest.raises(api.TokenExpiredError, match="rejected"):
            api_instance.refresh_access_token()


def test_refresh_api_error_code_raises_token_expired() -> None:
    api_instance = _token_pair_api()
    resp = _json_response(200, payload={"code": 50002, "message": "token invalid"})
    with patch.object(api.requests, "post", return_value=resp):
        with pytest.raises(api.TokenExpiredError, match="code=50002"):
            api_instance.refresh_access_token()


def test_ensure_raises_when_all_refresh_strategies_exhausted() -> None:
    """No refresh token, no stored password → only re-auth can help."""
    api_instance = api.SolarOfThingsAPI(iot_token="tok_1", access_token_expires="2000-01-01T00:00:00Z")
    with patch.object(api.requests, "post"):
        with pytest.raises(api.TokenExpiredError, match="re-authenticate"):
            api_instance._ensure_token_valid()


# ── Successful refresh: token state + callback payload ───────────────────────


def test_refresh_success_updates_state_and_fires_callback() -> None:
    callback = Mock()
    api_instance = _token_pair_api()
    api_instance._on_token_refreshed = callback

    resp = _json_response(
        200,
        payload={
            "code": 0,
            "data": {
                "accessToken": "new_at",
                "refreshToken": "new_rt",
                "accessTokenWillExpiredAt": FUTURE_ISO,
                "refreshTokenWillExpiredAt": FUTURE_ISO,
            },
        },
    )
    with patch.object(api.requests, "post", return_value=resp):
        api_instance.refresh_access_token()

    assert api_instance.access_token == "new_at"
    assert api_instance.refresh_token == "new_rt"
    assert api_instance.access_token_expires_iso == FUTURE_ISO_OFFSET
    assert api_instance.session.headers.get("IOT-Token") == "new_at"

    callback.assert_called_once_with("new_at", "new_rt", FUTURE_ISO_OFFSET, FUTURE_ISO_OFFSET)


def test_refresh_callback_reports_empty_strings_for_missing_expiry() -> None:
    callback = Mock()
    api_instance = _token_pair_api()
    api_instance._on_token_refreshed = callback

    resp = _json_response(200, payload={"code": 0, "data": {"accessToken": "new_at"}})
    with patch.object(api.requests, "post", return_value=resp):
        api_instance.refresh_access_token()

    callback.assert_called_once_with("new_at", "", "", "")


# ── Re-login fallback after refresh rejection (password mode) ────────────────


def test_ensure_falls_back_to_login_when_refresh_rejected() -> None:
    """Password mode: refresh rejected → re-login with stored credentials."""
    api_instance = api.SolarOfThingsAPI(
        user_id="u", password="p",
        iot_token="stale_at", refresh_token="stale_rt",
        access_token_expires="2000-01-01T00:00:00Z",  # expired → refresh needed
    )
    assert api_instance._auth_mode == "password"

    rejected = _json_response(401)
    logged_in = _json_response(
        200,
        payload={
            "code": 0,
            "data": {
                "accessToken": "relogin_at",
                "refreshToken": "relogin_rt",
                "accessTokenWillExpiredAt": FUTURE_ISO,
                "refreshTokenWillExpiredAt": FUTURE_ISO,
            },
        },
    )

    with patch.object(api.requests, "post", side_effect=[rejected, logged_in]) as post:
        api_instance._ensure_token_valid()

    assert post.call_count == 2
    assert api_instance.access_token == "relogin_at"
    # Call 1 = refresh endpoint, call 2 = login endpoint
    assert "/apis/login/refresh/access/token" in post.call_args_list[0].args[0]
    assert "/apis/login/account" in post.call_args_list[1].args[0]


def test_session_is_kept_alive_across_refresh() -> None:
    """The session object must persist (only auth calls use requests.post)."""
    api_instance = _token_pair_api()
    session = api_instance.session
    assert session is not None
    assert session.headers.get("Accept") == "application/json"
    assert session.headers.get("Content-Type") == "application/json; charset=utf-8"