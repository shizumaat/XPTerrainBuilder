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
| 8 | `pipeline/publication.py`: `stretches` sidecar `[pts, cap_l, letter, ref]`; `axes` sidecar | stretch caps published un-tightened already; axes carry #5's values | UNCHANGED under §3-amended (round 1's 5th element `corridor_half_width_m` is withdrawn with the corridor — no reader needs it; the apron route box keys, like the taxi box, on the presence of `stretches`); `axes` change per #5 |
| 9 | `verify/within.py::within_shape` — taxi pairs over `taxi_route_pairs` budgets; apron pairs isotropic at the apron cap | apron ring pairs beside the route at 1 % × d, taxi pairs at the 1 % budgets | taxi pairs flow from #3; an apron face CROSSED by a published stretch (`apron_route_index`: an edge of the stretch on its outer ring or a hosted hole ring) leaves `within_shape` WHOLE and is read by `taxi_box` (§3 amended) over the SAME gated population — ONE enumeration, `apron_pairs` (adjacent edges, strict chords, body chords ≤ gate, chords inside the face), serves both; an uncrossed face reads isotropically as today |
| 10 | `verify/within.py::taxi_box` + `published_axis_index` | taxi-family rings only | + every `apron_pairs` member of a crossed apron face (any length) and the ring edges of its hosted holes, against the face's own `AxisIndex` of CROSSING stretches with the apron cap as `cT` (`apron_route_index`; the nearest-axis / strictest-tie rule of `AxisIndex.box_bound`, one rule with the taxi box) |
| 11 | oracle `check_grade._StretchBox.applies` / `budget` | taxi-role pairs under 30 m against the nearest axis | + every apron-role pair (any length) of a way whose FACE — its ring plus the `gap_interior_ring` ways stamped with it as host — carries an edge of a published stretch (identity join on node ids), priced against the nearest CROSSING stretch with the apron cap across; keyed on `stretches` like the taxi box (a 5th element is ignored) |
| 12 | oracle `taxi_axes` / `routes_ll` / `pair_caps_ll` (published routes and axes) | 1 % budgets through the apron | flow from #3 / #5 through the sidecar |
| 13 | `apron.apron_within_shape` (ring edges, spine / frontage chords, body chords at 1 %) | every pair isotropic at 1 % | in a face crossed by a stretch (`stretches.crossing_axes` over `face_stretches`) EVERY priced pair, any length, is the BOX row `|Δz| ≤ cL_stretch·|Δs| + cA·|Δt|` against the nearest crossing axis (`taxi.box_pair_rows` on an `AxisIndex` whose `cT` is the apron cap) — the existing gates (strict chords, body gate, 05ae face cover) select the population exactly as before; a face crossed by no stretch is unchanged |
| 14 | `apron.apron_edge_portions` (04t-2 alongside) | apron cap on the long shared portion | UNCHANGED (alongside, not through) |
| 15 | `planar/terraces.py` / 06n terrace joints | a route joins the cells it stations | UNCHANGED (a route never crosses a joint) |
| 16 | `solve/relax.py::_law_tier` (tier of the new rows) | — | the route box rows CITE the apron law (`common.roles.apron route box …`, read by `stated_role`): apron tier, relaxable under 04t-1 like the isotropic row they replace; the route's own centreline rows stay taxi tier, hard |
| 17 | `solve/why.py::_FAMILY_KEYS` | apron rows → `apron_within_shape` | + `("apron", "route box", "apron_route_box")` so the chain trace names the box rows |

Half-width law key (round 1's §3, kept as law after §3-amended — no
generator reads it): `[<authority>.taxi] width_m = { by_letter = … }`
added to `law/rulesets.toml` for BOTH authorities (ICAO Annex 14 §3.9.3
A 7.5 / B 10.5 / C 15 / D 18 / E 23 / F 25; FAA AC 150/5300-13B ADG
I 7.5 / II 10.5 / III 15 / IV 23 / V 23 / VI 30 through the letter proxy);
the corridor half-width is `width_m / 2`, `TaxiLaw.width_m` optional in
`law/model.py` (no numeric literal there).

## 3 amended (RULINGS 2026-09-06v, the spec author's ruling; owner question 06v-1 open)

