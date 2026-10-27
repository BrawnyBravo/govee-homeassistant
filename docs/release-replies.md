# Release reply queue

Replies to post after the next release, on threads that no released commit references with `#N`. Those get replies automatically. The daily-release workflow (`.github/workflows/daily-release.yml`) posts each entry below after it creates the release, then empties this list and commits that. On a night with no release, the entries wait.

Add one `##` section per thread:
- `close: yes|no`: close the thread after replying. Only use `yes` when the reporter confirmed the fix or asked for it to be closed.
- `brief:` what the reply must say. The workflow writes the comment from the brief, citing the released version only where the brief asks for it.

<!-- entries below; the workflow removes them once posted -->

## #236
close: no
brief: Thank veltho for testing v2026.10.1 so carefully (gateway power-cycle, reload, fresh diagnostics). Explain what the diagnostics show: the integration now reads the account data correctly, but Govee's own account copy for these two sensors is stale. The freezer's last stored reading is from 4 October, matching what Home Assistant shows, and the fridge has none at all, while other sensors on the same account are only minutes old. So the H5151 gateway seems to have stopped passing these two sensors' readings to Govee's cloud, and no other client found reads them from anywhere else. Ask two things: with the phone's Bluetooth switched off, or away from home on mobile data, does Govee Home still show current values for both sensors? And does the H5151's page in the app show it online with both sensors listed? If the values go stale without the phone nearby, the app was reading them over the phone's own Bluetooth. Then re-pairing the sensors to the gateway is worth a try, or Home Assistant's own Bluetooth (the Govee BLE integration or an ESPHome Bluetooth proxy) can read them directly. Do not cite a version.

## #261
close: no
brief: Thank cbaum0407 for the diagnostics and the clear description. Say the integration sends the H1A42 the same documented segment-colour command that works on other RGBIC strips, and Govee accepts it, so the strip itself or Govee's cloud is ignoring the colour. Ask them to try two things in order. First, in the Govee app switch the strip's Gradient setting off, set a solid colour, then run govee.set_segment_color for segment 0 green again: does the first segment turn green? If not, enable the account login (email and password) in the integration's Configure options, then run the govee.send_raw_ptreal action on the strip with the frame 33 05 15 01 00 FF 00 00 00 00 00 00 01 00 00 (should turn only the first segment green), then with 33 05 15 01 00 FF 00 00 00 00 00 00 FF 7F 00 (all fifteen segments), and say what lights up each time. Ask for a diagnostics download (Settings → Devices & services → Govee → ⋮ → Download diagnostics) right after the first test, so the command and Govee's answer are in it. Write the frames inline, not in a code block. Do not cite a version.

## #239
close: no
brief: Thank Peyto79 for finding that White light is one of the scenes. Say that picking a different scene from Home Assistant always sends a new scene command, so something on the device or Govee's side is keeping it on White light. To see which, ask for a diagnostics download (Settings → Devices & services → Govee → ⋮ → Download diagnostics) with the account login enabled, taken right after this sequence in Home Assistant: select White light, wait about 10 seconds, then select another scene such as Sunset. Also ask: in the Govee app itself, can they switch straight from White light to another scene without turning the light off first? Do not cite a version.

## #213
close: no
brief: Thank Audiosenpai for the diagnostics taken while DreamView ran from the app, and Rusich90 for the R2A80 data point (that model needs nothing). Say what this release changes: the H66A0's DreamView switch now follows the mode the light reports itself, so it no longer shows ON when screen sync isn't running. Explain the diagnostics showed the light uses a different video-mode command layout from the one the integration sends. Ask them to try it: with the backlight on and not in video mode, run the govee.send_raw_ptreal action on the H66A0 with the frame 33 05 00 00 08 64 00 02 and say whether screen sync starts (in Movie). If it doesn't, try 33 60 01 01 01. Mention that the app's single "Game" movie mode option does not look like what starts sync, so it is not being exposed. Write the frames inline, not in a code block. Cite this release for the switch change only.

## #265
close: no
brief: Thank FakeMayo for the detailed step-by-step log, and for confirming the setpoint now survives a restart (that was the #253 fix). Say what this release changes for the H7130: a heat-level or setpoint change from Home Assistant now shows the heater as on, matching what the device does; setpoints are rounded instead of cut off (69.8 °F was being sent as 20 °C, one degree low); a new Oscillation switch; and Auto Stop now uses the device's own Auto Stop setting, with the separate thermostat function as its own Thermostat switch. Say the Auto Stop change is unverified on hardware and ask which of the two switches actually changes the heater's behaviour. Ask two more things: for the case where 73.4 °F seemed to do nothing, which exact value they picked and what the Govee app showed for the heater's mode at the time; and whether the heater also drops to Low when the setpoint is changed from the Govee app. Ask for a diagnostics download (Settings → Devices & services → Govee → ⋮ → Download diagnostics) after trying. Do not include any frames or raw commands: this is a heating appliance. Cite this release.

## #269
close: no
brief: Thank magicmn for the clear write-up. Say two things work today: the select.select_option action always resends the scene even when it is already selected, and light.turn_on with effect set to the scene name does too, so automations can use either. Only the dashboard dropdown ignores picking the option it already shows. Say a change is planned so the scene and DIY selects show None while the light is off and the scene comes back when it turns on. It changes what every light shows (it reverses the March request in #18), so it ships in a release of its own. Do not cite a version.

## #243
close: yes
brief: Thank verreaul for confirming on v2026.10.1 that the sixth H5054 now gets its leak, battery and connectivity entities and that the other entities kept their IDs. Say the issue is being closed on that basis and can be reopened if anything comes back. Do not cite a version.

