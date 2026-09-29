# Road-exit corridor — spec v2 (issue #100, RULINGS 2026-09-29r / 29u / 29y / 29ab / 29ae)

Spec author: Fable 5.1. v1 2026-09-29 on `claude/roadexitspec` (merged
f22dd963); **v2 2026-09-29 on `claude/roadexitspec2` from `origin/main`
0a31b5f0**, revised on lane roadexit100's attempt-1 findings (RULINGS
29ae; branch `claude/roadexit100` c6eb536a, closing build
`roadexit100_NLWF` body 3243486f024b, ledger 244b1b442e8b). Design only —
no engine edits. Implementer: the SAME lane, resumed on its branch,
attempt cap 2 (§5). What changed in v2 is listed in §0.

## 0. v2 delta (29ae)

| # | v1 said | attempt 1 measured | v2 rule |
|---|---|---|---|
| a | §3 attributed the 204 round-3 `within_shape` rows to unframed corridor vertices | frames were published and joined 107/107; the census priced framed road pairs at the ring-axis-tightened 2 % | v1 §3 was WRONG. The lane's `check_grade._route_cap_l` (routed road pairs read at the role's longitudinal cap) is an accepted instrument correction (29ae). §3.1 corrected; §1.4 rewritten. |
| b | the 0.6 m cut-back strip beside a band is a terrace (§1.3 (5)) | 17 cockpit cliffs across the strip, worst 3.91 m over 1.12 m at −14.3115266, −178.0698277 (`road_exit:4` beside zone2#0) | the corridor's OWN BANK spans the strip: the band is cut back by the bank-foot width, §1.1 (4) / §1.3 (5). |
| c | one-way mouth rows (`follows`) | 370 of 950 one-way rows unsettled after 3 lag rounds (worst 0.769 m on `roads.road_ribbon airside follower`); CYXY 643 of 5,388 | no one-way row touches the corridor: the mouth is bound TWO-WAY to its band-ring neighbours and to the first station; the band's own one-way rows from pavement are the only lag hop. §1.3 (1). |
| d | mint gate = band-exit step ≥ `cockpit.visual_m` | 14 corridors at CYXY (steps 0.58–2.40 m) | gate = a band-EXIT onto ground whose DRAPE from the band level would exceed the road cap by a visible amount within the cap's reach; never a sub-cap step. §1.2. |
| e | (lane assumption) 60 m in-band gap bridge | not law (29ae (iv)) | removed. Two exits 35 m apart are two mouths; the band between them is cut back per §1.1 (4) and stays a band. |
| f | acceptance read with `road_course_profile.py` top-5 | the top-5 were raw-DEM samples (28.2 % at s=1856 is the corridor's west END standing off the DEM); road −3 ON-PATCH reads **9.1 %** at s=1972, −14.311380, −178.069725 (base on-patch 9.0 % at s=2204) | §4 (1): the on-patch read (every window sample on the patch) plus the corridor-END bar (last station within `visual_m` of the DEM). The tool grows an `--on-patch` read (extend, do not fork). |
| g | — | `road_cross_section` 8 (max 0.43 m), `adjacent_ground_step` 2 (0.62 m), `hairline_pair` 16 vs 12, `strip_transverse` 1 (1.88 m) | attributed in §3.6; rules in §1.3 (1)/(6), §1.1 (4), §1.3 (7). |
 Beta 2 gates on this item (29y).

Inputs read: `gh issue view 100 --comments` (four lane reports);
RULINGS 29p (NLWF line), 29r, 29u, 29y, 29ab, 13ar, 08-12b ("a road's
own course is never terraced"), 08-30l; parked branches
`origin/claude/nlwfroad100-wip` 68f6abd1 and `origin/claude/nlwfroad100c`
02d99b50 (`git diff origin/main...origin/claude/nlwfroad100c -- Ortho4XP/src`);
closing patch `/tmp/harness/nlwfroad100c_NLWF.osm` (body b0d6c1f84315)
+ `.axes.json` + `/tmp/harness/nlwfroad100_base.osm`, both re-censused
with `tools/harness/census.py --rows-json --sites`; the round-3 replay
(`tools/v2_solve_replay.py --replay f/NLWF.pkl --from classify --verify`
on the nlwfroad100c worktree).

Law constants used below (file:line on main): `service_road`
longitudinal 0.080 / transverse 0.020 (`law/rulesets.toml:33`);
`groundside_cutback_m = 0.6` (`law/zones.toml:20`); `[cockpit] visual_m
= 0.5` (`law/emit.toml:136`); `edge_min_drop_m = 2.0`, `edge_grid_m =
5.0` (`law/emit.toml:767-768`); `road_half_width_m` = lane half-width +
cutback (`planar/terrain_edge.py:117-122`); census proximity knob
`SHARED_VERTEX_TOL_M = 0.5` (`LAW_TRUE_KNOBS['proximity_m']`).

---

## 1. The model

### 1.1 What a road-exit corridor is

A **road-exit corridor** is a ROAD FACE (role `service_road`, ref
`road_exit:<k>`) minted where a mapped OSM road (`Airport.osm_ways`,
`planar/terrain_edge.road_lines`) crosses the boundary of an
adjacent-ground band (`adjacent_ground:*` graded_strip region) and the
ground it steps onto is NOT the band's level. It is the road's own
cross-section from the **mouth** (the point where the road centreline
crosses the band boundary) outward along the road, for as long as the
road's grade cap needs to reach the terrain. Under 29r the corridor is a
ROAD, not ground: the groundside terrace law grades roads; zone 3's
"raw DEM" applies to ground beside the corridor, never to the corridor.

Geometry, per corridor:

1. **Axis** — the OSM way's own centreline from the mouth outward
   (chainage `s`, `s = 0` at the mouth). The corridor's axis IS the
   road's axis; it is published (§1.4).
2. **Ribbon** — the axis buffered by the road's lane half-width
   (`road_half_width_m` MINUS `groundside_cutback_m` = 4.0 m; the
   cutback is NOT part of the road face — §1.3), square-capped at the
   mouth PERPENDICULAR to the axis so the mouth cross-section is one
   band cross-section. ONE polygon per road piece OUTSIDE the bands: a
   road that leaves a band, climbs a hill and re-enters the same or
   another band is one corridor with two mouths. A road that re-enters
   a band and leaves it again has TWO corridors and the band between
   them stays a band (no gap bridge, 29ae (iv); the v1 "60 m" was a lane
   assumption). Where that in-between band is shorter than the road's
   cross-section it is the in-band pocket case (§1.2).
3. **Length** — from the mouth to the first station `s*` where the
   cap-limited profile meets the DEM: `|DEM(s*) − z_band| ≤ cap·s*`
   (cap 0.08), plus one `edge_grid_m` of run so the last station is on
   the DEM. `z_band` is the pre-solve estimate (nlwfroad100c
   `_band_level`: lowest pavement-edge DEM within the band's reach less
   `band_min_down · d`) — the solve owns the real level, the estimate
   only sizes the polygon; 25 % slack on `s*` is kept (round 3).
4. **Stand-off = the corridor's own bank** (v2, 29ae (i)). The
   corridor never shares a vertex with any band it does not exit, and
   shares vertices with the band it exits ONLY on the mouth
   cross-section. The stand-off is the band's cut-back from the corridor
   at the ONE derivation site (`planar/zones.zone_regions`' groundside
   cut-back, `zones.toml:20`; the lane's `road_exit_cutback` feeds it —
   keep), but its WIDTH is no longer the fixed 0.6 m: beside a corridor
   the band is cut back by the corridor's BANK-FOOT width,
   `w(s) = max(groundside_cutback_m + snap, |z_prof(s) − z_band(s)| /
   bank_slope)` with `bank_slope` 0.33 (`emit.toml:683`), `z_prof` the
   pre-solve centreline profile (§1.3 (3)) and `z_band` the band-level
   estimate at the nearest band point — sampled per station and buffered
   as a variable-width strip. The strip between the corridor edge and the
   band's cut-back edge is ground the mesh drapes at ≤ 1:3 — the same
   bank every patch edge gets from `emit/bank.py` (`bank_min_width_m` 5 m,
   `|z − DEM| / 0.33`), now spanning to the band instead of to the DEM.
   Attempt 1 measured the fixed 0.6 m strip at 17 cockpit cliffs (worst
   3.91 m over 1.12 m, 348 %); a 3.9 m difference needs 11.8 m of bank.
   In the runway's zone-2 half-width the difference is bounded by the
   strip ceiling (§1.3 (7)), so the cut never removes more strip than
   the corridor's clamped climb needs. The mouth box (lane: `half + cut`
   flat-capped, the part behind the mouth) is kept; its END edge is
   chamfered so the band ring's jog from the shared mouth edge to the
   cut-back line is one segment of length ≥ `weld_spacing_m` (1.0 m,
   `emit.toml:15`) — attempt 1's jog was 0.50 m, exactly the census
   hairline spacing (§3.6).
5. **Shore** — the corridor is clipped by the sea AND by the
   natural-shore wedge (`planar/zones.shore_wedge_m`, the wedges in
   `PlanarMap.natural_shore_wedges`) and a mouth inside a shore wedge
   is NOT minted (the road ends at the sea; the band's shore law
   governs there). A corridor vertex is a pavement vertex, and
   `constraints/water._natural_shore_pins` (water.py:164) never pins a
   pavement vertex to sea level — so a corridor that reaches the
   coastline is a sea wall by §37 (11) (§3.2). The corridor therefore
   never carries a coastline vertex and never shares one with a band.
6. **Airside** — the corridor is minted outside every airside cell
   (the round-3 `inside = bands ∪ paved` difference stays). Airside is
   king: no corridor vertex is an airside vertex.

### 1.2 When a corridor is minted

Gate (v2, 29ae (iii)): a corridor is minted ONLY where the road LEAVES
a band onto ground whose DRAPE from the band level would exceed the
road's cap. Read on the DEM along the road from the mouth, over the
cap's reach: the excess of the drape over the cap ramp,
`e = max_s (|DEM(s) − z_band| − cap·s)` for `0 < s ≤ s_reach`, where
`s_reach` is the first station at which `|DEM(s) − z_band| ≤ cap·s`
(or the road's end); the corridor is minted iff `e ≥ [cockpit]
visual_m` (0.5 m) — the road draped on the ground would stand a
visible amount steeper than 8 % somewhere. A step that the drape takes
inside the cap (`e < 0.5`), however large `|DEM(mouth) − z_band|` alone
reads, mints nothing: the road grades to the DEM under its cap by
itself (08-12b). The v1 gate (`|DEM(mouth) − z_band| ≥ visual_m`) minted
14 corridors at CYXY with steps 0.58–2.40 m; the lane reports `e` per
candidate on the CYXY replay and the bar is 0 corridors there (§4 (8)).
`z_band` at the mouth is the band's OWN level estimate (the lane's
`_family_levels`, keep); an estimate error is a report line, never a
mint. The §19 `edge_min_drop_m` (2 m) terrain-drop gate is not this
gate (round 2 measured it missing the west exit).

Two exit classes, one rule:

* the **terminal exit** (NLWF road −3 behind the terminal, mouths at
  −14.311341, −178.068402 east and −14.311628, −178.070913 west): the
  road leaves the runway/taxi zone-2 band onto a hill (DEM to 18.5 m,
  band ≈ 4.2 m);
* the **runway-end corner** (NLWF road −1 NE, past the 25 end,
  −14.310589, −178.060933): the road leaves the zone-2 band's end
  quadrant. This ALSO requires 29u (i): every adjacent-ground band
  vertex carries a band row — an abeam vertex the transverse row, an
  end-corridor vertex the end-skirt foot row, a corner-quadrant vertex
  the END ROW from the nearest pavement-end point (nlwfroad100c
  `constraints/zones._end_row`, one-way, `d` clamped to the zone-2
  half-width). Kept as landed; it is zone law, not road law.

**In-band pocket (29ab (1)).** Where the road, INSIDE the zones, crosses
from one band face to another of a different class (NLWF: the
taxi-lip pocket at 7.0 m into the runway zone-2 band at 4.04 m, 20 m
apart = 14.4 %), and the estimated step across that boundary is ≥
`visual_m`, the corridor EXTENDS inward across that boundary: the ribbon
is cut out of both bands (the same cut-back, §1.1 (4)), its vertices
carry the road's course cap (§1.3), each band stays mandatory-down from
its own pavement to the corridor's cut-back edge, and the two bands
terrace against each other across the cut-back strip beside the road,
never under it. Where the road is inside ONE continuous band, 13ar
applies unchanged: the road grades with the zone and no corridor
exists.

### 1.3 Rows

All rows are `service_road` rows; the generator is `road_exit`
(`constraints/__init__.GENERATORS`, registered after `road_ramp`).

1. **Course rows and the mouth (v2, 29ae (ii))** — for consecutive
   corridor stations along the axis (`road_within_shape` on the
   corridor's route frame, §1.4): `|z(s_{i+1}) − z(s_i)| ≤ 0.08 · Δs`,
   TWO-WAY among corridor vertices AND two-way between the mouth
   vertices and the first station. NO row touching the corridor is
   one-way (`follows`): the v1 one-way mouth hop and the one-way
   `road_within_shape` mouth pairs chained behind the band's own one-way
   rows (mouth follows pavement; corridor follows mouth) and the lag
   did not settle (370 of 950 rows after 3 rounds; CYXY 643 of 5,388).
   13ar ("the band is never lifted for the road") is kept by the band
   law itself, which is a HARD range `[lo, hi]` from the pavement
   (`zones.adjacent_ground`, one-way from pavement, `emit.toml:912`): a
   two-way mouth row can move the mouth only INSIDE its band, never
   above `hi`. The 29u lift (v284 8.06 m against a 3.9 m ceiling) came
   from §37 (6)'s ramp target + ceiling, which stays withdrawn (4), not
   from a two-way pair. ADDED: a **ring-continuity row** on each mouth
   vertex — `z(mouth) = (1 − t)·z(n₀) + t·z(n₁)` for its two band-ring
   neighbours `n₀, n₁` (t by ring chainage), two-way, generator
   `road_exit`, ruling `roads.road_exit mouth on the band ring` — so the
   corridor cannot notch the band ring at the mouth (attempt 1: the
   `road_exit:0` mouth vertices sat 0.61–0.62 m above their neighbours
   1.12 m away, the two `adjacent_ground_step` rows, §3.6). Lag: the
   band rows settle in round 1 (leaders = pavement, fixed from stage 1),
   the mouth and the corridor are two-way with them — one hop.
   `"roads.road_exit band follower"` is REMOVED from `one_way_rulings`
   (the `_end_row` head registration stays).
2. **Cross-section rows** — at each station the ribbon's vertices are
   within the transverse cap (0.020 · width) of each other: the
   corridor is a road, laterally flat. Round 3 fitted every corridor
   vertex to its OWN DEM (`with_road_ramp`: `keep.update({v: dem_z for v
   in exit_v − seam_v})`), which on a side-hill puts the two ribbon
   edges at different heights — the 41 `road_cross_section` rows
   (max 0.76 m) of §3.
3. **Fit target** — the corridor's soft target is the CENTRELINE
   profile, one value per station, applied to every vertex of that
   station: `z(s) = z_mouth + clamp(DEM_axis(s) − z_mouth, −0.08·s,
   +0.08·s)`, then once the profile has met the DEM, the DEM's
   centreline value clamped to 8 % between stations. The terrain is
   CUT or FILLED to that profile (29y): "the road climbs only at the
   road's maximum grade; the terrain is cut to support that grade".
4. **§37 (6) withdrawn on corridor vertices** — the groundside-road ramp
   target and its hard ceiling (`airport/road_ramp.with_road_ramp`,
   `constraints/road_ramp.road_ramp_rows`) do not apply to corridor
   vertices (they are what lifted the band edge). `road_coverage_join`
   (§37 (9)) is unaffected (it pins the coverage edge; the 29u read
   shows no effect) and stays.
5. **Bank strip (v2)** — the strip between the corridor's edge and a
   band's cut-back edge is ground (no face), of width `w(s)` (§1.1 (4)),
   which the mesh drapes at ≤ 1:3 between the two constrained edges:
   the corridor's own bank, not a terrace. The census `groundside_cutback`
   family prices pairs within its 0.6 + 1.0 + snap horizon
   (`check_grade.py:2932-2935`) report-only; any pair it finds reads
   ≤ 33 % (no cockpit cliff). Beyond the corridor's outer edge where no
   band is beside it, the emit bank (`emit/bank.py`) drapes to the DEM
   as for every patch edge; no zone-3 patch vertex outside the corridor
   moves (29r, read at the solve — §2 row 28).
6. **Band rows on the mouth** — the mouth vertices keep their band rows
   (`constraints/zones._context`: exit-seam vertices removed from
   `own_law`, kept in `member` — keep) and, at a runway end, their
   end-skirt foot row (`strips._end_foot_rows` — keep). The mouth
   cross-section is a BAND cross-section: its transverse slope is the
   band's, and the road's 2 % cross-section cap applies from the first
   station outward; the census `road_cross_section` family exempts a
   pair whose BOTH nids are mouth vertices (an instrument-scope
   correction of the same class as `_route_cap_l`; attempt 1's 8 rows
   are all mouth-adjacent, §3.6). Between the mouth and the first
   station the cross-section row is the road's.
7. **Runway strip envelope (v2)** — a corridor vertex inside a runway's
   zone-2 half-width KEEPS the strip tie (`strip_transverse`, the
   rise-side ceiling from the runway edge): v1 row 25's `tie_pop`
   exclusion is REVERSED for runway ties (airside is king; a road may
   not stand above the graded-strip envelope — attempt 1: 1.88 m over
   at 35.3 m from 07/25, −14.3113126, −178.0693735, `road_exit:4`).
   The profile target (3) is clamped to the strip ceiling at those
   stations and the terrain is cut (29y). The taxi-family tie exclusion
   of row 25 stays.

### 1.4 What it publishes

* **Route frame (29ab (2), corrected by 29ae)** — every corridor vertex
  (mouth included) is framed on the corridor's own axis as route
  `ROAD_EXIT_ROUTE_BASE + k` in `road_route_frame` (lane: `airport/
  road_ramp.road_exit_profile`; attempt 1 published and joined 107/107).
  The census reads a routed road pair at the ROLE's longitudinal cap
  (`check_grade._route_cap_l`, accepted 29ae) — v1's claim that the
  round-3 rows were unframed was wrong: they were framed and priced at
  the ring-axis-tightened 2 %. The `road_exit_axes` sidecar key (the
  axis polyline per corridor, for the replay read and the profile tool)
  is still owed.
* **`station_caps`** — the corridor's stations at 0.08 (round 3
  already published 51; keep).
* **Report** — `road_exit` count, per-corridor mouth lat/lon, step,
  length, class (terminal exit / runway-end corner / in-band pocket),
  in the build log and the replay read (`overlay.ROAD_EXITS`).
* **Frames** — the NLWF capture used is registered in
  `docs/frames.jsonl` (the nlwfroad100c branch added rows; keep).

---

## 2. Consumer census (owner ruling 2026-08-30l)

Every reader of the geometry the corridor touches, one ruled
interaction per row. File:line on `origin/main` 864df50c unless marked
(c) = nlwfroad100c 02d99b50.

| # | Reader | Where | What it reads | Ruled interaction |
|---|---|---|---|---|
| 1 | Zone derivation | `planar/zones.zone_regions` (cut-back from groundside pavement, `zones.toml:20`) | bands minus groundside pavement + 0.6 m | THE stand-off mechanism: corridors (minus mouth discs) are fed here as groundside pavement. Bands are cut back 0.6 m from the corridor everywhere except the mouth. Nothing else subtracts bands from corridors. |
| 2 (v2) | Corridor derivation | `planar/overlay.build_arrangement` (c: `road_exit_corridors` after `zone_regions`, regions role `service_road`, kind `cell`) | zones, cells, DEM, road lines, water | Order: zones → corridors (mouths from the UNCUT band boundary) → band cut-back re-applied with the corridors at the BANK width → regions. v2: the 60 m gap bridge (`_GAP_BRIDGE_M`) is deleted; the mouth box end is chamfered (§1.1 (4)). |
| 3 | Terrain edge / §19 | `planar/terrain_edge.clip_to_terrain_edge`, `_road_barriers` (:198-215, road half-width incl. cutback), `road_half_width_m` (:117) | road lines as barriers to the terrain-edge clip; `edge_min_drop_m` | The corridor is a road: it is a barrier like any road ribbon. The 2 m drop gate is NOT the corridor's mint gate (§1.2). The lane half-width used for the corridor ribbon is `road_half_width_m − groundside_cutback_m`. |
| 4 | Zone bands (transverse) | `constraints/zones.zone_bands`, `_context` (`member`, `own_law` :326-335 (c)), `_found`, `strip_transverse` | every graded_strip ring vertex; road-role vertices in `own_law` are exempt from the band | Mouth vertices: banded (in `member`, removed from `own_law`) — keep round 3. Corridor vertices off the mouth: NOT graded_strip vertices (the band is cut back), so no band row. In-band pocket vertices: corridor vertices only (the ribbon is cut out of the bands). |
| 5 | End row | `constraints/zones._end_row` (c :460-505) | runway zone vertices past the end with no abeam/taxi reference | Keep (29u (i)). A mouth vertex at a runway-end corner carries it. |
| 6 | End-skirt feet | `constraints/strips._end_foot_rows` (:399-412 (c)) | strip ring vertices not pavement, not wall | Keep the round-3 amendment: an exit-seam (mouth) vertex is NOT pavement here. |
| 7 | Natural-shore pins | `constraints/water._natural_shore_pins` (:142-185; `ids -= set(vw.pavement_vertices)` :164) | natural-shore region ring vertices within snap of the sea | A corridor vertex is pavement and never gets the pin. RULE: the corridor is clipped by the sea + shore wedge and no mouth is minted inside a wedge (§1.1 (5)) so no band shore vertex is ever a corridor vertex. Twin: every band vertex within snap of the sea is pinned at 0.0 with corridors present. |
| 8 | Shore wedge / verdict | `planar/zones.shore_declarations`, `shore_region`, `shore_wedge_m`; `constraints/zones._in_wedges` (:434-445) | natural-shore wedges over the band | Unchanged (both sidecars: 21 `shore_edges`, 2 `natural_shore`, "natural by default"). The corridor is subtracted from the wedge's area only where it lies outside the wedge — i.e. never; see row 7. |
| 9 | Groundside road ramp | `airport/road_ramp.road_ramp_targets`, `with_road_ramp` (:770-860 (c)); `constraints/road_ramp.road_ramp_rows` (§37 (6)) | groundside road vertices: ramp target + hard ceiling from the airside contact | WITHDRAWN on corridor vertices (29u interventional read). Corridor vertices carry §1.3 rows instead. The per-vertex DEM `keep` of round 3 is replaced by the centreline profile target. |
| 10 | Coverage-edge join | `constraints/road_ramp.road_join_rows` (§37 (9)) | pinned vertices at the patch coverage edge | Unchanged; a corridor ending at the coverage edge is pinned like any road (R3 sidecar `road_coverage_join` 1 entry at −14.31049615, −178.06053556, 8.13 m — the NE corridor's far end). |
| 11 | Airside contact | `constraints/road_ramp.road_contact_rows` (§37 (10) (1)) | road END within `contact_reach_m` of an airside edge | A corridor's mouth is a band edge, not an airside edge: no contact row. |
| 12 | Road ribbon / lateral | `constraints/roads.*` (`road_family_roles`, ribbon rows, `roads.road_ribbon airside follower`), `road_profile` pass (`station_caps`) | every `service_road` face | The corridor IS a service_road face with a route: cross-section rows and station caps apply as to any road. Its axis is the OSM way (row 16). |
| 13 (v2) | One-way rulings | `law/emit.toml [design] one_way_rulings` (:911-925); `solve/design_roles.py:128-132`; applied `solve/design.py:448, 522-535` (exact match on the head, the text before " ("); `model/constraints.py:76-82, 164-170` | a `follows=` row is one-way ONLY if its head is registered; else `follows` is ignored and the row is TWO-WAY | v2: `"roads.road_exit band follower"` is REMOVED (no row touching the corridor is one-way, §1.3 (1)); the `_end_row` head stays registered (lane did). Staged solve: any `follows` row is dropped from stage 1 (`design.py:474-476`). |
| 14 | Precedence / weld | `constraints/precedence.view`, `planar/weld.weld_cells` | overlapping regions, shared vertices | `service_road` vs `graded_strip` never overlap (row 1). Mouth vertices are shared by construction (the ribbon's square cap coincides with the band boundary segment). |
| 15 (v2) | Census `groundside_cutback` | `tools/check_grade._check_groundside_cutback` | road ring vertex vs nearest zone vertex across the strip, report-only, `cutback_intent_q97` | Pairs across the bank strip within the horizon; with the bank-width cut-back (§1.1 (4)) every such pair reads ≤ 33 % — no cockpit cliff (attempt 1: 22 rows, 17 cliffs, worst 3.91 m over 1.12 m). |
| 16 | Census `within_shape` axis lookup | `tools/check_grade.py:823-845` (`_road_frame_by_nid`), `:2253-2340` (route reading), `:2342-2378` (`_xsec` ring-axis fallback, ≥ 45° = transverse at 0.02·d) | route reading iff BOTH nids are framed in `road_route_frame`; else the ring's min-area-rect axis | Frame every corridor vertex on the OSM route (§1.4). Bar: 0 `within_shape` rows ≤ 8 % on corridor faces. |
| 17 | Census `hairline_pair` | `_check_hairline_pair` (:7519), proximity `SHARED_VERTEX_TOL_M` 0.5 | an emitted vertex within 0.5 m of a foreign edge it does not lie on; segments < 0.5 m | With the cut-back (0.6 m + snap) as the ONLY stand-off and no core neck, no corridor outline vertex lies under 0.6 m from a band edge except the shared mouth vertices. Bar: hairline count = base (12). |
| 18 | Census `sea_wall` | `_check_sea_wall` (:6860), `stamp_sea_wall_tears` | ring edges with both vertices on declared `shore_edges` above water | Row 7 makes a corridor shore edge impossible. Bar: 0. |
| 19 | Census `adjacent_ground_step` | `_check_adjacent_ground_steps` (:2845) | consecutive welded pair of one zone ring, step ≥ `visual_m` and grade ≥ cliff | The band ring beside a corridor now has the cut-back edge; the mouth is the only shared point. Row 7 removes the shore case. NOTE the row's reported lat/lon is not the site (§3.4). |
| 20 | Cockpit critical | `census.py --sites`: sim-visible rows (`visibility_m` 0.05) by family; "visual" = not-adjudicated sim-visible rows | hairline + sea_wall in round 3 (49 + 2 = 51; base 12 + 0) | Rows 17–18 return it to 12. |
| 21 | Emit / sidecar | `emit/osm_adapter.py` (sidecar writer), `road_route_frame`, `station_caps` | per-face roles, refs, axes | Adds the corridor axis entry (row 16); ref `road_exit:<k>` kept so `road_exit_vertices` readers (rows 4, 6, 9) find the faces. |
| 22 | Verify (engine) | `verify/*` families in `NLWF.report.json` `verify.by_family` | same families pre-emit | Same bars as the census; `runway_*` DEFECT families stay zero. |
| 23 | Frames / instrument | `tools/road_course_profile.py` (c, INDEX row), `docs/frames.jsonl` | the course grade over 10 m | The acceptance instrument (§4). |
| 24 | `road_within_shape` (roads) | `constraints/roads.py:194-316` | ALL pairs of every road ring, two-way `Diff` at 8 % (2 % transverse); only cross-route/merged pairs touching an airside vertex become the one-way `roads.road_ribbon airside follower` | v2: mouth↔corridor pairs are TWO-WAY (the lane's one-way mouth pairs are reverted); the band's hard range and the ring-continuity row (§1.3 (1)) hold the mouth. |
| 25 | `strip_transverse` tie population | `constraints/zones.py:364-379` (`tie_pop`), rows `:545-640` | every vertex of every non-runway-family face within the zone-2 half-width of a runway edge | v2: corridor vertices inside a RUNWAY zone-2 half-width KEEP the strip tie (§1.3 (7); attempt 1 measured 1.88 m over it); the taxi-family tie exclusion stays. |
| 26 | Groundside body datum plane | `solve/design.py:614-635`; `solve/rows.py:498, 636` | every groundside pavement body gets a least-squares DEM plane (mean + tilt) at `detached_mean` 1.0 (`emit.toml:485`) | The corridor is a groundside body and would take a DEM plane against its profile target (§1.3 (3)). RULE: bodies made only of `road_exit:*` faces carry no plane datum; a corridor merged with an OSM route cell is one body whose plane is the route's (unchanged). |
| 27 | `ground_datum_vertices` | `solve/design_ground.py:37-99`; rows `solve/design.py:425-434` | ground-role boundary vertices minus pavement vertices, weak `z = DEM` at 3.0 (`emit.toml:393`) | Mouth vertices are pavement → the band loses its DEM datum there (correct: the mouth is banded). Band edges now shared with the corridor stop being map-boundary edges (the flood seed, `design_ground.py:60-76`): with the cut-back model (row 1) the band's cut-back edge remains a boundary edge — verify in the twin (b). |
| 28 | Patch bank (emit) | `emit/bank.py:1-40`, `daylight_feet` :272, `with_bank` :656 | every patch-boundary ring gets a foot ring on the DEM at max(`bank_min_width_m` 5 m, |z−DEM|/0.33) | The corridor's outer sides and far end ARE patch boundary: the mesh blends them to the DEM over a ≥ 5 m 1:3 bank, like every patch edge — the "cutback terraces to the DEM" of 29r is this bank, not a vertical wall. SPEC-AUTHOR NOTE for the 29r twin ("the ground 1 m beyond its cutback is DEM"): read it at the SOLVE (no patch vertex outside the corridor moves, the corridor's outer vertex is the last non-DEM one); at the mesh, the bank foot ≥ 5 m out is the first DEM sample. |
| 29 | `weld_to_shore` (emit) | `emit/osm_adapter.py:658+`, `pipeline/build.py:1170-1178` | every emitted vertex within 0.5 m of `shore_edges` is snapped to it or dropped, role-agnostic | With §1.1 (5) no corridor vertex is within the shore wedge, so none is snapped. Twin (c) asserts it. |
| 30 | `road_route_frame` / `_osm_levelled` | `airport/road_ramp.py:544-634`; `airport/road_profile.py` (`core_profiles` :545-595, `_osm_levelled`) | (route, s, t) per road-family ring vertex from an OSM-levelled way, else the face axis | UNVERIFIED by the scout whether the exit way passes `_osm_levelled`; step 3 of §5 reads `road_route_frame` coverage of `road_exit:*` vertices on the replay before anything else. |
| 31 | Pass A snap-round | `planar/overlay.py:252, 281` (`unary_union(..., grid_size)` over all base-region rings) | global noding of every base region | Corridor lines near airside cells can move noded vertices by up to half a grid cell: airside identity is no longer a function of the airside alone. Bar 8 (CYXY airside identical) and NLWF `airside_value_delta` 0 vs base guard it. |
| 32 | `_claiming_region` | `planar/overlay.py:395-432` | overlap / containment / `authority_rank` (`precedence.toml:21`, `service_road` 10th) | The corridor may overlap groundside cells (route cells, lots, pads): it wins over `service_junction` / `groundside_pavement` / `parking_lot`, loses to `apron` / `building` / airside. RULE: the corridor is also subtracted from every groundside CELL (a road that is already a cell needs no corridor). |
| 33 | `strip_seam_tear` | `tools/check_grade.py:5464+`; `src/auto_patch/strip_seam_law.py:120-192` | band↔band pairs on different ways < 6 m; floor 1 m when the connecting segment stays in the graded domain (`service_road` IS in `STRIP_SEAM_GRADED_ROLES`) | Two bands terracing against each other across the corridor's cut-back (in-band pocket, §1.2) are priced at the 1 m floor. Bar 5 keeps it 0; if a lawful pocket terrace > 1 m appears, that is a ruling question, not a tuning knob. |
| 34 | Cockpit classifier | `tools/check_grade.py:11433-11540`; `rolled_on_roles` `law/tables.py:569`; `cockpit_in_view` :11398 | MOTION needs both roles rolled-on; VISUAL needs > 0.5 m, a welded step or a > 33 % cliff, in view | `service_road` is not rolled-on: a corridor row is never MOTION. Corridor↔band rows are VISUAL only over 0.5 m and > 33 %. |
| 35 | `road_contact_rows` reach | `airport/road_ramp.py:184-232`, `contact_roles` :141; `emit.toml:233` `contact_reach_m` 15 | a road END within 15 m of an airside VALUE face edge | A corridor's far end within 15 m of taxiway/apron pavement takes a one-way contact row (lawful; the band is not a value role). |

(Rows 24–35 come from the read-only scout sweep of this round; its
"could not verify" list is carried into §5 step 3 and §6.)

---

## 3. Attribution of the round-3 regressions (29ab (3))

Base `nlwfroad100_base` (13 rows / 1 adjudicated) vs round 3
`nlwfroad100c_NLWF` (311 / 247), both censused 2026-09-29 with
`tools/harness/census.py --rows-json --sites`.

### 3.1 The families

| family | base | round 3 | roles (round 3) |
|---|---|---|---|
| `within_shape` | 0 | 204 | `service_road|service_road` ×204, caps 2.0–3.3 % on 177, 5.5–7.9 % on 27; 27 rows > 8 %. v2 CORRECTION (29ae): the vertices WERE framed; the census priced routed pairs at the ring-axis-tightened cap. Instrument, fixed by `_route_cap_l`. |
| `road_cross_section` | 0 | 41 | corridor faces −10023 ×17, −10019 ×13, −10020 ×7, others 4; max 0.76 m |
| `hairline_pair` | 12 | 49 | +23 `graded_strip|service_road` "ring", +12 `service_road|service_road` "short", +1 svc "shore", +1 gs|gs "short" |
| `groundside_cutback` | 0 | 13 | stamped `cutback_intent_q97`, worst 0.59 m — lawful |
| `sea_wall` | 0 | 2 | see §3.2 |
| `adjacent_ground_step` | 0 | 1 | 2.72 m over 1.57 m, see §3.4 |
| `pad_airside_renode` | 1 | 1 | unchanged |

### 3.2 `sea_wall` 0 → 2 — NOT a shore verdict change

Both sidecars carry the same shore: `shore_edges` 21, `natural_shore`
2, and both build logs read "shore decision (29a): 1 contact(s):
natural by default 1" at −14.312505, −178.070133. The two rows are the
corridor at the coast:

* **Row A** `service_road|service_road`, way −10017 = shapeID 16 =
  `road_exit:3` (road −3 west exit), edge from node −420 (2.78 m),
  22.1 m long, 2.87 m above water, at −14.312738, −178.072010. The
  corridor polygon was clipped by the water (`blocked = inside ∪
  water`), so its outer edge IS the declared shore linework (2 of its 6
  vertices stand on `shore_edges`). Corridor vertices are pavement, and
  `_natural_shore_pins` skips pavement (`water.py:164`), so they sit on
  the DEM's last on-land post: a pavement edge at the water above water
  level is a sea wall by §37 (11) (2)/(3)/(5).
* **Row B** `graded_strip|graded_strip`, way −10011 =
  `adjacent_ground:runway:2:zone2#0`, 88.9 m at 1.48 m mean, from node
  −301 at −14.3127129, −178.0718069. In base the same vertex (node
  −289) is at **0.00 m** (natural-shore pin); in round 3 node −301 is
  at **2.96 m** and is SHARED with `road_exit:3` (the corridor's mouth
  welded to the band at the shore). As a corridor vertex it became a
  pavement vertex, lost its sea-level pin (`water.py:164`), and the
  band/exit rows put it at 2.96 m; the band's shore edge from it now
  stands above the water → a sea wall. Base zone2#0 shore vertices: 7
  at 0.00; round 3: 6 at 0.00 and −301 at 2.96.

Rule that removes both: §1.1 (5) — clip the corridor by the sea plus
the shore wedge and mint no mouth inside a wedge.

### 3.3 Critical visual 12 → 51

"Visual" in `census.py --sites` is the sim-visible, not-adjudicated
rows: base 12 = the 12 hairline rows (4 gs|gs "shore on_the_edge", 8
"above_degenerate_floor" ring/short rows — the unmeshable hairlines the
issue thread names). Round 3: 49 hairline + 2 sea_wall = **51**. The
+37 hairlines:

* **23 `graded_strip|service_road` "ring"** rows at d = 0.494–0.500 m
  (magnitude 0.001–0.006 m; two at 0.27 and 0.34 m). A corridor outline
  vertex 0.5 m from a band edge. This is the round-3 stand-off
  construction: `bands.buffer(0.6, mitre).difference(mouths)` subtracted
  from the ribbon leaves, at every place the outline turns from the
  welded mouth to the offset line, a vertex that the mitre/disc
  geometry puts at ~0.5 m from the band edge — exactly the census's
  proximity knob (`SHARED_VERTEX_TOL_M` 0.5), so it reads as "laid
  beside". The 0.27 / 0.34 m rows are the `_one_ribbon` core neck
  (0.25 × half-width) crossing the stand-off at −14.311725,
  −178.063580 and −14.311531, −178.069902.
* **12 `service_road|service_road` "short"** rows at the SAME
  coordinates as ring rows (e.g. −14.311093, −178.066477; −14.311337,
  −178.068359): the 0.5 m outline segment from the shared mouth vertex
  to the offset vertex — a segment under the identity spacing.
* 1 svc "shore on_the_edge" (row A's corridor at the water) and 1 extra
  gs|gs "short" (a band ring re-noded at a mouth).

Rule that removes them: §1.1 (4) — the stand-off is the band's own 0.6 m
(+ snap) cut-back from the corridor, and the corridor outline is the
plain lane ribbon (no buffer subtraction, no core neck). Bar: hairline =
base 12, visual = 12.

### 3.4 The 2.72 m `adjacent_ground_step`

The census row prints lat/lon −14.3115574, −178.0666656, but NO patch
vertex lies within 6 m of that point in either patch; the row's
`site_m` is [[645.34, 12.36], [645.33, 13.94]] — ~645 m east of the
layout origin, and the printed lat/lon is the origin's neighbourhood,
not the site (instrument defect: `_check_adjacent_ground_steps` row
lat/lon; file as a `bug` `area:harness` issue, not fixed here). The
pair, found by searching the round-3 patch for a graded_strip vertex
and a corridor vertex 1.57 m apart with Δz 2.72:

* node −346, way −10011 (zone2#0), **0.00 m** (natural-shore pin), at
  −14.3113508, −178.0609526;
* node −347, ways −10011 AND −10022 (`road_exit:0`, the road −1 NE
  corner corridor), **2.72 m**, 1.57 m away.

This is the NE-corner corridor's MOUTH minted 1.57 m from the coastline,
inside the natural-shore wedge: the mouth vertex is a pavement vertex
(no sea pin), banded from the 25 end, and its ring neighbour is pinned
at sea level — a 173 % cliff on the band's own ring. Same mechanism as
§3.2 row B; same rule (§1.1 (5)).

### 3.5 The remaining course residuals (for completeness)

* Road −3 east mouth 14.4 % at −14.311371, −178.068277: the in-band
  pocket (taxi lip 7.0 m vs runway band 4.04 m over 20 m) — §1.2 in-band
  pocket rule.
* Road −1 NE corner 8.4 % at −14.310589, −178.060933: corridor
  triangles standing on two seam vertices, priced per vertex pair
  (round 3 bounded on the seam-LINE distance). Under §1.3 the course
  rows are per station along the axis, and the profile target is the
  centreline's; the plane over a thin mouth triangle then climbs at the
  station grade.
* `road_cross_section` 41: §1.3 (2)/(3) (per-vertex DEM fit removed) — v1 reading, superseded by §3.6 for attempt 1.
* Lag not settled (1.509 m on the follower chain): §1.3 (1).

### 3.6 Attempt 1 (`roadexit100_NLWF`, body 3243486f024b) — measured on the patch

Censused with the lane's corrected `check_grade` (from its worktree):
`groundside_cutback` 22, `hairline_pair` 16, `road_cross_section` 8,
`adjacent_ground_step` 2, `strip_transverse` 1, `pad_airside_renode` 1
(main's uncorrected census adds 127 `within_shape` + 12
`road_cross_section`, all the 2 % reading). Five corridors:
`road_exit:0` (way −10017, mouth −14.311761, −178.063885, step −1.55 m,
39 m), `:1` (−10018, −14.311886, −178.064851, −0.84 m, 26 m), `:2`
(−10020, −14.311098, −178.066520, +1.75 m, 181 m), `:3` (−10021, NE
corner, +5.15 m, 57 m), `:4` (−10019, −14.311341, −178.068401, +5.69 m,
291 m).

* **Road −3 on-patch: 9.1 %** at s=1972, −14.311380, −178.069725 (and
  8.9 / 8.8 % at s=1970 / 1946), inside `road_exit:4` — the course
  bar is MISSED on the patch by 1.1 %, not proven-unknown. The 28.2 %
  at s=1856 (−14.311613, −178.070728) is a PATCH-EDGE window: the
  corridor's west end stands ~2.8 m off the raw DEM — the corridor
  length (sized on the pre-solve estimate) ended before the profile met
  the ground. Base on-patch: 9.0 % at s=2204 (the sawtooth remnant);
  base patch-edge 41.7 % at the east mouth. Road −1 on-patch 7.7 %
  (base 15.0 %): PASS.
* **`groundside_cutback` 17 cliffs**: all `road_exit:4` (−10019) beside
  zone2#0 (−10011) and the taxi band zone2#1 (−10013) — 3.91 m / 1.12 m
  at −14.3115266, −178.0698277, 2.44 m / 1.01 m at −14.3116260,
  −178.0702633, 2.19 m / 1.00 m at −14.3111696, −178.0686459 (taxi
  band) … — the corridor climbing the hill inside a 0.6 m strip of a
  band held mandatory-down. Rule: §1.1 (4) bank-width cut-back.
* **`adjacent_ground_step` 2** (0.61 / 0.62 m over 1.12 m, 55 %): ring
  pairs −334→−335 and −336→−337 of zone2#0 at −14.3117525,
  −178.0639002 / −14.3117616, −178.0638863, i.e. the two mouth vertices
  of `road_exit:0` (3.61 / 3.59 m) against their band-ring neighbours
  (3.00 / 2.97 m): the corridor notched the band ring at the mouth
  within the band's range. (The census prints −14.3115617, −178.0668698
  for both — issue #107.) Rule: the ring-continuity row, §1.3 (1).
* **`road_cross_section` 8** (0.24–0.43 m over 3.0–8.1 m, 6.7–8.2 %):
  `road_exit:1` ×5 at −14.31189, −178.06485 (its mouth), `road_exit:2` ×2
  at −14.31110, −178.06650 (its mouth), `road_exit:0` ×1 at −14.31178,
  −178.06390 (its mouth) — every row is mouth-adjacent: the mouth
  cross-section carries the band's transverse slope (the road crosses
  the band boundary obliquely), which the road's 2 % cap cannot meet.
  Rule: §1.3 (6) — the mouth is a band cross-section; pairs with both
  nids on the mouth are the band's, and the corridor's cap starts at the
  first station.
* **`hairline_pair` 16 vs 12**: the 12 base rows are unchanged (4 gs|gs
  "shore on_the_edge", 8 above-floor). The +4: `graded_strip|service_road`
  "ring" at d 0.496 m (−14.3118791, −178.0648502, node −323 of
  `road_exit:1`'s mouth against −324 of the band ring) and d 0.500 m
  (−14.3110927, −178.0664816, `road_exit:2`'s mouth), plus the two
  `graded_strip|graded_strip` "short" 0.50 m segments at the same
  points: the band ring's JOG from the shared mouth edge to the cut-back
  line is 0.50 m long — exactly the hairline spacing. Rule: the
  chamfered mouth-box end, jog ≥ 1.0 m (§1.1 (4)).
* **`strip_transverse` 1** (1.88 m over 35.3 m, `runway|service_road`,
  −14.3113126, −178.0693735): a `road_exit:4` vertex inside 07/25's
  zone-2 half-width, 1.88 m above the strip's rise ceiling — the v1 row
  25 exclusion let the corridor leave the strip envelope. Rule: §1.3 (7).
* **Lag**: 370 of 950 one-way rows unsettled after 3 rounds, worst
  0.769 m on `roads.road_ribbon airside follower`: the chain, §1.3 (1).
* **CYXY**: 14 corridors minted (steps 0.58–2.40 m), runway bows
  identical: the gate, §1.2.


---

## 4. Pre-registered acceptance

Instrument: `tools/road_course_profile.py PATCH.osm --capture
<scratchpad>/f/NLWF.pkl --ways -3,-1` (step 2 m, window 10 m). Census:
`tools/harness/census.py PATCH.osm --sites`. ONE closing build
`build_airport.py NLWF` (tag `roadexit_NLWF`), base arm
`nlwfroad100_base` (main d5173ad6 census 13/1) re-cut on the merge base
if main has moved.

1. **Course, read ON-PATCH (v2)**: `tools/road_course_profile.py
   --on-patch` (extend the tool: a window counts only when EVERY sample
   of it lies on the patch; print the worst on-patch window and,
   separately, the worst PATCH-EDGE window) — road −3 (both mouths, the
   in-band pocket at −14.311371, −178.068277, and the whole of
   `road_exit:4`, attempt 1: 9.1 % at s=1972) and road −1 (NE corner)
   read ≤ 8.0 % over any 10 m on-patch window. Corridor END bar: the
   last station of every corridor stands within `visual_m` (0.5 m) of
   the DEM, so the patch-edge window at a corridor end reads ≤ 8 % +
   0.5 m/10 m (attempt 1: 28.2 % at s=1856, the west end 2.8 m off).
2. **Census** (with `_route_cap_l`, now the instrument): LAW-TRUE ≤
   base + lawful corridor rows, where the ONLY admitted new rows are
   `groundside_cutback` (stamped `cutback_intent_q97`, every row ≤ 33 %)
   and `road_cross_section` on non-mouth pairs ≤ 0.05 m; `within_shape`
   0; `adjacent_ground_step` 0; `strip_transverse` 0; `hairline_pair` =
   base (12); adjudicated ≤ 1 (base).
3. **`sea_wall` 0**; every band vertex within the snap margin of the sea
   at 0.00 m (7 on zone2#0 as in base).
4. **Shore** at −14.312505, −178.070133 "natural by default" in the
   build log; `natural_shore` 2 entries in the sidecar.
5. **Runway families zero**: `runway_step`, `runway_end_skirt`,
   `runway_crown` (verify DEFECT families), `strip_transverse`,
   `adjacent_ground_step` 0, `strip_seam_tear` 0.
6. **Critical**: motion 0; visual ≤ 12 (base) — attempt 1 read 33 (17
   `groundside_cutback` cliffs + 16 hairlines).
7. **Lag settled**: the build log reports the one-way set settled (no
   `LAG NOT SETTLED` on `roads.road_exit`); status `optimal`.
8. **CYXY**: `v2_solve_replay.py --replay CYXY --from classify --verify`
   fix vs base: runway bows identical, airside `airside_value_delta` 0
   vs the reference; verify rows ≤ base; **0 corridors minted** (the
   lane prints `e` per candidate; a candidate with `e ≥ 0.5` is a
   ruling question, reported with its site, not a mint); one-way set
   settled.
9. **Twins** (`tests/auto_patch_v2/test_v2rwycorner.py` extended, plus a
   new `test_v2roadexit.py`): (a) 29r — a road exiting a band onto a
   5 m higher synthetic DEM reads ≤ 8 % along its course and the ground
   1 m past the corridor edge is DEM; (b) no corridor outline vertex
   (other than mouth vertices) lies < `groundside_cutback_m` from a band
   edge; (c) a corridor that would reach the sea is clipped by the
   shore wedge and its band's shore vertices stay pinned at 0.0; (d)
   the corridor axis is in the sidecar and the census prices a 7 %
   corridor pair as longitudinal; (e) the end-row and mouth-seam twins
   of nlwfroad100c (12) still pass; (f) suite green (`-n0
   tests/test_qt_*.py`, then the rest).

---

## 5. Implementation plan v2 (the same Opus lane, resumed on `claude/roadexit100`, attempt cap 2 — this is attempt 2)

Synthetic-first; replay before the build; ONE NLWF build at the close.
Keep from attempt 1: derivation (lane ribbon, uncut-band mouths,
shore-wedge clip, `road_exit_cutback` feed, in-band pocket walk),
`road_exit_profile` (profile target + route frame), `_end_row` head
registration, plane-datum exemption (row 26), `_route_cap_l`,
`road_exit` report lines, frames row.

1. **Derivation** — delete `_GAP_BRIDGE_M` and the bridge; cut-back
   width per station `w(s)` (§1.1 (4)) fed to `road_exit_cutback`;
   chamfer the mouth-box end (jog ≥ 1.0 m). Twin (b) rewritten: no
   corridor outline vertex other than mouth vertices within
   `groundside_cutback_m` of a band edge; the band ring's jog segment
   at every mouth ≥ 1.0 m; and the strip width between corridor and
   band ≥ `|Δz_est| / 0.33`.
2. **Gate** — replace the `visual_m` step gate with the drape-excess
   gate `e` (§1.2); print `e` per candidate; CYXY replay: 0 corridors
   (bar 8); NLWF: the five attempt-1 corridors still mint (all have
   `e` ≥ 0.5 by construction of their steps — report `e` for each).
3. **Rows** — remove `follows` from `road_exit_rows` and from the
   `road_within_shape` mouth pairs (revert the lane's row-24 change);
   remove `"roads.road_exit band follower"` from `one_way_rulings`;
   add the ring-continuity row; restore the runway strip tie on
   corridor vertices and clamp the profile target to the strip ceiling
   (§1.3 (7)). Replay NLWF: log reads settled (no `LAG NOT SETTLED`),
   `--why-hard` empty, `strip_transverse` 0, `adjacent_ground_step` 0.
4. **Corridor end** — size the corridor so the last station reaches the
   DEM within `visual_m` (extend the run by stations until
   `|z_prof − DEM| ≤ 0.5` or the road/coverage ends); the coverage-edge
   join pin (row 10) at the far end is then consistent.
5. **Instrument** — `road_course_profile.py --on-patch` (worst on-patch
   window, worst patch-edge window, per corridor end `|z − DEM|`);
   INDEX row updated; the census `road_cross_section` mouth-pair
   exemption (§1.3 (6)) beside `_route_cap_l`, with its twin.
6. **Closing build** `roadexit100b_NLWF`; census (lane frame); profile
   on-patch; bars 1–8; frames row; #100 comment, site numbers first.
7. **Cap**: this is attempt 2. A missed bar in {1, 2, 6, 7, 8} parks the
   branch with an interventional read (`--drop-generator road_exit`,
   then the §2 row that owns it) and returns to the spec author.

## 6. Open items the lane resolves by reading, not by tuning (v1 list, still owed)

* Row 30: does the exit way pass `_osm_levelled`? If not, the corridor
  vertices are framed on the face axis and the census reads the ring
  axis — register the route explicitly.
* `wall_corridor_probe.py` / `wall_corridor_ramps.py` `ROAD_ROLES`
  include `service_road`: confirm a `road_exit:*` face is inert there
  (no wall corridor at NLWF; a HECA/LEMD replay corridor count of 0 is
  the check).
* `emit/bank.py` where a corridor side and a band side share a foot
  ring: read `with_bank` before the closing build.
* `[design] road = 3.0` (`emit.toml:444`): confirm it is the
  `preferred_z` weight the profile target binds with.
* The census `adjacent_ground_step` row lat/lon (§3.4): file the issue.
