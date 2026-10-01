# Research: open PRs #227 (fixes #226) and #225

Researched 2026-10-01 against main `2194835`. Both PRs are based on `2d7184d`, and both merge cleanly into main and into each other (`git merge-tree --write-tree`).
Local gates ran in scratch worktrees `<scratchpad>/wt-225` and `<scratchpad>/wt-227` (refs `refs/pr/225` and `refs/pr/227`), using venv
`/tmp/claude-1000/-home-lasswellt-Projects-govee-homeassistant/b7101f46-014d-44f1-8beb-88aa11ef75c4/scratchpad/venv` (py3.12, HA 2025.1.4, the CI py312 lane).

## Both are fork PRs, and CI has not run on either

- #227 (drewcotten, `fix/lan-light-cloud-outage`, head `a71e386`): four workflow runs show `action_required` (Type Checking, HACS/HASS, Style, Tests). A maintainer has to approve them.
- #225 (usednick, `fahrenheit-h5103`, head `1320693`): `gh pr checks` reports no checks, and no fork run appeared in the last 30 runs. CI was never triggered or still awaits approval.
- So both have to be gated locally (done below) or approved in Actions before merging.

## PR #227: preserve LAN light availability during cloud outages

Verdict: **merge with edits**. The edits are wording updates in docs and metadata. The code is sound.

What it changes:
- `coordinator.py` `_async_update_data`: moves the all-outage `UpdateFailed` raise from just after the result loop to the end, after rate-limit clearing (a no-op, since `successful_updates == 0`), `_apply_budget_pacing`, `_refresh_mqtt_health`, `_refresh_ble_staleness`, and the LAN rescan/reads.
  - `_refresh_lan_staleness()` moves out of the try block, so staleness still runs when the rescan or read raises.
  - On consecutive failures (`not self.last_update_success`) it calls `self.async_update_listeners()` before raising. This is needed because HA's `_async_refresh` suppresses listener notifications when the previous and current refresh both failed. The first failure keeps HA's normal notification.
- `light.py`: `GoveeLightEntity.available` returns True when the device is not a group, the LAN `TransportHealth.is_available` is set, and `device_state` is not None. Otherwise it falls back to `GoveeEntity.available`.
  - `GoveeMainLightEntity` opts out with `_allow_lan_availability = False`, because ring segments have no LAN path.
  - `GoveeNightLightEntity` does not subclass `GoveeLightEntity`, so it is unaffected. Segment lights in `platforms/` are unaffected.
- Tests: new `tests/test_lan_availability.py` (availability truth table, auxiliary and group cases) and `TestCloudOutage` in `tests/test_lan_integration.py`. The second uses the real coordinator, HA's refresh wrapper, and the fake UDP LAN responder. It covers repeated failures, local state publication, staleness and recovery, LAN-verified power/brightness/RGB/CT writes with no REST call, and cloud recovery. One fixture line was added to `tests/test_coordinator_outage.py`.
- `ARCHITECTURE.md`: the Polling bullet, an entity paragraph, and the update-flow diagram are updated.

Does it conflict with the CLAUDE.md design ("a total cloud outage raises `UpdateFailed` so entities go unavailable")?
- No. It is correctly scoped. `UpdateFailed` is still raised, and HA still logs once on failure and once on recovery, so the `log-when-unavailable` rule holds.
- Every cloud-dependent entity (sensors, selects, switches, groups, the main panel, the night light, segments) still goes unavailable.
- The only exception is the whole-device light, and only while its LAN transport is fresh, which is read-driven within `LAN_STALE_SECONDS`.
- This keeps the fix for finding 2 of the 2026-09-13 review (stale cloud-only state served silently).

Local gates on `refs/pr/227`:
- pytest: 3530 passed. Coverage 99.88% total. `coordinator.py`, `light.py`, and `config_flow.py` are each at 100%.
- black: clean. flake8: clean. mypy (strict, py3.12 target): "no issues found in 45 source files".

