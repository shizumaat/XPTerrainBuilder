# Per-cluster object seating + terrain-side building pads (Fable design, 2026-07-26)

**STATUS: DRAFT FOR OWNER REVIEW — no code has been written against this
document.  Every constant, law and phase below is proposed, not landed.**

**Reads with:** `docs/dsf_object_integration_spec.md` (the OBJ8
reader / partition / y-bake machinery this extends, and the invariant
register this amends), `docs/obj8_structure_partition.md` (the contact-graph
theory), `docs/object_terrain_features_spec.md` (the terrain-feature emission
idioms and rulings R1/R2/R8 the pad system reuses), and
`docs/adjacent_ground_grade_law_plan.md` (the envelope + weld machinery the
pad blend borrows).

ORIGIN (owner session 2026-07-26, HECA "a ton of floating objects"): the
per-STRUCTURE rigid seat — one vertical offset per connected component of
the contact graph — is the right physics for a building and the wrong
physics for what heavy payware packs actually ship.  All three measured
heavy packs (KCLT, KBNA, HECA) weld their terminal complex into ONE
km-scale mega-structure carrying 96–100 % of their elevated objects as
supporter-inheritors.  At KCLT/KBNA that is harmless: the ground under the
mega-structure is flat (ground-contact relief 0.022 m / 0.005 m), so one
offset seats everything.  At HECA the same topology sits on **26.86 m** of
ground-contact relief — and that relief is REAL (owner ruling 3 below):
~85 m across the airport, DEM and CIFP agreeing.  One rigid body cannot
seat three zones (T23 high ≈ 93.7–99.5 m, the people-mover bridge, Private
Hall low ≈ 72.6–81.5 m); the rigid-seat span gate rightly refuses it; and
with the supporter-fate rule the refusal correctly cascades to everything
the mega-structure supports.  Correct, and useless: the terminal complex of
a real airport on real relief ends up entirely at authored elevations.

The fix is to stop pretending the mega-structure is one rigid body.  It is
many rigid bodies — CLUSTERS — joined at contact edges where the ground
happens to step.  This spec defines (1) how clusters are formed (a
T-tolerance cut on the contact graph), (2) the per-cluster rigid seat and
inheritance, (3) the tear law that replaces invariant I-20, and (4) the
terrain-side building-pad system (owner ruling 2) that absorbs the residual
a rigid seat cannot, welded to pavement and blended to DEM.

## 0. Rulings in force (owner, 2026-07-26 unless noted)

Decided; do not relitigate.  If implementation proves one wrong, stop and
escalate.

**R1 — Per-cluster seating.** "Probably need the per cluster seating."
The per-structure rigid seat is refined to per-cluster; the structure
partition itself (pooling, welding, ε-contact) is unchanged.

**R2 — Terrain-side building pads.** Verbatim: "Some sort of compromise is
correct, but we have to be sure we don't create building pads that are then
giant cliffs in relation to the graded pavement.  They want to generally be
as close as feasible to DEM, then some adjustment to terrain is acceptable,
but particularly for buildings adjacent to airside pavement they must not
deform the graded pavement."  Formalised as the PAD LAW in §5.

**R3 — HECA relief is real.** HECA is NOT flat — ~85 m of relief across
the airport is real (DEM + CIFP agree).  The seating problem is real
structures on real relief, never a data defect.  No "flatten HECA" escape
hatch exists; the design must seat buildings ON the relief.

**R4 — Weld ruling class (user, 2026-07-09, carried).** Emitted terrain
strips weld fully to pavement; deliberate divergence only via node-split
walls; pavement value always wins at any contact; no standoff grooves.
Pads are members of this class.

**R5 — One-solve doctrine (user, 2026-07-09, carried).** Laws live in
`grade_law.py`, emitter and validator import the same function; minimise
post-solve mutation; solver performance is first-class.

**R6 — Assumed-landed prerequisites (in flight this session; this spec
builds ON them, not around them).**
* Supporter-fate: inheritors share their supporter's outcome
  (`DSF_OBJECT_SUPPORTER_FATE`, `object_anchor.structure_deltas` pass 3).
* Defect B fix: inheritance picks the SMALLEST containing supporter, not
  the first in list order.
* Defect A fix: the whole-structure span gate is replaced/augmented by a
  robust median-seat-vs-authored A3 test (EGGW A/B pending).
If any of these does not land, the affected sections (§4.3, §4.4) must be
re-based before implementation.

**R7 — HARD LAW (build time, owner 2026-07-18, canonical text in repo-root
`CLAUDE.md`).** Per-airport auto-patch wall ≤ 60 s cold; any new code
costing ≥ 0.6 s must pass a Fable-class optimization review.  §7.5 is this
spec's budget statement.

## 1. Measured foundation (2026-07-26 session; cite, don't re-derive)

All numbers from the session's diagnosis scripts (`perpart*.py`,
`bands.py`, `supporter.py`, scratchpad JSON dumps) against production
packs and the built `+30+031` mesh.

* **Mega-structure topology is universal in heavy packs.** KCLT / KBNA /
  HECA each weld the terminal complex into one km-scale structure carrying
  96–100 % of elevated objects as supporter-inheritors.  The
  DISCRIMINATOR between harmless and catastrophic is ground-contact
  relief under the structure: 0.022 m (KCLT) / 0.005 m (KBNA) /
  **26.86 m** (HECA).
