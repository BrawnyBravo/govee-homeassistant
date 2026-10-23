# Security review: fork PRs in issue-sweep-late-oct

Scope: Python code (custom_components/, tests/) of #238, #247, #248, #250, #251, #252, #253, #254, #255, #257, #259.
Base: main @ 82cbd92. Diffs: `git diff main...refs/pr/N`. Line numbers are in the PR head (`git show refs/pr/N:<path>`).

## Verdicts

| PR | Verdict | Highest |
|----|---------|---------|
| #238 | clean | none |
| #247 | clean (optional LOW hardening) | LOW |
| #248 | clean | INFO |
| #250 | clean; 3 LOW fixes are cheap, worth applying in the merge | LOW |
| #251 | fix before merge (MEDIUM re-login latch; LOW retry classification) | MEDIUM |
| #252 | clean (LOW pre-existing LAN trust note) | LOW |
| #253 | clean | INFO |
| #254 | clean | INFO |
| #255 | clean (privacy improvement) | none |
| #257 | fix before merge (one-line condition change, safety) | LOW |
| #259 | clean | INFO |

No CRITICAL/HIGH. No new hosts, no TLS changes, no secrets in new logs, diagnostics, repairs or Store files, and no real credentials or personal data in any test fixture.

## #238 (H5108 status-sweep exclusion)

No findings. One SKU added to `MQTT_STATUS_QUERY_EXCLUDED_SKUS` (const.py:369); this only removes MQTT publishes. Test uses synthetic IDs.

## #259 (stop status sweep on account-wide AWS IoT refusal)

No findings. `_status_query_unanswered_skus` is bounded by the number of SKUs on the account and cleared after any answered query; the new flag only stops publishes (reduces traffic). Warning logs device name + SKU, which existing warnings already do. Diagnostics adds a bool only. Tests use synthetic IDs.

