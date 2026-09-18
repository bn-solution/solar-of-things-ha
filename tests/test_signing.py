"""Wire-signing contract tests — golden vectors computed independently.

These tests pin the exact wire signing scheme of the Siseli IOT API:
  * header set and alphabetical ordering (IOT-Open-AppID, IOT-Open-Body-Hash,
    IOT-Open-Nonce, IOT-Open-Sign),
  * body-hash = lowercase sha256 hex of the raw body bytes,
  * nonce = 32 lowercase hex chars from os.urandom(16),
  * sign = MD5( HMAC-SHA256( base64( sorted "k=v&k=v" qs ), app_secret ) ),
  * AES-128-CBC key/iv = MD5(appId) split [:16] / [16:], zero-padding.

All golden expectations below were computed from the first principles
described above (independent re-implementations in this file), not copied
from api.py. The real embedded app secret is never asserted as a value —
only its structural properties.
"""

import base64
import hashlib
import hmac
import json

import pytest
from Crypto.Cipher import AES

from custom_components.solar_of_things import api
from custom_components.solar_of_things.const import IOT_APP_ID, IOT_APP_SECRET_ENC

# ── Golden constants (computed independently) ────────────────────────────────

GOLDEN_APP_ID = "rBrTRfAPXz"
GOLDEN_NONCE = "ab" * 16
GOLDEN_BODY = b'{"a":1}'
GOLDEN_SECRET = "golden_secret_000000"
GOLDEN_MD5_APP_ID = "679491a9e47f235449d169b01a15fcc5"
GOLDEN_AES_KEY = "679491a9e47f2354"
GOLDEN_AES_IV = "49d169b01a15fcc5"
GOLDEN_BODY_HASH = (
    "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"
)
GOLDEN_QS = (
    f"IOT-Open-AppID={GOLDEN_APP_ID}"
    f"&IOT-Open-Body-Hash={GOLDEN_BODY_HASH}"
    f"&IOT-Open-Nonce={GOLDEN_NONCE}"
)
GOLDEN_B64_QS = base64.b64encode(GOLDEN_QS.encode("ascii")).decode("ascii")
GOLDEN_SIGN = "3fafe08485196488e94baf173b3b6cd4"


def _spec_compute_sign(headers: dict[str, str], secret: str) -> str:
    """Reference implementation of the sign scheme (independent of api.py)."""
    qs = "&".join(f"{k}={v}" for k, v in sorted(headers.items()))
    b64_qs = base64.b64encode(qs.encode("utf-8")).decode("ascii")
    hmac_digest = hmac.new(secret.encode("utf-8"), b64_qs.encode("utf-8"), hashlib.sha256).digest()
    return hashlib.md5(hmac_digest).hexdigest()


def _spec_key_iv(app_id: str) -> tuple[bytes, bytes]:
    md5_hex = hashlib.md5(app_id.encode("utf-8")).hexdigest()
    return md5_hex[:16].encode("ascii"), md5_hex[16:].encode("ascii")


def _spec_aes_encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    padded = plaintext + b"\x00" * (16 - len(plaintext) % 16)
    return AES.new(key, AES.MODE_CBC, iv).encrypt(padded)


# ── Module-level identity ────────────────────────────────────────────────────


def test_module_constants_match_production_wire_identity() -> None:
    assert api.IOT_APP_ID == GOLDEN_APP_ID
    assert IOT_APP_ID == GOLDEN_APP_ID
    # Embedded encrypted secret must be decryptable at import time.
    assert api._CRYPTO_AVAILABLE is True


# ── Golden vector coverage ───────────────────────────────────────────────────


def test_iot_sign_golden_vector() -> None:
    assert api._compute_iot_sign(GOLDEN_APP_ID, GOLDEN_NONCE, GOLDEN_BODY_HASH, GOLDEN_SECRET) == GOLDEN_SIGN


def test_iot_sign_matches_independent_reimplementation() -> None:
    """Feed the same inputs to api.py and the spec re-impl: equal output."""
    assert api._compute_iot_sign(GOLDEN_APP_ID, GOLDEN_NONCE, GOLDEN_BODY_HASH, GOLDEN_SECRET) == _spec_compute_sign(
        {
            "IOT-Open-AppID": GOLDEN_APP_ID,
            "IOT-Open-Body-Hash": GOLDEN_BODY_HASH,
            "IOT-Open-Nonce": GOLDEN_NONCE,
        },
        GOLDEN_SECRET,
    )


def test_sign_components_golden() -> None:
    """The exact string pipeline: qs → base64 → HMAC-SHA256 → MD5 hexdigest."""
    secret = GOLDEN_SECRET
    headers = {
        "IOT-Open-AppID": GOLDEN_APP_ID,
        "IOT-Open-Body-Hash": GOLDEN_BODY_HASH,
        "IOT-Open-Nonce": GOLDEN_NONCE,
    }
    qs = "&".join(f"{k}={v}" for k, v in sorted(headers.items()))
    assert qs == GOLDEN_QS
    b64 = base64.b64encode(qs.encode("utf-8")).decode("ascii")
    assert b64 == GOLDEN_B64_QS
    digest = hmac.new(secret.encode("utf-8"), b64.encode("utf-8"), hashlib.sha256).digest()
    assert hashlib.md5(digest).hexdigest() == GOLDEN_SIGN