* **HECA structure 0:** 16,868 welded parts, 1,823 ground-contact parts,
  in three zones: T23 high (~93.7–99.5 m), the people-mover bridge, and
  Private Hall low (~72.6–81.5 m).  The two natural sub-complexes alone
  span 5.8 m / 8.9 m of ground relief — **no rigid-body seat exists under
  the 3.0 m limit** (`DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M`) even after a
  perfect zone cut.  Per-cluster seating alone is therefore NOT
  sufficient; §5's pads are load-bearing, not cosmetic.
* **Contact-edge seat analysis** (HECA structure 0: 21,366 contacting part
  pairs, 1,634 ground↔ground): per-edge seat difference |Δseat|
  p50 0.006 / p90 0.258 / p99 1.60 / max 4.13 m.  Cut tolerance T = 0.05 m
  would cut 38 % of ground↔ground edges (shredding the structure);
  **T = 0.5 m cuts 3.6 %** — only the genuine relief transitions.
  1,289 contacts have exactly one elevated end — the population §4.2's
  cluster-inheritance rules exist for.
* **Elevation-only banding is rejected on measurement** (`bands.py`):
  bucketing ground parts by elevation bands produces NON-COMPACT,
  spatially interleaved bands — parts of one building land in different
  bands and parts of distant buildings share one.  Clustering must follow
  the CONTACT GRAPH (physical adjacency), with elevation only deciding
  which edges to cut.  This is a design constraint, not an option.
* **Cost substrate:** the partition already builds the pool frame, welds
  parts, computes the ε-contact graph, and (pass 3 of `structure_deltas`)
  samples ground under every ground part's centroid.  Cluster formation
  is a re-read of data the pipeline already pays for (§7.5).

## 2. The model

