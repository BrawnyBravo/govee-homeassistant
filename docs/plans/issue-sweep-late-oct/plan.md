# Plan: issue-sweep-late-oct (v2, after the validation and security round)

## Architecture
The work runs in five stages:
0. **Release pipeline first (T-001–T-003).** The security review rated the nightly release job CRITICAL, and the fork PRs are the trigger. With nothing merged, the job skips its Claude steps. The first merge of this wave would hand it ~20 referenced threads and 75 fork-authored commits, while the model holds an admin PAT and push/close tools. T-001 limits the model to writing two files with a read-only token, and shell does the posting. T-003 covers the settings only the maintainer can change. Every merge depends on T-003.
1. **Merges not held by #249 (T-004–T-012),** in conflict order: #238 → #259 → #253/#257 → #248 → #250 (the conflict hub) → #255 → #247 → kettle #231 → #233 → #234. Each merge task applies the security fixes for its PR before pushing.
2. **Our fixes (T-013–T-025).** They wait for the kettle merges (validate-plan M1). The `async_control_device` edits are chained T-017 → T-020 → T-023 (M2). strings.json edits are serialized via T-016 → T-017 → … The `models/device.py` edits are serialized T-014 → T-015.
3. **Held merges (T-026–T-028),** after the maintainer reads the #249 report. Fixes that need #252 come after them (T-029 BLE back-off, T-030 LAN scan trust).
4. **Gates, then #254 alone (T-031, T-032).**

**Tradeoffs chosen**
- **Release job:** hardened in code (T-001) plus maintainer settings (T-003). Rejected: disabling the Claude steps outright, which would lose replies.
- **#251/#252/#256:** held until the #249 report is read (user). The cost is that #251 then resolves conflicts against more code (#255, #247, kettle). Its author is active.
- **#254:** last, on its own release day, with conflicts resolved here (user). Rejected: asking the author to rebase, and merging it first.
- **#242:** reachable-if-any-transport, with the base class gated on coordinator health and light.py's LAN bypass kept (M3). Rejected: folding the bypass into the base, which breaks either half of #226.
- **#245:** built here, light commands only. Never resend to appliances or resend power-on (security F-03).
- **#235:** declined.

## File map
- `.github/workflows/daily-release.yml`, `scripts/release_replies.py` (new), `tests/test_release_workflow.py` (new): T-001; later merged with #256 (T-026)
- `SECURITY.md` (new), `.github/CODEOWNERS` (new), `.github/dependabot.yml`, `.github/workflows/*.yml` SHA pins, `install-stats.yml`, `uptime.yml`, `rebase_dependencies.yml` (deleted): T-002
- `custom_components/govee/const.py`: H5108 (T-004), `REQUEST_STATUS_MIN_INTERVAL` (T-012), `PTREAL_LIGHT_ZONE_SKUS` (T-020), `CONF_CONFIRM_COMMANDS` (T-023)
- `custom_components/govee/coordinator.py`: PR merges; `mqtt_silent` (T-016); offline reply (T-017); `device_reachable` (T-018); `bff_last_measurement_at` (T-019); `async_set_ring` and zone toggles (T-020); CommandConfirmer hook (T-023); `_ble_connect_backoff_until` (T-029)
- `custom_components/govee/__init__.py`, `config_flow.py`: `_registry_device` compat helper (T-013)
- `custom_components/govee/services.py`: admin-only, rate-limited `request_status` (T-012)
- `custom_components/govee/request_budget.py`: Store/Retry-After hardening (T-007)
- `custom_components/govee/binary_sensor.py`: leak flap fix (T-005), `GoveeReportedOnlineBinarySensor` (T-019)
- `custom_components/govee/api/auth.py`: re-login stop and `is_connection_error` fix (T-028)
- `custom_components/govee/models/device.py`: `looks_like_group_id` (T-014), H5111 (T-015)
- `custom_components/govee/api/lan_client.py`: group filter (T-014)
- `custom_components/govee/api/lan.py`: scan source trust and cap (T-030)
- `custom_components/govee/api/exceptions.py`, `api/client.py`: `GoveeDeviceOfflineError` (T-017)
- `custom_components/govee/entity.py`: availability (T-018)
- `custom_components/govee/light.py`: `GoveeRingLight` and panel colour temperature (T-021); #254 conflict (T-032)
- `custom_components/govee/sensor.py`: `GoveeLastMeasurementSensor` (T-019)
- `custom_components/govee/api/ble_packet.py`, `models/state.py`: zone frames, `aa 30` decode (T-020)
- `custom_components/govee/command_confirm.py` (new), `diagnostics.py`, `README.md`: T-022–T-024
- `strings.json`, `translations/en.json`, `icons.json`: `mqtt_silent`, `device_offline`, `last_measurement`, `reported_online`, `govee_ring_light`, confirm option
- `docs/release-replies.md`: queue (T-025, plus thank-you entries in T-026, T-028, T-032)
- `CLAUDE.md`: Device ID Detection (T-014), orphan-cleanup note (T-008), release time via #256 (T-026)

