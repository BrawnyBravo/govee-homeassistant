# Code review: govee-homeassistant v2026.9.5

Reviewed on 2026-09-13 against the Home Assistant developer guidelines, the core architecture page, the documentation standards, and the Integration Quality Scale rule pages. Scope: every module under `custom_components/govee/` (26,320 lines), the test suite (33,174 lines, 65 files), tooling and CI, and the user-facing docs (`README.md`, `strings.json`, CLAUDE.md, CONTRIBUTING.md, TESTING.md, ARCHITECTURE.md). Line numbers refer to the tree at commit `93fbb5d`.

## Verdict

The integration is functionally rich and unusually well commented, and the automated gates are green: flake8 and mypy strict pass, and 2,159 tests pass in 17 s. Against the Home Assistant rules it does not reach the tier it declares. `manifest.json` claims `silver` and `quality_scale.yaml` marks most Gold and Platinum rules done; the code fails four Bronze rules and five Silver rules outright, and several Gold claims are inaccurate. One correctness bug was reproduced empirically: the orphan-entity cleanup deletes the hub-level diagnostic sensors and every leak-sensor entity from the entity registry on every config-entry setup. Two more High bugs in the Bluetooth advertisement handler were confirmed by reading the code: every advertisement re-arms the cloud poll timer, and two devices of the same model can never enrol for BLE.

Gate results on the current tree (Python 3.12, Home Assistant 2025.1.4):

| Gate | Result |
|---|---|
| flake8 (`select = E,W,F`, E501 ignored) | clean |
| mypy `--strict` | clean, 47 files |
| black `--check` (line length 119) | 85 of 112 files would be reformatted |
| pytest | 2,159 passed |
| coverage | 77.4 % overall; `__init__.py` 39 %, `config_flow.py` 54 %, `repairs.py` 48 %, `services.py` 55 %, `event.py` 0 % |

CI runs `black .` without `--check`, so the style job can never fail, and both `tox.ini` and `.coveragerc` set the coverage floor at 25 %. The 95 % figure in CLAUDE.md, CONTRIBUTING.md, and TESTING.md is not enforced anywhere.

## Quality scale: claimed versus observed

| Rule | Claimed | Observed | Evidence |
|---|---|---|---|
| unique-config-entry (Bronze) | done | fails | no `async_set_unique_id`, `_abort_if_unique_id_configured`, or `_async_abort_entries_match` anywhere in `config_flow.py`; the same API key can be added twice |
| action-setup (Bronze) | done | fails | services registered from `async_setup_entry` (`__init__.py:251-252`); there is no `async_setup` |
| config-flow-test-coverage (Bronze) | done | fails | 54 % coverage; the `reauth_confirm` body (`config_flow.py:475-519`) and most of `reconfigure` are uncovered; no test calls `hass.config_entries.flow.async_init`; flows are driven with `flow.hass = MagicMock()` |
| test-before-setup (Bronze) | done | partial | first refresh is tested, but `async_setup_entry` converts every exception into `ConfigEntryNotReady` (`__init__.py:229-234`), which hides programming errors behind a retry loop |
| action-exceptions (Silver) | not listed | fails | no `HomeAssistantError` or `ServiceValidationError` is raised outside `api/`; entity actions log a warning and return |
| entity-unavailable (Silver) | not listed | fails | a total cloud outage never raises `UpdateFailed`; entities keep stale state and stay available (`coordinator.py:3583-3588`, `3981-3984`) |
| log-when-unavailable (Silver) | done | fails | same path: connection failures are logged at debug only |
| parallel-updates (Silver) | done | partial | `event.py` has no `PARALLEL_UPDATES`; the other 11 platforms set 0, including the seven action platforms |
| reauthentication-flow (Silver) | done | partial | reauth works but cannot verify the same account (no unique id, so no `_abort_if_unique_id_mismatch`) |
| test-coverage (Silver) | done | fails | 77.4 % against the 95 % rule; setup, unload, cleanup, and services are largely untested |
| entity-translations (Gold) | done | partial | seven entities hard-code `_attr_name`; three translation keys used in code are missing from `strings.json` |
| icon-translations (Gold) | exempt | not exempt | about 40 `_attr_icon` assignments and one dynamic `icon` property; `icons.json` covers only the fan |
| exception-translations (Gold) | done | fails | `strings.json` has no `exceptions` section; the claim confuses config-flow error keys with exception translations |
| repair-issues (Gold) | done | partial | `rate_limited` and `mqtt_disconnected` are informational; the rule requires actionable issues |
| stale-devices (Gold) | done | buggy | cleanup removes live entities (finding 1) |
| docs-removal-instructions (Bronze) | done | fails | README has no removal section; the only "remove" sentence (README:139) is about account login |
| docs-examples, docs-use-cases (Gold) | todo | missing | no automation examples; the one YAML snippet (README:194) uses the deprecated `service:` key |
| inject-websession (Platinum) | done | partial | four fallbacks create a bare `aiohttp.ClientSession()` (`api/auth.py:837, 1014, 1256, 1351`) |
| strict-typing (Platinum) | done | partial | mypy strict passes, but `GoveeConfigEntry` is only used in `__init__.py`; every platform types the entry as plain `ConfigEntry` |

