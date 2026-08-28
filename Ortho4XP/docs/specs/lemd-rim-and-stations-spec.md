# LEMD round 2 — stations weld or stand down; the trench outranks
# pavement at its rim; the rim seats at the SOLVED neighbour
# (Fable spec, 2026-08-28; RULINGS 2026-08-28 items 1–3, attribution
# lane/lemd123 cfae6daa)

## §0 Measured frame (lane/lemd123 report; patches pv_on/off_lemd,
## padvars_on, pv_on_spjc, pv_on_cyxy)

- Item 1: `apron_spine_stations._free` guards candidates against plan
  VERTICES only (0.5 m STRtree) — no EDGE test — and aircraft axes are
  routinely collinear with the apron slice boundaries, so stations
  land ON shared ring edges as unwelded T-vertices: 144 on-edge nodes
  across four airports (LEMD 76, HECA 29, SPJC 33, CYXY 6/6), every
  one on a TWO-host shared boundary; hosts 121 apron / 23 junction;
  worst value tear 0.907 m (CYXY). The lattice population is clean —
  the defect is the station minter alone. The two near-collinear
  constrained segments ~2 cm apart are additionally the documented
  mm-jitter segment-recovery killer, so a value-only patch cannot fix
  the tear.
- Item 2: building8's pad variable is EXONERATED (identical 600.50 in
  both arms, domain sampled wholly outside the pan, yield in force —
  the pan emits at 100 % of authored). The real gap: the 2026-08-26
  trench-seniority implementation scopes its yield population to
  `ROLE_BUILDING` (`object_terrain_assembly.py:3516`), so apron -10228
  — standing 0.70–0.89 m off the pan along one 98 m run — consumes the
  floor cutback AND the whole 0.6 m rim band there: a 12.75 m unwalled
  drop at exactly the owner's coordinate. Rim coverage 289/338
  perimeter samples; every missing sample has pavement < 0.9 m away.
- Item 3: each rim band part seats at the RAW DEM at its own centroid
  (`object_terrain_assembly.py:3944-3959`; R_est is only the nodata
  fallback). Measured: all 13 LEMD rim parts LOW vs their nearest
  built neighbour, median −3.84 m, worst −5.41 m vs building8's
  600.50; 4.14 m of rim self-spread from per-part DEM sampling; a
  67 m nodeless span between rim (595.2/597.8) and apron (599.98)
  reads as the owner's visible down-slope. Collides with DEM-LAST and
  with the basin-rim-flush spec's own unimplemented §1(2).

## §A STATIONS WELD INTO THE MEMBRANE, STAND DOWN ON SENIORS

1. `apron_spine_stations` gains the EDGE test `_free` lacks: a
   candidate whose foot lies within `SHARED_VERTEX_TOL_M` of a ring
   EDGE (strictly interior, endpoint-clear) is never minted as a free
   node. Disposition by the host edge's role (max-tier over both
   hosts of a shared boundary):
   (a) APRON-family hosts → T-VERTEX WELD: insert the station into
   EVERY host ring at the edge lerp (the `crown.
   _weld_terminus_into_rings` case-(b) transplant — index-aligned
   ring + node_altitudes rebuild), ONE node, and THE STATION VALUE
   WINS (round-3 Amendment 1: station values are phase-A constants;
   the membrane side is what yields). The geometric tear closes
   because there is one geometry, not two segments 2 cm apart.
   (b) TAXIWAY-family hosts (junction/taxiway/stub/primary_parallel)
   → the station STANDS DOWN (not minted): that ground already
   carries the anchored surface the station would re-state, and
   round-3 Amendment 2's gate 2a (taxiway-family byte-identity vs
   stations-OFF) is preserved by construction. Log count per airport.
2. Acceptance: the on-edge-unwelded population (the lane's sweep,
   promoted per §D) goes 144 → 0 across the four patches; taxiway-
   family byte-identity re-asserted; owner site 40.4968469,-3.5645062
   carries welded vertices with one value; census honest A/B (apron
   rings gain vertices — rows may move).

