"""HTTP wire-contract tests: 401 auto-refresh retry, 5xx, timeout, bad JSON.

Everything here runs against mocked requests objects — zero network I/O.
The two transport helpers under contract are `_post`/`_get` (both implement
the canonical 401 → refresh → retry-once shape).

Defect-adjacent behaviour that is deliberately NOT pinned here:
  * fetch_monthly_summary / get_device_settings / _write_setting have no
    401-retry loop — documented in tests/KNOWN_DEFECTS.md instead.
  * legacy repeated-401 → HTTPError — documented in tests/KNOWN_DEFECTS.md.
"""

from unittest.mock import Mock, patch

import pytest
import requests

from custom_components.solar_of_things import api
from custom_components.solar_of_things.const import API_BASE_URL

FUTURE_ISO = "2099-01-01T00:00:00Z"


def _json_response(status: int = 200, payload: dict | None = None) -> Mock:
    resp = Mock()
    resp.status_code = status
    resp.raise_for_status = Mock()
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status} error")
    resp.json = Mock(return_value=payload if payload is not None else {})
    return resp


def _make_api():
    """token_pair instance with a far-future token: the pre-flight
    _ensure_token_valid() is a no-op, so every call lands on session.post."""
    return api.SolarOfThingsAPI(
        iot_token="tok_1",
        refresh_token="rt_1",
        access_token_expires=FUTURE_ISO,
        refresh_token_expires=FUTURE_ISO,
    )


def _refresh_ok_response() -> Mock:
    return _json_response(
        200,
        payload={
            "code": 0,
            "data": {
                "accessToken": "tok_2",
                "refreshToken": "rt_2",
                "accessTokenWillExpiredAt": FUTURE_ISO,
                "refreshTokenWillExpiredAt": FUTURE_ISO,
            },
        },
    )


# ── POST: 401 auto-refresh retry ─────────────────────────────────────────────


def test_post_401_triggers_refresh_and_retries_once() -> None:
    api_instance = _make_api()
    session = Mock()
    session.post.side_effect = [_json_response(401), _json_response(200, {"code": 0, "data": {"ok": True}})]

    with (
        patch.object(api_instance, "session", session),
        patch.object(api.requests, "post", return_value=_refresh_ok_response()) as refresh_post,
    ):
        result = api_instance._post("/apis/station/info", {"stationId": "S1"})

    assert result == {"code": 0, "data": {"ok": True}}
    assert session.post.call_count == 2
    # Retry re-sent the identical payload to the identical URL.
    first, second = session.post.call_args_list
    assert first.args[0] == f"{API_BASE_URL}/apis/station/info"
    assert second.args == first.args
    assert second.kwargs == first.kwargs
    # Refresh happened exactly once, against the refresh endpoint.
    refresh_post.assert_called_once()
    assert "/apis/login/refresh/access/token" in refresh_post.call_args.args[0]
    # Session picked up the refreshed token for the retry.
    assert api_instance.access_token == "tok_2"


def test_post_repeated_401_with_rejected_refresh_raises_token_expired() -> None:
    """Refresh itself gets 401 → TokenExpiredError rather than HTTPError."""
    api_instance = _make_api()
    session = Mock()
    session.post.return_value = _json_response(401)

    with (
        patch.object(api_instance, "session", session),
        patch.object(api.requests, "post", return_value=_json_response(401)),
    ):
        with pytest.raises(api.TokenExpiredError, match="re-authenticate"):
            api_instance._post("/apis/station/info", {"stationId": "S1"})

    # The nested _ensure_token_valid() raises before the retry is attempted,
    # so exactly one wire attempt is made.
    assert session.post.call_count == 1


# ── POST: 5xx, timeout, malformed JSON ───────────────────────────────────────


def test_post_503_propagates_http_error_without_retry_or_refresh() -> None:
    api_instance = _make_api()
    session = Mock()
    session.post.return_value = _json_response(503)

    with (
        patch.object(api_instance, "session", session),
        patch.object(api.requests, "post") as refresh_post,
    ):
        with pytest.raises(requests.HTTPError, match="503"):
            api_instance._post("/apis/station/info", {"stationId": "S1"})

    # 5xx is not credential-related: exactly one attempt, no refresh.
    session.post.assert_called_once()
    refresh_post.assert_not_called()


def test_post_timeout_propagates_unswallowed() -> None:
    api_instance = _make_api()
    session = Mock()
    session.post.side_effect = requests.Timeout("timed out")

    with (
        patch.object(api_instance, "session", session),
        patch.object(api.requests, "post"),
    ):
        with pytest.raises(requests.Timeout):
            api_instance._post("/apis/station/info", {"stationId": "S1"})


def test_post_malformed_json_raises_value_error() -> None:
    api_instance = _make_api()
    session = Mock()
    resp = _json_response(200, {"code": 0})
    resp.json.side_effect = ValueError("Expecting value: line 1 column 1")
    session.post.return_value = resp

    with (
        patch.object(api_instance, "session", session),
        patch.object(api.requests, "post"),
    ):
        with pytest.raises(ValueError, match="Expecting value"):
            api_instance._post("/apis/station/info", {"stationId": "S1"})


# ── GET mirrors the POST retry shape ─────────────────────────────────────────


def test_get_401_triggers_refresh_and_retries_once() -> None:
    api_instance = _make_api()
    session = Mock()
    session.get.side_effect = [_json_response(401), _json_response(200, {"code": 0, "data": {"rows": []}})]

    with (
        patch.object(api_instance, "session", session),
        patch.object(api.requests, "post", return_value=_refresh_ok_response()) as refresh_post,
    ):
        result = api_instance._get("/apis/station/list", {"page": 1})

    assert result == {"code": 0, "data": {"rows": []}}
    assert session.get.call_count == 2
    refresh_post.assert_called_once()
    assert api_instance.access_token == "tok_2"


def test_get_repeated_401_raises_token_expired() -> None:
    api_instance = _make_api()
    session = Mock()
    session.get.return_value = _json_response(401)

    with (
        patch.object(api_instance, "session", session),
        patch.object(api.requests, "post", return_value=_json_response(401)),
    ):
        with pytest.raises(api.TokenExpiredError, match="re-authenticate"):
            api_instance._get("/apis/station/list", {"page": 1})

    assert session.get.call_count == 1