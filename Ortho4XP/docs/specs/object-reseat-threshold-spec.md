# Reseat threshold: terrain adapts below 1 m, pack modification above — spec (2026-08-09, FROZEN)

Author: lead session (Fable). Status: **FROZEN for implementation.**
Charter: owner 2026-08-09 (OTHH bug report, verbatim): "When it's less
than a meter deviation, adapt the terrain to the custom objects, rather
than reseating the objects. We prefer not to modify an airport if we
don't have to. If it has objects that deviate more than a meter, then
we will need to reseat them."

Parent designs this spec builds ON (read before implementing):
`docs/specs/per-cluster-object-seating-spec.md` (§5 pad law + consumer —
this spec charters implementing §5.2/5.3/5.4/5.5),
`docs/dsf_object_integration_spec.md` (R1 in-place `.obj` rewrite,
`.anchor_bak`, I-15/I-16 idempotence), `docs/object_terrain_features_spec.md`
(R4 Phase-2 interlock). Rulings canon: `docs/RULINGS.md`.

## 1. State of record (recon 2026-08-09; cite, don't re-derive)

* Reseating = the post-mesh y-bake: `post_mesh.rebake_dsf_objects`
  (`post_mesh.py:768`, tile-build step, gated by tile cfg
  `modify_custom_airports` default True and `DSF_OBJECT_REANCHOR`) →
  `object_anchor.structure_deltas` → `object_rebake.apply`
  (`object_rebake.py:928`) rewriting `VT` y tokens in the pack's own
  `.obj` files (backup `.anchor_bak`, provenance sidecar).
* **No deviation-magnitude threshold exists anywhere.** The bake gates
  are size/span/A3 tests; every non-zero delta bakes
  (`object_rebake.py:1146,1153`). At OTHH, 1,210 of 1,421 pack `.obj`
  files carry bakes; reconstructed |Δ| for the 774 measurable clusters:
  p50 0.51 m, ≥ 74 % under 1 m (a lower bound — the sample is biased
  toward worst-seated clusters).
* The terrain-adapt side is inert: pad REQUESTS are recorded
  (`o4_object_foot_pads.json`, v2; 823 cluster requests at OTHH) but
  per-cluster-object-seating-spec §5's consumer was never written —
  today the engine cannot choose terrain over pack modification.
* The only existing adapt-vs-bake selector is by object KIND
  (bridge/tunnel/basin exclusions, `object_terrain_assembly.py:888
  exclusion_set_for_dsf` → `post_mesh.py:531-556`), never magnitude.
* The OTHH pack was `--restore`d 2026-08-09 07:32 (live == backups,
  provenance sidecar removed, backups retained). No migration is
  needed: the next post-mesh pass re-derives from `.anchor_bak`
  authored space and this spec's law decides afresh; the reversion pass
  (`object_rebake.py:1209-1311`) un-bakes anything a new decision
  excludes.

## 2. The law

### 2.1 The threshold

New constant beside the other seating magnitudes (`config.py`, the
`:3589-3610` block):

    DSF_OBJECT_BAKE_MIN_DELTA_M   default 1.0   env O4_DSF_OBJECT_BAKE_MIN_DELTA_M

A SEATING UNIT — a cluster on the default path, a structure on the
non-clustered path, a foot-anchored structure's fitted rigid offset —
is baked only when its required correction reaches the threshold:

    bake(unit)  ⇔  max over the unit's resources of |delta(unit, O)|  ≥  DSF_OBJECT_BAKE_MIN_DELTA_M

using the deltas the existing arithmetic already computes
(`object_anchor.py:1687` per-cluster, `:2818-2820` per-structure).
The max, not the mean: a cluster is one rigid body — baking some
members and not others would tear it, so one member needing ≥ 1 m
reseats the whole unit, and a unit whose every member is under 1 m
stays entirely at authored elevations.

