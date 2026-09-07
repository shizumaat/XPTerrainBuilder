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

## §2a AMENDED (RULINGS 2026-09-07f) — the pre-arrangement polygon cut

Lane `v2terrace2` measured that §2's literal metric mints no joint (the
in-shape path from the other route's contact makes the apron the route)
and that cutting arranged faces along an interior seam fails on geometry.
Amended construction:

1. Contacts are RUNWAY-CONNECTED stations only (`routes.reach` reaches
   them from a threshold pin); dead-end lanes' stations are neither
   contacts nor joins.
2. Over each welded pavement complex (the 110 polygon and every
   pavement it overlaps), label every ring/hole vertex by its nearest
   runway-connected contact along the in-shape path (07c(2)); the joint
   PREDICATE is pairwise on adjacent territories:
   `|ceil(c₁) − ceil(c₂)| > max_cap × d_inshape(c₁, c₂) + terrace.min_step_m`
   (and the floor-only variant with the floors — report, do not decide,
   if it fires where the ceiling one does not).
3. Where the predicate holds, cut the RAW polygon (before
   `planar` builds the arrangement) along the SHORTEST chord that
   separates the two contact sets, crosses no runway-connected
   centreline, and respects holes (shapely `split`; among candidate
   chords between ring/hole vertices — simplified ring at
   `simplify_factor` × the identity spacing — take the shortest that
   separates). Both pieces keep the pavement's ref with a piece suffix;
   every other pavement overlapping the chord is split by it too.
4. The arrangement, 06n's grouping (joins through runway-connected
   stations only), the split copies and the declaration run unchanged.
5. Acceptance adds: the chord at HECA crosses within 60 m of 30.127729,
   31.412022 (07e) and no chord is minted at CYXY / OTHH / LEMD (their
   06n joint counts unchanged: CYXY 7, OTHH 55, LEMD quoted).

## §2b AMENDED AGAIN (RULINGS 2026-09-07g) — joints are label boundaries, not cuts

§2a's polygon cut is withdrawn. Mechanics: (1) label every pavement node
of a welded complex by its SERVING CONTACT (nearest runway-connected
station by shortest visible in-shape path; reuse `planar/territories.py`
from lane v2terrace2); (2) extend each node's reach band by the in-shape
leg (`routes.reach` + apron cap × path); (3) for every adjacent node pair
(a planar edge, or any row's endpoint pair) whose serving contacts
disagree under the pairwise predicate, the pair is a JOINT: the
generators mint no row across it — implement ONCE at the constraint-set
assembly (`pipeline/build.py` after the generators: drop every row whose
endpoints straddle a joint, by generator, and report the count per
family) rather than per generator — and the joint edges are declared in
`terrace_joints` (points + step) so `check_grade` / `census.py` /
`verify` read them lawful (06n's declaration path, unchanged); (4) roads
across a joint: rows dropped, step reported; (5) the feasibility
fallback: if a runway threshold pin reaches no other runway's pin through
the network, the shortest in-shape apron path joining the two route
systems is added to the route graph at the apron cap — report when it
fires. Acceptance §5 unchanged; the label boundary at HECA crosses
within 60 m of 30.127729, 31.412022.