Today (invariant I-6): structure = connected component of the ε-contact
graph; one rigid seat per structure; I-20 forbids tearing ("merge on
doubt").  I-20 was written when over-merging cost centimetres — true on
flat ground, false by 26.86 m at HECA.  On real relief, refusing to tear
IS the tear: the whole complex stays at authored y, floating over and
sinking into the terrain by tens of metres.

The replacement model, in one paragraph.  The structure partition is
unchanged — a structure remains the unit of pooling, discovery, refusal
accounting and provenance.  WITHIN a structure whose ground-contact relief
demands it, the ground↔ground contact edges are re-examined: an edge whose
two ends want seats more than T apart is CUT; the connected components of
what remains are the structure's CLUSTERS.  Each cluster gets its own
rigid seat (the median law, §4.1).  Elevated parts and elevated structures
inherit per cluster (§4.2).  Every kept edge is exactly rigid (identical
offset at both ends); every cut edge is a bounded, measured, audited seam
that exists only where the ground itself steps (§4.5, the tear law).  The
residual a rigid cluster seat still cannot close — intra-cluster relief up
to the cluster span — is handed to the terrain side as building pads (§5),
which raise or lower open terrain to meet the seated building, weld to
graded pavement (pavement wins absolutely), and blend to DEM under the
adjacent-ground-style envelope.

Degeneracy guarantee: on a pack whose ground is flat at the T scale
(KCLT, KBNA — relief ≤ 0.022 m « T), **zero edges are cut, every
structure has exactly one cluster, and the entire machinery reduces
byte-for-byte to today's behaviour.**  This is the primary regression
gate (§7.3).

## 3. Cluster formation

### 3.1 Inputs (reuse, never re-derive)

Cluster formation runs inside `object_anchor.structure_deltas`, per
structure, AFTER pass 1 (grounds) and BEFORE the seat/refusal arithmetic
of pass 3.  Its inputs already exist there:

* the structure's welded parts (`obj8_partition.weld_parts` — pass 3
  already re-welds per structure; welding is intra-part, so this exactly
  reproduces the partition's parts);
* the ε-contact edges AMONG those parts.  `partition_structures` computes
  these once (`obj8_partition.contact_graph`) and today throws them away;
  the implementation must THREAD them through (carried on a new optional
  `Structure` field or a parallel return, populated only for structures
  that enter clustering) rather than recomputing the narrow phase.
  Recomputing is the fallback, not the design (§7.5).
* per-ground-part ground samples (`ground_part_records`: pass 3 already
  samples `ground_under(part centroid)` for every part whose base y is at
  or below `DSF_OBJECT_ELEVATED_BASE_M`).

### 3.2 The cut (the only new geometry decision)

For each contact edge (i, j) where BOTH parts are ground-contact parts
with valid ground samples, define the per-end SEAT TARGET exactly as the
foot machinery does: `seat(p) = ground_under(p) − base_y(p)` — the world
elevation of the object's y = 0 plane that lands that part exactly on the
mesh.  Then:

    CUT (i, j)  ⇔  |seat(i) − seat(j)| > DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M

Everything else keeps its edge:

* ground↔ground edges with |Δseat| ≤ T — kept (rigid);
* any edge with an elevated end — **never cut here** (elevated parts
  cannot vote; they are assigned in §4.2, where the bridge rule prevents
  them from re-merging cut clusters);
* edges where either ground sample fell outside the mesh — kept (merge on
  doubt survives for UNMEASURED ground; only MEASURED divergence cuts).

CLUSTERS = connected components (union-find, deterministic order: parts
in shared-index order, edges in the partition's edge order) of the
ground-part subgraph after the cut.

Why seat difference and not raw ground difference: two adjacent parts
authored at different base y (a step in the building) on stepped ground
may want the SAME rigid offset — cutting them would tear a correctly
assembled facade.  Seat targets compare what each end actually wants,
which is the quantity the rigid body must reconcile.  (For co-planar
bases the two tests coincide; the measured distribution above was taken
on seat targets.)

### 3.3 The tolerance T (config constant; recommendation 0.5 m)

    DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M   default 0.5   (0 disables clustering)

From the measured distribution (§1): p90 = 0.258 m — everyday modelling
noise plus DEM texture, which must NOT cut (T well above it); p99 = 1.60 m
and max 4.13 m — the genuine zone transitions, which must cut (T well
below).  T = 0.5 m cuts 3.6 % of ground↔ground edges, exactly the relief
transitions; T = 0.05 m cuts 38 % (shredding); T = 0.3 m is defensible but
sits closer to the noise shoulder (between p90 and p99, cutting edges that
plain apron undulation can produce under a 30 m DEM).  0.5 m is also the
scale of a single stair riser + margin: a seam the pad system (§5) or a
human eye tolerates at a facade base.  Recommendation: **0.5**, config
constant, revisit only with a new measured distribution from another
relief-class pack.

Guards on T's value (asserted in config, mirroring the OLS constants
style): T must exceed the DSF elevation-pool quantum (~centimetres,
amendment A7) and the contact ε (0.25 m) — a tolerance below the
modelling gap it partitions across would be self-inconsistent.

### 3.4 Minimum cluster size and degenerate handling

There is NO minimum cluster size.  A one-part cluster is a legitimate
rigid body (a shed on its own knoll) and seats by the same law.  What
would motivate a minimum — fear of shredding — is handled at the cause
(T is above the noise shoulder) and audited at the effect (§4.5 flags any
cut edge whose measured ground step does not justify it).  Degenerate
cases:

* Structure with NO ground-contact parts: no clustering; the whole
  structure remains one inheritance unit (§4.2, "elevated structures").
* Structure whose every ground↔ground edge is kept: one cluster ==
  the structure; identical arithmetic to today by construction.
* Foot-anchored structures (`DSF_OBJECT_FOOT_ANCHOR`, the KBNA gantry
  machinery): **exempt from clustering entirely.**  Their ground records
  are their FEET, their seat is the per-foot midpoint law, their residual
  path is the existing `FootPadRequest`.  The two mechanisms answer the
  same question at different scales and must not stack; a structure is
  routed to exactly one of {foot-anchored, clustered} — foot-anchoring
  wins, because it is only ever assigned to elevated-classified
  structures with author-baked offsets, which clustering (a ground-part
  mechanism) cannot serve.  KBNA byte-stability (§7.3) checks this.
* A cluster all of whose parts borrowed the structure-centroid ground
  (every part centroid off-mesh): seats by that borrowed ground, exactly
  as today — and cannot have been cut from its neighbours (kept-on-doubt).

### 3.5 Determinism and idempotence

Clustering must add nothing to the existing idempotence story; it slots
into invariants I-14/I-15/I-16 as follows.

* **Pure function of fingerprinted inputs.**  Clusters are derived from
  (a) authored geometry — always re-read from the `.anchor_bak` originals
  (I-15), so a baked pack presents identical authored space; (b) the
  built mesh; (c) the gates.  All three are already fingerprinted by the
  provenance run record (`object_rebake.build_run_record`: mesh
  signature, per-resource file hashes, `_gate_digest`).  **T and the
  clustering gate join `_gate_digest`** so flipping either forces a full
  re-derive instead of a stale short-circuit.
* **Deterministic construction.**  Union-find over deterministically
  ordered parts/edges (§3.2); cluster ids are assigned in order of each
  cluster's lowest member part index; iteration over clusters is by id.
  No hash-order iteration anywhere (same discipline the pool/structure
  code already follows).
* **Byte-idempotent re-run.**  Same inputs → same clusters → same
  per-vertex deltas → the y-token rewriter (I-16) produces identical
  bytes and skips the write (I-15).  Re-running on an already-baked pack
  is stable because geometry comes from the backup, never the live file.
* **Reversion.**  Unchanged: a resource excluded from a later decision is
  reverted from its backup.  Clusters change WHICH deltas vertices get,
  not the delta plumbing, so the reversion pass needs no changes.
* **Provenance surface.**  The run record gains `clusters_baked`,
  `clusters_refused`, `cut_edges` counts (reporting only — the
  fingerprint match logic is untouched).  The per-pack provenance sidecar
  (`.o4_reanchor_provenance.json`) remains the single source the
  short-circuit reads.

## 4. Per-cluster seat

### 4.1 The seat (the A19 statistic, per cluster)

Amendment A19 chose the MEDIAN of ground-part grounds as a structure's
seat — the robust best single rigid offset.  That statistic is kept and
applied per cluster:

    cluster_ground(C) = median( ground_under(p) for ground parts p ∈ C )

(exactly the A19 median code path, fed the cluster's parts instead of the
structure's).  Per-vertex deltas keep invariant I-3 verbatim at cluster
granularity: for resource O contributing parts to cluster C,

    delta(C, O) = cluster_ground(C) − anchor_ground(O)

applied to the vertices of C's parts.  **The `RebakeDecision` shape does
not change**: `delta_by_resource_and_vertex` already maps individual
vertices to offsets, so one resource carrying several clusters simply
carries several delta values across its vertex map — the rebake writer,
the reversion pass, the I-16 rewriter and the I-21 output check are all
already vertex-granular and need zero changes.  (Positional commands and
per-`ANIM`-block reconciliation, I-10/I-11, already resolve by nearest
structure / containing structure; they re-target "nearest cluster" with
the same code shape.)

The median is also the "as close as feasible to DEM" statistic of owner
ruling R2: it minimises the total L1 terrain adjustment the pad system
must then make — the seat does the rigid share of the work, pads do the
residue, and no other single offset leaves less residue overall.

Pavement-adjacency refinement (ruling R2's sharp edge): if any of the
cluster's ground parts are PAVEMENT-ADJACENT — their contact points lie
within `DSF_OBJECT_PAD_PAVEMENT_ADJACENCY_M` (proposed default 2 m, the
weld-reach scale) of the graded pavement union — the median is taken over
the pavement-adjacent parts only:

    cluster_ground(C) = median( ground_under(p) for pavement-adjacent ground parts p ∈ C )

Rationale: pavement is graded, authoritative and IMMOVABLE (R4); a
building whose doors face the apron must meet the apron exactly, and any
mismatch must be pushed to the open sides where pads may lawfully absorb
it.  A cluster with no pavement-adjacent parts uses the plain median.

### 4.2 Inheritance — the supporter graph now points at clusters

Elevated geometry attaches at two scales; both re-target clusters.

**(a) Elevated parts WITHIN a clustered structure** (the 1,289 measured
one-elevated-end contacts).  After the ground clusters are fixed, take
the connected components of the ELEVATED-only part subgraph ("elevated
components"), using all kept-and-cut-exempt edges among elevated parts.
For each elevated component E, collect the set of clusters it touches via
elevated↔ground contact edges:

* touches exactly one cluster C → E joins C: same offset, same fate.
  (This is rooftop clutter, canopies, upper floors — the overwhelmingly
  common case.)
* touches zero clusters → E has no ground path inside its structure; it
  falls through to rule (b) as if it were an elevated structure.
* touches two or more clusters → E is a **BRIDGE** (HECA's people-mover
  is the type specimen).  A rigid bridge across a cut cannot follow both
  plateaus.  E joins the cluster with which it shares the most
  elevated↔ground contact edges (tie → the larger contact area; then the
  lower cluster id).  Every contact it keeps toward the OTHER clusters
  becomes an audited **bridge-class seam** (§4.5): magnitude =
  |cluster_ground(chosen) − cluster_ground(other)|, reported, never
  silently absorbed.  A bridge seam is not bounded by T — it is bounded
  by the real relief the bridge really spans, which is exactly what a
  bridge is for.  (Whether specific bridge structures should instead be
  refused whole is open question Q2, §8.)

The critical property: elevated components ASSIGN to clusters, they never
MERGE clusters.  Ground truth flows upward only.

**(b) Elevated STRUCTURES (invariant I-8, re-based).**  A structure with
no ground-touching part inherits — today from a supporter STRUCTURE, now
from a supporter CLUSTER: the ground-touching cluster whose horizontal
bounding box (pool frame) contains the inheritor's centroid, smallest
containing box first (the Defect-B rule, applied to cluster boxes), else
nearest by centroid distance.  Supporter-fate carries over verbatim: a
refused cluster's inheritors are left at authored elevations with the
`SUPPORTER_FATE_SKIP_REASON_PHRASE` reason quoting the cluster's; the
pass-3 supporters-before-inheritors evaluation order now orders clusters
before their inheritors (same sort, cluster-granular key).

At HECA this is the payoff line: the 96–100 % of elevated objects that
today inherit "the mega-structure" (and its refusal) instead inherit the
specific terminal zone they hover over, each seated at its own plateau.

### 4.3 Refusal — a cluster can still be refused

Clustering removes the REASON most refusals fired, not the gates.  Both
surviving gates run per cluster:

* **Span gate (backstop, not workhorse).**  `ground span(C)` = max−min of
  ground under C's ground parts; a cluster over
  `DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M` (3.0 m) is not seated RIGIDLY-ONLY.
  Note the accumulation case: a chain of kept edges each ≤ T can climb
  without bound (a long building following a gentle slope), so the cut
  law alone cannot bound cluster span and this gate must survive.  What
  changes is the OUTCOME: where today's structure-level gate refuses
  outright, a span-gated cluster is **seated at its median AND issued pad
  requests** for its out-of-tolerance ground parts (§5.3) — bake-and-pad,
  the A3/A19 philosophy extended.  Refusal-outright remains only when
  the required pad relief exceeds the pad cap or the pad is inadmissible
  (§5.4), recorded in `skip_reason` with the measured numbers.  HECA's
  natural sub-complexes (5.8 / 8.9 m span) land exactly here: seated at
  their zone median, padded at their sloping ends.
* **Robust A3 (Defect-A form).**  The median-seat-vs-authored comparison
  (corrected vs uncorrected residuals, with the
  `A3_GUARD_MAXIMUM_DIAMETER_METRES` guard) runs per cluster.  Cluster
  diameters are building-scale again, so the diameter guard regains the
  meaning A19 took from it at mega-structure scale.  A cluster whose
  correction would worsen seating stays unbaked, and (supporter-fate) so
  do its inheritors.

`needs_pad` becomes a per-cluster flag with the same
`DSF_OBJECT_PAD_FLAG_SPAN_M` (2 m) threshold, and the per-airport summary
counts clusters.

### 4.4 Interaction with feet and multi-foot

None, by construction (§3.4): foot-anchored structures bypass clustering,
clustered structures bypass foot detection.  The two residual paths
converge downstream: `FootPadRequest` (per foot) and the new
`ClusterPadRequest` (per out-of-tolerance ground part group, §5.3) are
siblings in the same sidecar and the same pad emitter, differing only in
how their contact rings were derived.

### 4.5 The tear law — invariant I-20′ and the tear audit

Invariant I-20 ("a contact pair that cannot be proved absent keeps its
edge; merge on doubt; tearing is unrecoverable") is REPLACED by:

> **I-20′ — bounded, justified tearing.**  A contact edge may be cut only
> when the MEASURED ground under its two ends differs by more than
> `DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M`; a pair whose contact — or whose
> ground — cannot be measured keeps its edge (merge on doubt survives
> for unmeasured pairs).  Every KEPT edge's two ends receive one
> identical offset.  Every CUT edge is recorded and audited: its
> rendered seam must be explained by the ground step under it.

Three audited quantities, one reader (`verification.check_object_seating`,
a findings-producing reader in the house style — every finding is a bug,
never chatter):

1. **Kept-edge rigidity** (exact): for every kept edge, both ends carry
   the same cluster, hence the same offset; verified from the OUTPUT à la
   I-21 (rendered elevations of formerly-coincident/contacting vertices),
   tolerance = the DSF elevation-pool quantum (amendment A7).  Finding
   otherwise.
2. **Cut justification**: for every cut edge, the recorded ground step
   `g(e) = |seat(i) − seat(j)|` measured at decision time must exceed T.
   Finding otherwise (an unjustified tear is a bug in the cut law).
3. **Seam accounting**: for every cut edge, the rendered seam is
   `seam(e) = |cluster_ground(A) − cluster_ground(B)|`, and the
   UNEXPLAINED component is `u(e) = |seam(e) − g(e)|` — the part of the
   displacement the local ground step does not account for.  By
   construction `u(e) ≤ dev_A(i) + dev_B(j)` where `dev` is each end
   part's deviation from its own cluster median, each bounded by half
   that cluster's span gate.  The reader flags `u(e) >
   DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M + solver quantum` as a finding and
   reports the full seam distribution (count, p50/p90/max, per class:
   ground-cut vs bridge).  **Honesty note (deliberate correction to the
   commissioning brief):** the raw seam at a cut edge is NOT bounded by
   T — it is bounded by the real relief (a 20 m plateau step yields a
   20 m seam, each side correctly seated on its own ground).  The
   T-bounded guarantee attaches to the UNEXPLAINED seam `u(e)`; asserting
   `seam(e) ≤ T` would mint a finding against every lawful plateau cut.
   Bridge-class seams (§4.2a) are reported in their own class and are
   exempt from the `u(e)` bound only in that their `g(e)` is taken
   between the two CLUSTER grounds rather than the edge's own ends.

The audit's inputs (cut list with per-edge `g(e)`, cluster assignment,
cluster grounds) are recorded in the provenance run record so the reader
never re-derives geometry — same pattern as the foot-cluster audit trail
on `RebakeDecision`.

## 5. Terrain-side building pads (owner ruling R2)

### 5.1 THE PAD LAW (single source, `grade_law.py`; stated precisely)

For a pad serving cluster C (or foot F) with rendered base elevation
`b = cluster_ground(C) + base_y(part)` (resp. the foot's
`target_ground_metres`):

1. **Target.**  The pad surface under the contact ring is `b` — terrain
   meets the building base exactly (no float, no sink).  The pad's
   deviation from DEM, `|b − DEM|`, is capped by
   `DSF_OBJECT_PAD_MAX_RELIEF_M` (proposed default 3.0 m, inheriting the
   rigid-seat limit's scale): "as close as feasible to DEM, then some
   adjustment to terrain is acceptable."  A pad needing more relief than
   the cap is refused → the requesting cluster's part keeps its residual
   and the refusal is a finding (§5.5).  Pads may RAISE or LOWER terrain
   (a cut bench is a pad; direction default-symmetric, open question Q4).
2. **Pavement wins absolutely.**  The pad polygon is CLIPPED against the
   graded pavement union before emission; a pad never contributes, moves,
   or re-values any pavement vertex.  Zero pavement deformation is an
   acceptance criterion (§7.4), verified byte-level on the pavement
   shapes.
3. **Weld at airside contact (R4, the 2026-07-09 weld class).**  Where
   the (clipped) pad boundary runs along a pavement edge, the pad's
   boundary row lies ON the pavement ring (d = 0, shared coordinates) and
   ADOPTS the pavement's solved values — a weld, no cliff, no standoff
   groove.  Between the welded pavement edge and the pad's interior
   target `b`, the surface transitions inside the pad at a lawful grade
   (≤ the groundside 4 % cap over the available run; where the run is too
   short the pad target is PULLED toward the pavement value — pavement
   wins over the building base too, and the shortfall re-appears as a
   residual finding rather than a cliff at the apron).
4. **Open-side blend.**  On sides not touching pavement, the pad blends
   from `b` to DEM under the adjacent-ground-style envelope
   (`grade_law.adjacent_ground_envelope` conventions: signed offsets from
   the pad edge anchor, cut/fill caps by distance) across a margin ring
   grown from the contact hull (`DSF_OBJECT_FOOT_PAD_MARGIN_M`-class
   margin, per-request).
5. **Lockstep.**  The law functions (pad target, pull-toward-pavement,
   blend envelope) are pure `grade_law` scalars imported by BOTH the
   emitter and the validator (R5), like the skirt and OLS laws.

### 5.2 Consuming `FootPadRequest` — the existing sidecar gets its consumer

`Patches/<tile>/o4_object_foot_pads.json`
(`post_mesh.OBJECT_FOOT_PAD_SIDECAR_FILENAME`, version 1) already carries,
per foot: structure index, resource, lat/lon, `base_y`,
`residual_metres`, `target_ground_metres`, `contact_points_lonlat`; it is
refreshed after every rebake, removed when empty, and duplicated into the
provenance run record (`run_record_foot_pad_requests`).  The ring builder
(`object_footprints.foot_pad_ring`: convex hull of contacts, dilated by
`DSF_OBJECT_FOOT_PAD_MARGIN_M` = 2 m) exists and is tested.  The consumer
does not exist — this section specifies it.

**Timing (the one structural decision).**  Requests are computed
POST-MESH (they sample the built mesh) but terrain features are consumed
PRE-MESH (layout → OSM patch → mesh build).  Ruled design: the
**next-build convergence loop**.  Build N's rebake writes the sidecar;
build N+1's auto-patch phase reads it (it already lives in the tile's
patch directory, exactly where auto-patch features load), emits the pads,
and the post-mesh rebake then re-measures: with terrain now meeting the
feet, residuals fall under `DSF_OBJECT_FOOT_PAD_RESIDUAL_M` and the
requests VANISH — the sidecar empties, and build N+2 is a fixed point.
To keep already-emitted pads stable once their requests vanish, the
consumer persists what it emitted: an `emitted` section is added to the
sidecar (version 2) recording each pad's ring + target + the fingerprint
of the cluster seat that produced it; a pad is re-emitted from the record
until its fingerprint goes stale (mesh/DSF/gate change), at which point
it is dropped and the loop re-converges.  An in-run re-mesh (emit pads
and rebuild the mesh inside one build) is REJECTED for this iteration:
it doubles the most expensive pipeline stage against the HARD LAW budget
(re-meshing alone is minutes-scale) for a convergence the two-build loop
already delivers.  (Owner may revisit: open question Q5.)

### 5.3 `ClusterPadRequest` (new, sibling of `FootPadRequest`)

Emitted by pass 3 for every baked cluster, per maximal connected group of
ground parts whose post-seat residual `|cluster_ground + base_y(p) −
ground_under(p)|` exceeds `DSF_OBJECT_FOOT_PAD_RESIDUAL_M` (0.75 m —
shared constant, one seating tolerance for both mechanisms).  Fields
mirror `FootPadRequest` (the sidecar schema gains a `kind:
"foot"|"cluster"` tag plus `cluster_id`); the ring is the hull of the
group's contact points, same builder, same margin.  Grouping connected
residual parts (rather than one request per part) keeps HECA's sloping
terminal ends as a handful of coherent pads instead of hundreds of
confetti rings.

### 5.4 Emission: role, admission, decimation, weld tiers

* **Role.**  Pads emit as terrain shapes with a new role `object_pad` in
  `ROLE_GRADE_LIMITS` (limit `None`, like `boundary` — the pad's grade is
  law-derived, not solver-capped).  They are POST-SOLVE EMISSION, the
  skirt/adjacent-ground idiom (R5: the solver's one profile is not
  re-opened; pads are off-pavement terrain whose values are pure law).
  They therefore need no solver admission at all — only clip + weld
  against the already-solved pavement and features.
* **Precedence.**  Pavement > existing terrain features (skirt, bands,
  OLS cuts) > pads > raw DEM.  A pad is clipped by everything above it
  and welds (adopts values) at every contact with it, per the
  weld-value-preload idiom in `adjacent_ground.py`.
* **Decimation/weld tiers.**  Pad rings are already minimal (hull +
  margin, `quad_segs=2`); they enter `emit_decimate` at the same tier as
  adjacent-ground bands (chord-capped, weld rows pinned — boundary rows
  shared with pavement are never decimated, interior nodes are fair
  game).  No new tier machinery.
* **Ordering within a build.**  Pads emit AFTER adjacent-ground bands and
  OLS (they must weld to final feature values), i.e. last in the terrain
  block, before tile cut.

### 5.5 Validator reader

`verification.check_object_pads(layout, dem, sidecar)` — findings
producing, law-lockstep:

* pad interior value == law target (pull-toward-pavement included) within
  solver quantum;
* every pad↔pavement shared-boundary vertex carries the pavement's value
  exactly (weld; a mismatch is a groove/cliff finding);
* pavement shapes byte-identical to the pad-free emission (zero
  deformation — the R2 hard clause);
* open-side boundary within the envelope of DEM;
* every refused pad (over-cap relief, inadmissible clip) surfaced as a
  finding carrying the measured numbers;
* every `emitted` sidecar record either re-emitted or expired-with-reason
  (no silent pad loss).

### 5.6 Pads vs seat — the decision rule (decisive)

Does the pad system replace part of per-cluster seating for
ground-adjacent buildings?  **No — the two are complementary by an exact
decomposition, and neither can do the other's job:**

* The SEAT handles the RIGID component of the misfit: the single offset
  (median; pavement-constrained median when the cluster touches apron)
  that moves the whole cluster.  Moving the building is free (a y-token
  rewrite), so the rigid share is always taken there first.
* PADS handle only the NON-RIGID residue: per-part residuals after the
  seat, capped at `DSF_OBJECT_PAD_MAX_RELIEF_M`.  Terrain adjustment has
  real costs (mesh area, visual plausibility, interaction with every
  neighbouring feature), so it gets only what no rigid motion can remove.

The rule, operationally: **seat first (rigid, pavement-constrained), pad
the residual, refuse what neither can lawfully absorb.**  "Move the
building down vs pad the terrain up" is therefore never a per-building
choice: the median seat IS "move the building" (down or up) exactly as
far as helps all its parts at once; a pad IS "move the terrain" exactly
where one part still disagrees.  The only precedence decision is at
pavement: there the seat is constrained (building meets apron) and the
pad is forbidden (pavement never deforms), so residuals migrate to open
sides by construction.

What pads DO replace is the span-gate REFUSAL (§4.3): bake-and-pad
supersedes refuse-outright for clusters whose residuals are pad-coverable.
I-19's "refused and reported as needing a pad — never split" ages into:
clusters ARE the lawful split (I-20′), and "needing a pad" is now an
actionable request, not a flag.

## 6. Config constants (proposed; values are the reviewable part)

    DSF_OBJECT_CLUSTER_SEATING              default 1 after gates (§7), env-gated O4_*
    DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M     0.5    (§3.3; the T)
    DSF_OBJECT_PAD_MAX_RELIEF_M             3.0    (§5.1; |pad − DEM| cap)
    DSF_OBJECT_PAD_PAVEMENT_ADJACENCY_M     2.0    (§4.1; pavement-constrained-median trigger)
    DSF_OBJECT_OBJECT_PADS                  default 0 until owner in-sim verdict (§7)
    (shared, existing)  DSF_OBJECT_FOOT_PAD_RESIDUAL_M 0.75 · DSF_OBJECT_FOOT_PAD_MARGIN_M 2
                        DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M 3.0 · DSF_OBJECT_PAD_FLAG_SPAN_M 2

## 7. Sequencing, gates, risk, budget

### 7.1 Build order: clusters first, pads second

Clusters are self-contained inside the post-mesh y-bake: no terrain
change, per-pack byte-level A/B, near-zero budget cost, and they fix the
dominant HECA failure (whole complex refused) on their own.  Pads depend
on cluster seats for their targets and touch the mesh loop (convergence,
weld/clip interactions with every feature) — strictly higher risk.
Sequencing pads first would also bake pads against the WRONG seats
(whole-structure medians), producing terrain that phase C then invalidates.

* **Phase C1 — clusters + seat + tear audit.**  §3, §4.1, §4.5.  Gate
  `DSF_OBJECT_CLUSTER_SEATING` default OFF.  Effort: ~2–3 agent-days
  (the arithmetic is a re-scoping of existing pass-3 code; the audit
  reader and provenance threading are the bulk).
* **Phase C2 — inheritance re-pointing + refusal.**  §4.2, §4.3
  (bake-and-pad outcome lands here but requests go to the sidecar
  unconsumed, exactly like feet today).  Effort: ~2 agent-days.
* **Phase P1 — pad consumer for the EXISTING foot sidecar.**  §5.2, §5.4,
  §5.5 on the foot-request population (KBNA class) — smallest real
  workload, proves the loop, the weld law and the validator.  Gate
  `DSF_OBJECT_OBJECT_PADS` default OFF.  Effort: ~3–4 agent-days.
* **Phase P2 — `ClusterPadRequest` + pavement-constrained seat.**  §4.1
  refinement, §5.3.  Effort: ~2 agent-days.
* Each phase lands only behind its gate with its A/B green; flags default
  ON only after the HECA in-sim verdict (owner).

### 7.2 Prerequisite gates (must be true before C1 merges)

Supporter-fate, Defect B (smallest-containing supporter) and Defect A
(robust A3) landed and green on their own A/Bs (R6).  If EGGW's Defect-A
A/B is still pending, C1 may proceed gated-off but must rebase before
default-on.

### 7.3 A/B protocol per airport class

* **KCLT / KBNA (flat-ground heavy packs): byte-stable required.**  With
  T = 0.5 » measured relief (0.022 / 0.005 m), zero edges cut, one
  cluster per structure — gate-on vs gate-off must be BYTE-IDENTICAL on
  the pack (allowing only provenance-sidecar count fields).  Any diff is
  a bug in the degeneracy guarantee.  KBNA additionally proves the
  foot/cluster routing exclusivity (§3.4).
* **EGGW (connector-split payware): strictly improve or byte-stable.**
  Structures already split by the connector machinery must not re-merge
  or re-fragment; the robust-A3 counts must not regress; floated-object
  count (the original EGGW defect metric) must be ≤ baseline.
* **HECA (relief class): acceptance criteria.**
  1. Every non-refused structure's ground parts within
     `DSF_OBJECT_FOOT_PAD_RESIDUAL_M` (0.75 m) of terrain — or covered by
     an emitted/requested pad (phase C: requested; phase P: emitted).
  2. Zero pavement deformation (pavement shapes byte-identical to the
     object-machinery-off emission).
  3. Every cut-edge seam ground-justified: `g(e) > T` for all cuts, and
     unexplained seam `u(e) ≤ T + quantum` (tear audit clean).
  4. Refused-cluster count → 0 for the terminal complex (the three zones
     each seat at their own plateau; bridge seams reported, counted, and
     eyeballed in-sim).
  5. Supporter-inheritor population follows its zone cluster (no
     inheritor left on the "mega refused" path).

### 7.4 Risks

* **Shredding on noisy DEM** (T too low for some pack/DEM pair): bounded
  by the audit (unjustified-cut findings) and by T being config; the
  measured distribution says 0.5 sits in a wide gap at HECA, but only one
  relief-class pack has been measured — treat the first non-HECA relief
  pack as a measurement task before trusting defaults.
* **Ramp accumulation** (long gentle-slope cluster over the span gate):
  handled by bake-and-pad; residual risk is pad-relief cap refusals on
  extreme slopes — surfaced as findings, never silent.
* **Bridge seams look wrong in-sim**: contained by the bridge-class audit
  + open question Q2 (owner can flip bridges to refuse-whole without
  re-architecture — it is one branch in §4.2a).
* **Pad convergence oscillation** (pad changes mesh → seat changes → pad
  target changes): damped by the fingerprinted `emitted` records (§5.2 —
  a pad re-emits stably until inputs change) and by targets being derived
  from cluster seats whose median is insensitive to the ≤ 0.75 m ground
  changes a correct pad makes.  The fixed-point argument must be
  regression-tested with a two-build harness (new test, phase P1).
* **Sidecar cache traps** (project memory: warm/cold inset cache, stale
  pavement sidecars): every A/B in this program quotes the
  STALE/read-log lines and uses `check_build_time --runs N`, per memory.

### 7.5 Build-time budget statement (HARD LAW, R7)

Phase C adds, per airport: (a) per-edge seat comparisons + union-find
over the measured contact graphs — HECA structure 0, the worst measured
case, is 16,868 parts / 21,366 edges → well under 50 ms in Python;
(b) ZERO new mesh samples (pass 3 already samples every ground part's
centroid); (c) contact-edge threading from `partition_structures` (design
requirement §3.1) so the narrow phase is NOT recomputed — recomputation
would be the one way this phase could breach 0.6 s, and it is designed
out.  Phase C total: **≪ 0.6 s (1 % of the 60 s budget) — no
optimization-agent review expected, measured confirmation required** via
`tools/check_build_time.py --runs N` at HECA and KCLT before merge.

Phase P adds: sidecar read + ring/clip/weld geometry per request
(dozens-to-hundreds of small hulls; shapely ops at this count are
sub-second) + the emitted pad vertices riding the existing decimation
budget.  Provisional estimate ≤ 0.5 s at HECA; if measurement shows
≥ 0.6 s, the phase goes to a Fable-class optimization review per the HARD
LAW before landing.  Whole-tile impact: pads emit only inside airport
patches; no whole-tile pass is added.

### 7.6 Invariant register amendments (for `dsf_object_integration_spec.md` §5)

* I-20 → I-20′ (§4.5 text) — owner sign-off required, this is the
  charter change.
* I-19 reworded: bake-and-pad supersedes refuse-and-flag where pads are
  admissible (§5.6); refusal survives only past the pad cap.
* I-6 note: structure remains the partition unit; CLUSTER added as the
  seating unit (new invariant: clusters partition a structure's ground
  parts; kept edges never cross clusters; elevated components never merge
  clusters).
* I-8 re-based to clusters, smallest-containing (Defect B) (§4.2b).
* New: pad system invariants — pavement never deformed by a pad;
  pad↔pavement contact is welded; every pad target within
  `DSF_OBJECT_PAD_MAX_RELIEF_M` of DEM (§5.1).

## 8. Open questions for the owner (only the genuinely undecidable)

* **Q1 — T default.**  0.5 m recommended from the measured HECA
  distribution (§3.3); 0.3 m is the tighter defensible alternative.
  Which default ships?
* **Q2 — Bridge policy.**  A rigid elevated component spanning two
  clusters (HECA people-mover): join-one-side with an audited plateau-
  scale seam at the far end (§4.2a, recommended), or refuse the bridge
  component whole (left at authored y, floating over both plateaus)?
  Both are one branch; the in-sim look should decide.
* **Q3 — Pad relief cap value.**  3.0 m proposed (rigid-seat-limit
  heritage).  Higher buys more HECA coverage (the 8.9 m-span sub-complex
  will still have over-cap ends at 3.0), at the cost of taller terrain
  benches beside buildings.
* **Q4 — May pads CUT terrain by default** (building seated below DEM →
  bench cut), or fill-only until in-sim review?  Symmetric recommended;
  cut pads are how a building dug into a slope reads correctly.
* **Q5 — Convergence loop.**  Pads reach the mesh one build late
  (§5.2).  Acceptable steady-state (recommended: scenery rebuilds are
  already iterative), or is an in-run re-mesh worth minutes of budget at
  relief-class airports?
