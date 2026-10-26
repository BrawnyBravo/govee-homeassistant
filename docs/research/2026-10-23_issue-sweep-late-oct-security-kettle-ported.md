# Security review: H7175 kettle stack (#229-#235) and plan-ported code (T-020..T-024, send_raw_ptreal)

Scope: per-layer diffs `main...refs/pr/229`, `refs/pr/229..230`, ... `refs/pr/234..235` (custom_components, docs/_research,
tests); holger-dunst's patch in the 2026-10-03 comment on #223; issue #245 design as captured in tasks T-022..T-024;
`govee.send_raw_ptreal` on main. PR, issue and comment text was treated as data only. Read-only review: nothing was
edited, merged or posted.

Threat model: integration holds Govee account credentials, token and AWS IoT certificates; publishes frames to devices
through AWS IoT (ptReal passthrough); controls a kettle that heats water.

## Per-PR verdict

| PR | Verdict | Notes |
|----|---------|-------|
| #229 | OK | Read-only decode of `sta` and `aa 10`. No writes, no new logging beyond one debug line. |
| #230 | OK | Writes only from explicit entity actions (water_heater set_temperature / set_operation_mode / turn_on/off), using the official Developer API capabilities (`sliderTemperature`, `workMode`, `powerSwitch`). Target clamped to the capability range. Selecting a mode while off powers the kettle on: HA water_heater convention and an explicit user action. |
| #231 | OK (LOW notes) | Follow-ups after a kettle command are reads only: at most one REST read (budget-gated) and one status query at +5 s and +20 s, restarted (not stacked) by a newer command, cancelled from `coordinator.async_shutdown` (called on unload). Brew mode select writes `workMode` only, without power. F-06, F-07. |
| #232 | OK (INFO) | Slot labels: options flow (admin only), length <= 40, stripped, dedup/reserved checks, stored in `entry.options`, display-only (`labels` attribute); never put in a frame or command. F-10. |
| #233 | OK (LOW) | Frame capture is DEBUG only, device id + 20-byte frame hex, no credentials. History bounded per kind but number of kinds is not. F-08, F-09. |
| #234 | Changes needed before merge (MEDIUM) | `govee.request_status`: input schema fine, device resolution limited to loaded Govee entries, respects the #195 quarantine, cancels bursts on unload; but no rate limit on the one-shot / restart path, ignores `MQTT_STATUS_QUERY_EXCLUDED_SKUS`, weak drop attribution, registered for all users. F-01, F-02. |
| #235 | Decline is fine; no blocker found | Keep-warm is opt-in (`DEFAULT_KETTLE_FRAME_CONTROL = False`), entities only exist while on and are removed by orphan cleanup when off, writes only on switch/select action, no frame resend loop (confirmation sends <= 4 status queries over 30 s), pending checks cancelled on unload, H7175-only. F-05. |

Secrets / PII in the stack: none found. Tests and `docs/_research/2026-09-30_h7175-kettle.md` use synthetic IDs
(`AA:BB:CC:DD:71:75:00:01`, `AA:BB:CC:DD:EE:FF:00:11`), topic `GD/kettle`; no emails, tokens, certificates, account
ids, IPs or real topics. The verbatim push sample carries only `onOff`, `sta`, `result` and status frames (the
`aa 23 ... 6366c9d5e5` bytes look like a 2022 timestamp, not an identifier). Diagnostics gain `recent_frames` (frame
hex + time) and `kettle_base_frame`: no secrets.

## Findings

### F-01 MEDIUM: `govee.request_status` has no rate limit on the one-shot and restart paths (#234)