## High severity

### 1. Orphan cleanup deletes hub-level and leak-sensor entities on every setup

`_async_cleanup_orphaned_entities` (`__init__.py:368-503`) treats any registry entry whose unique ID does not start with a key of `coordinator.devices` as "device not discovered" and removes it. Leak sensors live in `coordinator.leak_sensors`, hub devices are registered separately, and the three hub-level diagnostic sensors use `entry_id` as their prefix, so none of them ever match.

Reproduced with a throwaway test against the real function: a registry seeded with one real light, the rate-limit and MQTT-status sensors, and a leak moisture and battery entity came back with only the light surviving; the log showed `Removing orphaned entity` for the other four. Platform setup recreates them afterwards, so the visible effect is registry churn on every restart or reload, loss of user customisation on those entities (renamed entity IDs, areas, disabled state, depending on the Home Assistant version), and a misleading `Cleaned up N orphaned entities` line at info level.

The same function also removes entities and devices whenever `get_devices()` returns a shorter list, which is what the stale-devices rule warns against ("only remove devices you are certain are unavailable").

Fix: build the set of owned IDs from `coordinator.devices`, `coordinator.leak_sensors`, the registered hub IDs, and the `entry_id` prefix; only remove entities whose device is absent from a successful, complete discovery, and never after a discovery step that timed out or failed (`_run_startup_step` swallows those). Add `async_remove_config_entry_device` so users can delete stale devices by hand, which is the pattern the rule recommends when certainty is not available. Cover the function with a test that uses `MockConfigEntry` and the real entity registry.

### 2. A cloud outage never makes entities unavailable and is never logged

`_fetch_device_state` catches every exception and returns it (`coordinator.py:3981-3984`); `_async_update_data` logs each failure at debug and keeps the previous state (`coordinator.py:3583-3588`). `UpdateFailed` is only raised during initial discovery. With DNS down or Govee's API unreachable, every light keeps its last known state and `available` stays true, because `GoveeEntity.available` only checks `last_update_success` and the cached `state.online`. Nothing at info or warning level tells the user why commands stop working.

Fix: keep per-device isolation for partial failures, but when every pollable device fails with a connection error, raise `UpdateFailed` once. The coordinator then logs once on failure and once on recovery, and entities become unavailable, which is what the two Silver rules ask for.

### 3. Entity actions and services swallow failures

`GoveeCoordinator.async_control_device` catches `GoveeApiError`, logs at error level, and returns `False` (`coordinator.py:4212-4215`). Every platform then either ignores the return value (`light.py:340-372`, `switch.py:279-292`, `fan.py:470-495`, `humidifier.py:267-279`) or logs a warning (`select.py:369-373`, `number.py:299-303`). A failed `light.turn_on` therefore reports success to the automation that called it. `humidifier.async_set_mode` and `async_set_humidity` raise bare `ValueError` (`humidifier.py:283`, `333`). The two services return silently on an unknown device or an out-of-range segment (`services.py:62-75`, `104-112`).

Fix: raise `HomeAssistantError` from the coordinator, or from the entity when the coordinator returns `False`, and `ServiceValidationError` for bad input, both with `translation_domain=DOMAIN` and keys in a new `exceptions` block of `strings.json`. That closes action-exceptions and exception-translations together.

### 4. Duplicate config entries are not prevented and account identity is never checked

