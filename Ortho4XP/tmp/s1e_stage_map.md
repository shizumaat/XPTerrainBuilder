# S1e PHASE 1 — THE POST-SOLVE STAGE MAP (lane `lane/s1e`)

Tree: worktree `s1e` at `0802aac` (= `main` tip, every round merge + rim
pockets ON).  Instrument: `geom_guard.seam_checkpoint` / `seam_report`,
armed by `O4_GEOM_SEAM_AUDIT=1`, hung off the seam list the pipeline
ALREADY marks (`pipeline._rod_ckpt` — the same seams the rod-carry and
mutation-seam audits use; no seam invented).  Gate off ⇒ one env read, so
a default build is byte-identical.

BYTE-INERTNESS PROVEN, not asserted: three armed CYXY `--patch-only` arms
at this tree all emit `body_sha=a4aa1654431a`, the 2026-08-14 round-close
reference body (`/tmp/harness/round_close_cyxy.osm`, 428 shapes).  The
instrument is therefore also the lane's clean control.

## What the guard's 914 actually measures

`report_post_solve_changes` compares against a snapshot taken at
`pipeline.py:5368` — BEFORE the geometry freeze — and its population,
`geom_guard._AIRSIDE_ROLES`, INCLUDES `ROLE_SERVICE_JUNCTION`, which
`layout.GROUNDSIDE_ROLES` puts on the GROUNDSIDE side of the solve
partition (it is a projection RECEIVER, stage B).  So the headline number
mixes three different things:

  1. genuine airside plan-geometry refinement,
  2. lawful stage-B service seating (`seat_service_pavement_on_law`,
     `pipeline.py:6267` — rings the one solve never reached), and
  3. additive post-solve emission.

Reading it as one population is the two-instruments/one-assumed-population
trap.  The seam ledger splits it at the source.

## The two carry laws (RULINGS 2026-08-14, the ruling's own words)

"a cut vertex interpolates along its edge, a weld adopts the precedence
winner's value, a densified vertex interpolates its span".  So an inserted
vertex is VALUE-PRESERVING when EITHER

  * its altitude is the linear interpolation of the two surviving vertices
    bracketing it on the ring (cut / densify / crossing-resolution), OR
  * its altitude equals the value another shape already carries at that
    exact coordinate (weld: a shared node has ONE value — scoring a weld
    against the host edge's lerp would demand it re-tear the seam it was
    run to close).

An insert that is neither, and any surviving airside vertex whose value
moved with no carry law, is the RE-PROJECTION CLASS: a value only a
projection can justify.  That is the number the ruling drives to zero.

## The map — CYXY (`s1e_p1c_cyxy`, 40.9 s, body `a4aa1654431a`)

Baseline is the solve's exit (`00_post_solve`); seams before it are not
post-solve stages, and diffing across the solve would book the solve's own
work as a value move.

| seam (stage) | airside geometry | carried | RE-PROJECTION CLASS |
|---|---|---|---|
| `01`–`08` (transition emit, bridge post-proc, tile cut, road deconflict, feature conformance, ribbon seam, dedup, flatedge) | INERT | — | 0 |
| `09_planarize_airside` | 49 shapes, pure INSERT, 99 vertices | 34 lerp + 65 weld | **1** (one runway vertex, \|dz\| < 0.0001 m) |
| `10`–`15` | INERT | — | 0 |
| `16_repair_sliver_corners` | 21 shapes, pure DROP, 25 vertices | all survivors held | 0 |
| `17` (late densify) | INERT | — | 0 |
| `18_emit_decimate` | 174 shapes, pure DROP, 2,353 vertices | all survivors held | **1** (same runway vertex, sub-materiality) |
| `19_final_projection_mid` | no geometry change | — | PROJECTION AUTHORED 384 values |
| `20`–`21` | INERT | — | 0 |
| `22_weld_crown_densify` | 10 shapes (6 insert, 4 move), 11 vertices | 7 lerp + 4 weld | 0 |
| `23_final_projection_late` | no geometry change | — | PROJECTION AUTHORED 52 values |
| `24`–`26` (spine reclamp, strip reconcile, band seal) | INERT | — | 0 |

**TOTAL RE-PROJECTION CLASS: 2**, both the same runway vertex at
(374.9, −927.7) moving by less than the 0.0001 m the report rounds to —
PASS-with-residual under the standing materiality floor (0.01 m).
Stage-B service seating: 112 vertices, lawful groundside partition.

### The finding

**Post-solve refinement is ALREADY value-preserving at CYXY.**  Every
geometry operation between the solve and emit carries its values: the
decimators drop 2,353 vertices without moving a survivor, planarize's 99
inserts are all lerp or weld, the late densify and crown completion carry
theirs.  Clause (1) of the ruling is not a large body of missing work at
this airport — it is a rail that needs to exist and be enforced.

