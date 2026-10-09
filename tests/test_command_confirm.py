"""Confirm-and-resend for cloud and MQTT commands.

Govee's cloud can answer a control call with HTTP 200 and never deliver it, and
an MQTT publish is never acknowledged at all, so a dropped command used to mean
pressing the button again. These tests cover the pure matching rules in
``command_confirm`` and the coordinator flow around them: wait for the device's
own status frame, ask for one with a status query, resend once on a
contradiction, fall back to a cloud read only when no frame spoke, never spend
past the request budget, and never resend a command a newer one replaced.

The coordinator is a real one over a mocked hass/entry whose background tasks
run on the test loop; the MQTT client, the REST client and the device's answers
are fakes. Windows are shrunk to fractions of a second.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import custom_components.govee.coordinator as coord_mod
from custom_components.govee.api.exceptions import GoveeApiError
from custom_components.govee.command_confirm import (
    BRIGHTNESS_CONFIRM_TOLERANCE,
    COLOR_TEMP_CONFIRM_TOLERANCE,
    cloud_request_affordable,
    confirm_field,
    confirms_conflict,
    frame_confirms,
    state_confirms,
)
from custom_components.govee.const import (
    CONF_COMMAND_CONFIRM,
    CONF_COMMAND_CONFIRM_RESENDS,
    CONF_COMMAND_CONFIRM_WINDOW,
    CONF_MQTT_STATUS_INTERVAL,
    DEFAULT_COMMAND_CONFIRM_RESENDS,
    DEFAULT_COMMAND_CONFIRM_WINDOW,
)
from custom_components.govee.coordinator import GoveeCoordinator
from custom_components.govee.models import (
    BrightnessCommand,
    ColorCommand,
    ColorTempCommand,
    GoveeCapability,
    GoveeDevice,
    GoveeDeviceState,
    PowerCommand,
    RGBColor,
    SceneCommand,
    SegmentColorCommand,
)
from custom_components.govee.models.device import (
    CAPABILITY_COLOR_SETTING,
    CAPABILITY_ON_OFF,
    CAPABILITY_RANGE,
    INSTANCE_BRIGHTNESS,
    INSTANCE_COLOR_RGB,
    INSTANCE_COLOR_TEMP,
    INSTANCE_POWER,
)
from custom_components.govee.sensor import GoveeRateLimitSensor

DEV = "AA:BB:CC:DD:EE:FF:00:11"
TOPIC = "GD/device-topic"

_POWER = GoveeCapability(type=CAPABILITY_ON_OFF, instance=INSTANCE_POWER, parameters={})
_BRIGHTNESS = GoveeCapability(
    type=CAPABILITY_RANGE, instance=INSTANCE_BRIGHTNESS, parameters={"range": {"min": 0, "max": 100}}
)
_RGB = GoveeCapability(type=CAPABILITY_COLOR_SETTING, instance=INSTANCE_COLOR_RGB, parameters={})
_CT = GoveeCapability(
    type=CAPABILITY_COLOR_SETTING, instance=INSTANCE_COLOR_TEMP, parameters={"range": {"min": 2000, "max": 9000}}
)

RED = RGBColor(r=255, g=0, b=0)
BLUE = RGBColor(r=0, g=0, b=255)


# --------------------------------------------------------------------------- #
# Pure rules
# --------------------------------------------------------------------------- #


class TestConfirmField:
    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            (PowerCommand(power_on=True), "power"),
            (BrightnessCommand(brightness=40), "brightness"),
            (ColorCommand(color=RED), "color"),
            (ColorTempCommand(kelvin=3000), "color_temp"),
        ],
    )
    def test_the_four_status_fields_are_confirmable(self, command, expected):
        assert confirm_field(command, "H6072") == expected

    @pytest.mark.parametrize(
        "command",
        [
            SceneCommand(scene_id=1, scene_name="Sunset"),
            SegmentColorCommand(segment_indices=(0,), color=RED),
            BrightnessCommand(brightness=0),
        ],
    )
    def test_nothing_else_is(self, command):
        assert confirm_field(command, "H6072") is None

    @pytest.mark.parametrize("sku", ["H5080", "h5083"])
    def test_power_on_the_17_16_plugs_cannot_be_read_back(self, sku):
        """Those plugs report onOff as 17/16, so a frame cannot tell on from off."""
        assert confirm_field(PowerCommand(power_on=False), sku) is None
        assert confirm_field(BrightnessCommand(brightness=50), sku) == "brightness"


class TestConfirmsConflict:
    def test_same_field_replaces(self):
        assert confirms_conflict("brightness", "brightness") is True

    def test_brightness_and_colour_from_one_turn_on_both_survive(self):
        assert confirms_conflict("color", "brightness") is False
        assert confirms_conflict("brightness", "color") is False

    @pytest.mark.parametrize("pending", ["power", "brightness", "color", "color_temp"])
    def test_power_and_unconfirmable_commands_cancel_everything(self, pending):
        assert confirms_conflict("power", pending) is True
        assert confirms_conflict(None, pending) is True

    @pytest.mark.parametrize("new", ["brightness", "color", "color_temp"])
    def test_any_newer_command_cancels_a_pending_power_confirm(self, new):
        """Resending "off" after a newer brightness would switch the light off again."""
        assert confirms_conflict(new, "power") is True

    def test_colour_and_colour_temperature_replace_each_other(self):
        assert confirms_conflict("color", "color_temp") is True
        assert confirms_conflict("color_temp", "color") is True


class TestFrameConfirms:
    def test_power(self):
        on = PowerCommand(power_on=True)
        assert frame_confirms(on, {"onOff": 1}) is True
        assert frame_confirms(on, {"onOff": 0}) is False
        assert frame_confirms(PowerCommand(power_on=False), {"onOff": 0}) is True

    def test_a_frame_that_does_not_mention_the_field_is_no_evidence(self):
        assert frame_confirms(PowerCommand(power_on=True), {"brightness": 50}) is None
        assert frame_confirms(BrightnessCommand(brightness=50), {"onOff": 1}) is None
        assert frame_confirms(ColorCommand(color=RED), {"onOff": 1}) is None
        assert frame_confirms(ColorTempCommand(kelvin=3000), {"onOff": 1}) is None

    @pytest.mark.parametrize("value", [None, "", "on", True])
    def test_unreadable_values_are_no_evidence(self, value):
        assert frame_confirms(PowerCommand(power_on=True), {"onOff": value}) is None
        assert frame_confirms(BrightnessCommand(brightness=50), {"brightness": value}) is None

    def test_brightness_within_tolerance(self):
        command = BrightnessCommand(brightness=50)
        assert frame_confirms(command, {"brightness": 50 + BRIGHTNESS_CONFIRM_TOLERANCE}) is True
        assert frame_confirms(command, {"brightness": 50 + BRIGHTNESS_CONFIRM_TOLERANCE + 1}) is False

    def test_wide_range_brightness_accepts_either_scale(self):
        """A 0-254 device's frame may carry 1-100 or native; both mean "landed"."""
        command = BrightnessCommand(brightness=127)
        assert frame_confirms(command, {"brightness": 50}, (0, 254)) is True
        assert frame_confirms(command, {"brightness": 127}, (0, 254)) is True
        assert frame_confirms(command, {"brightness": 90}, (0, 254)) is False

    def test_colour_dict_and_packed_forms(self):
        command = ColorCommand(color=RGBColor(r=200, g=100, b=50))
        assert frame_confirms(command, {"color": {"r": 200, "g": 100, "b": 50}}) is True
        assert frame_confirms(command, {"color": {"r": 201, "g": 99, "b": 52}}) is True
        assert frame_confirms(command, {"color": (200 << 16) | (100 << 8) | 50}) is True
        assert frame_confirms(command, {"color": {"r": 0, "g": 0, "b": 255}}) is False

    @pytest.mark.parametrize("value", ["red", None, [1, 2, 3], {"r": "x"}])
    def test_unreadable_colour_is_no_evidence(self, value):
        assert frame_confirms(ColorCommand(color=RED), {"color": value}) is None

    def test_colour_temperature_within_the_firmware_grid(self):
        command = ColorTempCommand(kelvin=3000)
        assert frame_confirms(command, {"colorTemInKelvin": 3000 + COLOR_TEMP_CONFIRM_TOLERANCE}) is True
        assert frame_confirms(command, {"colorTemInKelvin": 6500}) is False
        # A colour write reports colorTemInKelvin 0: the temperature did not land.
        assert frame_confirms(command, {"colorTemInKelvin": 0}) is False

    def test_unconfirmable_command_is_never_judged(self):
        assert frame_confirms(SceneCommand(scene_id=1), {"onOff": 1}) is None
        assert frame_confirms(PowerCommand(power_on=True), {"onOff": 17}, sku="H5080") is None


