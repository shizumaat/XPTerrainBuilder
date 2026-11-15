# #2091 round 2 spec (Fable review of l2091 d93857c33, 2026-11-15)

Lines on origin/claude/l2091 (d93857c33), under Ortho4XP/src/auto_patch_v2/. Keep round 1: pit refusal (airport/walled_pit.py:285,317, law/structures.toml:225), pages-dump fix, FABDEM fix, end-line read (airport/bridge_witness.py:588-700).

## Findings
Item 1 (s1 25.256748,51.613318 drawn 2.06 → 0.04): `building7/p1` is a PASSAGE LEVEL SEED, not a split-level storey. planar/level_regions.py:173 `_unit_seed` takes a unit's walled parts (≥ 2.5 m, not supports) whose foot plane is ≥ `low_level_min_step_m` (3.0) under the unit's zero; with a mapped road through them, `seed_levels` (:230, cut :301) makes the pad under them one flat level at the walls' depth. Arm log: "unit 28 depth 3.93 (59 walled parts, 14733 m2, passage 3432 m2, soffit 0.267)"; "building7/p1 of unit 28 on building7: y -3.93 11980 m2"; level_runout_ends 8 ends, 8 climbs, 0 falls. In the control, OTHH_TerminalRoads_03_002/004/005 were pit members and skipped from the partition; with the pit refused they rejoin the terminal unit as walled parts. They are ramps with buried skirts (03_002 near-horizontal faces y −2.0..+8.0; 03_004 7,517 m² vertical faces with feet at y −2.0). Not new: 11-13 frame lothhdeck2 already had building7/p1 at 0.04 m (2,925 m² 13.4 m from s1, + 4,006 m² at 25.2588,51.6172).
Witness: no road reaches the level — exit read planar/cut_runout.py:234-247 (DEM at each lip vs level): OTHH 8/8 exits climb 3.92–5.56 m. KMCI (300.24) run-outs +0.08..+2.23; KIAH (22.85) no run-out (its building99 p1–p3 partly its seed level) — the KIAH replay is the real check. Clearance at zero does not separate it. With the level refused, pad building7 (477,482 m², 3.96) holds s1 flat at grade.

Item 3 (corner a 25.251530838,51.617033415 +0.62; corner b 25.251625620,51.617088015 +0.21): the apron is centred on the ROAD, not on the end line. `StackEnd.half_width` = half the end line (model/deck_stack.py:109), and four consumers buffer the route path by it: geom/deck_ground.py:160,162 (apron and bank), constraints/deck_stack.py:284 (R6 corridor), airport/deck_ends.py:83, airport/deck_stack.py:631. Route meets this end ~3 m from corner b → apron overshoots b ~3.25 m and stops ~3.25 m short of a. Corner a = ring vertex 174 of OTHH_Bridge_03_LOD0_000 (25.2515324, 51.6170258); corner b = vertex 169 (25.2516318, 51.6170853); end edge 12.5 m straight; plate ~8.38 at a, 8.56–8.60 at b. Latent defect in round-1 block constraints/deck_stack.py:239-261: overwrites r1[v] unconditionally; a vertex in `refused` (first loop :224) is still dropped at :273; overlapping ends → last wins. The drawn gate judged only the 6.8 m run at b; corner a's 6.5 m run was unjudged.

Item 4 (owner 2026-11-15T01:03Z, verbatim): "OTHH it looked like the parking garage in front of the terminal was partly submerged, could be related to the fixes in progress". Not yet measured.

## Round 2 (fresh Opus lane, medium, from origin/claude/l2091). Register patch, sidecar and capture with tools/harness/frames.py BEFORE the worktree is removed.

### S0. Capture and attribute (replay only)
1. `tools/v2_solve_replay.py --capture OTHH` at the branch head.
2. Print the unit-28 seed note and each exit's (lip, DEM, level).
3. List every planar vertex within 1.5 m of the end edge a→b and within 1.5 m of ring vertices 174 and 169: face refs/roles; in `hard`, `road_ids` or `refused`; its R1 and R3 rows; solved z; any relaxed row.
4. Replay /Users/noah/XPTerrainBuilderData/.harness/frames/lobjgate3/KIAH.pkl from planar on the base; record `low_level_list` (installed patch has building99/p1..p3, band [−3.93, −3.00]).
5. Item 4: find the parking garage in front of the terminal (pack objects; garage/parking OBJ/AGP near the terminal frontage); read its authored ground floor vs drawn ground on the 1.0.528 install (frames/l2091/ctl528.drawn.json / installed pack) and on the capture; say whether it shares the S1 mechanism (passage level / lower pad), the walled pit, FABDEM, or something else. If it is the S1 mechanism, S1 covers it; otherwise report the mechanism with numbers and a proposed general fix (do not implement a different mechanism this round).

