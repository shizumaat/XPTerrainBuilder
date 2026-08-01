# Apron string law + cache-aware scheduling + anchor honesty

Owner rulings 2026-07-30.  **Revision 2** — incorporates the Fable
code review (2026-07-30) and the owner's four resolving rulings.
Review verdict on revision 1 was "not ready"; the blocking findings are
resolved below and marked ★.

---

## Part A — cache-aware build admission (owner item 1 + item 2)

### A.1 Rulings

> "Update the concurrency to consider whether a tile has its data
> cached, so I could run as many tiles as I have cores concurrently if
> they have all their data downloaded, and as downloads complete more
> are allowed to start, but keep downloads to 4 concurrent."
>
> "I think we can let the machine manage the CPU."
>
> **Resolving (2026-07-30):** "4 OSM + 4 imagery"; "cap memory usage to
> 80 % of available memory".

### A.2 Semantics

**Fetch admission — per class, 4 each.**  `OSM_CLASS_LIMIT = 4`,
`IMAGERY_CLASS_LIMIT = 4` (was 2/2), env-overridable
(`O4_OSM_CLASS_LIMIT` / `O4_IMAGERY_CLASS_LIMIT`, already landed).
A tile holds a fetch token only while it may issue remote requests and
releases it the moment it cannot — generalising the landed
vector-split release at `AutoPatchBegin`.  The imagery step is likewise
hybrid: release at download-queue drain, continue the DDS conversion
tail under compute.

**Compute admission — cores, bounded by memory.**  A tile needing no
fetch token is admitted while BOTH hold:
* concurrent compute tiles < `machine_core_count()` (logical cores; the
  OS arbitrates the processor per the 2026-07-17 ruling), and
* projected memory ≤ **80 % of available RAM** (owner ruling).  The
  projection reuses the existing `MESH_MEMORY_ESTIMATES_GB` sizing,
  extended beyond the mesh step to any step with a memory estimate.
  ★ This replaces revision 1's cores-only rule, which the review showed
  would admit 16 tiles on a 16-core/32 GB machine where today's formula
  admits 5.

The retired `effective_build_slots` single-slot count no longer gates
compute; keep the symbol only if something outside this spec needs it.

**Cache determination — per-subsystem predicates.**  ★ The scheduler
MUST NOT re-derive "what will this step read": that is a duplicated
derivation and it will drift (scheduler says cached → step fetches
anyway → the fetch cap is breached silently).  Each fetch subsystem
exposes its own `is_cached(tile)` predicate co-located with its fetch
code — elevation (incl. **airport insets**, honouring their STALE
semantics), vector/OSM extract, imagery, **bathymetry**, airport packs.
Cheap and conservative: filesystem/manifest only, never a network
probe; unknown ⇒ NOT cached.
★ Imagery's needed-set is mesh-derived and cannot be enumerated up
front, so imagery's predicate requires a **step-completion manifest**
written when a tile's texture set finishes; absent a manifest the
answer is "not cached".  Writing that manifest is in scope.

**Promotion.**  A released fetch token dispatches to a queued tile in
the same lock hold.  An already-cached queued tile never waits for a
fetch token.

### A.3 The invariant, stated honestly

★ Revision 1's "never more than N tiles issuing remote requests" is
not implementable from the parent: the parent-side OSM cache warmer
(`parallel.py:1329-1440`) is untokened, and three child-side fetchers
(background vector prefetch `O4_Vector_Map.py:298`, airport-inset
WCS/COG pool, bathymetry prefetch) are invisible to the parent.
Therefore:

* **Binding invariant:** no tile is ADMITTED to a fetch phase beyond
  its class cap, and the parent-side cache warmer takes an `osm` token
  like any other fetcher.
* **Acknowledged slack:** background prefetch tails may briefly run
  past a token release.  Bounding them properly needs child→parent
  transition events (a wire-protocol addition — additive only, and
  `tools/blast.py` must be run plus the Swift client checked for
  unknown-event tolerance).  **Out of scope here; recorded as the
  known residual.**
