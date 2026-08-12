# Scorer round — wide_blob never authors, and the KCLT apron/TAXI finding

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **scorer** (dispatch
after task "classify_report guard" merges — verification runs must be
lawful; and after r16/r17 merge if any shared file emerges). Pre-ship
mode (docs/RULINGS.md); deviations STOP-and-report. Owner-ruled
2026-08-11b (RULINGS c366c13).

## Carried evidence (SQ2 artifacts, session scratchpad sq2/)

* KMCI shapeID 995 (emitted way -10993): 28.6k m² LANDSIDE parking
  lot roled `apron` — the scorer flips GROUNDSIDE→APRON at 0.53 HIGH
  on `wide_blob`=1.0 ALONE (APRON 1.81 vs GROUNDSIDE 0.84), zero
  airside features (no name/apron/stand/runway_connected/
  airside_contact/taxi_contact). Sibling idx 1052 (53.2k m²) same
  shape of decision. `parking_cover` is 0.00 on every KMCI shape and
  `outside_boundary` 0 for these two — neither existing feature can
  catch them.
* KCLT idx 1254: 13,042 m² roled `apron`; scorer says TAXI at 0.58
  HIGH (`osm_taxi_major` 1.0, `name_taxi` 0.99) — 13k m² possibly
  graded under apron law.

## The laws

### S1 WIDE_BLOB MAY MAGNIFY, NEVER AUTHOR (owner-ruled)

In the scorer (`pavement_scoring.py` / `pavement_classification.py`,
the §7 hard-gate idiom per the classification-overhaul design): a
shape may be classified APRON only if at least one AIRSIDE-CONTACT
feature is positive (the artifact's own list: name/apron tag, stand,
runway_connected, airside_contact, taxi_contact — take the
production feature registry's actual names; never invent a feature).
`wide_blob` keeps its full weight WHEN such a feature is present
(magnifier), contributes zero authorship without one (hard gate, not
a weight tweak — the gate is structural so no future re-weighting
can un-rule it). One loud census line counts gated shapes per build.

### S2 THE KCLT idx1254 FINDING — adjudicate, then align

Attribute first: is idx 1254's apron ROLE (legacy) or the scorer's
TAXI the truth on the ground (OSM tags, geometry, the owner's
centroid to fly to — produce the same artifact shape as SQ2, one
page). If the scorer is right, the role flip rides the normal
shadow-pass promotion path (no special-case); if the legacy role is
right, the finding names which taxi features misfire
(`osm_taxi_major`/`name_taxi` on an apron-named way?). VERDICT IS
THE OWNER'S — STOP after the artifact if ambiguous; a clear-cut
scorer-correct case may proceed under S1's round with the artifact
quoted.

## Tests

Twins, mutation-checked: a landside wide blob with zero airside
contact stays GROUNDSIDE under S1 (the KMCI shape, synthesized); the
same blob WITH one airside-contact feature classifies as before
byte-for-byte; the gate census line. Directly-covering files once,
ledgered (test_classification_round.py + the scorer files' own
tests).

## Acceptance (battery LAST)

KMCI `--patch-only`: shapeID 995 and idx 1052 emit GROUNDSIDE-family
roles; census delta quoted (rows the apron law released); KCLT
`--patch-only` control (delta 0 beyond floor except idx1254 if S2
proceeded); one gentle control (SPJC or CYXY) delta 0. Guarded
classify_report (post-toolguard) re-run for the after-artifacts.

## Bookkeeping

Cap 2, STOP on second miss; `.progress` heartbeat; DEFERRED lines
per skip; tripwire only. Cross-refs: RULINGS c366c13,
[[pavement-classification-overhaul]] (§7 hard gates; owner shapeID
joins), [[emit-consensus-mints-violations]], sq2 artifacts.
