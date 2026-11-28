---
citations:
  - url: "https://github.com/lasswellt/govee-homeassistant/issues/314"
    title: "I have an H61D3 light strip. I added some DIY scenes to it b…"
    pub_date: "2026-11"
    fetched_ts: "2026-11-28T12:20:00Z"
    claimed_span: "Reporter on v2026.11.2 / HA 2026.11.3: three DIYs created recently in the app on the device are missing; diagnostics attached."
    status: LIVE
  - url: "https://github.com/lasswellt/govee-homeassistant/issues/288"
    title: "Feature Request: Support Govee Tap-to-Run"
    pub_date: "2026-11"
    fetched_ts: "2026-11-28T12:20:00Z"
    claimed_span: "exec-plat/home accepts the integration's existing app2 token; HTTP 200; 4 components, 10 oneClicks, every rule step has iotMsg; cmds turn, brightness, ptReal, colorwc."
    status: LIVE
  - url: "https://raw.githubusercontent.com/wez/govee2mqtt/main/src/undoc_api.rs"
    title: "govee2mqtt undoc_api.rs"
    pub_date: "2026-04"
    fetched_ts: "2026-11-28T14:43:00Z"
    claimed_span: "get_saved_one_click_shortcuts GETs https://app2.govee.com/bff-app/v1/exec-plat/home with Bearer community token, appVersion, clientId, clientType 1, iotVersion 0, timestamp; parse_one_clicks skips oneClicks with empty iot_rules and keeps entries whose device_obj.topic is set."
    status: LIVE
  - url: "https://raw.githubusercontent.com/wez/govee2mqtt/main/src/service/iot.rs"
    title: "govee2mqtt service/iot.rs"
    pub_date: "2026-04"
    fetched_ts: "2026-11-28T14:44:00Z"
    claimed_span: "activate_one_click publishes each serialized msg to entry.topic with QoS::AtMostOnce, in order, no delay."
    status: LIVE
  - url: "https://raw.githubusercontent.com/wez/govee2mqtt/main/src/service/hass.rs"
    title: "govee2mqtt service/hass.rs"
    pub_date: "2026-04"
    fetched_ts: "2026-11-28T14:44:00Z"
    claimed_span: "mqtt_oneclick re-parses one-clicks, finds the item by name, calls iot.activate_one_click."
    status: LIVE
  - url: "https://raw.githubusercontent.com/constructorfleet/ultimate-govee/main/lib/data/api/diy/govee-diy.config.ts"
    title: "ultimate-govee DIY config"
    pub_date: "2024-05"
    historical: "current HEAD of the only public groups-diys client; no newer source exists"
    fetched_ts: "2026-11-28T14:46:00Z"
    claimed_span: "deviceDiyUrl = https://app2.govee.com/appsku/v1/diys/groups-diys; oneClicksUrl = https://app2.govee.com/bff-app/v1/exec-plat/one-click-rules"
    status: LIVE
  - url: "https://raw.githubusercontent.com/constructorfleet/govee-ultimate/main/custom_components/govee/rest_client.py"
    title: "govee-ultimate rest_client.py"
    pub_date: "2025-11"
    historical: "current HEAD (last commit 2025-11-03) of the only public groups-diys client"
    fetched_ts: "2026-11-28T14:46:00Z"
    claimed_span: "GET groups-diys with params sku, goodsType, device and BFF headers; parse data.diys(.diyGroups)[].diys[] code|diyCode, name|diyName, diyOpCodeBase64|effectStr, effectType."
    status: LIVE
  - url: "https://raw.githubusercontent.com/constructorfleet/govee-ultimate/main/custom_components/govee/state/states.py"
    title: "govee-ultimate state/states.py DiyModeState"
    pub_date: "2025-11"
    historical: "current HEAD (last commit 2025-11-03); only public DIY ptReal activation code"
    fetched_ts: "2026-11-28T14:47:00Z"
    claimed_span: "DiyModeState rebuilds ptReal commands from the DIY's code and diyOpCodeBase64 and sends them as a type-1 command; status report op 0xaa 0x05 DIY code lo/hi."
    status: LIVE
  - url: "https://developer.govee.com/discuss/6679fd87b1b812005c266d6f"
    title: "Govee developer forum: Not all DIY scenes available?"
    pub_date: "2024"
    historical: "only Govee-hosted report of the DIY subset; page now 404 (Wayback snapshot 2025-05-08)"
    fetched_ts: null
    claimed_span: "Users report the Developer API returns only some saved DIYs for a device."
    status: DEAD
  - url: "https://community.homey.app/t/app-govee-making-your-life-smarter/50660?page=32"
    title: "Homey Govee app thread"
    pub_date: "2025"
    historical: "independent third-party client report of the same symptom"
    fetched_ts: null
    claimed_span: "Advanced DIY scenes reported absent from the API."
    status: NOT_FETCHED
  - url: "https://github.com/wez/govee2mqtt/issues/628"
    title: "govee2mqtt #628 Service not enabled"
    pub_date: "2026"
    fetched_ts: null
    claimed_span: "Account login path failing with 'Service not enabled'."
    status: NOT_FETCHED
