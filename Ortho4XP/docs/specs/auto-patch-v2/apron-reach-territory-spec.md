# v2 — apron REACH TERRITORIES: a joint wherever an apron cell would otherwise shortcut two routes (spec, 2026-09-07)

Owner (RULINGS 2026-09-07c): an apron point's route to the runways is a
visible path inside its apron shape to a taxi route, then centrelines
only; no shortcuts across aprons; unconnected aprons step. Measured
basis: RULINGS 07a (ablation on the HECA capture — runway + routes hold
the 05C/23C hold at 109.3 m; every surface family bridging apron #364's
two contacts, 2,725 m apart by route and 34 m apart by ceiling, drags it
to 107.9). Author: session (Fable). Implementer: lane `v2terrace2`.

## 1. What 06n left open

`planar/terraces.py` partitions BETWEEN cells (two cells joined by a
taxi station on their shared boundary are one terrace) and states "(3)
within one cell the apron law stands". HECA #364 is ONE cell touching
two routes whose contacts disagree by 34 m: its own within-shape rows,
junction #397's mesh, the taxi rings' box chains and the service roads
each bridge the span at 1.5 % (07a's redundancy). The partition must run
INSIDE a cell, and the joint must cut every face that spans it.

## 2. Reach territories (the partition rule)

For every apron-like cell (`terrace.cell_roles` ∪ `neighbour_roles`):

* CONTACTS: the taxi-centreline stations on the cell's boundary and the
  stations of every route THROUGH the cell (the 06t crossing lanes).
  Each contact carries its route-graph ceiling and floor
  (`constraints/routes.py::reach`).
* IN-SHAPE DISTANCE: the visible path from a cell vertex to a contact
  that never leaves the cell polygon (holes respected) — the shortest
  path in the polygon's visibility graph (vertices = ring/hole
  vertices + the contacts; an edge where the segment is covered by the
  face, `geometry.face_cover` / `chords_covered` as `apron.py` already
  uses). For a convex cell this is the chord; the lane states the
  cost (HECA #364: 5,706 ring vertices — build the visibility graph on
  the SIMPLIFIED ring at `emit.identity.min_distinct_spacing_m` × 10 and
  snap; state the wall).
