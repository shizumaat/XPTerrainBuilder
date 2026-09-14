# Brief pack — lane `v2othhfix`

Base: main `4bb102c1` · generated 2026-09-14 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

OTHH: the basin floor is the whole region (§24 (7)); ramp chords only at bends (§34 (7)); a stopped climb ends at the pavement with a portal (§34 (8))

## The brief

Three OTHH fixes, one lane (RULINGS 14p; the spec sections §24 (7), §34 (7), §34 (8) carry the mechanism, numbers and bars). Files: `Ortho4XP/src/auto_patch_v2/airport/obj8.py` (the `buried_components` skip :669-671 and `_witness` :781-812), `planar/basins.py` (:517-521 region, :640-643 plates, :724-727 the void → retaining_wall), `planar/wall_corridor_ramps.py` (`stop_and_steepen` :118-149, the snapped stop :133), `planar/structure_geometry.py` (`_geometry_at` :196-224, the snap :137-150), `planar/structures.py`, `law/structures.toml`. Frame: the owner's 1.0.332 OTHH products (`/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+25+051/OTHH/OTHH.report.json`, `OTHH.rebake.json`, the patch `Patches/+20+050/+25+051/OTHH_auto.patch.osm`, READ-ONLY) and the registered OTHH capture (`frames.py list OTHH`, base 7949757a) for `python -m auto_patch_v2.planar --stage structures` dry arms (lane-local mod cache, WARM overlay). Scout readers in `…/scratchpad/` (`v2othh332`'s — find them under the session scratchpad; the mesh sampler is `tools/mesh_elevation_sampler.py`). Order: (1) basin (§24 (7)) — dry `--stage structures` before/after: floor/region per basin; (2) ramp chords (§34 (7)) — collapse after the profile solve; (3) underpass (§34 (8)) — measure the half-metre first, then the portal. Consumer census for each (readers of basin floors/`retaining_wall`, of ramp rings, of corridor refusals). Closing: ONE OTHH build (`build_airport.py OTHH --tile 25 51` or the patch-only entry — patch-only is enough unless the mesh read is needed for the basin bar; it is: the basin bar is mesh stations — so the tile-mesh entry `run_tile_mesh_only.py 25 51` lane-local after the patch build, or accept the graded-surface reading and say so). LEMD basin:0 dry as the control.

## Bars

- Basins: floor/region ≥ 0.95 on all ten OTHH basins (today 0.10–0.56; basin:6 879 / 4,330 m²); basin:6 stations inside the rim above −9.18: 270 / 393 → 0 (mesh or graded surface, say which); every skipped buried component named; LEMD basin:0 97.4 % unchanged.
- Ramps: −10854 40 → 8 nodes, −10859 29 → 8; lateral offset from the chord ≤ 0.05 m; profile within 0.01 m at every former station; all 23 `tunnel_ramp` ways before → after.
- Underpass: `OTHH_Terminal_Base_2_5.obj@0` cut with both mouths; portal heights named; the five `Terminal_Base_2_1` corridors byte-identical; airside vertices moved > 0.1 m = 0.
- OTHH build rc 0, verify DEFECT families empty; census before → after (matched pair); plan/planar stage not worse than +5 %; suite twice.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/obj8.py`, `Ortho4XP/src/auto_patch_v2/planar/basins.py`, `Ortho4XP/src/auto_patch_v2/planar/wall_corridor_ramps.py`, `Ortho4XP/src/auto_patch_v2/planar/structure_geometry.py`, `Ortho4XP/src/auto_patch_v2/planar/structures.py`, `Ortho4XP/src/auto_patch_v2/law/structures.toml`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/classify/`, `Ortho4XP/src/auto_patch_v2/airport/footprint_unit.py`, `Ortho4XP/src/O4_Vector_Map.py`, `Ortho4XP/src/O4_Mesh_Utils.py`

## Spec (design-surface) §24 (7)

### §24 (7) THE FLOOR IS THE WHOLE ADMITTED REGION (owner RULINGS 2026-09-14n item 1; Fable 2026-09-14; RULINGS 2026-09-14p) — lane `v2othhfix`

