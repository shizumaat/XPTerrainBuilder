# Brief pack — lane `xplatquantum`

Base: main `79f36611` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§46 the input quantum: one programme on every platform

## The brief

## Lane xplatquantum — spec §46: one airport, one programme on every platform (THE INPUT QUANTUM)

The spec section above (§46) is your law; RULINGS 2026-09-17d and 17g are its history.
Read §46 whole before anything else. What the session adds that is not law:

WHAT EXISTS ON MAIN FOR YOU (merged e84d4358, lane `xplatspread`, instrument only and
byte-neutral when unarmed): `auto_patch_v2/pipeline/xplat.py` (per-stage digests, the
exact-hex projection recorder, exact constraint rows, `compare_projection`);
`airport/load._vector_to_xy` carries the ONE hook (`_projection_recorder`, a
`sys.modules` lookup because `pipeline` imports this package — an import would be a
cycle); `pipeline/build.Config.xplat_quantise_m` + env `O4_V2_XPLAT_QUANTISE_M` read once
in `auto_patch/engine_v2.py` — that is the DUMP-ARM quantiser that proved the fix (LOAD
stage only); `scripts/check_frozen_tile.py --xplat-dump / --compare / --compare-projection
/ --xplat-quantise` and its non-gating PASS 2b; twins `tests/auto_patch_v2/test_xplat_spread.py`
(16) and `test_xplat_digest.py` (10). Artefacts of the two measuring runs are at
`/tmp/harness/xplatspread/{mac,linux,windows}/` (re-fetch: `gh run download 35285038635 -p
'frozen-tile-logs-*'`).

ORDER OF WORK
1. THE CENSUS TABLE FIRST (§46 (5)), committed as a MEASURED block appended under §46 in
   `Ortho4XP/docs/specs/auto-patch-v2/design-surface-spec.md` BEFORE any consumer edit:
   every caller of `Frame.transformers()` / `to_xy` / `_vector_to_xy`, file:line, the
   domain of what it projects, and its ruling (INPUT-DOMAIN → entry projection /
   OWN-GEOMETRY → exact / INVERSE-ONLY). Be exhaustive; a missed consumer of a
   cross-cutting change is how the bridge-deck exemption cost eight build rounds.
2. THE LAW PARAMETER: `emit.identity.input_quantum_m = 0.001` in `law/emit.toml`, typed in
   `law/model.py` (`Identity`), exposed in `law/tables.py`; `tests/auto_patch_v2/test_law_tables.py`
   pins the file's literal text (~:525-527) — extend it. The toml change moves
   `law_tables_digest`: intended (§46 (8)).
3. THE ENTRY PROJECTION on `model/frame.Frame` — one site; `to_xy` stays exact. Rewrite
   the frame module's header comment (it currently says the projection is NOT quantised
   and why): it must describe the law as it now stands. Retire the dump-arm quantiser
   (`xplat_quantise_m` / `O4_V2_XPLAT_QUANTISE_M`) or make it an explicit OVERRIDE of the
   law value for measurement arms — one quantiser in the tree, never two.
4. SWITCH the input-domain consumers in the census's order, twins as you go. Known
   re-founding: none of the 52 `identity_dp=11` test files should need touching (the
   identity does not move) — if one goes red, that is a FINDING about an own-geometry
   round trip; report it before "fixing" the test.
5. §46 (6) (i) the Windows contact flip and (ii) the mac `lp.nnz` +2: attribute each
   INTERVENTIONALLY on the runners (you cannot reproduce Windows locally), then fix (i)
   as a total order with a deterministic tie-break; no law threshold moves.
6. THE GATE (§46 (7)): once green, a fourth job in `.github/workflows/release.yml` that
   needs the three platform jobs, downloads the three `frozen-tile-logs-*` artifacts and
   fails on the first divergent stage. You OWN release.yml this round for that job only;
   do not disturb signing, tag/version steps, the AppImage steps or the frozen checks.

BARS: §46 (7), on the three runners with the quantum SHIPPED (no `--xplat-quantise`).
PRICE MEASUREMENT: §46 (8) — ONE harness HECA build and ONE CYXY through
`tools/harness/build_airport.py`, verify family table + ADJUDICATED census
(`tools/harness/census.py`) before (main) vs after (your branch), every family moving by
> 1 % named, `[harness] shared repo UNCHANGED` quoted. NOTE RULINGS 17g residual (3): the
shared corpus lacks `Airport_mod_cache/CYXY Whitehorse/+60-136.dsf.ba2a1655.text`, so an
object-stage CYXY build may REFUSE until the owner runs `--refresh-data airport_mod_cache`
— if it does, report the named scope and use HECA alone; never refresh the corpus yourself.
Standing suite once, FAILED lines verbatim.