class TestStateConfirms:
    def _state(self, **values: Any) -> GoveeDeviceState:
        state = GoveeDeviceState.create_empty(DEV)
        for key, value in values.items():
            setattr(state, key, value)
        return state

    def test_each_field(self):
        assert state_confirms(PowerCommand(power_on=True), self._state(power_state=True)) is True
        assert state_confirms(PowerCommand(power_on=True), self._state(power_state=False)) is False
        assert state_confirms(BrightnessCommand(brightness=40), self._state(brightness=41)) is True
        assert state_confirms(BrightnessCommand(brightness=40), self._state(brightness=80)) is False
        assert state_confirms(ColorCommand(color=RED), self._state(color=RED)) is True
        assert state_confirms(ColorCommand(color=RED), self._state(color=BLUE)) is False
        assert state_confirms(ColorTempCommand(kelvin=4000), self._state(color_temp_kelvin=4100)) is True
        assert state_confirms(ColorTempCommand(kelvin=4000), self._state(color_temp_kelvin=2700)) is False

    def test_missing_values_and_unconfirmable_commands_are_no_evidence(self):
        assert state_confirms(ColorCommand(color=RED), self._state(color=None)) is None
        assert state_confirms(ColorTempCommand(kelvin=4000), self._state(color_temp_kelvin=None)) is None
        assert state_confirms(SceneCommand(scene_id=3), self._state()) is None


