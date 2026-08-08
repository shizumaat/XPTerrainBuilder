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

> **VERIFICATION VERDICT (2026-08-07 late, lane b8d95cc — STOP; the
> ratified pavement-only scoping is FALSIFIED IN-BUILD).** Works:
> merge-in of the trunk clean (718 tests green); walls inside pocket
> enclaves die correctly on the post-re-bake corpus (the one in-void
> adjacent_ground_wall gone; out-of-enclave walls untouched); SPJC's
> two small vetoes lift. FAILS: (1) the keep-out bounds the ZONE but
> stands down STATIONS, and a station inside a pocket removes band
> ROWS that reach into the WIDE infield — WIDE-region band 150,438 m²
> → 0 (the Phase-2 "restore" prediction came from an offline reader
> and is falsified); (2) consequent adjudicated AIRSIDE-NEGATIVE
> movement (+57 real / +136 −500, within_shape::apron dominated) —
> forbidden; (3) SPJC's 213,743 m² pocket is STILL vetoed —
> `_enclave_exempt` does not reach that blocker call site. SPECIMEN
> MOOT: the owner's re-bake PAVED the specimen void (41,854 m² apron
> both arms); on the pre-re-bake arms the fix demonstrably worked.
> wall_foot_ll rider population EMPTY on this corpus.
>
> **SCOPING v2 (Fable, this revision — the design delta):** the
> keep-out operates on BAND GEOMETRY, not station anchors: a band
> row/segment is stood down only where its OWN geometry lies inside a
> pocket region, CLIPPED at the region boundary (a row spanning
> pocket→WIDE survives in its WIDE extent). Cover the second veto
> call site with the same `_enclave_exempt`. Acceptance v2:
> WIDE-region band area == control (±1%); adjudicated airside Δ ≤ 0
> both worlds; in-pocket walls stay dead; out-of-enclave geometry
> byte-comparable; SPJC's big pocket faced or its veto attributed at
> the call site. Budget 3–4 builds, cap 5.

> **SCOPING v2 OUTCOME (2026-08-08, lane/enclave — measurements only;
> the design sentence above is unchanged).** Landed: the keep-out acts
> on band and wall GEOMETRY (`_derive_shape_stations_and_bands` no
> longer takes a zone at all), and the enclave EXEMPTION is width-scoped
> by the same `GAP_FILL_MAX_WIDTH_M` (`gap_fill._enclave_treatable`).
>
> ACCEPTANCE v2, measured against the reused post-re-bake controls:
> (1) WIDE-region band area **HECA real 150,438.5 → 150,614.9 m²
> (+0.117 %)**, **HECA −500 96,804.7 → 96,804.7 m² (0.000 %)**, **SPJC
> 0.0 → 0.0** — MET (±1 %). (2) adjudicated airside **HECA real 2,257 →
> 2,252 (−5)** MET, **SPJC 143 → 141 (−2)** MET, **HECA −500 1,858 →
> 1,954 (+96)** — **MISSED, this is the STOP**. (3) in-pocket walls dead
> both worlds (real 1 → 0, −500 13 → 0; out-of-void walls unchanged).
> (4) out-of-enclave PAVEMENT plan-identical (HECA junction 563/583,
> apron 247/264, groundside 1,034/1,037; SPJC junction 373/379); the
> band ways themselves are re-cut as a group by construction, their
> out-of-void AREA comparable to 0.011 % / 0.28 % / 0.000 %. (5) SPJC's
> 213,743 m² pocket: veto ATTRIBUTED at the named call site —
> `blocker=crossing_zone overlap=4203 m2 enclave=covered
> blocker_set=hard`. The exemption DOES reach it; the published crossing
> influence zone blocks unconditionally by design (a crossing is the
> owner's escape clause), so the veto is lawful and the v1 hypothesis
> ("`_enclave_exempt` does not exempt its foreign shape") is falsified.
>
> THE MECHANISM THE v1 VERDICT MIS-NAMED, for the record: the 150,438 m²
> of Annex 14 graded strip was never taken by the keep-out. The item-3
> exemption let HECA's 3.40 km² infield past the foreign-shape blocker;
> the gap law then declined the face on WIDTH (1,264 > 175 m) and
> `_emit_pocket_collar_rings` claimed the region as a "width-skipped
> pocket" (3 collar loops, 647 nodes), after which the COLLARED-POCKET
> zone stood the bands down over all of it. Offline proof on the v1
> arms: the 38 lost band ways sit 60–780 m from any pocket region and
> their 7 host shapes have 0 of 5,569 ring samples within 1.5 m of one.
>
> −500 STOP DETAIL (attempt cap 2 reached — geometry clip, then width
> scoping): +96 = NEW 295 / GONE 199 (`census_rows_diff`, airside).
> By class: within_shape::apron +39, strip_arc +21, strip_longitudinal
> +21, transverse +12, strip_seam_tear +9, frontage_near_miss −4,
> vertex_to_edge_step −1. By region: pocket ±0, WIDE +53, outside +43 —
> i.e. NOT in keep-out territory. The strip families concentrate on ONE
> site, band way `-12976` at 30.105897, 31.407168 (3.0–3.6 m steps at
> 9–56 %). Reading offered, not ruled: the in-pocket band removal
> (13,034.7 m²), 4 more gap faces and 14 fewer walls perturb the single
> solve, and the flat world's threshold density turns that into
> crossings — the accepted road-feed +192 class. It needs a ruling.
>
> SITE CENSUS (the campaign scoreboard, `census --sites`), for scale:
> ACTIONABLE sites **HECA real 121 → 115 (−6)**, **SPJC 18 → 16 (−2)**,
> **HECA −500 147 → 150 (+3)**. The −500 STOP is +96 rows = +3 places.
> Build-time note (tripwire only, no timing claim): 441.7 / 536.5 /
> 293.9 s against control walls ~440 / ~490 / ~322 s — no anomaly.

## Sequencing

AFTER lane/nidrepair merges — shared blast radius in
adjacent_ground/layout emission. Do not start before the lead
dispatches it.

## Budget

2–4 HECA builds + offline battery censuses; hard cap 6. Build-time
impact: the deduplicated enclave computation should be ≤ today's two
constructions — state the measured phase note. Deviations:
STOP-and-report for Fable review.
