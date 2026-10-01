# Research: #222, #220, #186 (issue sweep, Oct)

## #222: MQTT connected, no frames since 2026-09-26 19:11 UTC (H5044 + H5310)

**Class:** probably on Govee's side (no fix on our side brings the frames back). Two small code fixes: diagnostics, and the connection_mode attribution.

**Root cause (what we can rule out):**
- Not caused by a release of ours. v2026.9.14 was tagged on 2026-09-24 at 20:22 EDT, and its MQTT/coordinator commits (b7a7a49 H5310 byte-14, 83fa603 music ptReal, ec22b8d H5074 sweep exclusion, 12ae345 poll cadence) don't touch subscribing or receiving. The frames stopped about 2 days later, partway through a session. Nothing in v2026.9.15 (8e7de04, f247b61, ...) touches the receive path either.
- Frames are not reaching the client at all. They aren't being filtered out. `_handle_multisync` records every decoded packet before it filters anything (`api/mqtt.py:985-990` → `_record_multisync` :871). So an empty `recent_multisync` after 22 h means no multiSync arrived on the account topic. `tracked_devices: 0` means no `state` message arrived for any device either, not even a status-sweep reply from the H5044.
- Subscription refusal is ruled out. A SUBACK 0x80 raises an error and reconnects (`api/mqtt.py:606-609`), and the reporter's session shows 0 failures.
- A client-id collision is unlikely. The MQTT id is `AP/{accountId}/{_derive_client_id(email)}` (`api/auth.py:1693-1695`), the same on every instance using that email. A second instance would knock the sessions off in turn, but this session ran 22 h without dropping.
- Remaining explanations: the gateway is no longer routed to this account topic on Govee's side, or something tied to the stored cert/topic. The reporter's account BFF poll still gets hourly values, so the token is fine and `_async_refresh_iot_credentials` (`coordinator.py:1930`) never re-logs in.
- The one remaining thing to try costs nothing in code: **Reconfigure (a fresh login, with a 2FA code)**. It writes new `entry.data[KEY_IOT_CREDENTIALS]`, and `async_restart` (`api/mqtt.py:433`) swaps the cert/topic if they changed.