---

# Research: Account-side DIY scenes (#314) and Tap-to-Run (#288)

**Date**: 2026-11-28
**Type**: Feature Investigation
**Status**: Complete
**Stack**: Python 3.14, Home Assistant custom integration (`custom_components/govee`), aiohttp, aiomqtt AWS IoT client; HA minimum 2024.11 (`hacs.json`)

---

## Summary

#314 is not a bug in our code. The v2026.11.2 diagnostics show the H61D3's Developer API DIY fetch succeeded and returned 3 scenes (`diy_scenes: {"count": 3}`, no error). The cache is in memory and the reporter restarted to update, so this was a fresh fetch. Govee's Developer API leaves out the three DIYs made recently in the app. Forum reports describe the same partial, per-device subset, and Govee has never explained it.

The account-side `GET /appsku/v1/diys/groups-diys` lists a device's DIYs with their effect data, but only one project, govee-ultimate, calls it. Nobody has captured its response from a real device, and no one has confirmed how to activate an app-only DIY.

#288 Tap-to-Run is now unblocked. The reporter showed that `GET /bff-app/v1/exec-plat/home` accepts our existing app2 token. govee2mqtt's source shows how to run one: publish each step's `iotMsg`, exactly as stored, to the step's `deviceObj.topic`, in order. Our MQTT client can publish to any topic but needs a raw-publish method.

Recommendation:
- **#288:** build Tap-to-Run now, as `scene` entities behind an option.
- **#314:** first ship a diagnostics-only `groups-diys` fetch (counts, plus whether its ids overlap the Developer API ids). Choose the activation path once a reporter's diagnostics show the real response.

---

## Research Questions

### Q1: Why are the three #314 DIYs missing?
**Answer**: Govee's Developer API `POST /router/api/v1/device/diy-scenes` did not return them. Our code drops nothing: `api/client.py:804-848` collects every option, and `scene_cache.py:271-310` records `{"count": n}`. The diagnostics say `count: 3` with no error.

Developer-forum and Homey reports describe the same partial lists, possibly limited by DIY type ("advanced" DIYs) or by device. Govee has published no rule. The reporter's split is telling: the scenes created before the device joined the account are returned, and those created on the device afterwards are not. Confidence: high that the cause is upstream, low on which rule Govee applies.

### Q2: Can `groups-diys` replace or add to the Developer list, and how is a DIY from it activated?
**Answer**: govee-ultimate requests it with `sku`, `goodsType` and `device` plus the BFF headers. It parses `data.diys` (or `data.diys.diyGroups`) `[].diys[]` into `code|diyCode`, `name|diyName`, `diyOpCodeBase64|effectStr` and `effectType` (`rest_client.py:114-145`, `:454-489`). To activate a DIY it rebuilds ptReal frames from `diyOpCodeBase64` and the code (`states.py:4717-4849`).

govee2mqtt does not use this endpoint. No one has captured its response or shown hardware evidence that activation works. Two things are still unknown: whether a `groups-diys` `code` matches the Developer `diyScene` value (e.g. `21104832` in `docs/govee-protocol-reference.md:634`), and whether the Developer `diyScene` control accepts codes it never listed.

