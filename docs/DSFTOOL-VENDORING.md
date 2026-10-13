# Vendoring a DSFTool build (issue #587, RULINGS 2026-10-12f)

The bundled `Ortho4XP/Utils/{mac,lin,win}/DSFTool[.exe]` are replaced by
hand, from ONE run of `.github/workflows/build-dsftool.yml`.  The workflow
never commits.  What it builds and why each build setting is what it is:
`Ortho4XP/Utils/toolchains/build_dsftool.sh` (every pin lives there).

## 1. Run the workflow

    gh workflow run build-dsftool.yml --ref <branch carrying the workflow>
    gh run list --workflow build-dsftool.yml --limit 1     # the run id
    gh run watch <RUN_ID>

All four jobs must be green.  Each build job has already run
`Utils/toolchains/smoke_test_dsftool.py` on its binary (macOS: once per
slice, the x86_64 one under Rosetta).  A red job is a finding, not
something to route around: the Linux and Windows recipes had not been run
anywhere before the first dispatch (only the macOS one was proven
locally, 2026-10-12).

## 2. Download and verify

    mkdir -p /tmp/dsftool-<RUN_ID> && cd /tmp/dsftool-<RUN_ID>
    gh run download <RUN_ID> --name dsftool-binaries
    tar -xzvf dsftool-binaries.tar.gz        # Utils/  SHA256SUMS  BUILDINFO.txt
    shasum -a 256 -c SHA256SUMS              # all three: OK
    cat BUILDINFO.txt                        # pins, toolchains, --version per platform

Compare the three sha256 with the `Identity` step of each build job's log
(`gh run view <RUN_ID> --log | grep -A1 sha256`): the tarball is
assembled by a fourth job, the log line is printed by the job that built
the file.  Check `BUILDINFO.txt` names the three `XPTOOLS_*_SHA` and the
`XPTOOLS_PATCHED_TREE` of `build_dsftool.sh` on the branch you are
landing.

## 3. Judge it on this Mac BEFORE replacing anything

From `Ortho4XP/` (a lane worktree; text goes to the lane scratch, ~1.3 GB
per folder — delete both when done):

    S=<your lane scratch folder>
    NEW=/tmp/dsftool-<RUN_ID>/Utils/mac/DSFTool
    python3 Utils/toolchains/smoke_test_dsftool.py $NEW
    R="$HOME/X-Plane 12/Global Scenery/Global Airports/Earth nav data"
    venv/bin/python tools/dsftool_dump_census.py "$R" --out $S/new.jsonl --tool $NEW --jobs 8 --keep-text $S/new_text
    venv/bin/python tools/dsftool_dump_census.py "$R" --out $S/old.jsonl            --jobs 8 --keep-text $S/old_text
    venv/bin/python tools/dsftool_dump_census.py --diff-text $S/old_text $S/new_text

Expected (measured 2026-10-12 with a local build of the same pinned
source, lane dsfbin587; 7,077 stock DSFs):