**What the projections actually do is therefore NOT repair of un-carried
refinement.**  They author 384 + 52 values that no carry law produced, on
law pairs that only exist on the FINAL rings: decimation removes vertices,
so a chord between two SURVIVING vertices spans what used to be a polyline
and can exceed its cap although every sub-chord was lawful.  That is a
genuine law question about the geometry X-Plane renders, and it is
answerable ONCE, after all geometry settles — which is exactly the
collapse the ruling orders.

## The map — HECA (`s1e_p1c_heca`, 397 s, body `3c084a212d0f`)

| seam (stage) | airside geometry | carried | RE-PROJECTION CLASS |
|---|---|---|---|
| `01_terrain_transition_emit` | 9 new / 9 removed shapes | — | 0 |
| `09_planarize_airside` | 363 shapes (359 ins, 4 move) | 284 lerp + 864 weld | **5** (all `service_junction`, worst 0.114 m) |
| `11_building_pad_reclip` | 1 shape, 1 insert | 1 lerp | 0 |
| `16_repair_sliver_corners` | 71 shapes, 240 dropped | survivors held | 0 |
| `18_emit_decimate` | 1,176 shapes, **17,514 dropped** | survivors held | **0** |
| `19_final_projection_mid` | — | — | PROJECTION AUTHORED 11,256 |
| `20_post_projection_conformance` | — | — | **8** (the named pad-host relevel LAW: building+apron at (−2500,1407) 88.500 → 85.550) |
| `22_weld_crown_densify` | 98 shapes, 6 new | 79 lerp + 36 weld | **3** (2 `service_junction`, 1 junction 0.019 m) |

**TOTAL RE-PROJECTION CLASS 13** — 5 + 3 on `service_junction` (a
stage-B role) and 8 that are a named law pass.  17,514 decimated vertices
and 1,148 inserts carry perfectly.  The guard's headline 914 decomposes
as apron 83 / building 6 / junction 570 / runway 3 / **service_junction
235 + 9 new + 8 removed** — 252 of the 914 are the stage-B role.

## PHASE 2 — the collapse, both directions, measured

The spec's parenthetical expected the LATE position to survive and told
the lane to re-measure.  Both arms were built at all three airports.

| | projection exit, over-cap edges | census vs reference |
|---|---|---|
| control (mid **and** late) | HECA 7107 → 7861; CYXY 55 → 80 | HECA 7139, CYXY 328, OTHH 5874 |
| **late-only** | HECA **8933**; CYXY **85** | HECA **+263**, CYXY **+4**, OTHH −9 |
| **mid-only** | HECA **7107**; CYXY **55** | HECA **+116**, CYXY **+0 (EXACT)**, OTHH **−11** |

**THE MECHANISM (read off the projection's own exit line).** The mid call
runs with 9,791 hard nodes at HECA; the late call with 20,213.  Post-solve
FEATURE emission is what doubles the hard set — "nodes welded to
already-emitted FEATURE shapes are HARD" is the projection's own contract
— so by the late position half of airside is frozen and the projection can
only nudge what remains.  The two calls were never a duplicate pair: the
mid call is the only one that runs while airside pavement is still FREE,
and that freedom is law-solving power no value-carry hands back.
**Mid-only is therefore the collapse direction**, inverting the spec's
guess.

### THE STOP — HECA's residual +116

Mid-only is exact at CYXY and an improvement at OTHH, but costs +116 rows
at HECA, row-attributed:

| family | Δ | new sites, by role |
|---|---|---|
| `within_shape` | +89 | 134 `apron|apron`, 17 `service_junction`, 13 `junction`, 7 groundside (worst 5.85 m) |
| `mid_edge_step` | +21 | **42 of 45 `service_junction`** (worst 2.96 m) |
| `vertex_to_edge_step` | +3 | **9 of 9 `service_junction`** |
| `transverse` | +2 | **41 of 49 `service_junction`** |
| `frontage_near_miss` | +1 | 1 `building|service_junction`, 1 `building|junction` |

Two distinct causes, and they are not the same finding:

1. **STAGE-B SEATING RELIES ON A LATER PROJECTION.**  The step families
   and most of `transverse` are dominated by `service_junction` — the
   role the post-solve law seating (`seat_service_pavement_on_law`,
   `seat_groundside_on_law`) authors, 1,857 vertices at HECA in this arm.
   The late projection was closing that seating's own steps.  Under the
   staged solve, stage B is supposed to produce a lawful groundside
   surface itself; that it does not is a stage-B defect this lane
   surfaces but does not own.

2. **AIRSIDE `apron|apron` +134 sites, worst 5.85 m.**  This is an
   airside delta attributed to the late call's retirement but NOT
   explained by any un-carried refinement — the carry ledger for the
   stages between is 0/0/3.  Whether these rows should be closed by
   making stage B lawful, by a third mechanism, or accepted, is an
   adjudication above this lane's charter.

**Neither collapse direction reproduces HECA's reference census.**  The
lane leaves mid-only committed as the best-measured state and STOPS here
rather than merging a +116 airside regression.
