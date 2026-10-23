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
