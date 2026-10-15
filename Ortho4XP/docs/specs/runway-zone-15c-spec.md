# Runway zone 2 and the runway end — spec and consumer census (RULINGS 2026-10-15c)

Status: IMPLEMENTED (lane `rwyzone15c`, 2026-10-15, branch
`claude/rwyzone15c-p2`). The master answered §8's questions the same day
(Q1 (a) 300 m; Q2 (a) estimate + cap; Q3 yes; Q4 yes); §9 records what
was built where it differs from the proposal. Phase 1 (#750) is §1.

Owner rulings this spec implements (RULINGS 2026-10-15c, verbatim choices):
(1) "From the centreline", (2) "Full safety-area length", (3) "1:3 bank",
(4) "5% for FAA".

## 1. Phase 1, the base this builds on (landed separately)

Measured at KBJC 12L (capture `KBJC.pkl` on main 32bcb6881, replayed on
c075032f2). The end band stood 1.5–7.5 m over a falling DEM. The floor
holding it came from the PARALLEL runway 12R/30L (4B), 250–330 m away.
The zone class key `("runway", 4, None)` joined vertices beyond 12L's end
(where 12L's own edges are not abeam) to 12R's edge, using its clamped
corridor floor (−0.747 m at 22.9 m). The projection then put the empty
band at its midpoint (1726.56 m). Phase 1:

* `constraints/zones._found`: the class join takes the NEAREST edge of
  its class whether abeam or not. Where that edge belongs to a runway
  and the vertex lies beyond the runway's end, the class contributes
  nothing. A farther candidate past its own half-width is kept only when
  it is that join's edge.
* In the end box (`strips.end_band_vertices`), a taxi class floors only.
  The end profile is the ceiling.
* `solve/project.senior_band`: the end-profile chord band is senior. A
  zone floor yields to its ceiling, where before the clamp took the
  midpoint.

## 2. What the four rulings change, in one sentence each

| # | Law | Today | After |
|---|-----|-------|-------|
| (1) | zone-2 lateral width of a RUNWAY | buffered `hw` from the PAVEMENT EDGE (`planar/zones.py:323`), `hw` = `zones.toml` `half_width_m` / `half_width_faa_m`, which are CENTRELINE figures; FAA also drops the letter in planar (`key = ("runway", cn, None)` → 76.2 m for a 4B runway, while `constraints/zones` prices 22.9 m) | edge offset `= max(lip_width_m, hw(cn, cl) − runway_half_m)`, so the zone's outer edge stands `hw` from the CENTRELINE (FAA by letter: A 18.3, B 22.9, C–F 76.2; ICAO by code: 30 / 40 / 75 / 75) |
| (2) | end band length | the zone buffer: `hw` beyond the SLAB end (the far edge of the blast pad) — KBJC d = 137 m from the threshold | the RSA length measured from the RUNWAY END (`RunwayEnd.xy`, the blast pad / overrun inside it): FAA by the letter proxy A 73.2 m (240 ft, A/B-I), B 91.4 m (300 ft, A/B-II), C–F 304.8 m (1,000 ft; AC App. G R, `fabric-model-reg-set.md` §3.1); ICAO strip end 60 m + RESA (see Q1) |
| (3) | graded zone meets raw terrain | a bare step at the zone's outer ring (lawful 2026-08-01, "boundary steps are lawful terraces") | a 1:3 bank (`emit.design.bank_slope` 0.33) where the fill or cut at the ring exceeds the foot tolerance; under the tolerance the step stays lawful |
| (4) | runway band max transverse fall | `adjacent_ground.runway.band_max_down` 3 % at code 3/4 under both rulesets | FAA 5 % (`[faa.resa] transverse_max`); ICAO keeps 3 % at code 3/4 |

Every runway at every airport changes once, and the owner re-reads the
approved airports.

## 3. CONSUMER CENSUS (RULINGS 2026-08-30l) — every pass that reads the regions

Region names: **Z** = the runway zone-2 lateral band (width (1), fall
(4)); **E** = the runway end band (length (2)); **B** = the new bank
annulus (3).

| Consumer | file:line | Reads | Today | Ruling for this change |
|---|---|---|---|---|
| zone faces (THE derivation site) | `planar/zones.py:292-330` `zone_regions` | Z, E | buffer of the class union by `hw`, mitre 2 | **Changes.** Runway groups are keyed PER RUNWAY REF, not per class. Each one is buffered by its own edge offset (1). The end is cut flat at the RSA length beyond each runway end (2). This is the ONE place the region is trimmed (08-30l). |
| end breaks | `planar/zones.py:147-189` `runway_end_breaks` | E | the break line at `EndProfile.break_m` from the slab end | **Changes.** Measured from the RUNWAY END, not the slab end (2). Today's line already takes `hw` from the centreline. |
| terrain-edge clip | `planar/terrain_edge.py` (called from `zone_regions`) | Z, E | crest / rim-road clip of every region part | **Reads the new region unchanged.** A 305 m end band reaches more crests, so more parts get clipped. The clip stays BEFORE the bank: a bank is minted only where the clipped ring meets raw DEM. |
| zone bands | `constraints/zones.py:91-176, 258-264, 451-542` | Z | `half_of(edge)` = `zone2_half_width_m(cn, cl)`, measured from the EDGE | **Changes.** `half_of` = the edge offset of the edge's own runway (the runway half from `airport.runways` by face ref). `zone_bounds` reads the edge offset. |
| strip tie (06b/06p/06q) | `constraints/zones.py:545-650` | Z, (4) | `strip_transverse_bound(d)` = the zone floor | **Follows `zone_bounds`.** The cap is 5 % under FAA (4). The tie population is still "within the zone-2 half width" (now the edge offset). |
| pocket rule | `constraints/zones._found` | Z | nearest pavement, clamped to its half | **Unchanged rule, narrower runway corridors.** Taxi floors near a runway now reach more of the ground between runway and parallel, because the runway band no longer covers it. |
| strip footprint / end corridors | `constraints/strips.py:117-166` `runway_groups` | Z, E | lateral rect `axis ± hw` (from the CENTRELINE already); end rect `max(width, hw)` wide, `corridor_length_m` long, measured from the SLAB end | **Changes (E).** Length = RSA length from the RUNWAY end (`RunwayEnd.xy`), not the slab end. Lateral: unchanged (already centreline). This makes the zone faces agree with the strip footprint for the first time. |
| end profile rows | `constraints/strips.py:462-556` + `_end_foot_rows` | E | profile from the runway END EDGE (slab end), over the end rect | **Changes datum (E).** `d` = distance beyond the runway end. The pad's far edge is a transect foot (already: `end_transect_foot`). See Q3 for the profile over the pad itself. |
| RESA transverse | `constraints/strips.py:283-340` | E | pairs in the end rect, `resa.transverse_max` (FAA near zone by letter) | **Longer rect.** No law change. |
| end rate (FAA) | `constraints/strips.py:698-768` | E | rate along the corridor | **Longer rect.** No law change. |
| raoa (ICAO) | `constraints/strips.py:769-` | approach rect | its own `raoa.length_m` rect | **Unchanged** (its own region). |
| end box (phase 1) | `strips.end_band_vertices` | E | stations in the end rect | **Follows `runway_groups`.** |
| strip keep-out (shapes) | `planar/strip_keepout.py:23-55` | Z, E | axis extended by `corridor_length_m`, buffered `max(hw, half)` from the centreline | **Changes (E length only).** Read the RSA length through the one helper. |
| runway footprint (classify) | `classify/roles.py:1385-1424` | Z, E | `LineString(ends).buffer(hw)` from the centreline, extended by `corridor_length_m` | **Changes (E length only)**, same helper. |
| structure strip keep-out | `planar/structures.py:312-326` | Z | `runway poly.buffer(hw)` from the EDGE | **Changes (Z).** Buffer by the edge offset, the same function as the zone faces. |
| ribbon extent | `classify/ribbon_mint.py:31-47` | Z | `runway cell.buffer(hw)` from the EDGE | **Changes (Z).** The patch a road is ribboned inside: the same edge offset. It must also cover E's new length and B (the bank is patch). |
| zone weights | `solve/rows.py:262-290` `_zone_weights` | Z | graph distance normalised by `hw` | **Changes (Z).** Normalise by the edge offset. Reads only "is the sheet anchored" — byte-level movers expected, no law. |
| verify strip readers | `verify/strips.py:118-190, 220-290` | Z, E, (4) | tie bound by `zone2_half_width_m`; end groups mirror `runway_groups` | **Lockstep.** The same helpers, so generator and reader read one number. |
| verify keep-out / walls | `verify/keepout.py:128-140`, `verify/structures.py:92-108` | Z | `zone2_half_width_m` from the edge | **Changes (Z).** The edge offset. |
| harness census | `tools/check_grade.py:8200-8215`, `tools/harness/law_support/grade_law.py:157-345, 654-700` | Z, E | v1 tables: strip from the centreline, end corridor `max(width, strip_half)` × `runway_end_clearance_length_m` | **Lockstep.** `adjacent_ground_envelope(d from the edge)` takes the edge offset. The end corridor length becomes the RSA length. The census twin (`test_harness.py`) asserts the one code path. |
| runway-end ground tool | `tools/runway_end_ground.py:150-210` | E | `zone2_half_width_m(code, None)`, i.e. the letter dropped | **Changes.** Read with the letter and the new length. Phase 1's KBJC 30L rows came from this letter-less reading: a 76.2 m footprint for a 4B runway whose law is 22.9 m. |
| replay tool | `tools/v2_solve_replay.py:1127-1180` | Z | `zone2_half_width_m` | Report only. Follows the helper. |
| adjacent-ground census families | `verify` + census: `adjacent_ground_tear`, `strip_seam_tear`, `adjacent_ground_step`, `runway_end_skirt`, `resa_transverse` | Z, E, B | the bands, end skirt, RESA over `graded_strip` rings | **Read the new regions.** B faces are a new role/ref. `adjacent_ground_step` across a bank's toe is the lawful 1:3 face, not a step (the bank row prices it). |
| terrace joints | `pipeline/publication.terrace_joints_ll` | Z outer ring | declared steps | **A bank replaces the declared terrace** where B is minted. Under the foot tolerance the terrace stays. |
| lips (zone 1) | `planar/zones.py:322` `inner = u.buffer(min(lip, hw))` | Z | 3 m from the edge | **Unchanged.** The edge offset is never below the lip (the `max`). |
| tile edge / patch boundary | patch coverage = pavement ∪ zones (∪ B) | Z, E, B | zones clipped to the tile | **Larger coverage.** A 305 m end band can cross a tile edge. The existing per-tile clip applies, so a check is needed, not a rule. The bank is clipped the same way. |
| landing collars / pads / platforms | `planar/landing.py` (`#collar`), `constraints/platform._bank_rows` | — | their own 1:3 banks | **Unchanged.** B REUSES `_bank_rows`' form (§5); a pad / landing in a zone keeps its own law. |
| roads / taxiways crossing E | `strips._unbound_end_vertices`, road cap (02ag (2)), `own_law` | E | a road ribbon is road-cap governed; an airside face is its own law | **Unchanged rule, more crossings.** At 305 m KBJC 12L's service road (230–270 m beyond the pad) is now inside E. The road cap governs its ribbon (02ag (2)). |
| shore / quay / natural shore | `planar/zones.py` shore trim, `constraints/zones` quay / natural | Z, E | trimmed at the coastline | **Unchanged.** Trimmed at the same site. A natural shore already falls at 1:3. No bank is minted toward water. |
| gap aprons / rim strips | `planar/zones._unclaimed` | Z, E | outside every band | **Unchanged.** |

Two derivation helpers carry every row above (no consumer computes its
own):

* `law.tables.runway_zone_edge_offset_m(law, cn, cl, runway_half_m)` =
  `max(lip_width_m, zone2_half_width_m(law, "runway", cn, cl) −
  runway_half_m)`. `zone2_half_width_m` keeps its meaning (the
  CENTRELINE figure) for the centreline consumers.
* `law.tables.runway_safety_area_length_m(law, cn, cl)`: FAA
  `[faa.end_skirt] rsa_length_m` by letter; ICAO
  `strip.end_length_m + end_skirt.corridor_length_m` (Q1). Measured from
  `RunwayEnd.xy`.

## 4. (1)+(2) The zone faces

Per runway ref (shoulders excluded, §40 (4)):

1. `u_r` = the union of the runway's own cells (its slab, which includes
   the blast pad).
2. The lateral band = `u_r.buffer(edge_offset)` intersected with the
   centreline rectangle `axis(RunwayEnd 0 − L_rsa … RunwayEnd 1 + L_rsa)
   ± hw`. The end band is then that rectangle's part beyond the slab, so
   it is `hw` from the centreline everywhere, and the zone's outer ring is
   the RSA's own rectangle (KBJC 12L: 152.4 m wide, 304.8 m from the
   threshold. The owner's two points are 156.4 m apart, ~303 m past the
   threshold).