* Acceptance asserts the admission invariant, not the unobservable one.

---

## Part B — the apron string law (owner item 3, as clarified)

### B.1 Rulings

> "An apron's 'string' should be straight chords between taxiway
> connections, buildings, and all edges.  Essentially an apron *wants*
> to be flat across its whole surface, but is allowed to grade up to
> 1% where necessary, no more."
>
> **Resolving (2026-07-30):**
> * "The apron is not 1% all-pair, **it's visible geodesic**, and the
>   taxi spines get 1.5%."
> * "1.5% along spine, 1% lateral in aprons."
> * "Unless we have better than 1 m lidar coverage, DEM is not accurate
>   enough to drape and pavement should **cut through or fill**:
>   straight chords between anchors.  If we have 1 m coverage then we
>   could drape."

### B.2 ★ The cap structure (resolves the review's blocking finding)

The review showed a strict isotropic 1 % cap is infeasible by
construction wherever a spine climbs at its own 1.5 % through an apron
— i.e. across HECA's terminal fabric.  The owner's clarification
resolves it:

* **Longitudinal (along a taxi spine crossing the apron): the spine's
  own per-letter cap, up to 1.5 %.**
* **Lateral (transverse to the spine, and everywhere no spine
  governs): 1 %, flat-preferring.**

Implement in the SPINE FRAME using the landed decomposition
(`grade_graph.ds_decompose` + the route oracle) — build-once reuse, no
new derivation.  This is the same frame the spine-frame pair law
already uses, so the two laws cannot disagree.

### B.3 ★ Visible geodesic, not all-pair

The apron grade law binds **mutually visible vertex pairs**, budgeted
along the **geodesic distance within the apron component** — not every
vertex pair against its straight-line chord.  For a mutually visible
pair the geodesic IS the chord; for a pair whose straight line leaves
the pavement (through a building, a gap, another shape) the law does
not apply directly, and the relationship is governed transitively
through the intermediate visible pairs along the real path.

Consequence to verify and report: this is precisely the composed
straight-chord chain that produced the 2026-07-29 burial (a 2,940 m
"chain" whose hops were chords through buildings and across a
slice-welded fabric).  The implementer must confirm whether the
existing `visible_fn` / mesh-membership gating in
`grade_graph.shape_constraints` already implements this ruling, partly
implements it, or contradicts it — and report the measured change in
the HECA composed-chain budget.

### B.4 The reference surface R

Per **connected apron component** (★ union of welded apron-role shapes,
not per shape — per-shape R mints a reference step at every
apron↔apron weld):

* **Anchors** (R equals these): taxiway connections (spine crossings);
  building pad-face contacts — the pad's **rod level**, not the raw
  seat scalar (the landed pad-rod coupling; 21/25 HECA pads differ);
  and all welded boundary edges against any graded neighbour.
* **Between anchors: straight chords**, per the ruling.
* **Flat is the preference**, expressed as ★ **minimum Dirichlet
  energy** (squared gradient) subject to the anchors — revision 1's
  "minimise total gradient magnitude" is degenerate (L1 ties every
  monotone profile).  The 1-D restriction of the Dirichlet minimiser
  between two anchors is exactly the straight chord, i.e. the ruling.
* **Caps** per B.2 (1.5 % longitudinal / 1 % lateral), applied per edge.
* **Construction:** Dirichlet solve + POCS projection onto the per-edge
  cap slabs, on the shape's existing CDT edge set
  (`grade_graph.mesh_edge_keys` — the declared single source; no new
  triangulation).  O(E·sweeps); E ≈ 3 k for the 931 k m² component,
  est. < 0.1 s.
* ★ **Frame and sample time:** R lives in the crown-lifted z′ frame;
  anchor values are sampled from **law-true sources** (pad rod levels,
  rod-held spine values), never from raw `elev` at yield entry — that
  re-imports the exact pathology Part D diagnoses.
