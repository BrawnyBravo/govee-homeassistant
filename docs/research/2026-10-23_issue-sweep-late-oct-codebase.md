# Issue sweep (late Oct 2026): codebase research

Read-only research against `main` @ 3de6ea9. Paths are relative to `custom_components/govee/`.
Open PRs checked: #251 and #255 do NOT touch the all-digit group heuristic (#243). #252 partly covers #246.

---

## #243 H5054 with an all-digit device ID treated as a group — FIXABLE (S)

**Root cause.** `models/device.py:1321-1326` sets `is_group = device_type in (group types) or device_id.isdigit()`.
An 18-char hex ID with no A-F digits (`devices.types.sensor`) becomes a group, is skipped when
`enable_groups=False`, and with groups on still loses its leak/battery/button entities (all gate on
`is_group`). Same heuristic at `coordinator.py:4880` (`_try_lan_command`: `device.is_group or device_id.isdigit()`)
and `api/lan_client.py:226` (`non_group_ids = [... if not device_id.isdigit()]`).

**Change.**
- `models/device.py`: add module helper `looks_like_group_id(device_id: str, device_type: str) -> bool`:
  explicit group types → True; else True only when `device_id.isdigit()` **and** `len(device_id) < 12`
  **and** `device_type` is not a concrete `devices.types.*` other than the group ones (real group IDs are
  short decimal, e.g. `11825917`; device IDs are 16-18 hex chars / colon MACs). Use it at line 1321.
- `coordinator.py:4880`: drop `or device_id.isdigit()` (rely on `device.is_group`).
- `api/lan_client.py:226`: filter with `looks_like_group_id(device_id, "")` (length rule) instead of bare `isdigit()`.
- Check BFF leak/water paths compare colon-stripped IDs (`is_bff_leak_sensor`) — unaffected.

**Tests.** extend `tests/test_models.py` (or `tests/test_cov_models_device.py`): `"123456789012345678"` with
`devices.types.sensor` → not group; `"11825917"` with `devices.types.light` → group; explicit group type → group.
Extend `tests/test_lan_client.py` for an 18-digit ID being probed.
**Grep symbol:** `looks_like_group_id`.

## #244 H5054 "not updating" — SEPARATE from #243; DATA-NEEDED / config (no code)

Diagnostics: device `5ABF25CD9C140011EB` has letters → `is_group: false`, so not #243. `has_iot_credentials: false`,
`leak_sensors: {}`, `openapi_events.connected: true`, `recent_events: []`.
On an API-key-only install the moisture entity (`binary_sensor.py:94` `GoveeWaterLeakBinarySensor`) is fed only by the
OpenAPI `bodyAppearedEvent` push (`coordinator.py:1874`); battery, online, last-wet, and the initial state need the
account (email/password) login (BFF `warnMessage` poll). Entity shows dry (`is_on` False default, #145) until a trip.
"Connection mode Unavailable / Disconnected" is expected for a sleepy RF sensor (cloud_api health never set: the
Developer poll returns nothing for it).
**Ask:** add the account login (Configure → account), then do a wet test on one sensor and attach diagnostics.
Optional small doc fix: README note that H5054 battery/initial state require account login.

## #242 Cloud-only availability hard-gates on `state.online` — FIXABLE (M)

**Root cause.** `entity.py:73-86` `GoveeEntity.available` returns `state.online` for non-groups. The poll writes the
Developer API `online` flag each cycle; the IoT push (`coordinator.py:3051`, `3350`) and BLE write (`5171`) set
`online=True`, but the next poll's `online:false` reverts it. Only LAN has an override (`light.py:179-188`
`_allow_lan_availability`). Follow-up comment: some `online:false` are genuine (control returns body code 400
"Device is offline").

**Rule (sane):** keep gating on `online`, but a device is "reachable" if `online` is True **or** any local/push
transport has proven it alive recently: LAN `is_available`, BLE `is_available`, or an MQTT frame for the device
within `REACHABLE_PUSH_WINDOW` (10 min, `mqtt_last_receive_for`, `coordinator.py:670`). And a control reply of
"Device is offline" flips `online=False` immediately and raises a translated `device_offline` error.

**Change.**
- `coordinator.py`: new `def device_reachable(self, device_id) -> bool` implementing the rule above.
- `entity.py:85`: `return state is not None and self.coordinator.device_reachable(self._device_id)`;
  `light.py:181-188` can collapse into it (keep `_allow_lan_availability=False` behaviour for the main-panel entity).
