# Road-exit corridor — spec (issue #100, RULINGS 2026-09-29r / 29u / 29y / 29ab)

Spec author: Fable 5.1, 2026-09-29, branch `claude/roadexitspec` from
`origin/main` 864df50c. Design only — no engine edits. Implementer: an
Opus lane, attempt cap 2 (§6). Beta 2 gates on this item (29y).

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
   (`road_half_width_m` MINUS `groundside_cutback_m`; the cutback is
   NOT part of the road face — §1.3), square-capped at the mouth so the
   band's own boundary is the mouth cross-section. ONE polygon per
   road piece: a road that leaves a band, climbs a hill and re-enters
   the same or another band is one corridor with two mouths.
3. **Length** — from the mouth to the first station `s*` where the
   cap-limited profile meets the DEM: `|DEM(s*) − z_band| ≤ cap·s*`
   (cap 0.08), plus one `edge_grid_m` of run so the last station is on
   the DEM. `z_band` is the pre-solve estimate (nlwfroad100c
   `_band_level`: lowest pavement-edge DEM within the band's reach less
   `band_min_down · d`) — the solve owns the real level, the estimate
   only sizes the polygon; 25 % slack on `s*` is kept (round 3).
4. **Stand-off** — the corridor never shares a vertex with any band it
   does not exit, and shares vertices with the band it exits ONLY on
   the mouth cross-section (the two mouth vertices and the band-boundary
   segment between them). The stand-off is NOT a subtraction of a
   band buffer from the ribbon (round 3, `bands.buffer(cutback)
   .difference(mouths)` + `_one_ribbon` core re-union — the source of
   the 37 new hairlines, §3.3). It is the SAME cut-back every
   groundside pavement already receives: `planar/zones.zone_regions`
   cuts every band back `groundside_cutback_m` (+ snap) from
   groundside pavement (`zones.toml:20`), and the corridor is fed to
   that cut as groundside pavement, MINUS the mouth disc (radius = lane
   half-width) so the exit band is not cut at the mouth. One derivation
   site (30l corollary (a)): the band is trimmed, the corridor stays one
   continuous ribbon by construction, no core neck, no severing.
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

Gate: the **band-exit step** at the mouth, `|DEM(mouth) − z_band| ≥
[cockpit] visual_m` (0.5 m) — the step a pilot sees — never §19's
`edge_min_drop_m` (2 m) terrain-drop gate (round 2: it missed the west
exit, estimate 1.8 m vs actual 2.4 m). Under the gate, the road drapes
from the band onto the DEM with no corridor (the step is invisible).

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

