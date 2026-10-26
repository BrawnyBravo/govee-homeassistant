# validate-plan: issue-sweep-late-oct (correctness review)

Reviewed 2026-10-23 against `origin/main` = 82cbd92, PR heads in `refs/pr/N` (all present except refs/pr/235),
`gh issue list` / `gh pr list` as of this run. Security is out of scope (separate review).

Severity counts: BLOCKER 2, MAJOR 10, MINOR 14.

---

## BLOCKER

### B1. T-025 (+T-008, T-012): "no production code calls the deprecated registry method" stops being true mid-plan
- Evidence: `git grep -n 'async_get_device(' refs/pr/255 refs/pr/234 -- custom_components` shows
  `custom_components/govee/__init__.py:411,416` (#255 `_async_migrate_hub_device`) and
  `custom_components/govee/config_flow.py:959` (#234). HA 2026.10.2 `helpers/device_registry.py:2039-2066`:
  `async_get_device` calls `report_usage(... breaks_in_ha_version="2027.8.0")`; `async_get_device_by_identifier`
  does not exist on HA 2025.1 (venv312).
- Ran the full suite under `.cc-sessions/venv314` on each PR head: #255 adds two new failures
  (`tests/test_setup_entry.py::test_hub_device_migrates_in_place_for_a_single_entry`,
  `::test_hub_device_splits_when_two_entries_share_it`) on top of the two known ones. Every other PR head tested
  (#234 #247 #248 #250 #251 #252 #254) fails only the known two.
- T-025's verify only runs `test_dual_probe.py` and `test_setup_entry_account.py` on 3.14, so it passes while the
  3.14 suite still fails and production code still calls a method that HA removes in 2027.8. The outcome "suite passes
  on Python 3.14" is not met.
- Fix: T-025 adds a small compat helper (e.g. `_registry_device(dr, identifier)` that prefers
  `async_get_device_by_identifier` and falls back to `async_get_device` on old HA) and uses it in `__init__.py` and
  `config_flow.py`. Add `__init__.py` and `config_flow.py` to files[], add `T-012` to depends_on, and replace verify with:
  - `.cc-sessions/venv314/bin/pytest -q --no-cov -p no:cacheprovider -o addopts= tests`
  - `.cc-sessions/venv312/bin/pytest -q --no-cov -p no:cacheprovider -o addopts= tests`
  - `! grep -rnE '\.async_get_device\(' custom_components/govee tests | grep -v '_registry_device'` (or the helper's name)
  - `.cc-sessions/venv312/bin/pytest -q -p no:cacheprovider -o addopts= --cov=custom_components.govee.config_flow --cov-fail-under=100 tests`
  Drop the "test-only" claim from the notes.

### B2. Release replies: almost nothing in this plan is "auto". Commit subjects don't carry `#N`
- Evidence: the reply step (`.github/workflows/daily-release.yml`, "Reply on issues and PRs") replies only to `#N` found
  in commit subjects from `git log <tag>..HEAD --format='%h %s' -- custom_components/`. Across all 17 PR heads only two
  subjects reference anything: `82de6d8 ... (#237)` (#238) and `3aa531c`/`d436d5b ... (#200)` (#247). Simulating the
  whole chain (`merge-tree` + `commit-tree` with `--no-ff` merge commits) and running the workflow's own log command:
  `git log --format=%s origin/main..<sim> -- custom_components/ | grep -oE '#[0-9]+' | sort -u` → `#200 #237`.
- So, with the plan as written, the nightly bot never thanks or notifies the authors of #229-#234, #248, #250-#257, #259
  and #254, never replies on #228 or #246 (via #252), and the fix tasks reply only if the dev agent happens to put
  `(#243)` etc. in the subject. The plan's Coverage table marks all of these "auto". That breaks the CLAUDE.md rule that
  every thread gets its reply after the release.
- Simulation also shows the #238 merge commit is TREESAME under `custom_components/`, so it's hidden from the
  path-limited log. Only the PR's own commit (#237) shows up.
- Fix: (a) every merge task makes a `--no-ff` merge commit whose subject is `Merge PR #N: <title> (refs #issue)` and
  adds the verify `git log --format=%s v2026.10.0..HEAD -- custom_components/ | grep -q '#N'`. (b) Every fix task
  (T-013..T-024) requires a `(#issue)` subject on the commit touching custom_components, with the same style of verify
  (e.g. T-013: `git log --format=%s v2026.10.0..HEAD -- custom_components/ | grep -q '#243'`). (c) T-026 queues explicit entries for PR threads
  that a path-limited log can't reach: #238 (thank you, the merge is TREESAME), #256 (no custom_components change), and
  the kettle layers #229, #230, #232, #233 (merged as ancestors, never named in a subject). Make the #228 entry
  unconditional.

---

## MAJOR

### M1. T-011/T-012 vs T-013..T-022: kettle merges run in parallel with coordinator fix tasks
- Evidence: T-013, T-014, T-016, T-017, T-020, T-022, T-025 and T-026 depend only on T-010, while T-011 (#231) and
  T-012 (#234) still have to merge. Simulated: #231 conflicts with main+chain in `coordinator.py`; #234 conflicts in
  `config_flow.py`. #231 rewrites `async_control_device` into a wrapper plus `_async_control_device`
  (kettle follow-up). T-015, T-017, T-020 and T-023 all edit that function.
- The plan says (stage 1) that fixes are written on merged code so they don't create new PR conflicts. Letting the fix
  tasks run before the kettle merges contradicts that and makes the 5.6k-line kettle merge resolve against moving code.
- Fix: add `T-012` to depends_on of T-013, T-015, T-016, T-017, T-020 and T-022 (every task that touches
  `coordinator.py` or command dispatch). Or, if kettle review is slow, move T-011/T-012 after the fix tasks on purpose
  and say so. Either way, pick one order.

### M2. Same-hunk parallel edits in `async_control_device` / dispatch with no edges
- T-015 (BLE tier at coordinator.py:4638-4642), T-017 (offline reply → `state.online=False` inside
  `async_control_device`), T-020 (zone toggles over the passthrough inside the dispatch, near :4692) and T-023
  (confirmer hook after MQTT/REST success in `async_control_device`) all edit the same function. Their only shared
  dependency is T-010, so `--parallel` can run them together.
- Fix: serialize them as T-015 → T-017 → T-020 → T-023 (add `T-015` to T-017.depends_on, `T-017` to T-020.depends_on and
  `T-020` to T-023.depends_on). Also add `T-015` to T-018.depends_on: T-018's "BLE healthy" has to mean transport
  health, not "outside T-015's back-off window", and the two edit neighbouring code.

### M3. T-018 vs T-021 (light.py) and T-018 design ambiguity vs #226
- T-018 "folds light.py's LAN override into" `GoveeEntity.available` (entity.py:73-87). T-021 adds `GoveeRingLight`,
  which shares an implementation with `GoveeMainPanelLight` (`_allow_lan_availability = False`, light.py:458). No edge
  links them, and both edit the availability code in light.py.
- #226 (CLAUDE.md): "a total cloud outage raises UpdateFailed so cloud-dependent entities go unavailable; a
  whole-device light whose LAN transport is healthy stays available". Today that works because light.py:182-188
  returns True *before* `super().available` (which checks `last_update_success`). Folding the override in has two
  possible results. If `device_reachable` sits after the coordinator check, the #226 light goes dark in an outage. If
  it sits before, every entity of a device with healthy LAN, BLE or recent MQTT (scene selects, segment lights,
  switches) stays available during a total cloud outage, which breaks the other half of the rule.
- Fix: write the rule into T-018: `GoveeEntity.available = super().available and (is_group or
  coordinator.device_reachable(id))`; leave light.py's pre-coordinator LAN bypass as is (only `_allow_lan_availability`
  lights skip `last_update_success`). Add `T-018` to T-021.depends_on, and T-021 sets `_allow_lan_availability = False`
  on `GoveeRingLight`. Add `tests/test_thermometer.py tests/test_water_leak.py` to T-018's pytest verify: BFF
  thermometers and water detectors keep their own mixin (sensor.py:363-382) and must not change (#97/#145).

### M4. T-016 `mqtt_silent` gives false positives in exactly the #259 / status-poll-off case
- A connected session whose sweep is stopped (#259's `_status_queries_refused`, or the re-query option set to 0) gets
  inbound frames only when a device pushes on its own. An all-lights account left untouched overnight gets zero
  inbound messages for 6 h and would raise a repair telling the user to reconfigure, which fixes nothing.
- Fix: arm the watchdog only when status queries were published and none came back since connect (status re-query on
  and not refused), or when the account has push-reporting sensors. Add a test case "sweep refused → no repair" to
  `tests/test_issue_222.py`.

### M5. T-026 verify is unstable, and its briefs can be posted before the work they describe ships
- The nightly workflow empties `docs/release-replies.md` after posting (step 2 of the reply prompt). Once a release
  runs, `grep -q '^## #224' docs/release-replies.md` fails for good, so `/blitz:check --scope plan` (which re-runs
  every verify) can't pass.
- T-026 depends only on T-010. Its #235 brief says "layers 229-234 merged" and it closes #235. If a release goes out
  before T-011/T-012 merge, the bot posts a false statement.
- Fix: replace the verifies with history checks, e.g. `git log -p --format= -- docs/release-replies.md | grep -q '^+## #224'`
  (the same for #260, #244, #213), and keep `! grep -q '^## #249' docs/release-replies.md`. Add `T-012` to depends_on.

### M6. Merging #238 and #229 auto-closes #237 and #228 before release or validation
- Evidence: `gh pr view N --json closingIssuesReferences` → #229: [228], #238: [237]. When a PR head lands in `main`,
  GitHub marks the PR merged, and that closes the issues it links. CLAUDE.md: "leave issues open until the reporter
  validates". The comments research also says #237 should close only "after release + reporter confirms".
- Fix: in T-002 and T-011, before merging, edit the PR body (maintainers can) from "closes" to "refs", or reopen right
  after. Add verifies: `test "$(gh issue view 237 --json state -q .state)" = OPEN` (T-002) and the same for 228 (T-011).
  These need `gh`, so note that they run with the sandbox disabled.

### M7. T-009 / #254: the conflict picture is incomplete, and the fix tasks will make it worse
- Sequential simulation (main + 256, 238, 259, 253, 257, 252, 248, 250, 251, 255, 247, 231, 234, then 254), using
  `git merge-tree --write-tree` and continuing with `-X theirs` after each conflict:
  - #256, #238, #253, #257, #252, #248, #250: clean
  - #259: `tests/test_issue_195.py` (expected)
  - #251: `__init__.py`, `coordinator.py` (expected)
  - #255: `__init__.py`, `coordinator.py` (**T-008 notes don't mention it**; pairwise sources: #250 coordinator.py, #251 __init__.py)
  - #247: `coordinator.py` (expected)
  - #231: `coordinator.py` (expected)
  - #234: `config_flow.py` (**not in T-012 notes**; the source is #255, pairwise) and config_flow.py has to stay at 100 %
  - #254 last: `CLAUDE.md`, `coordinator.py`, `scene_cache.py`. Pairwise: scene_cache.py ← #255; CLAUDE.md and
    coordinator.py ← #231/#234. T-009 notes list only scene_cache.py.
- The coordinator hunk is semantic. #231 and #254 both split `async_control_device` into a wrapper plus a method named
  `_async_control_device` (kettle follow-up vs. segment-colour rollback), so the fix has to chain them, not pick one.
- Predicted extra conflicts from the fix tasks, all landing before #254:
  - T-015, T-017, T-020, T-023 edit that same wrapper/dispatch region. #254 also edits :4724
    (`SegmentBrightnessCommand` → `_dispatch_segment_command`) next to T-020's ptReal segment path.
  - T-021 rewrites `GoveeMainPanelLight.async_turn_on` to add `kelvin=` and share code with the ring. #254 rewrites the
    same lines (light.py:798-823, `ha_to_device_brightness(MAIN_PANEL_BRIGHTNESS_RANGE, …)` and the
    optimistic-after-accept change). Expect a guaranteed conflict there.
  - T-018's light.py availability edit is near #254's hunks at light.py:67-74/323-425 (lower risk).
  - Nothing planned touches scene_cache.py or entity.py, so no new conflict there beyond #255's.
- #254 is not only a brightness change. It carries 12 commits (segment brightness send, scene refresh signal, select
  unknown state, purifier "low", H1270 main-panel name, failed-segment rollback). Holding it back delays all of them.
- Recommendation: after T-027, ask BrawnyBravo (active; 8 PRs) to rebase #254 onto `main` rather than have the
  maintainer resolve ~5+ hunks across coordinator.py and light.py on code they didn't write. Queue the request through
  `docs/release-replies.md`, since no commit references #254. T-009 then re-fetches `refs/pr/254` before its checks.
  The alternative is to merge #254 first, on a day of its own, so the fix tasks are written on top of it.
  Either way, T-021's port of the H1252 patch should be planned against #254's new main-panel code.
- Fix to T-009: add `T-021` to its notes as a known conflict, and add verify gates after the merge:
  `.cc-sessions/venv312/bin/flake8 .`, `.cc-sessions/venv312/bin/mypy custom_components/govee`,
  `.cc-sessions/venv312/bin/black --check .`, and
  `.cc-sessions/venv312/bin/pytest -q -p no:cacheprovider -o addopts= --cov=custom_components.govee --cov-fail-under=95 tests`.
  T-027's gates run before #254, so #254's ~900 lines are never gated locally.

### M8. T-009 first verify can pass falsely
- `git describe --tags --abbrev=0 origin/main` is the right tag source. Releases are lightweight tags made by
  `gh release create --target <bump SHA on main>`; `git fetch --tags` works in the sandbox (tested: rc 0, `v2026.10.0`).
- It only proves #247 (T-010) shipped. T-011..T-026 (kettle merges and every fix task) can land on a later day. #254
  would then merge while other unreleased custom_components changes sit on main, and they'd ship together, which
  defeats the point of T-009. Condition (3) "nothing else merges the same Eastern day" isn't checked at all.
- It can also never pass if #247 is cherry-picked or rebased during T-010's conflict resolution, or if `refs/pr/247` is
  re-fetched after the author pushes again.
- Replacement check (true only if the main side right before #254's merge had nothing unreleased under
  custom_components):
  `git fetch -q --tags origin && M=$(git rev-list --merges --ancestry-path refs/pr/254..HEAD | tail -1) && test -n "$M" && T=$(git describe --tags --abbrev=0 "$M^1") && git diff --quiet "$T" "$M^1" -- custom_components/ ':(exclude)custom_components/govee/manifest.json'`

### M9. T-021 needs coordinator methods that no task creates
- T-021 calls `coordinator.async_set_ring` and `async_set_main_panel(kelvin=)`. On main, `async_set_main_panel`
  (coordinator.py:4525) accepts only `rgb`/`brightness`, and `async_set_ring` doesn't exist. T-020's notes and verify
  don't add either, and T-021's files[] has no coordinator.py, so a file-disjointness scheduler will run it next to
  other coordinator tasks.
- Fix: move both into T-020 (notes and verify `grep -q 'def async_set_ring' custom_components/govee/coordinator.py`;
  `grep -q 'kelvin' <(sed -n '/def async_set_main_panel/,/-> bool/p' custom_components/govee/coordinator.py)`), or add
  coordinator.py to T-021's files[].

### M10. T-028 (added to tasks.json at 12:33Z, during this review) is missing from T-027's depends_on
- T-028 (LAN scan source-address trust, depends on T-004) isn't in T-027's depends_on. T-009 (#254) depends only on
  T-027, so #254 can merge while T-028 is still open, and the two could ship in the same release. That breaks #254's
  isolation, and T-028 never goes through the final coverage, mypy and black gates.
- Its own verify is fine. `record.setdefault("ip", addr[0])` is at api/lan.py:364 on main and on #252. Among the
  merged PRs only #252 touches lan.py, so T-004 → T-028 creates no new merge conflicts. tests/test_lan.py and
  tests/test_lan_integration.py exist, and tests/test_lan_scan_trust.py is created by the task.
- Fix: add `T-028` to T-027.depends_on.

---

## MINOR

### m1. T-011: `! git merge-base --is-ancestor refs/pr/235 HEAD` passes vacuously
- `refs/pr/235` isn't fetched. merge-base exits 128 and the `!` turns that into 0 (ran it: rc=0).
- Fix: `git rev-parse -q --verify 'refs/pr/235^{commit}' >/dev/null && ! git merge-base --is-ancestor refs/pr/235 HEAD`,
  and add `git fetch origin +refs/pull/235/head:refs/pr/235` to the notes (head 5aeef68).

### m2. T-022: `! grep -nE 'TODO|NotImplementedError' command_confirm.py` passes when the file is missing (rc 2)
- Harmless while the first verify exists. Prefix it with `test -f custom_components/govee/command_confirm.py &&`.

### m3. T-013 verify misses one of the three call sites
- The device.py site is `) or (device_id.isdigit())` (models/device.py:1326). The pattern `or device_id.isdigit()`
  doesn't match it because of the paren, and lan_client.py:226 isn't checked at all. The verify can pass with only
  coordinator.py:4880 changed.
- Fix: `test "$(grep -rn 'isdigit()' custom_components/govee --include=*.py | grep -v 'def looks_like_group_id' | grep -vc 'looks_like_group_id')" -le 1`.
  Simpler and acceptable:
  `! grep -nE 'device_id\.isdigit\(\)' custom_components/govee/coordinator.py custom_components/govee/api/lan_client.py && ! grep -nE 'or \(?device_id\.isdigit' custom_components/govee/models/device.py`.
  Also update CLAUDE.md's "Device ID Detection" section, which still says `device_id.isdigit()`.

### m4. files[] are incomplete, so `--parallel` disjointness checks can't be trusted
- T-017 also edits strings.json, translations/en.json, entity.py and the new tests/test_issue_242.py.
- T-016 also edits repairs.py and tests/test_issue_222.py.
- T-019 also edits strings.json, en.json, icons.json and tests/test_issue_258.py.
- T-021 also edits icons.json, coordinator.py and tests.
- T-020 also edits models/state.py (its verify greps models/) and tests/test_ceiling_light_zones.py.
- T-013 also edits tests/test_issue_243.py; T-018 edits tests/test_issue_242_reachable.py.
- T-016, T-017, T-019 and T-021 all edit strings.json and en.json with no edges between T-016 and T-017.
- Fix: list the real files and add `T-016` to T-017.depends_on (or T-017 to T-016) so the strings.json edits are serialized.

### m5. T-008 notes don't mention #255's conflicts
- #255 conflicts in `__init__.py` (vs #251) and `coordinator.py` (vs #250). Add that to the notes.

### m6. T-012 notes don't mention #234's config_flow.py conflict
- The conflict is with #255's options-flow changes. Add it to the notes, since config_flow.py has to stay at 100 %.

### m7. Fork-PR gates are named in notes but not enforced
- T-005, T-010, T-011 and T-012 say "full suite + flake8 + mypy + black locally", but their verifies run only pytest.
  A merge that breaks black or mypy reaches main and blocks the nightly release (CI must be green).
- Fix: add `.cc-sessions/venv312/bin/flake8 . && .cc-sessions/venv312/bin/mypy custom_components/govee && .cc-sessions/venv312/bin/black --check .`
  to each of them. All three run in under 5 s on main.

### m8. T-002 verify misses tests/test_diagnostics.py
- #259 changes tests/test_diagnostics.py (+18 lines) and diagnostics.py. Add that test file to the verify.

### m9. T-026 `close: yes` for #260 and #235 contradicts the queue file's own rule
- The rule at the top of docs/release-replies.md: "Only use yes when the reporter confirmed the fix or asked for it
  to be closed."
- Mechanically it works: the prompt runs `gh issue close N --reason completed`, `gh issue close` handles PR numbers,
  and the tool is allow-listed. But "completed" is the wrong reason for a declined PR or a duplicate.
- Fix: either have the maintainer close #235/#260 by hand, or amend the queue header and workflow prompt to allow
  maintainer-decided closes (`close: duplicate|declined` mapped to `--reason "not planned"`, or `gh pr close` for
  PRs). That's a workflow edit outside this plan's files.

### m10. New issue #261 has no task and no out-of-scope line
- #261 (H1A42 `govee.set_segment_color` doesn't change segments) was opened today at 12:13Z, after the plan was
  written. Add a T-026 entry asking for Download diagnostics, plus an Out-of-scope line. It may also overlap #254's
  "forget a segment colour Govee rejected" commit.

### m11. T-001's CLAUDE.md edit is already in #256, and memory says 03:00 UTC
- #256 itself changes CLAUDE.md to "02:00 UTC (10pm EDT, 9pm EST)" and "six required checks", so T-001's CLAUDE.md
  work is a no-op. The claim is correct: the cron goes `0 3 * * *` → `0 2 * * *`.
- Memory file `daily-release-cloud-routine.md` still says 03:00 UTC. Update it after the merge (it's not a repo file).

### m12. T-015: "skip the BLE tier while LAN is healthy" is too broad
- LAN carries only power, brightness, colour and colour temperature (README:179). Skip BLE only for LAN-capable
  commands when LAN is healthy. Otherwise H1270 commands LAN can't carry fall to MQTT/REST instead of BLE.

### m13. T-019: the `GoveeReportedOnlineBinarySensor` needs its own availability
- It must override `available` like `GoveeDeviceConnectivity` (binary_sensor.py:341-349). Otherwise the base or BFF
  mixin hides it, or it shows unavailable exactly when it reports offline. Put that in the notes and the test.

### m14. T-027's per-module ">96 %" rule isn't enforced
- Optional fix:
  `.cc-sessions/venv312/bin/coverage report --fail-under=0 | awk '$NF ~ /%/ && $1 ~ /custom_components/ {gsub("%","",$NF); if ($NF+0 < 96) {print; bad=1}} END{exit bad}'`
  after the coverage run.

---

## Checked and correct
- Every merge-task grep symbol exists in its PR head:
  - `exclude-drafts` (#256), `MQTT_STATUS_QUERY_EXCLUDED_SKUS … "H5108"` (#238, one line, const.py:369)
  - `def mqtt_status_queries_refused` (#259), `_async_last_state_in_celsius` (#253), `LEAK_MQTT_STORE_KEY` (#257)
  - `DISCONNECT_DELAY = 120` (#252, api/ble.py), `_control_h8057_segment_color` (#248), `def _request_counts_store` (#250)
  - `def is_connection_error` (#251, api/auth.py), `def _async_migrate_hub_device` (#255)
  - `POWER_MONITORING_STATUS_INTERVAL` (#247, const.py), `KETTLE_FOLLOWUP_DELAYS` (#231)
  - `class StatusBurst` and `^request_status:` (#234), `def ha_to_device_brightness` (#254, brightness.py)
- The `_LOGGER.info("Govee OpenAPI event channel reconnected")` line already exists on main (openapi_events.py:156).
  #251 only moves it, so demoting it is a pre-existing cleanup, and T-007's grep matches it on both.
- Every grep/git verify fails on main today. The only exceptions are the vacuous negations m1, m2 and T-026's
  intended `! … #249`.
- Every pytest target file in verify either exists on main or is a new test file the task creates.
- `--cov=custom_components.govee.config_flow --cov-fail-under=100 -o addopts=` measures that module only: ran it on
  main → `config_flow.py 368 0 100.00%`, 3598 passed, 30 s. flake8 (rc 0), black (153 unchanged) and mypy (no issues,
  45 files) all run clean from the repo root with the venv binaries.
- Symbols that exist as described:
  - `THERMO_HYGRO_BFF_READ_SKUS` (models/device.py:71, used in api/auth.py:883)
  - `_ble_write_eligible` (coordinator.py:5110, used :4642)
  - `mqtt_last_receive_for` (coordinator.py:670)
  - `_allow_lan_availability` (light.py:179/458)
  - `PTREAL_MAIN_PANEL_BIT = {"H1232": 16}` (const.py:208)
  - isdigit sites (device.py:1326, coordinator.py:4880, lan_client.py:226)
- H1252 is correct for the #223 patch (the issue title says H1232; holger-dunst's comments are about the H1252).
- Py3.14 claims reproduced: `_attr_translation_key` is a class property on HA 2026.10, and `async_get_device` raises in tests.
- Every open PR is covered, and every open issue is covered or out of scope except #261 (m10).
