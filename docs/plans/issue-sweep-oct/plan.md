# Plan: issue-sweep-oct

## Architecture
Independent, SKU-scoped fixes; no shared subsystem change. Each follows an existing pattern:
- #221: device-model property (`purifier_gear_work_mode`) picks the command path in the existing select; no new entity or unique_id change. Rejected: removing the select (loses a working H6006 control).
- #220: off-only SKU set (`DREAMVIEW_OFF_VIA_COLOUR_SKUS`) that falls through to the existing colour restore. Rejected: adding H605B to `PTREAL_DREAMVIEW_SKUS` (reroutes the working ON path).
- #222: attribution + diagnostics only. Rejected: watchdog/forced re-login (fresh session didn't help; 2FA risk).
- #224: extend existing leak decode + dispatcher-based entity pattern.
- #223: masked ptReal frames through the existing AWS IoT passthrough (`async_send_ble_packet`), with a REST fallback for API-reachable segments. Rejected: `MAIN_LIGHT_TOGGLE_SKUS` (H1232 toggles work).
- PRs: merge author SHAs, then a doc follow-up commit for #227.

## File map
- `custom_components/govee/const.py` → H5103 (PR), `DREAMVIEW_OFF_VIA_COLOUR_SKUS`, `LEAK_DUAL_PROBE_SKUS`, `PTREAL_SEGMENT_SKUS`, `PTREAL_MAIN_PANEL_BIT`, `SKU_SEGMENT_OVERRIDES["H1232"]`
- `custom_components/govee/models/device.py` → `purifier_gear_work_mode`; `GoveeLeakSensorState.upper_probe_wet/lower_probe_wet`
- `custom_components/govee/select.py` → purifier select gear path
- `custom_components/govee/coordinator.py` → PR #227; `mqtt_connected_since`; H605B off gate; leak probe storage; H1232 ptReal segment route; `async_set_main_panel`
- `custom_components/govee/sensor.py` → connection_mode session check
- `custom_components/govee/api/mqtt.py` → inbound counters; probe bytes 13/14
- `custom_components/govee/diagnostics.py` → `inbound_messages`, `last_inbound_at`, `last_device_message_at`
- `custom_components/govee/api/ble_packet.py` → `build_segment_color_ptreal`, `build_segment_brightness_ptreal`
- `custom_components/govee/binary_sensor.py` → `GoveeLeakProbeBinarySensor`
- `custom_components/govee/light.py` → PR #227; `GoveeMainPanelLight`
- `strings.json`, `translations/en.json`, `icons.json` → `leak_upper_probe`, `leak_lower_probe`, `light.govee_main_light_panel` icon
- `CLAUDE.md`, `quality_scale.yaml` → outage wording (#226)
- `docs/govee-protocol-reference.md` → H605B note
- `docs/release-replies.md` → #211, #186, #85
- tests: `test_purifier.py`, `test_models.py`, `test_connection_mode_sensor.py`, `test_diagnostics.py`, `test_cov_coordinator_control.py`, `test_mqtt_multisync.py`, `test_water_leak.py`, `test_cov_binary_sensor_event.py`, `test_ble_packet.py`, `test_cov_light.py`

## Coverage
| Outcome | Model/const | Transport/coord | Entity | Strings | Test | Reply |
|---|---|---|---|---|---|---|
| #221 purifier | T-003 | — | T-003 | — | T-003 | auto (#221) |
| #225 H5103 | T-001 | — | — | — | T-001 | auto + T-012 (#85) |
| #226 LAN avail | — | T-002 | T-002 | — | T-002 | auto |
| #222 MQTT | — | T-004, T-005 | T-004 | — | T-004, T-005 | auto |
| #220 H605B | T-006 | T-006 | — | — | T-006 | auto |
| #224 H5059 | T-007 | T-007 | T-008 | T-008 | T-007, T-008 | auto |
| #223 H1232 | T-009 | T-010, T-011 | T-011 | T-011 | T-009..T-011 | auto |
| #211, #186 | — | — | — | — | — | T-012 |

## Risks
- Both PRs are forks; CI never ran (#227 `action_required`, #225 no checks). Local gates passed (3530 / 3520). Approve the runs or rely on main's CI after merge.
- T-002 and T-011 both edit `light.py`; T-011 should land after T-002 merges.
- Several tasks edit `coordinator.py` (T-002, T-004, T-006, T-007, T-010, T-011): run sequentially, not `--parallel`.
- #223 frames verified by one reporter on one device; H60A6/H1252 deliberately excluded.
- #221: reporters said "it used to work"; the select payload never changed (v2026.9.6 started raising). Reply asks them to confirm the fan entity worked.
- Verify commands pin a scratchpad venv from session b7101f46; it can disappear.

## Solutions consulted
- `docs/solutions/` and `docs/plans/BACKLOG.md` absent; no effect.
- Memory: issue-sweep-includes-closed-threads (comments feed since 2026-09-24), issue-replies-after-release (T-012 queue), lan-transport-health-is-read-driven (#227 review note 4), quality-scale-claims-verified-against-code (T-002 doc edit).

## Research
- `docs/plans/issue-sweep-oct/research-221.md`
- `docs/plans/issue-sweep-oct/research-prs.md`
- `docs/plans/issue-sweep-oct/research-misc.md`
- `docs/plans/issue-sweep-oct/research-features.md`
