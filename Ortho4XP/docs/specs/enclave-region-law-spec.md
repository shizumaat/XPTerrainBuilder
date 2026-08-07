# Enclave region law — G-ENCLAVE becomes a region, gap-fill stops being vetoed — spec

> **PHASE-1 OUTCOME (2026-08-07, lane/enclave efdeae6 — NOT merged;
> STOP at item 4, correctly).** Items 1-3/5/6 land clean: ONE
> published computation (enclaves.py; shape predicate + GAP_M knob
> retired, not inert); 7/7 adjacent_ground_walls GONE incl. specimen
> -12825; specimen void = gap ring + spine; KCLT escapes untouched;
> HEAZ inert; 33 twins; void_census promoted. STOP: the band
> keep-out computed from the airside∪building union deletes
> 175,671 m² of band — 152,734 m² of it Annex-14 graded strip in the
> infield — because BUILDINGS subdivide the 3.4M m² infield into
> pocket-width regions the gap law itself declines on width: the
> keep-out stood bands down over ground the ruled treatment never
> takes. RATIFIED SCOPING (Fable, the lane's proposal): the BAND
> KEEP-OUT computes from the PAVEMENT-ONLY union's pocket-width
> regions — it must agree with the gap law about which ground the
> treatment OWNS — while layout.airside_enclaves stays
> airside∪building for G-ENCLAVE classification. CONTINUATION owes:
> the scoping (1 HECA verify build), the wall_foot_ll re-census
> (unmeasured at cap), the 322 m² untreated-void attribution, SPJC
> offline census (moves slightly; not claimed inert). Known
> intermittent: the library-index churn now REFUSES a build when the
> engine rewrites that cache (demfix detector working as designed on
> the chored noise class) — retry once warm, never touch the guard
> (the owner's chip session owns that fix).

Author: lead (Fable), 2026-08-07. Charter: G-ENCLAVE (owner
2026-07-28) + the 2026-08-07 extension to bare ground + the
attribution dossier `Ortho4XP/tmp/enclave_attrib/enclave_dossier.md`
(read it end-to-end; its mechanism is log-line-proven, not inferred).

## The attributed defect (from the dossier)

The ruled treatment (gap ring + spine, `gap_fill.py`) DETECTED the
specimen void and was vetoed by the foreign-shape blocker
(`gap_fill.py:2548-2570`) over a 5.58 m² groundside sliver — the
build's own `[gap-fill] skipped gap (foreign shape inside)` line
names it. The void then fell through to the adjacent-ground band
consumer, which owed a 7.4 m wall. One gate explains all five HECA
no-escape voids. G-ENCLAVE itself is structurally blind here: its
predicate is shape-ring-coverage (a shape must FILL the void to
pass), its candidate set is role/area-restricted, and 87.6% of the
specimen enclave is bare ground outside the shape universe entirely.

## The work

1. **ONE enclave computation** (single-pass principle): bounded
   complement components of the airside∪building union, computed
   once and published as `layout.airside_enclaves`. Deduplicate the
   two existing constructions (`pavement_scoring.py:2339`,
   `gap_fill.py:2136` — byte-identical role sets today). The
   tunnel/bridge escape clause stays: a void with a touching
   tunnel/bridge escape is NOT an enclave.
2. **G-ENCLAVE becomes point-in-enclave**: any shape inside a
   published enclave is airside-interior — no GAP_M, no 10 m² floor,
   no birth-role restriction, and the sweep sees post-demotion state
   (the dossier: 1 re-verdict against 1,103 demotions today).
3. **The gap-fill blocker stops vetoing ruled treatment**: a shape
   inside a published enclave does not block the gap face — the void
   takes ring + spine per the owner's treatment; interior shapes
   re-role per (2).
4. **The adjacent-ground band/wall consumer never runs inside an
   enclave interior** — enclave interiors are airside-interior by
   law, not band territory.

## Acceptance

1. Specimen: the 30.128508, 31.403444 void emits gap interior ring +
   spine; wall `-12825` (production id) is GONE; all five HECA
   no-escape voids treated; all seven `adjacent_ground_wall` ways in
   them gone.
2. Battery: KCLT's tunnel-escape voids untouched (escape clause
   twin); SPJC/SPLP/CYXY/HEAZ expected ~byte-identical (they have
   zero of the class on current evidence — a delta is reported, not
   hidden).
3. Census, matched control: every moved row attributed. The 10,657
   m² of groundside shapes in no-escape voids re-verdict airside —
   their rows re-adjudicate under airside law and are REPORTED as
   the lawful reclassification they are (list per shape). No other
   family moves.
4. `wall_foot_ll` re-censused from the harness census (expect HECA_lo
   48 → 38 per the dossier's join; NEVER adjusted arithmetically).
5. Twins: point-in-enclave predicate; in-enclave shape does not veto
   gap treatment; escape clause; band consumer skip inside enclaves.
6. Promote the dossier's `void_census.py` into tools/ with an INDEX
   entry + twin (second use is the promotion signal).

## Sequencing

AFTER lane/nidrepair merges — shared blast radius in
adjacent_ground/layout emission. Do not start before the lead
dispatches it.

## Budget

2–4 HECA builds + offline battery censuses; hard cap 6. Build-time
impact: the deduplicated enclave computation should be ≤ today's two
constructions — state the measured phase note. Deviations:
STOP-and-report for Fable review.