class TestCloudRequestAffordable:
    def _ok(self, **overrides: Any) -> bool:
        values: dict[str, Any] = {
            "requests_today": 100,
            "daily_budget": 9000,
            "rate_limit_remaining": 80,
            "rate_limit_reserve": 20,
            "rate_limited": False,
        }
        values.update(overrides)
        return cloud_request_affordable(**values)

    def test_room_in_both_limits(self):
        assert self._ok() is True

    def test_never_past_the_daily_budget(self):
        assert self._ok(requests_today=8999) is True
        assert self._ok(requests_today=9000) is False
        assert self._ok(requests_today=12000) is False

    def test_keeps_the_per_minute_reserve_free(self):
        assert self._ok(rate_limit_remaining=21) is True
        assert self._ok(rate_limit_remaining=20) is False
        assert self._ok(rate_limit_remaining=0) is False

    def test_nothing_while_backing_off_a_429(self):
        assert self._ok(rate_limited=True) is False

    @pytest.mark.parametrize(
        "overrides",
        [{"requests_today": None}, {"daily_budget": "9000"}, {"rate_limit_remaining": MagicMock()}],
    )
    def test_unusable_counters_refuse_rather_than_guess(self, overrides):
        assert self._ok(**overrides) is False


# --------------------------------------------------------------------------- #
# Coordinator flow
# --------------------------------------------------------------------------- #


def _coordinator(options: dict[str, Any] | None = None) -> GoveeCoordinator:
    """A real coordinator whose background tasks run on the test loop."""
    entry = MagicMock()
    entry.entry_id = "confirm_entry"
    entry.title = "Govee"
    entry.options = options if options is not None else {}
    entry.data = {}

    def _create_task(hass: Any, coro: Any, name: str | None = None) -> asyncio.Task[Any]:
        return asyncio.get_running_loop().create_task(coro, name=name)

    entry.async_create_background_task = _create_task
    coord = GoveeCoordinator(
        hass=MagicMock(),
        config_entry=entry,
        api_client=MagicMock(),
        iot_credentials=None,
        poll_interval=60,
    )
    coord._api_client.control_device = AsyncMock(return_value=True)
    coord._api_client.get_device_state = AsyncMock()
    coord._api_client.rate_limit_remaining = 100
    coord._api_client.requests_today = 10
    coord.async_set_updated_data = MagicMock()
    coord.async_update_listeners = MagicMock()
    return coord


def _device(*, sku: str = "H6072", is_group: bool = False) -> GoveeDevice:
    return GoveeDevice(
        device_id=DEV,
        sku=sku,
        name="Test light",
        device_type="devices.types.light",
        capabilities=(_POWER, _BRIGHTNESS, _RGB, _CT),
        is_group=is_group,
    )


