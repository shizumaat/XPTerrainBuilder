# Cycle 6 — Band wins (Part P) and DEM-writer ingestion (Part D)

**Status: BINDING.** Evidence: the c5auth dossier
(c5auth worktree, tmp/c5auth_dossier.md). Verdicts all (a) — no law is
missing or wrong; a conflict between two CORRECT constraints is being
resolved in the wrong direction, and ring writers seed raw DEM the
single-solve ruling already schedules for ingestion. Mode:
BUILD-COMPLETE-THEN-DEBUG. NOTE ON FRAMES: the dossier's tree lacks
lane/c5flex; the campaign tip has both — every lane establishes its own
baseline build before measuring a delta.

## Part P — the band WINS a groundside conflict (airside-first; do FIRST)

The defect: `one_solve.py:2616-2629` — when a freed groundside pin's
per-sweep law-ceiling box (fix 3; ceiling = the lot's weld datum, ≈1 m
in the plateau world) is DISJOINT from the airside reach band (fix 2),
the merge declares a conflict, KEEPS THE PIN BOX AND DISCARDS THE BAND.
fp#8 then clamps those nodes to the lot datum (14 nodes at HECA, up to
87 m below their band floor); `final_grade_projection`, carrying no
such box, lifts them back — those lifts ARE the second-author extremes
(all 14 >10 m moves; the stuck 89 m residual's carrier). Decisive:
14 declared conflicts ≡ the 14 below-floor gs_pin nodes; cross-airport
the count predicts the worst residual (HEAZ 0/3.79 · SPJC 0/0.83 ·
KCLT 0/0.55 · HECA 14/89.14).

The law (standing): AIRSIDE IS KING — groundside must have zero pull
on airside; the graded/DEM and graded/groundside boundary terraces
freely (retaining walls). Required: at a declared conflict the BAND
binds; the groundside box YIELDS — its ceiling re-derives from the
airside-conformed datum at that node (the lot conforms via the
terrace/wall machinery), or the node leaves the groundside box set;
never a silent discard of either constraint — the conflict stays a
loud report line naming both halves and the resolution. No relaxation
of the band, no new constants.

Acceptance (fresh baseline first): the declared-conflict nodes exit at
or above their band floor; fp#8 worst residual collapses off the ~89 m
class (quote the next-worst class honestly); who_wrote --author
untouched moves >10 m → ≈0; HECA plateau + HEAZ sentinel builds,
censuses quoted; the SOLVE EXIT certificate before/after (expected to
improve; quote, don't promise); twins for the resolution direction
(a synthetic disjoint pin-box/band case must resolve airside).

## Part D — ring vertices never take raw DEM (the ingestion)

The defect: SEVENTEEN geometry-time ring writers seed new vertices
from raw DEM (dossier table; top: `pavement_scoring.py:2166:
_enact_verdict` — 7,653 in-memory; plus groundside separate/merge,
`finalize.emit_terrain_transition_features` (also a live second
author: 89 untouched moves, worst 94.52 m), bridges portals,
adjacent-ground walls, solve seats). Battery-wide they own cluster D:
2,166 adjudicated rows ≥10 m (17.2%; HEAZ 57.1% and KCLT 41.4% of
their own totals), and the canyon stranded-at-DEM class (SPJC 55 /
KCLT 186+259 / HEAZ 7).

Required (single-solve ruling 2026-08-03; DEM is a seed): a ring
vertex minted after the solve NEVER takes raw DEM. It takes the
law-interpolated value along its host ring edge (the same insert-value
law planarize uses, crown-consistent) or — where the writer runs
pre-solve — the vertex joins the node list and the solve values it.
Work through the dossier's 17-site table top-down by emitted-vertex
count; per site, decide interpolate-vs-ingest (decide-and-note), and
the who_wrote DEM-origin instrument must read ZERO emitted DEM-seeded
vertices at the end. A site whose DEM value is actually lawful
authority (e.g. a true raw-DEM zone boundary under the adjacent-ground
law) is EXEMPT with its citation named in the report.

Acceptance: cluster D adjudicated rows collapse (quote per airport);
the canyon stranded-at-DEM class → 0 (HEAZ/SPJC/KCLT canyon builds);
who_wrote --author-dump DEM-origin writers → 0 emitted (minus named
exemptions); full four-airport plateau censuses quoted vs the lane's
own baseline; suite + harness twins green.

Budget: P ~3 builds; D ~6-8 builds (it may batch airports). Materiality
0.01 m; attempt cap 2 per site/fix; heartbeat; foreground builds;
no real-DEM; no shared-repo writes.