### Q3: What is the exec-plat/home shape, and how is a One-Click run?
**Answer**: The response is `data.components[]` → `oneClicks[]` (`name`, `groupName`, `execRules`, `iotRules[]`) → `iotRules[]` (`deviceObj{topic, sku, device, name, bleAddress,…}`, `rule[]`). Each `rule[]` entry carries `iotMsg`, `blueMsg` and `cmdVal`, all JSON-encoded strings (`undoc_api.rs:575-700`).

govee2mqtt skips any oneClick with empty `iotRules` and any rule without a topic (`undoc_api.rs:458-482`). It then publishes every `iotMsg` in order at QoS 0, with no delay (`iot.rs:212-227`). The #288 reporter saw 10 Tap-to-Runs, every step with an `iotMsg` and no `execRules` or BLE-only steps.

### Q4: Which token, headers and refresh cadence?
**Answer**: govee2mqtt sends a separate community-api login token (`undoc_api.rs:291-305`, `:415-456`). The #288 reporter showed the app2 account token works with the same headers (`appVersion 7.4.10`, `clientId`, `clientType 1`, `iotVersion 0`, `timestamp`, `User-Agent`), so no second login is needed.

govee2mqtt caches One-Clicks with a 1-day soft and 1-week hard TTL, and refreshes when the user purges its cache (`undoc_api.rs:415-430`). Our `_async_bff_call` (`coordinator.py:2468`) already does one re-login and retry when the token is rejected.

### Q5: Where does each feature fit in our code, and how large is it?
**Answer**:
- **Account DIY source:** about 170 lines plus about 150 lines of tests, across `api/auth.py`, `scene_cache.py`, `coordinator.py`, `diagnostics.py`, and `select.py`/`models/commands.py` if activation differs.
- **Tap-to-Run:** about 370 lines plus about 300 lines of tests, across `api/auth.py`, new `models/one_click.py`, `api/mqtt.py` (raw publish), `coordinator.py`, a new `scene.py`, `const.py`, `config_flow.py`, the strings and icons files, and `diagnostics.py`.

These figures are the codebase agent's estimates from the files it read; Findings has the per-file breakdown.

---

## Findings

### Theme 1: #314 evidence and the Developer API subset
- Diagnostics (`data.devices.device_3b1fcd18.diy_scenes = {"count": 3}`, `diy_scene_cache_count: 8`, integration 2026.11.2, HA 2026.11.3) confirm the fetch succeeded. The device lists the `diyScene` capability. Source: the #314 attachment.
- `SceneCache` is in memory with `SCENE_CACHE_TTL = 86400` (`scene_cache.py:22`), and a restart clears it. The reporter updated, and so restarted, before downloading the diagnostics, so staleness is ruled out.
- Forum threads report Developer DIY lists missing saved scenes (developer.govee.com/discuss/6679fd87…) and "advanced" DIYs absent (Homey thread page 32). Govee has given no explanation. These are snippets from search results; the pages were not opened.
- Related symptoms in #296 (H60B3, `options: []`), #298 (H7087) and #281 (H70B6) fit the same class (docs/research/2026-11-16_post-2026-11-0-sweep.md row 296).

### Theme 2: Account-side DIY endpoint
- `groups-diys` appears only as a table row in `docs/govee-protocol-reference.md:1129`, with no schema.
- govee-ultimate is the only public client found that calls it. Its response parsing hedges between field names (`code|diyCode`, `diyOpCodeBase64|effectStr`), which suggests the field names were never confirmed against a real response.
- Activation options for an app-only DIY, cheapest first:
  - **a.** Developer `diyScene` control with the `groups-diys` code, through the existing `DIYSceneCommand` (`models/commands.py:202-217`). Zero new transport, works only if the ids match.
  - **b.** The existing passthrough `build_diy_scene_packet(scene_id)` (`api/ble_packet.py:360`, called from `coordinator.py:6959` `async_send_diy_scene`). This sends a mode switch by id and may need the effect payload.
  - **c.** govee-ultimate's full ptReal rebuild from `diyOpCodeBase64`. Most work and unverified on hardware.

