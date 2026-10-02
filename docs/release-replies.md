# Release reply queue

Replies to post after the next release, on threads that no released commit references with `#N`. Those get replies automatically. The daily-release workflow (`.github/workflows/daily-release.yml`) posts each entry below after it creates the release, then empties this list and commits that. On a night with no release, the entries wait.

Add one `##` section per thread:
- `close: yes|no`: close the thread after replying. Only use `yes` when the reporter confirmed the fix or asked for it to be closed.
- `brief:` what the reply must say. The workflow writes the comment from the brief, citing the released version only where the brief asks for it.

<!-- entries below; the workflow removes them once posted -->

## #211
close: no
brief: Thank the reporter for the diagnostics. They confirm the Developer API has no per-zone colour or relative-brightness channel for the H60B0: only 8 generic segments (the earlier #83 capture had 15, so the count varies by revision), and #196 already showed `segmentedBrightness` does not move the Ripple light. The lamp's own AWS IoT status frames do seem to carry the zone settings (one looks like the bottom light at 100 % and 2700 K), so a native path is plausible but no write frame is known yet. Ask, with the lamp ON and the account login enabled, for one diagnostics download (Download diagnostics button) after each single change in the Govee app: side brightness 30 % to 80 %; ripple brightness 30 % to 80 %; bottom brightness 100 % to 50 %; bottom warmth 2700 K to 5000 K; side colour to pure red; ripple colour to pure blue. Also ask which physical part lights up when each of the 8 segment entities is changed in Home Assistant. No entities until a frame is verified on the lamp. Do not cite a version.

## #186
close: no
brief: Glad the H6022 responds to music mode now; the going-dark bug was fixed by sending the app's own AWS IoT frame with the account login. On Spectrum looking different: this lamp's API numbers Spectrum and Rolling the other way round from other Govee lights, so Home Assistant's "Spectrum" may be playing Rolling. Ask whether Home Assistant's Rolling looks like the app's Spectrum. To settle it, ask them to pick Spectrum in the Govee app, wait a minute, and attach a device diagnostics download (Download diagnostics button); the lamp's own report in it shows the exact effect code and colour the app uses, and the integration will be matched to it. Do not cite a version.

## #85
close: no
brief: The H5103 is now on the list of models whose Developer API temperature arrives in Fahrenheit (via PR #225), so with the temperature unit option on Auto it converts automatically and the Fahrenheit-option workaround from this thread is no longer needed. Cite the released version. Ask the reporter to switch the option back to Auto after updating and confirm the reading matches the Govee app.