class _Device:
    """Answers status queries with whatever it is currently showing."""

    def __init__(self, coord: GoveeCoordinator) -> None:
        self.coord = coord
        self.showing: dict[str, Any] | None = None
        self.queries = 0

    async def answer_query(self, topic: str | None) -> bool:
        self.queries += 1
        assert topic == TOPIC
        if self.showing is not None:
            frame = dict(self.showing)
            asyncio.get_running_loop().call_soon(self.coord._on_mqtt_state_update, DEV, frame)
        return True


@pytest.fixture
def fast_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(coord_mod, "COMMAND_CONFIRM_QUERY_DELAY", 0.02)
    monkeypatch.setattr(coord_mod, "MQTT_STATUS_QUERY_SPACING", 0.01)


def _ready(
    *, options: dict[str, Any] | None = None, device: GoveeDevice | None = None, window: float = 0.15
) -> tuple[GoveeCoordinator, _Device]:
    """A coordinator with one light that has answered over MQTT this session."""
    coord = _coordinator(options)
    if coord._confirm_window is not None:
        coord._confirm_window = window
    device = device or _device()
    coord._devices[DEV] = device
    coord._states[DEV] = GoveeDeviceState.create_empty(DEV)
    coord._ensure_transport_health(DEV)
    coord._record_transport_success(DEV, "mqtt")  # heard from over AWS IoT
    coord._device_topics[DEV] = TOPIC
    fake = _Device(coord)
    client = MagicMock()
    client.connected = True
    client.async_publish_command = AsyncMock(return_value=True)
    client.async_publish_status_query = AsyncMock(side_effect=fake.answer_query)
    coord._mqtt_client = client
    return coord, fake


async def _settle(coord: GoveeCoordinator) -> None:
    """Wait for every confirm in flight to finish."""
    tasks = [p.task for by_field in coord._pending_confirms.values() for p in by_field.values() if p.task]
    if tasks:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5)


def _sent(coord: GoveeCoordinator) -> list[Any]:
    return [call.args[2] for call in coord._api_client.control_device.await_args_list]


class TestOptions:
    def test_on_by_default_with_the_documented_window_and_resends(self):
        coord = _coordinator({})
        assert coord._confirm_window == float(DEFAULT_COMMAND_CONFIRM_WINDOW)
        assert coord._confirm_resends == DEFAULT_COMMAND_CONFIRM_RESENDS
        assert coord.command_confirm_stats["enabled"] is True

    def test_configured_values(self):
        coord = _coordinator({CONF_COMMAND_CONFIRM_WINDOW: 10, CONF_COMMAND_CONFIRM_RESENDS: 0})
        assert coord._confirm_window == 10.0
        assert coord._confirm_resends == 0

    @pytest.mark.parametrize("value", [1, 31, "soon", None])
    def test_bad_window_falls_back_to_the_default(self, value):
        assert _coordinator({CONF_COMMAND_CONFIRM_WINDOW: value})._confirm_window == float(
            DEFAULT_COMMAND_CONFIRM_WINDOW
        )

    @pytest.mark.parametrize("value", [-1, 4, "twice"])
    def test_bad_resend_count_falls_back_to_the_default(self, value):
        assert _coordinator({CONF_COMMAND_CONFIRM_RESENDS: value})._confirm_resends == DEFAULT_COMMAND_CONFIRM_RESENDS

    def test_turned_off(self):
        coord = _coordinator({CONF_COMMAND_CONFIRM: False})
        assert coord._confirm_window is None
        assert coord.command_confirm_stats["enabled"] is False

    def test_hand_built_coordinators_keep_the_old_path(self):
        coord = object.__new__(GoveeCoordinator)
        assert coord._confirm_window is None
        assert coord.command_confirm_stats["enabled"] is False
        assert coord.command_resends == 0


