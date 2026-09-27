## 2026-09-27T15:31:56Z plan created
Ruling: class=architectural tasks=5 — four independent fixes across coordinator/auth/services (about 9 files); #208 frame unknown, so a debug service instead of a guessed codec
## 2026-09-27T15:32:58Z build T-001 start (attempt 1)
## 2026-09-27T15:35:11Z verify T-001 ok=true
## 2026-09-27T15:35:11Z build T-002 start (attempt 1)
## 2026-09-27T15:37:20Z verify T-002 ok=true
## 2026-09-27T15:37:20Z build T-003 start (attempt 1)
## 2026-09-27T15:39:35Z verify T-003 ok=true
## 2026-09-27T15:39:35Z build T-004 start (attempt 1)
## 2026-09-27T15:42:02Z verify T-004 ok=true
## 2026-09-27T15:42:02Z build T-005 start (attempt 1)
## 2026-09-27T15:46:25Z verify T-005 ok=true
Ruling: descope — critic advisory 5 (blind BLE writes until the next staleness poll) left as is; the window existed before and is bounded by 120 s plus the poll interval (T-001, round 1)
## 2026-09-27T15:50:08Z build complete 5/5 done; critic LGTM; advisories 1-4 fixed in follow-up commit
