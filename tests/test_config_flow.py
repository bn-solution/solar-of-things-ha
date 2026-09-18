"""Test the Solar of Things config flow.

Walks the REAL flow: the first user step asks for an auth-mode selection
("password" or "token"), and only after that are the per-mode credential
fields submitted.  Earlier versions of this file posted token fields straight
into the SOURCE_USER step, which the real schema (auth_mode selector only)
rejects with a VOL error — this rewrite matches the actual step sequence in
config_flow.py.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solar_of_things.api import AuthenticationError
from custom_components.solar_of_things.const import (
    CONF_ACCESS_TOKEN_EXPIRES,
    CONF_DEVICE_ID,
    CONF_IOT_TOKEN,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_EXPIRES,
    CONF_STATION_ID,
    CONF_TIME_ZONE,
    CONF_USER_ID,
    DOMAIN,
)

pytestmark = pytest.mark.asyncio

STATION_ID = "486217907720650752"
DEVICE_ID = "486217907745816576"


# ─── Step 1: auth-mode selection ─────────────────────────────────────────────

async def test_user_step_offers_auth_mode_selection(hass: HomeAssistant) -> None:
    """The first user step must ask for an auth mode, not for credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None
    assert "auth_mode" in result["data_schema"].schema


async def test_user_step_defaults_to_password_when_auth_mode_omitted(
    hass: HomeAssistant,
) -> None:
    """Credential fields posted straight into the auth-mode step are dropped.

    The real schema is only an auth_mode selector; voluptuous ignores
    extraneous keys (ALLOW_EXTRA) and the flow defaults the mode to
    "password", so posting token fields early is a no-op, not an error.
    This pins that contract: step 1 never consumes credentials.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"iot_token": "test_token", "station_id": STATION_ID},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "password"


# ─── Step 2a: user-id + password ─────────────────────────────────────────────

async def test_password_flow_creates_entry(hass: HomeAssistant) -> None:
    """Full password-mode walk: auth-mode select → credentials → CREATE_ENTRY."""
    with (
        patch("custom_components.solar_of_things.api.SolarOfThingsAPI.login"),
        patch(
            "custom_components.solar_of_things.api.SolarOfThingsAPI.test_connection",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"auth_mode": "password"}
        )

        assert result["step_id"] == "password"
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USER_ID: "myaccount",
                CONF_PASSWORD: "hunter2",
                CONF_STATION_ID: STATION_ID,
                CONF_DEVICE_ID: DEVICE_ID,
                CONF_TIME_ZONE: "Asia/Manila",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Solar Station {STATION_ID}"
    data = result["data"]
    assert data[CONF_USER_ID] == "myaccount"
    assert data[CONF_PASSWORD] == "hunter2"
    assert data[CONF_STATION_ID] == STATION_ID
    assert data[CONF_DEVICE_ID] == DEVICE_ID
    assert data[CONF_TIME_ZONE] == "Asia/Manila"
    # Token field contract: every persisted key must be present (values are
    # populated by the real login; here login is mocked so they are empty).
    assert set(data) >= {
        CONF_IOT_TOKEN,
        CONF_REFRESH_TOKEN,
        CONF_ACCESS_TOKEN_EXPIRES,
        CONF_REFRESH_TOKEN_EXPIRES,
    }


async def test_password_flow_rejects_bad_credentials(hass: HomeAssistant) -> None:
    """AuthenticationError must surface as invalid_auth on the password step."""
    with patch(
        "custom_components.solar_of_things.api.SolarOfThingsAPI.login",
        side_effect=AuthenticationError("Login failed: bad credentials"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"auth_mode": "password"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USER_ID: "myaccount",
                CONF_PASSWORD: "wrong",
                CONF_STATION_ID: STATION_ID,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "password"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_password_flow_handles_unreachable_station(hass: HomeAssistant) -> None:
    """Login succeeding but the station being unreachable → cannot_connect."""
    with (
        patch("custom_components.solar_of_things.api.SolarOfThingsAPI.login"),
        patch(
            "custom_components.solar_of_things.api.SolarOfThingsAPI.test_connection",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"auth_mode": "password"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USER_ID: "myaccount",
                CONF_PASSWORD: "hunter2",
                CONF_STATION_ID: STATION_ID,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "password"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_password_flow_rejects_non_iana_timezone(hass: HomeAssistant) -> None:
    """Free-text time zone must be validated before the credentials hit the API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"auth_mode": "password"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USER_ID: "myaccount",
            CONF_PASSWORD: "hunter2",
            CONF_STATION_ID: STATION_ID,
            CONF_TIME_ZONE: "GMT+2",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_time_zone"}


