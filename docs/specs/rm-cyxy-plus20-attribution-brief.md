# RM merge gate — attribute CYXY's +20 airside rows (Fable brief,
# 2026-08-18; the per-airport ruling's blocker, RULINGS 2026-08-18
# "'AIRSIDE STRICTLY IMPROVES' IS PER-AIRPORT")

Context: lane/routemetric (c009239, on the Mac) nets HECA airside
−194 but CYXY — an airport with ZERO within-debt — pays +20. Under
the per-airport ruling those 20 rows are the merge blocker. This
brief is attribution-first: locate the mechanism before any fix.

## Pre-registered reads (before any intervention arm)

1. The 20 rows themselves from the lane's CYXY census vs its control:
   family, way ids, coords, values — the row-level diff, not totals.
2. For each row: is the pair's budget the one RM changed (apron/
   junction/groundside within_shape → route-metric) or a DIFFERENT
   family whose value merely moved (transverse, seam, spine)?
3. The lane's SM decomposition script re-run on CYXY (promote
   rm/sm_decompose.py into tools/ WITH its INDEX entry on this second
   use — the standing tool-discipline ruling; its C1-proxy lat/lon
   bug is already fixed in the lane copy).

## Pre-delegated decision tree

* Rows are RELOCATED TRANSVERSE (the chord law's flatness role) →
  they belong to C3's docket by the 2026-08-18 RM (a) ruling. RM
  merges AFTER the C3 airside-frozen rework prices them back to ≤
  baseline on the composed tree — merge order becomes chord limiter
  → C3 → RM, and the RM acceptance re-runs on that base.
* Rows are ROUTE-METRIC RE-PRICING of pairs that were previously
  under-budgeted (the census now sees violations the chord metric
  hid) → they are newly-legible, not new debt: bring the row-by-row
  case to the lead for a newly-legible adjudication (the 20260812b
  precedent); merge is lawful only with that adjudication recorded.
* Rows TRACE TO THE LANE'S OWN BAKE (solver pair_caps and census
  disagree on any pair — a lockstep fork) → defect in the lane, fix
  in the lane, re-measure; this is the one branch where a fix
  precedes the merge-order question.
* Anything else → STOP-and-report to the Fable lead with the
  row-level evidence; do not improvise a fourth disposition.

## Constraints

Owner-artifact baseline law applies: read the lane's existing arms
and censuses first — a rebuild is lawful only if a read cannot answer
the attribution. No spec deviation without a Fable ruling. Materiality
0.01; attempt cap 2; per-airport acceptance is the merge gate, on
EVERY battery airport, not only CYXY.