@pytest.mark.usefixtures("fast_windows")
class TestConfirmAfterCloudCommand:
    @pytest.mark.asyncio
    async def test_a_status_frame_showing_the_new_value_confirms_without_a_resend(self):
        coord, device = _ready()
        device.showing = {"onOff": 1, "brightness": 40}

        assert await coord.async_control_device(DEV, BrightnessCommand(brightness=40)) is True
        await _settle(coord)

        assert _sent(coord) == [BrightnessCommand(brightness=40)]
        assert device.queries == 1
        assert coord.command_confirm_stats["confirmed"] == 1
        assert coord.command_confirm_stats["resent"] == 0
        assert coord._pending_confirms == {}

    @pytest.mark.asyncio
    async def test_a_device_that_pushes_on_its_own_is_not_queried(self):
        coord, device = _ready()

        assert await coord.async_control_device(DEV, PowerCommand(power_on=True)) is True
        coord._on_mqtt_state_update(DEV, {"onOff": 1})
        await _settle(coord)

        assert device.queries == 0
        assert coord.command_confirm_stats["confirmed"] == 1

    @pytest.mark.asyncio
    async def test_a_dropped_command_is_resent_once_and_then_confirms(self):
        coord, device = _ready()
        device.showing = {"onOff": 1, "color": {"r": 0, "g": 0, "b": 255}}  # still blue
        command = ColorCommand(color=RED)

        def _deliver(*_args: Any) -> bool:
            # The resend is the one that reaches the device.
            if coord._api_client.control_device.await_count == 2:
                device.showing = {"onOff": 1, "color": {"r": 255, "g": 0, "b": 0}}
            return True

        coord._api_client.control_device = AsyncMock(side_effect=_deliver)

        assert await coord.async_control_device(DEV, command) is True
        await _settle(coord)

        assert _sent(coord) == [command, command]
        stats = coord.command_confirm_stats
        assert (stats["resent"], stats["confirmed"], stats["confirmed_after_resend"]) == (1, 1, 1)
        assert coord.command_resends == 1
        # The contradicting frame showed blue; the resend puts the intended red back.
        assert coord._states[DEV].color == RED

    @pytest.mark.asyncio
    async def test_gives_up_after_the_configured_resends(self):
        coord, device = _ready(options={CONF_COMMAND_CONFIRM_RESENDS: 2})
        device.showing = {"onOff": 0}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert len(_sent(coord)) == 3  # the command plus two resends, never more
        assert coord.command_confirm_stats["resent"] == 2
        assert coord.command_confirm_stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_zero_resends_only_counts_the_drop(self):
        coord, device = _ready(options={CONF_COMMAND_CONFIRM_RESENDS: 0})
        device.showing = {"onOff": 0}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert len(_sent(coord)) == 1
        assert coord.command_confirm_stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_a_stale_frame_is_overruled_by_a_later_matching_one(self):
        """Power-on reporting lag: the first frame can predate the command."""
        coord, device = _ready()
        device.showing = {"onOff": 1}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        coord._on_mqtt_state_update(DEV, {"onOff": 0})  # in flight before the command landed
        await _settle(coord)

        assert len(_sent(coord)) == 1
        assert coord.command_confirm_stats["confirmed"] == 1

    @pytest.mark.asyncio
    async def test_a_failed_resend_is_counted_and_not_retried(self):
        coord, device = _ready(options={CONF_COMMAND_CONFIRM_RESENDS: 3})
        device.showing = {"onOff": 0}
        coord._api_client.control_device = AsyncMock(side_effect=[True, GoveeApiError("boom", code=500)])

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert coord._api_client.control_device.await_count == 2
        assert coord.command_confirm_stats["failed"] == 1
        assert coord._transport.get(DEV, "cloud_api").last_failure_reason == "boom"

    @pytest.mark.asyncio
    async def test_a_rejected_resend_is_counted_and_not_retried(self):
        coord, device = _ready(options={CONF_COMMAND_CONFIRM_RESENDS: 3})
        device.showing = {"onOff": 0}
        coord._api_client.control_device = AsyncMock(side_effect=[True, False])

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert coord._api_client.control_device.await_count == 2
        assert coord.command_confirm_stats["failed"] == 1


@pytest.mark.usefixtures("fast_windows")
class TestBudget:
    @pytest.mark.asyncio
    async def test_no_resend_past_the_daily_budget(self):
        coord, device = _ready(options={"daily_request_budget": 9000})
        coord._api_client.requests_today = 9000
        device.showing = {"onOff": 0}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert len(_sent(coord)) == 1
        assert coord.command_confirm_stats["skipped_budget"] == 1

    @pytest.mark.asyncio
    async def test_no_resend_into_the_per_minute_reserve(self):
        coord, device = _ready()
        coord._api_client.rate_limit_remaining = 5
        device.showing = {"onOff": 0}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert len(_sent(coord)) == 1
        assert coord.command_confirm_stats["skipped_budget"] == 1

    @pytest.mark.asyncio
    async def test_no_resend_while_rate_limited(self):
        coord, device = _ready()
        coord._rate_limited = True
        device.showing = {"onOff": 0}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert len(_sent(coord)) == 1


