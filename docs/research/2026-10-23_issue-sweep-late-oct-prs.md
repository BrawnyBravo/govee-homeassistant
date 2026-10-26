# Open PR triage (2026-10-23)

Method: `gh pr view/diff/checks`, PR heads fetched to `refs/prtriage/N`, pairwise `git merge-tree` for textual conflicts. Review was a diff skim plus grep for CLAUDE.md rule violations (`_attr_name`/`_attr_icon`, info logging, f-string logging, type: ignore, no cover). It was not a line-by-line audit of the 5.6k-line kettle stack.

None of the 19 PRs fixes #246 (H1270 transport flapping), #242 (online:false), #243 (H5054 all-digit ID) or #222 (MQTT silent). Two are only loosely related: #252 (BLE: matching-MAC enrolment, idle link release) touches the H1270 BLE path but does not address LAN/BLE switching, and #259 is MQTT sweep hygiene, not #222's no-frames case.

CI: the fork PRs from StevenC4 (#229-#235), snoack (#247) and EasyBizz (#248) have **no checks run**: they wait on maintainer approval. They need "Approve and run" or local gating (py3.12 mise venv) first.

## Textual conflicts (merge-tree, pairwise)
- 238 x 259: tests/test_issue_195.py (trivial; both append tests)
- 247 x 250, 247 x 251: coordinator.py
- 250 x 251: __init__.py, coordinator.py
- 250 x 255: coordinator.py
- 251 x 255: __init__.py
- 254 x 255: scene_cache.py
- 235 (kettle stack tip) x 251/254/259: coordinator.py; x 254: CLAUDE.md; x 255: config_flow.py
- No conflicts: 248, 252, 253, 256, 257 against any other PR.

## Per PR

### Kettle stack #229 -> #235 (StevenC4, issue #228)
These are stacked: each branch contains the previous one (1..7 commits on main@82cbd92, 0 behind). The diffs below are cumulative. Per-layer increments are roughly: 229 17f +715/-8, 230 +1.9k (water_heater platform, entities, ca/es/en strings), 231 +0.8k (Brew-mode select), 232 +0.5k (slot labels, **config_flow.py options**), 233 +0.4k (on-base binary sensor, button event, frame capture log), 234 +0.5k (`govee.request_status` service + status_burst.py), 235 +0.85k (experimental keep-warm writes of raw `3a 22` frames, opt-in).
- CI: none ran (fork). Mergeable: yes (BLOCKED only by checks/review).
- Quality: well documented, with many tests per layer, translation keys present and `_attr_name = None` only on the main feature entity (allowed). Concerns:
  - Several `# type: ignore[arg-type]` on `KettleManager(coordinator)` in tests only. Fine.
  - Every layer edits CLAUDE.md, ARCHITECTURE.md and README, and commits `docs/_research/2026-09-30_h7175-kettle.md`.
  - 232 adds config_flow options, so config_flow.py must stay at 100% coverage: verify.
  - 234 adds a public service, so services.yaml, strings and `async_setup` registration need checking.
  - 235 writes undocumented frames and is self-described as "fine to decline".
- Verdicts:
  - #229: **MERGE-AFTER-FIX**. Approve CI and confirm it is green; it is the actual #228 stale-temperature fix and small.
  - #230-#233: **MERGE-AFTER-FIX**. Approve CI, then review each layer's compare link and verify config_flow 100% on #232. Merge in order.
  - #234: **MERGE-AFTER-FIX**. Same as above; also confirm the service is registered in `async_setup_services`, not per entry.
  - #235: **REJECT / defer**. It is experimental raw-frame control of a kettle, the author offers to drop it, and it is the largest conflict surface (coordinator, config_flow, CLAUDE.md vs 251/254/255/259).

### #238 BrawnyBravo: H5108 MQTT sweep exclusion (fixes #237)
2 files, +27/-1. CI 6/6 pass. CLEAN. It is a one-line `MQTT_STATUS_QUERY_EXCLUDED_SKUS` add plus a test, and the reporter verified it. Conflicts only with #259's test file (trivial). **MERGE** (first).

### #247 snoack: H5086 energy resets (refs #200)
7 files, +580/-22. No CI (fork). Conflicts with 250 and 251 in coordinator.py.
- The new `EnergyCounter` model switches the energy sensor from `total_increasing` to `total` + `last_reset`, persisted via RestoreEntity extra data. It has captured-data tests and logic validated on govee2mqtt.
- Concerns:
  - It changes the state_class for existing users. HA accepts this, but the LTS history around the switch should be checked.
  - It adds a 60 s MQTT status tick whenever an H5086 is present. That is more AWS IoT queries, interacting with #237/#259 session-drop handling: with #259, a refusal stops the plug queries too, which is fine.
  - It filters pushes on `stc[0]==19`, a heuristic.
- **MERGE-AFTER-FIX**: approve and run CI, then rebase onto 250/251 after they land.

### #248 EasyBizz: H8057 4th segment RGB via ptReal
3 files, +290/-2. No CI (fork). No conflicts. SKU-scoped (index 3 only, mask 0x000008), with good failure handling (raises translated error, no REST retry) and extensive tests. The hardware evidence covers the raw frame only, not the integration code. No issue linked. **MERGE-AFTER-FIX**: approve CI. SKU-scoped unverified fixes are acceptable per the HACS policy.

### #250 BrawnyBravo: 429 back-off hold, send-once, persisted request counts
11 files, +827/-22. CI pass, CLEAN. Mentions #226 (outage UpdateFailed for group/H5054 accounts). Conflicts with 247, 251, 255 (coordinator/__init__). Each fix has a failing-on-main test. Test stubs use `type: ignore[override]` (tests only). **MERGE** (early, since it is the conflict hub).

### #251 BrawnyBravo: account login / MQTT robustness
14 files, +1179/-254. CI pass, CLEAN. Touches config_flow.py (100% rule; CI coverage passed). It adds `_LOGGER.info("Govee OpenAPI event channel reconnected")`, which violates the "info only for user action" rule; it should be debug. Conflicts with 247, 250, 255, 235. **MERGE-AFTER-FIX**: demote that info log to debug, rebase after #250.

### #252 BrawnyBravo: BLE enrolment by MAC, idle BLE release, LAN hardening
13 files, +828/-44. CI pass, CLEAN, no conflicts. It is a solid fix, but it assumes BLE MAC = last 6 octets of the cloud ID (non-matching devices lose BLE). The 120 s idle disconnect adds reconnect latency on H1270 (handshake), which has not been measured. That may affect the #246 H1270 reporter, positively (no proxy slot hogging) or negatively (latency). Not a #246 fix. **MERGE**, and mention it in the #246 thread.

### #253 BrawnyBravo: heater target/auto-stop restore and poll merge
6 files, +404/-38. CI pass, CLEAN, no conflicts. It is a clear bug fix (unit conversion on restore, poll overwrite) and is tested. **MERGE**.

### #254 BrawnyBravo: segment brightness send, exact brightness, scene refresh
34 files, +910/-194. CI pass, CLEAN. New `brightness.py`, which changes the brightness mapping for all lights (behavioural, broad). Edits CLAUDE.md and strings in 3 languages. Conflicts with 255 (scene_cache.py) and 235. Tests are broad. **MERGE** (after 255 or rebase). Watch for user reports on brightness levels.

### #255 BrawnyBravo: keep segment modes on options save, per-entry diag device, state merge
15 files, +634/-50. CI pass, CLEAN. Touches config_flow.py (CI coverage green) and a `type: ignore[arg-type]` in scene_cache.py (prod code; minor). Changes the diagnostics device to per-entry, so check device-registry migration/orphan cleanup for the old `hub` device. Conflicts with 250, 251, 254, 235. **MERGE** (after 250/251, then rebase 254).

### #256 BrawnyBravo: daily-release workflow gates
2 files, +38/-13. CI pass. Fixes real wedge and draft bugs in `.github/workflows/daily-release.yml`. Touches no custom_components code. **MERGE** (anytime; best before tonight's 03:00 UTC run).

### #257 BrawnyBravo: leak fallback latch after reload
2 files, +383/-3. CI pass, no conflicts. It keeps the MQTT wet/dry stamps in `hass.data`. CLAUDE.md says IoT creds are not kept in hass.data at runtime, but this is a different state and is acceptable; prefer runtime_data if possible (minor). **MERGE**.

### #259 meeowgler: stop the sweep on account-wide status-query refusal
7 files, +194/-3. CI pass. It stops the sweep after 3 distinct SKUs drop without an answer in between. It adds a diagnostics field and updates strings.json and en.json, but not ca/es. Conflicts with 238 (test file only) and 235. It uses a warning, not info; fine. Related to #222/#237 churn but fixes neither. **MERGE** (after 238; resolve the test-file append).

## Proposed merge order
1. #256 (CI only)
2. #238
3. #259 (rebase the test file)
4. #253
5. #257
6. #252
7. #248 (after CI approval)
8. #250
9. #251 (info->debug; rebase)
10. #255 (rebase)
11. #254 (rebase scene_cache)
12. #247 (CI approval + rebase coordinator)
13. #229 -> #234 kettle stack in order (CI approval, rebase each against the new coordinator/config_flow)
14. #235: defer/decline.
