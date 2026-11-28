# Plan: diy-source-and-tap-to-run

## Architecture

The plan has two independent tracks that share the account-API plumbing. Every account-API call goes through `GoveeAuthClient` in `api/auth.py` and the coordinator's `_async_bff_call`. That wrapper does nothing without IoT credentials and retries once with a fresh login when the token is rejected.

**Tap-to-Run (T-001 to T-007):**
- **Parse.** `parse_one_clicks` reads the exec-plat/home JSON into frozen `OneClick` and `OneClickStep` models, so mypy strict holds at the boundary.
- **Fetch.** `GoveeAuthClient.fetch_one_clicks` makes the request.
- **Publish.** `GoveeAwsIotClient.async_publish_raw` sends each `iotMsg` exactly as stored.
- **Coordinator.**
  - Fetches the list at setup, only when the option is on, then on a 24-hour TTL.
  - On a failed fetch, keeps the last good list.
  - Exposes `async_activate_one_click`, which publishes the steps in order and returns `False` on the first failure.
- **Scenes.** `scene.py` puts one `GoveeOneClickScene` per Tap-to-Run on the per-entry hub device, which orphan cleanup already protects. It adds and removes entities on a coordinator signal.

**DIY probe (T-008 and T-009):**
- `fetch_diy_groups` returns the account DIY codes for one device.
- `_fetch_bff_device_topics` also records each device's `goodsType`, since the request needs it.
- After each successful Developer DIY fetch, `SceneCacheManager` calls a probe callable and adds `account_count` and `overlap_with_developer` (or `account_error`) to the per-device fetch result that diagnostics already prints.

**Tradeoffs:**
- **Chosen:**
  - A scene entity over a button. It is native HA semantics, govee2mqtt does the same, and it shows in the Scenes dashboard.
  - Default off.
  - Probe the DIY endpoint before building anything on it.
- **Rejected:**
  - A button entity, which is a generic action with no scene semantics.
  - Merging account DIYs into the select now: the response shape and activation path are unverified, so we could ship broken behaviour.
  - A second community-API login like govee2mqtt's, which the #288 test showed is unnecessary.

## File map

| Path | Change |
|---|---|
| `custom_components/govee/models/one_click.py` | new: frozen `OneClick` and `OneClickStep`, `parse_one_clicks` (T-001) |
| `custom_components/govee/api/auth.py` | `GOVEE_BFF_ONE_CLICK_URL` and `fetch_one_clicks` (T-002); `GOVEE_DIY_GROUPS_URL`, `fetch_diy_groups`, and per-device `goodsType` with a `goods_types()` accessor (T-008) |
| `custom_components/govee/api/mqtt.py` | `async_publish_raw(topic, payload)` at QoS 1 (T-003) |
| `custom_components/govee/const.py` | `CONF_ENABLE_ONE_CLICKS` and its default (T-004) |
| `custom_components/govee/config_flow.py` | option toggle in `async_step_init` (T-004) |
| `custom_components/govee/strings.json`, `translations/en.json` | option label and description, `entity.scene.one_click` name, failure exception (T-004) |
| `custom_components/govee/icons.json` | `entity.scene.one_click` icon (T-004) |
| `custom_components/govee/coordinator.py` | fetch, TTL refresh, `one_clicks`, change signal, `async_activate_one_click` (T-005); `goodsType` capture and the probe callable (T-009) |
| `custom_components/govee/scene.py` | new: `GoveeOneClickScene` and setup with add/remove on the signal (T-006) |
| `custom_components/govee/__init__.py` | `Platform.SCENE` in `PLATFORMS` (T-006) |
| `custom_components/govee/diagnostics.py` | `one_click_count`, `one_click_skipped` (T-007) |
| `custom_components/govee/scene_cache.py` | probe result recorded beside `{"count": n}` (T-009) |
| `README.md`, `CLAUDE.md` | Tap-to-Run section; `scene.py` in the directory map (T-007) |
| `tests/test_one_click_model.py`, `test_auth_one_click.py`, `test_mqtt_publish_raw.py`, `test_config_flow_one_clicks.py`, `test_coordinator_one_click.py`, `test_scene.py`, `test_diagnostics_one_click.py`, `test_auth_diy_groups.py`, `test_scene_cache_diy_probe.py` | new tests, one file per task |