EXCEPTION to no-push: push ONLY `claude/xplatquantum`; dispatch Release ON THAT BRANCH
ONLY, at most 5 rounds (~8 min each; prove everything you can locally first — the mac
source tree runs the frozen check's JSONL entry, as `xplatspread` did); download this
repo's own `frozen-tile-logs-*` artifacts into your scratchpad. Never main, never a tag,
never a PR.

OTHER LANES IN FLIGHT — not your files: `src/O4_Airport_Elevation_Insets.py`,
`src/auto_patch_v2/airport/dem_production.py`, `tools/harness/build_airport.py` (lane
insetbounds); `src/O4_Mesh_Utils.py`, `src/O4_Default_Terrain_Map.py`, the DSF terrain
writer (lane shorewater).

Rules: worktree from Ortho4XP/ `tools/harness/lane_worktree.sh up xplatquantum`; merge main
first. The bash guard refuses engine build/test commands whose effective cwd is not an
Ortho4XP/ with venv and OSM_data (run them from your worktree's Ortho4XP/ in their own
call), pattern-matches test-runner words inside heredocs (write files with the Write
tool) and refuses `git stash`. Release Xcode only; never quit the owner's app; never run
make_app/make_engine; commit early, one commit per step; do not merge; no RULINGS entry
(the session records it). Report: branch + sha, the census table, the run links with the
bars of §46 (7) each stated met/not met with numbers, the attribution of (6)(i) and (ii),
the HECA/CYXY before/after, and everything not done.

## Spec (design-surface) §46

## §46 ONE AIRPORT, ONE PROGRAMME ON EVERY PLATFORM — THE INPUT QUANTUM (owner 2026-09-17, Q 17d-1: "let's implement option A now … can we simply standardize everything to the nearest 1 mm?"; Fable 2026-09-17; founded on lanes `xplatdeterminism`, `xplatspread` and the identity census) — lane `xplatquantum`

**(1) THE DEFECT (17d, measured).** One apt.dat, identical library versions, three
platforms, three different programmes: CYXY solved 17128×1933 (mac arm64) /
17151×1922 (Linux) / 17039×1934 (Windows). The first divergent stage is `load`; the
only thing between the identical input and the difference is PROJ's compiled forward
transverse Mercator.

**(2) WHAT THE SPREAD REALLY IS (lane `xplatspread`, release runs 35283889554 and
35285038635, exact `float.hex()` joins over 2,847 load-stage coordinates).**
Nanometres — max **2.11e-9 m**, p50 3.6e-10 m, almost entirely in northing, easting at
the ulp; it does NOT grow with distance from the origin (289-point lattice to ±13.9 km).
17d's bracket "(5e-7, 5e-5) m" was an over-reading of a digest ladder: agreement at a
coarse rung does not bound a spread, and disagreement at a fine rung does not establish
one. Linux and Windows are NOT identical either (84 of 2,847 differ by ~1.4e-9 m).
STRADDLES — coordinates that round differently on two platforms — are **ZERO at every
grid tried (1e-4, 1e-3, 1e-2, 0.5 m), on every pair.** So the session's hypothesis that
the pipeline's existing snaps (`min_distinct_spacing_m` = 0.5 m, classify `snap_grid_m`
= 0.01 m) are where the nanometre becomes a decision is REFUTED: the decision is minted
DOWNSTREAM, in derived geometry computed from inputs that differ in their last digits.

**(3) THE INTERVENTION THAT WORKED.** With the LOAD stage's projected inputs quantised
to 1 mm (dump arm only), the projection came out bit-identical on all three and then:
load, partition, classify, planar (every DEM sample), shapes — every digest agrees at
every rung; constraints — identical counts by type and 73,528 exact row values agreeing
to ≤ 7.96e-13 m; LP **17289×1918, 181 rounds, identical everywhere**; the emitted patch
BODY **byte-identical on all three** (header path and line endings apart); emitted z at
today's 1 cm: zero cross-platform differences. Bit-identical inputs give bit-identical
derived geometry: GEOS, numpy and scipy are deterministic across these platforms once
they are fed the same doubles.

**(4) THE LAW — INPUTS ENTER THE FRAME ON A GRID; NOTHING ELSE CHANGES.**
 (a) Every coordinate that ENTERS an airport's metric frame from outside — apt.dat,
     OSM, DSF/OBJ8 placements and feet, any lat/lon we did not compute ourselves — is
     quantised ONCE, at entry, to `emit.identity.input_quantum_m` = **0.001 m**
     (law, `law/emit.toml [identity]`; typed in `law/model.py`, exposed in
     `law/tables.py`). ONE derivation site: `model/frame.Frame` gains the entry
     projection (name it for what it is, e.g. `enter(lon, lat) -> XY`); `to_xy`
     stays the EXACT projection for our own geometry.
 (b) THE IDENTITY DOES NOT MOVE. 17d-1's option (A) — identity in the metre domain —
     was proposed because quantising `to_xy` AT THE FRAME broke
     `to_xy(to_ll(xy)) == xy` against the 11-dp lat/lon key (arm 8615f4f9: the
     pad-ceiling twin and the 1e-9° round-trip twin red). Quantising at ENTRY only
     leaves every round trip of our own geometry exact, so that conflict never arises:
     `coordinate_dp` = 11 stays the canonical key AND the emit format, `Vertex.key`
     keeps its shape, captures and dumps keep their schema, the sidecar ↔ patch ↔
     census joins are untouched, the 52 test files that build a `Frame` with
     `identity_dp=11` stand. Option (A) is NOT taken because it is no longer needed;
     it remains available if a later measurement finds an own-geometry round trip that
     decides something.
 (c) WHY 1 mm. apt.dat carries 8 decimals (≈ 1.1 mm): 1 mm respects the source's own
     resolution and moves no input by more than 0.5 mm, against a planar lattice of
     0.5 m. Expected straddles per build = N × spread / q: at q = 1 mm, 0.001 at CYXY,
     0.011 at a hub of 10× CYXY's coordinates, 0.055 at a deliberately pessimistic 50×;
     1 cm is ten times rarer again and 0.1 mm would put roughly one hub build in two at
     risk. A straddle, when it happens, is one input 1 mm apart on one platform — a rare
     one-off difference, never a systematic one; the instrument (5) names it.
 (d) The shore weld is untouched: `weld_to_shore` copies a FOREIGN OSM coordinate,
     which is input data and identical on every platform, and §39's exact snap stands.
     Nothing is snapped at EMIT. (The census's two objections to a 1 cm grid — the
     mesher's `HAIRLINE_DEGENERATE_M` and shore welds landing g/2 off the water — apply
     to an emit-side grid, which this law does not create.)

