# Brief pack — lane `lellx3`

Base: main `401e65e71` · generated 2026-11-20 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

OWNER 2026-11-20T16:59Z approved a lane for the open ELLX issues. Base origin/claude/test-568 401e65e71 (= app 1.0.568). Branch claude/lellx3. Opus, effort high. Tile +49+006 (ELLX). Earlier ELLX work: branches lellx2185, lellx2188, lellxlot, lellxpad (read their reports in the spec/RULINGS before redesigning).

## Items (owner sim read 2026-11-20T14:20Z, verbatim in each issue)
1. #2194 highway along the extended runway centreline (≈49.6370, 6.2401): holes in the road; should be a clean smooth cut, possibly just following lidar; the pack bridge object comes apart instead of seating as one group.
2. #2195 fuel-farm tanks (≈49.6347, 6.2222) raised, still locked to the upper parking area as one pad — seat on their own lidar ground.
3. #2196 large object at 49.634213184, 6.221600995 modelling a building and its pavement floats — seat it on the ground.
4. #2197 underground-parking lots both sides of the terminal (≈49.6345, 6.2144) are partial terrain shells — terrain meets their outer edges flush all the way round.
5. #2198 (small, app/engine): 1.0.567 asks for write access to a read-only pack `plugins` directory — request write access only where a file will actually be edited (Mac app + Qt mirror per #1244 if UI).
Also open: #2185, #2188 (older ELLX, same sites) — close their findings into these.

## Process
- Do NOT touch generated-bridge files (`planar/deck_*`, `pipeline/road_deck`, `pipeline/generated_publication`, `constraints/deck_carve`, `deck_floor_follow`): lane lcross21 owns them. Elevated-structure clearance over roads/rails is lane lskyclear's (20g); coordinate via the master if you need the same file.
- General rules only, no airport-specific code (gate test_no_airport_specific_code).
- Synthetic-first; stop at replay/capture evidence at ELLX (no closing tile build, 17r). Certified: list movers > 0.1 m.

## Bars

- #2194: highway under the bridge one smooth surface following lidar (no holes, max step ≤ 0.05 m along the road); bridge object bodies at one seat (spread ≤ 0.05 m).
- #2195: fuel farm pad within 0.5 m of its own lidar ground; not tied to the parking pad.
- #2196: object's lowest ground-contact edge within 0.5 m of the ground all round.
- #2197: terrain within 0.5 m of each lot's outer edge all the way round (list worst gap).
- #2198: no write-access request for a folder with nothing to edit (twin).
- Airside movers ≤ 0.5 m and no grade break.

## RULINGS

