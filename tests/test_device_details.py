"""Tests for the per-device "Daily Production" (kWh) sensor.

Covers the additive device/details endpoint source (see const.py comment):
the unit kWh is backed by an arithmetic cross-check from a live capture
(2026-09-18, device 517915003814383616):

    totalProducedQuantity (99.468) = totalGeneratedEnergy (97.939)
                                   + dailyProducedQuantity (1.529)

The value is merged into the device coordinator's time_series dict under the
``daily_production`` key so the existing per-device sensor loop picks it up
without touching the sensor platform.  A device/details failure must degrade
quietly — the coordinator must still return its other data.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.solar_of_things.api import SolarOfThingsAPI, TokenExpiredError
from custom_components.solar_of_things.const import (
    API_DEVICE_DETAILS,
    SENSOR_DEFINITIONS,
)

DEVICE_ID = "517915003814383616"


# ─── fetch_device_details (API method) ────────────────────────────────────────

def test_fetch_device_details_parses_daily_production() -> None:
    """Raw data object returned, carrying dailyProducedQuantity."""
    api = SolarOfThingsAPI(iot_token="test-token")
    api._ensure_token_valid = lambda: None  # no network

    api._get = lambda path, params, **kwargs: {
        "code": 0,
        "data": {
            "dailyProducedQuantity": 1.529,
            "totalProducedQuantity": 99.468,
            "summaryProperty": {"totalGeneratedEnergy": 97.939},
        },
    }

    result = api.fetch_device_details(DEVICE_ID)

    assert result["dailyProducedQuantity"] == 1.529
    assert result["totalProducedQuantity"] == 99.468
    # The cross-check that pins the kWh unit.
    assert result["totalProducedQuantity"] == pytest.approx(
        result["summaryProperty"]["totalGeneratedEnergy"]
        + result["dailyProducedQuantity"]
    )


def test_fetch_device_details_uses_get_endpoint() -> None:
    """Calls _get with the device/details path and deviceId param."""
    api = SolarOfThingsAPI(iot_token="test-token")
    api._ensure_token_valid = lambda: None  # no network
    seen = {}

    def fake_get(path, params, **kwargs):
        seen["path"] = path
        seen["params"] = params
        return {"code": 0, "data": {}}

    api._get = fake_get
    api.fetch_device_details(DEVICE_ID)

    assert seen["path"] == API_DEVICE_DETAILS
    assert seen["params"] == {"deviceId": DEVICE_ID}


def test_fetch_device_details_error_code_raises_runtime_error() -> None:
    """A non-zero code raises RuntimeError; callers degrade around it."""
    api = SolarOfThingsAPI(iot_token="test-token")
    api._ensure_token_valid = lambda: None  # no network
    api._get = lambda path, params, **kwargs: {"code": 1, "message": "boom"}
    with pytest.raises(RuntimeError):
        api.fetch_device_details(DEVICE_ID)


def test_fetch_device_details_empty_data_returns_empty_dict() -> None:
    """No data field -> empty dict, never None, so the merge stays safe."""
    api = SolarOfThingsAPI(iot_token="test-token")
    api._ensure_token_valid = lambda: None  # no network
    api._get = lambda path, params, **kwargs: {"code": 0}
    assert api.fetch_device_details(DEVICE_ID) == {}


def test_daily_production_definition_is_energy_kwh() -> None:
    """Sensor definition: kWh, energy device class (TOTAL_INCREASING exists)."""
    definition = SENSOR_DEFINITIONS["daily_production"]
    assert definition["unit"] == "kWh"
    assert definition["device_class"] == "energy"


# ─── Coordinator merge (_async_update_data) ───────────────────────────────────

def _build_coordinator(api):
    """Bare coordinator instance; only the members _async_update_data needs."""
    from custom_components.solar_of_things import SolarOfThingsDeviceCoordinator

    entry = AsyncMock()
    entry.async_start_reauth = AsyncMock()

    coord = SolarOfThingsDeviceCoordinator.__new__(SolarOfThingsDeviceCoordinator)
    coord.api = api
    coord.device_id = DEVICE_ID
    coord.device_meta = {"name": "Test Inverter", "model": "X"}
    coord.station_id = "123456789012345678"
    coord._entry = entry
    coord.hass = SimpleNamespace(
        async_add_executor_job=lambda fn, *a: asyncio.to_thread(fn, *a)
    )
    return coord


async def test_coordinator_merges_daily_production_into_time_series() -> None:
    """details.dailyProducedQuantity lands under time_series['daily_production']."""
    api = SolarOfThingsAPI(iot_token="test-token")
    api._ensure_token_valid = lambda: None  # no network
    api.fetch_latest_data = lambda device_id: {"pvInputPower": 1000}
    api.fetch_settings = lambda device_id: {}
    api.fetch_device_details = lambda device_id: {"dailyProducedQuantity": 1.529}

    result = await _build_coordinator(api)._async_update_data()

    assert result["time_series"]["daily_production"] == 1.529
    # Other data still present, shape unchanged otherwise.
    assert result["settings"] == {}
    assert result["device"] == DEVICE_ID
    assert result["device_meta"]["name"] == "Test Inverter"


async def test_coordinator_tolerates_detail_failure() -> None:
    """A failing device/details must not fail the whole coordinator update."""
    api = SolarOfThingsAPI(iot_token="test-token")
    api._ensure_token_valid = lambda: None  # no network
    api.fetch_latest_data = lambda device_id: {"pvInputPower": 1000}
    api.fetch_settings = lambda device_id: {}

    def boom(device_id):
        raise RuntimeError("details down")

    api.fetch_device_details = boom

    result = await _build_coordinator(api)._async_update_data()

    assert result["time_series"]["pvInputPower"] == 1000
    assert "daily_production" not in result["time_series"]
    assert result["device"] == DEVICE_ID


async def test_coordinator_token_expiry_from_details_still_triggers_reauth() -> None:
    """TokenExpiredError from device/details must reach the outer handler,
    which starts re-auth and surfaces UpdateFailed — never silently swallowed
    by the additive detail-failure guard.
    """
    api = SolarOfThingsAPI(iot_token="test-token")
    api._ensure_token_valid = lambda: None  # no network
    api.fetch_latest_data = lambda device_id: {"pvInputPower": 1000}
    api.fetch_settings = lambda device_id: {}

    def expired(device_id):
        raise TokenExpiredError("expired")

    api.fetch_device_details = expired

    coord = _build_coordinator(api)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
    coord._entry.async_start_reauth.assert_called_once()