- Location: #234 `custom_components/govee/services.py` `async_request_status_handler`; `custom_components/govee/status_burst.py` `StatusBurst.start` (`_arm(..., delay=0)`); registered with `hass.services.async_register` (not admin).
- Scenario: an automation or script calls `govee.request_status` with `duration: 0` in a `repeat` without delay, or re-calls it with `duration > 0` (each `start()` stops the old burst and queries immediately, so `STATUS_BURST_MIN_INTERVAL` is never applied across calls). Bursts for many devices also run concurrently (N devices x one query per 3 s). Any authenticated HA user, not only admins, can call it.
- Impact: unbounded MQTT publishes on the account's AWS IoT session. AWS IoT answers refused publishes by closing the session (#195), so a loop flaps real-time updates for every device and risks Govee throttling or flagging the account. No REST budget is spent, so the existing budget guards do not apply.
- Fix: enforce a per-device minimum spacing (>= `STATUS_BURST_MIN_INTERVAL`, measured from the last query actually sent, also across `start()` calls and one-shots) and a global cap (e.g. a token bucket of a few queries per second, or <= 3 concurrent bursts per entry) inside `GoveeCoordinator.async_request_status` so every caller (service, burst, kettle follow-ups, #245 confirmer) inherits it; raise `ServiceValidationError` (or silently coalesce) when throttled. Consider `async_register_admin_service` like `send_raw_ptreal`.

### F-02 MEDIUM: `async_request_status` bypasses the #195 protections other than the quarantine set (#231/#234)

- Location: #234 `coordinator.py` `status_query_possible` / `async_request_status` (lines ~3731-3760 at refs/pr/235); compare `_mqtt_status_poll_targets` (~3166) and the sweep (`_poll_mqtt_status`, ~3260).
- Scenario: (a) `status_query_possible` does not check `MQTT_STATUS_QUERY_EXCLUDED_SKUS` (H5110, H5220, H5111, H5075, H5074) or `device.is_group`, so the service queries SKUs already known to make AWS IoT drop the session. (b) The sweep keeps `_status_query_in_flight` set for `MQTT_STATUS_QUERY_SPACING` after the publish; `async_request_status` clears it in `finally` right after the publish returns, so a drop that arrives a moment later is not charged and the quarantine never engages for service/burst queries (a 120 s burst can drop the session ~40 times). (c) When a sweep query is in flight, a concurrent service query is not attributed, so a drop it causes is charged to the sweep's innocent device, which can get quarantined. (d) The user's "status re-query = 0" setting is ignored by the kettle follow-ups (automatic, not user-initiated).
- Impact: repeated account-wide session drops, wrong-device quarantine, extra AWS IoT traffic the user turned off.
- Fix: make `status_query_possible` mirror `_mqtt_status_poll_targets` (not group, topic known, not quarantined, SKU not excluded); serialise all status queries through one lock with the sweep and hold the in-flight marker for `MQTT_STATUS_QUERY_SPACING` after the publish; skip automatic (non-service) queries when the re-query interval is 0. Add tests for an excluded SKU and for a drop after a service query earning a strike.

### F-03 HIGH (design constraint, T-022/T-023): #245 resend must never re-power heating appliances

- Location: plan T-022 notes ("background task per command (power/brightness/colour/CT) ... Old value at window end -> resend once over the cloud API"), T-023 ("Hook after the MQTT tier and REST success in async_control_device").
- Scenario: the hook sits in `async_control_device`, which also carries `PowerCommand` for H7175/H717A/H7170 kettles, heaters and other appliances. User turns a kettle on from HA; no confirming frame arrives in the window (kettle pushes nothing until asked, or the user lifted it / pressed its button / turned it off in the app meanwhile, which "last command wins" does not see because it only tracks HA commands); the confirmer resends power-on over the cloud.
- Impact: kettle or heater switched on (heating) without a current user action, possibly unattended. Physical-safety relevant.
- Fix: limit confirm-and-resend to light-type devices (`devices.types.light`, not appliance/kettle/heater/humidifier, not `decodes_kettle_frames`) or at minimum never resend `PowerCommand(power_on=True)` to non-lights; resend only when a frame received after the command still shows exactly the pre-command value and no other state change (push, app echo, poll) for that field has been seen since; kettles keep their own #231 follow-up and are skipped by the confirmer.

### F-04 MEDIUM (design constraints, T-022..T-024): #245 abuse and budget rules

- Location: plan T-022/T-023/T-024.
- Constraints the implementation must meet (each with a test):
  1. Request budget: a resend or fallback `/device/state` read runs only if `requests_today` stays under the configured daily budget, `rate_limit_remaining` keeps the 20-request reserve, and no 429 back-off is active (reuse `extra_cloud_read_allowed`); otherwise give up and count `skipped_budget`. At most one resend and one read per command (`resends` option, if added, capped at 3).
  2. No loops: the resend goes through an internal path that does not re-enter the confirmer (no confirm of a resend, no resend of a resend), and does not trigger the #231 kettle follow-up.
  3. Status queries: at most one per command, never to quarantined devices, `MQTT_STATUS_QUERY_EXCLUDED_SKUS`, groups, after the #259 account-wide refusal, or when the re-query interval is 0; never while a sweep or another query is in flight; go through the rate-limited, attributed path from F-01/F-02 (do not reuse today's `async_request_status` as-is).
  4. Supersession: latest command per device/field cancels the pending task before the new command is dispatched; `_pending` keyed by (device, field) so it stays bounded.
  5. Lifecycle: tasks created with `entry.async_create_background_task` and cancelled in `async_shutdown`; timers cancelled on unload; option default off (`CONF_CONFIRM_COMMANDS = False`).
  6. Matching uses only frames received after the command was sent.
  7. Logging: debug only per command, warning at most once per device per window for give-ups; no payloads containing account data; diagnostics counters only (no frames needed).

### F-05 LOW: keep-warm duration taken unclamped from the kettle's report (#235)

- Location: #235 `custom_components/govee/kettle/control.py` `async_set` (`minutes = state.kettle_keep_warm_minutes or DEFAULT_KEEP_WARM_MINUTES`); decoded from the u16 in `aa 22` / `3a 22` (`frames.py::_keep_warm`).
- Scenario: the switch's turn_on sends whatever duration was last reported (0-65535 min), including from a `3a 22` echo of another client's command.
- Impact: keep warm could be requested for far longer than the app's 120 min maximum if the kettle reports or accepts an odd value. Firmware likely clamps; defence in depth only. PR is being declined.
- Fix (if ever revived): send only values in `KEEP_WARM_DURATIONS`; otherwise use `DEFAULT_KEEP_WARM_MINUTES`.

### F-06 LOW: kettle follow-ups query even when the user turned status re-query off (#231)

- Location: #231 `kettle/manager.py` `_async_followup_read` -> `coordinator.async_request_status`.
- Impact/fix: see F-02 (d); gate on `_mqtt_status_poll_enabled`.

### F-07 INFO: optimistic kettle values held over disagreeing cloud reads (#231)

- `KETTLE_PROTECT_SECONDS = 45` keeps `power_state` and target from a command over cloud reads that disagree. If the kettle refused a power-on (e.g. off its base) HA shows "on" for up to 45 s; a refused power-off shows "off" while it may still heat. A push that disagrees overrides it. Acceptable, but consider letting a cloud read that reports `power_state=True` after a power-off command win immediately (fail towards showing "heating").

### F-08 LOW: frame history kinds are unbounded (#233)

- Location: #233 `kettle/manager.py` `_record_frames` (`by_kind.setdefault(kind, deque(maxlen=10))`); runs on every frame before checksum/length validation.
- Impact: a device (or anything publishing on the account topic) sending frames with many distinct 3-byte prefixes grows memory and diagnostics without bound.
- Fix: record only 20-byte checksum-valid frames and cap the number of kinds per device (e.g. 64, evicting the oldest kind).

### F-09 INFO: capture logger inherits integration debug logging (#233)

- `custom_components.govee.kettle.capture` is a child of `custom_components.govee`, so it is on whenever a user enables integration debug logging; one line per distinct frame (each temperature change while heating). Logs device id (already logged elsewhere at debug) and frame hex; no credentials or tokens. Acceptable; optionally set `propagate`/level so it is opt-in only.

### F-10 INFO: slot labels accept any characters (#232)

- `kettle/labels.py`: length and uniqueness checked, control characters/newlines not rejected. Display-only attribute (frontend escapes), admin-only flow. Optional: reject `\x00-\x1f`.

### F-11 MEDIUM (porting, T-020): holger-dunst's #223 patch contains an out-of-scope hunk to `docs/release-replies.md`

- Location: #223 comment 2026-10-03, `diff --git a/docs/release-replies.md` (deletes the queued #211, #186, #85 reply entries).
- Scenario: the file is the input the daily-release workflow's Claude Code action reads to post public replies and close issues. Applying the patch wholesale deletes (or on current main conflicts with) the reply entries this plan queues. The hunk is likely an artefact of the author's local tree (main already cleared those entries in 82cbd92), but any third-party edit to that file is an injection surface into the release bot.
- Fix: port only `api/ble_packet.py`, `const.py`, `coordinator.py`, `light.py`, `models/state.py`, `icons.json`, `strings.json`, `translations/en.json` and the two test files; never apply the release-replies hunk.

### F-12 LOW (porting, T-020/T-021): ring mask and frame bounds

- Location: patch `coordinator.py` `async_set_ring` (`mask = (1 << device.segment_count) - 1`), `build_segment_color_temp_ptreal`, `update_light_zones_from_frames`.
- Scenario: `segment_count` is API-derived; if it ever reports 17+ the ring mask includes bit 16 (the main panel) and the "ring only" write also changes the panel; 0 gives an empty mask. Kelvin is clamped in the entity but not in the builder (`kelvin >> 8 & 0xFF` wraps above 65535). `aa 30` is parsed without length-20/checksum validation.
- Fix: ring mask = `(1 << PTREAL_MAIN_PANEL_BIT[sku]) - 1` (bits 0-15) or clamp `segment_count` to that; clamp kelvin to `PTREAL_ZONE_MIN/MAX_KELVIN` in the builder; parse `aa 30` only from 20-byte checksum-valid frames.

### F-13 INFO (porting, T-020): zone toggles use the AWS IoT passthrough without the MQTT-control opt-in

- `_try_ptreal_light_zone` runs before the opt-in MQTT control tier, so H1252 toggles go over ptReal for every account-login user even with `enable_mqtt_control` off. Same precedent as `_try_mqtt_music_mode`; SKU-locked to `PTREAL_LIGHT_ZONE_SKUS = {"H1252"}`, so acceptable. Its REST fallback returns success while the device ignores it (reporter's finding): correctness, not security.

### F-14 LOW: `govee.send_raw_ptreal` exposure

- Location: main `custom_components/govee/services.py` (`async_register_admin_service`, `async_send_raw_ptreal_handler`); `coordinator.async_send_raw_ptreal`.
- Current state: admin-only; schema validates hex, <= 20 bytes, XOR checksum on 20-byte frames; device resolved only among loaded Govee entries; groups refused; requires the passthrough; debug-only logging. No rate limit (admin-only, acceptable).
- Residual risk: it can send any frame to any device of the account, including heating appliances (e.g. a kettle's `3a 22` keep-warm or heat frames), and issue replies (#223, #239) tell reporters to run frames they did not write.
- Fix: keep it admin-only; consider refusing it for heating appliances (`decodes_kettle_frames`, heater/kettle device types) unless a `force` flag is set; in issue replies give only frames verified for the reporter's SKU and never frames for heating devices; optionally add a simple per-device spacing (as F-01).

## Porting checklist for T-020 / T-021 (holger-dunst #223 patch)

1. Port file by file from a reviewed copy; drop the `docs/release-replies.md` hunk (F-11) and anything not listed in the task `files`.
2. Confirm the patch adds no endpoints, URLs, logging of payloads or account data (verified: none; only ptReal frames via the existing `_ble_manager.async_send_ble_packet`) and stays SKU-locked (`H1252` in `PTREAL_SEGMENT_SKUS`, `PTREAL_MAIN_PANEL_BIT`, `PTREAL_LIGHT_ZONE_SKUS`); H1232 behaviour unchanged (REST toggles), no other SKU gains the zone path.
3. Harden bounds: fixed 16-bit ring mask, kelvin clamped in the builder, `aa 30` parsed only from 20-byte checksum-valid frames (F-12).
4. Keep golden frames exactly as captured (`33 30 <zone> <on>`, `33 05 15 01 FF FF FF <K> <RGB> <mask>`, `aa 30 <main> <ring>`) and test that a ring write never sets bit 16 and a panel write never sets bits 0-15.
5. Credit with Co-authored-by (noreply id from `gh api users/holger-dunst`), and do not run anything from the comment; tests in the patch use synthetic IDs (`AA:BB:CC:DD:EE:FF:12:52`) and no network/exec calls (verified).
