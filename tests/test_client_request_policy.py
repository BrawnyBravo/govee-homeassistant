"""How the REST client spends requests: what is retried, and how answers are read.

These run the real aiohttp-retry client over a fake session so the number of
requests actually sent is what is asserted, not how the retry client was
configured.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.govee.api.client import GoveeApiClient
from custom_components.govee.api.exceptions import GoveeApiError, GoveeConnectionError
from custom_components.govee.models import PowerCommand

DEVICE = "AA:BB:CC:DD:EE:FF:00:11"


def _response(method: str, status: int, body: Any = None, headers: dict[str, str] | None = None) -> MagicMock:
    response = MagicMock()
    response.method = method
    response.status = status
    response.headers = headers or {}
    response.closed = False
    response.json = AsyncMock(return_value=body if body is not None else {"code": status, "message": "error"})
    response.text = AsyncMock(return_value="")
    return response


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch):
    """Skip aiohttp-retry's back-off sleeps."""
    import aiohttp_retry.client as retry_module

    monkeypatch.setattr(retry_module.asyncio, "sleep", AsyncMock())


def _client(request: AsyncMock) -> GoveeApiClient:
    session = MagicMock()
    session.request = request
    return GoveeApiClient("test-key", session=session)


@pytest.mark.asyncio
async def test_control_command_is_sent_once_on_timeout():
    request = AsyncMock(side_effect=TimeoutError())
    client = _client(request)

    with pytest.raises(GoveeConnectionError):
        await client.control_device(DEVICE, "H6159", PowerCommand(power_on=True))

    assert request.await_count == 1


@pytest.mark.asyncio
async def test_control_command_is_sent_once_on_server_error():
    request = AsyncMock(return_value=_response("POST", 503))
    client = _client(request)

    with pytest.raises(GoveeApiError):
        await client.control_device(DEVICE, "H6159", PowerCommand(power_on=True))

    assert request.await_count == 1


@pytest.mark.asyncio
async def test_state_read_still_retries_on_timeout():
    request = AsyncMock(side_effect=TimeoutError())
    client = _client(request)

    with pytest.raises(GoveeConnectionError):
        await client.get_device_state(DEVICE, "H6159")

    assert request.await_count == 3
