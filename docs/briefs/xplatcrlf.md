# Brief pack — lane `xplatcrlf`

Base: main `2fb0799f` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Windows writes emit-path text with CRLF: pin newline at every writer

## The brief

## Finding (lane xplatdeterminism, RULINGS 2026-09-17d, Release run 35274144555)

With the solve programme identical on all three platforms (interventional arm, commit 8615f4f9),
the Windows frozen bundle's CYXY patch was 851,654 B vs 829,181 B on mac/Linux (+22,473 B).
Hypothesis: Windows text-mode writes translate `\n` to `\r\n`. UNATTRIBUTED — confirm before fixing.

## Session pre-grep (not exhaustive; the lane's AST scan is the census)

`Path.write_text(...)` with no `newline=` (py3.10+ accepts `newline="\n"`):
- `Ortho4XP/src/auto_patch_v2/emit/osm_adapter.py:983` patch `.osm`, `:992` sidecar `.axes.json`, `:994` graded surface
- `auto_patch_v2/pipeline/build.py:1009` rebake plan, `:1123` `{icao}.report.json`
- `auto_patch_v2/planar/__main__.py:153,273,274,289,642`

`open(path, "w")` with no `newline=`:
- `auto_patch_v2/pipeline/why.py:314`, `pipeline/xplat.py:368`, `planar/index.py:119`
- `auto_patch_v2/airport/dsf_write.py:747,780`, `airport/placement_write.py:220` (latin-1 — KEEP its encoding), `:326`

Also sweep: `to_osm` and any v1 writer still on the v2 emit path, `Path.open("w")`, `io.open`,
`tempfile.NamedTemporaryFile(mode="w")`, `csv` writers (csv wants `newline=""` — rule per site), `json.dump(fh)`.

## Work

1. ATTRIBUTE: `gh run download 35274144555 -n frozen-tile-logs-windows` (+ the mac/linux artifacts) into the
   lane scratch dir (never into the repo or the shared data repo). Show: windows_bytes − posix_bytes == count of
   `\n` in the posix patch, and the `\r\n` count in the Windows patch == its line count. Same for every sidecar in
   the artifact. If the difference is NOT exactly the line count, STOP and report — there is a second cause.
2. FIX at the write sites: `newline="\n"` and explicit `encoding="utf-8"` (preserve a site's deliberate
   non-utf-8 encoding, e.g. placement_write latin-1 for X-Plane text; for DSFTool text input check what DSFTool
   accepts on Windows before pinning, and say which you chose and why). If one write helper already exists,
   extend it — no fork.
3. TWIN: an AST scan under `Ortho4XP/tests/auto_patch_v2/` asserting no emit-path module calls `open` in a
   text write/append mode, `Path.write_text`, or `Path.open` text-write without a pinned `newline=` keyword.
   Scope = every module under `auto_patch_v2/` plus any non-v2 module the emit path writes through; an
   allowlist entry needs a one-line reason. The twin must FAIL on the pre-fix tree (show it).
4. READER/HASH census (one table in the report): patch body hash, freshness stamps, partition-cache keys,
   scenery signature, run-ledger hashes, `check_frozen_tile.py --compare` digests, and the Swift/Qt readers —
   for each: does it hash/compare raw bytes of a file whose bytes change on Windows only? On mac/Linux the bytes
   must be UNCHANGED by this lane (prove: CYXY patch + sidecar sha256 before/after identical on this machine).
   Name any Windows-side cache that will invalidate once on upgrade.
5. VERIFY: ONE branch dispatch `gh workflow run Release --ref <lane-branch>` (NEVER main, NEVER a tag — a tag
   auto-publishes). Pushing the lane branch to origin for this dispatch is authorised by the owner's brief.
   Download the three `frozen-tile-logs-*` artifacts; run `scripts/check_frozen_tile.py --compare` and give a
   byte-size / `\r`-count table for patch + sidecars on all three. The solve itself still diverges per platform
   (owner Q 17d-1 open), so patch BYTES will not be equal across platforms on main's programme — the bar is
   zero `\r` bytes on Windows, not equal sizes.

## Bars

