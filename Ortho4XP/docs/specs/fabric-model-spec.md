# The fabric model — sparse lawful emission — spec

Author: lead (Fable), 2026-08-08. Charter: the 2026-08-08 owner
ruling "THE FABRIC MODEL" (RULINGS — read the verbatim and all four
scope answers). This spec REPLACES the planned relief-generation
round (retrospective structure #2). The walls-to-carves, feather,
frontage-weld-authority, and mouth-fed-banding rulings all fold into
this model.

## The owner's design, verbatim thought experiments (canonical)

1. "Take two squares… place them 50m apart at 100m flat elevation.
   In the −500m world you will have two plateaus high above the
   world, and the terrain will naturally drop to the mid point
   between them because the Ortho4XP engine already creates the
   triangles to blend patch shapes into the DEM. In the +10,000m
   world, the same, only two deep holes with steep terrain climbing
   up on all sides. [On sloping DEM] two flat shelves, cut in on one
   side, raised on the other. We simply need to grade our pavement
   and building pads, and Ortho4XP will automatically blend the
   surrounding terrain."
2. "A rectangular apron 50m × 100m, sloping along its long axis…
   three buildings on one long edge… a taxiway along the opposite
   edge. Chords from the building frontage go straight across to the
   taxiway at 1%, but the nodes along the back edge of the apron
   should be welded to the building corners; if we place no nodes
   between the buildings, and each building is at its correct seat,
   then the back apron edge between the buildings will automatically
   slope between them."

## The model

1. **The solve distributes** the pinned spread (CIFP/runway anchors)
   through the route network under caps — unchanged law, and proven
   feasible (fp#8 ladder: pure law satisfiable at HECA, 742 rows @
   0.08 m). There is no capacity deficit; nothing "generates relief."
2. **Emission is sparse and law-carrying**: a node exists only where
   the law needs a vertex — seats, welds, mouths, boundary direction
   changes, reg features — PLUS (owner rider) adequate nodes on
   SPINES (the route profile must be expressible) and at CURVES
   (chord fidelity; the existing curve/chord machinery defines
   "adequate" — measure, don't invent). Between law vertices,
   interpolation IS the lawful surface, and the census measures the
   same sparse fabric the sim renders.
3. **Explicit shaping only in the REG SET**: runway strips (Annex-14
   graded strip), RESA/OFZ where the standards demand graded
   surfaces, and drainage — runway crowns, pavement-edge slopes, and
   (owner rider) drainage requirements ALONG ALL TAXIWAYS. Region-
   keyed per the rulesets ruling; values PRIMARY-VERIFIED per the
   standards-gap review.
4. **Unregulated ground: NOTHING.** No bands, no rings, no fan
   zones, no emitted feather — the drape (Triangle blending patch
   shapes into the DEM) is the transition. Walls exist only at carve
   structures (standing ruling).

## Retire list (each with twins proving the successor behavior)

Fan-zone declarations and machinery; general-purpose adjacent-ground
band rings outside the reg set; stationing density beyond the
adequate-spine/curve floor; the relief vocabulary in the census
(exemptions become unnecessary where no dense rows exist to exempt).
The parked frontweld hygiene (lane/frontweld 2d2a8e7) re-measures and
re-lands inside this round once −10447 grades.

## Phases

- **Phase 0 — standards enumeration (research, no code)**: the exact
  FAA/ICAO requirements for strips, RESA/OFZ graded surfaces, and
  drainage (crowns, pavement-edge, taxiway-edge): dimensions, slopes,
  applicability, per ruleset; mapped against existing machinery
  (keep/retire/build). Feeds the reg-set implementation.
- **Phase A — the proof pair (gated, in-lane)**: sparse emission for
  the apron −10447 cluster and the CYXY hillside group. Acceptance:
  the −10447 class (1,373 rows in the current frame) reads ~0 on the
  sparse arm with NO exemptions; the solve's distribution is quoted
  (how the 11 m routes through the neighbors); mesh clean (sliver
  bands, no long-triangle artifacts — quote the area-bands table);
  node count on the arm vs today quoted; CYXY hillside Δ-clean and
  visually plausible (owner sim look). Budget 4 builds + 2 mesh runs.
- **Phase B — the overhaul**: the emission model switches, the retire
  list executes, battery re-reads (sites + actionable under the
  floor), sim pass. Scoped after Phase A reports; its spec revision
  carries Phase A's measured constants ("adequate" spine/curve
  density).

## Guards

Phase A is gated and in-lane; production emission is untouched until
Phase B. Deviations: STOP-and-report for Fable review. Every
comparison arm matched, frames labelled. Build-time expectation:
sparse emission should be FASTER everywhere (fewer nodes, fewer
constraints, smaller mesh) — any slowdown is a finding.
