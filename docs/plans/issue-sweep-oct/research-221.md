# Research: #221 Air purifiers (H7124, H7129, H7126) "Mode" select rejected

## Symptom
`select.select_option` on the purifier **Mode** select (options Low/Medium/High) fails with
"Govee did not accept the command". client.py:620 logs
`instance=purifierMode value=3 ... 'devices not support this instance'` (H7124, H7129, H7126 value=2).
These SKUs have NO `devices.capabilities.mode / purifierMode` capability; they expose speed as
`devices.capabilities.work_mode / workMode` with `modeValue.gearMode -> Low=1/Medium=2/High=3`
(plus Sleep/Auto/Turbo as their own workModes).

## Root cause
1. `GoveeDevice.get_purifier_mode_options()` — custom_components/govee/models/device.py:1073-1103.
   Pattern 1 (1084-1087) reads a real `purifierMode` mode capability (H6006). Pattern 2 (1089-1102,
   added 7d7fd59, 2026-02-19) falls back to the **workMode** capability and returns the nested
   `gearMode` sub-options. The entity cannot tell which pattern produced the options.
2. `GoveePurifierModeSelectEntity.async_select_option()` — custom_components/govee/select.py:857-866;
   line 863 always sends `ModeCommand(mode_instance=INSTANCE_PURIFIER_MODE, value=value)`.
   For pattern-2 devices that targets an instance the device does not have -> Govee 400.
   The correct payload is `WorkModeCommand(work_mode=<gearMode workMode value, 1>, mode_value=value)`.
3. `current_option` (select.py:846-855) reads `state.purifier_mode`, which nothing ever writes
   (grep: only declared at models/state.py:260), so the select always shows the first option.

## Why it "broke after an update" (it was always wrong)
- The select has sent `purifierMode` for workMode purifiers since 2026-02-19; no change to the
  purifier select/parser between v2026.9.11 and HEAD (`git diff v2026.9.11 HEAD -- select.py` has no
  purifier hunks; ModeCommand unchanged since Jan).
- c02671d (shipped v2026.9.6, 2026-09-13) replaced the old "log a warning and return" with
  `_async_send_command` (raises translated HomeAssistantError). The rejection that used to be
  silent is now a visible error — that is the change the reporters noticed.
- #201 fix 39dfa2a (v2026.9.12) is NOT the cause: it only touches fan.py, and
  `_detect_tiered_speeds` returns early when a manual/gear mode exists (fan.py:378 `if manual_name: return`).
  H7124/H7129/H7126 have `gearMode`, so their fan entity path is unchanged.
- The fan entity (purifiers get one: `is_fan` includes DEVICE_TYPE_PURIFIER, device.py:565-572, since
  46e0eb9 / #37) already sends `WorkModeCommand(1, 1..3)` for speeds and exposes Sleep/Auto/Turbo
  as preset modes — likely what "worked" for the reporters. Ask them to confirm.

## Proposed fix (minimal; keeps unique_id, option list, and #201)
### custom_components/govee/models/device.py
- Add property `purifier_gear_work_mode -> int | None`: return None when a
  `CAPABILITY_MODE`/`INSTANCE_PURIFIER_MODE` capability exists (pattern 1); otherwise, on the
  `CAPABILITY_WORK_MODE`/`workMode` cap, return the `value` of the `workMode` field option named
  `gearMode` (fallback 1 if gearMode is only present under modeValue). Place next to
  `get_purifier_mode_options` (~line 1073).
### custom_components/govee/select.py (GoveePurifierModeSelectEntity, 805-866)
- `__init__`: `self._gear_work_mode = device.purifier_gear_work_mode`.
- `async_select_option`: if `_gear_work_mode is not None` send
  `WorkModeCommand(work_mode=self._gear_work_mode, mode_value=value)` (already imported, used at 793);
  else keep the `ModeCommand(purifierMode)` path for H6006-style devices.
- `current_option`: for the gear path return the name whose value == `state.mode_value` when
  `state.work_mode == self._gear_work_mode`; else None-safe fallback as today. (WorkModeCommand is
  applied optimistically via `apply_optimistic_work_mode`, coordinator.py:5475-5476; workMode state is
  parsed at models/state.py:442-444.)
- Optional (separate, tiny): in coordinator.py:5465-5471 set `state.purifier_mode = command.value`
  for `INSTANCE_PURIFIER_MODE` so pattern-1 current_option is not stuck on the first option.
### Not touched
- fan.py (#201 tiered path stays as is). H7121 has no gearMode -> `get_purifier_mode_options()`
  returns [] -> no purifier select is created, so the change cannot reach it.
- No new entity, no unique_id change, no strings change (option names are raw device names).

## Tests to add
- tests/test_purifier.py (entity tests at ~140-240 use H6006 fixture `mock_purifier_device`):
  - New class using conftest `mock_air_purifier_device` (H7126 workMode/gearMode fixture,
    tests/conftest.py:~500-558): selecting "High" sends `WorkModeCommand(work_mode=1, mode_value=3)`,
    NOT `ModeCommand`; assert `not isinstance(command, ModeCommand)`.
  - `current_option` returns "Low" for state work_mode=1, mode_value=2 (fixture: Sleep=1/Low=2/High=3);
    returns first option/None-safe when work_mode is Auto (3).
  - Existing H6006 test `test_select_purifier_mode` keeps asserting ModeCommand(purifierMode) (regression guard).
- tests/test_models.py (~324): `purifier_gear_work_mode == 1` for H7126 fixture; `None` for H6006
  (pattern-1) device; `None`/no select for an H7121-shaped device without gearMode.
- tests/test_cov_select.py:695 `test_purifier_mode_select_created` stays green; add a branch test
  for the fallback-to-1 path to keep coverage (select.py/device.py > 96%).
- tests/test_fan.py: no change; run the #201 tier tests as regression (`-k "tier or 201"`).

## Verify
```
grep -n "purifier_gear_work_mode" custom_components/govee/models/device.py custom_components/govee/select.py
grep -n "WorkModeCommand(work_mode=self._gear_work_mode" custom_components/govee/select.py
pytest tests/test_purifier.py tests/test_cov_select.py tests/test_models.py tests/test_fan.py -q
pytest tests/test_fan.py -q -k "tier or 201"
black --check . && flake8 . && mypy custom_components/govee
```

## Reply brief (post after the release that ships it)
The Mode dropdown on workMode purifiers (H7124/H7129/H7126) sent a `purifierMode` command these models
don't have; it now sends the gearMode speed through `workMode`, as the app does. The bug predates
v2026.9.12 — v2026.9.6 just stopped hiding the rejection — and the H7121 fix from #201 is unaffected.
Sleep/Auto/Turbo stay on the fan entity's preset modes; please confirm Mode and fan speed both work.