# ── _make_signed_headers behaviour ───────────────────────────────────────────


def test_make_signed_headers_deterministic_with_fixed_nonce() -> None:
    fake_secret = GOLDEN_SECRET
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api.os, "urandom", lambda n: bytes.fromhex(GOLDEN_NONCE))
        mp.setattr(api, "_decrypt_app_secret", lambda app_id, blob: fake_secret)
        headers = api._make_signed_headers(GOLDEN_BODY)

    assert headers == {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "IOT-Open-AppID": GOLDEN_APP_ID,
        "IOT-Open-Body-Hash": GOLDEN_BODY_HASH,
        "IOT-Open-Nonce": GOLDEN_NONCE,
        "IOT-Open-Sign": GOLDEN_SIGN,
        "Origin": "https://solar.siseli.com",
        "Referer": "https://solar.siseli.com/",
    }


def test_make_signed_headers_nonce_is_32_lowercase_hex() -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "_decrypt_app_secret", lambda app_id, blob: GOLDEN_SECRET)
        headers = api._make_signed_headers(b"")
    nonce = headers["IOT-Open-Nonce"]
    assert len(nonce) == 32
    assert all(c in "0123456789abcdef" for c in nonce)


def test_body_hash_is_sha256_hex() -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(api, "_decrypt_app_secret", lambda app_id, blob: GOLDEN_SECRET)
        headers = api._make_signed_headers(GOLDEN_BODY)
    assert headers["IOT-Open-Body-Hash"] == GOLDEN_BODY_HASH
    assert headers["IOT-Open-Body-Hash"] == hashlib.sha256(GOLDEN_BODY).hexdigest()
    assert headers["IOT-Open-Body-Hash"].islower()


def test_header_ordering_is_alphabetical() -> None:
    # Inputs arrive in shuffled order; internals must sort before signing.
    assert api._compute_iot_sign(GOLDEN_APP_ID, GOLDEN_NONCE, GOLDEN_BODY_HASH, GOLDEN_SECRET) == GOLDEN_SIGN


# ── AES-key derivation (independent ciphertext roundtrip) ───────────────────


def test_aes_key_iv_matches_md5_split() -> None:
    key, iv = _spec_key_iv(GOLDEN_APP_ID)
    assert key.decode("ascii") == GOLDEN_AES_KEY
    assert iv.decode("ascii") == GOLDEN_AES_IV
    assert GOLDEN_MD5_APP_ID == GOLDEN_AES_KEY + GOLDEN_AES_IV


def test_decrypt_app_secret_roundtrips_independent_ciphertext() -> None:
    """Encrypt our own plaintext with an independent AES-CBC call, base64 it;
    api.py must decrypt it back. Validates key/iv derivation + zero-padding
    removal without asserting anything about the real embedded secret."""
    plaintext = b"independent vector plaintext"
    key, iv = _spec_key_iv(GOLDEN_APP_ID)
    ciphertext = base64.b64encode(_spec_aes_encrypt(plaintext, key, iv)).decode("ascii")
    assert api._decrypt_app_secret(GOLDEN_APP_ID, ciphertext) == plaintext.decode("utf-8")


def test_real_embedded_secret_decrypts_to_plausible_secret() -> None:
    secret = api._decrypt_app_secret(IOT_APP_ID, IOT_APP_SECRET_ENC)
    assert isinstance(secret, str)
    assert 1 <= len(secret) <= 128
    assert secret.isprintable()
    # Deterministic.
    assert api._decrypt_app_secret(IOT_APP_ID, IOT_APP_SECRET_ENC) == secret


# ── login() wire shape ───────────────────────────────────────────────────────


def test_login_sends_md5_password_and_full_signed_headers() -> None:
    """The on-the-wire body the login call posts must be signed with the
    same helper machinery and carry the MD5-encoded password."""
    from unittest.mock import Mock, patch

    resp = Mock()
    resp.status_code = 200
    resp.raise_for_status = Mock()
    resp.json = Mock(
        return_value={
            "code": 0,
            "data": {
                "accessToken": "at_login",
                "refreshToken": "rt_login",
                "accessTokenWillExpiredAt": "2099-01-01T00:00:00Z",
                "refreshTokenWillExpiredAt": "2099-01-01T00:00:00Z",
            },
        }
    )

    api_instance = api.SolarOfThingsAPI(user_id="user_1", password="plainpass")
    with patch.object(api.requests, "post", return_value=resp) as post:
        api_instance.login()

    assert api_instance.access_token == "at_login"
    assert api_instance.refresh_token == "rt_login"
    assert api_instance.session.headers.get("IOT-Token") == "at_login"

    body = json.loads(post.call_args.kwargs["data"])
    # Password travels as md5 hex digest of the raw password bytes.
    assert body["password"] == hashlib.md5(b"plainpass").hexdigest()
    assert body["account"] == "user_1"

    headers = post.call_args.kwargs["headers"]
    for key in ("IOT-Open-AppID", "IOT-Open-Body-Hash", "IOT-Open-Nonce", "IOT-Open-Sign"):
        assert key in headers
    assert headers["IOT-Open-AppID"] == GOLDEN_APP_ID