## Coverage
| Outcome | Merge | Security fix | Model/API | Coordinator | Entity | Strings | Test | Reply |
|---|---|---|---|---|---|---|---|---|
| Release pipeline | n/a | T-001, T-002, T-003 | n/a | n/a | n/a | n/a | T-001 | n/a |
| #237/#259 sweep | T-004 | T-009 (H5086 tick guard) | T-004 | T-004 | n/a | T-004 | T-004 | subject + reopen |
| Leak/heater | T-005 | T-005 (flap) | n/a | n/a | T-005 | n/a | T-005 | subject |
| Request budget | T-007 | T-007 | T-007 | T-007 | n/a | n/a | T-007 | subject |
| Kettle #228 | T-010, T-011, T-012 | T-012 (F-01/F-02) | PR | PR | PR | PR | PR | subject + T-025 |
| HA 2026.10 / py3.14 | n/a | n/a | n/a | n/a | n/a | n/a | T-013, T-031 | subject (#223) |
| #243 | n/a | n/a | T-014 | T-014 | n/a | n/a | T-014 | subject |
| #236 | n/a | n/a | T-015 | existing | n/a | n/a | T-015 | subject |
| #222 | n/a | n/a | n/a | T-016 | repair | T-016 | T-016 | subject |
| #242 | n/a | n/a | T-017 | T-017, T-018 | T-018 | T-017 | T-017, T-018 | subject |
| #258 | n/a | n/a | parsed | T-019 | T-019 | T-019 | T-019 | subject |
| #223 H1252 | n/a | porting checklist | T-020 | T-020 | T-021 | T-021 | T-020, T-021 | subject |
| #245 | n/a | F-03/F-04 | T-022 | T-023 | n/a | T-023 | T-022–T-024 | subject |
| Held #256/#252/#251 | T-026–T-028 | T-028 (re-login) | PR | PR | n/a | n/a | PR | subject + queue |
| #246 | T-027 | n/a | n/a | T-029 | n/a | n/a | T-029 | subject |
| LAN scan trust | n/a | T-030 | T-030 | n/a | n/a | n/a | T-030 | n/a |
| Data requests, closes | n/a | n/a | n/a | n/a | n/a | n/a | n/a | T-025 |
| #254 | T-032 | n/a | PR | PR (conflict) | PR (conflict) | PR | PR | subject + queue |

"subject" means a commit subject carries `#N`. From T-001 onward the nightly bot replies to every `#N` in any commit subject since the last tag.

## Risks
- **The loop blocks on the maintainer three times:** T-003 (repo settings), the `#249 report reviewed` line (T-026–T-028) and the `PR #254 tried on own lights` line (T-032). If the #249 report is slow, T-029–T-032 wait.
- **#251 held means bigger conflicts later:** it merges after #255, #247 and the kettle layers (`__init__.py`, `coordinator.py`, `config_flow.py` at 100 %).
- **#254 conflicts** (validate-plan M7) are certain in CLAUDE.md, scene_cache.py, coordinator.py and light.py. #231 and #254 both split `async_control_device` into `_async_control_device`, so the two must be chained by hand.
- **T-001 rewrites a workflow that only runs at night.** It is tested by YAML-property tests and a manual `dry_run`. #256 later conflicts with it (T-026 keeps T-001's security properties).
- **#247:** the energy sensor `state_class` changes for existing users.
- **#252:** BLE MAC is assumed to be the last 6 octets of the cloud ID. Spoofing by a deliberate nearby attacker remains possible.
- **T-030 Docker mismatch rule:** a wrong gateway heuristic would break LAN for bridge-mode Docker users, which is why that case is tested explicitly.
- **#242 vs #258:** BFF thermometers keep #97 availability. T-018 must not change it, so its verify runs the thermometer and water-leak suites.
- **H1252:** zone colour and brightness are optimistic. A LAN whole-device write doesn't re-light a zone switched off over ptReal.
- **No CI on fork PRs** (#247, #248, #229–#234) until approval. They are gated locally.

## Solutions consulted
- `docs/solutions/` and `docs/plans/BACKLOG.md`: not present.
- Memory used: local-test-env (venv recipe; fork PRs need local gating), hacs-reporters-cannot-test-branches, issue-replies-after-release and the CLAUDE.md reply rule, bff-devicesettings-scalar-source (T-015), sandbox-placeholder-dotfiles, and broad-behaviour-change-own-release-day (new this session, T-032).
- Prior plans `issue-sweep-oct` and `open-issue-fixes`: the #222 counter shipped; `govee.send_raw_ptreal` is what verified the H1252 frames.

## Research
- `docs/research/2026-10-23_issue-sweep-late-oct-prs.md`: PR triage, pairwise conflicts, first merge order
- `docs/research/2026-10-23_issue-sweep-late-oct-codebase.md`: per-issue design
- `docs/research/2026-10-23_issue-sweep-late-oct-comments.md`: every thread since 2026-10-01
- `docs/research/2026-10-23_issue-sweep-late-oct-validate-plan.md`: plan validation (2 blockers, 10 majors, 14 minors), all applied in v2
- `docs/research/2026-10-23_issue-sweep-late-oct-security-prs.md`: integration PR security review
- `docs/research/2026-10-23_issue-sweep-late-oct-security-kettle-ported.md`: kettle stack, #223 patch, #245 constraints
- `.cc-sessions/sessions/22dba441-da3a-47bc-93b2-f71f2e386b3f/plan-issue-sweep-late-oct/security-ci.md`: CI/release review. Kept out of `docs/` because it describes an unfixed attack path on `main`; move it in after T-001 and T-003 land