@pytest.mark.usefixtures("fast_windows")
class TestCloudReadFallback:
    @pytest.mark.asyncio
    async def test_only_when_no_frame_spoke_and_a_confirming_read_ends_it(self):
        coord, _device_fake = _ready()  # the device answers nothing
        state = GoveeDeviceState.create_empty(DEV)
        state.power_state = True
        coord._api_client.get_device_state = AsyncMock(return_value=state)

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        coord._api_client.get_device_state.assert_awaited_once_with(DEV, "H6072")
        assert coord.command_confirm_stats["cloud_reads"] == 1
        assert coord.command_confirm_stats["confirmed"] == 1
        assert len(_sent(coord)) == 1

    @pytest.mark.asyncio
    async def test_a_contradicting_read_earns_a_resend(self):
        coord, _device_fake = _ready()
        state = GoveeDeviceState.create_empty(DEV)
        state.power_state = False
        coord._api_client.get_device_state = AsyncMock(return_value=state)

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert len(_sent(coord)) == 2
        assert coord.command_confirm_stats["resent"] == 1

    @pytest.mark.asyncio
    async def test_never_when_a_frame_already_answered(self):
        coord, device = _ready()
        device.showing = {"onOff": 0}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        coord._api_client.get_device_state.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skipped_without_budget_and_left_unverified(self):
        coord, _device_fake = _ready()
        coord._api_client.requests_today = 9000

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        coord._api_client.get_device_state.assert_not_awaited()
        assert len(_sent(coord)) == 1
        assert coord.command_confirm_stats["unverified"] == 1

    @pytest.mark.asyncio
    async def test_a_failed_read_is_left_unverified(self):
        coord, _device_fake = _ready()
        coord._api_client.get_device_state = AsyncMock(side_effect=TimeoutError())

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert len(_sent(coord)) == 1
        assert coord.command_confirm_stats["unverified"] == 1


@pytest.mark.usefixtures("fast_windows")
class TestLastCommandWins:
    @pytest.mark.asyncio
    async def test_a_newer_power_off_cancels_a_pending_brightness_confirm(self):
        """Resending the brightness after "off" would switch the light back on."""
        coord, device = _ready(window=0.5)
        device.showing = {"onOff": 1, "brightness": 10}  # brightness write dropped

        await coord.async_control_device(DEV, BrightnessCommand(brightness=80))
        brightness_task = coord._pending_confirms[DEV]["brightness"].task
        device.showing = {"onOff": 0, "brightness": 10}
        await coord.async_control_device(DEV, PowerCommand(power_on=False))
        await _settle(coord)

        assert brightness_task is not None and brightness_task.cancelled()
        assert _sent(coord) == [BrightnessCommand(brightness=80), PowerCommand(power_on=False)]
        assert coord.command_confirm_stats["superseded"] == 1

    @pytest.mark.asyncio
    async def test_a_newer_command_on_any_tier_still_cancels(self):
        """The cancel happens before dispatch, so a BLE/LAN-delivered command counts too."""
        coord, _device_fake = _ready(window=0.5)
        await coord.async_control_device(DEV, ColorCommand(color=RED))
        task = coord._pending_confirms[DEV]["color"].task
        coord._try_lan_command = AsyncMock(return_value=True)

        await coord.async_control_device(DEV, ColorTempCommand(kelvin=3000))
        await asyncio.sleep(0)

        assert task is not None and task.cancelled()
        assert DEV not in coord._pending_confirms

    @pytest.mark.asyncio
    async def test_brightness_and_colour_from_one_call_are_each_confirmed(self):
        coord, device = _ready()
        device.showing = {"onOff": 1, "brightness": 60, "color": {"r": 255, "g": 0, "b": 0}}

        await coord.async_control_device(DEV, BrightnessCommand(brightness=60))
        await coord.async_control_device(DEV, ColorCommand(color=RED))
        assert set(coord._pending_confirms[DEV]) == {"brightness", "color"}
        await _settle(coord)

        assert coord.command_confirm_stats["confirmed"] == 2
        assert coord.command_confirm_stats["superseded"] == 0

    @pytest.mark.asyncio
    async def test_a_scene_cancels_a_pending_colour_confirm(self):
        coord, _device_fake = _ready(window=0.5)
        await coord.async_control_device(DEV, ColorCommand(color=RED))
        task = coord._pending_confirms[DEV]["color"].task

        await coord.async_control_device(DEV, SceneCommand(scene_id=7, scene_name="Aurora"))
        await asyncio.sleep(0)

        assert task is not None and task.cancelled()

    @pytest.mark.asyncio
    async def test_unload_cancels_everything_pending(self):
        coord, _device_fake = _ready(window=0.5)
        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        task = coord._pending_confirms[DEV]["power"].task

        coord._cancel_command_confirms()
        await asyncio.sleep(0)

        assert task is not None and task.cancelled()
        assert coord._pending_confirms == {}