Deviation is measured in AUTHORED space (geometry always re-read from
`.anchor_bak` originals, invariant I-15), so the decision is stable
across rebuilds — a baked pack presents the same deltas next run.

* Decision points: `object_anchor.py:1670-1692` (cluster path, before
  `clusters_baked += 1`) and `:2813-2826` (structure path). Check the
  threshold BEFORE the A3 comparison (cheaper; A3 continues to govern
  only ≥-threshold units). Skipped units take the existing
  `skip_reason` channel with a new counted reason,
  `below_bake_threshold`, carrying the measured max |delta|.
* Supporter-fate is unchanged and applies: inheritors of a
  below-threshold unit stay at authored elevations with the parent's
  reason (the assembly stays put together; terrain comes to it).
* Kind-based exclusions (bridge/tunnel/basin, R4 interlock) run BEFORE
  this law exactly as today — an excluded object never reaches the
  threshold test.

### 2.2 Terrain adapts to below-threshold units

A `below_bake_threshold` unit routes its ground contacts to the pad
system instead of the pack:

* Pad requests are raised for a below-threshold unit's ground-contact
  groups exactly as `_raise_cluster_pad_requests`
  (`object_anchor.py:1771`) / the foot path (`:2776-2811`) do for baked
  units, with target = the ground elevation that meets the UNBAKED
  (authored, as-draped) base — the request record already carries
  `target_ground_metres`, the contact ring, and the relief-cap flag.
* Materiality floor for these requests: new constant

      DSF_OBJECT_NOBAKE_PAD_FLOOR_M   default 0.15   env O4_DSF_OBJECT_NOBAKE_PAD_FLOOR_M

  — a contact group whose |residual| is under it raises no request
  (sub-15 cm float/sink is under the visible-seam scale and the mesh
  quantum; adapting terrain to it would be churn). The existing 0.75 m
  `DSF_OBJECT_FOOT_PAD_RESIDUAL_M` continues to govern residuals of
  BAKED units, unchanged. (Owner may tune; open question Q-A.)

### 2.3 The pad consumer exists (charter)

Implement the pad consumer per per-cluster-object-seating-spec
**§5.2 (next-build convergence loop + `emitted` fingerprint records),
§5.4 (emission: role, precedence pavement > features > pads > DEM,
decimation tier, ordering), §5.5 (validator reader
`verification.check_object_pads`)** — that text is the design of
record; this spec adds only:

* Gate `DSF_OBJECT_OBJECT_PADS` **default ON** (env
  `O4_DSF_OBJECT_OBJECT_PADS`). The parent spec held it OFF pending an
  owner in-sim verdict; the owner's 2026-08-09 charter ("adapt the
  terrain to the custom objects") IS the verdict that the terrain-side
  mechanism is wanted. Env kill switch stays.
* The role literal `object_pad` (§5.4) is NEW and wire-adjacent: it
  must be registered in `ROLE_GRADE_LIMITS` (limit `None`) AND in the
  harness law-family machinery in the same change — the
  `tests/test_harness.py` twins fail otherwise by design. If
  registration surfaces a question the harness twins cannot answer,
  STOP and report; do not improvise a family.
* `modify_custom_airports = False` semantics: the post-mesh pass runs
  in MEASURE-ONLY mode — no pack writes at all (every unit routed as if
  below threshold; pad requests still raised, reversion pass still
  restores prior bakes). The flag gates pack modification, not terrain.
  Today's flag short-circuits the whole pass at `post_mesh.py:793`;
  re-scope it to the write path.

### 2.4 What this yields (the owner's stated preference)

An airport whose every unit deviates under 1 m gets an UNTOUCHED pack —
no backups, no provenance, no writes — and terrain pads where the
deviation is visible. Terrain-class expectations (owner 2026-08-09):
**KCLT and KBNA sit in HILLY terrain** — their sub-1 m units stop
baking, but their ≥ 1 m units continue to reseat; do NOT expect
unmodified packs there. **OTHH is very flat** and is the airport
expected to approach ZERO pack modification: after this law plus the
basin spec, any remaining OTHH bake is a measured ≥ 1 m unit and must
be reported per family — the owner's stated ideal is that the
population trends to zero as the terrain side takes the work.