3. Zone 1 (the lip) stays `u_r.buffer(lip)`.
4. Claim order: runways first, wider first (as today); then taxi classes
   (unchanged).

A runway narrower than `2 × (hw − lip)` gets the full `hw − half` band. A
runway as wide as its RSA (none at the battery) gets the lip alone.
Emittability: the region is a plain polygon with holes, the same kind as
today, so the heightfield mesh is unaffected.

The face ref carries the runway ref (`adjacent_ground:runway:<ref>:zone2#k`)
so `constraints/zones` reads the runway half from `airport.runways`, never
from a class key. The class-key join that minted phase 1's bug then has
no shared key left between two runways.

## 5. (3) The bank

Where the graded surface meets raw terrain (the zone's outer ring after
the terrain-edge clip, not on a shared edge with another patch face, not
on water), the solved fill or cut `Δ = z_ring − DEM(ring)` over
`|Δ| > foot_tol` ties in at 1:3.

* **Planar**: a bank annulus `<zone ref>#bank` is minted outside the ring.
  Its width is `W = clamp(Δ̂ / bank_slope, bank_min_width_m, W_cap)`, and
  `Δ̂` is a PRE-SOLVE estimate (Q2). It claims ground only where nothing
  else does (after every airside / pad / road region). It is the same
  class of region as a landing's `#collar` (`planar/landing.py:224-237`).