### Theme 3: Tap-to-Run mechanics
- Endpoint, headers and parsing: `undoc_api.rs:415-482`. Execution: `iot.rs:212-227`.
- govee2mqtt exposes them as HA scene entities named `One-Click: <group>: <name>` and refreshes on a cache purge.
- Our `GoveeAwsIotClient.async_publish_command` (`api/mqtt.py:1149-1209`) builds its own `{"msg":{cmd,data,cmdVersion,transaction,type}}` envelope and publishes at QoS 1 (`:1200`). A pre-built `iotMsg` needs a sibling `async_publish_raw(topic, payload)`. The only guards are the connection state and a non-empty topic.
- Each rule carries its own topic, so the `_device_topics` lookup is not needed. Rules for a device shared from another account may be refused by the IoT policy. The publish then raises, and the scene reports failure.
- The per-entry hub device (`sensor.py:83`, `hub_device_identifier`) is already protected from orphan cleanup (`__init__.py:470-481`), so Tap-to-Run entities can live on it.

### Theme 4: Robustness and risk signals (contrarian)
- App-API auth breaks without notice. govee2mqtt #628 ("Service not enabled") is a recent example; it comes from a search snippet and was not opened. Tap-to-Run must degrade to "no entities" and never fail setup.
- No ToS clause or confirmed ban policy covers app-API use. The ban stories are anecdotal and involve the Developer API's 429s, not app2.
- No community evidence exists for `groups-diys` reliability or rate limits.

---

## Compatibility Analysis

### Stack Compatibility

| Aspect | Status | Notes |
|--------|--------|-------|
| HA 2024.11 minimum | Compatible | `homeassistant.components.scene.Scene`, `SelectEntity` and `DeviceInfo` all exist in 2024.11 |
| Account login gate | Compatible | `_async_bff_call` returns `None` without IoT credentials, so both features switch off cleanly for API-key-only users |
| mypy strict | Requires models | BFF payloads are `Any`; add frozen dataclasses in `models/one_click.py` that parse defensively |
| Coverage (95 % floor, config_flow 100 %) | Requires tests | A new option toggle means extending the `tests/test_config_flow*.py` suites |
| Platform list | Requires change | Add `Platform.SCENE` to `PLATFORMS` (`__init__.py:85+`) |
| Existing dependencies | No conflicts | aiohttp and aiomqtt are already in use; nothing new to install |

### Integration Complexity

- **Effort estimate**:
  - Tap-to-Run: Medium (1–2 days).
  - DIY diagnostics probe: Low (hours).
  - DIY activation: unknown until we have response data.
- **Files affected**: about 11 for Tap-to-Run and about 4 for the DIY probe (see Q5).
- **Breaking changes**: none. Both features are additive, and Tap-to-Run is off by default.
- **Migration path**: none.

---

## Recommendation

### Decision

Split the work into two tracks with different confidence:

1. **#288 Tap-to-Run: build it now.**
   - Add `GoveeAuthClient.fetch_one_clicks(token)`, following `_fetch_bff_device_topics`, called through `_async_bff_call`.
   - Parse the response into frozen `OneClick` models. Skip any oneClick with no topic-bearing `iotRules`, and count the skipped ones (including BLE-only and `execRules`-only) for diagnostics.
   - Add `GoveeAwsIotClient.async_publish_raw(topic, payload)`.
   - Expose each Tap-to-Run as a `scene` entity on the per-entry hub device. Activating it publishes every `iotMsg` in order and raises a translated `HomeAssistantError` if any publish fails.
   - Gate it behind a new `CONF_ENABLE_ONE_CLICKS` option, default off.
   - Fetch at setup and on a 24 h TTL. Prune scenes that disappear.
   - Diagnostics show counts only, never topics or `iotMsg` contents.