Once a region is admitted as a pit, the trench floor covers the region minus
the rim stand-off; the witnessed plate DELIMITS NOTHING — it witnesses depth.
(a) The floor witness is read over the whole ADMITTED FAMILY: a sibling
placement whose deep horizontal plate lies inside an admitted region
contributes it even when its own shell never reaches grade (the
`buried_components` skip in `obj8.py` is a pit-SEED test and never
suppresses a plate inside another placement's pit); every skipped buried
component is NAMED in the report with its area and depth.  (b) Where no
plate lies under part of the region the floor still takes `floor_z`: a
rim-level island inside a pit is terrain standing inside the object's walls.
BARS (OTHH 1.0.332 frame): floor/region ≥ 0.95 on all ten basins (today
0.10–0.56; basin:6 879/4,330 m²); mesh stations inside basin:6's rim above
`solid_min_z` (−9.18) 270 of 393 → 0; LEMD basin:0 unchanged (97.4 %, the
control); ONE OTHH build.

## Spec (design-surface) §34 (7)

### §34 (7) A RAMP CORRIDOR CARRIES A CROSS-CHORD ONLY WHERE THE ROUTE BENDS OR THE PROFILE BREAKS (owner RULINGS 2026-09-14n item 2; Fable 2026-09-14; RULINGS 2026-09-14p) — lane `v2othhfix`

Stations at `station_m` are the SAMPLING of the profile, not the emitted
shape.  After the profile is solved, consecutive stations whose axis stays
within `min_distinct_spacing_m` (0.5) of the chord between the surviving ends
AND whose design z stays within the materiality floor (0.01 m) of the linear
interpolation between them are COLLAPSED; a straight constant-grade run emits
its two end chords and nothing between; a landing-to-climb transition keeps
its chord.  The 0.5 m identity `snap_out` then has nothing between the ends to
stagger.  BARS: OTHH ways −10854 (40 nodes) / −10859 (29) → 8 nodes each
(landing / climb / landing), max lateral offset from the chord ≤ 0.05 m
(today 0.27–0.49); the ramp profile unchanged within 0.01 m at every former
station; every `tunnel_ramp` at OTHH before → after node counts.

## Spec (design-surface) §34 (8)

### §34 (8) A CLIMB STOPPED BY AIRSIDE ENDS AT THE PAVEMENT; THE REFUSAL IS THE RAMP'S, NEVER THE CORRIDOR'S (owner RULINGS 2026-09-14n item 2; Fable 2026-09-14; RULINGS 2026-09-14p) — lane `v2othhfix`

When `stop_and_steepen` cannot reach the ground inside `max_ramp_grade`
before the axis enters airside pavement, the ramp ENDS at the pavement edge
at the grade it has, and the residual step is taken by a PORTAL / RIM FACE at
the pavement boundary (a retaining wall — what the pack authors there); the
airside cell is never pulled (airside is king).  A corridor whose trench is
otherwise lawful is CUT with its mouths (§33 (2)); the report names the ramp
refusal and the portal height.  Measure first: the stopped station is snapped
one `grid` short of the cell boundary (`wall_corridor_ramps.py:133`) — at
OTHH `Terminal_Base_2_5.obj@0` the miss is 1.0 pp over 17.1 m (1.88 m of
rise); if recovering that half-metre makes it lawful, say so, and still land
the portal rule for the next one.  BARS: the corridor under the terminal at
25.26621, 51.61134 CUT (trench + both mouths), the portal faces named with
their heights; the five `Terminal_Base_2_1` corridors unchanged; no airside
vertex moves.

## RULINGS

## 2026-09-14p OTHH items attributed (scout `v2othh332`): the basin floor is read per placement and the floor slab is a silently-skipped buried component; the ramp zig-zag is the 0.5 m identity snap per 2 m station; the underpass is refused by a 1.0 pp ramp grade — §24 (7), §34 (7), §34 (8) written; lane `v2othhfix`

* BASIN (basin:6, `OTHH_Dewatering_02_LOD0_002.obj`): the two floor
  faces (ways −10875/−10876 at −9.68) are the only witnessed plates of
  the SHELL placement (879 of 4,330 m², 20 %); the 2,998 m² floor slab
  is a SIBLING placement `…_001.obj` whose components are skipped as
  BURIED (`obj8.py:669-671`, `shell_reaches_grade and top < local −
  contact_band_m` → `buried_components`, no report line) and whose only
  grade-reaching parts are 2.5/5.6 m² risers refused by
  `rim_protrusion_max_fraction`. The void becomes `retaining_wall` at
  the rim: mesh inside the rim median −5.63 m, 270 of 393 stations
  above the object's floor −9.18 — a V-funnel with ~10 m of flat floor.
  LEMD's basin: one grade-reaching shell whose plate IS the footprint
  (97.4 %); every OTHH basin 10–56 %.
* RAMPS (`tunnel_ramp` / `wall_corridor_ramp`, 8–57 nodes): one
  cross-section per 2 m station (`[cutout].station_m`), every edge
  point `snap_out`ped to the 0.5 m identity grid on both coordinates
  (`structure_geometry.py:137-150`) — max lateral offset from the
  straight chord 0.27–0.49 m, i.e. one grid quantum; the route is
  straight. The faithful shape is landing / climb / landing = 8 nodes
  (today 40 / 29).
* UNDERPASS (`OTHH_Terminal_Base_2_5.obj@0`, inside `building5`): every
  admission test PASSES (wall depth 1.89 > 1.0, headroom 4.31 > 3.5,
  mouths, authored grade, not a jetway); refused at `stop_and_steepen`
  — the 8 % climb out of each mouth is stopped by airside pavement
  (`pav24` / `pav11`) at s = 56.0 with 17.1 m left for 1.88 m of rise =
  11.0 % > `max_ramp_grade` 10 % (08m (a)) — ONE ROW PER ENTRANCE, and
  Law C discards the whole corridor. `Terminal_Base_2_1`'s five
  corridors under the same terminal cut fine (their climbs reach open
  ground). `structure_underpass` (§34 (5)) cannot apply: the seed is an
  OSM aeroway bridge.
* RULINGS: §24 (7) a basin's floor is the WHOLE admitted region;
  sibling placements' deep plates witness inside an admitted region;
  a buried component inside someone else's pit is never dropped
  silently. §34 (7) a ramp corridor carries a cross-chord only where
  the route bends or the profile breaks (stations are the sampling,
  not the shape). §34 (8) a climb stopped by airside pavement ends AT
  the pavement with a portal/rim face taking the residual step; the
  refusal is a RAMP refusal, never a corridor refusal. Lane `v2othhfix`.

## 2026-09-14n Owner on 1.0.332 OTHH: "Two small issues at OTHH, then I think it's fully approved!" — scout `v2othh332`

Owner, verbatim: "1. The drainage basins are not cutting out the whole
basin, just either side here: 25.2523246, 51.6245625 and 25.2527399,
51.624374, but the object goes between those two points, so it seems
like the same below grade cut shape should extend across that space so
no terrain pokes through the basin object, just like the much larger
basin at LEMD. 2. The small ramps leading down along the main terminal
look good, however I don't understand why the shapes have so many nodes
and are not straight, but seem to zig zag back and forth. Since they're
straight, why not a simple rectangle with 4 nodes, two at the low end of
the ramp and two at the high end? And we're still not cutting the ramp
for the one corridor that passes under the terminal and has the same
sort of short retaining walls extending out from the terminal building
at each entrance."

* Scout `v2othh332` (1.0.332 OTHH products): (1) the basin at the two
  points — which basin bodies/rings (§24) exist there, why the cut is
  two pieces with the object's middle uncut (two components of one
  object? the floor read per part? a covered stretch dropped?), the
  object's footprint vs the rings; (2) the terminal ramps — which
  shapes (role, node count, the route/station derivation §34 that mints
  the zig-zag: per-station widths?), and the ruling to write: a straight
  ramp is a 4-node rectangle between its two end chords (stations only
  where the route bends); (3) the corridor under the terminal with
  retaining walls at each entrance — why no underpass cut (§34 (4)–(6),
  `structure_underpass`, `structure_approach`, door wells: which test
  refused it, with numbers).

