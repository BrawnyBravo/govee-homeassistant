# Fork notes

This is BrawnyBravo's fork of [lasswellt/govee-homeassistant](https://github.com/lasswellt/govee-homeassistant).

## Why the fork exists

It is a workbench for fixes that go back upstream. Changes are made and tested
here, then sent to the upstream project as pull requests. The fork is not meant
to diverge from upstream, and it is not a distribution.

**Home Assistant installs the upstream project, not this fork.** A fix only
reaches a running install once upstream has merged and released it.

## What it carries that upstream does not

As of 2026-09-13, nothing functional. Everything below is fork plumbing:

| Change | Why it stays here |
| --- | --- |
| `.github/workflows/sync-upstream.yml` | Daily merge of upstream `main`; opens an issue on conflict and closes it once a later run merges cleanly. |
| `-house.N` suffix on `version` in `custom_components/govee/manifest.json` | Makes a build of this fork distinguishable from an upstream release. |

Upstreamed from this fork:

- [#191](https://github.com/lasswellt/govee-homeassistant/pull/191), merged 2026-09-11 and
  released in v2026.9.5: per-device poll deadlines, skipping devices whose entities are all
  disabled, the daily request counter, and attributing entities to devices by separator
  rather than by prefix.

## Syncing: the version line conflicts by design

The sync job merges upstream every day. Whenever upstream bumps its version,
`manifest.json` conflicts, because both sides changed the same line. That is
expected. Resolve it by taking upstream's new version and keeping the suffix:

```
upstream "2026.9.7"  +  fork "2026.9.6-house.1"  ->  "2026.9.7-house.1"
```

For any other conflict: take upstream's version of anything upstream already
has, keep only what is genuinely the fork's, run the tests and linters, and push.
The rule is to resolve a conflict, never to let the fork drift.

## Do not create GitHub Releases here

HACS tracks this repository's default branch. Publishing a Release switches it
to tracking releases instead.