## Coverage

| Outcome | Model | API (auth) | MQTT | Option/strings | Coordinator | Entity | Diagnostics/docs | Test |
|---|---|---|---|---|---|---|---|---|
| 1 Scenes appear and run | ✓ T-001 | ✓ T-002 | ✓ T-003 | ✓ T-004 | ✓ T-005 | ✓ T-006 | n/a | ✓ T-001..T-006 |
| 2 Failures contained | ✓ T-001 (no raise on bad shape) | ✓ T-002 | ✓ T-003 | ✓ T-004 (exception key) | ✓ T-005 | ✓ T-006 | n/a | ✓ T-002, T-003, T-005, T-006 |
| 3 List stays current | ✓ T-001 (stable id) | n/a | n/a | n/a | ✓ T-005 | ✓ T-006 | n/a | ✓ T-005, T-006 |
| 4 Diagnostics counts only | ✓ T-001 (skipped count) | n/a | n/a | n/a | ✓ T-005 | n/a | ✓ T-007 | ✓ T-007 |
| 5 DIY probe result | n/a | ✓ T-008 | n/a | n/a | ✓ T-009 | n/a | ✓ (already printed, `diagnostics.py:248`) | ✓ T-008, T-009 |

No gaps.

## Risks

- **Response shape (exec-plat/home).** We have govee2mqtt's structs and one account's summary from the #288 reporter, not a raw body. T-001 parses defensively with `.get()`, and its fixture follows `undoc_api.rs:575-700`. The #288 reporter's diagnostics confirm it after release.
- **Response shape (groups-diys).** It is completely unconfirmed: govee-ultimate hedges between `code` and `diyCode`. T-008 accepts both names, and a failure is recorded as `account_error` rather than raised. Learning the shape is the probe's whole purpose.
- **App-API auth breakage** (the govee2mqtt #628 pattern). `_async_bff_call` returns `None` or raises `GoveeApiError`, and T-005 keeps the previous list and never fails setup.
- **Shared-device topics.** The IoT policy may refuse topics of devices shared from another account. The publish then fails, and the scene raises a translated error.
- **`presetId` stability** across refreshes is unverified. If it changes, an entity is replaced on refresh, which costs a new entity_id and nothing worse. We check this against the #288 reporter's next diagnostics.
- **File overlap.** `auth.py` is shared by T-002 and T-008, and `coordinator.py` by T-005 and T-009. The dependency edges T-008→T-002 and T-009→T-005 serialise them, so `--parallel` never merges conflicting edits.
- **Task size.** T-004 touches 6 files, above the 1–3 guideline. Each edit is a few lines, and the option, its strings and its icon ship as one reviewable unit.
- **Coverage gates.** `config_flow.py` must stay at 100% (T-004 verifies this with `--cov-fail-under=100`), and the overall floor is 95%.

## Solutions consulted

- `docs/solutions/`: absent.
- `docs/plans/BACKLOG.md`: absent.
- Prior plans: open-issues T-004 (DIY fetch diagnostics, `_diy_fetch_results`) is the pattern T-009 extends.

## Research

- `docs/research/2026-11-28_diy-source-and-tap-to-run.md` (`--from-research`; no agents spawned).
- Spot-checked against the code on 2026-11-28:
  - `api/auth.py:743` `_fetch_bff_device_topics`;
  - `coordinator.py:2468` `_async_bff_call`, and `:1454` the topics startup step;
  - `api/mqtt.py:1149`, `:1200` QoS 1 publish;
  - `__init__.py:84` `PLATFORMS`, `:480` hub protection;
  - `const.py:669` `hub_device_identifier`;
  - `scene_cache.py:82`, `:290`, `:300` fetch-result store;
  - `diagnostics.py:248`.
- `goodsType` is absent from the integration today, and is present in the BFF device-list schema (`docs/_research/2026-06-30_30day-issue-sweep.md:840`).
