# Feature research: #224, #223, #211

| Issue | Verdict | Size |
|---|---|---|
| #224 H5059 upper/lower probe entities | **implement-now** (MQTT path); OpenAPI fallback optional | S |
| #223 H1232 16 ring segments + main panel via ptReal | **implement-now** (SKU-scoped, needs account login at runtime) | M |
| #211 H60B0 per-zone colour / relative brightness | **needs-more-data** (no write path known) | - |

---

## #224 H5059: upper / lower probe moisture entities

**How it is modelled today**
- Hub sub-devices come from the BFF roster: `GoveeLeakSensor` (frozen) + `GoveeLeakSensorState` (mutable), `models/device.py:1387-1414`.
- MQTT decode: `api/mqtt.py:_handle_multisync`, leak branch at `mqtt.py:1067`:
  `is_wet = raw[5]==1 or (len>=17 and (raw[14]==1 or raw[16]==1))`. It emits `{_leak_event, hub_device_id, sensor_slot, is_wet}` (`mqtt.py:1076-1081`). `raw[13]` (upper) is never read. Aggregate `raw[16]` already covers an upper-only trip, so the parent entity is correct.
- Coordinator: `_handle_leak_event` (`coordinator.py:2950`) maps `(hub, slot)` → sensor_id through `_sno_to_sensor_id`, sets `state.is_wet`, and fires the `govee_leak_update` dispatcher signal.
- BFF poll (`coordinator.py:~2740-2787`) only sets battery/online/last_wet_time and has a "force wet" fallback. It has no per-probe data.
- Entity: `GoveeLeakBinarySensor` (`binary_sensor.py:457`), unique_id `{mac}_leak`, `name=None`, MOISTURE, uses the dispatcher signal and is not a CoordinatorEntity. It is created per BFF sensor at `binary_sensor.py:~124`.
- OpenAPI `bodyAppearedEvent` (`coordinator.py:1856`): the H5059 is also in the Developer list (catalog: `event/bodyAppearedEvent`), so the event lands on the **developer** `GoveeDeviceState.water_leak`. No entity reads that for a BFF-rostered sensor (it is suppressed by `is_bff_leak_sensor`). `probesState` is never parsed.

**Reporter's mapping is consistent with our decoder**: same frame header `ee 34 <slot> 02 00 64`, `raw[16]`=aggregate (already used), `raw[14]`=lower (already OR'd in), `raw[13]`=upper (new). There are 4 labelled frames plus a physical test on one of 7 sensors.

