# Round 15 — a degenerate sliver never kills a tile

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **r15mesh**. Pre-ship mode
(docs/RULINGS.md); deviations STOP-and-report. Owner is BLOCKED on this
in-app: tile +25+051 crashes at mesh post-processing on 1.0.238.

## Measured attribution

* App console traceback: `O4_Mesh_Utils.py:186
  post_process_nodes_altitudes` → `ValueError: invalid literal for
  int() with base 10: '1.4375'`.
* The tile's `.ele` (X-Plane 12/Custom Scenery/zOrtho4XP_+25+051/
  Data+25+051.1.ele, READ-ONLY — never write the X-Plane install) holds
  exactly 2 triangles (lines 1388590/1388776) whose ATTRIBUTE column is
  the float `1.4375`; Triangle's ele-attribute column is REAL by format
  spec, and the parser does `int(x)` on it.
* Those triangles' four vertices are ONE POINT: coordinates differ only
  at the 11th decimal (sub-micron), all at Z0 3.962 — degenerate
  slivers. In the consumed patch (Patches/+20+050/+25+051/
  OTHH_auto.patch.osm, 17:09) the area holds `object_pad:2336`'s ring +
  `object_pad_blend:2336` + an untagged way within ~2 m, nodes no
  closer than 0.05 m — so the sub-micron cluster was minted DOWNSTREAM,
  by mesh-input insertion (edge intersection/encroachment splitting in
  O4_Vector_Map), not by the patch.
* Window: the same tile built clean at 15:03 on engine 1.50.1680
  (rounds 10-12) and crashed at 17:18 on 1.50.1681 (rounds 13-14) —
  round 14's OTHH recomposition changed insertion content/order enough
  to expose the class; the class itself (near-coincident intersection
  vertices) is old and data-dependent.
* Latent second trap: the parser's fast-skip `line[-2] == "0"` and the
  `int()` both assume integer text; an INTEGRAL float ("16.0") would
  also crash.

## The laws

### R15-1 CONTAINMENT — the parser accepts REAL attributes, loudly

In `post_process_nodes_altitudes` (and any sibling reader of the ele
attribute column — grep for the idiom): vertex indices parse as int
(they ARE ints); the attribute parses as FLOAT. An integral float
(|attr − round(attr)| ≤ 1e-6) is its int. A NON-integral attribute is
a MEASURED DEGENERACY: one loud line per build naming the count, the
first few triangle indices, attr values and a vertex coordinate — and
the triangle is treated as the dummy attribute (no post-treatment),
which for a sub-micron sliver is exact. The fast-skip stays only if it
remains correct for float text (prove it or drop it). A tile NEVER
crashes on this again.

### R15-2 THE WELD — sub-micron constrained vertices are one vertex

Attribute FIRST (mechanism-before-fix): find where the mesh-input
insertion minted four vertices within 1e-11° at 25.270446,51.591788 —
O4_Vector_Map's insert/split path (encroachment splits, edge
intersections) and its node-dedup tolerance are the suspects. Name the
exact minting path in the commit message. THEN: constrained mesh-input
vertices within the insertion epsilon WELD to one vertex at insertion
(follow the vector map's existing dedup idiom — tighten/route through
it, never a second registry). If the mechanism turns out NOT to be a
weld-tolerance gap (e.g. genuinely distinct constraint geometry that
cannot merge), STOP and report with the geometry.

## Tests

tests file per the repo idiom: R15-1 twins (float attr "1.4375" → 
dummy + loud count; "16.0" → int 16; "16" unchanged; vertex columns
still strict int); R15-2 twin per the found mechanism (two constraint
segments minting a sub-epsilon intersection pair → one welded vertex).
Run the directly-covering files once, ledgered (find the existing
O4_Mesh_Utils / Vector_Map coverage; pre-existing failures matched at
base are out of scope).

## Acceptance

The blocked tile: a mesh-steps rebuild of +25+051 through
`tools/run_tile_mesh_only.py` (the sanctioned mesh entry, guard armed)
in a LANE-LOCAL build dir — NEVER the X-Plane install; copy/point the
inputs per that tool's own documented usage — completes with rc=0.
Quote: the loud-line count (expect 0 after R15-2's weld, or the
counted containment if the weld legitimately can't cover), and
before/after the number of sub-micron vertex clusters in the .node
output (measure: vertex pairs within 1e-9°). KCLT mesh steps as the
control (was already passing — must stay passing).

## Bookkeeping

Lead writes the DEFERRED_VERIFICATION line. NOTE for the round-16
queue (not this lane): the wall-face/anchor/joint-floor residuals and
the OTHH 25.2566 needle class share the "emitted near-coincident
geometry makes mesh slivers" family with this round — cross-reference.
