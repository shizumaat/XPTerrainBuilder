# #2129 — the terrain grades up to the elevated ends of a unit's deck (Fable review, 2026-11-18)

TWO-ROUND-CAP-REVIEW of leddh4 (`claude/leddh4` ca70ceeb4) items 1 and 2. Read-only review; this
file is the spec for ONE fresh Opus round (high). A miss goes to the owner. Law: RULINGS 2026-10-22m
(2) ("A bridge attached to a building stays grouped with it ... the terrain must grade to the other
end"), 2026-10-03e (#290, landings), 2026-10-14c (5) (#711, run-out at road grade, 1:3 sides),
2026-11-14d/e/f (A3 end states), 13r, 08-30l, 10-05e. Paths under `Ortho4XP/src/auto_patch_v2/`.
Never raise the lane cap; delete your scratch builds when you report.

## 0. Evidence read (no build, no capture)

The owner's own 1.0.559 build products stand in the data repo (header `o4_app='1.0.559'`,
`o4_build_sha='1d4b84656373'`): `XPTerrainBuilderData/tmp/auto_patch_v2/+53+009/EDDH/EDDH.report.json`,
`Patches/+50+000/+53+009/o4_v2_rebake_EDDH.json` (plan v16), `Patches/+50+010/+53+010/EDDH_auto.patch.osm`.