* **Constraints**: one new generator file `constraints/zone_bank.py`
  (family member, not an append) that REUSES `platform._bank_rows`' form.
  The inner ring LEADS (one-way, the zone's ground never moves for its
  bank), the outer ring is ON the DEM, and every bank vertex lies inside
  the 1:3 cone between them. Where `W` is too wide the solve places the
  toe inside it (the collar precedent, 10-02v (5)). Where it is too
  narrow the residual is reported, never hidden.
* **Census**: a new family `zone_bank_slope` (the bank steeper than 1:3 +
  noise), registered in `LAW_FAMILIES` (test_harness twin). The bank's
  toe is not an `adjacent_ground_step`.
* Under `foot_tol` there is no bank and the bare step stays lawful
  (2026-08-01 as amended).

`foot_tol`: today's `emit.instrument.strip_edge_noise_m` (0.15 m,
13a (4)) is the nearest existing key. See Q2.

## 6. (4) FAA runway band 5 %

`zones.toml [adjacent_ground.runway]` gains `band_max_down_faa = 0.05`
(cited: AC 150/5300-13B Table 3-6, `[faa.resa] transverse_max`).
`tables.zone_bounds` reads it under the FAA authority, the same switch
`half_width_faa_m` already uses. `strip_transverse_bound` follows, and
so do the readers (`verify/strips`, the census `adjacent_ground_envelope`
gets the same key). ICAO is unchanged.

