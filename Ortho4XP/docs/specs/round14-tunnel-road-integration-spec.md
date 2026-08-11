# Round 14 — roads serve tunnels: the paved area IS the corridor

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **r14roads**. Pre-ship
mode (docs/RULINGS.md); deviations STOP-and-report. Owner feedback on
the round-10 KCLT output (artifact KCLT_20260811T1405), verbatim laws.

## Measured sites (all in the r10 artifact)

* 35.2154711,-80.9439018 / 35.2153396,-80.9440718: the triangular
  service intersection between the two facing portals — junction
  shapes 603/605/606/1634/1636 and apron 602 all AT GRADE while the
  synthetic `tunnel_corridor` and mouths are sunk beside them: a cliff
  where the service road meets the tunnel system. Owner: the approach
  service road IS the ramp (apron grade down to bore depth at the
  intersection); the whole triangular intersection and both portal
  areas are ONE level surface at bore depth; no corridor strip cutting
  between the mouths — "the paved area IS the corridor."
* 35.2136167,-80.9422409 → 35.2140492,-80.9411416 →
  35.2137894,-80.9404677: the SE tunnel's mouth emits a CHAIN of
  tunnel_ramp segments (1731→1738) along the way's whole remaining
  extent, crossing taxiway junction 378/1049 (wall 1744 wraps it) —
  an impassable canyon in a taxiway. Owner: the ramp should climb
  from the mouth to ambient in ~100 m (which is depth ≈ 5.1 m at
  service-road grade); the crossing point is AT GRADE (a service road
  crossing apron and taxiway); nothing may cut a taxiway.

## The laws

### R14-1 WHERE MAPPED ROAD PAVEMENT COVERS THE APPROACH, THE ROAD IS
### THE TUNNEL SURFACE

Within a tunnel system's open-cut extent (portals, the gap between
facing portals, the graded approaches):

* road-family LAYOUT SHAPES (service_road / service_junction and their
  kin) covering the alignment are RE-PROFILED to the tunnel profile —
  portal areas and the pavement between facing same-road portals at
  bore depth (one level surface, the A3-corridor grade rule); approach
  pavement grading smoothly from bore depth up to its ambient solved
  grade over the R14-3 run. Route this through the existing
  below-grade re-profile machinery (the R5 transition-law family /
  `apply_below_grade_transition` and its authority registration) — if
  that machinery cannot carry a road-shape re-profile without a new
  authority class, STOP and report the gap; do not invent an authority.
* synthetic `tunnel_ramp` / `tunnel_corridor` rectangles emit ONLY
  where NO mapped road pavement covers the alignment (the geometry
  fallback, not the default). Where they abut re-profiled pavement
  they WELD (shared canonical nodes) — a cliff between road pavement
  and tunnel surface is the defect class this round exists to kill.
* retaining walls trace the DEPRESSED PAVEMENT's outline against
  surrounding ground (the R10-2 cuts apply unchanged; the wall never
  covers the pavement it guards).

### R14-2 A CUT NEVER INTERRUPTS TRANSIT PAVEMENT