- `api/client.py:365-370`: map a non-200 body whose `msg`/`capability.state.errorMsg` contains "offline" to new
  `GoveeDeviceOfflineError(GoveeApiError)` in `api/exceptions.py`; in `async_control_device` catch it, set
  `state.online=False`, `async_set_updated_data`, return False; `entity._command_failed` uses a `device_offline`
  key in `strings.json` exceptions (+ translations/en.json).
- Do NOT add `assume_online` option (weaker, per reporter).
**Tests.** `tests/test_entity.py` (online False + fresh MQTT ts → available; stale ts → unavailable),
`tests/test_api_client.py` (offline body → `GoveeDeviceOfflineError`), `tests/test_coordinator.py` (offline error flips state).
**Grep symbol:** `device_reachable`, `GoveeDeviceOfflineError`.

## #258 H5179 last measurement timestamp / device-online — FIXABLE (S-M)

H5179 is in `THERMO_HYGRO_BFF_READ_SKUS` (`models/device.py:71`); readings come from BFF `lastDeviceData`, which
already parses `last_time` (`api/auth.py:958`, also 1296). Availability for BFF thermometers ignores `online`
by design (`sensor.py:368-382` `_BffThermometerAvailabilityMixin`, #97), and `GoveeDeviceConnectivity`
(`binary_sensor.py:322`) reflects transport health, so "Connected" + months-old values is expected today.
`GoveeSensorReadingTimestampSensor` (`sensor.py:851`) is "last *change*", stamped by HA, not the device time.

**Change.**
- `coordinator.py`: store `self._bff_last_measurement[device_id] = datetime.fromtimestamp(last_time/1000, UTC)` in
  `_discover_bff_thermometers` (~2429) and `_refresh_bff_thermometers` (~2555); accessor
  `def bff_last_measurement_at(device_id) -> datetime | None`.
- `sensor.py`: `GoveeLastMeasurementSensor` (TIMESTAMP, DIAGNOSTIC, translation_key `last_measurement`, unique id
  `{id}_last_measurement`), created when the device is a BFF thermometer (`coordinator.is_bff_thermometer`).
- `binary_sensor.py`: `GoveeReportedOnlineBinarySensor` (CONNECTIVITY, DIAGNOSTIC, key `reported_online`) from
  `state.online` for BFF thermometers only, available on coordinator success. Leaves transport semantics unchanged.
- Skip the optional stale timeout (users can template on the timestamp). strings.json/en.json/icons.json entries.
**Tests.** `tests/test_sensor.py`, `tests/test_binary_sensor.py`, coordinator BFF refresh test with `lastTime`.
**Grep symbol:** `GoveeLastMeasurementSensor`, `bff_last_measurement_at`.

## #236 H5111 behind H5151 stays Unknown — FIXABLE (XS) + partly INFEASIBLE

Freezer diagnostics (downloaded): Developer state `online:false`, `sensorTemperature value ""`; BFF
`lastDeviceData {"tem": -2090, "hum": 6000, "lastTime": 1791145080000}`; `battery: 100` already applied via
`_apply_bff_thermo_battery` (`coordinator.py:2248`). The reading is never applied because `fetch_bff_thermo_hygrometers`
(`api/auth.py` ~877) only keeps `THERMO_HYGRO_BFF_SKUS`/`THERMO_HYGRO_BFF_READ_SKUS`/probe SKUs, and H5111 is in none,
so the hand-over in `_discover_bff_thermometers` (`coordinator.py:2416-2437`) never runs. The H5179/H5112 path (#141)
is exactly this case.
MQTT: `inbound_messages: 0` on a connected session (same symptom as #222) so the H5151 multiSync route can't help yet.

**Change.** `models/device.py:71`: `THERMO_HYGRO_BFF_READ_SKUS = frozenset({"H5179", "H5112", "H5111"})`.
The #151 guard keeps the refrigerator (no tem/hum in BFF) on the Developer poll and in `_bff_thermo_pending`,
so it picks up a reading later. `tem` scale here is hundredths (−20.90 °C, plausible); `_bff_reading` `("tem", True)` /100.
**Infeasible part:** the refrigerator has no reading in any source the integration can read; nothing to apply until Govee's
cloud carries it.
**Tests.** extend the H5112 case in `tests/test_coordinator_bff*.py` / `tests/test_api_auth.py` with an H5111 fixture.
**Grep symbol:** `"H5111"` in `THERMO_HYGRO_BFF_READ_SKUS`.

## #246 H1270 LAN↔BLE fallback; BLE connect fails (no slot) — FIXABLE (S); PR #252 partial

**Root cause.** `coordinator.py:4638-4645` dispatches BLE-first whenever `_ble_write_eligible` (`5110-5118`) is True.
Eligibility is advertisement freshness only; a failed connect (`_try_ble_command` except, 5149) records a failure but the
next advert flips health back, so every command pays bleak-retry-connector's 9 attempts (~30 s) before LAN.
PR #252 releases idle BLE links after 120 s (frees proxy slots) and fixes single-candidate mis-enrolment, but does not
change the ordering or add a connect backoff.

**Change (coordinator.py).**
- `_ble_connect_backoff_until: dict[str, float]`; on BLE exception set `now + min(300 * 2**n, 3600)`
  (`_ble_connect_failures[device_id]` counter, reset on success); `_ble_write_eligible` returns False while backed off.
- LAN-healthy preference: skip the BLE tier when `self._transport.get(device_id, "lan")` is available
  (order becomes LAN > BLE > MQTT > REST when LAN is healthy). Debug log once per backoff.
- No per-SKU toggle needed; mention in reply.
**Tests.** `tests/test_coordinator_transport*.py` / `tests/test_cov_coordinator.py`: BLE raises → second command skips BLE;
LAN healthy → BLE never called.
**Grep symbol:** `_ble_connect_backoff_until`.
Merge order: land after #252 (both touch the BLE path).

## #209 / #260 H7105 Tower Fan 2 not showing — INFEASIBLE on Developer API (L if done via BFF)

#209 frozenbutt (2026-10-09): H7105 present in `bff_device_census`, absent from `raw_api_devices`, same account.
Entities are only built from Developer API devices (`fan.py` platform iterates `coordinator.devices`); the only
H7105 handling is `MQTT_OSCILLATION_SKUS` (`const.py:134`) + oscillation frame in `api/ble_packet.py:303`, which
never runs since the device is never discovered. #260 is a duplicate (no body detail).
A fix would mean a `GoveeDevice.synthetic_tower_fan()` from the BFF list plus ptReal power/speed/oscillation frames
(homebridge-govee has them) and state from AWS IoT status — new device class, unverified frames. Recommend: close #260
as dup of #209; on #209 explain Govee's Developer API omits it; optionally ask for a Govee support ticket. If pursued: L,
needs a tester with account login.

## #240 H7073 no colour control — DATA-NEEDED

Screenshots are not fetchable (asset URLs need auth). No H7073 reference in code. Colour support comes from
`colorRgb`/`colorTemperatureK` capabilities; if absent, only power/brightness/scenes appear.
**Ask:** device diagnostics download (Download diagnostics button) — need the `capabilities` list and `raw_api_state`.

## #239 H7045 bright white mode — DATA-NEEDED (feature)

Not referenced in code. Needs to know whether the Platform API advertises a capability (e.g. a `toggle`/`mode`
instance) or whether the app uses a ptReal frame.
**Ask:** diagnostics with account login, taken once with White mode ON (from the app) and once with a normal colour, so
`capabilities` and `last_mqtt_message._op_frames` can be diffed. Then a frame can be tested with `govee.send_raw_ptreal`.

## #241 H6099 Video Mode / DreamView missing — DATA-NEEDED

`supports_dreamview` (`models/device.py:844-857`) needs `dreamViewToggle` (or `movieMode` for `MOVIE_MODE_DREAMVIEW_SKUS`,
`const.py:445`). The H6099 advertises neither, so no switch. The ptReal video-mode path exists
(`async_send_dreamview` → `_ble_manager.async_send_dreamview`, `coordinator.py:5346-5410`, used for
`PTREAL_DREAMVIEW_SKUS={"H66A0"}`), but on the H66A0 that ON frame is reported not to work (#213, 2026-10-10), so
reusing it blind for the H6099 is risky.
**Design once verified:** `PTREAL_ONLY_DREAMVIEW_SKUS = {"H6099"}` → `supports_dreamview` True and `skip_rest` True.
**Ask:** diagnostics with account login while Video Mode is running from the app (status frame `aa 05 00 ...` in
`last_mqtt_message._op_frames`), and the capabilities list.

## #245 MQTT/cloud readback confirm + resend — FIXABLE as design (L), maintainer decision

No code yet. LAN analog: `_try_lan_command` readback (`coordinator.py` ~4870-4990). Hooks: after the MQTT tier
(`4668-4676`) and REST success in `async_control_device`, spawn `hass.async_create_background_task(self._confirm_command(...))`.
Confirm source: per-device MQTT status (`_mqtt_heard_from`, `last_message_ts_for`). Status query must respect
`MQTT_STATUS_QUERY_EXCLUDED_SKUS`, #195 quarantine and PR #259 (account-wide refusal stop). Budget: share
`requests_today` and the 20/min reserve used by the segment re-assert. Supersede via a per-device
`_pending_confirms: dict[str, dict[str, asyncio.Task]]` keyed by field.
Recommend: new module `command_confirm.py` (`CommandConfirmer`), options `confirm_commands` (default off),
`confirm_window` 2-30 s (6), `confirm_resends` 0-3 (1); diagnostics `command_confirm` counters. Tests in
`tests/test_command_confirm.py`. Land after #250 (request budget) and #259. **Grep symbol:** `CommandConfirmer`.
Reply: ask the proposer whether they want to send the PR (the proposal reads like they have one).

## #211 H60B0 per-zone colour/brightness — WAITING on PR from reporter (data now sufficient)

2026-10-18 reporter has local working code (overall/ripple/bottom brightness, ripple colour, bottom CT) and plans a PR.
2026-10-21 SamWiIIiams posted a verified LAN ptReal table: side brightness `33 05 2c 02 02 <1-100> <mask>`, side
colour `33 05 2c 02 01 RR GG BB KK KK <mask>`, lower CT `33 05 2c 03 01 KK KK` (2700-6500 K only), section on/off
`33 30 <sec> 01|00` (1 ripple, 2 side, 3 lower; max two on), ripple flow `33 05 2c 01 03 <0-100>`, frames batched in
one `command` array (≤18). Note: docs/release-replies.md still has the old #211 ask queued — **remove/replace that
entry** (it asks for data already provided). Status: WAITING for RuslanMelnychenko's PR; reply pointing at the frame table.

## #222 MQTT session connected, zero frames — FIXABLE (S) + reply owed

T-004/T-013 shipped connection_mode fix + inbound counter (v2026.10.0). Reporter (2026-10-02) shows
`inbound_messages: 0` over 70 min on a fresh session and asks whether to wait a day or re-login; **unanswered**.
Same signature appears in #236's diagnostics (inbound 0). Remaining code gap: a "connected but silent" session is never
treated as unhealthy.
**Change.** `api/mqtt.py`/`coordinator.py`: watchdog `_mqtt_silence_check` — if connected ≥ 6 h with
`inbound_messages == 0` and the account has device topics, raise a repair issue `mqtt_silent` (strings.json `issues`)
suggesting reconfigure (re-login refreshes IoT certs); optionally one forced reconnect first. Tests
`tests/test_mqtt.py` / `tests/test_repairs.py`. **Grep symbol:** `mqtt_silent`.
Reply: yes, please re-enter the account login (reconfigure) now; then diagnostics after an hour.

## Reporter follow-up check (since 2026-10-01)

| # | Latest non-maintainer activity | Status |
|---|---|---|
| #200 | k-perri 2026-09-21 (will test air-quality label later) | WAITING |
| #201 | none since fix 2026-09-21 | WAITING |
| #207 | none | WAITING |
| #208 | jjnuecht 2026-09-22; maintainer 09-28 asked for BLE capture | WAITING |
| #213 | Audiosenpai 2026-10-10: H66A0 ptReal video-mode ON does not start sync (OFF works); Rusich90 2026-10-11: R2A80 REST `dreamViewToggle` works, response has `dreamType: movie` | ACTIONABLE → DATA-NEEDED: ask Audiosenpai for diagnostics while DreamView runs from the app (status/op frames) and the REST response body for `dreamViewToggle` (does it carry `dreamType`?); consider trying `movieMode` REST for H66A0 (`MOVIE_MODE_DREAMVIEW_SKUS`) |
| #215 | none since 09-25 fix | WAITING |
| #223 | holger-dunst 2026-10-03: H1252 fully verified frames (API has 16 segments already; REST main/background toggles do nothing; zone switch `33 30 <zone> <on>` 00=panel 01=ring; panel/ring CT via `33 05 15 01 FF FF FF KK KK R G B <mask>`; zone state `aa 30 <main> <ring>`) | ACTIONABLE → FIXABLE (M): add H1252 to `PTREAL_SEGMENT_SKUS` main-panel path (`const.py:202`), new `PTREAL_ZONE_SWITCH_SKUS={"H1252"}` for on/off via `33 30`, decode `aa 30` into toggles; tests in `tests/test_light_main_panel*.py` |