## 2026-11-19j — OWNER, A PLACEMENT IS SPLIT ONLY WHERE ITS BODIES' SEATS DIFFER BY MORE THAN THE 0.5 m GROUND BAR; WITHIN IT THE PLACEMENT STAYS WHOLE, AS AUTHORED, AT ONE ZERO, AND THE TERRAIN ABSORBS THE REST (the 0.5 m is the 09-12y ground visibility bar the lanes judge by since 10-15; not 14g (3)'s 0.05 m authored-keep tolerance, which stands for its own keep): 2026-11-19T01:35Z, owner: "Yes, and I would say use our 0.5m rule, not 5cm... within 0.5m the terrain should be able to adapt to any discrepancies and keep the objects as authored." RULED (general rule, no airport named): once every pass has seated a placement's bodies, a placement whose bodies' zeros (surface_z - y_zero) spread at most `[placement] split_bar_m` = 0.5 is written WHOLE -- one body, one file, every component at its authored place -- at ONE zero; a TERMINAL OR CLUSTER GROUP always seats as one unit: a body whose zero is shared with another placement (a touching group, a §16g unit or 22o group, a carrier of another placement's rider, a piece riding another placement's or a unit's file) names that zero, and a placement whose shared bodies sit at two zeros stays split (no group is moved by this rule). READINGS (lane lsplitbar): the rule is read ONCE, last in `build_splits` (after the touch pass and the deck warp) over the final bodies, by `airport/split_bar.keep_whole`; with no shared body the zero is the senior body's (a ground body, most ground-contact feet); a seat that is more than a zero keeps its split (a seat tilt, a deck warp or plate band, a draped slab, a plate-kind member, a row-held OBJECT_MSL body, a bridge cluster, unequal authored lifts); the terrain is NOT re-graded -- the whole placement stands on the solved surface, and where a whole seat would leave a ground-contact foot floating or buried more than the bar and worse than its own seat did, the split stands and is listed (`split_bar_ground`); the decision is per placement (whole or as today), never a partial regrouping of a placement's bodies. MEASURED (object-stage replay `v2_rebake_replay plan` of the shared Patches rebake plans on the installed tile DSFs, base claude/test-561 30ded9427; body files before -> after, bodies moved > 0.1 m): KORD 1,523 -> 1,394 (56 placements whole; 1 mover 0.105 m), KASE 168 -> 132 (3 movers, worst 0.35 m; matched by a base-src replay), HECA 3,311 -> 3,014 (0), KEGE 135 -> 62 (0), BIKF 110 -> 101 (0), OMDB 507 -> 417 (0), LGAV 1,132 -> 1,052 (15, worst 0.475 m, static vehicles and apron clutter), KBNA 1,840 -> 1,509 (8, worst 0.453 m), OTHH 1,745 -> 1,510 (14, worst 0.363 m), LOWS 5,559 -> 5,527 (0), NZWN 29 -> 29; kept split by the ground check: HECA `T23/black_NO_shadow` (float 0.565 -> 0.593), KBNA `Building_Military38-part6` (burial 0.17 -> 0.57), OMDB `services_area/s_4` (burial 0.33 -> 0.54).