- Attribution: byte delta == line count, shown from the run 35274144555 artifacts, per file.
- Zero `\r` bytes in every Windows emit-path text output on the lane's Release branch dispatch.
- mac local: CYXY patch + sidecar sha256 identical before/after the fix (harness build only: `tools/harness/build_airport.py CYXY`).
- Twin red on the pre-fix tree, green after; campaign suite `venv/bin/python -m pytest tests/auto_patch_v2 tests/test_harness.py` from Ortho4XP/ with every FAILED line quoted (never `tail -1`).
- `Ortho4XP/venv/bin/python tools/blast.py <file>` run before each edited file; hazards quoted in the report.
- No RULINGS append, no merge to main — the spawner owns both. Report a draft ruling text.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/emit/osm_adapter.py`, `Ortho4XP/src/auto_patch_v2/pipeline/build.py`

## RULINGS

## 2026-09-17d xplatdeterminism MERGED (1a1aa12f; lane suite 1904 passed, 2 skipped, 1 xpassed, 0 FAILED): THE THREE PLATFORMS SOLVE DIFFERENT PROGRAMMES BECAUSE PROJ'S FORWARD TMERC DIFFERS IN THE LAST ULP — attributed interventionally; the fix is an OWNER question

**Finding (betafrozenpatch, run 35262948212):** the frozen check's CYXY solve is `optimal` everywhere but LP 17128×1933 (mac arm64) / 17151×1922 (Linux) / 17039×1934 (Windows). **Refuted first, no CI:** two runs of one mac bundle byte-identical (not ordering); frozen py3.13 == source venv py3.14 on one Mac (not packaging/Python); CI-mac == local-mac through `lp`. Every wheel bundles the SAME libraries (PROJ 9.5.1, GEOS 3.13.1, shapely 2.1.2, pyproj 3.7.2, numpy 2.4.4, scipy 1.17.1) — aligning versions buys nothing.

**First divergent stage = `load`** (run 35272775466): counts identical, geometry digests equal at dp4 (0.1 mm), apart at dp6 (1 µm); Linux == Windows, arm64 apart. Only `to_xy` stands between an identical apt.dat and that. `classify` turns the micron into a decision (cells 105/104/105, runway 6/5/6); planar V 4289/4283/4287; constraint rows 73176/73421/73001.

**Interventional (run 35274144555, arm `8615f4f9`, REVERTED `e885d4d0`):** quantising `to_xy` to 0.1 mm at its one site made load, classify, planar (every DEM sample), shapes and every constraint COUNT byte-identical on all three — LP 17096×1926, 275 rounds everywhere. Residue: row values < 1e-4 m, `lp.nnz` 16881/16879/16879, solved z past dp4–dp6, and Windows writes the patch with CRLF (851,654 vs 829,181 B for one programme — UNATTRIBUTED, follow-up).

**Why the arm is not the fix:** quantised metres break `to_xy(to_ll(xy)) == xy` while the identity join is lat/lon at `emit.identity.coordinate_dp = 11` ≈ 1 µm — `test_v2padceiling::test_a_groundside_face_is_not_senior_here` red at 1 mm AND 0.1 mm; the frame's 1e-9° round-trip twin red at 1 mm; CYXY planar V moved 4289 → 4256 / 4283 on one tree. **OWNER Q 17d-1:** close it by (A) moving the canonical identity into the metre domain (quantised xy carries the node id), (B) coarsening `coordinate_dp` (a law parameter), or (C) accept per-platform surfaces for the beta and ask testers to name their OS in every report. Measured for the decision: PROJ ll→xy→ll residual 2.8e-9 m; platform spread in (5e-7, 5e-5) m; snap grid 0.5 m, weld 1.0 m.

**Merged (instrument only, byte-neutral: CYXY 17128×1933, 835,585 B, 268 rounds, every digest equal at 9 dp):** `auto_patch_v2/pipeline/xplat.py` (per-stage counts + order-free sha256 at 9/6/4/2/1 dp + bundled library versions; armed by `Config.xplat_dump`, `O4_V2_XPLAT_DIGEST` translated once in `auto_patch/engine_v2.py`); `check_frozen_tile.py --xplat-dump DIR` / `--compare NAME=PATH …` (exit 2, names the first divergent stage, runs under a bare python3); `release.yml` uploads `frozen-tile-logs-*` on `always()`; `airport/load._vector_to_xy` now DELEGATES to the frame (it was a second spelling of the projection); twin `test_xplat_digest.py` (10); INDEX row. CI spent ~46 min over two dispatches.

## Tool: check_frozen_tile

| `scripts/check_frozen_tile.py` | You are proving a FROZEN release bundle can build a tile and SOLVE an airport through the shipped JSONL protocol (`--pass tile|airport|both`), or you are chasing a CROSS-PLATFORM divergence in that solve. `--xplat-dump DIR` arms the engine's own per-stage digest writer (`auto_patch_v2/pipeline/xplat.py`, `O4_V2_XPLAT_DIGEST`) and copies `CYXY.xplat.json` + the report + the patch out of the throwaway fixture before it is deleted; the release job uploads that directory on SUCCESS from all three platforms. `--compare NAME=PATH …` then prints the per-stage AGREE/DIFFER table (load, partition, classify, planar, shapes, constraints, lp, solved) with the numbers and names the FIRST divergent stage, exit 2. Every digest is a sorted-line sha256 taken at 9/6/4/2/1 dp, so a last-ulp difference (fine rounding only) is distinguishable from a topology change (every rounding), and no enumeration order can move it. The driver needs NOTHING but the standard library — it never derives a number, the bundle under test does. Twin: `Ortho4XP/tests/auto_patch_v2/test_xplat_digest.py`. Measured basis (lane `xplatdeterminism`, 2026-09-17): two runs of one macOS bundle agree at 9 dp at EVERY stage, and the CI macOS bundle (py3.13, frozen, GitHub runner) agrees with a local macOS SOURCE run (py3.14, venv, another machine) at every stage through `lp` — so the divergence is the ARCHITECTURE, not ordering, packaging or the Python version. Run 35272775466 named the first divergent stage `load`: identical counts, geometry equal at 4 dp and apart at 6 dp, Linux == Windows there and macOS apart, on identical PROJ 9.5.1 / GEOS 3.13.1 / numpy 2.4.4 — PROJ's compiled forward tmerc, last ulp; `classify` then came out 105 / 104 / 105 cells and the three solved 17128x1933 / 17151x1922 / 17039x1934. Run 35274144555 is the INTERVENTIONAL arm (projection quantised to 0.1 mm, commit `8615f4f9`): load, classify, planar (DEM included), shapes and every constraint count identical on all three, LP exactly 17096 x 1926 / 275 rounds everywhere. |

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

