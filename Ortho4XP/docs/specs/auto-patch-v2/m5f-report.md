# auto-patch-v2 — M5f report: JUNCTION BODIES PRICED BY THEIR MESH (RULINGS 2026-09-04y)

Lane `lane/v2junction` off main `74bba0cc`. Ruling implemented: **04y**
(applying 04t-3) — "a junction body chord whose endpoints lie on
stretches of DIFFERENT letters is not a law edge — v2 prices junction
bodies as the oracle does (triangle planes at the stretch cap; centreline
chords per stretch), never as all-pairs across letters." Every law value
from the TOML tables (one new key); no env reads; no v1 imports in v2 (the
oracle edit is v1's tool, `tools/check_grade.py`); every v2 file ≤ 1,000
lines; attempt cap two respected (one attempt per target; one rule
corrected on the twin fixture before any build, §1).

## 0. Site first — CYXY pav17 complex (owner's "apron off E at G")

`why CYXY --at 60.708422,-135.072589` (the apron, face 151 on this tree —
the shipped patch's 156; m5e's like-for-like reading) and
`why CYXY --shape 156` (face 156 on this tree is the pav17 JUNCTION beside
it, letter A, 6 vertices):

| | z − DEM median (min) | chain to the runway-02 CIFP pin 694.334 |
|---|---|---|
| before (m5e, `a2c00e96782d`) | apron **−1.87** (−2.12) | v2348 → v477 **taxi_within_shape 1.50 % × 222.0 m** (+3.33): a junction-100 BODY chord between a vertex on stretch 20 (taxi17, A) and one on stretch 27 (E, D) → v469 runway edge 1.5 % × 199.3 m → pin |
| after (this lane, `cff35e459d38`) | apron **−1.79** (−2.04); junction 156 **−1.59** (−1.81) | v3167 apron → v2347 apron_within_shape 1 % × 20.4 m (+0.20) → v2336 junction 100 **no_step_pairs 1.50 % × 107.9 m** (+1.62) → v479 **junction_mesh plane** (+0.31) → v469 **taxi_within_shape 1.50 % × 299.2 m on primary_parallel 6** (+4.49) → runway crown → pin; Σ +6.60 m |

The 222 m cross-letter chord no longer exists (it is in no generator, §1);
the apron rose 0.08 m. The next limiter is not a junction chord: a
no-step pair at 1.5 % over the 107.9 m route to junction 100 plus the
primary_parallel 6 rect's own 299 m within-shape pair at 1.5 % (a
PLANE-shape rect, all-pairs by the census's own reading, letter D). Relax
arms (full re-solve): `no_step_pairs` alone puts the apron ON the DEM
(z−dem +0.00, dz median +1.59); `junction_mesh`, `apron_within_shape`,
`no_step_rate`, `apron_edge_portion` each ≤ +0.04 m. What still holds the
site is therefore the 04o route/no-step pricing between the apron and the
parallel taxiway, not this lane's family — open question 1.

## 1. The rule as implemented

* `constraints/junction_mesh.py` (new, 205 lines; generator
  `junction_mesh`, registered after `triangle_planes`) for every face of a
  role in `emit.within_shape.junction_mesh_roles` (= `["junction"]`; v1's
  `JUNCTION_ROLES` also names `service_junction`, which is the road family
  in v2 and keeps `roads.py`):
  * THE MESH (`face_triangles`, :66): the face's Delaunay triangulation
    built exactly as the oracle builds it (`grade_graph.mesh_edge_keys`:
    GEOS Delaunay over the ring + hole vertices, triangles whose centroid
    the face contains, corners matched at 3 dp), published as sidecar
    `mesh_edges` (`mesh_edges_ll`, :190; `pipeline/publication.py`) so the
    oracle consumes v2's mesh 1:1 (`MeshEdgesExact`) instead of
    re-triangulating the emitted ring.
  * A MESH EDGE (ring edges included; `mesh_edge_caps`, :127) is priced at
    the cap of the crossing stretch NEAREST ITS MIDPOINT — perpendicular
    distance to the stretch polyline (`stretches.nearest_line_cap`, :223),
    the STRICTEST cap among stretches tied within 1 µm, the face's own cap
    when no stretch crosses it. "Crossing" = a stretch with an edge
    bounding the face (`Stretches.face_stretches`; verify: two consecutive
    stretch vertices on the ring). A mesh edge with a pad endpoint holds
    the pad's cap (frontage, 09-01g). One `Diff` row per edge.
  * A TRIANGLE's plane (`triangle_caps`, :178; the 16 half-plane
    linearisation factored into `taxi.plane_rows`) is bound at the cap of
    the stretch nearest its CENTROID. First written as the strictest of its
    three edges' caps and corrected on the twin fixture before any build:
    a plane bound is isotropic, so a triangle straddling G (A, 3 %) and
    the D taxiway bound at 1.5 % forbade the ruling's own example — X ↔
    the next G node (57 m) solved at 1.47 % instead of the 1.92 % it uses
    now. Under the centroid rule the G edge of that triangle is at 3 %,
    its D edge keeps 1.5 % through its own `Diff` row.
  * COMMON-STRETCH PAIRS (both vertices on one stretch) stay all-pairs at
    that stretch's cap: `taxi.taxi_within_shape` calls
    `stretches.pair_caps(..., common_only=True)` on junction-mesh faces;
    every other chord of the face — a G vertex ↔ an A vertex, or any body
    chord that is not a mesh edge — produces NO row in any generator.