**(5) CONSUMER CENSUS — BEFORE ANY EDIT (RULINGS 2026-08-30l).** The lane tables every
caller of `Frame.transformers()` / `to_xy` / `_vector_to_xy` (the measurement lane
counted ~12 beyond load: `planar/build._vector_to_ll`, `planar/overlay._degree_offset`,
`constraints/foot_rows`, `constraints/pad_relief`, `classify/evidence`,
`pipeline/publication`, `airport/pack_partition`, `constraints/cluster_pad`, …) and
rules each ONE of: INPUT-DOMAIN (switch to the entry projection), OWN-GEOMETRY (leave
exact), or INVERSE-ONLY (no change). A site that takes a lat/lon WE produced and
projects it back (the census names `pad_relief.py:118` and `foot_rows.py:276` as
fixture-only exposures; production feet are input-domain from DSF/OBJ8 — VERIFY) is
listed with its ruling. The `load` hook `xplatspread` left in `_vector_to_xy` is the
first consumer.

**(6) THREE RESIDUES THE QUANTUM DOES NOT CLOSE, SAME LANE.**
 (i)  THE WINDOWS CONTACT FLIP: 22 of 616 `road_ramp` rows (`roads.groundside_road
      airside contact`, §37 (10), owner 2026-09-13cs item 5) anchor on a different
      airside vertex on Windows — (−281.0, 151.0) m against (−300.5, 120.5) m on
      mac and Linux, 36 m apart, so not a near-tie in distance: a SELECTION resolving
      differently (an unstable sort or an argmin over equal scores, a set/dict order).
      Attribute it interventionally, then make the selection a total order with a
      deterministic tie-break on the canonical key. No law threshold moves.
 (ii) `lp.nnz` 16874 (mac) vs 16872 — attribute (a structural zero kept or dropped on
      a sign of ±0.0?); fix only if it is a decision, else record it.
 (iii) LINE ENDINGS — ALREADY CLOSED on main by lane `xplatcrlf` (RULINGS
      2026-09-17g, fd1702ff): `newline="\n"` + an explicit encoding at 29 writers,
      AST twin `test_newline_pinned.py`, Windows patch `\r` = 0 on run 35284573827.
      This lane only VERIFIES it under the bars of (7) — it changes nothing there.

