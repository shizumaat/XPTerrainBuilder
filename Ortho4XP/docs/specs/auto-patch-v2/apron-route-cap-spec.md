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

## 2a. Census (lane `v2routecap`, written BEFORE any consumer edit — owner 30l)

Readers of `stretches.edge_cap`, of the stretch caps (`Stretch.cap_l` /
`cap_t`) and of the apron face's pair rows, greped 2026-09-06 on main
1e0828a8 (`grep -rn "edge_cap\|\.cap_l\|\.cap_t" src/auto_patch_v2`;
`_StretchBox` / `taxi_box` / `stretches` in `tools/check_grade.py`).
"Today" = a taxi centreline route (a stretch) THROUGH an apron face.

| # | Reader | Today (route through an apron) | After (§2 + §3) |
|---|---|---|---|
| 1 | `stretches.edge_cap` (the derivation site) | a stretch edge bounding an apron face is tightened to the apron's (1 %, 1 %) (09-03j) | an APRON-family bounding face no longer tightens an edge on a stretch; runway slab / road / structure faces still do; an edge on no stretch (road centreline, plain edge) unchanged |
| 2 | `taxi.taxi_centerlines` (one hard Diff per centreline edge, the chain law 05ac) | the edges through the apron hold 1 % | the stretch's letter cap (1.5 % C–F, 3 % A/B) — flows from #1 |
| 3 | `routes.py` (i) stretch edges of the route graph → reach bands, `no_step` route distances, `taxi_pair_routes` budgets (`taxi_route_pairs` sidecar), the `why` chain | budget 1 % × length through the apron | stretch cap × length — flows from #1; a part noded inside a runway slab keeps the runway cap (unchanged) |
| 4 | `routes.py` LATERAL hops (`taxi.taxi_chain`): a ring vertex to its perpendicular foot at the FACE's transverse cap | an apron ring vertex hops onto the route at the APRON cap (1 %) | UNCHANGED (04q-1 / 06p-2: the hop is the apron vertex's own face law); a taxiway ring vertex hops at the taxi transverse cap as today |
| 5 | `transverse.axes` (`_edge_cap`) → `transverse()` cross-section rows and the `axes` sidecar; `verify/transverse.py` reads `entry[2]` as `cap_t` | an axis through the apron carries (1 %, 1 %): cross-sections across the route priced at 1 % | the stretch's (cL, cT): the TAXI transverse cap across the route through the apron (06t) — flows from #1, both generator and verify (the sidecar carries the value) |
| 6 | `junction_mesh.nearest_line_cap` / `stretch_lines` / `mesh_edge_caps` / `triangle_boxes` | read `Stretch.cap_l`/`cap_t` directly (never `edge_cap`) | UNCHANGED |
| 7 | `stretches.pair_caps` / `compose_pairs` (taxi-face per-stretch pairs; verify `stretch_pair_caps`, oracle `_common_stretch_cap` / `_junction_stretch_cap`) | `Stretch.cap_l` directly | UNCHANGED |
| 8 | `pipeline/publication.py`: `stretches` sidecar `[pts, cap_l, letter, ref]`; `axes` sidecar | stretch caps published un-tightened already; axes carry #5's values | `stretches` gains a 5th element `corridor_half_width_m` (§3, the letter's taxiway half-width); `axes` change per #5 |
| 9 | `verify/within.py::within_shape` — taxi pairs over `taxi_route_pairs` budgets; apron pairs isotropic at the apron cap | apron ring pairs beside the route at 1 % × d, taxi pairs at the 1 % budgets | taxi pairs flow from #3; an apron pair under `withdrawn_chord_min_m` whose midpoint lies in a crossing stretch's corridor leaves `within_shape` and is read by `taxi_box` (§3) — the SAME gated population (adjacent edges, strict chords, body chords ≤ gate, chords inside the face) |
| 10 | `verify/within.py::taxi_box` + `published_axis_index` | taxi-family rings only | + apron rings (outer and hosted holes) for the in-corridor short pairs against the crossing stretch's axis (`corridor_box_bound`) |
| 11 | oracle `check_grade._StretchBox.applies` / `budget` | taxi-role pairs under 30 m against the nearest axis | + apron-role pairs under 30 m whose midpoint lies within the corridor of a stretch with an edge ON THE WAY's ring (identity join), priced against that corridor's axis; keyed on the sidecar's 5th element (a patch without it reads as today) |
| 12 | oracle `taxi_axes` / `routes_ll` / `pair_caps_ll` (published routes and axes) | 1 % budgets through the apron | flow from #3 / #5 through the sidecar |
| 13 | `apron.apron_within_shape` (ring edges, spine / frontage chords, body chords at 1 %) | every pair isotropic at 1 % | a ring pair under 30 m whose midpoint lies within a crossing stretch's corridor is the BOX row `|Δz| ≤ cL·|Δs| + cT·|Δt|` (the stretch's caps) instead — the 05ae inside-the-face gate still applies to chords; pairs outside every corridor and long pairs unchanged |
| 14 | `apron.apron_edge_portions` (04t-2 alongside) | apron cap on the long shared portion | UNCHANGED (alongside, not through) |
| 15 | `planar/terraces.py` / 06n terrace joints | a route joins the cells it stations | UNCHANGED (a route never crosses a joint) |
| 16 | `solve/relax.py::_law_tier` (tier of the new rows) | — | the apron box rows bind apron ring vertices: apron tier by the vertex rule (relaxable under 04t-1, like the apron row they replace); the route's own centreline rows stay taxi tier, hard |
| 17 | `solve/why.py::_FAMILY_KEYS` | apron rows → `apron_within_shape` | + `("apron", "short-pair box", "apron_route_box")` so the chain trace names the box rows |

Half-width law key (§3): `[<authority>.taxi] width_m = { by_letter = … }`
added to `law/rulesets.toml` for BOTH authorities (ICAO Annex 14 §3.9.3
A 7.5 / B 10.5 / C 15 / D 18 / E 23 / F 25; FAA AC 150/5300-13B ADG
I 7.5 / II 10.5 / III 15 / IV 23 / V 23 / VI 30 through the letter proxy);
the corridor half-width is `width_m / 2`, `TaxiLaw.width_m` optional in
`law/model.py` (no numeric literal there).
