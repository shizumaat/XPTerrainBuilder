# Lane dsftool568 — notes (issue #568)

Branch `claude/dsftool568`, on top of `claude/dump560` @ 1b884a84e.

## RESUME HERE

State 2026-10-12: steps 1 (extent), 2 (root cause), 3 (fix (b) + twins)
DONE and committed. Step 4 (KBFI closing build through the harness): see
"4. Closing test" at the bottom — if that section is empty the build has
not been run yet. Option (a) (a fixed binary) is DESCRIBED below, not
done: it needs the master's/owner's go.

Scratch (lane-local, not in the corpus):
`/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/466e18b3-e03c-471f-b042-c64d8df4e04d/scratchpad/dsftool568/`
— `global.jsonl` (census rows), `emul.pkl`, `proof.py`, `crashers/<tile>/`
(fixed dump, no-overlay dump, round-trip DSF + dump per crasher),
`xptools_src/` (the upstream sources read).

## 1. Extent (measured)

`tools/dsftool_dump_census.py` over the owner's stock install,
`X-Plane 12/Global Scenery/Global Airports/Earth nav data`, bundled
`Utils/mac/DSFTool` 2.4.0-b1 (sha256[:16] 4abaed055ff77b09):

**8 of 7,077 DSFs crash (SIGSEGV), 7,069 dump.**

    +18-067  +47+007  +47+019  +47-123  +50+004  +50+008  +51+006  +52-002

(San Juan, Bern/Zurich area, Budapest, Seattle, Brussels, Frankfurt,
Dusseldorf/Cologne, Birmingham — dense tiles, 418 to 881 object defs.)

What the 8 share and the 7,069 lack — exact, both directions: they are
the overlay DSFs whose **command stream sets a 16-bit definition index
(`SetDefinition16`, cmd 4 — a definition index above 255) BEFORE its
first `PoolSelect`**. Predictor `dsf_commands.select_pool_first(bytes) is
not None` over all 7,077: predicted 8, crashed 8, the same 8.
Not the trait: having > 255 object defs, or using `SetDefinition16` at
all — 278 other stock files use it and dump (their first object uses a
definition <= 255, so a pool is already selected at the first 16-bit one).
The +47-123 stream opens `02 00000000 | 20 06 … | 04 2401 | 01 1300 | …`:
junction offset, comment, **SetDefinition16 292, then PoolSelect 19**.

Custom packs (owner's `Custom Scenery`, packs with <= 40 DSFs: 1,542
packs, 2,188 DSFs; 2,057 read, 23 compressed, 106 over 30 MB skipped):
**2 carry the trait and both crash**: `KDAL Dallas Love Field
(iBlueYonder)` `+32-097.dsf`, and `c_BRA - 100_airport - SBGL …`
`-23-044.dsf`. Both dump through the fix (80,827 / 58,518 lines).

## 2. Root cause (upstream source, read on GitHub)

Bundled binaries: `Ortho4XP/Utils/{mac,lin,win}/DSFTool[.exe]`, vendored
with the Ortho4XP engine (commit 38b3eaf54), "DSFTool 2.4.0-b1 … Compiled
on May 9 2024 … X-Plane Scenery Tools release: 24-5" = xptools
`c31ed76b5` (2024-05-08). PyInstaller ships the whole folder
(`Ortho4XP.spec:144` `('./Utils', './Ortho4XP_Data/Utils')`).

