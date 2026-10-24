## 2026-10-23T00:00:00Z plan created
Ruling: class=architectural tasks=27; 17 fork PR merges in conflict order, 9 issue fixes, py3.14 test fixes, reply queue, final gates; #254 isolated to its own release day at the user's request.

- Baseline: `.cc-sessions/venv312` (Python 3.12.14, HA 2025.1 lane) 3,598 passed. `.cc-sessions/venv314` (Python 3.14.9, HA 2026.10.2) 3,596 passed, 2 failed (test-only, T-025).
- PR heads fetched to `refs/pr/N` for #229–#234, #238, #247, #248, #250–#257, #259 at the SHAs in research-prs.md.

## 2026-10-23T13:30:00Z plan v2 after validation + security round
Ruling: class=architectural tasks=32; four independent reviews (plan validation: 2 blocker / 10 major / 14 minor, all applied; CI security: 1 critical / 3 high on main's release workflow; integration PRs: 0 high, fixes folded into T-005/T-007/T-028; kettle + ported code: #234 F-01/F-02 and #245 F-03 folded into T-012/T-022).
- User decisions: harden the release job first (T-001..T-003); hold #251/#252/#256 until the #249 report is read; resolve #254 ourselves, last, on its own release day; add the LAN scan trust fix (T-030).
- New issue #261 (H1A42) -> data request in T-025.
- Five checks pass today by design (invariants): T-004/T-010 issue OPEN, T-010 #235 not merged, T-018 _allow_lan_availability kept, T-025 no #249 entry.
- security-ci.md stays out of docs/ until T-001 and T-003 land (describes an unfixed attack path on main).

## 2026-10-23T13:24:01Z build T-001 start (attempt 1)
## 2026-10-23T13:28:07Z review T-001 ok=false failed="main-thread review" tail="Write(path) rules never match in Claude Code (docs: use Edit(path)); notes.md would never be written, and the release breaks after the bump push"
## 2026-10-23T13:29:18Z verify T-001 ok=true (fix round 1: Edit(//) rule, notes before bump, dedupe/cap/PR-close; actionlint clean)
- Note: dry_run stops before the Claude steps, so the Edit(//...) rule is first exercised on a real release night; a failure there now stops before the bump.
## 2026-10-23T13:29:35Z build T-002 start (attempt 1); scope+ .github/workflows/*.yml|yaml (pins, badge permissions, delete rebase_dependencies.yml) per its notes
## 2026-10-23T13:31:05Z verify T-002 ok=true (all action SHAs cross-checked upstream; actionlint clean; no tracked .claude/settings)
## 2026-10-23T13:38:30Z T-003 settings applied via gh api (user-approved): tag ruleset 25725868 on refs/tags/v* (update+deletion, no bypass), immutable releases on, Dependabot alerts on, fork-PR approval all_external_contributors. secret_scanning_non_provider_patterns stayed disabled (plan-gated); push protection already on. Remaining: maintainer rotates RELEASE_TOKEN.
## 2026-10-24T11:40:46Z verify T-003 ok=true (RELEASE_TOKEN rotated by maintainer, updated_at 2026-10-24T11:40:11Z)
## 2026-10-24T11:44:27Z build T-004 start (attempt 1); main thread (two small PRs, merges only)
## 2026-10-24T11:56:48Z verify T-004 ok=true (#238, #259 merged; #238 body Fixes->Refs #237 so #237 stays open; CI green on 8f6b7ea)
## 2026-10-24T11:57:14Z build T-005 start (attempt 1); main thread; flap fix lives in coordinator.py (scope+coordinator.py, tests/test_leak_mqtt_stamps.py)
## 2026-10-24T12:02:36Z verify T-005 ok=true (#253, #257 merged; flap fix requires dry > max(mqtt wet, cloud last_wet); #253 isfinite guard; CI green on fbeab40)
## 2026-10-24T12:03:03Z build T-006 start (attempt 1); main thread; fork PR gated locally
## 2026-10-24T12:08:16Z verify T-006 ok=true (#248 merged; raw HomeAssistantError -> segment_passthrough_failed translation key; CI green)
## 2026-10-24T12:08:33Z build T-007 start (attempt 1); main thread; LOW fixes land in api/client.py and __init__.py (scope+api/client.py)
## 2026-10-24T12:13:49Z verify T-007 ok=true (#250 merged; Retry-After finite+capped 3600 s, future buckets dropped, Store load guarded; CI green)
## 2026-10-24T12:14:02Z build T-008 start (attempt 1); main thread
## 2026-10-24T12:20:22Z verify T-008 ok=true (#255 merged; conflict with #250 kept both: commit in _fetch_device_state_bounded, count only non-cached; config_flow 100%; CLAUDE.md orphan note updated by the PR; CI green)
- T-001 gap (found by peer session 0f945fd3, memory claude-allowlist-git-log-output-write): Bash(git log:*)/Bash(git show:*) allow --output=<path>, so the Claude steps can overwrite files a later RELEASE_TOKEN step runs. Fix before the 03:00 UTC run: Claude steps in their own job, pre-rendered inputs, Read + Edit(out/**) only. Asked the peer session whether it owns the fix.
## 2026-10-24T12:28:30Z build T-009 start (attempt 1); main thread; fork PR gated locally
## 2026-10-24T12:33:52Z T-001 rework: 56504cb splits daily-release.yml into gate/draft/preview/publish (Claude in its own job, no Bash/web, /proc denied; publish on a fresh runner takes only notes.md + replies.json after check-drafts); secret-shape rejects; dry run 40094032298 started
## 2026-10-24T12:33:52Z verify T-009 ok=true (#247 merged; refusal guard covers the 60 s H5086 tick, tick skips excluded SKUs (tests); naive restored datetimes dropped; CI green)
## 2026-10-24T12:34:30Z build T-010 start (attempt 1); main thread; #229 body Fixes->Refs #228
## 2026-10-24T12:40:15Z dry run 40094032298 ok: gate/draft/preview success, publish skipped; Claude (no Bash) wrote notes.md (10 KB) + replies.json (8 drafts), check-drafts passed, preview would comment on #259 #237 #238 #250 #248 #257 #253 #255. The new Edit(//) rule is now exercised by a dry run.
## 2026-10-24T12:40:15Z verify T-010 ok=true (#229-#231 merged as one stack; #229 body Fixes->Refs #228, #228 open; async_read_device double commit removed after #255; kettle status queries respect re-query off and #259 refusal; #235 not merged)
- Ruling: defer; the H7175 doc stays in docs/_research/ (the repo's established folder, 40 docs), not moved to docs/research/ as T-010 notes said (T-010)
## 2026-10-24T12:40:25Z build T-011 start (attempt 1); main thread
## 2026-10-24T12:47:42Z verify T-011 ok=true (#232/#233 merged; options save keeps slot labels + segment modes; frame kinds capped at 32; config_flow 100%; CI green)
## 2026-10-24T12:47:55Z build T-012 start (attempt 1); main thread
## 2026-10-24T13:01:41Z verify T-012 ok=true (#234 merged; request_status admin-only; one throttled, lock-serialised path with in-flight marker held for the spacing window; REQUEST_STATUS_MIN_INTERVAL per device; mirrors sweep targets + #259 refusal; rebased over peer commit ecaa078 (App-token publish), merge edits restored from 905efed; CI green)
