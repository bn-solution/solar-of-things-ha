"""Test configuration for Solar of Things integration."""
import sys
import os

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant import loader as _loader
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solar_of_things.const import DOMAIN


if sys.platform == "win32":
    # pytest-ha's pytest_runtest_setup() calls
    # pytest_socket.disable_socket(allow_unix_socket=True), which replaces
    # socket.socket with a GuardedSocket that raises on EVERY socket creation
    # (host allow-listing only guards connect(), not creation). On Linux the
    # asyncio event loop needs no socket, so the guard is harmless there. On
    # Windows, HA's HassEventLoopPolicy builds a ProactorEventLoop, and that
    # loop requires an AF_INET self-pipe (socket.socketpair()), so every test
    # setup died with pytest_socket.SocketBlockedError before running.
    #
    # Phase 0 fix (baseline only, no production change): on win32 replace the
    # creation-blocking guard with a connect-level guard restricted to
    # 127.0.0.1 (which pytest-ha itself already allow-lists for asyncio).
    # Event-loop machinery may create sockets, but any real connection to
    # solar.siseli.com (or anywhere else) still raises loudly.
    import socket as _socket  # noqa: PLC0415
    import pytest_socket as _pytest_socket  # noqa: PLC0415

    _real_socket = _socket.socket

    def _win32_disable_socket(allow_unix_socket: bool = False) -> None:
        """Windows variant of pytest_socket.disable_socket().

        Keeps socket creation working (ProactorEventLoop self-pipe) while
        still blocking every non-loopback connect().
        """
        _pytest_socket.enable_socket()
        _pytest_socket.socket_allow_hosts(["127.0.0.1"])

    _pytest_socket.disable_socket = _win32_disable_socket


def pytest_configure(config) -> None:
    """Make pytest-asyncio behave the way pytest-ha expects.

    pytest-homeassistant-custom-component ships its own test template with
    ``asyncio_mode = auto`` in pytest.ini. Without that ini key pytest-asyncio
    stays in strict mode, leaves async fixtures such as the plugin's ``_hass``
    as raw async generators, and every test receiving ``hass`` dies with
    "'async_generator' object has no attribute 'config_entries'".
    """
    config.option.asyncio_mode = "auto"


@pytest.fixture(autouse=True)
def _mount_custom_components(hass: HomeAssistant) -> None:
    """Point HA's integration loader at this repository's custom_components.

    pytest-ha's async_test_home_assistant() sets hass.config.config_dir to a
    bundled ``testing_config`` folder that is not shipped in the installed
    wheel, so ``loader.async_get_integration`` can never find
    ``solar_of_things`` and every flow/entry test dies with
    ``UnknownHandler: Cannot find integration solar_of_things``.

    Re-point config_dir at the repo root (where custom_components/ lives) and
    drop the loader cache so the scan reruns. Test-only, no production code
    is touched.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hass.config.config_dir = repo_root
    hass.data.pop(_loader.DATA_CUSTOM_COMPONENTS, None)
    yield


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "iot_token": "test_token_123",
            "station_id": "123456789012345678",
            "device_id": "876543210987654321",
        },
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_api_response():
    """Return mock API response data."""
    return {
        "data": {
            "pvInputPower": [{"ts": 1234567890, "value": 2500}],
            "acOutputActivePower": [{"ts": 1234567890, "value": 1800}],
            "batteryDischargeCurrent": [{"ts": 1234567890, "value": 0}],
            "batteryChargingCurrent": [{"ts": 1234567890, "value": 10}],
            "batteryVoltage": [{"ts": 1234567890, "value": 48}],
            "feedInPower": [{"ts": 1234567890, "value": 500}],
            "batterySOC": [{"ts": 1234567890, "value": 75}],
        }
    }