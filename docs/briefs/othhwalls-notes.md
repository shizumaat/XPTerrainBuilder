# Lane othhwalls / othhwalls2 — continuation notes (2026-10-07, handed back early: machine shutdown)

Branch `claude/othhwalls`. The top commit is a WIP commit holding tasks B and C together (not yet split).
Capture used: `/Users/noah/XPTerrainBuilderData/.harness/frames/perfB362/OTHH.pkl` (`--from planar` replays work on it).
Scratch (local, lost to a cloud lane): `<scratchpad>/othhwalls2/` — `repA/` (replay with A only), `pdC.log` (planar dump with A+B+C).

## A (#453 #454 #455) — DONE as c1f50c88, verified by twins + one replay
- `tests/auto_patch_v2/test_tunnel_objects.py`: 14 passed.
- OTHH replay `--from planar --emit` with A only (rc 0, planar 115 s; body sha NOT read — do it in the closing build):
  ramp face at #453 site 84.1 x 22.8 m -> 103.6 x 31.2 m (`tunnel_sw.obj@0`, walls 103.3 m, grade 4.94 %, floor -1.14 = ground 3.96 - 5.10);
  #454 84.5 x 25.1 -> 221.2 x 39.0 m (`tunnel west 3.obj@0`, walls 221.3 m, 2.30 %);
  #455 83.8 x 23.8 -> 220.9 x 41.8 m (`tunnel west 2.obj@0`, walls 221.3 m, 2.30 %) plus a flat trench 39.7 x 35.6 m (`tunnel west 1.obj@0`, bores at both ends).
- REBAKE TABLE — NOT FINISHED. Before (sw `swg_OTHH.v2/OTHH.rebake.json`, plan v12): unit agl / plate_y:
  south west 2 -5.5 / 10.0; tunnel1 x2 -5.0 / 9.55; middle west, middle east -3.0 / 5.0;
  tunnel_sw -0.0 / None; west 2 -0.0 / None; west 1 +2.499 / None; west 3 +0.999 / None (all plate_clearance 0.0).
  After: needs the closing build's `OTHH.rebake.json`. EXPECTED CONFLICT WITH 07b (1): A admits tunnel_sw, west 1, west 2,
  west 3 as corridors, which makes them plate members, so the object stage will now re-seat four walls it used to leave at
  the authored elevation. Not measured. The master should decide whether A may land before lane `authspec`'s rule.

## B (#449 ridge) — CODE + TWINS DONE, in the WIP commit; OTHH effect NOT measured
- Mechanism (measured on the 1.0.383 graded.json): faces 955/959 share the edge (0.6,0.5 z 2.07) -> (-49.4,-18.5 z 3.77), one
  53 m edge with no vertex at the knee; outer edges carry the knee at s ~27. Centre 0.87 m over the edges.
- NOT VERIFIED: that this shared edge is a `road_centerline` cut line (inferred from `planar/overlay.py:298`); the dump that
  would show it (`pdC.pkl`, key `cut_lines`) was written but not read.
- Change: `planar/structure_service.knee_nodes` (new public symbol) adds a point to every surface cut line where it crosses a
  ramp's emitted cross-chord (spec §34 (7)); wired in `planar/structures.py` after `decked_exclusion`.
- Twins: `tests/auto_patch_v2/test_othhwalls.py` (2 passed).

## C (#448, #449 length; RULINGS 07b (2)) — CODE + TWINS DONE, in the WIP commit; SPEC TEXT NOT TOUCHED; no replay/emit
- `planar/wall_corridor_ramps.full_wall_ramp` (new public symbol): top = ground at the walls' outer end (the record's last
  station = where BOTH walls stand, i.e. the SHORTER wall's end — spec silent, QUESTION), full depth at the covering plate's
  edge, capped at `max_ramp_grade`; over the cap the knee moves back under the building (14u); if even the whole wall is too
  short, a closed bay holds the cap and raises its floor (17h Q1 / §47 (7)), an open half is refused.
