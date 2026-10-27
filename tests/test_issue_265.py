"""H7130 heater: heat-level/setpoint writes imply power on; the setpoint rounds (issue #265)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.govee.models import GoveeCapability, GoveeDevice
from custom_components.govee.models.commands import TemperatureSettingCommand, WorkModeCommand
from custom_components.govee.models.state import GoveeDeviceState
from custom_components.govee.number import GoveeHeaterTemperatureNumber
from tests.coordinator_mocks import follow_online_flag
from tests.test_cov_coordinator_control import _add, _coordinator

HEATER_ID = "AA:BB:CC:DD:EE:FF:00:22"
FAN_ID = "AA:BB:CC:DD:EE:FF:00:33"

# Developer-API capabilities the H7130 advertises (heat level, setpoint, power).
_CAPS = (
    GoveeCapability(type="devices.capabilities.on_off", instance="powerSwitch", parameters={}),
    GoveeCapability(
        type="devices.capabilities.work_mode",
        instance="workMode",
        parameters={
            "dataType": "STRUCT",
            "fields": [
                {
                    "fieldName": "workMode",
                    "dataType": "ENUM",
                    "options": [
                        {"name": "Low", "value": 1},
                        {"name": "Medium", "value": 2},
                        {"name": "High", "value": 3},
                    ],
                },
                {"fieldName": "modeValue", "dataType": "ENUM", "options": [{"name": "Low", "value": 0}]},
            ],
        },
    ),
    GoveeCapability(
        type="devices.capabilities.temperature_setting",
        instance="targetTemperature",
        parameters={
            "dataType": "STRUCT",
            "fields": [
                {"fieldName": "temperature", "dataType": "INTEGER", "range": {"min": 5, "max": 30, "precision": 1}},
            ],
        },
    ),
)


def _device(device_id: str, device_type: str) -> GoveeDevice:
    return GoveeDevice(device_id=device_id, sku="H7130", name="Heater", device_type=device_type, capabilities=_CAPS)


def _heater_state() -> GoveeDeviceState:
    state = GoveeDeviceState.create_empty(HEATER_ID)
    state.power_state = False
    return state


def test_heat_level_write_turns_power_on() -> None:
    coord = _coordinator()
    state = _add(coord, _device(HEATER_ID, "devices.types.heater"), _heater_state())
    coord._apply_optimistic_update(HEATER_ID, WorkModeCommand(work_mode=3, mode_value=0))
    assert state.power_state is True
    assert state.work_mode == 3


def test_setpoint_write_turns_power_on() -> None:
    coord = _coordinator()
    state = _add(coord, _device(HEATER_ID, "devices.types.heater"), _heater_state())
    coord._apply_optimistic_update(HEATER_ID, TemperatureSettingCommand(temperature=21, auto_stop=0))
    assert state.power_state is True
    assert state.heater_temperature == 21


def test_fan_work_mode_write_leaves_power_alone() -> None:
    coord = _coordinator()
    fan_state = GoveeDeviceState.create_empty(FAN_ID)
    fan_state.power_state = False
    state = _add(coord, _device(FAN_ID, "devices.types.fan"), fan_state)
    coord._apply_optimistic_update(FAN_ID, WorkModeCommand(work_mode=1, mode_value=2))
    assert state.power_state is False
    assert state.work_mode == 1


def _number() -> tuple[GoveeHeaterTemperatureNumber, MagicMock]:
    device = _device(HEATER_ID, "devices.types.heater")
    state = GoveeDeviceState.create_empty(HEATER_ID)
    state.heater_auto_stop = 0
    coordinator = MagicMock()
    coordinator.devices = {HEATER_ID: device}
    coordinator.get_state = MagicMock(return_value=state)
    coordinator.async_control_device = AsyncMock(return_value=True)
    follow_online_flag(coordinator)
    entity = GoveeHeaterTemperatureNumber(coordinator=coordinator, device=device, temp_range=(5, 30))
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()
    return entity, coordinator


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (20.999999999999996, 21),  # 69.8 F converted to C; int() gave 20
        (21.4, 21),
        (21.5, 22),  # round() is half-to-even: 21.5 -> 22 (22 is even)
        (22.5, 22),  # half-to-even again: 22.5 -> 22
        (2.0, 5),  # clamped to native min
        (45.0, 30),  # clamped to native max
    ],
)
async def test_setpoint_rounds_not_truncates(value: float, expected: int) -> None:
    entity, coordinator = _number()
    await entity.async_set_native_value(value)
    command = coordinator.async_control_device.await_args.args[1]
    assert isinstance(command, TemperatureSettingCommand)
    assert command.temperature == expected