## §B THE TRENCH IS SENIOR TO PAVEMENT AT ITS RIM

1. RULING (extends 2026-08-26 "trench senior to every pad/building
   authority" to pavement, on the owner's item-2 intent): within the
   below-grade region AND its rim band, PAVEMENT authority yields
   exactly as building authority does. Mechanically: the yield
   population at `object_terrain_assembly.py:3516` widens from
   `ROLE_BUILDING` to include pavement shapes overlapping
   pan ∪ rim-band; a pavement shape is CLIPPED back by the rim-band
   width where it overlaps (the rim band must exist along 100 % of
   the pan perimeter — the apron edge then abuts the rim's OUTER
   edge, never the pan). Geometry/welds/identity of the pavement
   shape otherwise untouched (the Amendment-3 authority-yield
   mechanics, third population).
2. Acceptance: rim perimeter coverage 289/338 → 338/338 (100 %); the
   98 m unwalled run at 40.4910231,-3.5688464 carries rim (and wall
   where the wall law asks); no pavement vertex inside pan ∪ band.

## §C THE RIM SEATS AT THE SOLVED NEIGHBOUR, DEM LAST

1. RULING (the owner's item 3 verbatim + DEM-LAST): a rim band part's
   value is the SOLVED adjacent built surface, not a DEM sample. Per
   part, in priority order: the value of the nearest ANCHORED built
   neighbour within a window (a seated pad's value; an apron/
   groundside ring lerp at the adjacency) → `R_est` (the law median)
   where no built neighbour reaches → raw DEM only as the final
   nodata fallback. One value source, the existing
   `born_flat_solver_plate` unchanged otherwise.
2. Consequence measured against §0: the 13 LEMD parts converge to
   their neighbours (~599–600.5 next to building8/apron) instead of
   595–599 DEM; the rim self-spread collapses to the neighbours' own
   lawful variation; the rim-to-apron slope the owner saw flattens
   because both ends are now the same surface family.
3. Acceptance: rim parts within 0.01 m of their §C source; the three
   §0 transects re-read (T_SW's 67 m span now runs level-to-level);
   the owner's "rim level with apron" read verified at the T4S pit;
   OTHH non-regression (its bowls keep authored depth — floors are
   untouched; only the rim VALUE source changes).

## §D Shared

- The lane's `station_edge_sweep` promotes as an `--on-edge`
  subcommand of `tools/lattice_overlap_read.py` (same parser
  contract), INDEX row + twin, per RULINGS 7e90032.
- Twins per section (edge-test suppression + weld value + junction
  stand-down; pavement clip + full-perimeter rim; neighbour-valued
  rim with each fallback rung); flag per section (`O4_STATION_EDGE_
  WELD`, `O4_TRENCH_PAVEMENT_YIELD`, `O4_RIM_SOLVED_NEIGHBOUR`), all
  default ON, OFF byte-identical each.
- Acceptance builds: ONE LEMD + ONE HECA (stations touch every
  airport) + OTHH if the artifact ledger serves it cheaply; census
  A/B honest; SPJC/CYXY station sweep re-run.
- Convergence guards: materiality 0.01 m, attempt cap 2, STOP on
  second miss, heartbeat; no shared-repo writes; no timing claims;
  build-time statement.

## Amendment 1 (Fable, 2026-08-28 — rulings on the lane's two STOPs;
## attempt cap resets for §B/§C, cap 2)

Measured (lane/lemdrim 143d76bc): §A/§D complete (on-edge 144 → 0,
feature×ring needle pairs 0 at all five airports, rim 338/338, OFF
byte-identical). Two residuals:

1. **A PAD RING IS A STAND-DOWN HOST FOR EVERY WELD — a pad is ONE
   flat value by definition.** The §B rim/pan rings ran along
   building8's yielded pad ring and the final weld inserted their
   nodes into it: 19 nodes at one value → 71 at three (600.50/596.30/
   587.75), LEMD census 3205 → 4781 with 1,421 building|building rows
   to 12.75 m. Ruling: the weld machinery (the §A inserter AND the
   generic final weld) treats ANY building-pad ring as a stand-down
   host — foreign-valued nodes are NEVER inserted into a pad ring
   (this is the flatness invariant §1.1 of pads-as-band-variables
   already states, enforced at the geometry layer). Rim/pan geometry
   may ABUT the pad ring; ownership of the rim band stands (§B
   unchanged); only the node insertion is forbidden. The
   Amendment-3 wall-setback mechanics are untouched. Expected: LEMD
   census returns to its §B-lawful level with rim coverage kept —
   report the number honestly.
2. **THE RIM RE-SEATS POST-SOLVE (the staged/adoption precedent).**
   §C rung 1 cannot fire pre-solve — no neighbour carries a value
   yet. Ruling: the pre-solve plate keeps `R_est` as its SEED; a
   post-solve re-seat pass (beside the existing adoption/writeback
   passes) re-values each rim part from its nearest SOLVED anchored
   neighbour within the window (one-directional adoption — the
   neighbour never moves), `R_est` where none reaches, DEM only as
   nodata. Acceptance: the §0 rim table re-measured — parts converge
   to their neighbours (~599–600.5 beside building8/apron), the
   rim-to-apron transects read level-to-level.

## Amendment 2 (Fable, 2026-08-28 — the declared pit wall is
## step-exempt BY DECLARATION; cap resets for this one change)

Measured (lane/lemdrim 434ff906): §1/§2 complete (building8 one flat
value, rim 18/18 adopted at 600.47, T_SW level-to-level). The LEMD
census rose 3205 → 5004 entirely on mid_edge/vertex_to_edge steps at
the pan↔rim boundary — 1,932 tunnel_trench|tunnel_trench rows pricing
the PIT WALL ITSELF (587.75 vs 600.47), now fully emitted because §B
put the rim on 100 % of the perimeter. Ruling:

1. The pan↔rim boundary is a DECLARED WALL — the trench law's own
   designed step, like a declared terrace. The emitter PUBLISHES each
   pan↔rim joint into the census's existing declared-step register
   (the terrace_joints mechanism — extend that register, never a
   role-based blanket exemption), and the census exempts EXACTLY the
   declared joints: an undeclared trench step still prices. The
   building|tunnel_trench standoff rows at the pad face are the same
   declaration (the pad abutting the pan is §1's ruled geometry).
2. Acceptance: LEMD census re-read with the declarations in place —
   expect ≈ the §B-lawful level (the 1,932 wall rows exempted BY
   NAME, the residual reported honestly); the register/parity twins
   (test_harness) extended so an unpublished joint fails a test, not
   a sim pass.

## Amendment 3 (Fable, 2026-08-28 — a below-grade wall under a carried
## surface does not sever a route; one conditional, cap resets)

Measured (lane/lemdrim b1ff0714): Amendment 2 complete (declaration
follows emission, byte-identical patch, census 3205 → 3039, undeclared
steps still price). Residual: `terrace_joint_route` 0 → 11 — declared
`basin_trench_wall` arcs crossing taxi ROUTE axes. Ruling:

1. The route/strip terrace twins exist because a SURFACE terrace
   crossing a taxi path is impassable. A below-grade trench wall whose
   crossing point lies inside a below-grade region carried by a
   pad/shell or roofed span (the yield population's own geometry —
   reuse that register, no new notion) is NOT on the movement
   surface: the route rides the shell above it. `basin_trench_wall`
   joints are EXEMPT from the route/strip terrace families exactly
   there — a wall arc crossing a route on OPEN ground still prices in
   full (that severance is real). At LEMD all 11 lie under building8's
   shell; expected total ≈ 3028.
2. Twin: a declared wall joint under a carried span → no route row; the
   same joint on open ground → prices.
