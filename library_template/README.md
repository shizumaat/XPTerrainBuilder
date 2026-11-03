# XPTerrainBuilder patch library

Solved airport patches for [XPTerrainBuilder](https://github.com/shizumaat/XPTerrainBuilder),
shared by its users and by scenery developers. A patch is matched to the
CONTENT of the scenery pack it was made for (its apt.dat block and its DSF),
never its name: it only does anything for a user who has that pack installed,
and it is applied to the user's own copy.

Nothing here is hosted by a server. XPTerrainBuilder reads this repository's
files directly (no account needed) and publishes into it through pull requests
from the publisher's own GitHub account ("Publish patch" in the app).

## Layout

```
publishers.json          verified developers and the packs they own; reviewers
licences.json            the source allowlist (licence gate)
entries/<ICAO>/<pack>/<pack version>/v<N>/
    manifest.json        match key (pack signature, auto-patch law, solve settings),
                         versions, file hashes, sources and licences
    edits.json           the user edits and role overrides
    ATTRIBUTION.txt      credits, built from the manifest
    solved/*.xz          the solved patch family (patch, sidecar, graded surface,
                         object plans), xz-compressed
    edits/*.xz           the edited patch, when the entry has one
index/<region>.json      per 10-degree region: every airport's entries (rebuilt on merge)
```

`<pack version>` is the first 12 hex digits of the pack signature; `v<N>` is
the entry's version. Publishing an improvement adds the next version; older
versions stay. A published version never changes.

## Licence

Every entry is published under the [Open Database License (ODbL) 1.0](LICENSE.md),
because patches are derived from OpenStreetMap data. © OpenStreetMap
contributors; each entry's `ATTRIBUTION.txt` credits its elevation sources.
Payware packs: a community entry for a payware pack needs pack-relative
encoding, which the library does not take yet; the pack's own developer can
publish as a verified developer.

## Checks and merging

`.github/workflows/check.yml` runs on every pull request. It READS the entry as
data (JSON, hashes, decompressed text) with XPTerrainBuilder's own checker
(`Ortho4XP/src/patch_library/checks.py`) and never runs anything from it. A
verified developer's pull request that adds one entry for one of their own
packs and passes the checks is merged automatically; every other pull request
is labelled `needs-review` for the community reviewers, with the maintainer as
final say. `.github/workflows/index.yml` rebuilds `index/` on every merge.

## Verified developers

The maintainer adds a developer's GitHub login and their packs to
`publishers.json` (pack names as `fnmatch` patterns, with the airports they
cover). Their entries get a "Verified developer" badge in the app and are listed
first.
