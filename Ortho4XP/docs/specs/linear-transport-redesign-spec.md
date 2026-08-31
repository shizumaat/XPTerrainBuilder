# Linear-transport redesign — roads, bridges, tunnels, airside connections
# (RULINGS 31a/31b mandate; consumer census: linear-transport-consumer-
# census.md, 118 rows — every interaction below is ruled against it.
# Author: Fable lead, 2026-08-31. ONE owner ratification covers this
# whole spec; per-batch sim checkpoints adjudicate, per 31a.)

## §1 The model

ONE law for a road's vertical profile everywhere: follow terrain;
where terrain exceeds `SERVICE_ROAD_MAX_GRADE` (8 %), LIFT or CUT the
minimum needed to hold the cap (the bounded-envelope clamp — census #5,
free_road_profile's envelope branch, which is KEPT as the algorithm);
laterally level (no banking). Pins exist ONLY at airside pavement
contact (29c contact-is-value) and at bridge decks (30c §5,
re-expressed below). OWNERSHIP: the core's `include_roads` owns
general roads; auto_patch owns (a) contact transitions, (b) bridges,
(c) tunnels as mouths/ramps/retaining walls. The `tunnel_road` claim
class (R14-1) and the chord/self-pin profile model retire.

## §2 Core roads (census §5)

1. LONGITUDINAL CLAMP, per-way on centerlines (census #111 option i —
   NEVER on the merged buffered ring): for each way in
   `road_network_banked`, sample the shifted-DEM profile at ≤20 m
   stations, run the envelope clamp (lift-or-cut, cap-Lipschitz —
   the same algorithm as free_road_profile's envelope branch, ported),
   and store per-way clamped stations. `alt_vec_shift` answers from
   the nearest clamped station within lane_width×2 (cKDTree), falling
   back to shifted DEM beyond. Grade constant: new cfg var
   `road_grade_limit` (O4_Cfg_Vars beside `road_banking_limit`,
   census #116), default = `auto_patch.config.SERVICE_ROAD_MAX_GRADE`
   (one constant, import direction already exists — census #115).
2. PATCH-AREA MAX DETAIL UNCONDITIONAL (owner 2026-08-31): the
   airport-inset level-5 + rail leveling runs whenever auto_patch
   runs, regardless of a numeric user `road_level`; the user knob
   governs tile-wide only.
3. FIX the key-presence exclusion (census #106): exclude a way only
   when `bridge`/`tunnel` has a truthy value (not `no`), so
   `bridge=no` ways level normally. The exclusion set is the seam
   with auto_patch's (b)/(c): approaches level with the core, the
   tagged span belongs to auto_patch.
4. MEASURABILITY (census #91, the blindness the post-mortem names):
   the clamp pass WRITES a levelled-roads sidecar
   (`<tile>/o4_levelled_roads.json`: per-way station lat/lon +
   clamped alt + DEM alt) beside the tile. `tools/
   road_terrain_conformance.py` gains `--levelled-roads` to price
   core-owned roads from it; census/check_grade stay patch-only
   (their law populations shrink per census #83-90, accepted).
   Granularity: clamp stations ≤20 m so the instrument outresolves
   emit_decimate's 60 m (census #112).

## §3 auto_patch roads — the contact model (census §1, §4)

1. RETIRE: both `solve_free_road_profiles` call sites, the chord
   branch, self-pins, `cap_distance_prefix` (if unused after the
   port), PROFILE_KEYS/binding-refusal registers, O4_FRP_* flags
   (census #1-4, #6-7, #10-12).
2. KEEP AND REWIRE into the transition profiler: LAW 1 freeze-weld
   (#8), LAW 2 end-on binding (#9), `_road_vertex_graph` (#13),
   `_airside_value_at` (#14), `adopt_road_airside_crossing_values`
   (#61), the envelope clamp (#5). A transition chain runs from the
   airside contact pin outward at most `SERVICE_ROAD_PAVEMENT_NEAR_M`
   (25 m; seam-probe 5 measures whether that set IS the contact set)
   and its OUTER END takes the value of the SAME shared clamp
   function the core uses (one function ⇒ the handoff welds by
   construction).
3. OWNERSHIP SHRINK: `build_service_road_network` mints only contact
   stubs (within the transition scope of airside pavement or a
   bridge/tunnel feature); general road courses stop emitting as
   patch pavement (#53). `SERVICE_ROAD_CARVE` (#54) keeps — airside
   by construction. The ~15 spec-must-rule writers in census §4a rule
   as: passes that exist to manage road-vs-lot ownership at scale
   (#68 route corridors, #96 lot sever, #97 road_zone sever, #98
   road-only lots, #99 absorption, #101 full-width merge) go DORMANT
   with their domain (retire only after a full-battery zero-fire
   measurement, 29f); value-writers that remain in the contact scope
   (#56 dem_follow, #57 reach, #59 lateral contiguity + cap vector,
   #60/#63 seats, #64 chord limiter, #66/#67) KEEP, now operating on
   the small contact population. `svc_free_ends` (#17/#58): a
   transition's outer end is no longer "free" — the free-end DEM tie
   retires with general roads; corridor_axis_coverage's --free-ends
   mode re-reads from the levelled-roads sidecar.
4. CENSUS MIGRATION GUARD MIRROR (#90): add the outbound twin — the
   road-family population leaving the patch is DECLARED (a
   `road_ownership` sidecar count), so census shrinkage is provably
   the shrink, not a silent drop.
5. CONVERGENCE-POINT DISCIPLINE (census §4a SUPPLEMENT): the road
   family has ~40 altitude writers in 19 modules, converging at TWO
   points — the solver writeback (`solver_primitives._writeback`,
   both call sites) and `to_osm`'s authority resolution. The shrink
   is a POPULATION change (general road shapes stop existing in the
   patch), not 40 code edits: writers act on whatever road shapes
   remain, which is the contact set. Batch 2 verifies by seam-probe
   (`who_wrote.py --at`) at one airport, not by editing writers. The
   `_cut_back_road_frontage` gate conflict (census supplement) is
   seam-probed in Batch 2 before any assumption. The mint has NO
   pre-solve value authority (census correction) — the transition
   profiler is therefore installed at the writeback/`reseat_service_
   mouths` seam, the census-named "natural home" of the pinned-
   transition law.

## §4 Bridges (census #75, #44; 30c/30d/30f re-expressed)

Detection (`road_bridge_deck` §1/§2) KEEPS: bridge-tagged feed way ×
emitted below-grade structure = terrain deck; object-governed spans
keep the object law. The deck is core-owned road ground WITH a pin:
30c §5's "pin in the free-road profile solve" re-expresses as a pin
in the CORE clamp (a clamped-station override at deck stations: deck
level = max(clamped value, structure-beneath + 5.1 m... per 30d the
structure holds bore datum so this is the road solve's own level —
the pin's function is §6 refusal detection and the approach grade
check, both priced in the clamp pass). Cuts on either side hold
`BRIDGE_ROAD_CLEARANCE_M` (5.1) under the span (30d full-depth
geometry unchanged). OSM-level classifier: shared node ⇒ same level;
crossing without shared node orders by layer/bridge/tunnel — built
on the existing G-TUNNEL-ROAD tag machinery (#42), which KEEPS.

## §5 Tunnels — mouths, ramps, retaining walls (census §2, §3)

1. RETIRE: `TUNNEL_ROAD_REF` and its minters (#22-26), the stand-down
   (#31), claim audits (#32), claim publisher + `tunnel_open_cut_
   claim_polys` (#48), the 30i clip membership (#30), solver claim
   pins (#37), claim env flags. RULINGS superseded: R14-1, 25e-claim
   lineage, 30i — named in the ratification.
2. REWIRE BY ROLE/GEOMETRY, not ref: walls key on ramp/mouth geometry
   (#27, #28); `claimed_tunnel_corridor` readers become tunnel_ramp
   checks (#33, #34); BELOW_GRADE_REFS drops "tunnel_road" (#35);
   node-book exclusion re-keys to `tunnel_open_cut_polys` (#51 —
   seam-probe 4 verifies ring coverage BEFORE the closing build);
   region publication re-homes out of the claim pass (#47, #49);
   claim-edge seniority reads the cut half only (#50).
3. The canonical mouth (30 ruling) stands: one ramp to the mouth
   line, one wall+foot per side, one end cap. Where mapped road
   pavement lies over the cut, it is now CORE road ground above a
   covered stretch (the deck model, §4) or severed by the open cut —
   never re-profiled in place.
4. `tunnel_portal_acceptance` re-keys its bore-cover check to
   ramp/mouth geometry (#40) — updated in the SAME batch so the OTHH
   battery cannot silently SKIP.

## §6 Implementation batches (sim-checkpoint gate: ONE batch between
## owner sim reads; each batch ONE lane, ONE closing build)

- Batch 0 (enabler, no geometry change): merge lane/phase0roads
  (instrument + off-arms); this spec + census ratified.
- Batch 1 — CORE: §2 items 1-4 (clamp, sidecar, unconditional patch-
  area leveling, exclusion fix, instrument extension). Closing:
  one tile build (LEMD), conformance read on the sidecar. auto_patch
  untouched.
- Batch 2 — ROADS: §3 (FRP retirement, contact model, ownership
  shrink, guard mirror). Closing: HECA + the SPJC owner site
  (follow_ratio at way 702's chain ≥0.95, no cutting >2 m).
- Batch 3 — TUNNELS+BRIDGES: §4+§5. Closing: OTHH (three canonical
  mouths, wall count per side = 1) + LEMD (bridge span per 30d/30n).
- Batch 4 — CLEANUP: retired tests rewritten/deleted (census test
  list), env flags removed, dormant passes measured zero-fire then
  deleted, RULINGS supersessions recorded, PERF re-measured against
  tools/build_time_baselines.json (the 31a anchor) — the retirements
  should claw back part of the 5-6x accretion; quote the delta.

## §7 Emitability + heightfield check (30l requirement)

Everything here emits in a heightfield: core roads are INTERP_ALT
ring altitudes (existing machinery); transitions are patch pavement;
decks are terrain at road level over severed cuts (30d, proven at
LEMD); tunnels are open cuts + walls (pre-claim model, proven).
No floating geometry anywhere in the model.

## Acceptance (whole redesign)

Owner sites: SPJC 702 terrain-following ≤8 %; LEMD 40.4834432,
-3.5805328 bridge per policy; OTHH mouths canonical. Census not
worsened beyond the DECLARED ownership migration; conformance
instrument green on both patch and levelled-roads populations;
basin/ramp invariants held; perf delta vs committed baselines quoted.
Below-bar = STOP with residual. Sim read between every batch.