1. **Course rows** — for consecutive corridor stations along the axis
   (every corridor vertex projected to its chainage `s`, cross-section
   groups at one `s`): `|z(s_{i+1}) − z(s_i)| ≤ 0.08 · Δs`. Two-way
   AMONG corridor vertices. ONE-WAY only at the mouth: the first
   station follows the mouth vertices (`follows=(v,)`, ruling
   `"roads.road_exit band follower"` in `[design] one_way_rulings`),
   because the mouth vertices are BAND vertices whose level the band
   law alone sets (13ar; the band is never lifted for the road — the
   29u interventional read: `road_ramp` lifted v284 8.06 m against a
   3.9 m ceiling). Round 3 made EVERY corridor vertex a one-way
   follower of its nearest seam vertex; the replay reports the chain
   does not settle ("LAG NOT SETTLED after 3 of 3 rounds: 156 of 668
   one-way rows still move, worst 1.509 m on `roads.road_exit band
   follower`, leader v455 at −14.31108822, −178.06860417") — a 30–60
   vertex follower chain resolves one hop per lag round. Two-way
   course rows among corridor vertices settle in the same round as the
   mouth.
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
5. **Cut-back terrace** — the 0.6 m strip between the corridor's edge
   and a band's cut-back edge is ground (no face); the mesh drapes it
   as a terrace, priced report-only by the census `groundside_cutback`
   family (`_check_groundside_cutback`, stamped `cutback_intent_q97`).
   Beyond the corridor's outer edge, where no band is beside it, the
   ground 1 m past the edge is raw DEM (29r twin). No zone-3 ground
   outside the corridor moves.
6. **Band rows on the mouth** — the mouth vertices keep their band rows
   (`constraints/zones._context`: exit-seam vertices removed from
   `own_law`, kept in `member` — round 3, keep) and, at a runway end,
   their end-skirt foot row (`strips._end_foot_rows`: a strip vertex
   shared only with a road-exit face is the band's seam, not pavement —
   round 3, keep).

### 1.4 What it publishes

* **Sidecar road axis (29ab (2))** — the census prices a road pair as
  LONGITUDINAL only when BOTH its vertices carry a `road_route_frame`
  entry (`[lat, lon, route, s, t]`; published `pipeline/publication.py:
  495-506`, joined by 7-dp lat/lon `tools/check_grade.py:823-845`, used
  at `:2253-2340`); otherwise it falls to the ring's own min-area-rect
  long axis and prices any pair ≥ 45° off it as TRANSVERSE at 0.02·d +
  quant noise (`:2342-2378`, `grade_law.py:2865-2929`). Round 3's 204
  `within_shape` rows at 2.0–3.3 % are that fallback on curved corridor
  rings. RULE: every corridor vertex is framed on the OSM way's own
  route (`airport/road_ramp.road_route_frame` :544-634, sourced from
  `road_profile.core_profiles`; the `_osm_levelled` filter must admit
  the exit way, or the corridor's axis is registered as a route
  explicitly) and published in `road_route_frame`; the axis polyline
  (mouth → end) is ALSO published as its own sidecar key
  (`road_exit_axes`: `[ref, [[lat, lon], …]]`) for the replay read and
  `road_course_profile.py`. Bar: 0 `within_shape` rows ≤ 8 % on
  corridor faces.
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
| 2 | Corridor derivation | `planar/overlay.build_arrangement` (c: `road_exit_corridors` after `zone_regions`, regions role `service_road`, kind `cell`) | zones, cells, DEM, road lines, water | Order: zones → corridors (mouths from the UNCUT band boundary) → band cut-back re-applied with the corridors → regions. The `_one_ribbon` core re-union and the `bands.buffer(cutback)` subtraction are DELETED. |
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
| 13 | One-way rulings | `law/emit.toml [design] one_way_rulings` (:911-925); `solve/design_roles.py:128-132`; applied `solve/design.py:448, 522-535` (exact match on the head, the text before " ("); `model/constraints.py:76-82, 164-170` | a `follows=` row is one-way ONLY if its head is registered; else `follows` is ignored and the row is TWO-WAY | `"roads.road_exit band follower"` registered (c). DEFECT in the parked code: the `_end_row` head `zones.adjacent_ground end row from the pavement end` is NOT registered, so the end row is priced two-way (the pavement end can be pulled by the corner vertex). Register it. Staged solve: any `follows` row is dropped from stage 1 (`design.py:474-476`). |
| 14 | Precedence / weld | `constraints/precedence.view`, `planar/weld.weld_cells` | overlapping regions, shared vertices | `service_road` vs `graded_strip` never overlap (row 1). Mouth vertices are shared by construction (the ribbon's square cap coincides with the band boundary segment). |
| 15 | Census `groundside_cutback` | `tools/check_grade._check_groundside_cutback` | road ring vertex vs nearest zone vertex across the strip, report-only, `cutback_intent_q97` | The corridor's cut-back strips are priced here and adjudicated nowhere (13 rows in round 3, worst 0.59 m). Lawful rows. |
| 16 | Census `within_shape` axis lookup | `tools/check_grade.py:823-845` (`_road_frame_by_nid`), `:2253-2340` (route reading), `:2342-2378` (`_xsec` ring-axis fallback, ≥ 45° = transverse at 0.02·d) | route reading iff BOTH nids are framed in `road_route_frame`; else the ring's min-area-rect axis | Frame every corridor vertex on the OSM route (§1.4). Bar: 0 `within_shape` rows ≤ 8 % on corridor faces. |
| 17 | Census `hairline_pair` | `_check_hairline_pair` (:7519), proximity `SHARED_VERTEX_TOL_M` 0.5 | an emitted vertex within 0.5 m of a foreign edge it does not lie on; segments < 0.5 m | With the cut-back (0.6 m + snap) as the ONLY stand-off and no core neck, no corridor outline vertex lies under 0.6 m from a band edge except the shared mouth vertices. Bar: hairline count = base (12). |
| 18 | Census `sea_wall` | `_check_sea_wall` (:6860), `stamp_sea_wall_tears` | ring edges with both vertices on declared `shore_edges` above water | Row 7 makes a corridor shore edge impossible. Bar: 0. |
| 19 | Census `adjacent_ground_step` | `_check_adjacent_ground_steps` (:2845) | consecutive welded pair of one zone ring, step ≥ `visual_m` and grade ≥ cliff | The band ring beside a corridor now has the cut-back edge; the mouth is the only shared point. Row 7 removes the shore case. NOTE the row's reported lat/lon is not the site (§3.4). |
| 20 | Cockpit critical | `census.py --sites`: sim-visible rows (`visibility_m` 0.05) by family; "visual" = not-adjudicated sim-visible rows | hairline + sea_wall in round 3 (49 + 2 = 51; base 12 + 0) | Rows 17–18 return it to 12. |
| 21 | Emit / sidecar | `emit/osm_adapter.py` (sidecar writer), `road_route_frame`, `station_caps` | per-face roles, refs, axes | Adds the corridor axis entry (row 16); ref `road_exit:<k>` kept so `road_exit_vertices` readers (rows 4, 6, 9) find the faces. |
| 22 | Verify (engine) | `verify/*` families in `NLWF.report.json` `verify.by_family` | same families pre-emit | Same bars as the census; `runway_*` DEFECT families stay zero. |
| 23 | Frames / instrument | `tools/road_course_profile.py` (c, INDEX row), `docs/frames.jsonl` | the course grade over 10 m | The acceptance instrument (§4). |
| 24 | `road_within_shape` (roads) | `constraints/roads.py:194-316` | ALL pairs of every road ring, two-way `Diff` at 8 % (2 % transverse); only cross-route/merged pairs touching an airside vertex become the one-way `roads.road_ribbon airside follower` | A seam(mouth)↔corridor pair is a plain TWO-WAY row: the corridor pulls the band's mouth. RULE: any pair touching a road-exit mouth vertex is one-way (road follows), under the existing `roads.road_ribbon airside follower` head. |
| 25 | `strip_transverse` tie population | `constraints/zones.py:364-379` (`tie_pop`), rows `:545-640` | every vertex of every non-runway-family face within the zone-2 half-width of a runway edge | Corridor vertices are in the tie population; a runway-end-corner corridor abeam the runway would take the strip tie. RULE: `road_exit:*` vertices are excluded from `tie_pop`; the band's cut-back edge carries the tie. |
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
| `within_shape` | 0 | 204 | `service_road|service_road` ×204, caps 2.0–3.3 % (transverse) on 177, 5.5–7.9 % on 27; 27 rows > 8 % |
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
* `road_cross_section` 41: §1.3 (2)/(3) (per-vertex DEM fit removed).
* Lag not settled (1.509 m on the follower chain): §1.3 (1).

---

## 4. Pre-registered acceptance

Instrument: `tools/road_course_profile.py PATCH.osm --capture
<scratchpad>/f/NLWF.pkl --ways -3,-1` (step 2 m, window 10 m). Census:
`tools/harness/census.py PATCH.osm --sites`. ONE closing build
`build_airport.py NLWF` (tag `roadexit_NLWF`), base arm
`nlwfroad100_base` (main d5173ad6 census 13/1) re-cut on the merge base
if main has moved.

1. **Course**: road −3 (behind the terminal, both mouths and the in-band
   pocket at −14.311371, −178.068277) and road −1 (NE corner past the 25
   end) read ≤ 8.0 % over any 10 m window along the course wherever the
   sample is on the patch; raw-DEM samples outside the patch are not
   priced (round 3: the ≥ 12 % samples at s < 340 are west of the patch).
2. **Census**: LAW-TRUE ≤ base + lawful corridor rows, where the ONLY
   admitted new rows are `groundside_cutback` (stamped
   `cutback_intent_q97`) and `road_cross_section` ≤ 0.05 m; `within_shape`
   on corridor faces 0 (axis published; any residual row is a > 8 %
   defect); `hairline_pair` = base (12); adjudicated ≤ 1 (base).
3. **`sea_wall` 0**; every band vertex within the snap margin of the sea
   at 0.00 m (7 on zone2#0 as in base).
4. **Shore** at −14.312505, −178.070133 "natural by default" in the
   build log; `natural_shore` 2 entries in the sidecar.
5. **Runway families zero**: `runway_step`, `runway_end_skirt`,
   `runway_crown` (verify DEFECT families), `strip_transverse`,
   `adjacent_ground_step` 0, `strip_seam_tear` 0.
6. **Critical**: motion 0; visual ≤ 12 (base).
7. **Lag settled**: the build log reports the one-way set settled (no
   `LAG NOT SETTLED` on `roads.road_exit`); status `optimal`.
8. **CYXY airside identical**: `v2_solve_replay.py --replay CYXY --from
   classify --verify` fix vs base: runway bows identical, airside
   `airside_value_delta` 0 vs the reference; verify rows ≤ base.
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

## 5. Implementation plan (Opus lane, attempt cap 2)

Start from `origin/claude/nlwfroad100c` 02d99b50 rebased on
`origin/main` (the end row, the seam-keeps-band-rows, the
`_end_foot_rows` amendment, `road_course_profile.py`, the frames rows
and the 12 twins are kept). Synthetic-first; replay before any build;
ONE NLWF build at the close.

1. **Derivation (planar)** — `planar/zones.road_exit_corridors`: drop
   the `bands.buffer(cutback).difference(mouths)` subtraction and
   `_one_ribbon`; ribbon half-width = lane half-width (without the
   cutback); clip by sea ∪ shore wedges; skip a mouth inside a wedge;
   add the in-band pocket extension (mouth walk inward across
   band-class boundaries with step ≥ `visual_m`). Then feed the corridor
   polygons minus mouth discs into `zone_regions`' groundside cut-back
   (the existing mechanism; extend its pavement input, do not fork it)
   and re-derive the bands. Twins (b), (c).
2. **Rows (constraints)** — replace `road_exit_rows` with station course
   rows (two-way among stations, one-way from the mouth) + cross-section
   rows; centreline profile target replaces the per-vertex DEM `keep`
   in `with_road_ramp`; §37 (6) stays withdrawn on corridor vertices;
   register the `_end_row` head in `one_way_rulings` (row 13); make
   `road_within_shape` pairs touching a mouth vertex one-way (row 24);
   exclude corridor vertices from `tie_pop` (row 25) and corridor-only
   bodies from the plane datum (row 26).
   Twin (a). Replay NLWF `--from classify --verify` and read the
   course profile: bars 1, 7 on the replay; `--why-hard` empty.
3. **Frame + sidecar** — FIRST read `road_route_frame` coverage of
   `road_exit:*` vertices on the replay (row 30). Frame every corridor
   vertex on the OSM route and publish `road_exit_axes` (§1.4, row 16);
   twin (d). Replay + census of the replay's `--emit` patch: bar 2's
   `within_shape` 0.
4. **CYXY replay** vs base (bar 8). If any airside value moves, stop and
   report — do not tune.
5. **Closing build** `roadexit_NLWF`; census; profile; bars 1–7. Register
   the frame; comment #100 with the site numbers first.
6. **Attempt cap**: attempt 1 = steps 1–5. If any bar in {1, 2, 3, 6} is
   missed, ONE more attempt on the same branch after an attribution of
   the miss (interventional: `--drop-generator road_exit`, then the
   consumer table row that owns it). A second miss parks the branch
   with the read and returns to the spec author.

Not in scope: the census lat/lon instrument defect (§3.4, file an
issue); Windows/CRLF; any HECA/LEMD change (the corridor only exists
where a road exits a band with a ≥ 0.5 m step — the lane reports the
corridor count on CYXY/HECA replays if either capture carries one, and
an unexpected corridor there is a STOP).

---

## 6. Open items the lane resolves by reading, not by tuning

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