## 2026-11-18h — OWNER, BUILDING GROUPS ON SLOPES: FIX ONLY THE PROBLEM SPOTS -- EVERY BUILDING SEATS STRAIGHT ON ITS OWN GROUND; A DECK STACKED ON WALLS RIDES THEM; A CONNECTOR BETWEEN TWO SEATS IS WARPED LIKE A RAIL DECK; A SEAT TILT THAT FLOATS A FOOT IS UNDONE (#2129 EDDH multi-storey car parks, tile +53+010: g1 53.625561, 10.006926; g2 53.621335, 10.001207; REPLACES the draft 18h of branch claude/leddhgar, which levelled every building group and sank HECA hangars 3.56 m and the EDDH terminal 0.94 m; narrows 10-01k Q1 / 14p (1) by (4)): 2026-11-18T18:09-18:12Z, owner: "Can we use the same code we used for rails, to keep vertical components vertical, and put the slope into connecting decks, sky bridges, etc, so that individual buildings still seat straight, and groups maintain their connecting pieces ... So far things have been looking mostly fine, so maybe there's a more specific ruleset we could use to only fix problem spots"; he approved this rule set. RULED (general rules, no airport named): (1) every building body seats on its own ground as today -- nothing that reads fine today moves; (2) a DECK STACKED ON WALLS rides those walls at its AUTHORED relative height whatever the gap -- no 16v 1-2 m judgement band for it -- and the bodies its seat holds at its zero (its unit) move with it; (3) a CONNECTOR between two separately seated buildings at different heights (sky bridge, walkway, connecting deck: a body whose ends touch two bodies of different groups/seats) is WARPED to meet both with the #2144 deck warp (`airport/obj8_warp` Track, `airport/deck_profile`: y' = y + D(x, z), piers and walls stay vertical), capped at `[deck] shear_max_grade` 0.10 (§49 (5)); above the cap it keeps today's seat and is listed; (4) a SEAT TILT (`placement_seat_tilt`, caps `seat_tilt_max_deg` 1.5 / `frame_tilt_max_deg` 1.0) applies only if no foot of the tilted body floats afterwards (> 0.05 m); otherwise the body seats LEVEL at the no-float zero; a tilted body is no longer FIXED for the touching-pair pass (`touch_seat`). READINGS (lane lgroupseat): (2) a DECK is the plan's class `deck`, seated on its own (not already carried by the walls; an elevated piece the carrier law carries rides its carrier -- read as decks, HECA's material-split hangar pieces moved 0.3-2.4 m onto a neighbour's wall tops); it STANDS ON a building when one of its elevated parts (bottom >= `chain_min_height_m` over its zero) overlaps in plan a part that rises from under it to within `[placement] split_tol_m` of the slab; and (master, same day) a CARRIED piece whose lowest part stands more than a storey (`chain_min_height_m`) over its carrier's top -- not resting on it -- and which touches in plan a building holding an elevated part at its own authored height (bottoms within `split_tol_m`) rides that building, not the carrier (EDDH `park_03__b4`, a 3 x 2 m slab at y 8.70 carried 5.65 m over `park_04__b9`: b0~b4 1.21 -> 0.00, it alone moves, -1.21 m); (3) a connector is a footless or deck body TOUCHING two building seats whose final zeros differ by more than `authored_keep_tol_m`, its nodes one per SEAT (a building's bodies at one zero); a carrier it does not touch is no end; (4) the test is read ONCE over the final bodies AS WRITTEN (rotated, at the zero later passes gave them -- EDDH `park_03__b0` was fitted at its own zero and re-zeroed 0.4 m higher by its 22o group), on the ground contact feet of the tilted FRAME (one unit, zero and gradient pair); the no-float sink is taken only within 16v's "less than a meter" (`touch_seat.SEAT_MAX_M`): a frame whose LEVEL seat floats more than that is no tilt problem, rule (1) keeps it and it is listed (HECA `Hangar_Tower` 11.2 m, EDDH fire station 2.1 m). Implemented: `airport/tilt_float` (rule 4, first in `touch_seat.seat_touching`), `airport/stacked_deck` (rule 2, in the touch pass: the deck takes no vote and moves to its walls' final zero), `airport/connector_warp` (rule 3: the touch pass lists the connectors, `deck_profile.warp_decks` warps them through its one per-group body `_warp_group`). MEASURED (owner 1.0.559 EDDH plan and the shared HECA/KEGE/KASE/BIKF plans replayed on the installed DSFs, base test-560): g1 roof `park_05__b2` 13.26 -> 11.41 = its walls `park_04__b6` (its 0.42 deg tilt floated a foot 0.34 m: level 11.86 -> 11.41), roof-to-walls 1.40 -> 0.00; g2 `park_03__b0` (its 0.72 deg tilt floated 0.34-0.43 m at every foot) level at 14.34, no foot floats; EDDH movers 9 (rules 2/4, all car-park bodies), terminal group fu:8:2135 and fire station 0; HECA 8 (rule 4, sinks 0.16-0.79 m); KEGE, KASE, BIKF 0; no connector under the 10 % cap at the five (EDDH `fire_03__b3` 41.6 %, HECA seven at 11.8 % and steeper: listed).

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file. SIZE (owner 2026-10-04c, `tools/ratchets.py`): 1,000 lines is a guide and a
  warning, never a gate — the report (files past 1,000, files that grew, functions of
  200+ lines) is read by the master at merge. Split by responsibility, never to make a
  number. THE PRIORITY IS REUSE: small one-responsibility modules, no second
  implementation of a thing that exists (the identical-body duplicate count IS a gate:
  it may fall, never rise; `dupes --near` is reported).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`.
  Do NOT set `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR`: the harness makes its own
  overlay, and with them set a build refuses ("pack DSF dump MISSING", #342) — they are
  the pytest suite's mechanism, set by `tests/conftest.py`.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched; net lines added/removed
  + new public symbols (owner 2026-10-04a (5)).