`src/DSF/DSFLib.cpp` @ c31ed76b5, in `DSFReadMem`, the HEIGHTS guess:

    671  bool is_overlay = true;                       // NAME IS INVERTED:
    677  if (strcmp(str,"sim/overlay")==0 && atoi(str2)==1)
    679      is_overlay = false;                       // false FOR an overlay
    691  auto ptPools = GetAllPools(cmdsAtom, is_overlay);
    698  for (auto p : ptPools) {
    700      double scal = planeScales[p][is_overlay ? 2 : 3];   // <- crash
    701      double pmin = planeOffsets[p][is_overlay ? 2 : 3];

and `GetAllPools` (line 275):

    277  unsigned short pool, currentPool = 0xFFFF;
    291  case dsf_Cmd_ObjectRange:
    292      if (!overlay) ptPools.insert(currentPool);
    303  case dsf_Cmd_SetDefinition16:                 // falls through
    304  case dsf_Cmd_Object:
    305      cmdsAtom.Advance(2);
    306      if (!overlay) ptPools.insert(currentPool);

For a `sim/overlay 1` file the "current pool" is recorded at every
SetDefinition16. Before the first PoolSelect it is the sentinel 0xFFFF,
so line 700 reads `planeScales[65535][3]`: element 65,535 of a
`vector<vector<double>>` holding ~200 — memory far past the table, whose
"data pointer" is null, plus `3 * 8` = **address 0x18**, the fault in the
crash reports. Removing `sim/overlay 1` flips the flag, the census reads
terrain patches instead (none), and nothing is indexed — why dump560's
experiment dumped.

Upstream fixed it: `9c1a06c7b` 2026-03-08 "Fix dsf2text crash for object
def indices over 255" (+ `a3725c8f5` 2026-04-14): SetDefinition16 no
longer records, and `currentPool != 0xFFFF` guards the inserts. **No tool
release carries it**: master's `src/XPTools/version.h` still says
`XPT_PACKAGE_VER "24-5"`, `DSFTOOL_VER 20400 "-b1"`; the only GitHub
release is WED 2.7.1. So "a newer released DSFTool" does not exist — a
fixed binary means BUILDING one.

Side finding, same lines, NOT fixed upstream: for the usual 3-plane
object pools (AGL objects) `planeScales[p][3]` is one past the end of a
3-element vector, so the `HEIGHTS` row of nearly every overlay dump is
derived from stray memory (+47-123: `HEIGHTS 0.03125 -123.0` — the
longitude offset). 7,021 of the 7,077 stock files are in that class. It
is stable run to run and the engine already compares `HEIGHTS` by keyword
only / reconciles it (`dsf_write._heights_reconciled`).

## 3. Fix (b): select a pool first, on a temp copy, on a crash

- NEW `auto_patch_v2/airport/dsf_commands.py` — `atoms()` (moved from
  `dsf_write._atoms`, one implementation) and `select_pool_first(bytes)`:
  for an uncompressed `sim/overlay 1` DSF whose stream reads the
  unselected pool, the same DSF with ONE `PoolSelect` command put in
  front (3 bytes; CMDS atom length and trailing MD5 fixed). The pool
  selected is the first SELECTED pool the tool's census records anyway,
  so the census is the bundled tool's own minus the sentinel. `None`
  for any file without the trait.
- `dsf_write.dump()` — on a DSFTool CRASH (signal death only), retries
  once on that copy in a system temp dir (`_dump_pool_selected`); no
  trait -> the crash stands as before. `DsfToolError.crashed` added.
  The pack DSF is never written. Non-crashing files take the path they
  took before, byte for byte.
- Not gated on a tile, ICAO, sha or tool version: the witness is in the
  file's command stream.

Why this and not "drop `sim/overlay 1`" (dump560's experiment): that
changes the text (the property row is gone and would have to be put
back for the WRITE half; `HEIGHTS` becomes `0.5 0.0`). Selecting a pool
first changes NO row.

Proof it loses nothing (`scratch/proof.py`, real DSFTool, real files):

- A. The same insertion FORCED on 958 non-crashing stock DSFs (all 278
  that use SetDefinition16 + every 10th of the rest): **957 dumps
  byte-identical** to the plain dump apart from the `# file:` comment
  (which `partition_cache.dump_digest` already strips); 1 file has no
  object pool to select (not applicable). Every def, property, object,
  polygon, facade, network row, their order and indices, DIVISIONS and
  HEIGHTS: identical.
- B. The 8 crashers through `dsf_write.dump`: all dump (31,500 to 134,590
  lines). Against the no-overlay dump of the same file the ONLY differing
  rows are: `# file:`, the `# … pools found` comment, `HEIGHTS`, and
  `PROPERTY sim/overlay 1` (present in ours).
- C. Write half: each fixed dump -> `dsf_write.encode` (text2dsf) ->
  `dsf_write.dump` -> `compare_dumps`: **ok on all 8, 0 unmatched**
  (5,005 / 3,820 / 4,404 / 13,168 / 9,310 / 18,845 / 5,276 / 10,006
  placements); `PROPERTY sim/overlay 1` is in the re-encoded file.
  NOTE: the re-encoded DSF has the trait again on all 8 (DSFTool's
  writer emits definition-then-pool), so the round-trip verify of a
  WRITTEN pack on such a tile would have crashed too — the same `dump()`
  retry covers it.

What the readers lose: nothing measured. What stays open: a COMPRESSED
(7z) DSF with the trait is not repaired (the crash stands, in plain
words); none found in the stock install, 23 compressed files in the
custom sample were not classified.

Tests: `tests/test_dsf_pool_select_first.py` (15: the repair, 9 "left
alone" cases, the dump retry with a fake subprocess),
`tests/test_dsftool_dump_census.py` (1). Covering files run once: 507
passed + console-encoding 193 passed after the tool's console pin.
`tools/ratchets.py`: duplicate ratchet PASS, layer ratchet PASS; size
WARN `dsf_write.py` 1370 -> 1510 (dump560's +115 and this lane's +25).

New tool: `Ortho4XP/tools/dsftool_dump_census.py` (INDEX row added) —
also the instrument for judging a replacement binary (`--tool`).

## Option (a): a fixed DSFTool in the bundle — for the master

- There is nothing to download: no released DSFTool has the fix. It
  must be BUILT from `github.com/X-Plane/xptools` at master >=
  `a3725c8f5` (or `c31ed76b5` + the two commits cherry-picked, which
  keeps every other behaviour of 2.4.0-b1), target `DSFTool`, three
  times: macOS universal (arm64 + x86_64), Windows x64, Linux x86_64
  (glibc floor today: built "for GNU/Linux 3.2.0"). Source is MIT-style
  (Laminar Research header). Upstream's `Building.md` / `cmake.sh` /
  `conanfile.py` describe the build; a CI workflow modelled on
  `.github/workflows/build-osmium.yml` (+ `Utils/toolchains/`) is the
  repo's precedent for a vendored tool.
- Pick-up is automatic: replace `Ortho4XP/Utils/{mac,lin,win}/DSFTool`
  in git; `Ortho4XP.spec:144` ships the folder, `scripts/sign_app.sh`
  signs the mac helper. Nothing else names a version.
- Before it lands: `tools/dsftool_dump_census.py --tool NEW --keep-text`
  over Global Airports and diff against the bundled tool's dumps — the
  fix changes the pool census, so `HEIGHTS` rows WILL differ on files
  that use SetDefinition16 (286 stock files); content-keyed dump caches
  are keyed by DSF sha, not tool, so old and new dumps would mix unless
  the cache key or a refresh says otherwise.
- With (b) landed, (a) is no longer needed to read these files; it would
  remove one crash + one crash report per first dump of such a file.

## 4. Closing test

`venv/bin/python tools/harness/build_airport.py KBFI --tile 47 -123`,
branch sha ae2b4a3b9, 2026-10-12 09:53-10:17 (1,492 s; run-ledger key
`40938be1…`, recorded exit 1).

**KBFI built.** Report `tmp/auto_patch_v2/+47-123/KBFI/KBFI.report.json`:
pack `Global Airports`, `dsf_dump_path` = the lane-local
`tmp/engine_caches/Airport_mod_cache/Global Airports/+47-123.dsf.2f51dffe.text`
(3,653,663 bytes — the harness redirects the cache, so the dump was
re-derived there through the crash retry), `dsf_dump_stale` false, 1,065
objects resolved, 0 unresolved, warnings `[]`; patch 527 ways / 5,489
nodes. **All nine airports of the tile emitted a patch**: KBFI KGRF KPAE
KPLU KPWT KTCM (the six refused before) + KRNT KSEA KTIW. Mesh step DONE
(224 s).

**The harness REFUSED to report the build (rc 1) — for the DEM, not for
the dump**: the shared-repo guard blocked 6 `os.remove` of
`Elevation_data/+40-130/N47W123_airport_insets/{KGRF,KTCM}_usgs3dep.tif.refetch*`
(scope dem) and the engine carried on. So no census number from this
build is quoted. STOPPED here; a `--refresh-data dem` run is the master's
ledgered act.

**Left in the shared corpus by this build (NOT cleaned — master's
call):** 74 files, 166 MB, all `*.refetch*` beside the KGRF (10) and KTCM
(64) insets, written 09:53-09:56 by the inset re-fetch before the guard
blocked their removal. The insets themselves (`KGRF_usgs3dep.tif`,
`KTCM_usgs3dep.tif`, KBFI's) are untouched. The harness's contamination
report also lists 19 + 3 paths under `N45W123_*` written 10:11-10:15:
another tile, not this build's (another process was writing the corpus).
The 0-byte `Airport_mod_cache/Global Airports/+47-123.dsf.2f51dffe.text`
of 2026-10-11 is still in the shared corpus (dump560's note stands); the
app's next build of the tile replaces it through `dump()`.