**Minimal design**
1. `const.py`: `LEAK_DUAL_PROBE_SKUS: Final = frozenset({"H5059"})`.
2. `models/device.py` `GoveeLeakSensorState`: add `upper_probe_wet: bool | None = None` and `lower_probe_wet: bool | None = None` (None = not yet reported).
3. `api/mqtt.py:1067` block: when `len(raw) >= 17`, add `"upper_probe_wet": raw[13] == 1, "lower_probe_wet": raw[14] == 1` to `event_data`. Leave the aggregate unchanged. Update the `_handle_multisync` docstring byte map (byte 13 = upper, 14 = lower, 16 = aggregate).
4. `coordinator.py:_handle_leak_event`: when the keys are present **and** the sensor SKU is in `LEAK_DUAL_PROBE_SKUS`, store them. On an aggregate-dry frame (`is_wet False`), force both to False (the reporter's "clear is authoritative"). The BFF force-wet fallback leaves the probes untouched.
5. Optional, second step: in `_on_openapi_event` for `bodyAppearedEvent`, if `is_bff_leak_sensor(device_id)`, resolve the leak sensor id with `normalize_device_id` and read `probesState.top/bot` from any state_list entry (parse tolerantly, since the nesting is not shown in the issue). value 2 (clear) sets both False. This is worth doing only once we have one real event payload; `openapi_events.recent_events` in diagnostics would show it.
6. `binary_sensor.py`: new `GoveeLeakProbeBinarySensor(BinarySensorEntity)`, a copy of the `GoveeLeakBinarySensor` pattern (dispatcher signal, `leak_sensor_device_info`, MOISTURE). It takes a `probe: Literal["upper","lower"]`, unique_id `{mac}_leak_upper_probe` / `{mac}_leak_lower_probe`, and `is_on` returns the field (None means unknown). Create it in the leak loop only when `sensor.sku.upper() in LEAK_DUAL_PROBE_SKUS`.
7. Strings (`strings.json` + `translations/en.json`, `entity.binary_sensor`): `leak_upper_probe: {"name": "Upper probe"}`, `leak_lower_probe: {"name": "Lower probe"}`. Icons: optional `icons.json` `binary_sensor.leak_upper_probe/leak_lower_probe` with `default: mdi:water-off`, `state.on: mdi:water-alert` (MOISTURE already supplies icons; add them only for consistency).
8. Diagnostics: none needed. `leak_states` are dumped through `dataclasses.asdict` (`diagnostics.py:250,572`), so the new fields appear on their own.

**Tests** (`tests/test_mqtt_multisync.py`, `tests/test_water_leak.py`, `tests/test_cov_binary_sensor_event.py`)
- Decode the reporter's 4 frames: upper-wet `ee34050200641e14b86abd055c01000301800006` gives upper=True, lower=False, wet=True. Lower-wet `...05630001030180003b` gives upper=False, lower=True. The two clear frames give both False. Wet stays True for both trip frames, so there is no regression.
- Coordinator: probes stored only for H5059; an H5058 frame leaves them None; an aggregate-dry frame clears both.
- Platform: an H5059 sensor gets 2 extra entities; an H5058 gets none; unique_ids and translation keys are as above.

**Reply brief (#224)**: Thanks; the byte map matches what the decoder already uses (16 = aggregate, 14 = lower), and adding 13 = upper is a small change. Planned: Upper probe / Lower probe moisture entities on H5059 only, with the parent unchanged and both probes cleared by a dry frame. Ask for **one OpenAPI `bodyAppearedEvent` payload** (Download diagnostics → `openapi_events.recent_events`, captured right after a trip) so the `probesState` fallback can be parsed against a real shape. The patch is welcome as a PR, but we'll implement from the byte map either way. Cite the version after the daily release.

---

## #223 H1232: 16 ring segments + separate main panel

**Current state**
- `SKU_SEGMENT_OVERRIDES` (`const.py:163`) has H7075/H7076/H7026 and no H1232, so `segment_count` = API 13 (`models/device.py:1249`).
- `MAIN_LIGHT_TOGGLE_SKUS = {"H1270"}` (`const.py:407`) applies only to fixtures whose toggles are inert. On the H1232 the toggles **work**, so it already gets `govee_main_light` / `govee_background_light` switches through `named_light_toggle_instances`. **Do not** add the H1232 to MAIN_LIGHT_TOGGLE_SKUS: that would drop the working switches and use the black-colour hack.
- Segment writes: `GoveeSegmentEntity.async_turn_on` → `SegmentColorCommand` (`platforms/segment.py:111`). The coordinator routes BLE → LAN → MQTT → REST `_dispatch_segment_command` (`coordinator.py:4614`, `4696`). There is no native mask-based segment write anywhere. The existing `_build_rgb_segmented_frame` (`api/ble.py:196`) is a whole-strip direct-BLE frame with a fixed `FF 7F` tail.
- ptReal transport exists: `coordinator.async_send_raw_ptreal` (`coordinator.py:5365`) → `build_packet` (`api/ble_packet.py:61`) + `_ble_manager.async_send_ble_packet` (AWS IoT passthrough; needs account login, `_ble_manager.available`).

**Is the reporter's mapping enough? Yes, for colour and for panel brightness.** The frames decode cleanly to the standard Govee `33 05 15 01 RR GG BB <5 bytes CT, zeroed> <mask LE>` layout. The 3-byte little-endian mask has bit i = internal segment i+1:
- `FF FF 01` = ring + panel; `00 E0 01` = bits 13-15 + 16 (segments 14-16 + panel); `00 00 01` = panel only. Platform index i (0-12) = mask bit i, so ptReal index 13-15 = API-unreachable ring segments, and bit 16 = main panel.
- Brightness: `33 05 15 02 HH <mask LE 3 bytes>` (ring `FF FF 00`, panel `00 00 01`).
All four frames were visually verified on the device. Status readback (`aaa501..aaa505`, 17 entries) is not needed for a first cut, because segments are already optimistic + RestoreEntity.

**Minimal design**
1. `api/ble_packet.py`: `build_segment_color_ptreal(rgb, mask: int) -> list[int]` returning `[0x33,0x05,0x15,0x01,r,g,b,0,0,0,0,0, mask&0xFF, (mask>>8)&0xFF, (mask>>16)&0xFF]`, plus `build_segment_brightness_ptreal(pct, mask)` returning `[0x33,0x05,0x15,0x02,pct, m0,m1,m2]`. Both are passed through `build_packet`.
2. `const.py`: `PTREAL_SEGMENT_SKUS: Final = {"H1232": 16}` (ring segments addressable by ptReal) and `PTREAL_MAIN_PANEL_BIT: Final = {"H1232": 16}`. Add `SKU_SEGMENT_OVERRIDES["H1232"] = 16`, with a comment citing #223 and the verified frames. Keep the H60A6/H1252 out until someone verifies them.
3. `coordinator.py` `async_control_device`: before the REST segment branch (`~4614`), if `isinstance(command, SegmentColorCommand)` and the SKU is in `PTREAL_SEGMENT_SKUS` and `self._ble_manager.available`, build one frame whose mask is all indices OR'd together (so a grouped write is one publish), send it with `async_send_ble_packet`, then apply optimistic state and record the transport send (`mqtt`). If ptReal is unavailable: indices < API count fall through to REST; any index >= API count returns False (the entity raises the translated error).
   Option: make `GoveeSegmentEntity.available` False for index >= `segment_count_resolution["api_count"]` when `coordinator.ble_passthrough_available` is False. That is cleaner than an error.
4. New coordinator method `async_set_main_panel(device_id, *, rgb=None, brightness=None) -> bool` that sends the panel-masked frames through the same passthrough.
5. `light.py`: new `GoveeMainPanelLight(GoveeEntity, LightEntity, RestoreEntity)`, created at `light.py:~97` when `sku in PTREAL_MAIN_PANEL_BIT`. On/off goes through `ToggleCommand("mainLightToggle")` via `_async_send_command`, and `is_on` reads `state.toggles["mainLightToggle"]`. Colour and brightness go through `async_set_main_panel`; on False it does `raise self._command_failed()`. Colour modes are RGB (and brightness). State is optimistic + restored. Reuse translation key `govee_main_light_panel` ("Main light", already in strings/en.json:174). Use a new unique_id suffix `SUFFIX_MAIN_PANEL = "_main_panel"`, to avoid reusing the H1270 semantics of `_main_light_toggle`. Icon: add `icons.json` `light.govee_main_light_panel: mdi:ceiling-light` (currently absent).
   "Ring as one light" already exists: the user sets segment mode to grouped/both, so `GoveeGroupedSegmentEntity` covers it and now reaches all 16 through one masked frame.
6. Notes in the reply/plan: scenes render only on the panel; any segment write ends a scene (device behaviour, no code needed).

**Tests**: frame builders (the reporter's 4 hex frames as golden values, checksum added by `build_packet`). Coordinator: H1232 segment command with passthrough → one ptReal publish with mask bits for 13-15 and no REST call; without passthrough, idx 3 → REST and idx 14 → False. `segment_count` = 16 with `source="override"`. Light: the panel entity exists only for the H1232, on/off sends the mainLightToggle ToggleCommand, colour sends the `00 00 01`-masked frame, and failure raises HomeAssistantError. Keep `config_flow` untouched. Cover the new branches to hold the 96% per-module floor (`test_cov_light.py`, `test_cov_coordinator_control.py`).

**Reply brief (#223)**: The frame decoding is clear (3-byte LE mask, bit 16 = panel), so it's planned for the H1232 only: 16 ring segments and a separate Main light (panel) entity with colour and brightness over ptReal, with on/off on the working mainLightToggle. These need account login (AWS IoT). Without it, segments 14-16 stay unavailable and 1-13 use the Platform API. H60A6/H1252 stay out until someone verifies them with `send_raw_ptreal`. Ask the reporter to test after the release and to compare the template-light behaviour.

---

## #211 H60B0: per-zone colour + relative brightness

**What the new diagnostics show** (fw/hardware not needed; captured with the lamp **off**):
- Capabilities: powerSwitch, brightness 1-100, `segmentedColorRgb` + `segmentedBrightness` **8 segments (elementRange 0-7, size.max 8)**. That differs from the #83 capture, which had 0-14/15 segments, so segment count varies by firmware or hardware revision. There are also colorRgb, colorTemperatureK, lightScene/diyScene/snapshot, musicMode, dreamViewToggle, and `rippleLightToggle`/`sideLightToggle`/`bottomLightToggle`, which are already switches since #196.
- There is **no** per-zone colour, CCT, or relative-brightness capability. #196 already showed `segmentedBrightness` returns success but does not change Ripple brightness and breaks the active scene.
- AWS IoT `_op_frames` (state while off) carry plausible zone settings:
  - `aa a5 01..03`: 9 entries (8 segments + 1), each `[brightness, r, g, b]`.
  - `aa 12 00 64 09 00 80 0f 00 ff ae 54 0a 8c`: `0x64` = 100 %, `ffae54` warm white, `0x0a8c` = **2700 K**. This looks like the **bottom light** relative brightness + CCT.
  - `aa 11 00 1e 0f 00 00 ff 32`: `0x1e` = 30, possibly a side/ripple relative brightness. `aa 23 ff 00000080 ...`, `aa 41`, `aa 42`: unknown.
- That makes zone writes probably `33 11 ...` / `33 12 ...` ptReal frames, but this is a hypothesis with no write capture and no labelled read.

**Why separate light entities aren't possible yet**: the Developer API exposes no zone channel. Building on segments would repeat #196, because we don't know which of the 8 segments are side vs. ripple. The only path is ptReal, which needs labelled frames first.

**Data needed (ask)**: with the lamp **on** and account login enabled, change one setting at a time in the app and download diagnostics after each (`devices.<id>.last_mqtt_message._op_frames`):
1. Side relative brightness 30 → 80 %. 2. Ripple relative brightness 30 → 80 %. 3. Bottom relative brightness 100 → 50 %, then bottom warmth 2700 → 5000 K. 4. Side colour → pure red. 5. Ripple colour → pure blue.
Also: when they move a HA segment entity (1-8), which physical part changes?
Then they could try `govee.send_raw_ptreal` with `33 12 00 32 ...` (the `aa 12` payload with brightness 0x32) to confirm the write echo. Pin down the exact candidate frames after the captures arrive.

**Reply brief (#211)**: Thanks for the diagnostics. They confirm the Developer API has no per-zone colour or relative-brightness channel (only 8 generic segments, and #196 showed `segmentedBrightness` doesn't move Ripple). The device's own status frames do seem to carry the zone settings (one looks like the bottom light at 100 % / 2700 K), so a native path is plausible. Ask for the one-change-at-a-time diagnostics above. No entities until a frame is verified on the lamp. Keep the issue open; no release reference.