@pytest.mark.usefixtures("fast_windows")
class TestWhoIsConfirmed:
    @pytest.mark.asyncio
    async def test_a_device_never_heard_on_mqtt_costs_nothing(self):
        coord, _device_fake = _ready()
        coord._transport = coord_mod.TransportHealthTracker()
        coord._ensure_transport_health(DEV)

        await coord.async_control_device(DEV, PowerCommand(power_on=True))

        assert coord._pending_confirms == {}
        assert coord.command_confirm_stats["started"] == 0

    @pytest.mark.asyncio
    async def test_nothing_while_mqtt_is_down(self):
        coord, _device_fake = _ready()
        coord._mqtt_client.connected = False

        await coord.async_control_device(DEV, PowerCommand(power_on=True))

        assert coord._pending_confirms == {}

    @pytest.mark.asyncio
    async def test_nothing_when_turned_off(self):
        coord, _device_fake = _ready(options={CONF_COMMAND_CONFIRM: False})

        await coord.async_control_device(DEV, PowerCommand(power_on=True))

        assert coord._pending_confirms == {}
        assert coord.command_confirm_stats["started"] == 0

    @pytest.mark.asyncio
    async def test_nothing_for_a_group(self):
        coord, _device_fake = _ready(device=_device(is_group=True))

        await coord.async_control_device(DEV, PowerCommand(power_on=True))

        assert coord._pending_confirms == {}

    @pytest.mark.asyncio
    async def test_nothing_for_a_command_with_no_status_field(self):
        coord, _device_fake = _ready()

        await coord.async_control_device(DEV, SceneCommand(scene_id=1, scene_name="Sunset"))

        assert coord._pending_confirms == {}

    @pytest.mark.asyncio
    async def test_nothing_when_the_cloud_rejected_the_command(self):
        coord, _device_fake = _ready()
        coord._api_client.control_device = AsyncMock(return_value=False)

        assert await coord.async_control_device(DEV, PowerCommand(power_on=True)) is False

        assert coord._pending_confirms == {}

    @pytest.mark.asyncio
    async def test_power_on_a_multi_outlet_plug_is_left_alone(self, monkeypatch: pytest.MonkeyPatch):
        """Its onOff is a per-outlet mask, not the commanded power."""
        coord, _device_fake = _ready()
        monkeypatch.setattr(GoveeDevice, "mqtt_outlet_count", property(lambda self: 2))

        await coord.async_control_device(DEV, PowerCommand(power_on=True))

        assert coord._pending_confirms == {}

    @pytest.mark.asyncio
    async def test_an_mqtt_tier_command_is_confirmed_and_resent_over_the_cloud(self):
        coord, device = _ready()
        coord._enable_mqtt_control = True
        device.showing = {"onOff": 0}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        pending = coord._pending_confirms[DEV]["power"]
        assert pending.origin == "mqtt"
        await _settle(coord)

        coord._mqtt_client.async_publish_command.assert_awaited_once()
        assert _sent(coord) == [PowerCommand(power_on=True)]  # the resend, via REST
        assert coord.command_confirm_stats["resent"] == 1


