"""Regression tests for account-login, MQTT and BFF robustness fixes.

Covers timers re-arming on a shut-down coordinator, the water-detector poll's
token recovery, defensive BFF parsing, HTTP 401 mapping, the OpenAPI events
SUBACK/backoff handling, topic redaction in MQTT debug logs, and login error
parsing. Every network client is an in-process fake.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import custom_components.govee.coordinator as coord_mod
from tests.test_cov_coordinator_setup import CREDS, _coordinator, _TimerCapture


async def _shut_down(coord: Any) -> None:
    coord._api_client = MagicMock()
    coord._api_client.close = AsyncMock()
    await coord.async_shutdown()


class TestTimersStayDeadAfterShutdown:
    """A timer callback that resumes after unload must not re-arm (COORD-1)."""

    @pytest.mark.asyncio
    async def test_bff_poll_callback_does_not_rearm_after_shutdown(self, monkeypatch):
        timers = _TimerCapture()
        monkeypatch.setattr(coord_mod, "async_call_later", timers)
        coord = _coordinator(iot=CREDS)

        # The unload lands while the callback awaits its HTTP call.
        async def _poll() -> None:
            await _shut_down(coord)

        coord._poll_bff_leak_state = _poll
        coord._refresh_bff_thermometers = AsyncMock()

        await coord._bff_poll_callback()

        assert timers.calls == []

    @pytest.mark.asyncio
    async def test_water_detector_callback_does_not_rearm_after_shutdown(self, monkeypatch):
        timers = _TimerCapture()
        monkeypatch.setattr(coord_mod, "async_call_later", timers)
        coord = _coordinator(iot=CREDS)

        async def _poll() -> None:
            await _shut_down(coord)

        coord._poll_water_detectors = _poll
        await coord._water_detector_poll_callback()

        assert timers.calls == []

    @pytest.mark.asyncio
    async def test_probe_callback_does_not_rearm_after_shutdown(self, monkeypatch):
        timers = _TimerCapture()
        monkeypatch.setattr(coord_mod, "async_call_later", timers)
        coord = _coordinator(iot=CREDS)
        coord._probe_polling_enabled = {"dev"}

        async def _poll() -> None:
            await _shut_down(coord)
            coord._probe_polling_enabled = {"dev"}

        coord._poll_probe_thermometers = _poll
        await coord._probe_poll_callback()

        assert timers.calls == []

    @pytest.mark.asyncio
    async def test_status_callback_does_not_rearm_after_shutdown(self, monkeypatch):
        timers = _TimerCapture()
        monkeypatch.setattr(coord_mod, "async_call_later", timers)
        coord = _coordinator(iot=CREDS)

        async def _poll() -> None:
            await _shut_down(coord)

        coord._poll_mqtt_status = _poll
        await coord._status_poll_callback()

        assert timers.calls == []

    @pytest.mark.asyncio
    async def test_start_mqtt_is_a_noop_after_shutdown(self, monkeypatch):
        coord = _coordinator(iot=CREDS)
        await _shut_down(coord)
        built = MagicMock()
        monkeypatch.setattr(coord_mod, "GoveeAwsIotClient", built)

        await coord._start_mqtt()

        built.assert_not_called()
        assert coord._mqtt_client is None

    def test_schedulers_still_arm_while_running(self, monkeypatch):
        timers = _TimerCapture()
        monkeypatch.setattr(coord_mod, "async_call_later", timers)
        coord = _coordinator(iot=CREDS)
        coord._schedule_bff_poll()
        coord._schedule_water_detector_poll()
        coord._schedule_probe_poll()
        coord._schedule_status_poll()

        assert len(timers.calls) == 4
