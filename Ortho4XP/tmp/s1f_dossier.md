# S1f — THE +89 ADJUDICATION AND THE ARCHITECTURE-DEBT DOCKET (lane `lane/s1f`)

Tree: worktree `s1f` at `lane/s1e` tip (`1514efa`), the mid-only single-
projection tree.  Every number below is measured on the SHARED corpus
through the harness entries; no lane-private build or census wrapper.

CONTROL IDENTITY, FIRST (identity-mismatch law).  A HECA `--patch-only`
build of this tree with the seam audit armed emits `body_sha=3ab5a8dfae80`
— byte-identical to S1e's own mid-only arm — and the harness reports the
shared repo UNCHANGED.  So the instrument added here (the seam ledger
dump) is byte-inert and every arm below is comparable to S1e's.

## ITEM 1 — WHAT THE LATE PROJECTION WAS DOING AT THE +89's SITES

### The join

`census_rows_diff` on the two S1e arms (`s1e_p1c_heca` control,
`s1e_mid_heca` mid-only; identical law knobs and axis frame, so the join is
lawful): EXACT 7,048, MOVED 0, GONE 91, NEW 207, NET **+116**.  The airside
headline is `within_shape::apron|apron` NEW **134** / GONE 70.

Canonical identity join of those 134 rows against the control arm — 11-
decimal lat/lon spelling, the patch's own layout-local metre frame taken
from the axes sidecar's anchor, never proximity — resolves **134 of 134**,
zero unmatched.  Per row the control differs from mid-only at:

| both endpoints | one endpoint | neither |
|---|---|---|
| 49 | 85 | **0** |

**183 endpoint values** the late call moved: |Δ| min 0.010 m, **p50
0.040 m, max 0.240 m**, spread over **93 distinct coordinates in 27
clusters** at 80 m — dispersed across the airport, not one site.

What stands at those nodes in the control (every way at the node id, features
included): moved endpoints are `apron` (71), `apron+taxiway` (71),
`apron+building` (34), `aerodrome+apron+building` (6), `apron+building+
taxiway` (1).  **No ribbon, bridge, clearance, skirt or band feature stands
at any of them.**

### The interventional read — the seam ledger