### S1. A passage level is ground a road reaches (item 1)
In `seed_levels`, after `level_cut` and the block choice and before anything is registered, read the candidate level's road exits with the same reader the run-outs use. If at least one exit has a datum and every one has DEM at the lip − level ≥ `low_level_min_step_m`, mint nothing. Expose the exit read from `cut_runout._road_runouts` as one function `_road_runouts` itself calls (no second implementation). Note on refusal: "unit N: no road reaches its level Z: all K roads leaving climb A..B m to their ground (≥ step): its walls' feet are buried, the roads run at its zero". Zero exits or no datum: unchanged. No new law key. Nothing names OTHH. State what `viaduct_road.passage_roads`, `low_level_split(seeds=…)` and `_pieces`/`_courts` do for a refused seed; change none unless a bar fails. Twin in tests/auto_patch_v2/test_level_seeds1852.py: all exits a storey up → no level; one exit at grade → level minted.

### S2. The grade-up meets the whole end edge (item 3)
(a) One helper in geom/deck_ground.py returning the path corridor united with the same path translated along the end line so it leaves the end line's middle, buffered by the same half width; when the path start is within 0.5 m of the middle, return today's polygon exactly. All four consumers above use it; `s` stays `path.project`.
(b) Make the round-1 block the single R1 source for slab vertices: one band per (vertex, end); two ends on one vertex intersect or refuse; no stale `refused`.
(c) Act on S0's vertex table: no vertex within 1 m of the end edge near a → the rowed end's slab is stack ground wherever the ground is not airside / structure / rigid pad / road ribbon (name what cut it); vertex is `hard` → STOP and report (14f(4) class); row relaxed → report the opposing family, no further change.
Twins in tests/auto_patch_v2/test_bridge_stack2065.py: an off-centre route's apron and R6 rows cover both corners; a centred end's footprint is identical.

## Bars
Replay: OTHH no passage level, refusal note present, 0 new relaxed rows; KIAH `low_level_list` identical to base; touched tests + test_no_airport_specific_code + ratchets dupes --near / unused not rising.
Closing build (one): /tmp/claude-501/l2091/bin/build.sh with tag l2091r2_OTHH (OTHH tile, --pack-copy, --texture-mode default_xplane, --refresh-data dem). Then drawn_gate.py with the 13 sites in /tmp/claude-501/l2091/sites.txt (+ a site on the front garage from S0.5) --against /Users/noah/XPTerrainBuilderData/.harness/frames/l2091/ctl528.drawn.json.
- s1: drawn mesh 3.96 ± 0.10; no `/p` level and no `object_floor` way within 150 m; objects 0 FAIL; no patch→drawn node over bars; road step ≤ 0.5 m (if 0.53 remains with the level gone, report the way, don't chase).
- s2: as round 1 (ramp 2.61–3.96, roads PASS).
- s3: drawn mesh at five points 1.0 m outside the end edge, at 0.5, 3.0, 6.25, 9.5, 12.0 m from corner a (recompute from the build's deck_ring; reviewer's: (25.2515407,51.6170194), (25.2515605,51.6170313), (25.2516122... see sites)) — each plate − ground in [−0.05, +0.15] m; first and last differ ≤ 0.10 m.
- Front garage: report its ground-floor vs drawn ground before→after.
- R2 nine sites: PASS, no MOVED.
Stop (report, no second attempt): KIAH's level changes; S0 shows a senior region at corner a; s1 or s3 bars miss on the closing build.

Ruling text for the master to record (owner 2026-11-14T21:03Z items 1 and 3): a passage level is minted only where at least one road leaving it meets its ground within a storey; the grade-up to a bridge end spans the end edge corner to corner.