* R supplies **`z_ref`** for non-anchor apron nodes (★ it does not
  replace phase A — the §7 machinery is landed and measured; a second
  interpolator would be a duplicated derivation).

### B.5 ★ Terrain: cut through, conditionally drape

Default: **cut through or fill** — the patch is authoritative; an
interior DEM rise under real apron pavement is not a support
constraint.  Draping is permitted **only** where the tile's elevation
source is 1 m lidar or better (the engine already knows its elevation
level — see the level classes behind `MESH_MEMORY_ESTIMATES_GB`).
Below that accuracy the DEM may not push pavement around.
Gate the drape branch and default it off except on qualifying sources;
report which HECA sources qualify (expected: none).

### B.6 Residual open item for the owner

HECA's largest apron component is slice-born, 931 k m², 3.0 × 2.1 km,
spanning ~40 m of real relief.  Under B.2/B.3 it may now be feasible
(the spine carries 1.5 % longitudinally and the geodesic law no longer
composes chords through buildings).  **Measure and report** whether it
is; if it is still infeasible, the question of splitting it returns to
the owner.  Do not split it on your own authority.

---

## Part C — groundside pins must not float above their own DEM

### C.1 Defect

`gs_pin` anchors sit **+7.76 m median above their own DEM** (max
+9.88) while detached building pads sit at +0.06; independently they
are the **floor witness for 4,213 broken nodes**.  Mechanism confirmed
in code (`anchors.py:1386-1411`): the lift is
`base_elev − cap·route_len − dem_gs`; `route_len` is capped at 90 m but
**the lift itself is unbounded**, and the result is frozen as a HARD
pin.  A high apron thus launders its own error into an anchor that
locks it in.

### C.2 ★ Semantics — a VALUE bound (revision 1's rule was vacuous)

Every `gs_pin` is a mouth weld by construction, so revision 1's
"except within a mouth zone" constrained nothing.  Replace with:

> A groundside pin's value may not exceed its own DEM by more than
> `cap · MOUTH_ALLOWANCE_M` (a short, named, configurable allowance;
> propose a value and justify it).  Where the connector cannot reach
> the apron mouth within that bound, the deficit surfaces on the
> AIRSIDE side (connector/apron mouth) as an over-cap or break, and is
> never resolved by lifting groundside.

★ **Mouth-relax interaction:** the verify-and-relax pass
(`solve.py:1443-1505`) frees conflicted mouth clusters and has the lot
adopt the projected mouth profile.  A DEM-bounded pin's adopted profile
must be bounded the same way, or the lift returns through that door.

### C.3 Expected effect and new-defect watch