Behaviour notes (none of them block the merge):
1. Even with the cloud up, a light whose cloud `online` is False but whose LAN reads are fresh now shows as available (truth-table row `(True, True, False, ...)` falls into the LAN branch). This is arguably more correct: LAN-fresh devices already skip cloud reads through `_locally_fresh_devices`, so their `online` flag can be stale.
2. During an outage, every poll after the first notifies all listeners, even when nothing changed. Entities then write state once per poll interval. This is minor churn, and gating it is hard because the LAN overlay mutates state in place.
3. Budget pacing, MQTT health, and BLE staleness now also run during an outage, where before they were skipped. They are harmless: pacing only slows the poll and reads the daily counter.
4. LAN health is read-driven (see the memory note on #57). A light can show available while a LAN write fails confirmation and then falls through to REST, which fails offline. That case raises a translated `HomeAssistantError` through `_async_send_command`, which is acceptable.

Edits needed at merge, best done as a follow-up commit on main after merging the author's SHA:
- `CLAUDE.md:188`: change to "a total cloud outage raises `UpdateFailed` (after LAN reads and health refresh) so cloud-dependent entities go unavailable; a whole-device light with healthy LAN stays available (#226)".
- `custom_components/govee/quality_scale.yaml:87-89` (`entity-unavailable` comment): it says "every entity goes unavailable". Add the LAN-healthy whole-device light exception, and verify the claim against the code (per the quality-scale memory note).
- Optional: the comment block above the LAN try in `coordinator.py` ("Runs AFTER the cloud fan-in... return below fires HA listeners") is now only half true on the outage path. A one-line tweak would fix it.
- No strings, translations, or icons are affected.

Verify:
```
grep -n "_allow_lan_availability" custom_components/govee/light.py            # 2 hits: base True, GoveeMainLightEntity False
grep -n "if not self.last_update_success" custom_components/govee/coordinator.py
grep -n "unreachable for all" custom_components/govee/coordinator.py          # raise is after _refresh_lan_staleness()
grep -n "cloud-dependent" CLAUDE.md custom_components/govee/quality_scale.yaml
pytest tests/test_lan_availability.py tests/test_lan_integration.py::TestCloudOutage tests/test_coordinator_outage.py -q
pytest -o addopts="" --cov=custom_components.govee --cov-report=term-missing | grep -E "coordinator.py|light.py|config_flow.py|TOTAL"
black --check . && flake8 . && mypy custom_components/govee
```

## PR #225: add H5103 to FAHRENHEIT_REPORTING_SKUS

Verdict: **merge as-is.**

- `const.py`: adds a comment entry in the existing FAHRENHEIT_REPORTING_SKUS rationale block, matching the H5053/H5171 #173 entries, plus a one-line `"H5103",` in the frozenset after H5171. It follows the pattern exactly.
- `tests/test_thermometer.py`: adds three tests mirroring the H5171 trio:
  - `test_h5103_wifi_hygrometer_auto_converts_fahrenheit` (71.2 to about 21.78)
  - `test_h5103_celsius_override_passthrough`
  - `test_h5103_account_celsius_hint_beats_allowlist`
- The evidence is solid. The app shows 21.8 °C and HA showed 71.2 under Auto. The BFF harvest found 0 thermo-hygrometers, so there was no `fahOpen` hint and the SKU list is the only signal.
- Same model as #85 (CLOSED, "H5103 Temperature wrong Shown 74,1C, real in Govee App 23,4C"), which was closed with the Fahrenheit-option workaround. After the release, queue a `docs/release-replies.md` note on #85 (`close: no`).
- Local gates on `refs/pr/225`: 3520 passed, 99.88% coverage, `const.py` at 100%. black clean, flake8 clean, mypy clean.
- Nit, not blocking: the PR body is Claude-generated and says "93 passed (Python 3.13)". That is irrelevant, since the local py3.12 lane passes.

Verify:
```
grep -n '"H5103"' custom_components/govee/const.py
pytest tests/test_thermometer.py -k h5103 -q        # 3 passed
```

## Merge order and mechanics

- The two PRs don't conflict, so the order doesn't matter. Merge #225 first because it is trivial.
- Approve the fork workflow runs, or rely on the local gates. Then `gh pr merge N --squash`, or `git merge --ff-only refs/pr/N` to keep the author's SHA.
- After that, commit the #227 doc edits on main and wait for all 5 CI workflows (`gh run list --commit "$(git rev-parse HEAD)"`).
- Don't bump the version. The daily-release workflow cuts it, and the replies on #226, #227, #225, and #85 go out after the release.
- Clean up afterwards: `git worktree remove <scratchpad>/wt-225 <scratchpad>/wt-227; git update-ref -d refs/pr/225; git update-ref -d refs/pr/227`.