**(7) BARS.** On the three runners, through the frozen release check's CYXY pass with
the quantum SHIPPED (no dump-arm quantisation): every stage digest AGREES at every rung
on every pair; LP rows × cols and rounds identical; the 616 `road_ramp` rows identical;
the emitted patch body BYTE-IDENTICAL on all three (the `<osm>` header line excluded —
it carries the runner's temp path); `.graded.json` byte-identical; emitted z
cross-platform differences 0. Make `check_frozen_tile.py --compare` a GATE in
`release.yml` once it is green (three artefacts from three jobs: a fourth job that
downloads the three `frozen-tile-logs-*` and fails on the first divergent stage).

**(8) THE PRICE, STATED.** `emit.toml` changes, so `law_tables_digest` changes, so
EVERY airport's patch invalidates and rebuilds once, by itself. Inputs move by
≤ 0.5 mm against a 0.5 m lattice, so the expectation is surfaces indistinguishable to a
pilot and census counts within a few rows — MEASURED, not assumed: one harness HECA
build and one CYXY, verify family table and ADJUDICATED census before/after, every
family that moves by > 1 % named. Registered captures and coordinate-literal pins
(`repro_cut`) predate the quantum: a capture replays under the CURRENT tree and says
so; a pin that no longer matches refuses BY NAME (R5), which is the right failure.

## RULINGS

## 2026-09-17d xplatdeterminism MERGED (1a1aa12f; lane suite 1904 passed, 2 skipped, 1 xpassed, 0 FAILED): THE THREE PLATFORMS SOLVE DIFFERENT PROGRAMMES BECAUSE PROJ'S FORWARD TMERC DIFFERS IN THE LAST ULP — attributed interventionally; the fix is an OWNER question

**Finding (betafrozenpatch, run 35262948212):** the frozen check's CYXY solve is `optimal` everywhere but LP 17128×1933 (mac arm64) / 17151×1922 (Linux) / 17039×1934 (Windows). **Refuted first, no CI:** two runs of one mac bundle byte-identical (not ordering); frozen py3.13 == source venv py3.14 on one Mac (not packaging/Python); CI-mac == local-mac through `lp`. Every wheel bundles the SAME libraries (PROJ 9.5.1, GEOS 3.13.1, shapely 2.1.2, pyproj 3.7.2, numpy 2.4.4, scipy 1.17.1) — aligning versions buys nothing.

**First divergent stage = `load`** (run 35272775466): counts identical, geometry digests equal at dp4 (0.1 mm), apart at dp6 (1 µm); Linux == Windows, arm64 apart. Only `to_xy` stands between an identical apt.dat and that. `classify` turns the micron into a decision (cells 105/104/105, runway 6/5/6); planar V 4289/4283/4287; constraint rows 73176/73421/73001.

**Interventional (run 35274144555, arm `8615f4f9`, REVERTED `e885d4d0`):** quantising `to_xy` to 0.1 mm at its one site made load, classify, planar (every DEM sample), shapes and every constraint COUNT byte-identical on all three — LP 17096×1926, 275 rounds everywhere. Residue: row values < 1e-4 m, `lp.nnz` 16881/16879/16879, solved z past dp4–dp6, and Windows writes the patch with CRLF (851,654 vs 829,181 B for one programme — UNATTRIBUTED, follow-up).

**Why the arm is not the fix:** quantised metres break `to_xy(to_ll(xy)) == xy` while the identity join is lat/lon at `emit.identity.coordinate_dp = 11` ≈ 1 µm — `test_v2padceiling::test_a_groundside_face_is_not_senior_here` red at 1 mm AND 0.1 mm; the frame's 1e-9° round-trip twin red at 1 mm; CYXY planar V moved 4289 → 4256 / 4283 on one tree. **OWNER Q 17d-1:** close it by (A) moving the canonical identity into the metre domain (quantised xy carries the node id), (B) coarsening `coordinate_dp` (a law parameter), or (C) accept per-platform surfaces for the beta and ask testers to name their OS in every report. Measured for the decision: PROJ ll→xy→ll residual 2.8e-9 m; platform spread in (5e-7, 5e-5) m; snap grid 0.5 m, weld 1.0 m.

**Merged (instrument only, byte-neutral: CYXY 17128×1933, 835,585 B, 268 rounds, every digest equal at 9 dp):** `auto_patch_v2/pipeline/xplat.py` (per-stage counts + order-free sha256 at 9/6/4/2/1 dp + bundled library versions; armed by `Config.xplat_dump`, `O4_V2_XPLAT_DIGEST` translated once in `auto_patch/engine_v2.py`); `check_frozen_tile.py --xplat-dump DIR` / `--compare NAME=PATH …` (exit 2, names the first divergent stage, runs under a bare python3); `release.yml` uploads `frozen-tile-logs-*` on `always()`; `airport/load._vector_to_xy` now DELEGATES to the frame (it was a second spelling of the projection); twin `test_xplat_digest.py` (10); INDEX row. CI spent ~46 min over two dispatches.

## 2026-09-17g xplatcrlf MERGED (fd1702ff; merged tree: campaign suite + freshness 1893 passed, 2 skipped, 1 xpassed, 0 FAILED; Release run 35284573827 green on all three platforms): THE WINDOWS PATCH WAS CRLF AND NOTHING ELSE — the emit path pins `newline` at the call

**Attributed** from run 35274144555's `frozen-tile-logs-*` (the 17d interventional arm, one solve programme everywhere), per file: the Windows CYXY patch carried 22,375 `\r\n` and ZERO lone `\r` — exactly the 22,375 `\n` of the POSIX patch. CRLF-normalised it is 829,279 B against mac 829,277 / linux 829,181, inside the 96 B mac↔linux spread 17d attributes to PROJ's forward tmerc last ulp (so the raw +22,473 B vs linux = 22,375 newline + 98 tmerc residue). Same shape for `CYXY.report.json` (173,667 lines) and `CYXY.xplat.json` (237). Cause: the platform default of an unqualified `open(path, "w")` / `Path.write_text(text)`.

**Merged:** `newline="\n"` + an explicit encoding at 29 writers — every module under `auto_patch_v2/` plus the seven non-v2 modules that write a v2 build's output set (`engine_v2`, `driver`, `layout`, `constant_dem`, `solve_capture`, `object_rebake`, `object_terrain_assembly`). Two deliberate encodings: `placement_write`'s OBJ8 text stays latin-1; `dsf_write`'s DSFTool intermediate pins utf-8/`surrogateescape` on BOTH sides so an untouched line round-trips byte-exactly whatever the locale (the read was already universal-newline; LF is what `edit_dump` always saw) — this path is NOT exercised by the frozen tile check (local twins only, 162 green). `scripts/check_frozen_tile.py`'s JSONL capture pinned too (its log invented 275 CRLF the wire never carried); `engine-stderr.log` stays binary — its `\r` are the engine's real Windows stderr. Session addition (0f1876be): the driver's verify-log part read is `errors="replace"` (a `UnicodeDecodeError` is not the `OSError` that block catches). Twin `tests/auto_patch_v2/test_newline_pinned.py`: AST scan, EMPTY allowlist keyed by line text, a self-instrument test; RED pre-fix naming these 29 sites.

**Byte-neutral on POSIX** (single tree f1313f75, harness CYXY, shared repo UNCHANGED): patch `6994aa0e2eff`, `CYXY.graded.json` `82266ad3493d`, `CYXY.rebake.json` `d5d1ec07c20c` identical before/after; the `.axes.json` sidecar matches once its per-run wall-clock fields are masked (it embeds `wall_s` timings and is never byte-stable run to run — shown with a pre-fix-vs-pre-fix pair).

**Verified:** run 35284573827 (`--ref claude/xplatcrlf`, one dispatch, on a5d24ed5): Windows patch 834,939 B / report 3,224,395 / xplat 5,079, `\r` = 0 in all three. `--compare` still names `load` as the first divergent stage (LP 17128×1933 / 17151×1922 / 17039×1934) — **Q 17d-1 UNCHANGED**; cross-platform byte equality was never this lane's bar.

**Reader census:** no consumer flaps. Freshness stamps, the scenery signature (names/mtimes/sizes), the run-ledger and artifact-ledger keys, `planar_sha256` (in-memory) and `--compare` (parsed values) are newline-insensitive; the tile-side patch reader is universal-newline. ONE-SHOT Windows invalidations on upgrade: the pack `.obj` sha in the rebake provenance, the `.obj`/DSF stat entries in the v2 partition fingerprint, the DSF `written_sha256` + dump tag. The harness `body_sha256` retains CR, so Windows and POSIX bodies only become comparable from this merge.

**Residuals:** (1) ~40 unpinned text writers on the Ortho4XP tile side (`src/O4_*.py`, v1 forensics) — readers uncensused (2026-08-30l), chip filed, NOT in this merge; (2) `route_profile/taut_string.py:1463` pins `newline=""` with no `encoding=` (locale-dependent on Windows, not a CR defect); (3) the shared corpus lacks `Airport_mod_cache/CYXY Whitehorse/+60-136.dsf.ba2a1655.text` — an object-stage CYXY build will refuse until the owner runs `--refresh-data airport_mod_cache`.

## Tool: check_frozen_tile

| `scripts/check_frozen_tile.py` | You are proving a FROZEN release bundle can build a tile and SOLVE an airport through the shipped JSONL protocol (`--pass tile|airport|both`), or you are chasing a CROSS-PLATFORM divergence in that solve. `--xplat-dump DIR` arms the engine's own per-stage digest writer (`auto_patch_v2/pipeline/xplat.py`, `O4_V2_XPLAT_DIGEST`) and copies `CYXY.xplat.json` + the report + the patch out of the throwaway fixture before it is deleted; the release job uploads that directory on SUCCESS from all three platforms. `--compare NAME=PATH …` then prints the per-stage AGREE/DIFFER table (load, partition, classify, planar, shapes, constraints, lp, solved) with the numbers and names the FIRST divergent stage, exit 2. Every digest is a sorted-line sha256 taken at 9/6/4/2/1 dp, so a last-ulp difference (fine rounding only) is distinguishable from a topology change (every rounding), and no enumeration order can move it. The driver needs NOTHING but the standard library — it never derives a number, the bundle under test does. Twin: `Ortho4XP/tests/auto_patch_v2/test_xplat_digest.py`. Measured basis (lane `xplatdeterminism`, 2026-09-17): two runs of one macOS bundle agree at 9 dp at EVERY stage, and the CI macOS bundle (py3.13, frozen, GitHub runner) agrees with a local macOS SOURCE run (py3.14, venv, another machine) at every stage through `lp` — so the divergence is the ARCHITECTURE, not ordering, packaging or the Python version. Run 35272775466 named the first divergent stage `load`: identical counts, geometry equal at 4 dp and apart at 6 dp, Linux == Windows there and macOS apart, on identical PROJ 9.5.1 / GEOS 3.13.1 / numpy 2.4.4 — PROJ's compiled forward tmerc, last ulp; `classify` then came out 105 / 104 / 105 cells and the three solved 17128x1933 / 17151x1922 / 17039x1934. Run 35274144555 is the INTERVENTIONAL arm (projection quantised to 0.1 mm, commit `8615f4f9`): load, classify, planar (DEM included), shapes and every constraint count identical on all three, LP exactly 17096 x 1926 / 275 rounds everywhere. **The EXACT spread (lane `xplatspread`):** `--xplat-dump` also writes `CYXY.xproj.json` — every load-stage `to_xy` as `float.hex()` IN and OUT (join key = the input pair, identical everywhere by construction, so the join is exact and never proximity), a deterministic lattice probe forward and inverse out to ~14 km (hub scale), and the solved z keyed by its vertex's xy. `--compare-projection NAME=PATH …` prints, per platform pair and per axis, max / p99 / median `|Δ|` in metres, the decade histogram, the growth with distance from the frame origin, and the STRADDLE counts at 1e-4 / 1e-3 / 1e-2 m and at **0.5 m** — the two coarser ones being the grids the pipeline ALREADY snaps to (`classify` `[cells] snap_grid_m` = 0.01 m, `classify/rules.toml:8`; the planar arrangement's `grid_size` = `emit.identity.min_distinct_spacing_m` = 0.5 m, `planar/overlay.py:360-362, 441, 476`), per axis, per coordinate and for z, with the straddling coordinates NAMED in lat/lon so they can be cross-referenced with the stage dumps' first divergence, and the expected count projected to 10x / 50x CYXY's N — the numbers owner Q 17d-1's grid choice rests on. `--xplat-quantise M` (default 1e-3, 0 disables) runs a SECOND, NON-GATING solve with the load stage's projection snapped, i.e. every platform fed identical inputs, into `<dump>/quantised`. Byte-neutral when off and when merely armed: CYXY 17128 x 1933, 268 rounds, 835,585 B on all three of OFF / armed / pre-lane. Twin: `Ortho4XP/tests/auto_patch_v2/test_xplat_spread.py`. MEASURED (runs 35283889554 and 35285038635, CYXY, N = 2,847 load coordinates): the real spread of `to_xy` is **~4e-10 m mean, 2.1e-9 m max** — NANOMETRES, three to five decades finer than 17d's "(5e-7, 5e-5) m" bracket, which over-read a dp6 digest (a digest differs when ANY of 2,847 values straddles the 1e-6 rounding, expected ~2). It is almost all NORTHING (x mean 1.5e-14, y 3.8e-10) and does NOT grow with distance from the origin out to 14 km. STRADDLES at 1e-4 / 1e-3 / 1e-2 / 0.5 m: **0 of 2,847 on every platform pair** — so the existing 1 cm classify and 0.5 m planar grids are NOT where the divergence is minted. Linux and Windows are NOT equal (84 of 2,847 coordinates apart by ~1.4e-9 m); the inverse `to_ll` differs on 18 of 289 probe points by ≤1.9e-9 m. With the load projection snapped to 1 mm, every stage through `shapes` agrees on all three, LP is 17289 x 1918 / 181 rounds everywhere, matched constraint rows agree to ≤8e-13 m, and the emitted patch BODY is BYTE-IDENTICAL on all three (header excluded, CRLF normalised). |

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`; `--why-from PKL --probe-site LAT,LON [--probe-drop M] [--probe-arm TERM=V ...]`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (**and THE CLUSTERS beside the partition and the groups** — lane ``v2padjoin`` 2026-09-14: a capture without ``Airport.clusters`` leaves §30 (4)'s cluster pad, its apron reach and §16g (10)'s derived pads INERT in every replay of it, so a pads-ON arm silently measures the pads-OFF law; a capture predating them has them DERIVED at replay off its own partition, named on stdout) (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate).  **`--probe-site LAT,LON` IS THE STABILITY PROBE** (lane `v2qp`, spec §20c, promoted from lane `v2settle` r2's `scratchpad/v2settle/probe3.py`/`probe4.py` on its second use): off a `--solved-out` pickle, one extra `Band` ceiling `--probe-drop` (default 0.30) metres under the ARM's OWN base surface at the vertex nearest the point, re-solved, and the moved set (> 0.02 m) binned by distance from it — 0-40 / 40-100 / 100-250 / 250-500 / beyond, with the worst beyond 250 m, each arm's hard set and its exit line.  `--probe-arm TERM=V` repeated makes it a MATCHED PAIR of `[design]` arms on ONE problem (`--probe-arm solver=fixed_point --probe-arm solver=qp` is §20c's own bar); with none it probes the shipped law alone.  This is the instrument RULINGS 2026-09-14bw's headline was taken on (HECA: 959 vertices moved by one 0.30 m row, 953 beyond 500 m, ZERO within 100 m).  `--design-weight TERM=V` also takes a NON-NUMERIC value now (§20c's `solver=qp`); a value that does not parse as a float is passed through as the string.    **`--placement KEY=V` IS THE CAPTURE-TIME LAW ARM** (lane `v2padqp`, spec §16g (10) (11)): the §16g (10) pad keys (`pad_from_cluster`, `pad_airside_clip`) are read in `classify/evidence._pads` and `planar/overlay` — UPSTREAM of the capture — so `--design-weight` (a `[design]` override applied at REPLAY) cannot arm them and a pads-ON replay of a pads-OFF capture silently measures the pads-OFF law; a matched OFF/ON pair is therefore TWO CAPTURES of one tree, never two edits of the shipped toml (the value is coerced to the key's own type, an unknown key refuses by name, and the arm is recorded in the pickle).  `--capture` also arms `harness/build_airport.arm_shared_repo_protection` — the ONE arming composition — and prints `[guard] shared repo UNCHANGED`.  **`--rule SECTION.KEY=V` IS THE CAPTURE-TIME CLASSIFY ARM** (lane `v2shoulderband`, spec §40 (5)): the same thing for `classify/rules.toml` that `--placement` is for `[placement]` — a CLASSIFY key is read upstream of the capture (the capture HOLDS the classification, so `--from planar` cannot see a classify change at all), which makes a matched pair on one TWO CAPTURES; doing that by editing the shipped toml between the arms is the defect RULINGS 2026-09-15az records (disarming a head by prefix also deleted `foot_row_rulings` and silently re-priced every foot row), so the arm is ONE COMMAND-LINE VARIABLE on one unedited tree instead. `SECTION.KEY=VALUE`, coerced to the key's own type, an unknown section or key refuses BY NAME, and the arm is printed on stdout — e.g. `--rule corridor.runway_shoulder_band=false`.  **`--reclassify PKL` IS THE DRY §40 BAND READ** (lane `v2shoulderband` r2, promoted on its SECOND use per RULINGS `7e90032` — r1 hand-rolled it in a scratchpad for the HECA control and r2 needed it at five airports): a CLASSIFY key cannot be armed at replay, but the capture also carries the `Airport` the classifier ran on, so the CLASSIFY STAGE ALONE is re-run over it on the CURRENT tree with `--rule` as the only variable — seconds against a capture's minutes (LEMD 74-79 s). It prints §40 (5)'s own table: the `runway_shoulder` population (cells, m², each named with its host runway and its worst lateral offset), the runway BODY beside it, what the remainder earned BY ROLE, the worst lateral offset of a shoulder vertex off its own runway's apt.dat axis and how many stand beyond the band (§40 (5) (1)'s own bar, "→ 0"), and the classifier's own `shoulder_band_*` stats; `--json` dumps it with the arm recorded, so no reading is frame-less. It is a DRY read and says so — no planar build, no solve, no emit — so it PRICES NO LAW AND COUNTS NO DEFECTS (defect counts come from `harness/census.py` and nowhere else) and it cannot answer anything downstream of classify: a `runway_step` row or a census family needs a built patch. The axis and the half width are the derivation's own (`classify/roles.shoulder_band`), imported and never re-spelled. Control: re-read on the registered `LEMD capture base e856ce64` it reproduces r1's ON arm EXACTLY (271,086 m² / 19 cells / remainder 273,949 m² in 28 faces). Twin: `tests/auto_patch_v2/test_runway_shoulder.py` (the table IS the classifier's verdict on both arms, band + remainder PARTITION the cell, the arm is recorded).  **A CAPTURE CARRIES THE ARRANGEMENT'S RE-NODE READING** (lane `v2padclip`, spec §16g (10) (12) (2)): `pipeline/publication` publishes the sidecar's `pad_airside_renode` out of a module global `planar/overlay.PAD_AIRSIDE` that only a BUILD fills, so every replay arm published an EMPTY list and read a perfect family — the silent-degradation class. `--capture` now pickles that dict and `--replay` restores it and prints `pad/airside re-node from the capture: deleted N minted M`; a capture written before 2026-09-16 carries none and the sidecar key is then OMITTED, which every reader reads as NOT MEASURED rather than zero.   Twin: `tests/auto_patch_v2/test_v2qp.py` (the probe as a fixture pair) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. **`--stage1-dump OUT.json.gz` / `--stage1-diff A B [--movers AVD.json]` IS THE §20b (3) STAGE-1 POPULATION READER** (lane `v2stagepop`, spec §20b (3) (4), RULINGS 2026-09-16v): off a `--solved-out` pickle (`--why-from`) or off a CAPTURE (`--replay`, the generators re-run under the current tree), it runs `solve/design.stage_split` + `solve/design.assemble` — the assembly the stage actually solves, never a re-derivation — and writes every ROW (least-squares, per-body datum and one-sided, each keyed by its owner/ruling, its terms and its right-hand side), every COLUMN (the reduction's own merged vertex set), every SHEET FACE with its area and every TRIANGLE, all keyed by the canonical 11-dp lat/lon so two arms diff BY IDENTITY (memory `canonical-identity-join`); it REFUSES if its own sheet re-read does not reproduce `DesignReport.triangles`. `--stage1-diff` prints the decomposition §20b (3) (4) asks for — counts, then rows REMOVED / ADDED / **RETARGETED** (the same row over the same vertices at a different right-hand side: a target the groundside moved, never a row of the pad law), the columns, the sheet faces by role and m², the triangles — and with `--movers` (an `airside_value_delta --json`) attributes each moved airside vertex to the class of stage-1 change it stands on, with the far field's distance profile to the nearest change. It SOLVES NOTHING, prices no law and counts no defects (defect counts come from `harness/census.py`). Measured basis (HECA, the v2padclip r2 staged arms, every pad generator dropped): columns 18,495 → 18,499, one-sided rows 1,317,645 → 1,322,265 (`apron` frontage-chord / preferred-tier 4,712 removed / 9,178 added), `apron_trend` 1,107 RETARGETED, sheet faces 892 vs 890 → 859 = 859 once the stage's own roles decide the sheet. |

## Registered frames: CYXY

CYXY  patch    base 8dac3c6b   lane v1settings       2026-09-13T12:56:32  /tmp/harness/v1settings_base.osm  [MISSING]  — base arm: CYXY --engine v2 at main 8dac3c6b, body_sha fc59980475f5 (v1-retirement stage A control)
CYXY  patch    base 9ae9e5a9   lane v1settings       2026-09-13T12:56:32  /tmp/harness/v1settings_lane.osm  [MISSING]  — lane arm: CYXY, no --engine flag, body_sha fc59980475f5 — byte-identical to the base arm
CYXY  patch    base dc5517c0   lane solvemodel       2026-09-13T15:55:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/base_CYXY/CYXY_20260913T155123.osm  [MISSING]  — BASE arm, solve_model retirement closing test; body_sha ca2c7bbaa57e, 314 ways / 4690 nodes / 344 verify rows
CYXY  patch    base dc5517c0   lane solvemodel       2026-09-13T15:55:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/lane_CYXY/CYXY_20260913T155153.osm  [MISSING]  — LANE arm (claude/solvemodel fdd291e9); body_sha ca2c7bbaa57e — byte-identical to the base arm, patch cmp-clean
CYXY  patch    base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /tmp/harness/CYXY_20260913T173248.osm  [MISSING]  — CYXY control on claude/v2zonebank cde84e27 (rc 0, 16.4 s, body_sha b38fbb12b262) — census law-true 1,087, bank_across_seam 0, stacked_nodes 0 (the RULINGS 10g plateau-tearing class clean)
CYXY  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:36  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/cyxy/v2sl_cyxy2.osm  [MISSING]  — CYXY control, lane arm (claude/v2slivers 88dfed33): rc 0, 13.6 s, ways 268, body_sha 018092d831df. NOT byte-identical to the base arm and lawfully so: CYXY carries 12 zone slivers / 339 m2 and 4 hairline hole rings at base, all dissolved/suppressed. Base arm v2sl_cyxy_base (main fef82b29): 284 ways, body_sha 673393ea5af0, 121 graded_strip faces / 12 slivers, 13 rings / 4 hairline
CYXY  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/CYXY.osm/cyxylane.osm  [MISSING]  — CYXY control, LANE arm (claude/v2cost2 12b29e6c): rc 0, 12.9 s, body_sha 018092d831df — cmp-IDENTICAL to the base arm at main 4c6f467c in scratchpad/v2cost2/base/CYXY.osm/cyxybase.osm (13.2 s, same sha)
CYXY  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/CYXY_r2.osm/cyxyr2.osm  [MISSING]  — CYXY control, round 2 lane arm (claude/v2cost2 7bc09ea7): rc 0, 14.2 s, body_sha 018092d831df, cmp-IDENTICAL to the base arm scratchpad/v2cost2/base/CYXY.osm/cyxybase.osm
CYXY  capture  base 12400580   lane v2settle         2026-09-14T23:01:33  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/CYXY.pkl  [MISSING]  — v2_solve_replay --capture CYXY on main 12400580 (8 s, 4,503 vertices / 261 faces); guard shared repo UNCHANGED. The cheap control: single solve 17/32,327 hard rows violated, active-set exits line_search_stalled x1 (never the set's own fixed point). Lane v2settle r2's byte-identity arm.
CYXY  graded   base 63258868   lane v2qp             2026-09-15T00:29:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2qp/emit_cyxy_qp/CYXY.graded.json  [MISSING]  — QP ARM of the v2qp matched CYXY replay pair off cap/CYXY.pkl (base 12400580): solve 3.2 -> 4.2 s (1.31x), status feasible -> optimal, hard rows over 0.02 m 17 -> 12, runway projection worst hard row 0.0044 -> 0.0002 m, lag worst leader move 0.319 -> 0.162 m. BASE ARM at emit_cyxy_fp/. Census A/B ADJUDICATED 427 -> 379 (-11.2 %), NO family worse. The FISTA cross-check and the HiGHS refutation were measured on this capture (scratchpad/v2qp/*.log)
CYXY  patch    base f32fb08c   lane v2channel        2026-09-15T10:23:52  /tmp/v2channel/r3/br_CYXY/structures.json  [MISSING]  — v2channel round-3 DRY structure replay (branch), paired with base CYXY at main 46b219d8 in /tmp/v2channel/r3/base_CYXY
CYXY  patch    base 395bd09a   lane v2channel        2026-09-15T10:52:05  /tmp/v2channel/r4/br_CYXY/structures.json  [MISSING]  — v2channel round-4 DRY structure replay (branch, §45 (13)); base arm at main in /tmp/v2channel/r4/base_CYXY
CYXY  capture  base 3e15a18d   lane v2shoulderband   2026-09-16T09:10:47  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/r2/cap/CYXY.pkl  [MISSING]  — CYXY capture carrying §40 (5), taken AFTER merging the peer's v2usgsbox (main bc7f16a2) which un-refused CYXY's two version-stale USGS3DEP negatives (4 s, 4,474 vertices / 257 faces, guard UNCHANGED). One §40 (1) shoulder, 14,399 m2 on 14L/32R reaching 172.3 m -> band 12,778 m2 (88.7 %) + 1,621 m2 stub. The end cap changes NOTHING here
CYXY  patch    base 3e15a18d   lane v2shoulderband   2026-09-16T09:10:47  /tmp/harness/v2sb_CYXY2.osm  [MISSING]  — closing CYXY build of v2shoulderband r2 (post-v2usgsbox merge): rc 0, 15.5 s, ways 276, nodes 4423, body_sha 98fb821518ab, artifact ledger c23bbd629ce5, optimal, v2-verify 339 rows, every §40 DEFECT family ZERO, shared repo UNCHANGED. Census law-true 1,102 adjudicated 375
CYXY  patch    base f1313f75   lane xplatcrlf        2026-09-17T15:58:33  /tmp/harness/crlffix.osm  — LANE arm, newline pinning (claude/xplatcrlf a5d24ed5): CYXY rc 0, 12.4 s, ways 268, nodes 4335, body_sha e1b9e0e9cc19 - byte-IDENTICAL to the pre-fix base arm /tmp/harness/crlfbase.osm at f1313f75 (same body_sha, same file sha256 6994aa0e2eff); CYXY.graded.json and CYXY.rebake.json also sha256-identical. Proves the CRLF pinning is a no-op on POSIX. Shared repo UNCHANGED both arms.
CYXY  patch    base 2fb0799f   lane xplatspread      2026-09-17T16:12:39  /tmp/harness/xplatspread  — NOT a harness build: the CROSS-PLATFORM PROJECTION frames, Release run 35285038635 (r2) on branch claude/xplatspread, all three runners GREEN (r1 = 35283889554). Re-fetch: gh run download 35285038635 -p 'frozen-tile-logs-*'. Each of mac/linux/windows carries CYXY.xproj.json (exact float.hex of every load-stage to_xy, N=2847; a 289-point lattice probe forward+inverse to 14 km; solved z per vertex), CYXY.xplat.json (stage digests), the emitted patch, and quantised/ = the same with the load projection snapped to 1 mm plus 73,528 exact constraint rows. Read with scripts/check_frozen_tile.py --compare-projection / --compare. MEASURED: to_xy spread 4e-10 m mean / 2.1e-9 m max (17d's (5e-7,5e-5) bracket over-read a dp6 digest), ZERO straddles at 1e-4/1e-3/1e-2/0.5 m, Linux != Windows (84 of 2847); in the 1 mm arm LP 17289x1918 / 181 rounds on all three and the emitted patch BODY byte-identical (header excluded, CRLF normalised).

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

