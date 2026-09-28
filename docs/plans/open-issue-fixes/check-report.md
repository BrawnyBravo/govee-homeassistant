---
result: PASS
ts: 2026-09-27T15:57:58Z
ref: 229c51cbd286552cfd616c21b1466511ef020d24
scope: plan
plan: open-issue-fixes
---
# Check report: open-issue-fixes

## Gates
| Gate | Result |
|---|---|
| pytest | 3515 passed; coverage 99.88% (floor 95%); auth.py, coordinator.py, services.py 100% |
| flake8 | 0 violations |
| black --check | clean |
| mypy (strict) | 0 errors |
| build | n/a (Python custom component; CI hassfest/HACS runs on push) |

## Tasks
| Task | verify | Held-out check |
|---|---|---|
| T-001 stale BLE skipped (#198) | ok | ok: advert backdated past BLE_STALE_SECONDS, real refresh → REST |
| T-002 BLE writes recorded as sends (#198) | ok | ok: write doesn't reset the advert clock; recent_commands transport=ble |
| T-003 leak-alert hardening (#218) | ok | ok: real GoveeAuthClient, non-dict/invalid-JSON 200 → clear returns False |
| T-004 raw ptReal coordinator (#208) | ok | ok: packet shape, checksum, refusals |
| T-005 send_raw_ptreal service (#208) | ok | ok: 7 frame-parsing cases |

## Deterministic lane
18 pass, 1 n/a (det-18: runtime hook on shell commands), 0 findings. Rows written for a TypeScript layout (det-01/03/05/07/09/10, anti-mock, o2) were re-run against `custom_components/` and base `8e7de04`.

## Semantic lane
Survey (security + wiring): CLEAN. One Minor finding (a non-dict 200 leak body reported success) was fixed in `229c51c` before the reject critic ran.

## Ratchet
Bootstrapped this run (`docs/sweeps/ratchet.json`, Python detectors): test_count 3515, type_errors 0, lint 0, mocks_in_src 0, todo 0, type_ignore 10. No regression possible on the first run.

## Critic
`MODE: reject`: **LGTM**. Advisory only: duplicated 20-byte checksum check (service + coordinator, harmless); unreachable "unknown" sku fallback.

## Not auto-verified
Hardware behaviour: whether the H6199 responds once BLE is skipped (#198), and which frame the H7026 needs for segments 16–29 (#208). Both need a report from the reporter.

Automation: deterministic 18/18 runnable + ratchet + critic. e2e_coverage: none (no hardware). Recommendation: needs-human-review (hardware).