No tunnel ramp, trench, corridor or wall may cut ROLE runway /
taxiway / junction (airside transit) pavement — the only exception is
a stretch covered by a CLASSIFIED hard-deck object bridge (the object
machinery's existing evidence; none exists at these sites). Where the
below-grade way crosses such pavement, that stretch is COVERED BORE
(the existing drop law already hides it); the open-cut geometry ENDS
at the pavement edge with the existing graze clearance. The crossing
pavement keeps its solved surface untouched.

### R14-3 THE RAMP RUN IS DEPTH OVER GRADE

A mouth's open-cut approach runs `bore_depth / TUNNEL_APPROACH_GRADE`
(new module constant beside the tunnel constants, default 0.05 — the
owner's ~100 m at 5.1 m depth; comment the derivation), reaching
ambient grade there — NEVER the mapped way's full extent. The run
truncates earlier at a transit-pavement edge (R14-2). FIRST, per
mechanism-before-fix: name in the commit message WHAT today extends
the chain past grade-reach (the walk's termination condition) — the
fix must remove that mechanism, not mask it.

## Acceptance (ledgered harness builds, KCLT + OTHH)

* KCLT: at the triangle — the junction/apron shapes there carry bore
  depth (one level within 0.1 m across the intersection and both
  portal areas); the approach service junction grades from apron level
  to bore depth with no adjacent-node step > the road grade cap over
  1 m; ZERO `tunnel_corridor` shapes overlapping mapped road pavement;
  no node pair (road pavement vs tunnel surface) within 1 m
  horizontally differing by > 0.5 m.
* KCLT: at the SE tunnel — no tunnel shape of any kind within 5 m of
  taxiway junction 378/1049; the open-cut chain from mouth
  35.2136167,-80.9422409 extends ≤ 110 m; the crossing at
  35.2137894,-80.9404677 is at grade (junction surface untouched
  vs a pre-round baseline sample).
* KCLT: the round-10 acceptance table MUST still hold (area-1 zero,
  overlaps zero, mouths at portals, depth ≥ clearance) — re-quote it.
* OTHH: 8 clusters, tunnel geometry area within ±5 % of the r10 final
  (re-profiling may lawfully change shape composition where mapped
  roads cover OTHH approaches — quote what changed and why it is this
  spec's law doing it).

## Bookkeeping

Lead writes the DEFERRED_VERIFICATION line at merge. Version stamps
are the lead's at app build.

## AMENDMENT 2026-08-11 (lead rulings on the implementer's three STOPs)

**A-1 (STOP-A: THE CLAIM IS ONE NEW REF IN THE EXISTING SOURCE SET,
NOT A NEW AUTHORITY CLASS).** The R5 approach grading already works
(measured: the triangle's junctions already span 211–219 under
`apply_below_grade_transition`) — what is missing is only the LEVEL
plate. Ruling: the tunnel system CLAIMS road-family shapes
(`service_road`, `service_junction`, `groundside_pavement` — exactly
the R5 TRANSITION_ROLES road members) whose pavement lies inside its
open-cut extent, and re-profiles them DIRECTLY (sets `node_altitudes`
to the tunnel profile: bore-depth level across the between-portals
zone including the triangle; the R14-3 graded run along approaches) —
the same post-solve re-profiling precedent R5 itself set for these
roles. Each claimed shape takes ref `"tunnel_road"`, and
`BELOW_GRADE_REFS` gains that one ref, so surrounding receivers grade
toward the claimed pavement under the UNCHANGED R5 law. Synthetic
ramp/corridor rectangles then stand down wherever a claimed road
covers the alignment (R14-1 second bullet as written).
AIRSIDE EXCEPTION: an `apron` (or any airside shape) inside the
open-cut extent is NEVER claimed or sunk — airside is king. Apron
`-10602` inside the triangle instead mints a counted
`tunnel_airside_conflict` finding (shape, area, the level it would
have needed): it is almost certainly a scorer misclassification of
road pavement, and that verdict is adjudicated with the classify
instrument, not by this emitter. The acceptance's "one level" bullet
applies to the CLAIMED road shapes.

**A-2 (STOP-B: SYNTHETIC BORE DEPTH IS THE CLEARANCE, NOT 8 m).** A
bore with no DEM cut takes `deck_reference − BRIDGE_ROAD_CLEARANCE_M`
as its floor — the round-10 depth law, now applied to the walk's
`elev_low` as well; `cut_detected` bores take max(DEM cut, clearance)
per R10-3 unchanged. `tunnel_depth_m = 8.0` survives only as the
last resort when there is no deck reference at all (layer<0 + no
usable DEM + no crossing deck). All three run-extenders go: `req`
sizes from the ACTUAL bore depth, the grade is
`TUNNEL_APPROACH_GRADE = 0.05`, and `ramp_min_length_m`'s 200 m floor
is DELETED (a minimum that outlives grade-reach is exactly the
mechanism R14-3 told you to name). SE site expectation: depth ≈ 5.1,
run ≈ 102 m ≤ 110 ✓.

**A-3 (STOP-C: THE PROTECTED SET IS THE AIRCRAFT-TRANSIT FAMILY).**
R14-2 protects `runway`, `runway_clearance`, `runway_crossing`
(already never cut) PLUS `junction`, `cross_connector`,
`primary_parallel`, `secondary_parallel`, `stub` — remove those five
from `_tunnel_ramp_cut_roles`. `apron`, `service_road`,
`service_junction`, `groundside_pavement` STAY cuttable — owner
ruling 4's beheading precedent lives exactly there (OTHH's mapped
portals open within apron/service pavement), and the owner's R14-2
law names taxiways. This supersedes ruling 4 for the taxiway family
only; record that in RULINGS.md in the same commit (the canon is
updated the session a ruling lands).
