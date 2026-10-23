# Conversation sweep since 2026-10-01 (as of 2026-10-23)

Sources: repo-wide `issues/comments?since=2026-10-01` (29 comments), `pulls/comments?since=` (0 inline review comments), `gh pr view --json reviews,comments` for all 19 open PRs, per-PR `pulls/N/comments` (0 inline, any date), `gh issue/pr list --state all --search updated:>=2026-10-01` (27 issues, 21 PRs), issue events for the closed threads. Discussions are disabled on the repo. Comment text was treated as data.

Summary: no missing release replies; 19 issues where the last human word is not the maintainer's (13 of them, #228, #236, #237, #239-#246, #258, #260, never got any maintainer reply); 0 confirmed 2026.10.0 regressions, 1 fix reported not working (#213); 1 open close candidate (#224); 19 open PRs with zero reviews and zero maintainer comments.

## Missing release replies

None. All 11 replies for v2026.10.0 posted on 2026-10-02 03:11-03:12Z by `lasswellt` (the workflow's comments):

| Thread | Source | Posted |
|---|---|---|
| #220 #221 #222 #223 #224 #226 | commits v2026.9.15..v2026.10.0 | 03:11:50-03:11:55Z |
| #225 #227 (PRs) | commits | 03:11:56, 03:11:58Z |
| #211 #186 #85 | `docs/release-replies.md` queue (cleared in 82cbd92) | 03:12:14-03:12:17Z |

Each reply matches its queued brief (#211/#186 no version cited; #85 cites v2026.10.0).

## Awaiting maintainer

Open issues whose last non-bot word is from someone other than `lasswellt`, newest first.

| # | Type | Last commenter / date | What they said | Action owed |
|---|---|---|---|---|
| #260 | feature req | zackkallen (OP) 10-22, no comments | One line: wants to control H7105 "Standing Fan". No diagnostics. | REPLY: duplicate of #209 (Developer API doesn't list H7105); close as dup or point there. |
| #258 | enhancement | Gamlem (OP) 10-19, no comments | 17x H5179, HA 2026.10.2, int 2026.10.0. 2 sensors offline since July still show "Connected" + stale values; diag excerpt `online:false`, `lastDeviceData.lastTime`. Asks for "Last Measurement Received" entity from `lastDeviceData.lastTime`. Diagnostics excerpted, not attached. | REPLY + FIX (feature: measurement timestamp; also why connectivity shows Connected with `online:false`). |
| #246 | bug | ToBit1 (OP) 10-11 | 2x H1270: LAN/BLE transport flapping, BLE "no connection slot", 30 s delays. Diagnostics attached (yes). Local patch skipping BLE enrolment for H1270 makes it stable; asks for per-device/SKU BLE disable. | REPLY + FIX (BLE enrol/fallback for H1270; compare BrawnyBravo PR #252 "release idle BLE links"). |
| #245 | proposal | BrawnyBravo (OP) 10-09, no comments | Proposal: confirm cloud/MQTT commands against the AWS IoT status frame and resend dropped ones. No PR. | REPLY: accept/decline the design. |
| #244 | support/bug | Roachforlife (OP) 10-09, no comments | 10x H5054, all no updates, connection mode Unavailable; API key only apparently; was using Govee MQTT addon. Pasted system-info, no device diagnostics (imgur screenshot). | DATA-NEEDED: Download diagnostics; ask whether account login is configured. Not obviously the #243 cause (all 10 fail, not 1). |
| #243 | bug | verreaul (OP) 10-09 | 6x H5054 on 2x H5040; one with an all-digit 18-char ID is classified as group (`device_id.isdigit()` in `models/device.py` `from_api_response`, also coordinator ~4880 and `api/lan_client.py` ~226) and skipped. Debug log yes. | FIX (group detection must not use `isdigit()` alone for concrete device types) + REPLY. |
| #242 | bug | Darroll (OP) 10-09 | Cloud-only install: every entity unavailable when API reports `online:false`. Follow-up corrects himself: 2 devices really are offline (control endpoint returns "Device is offline"); narrower ask: let a successful control round-trip / recent IoT signal override the flag, surface the real reason; opt-in `assume_online` secondary. | REPLY (design decision) + possible FIX. Opposite pull to #258. |
| #241 | feature | Jan-Niklas703 (OP) 10-08, no comments | H6099 TV Backlight 3 Lite: no DreamView/Video Mode switch; `dreamview_enabled: null`; Alexa "Video mode" works. Offers diagnostics. | DATA-NEEDED: diagnostics while toggling Video Mode in the app (MQTT frame capture). |
| #240 | bug | sertanakar-tech (OP) 10-07, no comments | H7073: on/off and scenes work, no colour control. Screenshots only. | DATA-NEEDED: Download diagnostics. |
| #239 | feature | Peyto79 (OP) 10-07, no comments | H7045 string lights: wants the app's bright "white mode". | DATA-NEEDED: diagnostics + frame capture while toggling white mode in app. |
| #237 | bug | DanEllaweig (OP) 10-06, no comments | 6x H5108; status query closes AWS IoT session; ~35 min reconnect churn per restart until quarantine; 14x H5086 plugs blind meanwhile. Verified local fix: add H5108 to `MQTT_STATUS_QUERY_EXCLUDED_SKUS`. Says it affects safety monitoring, asks for a quick release. | FIX: merge PR #238 (open since 10-06). REPLY after release. **High priority.** |
| #236 | bug | veltho (OP) 10-06, no comments | 2x H5111 (fw 1.00.09) behind H5151 (fw 1.00.27 / wifi 2.06.23): temperature Unknown; Developer API `online:false`, `sensorTemperature value ""`; BFF has stale `tem:-2090` for one. Diagnostics observations yes. | REPLY + FIX/investigate BFF fallback for H5111-on-H5151. |
| #228 | bug + feature series | StevenC4 (OP) 10-02 | H7175 kettle. Opened PRs #229-#235 as a stack and asked: "Would you take 2-4? Would you accept 5 (ptReal keep-warm, default off)?" Unanswered for 3 weeks. | REPLY: answer the scope questions; review #229 first. |
| #224 | feature | jcsalos-ux (OP) 10-03 | Confirms Upper/Lower probe entities work on 2026.10.0; captured the live `bodyAppearedEvent` with `probesState {top:0, bot:1}` matching MQTT `raw[13]/raw[14]`. | CLOSE (thank, confirmed). |
| #223 | feature | holger-dunst 10-03 (OP hanssepp123-hue silent) | H1252 (WiFi FW 1.01.31 / HW 1.04.03) on 2026.10.0: verified ptReal frames (zone on/off `33 30 <zone> <on>`, zone CT, `aa 30` zone state push), full patch posted inline (new `GoveeRingLight`, `PTREAL_LIGHT_ZONE_SKUS`), "happy to open a PR". Also reports 2 tests failing on untouched v2026.10.0 under Python 3.14.4 (`test_dual_probe.py::TestSecondProbeEntity::test_distinct_unique_id_from_probe_one`, `test_setup_entry_account.py::test_services_resolve_registry_and_govee_ids`). OP never answered the 10-02 ask to test H1232 ring 14-16 / Main light. | REPLY: invite holger-dunst to open the PR. FIX pointer: the two py3.14 test failures. DATA-NEEDED from OP (H1232 ring 14-16). |
| #222 | bug | Araknus13 (OP) 10-02 | On 2026.10.0: MQTT `connected:true`, `inbound_messages: 0` after 70 min, `last_inbound_at: null`, `tracked_devices: 0`; cloud poll fine; `connection_mode` reads `cloud_api` (fix not yet exercised). Asks: (1) diagnostics after a full day, or (2) re-enter account login? Full diagnostics available on request. | REPLY: answer the 1-or-2 question (maintainer promised to read the inbound log). Possibly related to #259's account-wide status-query refusal. |
| #213 | bug | Rusich90 10-11 (after Audiosenpai 10-10) | **Fix not working.** Audiosenpai, H66A0 on 2026.10.0: DreamView OFF works, ON does not start sync though the ptReal frame is sent and acknowledged; switch reports ON. Rusich90: R2A80 (also "TV Backlight 3 Pro"; softVersion 1.00.20, wifiSoftVersion 1.01.18) DreamView works via plain REST `dreamViewToggle`, response includes `dreamType: 'movie'`; same `33 60 01` echo, so the echo doesn't indicate video mode. OP (PanagiotisKaraliolios) has not reported back. No diagnostics attached. | REPLY + FIX (H66A0 video-mode ON frame); DATA-NEEDED: diagnostics from Audiosenpai with a capture of app-initiated DreamView ON. |
| #211 | feature | SamWiIIiams 10-21 (after RuslanMelnychenko 10-18) | OP is reverse-engineering the Android app; working: overall/ripple/bottom brightness, ripple colour, bottom CT; side brightness not yet; plans a PR. SamWiIIiams posts H60B0 frame table (side brightness needs a trailing segment mask; `33 30 <sec>` section on/off; batch frames in one `command` array) and links his own LAN bridge repo plus a "request support" form. Frames are third-party claims, unverified here. | REPLY: encourage OP's PR; frames from the other commenter are unverified (treat the external link as outside the project). No action on the link. |
| #209 | bug | frozenbutt 10-09 | Same H7105 Tower Fan 2 missing on 2026.10.0, HA 2026.9.4; in `bff_device_census` but not `raw_api_devices`; **API key and app login are the same account** (rules out the maintainer's 09-21 hypothesis). | REPLY: Developer API doesn't list H7105 (Govee-side); decide whether to support BFF-only fan control or point users to Govee support. #260 is a dup. |

## Regressions

- **No confirmed regression in 2026.10.0.** No thread reports something that worked on 2026.9.x breaking on 2026.10.0.
- **Fix reported not working:** #213 H66A0 DreamView ON (v2026.9.15 ptReal video-mode path) still doesn't start screen sync on 2026.10.0 (Audiosenpai, 10-10). OFF works.
- **Fixes shipped but still unverified on hardware:** #222 `connection_mode` fix (reporter can't exercise it yet); #226/#227 LAN availability under a real WAN outage (maintainer asked, no report); #223 H1232 ring segments 14-16 and Main light (OP silent since 10-02).
- Not regressions but pre-existing behaviour reported on 2026.10.0: #246 (H1270 BLE flapping, "since a few months ago"), #237 (H5108 quarantine churn since 9.7), #242/#258/#236 (`online` flag handling).

## Close candidates

| # | State | Evidence | Action |
|---|---|---|---|
| #224 | OPEN | OP confirmed both probe entities work on 2026.10.0 and cloud event semantics match (10-03) | CLOSE with a thank-you |
| #221 | closed by reporter 10-02 | jfrykman (H7124/H7129) and k8seren (H7126) confirmed on 2026.10.0 | NONE (optional thanks) |
| #220 | closed by reporter 10-16 | Ein-nor: "It works perfectly" (H605B) | NONE |
| #198 | closed by reporter 10-05 | jlmaners: both lights (H6199/H6163) work | NONE |
| #226 | closed by maintainer 10-01 | shipped via #227 | NONE |
| #186 | closed by maintainer 10-23 10:54Z | reporter never sent the Spectrum diagnostics asked for on 10-02 | NONE |
| #210 | closed by maintainer 10-23 10:56Z | maintainer had said "leaving open until you've confirmed"; reporter never confirmed | NONE |
| #85 | closed | v2026.10.0 reply asked reporter to switch back to Auto; no response | NONE |
| #237 | OPEN | closes when PR #238 merges and ships | CLOSE after release + reporter confirms |

## PR review threads

All 19 open PRs: **0 reviews, 0 inline review comments, 0 maintainer comments, no review requests**, all `MERGEABLE`. No maintainer requests left unanswered and no review feedback unaddressed, because none has been given. The waiting is entirely on the maintainer.

| PR | Author | Opened | Links | Conversation |
|---|---|---|---|---|
| #259 | meeowgler | 10-20 | refs #195 | none. Stops the status sweep when AWS IoT refuses status queries account-wide (every session drops ~10 ms after first query). Overlaps #237/#238 territory and maybe #222. |
| #257 | BrawnyBravo | 10-14 | none | none (leak sensor latching wet after reload) |
| #256 | BrawnyBravo | 10-14 | none | none (daily-release workflow gate fixes; touches `.github/workflows/daily-release.yml`) |
| #255 | BrawnyBravo | 10-14 | none | none (segment modes on options save, diagnostics device, state merge) |
| #254 | BrawnyBravo | 10-14 | refs #131 #53 | none (segment brightness send, brightness round-trip, scene refresh) |
| #253 | BrawnyBravo | 10-14 | none | none (heater target Celsius, poll freezing) |
| #252 | BrawnyBravo | 10-14 | none | none (BLE enrol matching radio, release idle BLE links, LAN client); possibly relevant to #246 |
| #251 | BrawnyBravo | 10-14 | refs #132 | none (login/MQTT recovery after network errors) |
| #250 | BrawnyBravo | 10-14 | refs #226 | none (429 back-off, send once, daily request count) |
| #248 | EasyBizz | 10-13 | none (no issue exists for H8057) | author posted hardware validation on 2x H8057, HA 2026.10.1 + int 2026.10.0: segment 4 RGB works via ptReal |
| #247 | snoack | 10-13 | refs #200 (open) | none (H5086 reboot counted as energy reset; 1-min status query) |
| #238 | BrawnyBravo | 10-06 | closes #237 | none. One-line H5108 exclusion with reporter-verified fix; **oldest small, safety-relevant PR** |
| #229-#235 | StevenC4 | 10-02 | #229 closes #228; #230-#235 stacked (each contains the lower layers) | none on any PR; scope questions in #228 unanswered (see above). #234 adds a general `govee.request_status` service. #235 is opt-in experimental, author says fine to decline. |

## Waiting on reporter

| # | Waiting for | Since |
|---|---|---|
| #249 | Security: maintainer enabled the private reporting channel ("@BrawnyBravo enabled thanks", 10-23 10:53Z); private vulnerability reporting API reports `enabled: true`; no repository security advisory is listed yet. Waiting for the reporter to file privately. No details reproduced here. | 10-23 |
| #223 | OP hanssepp123-hue to test H1232 ring 14-16 and Main light | 10-02 |
| #213 | OP PanagiotisKaraliolios to report on v2026.9.15+ (another user already reported failure) | 09-28 |
| #226 / #227 | drewcotten: real WAN outage behaviour (optional) | 10-02 |
| #222 | after the maintainer answers, Araknus13 will pull diagnostics again | 10-02 (ball is with maintainer first) |
| #244, #240, #241, #239 | diagnostics (not yet requested: maintainer must ask first) | n/a |

## Duplicates and clusters

- **H7105 Tower Fan 2 missing from the Developer API:** #209 (canonical, 2 reporters) and #260 (one-line dup). Close #260 into #209.
- **H5054 leak sensors:** #243 (one all-digit device ID treated as a group; root cause found) and #244 (all 10 sensors no updates, likely config/transport, needs diagnostics). Related, probably not the same cause; don't close #244 as a dup until diagnostics show all-digit IDs.
- **AWS IoT status-query session drops (#195 lineage):** #237 + PR #238 (H5108 exclusion), PR #259 (account-wide refusal), possibly #222 (connected session, zero inbound messages).
- **`online` flag semantics, pulling opposite ways:** #242 (cloud flag shouldn't veto a working transport), #258 (offline sensors should look offline, expose real measurement time), #236 (H5111 behind H5151 `online:false` with empty values). Needs one design decision; related PR #250 (outage detection, refs #226).
- **TV backlight DreamView / video mode:** #213 (H66A0 ON fails; R2A80 works via REST), #241 (H6099 has no switch), #220 (H605B, fixed and confirmed).
- **H7175 kettle:** #228 + PR stack #229-#235.
- **BrawnyBravo code-review series:** PRs #250-#257 + proposal #245 + #238 + security channel #249.
- **Ceiling Light Pro zones:** #223 (H1232 shipped; H1252 patch offered), related closed #131 (main downlight) and PR #254 (refs #131). #246 H1270 is the same family but a transport problem.
- **H5086 power monitoring:** PR #247 refs open #200; #237 reporter's 14x H5086 plugs are hurt by the H5108 churn.