- DEVIATION FROM THE BRIEF, needs the master: the brief said "its grade is whatever that span needs"; I held the 10 % cap
  because 17h Q1 and 07b (2)'s first sentence say so. Consequence at OTHH (planar dump, A+B+C):
  the five `Terminal_Base_2_1` bays: walls 6.3 m, depth 1.35-1.39 m -> ramp 6.3 m at 10 %, floor RAISED 0.72-0.76 m (step at the door);
  uncapped it would be 22 %. `DutyFree@2`: walls 20.3 m, ramp 13.7 m at 10 %, knee at s 6.6.
  Through corridor `Terminal_Base_2_5@0/a,/b`: walls 38.9 m per half, ramp 18.9 m at 10 %, knee at s 20.0 (was ~26.5 m at 8 %
  running 16-20 m past the walls).
- Deleted as dead: `stop_and_steepen`, `locked_road_stops`, `airside_stops` (wall_corridor_ramps), `road_edge_witness`,
  the old `cap_held_note` signature; law keys `cutout.wall_corridor.ramp_grade`, `road_edge_line_reach_m`,
  `road_edge_line_parallel_deg` (toml + `law/cutout_schema.py`).
- LEFT INERT, not cleaned: `Tunnel.pinched`, `StructureStats.pinched_ramps`, `pipeline/publication.lifted_caps`, the census
  lifted-cap readers, `Group.stop_side`.
- Tests rewritten: `test_v2wallcorridor.py` (level / bay / pavement-beyond / pad), `test_v2corridor.py`. 66 passed over
  test_v2wallcorridor, test_v2corridor, test_othhwalls, test_law_tables. NOTHING ELSE WAS RUN (no full suite, no ratchets).
- TODO: spec amendment (§34 (8)/(9), §12h, §47 (7)) citing 07b (2); twin for `full_wall_ramp` itself in test_othhwalls.py;
  split the WIP commit into B and C; `planar/structures.py` is now 953 lines (gate <= 1000 in test_planar).

## D (10 % cap) — NOT STARTED; inventory only
Keys that carry the road / ramp / lot cap: `rulesets.toml [common.roles]` tunnel_ramp 0.080, service_road 0.080,
service_junction 0.080, groundside_pavement 0.080, parking_lot 0.050 (door_ramp, wall_corridor_ramp already 0.100);
`[common] road_max_grade 0.08`; `structures.toml [tunnel] ramp_max_grade 0.080`; `auto_patch/config.py`
SERVICE_ROAD_MAX_GRADE 0.080 (O4_Cfg_Vars `road_grade_limit` default and GROUNDSIDE_PAVEMENT_MAX_GRADE alias it),
TUNNEL_RAMP_MAX_GRADE 0.080; literals `tools/check_grade.py:120` and `:7673` (0.08 fallbacks). The §55 gap-piece cap was not located.
TWO OPEN QUESTIONS found: (1) `law/tables.pavement_fallback_cap` IS `road_max_grade` (29ac, "never a second number"), so
raising the road cap also raises the fallback ceiling of AIRSIDE pavement pairs 8 -> 10 %; (2) `constraints/ceiling.py` gives
the road ceiling only to `families.road_cross_section.roles` (service_road, service_junction) — parking lots and
groundside_pavement stay under the HARD 5 % `pavement_max_grade`, so a 10 % lot role cap alone changes nothing.

## E (#450) — ATTRIBUTION PARTIAL, no code
`tunnel:-1355@0`: mouth_z -1.14 (ground 3.96 - 5.10), `climb_from_s` 260.3, `top_s` 300.0, design grade 8 %, not clipped;
its only note is "stations collapsed 26 -> 12". The climb is deferred 260 m and 39.7 m at 8 % reaches only +2.04, not the
ground. WHICH interval (deck / pavement / object) sets 260.3 was NOT identified. Other mouth `tunnel:-1355@1` refused
"the mouth stands against building pad building4".
Next: print `deck_ivals`, `pav_ivals`, `obj_ivals` for that tid at `planar/structures.py` where `climb_from` is taken.

## Not done at all
Closing OTHH harness build, body sha, rebake plan hash, wall time; reach at CYXY SPJC KCLT KASE HECA NLWF; full non-Qt
suite, Qt split, the four gate files, `tools/ratchets.py`; draft PR; frames.py register.
