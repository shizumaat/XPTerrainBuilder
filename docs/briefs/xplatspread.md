# Brief pack — lane `xplatspread`

Base: main `5f68c961` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Round 4 lane xplatspread

## The brief

## Lane xplatspread — MEASURE the raw cross-platform projection spread, and what each grid size would buy (input to OWNER option A, RULINGS 2026-09-17d Q 17d-1)

OWNER 2026-09-17: "Let's implement option A now" (the canonical vertex identity moves
into the METRE domain: a snapped xy IS the node id), and asks: "can we simply standardize
everything to the nearest 1 mm? Even 1 cm seems like it would be plenty accurate … If
nothing can be finer than that, would that help?" The spec (session, Fable) needs ONE
measurement nobody has: 17d only BRACKETS the platform spread of `Frame.to_xy` as
"(5e-7, 5e-5) m" — inferred from digests agreeing at 4 dp and differing at 6 dp, not
measured. The grid size must be chosen against the real distribution, because a
coordinate within the spread of a snap boundary rounds differently on two platforms
(a STRADDLE), and expected straddles per airport = N_coords x spread / grid.

READ FIRST: RULINGS 2026-09-17d (Ortho4XP/docs/RULINGS.md ~:9000 — `tools/docq.py
ruling` returned empty for 17a earlier today; read the file if it does again) and the
header of `Ortho4XP/src/auto_patch_v2/model/frame.py` (:24-58). The instrument you
extend is merged: `auto_patch_v2/pipeline/xplat.py` (per-stage counts + order-free
sha256 at 9/6/4/2/1 dp, armed by `Config.xplat_dump` / `O4_V2_XPLAT_DIGEST`),
`scripts/check_frozen_tile.py --xplat-dump DIR` / `--compare NAME=PATH …`, and
release.yml already uploads `frozen-tile-logs-*` on `always()`. The arm that quantised
`to_xy` is commit 8615f4f9 on branch `claude/xplatdeterminism` (REVERTED e885d4d0) —
read it, do not re-land it.

MEASURE (this lane changes NO behaviour; everything it adds is dump-only, armed by the
existing switch, byte-neutral when off — prove neutrality: CYXY LP 17128x1933, patch
835,585 B, 268 rounds on the mac freeze, unchanged):
1. RAW PROJECTION: for every vertex the LOAD stage projects, dump the INPUT
   (lat, lon) exactly as parsed and the OUTPUT (x, y) as `float.hex()` — exact, no
   rounding — keyed by the input pair (identical on every platform, so the join is
   exact). Same for `to_ll` on the vertices the emit stage inverts (input xy hex,
   output lat/lon hex) if that is one site; if it is many, say so and do the forward
   direction only.
2. Offline comparer (extend `--compare`, stdlib only — it must run under a bare
   python3): per platform pair, per axis: max, p99, median |Δ| in metres; the histogram
   by decade (1e-13 … 1e-4 m); and for grid ∈ {1e-4, 1e-3, 1e-2} m the number of
   coordinates whose `round(v / grid)` DIFFERS between platforms (the straddles) out of
   N. Also report |Δ| against distance from the frame origin (does the spread grow with
   |x|,|y|? — a large hub is ~10x CYXY's extent).
3. DERIVED GEOMETRY: with the input projection made identical by construction (in the
   DUMP path only: feed every platform the SAME xy — e.g. quantise in the dump arm at
   1e-3 m exactly as 8615f4f9 did at 1e-4, behind the dump switch, never in the shipped
   path), do planar overlay / shapes / constraint VALUES still differ across platforms,
   and at what magnitude? 17d's residue says: row values < 1e-4 m, `lp.nnz`
   16881/16879/16879, solved z past dp4–dp6, and Windows writes the patch with CRLF
   (851,654 vs 829,181 B — UNATTRIBUTED). Attribute each: which stage first differs in
   VALUE (not count) once inputs are identical, by how much, and is it numpy/scipy/GEOS
   arithmetic or ordering? Find where the CRLF comes from (text-mode `open` without
   `newline=""` in the patch writer?) and name the one site — do not fix it here.
4. EMIT PRECISION TODAY: at what precision are node lat/lon and elevations written into
   `*_auto.patch.osm` and the `.axes.json` sidecar (cite the writer)? If every emitted z
   were rounded to 1 mm, how many emitted values would differ across platforms on CYXY
   (straddles again)? This sizes the owner's "nothing finer than 1 mm" idea for the
   VERTICAL axis.
All on the CYXY fixture through the frozen check on the three runners (that is the only
airport CI can build). Scale to a hub by N: report N_coords for CYXY and quote HECA's
order of magnitude from its report if a registered frame has it (`tools/harness/frames.py
list HECA`), never a build.

FILES YOU OWN: `scripts/check_frozen_tile.py`, `scripts/check_frozen_tile.sh`,
`Ortho4XP/src/auto_patch_v2/pipeline/xplat.py`, and the minimal dump hooks at the stage
boundaries xplat already instruments. Do NOT edit `model/frame.py`'s behaviour, the
law TOML, release.yml (lane betaappimagert has its linux job), the insets module or
`tools/harness/` (lane insetbounds).

EXCEPTION to no-push: push ONLY `claude/xplatspread`; dispatch Release ON THAT BRANCH
ONLY, at most 3 rounds (~10 min each; 17d spent 46 min over two — be deliberate: get
the dump right locally on the mac freeze first; you cannot re-freeze, so local proof
runs the SOURCE tree via the engine's JSONL entry if the frozen binary predates your
hooks — say which you did). Download the three `frozen-tile-logs-*` artifacts with
`gh run download` into your scratchpad (the session authorises downloading THIS repo's
own workflow artifacts for this lane) and run the comparer on them.

Deliver a short report the spec can quote: the spread distribution per platform pair,
the straddle table for the three grid sizes, whether derived geometry is identical once
inputs are, the residue attribution, the emit precisions, the CRLF site. Twins for the
comparer's arithmetic (straddle counting on synthetic hex pairs). Rules: not a law lane;
no harness airport build; worktree from Ortho4XP/ `tools/harness/lane_worktree.sh up
xplatspread`; merge main first; the bash guard refuses engine test commands whose
effective cwd is not an Ortho4XP/ with venv and OSM_data, pattern-matches test-runner
words inside heredocs (use the Write tool) and refuses `git stash`; release Xcode only;
never quit the owner's app; never run make_app/make_engine; commit early; do not merge;
no RULINGS entry. Report branch + sha, the run links, the numbers, and everything not done.

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

