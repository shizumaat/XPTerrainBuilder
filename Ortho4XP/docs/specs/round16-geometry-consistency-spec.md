# Round 16 — the geometry-consistency family

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **r16geom**. Pre-ship mode
(docs/RULINGS.md — read it; a brief violating a listed ruling is
invalid); mid-implementation deviations STOP-and-report to the Fable
lead, never decided in-lane. Owner-ruled round (closing interview
2026-08-11): one full round, four laws, one implementer.

## Measured attribution (carried evidence — do not re-derive)

* **Twin-ring spelling (R15-2 ledger, lane/r15mesh):** the +25+051
  crash vertices are Triangle Steiner points from a ZERO-WIDTH
  CONSTRAINED LENS minted by ONE RING SPELLED TWICE in the patch:
  `object_pad:2336`'s exterior ring vs its `shape_interior_ring`
  partner way, differing by one vertex EXACTLY on the chord.
  Population in the OTHH patch: **33 twin-ring pairs / 59 missing
  vertices / 5 exact-on-chord**. Mechanism: the sliver-corner repair
  removes needle vertices from EXTERIOR ways, and the chain-consistent
  needle-removal law (`layout.py` ~1606–1656) scans `pending`
  (exterior chains) only — `_interior_rings` never join the scan in
  either direction, so a hole ring keeps the vertex its pad's exterior
  lost.
* **Wall-face / anchor (R14 ledger residual, folded into this round):**
  recon measured **275 wall nodes ≥1 m above a ramp within 2 m**; the
  unowned **0.62 m `wall_gap` strip takes Z0** (no shape owns it, the
  mesh drapes it); and the transition anchor lands at the SHALLOWEST
  station against the law's own deepest-station prose
  (`groundside.py` `_BelowGradeIndex` / `transition_law_altitudes`,
  the prose at ~:456–505 is the law). Owner-visible tearing at
  **25.2566, 51.6095** (OTHH).
* **Claim floor (R14 ledger residual):** KCLT triangle level plate
  spread 0.13 m vs the 0.10 bullet — two ADJACENT claimed regions
  carry different clearance floors (**210.87 / 210.98**). Ruled fix:
  ONE floor per connected claimed plate — the walk's depth law
  (round-14 spec, i.e. the round-10 depth law applied to the walk)
  applied at CLAIM scope. Per-level floor machinery:
  `bridges.py` ~5312–5469.
* **The 25° pavement-needle class:** same OTHH site; the round-15
  spec's bookkeeping note places it in the "emitted near-coincident
  geometry makes mesh slivers" family. Population NOT yet
  characterized — R16-4 begins with attribution, never with a fix.

## The laws

### R16-1 ONE BOUNDARY, ONE SPELLING — needle removal sees every chain

The chain-consistent needle-removal law runs in the frame that
contains EVERY final chain: exterior ways AND interior hole rings.
Reorder so the removal scan runs where both populations exist with
holes already deduped to one chain each (the hoisted `_hole_key` dedup
— one hole, one chain), and scan symmetrically: a vertex the sliver
repair removed from ANY chain leaves every OTHER chain through it
under the existing near-collinear predicate (0.09 m needle height,
unchanged); a partner where the vertex is a REAL corner keeps it
(existing guard, unchanged — for a true twin the chord is identical,
so twins converge by construction). No new geometry, no second
registry, and this must remain BEFORE the nid-level final weld, which
stays the last geometry-affecting step (its own standing law).

Measure: twin-ring pairs in the emitted OTHH patch (a pair of emitted
chains spelling the same boundary with differing vertex sets)
**33 → 0**.

### R16-2 THE WALL FACE IS OWNED GEOMETRY + THE ANCHOR IS THE PORTAL

(a) **Deepest-station anchor.** Per below-grade body
(`index.component_of`), the portal is the body's DEEPEST station: the
minimum profile altitude over that body's source rings. The anchor is
the governed ring vertex nearest that station, pinned at
`deepest_alt + cap × gap` measured to THAT station — replacing the
per-vertex nearest-edge minimization that measured out at the
shallowest station. The docstring prose is the law; make the
behaviour match it. Relaxation around pinned anchors is unchanged.

