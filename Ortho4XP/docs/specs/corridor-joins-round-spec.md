# Corridor-joins round (Fable spec, 2026-08-12c)

Owner in-sim on 1.0.244 refuted two corridor acceptance claims at KCLT;
both attributions are complete and this spec is built on them. PRE-SHIP
mode; deviations STOP-and-report to this spec's author; RULINGS.md
canonical.

## Evidence (measured on the owner's 1.50.1687 tile artifact)

SEAM (35.213852,-80.9406291 and the far side):
- The minter cuts the corridor back from ALL aircraft pavement by
  `_PAV_CLEAR_TOL_M` = 1.0 (service_roads.py:244 `pav_union.buffer`,
  :276 `corridor.difference(pav_buf)`), but conformance welds only to
  0.5 m (`SHARED_VERTEX_TOL_M`, conformance.py:58) — every road↔taxiway
  seam is UNWELDABLE BY CONSTRUCTION (measured gaps 0.999 m both sites).
- The 1 m annulus is filled by a graded_strip carrying BOTH claims
  (road 216.95, taxiway 219.23); `emit_stacked_conflict_walls`
  (adjacent_ground.py:2680, face :3051-3055) consults ONLY the
  runway-strip keepout — `service_corridor_wall_keepout` is wired into
  the terrace pass alone (:3584, :3821-3822) — so it walls the 2.3 m
  conflict (way -13314). Far side: same gap, no wall, bare 2.0 m step.
- Mouth adoption (grade_graph.py:2582-2587) is vertex-based; it fired
  only where the axis met an existing airside VERTEX (apron node -7109,
  shared 4 ways — that mouth is perfect) and cannot fire mid-segment on
  a taxiway edge. No node anywhere is shared between road-family and
  taxiway ways.

FREE END (35.2077054,-80.9290667):
- `SERVICE_CORRIDOR_FREE_END` gates ONLY the wall keepout
  (adjacent_ground.py:499-501) — it seeds nothing. The DEM operator
  `apply_service_road_dem_follow` (anchors.py:3384) includes the
  pavement, but its spine-first seeder (:3145-3147) recognizes only
  row-1206 `is_service` centerlines — feed-sourced corridor chains
  (layout._service_corridor_lines) are invisible, so this road got the
  per-vertex fallback whose seeds are SOFT (:3104-3107, projections are
  the sole writer). Result: road descends 2.9% against an 8% cap and
  ends 6.31 m proud of DEM at the lane's own acceptance coordinate.
- The old terrace wall -12626 held that bench; the wall-course
  exclusion removed it and NOTHING graded the transition — the 10 m
  cliff sits on the wall's footprint. shapeID 884 (way -10885, 40.4 m²,
  ref=service) is lawful minter junction fill at the axis terminus.

ACCEPTANCE-INSTRUMENT DEFECT: the prior claims quoted pavement-internal
alt ranges and census-row ABSENCE. Rows exist only between paired
geometry — unwelded pavement is silent. Never again.

## Rulings

1. **Corridor mouths JOIN aircraft pavement.** At each axis
   crossing/terminus into aircraft pavement, the mouth's rect extends
   to the PAVEMENT EDGE ITSELF (difference against `pav_union`, not the
   1.0-buffered union) so corridor boundary nodes land ON the airside
   edge within weld reach and `enforce_conformance` welds them: shared
   nodes, ONE altitude at the seam. The corridor BODY keeps the 1.0 m
   clearance everywhere else (roads still never overlay pavement
   mid-run). THE SEAM VALUE IS THE AIRSIDE VALUE — airside is king: the
   weld may never move the airside ring's solved value; the road grades
   away from the seam under its 8% cap (the mouth-adoption law already
   provides the grade edge; now the geometry exists too). Twin: a mouth
   weld leaves the airside ring's values byte-identical; the road-side
   node adopts the airside value exactly.
2. **`emit_stacked_conflict_walls` consults the corridor keepout** with
   the same drop test as the terrace pass (belt — with ruling 1 the
   conflict should not arise at mouths at all; the keepout still stops
   edge-parallel conflict walls along the corridor course).
3. **Free ends get a HARD DEM tie.** The spine seeder consumes the SAME
   corridor chain set the grade graph registers (single source — feed
   chains included, not just 1206 `is_service`); a chain terminus not
   on pavement receives an ANCHORED end target = ambient DEM at the
   terminus, descending within the road cap (this is R20-2's
   walk-to-ground law made general). The seed must survive projection —
   it is a law target, not a soft seed. Where the wall-course exclusion
   suppresses a wall, the road's own descending surface now owns the
   level change; terminal junction fill (the shapeID-884 class) rides
   the same profile.
4. **Acceptance instruments.** Every corridor claim must quote:
   (a) seam-weld evidence — count of shared node refs between
   road-family and airside ways per mouth, with the max |Δalt| across
   each seam (0.00 by construction); (b) free-end DEM offset — pavement
   minus DEM at each chain terminus (|offset| ≤ 0.01 m); (c) the
   census afterward (secondary, never primary). Pavement-internal
   ranges and row-absence are not acceptance evidence.

## Implementation plan (ONE Opus lane; fan-out all arms simultaneously)

1. blast.py per file; ledgered tests once; twins per ruling (mouth
   geometry weld + airside byte-identity; stacked-conflict keepout
   consultation; seeder single-source over corridor chains incl. a
   feed-only fixture; hard free-end tie surviving a projection pass;
   the wall-exclusion + descent composition on a synthetic bench).
2. Implementation sites (from the attributions): service_roads.py
   mouth carve; adjacent_ground.py:3051 keepout test; anchors.py
   :3145-3147 seeder population + free-end anchor; verify
   grade_graph corridor-chain single-source is consumed, not forked.
3. Acceptance arms (FAN OUT in one launch): KCLT + CYXY + KSTJ + HECA
   --patch-only on the lane tree, plus the pre-round tree served from
   the artifact ledger as controls.
   - KCLT site 1: wall -13314-class GONE both sides; each road↔taxiway
     mouth has ≥2 shared nodes; max seam |Δalt| 0.00; airside ring
     values byte-identical to control at the taxiways.
   - KCLT site 2: terminus DEM offset ≤0.01 m; profile ≤8% end-to-end;
     no cliff on the old wall footprint (quote a transect).
   - HECA: airside deltas vs the 1.0.244 state must be the
     seam-joining class ONLY (rows whose pair includes a road↔airside
     seam node); any off-seam airside movement is a STOP (the +130
     disclosed residue stays as-is, neither grown nor claimed fixed).
   - CYXY/KSTJ: not byte-identical expected (mouths now weld) — quote
     the seam-weld tables and census deltas.
4. Build-time impact statement; materiality 0.01 m; attempt cap 2;
   `.progress` heartbeat; shared repo UNCHANGED; commit on the lane
   branch; no merge.

## Out of scope

The staged-solve architecture round (HECA +130 residue, rim pockets,
absorption); relief-round groundside items beyond the corridor's own
free ends; tunnel portal machinery; orthophoto-loss hardening (separate
infra item).