2. **#314 account DIYs: probe first, decide activation later.**
   - Add a diagnostics-only `groups-diys` fetch per DIY-capable device, for account-login users only. Record `{"account_count": m, "overlap_with_developer": k}` or `{"account_error": cls}` next to the existing `diy_scenes` result, and change no behaviour.
   - Ask the #314, #296 and #298 reporters for diagnostics on the release that carries it.
   - If `overlap_with_developer == developer count`, the codes share one id space. The follow-up then merges the account DIYs into the DIY select and activates them through the existing `DIYSceneCommand`, with the passthrough as fallback.
   - Otherwise, plan the ptReal path (activation option c in Findings) as its own piece of work.

### Rationale

- **The Tap-to-Run mechanics are verified.** govee2mqtt's source has been executing One-Clicks this way, and the #288 reporter showed our token works on the reporter's own account. What remains is ordinary integration plumbing, and that reporter offered to test a build.
- **A scene entity matches HA and upstream.** govee2mqtt exposes these as scenes, and HA treats a Tap-to-Run (set several devices to stored states) as a scene. Users can call `scene.turn_on` and the scenes show in the Scenes dashboard.
- **The DIY activation path is guesswork today.** No captured response exists, the only client that calls the endpoint is unverified, and three activation strategies remain open. A diagnostics probe costs a few hours and decides between them with real data. It follows the T-004 approach, which is what made #314 diagnosable at all.
- **Default-off and graceful degradation contain the app-API risk** shown by govee2mqtt #628. API-key-only users see no change.
- **The #314 reply can go out now**, without waiting on code: the scenes are missing upstream, and the next release adds a probe.

### Comparison Matrix

