# Kill-prep round: the three fixes that unblock quarantine deletion

Fable spec, 2026-08-03. The last fixes before the flip-and-kill round.
Lines against `d2321a6`. BINDING: docs/RULINGS.md (law compliance;
class-universal absorption `d2321a6`; feasibility-is-guaranteed;
convergence guards). Evidence: scratchpad `quarret2/` (the sole-cause
decomposition, adjudications, and kill-round input list — read first).

## §1 Service↔groundside absorption (gate `O4_SERVICE_LOT_ABSORPTION`, "0")
The owner-confirmed class-universal absorption applied to the A2/A3/A4
family (259 of 287 residual break nodes; 87% groundside/service roles):
* `anchors.apply_service_road_dem_follow`'s private cap-Lipschitz
  envelope (anchors.py ~2290-2320, export :2343) stops being a second
  grading authority: the service net's laterally-contiguous cross-
  sections join the ONE surface/one-cap law via the round-landed
  `lateral_contiguity` machinery (extend its class set; do not build a
  second walker). Where the service road welds to a lot, the contiguous
  surface takes the strictest cap (groundside 4% vs service 5% ⇒ 4%).
* A3's weld↔weld pocket premise ("neither may yield", solve.py:3001-19)
  dissolves — the two "authorities" are one surface; remove the pocket
  export under the gate (its scan may stay as a reporter).
* A2's mouth-relax export (solve.py:2995) under the gate exports
  NOTHING unconditionally: re-test the mouth after
  `adopt_projected_mouths`; only still-deficient nodes report (48 HECA
  + 6 HEAZ currently exported with zero deficit).
* OWNER CLARIFICATIONS (2026-08-03, binding): absorption is
  PORTION-ONLY — only the stretch sharing a lateral edge absorbs (the
  taxiway-through-apron pattern with a different cap); the free stretch
  (no pavement either side) MUST remain service road, with MANDATORY
  mouth cuts at every lateral-contact transition. THE SPINE REMAINS —
  absorption removes the separate surface, never the centerline (graph,
  reach, band semantics unchanged). CAP NOTE: the owner expects lots at
  ~5% but config's groundside cap is 4% — implement strictest-of-
  adjacent with today's constants (owner-only constants untouched) and
  REPORT the resulting shared-surface caps + any material grading
  change, feeding his separate ruling on the constant.
Pre-registered: HECA residual break nodes 287 → ≤ 40 (B3's 27 + shared
remainder); HEAZ 26 → ≤ 8; the 162 hidden rows either absorbed lawful
or visible; no airside surface change (airside-is-king control: runway
and junction role counts + runway vertices byte-compare).

## §2 B3 triangle-plane demotion (gate `O4_TRIANGLE_PLANE_REPORTS`, "0")
`_project_triangle_planes`' export (solve.py:4151-4159 → :5776):
"no single-vertex fix exists" is a search limitation, not
infeasibility. Under the gate the export becomes a REPORT (log line +
sidecar count, no break membership). The projection itself is
unchanged. Unresolved triangles surface as visible violations —
adjudicated as solver-convergence work, drained later; if the visible
residual after §1+§2 exceeds ~60 rows at HECA, note it for a
widen-the-search follow-up (do not implement one this round —
attempt-cap discipline).

## §3 The raster seed-cell fix (gate `O4_BAND_SEED_EXACT`, "0")
`raster_reach_band.py:428-432`: the 3 m grid cell collapses different
nodes' floor/ceiling seeds into one cell, pricing intra-cell route
distance at zero — manufacturing inversions up to cap×3√2 ≈ 0.064 m
(HEAZ's 6, four-of-four reproduced). Under the gate: per-cell seeds
must come from ONE node (the nearest-to-cell-centre, or price the
intra-cell leg at cap×distance — implementer picks the one that
preserves the band's existing lookup semantics and says why).
Pre-registered: HEAZ B1a inversions 6 → 0; the band's non-null coverage
unchanged (±0); HECA band values move ≤ 0.07 m anywhere (the artifact's
own bound) and only at collapsed cells.

## Acceptance
Gate-off byte identity: CYXY `dcebb6ff…`, SPLP `c2316222…`, HECA
repaired-config `9a49cbce…` (log every arm's `env | grep O4_` into
`.progress` — the mislabeled-arm lesson). Gates-on arms (repaired config
+ prior round gates + these three) at HECA + HEAZ + CYXY: the
pre-registrations above, both frames quoted, adjudication column
included (lawful-by-absorption vs visible-violation vs artifact-died).
Suite green over the same 23 reds + new tests per gate (each gate's
on/off behavior + the owner's ring-road tests still pass with the
extended class set). Exclusive CYXY `--runs 3` medians; foreground only.

## Out of scope
The flip-and-kill round itself (defaults flip + machinery deletion +
the loud final-field error at >0.01 m — next spec, needs this round's
readings plus the exclusive timing battery and the whole-pipeline
review); the spine-keyed scorer re-key; the late-mint binding point;
the memo-key bug; rulesets/KCLT.
