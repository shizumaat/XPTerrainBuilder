# auto-patch-v2 — M5c report: pad↔pavement pairs THROUGH THE CONTACT (RULINGS 2026-09-04r)

Lane `lane/v2padroute` off main `ed20f058`. Ruling implemented: **04r**
(under 03h/03i + 04o): "a pad↔pavement no-step pair is priced THROUGH THE
PAD'S CONTACT — the pad is a flat group levelled by its apron contact, so
its only law edge to pavement is the contact edge at the apron's cap
along pavement; free-standing pad↔pavement chords do not exist."
Prediction to test: HECA's hard set feasible, solve ≪ 60 s, census → 0.
Every law value from the TOML tables; no env reads; no v1 imports; every
file ≤ 1,000 lines; attempt cap two per family respected (one attempt
spent).

## 1. The mechanism — `constraints/no_step.py`

* `pad_contacts(planar, law)`: pad face → its CONTACT vertices, the rim
  vertices shared with airside pavement (the no-step roles). A pad with
  none is DETACHED and absent. A rim vertex only a groundside lot shares
  is the lot's (09-01g) and is no contact.
* `pad_pavement_edges(planar, law, pavement=None)`: for every attached
  pad, from each contact vertex the K nearest pavement vertices BY ROUTE
  inside the window (`routes.route_neighbours`, new `exclude=` — the
  pad's own flat group is never a partner and never spends the K),
  `cap = budget / d` so `Diff.bound_m = Σ cap_e·len_e` along the pair's
  own path — exactly a pavement pair. Pairs the pavement list already
  carries (a contact vertex is itself a pavement vertex with its own
  K-nearest in `airside_no_step_edges`) are not repeated. The pad's BODY
  vertices are never an endpoint; the chord population (`_sector_pairs`,
  M5) is DELETED (29f: a refuted mechanism is not kept gated).
* Tier: by the vertex rule the row belongs to the contact's owner — the
  apron (tier 3) or the taxi family — never tier 8. HECA's 1,181 tier-8
  pad rows (m5b §5) no longer exist as a population.
* Publication: `pad_pavement_no_step_edges` carries the same
  `{a, b, budget_m, dist_m}` record with `dist_m` = the ROUTE distance;
  `verify/no_step.py` prices both lists by identity, unchanged in code
  (docstring only). The v1 oracle's proximity-join limitation (M5 §3:
  the pad-only endpoint resolved to a mixed pad's 0.5 m cut-back node)
  is why the key stays separate; it is reported here, not worked around.

## 2. Pair counts, chord/direct → route-through-contact

| | before (m5b: pavement route + pad DIRECT) | after (this lane) |
|---|---|---|
| HECA | 117,119 (1,181 pad rows at tier 8) | **108,293** (pad rows tier 3, none at tier 8) |
| KCLT | 183,961 (M5 chord law; m5b did not build KCLT) | **132,195** |
| SPJC | 54,502 (m5b) / 55,828 (M5) | **56,809** (+2,307 contact pairs) |
| CYXY / SPLP / OTHH / LEMD | not rebuilt (main's ledger, §5) | — |

## 3. Twins — `tests/auto_patch_v2/test_pad_route.py` (4) + `test_m5.py` re-founded

Fixture: m5b's loop (apron 17.5 m north of the runway, joined only by
~830 m of taxiway; apron rim densified to 5 m) plus `pad1` ATTACHED
along the apron's south edge with its body 2.5 m from the runway edge
(the refuted chord well inside the window) and `pad2` DETACHED.

* the contact is exactly the shared frontage (`pad_contacts`), the
  detached pad is absent;
* no pad-body vertex and no detached-pad vertex is an endpoint in either
  list; no pad↔runway pair exists (the pad reaches the runway only by
  the loop); every pad pair leaves a contact vertex, its partner is not
  on the pad, `dist` = the shortest route and `cap·d` = Σ cap·len along
  it, on-apron partners carry the apron's 1 %;
* the pad rows' tier is the apron's / stub's, never the lowest;
* sidecar / verify equality record for record; a hand-minted step at a
  published pad pair is read back on it.
* `test_m5.py::test_pad_pavement_pairs_join_the_population` now asserts
  04r (attached pad through its contact, detached none, no pad-only
  endpoint, no duplicate of the pavement list).
* `tests/auto_patch_v2/`: **175 passed** (was 171).

## 4. Builds (`build_airport.py ICAO --engine v2`, ledgered, tree ec4517bf clean)

| | HECA | KCLT | SPJC |
|---|---|---|---|
| tag / artifact-ledger key | `HECA_20260904T104732` / **cee809865b7d** | `KCLT_20260904T105601` / **3bfaace6a7e6** | `SPJC_20260904T105714` / **91700133c773** |
| body sha | 2a9cb3e9f4b7 | 518490118a31 | 1d639eebaa8e |
| no-step pairs | 108,293 | 132,195 | 56,809 |
| hard set | **INFEASIBLE** → k_min 3 (k 8 infeasible 60.5 s, 4 infeasible 52.8 s, 2 optimal 115.5 s); tier 3 apron 175 rows, max 0.443 m; **no tier below 3 yields** | **FEASIBLE, OPTIMAL, no yield** (M5: infeasible → k_min 7) | feasible, OPTIMAL, no yield |
| solve wall | 241 s (m5b 248; M5 1,598) | (planar 5.7 s) total **71.6 s** (M5 168.5) | total 52 s (planar 40 s) |
| v2 verify rows | 93 (within_shape 22, lateral_contiguity 26, airside_no_step 20, strip_seam_tear 7, mid_edge_step 6, …) | 57 (lateral_contiguity 16, tunnel_wall_top_flat 13, strip_seam_tear 11, adjacent_ground_tear 5, cross_shape 4, vertex_to_edge_step 4, tunnel_mouth_canonical 4) | 2 (adjacent_ground_tear, as m5b) |
| oracle census adjudicated / airside | **84 / 84** (m5b 50 / 50) | **70 / 44** (M5 58 / 48) | **8 / 8** (m5b 0 / 0) |

KCLT and SPJC ran as a background chain while HECA's census ran; wall
times above are single runs under contention (never a timing claim).

### HECA — the prediction MISSED; the contradiction attributed by IIS

The tier-8 pad yield is gone (the population no longer exists) but the
hard set is still infeasible and the solve is not faster. Offline IIS of
the HARD set (`solve/iis.diagnose` on the pipeline's own constraint set,
73 s): **24 rows, one site** — apron face 340 `pav132` (the hangar row
30.1368 → 30.1280 N, 31.4105 → 31.4130 E, DEM 69.3 → 84.7 m, ~1 km):

* 8 `Flat` pad groups — building359 (69 vertices), 350, 339, 328, 323,
  311, 300, 343 — each welded to the apron rim along its whole frontage;
* 9 apron rows at 1 % (frontage chords pad-vertex↔pad-vertex of 19.6,
  28.2, 31.3, 85.0, 116.9 m and ring edges) + 3 `frontage_near_miss`
  rows + 2 taxi no-step pairs (1.5 %) at the south junction;
* 2 reach bands: north end v10470 [62.57, 68.12], south end v11014
  [73.28, 78.94] — the threshold values along the taxi routes into each
  end of the apron.

The mechanism: a flat pad's contact consumes the rim length it fronts,
so between the north and the south junction the apron can climb only
Σ (1 % × the gaps between pads) ≈ 4.9 m, while the routes require ≥ 5.16
m (bands) and the terrain climbs 15.4 m. The tiered solve answers it by
yielding the apron (tier 3) 175 rows ≤ 0.443 m; with the apron hard
(k_min 4) it is infeasible. This is the 03k class in the shape 04r
predicts away only when the pads are short: the pads ARE flat by law
(03h, 09-01g weld = value) and the apron IS 1 % (08-21b/c); the pads'
contacts are lawful, the row is not a generator defect. **Owner
question (03k, restated):** along a hangar row over real relief, does
the apron (a) DECLARE A TERRACE between pads, (b) release the pad
contact to slope along the frontage (the pad stays one flat value in
its interior; the door line follows the apron), or (c) accept the ≤ 0.44
m apron yield as the answer? `why` cannot run on HECA (the hard LP is
infeasible; `prepare` refuses) — the IIS is the instrument here.

Census 84 / 84 by family, against m5b's 50 / 50:

| family | m5b | now | site / reading |
|---|---|---|---|
| within_shape | 18 | 30 | apron|apron 12 at pav132 (the yield, ≤ 1.12 m at 1.14 % over 98 m); **junction|junction 12 NEW at 30.11/31.397 `pav47` (E) + 6 at pav132 (E), oracle cap 1.0 %** — §6 |
| airside_no_step | 17 | 15 | pav132 apron↔junction / apron↔apron (≤ 0.98 m) |
| mid_edge_step / vertex_to_edge_step | 4 / 0 | 23 / 3 | **NEW: cross_connector `pav129` #331 vs junction `pav81` #42, ≤ 1.59 m** and stub `pav78` #43 vs stub `pav131` #327 ≤ 0.65 m — §6 |
| strip_seam_tear | 3 | 7 | graded_strip|graded_strip 4.06 m at 30.12261/31.40745 (taxi E zone2 #21 vs taxi F zone2 #7) and 3.58 m at 30.10960/31.39378 — strips, ungoverned |
| cross_shape / frontage_near_miss | 4 / 4 | 3 / 3 | building|building 0.5 m slivers; pav132 frontage |

### KCLT — hard set FEASIBLE (was k_min 7), 71.6 s (was 168.5 s), census 70 / 44

* `strip_seam_tear` 23 (8.75 m at the tunnel site 35.2152/−80.9442) →
  **11, max 1.02 m**, at a different site (35.20826/−80.93020, ways
  −11342/−11558, graded_strip|graded_strip). The 8.75 m tunnel-site
  tear is gone from the census; not attributed with `why` (strips are
  ungoverned faces, `why` targets a governed shape).
* `within_shape` 25 → 33 airside, all junction|junction at oracle cap
  1.0 % (pav37 #887 F 0.88 m / 1.33 %, pav48 #838 F 0.79 m / 1.50 %,
  −11343 0.68 m / 1.51 %): §6.
* `why KCLT --at 35.21108,-80.93104` (face 887 junction `pav37`, letter
  F, 184 vertices, z−DEM ≈ 0): binding apron_within_shape 80 rows
  (Σ|dual| 3,196), taxi_within_shape 56, transverse 8, pads 34; chain
  v999 → v18210 FREE terminal, one hop taxi_within_shape +0.188 m; every
  relax arm moves the face < 0.36 m — the junction FOLLOWS THE TERRAIN
  inside the letter-F 1.5 % cap; only the oracle's 1.0 % reading makes
  it a row.
* 26 groundside rows (lot|lot steps ≤ 0.84 m at 35.2057/−80.9445 and
  35.2105/−80.9418, cross_shape 4): first-build residual, not this
  lane's class.

### SPJC — 0 / 0 → 8 / 8, all junction|junction within_shape ≤ 0.63 m at oracle cap 1.0 %

`why SPJC --at -12.01957,-77.11189` (face 142 junction `pav40`, letter F,
225 vertices, z−DEM median +0.82): binding families apron_within_shape
64 rows (Σ|dual| 3,092), transverse 26, taxi_within_shape 67, no_step
109, pads 5 (FLAT group 17 — a pad's contact on the junction rim); chain
v4829 → v5457 (junction 256 / parallel 153) FREE terminal, one hop
taxi_within_shape 1.5 % × 50.1 m = +0.751; relax arms: no single family
lifts the face (apron_within −0.66..+0.19; taxi_within ±0.06; no_step
−0.31; pads −0.82..+0.99). The junction is solved at the taxi letter F
cap (1.5 %) as 04q-2 rules; **the oracle prices it at 1.0 %**. Under the
chord law the pad-body chords (1 % over direct distance to every
pavement vertex within 150 m) happened to hold these junction vertices
under 1 %; removing the refuted population exposed the reader
disagreement, it did not create it (HECA's m5b census already carried 6
such rows at cap 1.0 on the same junction ways).

## 5. The seven-airport table

| airport | source | build s | hard set feasible? | oracle census adj / airside |
|---|---|---|---|---|
| CYXY | main m4c `c23880b3e574` (m5b 0 / 0, `a9ea8577e0d3`) | 4.5 (m5b 4.8) | yes | 0 / 0 |
| SPLP | main m4c `a4a3758be45b` | 7.5 | yes | 0 / 0 |
| SPJC | **this lane `91700133c773`** (main m4c `0a79668a0b63` 0 / 0) | 52 (planar 40; solve 5.4 m5b) | yes | **8 / 8** (§4, §6) |
| OTHH | main m6b `9ad5b9c3db45` (m4c `42a253005ec9`) | 28.9 (m5b solve 6.65) | yes | 0 / 0 |
| LEMD | main m4c `4d96b4d41c41` | 30.5 | yes | 0 / 0 |
| HECA | **this lane `cee809865b7d`** | 262 (solve 241) | **NO → k_min 3, apron yields ≤ 0.443 m** | **84 / 84** |
| KCLT | **this lane `3bfaace6a7e6`** | 71.6 | **yes** (M5: no, k_min 7) | **70 / 44** |

CYXY / SPLP / OTHH / LEMD were not rebuilt on this branch (one
representative airport per round; the sweep runs at app-build time).
Their pad populations change under 04r too (CYXY had 669 direct pad
pairs) — the sweep will re-census them.

## 6. Attributions that are NOT this lane's mechanism (reported, not fixed)

1. **Oracle 07-06 vs v2 04q-2 on junctions sharing an apron edge.**
   `grade_graph._body_cap_unbounded` prices a junction that
   `adopts_apron_grade` at the APRON's 1 % ("Apron (1 %) is more
   limiting, so the apron branch wins if both are set"); v2 prices a
   stamped junction at its inherited letter (E/F → 1.5 %). Every
   `junction|junction within_shape cap=1.0` row at SPJC (8), KCLT (33)
   and HECA (18) is this disagreement, 1.0 % < measured ≤ 1.52 % ≤ 1.5 %.
   Which reading is law — the owner's 07-06 (a junction sharing an apron
   edge follows the apron rules) or 04q-2 (the letter of the chains it
   serves) — is an owner question; the fix is one line on whichever side
   loses (v2: `cap = min(letter cap, apron cap)` for a junction sharing
   an apron edge; oracle: the letter branch before the apron branch).
2. **Near-coincident rims not welded (HECA mid-edge steps).** Faces
   cross_connector `pav129` #331 and junction `pav81` #42 touch (2
   shared vertices, polygons intersect) but the connector's rim vertex
   v10249 lies 0.554 m off the junction's edge with its nearest junction
   vertex 7.65 m away and the ROUTE between them 81.8 m (through the
   runway; budget 1.23 m) — beyond its K=16 nearest — so a 1.59 m step
   forms across a 0.55 m sliver of graded strip; stub #43 vs stub #327
   the same at 0.325 m. A planar-build class (sub-metre apt.dat
   overlaps/gaps between adjacent pavements — the identity spacing does
   not merge them and the strip fills the gap); the 04o population is
   right that the pair is not "adjacent along pavement" in the map. Fix
   belongs at the planar build (node the rim onto the neighbouring edge
   inside a tolerance), not in the pair generator.
3. **Strip seam tears** (HECA 4.06 / 3.58 m, KCLT 1.02 m): ungoverned
   strips of different families (taxi E zone2 vs taxi F zone2) meeting;
   not touched.

## 7. Not done / open questions (≤ 3)

1. HECA's hard set: the second attempt on the family is NOT spent — the
   contradiction is between three lawful populations (flat pads, apron
   1 %, taxi routes) and needs the 03k intent answer above before any
   mechanism.
2. The junction cap disagreement (§6.1) — one ruling, then a one-line
   fix on the losing side; SPJC returns to 0 / 0 with it (its 8 rows are
   all that class).
3. Mesh not built; CYXY / SPLP / OTHH / LEMD not re-censused here.
   `why` needs a tiered mode to run on an infeasible hard set (it
   refuses at HECA); the IIS stood in.