`O4_GEOM_SEAM_AUDIT=1` with the new `O4_GEOM_SEAM_AUDIT_JSON` dump, on the
mid-only tree (the arm whose body reproduces S1e's).  Airside VALUE
authorship after the pipeline's single projection (seam 19):

| seam | airside survivor values moved | worst |
|---|---|---|
| `20_post_projection_conformance` | **8** (pad-host relevel) | 2.950 m |
| `21_skirts_gapfill_bands` | 0 | — |
| `22_weld_crown_densify` | 0 (118 inserts, 3 off-lerp) | — |
| `23` (late-projection position, relevel only) | **0** | — |
| `24_spine_reclamp`, `25_strip_reconcile` | 0 | — |
| `26_band_seal` | 20, of which **18 groundside** | 9.382 m |

So between the surviving projection and emit, **ten airside vertices** are
re-authored in total, at two named passes.  The 183 endpoints the late call
moved were at sites **nothing had disturbed since the first call exited**.

### The pre-registered test of branch (b), and its REFUTATION

Branch (b) was tested before it was believed.  If the late call had been
"this same law, continuing" — the first call exits UNCONVERGED and says so:

    [proj-law-certificate] HECA final#1 ENTRY: over_cap=24121 law edge(s)
    [proj-law-certificate] HECA final#1 EXIT:  over_cap=16141 law edge(s)
    [final-projection] HECA: 119735 nodes, 9791 hard -> 7107 edge(s) over cap

    criterion=convergence: flat_blocks >= SWEEP_CONVERGENCE_PATIENCE=2,
    a block counting as flat when its drop < ... = 76 edge(s);
    n_material trajectory 15424 -> 15306 -> 15242 -> 15181;
    last block drop +61 edge(s)

— then giving the ONE call the patience the retired PAIR supplied should
reproduce its work.  Implemented and built (scoped `convergence_patience =
2 * SWEEP_CONVERGENCE_PATIENCE`, threaded the way `sweep_hard_cap` already
threads; arm `s1f_conv_*`):

| arm | projection exit | census vs the S1e control |
|---|---|---|
| mid-only (S1e) | 7107 over-cap edges, 17.4 s | +116 (NEW 207 / GONE 91) |
| **+ the pair's patience** | **7011**, 23.8 s | **+100 (NEW 247 / GONE 147)** |
| CYXY, same change | 55 → 55 | **+0, EXACT** (328 rows, all EXACT) |

**The target class does not move: `within_shape::apron|apron` stays at
134 NEW, unchanged, row for row.**  The extra sweeps bought −16 net
elsewhere while ADDING 43 new rows (10 airside) — and under the binary-law
merge criterion the number that counts is rows FLIPPING INTO violation,
which goes 207 → 247, i.e. WORSE.  The change was therefore REVERTED, not
kept: it does not do what it was built to test, and it costs flip-ins.
The refutation is the finding.

### The verdict — (a), A DEGRADATION SHIELD

With (b) measured false, what is left as the difference between the two
calls is the one thing S1e already named and this lane can now price: the
HARD SET.  The first call runs with **9,791** hard nodes, the retired
second with **20,213**, and the increment is the projection's own
contract — *"nodes welded to already-emitted FEATURE shapes are HARD"*.
By the late position the post-solve feature emission has frozen half of
airside at values the geometry-freeze law says must not constrain the
solve; a pair with ONE hard endpoint puts ALL of its correction onto the
free one instead of splitting it, which is exactly the signature measured:
free apron INTERIORS nudged 0.010–0.240 m (p50 0.040) at 93 coordinates,
while 27 of the 85 stationary partners stand on the `aerodrome` boundary
feature.

That is branch (a) verbatim: **the late call was re-dragging airside
interiors onto post-solve emitted feature values.**  It closed 134
near-cap apron pairs not by solving the law better but by re-solving it
under pins the freeze forbids.

**Consequences, per the brief's own routing.**  The +89 / +134 is the
HONEST UN-SHIELDED STATE and **the mid-only collapse STANDS**.  The rows
route to their true minter: the pipeline's single projection exits with
7,011–7,107 over-cap edges out of 24,121 at entry, and these 134 are the
near-cap tail of that residual — upper-bound excess (grade_mid − grade_ctl)
p50 **0.248 pp**, 36 of 134 within **0.10 pp**, 24 within 0.05 pp; chord
p50 20.7 m, max 417.6 m.  They are the same population the census already
reports as HECA's 7,139 rows, and they belong to the round's stage-B /
solve work, not to the projection's position.  No new mechanism is
required to explain them, and none is invented here.

## ITEM 2 — THE STAGE-B GROUNDSIDE CONFORM DEBT

Attribution, from the same seam ledger (mid-only HECA, the arm that
reproduces `3ab5a8dfae80`):

* **`14_groundside_separation` — the post-solve law seating.**  894
  `service_junction` vertices re-authored, worst **3.260 m**
  (`63.870 → 67.130` at (−5922.2, 336.7)).  This is
  `seat_service_pavement_on_law` / `seat_groundside_on_law` doing exactly
  its charter: seating rings the one solve never reached.
* **`26_band_seal` — the pipeline's LAST elevation author.**  20 vertices,
  **18 of them `service_junction`**, worst **9.382 m**
  (`115.980 → 106.598` at (−2418.2, −148.2)).  Nothing runs after it.

**The defect is not the seating's within-ring law — it is the STEP BETWEEN
RINGS.**  `seat_service_pavement_on_law` already closes its own ring
(`groundside.py:1677`, `_grade_limit_ring(ring, alts, cap, pinned=pinned)`
at the strictest cross-section cap), which is why the within-shape rows on
those rings are lawful.  What no pass owns is the seated ring against its
seated NEIGHBOUR: the census families that grew when the second projection
retired are precisely the BETWEEN-shape ones — `mid_edge_step` (42 of 45
new sites `service_junction`), `vertex_to_edge_step` (9 of 9),
`transverse` (41 of 49).  Under weld-or-gap a shared-node disagreement is
always a defect, and the seating mints it because each ring is graded in
isolation.

Site evidence, joined: the largest new step cluster is
(30.1067, 31.4105), ways −13273 | −11733 (9 `mid_edge_step` rows, worst
2.993 m), ~100 m from the band seal's own 9.4 m authorship at
(30.1076, 31.4096) — the same corridor.

**Status: ATTRIBUTED, NOT IMPLEMENTED.**  The lawful resolution is the
seating grading its steps against its neighbours (the weld-or-gap law
applied at the seat, absorbing the level change over the losing ring's own
run — the S6 routing's "a losing lot adopting the winner's value must
absorb the level change over its own run", the same integral constraint
the corridor profile carries).  That is a stage-B law change and it is
sized like one; this lane surfaces the minter with numbers and does not
land a partial version of it.

## ITEM 3 — THE SEED-PASS / REPEATED-CONSTRUCTION CENSUS

Measured with the merged duplicate-work census
(`profile_airport_build.py --count-inputs{,-identity} --count-clock cpu`)
on CYXY whole builds — **no solve capture exists on disk**, so a HECA
replay would itself have cost a build.

Five `_seed_elevations` call sites (`solve.py:1204, 2005, 5206, 5771,
6599`); three fire in a default build.  Six unified-graph builds, roster
written down at `grade_graph.py:2806-2810`; five fire now (the
adjacent-ground one is already served by `geometry_freeze.frozen_band`,
and the validator's fires only for a never-solved layout).

| construction | calls | verdict |
|---|---|---|
| `build_context` | 5 | **(b)** already collapsed — `centerline_specs` is memoised (8 calls, 0.0 s CPU) |
| `build_unified_graph` | 5 | **(c)** UNFINGERPRINTABLE by value; identity mode cannot judge it (fresh `bucket_to_idx` per call). Its per-shape layer IS memoised (`layout._sc_run_memo`): HECA 1,275/12,078 exact reproductions |
| `_build_shape_constraints` | 2 | **(b)** — shares the solve's ctx; the final pass runs on a rebuilt node space with `defer_shape_ids` |
| `_build_node_list` | 5 | **(c)** — 3 identity duplicates (0.19 s CPU) mean only "same layout object"; it mutates between every pair |
| `_seed_elevations` | 3 | **(b)** — distinct node lists; two are read-only readbacks |

**The one architectural (a):** the geometry freeze ALREADY builds and
publishes nodes + ctx + graph + band (`pipeline.py:5877`,
`geometry_freeze.publish`), and the solve REFUSES to reuse them
(`solve.py:2059-2086`) — not for a law reason but because
`shape_constraints_cached`'s per-ctx memo is keyed on `id(s.polygon)`
(measured breakage when reused: within_shape 3,764 → 5,629, worst 431 %).
Collapsing it means re-keying that memo onto the existing VALUE key
`_sc_run_key` (`grade_graph.py:2770`) plus the between-gap ring WKB set.
**Byte-preserving only while the node space is the same one** (append-only,
`solve.py:2061`); relabelling across a different node numbering is a
float-path change already measured and rejected (last-ULP route-budget
divergence, `grade_graph.py:2828-2842`).  Reported, not landed — it is a
solver-identity change and wants its own arm.

## ITEM 4 — THE SOLVE-CAPTURE DEM BOUNDARY LEAK

**Mechanism located, NOT implemented.**  `solve_capture.PICKLED_KEYS`
carries `tile_dem` — and on the AIRPORT path `tile_dem` is `None`
(`pipeline.py` passes it only for tile builds).  Phases 5-6 then call
`elevation._load_airport_dem` at REPLAY time and get whatever the shared
caches hold, which is the leak the ruling names: the replay's DEM is not
the build's.  `CAPTURE_VERSION` is still 1.

The fix's shape is therefore: capture the airport DEM (and the flat-site /
sea-exclusion products derived from it) that phases 5-6 would load, install
it at replay as the memo `_load_airport_dem` returns, and bump
`CAPTURE_VERSION` so every older capture refuses rather than default-filling.
Acceptance (OTHH capture→replay REPRODUCES, HECA still REPRODUCES) is four
builds plus replays; it did not fit this lane's budget beside items 1-2.
**OTHH replays remain not quotable.**

## ITEM 5 — THE STATION PATH AND THE INVERTED TUBES

**(a) The legacy per-vertex station path.**  Three writers inside
`_svc_seed_and_project` (`route_profile/anchors.py`): the whole-run corridor
profile (HELD, membership only, `anchors.py:4083-4091`, scoped to LINEAR
runs at `:4092-4123` — 2-D yards released per the Fable scoping ruling);
the pointwise station clamp (`:3707-3752`); and the legacy per-vertex path
(`:4030-4082`) owning every `svc_node` the spine never reached.  They do
NOT write the same nodes (`:4033-4048` skips claimed ones).  **The
over-cap residual, quoted:** only the profile enforces a longitudinal cap
(`corridor_profile.py:285` mints `over_cap_segment`); the other two clamp
into the BAND only — `anchors.py:3738-3740` and `:4077-4079` are both
`tgt = min(max(de, lo), c)`, a per-node band clamp **with no neighbour
term** — so DEM-follow noise between adjacent vertices is unbounded by cap
on exactly the nodes the whole-run law never reaches.  Routing the residual
through the profile's machinery therefore means giving those fallbacks a
Lipschitz pass over the adjacency (the `e_cap·dd` metric `_reach` already
prices at `:3920-3923`), or solving released yards as surfaces with the
profile's values as boundary seeds — which the scoping comment at
`:4093-4096` already names.  **Attributed; not implemented** (attempt
budget went to items 1-2).

**(b) The 1,631 inverted-tube conflicts.**  Both reach regimes are ONE
function at opposite sign: `anchors.py:3893-3926` `_reach(sign)`, called as
`ceil = _reach(+1)` (`:3928`) and `floor = _reach(-1)` (`:3929`).  Both are
lazy Dijkstras over the SAME `adj` from the SAME anchor set, so each claims
every node reachable from any anchor; the tube is
`[max floor, min ceil]` (`:3266-3272`) and the inversion is RECORDED, not
blended, in `_relax_tube` (`corridor_profile.py:192-219`, materiality
0.01 m at `:213`).  **Why it is an S1 boundary condition:** the anchor set
at `anchors.py:3880-3891` is built from every non-service, non-groundside
ring with **no stage discrimination**, although the stage machinery is
precise and available (`solve_stage.py:66-75`, `:88-99` `stage_of_role`,
`:107-120` `stage_of_roles`, `:159-171` `split_by_stage`).  `floor > ceil`
is literally two stages disagreeing.  Composing at the boundary = tag each
anchor with `stage_of_roles`, run `_reach` within stage A to freeze the
airside envelope, then run stage B reading those values as IMMUTABLE
boundary data (the corridor-mouth weld posture the 2026-08-14 rim-pocket
ruling names).  Residual inversions then partition into real vs
cross-stage, which today they cannot.  **Attributed; not implemented.**

## ITEM 6 — THE FRONTAGE ROW (30.12549863, 31.41625211)

**Verdict: NOT stack-minted.**  Read verbatim out of two census
`--rows-json` dumps: the row is `frontage_near_miss  apron|building
airside`, and it reads **|de| 0.04 m / 6.3544 %** in the round-close
reference body and **|de| 0.05 m / 7.9429 %** in the S1e mid-only arm —
same site_m, same ways (−10257 apron, −10022 building22 pad, 0.629 m
apart).

Dumping way −10257 in both arms: the apron ring's own graded vertices
(−2402…−2410) are **byte-identical** across the arms (83.71–83.85).  The
three pad-seat nodes welded into that ring (−214/−213/−212) read
**83.67** in the reference and **83.66** in the arm — matching building22's
`altitude` tag.  The offending pair is apron vertex −2409 at 83.71 against
the pad seat: 83.71 − 83.67 = 0.04, 83.71 − 83.66 = 0.05.

So the value that MOVED is the building22 seat, and it moved by exactly
**0.01 m — one emitted-altitude rounding step, and exactly the standing
materiality floor**.  The 1.6 pp of grade is that one rounding step divided
by a 0.629 m arm.  The row PRE-EXISTS the stack at 6.35 %; the docket's
"stack-minted" label is an artifact of two-decimal emitted altitudes over a
sub-metre frontage arm, not a minting.  The real question the site raises —
why apron vertex −2409 (which carries no pad seat, so the emitter's
seat-skip at `check_grade.py:4501-4505` does not excuse it) is not bound by
the near-miss law — needs the solve-side `_fp_law_counts` edge list for
building22 (`solve.py:6764`) dumped, which is an instrumented run this lane
did not spend.  **Named precisely; the residual question is stated, not
guessed.**
