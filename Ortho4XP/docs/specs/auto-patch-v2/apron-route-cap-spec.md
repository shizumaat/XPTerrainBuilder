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
=======
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

### Implemented (lane `v2routecap` round 3, 2026-09-07)

REMOVED (06w withdraws both boxes): round 2's two commits' code and
round 1's corridor box — `apron.py` (`ROUTE_BOX_RULING`, the per-face
`AxisIndex`, `priced`), `stretches.py` (`crossing_axes`, `_block`),
`verify/within.py` (`apron_route_index`, `apron_pairs`, `hole_rings`, the
apron branch of `taxi_box`), `check_grade._StretchBox`'s apron reading
(node-id crossing, hosted holes), `solve/why.py`'s `apron_route_box` key,
`families.toml`'s route-box clause, the `emit.toml` note — each file
restored from main and the §2 `edge_cap` change re-applied by hand (the
two round-2 commits are not `git revert`ed: the merge of main sat above
them).  KEPT: `edge_cap` not tightened by an apron face (06t), `APRON_ROLE`,
`[*.taxi] width_m` + `tables.taxi_half_width_m`, `test_pad_route`'s
premise.

THE TIERED LAW AS BUILT.  `rulesets.toml [common.roles] apron` /
`building` = `{ preferred = {0.010, 0.010}, max = {0.015, 0.015} }`
(the v1 value is the preference — `test_law_tables` RULED register);
`RoleCap.preferred`, parsed by the sibling `law/role_cap_schema.py`
(`model.py` sits at the 1,000-line law); `role_cap` = the hard cap,
`role_preferred_cap` the preference.  Every apron row generator emits
TWO rows per pair (`apron.tiered_rows`): the HARD `Diff(cap = max)` — the
row an IIS names and 04t(1) relaxes above 1.5 % — and the PREFERENCE
`Diff(cap = preferred, soft = "apron:<face>:<k>", ceiling = None)`.
Two rows, not one (the brief's fallback): `solve/relax.py` admits only
hard rows and `to_sparse(soft="ceiling")` prices a preference row at its
ceiling — a one-row form with `ceiling = max` would be un-relaxable, and
a preference twin with `ceiling = max` would re-cap a relaxed hard twin;
with no ceiling the preference row constrains nothing in the IIS, the
certificate and the variance program (it is charged only in the hard
solve and in stage 2).  DEVIATION (reported): the group is PER ROW, not
per face — `assemble` charges one slack per group at `weight × Σ chord
metres`, so a per-face group would price a 214,000 m² junction's whole
chord population against one escalation and free every row of the face
at once; per row the charge is exactly the metres of relief used.
Generators: `apron_within_shape` (ring edges, spine / frontage chords,
body chords under the gate and the 05ae cover), `apron_edge_portions`
(the hard row only where the host face's cap is looser than 1.5 % — a
road, a lot; a taxi face's own 1.5 % already holds it — the preference
row wherever the face's cap is looser than 1 %), `pads.frontage_near_
miss` (the stand entries).  UNCHANGED at the (new) hard cap without a
preference row, stated: the `routes.py` hops and route edges through
apron faces (reach, no_step distances — 1.5 % now), the `taxi.py` /
`junction_mesh.py` pad-frontage pairs on taxi faces (`min(c, pad_cap)`
is now the taxi cap itself), `transverse.py` (no apron-cap rows: the
cross-sections carry the axis's taxi transverse cap), `proximity.py`,
`verify/contiguity.py` (the lateral-contiguity strictest class is 1.5 %
for an apron now).

OBJECTIVE PLACEMENT (single weighted stage, `solve/assemble.py`;
`Weights.preference["apron"] = 0.9`): the preference is charged `0.9 ×
max(DEM-fit weight) = 18 per metre of relief` above 1 % — below the
runway family's fit (20 per metre per vertex) and its profile
smoothness (5,000 per metre of |Δgrade|·span), above every other role's
fit (taxi 8, apron 4, pad 1) and the most junior preference on the
ladder (crown 1e2, end_zone 1e3, seam 1e4, law 1e5).  The lexicographic
stages of `solve/stage1.py` are the LAST RESORT's (they run only on an
infeasible hard set) and price soft rows at their ceiling — the
preference lives in the hard solve and in stage 2.  Demonstrated on the
twins (`tests/auto_patch_v2/test_v2routecap.py`): a runway free to sag
beside an apron chain seated 2.2 m below the DEM keeps its ridge at the
DEM and its edge at the crown datum while three apron rows go to 1.5 %;
the labelled arm with the apron preference at 1e6 holds the apron at
1 % and sags the runway edge 0.09 m below its crown.  The 200 × 60 m
apron with the letter-E stretch: 1.5 m over 100 m FEASIBLE with 18/114
rows over 1 % (escalation ≤ 0.005); 1.6 m INFEASIBLE, the IIS naming
hard 1.5 % rows along the lane summing to 1.5 m, never a preference
row; nothing pinned → 0/114 over 1 % on a 2 % DEM.

REPORT FIGURE `apron_over_preference`: sidecar (evidence) + `report.json`
from `apron.apron_preference_report(cs, z, law)` (per face: rows, rows
over 1 % + materiality, max grade); the v2 verify's own reading
`verify/within.apron_over_preference` over its within-shape apron
population (same row count; one row within the emit quantum may read
either side); `why` prints it (`apron_preference_block`); the oracle
reads the sidecar's `apron_tier` (LAW INPUT `{preferred, max, fan}`,
`SIDECAR_LAW_KEYS`): an apron-law pair (an `apron` / `building` way, or
a 04t-2 portion pair) priced between the strict cap and the hard cap —
the strict 1 %, or v1's corridor credit (08-24b) which now equals the
hard cap — is judged at `max` and tallied in `_APRON_PREF_STATS`
(`family_out["_apron_over_preference"]`); `harness/census.py` prints it
beside the withdrawn-law heading and writes it to the census JSON.  The
oracle is NOT keyed on the `o4_grade_law_cap` tag (the tag composes as a
minimum and cannot raise a cap).  Lockstep on the fixture: both readers
read the same apron rows over 1.5 % on the population both price; v2
additionally prices EVERY spine chord of a ring vertex where the oracle
prices the nearest-spine chord only (families.toml) — a pre-existing
population difference, one row on the fixture (ABEAM_A ↔ ROUTE_A,
60.7 m), owed to the oracle beside round 2's visibility-buffer note.

OWED (06w (3), the 5 % back-edge class): v1's `plan_fan_ramp_zones`
(`auto_patch/elevation_per_surface/route_profile/apron_terrace.py`:
pad-pair reach hulls cut back along the pair axis, ∩ apron, − the
lattice-coarse corridor cover, area / two-building filters) is ~250
lines of shapely geometry plus `corridor_cover` / `lattice_coarse_cover`
and five constants; the port is a zone generator over the planar map
(pads, apron faces, the stretch corridors), a `fan_ramp_zones` sidecar
publication the oracle already reads (`_fan_ramp_pair_cap`), the hard
5 % + 1 % preference rows on chords inside a zone, a twin per predicate
— estimate 400–600 lines across `constraints/`, `pipeline/publication.py`,
`law/emit.toml` (the constants as law) and tests, one round.  Not
started: 1–2 is the part that moves the runway.

MEASURED (round 3, HECA `build_airport.py HECA --engine v2`, tag
`v2routecap3`, 362.4 s; round 1 in brackets): bow **−10.38 m at station
2,708 m** [−10.38 at 2,708] — UNCHANGED; ridge minimum 104.60 m at
2,732 m [104.60]; K 0.348 %/100 m [0.346], `runway_vertical_curve` 0;
max |grade| 1.535 % [halves ≤ 1.53]; tie 922/0 [922/0]; census
adjudicated **6** [5] (5 `strip_seam_tear` + 1 `vertex_to_edge_step`,
both NEW — deferred lines), v2-verify **32** [26] (26 lateral_contiguity
+ the same 6); relaxed rows **103 verify-side / 184 solve** [2,006 /
4,319] — the hard set is still infeasible but the IIS certificate now
arrives (226 rows in 60.5 s) and the relaxation is IIS-scoped (mean
excess 0.034 pp, max 0.17 pp, no demotion); solve 222.9 s [248.5]; LP
88,432 columns (37,811 preference groups) / 696,275 rows [51,598 /
637,091]; `apron_over_preference` generator 5,927 / 36,844 rows, max
built grade 2.08 % (a relaxed row), largest faces #215 1,010/3,024,
#264 1,007/3,775, #389 852/1,326, #364 749/5,706 (max 1.67 %), #365
483/561, #403 300/300; v2 verify 2,328 / 22,050 (max 1.64 %); oracle 992
/ 182,985 (its population prices every apron pair at any length).
CYXY `--base-arm` verify 0 (apron_over_preference 2/2,604; generator
15/2,945; 6.8 s); OTHH verify 0 (0/59,701; hard-feasible; 428 s).

WHY THE BOW DID NOT MOVE (`why HECA --shape 30`, 39 hops [44], Σ dz
+47.24 m from the 05C/23C low vertex v1444 to the 23R CIFP threshold
pin; KML `scratch/HECA_v2routecap3_binding_chain.kml`): by family along
the chain no_step_pairs +18.27, **apron_preference +16.03**, junction_mesh
+5.13, taxi_centreline +4.79, transverse +1.73, strip_transverse +1.25.
The chain crosses #364 on the SAME two chords as rounds 1–2 (806.2 m and
310.6 m, hops 16–17) — now as PREFERENCE rows built at 1.445 % and 1.41 %,
under the hard 1.5 %, each binding with dual −18 (the weight).  The
runway does not buy the remaining 0.055 pp because lifting v1444 needs
EVERY parallel apron chord between the same regions to escalate (#364
prices 5,706 rows; the chain shows one) — the per-row charge sums over
hundreds of rows against a few dozen runway vertices at 20/m, the
aggregate the twin (58 rows, 163 runway vertices) does not reproduce.
And the whole tier, fully spent on this chain, is worth **+0.72 m**
(0.055 pp × 806 m + 0.09 pp × 311 m): −9.66 m, not the owner's 6.1 m —
the other +31 m of the chain are no-step / junction / taxi rows already
at their 1.5 % between the 05C/23C low point and the 23R pin.  A single
weighted stage cannot order runway ≻ apron preference ≻ DEM fit at both
the fixture's and HECA's row density (measured sweep on the twins:
w ∈ {0.9 … 0.02} — the DEM fit wins the unpinned apron below w ≈ 0.3,
the runway loses HECA's parallel rows at every w that holds it); the
order the ruling states is LEXICOGRAPHIC (the runway family's fit held
first, the apron preference next, the DEM fit last — the shape of
`solve/stage1.py`'s last resort, applied to the hard solve).  Reported,
not decided: owner / spec-author question for round 4.

### Implemented (lane `v2lexi`, RULINGS 2026-09-06x: the objective order is LEXICOGRAPHIC)

MECHANISM.  `law/emit.toml [objective]` (`order = "lexicographic" |
"weighted"`, `stage_b_prefix = "apron"`, `warm_start`; schema
`law/objective_schema.py`, `model.py` held at 1,000 lines) is bound to
`Weights.lexicographic` by `pipeline.build.weights_under_law` (runway
roles from the precedence register, the ridge's breakline kind, the hold
= `[relaxation] runway_hold_tolerance_m` 0.01 m).  `solve/lexi.py` runs
the SAME assembled LP three times on one `highspy` model (`highs.solve`
dispatches; `"weighted"` is the single scipy stage as before): **A** the
runway family's terms (the DEM fit of every runway-family vertex, the
ridge's smoothness stations, and every preference group whose prefix is
not `apron` — crown, end zone, seam, the law ladder, the flat datum: the
groups the single stage already ranked above the runway; demoting them
would let the runway buy an end-zone or seam escalation, which no
ruling asked for — REPORTED as the reading of "every other preference
last"); **B** the apron preference alone, every runway-family vertex
bounded to its stage-A value ± 0.01 m and every column stage A charged
bounded at its stage-A value + 0.01 m in its own unit; **C** the whole
objective, stage B's columns held likewise.  Holds are BOUNDS, never a
row: the first form (one dense objective-hold row per stage, thousands
of coefficients spanning 20 … 1e5) ended HECA's stage C in
`kUnknown` / `kSolveError`; per-column bounds solve every stage.  Stage
A infeasible = the hard set's infeasibility (the IIS runs as before);
`why` reads STAGE A's point and duals (the chain that holds the runway)
with the final point carried for the figures; `Prepared.final_z`.

BUILD TIME (three LPs).  CYXY (hard-feasible, 122k rows): weighted 0.6 s
→ lexicographic 1.5 s cold (A 0.7 / B 0.5 / C 0.2), 4.3 s warm-started —
+0.9 s = 1.5 % of the 60 s budget (the per-change Fable optimisation
review is SUSPENDED, RULINGS 2026-08-04; the ledger tripwire stands);
harness solve 0.57 → 1.20 s.  HECA (the relaxed set, 696k rows): weighted
69.7 s → lexicographic 62.2 s cold (A 16.3 / B 26.3 / C 18.8), 142.6 s
warm (B 118 s) — three objectives converge faster than one; the closing
build's solve 222.9 → 156.4 s (the last resort's stages included).  OTHH
5.30 → 4.79 s.  `warm_start = false` is the measured default (a basis
left by one objective under new bounds is a poor start for the next).

TWINS (`tests/auto_patch_v2/test_v2lexi.py`, 6): the round-3 fixture
DENSIFIED — a 300 × 50 m apron abutting the runway edge with a ring
vertex every 5 m (3,981 parallel apron preference rows against 216
runway vertices), its far edge pinned 1.44 % below the crown datum:
weighted sags the ridge 0.105 m and spends 73 rows; lexicographic holds
the ridge on the DEM (0.001 m), the edge at its crown datum, and spends
774 rows to 1.5 % (an L1 stage concentrates relief at the cap — the
variance spread is the last resort's, not ruled here); no runway vertex
moves > 0.01 m between stage A and the final point; a free apron off a
second stub (unpriced in A and B) lands on its DEM at stage C; the law
table, the OFF arm, `why` reading stage A.  Suite: 705 passed, 1 skipped.

MEASURED (HECA `build_airport.py HECA --engine v2`, tag `v2lexi`, 299.4 s;
round 3 in brackets): bow **−10.38 m at 2,708 m** [−10.38] — UNCHANGED;
ridge minimum 104.60 at 2,732 m [104.60]; chain start v1444 z 107.89
[107.89]; K 0.346 [0.348]; max |grade| 1.535 % [1.535]; relaxed 184
[184]; solve 156.4 s [222.9]; census adjudicated **14** [6]: strip_seam_
tear 11 [5], terrace_actual_step 2 [0], vertex_to_edge_step 1 [1]; v2-
verify 40 [32] (26 lateral_contiguity + 12 strip_seam_tear + 1
adjacent_ground_tear + 1 step); apron over preference generator
7,059/36,844 max 2.08 % [5,927; max 2.08 %], #364 726/5,706 max 1.67 %
[749], #264 1,378 [1,007], #215 1,353 [1,010]; oracle 986/182,985 [992].
Other runways: 05L/23R bow −2.23 [−2.08], 05R/23L −9.74 [−9.72] — stage A
minimises the family's L1 sum with the crown preference above it, not
each runway's minimum.  CYXY verify 0 [0], generator 13/2,945 over
preference [15], oracle 2 [2]; OTHH verify 0 [0], 0/90,574 [0].

WHY THE BOW STILL DID NOT MOVE — the round-3 mechanism is REFUTED.  The
ceiling probe (maximise z[v1444] over every HARD row with every
preference slack free — stage A's feasible region) returns **107.890**,
exactly the built value: the runway's low point is held by HARD rows
alone; the apron preference rows never held it.  Round 3's "+0.72 m
fully spent" read hop 16's preference row (806 m at 1.445 %) as the
limit; the hard twin of the same chord (1.5 %) and the apron's own
within-shape chords across #364 (06x (2): 1,117 m at 1.5 % = 16.8 m; the
chain's hops 16 + 17 = 11.65 + 4.65 = 16.3 m) hold the same 16 m in
parallel — the LP had a degenerate choice of which tight row to price,
and the trace showed the priced one.  `why HECA --shape 30` on stage A
(39 hops, Σ +47.24 m; KML `scratch/HECA_v2lexi_binding_chain.kml` in
the lane worktree, written by `why --kml`): by family no_step +18.27,
apron_preference +11.65 (hop 16, 806 m, 1.445 %), junction_mesh +4.86,
taxi_centreline +4.79, apron_within_shape +4.65 (hop 17, 309 m at 1.5 %),
transverse +1.73, strip_transverse +1.25; the priced duals sit on hops
1–4, 6–8 (the 23C stub / parallel-taxiway no-step and centreline rows at
1.5 %) and 18–22, 24–34, 39 (junction #365/#366/#359 mesh and the strip
into the 23R pin) — hops 9–17 (the #381/#389 no-step run and the #364
crossing) carry zero dual: tight, not binding.  What binds next is the
owner's question 06x-1 (is the #364 crossing the intended coupling?) —
under 06w it is lawful and it is the shortest path.

THE NEW CENSUS ROWS (round 3's 6, now 14; read-only attribution, no fix —
the class is a generator population, not ≤ 20 lines).  All strip_seam_
tear rows are the same class: an apron ring vertex that is ALSO a
vertex of the adjacent-ground strip ring (`adjacent_ground:taxi:E:zone1`)
sits at the apron's surface while the strip's other vertices (zone1 /
zone2 boundary) are tied to the taxi junction beside them — no row
joins the two (06p: `zones.py` `own_law` exempts every ring vertex of an
airside value face; no_step pairs are pavement|pavement), so the strip
ring tears by the apron-vs-junction difference over 3 m.  Round 3
(pav131 rose ~1 m): pav131 #215 at the taxi-E stub rose +1.75 m (13
joined vertices; +2.7 at the strip site, its junction #221 +4.5) when
the tiered cap freed its rows (relaxed 4,319 → 184; the apron follows
the junction up toward the 05C/23C low at 1.5 % where 1 % held it
lower), and the strip vertex it shares rose with it against the zone
vertices at the junction (100.87 → 103.55 vs 105.29: 1.7 m over 3 m).
This round the same class grows at pav47 #95 (the apron rose a further
+2.1 … +2.6 m: 103.57 → 105.66 against a junction at 101.4; tear 4.15 m)
and at strip #19 / the pav47 terrace joint (terrace_actual_step 1.62):
under the lexicographic order pav47's apron vertices (DEM 101.4) sit at
105.66 — stage A leaves them unpriced (105.86), stage B holds every
apron row at ≤ 1 % where it can, and stage C's DEM fit (4/m) may not
lower them past the held apron slacks: the apron preference is now
SENIOR to the apron's own DEM fit, exactly as ruled, and an apron over
relief (03k) sits farther from its DEM than the weighted trade left it.
The `vertex_to_edge_step` (apron|building 0.63 → 0.86): building201's
pad dropped 87.15 → 86.93 → 85.73 while the apron vertex 0.8 m from its
edge stays — the pad frontage weld class.  OWED: a strip ↔ apron-ring
tie (or the apron ring vertex admitted to the zone tie) — one table
before any consumer edit (30l).