**Secondary bug (the reporter's connection_mode observation):** `_is_delivering` (`sensor.py:83-90`) only requires `is_available and last_success_ts`. After a reconnect, `refresh_mqtt_for_devices` (`transport_health.py:76-98`) sets `is_available=True` again, and the old `last_success_ts` from the previous session still counts. So the sensor keeps reading `mqtt` with no frames arriving.

**Fix per file:**
1. `sensor.py` `GoveeConnectionModeSensor._active_transport` (~:966-985): for `kind == "mqtt"`, also require `health.last_success_ts >= coordinator.mqtt_connected_since`. Add a coordinator property `mqtt_connected_since` next to `mqtt_last_message_ts` (`coordinator.py:646`) that returns `self._mqtt_client.connected_since` (`api/mqtt.py:426`). With this, a frame from the current session is required before the sensor reads `mqtt`.
2. `api/mqtt.py` `_handle_message` (:723): add `self._inbound_total += 1` and `self._last_inbound_ts = now` at the very top, before any filter (the "msg"-wrapped and missing-device-id messages are dropped today without a timestamp). Expose them as properties.
3. `diagnostics.py` mqtt block (:262-274): add `inbound_messages`, `last_inbound_at`, and `last_device_message_at` (`mqtt_client.last_message_ts`). With these a download can tell a completely silent account topic apart from a gateway that has stopped pushing.
4. Not now: a deaf-session watchdog (force a reconnect after N h with no inbound traffic). The reporter's fresh session didn't help, and a forced re-login risks triggering 2FA. Revisit after the Reconfigure result.

**Tests:** `tests/test_connection_mode_sensor.py`: MQTT stamped before `connected_since` → `cloud_api`; MQTT stamped after it → `mqtt`. `tests/test_cov_mqtt*.py` / mqtt tests: the inbound counter goes up for a "msg"-wrapped message and for one with no device. `tests/test_diagnostics*.py`: the new keys are present and a None timestamp passes through `_iso`.

**Verify grep:** `mqtt_connected_since`, `_inbound_total`, `last_inbound_at`, `inbound_messages`.

**Reply brief:**
1. Nothing on our side changed when your frames stopped, and your diagnostics show the session received no messages at all (no multiSync, no status replies), so the integration isn't dropping them. They never reach it.
2. Next step, please: Reconfigure → re-enter the Govee login (you'll get an email code). That gets fresh AWS IoT credentials, the last thing on our side that could matter. Then send a diagnostics download after ~1 h.
3. The connection_mode sensor will no longer read `mqtt` after a reconnect until a frame arrives in the new session (fix in the next release).

---

## #220: H605B DreamView T1 Pro, "Power Off not working"

**Class:** probably a SKU-scoped code fix, but we need data first (which entity, what the light does).

**Evidence (diagnostics attachment, downloaded to scratchpad):**
- `recent_commands` (buffer of 30, `api/client.py:64`) contains only the REST call `dreamViewToggle` 1→0→1→0 at 08:53:59–08:54:23, all answered `success` with `dreamType: movie`. There is no `powerSwitch` command, and `mqtt.last_sent` is null. So the reporter used the **DreamView switch**, not the light entity. (The device itself is named "DreamView", which invites that confusion.)
- `last_mqtt_message` at 08:55:36 (73 s after the final toggle-0) has the op frame `aa05 00 ...`: mode byte `0x00` is video/DreamView (`docs/govee-protocol-reference.md:1461`, :1501). So the light **was still in video mode after the toggle-0**, which matches #213: the REST toggle is accepted but does nothing (here for OFF, while ON works). The same frame reports `onOff: 0`, and the poll reports `powerSwitch: 0`. Two readings fit: the user powered it off from the app or remote, or the H605B reports onOff 0 during DreamView. In the second case HA shows the light as off while the backlight is syncing.

**Root cause (likely):** `coordinator.py:5237-5253` `async_send_dreamview`. For OFF, the REST `dreamViewToggle 0` returns success and the method returns True at :5248 before it reaches the colour-restore branch (:5261-5279). That branch is the only thing proven to take a light out of video mode ("the device leaves video mode as soon as it is given another mode"). For the H66A0 the whole REST tier is skipped via `PTREAL_DREAMVIEW_SKUS` (`const.py:420`). That set can't simply be reused: ON works over REST on the H605B, and adding it would send ON to the BLE video frame path instead.

**Fix per file:**
1. `const.py` (after :420): `DREAMVIEW_OFF_VIA_COLOUR_SKUS: Final = frozenset({"H605B"})`, with a comment citing #220 (REST toggle-0 is accepted, but the light stays in `aa 05 00` video mode).
2. `coordinator.py:5239`: change the gate to `if sku not in PTREAL_DREAMVIEW_SKUS and not (not enabled and sku in DREAMVIEW_OFF_VIA_COLOUR_SKUS):` so that OFF on the H605B falls through to the existing colour restore. ON keeps the REST path. Import the new const at :116.
3. `docs/govee-protocol-reference.md`: add an H605B note next to H66A0 (:2160).

**Tests:** `tests/test_cov_coordinator_control.py`, next to `test_h66a0_*` (:908-933):
- `test_h605b_on_keeps_the_rest_toggle`: `_sent == [dreamview(True)]`.
- `test_h605b_off_restores_the_last_colour_instead_of_the_toggle`: `_sent == [ColorCommand(last_color)]`, `dreamview_enabled is False`, no dreamview REST command.

**Verify grep:** `DREAMVIEW_OFF_VIA_COLOUR_SKUS`, `"H605B"` in const.py and the tests.

**Reply brief:**
1. Your diagnostics show the DreamView switch sending on/off and Govee accepting both, yet 70 s after "off" the light still reported video mode. Govee ignores the off toggle for the H605B, as it did with the H66A0 (#213).
2. Fix: DreamView off on the H605B now leaves screen sync by restoring your last colour. To turn the backlight off completely, use the light entity, not the DreamView switch.
3. Please confirm: was the 08:55 power-off done from the app or remote? And while DreamView is running, does HA show the light as on or off?

---

## #186: H6022 music mode works now, but "Spectrum" looks different from the app

**Class:** needs data. A likely code fix is ready once one diagnostics download confirms it.

**Current mapping:** `api/ble_packet.py:113-171` maps the music mode by name to app codes (`rhythm 03, spectrum 04, energic 05, rolling 06`). Legacy effects get the tail `00 00` (style 0, fixed colour off, no RGB). The send happens in `coordinator.py:4489` `_try_mqtt_music_mode` (called at :4585) for `MQTT_MUSIC_MODE_SKUS` (`const.py`, H6022/H612F).

**Two candidate causes:**
1. **The H6022 may number Spectrum and Rolling differently.** Its API list is `Energic 5, Rhythm 3, Spectrum 6, Rolling 4` (`docs/govee-protocol-reference.md:2968`). Every other model lists sequential positions (0/1-based); this one is unordered, and Energic=5 and Rhythm=3 exactly match the app codes. That suggests the H6022's API values are device codes, with Spectrum=0x06 and Rolling=0x04, the reverse of teh-hippo's table. teh-hippo's Spectrum=0x04 and Rolling=0x06 come from H6199 captures (`aa0513040000012060a0…`, `aa051306630001a06020…`), a different model. If so, HA "Spectrum" plays Rolling on the H6022. That fits "Spectrum differs a lot, Energic only slightly".
2. **Colour tail.** The app writes Spectrum and Rolling with a fixed colour (`<style> 01 R G B`; teh-hippo `h617a-music-implementation.md`: "Spectrum/Rolling fixed colour; Energetic no-edit"). We send `00 00` (auto). This would explain a palette difference rather than a different effect.

**Data needed (settles both):** with the account login active, the H6022's MQTT status carries `aa 05 13 <effect> <sens> <style> <fixed> R G B` in `last_mqtt_message._op_frames`. Ask for: (a) Spectrum set in the **Govee app** → wait 1 min → device diagnostics; (b) Spectrum set from HA → diagnostics. Quick test to ask for at the same time: does HA's **Rolling** look like the app's **Spectrum**?

**Fix once confirmed:**
- For cause 1: `api/ble_packet.py`, a per-SKU override `MUSIC_V3_SKU_EFFECT_OVERRIDES: dict[str, dict[str, int]] = {"H6022": {"spectrum": 0x06, "rolling": 0x04}}`. Make `music_v3_effect_code(name, sku)` consult it, and pass `device.sku` at `coordinator.py` `_try_mqtt_music_mode`.
- For cause 2: extend `build_music_mode_v3_packet(effect_code, sensitivity, rgb: int | None = None)`. For Spectrum/Rolling with `command.auto_color == 0 and command.rgb`, write `00 01 R G B`. Otherwise copy the app's captured tail.
- Tests: `tests/test_ble_packet.py` (the override yields the 0x06 byte for H6022 Spectrum and the default 0x04 for others; RGB tail bytes), and `tests/test_cov_coordinator_control.py` music tests (`async_send_music_mode_v3` awaited with 0x06 for H6022 Spectrum).
- Verify grep: `MUSIC_V3_SKU_EFFECT_OVERRIDES`, `music_v3_effect_code(`.

**Reply brief:**
1. Glad the lamp responds now. The going-dark bug is fixed by the AWS IoT frame plus your login.
2. On Spectrum: your lamp's API numbers Spectrum and Rolling the other way round from other Govee lights, so HA's "Spectrum" may be playing Rolling. Does HA's **Rolling** match the app's Spectrum?
3. To settle it: pick Spectrum in the Govee app, wait a minute, and send a device diagnostics download (the "Download diagnostics" button). The lamp's own report there shows the exact code and colour the app uses, and I'll match it.