Correcting the value is measured BEFORE any demotion-to-soft (the sag
investigation's alternative): at the top witness pair a `gs_pin` at
105.59 drives a 16.63 m deficit of which ~8 m is float.
★ Honest pins will mint over-cap connector chords and mouth steps
wherever the apron is still wrong until B lands — C's acceptance must
therefore include a mouth-step / connector-grade gate and
`test_single_graph_acceptance` 4/4, not just the global flat-fixture
gate.

---

## Part D — stop the quarantine blend from bending strung corridors

### D.1 ★ Correction to revision 1

Revision 1 said "register the rod before the spine-yield projection".
**That is already true** (`solve.py:990-1140`, phase-A pieces from
:868) and is therefore a no-op; the associated claim that 4,839 links
were law-clamped *because* the snapshot follows the bend is
**unsupported** — registration precedes the bend.  Re-attribute that
clamp count (suspect the Δ-vs-symmetric-pair-budget clamp,
`solve.py:1022-1058`, the CYXY 6.03 % class) and report.

### D.2 The actual fix

1. **Chain-rigid blend.**  In `one_solve.py`'s broken branch
   (:1497-1560, today a pointwise blend followed by a per-node
   hard-neighbour clamp at :1546-1551), treat a rod chain as rigid:
   compute the blend per chain and apply the chain's Δ shape.  A rod is
   a *difference* constraint, so it is always satisfiable inside a
   break region at zero cost in level.
   ★ **Preserve the per-node hard-neighbour clamp for chain
   ENDPOINTS** — that clamp is the 05C runway-kink guard.
2. **Corridor `z_ref` from the rod string.**  The §7 snapshot at
   `solve.py:1293-1296` captures raw `elev` at fp#8 entry, i.e. after
   the blend.  Derive non-service corridor `z_ref` from the rod-implied
   string instead.  Retain the yield-entry snapshot for **service**
   corridors (the CYXY 8.95 % mint reason).
   Note: (1) alone may suffice — an unbent profile makes the :1293
   snapshot harmless.  Measure (1) first and only add (2) if needed.

---

## Sequencing

Part A is independent (scheduler files only) and may run in parallel.
Solver order is **C → D → B**, each measured before the next: honest
floors (C) shrink the quarantine that D and B are measured against, and
B's hill acceptance depends on C having removed the false lift.
★ B/D disjointness must be asserted, not assumed: R's free set
(non-anchor apron nodes) and D's chain set (strung spine nodes) are
disjoint precisely because spine crossings are R-anchors.
★ If R's anchors are sampled before the spine settles, R must be
rebuilt from rod-held values rather than a stale absolute snapshot.

## Acceptance

Global (every part): no regression of the burial recovery (HECA seam
site in the 106-109 class), the pad-face welds (building199 ≤ 0.2 m),
or the flat fixtures (CYXY/SPJC/SPLP step and tear sections at ZERO).
Measure the EMITTED patch with the law-true frame.
★ Every part is default-ON behind a named env gate
(`O4_APRON_STRING`, `O4_GS_PIN_DEM_BOUND`, `O4_CHAIN_RIGID_BLEND`,
scheduler equivalents) with **gate-off byte-identity proven by
sha256** on at least one fixture.
★ **Build-time impact statement is mandatory** (CLAUDE.md hard law:
≥ 0.6 s/airport or ≥ 3 s/tile triggers an optimisation-agent review);
run `tools/check_build_time.py --runs N`, never a single-run comparison.

* **A**: with N cached tiles, concurrently CPU-active workers ≈
  min(N, cores) by sampling (not wall time); ≤ 4 tiles admitted per
  fetch class; memory projection never exceeds 80 % of available;
  emitted artefacts unchanged (orchestrator command equality accepted).
* **B**: the owner's hill site (30.1271204, 31.3966423) emits within
  **0.3 m of R**, and its former +3.54 m peak above the
  A(30.1253525,31.3942243)→B(30.1282119,31.3981184) chord is
  eliminated (≤ chord + 0.3 m); no apron node exceeds its lateral 1 % /
  longitudinal 1.5 % against R; report HECA within-shape and step
  counts, and the B.6 mega-component feasibility verdict.
* **C**: no `gs_pin` exceeds its DEM bound; broken-node count
  before/after; the hill site's supporting anchors re-measured; mouth
  and connector gates green; `test_single_graph_acceptance` 4/4.
* **D**: corridor sag ≤ 0.5 m with ★ **absolute level unchanged at
  named stations** (sag alone is translation-invariant); rod slab
  violations ~0; `test_spine_taut_string_heca` green on merit;
  ★ explicit CYXY service-mint guard (the 8.95 % class).

## Constraints

Main tree `/Users/noah/XPTerrainBuilder/Ortho4XP`, `venv/bin/python`
from that cwd; `git log --oneline -1 && git status --short` before AND
after every measurement (other sessions commit omnibus sweeps); never
commit/stash/revert; no KCLT builds (OOM); one airport build per
process; output to files, never pipes; PID/artifact-verified waits with
timeout arms; measure the EMITTED patch, never the pre-yield dump;
counts are evidence, wall times are contention-noise.
STATUS/memory documentation stays with the parent session.
