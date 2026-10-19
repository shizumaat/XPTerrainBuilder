# The band's wall against a road inside it — a solver-level wall joint

Issues #951 (the wall half) and #949 (the wall half). Owner law: RULINGS
2026-10-19a (a road at or below a safety-area band's grade beats the band),
19i (its edge against the band is a stand-off plus retaining wall, not a
slope), 19k (such a road is not held level with the runway; it follows its
own ground) and 19l (the census exempts the declared wall terraces from
CRITICAL visual). Lane m3, 2026-10-19.

## 1. What failed, and why

| try | construction | result |
|---|---|---|
| #988 (`claude/c951wall` 8556580) | a 0.6 m + snap stand-off strip CUT from the band; nothing claims it (a terrace) | walls at both owner sites, but the strip's band edge ran within one identity spacing of foreign edges: KBUR `hairline_pair` 328 → 380 |
| `claude/c951joint` d80cc47 | shared kerb, the band's first ring edge off the kerb DECLARED a wall | no hairlines, but (a) the design energy across the shared kerb dragged the road to the band (the 15a (2) twin's road 7 m over its ground); (b) the riser was the band's first ring edge — 3.28 m over 8 m (41 %) at KLAX, a slope |

Both missed the same two things: the SOLVE kept coupling the road to the
band across the wall (bending + pair rows), and nothing put a band-level
vertex close beside the kerb.

## 2. The construction

