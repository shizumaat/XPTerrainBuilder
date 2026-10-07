# gaps3 continuation notes (lane stopped 2026-10-06 07:12 for a machine shutdown)

> CLOSED BY LANE gaps4 (2026-10-06 evening). CORRECTION: the HECA ARM replay
> DID finish — it is kept at `frames/gaps3/ARM/` (solved.pkl, patch, log).
> Item 2 (bars), item 3 (owner sites) and item 4 (§53 (18)) are done:
> `docs/briefs/gaps4-findings.md` and spec §53 (18). The scratch reader
> `frames/gaps3/site_read.py` is superseded by `tools/v2_late_read.py --site`
> (`tools/v2_late_site.py`); do not run the scratch copy. The six-airport
> no-op was run through `tools/harness/build_airport.py`, not the per-airport
> capture plan below.

Branch `feature/pavement-gaps`, pushed. Worktree used: the existing
`.claude/worktrees/gaps292` (the ritual `up gaps3` refused: branch already
checked out there; `lane_worktree.sh check gaps292` was clean).

## Item 1 — MERGE origin/main (e649c894): DONE, committed, pushed

Merge commit `d78f4175`, follow-up `5e7e5144`. Only three files conflicted
(build.py, planar/build.py, constraints, verify, emit auto-merged):

| file | resolution |
|---|---|
| `Ortho4XP/src/auto_patch_v2/planar/structures.py` | main's `cover_polygons` structure kept; the gap stage's standing-cells read re-seated beside it: `structure_approach.standing_cover(classification)` -> (standing cells, gap pieces, polygons) and `structure_approach.cut_gap_cells(gap_cells, knife, law, cut)` (the stand-off cut, LAST). `cover_polygons` now SKIPS a gap piece, so the pooled wall-corridor field (`wall_field`, handed to pool workers in `planar/build.py:219`) and the mapped-tunnel field read the standing cover only. File is back at exactly 1,000 lines (`test_planar.py::test_import_and_budget`). |
| `tools/INDEX.md` | main's `v2_solve_replay` row + the `--late-from` sentences appended; the `v2_late_read.py` row kept. |
| `docs/frames.jsonl` | both sides kept. |

Semantic repairs after the merge (not textual conflicts):
- `--late-from` entered main's arm table (`tools/replay_arms.py`: solving `--replay` only) and its twin `tests/test_v2_solve_replay_arms.py`.
- `law/emit.toml`: the gap follow head moved from FIRST to LAST in `[design] hard_rulings` (membership only; main's `test_surfacesettle` fixture reads `hard_rulings[0]`).
- New twin `test_gap_mint.py::test_a_gap_piece_is_never_cover_for_the_structures_or_the_wall_field`.

Pool-worker check: the only classification-derived record handed to the pool
is `wall_field` (now gap-free by construction, twin above). The mint
(`classify`), the load reader and the last stage are serial. NOT yet checked
by measurement: `--workers 1` vs default on the ARM replay (same body sha).

Suites on `5e7e5144`: non-Qt split 8,666 passed / 20 skipped / 1 xpassed;
Qt `-n0` 304 passed; console_encoding + windows_text_io + v1_retired +
no_airport_specific_code 190 passed; `tools/ratchets.py` DUPLICATE PASS,
LAYER PASS (size WARN on files the feature touches: `classify/roles.py`
+3, `tools/v2_solve_replay.py` +217 — both include main's growth).

## Item 2 — BARS: PARTIAL

- Fresh capture on `5e7e5144`: REGISTERED `/Users/noah/XPTerrainBuilderData/.harness/frames/gaps3/HECA.pkl`
  (131 s; 43,010 vertices / 1,999 faces; `Airport.gap_sheets` 23; 39 pieces /
  1,001,184 m2, 20 apron-touching / 831,854 m2; 68 gap faces — all equal to
  the held round-12/13 numbers).
- Sheet-free base capture: `frames/gaps3/HECA_nosheet.pkl` (the same pickle
  with `airport.gap_sheets = ()`; NOT registered) replayed
  `--from classify --emit BASE --solved-out BASE/solved.pkl`: 34,053 nodes,
  2,012 ways, **body sha 09847984ac94 = main's HECA (sw1045)** — the merged
  tree without the sheet is a NO-OP at HECA. Kept at `frames/gaps3/BASE/`
  (NOT registered).
- ARM replay (`--replay gaps3/HECA.pkl --from classify --late-from BASE/solved.pkl --emit ARM --verify --solved-out ARM/solved.pkl`)
  was RUNNING at shutdown — no result. Re-run it (~6-12 min), then
  `tools/v2_late_read.py BASE/solved.pkl ARM/solved.pkl --patches BASE/HECA_auto.patch.osm ARM/HECA_auto.patch.osm`
  and compare to the held values: existing movers 0, foreign vertices 0, way
  groups 1,152 / 1,152, follow rows missed 165 of 1,583 (pad 121, apron 22,
  other 22), stepping pairs 68 of 147 (52 on pieces >= 1,000 m2), ribbons
  grown > 0.1 m: 8 of 59 (held log: `frames/gaps2-hold/A2/late.log`).
- Held `gaps2-hold/BASE|A2|ARM`: NOT registered. BASE there has 34,053 nodes
  like the new base, but it was solved on a pre-pool tree — per §53 (17)
  lesson 5 treat it as STALE for a `--late-from`; compare numbers only.
- Six other airports (CYXY, SPJC, KCLT, KASE, NLWF, OTHH): NOT DONE. Plan:
  per airport `--capture` on this tree (prints nothing about sheets — read
  `cap["airport"].gap_sheets` and the `gap:` cells of `cap["cl"]`), then
  `--replay --from constraints --emit` and `build_airport.body_sha256` of the
  patch against sw1045 (CYXY 2a00c361ffc2, SPJC 9d611f11e04b, KCLT
  795da9629004, KASE 738c2a8ceb64, NLWF 84be89f8b7bc, OTHH 88794a1d264b).

## Item 3 — OWNER SITES: NOT DONE

Scratch reader ready, never run: `frames/gaps3/site_read.py BASE/solved.pkl ARM/solved.pkl CAPTURE.pkl --site NAME LAT LON [--to LAT LON]`
(face at the point, the piece, welded / stand-off neighbours with levels,
a 1 m section on base and arm against the cap). Run from `Ortho4XP/`.
Sites: (a) #430 lot 30.1154841, 31.4105884 `--to 30.115331 31.4106152`;
(b) #292 30.1159784, 31.4106264; (c) #358 30.1193169, 31.4085087.
Lead for (a) from the held log: `gap:8 (10,136 m2) | service_road:route3`
steps 3.91 m (piece 101.07 vs road 97.16, 1.41 m apart) at
30.1152588, 31.4106360 — i.e. the piece does NOT meet the road at the
road's level today. `--probe-site` is a stability probe off a solved pickle,
not a section reader, and `--late-from` cannot arm it.

## Item 4 — §53 round-13 subsection: NOT WRITTEN

The code already cites it as §53 (18). Content: gaps2's items 1-4
(why-vertex on a late solve; `tools/v2_late_read.py`; foreign vertices
16 -> 0; the 0.03 m node -> 0; ribbon residue = within-cap slopes + two span
cases), this merge (table above), the re-measured bars, the three sites.

## Item 5 — nothing designed or wired (as briefed).

Found, not fixed: `planar/structures.py` sits at exactly its 1,000-line
test budget on main, so any feature edit there must extract.
