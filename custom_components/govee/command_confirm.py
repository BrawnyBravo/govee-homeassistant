"""Pure policy for confirming cloud and MQTT commands against device status.

A cloud ``/device/control`` call that returns HTTP 200 only says Govee's cloud
accepted the command, not that the device acted on it, and an MQTT publish is
never acknowledged at all. Both are sometimes dropped on the way to the
device, which is what users see as "I had to press it three times". The LAN
tier already reads the device back after every write; this is the same idea
for the cloud and MQTT tiers, using the device's own AWS IoT status frame as
the readback, which costs nothing against Govee's request quota.

Everything here is a pure function of a command and the values a device or
the cloud reported: no Home Assistant, no coordinator, no clock. The
coordinator owns the timing, the status query and the resend, and asks these
functions what the evidence says, which keeps the matching rules testable on
their own.
"""

from __future__ import annotations

from typing import Any, Literal

from .api.mqtt_control import POWER_QUIRK_SKUS, device_brightness_to_mqtt
from .models.commands import (
    BrightnessCommand,
    ColorCommand,
    ColorTempCommand,
    DeviceCommand,
    PowerCommand,
)
from .models.state import GoveeDeviceState, RGBColor

__all__ = [
    "BRIGHTNESS_CONFIRM_TOLERANCE",
    "COLOR_CHANNEL_CONFIRM_TOLERANCE",
    "COLOR_TEMP_CONFIRM_TOLERANCE",
    "ConfirmField",
    "cloud_request_affordable",
    "confirm_field",
    "confirms_conflict",
    "frame_confirms",
    "state_confirms",
]

ConfirmField = Literal["power", "brightness", "color", "color_temp"]

# Brightness tolerance, in the units the frame reports. Status frames carry
# brightness on the 1-100 scale the native ``brightness`` command takes, so a
# device with a wider native range (0-254) rounds on the way there and back;
# the same +-2 the LAN readback uses absorbs that without masking a write that
# never landed.
BRIGHTNESS_CONFIRM_TOLERANCE = 2

# Colour tolerance per RGB channel. Firmware occasionally reports a channel one
# step off what it was sent (gamma tables); a dropped command reports the
# previous colour, which is nowhere near this close.
COLOR_CHANNEL_CONFIRM_TOLERANCE = 2

# Kelvin tolerance. Firmware snaps the requested value onto its own grid, the
# same reason the LAN readback allows 150 K (issues #149, #158).
COLOR_TEMP_CONFIRM_TOLERANCE = 150


def confirm_field(command: DeviceCommand, sku: str = "") -> ConfirmField | None:
    """Which status field confirms ``command``, or None when nothing can.

    Only the four fields an AWS IoT status frame reports for every light are
    confirmable: power, brightness, colour and colour temperature. Scenes,
    segments, music modes, work modes and toggles have no field in the frame
    to compare against, so they are never confirmed (or resent).

    Power on the H5080/H5083 plugs is excluded: they report ``onOff`` as
    17/16 rather than 1/0, so a frame cannot tell on from off. A brightness of
    0 is excluded too, since firmware treats it as "off" and reports the last
    lit brightness.
    """
    if isinstance(command, PowerCommand):
        if sku.upper() in POWER_QUIRK_SKUS:
            return None
        return "power"
    if isinstance(command, BrightnessCommand):
        return "brightness" if command.brightness > 0 else None
    if isinstance(command, ColorCommand):
        return "color"
    if isinstance(command, ColorTempCommand):
        return "color_temp"
    return None


def confirms_conflict(new: ConfirmField | None, pending: ConfirmField) -> bool:
    """Whether a newer command makes a pending confirm stale.

    Last command wins: a pending confirm must never resend something the user
    has since changed their mind about. A colour followed by a brightness
    change (one ``light.turn_on`` call sends both) leaves each to be confirmed
    on its own, but:

    * any command that cannot be confirmed (a scene, a segment write) replaces
      whatever the light was showing, so it cancels everything;
    * power conflicts with everything in both directions, since resending a
      brightness after a newer "off" would turn the light back on, and
      resending "off" after a newer brightness would turn it off again;
    * colour and colour temperature replace each other;
    * a newer write of the same field replaces the older one.
    """
    if new is None or new == "power" or pending == "power":
        return True
    if new == pending:
        return True
    return {new, pending} == {"color", "color_temp"}


def _frame_brightness_matches(value: int, command: BrightnessCommand, brightness_range: tuple[int, int]) -> bool:
    """Match a frame brightness against the device-native value sent.

    Frames report brightness on the 1-100 scale, but which scale a given SKU
    uses for its push has never been confirmed for wide-range devices, so the
    device-native value is accepted too. On the common 0-100 range both are the
    same number.
    """
    scaled = device_brightness_to_mqtt(command.brightness, brightness_range)
    return (
        abs(value - scaled) <= BRIGHTNESS_CONFIRM_TOLERANCE
        or abs(value - command.brightness) <= BRIGHTNESS_CONFIRM_TOLERANCE
    )