@pytest.mark.usefixtures("fast_windows")
class TestStatusQueryRules:
    """The confirm's status query follows the sweep's rules (issue #195)."""

    @pytest.mark.asyncio
    async def test_marks_the_query_in_flight_and_clears_it(self):
        coord, device = _ready()
        seen: list[str | None] = []

        async def _answer(topic: str | None) -> bool:
            seen.append(coord._status_query_in_flight)
            return await device.answer_query(topic)

        coord._mqtt_client.async_publish_status_query = AsyncMock(side_effect=_answer)
        device.showing = {"onOff": 1}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert seen == [DEV]
        assert coord._status_query_in_flight is None

    @pytest.mark.asyncio
    async def test_not_when_the_re_query_is_turned_off(self):
        coord, device = _ready(options={CONF_MQTT_STATUS_INTERVAL: 0})
        device.showing = {"onOff": 1}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert device.queries == 0

    @pytest.mark.asyncio
    async def test_not_for_a_quarantined_device(self):
        coord, device = _ready()
        coord._status_query_quarantine.add(DEV)

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert device.queries == 0

    @pytest.mark.asyncio
    async def test_not_while_a_sweep_is_running(self):
        coord, device = _ready()
        coord._status_sweep_running = True

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        await _settle(coord)

        assert device.queries == 0


@pytest.mark.usefixtures("fast_windows")
class TestEdges:
    @pytest.mark.asyncio
    async def test_a_frame_about_other_fields_leaves_the_confirm_waiting(self):
        coord, device = _ready()
        device.showing = {"onOff": 1}

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        coord._on_mqtt_state_update(DEV, {"brightness": 30})  # says nothing about power
        assert coord._pending_confirms[DEV]["power"].verdict is None
        await _settle(coord)

        assert coord.command_confirm_stats["confirmed"] == 1

    @pytest.mark.asyncio
    async def test_scheduling_twice_for_one_field_cancels_the_first(self):
        coord, _device_fake = _ready(window=0.5)
        device = coord._devices[DEV]
        coord._maybe_schedule_command_confirm(DEV, device, PowerCommand(power_on=True), origin="cloud_api")
        first = coord._pending_confirms[DEV]["power"].task

        coord._maybe_schedule_command_confirm(DEV, device, PowerCommand(power_on=True), origin="cloud_api")
        await asyncio.sleep(0)

        assert first is not None and first.cancelled()
        coord._cancel_command_confirms()

    @pytest.mark.asyncio
    async def test_a_session_that_drops_mid_confirm_sends_no_query(self):
        coord, device = _ready()
        state = GoveeDeviceState.create_empty(DEV)
        state.power_state = True
        coord._api_client.get_device_state = AsyncMock(return_value=state)

        await coord.async_control_device(DEV, PowerCommand(power_on=True))
        coord._mqtt_client.connected = False  # the session drops before the query is due
        await _settle(coord)

        assert device.queries == 0
        assert coord.command_confirm_stats["cloud_reads"] == 1

    @pytest.mark.asyncio
    async def test_waiting_with_no_time_left_returns_at_once(self):
        coord, _device_fake = _ready()
        pending = coord_mod._PendingConfirm(
            device_id=DEV,
            sku="H6072",
            command=PowerCommand(power_on=True),
            field="power",
            origin="cloud_api",
            brightness_range=(0, 100),
        )

        assert await coord._wait_confirm_event(pending, 0) is False
        pending.event.set()
        assert await coord._wait_confirm_event(pending, 0) is True

    def test_unload_with_the_feature_off_is_a_no_op(self):
        coord = _coordinator({CONF_COMMAND_CONFIRM: False})
        coord._cancel_command_confirms()
        assert coord._pending_confirms == {}


class TestReporting:
    def test_diagnostics_carry_the_counters(self):
        from custom_components.govee.diagnostics import _runtime_diag

        coord = _coordinator()
        coord._mqtt_client = None
        coord._openapi_events_client = None
        coord._confirm_stats["resent"] = 3

        section = _runtime_diag(coord)["command_confirm"]

        assert section["enabled"] is True
        assert section["window_seconds"] == float(DEFAULT_COMMAND_CONFIRM_WINDOW)
        assert section["resent"] == 3

    def test_the_rate_limit_sensor_shows_requests_spent_on_resends(self):
        coordinator = MagicMock()
        coordinator.command_resends = 4
        sensor = object.__new__(GoveeRateLimitSensor)
        sensor.coordinator = coordinator

        assert sensor.extra_state_attributes["command_resends"] == 4
