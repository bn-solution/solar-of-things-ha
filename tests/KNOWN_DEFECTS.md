# Known Defects — Solar Of Things HA Integration

Status of this file: **evidence ledger, not a contract.**

The test suite in `tests/` pins *intended* behavior. Every entry below documents
behavior that the tests deliberately do **not** pin, because writing a test for
it would turn a bug into a contract. Fixes belong in
`custom_components/solar_of_things/` (out of the Phase-0 writable scope) —
before that, these tests must not be extended to assert the buggy path.

Reference: `api.py` line numbers verified against tag `v2.7.1`.

---

## 1. Legacy mode: 401 on data endpoint → `HTTPError`, not `TokenExpiredError`

**Severity:** High. Users on the legacy single-token setup get a raw
`requests.HTTPError` from `_post`/`_get` instead of a `TokenExpiredError` that
the flow layer can map to re-authentication.

**Root cause trace (verified against api.py, tag v2.7.1):**

1. Legacy mode = `iot_token` only (no `refresh_token`). Constructor:
   `api.py:382` `self._refresh_token = refresh_token or ""` → `""`, and
   `api.py:384` `self._access_expires = _parse_expiry(None)` → `None`.
2. `_token_needs_refresh()` (`api.py:563-569`) returns `False` for this
   state: with `_access_expires is None` it only refreshes if a refresh token
   exists (`return bool(self._refresh_token)` → `False`). So the pre-flight
   `_ensure_token_valid()` in `_post` skips refreshing.
3. Server rejects the stale token → first `session.post` returns 401.
   `_post` catches it, logs "received 401; forcing token refresh", sets
   `self._access_expires = None`, and calls the nested `_ensure_token_valid()`.
4. Nested call evaluates `_token_needs_refresh()` **again** → still `False`
   (no refresh token; expiry still None after reset) → returns **without
   raising**. `_post` retries `session.post` with the same dead token.
5. Second 401 → the retry path reaches `resp.raise_for_status()` (`api.py`
   ~655) → `requests.HTTPError` propagates to the caller.

**Why it differs from token_pair:** in token_pair mode the nested
`_ensure_token_valid()` *does* raise `TokenExpiredError` (refresh rejected →
strategy 3), so `_post` never reaches the retry (see
`tests/test_http_contract.py` `call_count == 1`). In legacy mode the nested
call is a no-op, so the retry happens and the final error is `HTTPError`.

**Consequence:** legacy-mode users see a confusing `HTTPError` and HA never
enters re-auth; the coordinator keeps retrying the same dead token.

**Test stance:** `tests/test_token_lifecycle.py::test_legacy_unknown_expiry_does_not_proactively_refresh`
pins only the mechanism (`_token_needs_refresh() is False` for a legacy token
with no expiry). The `HTTPError` outcome is **not** asserted. Once a
`TokenExpiredError`-on-second-401 path is implemented, that mechanism test
should be extended.

---

## 2. Token-pair setup: refresh token/expiry optional → silent degradation

**Severity:** Medium. The constructor accepts `iot_token` without
`refresh_token` (falls to "legacy") and accepts token pairs without expiry
fields. Config without expiry silently produces a token that is never
proactively refreshed (`_token_needs_refresh()` is False with
`_access_expires=None`), deferring all detection to the 401 path — which, in
legacy mode, is defect #1's `HTTPError`.

**Test stance:** auth-mode classification (password / token_pair / legacy / 
`ValueError`) is pinned in `tests/test_token_lifecycle.py`. The missing-refresh
fallback behavior is not pinned; a fix should validate that token-pair entries
carry both tokens + expiries at config-flow time.

---

## 3. Transport failure during refresh → wrongly surfaced as `TokenExpiredError`

**Severity:** Medium. `_ensure_token_valid` strategy 1
(`api.py:592-602`) catches `except Exception` around `refresh_access_token()`
and logs it as an error, then proceeds to strategy 2/3. A network timeout,
DNS failure, or 5xx from the refresh endpoint therefore surfaces as
`TokenExpiredError` ("re-authenticate") even though credentials are fine.

**Test stance:** the *refresh-rejected-classification* path (401/403 from
refresh endpoint → `TokenExpiredError`) IS pinned in
`tests/test_token_lifecycle.py`. The transport-failure misclassification is
**not** pinned.

---

## 4. `fetch_monthly_summary` / `get_device_settings` / `_write_setting`: no 401 handling at all

**Severity:** Medium. These three methods call `self.session.post` directly
(verified: `fetch_monthly_summary` at `api.py:953`, `_write_setting`
`api.py:1011`, `get_device_settings` `api.py:1025`) with inline query strings,
`resp.raise_for_status()` and a `code != (0, None)` RuntimeError check — but
**no** 401 detection, no `_ensure_token_valid()` re-entry, no refresh. An
expired token yields a raw `HTTPError` from

these endpoints, unlike `_post`/`_get`.

**Test stance:** the 401-retry contract is pinned **only** for `_post`/`_get`
in `tests/test_http_contract.py`. These three methods are excluded from the
HTTP contract tests. A fix should route them through `_post` (or add the same
401-retry shape).

---

## 5. `requests.Session` never explicitly closed

**Severity:** Low. `api.py:401` creates `self.session = requests.Session()`;
no `close()` exists anywhere in `custom_components/` (grep confirms). HA
recreates the API object on reload so leakage is bounded, but it is a
connection-resource leak with no deterministic teardown.

**Test stance:** the session's initial headers are pinned in
`tests/test_token_lifecycle.py`; `close()` behavior is not pinned. A fix
should add a `close()`/`async_close()` and wire it into the coordinator
unload path.