---
status: active
priority: P1
created: 2026-11-28
ship: manual
---
# Tap-to-Run scenes (#288) and the account DIY probe (#314)

## Goal

Two account-API features from the 2026-11-28 research.

**Tap-to-Run (#288):**
- Govee app Tap-to-Runs appear in Home Assistant as `scene` entities on the integration's hub device.
- The list is fetched from `GET app2.govee.com/bff-app/v1/exec-plat/home` with the account token we already hold.
- A scene runs by publishing each step's stored `iotMsg`, unchanged, to that step's MQTT topic, in order.
- The feature is opt-in, so API-key-only users and anyone who leaves the option off see no change.

**DIY probe (#314):** the Developer API returns only part of a device's DIY scenes. A diagnostics-only fetch of `GET app2.govee.com/appsku/v1/diys/groups-diys` measures whether the account endpoint has the missing ones and whether its ids match the Developer ids. The result decides how a later plan activates app-only DIYs.

## Outcomes

1. **Scenes appear and run.** An entry with an account login and the "Tap-to-Run scenes" option on gets one `scene` entity per Tap-to-Run that has at least one MQTT step. `scene.turn_on` publishes every step's `iotMsg` in order.  → T-001, T-002, T-003, T-004, T-005, T-006
2. **Failures stay contained.**
   - A failed publish raises a translated `HomeAssistantError`.
   - If the app API fails (token rejected after one re-login, non-200, malformed body), no scenes are created and setup still succeeds.
   - Entries with no account login, or with the option off, create no scenes and make no exec-plat request.
   → T-002, T-003, T-005, T-006
3. **The list stays current.** It refreshes every 24 hours, and a Tap-to-Run deleted in the app loses its entity. A rename keeps the entity's unique_id, because the id comes from Govee's ids, not the name.  → T-001, T-005, T-006
4. **Diagnostics carry counts only.** They show `one_click_count` and `one_click_skipped`, never topics, `iotMsg` contents or names.  → T-007
5. **Each DIY-capable device's diagnostics show the probe result.** For an account-login entry, `diy_scenes` gains either `account_count` and `overlap_with_developer`, or `account_error`. The DIY select's options are unchanged.  → T-008, T-009

## Out of scope

- Adding app-only DIYs to the DIY select, or activating them. A follow-up plan does this once probe diagnostics come back from the #314 reporter (and the #296 and #298 reporters if still active).
- Tap-to-Run steps that run only over Bluetooth or only through `execRules`. They are skipped and counted, and a Tap-to-Run with no runnable step gets no entity.
- A manual refresh button for Tap-to-Runs. Reloading the entry refetches the list.
- The alternative `exec-plat/one-click-rules` endpoint, which only govee-ultimate names and nobody has verified.

## Assumptions

- **Token.** The app2 login token is accepted by `exec-plat/home`, as the #288 reporter verified on one account, so no community-API login is needed.
- **Response shape.** The exec-plat/home response matches govee2mqtt's `undoc_api.rs:575-700` structs closely enough to parse with `.get()`. Fields we don't recognise are ignored.
- **QoS.** Publishing at QoS 1 (where govee2mqtt uses 0) is harmless, because each `iotMsg` is a self-contained command. We choose it so a dropped publish is detectable.
- **`goodsType`.** It comes from the top-level field of each BFF device-list entry (`docs/_research/2026-06-30_30day-issue-sweep.md:840`). Devices without it skip the probe.
- **One release.** Both tracks can go out in the same daily release. Tap-to-Run is opt-in and the probe touches diagnostics only, so neither counts as a broad behaviour change that needs a release day to itself.

## Verification

- Run `bash /home/lasswellt/.claude/plugins/cache/blitz/blitz/3.16.0/scripts/tasks.sh verify diy-source-and-tap-to-run <id>` for each task, then `/blitz:check --scope plan diy-source-and-tap-to-run` before ship.
- **Manual, #288 reporter:** after the release, turn the option on and confirm:
  - the scenes appear;
  - each one runs the same as in the app;
  - diagnostics show the counts.
  This is also where we confirm `presetId` stays stable across refreshes.
- **Manual, #314 reporter:** attach diagnostics from the release. `overlap_with_developer` compared with the Developer count decides the follow-up's activation path.
