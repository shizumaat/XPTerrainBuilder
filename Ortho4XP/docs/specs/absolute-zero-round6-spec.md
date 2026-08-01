# Absolute-zero round 6: straddle v2 + the missing-wall attribution

Fable spec, 2026-08-01. Follows round 5 (`bad9f5e`); its Part-1 findings
are the mechanisms here. Line numbers against `bad9f5e`.

## Part 1 — FIX: the straddle exemption, corrected (validator)

Two defects in `71f1ba4`'s exemption, both measured:

1. **The open-ground clause is missing.** The owner's law exempts
   terraces at the graded→DEM boundary in OPEN ground; the exemption
   fires on any wall crossing, and 9 of its 21 firings dissolved
   ZONE-1/2 tears (real defects, worst dz 10.33 m). Add the clause:
   a pair is straddle-exempt ONLY IF ungraded ground lies between the
   two nodes — the pair's connecting segment interior must leave the
   graded domain (graded_strip ∪ pavement polygons) by more than
   `STRIP_SEAM_OPEN_GROUND_MIN_M = 0.01` (round 5: the gap distribution
   is bimodal, 6e-15…3e-7 vs ≥0.02 m, nothing between — any threshold in
   [1 µm, 1 cm] gives the same split; 1 cm is the conservative end).
   Implement the graded-domain test the way round 5's instrument did
   (`scratchpad/round5/geom.py`) — max ungraded gap along the segment —
   or an equivalent; it must be O(pairs · local shapes), not all-pairs.
2. **Ring-closing wall faces are dropped** (`_build_vertex_edge_tables`
   skips the repeated last node, so `wall_segs` misses each ring's
   closing segment). Include the closing segment per wall ring.

Pre-registered effect (round 5's own rows): α dissolutions 4 → ~1 (the
one endpoint-contact validator-gap row may or may not legitimately
dissolve — report it either way); β 17 → ~12 ± the closing-face adds;
ZERO zone-1/2 or pocket dissolutions anywhere (assert this in a test).
Update the acceptance arithmetic (round-5 instrument verbatim, all four
airports, both arms) with v2 in place.

## Part 2 — ATTRIBUTION: why no wall is emitted at 75 open-boundary tears

Round 5: 90 % of surviving open-boundary tears (19 α + 56 β rows) have
NO `retaining_wall` segment within 12 m — the surface steps to DEM with
nothing emitted to hold it. Attribute, do not fix:

* Read the wall/terrace emission path (adjacent_ground.py and whatever
  emits `retaining_wall` shapes — find the actual emitter; cite
  file:line) and determine, for the 75 rows (use round 5's
  `PART1_survivors.txt` + `cls_*.json`), WHY each got no wall: below an
  emission threshold? outside the emitter's scoped piece classes (cut
  pieces?)? a zone/band bookkeeping miss? the step formed by a role the
  emitter does not watch? Classify all 75 with code-cited reasons;
  "unattributed" is an acceptable answer for a remainder, guessing is
  not.
* Deliver the class split with per-class magnitude (dz) and whether the
  class is string-dependent (α vs β membership), so the lead can spec
  the emitter fix (or an owner question, if any class looks like intent
  — e.g. "should a 0.3 m step at the open boundary get a wall at all,
  or is it a lawful unwalled terrace below some height?" is OWNER
  territory — collect the magnitude distribution that question needs).

## Part 3 — INSTRUMENT CHECK: the SPJC lab-vs-flipgate β delta

Round 5 deviation 6: SPJC round-4 lab β (201 within) vs flipgate β (181)
at the same commit/gates — 32 lab-only, 12 ref-only. Hypothesis to test
FIRST (cheap): the FRAME differs — lab = untiled whole-airport layout,
pytest = per-tile — exactly as proven for SPLP (round-5 deviation 7).
Check whether SPJC's pytest build is tiled and whether the row diff
clusters at tile boundaries / tile-scoped shapes. Only if the frame
hypothesis fails, test the probe-env hypothesis (one SPJC pytest-frame
build with probe env on vs off — the probes are supposed to be
write-only and HECA byte-identity says they are; a violation here would
taint every β reading and must be reported LOUDLY).

## Acceptance

1. Unit tests: v2 clauses each tested (zone-1/2 pair with a crossing
   wall stays FLAGGED; open-boundary pair with a closing-segment wall
   face dissolves; pocket assertion). Chip tests + round-5 suites green;
   no new reds.
2. Gate-off byte identity: CYXY `dcebb6ff…`, SPLP `d8d0f065…` (the
   validator is not in the build path, so identity is trivially expected
   — prove it anyway, it is cheap).
3. The v2 quantification table (three-way split, dissolved accounting,
   acceptance arithmetic) with the zone-1/2-dissolution count = 0.
4. Part 2's 75-row classification and Part 3's verdict.

Budget: no airport builds expected except Part 3's possible one SPJC
pytest arm (~25 s) + identity builds; the rest is validator re-runs on
existing patches + code reading. Honest total quoted.

## Out of scope

The wall-emitter FIX (next round, from Part 2's classes); census
priorities 2-5; the F-class α rows (25 zone-1/2 α tears are now
confirmed REAL defects — they join the emitter-fix round); gate flips;
R1/R2.
