# Release reply queue

Replies to post after the next release, on threads that no released commit references with `#N`. Those get replies automatically. The "govee daily release" routine posts each entry below after it creates the release, then empties this list and commits that. On a night with no release, the entries wait.

Add one `##` section per thread:
- `close: yes|no`: close the thread after replying. Only use `yes` when the reporter confirmed the fix or asked for it to be closed.
- `brief:` what the reply must say. The routine writes the comment from the brief, citing the released version only where the brief asks for it.

<!-- entries below; the routine removes them once posted -->

## #151
close: yes
brief: Thank @Araknus13 for the confirmation from a full cold night on v2026.9.14: the curve from 11.7 °C down to 8.0 °C and back was continuous, with no values in the 40–63 °C band, so the byte-14 rollover fix is confirmed and this issue is closed. On the separate MQTT silence (the session reconnected at 19:25 UTC on 2026-09-26, reads connected with no errors, but nothing has arrived since): `tracked_devices` only counts devices heard from since that reconnect, so the 0 is a symptom, not the cause. The integration resubscribes to the account topic on every reconnect and checks that AWS accepted it, so a refused subscription isn't the explanation. Ask them to open a new issue for it with a fresh diagnostics download (UI button). Before that, ask them to reload the integration once (Settings → Devices & services → Govee → ⋮ → Reload) and report whether MQTT frames start arriving again. That tells us whether a fresh session is enough, or whether the stored IoT credentials need a new login.

## #199
close: yes
brief: Thank @barmorebd for confirming on v2026.9.13 that the H2A41 DreamView switch appears and starts and stops screen sync. Closing as fixed. Mention that the H66A0 (#213) turned out to need a different command path, shipping in this release, in case they see anything related on the H2A41.

## #200
close: no
brief: Thank @k-perri for confirming on v2026.9.13 that the H5106 and H7152 temperatures are correct and that the H5086 power readings now have two decimals and work in the Energy dashboard. Leave the issue open until they've had a chance to check the air-quality label, and ask them to report back when they have.