* NEW: `0 failed`.  OLD: `8 failed` (the eight crashers of #568).
* `7003 dumps identical, 66 differ; only in OLD 0, only in NEW 8`.
* The only row classes that differ: `'# pool'` (the `# obj_pools found: N`
  comment, 66 files) and `'HEIGHTS'` (14 files on arm64; 17 through the
  x86_64 slice).  Any other class — an `OBJECT`, a `POLYGON_POINT`, a
  `PROPERTY`, `LINE COUNT` — is a STOP.

The old tool's 8 crashes each leave a report in
`~/Library/Logs/DiagnosticReports`; that is expected.

## 4. Replace, record, re-sign

    cp /tmp/dsftool-<RUN_ID>/Utils/mac/DSFTool     Ortho4XP/Utils/mac/DSFTool
    cp /tmp/dsftool-<RUN_ID>/Utils/lin/DSFTool     Ortho4XP/Utils/lin/DSFTool
    cp /tmp/dsftool-<RUN_ID>/Utils/win/DSFTool.exe Ortho4XP/Utils/win/DSFTool.exe
    chmod +x Ortho4XP/Utils/mac/DSFTool Ortho4XP/Utils/lin/DSFTool
    git update-index --chmod=+x Ortho4XP/Utils/mac/DSFTool Ortho4XP/Utils/lin/DSFTool

In the SAME commit:

* `Ortho4XP/Utils/DSFTool.identity.json` — the three `sha256` (from
  `SHA256SUMS`), the three `version` lines (first line of each
  `--version` in `BUILDINFO.txt`; the compile date is the run's day),
  `"patched": true`, `"ci_run": <RUN_ID>`, and `"build"` rewritten to
  "xptools c31ed76b5 + 9c1a06c7b + a3725c8f5, built by
  .github/workflows/build-dsftool.yml".
* `Ortho4XP/Utils/DSFTool-NOTICE.md` — the "Binaries currently bundled"
  table (build, date, run id, toolchain from `BUILDINFO.txt`).
* `Ortho4XP/Licence/copyright.txt`, DSFTool section — the source URL is
  the dead `dev.x-plane.com/cgit` one; replace it with
  `https://github.com/X-Plane/xptools` and add "built from commit
  c31ed76b5 with upstream commits 9c1a06c7b and a3725c8f5; full notice in
  Utils/DSFTool-NOTICE.md".

Signing: the repo file needs none.  The CI binary is ad-hoc signed by
Xcode; `scripts/sign_app.sh` discovers every Mach-O under the app's
`Utils/mac` and re-signs it with the Developer ID and the hardened runtime
when the app is built, as it does for the stock file.  Nothing to change
there.

Then:

    cd Ortho4XP
    venv/bin/python -m pytest tests/test_dsftool_identity.py \
        tests/test_dsf_pool_select_first.py tests/test_dsftool_dump_census.py -q

`test_dsftool_identity.py` fails until the identity file matches the three
files — that is its job.

## 5. Frozen checks, all three platforms

`Ortho4XP.spec` ships the whole `Utils/` folder, so the freeze needs no
change.  Per platform, on the frozen artifact (`release.yml` runs the same
script in each release job):

    scripts/check_frozen_tile.sh <frozen-binary>

and confirm the frozen bundle carries the new file
(`shasum -a 256 <bundle>/Ortho4XP_Data/Utils/<platform>/DSFTool*` against
the identity file).  The frozen smoke builds a synthetic tile and solves
one airport; it does NOT run DSFTool on a pack with the trait, so the
platform proof of the tool itself is the workflow's smoke step.

## 6. Closing test

One airport on a tile that used to need the retry — KBFI, tile +47-123
(`+47-123.dsf` is one of the eight) — through the harness:

    venv/bin/python tools/harness/build_airport.py KBFI --tile 47 -123

The dump must be made WITHOUT the pool-select retry: no new DSFTool crash
report, and the `# file:` line of the report's `dsf_dump_path` names the
pack's own DSF, not a `dsf_pool_select_*` temp copy.  The retry
(`dsf_write._dump_pool_selected`, #582) stays in the engine as the
fallback, by ruling.

## Proving the vendored files on Windows and Linux

The Windows and Linux binaries cannot be run on this Mac.  After the
vendoring commit is on a branch GitHub has — and again whenever
`Utils/toolchains/smoke_test_dsftool.py` learns a new check —

    gh workflow run verify-dsftool.yml --ref <that branch>

It builds nothing and changes nothing: per platform it checks the
checked-out `Utils/<platform>/DSFTool[.exe]` against
`DSFTool.identity.json`, compares it byte for byte with the
`dsftool-binaries` artifact of the recorded `ci_run` (a warning, not a
failure, once that artifact has expired — 90 days), and runs the smoke
test on it (macOS: both slices).  Three green jobs are the platform
evidence for the files that ship.  A smoke test that grew does NOT by
itself call for a rebuild: the source and pins are unchanged, and a
rebuild would only ship different bytes (compile date, non-reproducible
build) that then need this same proof.

## What a new tool invalidates

Dump caches are keyed by the DSF's bytes (`<tile>.dsf.<sha256[:8]>.text`
under `Airport_mod_cache/<pack>/`; RULINGS 2026-09-11m), not by the tool.
After the swap, old and new dumps coexist.  Measured, that is safe and
NOTHING has to be deleted:

* The rows that differ between the tools (`# obj_pools found` comments
  on 66 of 7,069 files; the `HEIGHTS` base on 14-17) are read by no
  loader.  `HEIGHTS` is read only by the round-trip verify, which compares
  its quantum by encodable range (`dsf_write._heights_reconciled`) and
  never its base.  The quantum did not change on any arm64 dump; through
  the x86_64 slice one stock file's printed quantum changed (`+33-082`,
  1.00000 -> 0.03125 — the stock tool printing stray memory, #181) and is
  reconciled.
* The version row (`800 written by DSFTool 2.4.0-b1`) IS compared by the
  verify, and the patched build keeps it byte for byte — which is why the
  release string is pinned by `test_dsftool_identity.py`.
* A dump of one of the eight crashers made through the engine's retry
  differs from the new tool's only in those same two row classes.
* `partition_cache.dump_digest` hashes the dump's text: a file that is
  re-dumped with the new tool and falls in the 66 gets a new digest and
  its partition cache is derived once more.  That is a one-time cost, not
  an error.
* A 0-byte dump left by an old crash is already refused and regenerated
  (#60, #560).

The tool's identity was NOT added to the dump cache key: the key is one
function (`airport/dsf.text_dump_tag`), defined by ruling as the content
tag of the DSF, shared by the v1 reader, the loader, the `.anchor_bak`
companion lookup and the harness pre-flight.  It has no slot for a second
input; mixing one in would rename every cached dump on every machine.  If
a later tool changes rows the readers use, the place for it is a
tool-identity component in that one function plus a ledgered refresh of
`Airport_mod_cache` — a design decision, not a side effect of vendoring.

What does change for written packs: the new build's `--text2dsf` orders
polygons and road segments differently from the stock one (measured: 159
of 368 sampled stock files re-encode to different bytes of the same
length; `compare_dumps` is ok on all 159 — the verify already compares
those as multisets).  A pack DSF written by the new tool is therefore not
byte-identical to one written by the old tool from the same plan; any
recorded hash of a WRITTEN DSF is tool-dependent.

Not measured: the default-terrain dump cache (`Default_dsf_cache_dir`,
base-mesh DSFs).  Those are not overlays; the fix only changes which pool
is recorded before the first pool select.