* TERRITORY of a vertex = the contact with the least
  `apron_cap × in_shape_dist + budget_from_contact` (the reach ceiling
  the owner's law gives that vertex; ties to the nearer contact).
* JOINT: the boundary between two territories T₁, T₂ is a joint when
  their contacts' ceilings differ by more than the apron's max cap can
  hold along the in-shape path between the contacts:
  `|ceil(c₁) − ceil(c₂)| > cap_max × d_inshape(c₁, c₂) + terrace.min_step_m`
  (state the key; default the emit step materiality). Otherwise the
  two territories are ONE terrace (the routes agree within what the
  surface can hold — the common case; CYXY/OTHH/LEMD must gain no joint
  their 06n census did not already declare, quote the counts).
* The joint POLYLINE is the territory boundary through the cell's
  interior (the arrangement's edges nearest the bisector between the
  two territories' vertex sets — the lane chooses the construction:
  either (a) split the face along the bisector polyline as a new
  planar edge run, or (b) assign existing interior vertices/edges and
  let the joint follow the existing edges between differently-owned
  vertices; (b) is preferred if the arrangement is dense enough; state
  which and why).

## 3. The joint continues through every spanning face (owner 30l table)

Faces of ANY role that touch both territories are cut by the same
polyline: junction bodies (their mesh rows never bridge), roads (a
road's profile rows stop at the joint; on each side the road ramps at
its own cap — `roads.py` core clamp — so a road crossing a 34 m joint
takes its own length to climb; the sim sees a road ramp, never a
cliff, only where the ramp is short of the step: report any road
whose ramp cannot reach), pads (one territory, the one with more of
its vertices), strips/zones (06n keep-outs: never inside a runway strip
or its end corridors — a joint that would enter the strip stops at the
keep-out and the two territories MERGE there; report the case). The
consumer table (reader → behaviour across a joint → after) is written
into this spec BEFORE any consumer is edited: `apron.py`,
`junction_mesh.py`, `taxi.py` (box, chain hops), `roads.py`, `pads.py`,
`no_step.py`, `zones.py`/`strips.py`, `proximity.py`, `contiguity.py`,
`transverse.py`, the emit adapter (split vertices, `terrace_joints`
declaration), `verify/*` and the oracle's `terrace_joints_ll` reading
(census) — with the expectation that the SPLIT VERTEX mechanism makes
most rows vanish without a per-consumer edit (no shared variable).


### 3.1 Consumer census (lane `v2terrace2`, written 2026-09-07 BEFORE any consumer edit; owner 30l)

Measured basis on the HECA capture (`scratch/territories_measure.py`,
pre-territory tree): partition by NEAREST contact along the in-shape
path (07c(2)); #364 has 3 reached contacts (3746 / 10159 at 81.7–81.9,
10286 at 125.2), 3 territories, 2 terraces, joint 10159|10286: gap
43.3 m over 472 m in-shape (hold 7.58 m); its ring shows exactly 2
label changes and its 3 holes none; visibility-graph wall 5.2 s over
113 cells (1.5 s for #364's 389 vertices, unsimplified). The spec's
literal budget metric (`cap × d + budget_from_contact`) was measured to
mint NO joint anywhere: at #364 the south contact owns the north
contact itself (81.67 + 0.015 × 541 = 89.8 < 125.16) — the metric IS
the shortcut — so the partition uses 07c(2)'s nearest contact and the
metric only in the JOINT PREDICATE (deviation reported, not decided).

Construction: **(a)** — a planar face has no interior vertices or edges
for (b) to follow (the arrangement's faces are the polygons; chords are
rows, not edges), so the cell is CUT along the in-shape shortest path
between the two ring vertices where the terrace label changes (the
straight chord where the face covers it; the visibility-graph geodesic
otherwise, its bends new vertices). The cut vertices are shared by both
pieces and are exactly the JOINT VERTICES the 06n split copies for the
junior group — no T-vertex is inserted into any neighbouring face. The
two pieces then fall to 06n's `split_terraces` unchanged: two apron-like
faces sharing a boundary with no station on it are two groups, the
boundary a joint, the junior ring retreated `joint_gap_m`, the joint
declared. Every consumer below therefore sees what 06n's census already
ruled for a between-cell joint, plus the three rows marked NEW.

| reader | across a territory joint today (one cell) | after the cut (two faces, split vertices) |
|---|---|---|
| `apron.py` within-shape (ring edges, frontage / spine / body chords, 05ae cover, 06w tiers) | chords span the whole cell: the 806 m / 311 m chain hops of 06x | face-local: each piece prices its own ring and chords; no chord crosses the cut (no shared variable) — no edit |
| `apron.py` edge portions (04t-2) | a junction's run along the cell | a run ends at the cut vertex; the junior piece's copies are no longer the junction's ring — 06n rule, no edit |
| `junction_mesh.py` | junction #397's mesh spans both territories | junction cells are apron-like (`neighbour_roles`) and partitioned by the SAME rule with their own contacts; a spanning junction is cut too — no edit; NEW: its cut vertex meets the apron's at the shared boundary or a few metres off (the boundary between a north piece and a south piece has no station → 06n joint) |
| `taxi.py` chain hops / route graph | a ring vertex hops to the perpendicular foot on any stretch touching the CELL | a hop targets only stretches touching the PIECE (`st.on` / `face_stretches` per face): a north-piece vertex cannot hop to the south route. Deviation reported: the hop stays perpendicular (05aa/06p), the in-shape metric serves the partition only |
| `taxi.py` short-pair box (06s) | box rows within taxi faces only | unchanged; a taxi face crossing the cut carries a breakline and is NEVER cut (a route across the joint contradicts the joint; a dead-end lane there is reported and stays welded — the step tapers) |
| `roads.py` `road_within_shape` (all pairs of a road ring), `contiguity.py` stations | a service road running from one territory to the other bridges the span at the road cap | NEW: a road-family face touching both terrace labels is cut by the same construction (labels propagated to its ring from the nearest labelled vertex, its two change points joined in-shape); each piece prices its own pairs, ramps at its own cap (`preferred_z` per vertex unchanged); a road whose ramp cannot hold the step is reported |
| `pads.py` (frontage, flats) | a pad belongs to the group it shares most vertices with | 06n rule over the pieces — no edit; a pad is never cut (rigid) |
| `no_step.py` route pairs / reach bands / cross-shape | pairs by ROUTE distance (2,725 m between the contacts: none inside the window) | the copies are leaves with their own hop; no pair across the cut; reach bands per vertex from the piece's own routes — no edit |
| `zones.py` / `strips.py` | 06n: a zone face wedged between two groups retreats from the cell (zone_owner) | unchanged; NEW keep-out rule: a cut whose polyline intersects the runway-strip keep-out is REFUSED for that cell (the territories merge there, counted `refused_strip`) |
| `proximity.py`, `transverse.py` | gap 0.6 m exceeds identity spacing; per face | no edit (06n) |
| emit adapter | — | copies are distinct nodes with distinct keys; the joint run (the cut polyline) declared in `terrace_joints` — no edit |
| `verify/steps.py`, oracle `terrace_joints_ll` (`terrace_joint_route` / `_strip` / `_actual_step`) | — | the declared line forgives the step; the cut crosses no breakline (faces are bounded by them) and never the strip keep-out — no edit |
| `publication.terrace_joints_ll` | — | reads `planar.terrace_joints`; `split_terraces` now PRESERVES joints already on the map (the 06n pass runs at planar build, the territory pass after the route graph exists) |

Pipeline order (dependency law: `planar` may not import `constraints`):
`planar.build` (06n split as before) → `constraints.no_step.reach_band_values`
(routes + threshold pins) → `planar.territories.terrace_territories(pm,
law, airport, classification, bands)` = partition + cut + `split_terraces`
(the same function, joints preserved). Law keys `[terrace]`:
`min_step_m` (the joint predicate's materiality, = `materiality.step_m`),
`continue_roles` (the non-cell roles the joint continues through: the
road family), `simplify_factor` (the visibility graph's ring
simplification as a multiple of `identity.min_distinct_spacing_m`).

## 4. Twins

* A 300 × 60 m apron with two route contacts at its ends whose
  ceilings differ by 12 m (routes 1,500 m apart): joint minted across
  the middle, each half solves to its own contact, the census reads
  the step lawful; the same cell with ceilings 3 m apart: no joint, one
  terrace at ≤ 1.5 %.
* A junction and a road spanning the same two territories: cut by the
  joint; the road ramps on each side at its cap; no row crosses.
* A cell with one contact: no joint (06n unchanged); a cell with no
  contact: island (06n unchanged).
* Oracle/verify lockstep on the joint declaration.

## 5. Acceptance (ONE airport = HECA; then CYXY, OTHH, LEMD `--base-arm`)

HECA `build_airport.py HECA --engine v2` once: the 05C/23C hold at the
109 m intersection ≤ 6.1 m under the threshold line (quote the built z,
the station and the line; `tools/rwy_profile.py`), the ridge minimum
and K; the `why` chain on the runway's lowest vertex made of taxi
centreline / crossing / runway rows ONLY (KML, state the path); joints
minted (count, total length, largest steps, which faces they cut —
apron / junction / road); census adjudicated (joints read lawful, bar
≤ 14, no DEFECT); v2-verify by family; six halves; solve wall vs 222.9 s
and the territory build wall. CYXY/OTHH/LEMD: verify 0 must hold; the
joint counts vs their 06n counts (CYXY 7, OTHH 55 — quote LEMD's).
Build-time statement.