`async_step_user` never sets a unique ID or matches existing entries, so the same key can be configured twice, creating colliding unique IDs (every entity's unique ID is the Govee device ID, without the entry ID). Reauth and reconfigure also cannot abort with `wrong_account`. The login response carries `accountId` (`api/auth.py:1694-1695`), which is a natural unique ID when account login is configured; without it, `_async_abort_entries_match({CONF_API_KEY: key})` is the documented fallback.

### 5. Services are registered per entry and cannot be validated

Registration happens inside `async_setup_entry` guarded by `has_service` (`__init__.py:251-252`). The action-setup rule requires `async_setup`, so automations referencing `govee.refresh_scenes` validate even when the entry is not loaded. `_get_coordinators` (`services.py:147-155`) should check `entry.state is ConfigEntryState.LOADED` rather than `hasattr(entry, "runtime_data")`. Both services take a raw Govee MAC in a text selector (`services.yaml`); the Home Assistant convention is a device selector resolved through the device registry, or `config_entry_id`.

## Medium severity

### 6. Test coverage and test style

- 77.4 % overall; `async_setup_entry`, `async_unload_entry`, and the cleanup pass are 0 % (`__init__.py:140-257`, `324-343`, `382-503`). The bug in finding 1 lives entirely in uncovered code.
- `event.py` is 0 %: the leak button event entity has never been instantiated in a test.
- No test file uses `MockConfigEntry`, a `hass: HomeAssistant` fixture, `flow.async_init`, or `FlowResultType`; 18 files set `hass = MagicMock()`. Config-flow tests construct `GoveeConfigFlow()` directly (`tests/test_config_flow.py:944-945`, `1010-1011`), so step IDs, abort reasons, `strings.json` keys, schema validation, and entry creation are never exercised. The `missing_credentials` abort reason used at `config_flow.py:291` has no entry in `strings.json`.
- Five test files are named after issues or sweeps (`test_issue_114.py`, `test_issue_118.py`, `test_issue_126.py`, `test_sweep_followups_2026_09.py`, `test_sweep_followups_2026_09b.py`); feature discoverability is lost. Fold them into feature files and keep the issue number in the test name.
- `tests/conftest.py:43-79` shadows the plugin's autouse `enable_event_loop_debug` fixture to survive pytest-asyncio 1.0; pin the plugin versions in `requirements_test.txt` instead.

### 7. Entity naming and translations

- Hard-coded names override translation keys: `button.py:71` ("Refresh Scenes"), `number.py:212` ("Music Sensitivity"), `number.py:353` ("Target Temperature"), `fan.py:682` ("Fan"), `light.py:469` ("Main light"), `platforms/segment.py:72` (`f"Segment {n}"`), `platforms/grouped_segment.py:93` ("Segments"). Title Case also breaks the sentence-case rule.
- The segment translations embed `{device_name}` (`strings.json` keys `govee_segment`, `govee_grouped_segment`). With `has_entity_name`, Home Assistant already prefixes the device name, so enabling those strings would produce "Strip Strip Segment 1". Use `{segment_index}` alone.
- Keys used in code but absent from `strings.json`: `govee_heater_temperature` (`number.py:319`), `govee_fan_speed_select` (`select.py:935`), `govee_purifier_mode_select` (`select.py:1029`).
- ENUM sensors without state translations: `mqtt_status` (`sensor.py:275`) and `leak_alert_status`, whose raw states are the Title-case strings "Pending" and "Acknowledged" (`sensor.py:961-987`). Enum states should be lowercase keys with translated labels.
- 46 of 54 multi-word names and titles in `strings.json` are Title Case ("Govee API Key", "Night Light", "Refresh Scenes", "Water Tank Full"), with the inconsistent pair "Main light" and "Main Light"; six strings say "Please"; three use "e.g.".
- `translations/ca.json` and `es.json` each lack 23 keys present in `en.json`.
- `reauth_confirm` has no `data_description` for `api_key`; the options step lacks `data_description` for `poll_interval`, `enable_scenes`, `enable_diy_scenes`, and `expose_transport_entities`.

### 8. Icons belong in icons.json

Forty static `_attr_icon` assignments across `binary_sensor.py`, `button.py`, `select.py`, `switch.py`, `number.py`, `sensor.py`, `fan.py`, and `light.py`, plus a dynamic `icon` property (`sensor.py:845`), while `icons.json` only describes the fan preset icons. The Gold rule has no exemption; the `exempt` note in `quality_scale.yaml` is wrong.

### 9. Logging

- Account emails are logged at info and warning level in `config_flow.py:216-252` and `564-601`, and at debug in `api/auth.py:1536`, `1548`. The guideline forbids logging usernames.
- 58 `_LOGGER.info` calls, 26 of them in `coordinator.py`. Most are operational chatter ("Fetched MQTT topics for %d devices", "Discovered %d leak sensors", "Refreshed scenes for all devices", "Set segments %s to color %s") and belong at debug. Info should be reserved for state the user must act on.
- `manifest.json` lists `aiohttp` and `aiomqtt` under `loggers`. Enabling debug logging for the integration from the UI then enables aiohttp debug output for every integration in the instance, which is noisy and can expose request headers.

### 10. Polling and parallelism

- `event.py` has no `PARALLEL_UPDATES`.
- The seven action platforms declare `PARALLEL_UPDATES = 0`. The rule allows 0 for read-only platforms behind a coordinator, but says a coordinator "does not limit outbound action calls". The integration already serialises segment writes and reserves API budget because Govee drops bursts, which argues for a small bound rather than unlimited fan-out on an area `turn_off`.
- Nine push-driven entity classes that do not inherit `CoordinatorEntity` (`GoveeLeakBinarySensor`, `GoveeLeakOnlineSensor`, `GoveeLeakHubOnlineSensor`, `GoveeLeakBatterySensor`, `GoveeLeakLastWetSensor`, `GoveeLeakAlertStatusSensor`, `GoveeLeakDeviceAddressSensor`, `GoveeLeakHubAddressSensor`, `GoveeLeakButtonEvent`) never set `_attr_should_poll = False`, so the entity platform polls them every 30 s for nothing.

### 11. Options flow robustness and selectors

- `async_step_init` dereferences `self.config_entry.runtime_data` (`config_flow.py:749`, `868`, `937`) without checking that the entry is loaded. Opening options on an entry that failed setup raises `AttributeError` and the UI shows "Unknown error occurred".
- `vol.In([...])` and `cv.multi_select` render raw values (`auto`, `celsius`, `fahrenheit`, `disabled`, `grouped`, `individual`, `both`). `SelectSelector` with `translation_key` and a `selector` block in `strings.json` is the documented way to get translated option labels.
- The poll interval range is 30 to 300 s in code (`config_flow.py:775`) and in the README, 30 to 600 in CLAUDE.md.

### 12. Repairs framework use

- `auth_failed` duplicates Home Assistant's own reauth handling: `ConfigEntryAuthFailed` from the coordinator already starts a reauth flow and shows a notification. The fix flow then starts a second reauth through raw `flow.async_init` (`repairs.py:181-186`) instead of `entry.async_start_reauth(hass)`.
- `rate_limited` and `mqtt_disconnected` are created with `is_fixable=False` and say "this clears itself". The rule states repairs should not be raised "for just letting users know that something is wrong". A persistent notification or the existing diagnostic sensors fit better.
- The `async_create_*_issue` helpers are `async def` with no awaits; the registry calls are synchronous callbacks.

### 13. Diagnostics side effects

`async_get_config_entry_diagnostics` runs a live multicast scan and then a UDP probe battery against every responding device on each download (`diagnostics.py:354-437`). Diagnostics are expected to be a snapshot; this one takes seconds, sends traffic to devices, and can differ between two downloads. It also reads private coordinator attributes (`coordinator._lan_devices`, `coordinator._lan_unmatched` at `diagnostics.py:519-520`). Redaction is otherwise thorough, though the parsed `device.name` is included while the raw `deviceName` is redacted.

### 14. Web session fallbacks

`GoveeAuthClient` creates a bare `aiohttp.ClientSession()` when constructed without a session in four BFF methods (`api/auth.py:837`, `1014`, `1256`, `1351`). Every call site passes `hass=`, so the branches are dead in production, but they contradict the Platinum claim and would leak sessions if ever hit. Remove them and require a session.

### 15. No request timeouts on REST calls

`GoveeApiClient` never passes `timeout=` (`api/client.py`), and Home Assistant's shared session has no default request timeout. Polls are bounded by `STATE_FETCH_TIMEOUT` in the coordinator, but `control_device` and the scene fetches are not, so a stalled connection can hold a service call for aiohttp's default of five minutes. Set `aiohttp.ClientTimeout(total=...)` per request or on the `RetryClient`.

### 16. Parsing robustness

- `state.py:407` and `597` coerce `colorTemperatureK` / `colorTemInKelvin` with a bare `int(value) if value else None`; a string payload raises `ValueError` out of `update_from_api`, which is the failure `_coerce_int` (`state.py:50-63`) was written to prevent. `RGBColor.from_dict` (`state.py:124-126`) and `ColorTempRange.from_capability` (`device.py:219`) have the same bare `int()`.
- `state.py:374` iterates `data.get("capabilities", [])`; a null `capabilities` raises `TypeError` (reproduced). `device.py:1294` stores `raw_cap.get("parameters", {})`, so a null `parameters` becomes `None` and every later `cap.parameters.get(...)` raises `AttributeError` (reproduced through `brightness_range`). Use `or []` / `or {}`.
- The consequences are contained today: `get_devices` skips a device that fails to parse (`api/client.py`) and `_fetch_device_state` swallows the exception, but each of these silently drops a device or freezes its state.

### 17. Coordinator size

`coordinator.py` is 5,268 lines and one class with roughly 130 methods covering REST polling, MQTT, LAN, BLE, BFF discovery, leak sensors, probe thermometers, water detectors, repairs, and optimistic state. The common-modules rule is satisfied in name only. `BleAdvertisementHandler` and `TransportHealthTracker` show the extraction pattern already works; the LAN tier (`_async_setup_lan` through `_merge_lan_correlation`, about 450 lines) and the BFF/leak tier (about 900 lines) are the obvious next candidates. `GoveeDevice` (1,009 lines, 70 methods) and `GoveeDeviceState.update_from_api` (189 lines) would benefit from a capability-type dispatch table.

### 18. Shipped stub

`async_send_diy_style` applies optimistic state and always returns `False` with a "not yet available" debug message (`coordinator.py:4939-4978`). `GoveeDIYStyleSelectEntity` therefore logs "Failed to set DIY style" on every use while its `current_option` shows the new value. Either implement the packet or drop the entity.

### 19. Number entities bypass the base class

`GoveeMusicSensitivityNumber` and `GoveeHeaterTemperatureNumber` subclass `CoordinatorEntity` directly (`number.py:161-431`), duplicate `DeviceInfo` without `via_device`, ignore `coordinator.last_update_success` in `available`, use the literal `"°C"` instead of `UnitOfTemperature.CELSIUS`, and the heater target has no `NumberDeviceClass.TEMPERATURE`, so Fahrenheit users get no unit conversion.

### 20. Inferred areas

`GoveeEntity.device_info` sets `suggested_area` from a hard-coded list of English room words matched against the device name (`entity.py:63`, `115-153`). Home Assistant reserves `suggested_area` for rooms the device or service reports; guessing from names silently assigns areas for English speakers only and misfires on names such as "Bathroom fan controller" mounted in the hallway.

### 21. Setup error handling

`async_setup_entry` catches `Exception` from the first refresh and re-raises `ConfigEntryNotReady` (`__init__.py:229-234`). `async_config_entry_first_refresh` already raises `ConfigEntryNotReady` for `UpdateFailed`; wrapping everything else turns a `TypeError` in discovery into an endless silent retry. Catch the API exception types only.

### 22. README against the documentation standards

- Missing sections required by the docs rules: removal instructions, automation examples, use cases, and a "Known limitations" heading (limitations are scattered across README:205, 221-226, and 423).
- The single YAML example (README:194) uses `service:`; current syntax is `action:`. `govee.refresh_scenes` has no example.
- Style: 90 em dashes, 12 "e.g.", 31 arrow breadcrumbs ("Settings → Devices & Services") where the standard is **Settings** > **Devices & services**, six tables (59 rows) where the guide prefers lists, "Click" at README:285, British spellings (honour, colour, behaviour, catalogued), "WiFi" for Wi-Fi, and "HA" as an abbreviation eleven times.
- Headings are already sentence case, which is the hard part; the rest is a mechanical sweep.

### 23. Dead and misleading architecture

- `protocols/` (`api.py`, `state.py`) is imported by nothing; `IStateObserver`, cited in CLAUDE.md and ARCHITECTURE.md, does not exist; `IAuthProvider` no longer matches `GoveeAuthClient.login`'s signature. Delete the package or make the coordinator depend on the protocols and test them.
- "Frozen dataclass" claims in `models/__init__.py:3`, `device.py:3`, CLAUDE.md, ARCHITECTURE.md, and CONTRIBUTING.md are false for `GoveeDeviceState`, `TransportHealth`, and `GoveeLeakSensorState`, and the frozen `GoveeCapability` holds the live API `dict`, so `hash(GoveeCapability)` raises `TypeError` (reproduced) and option lists are returned by reference from seven `get_*_options` methods.
- `models/device.py:13` imports `DeviceInfo` and builds Home Assistant device info inside the models package (`device.py:1408-1424`); move `leak_sensor_device_info` to `entity.py`.

## Low severity

- **Formatting and tooling.** black would reformat 85 files; the CI style job runs `black .` without `--check`; `.pre-commit-config.yaml` pins black 24.10 and `types-all` (a retired meta-package that no longer installs); `setup.cfg` and `tox.ini` both carry `[flake8]` sections with different line lengths (88 vs 119) and `setup.cfg` ignores E501, so line length is unenforced. Home Assistant itself uses ruff; adopting its ruleset would also catch the import and exception-chaining issues below.
- **Import placement.** `homeassistant.helpers.event` is imported after local modules in `coordinator.py:43`; `import aiohttp` follows the `TYPE_CHECKING` block in `api/auth.py:23`; `__init__.py` splits `homeassistant.helpers` imports across two blocks; function-level imports in `config_flow.py:382-383` (re-importing `Any`, already at module scope), `config_flow.py:435`, `api/client.py:97`, `api/auth.py:504`.
- **Exception chaining.** `raise GoveeApiError(...)` inside `except aiohttp.ContentTypeError` without `from` (`api/client.py:309-311`).
- **Stale comments and docs.** `config_flow.py:3` says "Fresh version 1 - no migration complexity" while `VERSION = 2` with a migration; `__init__.py:67` labels `Platform.NUMBER` as "DIY speed controls" but no such entity exists; CLAUDE.md describes `PowerCommand(device_id=..., value=...)`, `coordinator.register_observer`, `CONF_ENABLE_SEGMENTS`, `hass.data[DOMAIN][KEY_IOT_CREDENTIALS]`, a poll maximum of 600, a test table of 535+, and `git push origin master`, none of which match the code (the remote has only `main`); TESTING.md cites a `pytest.ini` that does not exist and shows `RGBColor(...).red` and `GoveeDevice(device_name=..., model=...)`, which are not the field names; CONTRIBUTING.md clones `hacs-govee.git` and references a `.devcontainer/` that is absent; ARCHITECTURE.md still lists `scene.py` and an `enable_segments` option.
- **Dead constants.** `_LOGGER` in `models/device.py` is never used; `INSTANCE_GRADUAL_ON`, `INSTANCE_TIMER`, `INSTANCE_TEMPERATURE`, `INSTANCE_FAN_SPEED`, and `DEVICE_TYPE_SENSOR` are referenced nowhere.
- **SKU lists.** Five SKU sets live in `const.py`, nine in `models/device.py`, one in `api/mqtt_control.py`; `.upper()` is applied inconsistently (`device.py:743`, `1332` compare raw); `strings.json` hand-copies a Fahrenheit subset that omits six SKUs. One SKU module, normalised once in `from_api_response`.
- **Type annotations that lie.** `device.py:984` returns un-coerced `Any` as `tuple[int, int]`; `state.py:424-425` assigns raw `Any` into `work_mode: int | None`; `commands.py:389` types `auto_color` as `int` though it is a flag.
- **manifest.json.** `"homekit": {}` is an empty discovery block; `after_dependencies` lists `network` although `api/lan.py:59` imports it unconditionally at module load.
- **hacs.json** declares 2024.11.0 as the minimum while the code uses `ConfigFlow._get_reconfigure_entry`, `async_update_reload_and_abort(data_updates=...)`, and `DataUpdateCoordinator(config_entry=...)`; re-verify the minimum against the oldest release that has all three.
- **services.yaml** duplicates `name` and `description` that `strings.json` now owns.
- **quality_scale.yaml** carries the inaccurate claims listed in the table above and a "143+ tests" comment.
- **Repository hygiene.** `.serena/cache/*.pkl` is tracked; reverse-engineering artefacts (`g2m_iot.rs`, `hb/`, `hb_aws.js`, `hb_constants.js`) sit untracked at the root; `.env` in the working tree holds what looks like a real API key. It is gitignored, so keep it that way and rotate the key if it was ever pasted anywhere.
- **Groups.** `GoveeEntity.available` returns true for group devices even when the coordinator has failed (`entity.py:80-81`).
- **Options data model.** `segment_mode_by_device` is written and read as a raw string key (`config_flow.py:930`, `__init__.py:386`) instead of a constant.
- **Tests asserting on log text** in `tests/test_fan.py`, `tests/test_api_client.py`, and `tests/test_services.py` (ten sites) will break on wording changes; assert on behaviour instead.

## API and transport layer

The 15 transport and helper modules (5,353 lines: `api/mqtt.py`, `api/lan*.py`, `api/ble*.py`, `api/openapi_events.py`, `api/probe_thermometer.py`, `api/mqtt_control.py`, `ble_passthrough.py`, `ble_advertisement.py`, `transport_health.py`, `scene_cache.py`, `models/transport.py`) were reviewed in a delegated pass. The two High findings and the MQTT brightness, OpenAPI subscribe, and manifest items were re-verified directly against the source; the remaining items carry the file and line the pass cited.

### 24. Every BLE advertisement re-arms the cloud poll and wakes every entity

`BleAdvertisementHandler.handle_advertisement` ends with an unconditional `coord.async_set_updated_data(coord._states)` (`ble_advertisement.py:275-277`). Home Assistant's `async_set_updated_data` cancels the pending refresh, reschedules it from now, and notifies every listener (`update_coordinator.py:499-514` in 2025.1.4). Bluetooth delivers callbacks per advertisement with no throttling, so a single strip advertising every second pushes the cloud poll out indefinitely and makes every entity of every device write state on each advert.

Fix: record transport success silently and notify only when something changed (first enrolment, an `online` flip), mirroring the before/after guard in `_on_lan_dev_status`, and never reschedule the poll from an advertisement. Severity: High.

### 25. Same-SKU Bluetooth devices never enrol

The tiebreaker for two devices of the same SKU tests `did.upper().startswith(ble_mac)` (`ble_advertisement.py:201-205`), but cloud IDs carry the MAC in the last six octets, as `ble_address_from_device_id` itself documents (`ble_advertisement.py:63-72`). With two or more strips of one model no advertisement ever matches, so BLE is silently disabled for exactly the households that own two of the same light. `enroll_from_cache` re-enters the same code, and `tests/test_coordinator.py:1416-1444` enshrines the wrong ID shape.

Fix: compare `ble_address_from_device_id(did) == ble_mac`. Severity: High.

### 26. Transport-layer medium items

- Untracked background tasks: `api/mqtt.py:480`, `api/openapi_events.py:99`, and `scene_cache.py:124`, `221` use `asyncio.create_task` or `ensure_future` instead of `entry.async_create_background_task`. In `scene_cache.py` cancelling one waiter cancels the shared fetch for every waiter; use `asyncio.shield` or inject a task factory from the coordinator.
- The OpenAPI event client marks itself connected and resets its backoff before subscribing, discards the SUBACK result, and logs every connection failure at debug (`api/openapi_events.py:148-153`, `167-177`). A bad API key or a refused topic leaves it "connected and deaf" with nothing in the log. `api/mqtt.py:613-617` already handles a refused subscription; reuse it and warn on the first failure.
- MQTT brightness is sent unscaled: `command_to_mqtt` forwards `command.brightness`, which is device-native (0-254 on some SKUs, `models/commands.py:102`), as the 1-100 `val` the module documents (`api/mqtt_control.py:38-45`, `95`), while the LAN path scales through `brightness_range` (`api/lan_control.py:141`). With MQTT control enabled, any device whose range is not 0-100 gets the wrong brightness.
- Dependencies: `homeassistant.components.bluetooth` and `network` are used with `dependencies: []` (`ble_advertisement.py:22-27`, `api/lan.py:59`); `bleak` is imported directly (`api/ble.py:54`, `api/ble_crypto.py:28`) but not declared; `api/ble.py:58` imports `close_stale_connections_by_address`, which the bleak-retry-connector changelog places in 3.4.0, while the manifest allows `>=3.0.0`. On an older connector the import error is swallowed by the try/except at `ble_advertisement.py:21-34` and BLE silently vanishes.
- Identifiers and payloads in logs: full inbound MQTT payloads with device MACs and names at debug (`api/mqtt.py:785-788`); the button sub-device MAC that the diagnostics buffer deliberately masks (`api/mqtt.py:1117-1124`); the BLE MAC at info (`ble_advertisement.py:247-252`); whole OpenAPI payloads (`api/openapi_events.py:223`, `234-240`). `api/mqtt.py:893` warns on every unparseable message, which a chatty device turns into spam. The diagnostics ring buffers already capture these payloads.
- `_on_disconnected` in `api/ble.py:346-351` ignores the client argument, so a late callback from a superseded `BleakClient` wipes the freshly established session; guard with `if client is self._client`.
- `ble_advertisement.py:108`, `121` register with `BluetoothScanningMode.ACTIVE` although `api/ble.py:229-231` documents passive; the name-prefix and manufacturer-ID matchers overlap, so one advertisement is handled twice.
- Info-level noise: "restarted" and "stopped" on every reload (`api/mqtt.py:455`, `513`), per-event pushes (`api/openapi_events.py:234`), per-device scene fetches (`scene_cache.py:152`, `251`), and "restored online" re-firing every poll cycle while the cloud reports offline (`ble_advertisement.py:268`).

### 27. Transport-layer low items

- Log style: trailing periods at `api/mqtt.py:1180-1182`, `ble_advertisement.py:220`, `235`, `api/lan_client.py:459-465`; the integration name inside messages at `api/lan_client.py:460`, `471`, `485`, `api/openapi_events.py:134`, `153`, `235`, `api/ble_crypto.py:141`, `148`, `213`, `api/ble.py:340`, `491`.
- Dead code: `_temp_dir` in `api/mqtt.py` (`353`, `501-508`, `531-536`) is never assigned and the `async_stop` docstring is stale; `refresh_ble_device` (`api/ble.py:249`) is never wired, so the proxy hand-off path at `api/ble.py:372-377` is inert; `verify_checksum` (`api/probe_thermometer.py:147-154`) is used only by tests; `ble_advertisement.py:186` carries an unused import.
- Duplication: `op.command` is base64-decoded three times (`api/mqtt.py:254-273`, `1008-1013`, `api/probe_thermometer.py:137-144`); the XOR checksum exists twice (`api/probe_thermometer.py:147-154`, `api/ble_packet.py:46-58`); reconnect constants are duplicated with differing timeouts (`api/mqtt.py:56-60`, `api/openapi_events.py:45-47`); `api/lan_client.py:43-50` imports private `_build_socket`, `_join_group`, `_drop_group` from `api/lan.py`.
- Typing: `typing.Callable` and `Iterable` instead of `collections.abc` (`api/mqtt.py:28`, `api/openapi_events.py:31`, `transport_health.py:16`); `Any` for the aiomqtt client and message and for Bluetooth service info (`api/mqtt.py:362`, `740`, `ble_advertisement.py:87`, `99`, `174`); `api/ble.py:55` needs a `type: ignore` only because `BleakError` is imported from `bleak_retry_connector` instead of `bleak`.
- Resources: `api/lan.py:532-536` leaks the socket if `create_datagram_endpoint` raises (`api/lan_client.py:477-489` handles the same case correctly); `api/openapi_events.py:129-131` rebuilds the SSL context on every attempt where `api/mqtt.py:564-571` caches it; `api/mqtt.py:544-547` writes the private key with `write_text` before `chmod` (open with `0o600` from the start).
- `api/probe_thermometer.py:246` `struct.pack(">h", ...)` raises `struct.error` for limits beyond ±327.67 °C; nothing validates the sentinel path upstream.
- Three functions in `api/mqtt.py` exceed 140 lines (`573-720`, `740-895`, `988-1148`).

Transport strengths: TLS with `CERT_REQUIRED`, hostname checking, and the Amazon root bundle; SSL context and certificate temp files built in the executor and cached across reconnects; capped exponential backoff with SUBACK 0x80 detection and QoS-1 publish with an ACK timeout so the REST fallback runs; the LAN client degrades cleanly when port 4002 is taken; BLE drops the connection on a failed encryption negotiation rather than falling back to plaintext.

## What is done well

- The separation of models, API clients, and entities keeps HTTP and MQTT out of the entity layer, and commands are immutable objects.
- Every quirk carries an issue number and a rationale in the docstring; the reasoning for optimistic state, BFF unit handling, and LAN write confirmation is unusually easy to audit.
- Diagnostics redaction is careful: MAC-shaped values are hashed consistently, IPs are bucketed, and raw BFF payloads are reduced to shape and redacted scalars.
- Startup is failure-isolated: each account/BFF step is bounded by `asyncio.timeout`, and a hang degrades a feature instead of the entry.
- Background work in the coordinator uses `entry.async_create_background_task`, and `async_shutdown` releases timers, sockets, BLE devices, and the MQTT client.
- Rate-limit accounting (per-minute from headers, daily counted locally) is exposed to users with honest caveats.
- Tests run offline, fast, and deterministic, with no skips or xfails.

## Suggested order of work

1. Fix the cleanup bug (finding 1) and the two BLE advertisement bugs (findings 24 and 25); add `MockConfigEntry`-based tests for setup, unload, and cleanup, and a two-same-SKU BLE test.
2. Raise `UpdateFailed` on total outage and `HomeAssistantError` on failed actions (findings 2 and 3), with an `exceptions` block in `strings.json`.
3. Add unique-ID handling to the config flow and move services to `async_setup` with `ServiceValidationError` (findings 4 and 5).
4. Correct `quality_scale.yaml` and `manifest.json` to what the code does; then work the Gold items (names, icons, translations, repairs) as a batch.
5. Enforce the tooling that already exists: `black --check` in CI, a coverage floor that matches the docs, and one lint configuration.

## Status after fixes (2026-09-13)

Applied in commits `c02671d` and `64efe24` and the quality-scale follow-up commit. Gates after the changes: flake8, mypy strict, and `black --check` clean; 3,242 tests pass; coverage 99.8 % with the floor raised to 95 %.

Fixed:

- High 1 to 5, 24, 25: orphan cleanup protects leak sensors, hubs, and the diagnostics device, skips removal after a failed or empty discovery, and `async_remove_config_entry_device` exists; a total cloud outage raises `UpdateFailed`; every entity action raises `HomeAssistantError` on a rejected command and `ServiceValidationError` on bad input, with an `exceptions` block in `strings.json`; the user step aborts on a duplicate API key and reauth or reconfigure refuse a key another entry owns; services live in `async_setup`, validate a loaded entry, and accept a Home Assistant device or a Govee ID; the BLE handler notifies listeners only on a change and never reschedules the poll; the same-SKU tiebreaker compares the last six octets.
- Medium 7, 8, 9, 10, 11, 14, 15, 16, 18, 19, 20, 21, 22, 23: names and icons moved to `strings.json` and `icons.json`; emails dropped from logs and 30 info lines demoted; `event.py` declares `PARALLEL_UPDATES` and push entities no longer poll; the options flow survives an unloaded entry and uses translated selectors; the bare session fallbacks are gone; REST calls have a 30 s timeout; null API fields no longer escape the parser; the DIY style stub is removed; the number entities inherit the base class; area inference is removed; setup only converts API errors into `ConfigEntryNotReady`; README gained removal, limitations, use-case, and example sections; `protocols/` is deleted and the docs match the code.
- Transport: MQTT brightness is rescaled from the device range, the OpenAPI client only reports connected after the subscribe and warns once per failure streak, the BLE disconnect callback ignores superseded clients, the scene cache shields shared fetches, and the manifest declares `bluetooth_adapters` and `network` with `bleak-retry-connector>=3.4.0`.
- Tests: `tests/test_setup_entry.py` and `tests/test_config_flow_manager.py` drive the real config entry, registries, and flow manager; `tests/test_ble_advertisement_notify.py` and `tests/test_coordinator_outage.py` cover the new coordinator behaviour.
- Quality scale: `rate_limited` and `mqtt_disconnected` are fixable repairs whose flows raise the polling interval and retry the account sign-in; every config-flow step is driven through the flow manager; the package ships `py.typed`; the `tests/test_cov_*.py` files take coverage to 99.8 % with a 95 % floor. `quality_scale.yaml` has no `todo` left and the manifest declares `silver`.

Left open:

- 13: diagnostics still run the LAN probe on download (the private attribute access is gone).
- 17: the coordinator is not split.
- 26 (part): `api/mqtt.py` and `api/openapi_events.py` still create their own tasks, MQTT payload debug logs still include identifiers, and the scanning mode is unchanged.
- Low: the SKU lists are not consolidated, the annotation clean-ups are not done, `.serena/cache` is still tracked, and the `hacs.json` minimum version is unverified.

Formatting: the whole repository is now black-formatted at 119 columns (`pyproject.toml` carries the shared config), CI runs `black --check --diff`, and the pre-commit and CI black versions are pinned to the same release.