| Criteria | Tap-to-Run as `scene` | Tap-to-Run as `button` | DIY: probe first | DIY: full merge + ptReal now |
|----------|----------|----------|----------|----------|
| HA semantics | Native (matches govee2mqtt and Hue) | Generic action | n/a | n/a |
| Verified mechanics | Yes (upstream source plus #288 test) | Yes | Yes (GET only) | No (shape and activation unverified) |
| New platform | `Platform.SCENE` | none (button exists) | none | none |
| Risk of shipping broken behaviour | Low (opt-in) | Low (opt-in) | None (diagnostics only) | High |
| **Overall** | **Recommended** | Acceptable | **Recommended** | Not recommended |

---

## Implementation Sketch

### Step 1: Account-API fetchers (`api/auth.py`)
Both fetchers follow `_fetch_bff_device_topics` (`api/auth.py:743`): the same BFF headers, then `_raise_if_unauthorized`, then `_raise_for_bff_status`.

```python
GOVEE_BFF_ONE_CLICK_URL = "https://app2.govee.com/bff-app/v1/exec-plat/home"
GOVEE_DIY_GROUPS_URL = "https://app2.govee.com/appsku/v1/diys/groups-diys"

async def fetch_one_clicks(self, token: str) -> list[OneClick]:
    headers = self._bff_headers(token)  # appVersion, clientId, clientType "1", iotVersion "0", timestamp
    async with self._session.get(GOVEE_BFF_ONE_CLICK_URL, headers=headers) as resp:
        self._raise_if_unauthorized(resp)
        body = await resp.json()
    self._raise_for_bff_status(body)
    return parse_one_clicks(body)  # models/one_click.py; json.loads each iotMsg string
```

### Step 2: Raw publish (`api/mqtt.py`)
`async_publish_raw(topic: str, payload: str) -> None` publishes at QoS 1 with `ACK_TIMEOUT`, raises if disconnected, and logs the topic truncated to `[:30]`. The coordinator's `async_activate_one_click(click_id)` publishes each entry in order and returns `False` on the first failure.

### Step 3: Scene platform (`scene.py`, `__init__.py`, strings)
- Each `GoveeOneClickScene(CoordinatorEntity, Scene)` has `_attr_translation_key = "one_click"`, a name placeholder carrying the Tap-to-Run name, unique_id `f"{entry_id}_one_click_{group_id}_{preset_id}"`, and `DeviceInfo` pointing at the hub identifier.
- `async_activate` raises a translated error when publishing fails.
- Add `Platform.SCENE` to `PLATFORMS`.
- Add the strings to `strings.json` and `translations/en.json`, and the icon `mdi:gesture-tap-button` to `icons.json`.

### Step 4: Option, refresh and diagnostics
- `CONF_ENABLE_ONE_CLICKS` (default `False`) in `const.py` and `GoveeOptionsFlow.async_step_init`.
- Fetch after `_fetch_device_topics` at setup, then on a 24 h TTL; remove stale entities through the entity registry.
- Diagnostics: `one_click_count`, `one_click_skipped`.

### Step 5: DIY probe (`scene_cache.py`, `coordinator.py`, `diagnostics.py`)
- Pass `SceneCache` a callable that wraps `_async_bff_call(auth.fetch_diy_groups, …)`.
- After the Developer fetch, call it with `sku`, `goodsType` and `device`, and record `account_count` and `overlap_with_developer` (codes intersected with Developer values) in `_diy_fetch_results[device_id]`.
- Change no select options.

### Configuration Changes
New option `CONF_ENABLE_ONE_CLICKS`. No new requirements and no change to the entry data schema.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| exec-plat response shape differs from govee2mqtt's model (we have one account sample) | Medium | Medium | Parse defensively (`.get`, skip malformed entries) and test against a sample built from the `undoc_api.rs` structs |
| IoT policy refuses topics of shared or other-account devices | Low | Low | Publish raises, the scene raises a translated error, and diagnostics count it |
| App-API auth breaks (govee2mqtt #628 pattern) | Medium | Medium | `_async_bff_call` returns `None` and no entities are created; setup never fails on it |
| `groups-diys` id space differs from the Developer `diyScene` values | Unknown | Medium | That is what the probe measures; the merge waits for its result |
| Tap-to-Run steps that are BLE-only or `execRules`-only cannot run over IoT | Low (none in the #288 sample) | Low | Skip and count them; a scene with zero runnable steps is not created |
| A Tap-to-Run is renamed in the app | Medium | Low | unique_id is built from `groupId`/`presetId`, not the name |

### Open Questions

- What is the real `groups-diys` response shape for an H61D3, and do its codes equal the Developer `diyScene` values? (Answered by the probe.)
- Does the Developer `diyScene` control accept a code it did not list? A one-off test by a reporter, or by the maintainer on their own hardware, would settle it.
- Which Govee rule decides the DIY subset (DIY type, created-on-device, library sync)? No public source answers this, and it is not needed for the fix.
- Is `presetId` stable and unique per Tap-to-Run across refreshes? Check it against the #288 reporter's next diagnostics.

---

## Dissent / Contradictory Evidence

- **The library-docs agent contradicted the premise** that govee2mqtt uses `groups-diys`. That is correct: govee2mqtt's only scene source is `light-effect-libraries?sku=` (`undoc_api.rs:343-371`). The only `groups-diys` client found is govee-ultimate, with no hardware evidence. This is why the DIY track is downgraded to a probe.
- **Community token versus app2 token:** govee2mqtt uses a separate community-api login for exec-plat (`undoc_api.rs:291-305`, `:436`). The #288 reporter's test contradicts the idea that it is required. That is a single-account result, so the fetcher should treat a 401 as "feature unavailable", never as a reason to re-login in a loop. `_async_bff_call` already retries only once.
- **govee-ultimate names a different One-Click endpoint,** `exec-plat/one-click-rules`, while govee2mqtt and the #288 reporter used `exec-plat/home`. The verified one is `exec-plat/home`.
- **Not every DIY gap is upstream:** the Homey maintainer says DIY lists load only at device init. That fits stale caches in general, but it is ruled out here because our cache is in memory and the reporter restarted.
- **Single-domain caution:** both upstream sources for the Tap-to-Run mechanics are from github.com (govee2mqtt and the #288 thread). The reporter's live test is independent evidence for the endpoint and token, but the execution semantics rest on one project.

---

## Citation Health

| url | status | last_probed_at |
|-----|--------|----------------|
| https://github.com/lasswellt/govee-homeassistant/issues/314 | LIVE | 2026-11-28T12:20Z |
| https://github.com/lasswellt/govee-homeassistant/issues/288 | LIVE | 2026-11-28T12:20Z |
| https://raw.githubusercontent.com/wez/govee2mqtt/main/src/undoc_api.rs | LIVE | 2026-11-28T14:43Z |
| https://raw.githubusercontent.com/wez/govee2mqtt/main/src/service/iot.rs | LIVE | 2026-11-28T14:44Z |
| https://raw.githubusercontent.com/wez/govee2mqtt/main/src/service/hass.rs | LIVE | 2026-11-28T14:44Z |
| https://raw.githubusercontent.com/constructorfleet/ultimate-govee/main/lib/data/api/diy/govee-diy.config.ts | LIVE | 2026-11-28T14:46Z |
| https://raw.githubusercontent.com/constructorfleet/govee-ultimate/main/custom_components/govee/rest_client.py | LIVE | 2026-11-28T14:46Z |
| https://raw.githubusercontent.com/constructorfleet/govee-ultimate/main/custom_components/govee/state/states.py | LIVE | 2026-11-28T14:47Z |
| https://developer.govee.com/discuss/6679fd87b1b812005c266d6f | DEAD (404; Wayback 2025-05-08) | 2026-11-28 |
| https://community.homey.app/t/app-govee-making-your-life-smarter/50660?page=32 | LIVE | 2026-11-28 |
| https://github.com/wez/govee2mqtt/issues/628 | LIVE | 2026-11-28 |

---

## References

1. #314 (https://github.com/lasswellt/govee-homeassistant/issues/314): the report and the v2026.11.2 diagnostics.
2. #288 (https://github.com/lasswellt/govee-homeassistant/issues/288): the reporter's live exec-plat/home test with the app2 token.
3. govee2mqtt `undoc_api.rs` (https://raw.githubusercontent.com/wez/govee2mqtt/main/src/undoc_api.rs): the One-Click fetch, parse and structs (`:415-482`, `:575-700`), the community login (`:291-305`) and the scene catalogue (`:343-371`).
4. govee2mqtt `service/iot.rs` (https://raw.githubusercontent.com/wez/govee2mqtt/main/src/service/iot.rs): `activate_one_click` (`:212-227`).
5. govee2mqtt `service/hass.rs` (https://raw.githubusercontent.com/wez/govee2mqtt/main/src/service/hass.rs): `mqtt_oneclick` (`:410-432`).
6. ultimate-govee DIY config (https://raw.githubusercontent.com/constructorfleet/ultimate-govee/main/lib/data/api/diy/govee-diy.config.ts): the `groups-diys` and `one-click-rules` URLs.
7. govee-ultimate `rest_client.py` (https://raw.githubusercontent.com/constructorfleet/govee-ultimate/main/custom_components/govee/rest_client.py): the `groups-diys` request (`:114-145`) and parse (`:454-489`).
8. govee-ultimate `state/states.py` (https://raw.githubusercontent.com/constructorfleet/govee-ultimate/main/custom_components/govee/state/states.py): `DiyModeState` ptReal rebuild (`:4717-4849`).
9. Govee developer forum (https://developer.govee.com/discuss/6679fd87b1b812005c266d6f): reports of partial DIY lists (snippet only).
10. Homey Govee thread (https://community.homey.app/t/app-govee-making-your-life-smarter/50660?page=32): reports that advanced DIYs are absent (snippet only).
11. govee2mqtt #628 (https://github.com/wez/govee2mqtt/issues/628): app-login breakage (snippet only).
12. `custom_components/govee/api/auth.py:743`: `_fetch_bff_device_topics`, the BFF GET template.
13. `custom_components/govee/coordinator.py:2468`: `_async_bff_call`, one re-login and retry.
14. `custom_components/govee/api/mqtt.py:1149-1209`: `async_publish_command`, the envelope and QoS 1.
15. `custom_components/govee/coordinator.py:6959`: `async_send_diy_scene`, REST then passthrough.
16. `custom_components/govee/api/ble_packet.py:360`: `build_diy_scene_packet(scene_id)`.
17. `custom_components/govee/scene_cache.py:22`, `:271-310`: the DIY cache TTL and the fetch-result bookkeeping.
18. `custom_components/govee/__init__.py:470-481`: the hub device's protection from orphan cleanup.