## 7. Measurement plan (after ratification)

Per airport (NLWF CYXY KASE SPJC KCLT HECA OTHH + KDEN KBJC; KPDX if
captured), one closing harness build against a base-arm control on the
same sha:

* band widths and lengths before / after per runway (zone faces' extent
  from the centreline, end-band length from the runway end);
* airside movers by family with the worst and lat/lon (runway pavement 0);
* the end profiles (`tools/runway_end_ground.py --profile`);
* the banks: count, area, max height;
* census law-true families before / after;
* phase times (larger graded areas): `pass 1a`, stage 2, the emit.

## 8. Questions (answered by the master 2026-10-15)

* **Q1 (ICAO end length).** The ruling reads "strip 60 m + RESA,
  `corridor_length_m` 240 m at code 4". (a) 60 + 240 = **300 m** beyond
  the runway end at code 4 (210 m code 3, 150 m code 2, 90 m code 1): the
  RESA measured from the strip end, as Annex 14 §3.5.3 measures it
  (reg-set F-4). (b) **240 m** total, today's `corridor_length_m`. This
  spec assumes (a).
* **Q2 (the bank's width before the solve).** The bank must be in the
  map before the solve sets `Δ`. (a) Estimate `Δ̂` per ring segment from
  the DEM at the nearest pavement edge, less the zone's mandatory fall,
  against the DEM at the ring, and mint `W = Δ̂ / 0.33` capped at
  `W_cap` (e.g. 30 m = a 10 m bank). (b) Mint every bank at `W_cap` and
  let the solve place the toe (simple, more patch area everywhere). This
  spec proposes (a) with (b)'s toe placement inside it.
* **Q3 (the profile over a blast pad).** The RSA length now runs from the
  runway end, so the end profile's first 61 m (FAA near-end rule) partly
  lies ON the paved blast pad. The pad is pavement with its own law
  (taxi-family caps); the ground profile resumes at the pad's far edge
  with the profile value at that distance (as `end_transect_foot` does
  today). Confirm the profile is NOT imposed on the pad pavement itself.
* **Q4 (FAA A/B lengths).** The letter proxy maps A → A/B-I (240 ft) and
  B → A/B-II (300 ft), the same proxy `half_width_faa_m` uses. The AC's
  visibility column (< 3/4 mile raises A/B to 600 ft) is not modelled, as
  it is not for the width. Confirm.

## 9. As built (deviations from §3–§5, for the reader)

* **The bank's width.** The pre-solve estimate cannot see the pavement
  standing off its DEM (KBJC: taxi up to 1.42 m, apron 1.65 m), so a station
  over the tolerance banks `(|Δ̂| + adjacent_ground.bank_estimate_margin_m)
  / bank_slope` wide (margin 1.0 m), capped at `bank_cap_width_m` (30 m).
  On level ground the band's own mandatory fall (about 1 m at a 76 m band's
  outer edge) is itself a step over the tolerance, so most zone rings bank.