F1 WHY park_10 IS NOT A BRIDGE (corrects the round's "airside-meets or W1, not confirmed"). Its frame
   is the terminal's: report `planar.basins.objects.deck_records[7]` — key (626.001, -348.693, 0.0),
   36 members, 15 plates; the plan's `unit:12` holds the same 36 (`new_terminal_001..019`,
   `park_01..16`; 15 `signature`, 21 `family`). `planar/free_bridge._read_free_bridges` therefore
   cannot keep or free it whatever W1 says: KEPT needs an all-deck frame (`_bridge_frame`, :187-194,
   :225, :241-242) and FREE needs `classify` = `free_bridge`, i.e. W6 FREE FRAME
   (`bridge_class.witness_holds` :63-65; `bridge_witness` W6: every other body the bridge's own).
   At best it is `attached_bridge` — 22m (2)'s case, for which NO grade-up exists (22m: "the terrain
   grading half is #1138"; A3 rule 1 builds free and all-deck bridges only). Which witness fails
   FIRST (`airside.meets` :216, W1, W2 ribbon cover on a 73,485 m2 plate) is not confirmed and does
   not matter; G0 prints it.
F2 The relation that DOES hold is 10-03e's: park_10 is a deck of a terminal unit, and
   `planar/landing` already grades the ground to such a deck — but only at its LOWEST band
   (`bridge_family.landing_pieces` :904: surface within `BAND_M` 0.5 of the deck's lowest y), and a
   deck standing over the pad is refused outright (`landing.py:30-33`, `landing_above_unit`, "a
   deviation flagged for the spec author"). EDDH mints 3 landings, 0 run-outs (report
   `constraints.by_generator.landing_level.landings` 3, `landing_runout` 0); `building39/landing1#collar`
   stands 32 m W of site 1.
F3 SITE 1 (53.630341269, 10.009158852) is ON park_10's plane (`deck_ring`, 4.6 m inside), on a level
   stub about 10 m wide (`deck_profile` y 6.0) whose END EDGE lies 12-16 m N of the point
   (ring corners (+6.8, +11.9) and (-3.5, +16.3) m E/N of it; both sides run > 45 m back). The patch
   road `small_roads:-129` runs along the stub under the point at 11.42-12.87 (guest piece,
   `o4_grade_law_cap_lifted` 0.12151); deck top = unit zero + 6.0 (the round: 17.8).
F4 SITE 2 (53.633821283, 10.009869078) is NOT on the plane (57.8 m off `deck_ring`): it stands on a
   park_10 strip 9 m wide (lon 10.009759-10.009895) and 52 m long (lat 53.63374-53.63421; plan part
   21781, a sub-ring), 9 m N of the strip's S end edge. No patch road stands on the strip: the
   nearest ribbons are `big_roads:-3175` (3-15 m W, 11.84-11.95, cap lifted 0.143) and
   `big_roads:-2663` (21-32 m W). The round's "48 m west edge" is this strip's long side. Whether the
   S edge is open or joins another part of park_10 was not read (needs the OBJ8: G0).
F5 So the round's rule ("where a mapped road leaves a deck's outline") covers site 1 and NOT site 2,
   and `rebake_plan`'s end stamps / `free_bridge_seat` are the wrong home: the seat is the unit's and
   stays (22m (2)). Nothing at the object stage changes.

## 1. Ruling: neither of the two options as posed — a third landing kind

Do NOT admit unit decks to the free-bridge route-end grade-up: its zero is fixed before the solve
(A3 rule 2) and a unit's zero is its block's SOLVED datum (`datum_pred` stood 1.7-1.9 m under it at
HECA, `landing_runout.py` doc). Do NOT add a free-floating "road leaves any deck" rule either.
EXTEND the 10-03e landing family (`Registries.landings`), which already holds the ground at
`block datum + y` in stage 2 (`constraints/platform.landing_rows` :599, `z_v - z_D = y`, one-way),
banks it 1:3 (`platform_collar_rows`) and runs it out at road grade (`planar/landing_runout`,
`constraints/ramp_runout.landing_runout_rows`): a new kind **`end`**, a new file
`planar/deck_end_fill.py` beside `pad_fill.py` (a `Fill` witness; nothing appended to `landing.py`
but its call). No new constraint head, no new law key unless §2 names it.

## 2. Rules

R1 WHICH DECKS. Every deck of a block by `bridge_family.viaduct_units` (the one 10-03e derivation,
   as `landing_regions` calls it, `landing.py:296`). Free, kept, stack, cut and class-A decks are
   absent from it or already taken (`taken`); a deck with a `DeckStack` end at the same place mints
   nothing here.
R2 THE DRIVEN SURFACE S of such a deck: the plan union of its near-horizontal up-faces
   (`bridge_witness.up_faces`, `[bridge] deck_plate_normal_y_min`) at ANY y — not the plane ring
   (F4: a ramp strip is off it).
R3 AN END EDGE of S (pure geometry): a straight run of S's outline (within `deck_flush_m`), length
   L <= 2 x `free_route_half_width_m`'s road cap or the piece's own width, whose two neighbours turn
   back >= 60 deg and each run >= L behind it (a ribbon's tip), and which is
   (a) OPEN: no up-face of any member of the frame within one `abutment_sample_step_m` outward at
       y within `deck_flush_m` + `ramp_grade` x step (else a JOINT, W7's meaning), and
   (b) UNSUPPORTED: no STANDING face of the frame (`bridge_end_state.standing_plan`: walls, the
       `end_solid_*` thresholds) under the edge reaching the ground band — an abutment the author
       built is left alone, counted `end_on_own_abutment`, and
   (c) ELEVATED: y_e (S's top on the edge, `geom/lowest_face.every_z_at`) > the deck's lowest y +
       `BAND_M` (else it is 10-03e's landing, unchanged) and gap = block `datum_pred`
       + y_e - G_e > `[cockpit] visual_m`, G_e the DEM `free_end_ground_out_m` out
       (`deck_stack._end_ground`).
   The lane may take the tips of `geom/centreline.ribbon_centreline` instead if G0's table is equal.
R4 THE PATH. A mapped `highway` / `railway` way, no tunnel, with `layer >= 1` or `bridge != no`
   inside S, that crosses the end edge: the path is that way outward (`bridge_end_state._walk_path`,
   straightest joins, run-on straight) — ROUTE end. A way with neither tag is under the deck, never
   carried. No such way: the edge's outward normal — STUB end. A way lying within L/2 of a stub's
   ray and within 30 deg of it for the whole run (F4's -3175, if G0 shows it) is NOT adopted: a
   mapping offset is a finding, reported with the distance.
R5 THE STATE, by `bridge_end_state.end_state` unchanged (top = y_e, zero = `datum_pred` + the
   block's `widest_reach`, the HIGH estimate `landing_runout` sizes with): FLUSH; HELD
   `end_at_pack_solid`; LISTED `end_on_airside`, `end_under_low_deck`, `end_on_water`,
   `end_beyond_reach` (a stub over `[building_pad] fill_road_reach_m`), `end_off_dem`; else GRADED.
   Only a GRADED end mints. 13r: any doubt, nothing built, one note.
R6 THE FILL of a GRADED end = a landing `<unit>/landing<k>`, `kind: "end"`, `y: y_e`,
   `deck: "end:<member>#<k>"`: PLATFORM = the end edge swept one `abutment_sample_step_m` outward
   (A3's slab), widened by `[basin] contact_band_m` as every landing is (`landing.py:310`); COLLAR =
   the landing's own 1:3 bank on every side, the deck's side included — it falls away under and
   beside the deck, single-valued. The landing gate's `landing_above_unit` refusal does not apply to
   kind `end`; `landing_below_unit` does.
R7 THE RUN-OUT, `runout:<landing ref>`, through `landing_runout.landing_runouts` with a foot-shaped
   record (mid-point, width L, direction): a STUB runs straight (today's strip); a ROUTE end's strip
   follows the path. Where the carried way has a ribbon, the RIBBON within the run is the strip:
   its vertices take the run-out rows and its road ramp is withdrawn there (the existing
   `road_ramp_withdrawn_on_runout` path, `constraints/road_ramp.py:1226`, `airport/road_ramp.py:776-785`);
   no second face is minted over a road. RESULT REQUIRED: beyond the end edge the road stands at the
   landing's level and descends at `ramp_grade`; the seam probe rules how.
R8 THE CARRIED STRETCH INSIDE S (site 1: -129 is ribboned under the deck it rides, climbing at 12 %):
   a ROUTE end's carried way is cut at the end edge and its stretch inside S becomes a bridge stretch
   marked `deck_carry.END_TAG` — A3 rule 7's ONE site, `deck_stack._rewrite_ways` :636, extended to
   take the end fills' (ring, way) pairs; no ribbon, no #1935 bridge-ground run on it. The ground
   under S is otherwise untouched.
R9 THE SIDE (site 2's long edge; the brief's "bank, wall or grade"): BANK. A deck's side over lower
   ground gets nothing of its own; within the collar of an end it is banked 1:3 (14c (5): "the 1:3
   bank of 10-03e stays for the ramp's sides"). A WALL is not emittable (a heightfield has no
   outward retaining face; the wall families are inward cuts). GRADING the whole approach under the
   deck (an embankment back to the first pier or crossing) would bury a lower roadway wherever the
   author modelled none, and no witness in hand separates a span on piers from one on fill when the
   pack omits both — owner question Q1, default (a): not built.
R10 PUBLICATION: `pipeline/publication.py:887` landing rows gain kind `end` with the end's stations,
   y_e, G_e, gap, state / why, path kind, run; every non-GRADED end is listed there too. Plan and
   object stage unchanged (PLAN_VERSION stays 16).

## 3. Consumer census (08-30l): every reader of `Registries.landings` / `landing_runouts`, S and the ways

| consumer | ruling |
|---|---|
| `planar/deck_end_fill.py` (NEW) | R1-R5: the witness, shape only |
| `planar/landing.landing_regions` :241 | EDIT: call it after the deck landings and pad fills (refs unchanged), R6; pass 1 platforms before collars holds for `end` |
| `planar/landing.landing_cut` :507, `_to_road`, `_risers`, `fill_road`, `fill_riser`, `fill_bank` | unchanged: `FILL_KINDS` stays ("plate", "piers"); an `end` is no pad fill, mints no riser. VERIFY the lot under a platform is cut back |
| `planar/landing_runout` | EDIT: R7 (path-following strip; foot-shaped input). Its "ground ahead is held asks nothing" counts stand |
| `airport/ramp_feet` | unchanged (an end is not a model ramp foot); VERIFY no foot double-mints on an `end` landing |
| `model/platform.fill_levels` / `held_levels`, `is_landing_ref` | unchanged: `kinds=None` readers see `end` as a landing (`z_hi`); `FILL_KINDS` readers do not |
| `constraints/platform.landing_rows` :599, `platform_collar_rows`, `_bank_rows`, :143-203 | unchanged: generic over landings; VERIFY a block with no datum column counts `landings_no_datum` and holds nothing |
| `constraints/ramp_runout.landing_runout_rows` :341-478 | EDIT only if R7's ribbon vertices need the rows keyed by path distance |
| `constraints/road_ramp.py:1226`, `airport/road_ramp.py:776-785, :979-980` | VERIFY: the run-out is its own route, the ribbon's ramp withdrawn (R7); a road mouth on the platform takes `z_hi` as a ceiling only (#1577) |
| `constraints/pads.py:592`, `riser.py:65/158`, `group_level.py:141`, `platform.py:622/642` | unchanged: keyed `kind == "low_level"` |
| `planar/low_level`, `level_regions`, `low_extent`, `group_up`, `station_level`, `low_fill`, `storey_pad`, `cut_runout`, `covered_cut`, `channel*` | unchanged: they mint or read their own kinds; VERIFY `level_regions.py:255` (iterates every landing ref) skips `end` |
| `planar/platform.py:211` (`landings.clear()`), `model/registries.py`, `pipeline/capture_state.py`, `stage_code.py`, `O4_Step_Code.py`, `provenance_code.py` | unchanged; a new module joins the stage-code closure by import (no string name) |
| `airport/deck_stack._rewrite_ways` :636, `deck_carry.END_TAG`, `airport/bridge_ground.bridge_runs` | EDIT: R8 at the one site; trench / free / kept stacks identical |
| `classify/ribbon_mint.road_extent` :84 | unchanged (an attached deck stands at the airport); VERIFY the run lies inside the extent, else list `end_beyond_extent` |
| `classify/ramp_runout.py`, `classify/roles.py:752` | unchanged: `runout:` refs are roads already |
| `airport/bridge_end_state` | unchanged, reused (R5) |
| `planar/free_bridge`, `airport/bridge_stack`, `bridge_class`, `constraints/deck_stack` | unchanged: no stack is minted |
| `constraints/edge_deck.py:168/443` (`_held_levels`) | VERIFY it reads no `end` landing as a hard-deck level |
| `airport/riser_wall.py`, `sunken_ramp.py`, `constraints/foot_road.py` | unchanged (risers / feet of their own kinds) |
| `pipeline/publication.py:887`, `late_stage.py` | EDIT: R10 |
| object stage (`footprint_unit.seat_viaducts`, `rebake_plan`, `anchor_rule`, `placement_coherence`) | unchanged: the unit seats as today; `seat_feet_census --rebake-plan` far-end gaps are the measure |
| `o4_engine/imagery_follow.py`, `imagery_commands.py` | unchanged (read landings for imagery; VERIFY kind-agnostic) |
| core mesh / neighbour tile (guest piece) | unchanged; both EDDH sites are on +53+010: measure there |

Heightfield: every surface single-valued; the platform is ground at the deck's top beyond its edge,
the collar ground under and beside the deck.

## 4. Twins (`tests/auto_patch_v2/test_deck_end_fill2129.py`, synthetic, headless)
A unit with a level stub 6 m over its pad: one `end` landing at y 6, collar on four sides, run-out
at 5 % (ROUTE along a curved way; STUB straight); the same stub with a wall under its edge mints
nothing (`end_on_own_abutment`); a stub abutting a second deck of the frame is a joint; an end
within `BAND_M` of the lowest y is the old landing, byte-equal; a way without `layer` / `bridge`
is not carried; an end over airside / water / under a deck < `clearance_m` is listed; the carried
stretch inside S is `END_TAG`, no ribbon; a unit with no elevated end: registry byte-equal.

## 5. Gates
G0 (before terrain code, no build): `tools/harness/frames.py list ICAO`; recapture
   `venv/bin/python tools/v2_solve_replay.py --capture EDDH` (the round's capture was deleted;
   register the frame), and KEGE, BIKF, HECA, OTHH, KMCI, KDEN from existing frames where they are
   current. Print one row per end R3 finds (member, mid lat/lon, L, y_e, G_e, gap, ROUTE / STUB,
   state) and the `[free-bridge]` note for park_10 (F1). STOP and report to the master before
   coding if: site 1's end is not a GRADED ROUTE end on -129; site 2's S edge is a joint or carries
   its own abutment (then the owner's point is the SIDE, R9, and Q1 goes to the owner first); KEGE or
   BIKF show any GRADED end; any airport shows more than about 10 ends (the witness is too loose).
G1 `tools/v2_solve_replay.py --replay <EDDH capture> --from planar --verify --emit`, the predicted
   end table written first. Bars: platform vertices within [-0.09, +0.05] of solved block datum +
   y_e; run-out grade <= 5.5 % between stations; no infeasible or relaxed hard row added against the
   base replay; airside nodes identical to base (airside is king); `--probe-site
   53.630341269,10.009158852` and `53.633821283,10.009869078` printed.
G2 PROTECTION (replay, base vs arm, `--emit`): KEGE and BIKF — 0 `end` landings, emit node-identical,
   or every mover listed and <= 0.1 m; rebake plans diffed, not only bodies. HECA (10-03e's home, 3
   named landings `building4/landing*`), OTHH, KMCI, KDEN: existing landing and run-out refs and
   levels identical; new `end` landings listed per airport for the master. A KMCI change is never
   landed without the owner's word.
G3 CLOSING is the master's, at integration (RULINGS 2026-11-17r): both tiles, on the merged code,
   `build_airport.py EDDH --tile 53 9 --pack-copy` and `--tile 53 10 --pack-copy`, then
   `drawn_gate.py EDDH --tag T --site s1=53.630341269,10.009158852,60 --site
   s2=53.633821283,10.009869078,60 --against <control>`. Acceptance (drawn): at each site's end edge
   the ground one step out stands within +/-0.15 m of the drawn deck top; the road beyond descends at
   <= 5.5 %; no body of unit:12 MOVED; MOVED ground only inside the published platforms, collars and
   run-outs. If G0 ruled site 2 a SIDE: its bar is "listed, Q1 pending", said in the report's first
   line.
Replay-first evidence only from the lane; no full suite; run the twins of §4, `test_deck_stack1971`,
the landing / run-out twins, `test_no_airport_specific_code`, `tools/ratchets.py` (dupes, unused,
layers). CI registry gates as the brief names them.

## 6. Not verified (read before trusting)
- Which witness first drops park_10 in `_read_free_bridges` (no capture; F1 holds either way).
- That park_10 is in `viaduct_units` for a held block (F2 infers it from `building39/landing1`).
- Site 2's S edge (open, joint or abutment) and whether any way is carried there (F4).
- -129's tags inside S (`layer` 1 per the round; `bridge` unread) and the round's 13.6 / 15.33 /
  16.76 / 13.35 m figures (the guest patch reads -129 at 11.42-12.87 near site 1).
- R7 on a ribbon: `road_ramp_withdrawn_on_runout`'s exact trigger; whether a path-shaped strip
  passes `landing_cut`. R3's thresholds on real packs (G0's count is the check).
- KEGE / BIKF hold no elevated unit end (G0).

## 7. Owner questions (defaults applied)
Q1 A deck's SIDE standing over lower ground behind an end: (a, default) banked only within the end's
   1:3 collar, the span behind it stays open like a bridge; (b) fill the ground under the approach
   up to the deck back to the first pier, wall, lower floor or crossing road, capped at 100 m.
   Recommend (a) now; decide (b) at the EDDH read.
Q2 A graded end whose run-out would cross another road at grade inside the run (site 1: -12367 and
   -19283 pass 13-30 m W at 10.3 m): (a, default) the run-out yields — that road keeps its ground and
   the end is listed if the profile cannot clear it; (b) seed the crossing at the profile (A3 14f (3)).

## 8. Estimate
One Opus round, high: G0 about 0.5 h (captures 1-3 min each, mostly from frames), code + twins
3-4 h (new module about 250 lines, about 60 lines of edits at four sites), G1 / G2 replays about
1 h. Build-time impact: one outline pass per unit deck at the planar stage, expected < 0.5 s per
airport (< 1 % of the 60 s budget); state it measured from the replay's stage clocks. No lane tile
build; the master's two EDDH tiles close it.
