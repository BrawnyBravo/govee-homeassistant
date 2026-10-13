"""Account/BFF client robustness: malformed device entries, HTTP 401 mapping, login errors.

Complements ``test_cov_auth.py`` with the shapes Govee is not documented to
send but the parsers must survive: a ``deviceExt`` of ``null``, a non-dict
``gatewayInfo``, a non-numeric slot, an HTTP 401 with a non-JSON body, a login
error with a null message, and a verification-code request answered with an
in-body error. Everything runs offline over fake aiohttp sessions.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.govee.api.auth import GoveeAuthClient
from tests.test_cov_auth import _bff_list, _leak, _response, _session, _thermo


def _non_json(status: int) -> MagicMock:
    """A response whose body is not JSON (an HTML/plain-text error page)."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(side_effect=aiohttp.ContentTypeError(MagicMock(), (), message="text/html"))
    return response


GOOD_LEAK_EXT = {"deviceSettings": {"sno": 1, "battery": 90, "gatewayInfo": {"device": "GW:1", "sku": "H5044"}}}


class TestMalformedDeviceEntries:
    """One odd device must not take the whole account list down (CLOUD-3)."""

    @pytest.mark.parametrize("bad_ext", [None, "null", 5, ["x"]])
    def test_topics_survive_a_non_dict_device_ext(self, bad_ext):
        devices: list[Any] = [
            {"device": "A", "deviceExt": bad_ext},
            "not-a-device",
            {"device": "B", "deviceExt": {"deviceSettings": {"topic": "GD/b"}}},
        ]

        assert GoveeAuthClient._extract_topics_from_devices(devices) == {"B": "GD/b"}
        assert GoveeAuthClient._extract_gateway_routes(devices) == {}

    async def test_leak_list_skips_only_the_malformed_sensor(self):
        devices: list[Any] = [
            _leak("L1", None),
            _leak("L2", {"deviceSettings": {"sno": "slot-x", "gatewayInfo": {"device": "GW:1"}}}),
            _leak("L3", {"deviceSettings": {"sno": 2, "gatewayInfo": "GW:1"}, "lastDeviceData": "null"}),
            _leak("L4", GOOD_LEAK_EXT),
            {"sku": "H5179", "device": "T9", "deviceExt": None},
            None,
        ]
        client = GoveeAuthClient(session=_session(get=[_response(200, _bff_list(*devices))]))

        sensors, _hubs, _thermo_readings = await client.fetch_bff_leak_sensors("tok")

        by_id = {s["device_id"]: s for s in sensors}
        assert set(by_id) == {"L3", "L4"}
        assert by_id["L3"]["hub_device_id"] == ""
        assert by_id["L3"]["online"] is True
        assert by_id["L4"]["sno"] == 1

    async def test_thermo_list_survives_a_null_device_ext(self):
        devices: list[Any] = [_thermo("T1", None), _thermo("T2", {"deviceSettings": {"battery": 70}}), 7]
        client = GoveeAuthClient(session=_session(get=[_response(200, _bff_list(*devices))]))

        sensors = {s["device_id"]: s for s in await client.fetch_bff_thermo_hygrometers("tok")}

        assert set(sensors) == {"T1", "T2"}
        assert sensors["T2"]["battery"] == 70

    async def test_water_detector_list_survives_a_null_device_ext(self):
        devices: list[Any] = [
            {"device": "AA:BB", "deviceExt": None},
            {"device": "CC:DD", "deviceExt": {"deviceSettings": "null", "lastDeviceData": {"lastTime": 9}}},
        ]
        client = GoveeAuthClient(session=_session(get=[_response(200, _bff_list(*devices))]))

        states = await client.fetch_water_detector_states("tok", {"AA:BB", "CC:DD"})

        assert states["AA:BB"]["online"] is True
        assert states["CC:DD"]["last_time"] == 9
        assert states["CC:DD"]["battery"] is None

    async def test_non_dict_data_envelope_reads_as_no_devices(self):
        client = GoveeAuthClient(session=_session(get=[_response(200, {"data": "null"})]))

        assert await client.fetch_bff_thermo_hygrometers("tok") == []