* **The toe, no cone.** The weak §23 ground datum alone let the bending
  term float the bank's outer ring (KBJC replay: 177 patch-edge vertices
  over 1 m), so each bank vertex on the coverage edge carries a `Band` at
  its DEM sample (`zones.adjacent_ground zone bank toe`, law weight). The
  §5 cone rows were BUILT AND REFUTED on the CYXY replay: one-way (zone
  leading) the lag did not settle (4,557 of 11,580 one-way rows moving
  after 3 rounds, worst leader move 8.5 m); two-way they dragged zone
  rings off their law line and, through an apron lip vertex, lifted
  `dsf:pol19` 1.88 m. Toe only, the lag settles (the base's 23 rows) and
  the census reads the same as with cones. No bank row touches a vertex
  another face shares (airside is king).
* **Readers.** The bank (`graded_strip`, ref `zone_bank:<zone ref>`,
  `model.planar.is_zone_bank_ref`) is read by no strip-law reader
  (longitudinal, arc, RESA, end, RAOA; generator `_strip_rings`, verify
  `_strips`, census `_is_zone_bank`) and by the cross-shape seam reader in
  both instruments (a bank steeper than 1:2 is a tear). No census family
  for the bank's own slope was added (not done).
* **Keep-outs unchanged.** `planar/structures` strip keep-out, the
  ramp-in-strip and wall-in-strip readers keep the half-width buffered
  from the edge — the wider, conservative footprint — so they stay
  lockstep with each other; only the graded band narrows.
* **The census frame.** The census end corridors read the RSA length less
  each end's published overrun (`check_grade._rsa_end_lengths` from the
  sidecar's `runway_axes`), and the census tie reads the declared runway
  width (`runway_axes` half_m) for the edge offset.
* **FAA letters in planar.** The runway band is built per runway REF with
  the runway's own letter, closing the letter-less 76.2 m planar width of
  FAA A/B runways (KBJC 12R/30L and 03/21 were 76.2 m in planar, 22.9 m in
  the law).

## 10. Findings for the master (not ruled here)

* **CYXY, the RSA over the escarpment.** The 300 m ICAO end band crosses
  the plateau edge; filled to the end profile it stands up to 11.9 m off
  the profile (`runway_end_skirt` 1 → 23 rows on the replay without banks)
  and a zone face carries a 34 m in-face step (`adjacent_ground_step`) where
  the terrain-edge clip leaves a piece. The standard and the terrain
  disagree there; the owner's to decide (clip the RSA at the crest, or fill).
* **Airside movement.** The narrower runway band moves pavement through two
  channels: the runway-edge tie (06p) no longer reaches pavement beyond the
  new zone (and under FAA ties at 5 %), and the new zone/bank rings re-node
  pavement edges. Measured per airport in the PR.
* **#715 twin.** A road 4–6 m inside a code-2 band's outer edge below a
  retaining wall settles 3–4.4 m over its lower ground
  (`test_wall_step715`, marked xfail with the numbers).
* **Rim road.** With the RSA ends a band runs round a rim road's governing
  stretch and a sliver beyond the road stays connected (`test_v2edge`).

## 11. Phase 3 (RULINGS 2026-10-15g (B), (C))

* **(B) No banks.** `planar/zone_bank`, `constraints/zone_bank`, the bank keys and every bank skip in the readers are deleted. The zone and its end area are graded by their own law and meet raw DEM at their outer edge. No census family reads a zone's outer boundary against the raw DEM — the census reads the patch alone — so that step is uncounted by construction. In-face steps (`adjacent_ground_step`) and steps against pavement (`groundside_cutback` against a road) still count.
* **(B) Groundside below a declared wall.** `road_ramp.wall_release` now releases a zone-law row (`zones`, `strips`) whose ground vertex stands across a declared wall from its pavement foot, whichever side holds a road. The released zone vertex, if no other face shares it, is held at its DEM (`zones.adjacent_ground beyond the wall`). On the #715 twin, the road's max |z − 92| is 0.215 m (bar 1.0). With claude/tri752 d32275871 merged it is 0.243 m.
* **(C) The end area stops at the top of a drop** (`model/end_area.py`, PROPOSED threshold for ratification). Stations run every `edge_grid_m` (5 m) along the extended centreline and the band's two side lines; the shortest of the three wins. A DROP needs both:
  * the ground stands more than `edge_min_drop_m` (2 m) below the end profile's lawful fall;
  * the ground falls steeper than `end_drop_min_grade` (0.20) over `edge_probe_m` (15 m).

  The end area ends at the crest of that steep run.

  | Airport | Steepest end ground (15 m) | End-area lengths |
  |---|---|---|
  | CYXY | 24.8 / 51.5 / 44.9 % | 14R/32L 145 / 80 m, 14L/32R 165 / 300 m, 02/20 90 / 90 m |
  | KBJC | ≤ 10.5 %, no 2 m deficit | 304.8 m at 12L/30R |
  | KDEN | ≤ 2.4 % | 304.8 m at every end |

  The lengths are published in the sidecar's `runway_axes` rows [8], [9] for the census.
* **Crossing pieces.** A `runway_crossing` cell (ref `a+b`) used to form a band group of its own. Its fallback axis, a few metres square, swung an RSA rectangle 300 m across CYXY (a 34 m in-face step). It now joins both runways' groups under each runway's own class.
* **Airside attribution.** Each airport ran replays of base, arm, and arm with the old corridor reach (`--from planar`).

  | Airport | Banks (phase 2) | 06p tie / (4) | Re-noding |
  |---|---|---|---|
  | CYXY | `dsf:pol19` 1.88 m, apron 0.36 m | 0 | the rest: arm and old-reach arm identical |
  | HECA | apron 1.00 → 0.25 m once removed | 0 | the rest: arm and old-reach arm identical |

  * **Re-noding:** the zone rings meet pavement edges at new points.
    * CYXY after the crossing fix: 96 / 77 solve-owned nodes differ; taxi 0.27 m, runway 0.05 m (one vertex).
    * HECA: 84 / 111 nodes; apron 1,135 at 0.25 m, taxi 0.37 m, runway 0.12 m.
  * **Refuted remedy:** noding zones after the airside, through the pads' clip and rim snap. Against a pass-B control at CYXY it still differs at 137 / 137 nodes, with 93 movers and the apron at 0.35 m. Deleted.

## 12. Phase 4 (RULINGS 2026-10-15h): the nine CYXY `runway_end_skirt` rows

Each row was attributed on replay arms of the registered capture
`overlay156/CYXY_shared.pkl` (`--from planar`). The closing build was
`rz5a_CYXY`, against the `--base-arm` control `rz5b_CYXY` at main
e11e531c5; both are registered.

| Rows (way, excess) | Kind | Cause | Fix |
|---|---|---|---|
| -10250 ×2 (0.002), -10194 (0.001); main's -10189 (0.004) | instrument | **Reader frame.** Both readers measured plan distance in a spherical equirectangular frame, which is 0.1–0.7 % off the ellipsoid. At 60.7 N the engine's 128.34 m chord read as 128.17 m, so a chord held exactly at its bound read as a breach. | The end-profile readers measure in the engine's tmerc metric (`verify.frame.metric_frame`, `Patch.in_metric_frame`, `check_grade._engine_metric`). Row points go back to the census frame, so every join is unchanged. |
| -10194 (0.008), -10237 (0.004) | instrument | **Tolerance composition.** The generator's slack was the key less materiality (0.01). The solver holds a row only within `design.hard_tol_m` (0.02), and each emitted altitude rounds to 0.01. | Generator slack = key − `rounding_noise_m`, the envelope `hard_tol_m` is sized under. The reader's forgiveness is unchanged. |
| -10237 (0.064) | real ground | **Class join by code number.** v3909 lies 270 m beyond 14L/32R's end. It was joined to 14R/32L's edge, 251 m away and of the same code. That floor held it 2 m over its DEM and over 14L/32R's end pair. | Each zone region carries its runway (`ZoneRegion.runway_ref` → `PlanarMap.zone_runway_of_ref`). A runway band's vertex joins that runway's edges only (`constraints/zones._runway_class`). |
| -10098 ×2 (0.36), -10097 (0.29) | real ground, **law conflict** | v2132 is 64 m beyond 02/20's end and 5 m beside the parallel taxiway pav9. Under 15c (2) the code-1 end area grew from 60 m to 90 m, which brought v2132 inside it. pav9 climbs 1.21 m within 72 m of the end. The end profile allows the ground +0.14 m there: the 2 % climb surface from a 60 m setback, at the 0.12 m generator slack. pav9 leads the ground through the one-way pavement pair and taxi D's floor. Two pavements lead the same ground, and no surface satisfies both. The same site carries the 3 new `raoa` rows and the 1 critical-motion row. | **Not fixed. Owner ruling needed** on which lead wins inside an end area. |
