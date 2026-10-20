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

## 7. The owner's answers (2026-10-19, relayed by the master) and round 2

The owner answered §6's three questions:

- **Q11 — yes:** at the wall, the top of the runway / taxi safety band holds
  its own graded level; it does not fall to raw DEM. **Built:**
  `zones.zone_bands` gives a band vertex at a wall
  (`constraints/band_standoff.band_wall_vertices`: a riser's band line, a
  road page's stand-off band vertex) the nearest pavement's graded level —
  its zone ceiling, never above the pavement edge (`min(ceiling, 0)`) — as
  its FLOOR (as built in round 2: see below). The one-way floor `z[band] ≥ z[road]` (§2) still holds the
  band level with a road above it (13ar / 29r).
- **Q12 — yes:** walls stand beside DSF road pages too, not only OSM
  ribbons. **Built:** a road page that is not a ribbon is a groundside cell,
  so the band is already cut back from it by `groundside_cutback_m` — the
  riser the ribbons need §2.1 to cut is the stand-off gap itself.
  `constraints/band_standoff.band_standoffs` pairs each runway / taxi band
  ring vertex with the nearest road-page vertex across it (within the
  cut-back + weld + snap horizon, never shared); the pair takes the graded
  floor, the one-way floor, and a declared `band_road_wall` line across its
  chord (`pipeline/band_road_wall._standoff_records`). No new geometry.
- **Q13 — whole road:** an in-band road drops together, not per vertex.
  **Built:** `constraints/road_ramp._whole_roads` releases from the 10-03b
  terrace every vertex of the ribbon faces connected to an in-band vertex,
  among the ribbon faces that stand in a runway / taxi band.

Consumer census additions (§3):

| consumer | reads | interaction | ruled |
|---|---|---|---|
| `band_riser._graded_rows` (between the stages) | band vertex at a wall, stage-1 levels | a `Band` floor at the graded level, whichever generator (zones, end skirt) shapes the band | Q11 |
| `band_riser.riser_release` floors | stand-off pairs | one-way floor band ≥ road page | Q12 |
| `publication.terrace_joints_ll` | stand-off pairs | a declared line per pair where the band stands above | Q12 |
| `road_ramp.terrace_rewrite` | in-band ribbon vertices | whole connected in-band road | Q13 |
| `constraints/groundside.groundside_ramps` | APRON ↔ groundside pairs only | band vertices are not read | unaffected |

Q11 as first built (a floor raised inside `zones.zone_bands`) reached no
riser at KLAX: the band there is the runway END area, shaped by the
`strips` end-skirt rows (chord bounds −7.2..+4.2 m), not by the zone rows.
It is now ONE row off the stage-1 pavement, whatever generator shapes the
band: `constraints/band_riser._graded_rows`, a `Band` floor at the nearest
stage-1 pavement vertex's solved level + `min(zone ceiling, 0)` at that
distance, added between the stages. A riser vertex nearer a ribbon than one
weld spacing less the snap margin (a median between carriageways) is no
wall vertex (measured: a median vertex held at band level stood 3.5 m over
both carriageways at KLAX 33.94033, −118.39618).

### 7.1 Measured — round 2, two iterations (STOPPED at the cap; bars NOT met)

Same replays (frames/c944, `--from planar`), base main 8f96a4c76:

| | KBUR main → r2 | KLAX main → r2 |
|---|---|---|
| `hairline_pair` in scope | 0 → 0 | 0 → 0 |
| `hairline_pair` raw (all `above_degenerate_floor`) | 333 → 459 | 1300 → 1345 |
| `adjacent_ground_step` | 3 → 8 | 5 → 9 (3.90 m) |
| `strip_seam_tear` | 0 → 0 | 4 → 12 (3.93 m) |
| road-road rows | — | `pavement_over_road_cap` 0 → 5 (2.93 m), `terrace_actual_step` 0 → 6 (3.02 m), `road_cross_section` worst 0.81 → 2.87 m, `vertex_to_edge_step` 0 → 1 |
| 30aa added/removed | 0/0 | 6/0 (main 6/0) |

Sites:

- **KLAX 33.945963, −118.436316: the wall stands.** The band line holds its
  graded level (riser `zone2#13:riser` 26.89–31.06 m, band beyond
  29.76–32.72 m) over the road at its ground; declared `band_road_wall`
  risers of 3.94 / 3.22 m there. The census still reports the riser chords
  (`adjacent_ground_step` / `strip_seam_tear` 3.90 m over 1.0 m): the
  declared MIDLINE stops at the riser face's own end edge, so a chord along
  that edge touches it without crossing; and the declared step is the
  nearest-pair maximum, 0.01 m under a 3.23 m diagonal pair. Both are the
  declaration's geometry, not the wall.
- **#951 road** `big_roads:-2346`: 26.83–28.04 m, on its ground.
- **KBUR building9 corner (34.19628, −118.35023): still not declared.** The
  stand-off pairs VERTEX to vertex; there the nearest `dsf:pol122` ring
  vertex is 2.69 m from the band corner (horizon 1.95 m) — the census's
  1.12 m is to the road's EDGE. The pairing must read the nearest point on
  the road page's edge (and the road level interpolated there).
- **KLAX road-road rows** (33.9403, −118.3962 and 33.9344, −118.3962, the
  taxiway-F end areas): released in-band roads following their ground into
  a dip at grades over the road cap; the road's cap rows are one-sided
  targets that the DEM fit outweighs once the 10-03b terrace target is gone.
  Not attributed further.

Next round (not done): declare the midline extended through the riser's
end edges and the step as the largest pair within a few metres; pair road
pages by nearest edge point; attribute the KLAX road-road rows (the road's
own profile target inside a band).

### 7.2 Measured — round 3 (STOPPED at the cap; bar NOT met)

Round 3 items: (1) the KLAX road-road rows were attributed to riser lines
noded through a tunnel trench at 33.9403, −118.3962 (main emits only the
`tunnel_ramp` face and `tunnel_wall` there); iteration 1 (medians between
two mapped roads stay road ground) made it worse, iteration 2 keeps the
riser off every other cell (`riser_geometry(keep_out=...)`). (2) road pages
pair by the nearest point on their edge. (3) the declared riser line runs
through the riser's end edges; the step is the largest pair within 4 weld
spacings.

| | KBUR main → r3 | KLAX main → r3 |
|---|---|---|
| `adjacent_ground_step` | 3 → 3 | 5 → 1 |
| `strip_seam_tear` | 0 → 0 | 4 → 12 (3.93 m, 33.941 / 33.934, −118.396) |
| `pavement_over_road_cap` | 0 → 1 (0.21 m) | 0 → 7 (2.86 m, 33.940, −118.396) |
| `terrace_actual_step` | 0 → 5 (0.27 m, 34.214, −118.362) | 0 → 6 (3.02 m, 33.934, −118.396) |
| `road_cross_section` | 30 → 76 (worst 0.43 → 0.33) | 24 → 11 |
| hairline in scope | 0 → 0 | 0 → 0 |
| 30aa added/removed | 0/0 | 6/0 (= main) |

- KLAX 33.945963, −118.436316: **clean** — no step row left at the site
  (only the runway-end skirt rows main carries, 0.81 / 0.76 m); declared
  risers 3.24 / 3.94 m.
- #951 road: 26.83–28.04 m, on its ground.
- KBUR building9 corner: **still not declared.** The band's ring vertices
  there are 2.1–2.9 m from the nearest `dsf:pol122` edge (horizon 1.95 m);
  the census's 1.12 m is from the ROAD's vertex to the band — the pairing
  must also run road vertex → nearest band edge point.
- KLAX taxiway-F end areas (33.934–33.941, −118.396): the tunnel-trench rows
  remain after the keep-out; not attributed further.

### 7.3 Measured — round 4 (STOPPED at the cap; bar NOT met)

Base re-taken on current main (bfa6f11ac): the round-3 base (8f96a4c76)
was stale — current main emits the KLAX taxiway-F roads (`big_roads:-4266`,
`-1147`, `-313`, `-4265`) at 33.934–33.941, −118.396 as ribbons too; the
"tunnel trench" reading of round 3 was an artefact of the stale base.

Iteration 1: a riser ring vertex within one identity spacing + snap of a
ribbon's ring (`law.tables.riser_kerb_near_m`) is the KERB — the emit welds
it onto the ribbon (measured: KLAX 33.94047, −118.39619, a riser vertex
0.5 m off a second carriageway, held at the band's level, shipped inside
that road's way 2.9 m over it). It is the road side of the cut and release,
and `zones.zone_bands` gives it the kerb's cap only. KLAX
`pavement_over_road_cap` 7 → 1 (0.15 m).

Iteration 2: stand-off pairs from both sides (road vertex → nearest point
on the band's edge); the declared riser step counts the band vertices
within 4 weld spacings of the kerb.

| | KBUR main → r4 | KLAX main → r4 |
|---|---|---|
| `adjacent_ground_step` | 3 → 4 | 5 → 3 (3.68 m) |
| `strip_seam_tear` | 0 → 0 | 4 → 14 (3.96 m) |
| `terrace_actual_step` | 0 → 0 | 0 → 6 (3.02 m) |
| `pavement_over_road_cap` | 0 → 1 (0.21 m) | 0 → 1 (0.15 m) |
| `runway_end_skirt` | 3 → 16 (1.57 m) | 1 → 6 (1.32 m) |
| hairline in scope | 0 → 0 | 0 → 0 |
| 30aa added/removed | 0/0 | 6/0 (= main) |

- KLAX 33.945963, −118.436316: clean (only main's end-skirt rows); the
  #951 road on its ground.
- KLAX taxiway-F (33.934 and 33.940, −118.396): the in-band roads sit on
  their ground 3–4 m under the band's graded level — walls by 19a/19i/Q11 —
  and the census's chords there (3.5–4.5 m, band beyond the riser to road)
  still exceed the declared riser; `terrace_actual_step` reads two roads at
  different levels (`-313` at 27.3 m, `-4265#1` at 30.2–31.8 m) across a
  declared riser.
- KBUR building9 corner: still not declared. In the PLANAR map the gap
  between the band ring and the `dsf:pol122` ring is 2.1–2.9 m (edge to
  edge), past the stand-off horizon (cut-back + weld + snap, 1.95 m); the
  census's 1.12 m pair is between EMITTED vertices. The gap is wider than
  the stand-off law makes it; why is not attributed.
- KBUR/KLAX `runway_end_skirt` rows are new: the Q11 graded floor (zone
  ceiling off the nearest pavement) lifts band vertices in a runway END
  area above the end-skirt profile there.

### 7.4 Round 5 (the master's last round on #951)

- **The walls are declared at their actual height along the whole strip.**
  `pipeline/band_road_wall` declares one `wall_terrace` record per segment
  of each riser's midline, at the largest step between a vertex on one side
  and one on the other within four weld spacings (band, road, or the next
  road across a narrow band). The owner ruled walls in safety areas
  correct, so the KLAX taxiway-F roads at their ground, 3–4 m under the
  band, are lawful walls; the roads are not raised.
- **In a runway end area the graded level is the end profile's.** Q11's
  floor for a wall vertex the `strips` runway-end profile chord row governs
  is that row's own level — its foot on stage-1 levels moved by the bound
  nearest zero — never the nearest pavement zone's
  (`constraints/band_riser._end_profile_levels`, at the one derivation site
  of the graded floor).
- **KNOWN RESIDUAL — KBUR building9 corner (34.19628, −118.35023), not
  declared.** In the PLANAR map the band ring
  (`adjacent_ground:taxi:C:zone2#36`) and the `dsf:pol122` road page's ring
  stand 2.1–2.9 m apart edge to edge, wider than the stand-off the zone
  cut-back makes (`groundside_cutback_m` + weld + snap = 1.95 m), so no
  stand-off pair is formed from either side; the census's 1.12 m reading is
  between EMITTED vertices. Why the planar gap is wider than the cut-back law
  is not attributed (filed by the master). The step reads only as the
  `groundside_cutback` terrace class (19l), 2.69 m over 1.12 m.

Measured (frames/c944 `--from planar`, base = main d384d336c; STOPPED at the
cap, bar NOT met):

| | KBUR main → r5 | KLAX main → r5 |
|---|---|---|
| `strip_seam_tear` | 0 → 2 (1.03 m) | 4 → 45 (4.6 m; 41 at taxiway F 33.934–33.941, −118.396) |
| `adjacent_ground_step` | 3 → 10 (1.03 m; 5 at the #949 road 34.197, −118.349) | 5 → 14 (3.68 m) |
| `terrace_actual_step` | 0 → 0 | **0 → 0** (round 4: 6) |
| `runway_end_skirt` | 3 → 16 (1.57 m, unchanged) | **1 → 0** |
| `pavement_over_road_cap` | 0 → 1 (0.21 m) | 0 → 1 (0.15 m) |
| hairline in scope | 0 → 0 | 0 → 0 |

Iteration 1 held the end-area band FLUSH with the runway end (the bound
nearest zero): KLAX `strip_seam_tear` 4 → 104 (6.6 m), KBUR
`runway_end_skirt` → 33. Iteration 2 holds it at the end profile's lowest
lawful level: KLAX's end skirt clears, KBUR's 16 rows are untouched (their
vertices carry no end-profile chord row, so the zone level still lifts
them).

The per-segment declaration cleared `terrace_actual_step`, but the
band-to-road `strip_seam_tear` / `adjacent_ground_step` chords at taxiway F
are not forgiven: those census readings pair nodes 1–4.5 m apart whose
chord does not cross a declared segment (the riser midline runs only where
the riser face is; the chords run past its ends and between the ribbons'
own split pieces). Round 4 (`1a14e3965`) read KLAX `strip_seam_tear` 14.

### 7.5 Handoff (lane m3 → the next lane, 2026-10-20)

This branch is round 4 (`1a14e3965`) plus round 5's end-area change (`band_riser._end_profile_levels`: in a runway end area the wall's graded floor is the end-profile chord row's lowest lawful level). Round 5's per-segment wall declaration (§7.4 item 1) is NOT on this branch; it is kept on the local branch `m3-951-r5-backup` (fd8c32ca6). Its measurement against main d384d336c was: `terrace_actual_step` cleared, but KLAX `strip_seam_tear` went from 14 to 45.

Open problems:
1. **Taxiway F, KLAX (33.934–33.941, −118.396).** The in-band roads sit 3–4 m under the band, and these are lawful walls ("for roads in safety area, wall is correct"). The census's band-to-road chords there are 1–4.5 m long and run past the wall-strip ends and between the ribbons' split pieces, so they cross no declared line. The next move is probably a declaration along the band's own edge facing the road, not the riser midline, or an extension through the riser's ends.
2. **The KLAX wall site (33.945963, −118.436316).** It read clean in round 4 and showed one `adjacent_ground_step` of 0.83 m over 1.0 m in round 5. Re-measure it on this branch first.
3. **KBUR end-skirt rows (34.214, −118.362 and 34.193, −118.356; `runway_end_skirt` 3 → 16).** Their wall vertices carry no runway-end profile chord row, so the graded floor still comes from the zone off the nearest pavement and lifts them above the end profile. Find which end-area rule binds those vertices (`strips.end_band_vertices`, or the transect / foot rows) and read the floor from that rule.
4. **KBUR building9.** This is the known planar-gap residual in §7.4; the master is filing it.

Replay recipe: frames/c944 KBUR and KLAX `--replay --from planar --emit`, plus a fresh main base for each, then `tools/harness/census.py` from this branch's tree. That tree carries the 19l exemption.
