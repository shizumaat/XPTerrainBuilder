# v2 — a taxi route THROUGH an apron carries the taxiway law (spec, 2026-09-06)

Owner (RULINGS 2026-09-06t): "the taxi route still gets 1.5 % even when
passing through an apron." Author: session (Fable). Implementer: lane
`v2routecap` (branch from main 5732848d, after v2ridge3).

## 1. The law as ruled

A taxi centreline route (a 1202 taxi_centerline breakline) THROUGH an
apron face carries the TAXIWAY law of its stretch's letter: the
longitudinal cap (1.5 % C–F) along it, the taxi transverse cap across
it — never the apron cap. The apron BESIDE the route stays under the
apron law (1 % all directions, 05ae chords inside the face, 06n
terraces). 05v's "crossing taxilanes at the apron cap" is withdrawn on
the cap; RULINGS 2026-09-03j's "1202 edges inside an apron are APRON"
stands for ROLES (the emitted role, the tier) and is withdrawn for the
CAP of a centreline edge. 04t-2 (a junction / road SHARING A LONG EDGE
with an apron takes the stricter cap on that portion) is about
alongside, not through — unchanged.

## 2. The single derivation site: `stretches.edge_cap`

`constraints/stretches.py::edge_cap` tightens a centreline edge's
`(cL, cT)` by every governed NON-taxi face it bounds. RULED: an APRON-
family face (`role_family(law, role) == "apron"`) no longer tightens a
centreline edge that lies ON A STRETCH (`st.by_edge` hit); every other
non-taxi family (runway slab, road, structure) still does. An edge on no
stretch keeps today's rule. That one change flows to every reader of
`edge_cap` — the consumer census (owner 30l) the lane writes in its
report BEFORE editing, one table: `taxi.taxi_centerlines` (chain rows),
`routes.py` (route edges, reach bands, no_step route distances, the
05ac chain hops — the HOP from an apron vertex onto the route stays at
the APRON cap, 04q-1), `transverse.py` (the cross-section rows: the
taxi transverse cap across a route through an apron, per 06t),
`junction_mesh.nearest_line_cap`, the verify readers and the oracle's
published `taxi_route_pairs` / stretch caps. State each reader's
behaviour before/after in the table; edit no consumer except as §3.

## 3. The apron's SHORT PAIRS beside a route compose with it (the box)

Without this the ring re-caps the route: an apron ring vertex 10 m
abeam a route holds `|Δz| ≤ 1 % × d` to each route vertex, and two
route vertices 100 m apart then cannot differ by 1.5 m. RULED: within
an apron face crossed by a stretch, every ring pair under
`withdrawn_chord_min_m` (30 m) whose MIDPOINT lies within the stretch's
TAXIWAY HALF-WIDTH of its axis (the letter's taxiway pavement half-
width; the lane names the rulesets key — if none exists, add
`[*.taxiway] width_m = { by_letter = … }` per Annex 14 §3.9.3: A 7.5,
B 10.5, C 15, D 18 (23 with OMGWS ≥ 9 m — use 18), E 23, F 25 m, and
FAA's ADG widths in the FAA table) is priced as the BOX against that
axis — `|Δz| ≤ cL·|Δs| + cT·|Δt|` with the STRETCH's `(cL, cT)` (06s's
`taxi_box` machinery: `constraints/taxi.py::box_pair_rows`,
`axis_index`) — REPLACING the apron's isotropic row for that pair.
Pairs with a midpoint outside every corridor stay at the apron cap
(unchanged). Long pairs (≥ 30 m) stay withdrawn (05aa). The oracle
reads the same population: `check_grade`'s `_TaxiBox.applies` admits an
apron-role pair whose midpoint lies within a crossing stretch's
corridor (the corridor half-width published beside the stretch in the
sidecar `taxi_stretches` or wherever the caps are published today), and
v2 `verify/within.py::taxi_box` likewise; the lockstep twin (the oracle
and v2 verify count the same rows on the fixture) is mandatory. 06n
terraces are untouched: a route never crosses a terrace joint (a
terrace group is cells joined by a 1202 station on their boundary).

## 4. Twins

* A synthetic apron (200 × 60 m, cap 1 %) with one letter-E stretch
  along its middle and a fixed 1.5 m rise between two route vertices
  100 m apart: FEASIBLE after; the same fixture with the route's
  vertices pinned to a 1.6 m rise is INFEASIBLE and the IIS names the
  route rows; a ring pair 40 m off the axis still reads the apron cap.
* `edge_cap` on a stretch edge bounded by apron faces returns the
  stretch's cap; bounded by a runway slab returns the tightened cap.
* Oracle/verify lockstep on the fixture.

## 5. Acceptance (ONE airport = HECA, `build_airport.py HECA --engine v2`)

Quote, current configuration first: the 05C/23C profile — the ridge's
low point vs the owner's 109 m intersection (state the built z at the
05C/23C × 05L/23R crossing and the ridge minimum, its station), the
bow below the threshold line (today −10.41), the max grade change per
100 m (K held), six halves ≤ 1.53 %; the 06r-1 binding chain: which
rows bind the runway now (`why` on the runway's lowest vertex), and
whether pav132 cell #364 still joins two routes; census adjudicated
(bar ≤ 8 today), v2-verify (26 lateral_contiguity pre-existing + box),
tie 922/0, solve wall vs 198.5 s, relaxation count. CYXY/OTHH
`--base-arm`: verify 0 must hold; quote any delta by role. Build-time
statement. Report the KML of the binding chain after (the owner reads
these — `scratchpad/limiting_kml.py` exists).

## §3 SUPERSEDED — RULINGS 2026-09-06w (owner): the tiered apron cap

§3's corridor box and 06v's any-length box are withdrawn. The law: every
apron row is HARD at `[*.apron] max` (1.5 % all directions) and carries
`[*.apron] preferred` (1 %) as a `Diff.soft` preference (one escalation
group per apron face, `ceiling` = the hard cap), charged junior to the
runway family's objective and senior to the DEM fit; chords between
adjacent pads at the back edge (the 08-24 `plan_fan_ramp_zones`
predicate, ported from v1 `auto_patch`) are hard at `apron_fan_ramp_max`
(5 %) with the same preference. `rulesets.toml` gains the two keys under
both authorities (`apron = { longitudinal, transverse }` today IS the
1 % — rename to `preferred` and add `max`; `role_cap(law, "apron")`
returns the HARD cap, a new `role_preferred_cap` the preference; the
oracle's `_role_grade_limit` for apron roles reads the hard cap through
the sidecar's ruleset and counts rows above the preference as the
report figure `apron_over_preference`). Twins: a 200 × 60 m apron with
a 1.5 m rise pinned over 100 m is FEASIBLE with the preference slack
charged and reported; 1.6 m is INFEASIBLE with the IIS naming apron
rows at the hard cap; with no rise pinned the surface sits at ≤ 1 %
(the preference holds when nothing senior needs more); oracle/verify
lockstep (rows over 1.5 % only). Acceptance §5 unchanged, bow bar:
shrinks toward 6.1 m — quote.