def _colors_match(reported: RGBColor, sent: RGBColor) -> bool:
    return (
        abs(reported.r - sent.r) <= COLOR_CHANNEL_CONFIRM_TOLERANCE
        and abs(reported.g - sent.g) <= COLOR_CHANNEL_CONFIRM_TOLERANCE
        and abs(reported.b - sent.b) <= COLOR_CHANNEL_CONFIRM_TOLERANCE
    )


def _frame_color(value: Any) -> RGBColor | None:
    """The colour a status frame carries, in either shape it is sent in."""
    try:
        if isinstance(value, dict):
            return RGBColor.from_dict(value)
        if isinstance(value, int) and not isinstance(value, bool):
            return RGBColor.from_packed_int(value)
    except (TypeError, ValueError):
        return None
    return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def frame_confirms(
    command: DeviceCommand,
    frame: dict[str, Any],
    brightness_range: tuple[int, int] = (0, 100),
    sku: str = "",
) -> bool | None:
    """Whether an AWS IoT status frame shows ``command`` took effect.

    Returns True when the frame reports the commanded value, False when it
    reports a different one, and None when the frame says nothing about that
    field (or the command is not confirmable). None is not evidence either
    way: a frame with no brightness in it cannot say a brightness write was
    dropped.

    Args:
        command: The command that was sent.
        frame: The frame's ``state`` dict as the MQTT client delivers it
            (``onOff``, ``brightness``, ``color``, ``colorTemInKelvin``).
        brightness_range: The device's native brightness range.
        sku: The device's SKU, for the power quirk in :func:`confirm_field`.
    """
    field = confirm_field(command, sku)
    if field is None:
        return None
    if field == "power" and isinstance(command, PowerCommand):
        on_off = _as_int(frame.get("onOff"))
        if on_off is None:
            return None
        return bool(on_off) == command.power_on
    if field == "brightness" and isinstance(command, BrightnessCommand):
        brightness = _as_int(frame.get("brightness"))
        if brightness is None:
            return None
        return _frame_brightness_matches(brightness, command, brightness_range)
    if field == "color" and isinstance(command, ColorCommand):
        if "color" not in frame:
            return None
        color = _frame_color(frame["color"])
        if color is None:
            return None
        return _colors_match(color, command.color)
    if field == "color_temp" and isinstance(command, ColorTempCommand):
        kelvin = _as_int(frame.get("colorTemInKelvin"))
        if kelvin is None:
            return None
        return abs(kelvin - command.kelvin) <= COLOR_TEMP_CONFIRM_TOLERANCE
    return None  # pragma: no cover - confirm_field and the branches above agree


def state_confirms(command: DeviceCommand, state: GoveeDeviceState, sku: str = "") -> bool | None:
    """Whether a cloud ``/device/state`` read shows ``command`` took effect.

    The fallback for a device that sent no status frame at all within the
    confirm window. Same verdicts as :func:`frame_confirms`; brightness here is
    already device-native, as the cloud reports it.
    """
    field = confirm_field(command, sku)
    if field is None:
        return None
    if isinstance(command, PowerCommand):
        return state.power_state == command.power_on
    if isinstance(command, BrightnessCommand):
        return abs(state.brightness - command.brightness) <= BRIGHTNESS_CONFIRM_TOLERANCE
    if isinstance(command, ColorCommand):
        if state.color is None:
            return None
        return _colors_match(state.color, command.color)
    if isinstance(command, ColorTempCommand):
        if state.color_temp_kelvin is None:
            return None
        return abs(state.color_temp_kelvin - command.kelvin) <= COLOR_TEMP_CONFIRM_TOLERANCE
    return None  # pragma: no cover - confirm_field and the branches above agree


def cloud_request_affordable(
    *,
    requests_today: object,
    daily_budget: object,
    rate_limit_remaining: object,
    rate_limit_reserve: int,
    rate_limited: bool,
) -> bool:
    """Whether one more cloud request (a resend or a state read) fits the budget.

    The confirm path spends from the same allowance as everything else, so it
    has to stay inside both limits the poll already respects:

    * the daily budget the user configured (``requests_today`` is the API
      client's count since UTC midnight; the request must not take it past
      ``daily_budget``), and
    * Govee's own per-minute allowance from the response headers, keeping
      ``rate_limit_reserve`` free for ordinary commands, the same reserve the
      segment re-assert leaves.

    Nothing is spent while the integration is backing off a 429. Counters that
    are not numbers (a malformed header) refuse the spend rather than guess:
    a missed resend costs one tap, a blown quota costs an outage.
    """
    if rate_limited:
        return False
    if not isinstance(requests_today, int) or not isinstance(daily_budget, int):
        return False
    if requests_today + 1 > daily_budget:
        return False
    if not isinstance(rate_limit_remaining, int):
        return False
    return rate_limit_remaining - 1 >= rate_limit_reserve