1. **The riser face** (`planar/band_riser.py`, called from the ribbons'
   own pass C, `planar/ribbons._ribbons_pass_c`). Around every mapped-road
   ribbon, the runway- and taxi-family zone regions (the safety-area bands;
   an apron's zone keeps 10-03b) yield the strip within
   `emit.identity.weld_spacing_m` (1.0 m) of the ribbon as its own region:
   role `graded_strip`, the zone's ref + `:riser`
   (`model.planar.RISER_SUFFIX`). The kerb stays SHARED (the ribbon's own
   ring is one side of the riser — no second edge beside the kerb, the
   hairline of #988); the far side is a band line 1.0 m off, twice the
   0.5 m identity spacing the hairline family reads. Pass A stays
   ribbon-free (30aa identity); the riser keeps off the finished airside by
   the rim band, as the ribbons do. `overlay.dissolve_sliver_zones` never
   dissolves a riser and never hosts a sliver in one (it is narrow by
   construction — it IS the wall).
2. **The design energy is cut across it** (`solve/wall_cut.riser_cut_edges`,
   joined into `wall_cut_edges`, the 15a (2) cut the thin-plate bending
   already skips for a pack wall): an edge from a ribbon vertex to a band
   vertex that crosses a riser face carries no bending weight — as a shape
   joint separates two complexes.
3. **The pair rows across it are released** (`constraints/band_riser.
   riser_release`, between §20b's stages beside `wall_release`): a stage-2
   row from a ribbon vertex to a band vertex across a riser is withdrawn.
   KEPT: a row that can only hold the road DOWN — a ceiling governing a
   ribbon vertex (the kerb's band cap of `zones.zone_bands`, #980: 19a, the
   band leads where the road would stand above it) — and every
   `wall_terrace` row.
4. **The road follows its own ground** (19k; ported from #988): the 10-03b
   terrace rewrite leaves out ribbon vertices that stand in a runway or
   taxi band (`constraints/road_ramp._in_band_ribbon_vertices`).
5. **The wall is declared** (`pipeline/band_road_wall.py`, from
   `publication.terrace_joints_ll`): where a riser's band side stands above
   its kerb by more than the elevation materiality floor, one
   `wall_terrace` record per part of the riser's MIDLINE (half a weld
   spacing off the ribbon, strictly between kerb and band line, so every
   chord across the riser crosses it once), shape label `band_road_wall`.
6. **The census** (19l, ported from #988 / c951joint): `groundside_cutback`
   takes the cockpit class `terrace` (REPORT, never critical); the
   runway-strip wall check (`terrace_joint_strip`) skips a
   `band_road_wall` joint (19i: lawful in the safety area).

## 3. Consumer census (RULINGS 2026-08-30l)

| consumer | reads | interaction | ruled |
|---|---|---|---|
| `planar/ribbons._ribbons_pass_c` | zone regions, ribbons, airside clip | the single derivation site of the riser; noded in the same one pass; rim guard covers its ring | derive here |
| `overlay._faces_of` claim | regions | a riser region claims its face like any zone region (`source` `zone`) | unchanged |
| `overlay.merge_slivers` | same role AND same ref | the riser has its own ref: never merged into its zone | unchanged |
| `overlay.dissolve_sliver_zones` | zone faces < 50 m² or < 3 m wide | would dissolve every riser | riser exempt, never a host |
| `planar/build` zone maps (`zone_runway_of_ref`, `quay_refs`, …) | regions by ref | built from the regions: the riser ref is carried | unchanged |
| `constraints/zones` membership (`_face_class`) | ref prefix `adjacent_ground:<fam>:` | the riser's upper vertices are band members with full band rows | unchanged |
| `PlanarMap.band_kerb_vertices` | ribbon ∩ `graded_strip` | the kerb is the riser's lower side, as before | unchanged |
| `constraints/zones.zone_bands` kerb cap (#980) | kerb | one-way ceiling on the road: kept by `riser_release` | keep |
| `constraints/ceiling` | kerb | kerb rows stay un-twinned | unchanged |
| `constraints/road_ramp.terrace_rewrite` | terrace feet | in-band ribbon vertices leave the terrace | release (19k) |
| stage-2 pair rows (zones, strips, caps, no-step) kerb→band across the riser | rows | the wall would be priced as a slope | release |
| `solve/design_assemble` bending | triangles | ribbon→band edges across a riser | cut |
| `pipeline/publication.terrace_joints_ll` | joints | the riser declared where the road is below | declare |
| `planar/shapes` | `emit.terrace.shape_roles` (pavement only) | `graded_strip` is not a shape role | unaffected |
| census `adjacent_ground_step`, `within_shape` | chords across the riser | forgiven by the declared joint | declared |
| census `groundside_cutback` | ribbon vertex ↔ nearest unwelded zone vertex | the riser's band line at 1.0 m: a terrace row | REPORT (19l) |
| census `terrace_joint_strip` | joints in the runway strip | a `band_road_wall` joint is lawful there (19i) | exempt |
| census `hairline_pair` | constrained edges within 0.5 m and parallel | the band line is 1.0 m off the kerb and shares the riser's end vertices | bar: ≤ main |

## 4. Emittable

The riser is an ordinary face of the planar map: two constrained rings 1 m
apart, one at road level and one at band level; the mesh builds the wall
between them (heightfield: a 1 m wide steep face, not a vertical one).

## 5. Bars (from the brief)

- `hairline_pair` ≤ main at KBUR and KLAX;
- the KBUR building9 corner (34.19628, −118.35023) and KLAX
  33.945963, −118.436316 are declared walls;
- the #951 road (33.946976888, −118.436319373) stays on its DEM;
- 30aa airside identity holds (`ribbon_airside_added/removed` 0 / 0).

## 6. Measured — lane m3, two iterations (STOPPED at the cap; bars NOT met)

Replays `--replay frames/c944/{KBUR,KLAX}.pkl --from planar --emit`,
census through `tools/harness/census.py`; base = main 8f96a4c76.

Iteration 1 (sections 2.1–2.6 as written):

- the synthetic #715 twin: the road at 92.00 m (its ground), the riser's band
  line at 99.32–99.63 m, a 7.64 m declared wall. Without the cut the road
  stood at 98.9–99.5 m (the release alone moved nothing: 0 rows crossed), so
  **the bending is the coupling** c951joint measured.
- KBUR: `strip_seam_tear` 0 → 82, worst 8.35 m at 34.197845, −118.347643: a
  band island the cut decoupled from roads standing 8 m ABOVE it fell to
  202.6 m.

Iteration 2 (added: a one-way floor `z[band line] ≥ z[nearest kerb]`, so
the band meets a road above it level, 13ar / 29r; and band remnants
narrower than `strip_min_width_m` beside a riser join it):

| | KBUR main → it2 | KLAX main → it2 |
|---|---|---|
| `hairline_pair` raw | 333 → 459 | 1300 → 1345 |
| `hairline_pair` in scope | 0 → 0 (every row `above_degenerate_floor` / `on_the_edge`) | 0 → 0 |
| `strip_seam_tear` | 0 → 0 | 4 → 10 (worst 3.58 m) |
| `adjacent_ground_step` | 3 → 8 | 5 → 8 (worst 2.75 m) |
| new road-road rows | — | `pavement_over_road_cap` 0 → 5 (2.72 m), `terrace_actual_step` 0 → 8 (3.02 m), `vertex_to_edge_step` 0 → 1, `road_cross_section` worst 0.81 → 1.90 m |
| CRITICAL visual | 336 → 467 | 1312 → 1377 |
| 30aa `ribbon_airside_added/removed` | 0 / 0 | 6 / 0 (main 6 / 0) |
| airside values (solve-owned, > 0.02 m) | — | 0 moved; the EMITTED solve-owned vertex set differs (164 / 180) — not attributed |

Owner sites:

- KBUR building9 corner (34.19628, −118.35023): `groundside_cutback` 2.69 m
  over 1.12 m between `adjacent_ground:taxi:C:zone2#36` and **`dsf:pol122`, a
  DSF road page, not an OSM ribbon** — no riser is built there (the riser
  follows the mapped-road ribbons). It reads as a declared terrace only by
  the 19l census class, not as a `terrace_joints` record.
- KLAX 33.945963, −118.436316: a 0.37 m declared riser and a 2.55 m step over
  7.07 m INSIDE the band (`adjacent_ground_step`, main: 1.86 m over 3.5 m at
  the kerb). The riser's band line sits at its DEM: zone 2's rows bound the
  band, they do not hold it at the band's grade, so the fit puts the line at
  the ground and the rise moves into the band.
- KLAX #951 road `big_roads:-2346` (33.946976888, −118.436319373): 26.83–28.03 m
  (main 27.11–30.07 m) — on its ground.

What the next round has to answer (not decided by the lane):

1. **What is the band's grade beside an in-band road?** The riser is vertical
   only where the band's rows hold the band line above the road; in a zone-2
   band the line falls to its ground. A wall at the owner's KLAX site needs
   a rule for the band line's level (e.g. the band's own profile carried to
   the riser) — that is an owner/spec decision.
2. **Which roads get the riser?** The KBUR site's road is a DSF page
   (`dsf:pol122`), not a mapped-road ribbon.
3. **The road-road defects at KLAX** come from 19k's release of in-band
   ribbon vertices from the 10-03b terrace while a neighbouring ribbon keeps
   it: the release reads per vertex, the roads meet per carriageway.
