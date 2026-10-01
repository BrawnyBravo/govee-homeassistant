---
status: active
priority: P0
created: 2026-10-01
ship: manual
---
# Issue sweep: open threads and recent comments (2026-10-01)

## Goal
Resolve every GitHub thread with an unanswered non-maintainer comment or no reply since v2026.9.15 (2026-09-28): merge the two ready fork PRs, fix the purifier regression (#221) and the H605B DreamView off (#220), add #222 MQTT diagnostics, ship the #224 H5059 probe entities and #223 H1232 full-segment/main-panel control, and queue data requests for #211 and #186. Threads that only wait on reporter validation (#200, #201, #207, #208, #209, #210, #213, #215, #198) are untouched.

## Outcomes
- H7124/H7129/H7126 purifier Mode select changes speed without a Govee 400  → T-003
- H5103 temperatures auto-convert from Fahrenheit (PR #225)  → T-001
- LAN-healthy lights stay available during a total cloud outage; docs match (PR #227, #226)  → T-002
- connection_mode no longer reads `mqtt` for a silent session; diagnostics show raw inbound MQTT count/time (#222)  → T-004, T-005
- Turning DreamView off on an H605B leaves video mode (#220)  → T-006
- H5059 leak sensors expose Upper probe / Lower probe moisture entities (#224)  → T-007, T-008
- H1232 exposes 16 ring segments and a separate main panel light over ptReal (#223)  → T-009, T-010, T-011
- #211, #186, #85 get replies after the daily release  → T-012

## Out of scope
- #211 H60B0 zone entities (no write path known; data requested)
- #186 H6022 Spectrum/Rolling code override (awaiting diagnostics; fix sketched in research-misc.md)
- MQTT deaf-session watchdog (#222) until the Reconfigure result is in
- OpenAPI `probesState` fallback for #224 until a real payload arrives
- Version bump / release (daily-release workflow does it)

## Assumptions
- `/blitz:plan` was run without `--autonomous`, but the goal ("all open and recent comments") fixes scope; the interview was skipped and the research verdicts were taken as the design.
- Merging the fork PRs (#225, #227) is outward-facing: confirm with the user at build time before merging.
- #220 fix ships before the reporter answers the app/remote question: diagnostics already show the inert toggle-0 (`aa05 00` 73 s after off).
- #223 ptReal segment control requires account login (AWS IoT passthrough); without it segments 14–16 fail and 1–13 use REST.
- Verify commands use the py3.12 scratchpad venv `/tmp/claude-1000/-home-lasswellt-Projects-govee-homeassistant/b7101f46-014d-44f1-8beb-88aa11ef75c4/scratchpad/venv`; rebuild per memory `local-test-env-python312-mise` if it is gone.
- Commits reference `#N` in the subject so the daily release replies automatically; reply asks (Reconfigure for #222, OpenAPI payload for #224, app-vs-HA question for #220) go in commit bodies.

## Verification
- `bash /home/lasswellt/.claude/plugins/cache/blitz/blitz/3.9.4/scripts/tasks.sh verify issue-sweep-oct <id>` per task; `/blitz:check --scope plan issue-sweep-oct` before ship
- Full gates on main before push: `venv/bin/pytest -o addopts="" --cov=custom_components.govee` (95% floor, config_flow 100%, every module >96%), `black --check .`, `flake8 .`, `mypy custom_components/govee`
- CI: all five workflows green on `gh run list --commit "$(git rev-parse HEAD)"`