* `verify/within.py` (`junction_pair_caps`, :126): the population of a
  junction-mesh face = ring edges ∪ published `mesh_edges` (identity join)
  ∪ common-stretch pairs; caps as above from the published `stretches`; a
  pair in none of the three classes is skipped. A patch without
  `mesh_edges` (pre-04y) reads the all-pairs superset as before.
* THE ORACLE (`tools/check_grade.py`): sidecar `stretches` becomes a law
  key (`SIDECAR_LAW_KEYS["stretches"] = "stretches_ll"`, threaded through
  `law_context_from_sidecar` → `run_checks(stretches_ll=)` →
  `_check_within_shape(stretches_m=)`); JUNCTION STRETCH CAPS
  (`_junction_stretch_cap`, :5666): a `JUNCTION_ROLES` pair priced at the
  way's BODY cap (never a frontage / apron-portion / cross-section pair,
  which the law already tightened) takes the cap of the crossing stretch
  nearest its midpoint, the allowance shifted by `(cap' − cap) · d` so the
  quantisation / terrace / fan-ramp terms stay as priced. Without the key
  the oracle reads a junction body at its stamped (strictest) letter, as
  before — the twin shows that reading minting rows on a lawful 2.5 %
  G-side mesh edge.

## 2. Builds (ledgered, `build_airport.py ICAO --engine v2`, tree `2d92cb66`)

| airport | tag / ledger key | build | v2 verify | oracle census adjudicated / airside | before (m5e) |
|---|---|---|---|---|---|
| CYXY | `CYXY_20260904T132811` / **cff35e459d38** | 4.8 s, optimal, crown:469 yielded 0.097; `junction_mesh` 7,875 rows in 0.018 s | 0 | **0 / 0** (the four runway\|runway rows gone with 04y's 1.5 % table) | 4 / 4 |
| SPJC | `SPJC_20260904T132831` / **f72e721615af** | 52.3 s, optimal, no yield | 2 (adjacent_ground_tear, as before) | **0 / 0** | 0 / 0 |
| HECA | stored `726a0e49cdce` (v2relax, `HECA_20260904T125846`) re-censused with the NEW oracle | not rebuilt | — | **52 / 52** — unchanged: within_shape 14 (04x/m5e: pad-endpoint frontage rows, which the stretch layer never loosens), strip_seam_tear 7, cross_shape 3, vertex_to_edge_step 3, mid_edge_step 23 (v2round3's classes) | 52 / 52 |

## 3. Twins (`tests/auto_patch_v2/test_stretches.py`, 9; suites `tests/auto_patch_v2` + `tests/test_harness.py` 500 passed)

On the m5e fixture (junction J crossed by taxiway A at D and G at A):
a G-vertex ↔ A-vertex chord produces no row in the whole constraint set
and every priced pair of J's body is a ring edge, a mesh edge or a
common-stretch pair (the all-pairs superset is gone); J's triangles read
3 % where the centroid is nearer G and 1.5 % nearer A, every mesh edge by
its midpoint, the row set exactly {A, D}, `mesh_edges` published; the
solved fixture reads 0 rows in v2 verify AND in the oracle (its mesh and
stretches from the sidecar) with X ↔ the next G node at 1.92 % > D; a
MINTED 2.5 % step on a G-side body mesh edge (vertex 288, edge to 284,
30.1 m) reads 0 junction rows in both readers and — the load-bearing arm —
rows at cap 1.5 % when the same patch is judged without `stretches`.
`test_harness.py`'s sidecar-drift twin covers the new key.

## 4. Not done / open questions (≤ 2)

1. **CYXY pav17 is now held by 04o's route pricing, not a junction
   chord**: `no_step_pairs` 1.5 % × 107.9 m (apron ↔ junction 100) and the
   primary_parallel 6 rect's 299 m within-shape pair at 1.5 %; relaxing the
   no-step family alone puts the apron on the DEM. Is a 300 m all-pairs
   chord inside a rect taxiway face (a PLANE shape by the census's own
   reading) the intended travel-path price, or should rect bodies also be
   priced along their centreline (04o)? Owner question.
2. **Junction ring edges shared with a rect / apron face** are priced twice
   (the neighbour's all-pairs at its cap, the junction's mesh edge at the
   nearest stretch's cap); the stricter binds, which is lawful but means a
   junction's A-side ring edge shared with a D rect stays at D. Is that
   the intended reading of "the stretch the face belongs to"?

Not done: HECA was not rebuilt (its 52 are v2relax / v2round3 classes);
`service_junction` bodies keep `roads.py`'s all-pairs; the oracle warns the
stored HECA sidecar carries `pad_pavement_no_step_edges` / `relaxed_rows`
in neither `SIDECAR_LAW_KEYS` nor `SIDECAR_EVIDENCE_KEYS` (v2padroute /
v2relax keys, not this lane's); `solve/why.py`'s `_FAMILY_KEYS` has no
label for the new generator (it reports under its generator name,
`junction_mesh`, as the chain above shows).
