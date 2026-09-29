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

## Cloud environment prerequisites (owner, once per environment)

Measured 2026-09-29 (routine `xptb-cloud-corpus-reproof-79`, session
`cse_01UCZME8U9HMTYQ5Jk64srRU`): a cloud session's outbound HTTPS goes
through a policy proxy that gates GitHub by the SESSION's GitHub credential
(the Claude GitHub App), not by any token in the environment. With the app
installed only on `XPTerrainBuilder`, `api.github.com/repos/shizumaat/
XPTerrainBuilderData-cloud/...` answers HTTP 403 "GitHub access to this
repository is not enabled for this session" even with a valid PAT, and
`add_repo` answers "you don't have access". The image also ships no GDAL
(`gdal-config: command not found`), so `pip install gdal` fails and every
`from osgeo import gdal` in the engine would too.

1. **GitHub App access:** GitHub → Settings → Applications → Installed
   GitHub Apps → Claude → Configure → Repository access → add
   `shizumaat/XPTerrainBuilderData-cloud` (read is enough). A cloud session
   then attaches it with `add_repo(owner="shizumaat",
   repo="XPTerrainBuilderData-cloud", access="read")` before any
   `gh release download`. `XPTB_DATA_TOKEN` stays as the credential
   `gh` uses for the release API once the proxy admits the host.
2. **Setup script** (the environment's "Setup script" field; runs before
   Claude starts, skipped when a cached environment exists):

   ```sh
   set -e
   # the image ships PPAs (deadsnakes, ondrej/php) the egress proxy answers
   # 403 to; apt-get update exits 100 on them (measured 2026-09-29) — drop them
   rm -f /etc/apt/sources.list.d/*deadsnakes* /etc/apt/sources.list.d/*ondrej*
   apt-get update -qq
   DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libgdal-dev gdal-bin libspatialindex-dev
   cd Ortho4XP
   python3 -m venv venv
   venv/bin/python -m pip install -q --upgrade pip
   grep -v '^gdal' requirements.txt > /tmp/req.txt
   venv/bin/python -m pip install -q -r /tmp/req.txt
   venv/bin/python -m pip install -q "gdal==$(gdal-config --version)"
   ```

   The Linux pin in `requirements.txt` (`gdal==3.9.0`) is for the AppImage
   build; in the cloud the wheel must match the distro's `libgdal`, hence
   `gdal-config --version`.

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
| `snap-20260928-002e4dda` | `002e4dda26a6c5b874430c728bc62ff89e7aa7f676a9d5422fab2bb2a85ceea9` | CYXY (121, 199.4 MB, 138.4 MB); HECA (8,555, 2,264.5 MB, 332.8 MB); NLWF (164, 43.2 MB, 5.4 MB); SPJC (886, 410.5 MB, 71.5 MB) | TFFJ (owner RULINGS 2026-09-29b: the TFFJ product stays local-only; `refused_by_ruling` in the allowlist) |

It supersedes `snap-20260928-70cb6ff7` (CYXY, HECA, NLWF only). Numbers
from that hash don't carry over.

Proof on the owner machine (2026-09-28, issue #79): SPJC was built from
`SPJC.tar.gz` alone with rc 0 and 0 snapshot leaks. Its `body_sha` was
`754fc43f209e4df3e857a77faa401891c42bd7301edc8cb9635af419600df617` (420
shapes), identical to the shared-corpus build on the same code. Getting
there took three fixes to the cut, all things a read trace cannot see:

- the library index. v2 resolves `lib/...` placements only through the
  engine's cached index, keyed on the install path. The cut ships
  `data/library_index.json` and the mount re-keys it for the snapshot.
- restore-before-read siblings. The loader stats `X.obj`, then reads
  `X.obj.anchor_bak`, so the cut carries `X.obj` too.
- neighbour tiles. Every `*_airport_insets` dir the trace touched is carried
  whole, since neighbour rasters are GDAL reads. The Global Airports slice
  keeps every airport of the cut tiles with neighbours.

CYXY, HECA and NLWF on this hash have not been re-proven by a snapshot
build.

SPJC's packs are `OWNER-CONFIRMED 2026-09-29b`. The other allowlist entries
are still marked `OWNER-CONFIRM`: the lane read them from pack readmes and
freeware listings, and RULINGS 2026-09-29b says the rest of the allowlist
stands as cut.