§3's corridor box is WITHDRAWN. Round 1 measured it on the §4 fixture:
a 1.5 % route through a 1 % apron is INFEASIBLE under any taxiway-width
corridor, because the apron keeps its chords to the route's stations
(05ab; 05aa withdrew long chords on TAXI faces only) and any apron
vertex P with d(P,A) + d(P,B) < 1.5·d(A,B) re-caps the route through
two 1 % chords (a 30 m-abeam vertex against stations 100 m apart:
58 + 58 < 150 → Σ ≤ 1.17 m over 1.5 m). At HECA the chain still crossed
cell #364 on 806 m and 311 m apron chords relaxed to 1.47 %.

RULED (the physics of one continuous surface): within an apron face
CROSSED by a stretch — an edge of the stretch lies on one of the face's
rings (outer or hole; `stretches.crossing_axes`, one definition for the
generator, the v2 verify and, on node ids, the oracle) — EVERY priced
pair (ring edges, spine chords, body chords under their existing gates
and the 05ae face-cover gate) at ANY length is the BOX against the
crossing stretch axis NEAREST the pair's midpoint (ties strictest):

    |Δz| ≤ cL_stretch·|Δs| + cA·|Δt|

with cL the stretch's longitudinal cap (1.5 % C–F, 3 % A/B) and cA the
APRON cap (1 %) across. A face crossed by no stretch stays isotropic.
The corridor, the sidecar's fifth stretch element and the round-1 knob
`emit.within_shape.apron_corridor_pair_max_m` are deleted (refuted
mechanisms are deleted — build economy). The `[*.taxi] width_m` law key
and `edge_cap`'s §2 change stay. The rows cite the apron law
(`common.roles.apron route box …`): apron tier, relaxable under 04t-1.
Consequence: a crossed apron cell may tilt at the route's cap along the
route's direction EVERYWHERE in the cell; across it stays at 1 %.

Twins (`tests/auto_patch_v2/test_v2routecap.py`): the §4 fixture is
FEASIBLE on the full generator set at 1.5 m and INFEASIBLE at 1.6 m
with the IIS naming the route's own rows (Σ bounds = 1.5 m); a pair
perpendicular to the route reads 1 %, a pair parallel to it 40 m off
reads 1.5 %; an uncrossed apron stays isotropic; oracle / v2 verify
lockstep on a stepped fixture (the same rows by distance, the same
caps).

Open (owner question 06v-1): whether 1.5 % along the route over the
WHOLE crossed cell is acceptable, or the cell should stay 1 % away from
the route (which re-caps the route to ~1 %), or terrace at the lane's
edge. Implemented as ruled pending the answer.

MEASURED (round 2, HECA `build_airport.py HECA --engine v2`, tag
`v2routecap2`, 382 s; round 1 in brackets): census adjudicated **43**
[5], all 43 = oracle `taxi_box::apron|apron` chords of pav132 (#364)
that the GENERATOR never priced — the oracle's chord-visibility buffer
is v1's `GRADE_VISIBILITY_BUFFER_M = 1.0 m` (`auto_patch/config.py`,
`grade_graph._visibility_predicate`) while the generator's and the v2
verify's 05ae face cover use the snap margin (0.354 m): on the identical
polygon in the identical frame the oracle admits chords grazing the
pad's concave corners (17.8 m / 0.51 m … 607 m / 8.66 m) that both v2
readers drop; the oracle's baked-path floor forgave them until the box
replaced it. Pre-existing gate divergence, NOT this law — owed to the
oracle (one tolerance, both readers). v2-verify 26 lateral_contiguity
[26], `taxi_box` 0 [0]; relaxed rows 1,332 verify-side / 3,242 solve
[2,006 / 4,319], of which 421 route-box rows; bow −10.38 m at station
2,708 m [−10.38]; ridge minimum 104.60 m at 2,732 m [104.60]; K
0.349 %/100 m [0.346]; six halves ≤ 1.53 % [≤ 1.53]; tie 922/0 [922/0];
solve 241.1 s [248.5]. The binding chain (`why`, 44 hops) still crosses
cell #364 — now on ONE `apron_route_box` chord (657 m at 1.48 %,
+9.72 m) instead of two relaxed 1.47 % apron chords (806 + 311 m,
+11.85 m). CYXY / OTHH verify 0 / 0, unchanged.
