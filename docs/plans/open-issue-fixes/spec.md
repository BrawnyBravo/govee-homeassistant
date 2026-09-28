---
status: active
priority: P1
created: 2026-09-27
ship: manual
---
# Open issue fixes (2026-09-27)

## Goal
Fix the open GitHub issues that can be fixed from the code, for tonight's end-of-day release: the rest of #198 (H6199 blind BLE writes), the hardening the critic raised on merged PR #219 (leak-alert calls), and a developer service that lets the #208 reporter try candidate segment frames without a custom branch.

## Outcomes
- A device whose BLE advertisements are stale skips the BLE tier, and its commands go over LAN/MQTT/REST → T-001
- A BLE write counts as a send, not a receive (the staleness clock follows advertisements only), and shows up in diagnostics `recent_commands` with `transport: "ble"` → T-002
- A malformed or non-JSON response to `warnMessage`/`warnLifted` raises `GoveeApiError`, so the button shows the translated failure; a 401 still triggers re-login → T-003
- `govee.send_raw_ptreal` sends a validated raw frame (checksum added or checked) to one device over the AWS IoT passthrough, and refuses cleanly without account login → T-004, T-005

## Out of scope
- #208 segment writes for indices 16–29: the frame format is unknown (research verdict ~30% for the obvious guess). The reporter is asked for an Android HCI snoop capture; the debug service lets them test candidates
- #213 H66A0 DreamView: on branch `fix/213-h66a0-dreamview`, waiting on a hardware test
- Issues waiting on reporter validation (#151, #186, #200, #201, #207, #210, #215) or data (#211)
- The same unguarded `data.get` pattern at other auth.py call sites (703, 744, 830, 999, 1235, 1598)

## Assumptions
- BLE eligibility mirrors the LAN gate: transport health `is_available`. A device with no advertisement yet this session falls through to the next tier
- The raw ptReal service is a debug tool: no entity, no persistence, and it only goes to devices the entry knows
- Frames of up to 19 bytes get their XOR checksum computed; a 20-byte frame must carry a valid one

## Verification
- `bash /home/lasswellt/.claude/plugins/cache/blitz/blitz/3.9.4/scripts/tasks.sh verify open-issue-fixes <id>` per task; `/blitz:check --scope plan open-issue-fixes` before ship
- Full gates before push: pytest (coverage floor 95%, auth.py/coordinator.py/services.py at 100%), flake8, `black --check`, mypy
- Critic review (`MODE: reject`) of the combined diff before merging to `main`
