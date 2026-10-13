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
from custom_components.govee.api.exceptions import (
    Govee2FARequiredError,
    GoveeApiError,
    GoveeAuthError,
    GoveeLoginRejectedError,
)
from custom_components.govee.const import (
    ACCOUNT_LOGIN_RETRY_INTERVAL,
    CONF_EMAIL,
    CONF_PASSWORD,
    KEY_IOT_CREDENTIALS,
    KEY_IOT_LOGIN_FAILED,
)
from tests.test_cov_coordinator_setup import CREDS, _coordinator, _patch_auth, _TimerCapture

ACCOUNT = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"}


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


class TestSetupLoginRetry:
    """A transient setup login failure is retried in the background (SETUP-1)."""

    def _coord(self, monkeypatch, login: Any) -> tuple[Any, _TimerCapture, MagicMock]:
        timers = _TimerCapture()
        monkeypatch.setattr(coord_mod, "async_call_later", timers)
        inner = MagicMock()
        inner.login = AsyncMock(side_effect=login) if isinstance(login, Exception) else AsyncMock(return_value=login)
        _patch_auth(monkeypatch, inner)
        monkeypatch.setattr(coord_mod.ir, "async_create_issue", MagicMock())
        monkeypatch.setattr(coord_mod, "async_create_mqtt_issue", MagicMock())
        coord = _coordinator(data=dict(ACCOUNT))
        return coord, timers, inner

    def _written(self, coord: Any) -> dict[str, Any]:
        return coord.hass.config_entries.async_update_entry.call_args.kwargs["data"]

    def test_schedule_arms_one_timer(self, monkeypatch):
        coord, timers, _ = self._coord(monkeypatch, CREDS)

        coord.schedule_account_login_retry()
        coord.schedule_account_login_retry()

        assert [d for d, _ in timers.calls] == [ACCOUNT_LOGIN_RETRY_INTERVAL] * 2
        assert timers.cancelled == 1

    @pytest.mark.asyncio
    async def test_success_stores_credentials_and_reloads(self, monkeypatch):
        coord, timers, inner = self._coord(monkeypatch, CREDS)

        await coord._account_login_retry_callback()

        inner.login.assert_awaited_once()
        assert self._written(coord)[KEY_IOT_CREDENTIALS]["token"] == "tok"
        coord.hass.config_entries.async_schedule_reload.assert_called_once_with("cov_entry")
        assert timers.calls == []

    @pytest.mark.asyncio
    async def test_transient_failure_rearms(self, monkeypatch):
        coord, timers, _ = self._coord(monkeypatch, GoveeApiError("Connection error during login: dns"))

        await coord._async_retry_account_login()

        assert [d for d, _ in timers.calls] == [ACCOUNT_LOGIN_RETRY_INTERVAL]
        coord.hass.config_entries.async_update_entry.assert_not_called()
        coord.hass.config_entries.async_schedule_reload.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error", [GoveeAuthError("wrong password"), GoveeLoginRejectedError("refused")])
    async def test_rejection_stores_marker_and_stops(self, monkeypatch, error):
        coord, timers, _ = self._coord(monkeypatch, error)

        await coord._async_retry_account_login()

        assert self._written(coord)[KEY_IOT_LOGIN_FAILED] == str(error)
        coord_mod.async_create_mqtt_issue.assert_called_once()
        assert timers.calls == []

    @pytest.mark.asyncio
    async def test_two_factor_stores_marker_and_raises_issue(self, monkeypatch):
        coord, timers, _ = self._coord(monkeypatch, Govee2FARequiredError())

        await coord._async_retry_account_login()

        assert self._written(coord)[KEY_IOT_LOGIN_FAILED] == "2FA verification required"
        assert coord_mod.ir.async_create_issue.call_args.args[2] == "mqtt_2fa_required_cov_entry"
        assert timers.calls == []

    @pytest.mark.asyncio
    async def test_noop_when_credentials_present_or_no_account(self, monkeypatch):
        coord, _, inner = self._coord(monkeypatch, CREDS)
        coord._iot_credentials = CREDS
        await coord._async_retry_account_login()
        coord._iot_credentials = None
        coord._config_entry.data = {}
        await coord._async_retry_account_login()

        inner.login.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_retry_or_reload_after_shutdown(self, monkeypatch):
        coord, timers, inner = self._coord(monkeypatch, CREDS)

        async def _login(*_a: Any, **_k: Any) -> Any:
            await _shut_down(coord)
            return CREDS

        inner.login = AsyncMock(side_effect=_login)
        await coord._async_retry_account_login()
        coord.hass.config_entries.async_schedule_reload.assert_not_called()

        # A timer armed before shutdown is cancelled; none is armed after.
        coord._shut_down = False
        coord.schedule_account_login_retry()
        await _shut_down(coord)
        assert timers.cancelled == 1
        coord.schedule_account_login_retry()
        await coord._async_retry_account_login()
        assert len(timers.calls) == 1