- INFO (merge note, with #247): #247 adds a `power_monitoring_only` path to `_poll_mqtt_status`. When both land, keep the `self._status_queries_refused` check in the top guard of `_poll_mqtt_status` so it also stops the 60 s H5086 ticks.

## #248 (H8057 segment 4 over ptReal)

No security findings. The ptReal packet is built only from a validated `RGBColor` and a constant mask; `_segment_locks` is keyed by an internal device_id; the passthrough uses the existing AWS IoT client (no new host).

- INFO: coordinator.py `_control_h8057_segment_color` raises a plain English `HomeAssistantError` instead of a translated one (CLAUDE.md convention). Not a security issue; switch to `translation_key` during the merge if wanted.

## #247 (H5086 energy counter, 60 s status tick)

- LOW: models/energy_counter.py `EnergyCounter.from_dict` accepts naive datetimes from restore state. `update()`/`rebooted()` then do `now - self.updated` / `now - self.reboot_seen` with an aware `dt_util.utcnow()`, raising `TypeError` inside `_handle_coordinator_update`. HA's `async_update_listeners` doesn't catch per-listener exceptions, so one bad restored row can break listener fan-out on every refresh. Only reachable through a hand-edited/corrupt `.storage/core.restore_state`, so low. Fix: in `from_dict`, return None when any parsed datetime has `tzinfo is None` (or `.replace(tzinfo=UTC)`), and have `_track_reading` wrap `update()` in `try/except (TypeError, ValueError)` that resets `self._counter = None`.
- INFO: query rate: whenever any power-monitoring outlet exists, the status timer ticks every 60 s whatever the configured `mqtt_status_interval` (only 0 disables it). These are AWS IoT QoS-0 publishes to the outlets only (no REST quota) and match the app's cadence; the quarantine/exclusion lists still apply via `_mqtt_status_poll_targets`. Acceptable; maybe note in the option description that H5086 outlets are queried every minute.
- Parsing of `sta.stc` (`uptime_from_sta`, `answers_other_client`) is type-checked and `int()` failures are caught. Tests: synthetic data, `token="tok"` placeholder only.

## #250 (persisted request counts, single-attempt control, 429 handling)

Store `govee.<entry_id>.request_counts` holds only `{day, today, buckets}`; no secrets; removed in `async_remove_entry`. `import_request_counts` type-checks every field (non-bool non-negative ints, today's UTC day only), so a corrupt file can't disable limits: it can only under-count back to the pre-PR behaviour (count from zero) or over-count (more conservative pacing). Single-attempt control POSTs and the per-device topic-refetch throttle reduce request volume.

- LOW: api/client.py `import_request_counts` keeps buckets with `hour >= cutoff` but no upper bound. A future hour (clock stepped backwards after an NTP fix, or a tampered file) stays at the deque's tail; `_note_request` then appends the current hour after it, breaking the sorted order its `popleft` pruning relies on, and inflates `requests_last_24h` until that hour passes. Fix: also require `hour <= int(now // 3600)` in the bucket filter.
- LOW: __init__.py `_async_attach_request_counts_store` calls `await store.async_load()` unguarded. HA renames a corrupt JSON file and returns None, but a file with a different `version`/`minor_version` and no migrate function raises `NotImplementedError`, so setup fails instead of starting from zero (contradicting "a bad file can only ever under-count"). Fix: `try: saved = await store.async_load() except (HomeAssistantError, NotImplementedError, ValueError): _LOGGER.debug(...); saved = None`.
- LOW (pre-existing, touched here): api/client.py `_parse_retry_after` returns `float(value)` unbounded, so `Retry-After: inf` makes coordinator.py `int(err.retry_after)` raise `OverflowError` after `_rate_limited` is set, and a huge finite value (e.g. `1e9`, or a far-future HTTP date) sets the poll interval to years, stopping polling until reload. The header comes from Govee over TLS, so this is robustness against a misbehaving upstream/proxy, not an attack. Fix: `if not math.isfinite(seconds) or seconds <= 0: return None; return min(seconds, 3600.0)`.
- Tests: `API_KEY = "12345678-1234-1234-1234-123456789abc"` placeholder, no real credentials.

## #251 (login/MQTT recovery, BFF parsing hardening)

What's fine: no new hosts or URLs; no TLS changes; login credentials still go only to the fixed Govee login URL through `GoveeAuthClient`; `_raise_if_unauthorized` puts only the body's `message` (never the token) into the exception; login warnings still go through `_sanitize_response_for_logging`; the inbound account-topic debug log is now truncated to 30 chars like the other topic logs (mqtt.py:791, an improvement); `_as_dict`/`_bff_devices` remove a class of type-confusion crashes on odd BFF bodies; `_shut_down` stops timers re-arming and a late login result from acting on a reloaded/removed entry; the OpenAPI SUBACK error message doesn't include the `GA/<api_key>` topic. The background retry re-derives `client_id` from the email as setup does, and on success persists through the existing `_persist_refreshed_credentials` (entry.data, as before).

- MEDIUM (pre-existing, widened by this PR): coordinator.py `_async_refresh_iot_credentials` (unchanged code) re-runs a full password login every `IOT_RELOGIN_MIN_INTERVAL` (15 min) whenever a BFF call gets a `GoveeAuthError`, and never latches after a definitive answer: after `Govee2FARequiredError`, `GoveeAuthError` (password changed in the app) or `GoveeLoginRejectedError` (now also what a 401 on the IoT-key step becomes, auth.py:1645) it only raises a repair and tries again 15 minutes later. That's up to ~96 password logins a day against an account that's already refusing them, which is the pattern the PR's own docstring says trips Govee's 2FA hardening. This PR widens the trigger: `_raise_if_unauthorized` now turns 401s from `fetch_device_topics`/legacy device list/IoT key into `GoveeAuthError`, and the H5054 water-detector poll now goes through `_async_bff_call` (coordinator.py `_poll_water_detectors`), so more call sites can start a re-login. A login that succeeds but leaves one endpoint 401-ing also repeats every 15 min. Fix (small, uses helpers this PR adds): in `_async_refresh_iot_credentials`, on `Govee2FARequiredError` call `self._persist_login_failed(LOGIN_FAILED_2FA)`; on `GoveeAuthError`/`GoveeLoginRejectedError`/`Govee2FACodeInvalidError` call `self._persist_login_failed(str(err))`; in both cases set an in-memory `self._relogin_disabled = True` checked at the top (Reconfigure clears the marker and reloads). Optionally double the re-login interval after each re-login that didn't stop the 401s.
- LOW: auth.py `is_connection_error` (line ~30 of the hunk) treats any `aiohttp.ClientError`, or a `GoveeApiError` caused by one, as network-level. `aiohttp.ContentTypeError`/`ClientResponseError` are `ClientError` subclasses, and `login()`/`get_iot_key()` call `response.json()` before checking non-401 statuses. So an HTML 403/429/5xx page (WAF, rate limit, maintenance) at setup is classified "network" and the background retry repeats the full password login (5 min doubling to 6 h, ~10/day), contrary to the stated rule that only DNS/refused/reset/timeout is retried. Fix: `def _is_net(e): return isinstance(e, (aiohttp.ClientError, TimeoutError)) and not isinstance(e, aiohttp.ClientResponseError)` and apply it to both `err` and `err.__cause__`.
- INFO: __init__.py now re-raises the "account sign-in failed: {login_failed}" repair on every start from the persisted `KEY_IOT_LOGIN_FAILED` string. That string is `str(err)` of login exceptions (Govee body `message`, aiohttp host/port text), with no email/password/token found on any path I traced. Keep it that way: never put request payloads or headers into login exception messages.
- Tests: `user@example.com` / `pw` / `tok` placeholders; `"SECRET-TOKEN-XYZ"` is a synthetic redaction-test value. No real data.

## #252 (LAN client hardening, BLE MAC binding, idle BLE disconnect)

BLE: `handle_advertisement` now enrols a single same-SKU candidate only when the advert's address equals the MAC derived from the cloud device ID, and never re-points an enrolled device to another address (ble_advertisement.py:200-215, 273-275). That closes the neighbour-light enrolment hole (before, any same-model advert in range was enrolled and received the owner's commands). `_mac_mismatch_logged` is bounded by the account's devices. The idle-disconnect path clears `_session` along with `_client`, and `_ensure_connected` renegotiates (or drops the link) before any write, so no plaintext fallback.

LAN: `RecursionError` is caught on every `json.loads` of a datagram; `_coerce_int`/`_parse_color` also catch `OverflowError`; the new `async_scan` reuses the persistent :4002 socket and allows one scan at a time; the setup retry backs off 300 s to 3600 s and checks `_lan_closed` so no socket outlives unload. `sendto` failures reported via `error_received` now count as failed sends.

- LOW (pre-existing, not addressed by the "hardening"): api/lan.py `_ScanProtocol.datagram_received` takes the device's address from the body's `"ip"` field (`record.setdefault("ip", addr[0])` only fills it when absent), and keys `responses` by the attacker-supplied `"device"` string with no cap. Any LAN host can answer a scan claiming the owner's device MAC with any `ip`, so LAN commands for that device go to that IP and devStatus from it is accepted as the device's state. Govee's LAN protocol is unauthenticated, so this is inherent, but the PR description's "hardening" doesn't include it. Fix: prefer the datagram source (`record["ip"] = addr[0]`, keep the body value only for diagnostics) and cap `responses` (e.g. stop recording after 256 entries); with `async_scan` all datagrams on the persistent socket now feed the collector during a scan.
- INFO: BLE addresses are trivially spoofable by a nearby attacker, so MAC binding stops accidental cross-enrolment, not a deliberate attacker. Nothing more to do in this PR.
- Tests: synthetic MACs (`AA:BB:CC:DD:EE:FF`, `11:22:33:44:55:66`), no credentials.

## #253 (heater target restore in Celsius)

No security findings. The restored target is clamped to the entity's min/max before it is seeded into `state.heater_temperature`, and a legacy display-unit state outside the range is discarded, so a restore can't send an out-of-range heater setpoint. The polled value now wins over the preserved one.

- INFO: number.py `async_added_to_hass`: `float(last.native_value)` of a NaN (only from a hand-edited restore file) passes the `min(max(...))` clamp unchanged and `round(nan)` raises `ValueError`, failing the entity add. Optional: `if native is None or not math.isfinite(native): return`.
- Tests: no credentials.

## #254 (segment brightness, scene refresh signal, brightness scaling)

No security findings. New `SegmentBrightnessCommand` values come from `ha_to_device_brightness`, which clamps into the device's range; it uses the same per-device segment queue as colours. Scene refresh rebuilds options from the same Govee catalog the selects already trusted; the dispatcher signal is per device id. `async_clear_scene` failures now raise instead of being swallowed.

- INFO: services.py `refresh_scenes` without a device now refreshes scenes and DIY scenes for every device that has either: up to 2 REST calls per device per invocation, where it used to be 1 per scene-capable device. User-initiated, but an automation looping it spends quota faster than before. Acceptable; no change needed.
- INFO: models/device.py `segment_brightness_range` does `int(range_data.get(...))` on API data without catching `ValueError`/`TypeError`; a malformed capability would fail entity creation for that device. Robustness only.
- Tests: no credentials.

## #255 (per-entry hub device, diagnostics redaction, scene inflight fix)

No findings; this one is a net privacy improvement. Diagnostics now redact the user-assigned device name (`_device_diag`) and leak-sensor names (`_leak_sensor_diag`), and anonymise the device-id keys of `segment_mode_by_device` in the options dump. The orphan-segment cleanup only deletes entities when the segment count comes from a trusted source (`override`/`size_max`), so a bad API response can't delete entities. The hub-device migration only touches registry entries owned by this entry. Tests: placeholder API key `12345678-1234-...` and made-up device names.

## #257 (leak MQTT wet/dry stamps persisted)

Store `govee.leak_mqtt_stamps` (global, not per entry) holds `{sensor_id: {"wet": epoch, "dry": epoch}}`: no secrets. The load filters to `wet`/`dry` numeric values, and any malformed shape or `OverflowError` falls into the broad `except`, so it never fails setup. Keys are only known sensor IDs (`_handle_leak_event` returns early for unknown `(hub, sno)`), so growth is bounded.

- LOW (safety, leak alarm suppression): coordinator.py `_poll_bff_leak_state`, `mqtt_saw_it_end = mqtt_wet_ms >= last_wet - LEAK_MQTT_SKEW_MARGIN*1000 and mqtt_dry_ms > mqtt_wet_ms`. Scenario: a leak starts flapping, MQTT reports wet at T1 and dry at T2, the sensor goes wet again at T3 ≤ T1+60 s, and that wet frame is lost (the exact case the BFF fallback exists for). The cloud's `last_wet_time` = T3, the condition still holds (the T1 stamp is within the 60 s margin and dry T2 > wet T1), so the fallback never forces wet and HA shows dry while there's water. With HA's clock ahead of Govee's by Δ, the window grows to Δ+60 s. The skew margin is applied in the suppressing direction, contrary to the comment's "errs toward a false alarm". Fix: also require that the dry report came after the cloud's wet time: `mqtt_saw_it_end = mqtt_wet_ms >= last_wet - LEAK_MQTT_SKEW_MARGIN * 1000 and mqtt_dry_ms > max(mqtt_wet_ms, last_wet)`. If HA's clock is behind, this errs toward a false alarm, which is the safe side. Add a test for wet→dry→re-wet-lost within 60 s.
- INFO: the global Store file is never removed (no cleanup when the last entry is removed), so stale sensor-id timestamps stay in `.storage`. Optional: delete it in `async_remove_entry` when no other govee entry remains.
- Tests: `token="tok"`, `refresh_token="r"` placeholders only.
