# Taut-string fix arm, round 2: the grip's pair graph is the LAW's pair graph

Fable spec, 2026-08-01. Follows round 1 (`b4ff1cd`); its measured findings
are the mechanisms here. Line numbers against `b4ff1cd`.

**The round-1 finding this fixes:** the grip guarantees lawfulness only
over DIRECT `spine_adj` edges. Two kept pins can still contradict
(a) across a junction RING edge the spine graph does not contain —
40 cross-string pin pairs over role cap in pin values, now emitted
verbatim under the final hold (e.g. HECA junction `-12539`: s9 112.386 vs
s2 104.410 over 3.69 m = 216.4% against 1.5%); and (b) THROUGH a shared
free neighbour — 2,375 of 5,252 declared rows have both authors kept pins
(pins at graph distance 2 whose interval through the free node is empty).
Both are the same defect: **the grip filters on a subgraph of the law.**
Ruling 52 already rules the remedy — the chord is never bent, the grip is;
these pins release.

## 0. Constraints

* Round-1 gates, probe machinery, and owner constants untouched. Fix
  entirely inside the string gate (it changes only the kept pin set), so
  gate-off byte identity (SPLP `d8d0f065…` / CYXY `dcebb6ff…`) must hold
  with no new gate.
* Mechanism-before-fix scoping: the measured defect classes are at law
  distance 1 (ring edges) and distance 2 (through one free node). This
  round fixes exactly those. Full multi-hop (≥3) route-metric Lipschitz
  filtering is pre-registered as the ESCALATION, triggered only if the
  declared both-pin population does not collapse (§3).
* Single-pass principle: the law's edge set must not be built twice.

## 1. Fix — grip pair-graph completion

### 1a. The edge set

`_build_shape_constraints` is today first called AFTER the hook
(`solve.py:1024` region). Reorder: build it ONCE before the S1 hook and
reuse that object at every later consumer in `solve_route_profile`
(verify by reading that nothing between the hook site and today's build
site mutates what the constraints are built from — they are phase-1
geometry + roles, not elevations; if that verification fails, STOP and
report). The grip's pair universe becomes:

    law_edges = spine_adj  ∪  shape-constraint edges whose BOTH ends
                are string-relevant nodes (pin or hard), with the
                constraint's own budget

Materialise only the edges the grip can act on (an end in `pins`) — never
the whole graph into pair tuples.

### 1b. The two-hop family

For every free node `v` with ≥ 2 pinned-or-hard neighbours in
`law_edges`: each pair `(i, j)` of those neighbours with
`i ∈ pins` gains a virtual pair with budget
`budget(i,v) + budget(v,j)` (the law's own freedom through `v` — the
exact interval round 1's bounding declares empty). Hard-hard pairs stay
skipped (pre-existing genuine steps). Degree-bounded enumeration; no
Dijkstra, no new engine.

### 1c. The filter

Both families feed the EXISTING `filter_pins_by_grade_law` machinery —
one `over` list, one greedy cover, one re-admission minimality pass, the
same endpoint-protective rank, `rule` field values: existing two, plus
`"ring_edge"` (1a beyond spine_adj) and `"through_free"` (1b). The
release candidate is always a pin; for pin-vs-pin two-hop pairs both are
candidates under the existing rank.

## 2. Probe extension — the `final_proj_1.entry` window

Round 1 left SPJC with a 51-pin G2 tail (max 4.74 m) labelled
`final_proj_1.entry` — minted between the solve's writeback and the first
final pass. Under the existing `O4_STRING_MOVER_LEDGER` gate, split that
window with sub-boundaries at the natural seams the pipeline already has
(writeback done; adjacent-ground/band emission; tile cut; conformance
welds; densify/decimate — use the seams that exist, label
`final_proj_1.entry.<stage>`, same diff idiom, watch set crossed by key
exactly as today). Report-only; no behaviour change; byte identity
unaffected (gate off = today's paths).

## 3. Measurement battery

1. Unit suite (round-1 set + new tests for 1a/1b/1c and the sub-
   boundaries; headless). No new reds.
2. All-gates-off byte identity: SPLP + CYXY vs the §0 hashes.
3. HECA + SPJC gate-on builds, all fixes + probes on (same env as
   round 1's battery, so arms are comparable).
4. Flip-gate β re-read against the ledgered α (`flipgate-alpha-gate-off`).

**Pre-registered outcomes:**
* Cross-string `a/b` class (pin values over the pair's cap): 40 → **0**;
  string-forced total 83 → the class-(c)-only residual; no frozen
  verbatim pin-pair violations anywhere in the created slice.
* Declared both-pin-author population: 2,375 → **~0** (release makes the
  through-node interval satisfiable). Residual > ~5% ⇒ the multi-hop
  class is real ⇒ ESCALATION: route-metric Lipschitz grip (value-seeded
  two-source field over the law graph) goes to the lead for its own spec
  — do not improvise it this round.
* Identity-joined G2: HECA stays in the 0-class; SPJC's 51-pin tail gets
  a NAMED sub-boundary attribution (fix next round, not this one).
* Flip-gate created slice: 837 → the sum of named residuals only
  (CYXY `adjacent_ground` clamp class → side task; SPJC entry-window
  class → named; everything else 0 target). Quote per-airport.
* W-CHORD1 worst bin: no regression from −4.78. Chords: byte-identical
  chord set; only pin dispositions change.
* Released-pin census by rule; GATE A coverage (86.2% baseline) must not
  drop below 80% — a larger drop is a finding (the pin web thinning),
  reported with the released stations mapped.
* Grip runtime: the reorder must not add a second constraints build
  (assert by construction/log); grip wall time quoted from the build's
  own phase ledger.

Budget: implementation + unit tests, 2 identity builds, HECA + SPJC
gate-on, one β battery (~712 s). Honest total ≈ 25 min of builds.

## 4. Out of scope

The SPJC entry-window mover fix (attribute first, this round), the CYXY
`adjacent_ground` clamp (side task), the multi-hop escalation (own spec
if triggered), gate-flip decisions (lead's, after readings), R1/R2.