## Tool: mesh_elevation_sampler

| `Ortho4XP/tools/mesh_elevation_sampler.py` | Sampling the terrain the sim actually renders, after grading. `--point` / `--lat --lon-range` / `--lon --lat-range` give points and transects; `--step-flag M` tells a FACE (one step) from a RAMP (several). **`--alt-raster DATA.alt` (2026-08-28, CYXY INTERP_ALT round) prints the tile's OWN `.alt` beside every sample with the delta, plus a worst/rms line** — the raster Triangle4XP was handed and re-sampled every free vertex from, which is the reference that separates "the DEM is wrong" from "something overwrote the DEM", and it is the acceptance instrument for any altitude-authority round. The frame is `O4_DEM_Utils`' own (square float32 over the tile-relative extent [-0.01,1.01]^2, row 0 at y1) and the interpolation is the TRUE BILINEAR of `Triangle4XP.altitude()` / `DEM.alt_baked` — nearest-neighbour reads up to a whole 14.8 m cell off, which on an escarpment is tens of metres of FAKE disagreement. The tile origin is parsed from the mesh filename; `--tile LAT LON` overrides it (needed when the mesh has been copied to a scratch path). Measured at +60-136: pre-fix the lat-60.7096 transect held a 697 m bench out to lon -135.054 and then dropped 63.7 m in ONE triangle (worst +58.7 m, rms 18.1 m); post-fix the bench ends at -135.058 and follows the raster down (worst +16.5 m mid-cliff, rms 3.2 m). |

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N]` on either a `--replay` arm or a `--why-from PKL`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Registered frames: OTHH

OTHH  rebake   base 05050624   lane v2unboxed        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/unboxed  — KCLT 1.0.324 / LEMD 1.0.325 / OTHH 1.0.326 rebake frames + dry arms
OTHH  capture  base 7949757a   lane v2othh327        2026-09-13T16:30:07  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othh327/OTHH.pkl  — v2_solve_replay --capture OTHH on main 7949757a (402 s); solved arms beside it: OTHH.solved.pkl (base) and OTHH.nofeet.pkl (--drop-generator foot_rows)
OTHH  patch    base a0f65165   lane v2cutfeet        2026-09-13T17:37:22  /tmp/harness/OTHH_20260913T171324.osm  — closing build of lane v2cutfeet (§11b (7) cut foot verdicts), rc 0, 968.0 s, ways 1097, body_sha 0ff85d1a7bff, artifact ledger 86493fdab68b; matched replay arms on the v2othh327 capture live in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cutfeet/out (OTHH.base.pkl / OTHH.cut.pkl / othh.base.json / othh.cut.json / *.log), KCLT arms beside them
OTHH  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_OTHH/structures.json  — OTHH planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_OTHH: basins array BYTE-IDENTICAL; only one sunken_refused message rounds 50%->49% roofed, same verdict
OTHH  capture  base cf87c942   lane v2unionsweep     2026-09-14T07:40:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2unionsweep/othh.lane.json  — DRY replay dump (NOT a capture: the plan_clusters reading OFF the registered OTHH capture 7949757a, via scratchpad/v2unionsweep/cluster_arm.py). MATCHED PAIR: othh.base.json = main cf87c942 (666.07 s, machine contended; scout v2partcost read 299.8 s uncontended at 628cca80), othh.lane.json = claude/v2unionsweep 99cf52ba (16.60 s). 44 clusters both arms, all 44 area_m2 BIT-IDENTICAL (struct.pack '<d' hex).

## Registered frames: LEMD

LEMD  capture  base ec8723e9   lane v2roadcap        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/rw/cap/LEMD.pkl  — the v2roadcap-era LEMD capture used by scout v2unsettled2
LEMD  capture  base 864e7577   lane v2settle         2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle  — fresh main capture + per-law arms + logs (13ak)
LEMD  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_LEMD/structures.json  — LEMD planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_LEMD: every basin rim_ll/region_ll/floor_z/ramp_rings_ll/area/notes and every basin refusal BYTE-IDENTICAL; only covered_fraction moves 0.22750697->0.22750614 at the 1 cm plane quantum
LEMD  mesh     base 8fce79cb   lane v2hairline       2026-09-13T17:43:19  /tmp/harness/tile_v2hairline_arm3/Data+40-004.mesh  — §39 ARM: shore weld ON, metric split ON, vector weld OFF — sub-0.1 m2 in bbox 1,641, aspect p50 1.61, 2,734,780 tris
LEMD  patch    base df67b414   lane v2hairline       2026-09-13T17:43:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/control.osm  — §39 CONTROL patch (harness tag v2hairline_control) with shore_edges injected from the same TileWater witness — hairline_pair 29 adjudicated
LEMD  capture  base 32c78eaf   lane v2lemd329        2026-09-13T20:49:45  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/LEMD.pkl  — fresh LEMD v2_solve_replay capture on main 32c78eaf (22158 vertices, 1119 faces, 353 s) — for the sunken-road round
LEMD  mesh     base 00d8b05c   lane v2hairline       2026-09-13T21:16:09  /tmp/harness/tile_v2hairline_r2cp/Data+40-004.mesh  — §39 round 2 FINAL arm: one witness + project + merge + crossing dedupe + 13cp z carry — 1,617 sub-0.1 m2 in bbox, aspect p50 1.65, 2,745,864 tris, pre-flight 7 UNMESHABLE (all non-patch markers)
LEMD  mesh     base 6b3a57cb   lane v2bankfoot       2026-09-13T21:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/fix/Data+40-004.mesh  — FIX ARM (13cp): bank rings CLOSED again, open runs wear PATCH_RING_MARKER, ribbon belt — annulus 39,105 of 58,555 valued, harmonic moved 491, isolated components 0, 111 closed bank_foot ways / 0 open; owner site 40.465414,-3.5531888 median 589.00 (1.0.329: 568.3); attr-8 nodes over 2 m = 3 of 275,861
LEMD  mesh     base 6b3a57cb   lane v2bankfoot       2026-09-13T21:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/omit/Data+40-004.mesh  — OMIT ARM (owner request): [design] bank_omit=true, NO bank_foot emitted — ribbons restored too (attr-8 over 2 m = 4), but patch edge step median 0.740 / p95 5.680 / >3 m 2,584 vs the fix arm's 0.415 / 4.944 / 1,924

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
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