(b) **No unowned strip.** The `wall_gap` strip between a ramp's outer
edge and its wall must be OWNED geometry: the wall face IS the wall's
— its inner boundary coincides with the ramp's outer boundary (welded
node identity, the canonical join — never proximity), carrying the
ramp's values on the inner edge and the crest's values on the outer
edge, so no strip is left for the mesh to drape at Z0/DEM. Follow the
existing wall emission idiom in `bridges.py` (the `wall_gap_m` sites);
reuse existing roles — a new role literal is a wire/blast hazard and a
STOP-and-report.

Measure: the 275-node population (wall nodes ≥1 m above a ramp within
2 m over an unowned strip) → **0 unowned**; no Z0-valued vertex inside
any former gap strip at the owner site 25.2566, 51.6095.

### R16-3 ONE FLOOR PER CONNECTED CLAIMED PLATE

Connected claimed plates — connectivity as the claim law itself
computes it, never a private union — share ONE clearance floor: the
joint depth (the minimum of the members' floors under the round-10
depth law, applied at claim scope). KCLT triangle: 210.87/210.98 →
one floor; the level-plate bullet (≤0.10 m spread) is restored.
Protected/pinned vertices keep their exactness (r14 behaviour).

### R16-4 THE 25° PAVEMENT-NEEDLE CLASS — attribute, then declaw

FIRST (mechanism-before-fix): characterize the population at
25.2566, 51.6095 and patch-wide in the emitted OTHH patch — outline
corners whose tip angle is near/below ~25°, their heights (they stand
ABOVE the 0.09 m near-collinear floor, which is why the existing
repair spares them), counts and roles. Quote the numbers in the
commit. THEN: an emitted pavement outline never carries a tip that
mints near-degenerate constrained triangles — blunt/declaw at emit,
riding the SAME partner-consistent chain frame as R16-1 (a declawed
vertex change applies to every chain through it or none). The angle
threshold lands as a config.py constant proposed from the measured
population (25° is a reporting observation, not yet law). If the
measured mechanism is NOT an outline-needle class — e.g. the tearing
is wholly the R16-2 strip presenting as needles — STOP and report
with the geometry; R16-2 may already cover it.

## Tests

Directly-covering files once, ledgered (pre-ship mode; pre-existing
failures matched at base are out of scope):

* R16-1 twin: synthetic pad-in-hole layout where the sliver repair
  removes a chord vertex from the pad's exterior — assert the emitted
  hole ring and pad ring spell ONE chain (and the symmetric
  direction).
* R16-2 twins: synthetic two-station ramp — anchor lands at the
  deepest station; wall inner boundary spells the ramp's outer
  boundary node-identically; no vertex between them unowned.
* R16-3 twin: two adjacent claimed plates with different member
  depths → one shared floor = the joint depth.
* R16-4 twin: per the measured mechanism (write after attribution).

## Acceptance (battery-run LAST — only after all unit tests pass)

* OTHH rebuilt through the harness (`tools/harness/build_airport.py
  OTHH --tile 25 51`), then the mesh replay
  (`tools/run_tile_mesh_only.py`, `first_step=2`, real inputs, LANE-
  LOCAL build dir — NEVER the X-Plane install): rc=0; twin-ring pairs
  33→0; sub-micron vertex clusters (pairs within 1e-9°) at or below
  the r15 count. The r15 scratch cluster-counter is hereby on its
  SECOND use — promote it into `tools/` with an INDEX entry and twin
  in the same commit (RULINGS `7e90032`); rebuild it from the r15
  ledger description if the scratch copy is gone.
* `tools/harness/census.py` on the OTHH patch before/after: quote the
  class-table delta; no new law-true rows from R16-1/2/4 beyond the
  0.01 m materiality floor.
* KCLT rebuilt: one claim floor, level-plate spread ≤0.10 m, round-10
  table holding; KCLT is also the twin-ring CONTROL (expect 0 pairs
  before and after).
* Build-time: pre-ship tripwire only; the brief's impact statement
  stands (all four laws are emit/solve-local, expected ≪1 % of the
  60 s budget); any measured ≥1 % goes to a Fable-5 optimization
  review before landing (hard law).

## Bookkeeping

Convergence guards (mandatory): materiality floor 0.01 m (elevation
classes); attempt cap 2 per pre-registered target, second miss =
STOP-and-report; `.progress` heartbeat in the lane scratch dir.
Every skipped verification = one line for
`docs/DEFERRED_VERIFICATION.md` (lead writes the final lines).
Cross-refs: r15 spec (mesh containment stays; this round removes the
minting), r14 spec (claim law, walk floor), RULINGS.md (canonical).