# ─── Step 2b: legacy IOT token ──────────────────────────────────────────────

async def test_token_flow_creates_entry_with_device_id(hass: HomeAssistant) -> None:
    """Token-mode walk: auth-mode select → token fields → CREATE_ENTRY.

    With a device ID the flow validates by fetching live data for that device.
    """
    with patch(
        "custom_components.solar_of_things.api.SolarOfThingsAPI.fetch_latest_data",
        return_value={"batterySOC": 75},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"auth_mode": "token"}
        )

        assert result["step_id"] == "token"
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IOT_TOKEN: "test_token",
                CONF_STATION_ID: STATION_ID,
                CONF_DEVICE_ID: DEVICE_ID,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Solar Station {STATION_ID}"
    assert result["data"][CONF_IOT_TOKEN] == "test_token"
    assert result["data"][CONF_DEVICE_ID] == DEVICE_ID


async def test_token_flow_validates_via_connection_test(hass: HomeAssistant) -> None:
    """Without a device ID the token flow falls back to test_connection()."""
    with patch(
        "custom_components.solar_of_things.api.SolarOfThingsAPI.test_connection",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"auth_mode": "token"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IOT_TOKEN: "test_token",
                CONF_STATION_ID: STATION_ID,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_IOT_TOKEN] == "test_token"
    assert CONF_DEVICE_ID not in result["data"]


async def test_token_flow_cannot_connect(hass: HomeAssistant) -> None:
    """A token the portal rejects must surface as cannot_connect."""
    with patch(
        "custom_components.solar_of_things.api.SolarOfThingsAPI.fetch_latest_data",
        side_effect=RuntimeError("401 Unauthorized"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"auth_mode": "token"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IOT_TOKEN: "bad_token",
                CONF_STATION_ID: STATION_ID,
                CONF_DEVICE_ID: DEVICE_ID,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "token"
    assert result["errors"] == {"base": "cannot_connect"}


# ─── Re-auth ─────────────────────────────────────────────────────────────────

async def test_reauth_password_updates_entry(hass: HomeAssistant) -> None:
    """Re-auth for a credential-based entry asks for a new password and
    persists the freshly-logged-in token state on the existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"station_{STATION_ID}",
        data={
            CONF_USER_ID: "myaccount",
            CONF_PASSWORD: "old-password",
            CONF_STATION_ID: STATION_ID,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_TIME_ZONE: "Asia/Manila",
        },
        entry_id="reauth_entry_id",
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.solar_of_things.api.SolarOfThingsAPI.login"),
        patch(
            "custom_components.solar_of_things.api.SolarOfThingsAPI.test_connection",
            return_value=True,
        ),
        patch.object(hass.config_entries, "async_reload", new=AsyncMock()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
        )

        assert result["step_id"] == "reauth_confirm"
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        # Credential-based entry: only the password is asked for.
        assert "password" in result["data_schema"].schema

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "fresh-password"}
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert hass.config_entries.async_get_entry(entry.entry_id).data[CONF_PASSWORD] == "fresh-password"


async def test_reauth_token_updates_entry(hass: HomeAssistant) -> None:
    """Re-auth for a legacy-token entry asks for a fresh IOT token and stores it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"station_{STATION_ID}",
        data={
            CONF_IOT_TOKEN: "expired_token",
            CONF_STATION_ID: STATION_ID,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_TIME_ZONE: "Asia/Manila",
        },
        entry_id="reauth_token_entry_id",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.solar_of_things.api.SolarOfThingsAPI.fetch_latest_data",
            return_value={"batterySOC": 50},
        ),
        patch.object(hass.config_entries, "async_reload", new=AsyncMock()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
        )

        assert result["step_id"] == "reauth_confirm"
        assert "iot_token" in result["data_schema"].schema

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IOT_TOKEN: "fresh_token"}
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert (
        hass.config_entries.async_get_entry(entry.entry_id).data[CONF_IOT_TOKEN]
        == "fresh_token"
    )