# Cloud test corpus

Owner ruling: RULINGS 2026-09-28a (7), which amends e9daef5 for cloud lanes.
Tool: `Ortho4XP/tools/harness/corpus_snapshot.py` (see its `tools/INDEX.md` row).

A cloud lane has neither the shared data repo (`/Users/noah/XPTerrainBuilderData`)
nor an X-Plane install. Instead it builds from a **hash-stamped snapshot**: the
exact subset of both that `build_airport.py ICAO` reads, cut per airport and
published as release assets in the private repo
`shizumaat/XPTerrainBuilderData-cloud`.

## The comparability rule

A snapshot counts as a lawful second corpus. **Numbers compare only within
one snapshot hash.** Never compare them across two snapshots, and never
between a snapshot and the shared corpus.

- `frame.json` records `corpus = "snapshot@<hash12>"` plus a `corpus_snapshot`
  block with the full hash, the directory and the verified airports. A
  shared-corpus build records `corpus = "shared"`.
- The artifact-ledger key includes the snapshot hash, so an arm stored on
  one corpus never serves a run on another. `--base-arm` refuses and says
  which corpora differ.
- When the snapshot changes (a new cut), its hash changes. Re-baseline the
  controls on the new hash. Numbers from the old one don't carry over.

## Fetching a snapshot (cloud lane)

The cloud environment carries a read-only token as the secret
`XPTB_DATA_TOKEN`, a fine-grained PAT with `contents:read` on
`shizumaat/XPTerrainBuilderData-cloud`.

```sh
export GH_TOKEN="$XPTB_DATA_TOKEN"
SNAP=$HOME/xptb-corpus                       # any directory
TAG=$(gh release list -R shizumaat/XPTerrainBuilderData-cloud -L 1 --json tagName -q '.[0].tagName')
mkdir -p "$SNAP" && cd "$SNAP"
gh release download "$TAG" -R shizumaat/XPTerrainBuilderData-cloud -p 'CYXY.tar.gz' -p 'snapshot.json'
for t in *.tar.gz; do tar -xzf "$t"; done   # every tarball unpacks into the same tree
cd -  # back to the repo
Ortho4XP/venv/bin/python Ortho4XP/tools/harness/corpus_snapshot.py verify "$SNAP"

export O4_CORPUS_SNAPSHOT="$SNAP"            # or pass --corpus snapshot:$SNAP
cd Ortho4XP && venv/bin/python tools/harness/build_airport.py CYXY
```

Each `<ICAO>.tar.gz` holds every file that airport needs, plus the whole
`snapshot.json`. You can unpack several airports into one directory, since
shared files are byte-identical across tarballs. `verify` re-hashes every file
present and lists the airports whose read set is complete. A build refuses an
airport the snapshot doesn't fully carry.

## What the mount does

`build_airport.py` in snapshot mode:

1. Sets `O4_DATA_REPO=$SNAP/data` before the write guard is imported, so
   the snapshot becomes the protected corpus and any write into it is
   refused. That covers downloads and cache regeneration too.
2. Verifies the snapshot and symlinks each corpus directory of the lane
   (`Elevation_data`, `OSM_data`, `Airport_mod_cache`, ...) into
   `$SNAP/data`. A real directory there is refused.
3. Renders `Ortho4XP.cfg` with the X-Plane paths on `$SNAP/xplane`.
4. Watches for leaks. A read of the real shared repo or the real install
   while the snapshot is mounted means the snapshot was incomplete. It is
   recorded as `snapshot_leaks` in frame.json and the build exits with rc 4.

On a local lane, `corpus_snapshot.py unmount <tag>.frame.json` puts the
shared mounts and the cfg back.

## Cutting a snapshot (local, owner machine)

```sh
cd Ortho4XP
venv/bin/python tools/harness/corpus_snapshot.py cut CYXY NLWF HECA --out /path/snap --skip-refused
```

`cut` runs a traced harness build for each airport
(`build_airport.py ICAO --trace-reads`) unless a trace already exists under
`--traces`. It then copies the read set:

- the DEM part comes from the harness's own `dem_cache_state`
- the pack apt.dat search reads are dropped, and the engine's selection is kept
- Global Airports apt.dat is sliced down to the cut's airport blocks

Next it applies the **licence gate**. Pack content is copied only for packs
listed in `tools/harness/corpus_snapshot_allowlist.json` (freeware, confirmed
by the owner). Any other pack refuses the airport, and OTHH is excluded by
name. Publish the tarballs with
`gh release create snap-<date>-<hash8> <release dir>/*`.

## Current snapshot

| release | hash | airports (files, raw, tarball) | refused by the licence gate |
|---|---|---|---|
| `snap-20260928-70cb6ff7` | `70cb6ff78c6731339b537d469ecfdb422315088f9f1da274acea273a4cb1eb24` | CYXY (120, 198.1 MB, 138.1 MB); HECA (8,507, 2,262.5 MB, 332.4 MB); NLWF (163, 41.9 MB, 5.1 MB) | SPJC (Aerosoft / Limesim static-aircraft library objects and other unlisted packs in its read set), TFFJ (the selected pack is an unlisted product) |

Proof on the owner machine (2026-09-28): CYXY was built from `CYXY.tar.gz`
alone with rc 0 and 0 snapshot leaks. Its `body_sha` was
`f4241e3bf75ca9c7856b760f6dbba14813ce471798be52fd14e40dbfb86d2d1b`, identical
to the shared-corpus build `/tmp/harness/sw0928_CYXY.osm`. The census was
identical too: law-true 1,340 (airside 1,257, groundside 79, mixed 4).

The allowlist entries are marked `OWNER-CONFIRM`. The lane read them from
pack readmes and freeware listings, and the owner has not yet confirmed
them.
