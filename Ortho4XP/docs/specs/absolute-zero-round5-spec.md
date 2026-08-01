# Absolute-zero round 5: tear-class quantification + the OLS NaN fix

Fable spec, 2026-08-01. First round of the absolute-zero program (owner
acceptance standard: zero actionable law-true defects on the four battery
airports, pre-existing included). Inputs: the α census
(scratchpad `alpha_census/`, 616 rows / 17 classes / 103 clusters), the
straddle exemption (`71f1ba4`), fix-arm round 4 (`d767cb4`). Line numbers
against `71f1ba4`.

## Part 1 — MEASUREMENT: what the straddle exemption dissolves

Run the revised `check_grade` (with `71f1ba4`'s straddle exemption) over
BOTH arms and quantify the tear-class change. Populations: the α-arm 45
graded_strip rows (census class F: HECA 37, CYXY 6, SPLP 2 — ALL α-only)
and the β-arm ~362 `adjacent_ground` rows (round-4 slice). Emitted
artifacts for HECA/SPJC exist from round 4; build CYXY and SPLP gate-on
lab arms fresh (round-2 gates + probes) — their last gate-on arms predate
round 4.

Deliver the three-way split the owner's enclosure ruling requires, per
row: (i) POCKET-INTERIOR (inside `gap_fill.collared_pocket_zone_union` —
the fill+drainage domain; a tear here is a REAL defect and must NOT
dissolve), (ii) ZONES 1-2 (graded corridor — real defect), (iii)
OPEN-BOUNDARY (graded→DEM edge — lawful terrace; the exemption's
legitimate prey). For every row the exemption dissolves, record which
class it was in; any dissolved POCKET or ZONE-1/2 row is a FINDING
(the exemption fired where law still applies) reported loudly with the
wall-face evidence. For every OPEN-BOUNDARY row that survives (no wall
face emitted), classify: is the surface actually torn there (emitter gap
— a real defect in the wall/terrace emission), or does the exemption's
geometry miss an emitted face (validator gap)? That split decides the
next fix.

Also re-quote the full acceptance arithmetic with the revised validator:
α total (was 616) and the β created slice (was 595), per airport, same
instruments as the census and round 4.

## Part 2 — FIX: census class C, the OLS-ROAD NaN class (48 rows, SPLP)

Mechanism (census, code-certain): `ols.py:1737` sentinels invalid
stations as `+inf`; the span grower at `ols.py:1773-1781` extends over
`gov_any` with NO `valid[]` guard (every other extension at
`:1782-1796` guards); `depth` is forced 0.0 at invalid stations
(`:1739`) so the blend-refusal guard at `:1808` passes; the analytic
blend at `:1884-1886` then computes `inf − inf = NaN`, and NaN altitudes
mint 34 within + 14 cross violations.

The fix, exactly scoped:
1. Guard the `gov_any` span extension at `ols.py:1773-1781` on
   `valid[]`, matching the neighbouring extensions' idiom.
2. A production finiteness assertion before the shape is built: if any
   emitted `vals` is non-finite, fail LOUDLY naming the piece, the
   stations, and which of the three invalidity causes fired
   (`sample_dem is None` / `_near_tile_seam` / `grid.refused`) — never
   emit a NaN altitude silently.
3. NO behaviour change to valid stations: the regrade/blend arithmetic
   for finite spans must be untouched (byte-comparison of all finite
   `vals` pre/post-fix on the same build is the check).

Open attribution question to ANSWER from the assertion's own output (do
not guess): which invalidity cause fires at SPLP's 34 vertices — the
census largely refuted the tile-seam hypothesis (2/34 within 10 m of the
seam), leaving refused-cell or DEM-hole.

## Acceptance

1. Unit tests: existing suites + new tests for the `valid` guard (a
   synthetic span crossing an invalid station stays finite) and the
   assertion (a forced-invalid fixture raises with the cause named). No
   new reds.
2. Gate-off byte identity on SPLP + CYXY vs the standing hashes — NOTE:
   the class-C fix is UNGATED (it fixes a NaN, there is no lawful
   "off" behaviour to preserve) so SPLP's body hash is EXPECTED to
   change; prove instead that the SPLP delta is confined to the 5
   `ols_road` shapes (#190-195 class) and that CYXY stays exactly
   `dcebb6ff…`. Report the new SPLP body hash for the baseline update.
3. Class C: 48 → 0 on the α arm (34 within + 14 cross), with the
   finiteness assertion silent (all stations valid or lawfully spanned).
4. Class M (6 real ols_road grade rows) unchanged — it is a DIFFERENT
   subclass; if the fix moves it, that is a finding.
5. β re-read NOT required this round: class C is α-only; quote Part 1's
   revised arithmetic instead.

Budget: 2 lab builds (CYXY, SPLP gate-on) + SPLP pre/post fix builds +
identity + suite ≈ 12 min of builds. Honest total quoted.

## Out of scope

Census priorities 2-5 (B+G portal steps, A emit-consensus probe, D, I+H
— next rounds, each with its own attribution instrument per the census);
the F-class emitter-vs-validator split's FIX (Part 1 only decides it);
tenure for off-graph chains; gate flips; R1/R2.
