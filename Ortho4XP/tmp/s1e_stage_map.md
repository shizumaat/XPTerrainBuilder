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

### Stages that genuinely REQUIRE a re-projection

None found at CYXY.  No stage's mutation forces a law re-derivation that
interpolation or weld adoption cannot carry; the residual 2 vertices are
sub-materiality float noise on one runway node.