### 2.5 (v2 amendment, 2026-08-09 — footprint-hugging pad rings)

Owner in-sim report (build 1.0.226, OTHH): object pads emitted as
"large rectangles ... spanning water and parking lots, causing
incorrect elevations" — measured: shapeID 1878 = 162,219 m² / 249
nodes; 1768/1762/1864 = 8-11-node hulls of 17k-30k m², 1762 flat at
−1.21 m across water. THE MECHANISM: the request ring is the CONVEX
HULL of the residual group's contact points (+2 m margin) —
`object_footprints.foot_pad_ring` fed a whole group — so any group
whose parts spread across a complex bridges the non-object ground
between them, and the pad law faithfully flattens it.

THE LAW: a pad ring HUGS the objects it serves. The request ring
becomes the UNION of per-contact-part hulls, each dilated by
`DSF_OBJECT_FOOT_PAD_MARGIN_M` (2 m), with each connected component
of that union raised as its OWN request ring (MultiPolygon components
never re-hulled together). Structural consequence, asserted in tests:
a pad can never span a gap wider than 2× the margin, and every pad
polygon is covered by (its parts' contact-hull union ⊕ margin) — no
vertex of a pad lies further than the margin from a real contact
hull. Grouping for RESIDUAL ACCOUNTING (which parts share one
request record) is unchanged; only the geometry stops being one hull.
Sidecar version bumps (3 → 4) so hull-ring request corpora are
discarded, `emitted` records with stale-version fingerprints drop,
and the convergence loop re-derives. The consumer (`object_pads`)
needs no geometry change — it consumes rings verbatim; verify its
per-request blend-width logic tolerates the smaller rings and that
the refusal accounting still partitions.

**(v2b, 2026-08-09 — the plan-box falsification, measured by the
padrings lane's offline replay.)** Per-part hulls of the recorded
contact geometry do NOT fix OTHH: the request producer records each
part's contact as its AXIS-ALIGNED PLAN BOX, and the offending pads
come from mega-parts whose boxes are the defect (shapeID 1878's
source part is one 560.7 × 534.1 m box; the Bridge_06 water-spanner
is four deck boxes; union-of-dilated-boxes ≈ the group hull; corpus
area moved only −1.1 %). AMENDED LAW: the producer records each
part's GROUND-CONTACT GEOMETRY — the 2D projection of the part's
contact-band triangles (the triangles whose vertices sit in the
part's ground-contact band, the same band the foot machinery uses) —
and the ring law of this section runs on the union of per-TRIANGLE
hulls dilated by the margin, components as their own rings. A part's
ring then follows its real footprint (a road network yields thin
bands, a bridge yields its touchdown patches), and covering water or
lots BETWEEN geometry is structurally impossible. Schema unchanged
(`contact_parts_lonlat` already carries point groups — one group per
triangle is lawful); consumer unchanged. Observability, not law: any
single ring component over 10,000 m² logs at verbosity 1 with its
resource. Structural tests re-run against triangle inputs; add one
mega-part fixture (a large L-shaped contact band) asserting the ring
covers the band and NOT the L's notch, and that a plan-box input
could not have passed.

## 3. Constraints (standing; violations are STOP-and-report)

1. R4 interlock holds: terrain-to-object and object-to-terrain
   corrections never stack — a padded unit is by definition unbaked,
   and a baked unit's pads serve only its post-seat residuals (the
   parent spec's §5.6 decomposition).
2. Pavement never deforms under a pad (parent §5.1 clause 2, verified
   byte-level); pad↔pavement contact welds (R4 weld class).
3. Zero airside effect; census adjudicates.
4. Idempotence I-14/I-15/I-16 hold; the two new constants join
   `_gate_digest` so flipping either forces a re-derive.
5. Build-time HARD LAW: the threshold test is O(1) per unit (~free);
   the consumer's budget statement per parent §7.5 (≤ 0.5 s estimate at
   HECA) with measured confirmation via `tools/check_build_time.py`;
   ≥ 0.6 s triggers the Fable-class optimization review before landing.
   Ledger tripwire discipline (no exclusive timing runs this campaign).

## 4. Tests (twins; headless, tmp_path fixtures)

* Threshold law: synthetic unit at |Δ| 0.99 → unbaked,
  `below_bake_threshold`, pad requests raised (≥ 0.15 m groups only);
  at 1.00 → baked; mixed cluster (one member 1.2 m, rest 0.1 m) →
  whole cluster baked (rigidity); previously-baked pack + now-under-
  threshold decision → reversion restores authored bytes.
* Measure-only mode: `modify_custom_airports=False` → zero pack writes,
  requests still recorded, prior bakes reverted.
* Consumer: request → emitted `object_pad` welded to pavement values,
  clipped, within relief cap; refused-over-cap surfaced as finding;
  `emitted` record re-emits stably; fingerprint staleness drops it.
  Two-build convergence harness (parent §7.4 risk item): requests
  vanish at the fixed point.
* Harness twins: `object_pad` family registration
  (`tests/test_harness.py` extension).
* Existing suites: `tests/test_object_anchor.py`,
  `test_object_cluster_seating.py`, `test_object_rebake.py`,
  `test_supporter_fate.py` — via `tools/run_with_ledger.py`, selection
  from `tools/blast.py` on every edited file.

## 5. Acceptance

1. Unit tests + blast-radius suite green (ledger).
2. Degeneracy gate: with `O4_DSF_OBJECT_BAKE_MIN_DELTA_M=0` (threshold
   disabled) behaviour is byte-identical to HEAD — packs, patches,
   provenance. Any diff is a bug. With the default 1.0: KCLT and KBNA
   (HILLY terrain, owner 2026-08-09) end with every remaining bake at
   max |delta| ≥ 1.0 m and every sub-1 m bake reverted — report
   modified-file counts before/after and the delta distribution of
   what remains; their patches CHANGE where pads replace sub-1 m
   bakes (census-adjudicated, no new airside rows).
3. OTHH (+25+051), two harness tile passes (the convergence loop needs
   the post-mesh step, so patch-only builds cannot verify this —
   budget it honestly): (a) modified-`.obj` count collapses from 1,210
   to only ≥ 1 m units — report the count and the per-family list;
   (b) build N+1 emits pads for the sub-threshold population; report
   count, area, relief distribution, over-cap refusals; (c) the
   validator reader is finding-clean; (d) census vs the 2026-08-08
   control: zero NEW adjudicated airside rows, groundside deltas
   attributed.
4. HECA: no regression in floated-object counts (the per-cluster
   seating campaign's metric); units ≥ 1 m still bake there. Report
   the below-threshold population size.
5. Build-time impact statement per §3.5.

## 6. Convergence guards (mandatory)

Materiality 0.01 m / 0.01 pp; attempt cap 2 per target then
STOP-and-report; `.progress` heartbeat. Honest budget: ledger suite +
2 OTHH tile passes + KCLT/KBNA/HECA patch-level controls; hard cap 3
tile passes. Foreground only; nothing here is a timing claim.

## 7. Open questions (owner)

* **Q-A** `DSF_OBJECT_NOBAKE_PAD_FLOOR_M` default 0.15 m — confirm or
  tune (the visible-float floor for units the pack never moves).
* **Q-B** `DSF_OBJECT_OBJECT_PADS` default ON everywhere (recommended;
  this charter implies it) vs ON only where a below-threshold unit
  exists.
