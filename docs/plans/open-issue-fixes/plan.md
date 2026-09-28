# Plan: open-issue-fixes

## Architecture
Four independent, small changes on `main`, each following an existing pattern:
- **BLE gate:** copy the LAN tier's `transport.get(...).is_available` check into the BLE tier. Rejected: a staleness TTL inside `_try_ble_command` (two places to keep in sync), and un-enrolling from `_ble_devices` (loses re-enrolment when advertisements come back).
- **BLE send accounting:** `_record_transport_send` plus `_record_local_command`, the same calls the MQTT and LAN tiers already make.
- **Auth hardening:** two module helpers in `api/auth.py`, applied only to the two leak calls. Rejected: sweeping every call site (out of scope, and more risk before the release).
- **Raw ptReal:** a coordinator method over the existing `BlePassthroughManager.async_send_ble_packet` and `build_packet`, plus a service in `services.py`. Rejected: a guessed `33 05 15` segment builder (unknown codec; a wrong frame recolours the whole string, which is the bug itself).

## File map
- `custom_components/govee/coordinator.py`: `_ble_write_eligible` gate (T-001); BLE send accounting in `_try_ble_command` (T-002); `async_send_raw_ptreal` (T-004)
- `custom_components/govee/api/auth.py`: `_read_json`, `_error_message`; `fetch_leak_warning`/`lift_leak_warning` use them (T-003)
- `custom_components/govee/services.py`, `services.yaml`: `send_raw_ptreal` (T-005)
- `custom_components/govee/strings.json`, `translations/en.json`: the service, plus `invalid_ptreal_frame` and `ptreal_unavailable` exceptions (T-005)
- tests: `test_cov_coordinator_control.py`, `test_coordinator.py`, `test_cov_auth.py`, `test_services.py`

## Coverage
| Outcome | Coordinator | API | Service/strings | Test |
|---|---|---|---|---|
| Stale BLE skipped | T-001 | — | — | T-001 |
| BLE send recorded | T-002 | — | — | T-002 |
| Leak response hardening | — | T-003 | — | T-003 |
| Raw ptReal service | T-004 | (reuse) | T-005 | T-004, T-005 |

## Risks
- T-001: devices whose advertisements arrive through a proxy with gaps over 120 s lose BLE-first (REST/MQTT still work)
- T-002: `mark_send` sets `is_available=True`; the next poll's `refresh_ble_staleness` re-stales it from `last_success_ts`. Tests must pin that
- T-004/T-005: sending arbitrary frames can put a light into an odd mode. It needs account login, is scoped to known devices and is documented as a debug tool
- T-001/T-002/T-004 share `coordinator.py` and one test file, so build them in order, not in parallel

## Solutions consulted
- No `docs/solutions/` or `docs/plans/BACKLOG.md` in this repo; no effect
- Session findings reused: #198 diagnostics analysis, critic reports on PR #219 and the #198 MQTT gate

## Research
- `.cc-sessions/sessions/b7101f46-014d-44f1-8beb-88aa11ef75c4/plan-open-issue-fixes/research-codebase.md`
