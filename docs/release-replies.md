# Release reply queue

Replies to post after the next release, on threads that no released commit references with `#N`. Those get replies automatically. The daily-release workflow (`.github/workflows/daily-release.yml`) posts each entry below after it creates the release, then empties this list and commits that. On a night with no release, the entries wait.

Add one `##` section per thread:
- `close: yes|no|duplicate|declined`: close the thread after replying (`no` leaves it open; `duplicate` and `declined` close it as not planned). Only use `yes` when the reporter confirmed the fix or asked for it to be closed.
- `brief:` what the reply must say. The workflow writes the comment from the brief, citing the released version only where the brief asks for it.

<!-- entries below; the workflow removes them once posted -->




## #288
close: no
brief: Nothing for Tap-to-Run ships in this release; do not say it is fixed or added, and do not cite this version. Thank the reporter for the exec-plat/home test: it showed the integration's existing account login works, so no extra sign-in is needed. Tap-to-Run is now planned: each Tap-to-Run appears as a Home Assistant scene on the integration's hub device, behind a new option that is off by default, and activating it sends the same stored commands the app sends, in order. Tap-to-Runs whose steps only work over Bluetooth are skipped. Say we will post here when a release carries it and would welcome their testing then (turn the option on, check each scene behaves like the app, attach the UI diagnostics download).

## #314
close: no
brief: Nothing for this issue ships in this release; do not say it is fixed and do not cite this version. Explain from their diagnostics: Govee's official Developer API returned 3 DIY scenes for the H61D3 with no error, so the integration is showing everything Govee sent; the three DIYs created on the device after it joined the account are missing from Govee's own API response. Other Govee API users report the same partial DIY lists, and Govee has not explained the rule. Next step: a coming release adds a diagnostics-only check of the Govee app's own DIY list for each device, to see whether it holds the missing scenes and whether they can be activated the same way. When that release is out we will ask them for a fresh diagnostics download (Settings → Devices & services → Govee → ⋮ → Download diagnostics). Leave the issue open.
