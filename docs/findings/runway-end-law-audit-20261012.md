# rwyend620 — runway-end grade law: standards, engine, measured ends (scout, 2026-10-12, read-only)

Sources actually read (text extracted with pdftotext from files WebFetch saved):
* **EASA CS-ADR-DSN Issue 7, 16 May 2025** (ED Decision 2025/004/R) — `https://www.easa.europa.eu/en/downloads/141978/en`. Primary EU text; word-identical to Annex 14 in these clauses.
* **ICAO Doc 9157 Aerodrome Design Manual Part 1 Runways, 4th ed. 2020, Amdt 1 (24/6/25)** — `https://www.bazl.admin.ch/dam/en/sd-web/6fUporPnIYiN/icao_doc_9157_aerodromedesignmanual-part1.pdf`. ICAO's own manual; its ch. 5 restates Annex 14 Vol I ch. 3 with shall/should wording and ITS OWN numbering (5.x.y). The Annex 14 paragraph numbers below (3.x.y) are the ones this repo's `docs/STANDARDS.md` and `rulesets.toml` carry and are **UNVERIFIED against an Annex 14 copy** (the only Annex 14 PDFs found sit behind a university login).
* **FAA AC 150/5300-13B**: faa.gov returns HTTP 403 to WebFetch (4 URL forms tried; web.archive.org is blocked for this tool). Every FAA clause below is **UNVERIFIED** — it is the repo's own transcription at `Ortho4XP/src/auto_patch/config.py:4915-4934` and `Ortho4XP/tools/harness/law_support/grade_law.py:481-488`, and the FAA document page lists the current issue as "Change 1, issued 2024-08-16" (search snippet, not read).
* TP 312 5th ed: not attempted (optional).

## A. What the standards say beyond a runway end

| # | rule | document + clause | applies | limit | SHALL / SHOULD |
|---|---|---|---|---|---|
| A1 | Strip extends before the threshold and beyond the end/stopway | Doc 9157 §5.3.2; CS ADR-DSN.B.155(a); (Annex 14 §3.4.2 unverified) | 0 → 60 m beyond the end (code 2/3/4; code 1 instrument); 30 m code 1 non-instrument | — | should |
| A2 | Graded portion of the strip = within 75 m (code 3/4) / 40 m (1/2; instrument) or 75/55/40/30 (non-instrument code 4/3/2/1) "from the centre line of the runway **and its extended centre line**" | Doc 9157 §5.3.12, §5.3.14; CS B.175(a)(b); (Annex 14 §3.4.8-9) | the whole strip length, i.e. including the 60 m beyond each end | — | should |
| A3 | Strip surface abutting a runway/shoulder/stopway is FLUSH with it | Doc 9157 §5.3.15 ("shall be flush"); CS B.175(c) | the abutting edge, incl. the end edge | flush | **shall** (ICAO) / should (EASA) |
| A4 | **Longitudinal slope of the graded portion** | Doc 9157 §5.3.17; CS B.180(b); (Annex 14 §3.4.12 as the repo cites it) | the graded portion — nothing in the text limits it to the abeam part, so it reads over the 60 m beyond the end too | 1.5 % code 4; 1.75 % code 3; 2 % code 1/2 | should |
| A5 | Longitudinal slope CHANGES on the graded portion | Doc 9157 §5.3.18; CS B.180(c) | same | "as gradual as practicable; abrupt changes or sudden reversals avoided" — NO number | should |
| A6 | Strip transverse | Doc 9157 §5.3.20; CS B.185(a) | graded portion | 2.5 % (3/4), 3 % (1/2); first 3 m from the pavement edge negative, up to 5 % | should |
| A7 | RAOA before the threshold (precision approach runways; Cat II/III, Cat I where practicable) | Doc 9157 §5.3.19 (±30 m) and §5.4.14 (≈60 m wide); CS B.205(b)(c) + GM1 B.205(a) | 300 m BEFORE the threshold, ±60 m (reducible to ±30 m) | slope changes avoided; where unavoidable ≤ 2 % per 30 m | should |
| A8 | RESA start and length | Doc 9157 §5.4.4-5.4.5; CS C.215(a) | from the END OF THE STRIP (= 60 m past the runway end): ≥ 90 m required (code 3/4; 1/2 instrument), 240 m recommended (3/4), 120 m (1/2 instr), 30 m (1/2 non-instr) | — | shall (90 m) / should (240 m) |
| A9 | RESA width | Doc 9157 §5.4.8-9; CS C.215(c) | — | ≥ 2× runway width; preferably = graded strip width | shall / should |
| A10 | RESA combined slope | Doc 9157 §5.4.12; CS C.230(a)(1) | RESA | no part penetrates the approach or take-off climb surface (binds RISING ground only) | should |
| A11 | **RESA longitudinal** | Doc 9157 §5.4.13; CS C.230(a)(2); (Annex 14 §3.5.9-10 as the repo cites) | RESA (60 → 150/300 m beyond the end) | downward ≤ 5 %; changes "as gradual as practicable", abrupt changes/reversals avoided | should |
| A12 | RESA transverse | Doc 9157 §5.4.15; CS C.230(b) | RESA | ≤ 5 % up or down | should |
| A13 | Runway own: first/last quarter | Doc 9157 §5.1.5; CS B.060(c) | first & last quarter of the runway | 0.8 % for code 4 (all) and code 3 precision Cat II/III; otherwise 1.25 / 1.5 / 2 % | should |
| A14 | Runway own: slope change and rate | Doc 9157 §5.1.6-5.1.7; CS B.065(b)(c) | the runway | change ≤ 1.5 % (3/4) / 2 % (1/2); rate ≤ 0.1 %/30 m code 4, 0.2 %/30 m code 3, 0.4 %/30 m code 1/2 | should |
| A15 | "The runway grade must CONTINUE for a distance beyond the end" | **NOT FOUND** in Doc 9157 Part 1 (grep "profile", "continu", "same slope") nor in CS-ADR-DSN B.150-B.205 / C.210-C.235 | — | The nearest things: A3 (flush at the end edge), A4 (strip cap over the 60 m beyond), A5 (qualitative gradualness), A7 (RAOA rate, precision runways, before the threshold only) | — |
| F1 | FAA RSA longitudinal, first 200 ft | AC 150/5300-13B §3.16.5 items 2-5 (UNVERIFIED; `config.py:4915-4919`) | 0 → 61 m beyond the end | 0 to −3 % | Standard (per the repo's transcription) |
| F2 | FAA RSA longitudinal beyond | same (UNVERIFIED) | > 61 m to the RSA end | ≤ −5 %; no part above the approach surface | Standard |
| F3 | FAA RSA grade change | same (UNVERIFIED) | RSA | ≤ ±2 % per 100 ft (30.5 m) | Standard |
| F4 | FAA RSA transverse | §3.16.5 item 6 + Table 3-6 S-3; Fig 3-35 (UNVERIFIED; `grade_law.py:481-488`) | first 61 m: 1.5-5 % (AAC A/B) / 1.5-3 % (C/D/E); beyond: ±5 % | | Standard |
| F5 | FAA RSA length per end | App. G (UNVERIFIED; `docs/STANDARDS.md:365-366`) | from the runway end (stopway end if present) | 240 / 300 / 600 / 1,000 ft by RDC | Standard |

Reading of A4 against the owner's belief: ICAO/EASA do NOT require the runway profile to continue; they cap the graded strip's longitudinal slope at 1.5/1.75/2 % and that cap, as written, covers the 60 m of strip beyond the end (the graded portion is defined about the runway centre line "and its extended centre line"). Beyond 60 m the RESA's 5 % governs. FAA's F1/F3 is the one numeric "gentle for a set distance" rule: −3 % for 61 m and a 2 %/30.5 m change limit — if the transcription is right.

## B. What the engine does

| standard rule | engine key / file:line | as written? | difference |
|---|---|---|---|
| A1/A8 extent beyond the end | `rulesets.toml:119` `[icao.end_skirt] corridor_length_m` 60/90/150/240 by code (`config.py:3118` comment: "fold the strip-end portion in and stay conservative-but-tunable") | no | not a standards number: ICAO = 60 m strip + 90 m (shall) / 240 m (should) RESA = 150 / 300 m for code 3/4. AND it creates no ground: it is only the FOOTPRINT rows are searched in (`constraints/strips.py:141-150`, `verify/strips.py:218-222`, `classify/roles.py:1389`, `planar/strip_keepout.py:29`). The ground beyond an end is CREATED by `planar/zones.py:259-262` `outer = u.buffer(hw, MITRE)` — the runway-family union buffered by the zone-2 half-width `zones.toml:24-25` (30/40/75/75 by code; FAA 18.3/22.9/76.2 by letter) in every direction, so the band reaches exactly `hw` past the last runway-family cell (apt.dat overrun/blast pad included). Code 3 ⇒ 75 m, not 150. |
| A2 graded width beyond the end | `zones.toml:24` half_width_m; `strips.py:140` `end_half = max(width, strip_half)` | yes (width) | — |
| A3 flush at the end edge | the zone-1 lip ring and the end-foot chord (`strips.py:351-440 _end_foot_rows`) | partly | the lip's mandatory 3-5 % fall starts AT the end edge (KBFI/NLWF rows below show −7 to −14 % over the 3 m lip at the end — the lip family's business, reported not judged) |
| **A4 strip longitudinal cap over the 60 m beyond the end** | `rulesets.toml:113` `[icao.strip] longitudinal` 1.75 % code 3 — generator `constraints/strips.py:212-235 strip_longitudinal` reads `g.rings[0]` (the LATERAL rectangle between the ends, :148) only; `strip_arc` :249 likewise; census `tools/check_grade.py:3877-3893` + :3795-3798 ("rings[0] is the LATERAL graded-strip rectangle … rings[1:] the two END corridors") and `verify/strips.py` the same | **no** | the strip cap is applied ABEAM only; beyond the end the only longitudinal cap is `end_skirt.max_down_grade` 5 % |
| A11 RESA 5 % downward | `rulesets.toml:118` 0.05 → `strips.py:321-348 end_corridor_longitudinal` (ring pairs in rings[1]/[2]) + `_end_foot_rows` chord from the end edge (±cap·d + q) | mostly | rows are TWO-SIDED `Linear(…, −cap·ds−q, cap·ds+q)` — they cap a RISE at 5 % too, which ICAO does not (rising ground is bound by the approach surface, A10, = the `eat` family); applied from 0 m, not from 60 m (stricter than ICAO's RESA, looser than A4) |
| A5 / F3 grade-change rate beyond the end | `rulesets.toml:120` `[icao.end_skirt] rate` 2 %/30.5 m PROVISIONAL, `:175` faa rate | **not implemented** | `end_skirt.rate` is read by NO generator and NO census reader (grep over `src/auto_patch_v2`, `tools/check_grade.py`, `grade_law.py`: only `max_down_grade`, `corridor_length_m`, `near_zone_m` have readers) |
| F1 FAA 0 to −3 % first 61 m | `rulesets.toml:171-173` `near_zone_m = 61`, `near_max_down_grade = 0.03` | **not implemented** | `near_max_down_grade` has no reader; `near_zone_m` is read only by `resa_transverse` (`strips.py:271`, `verify/strips.py:316`) |
| F4 FAA transverse near zone | `strips.py:269-318`; `verify/strips.py:300-335` | yes | — |
| A7 RAOA | `rulesets.toml:126-129`; `strips.py:443-491`; census `verify/strips.py raoa` | yes (ICAO only, all runways, not just precision) | applies to every ICAO runway; the text says precision approach runways |
| census of the end corridor's longitudinal | family `runway_end_skirt` (`families.toml:76-83`, roles `runway_clearance`); `verify/runway.py:258-276` reads rings with `ref == "runway_end_skirt"` — "v2 emits none" (:39); `check_grade.py:2946` same | **judges nothing** | the 5 % end-corridor rows are priced by the solver and censused by no family; `strip_longitudinal`/`strip_arc` census is lateral-only. So the issue's "all 0 rows judged" is a blind spot, not a pass |
| ties to the runway's own grade at the end | none | — | no row relates the first strip pair beyond the end to the last runway pair (`strip_arc` is rings[0]; `runway_vertical_curve` reads runway rings only) |
| what trims the band | `zones.py` ~:215 groundside cells + `groundside_cutback_m`; ~:275 shore; ~:290 `clip_to_terrain_edge` (spec §19, RULINGS 2026-09-10c "trim at road or crest"); gap aprons | — | none fired at CYCG (patch has no `terrain_edge` feature, sidecar `shore_edges`/`natural_shore` empty; the next transect station is OUTSIDE PATCH = raw DEM) |

## C. Measured runway ends (patch read only; no DEM for +49-118 in the data repo, so z-DEM is not given)

Method: `tools/patch_transect.py` (5 m stations, 300 m inside → 450 m beyond each sidecar `runway_axes` end) for coverage/extent/next shape; a scratch reader on `check_grade._parse_osm` for the NODE profile on the centreline (nodes within ±8 m of the axis; ±20 m where ±8 m found none — flagged †). "pav_end" = last runway-role node beyond the apt.dat end (blast pad/overrun); grades are outward, negative = falling away. Governed extent is measured from pav_end. Ruleset from each sidecar `ruleset`. Every end's next station past the governed edge reads OUTSIDE PATCH (raw DEM) unless a role is named.

Sorted by the first segment beyond the pavement end (steepest fall first). seg = (from m, to m, grade %, length m).

| airport (ruleset, code) | end | runway grade last 300 m / last 60 m | z end | segments beyond the end | grade change at the end (pp) | governed extent / `corridor_length_m` | what lies at the edge |
|---|---|---|---|---|---|---|---|
| SPJC (icao, 4D) | 34L | +0.69 / +0.93 | 20.55 | (0,12.3,+0.81),(12.3,87.2,**−3.71**) | −0.12 then −4.5 | 87.2 / 240 | graded_strip → OUTSIDE |
| SPJC (icao, 4D) | 16R | +0.11 / +0.45 | 8.92 | (0,12.3,+0.65),(12.3,87.2,**−3.57**) | +0.20 then −4.2 | 87.2 / 240 | graded_strip → OUTSIDE |
| CYCG (icao, 3E) | 15 | −0.39 / −0.49 | 492.56 | (0,74.4,**−2.77**) | **−2.28** | 74.4 / 150 | graded_strip zone2#2 → OUTSIDE |
| KASE (faa, 4D) | 15 | −1.99 / −2.00 | 2340.86 | (0,76.1,−2.35) | −0.35 | 76.1 / 240 | graded_strip → OUTSIDE |
| CYCG (icao, 3E) | 33 | −0.43 / −0.51 | 494.69 | (0,74.9,**−2.26**) | −1.75 | 74.9 / 150 | graded_strip → OUTSIDE |
| HECA (icao, 4F) † | 23L | +1.10 / +1.04 | 142.83 | ±20 m read: 0-60 m −2.59, end→edge −1.19 over 342 m | −0.18 | 342 (chained taxi bands) / 240 | service_road |
| KPDX (faa, 4D) | 3 | 0.00 / 0.00 | 6.71 | (0,76.1,−1.62) | −1.62 | 76.1 (strip), transect 332 via service road / 240 | graded_strip → cross_connector/service_road |
| SPJC (icao, 4D) | 16L | −0.32 / −0.20 | 13.32 | (0,11.6,−0.09),(11.6,23.9,0),(23.9,98.8,−1.75) | +0.11 | 98.8 / 240 | graded_strip → OUTSIDE |
| HECA (icao, 4F) † | 23C | +0.13 / +0.12 | 114.37 | ±20 m: 0-60 m −1.47, end→edge −1.44 | +0.13 | 86.8 / 240 | graded_strip → OUTSIDE |
| KCLT (faa, 4E) | 36R | −0.05 / −0.07 | 220.34 | (0,12,0),(12,87.9,−1.38) | +0.07 | 87.9 / 240 | graded_strip → OUTSIDE |
| SPJC (icao, 4D) | 34R | +0.71 / +0.58 | 33.71 | (0,12.3,+0.49),(12.3,86.7,−1.40) | −0.09 | 86.7 / 240 | graded_strip → OUTSIDE |
| KCLT (faa, 4E) | 18L | −0.19 / −0.35 | 227.17 | 12 m steps −0.33…−0.67, (83.9,90.9,−1.87), (101.5,159.8,−1.89) | +0.02 | 159.8 / 240 | graded_strip → OUTSIDE |
| HECA (icao, 4F) | 05L | +0.61 / +1.14 | 58.58 | (0,2.5,0),(2.5,74.3,−1.07) | −1.14 | 74.3 / 240 | graded_strip → OUTSIDE |
| KCLT (faa, 4E) | 36L | +0.23 / 0.00 | 226.76 | 12 m steps −0.17…−0.33, (71.4,147.3,−1.51) | −0.17 | 147.3 / 240 | graded_strip → OUTSIDE |
| KCLT (faa, 4E) | 18R | +0.04 / −0.23 | 226.63 | 12 m steps −0.33…−0.50, (71.4,147.3,−1.32) | −0.10 | 147.3 / 240 | graded_strip → OUTSIDE |
| KCLT (faa, 4E) | 18C | +0.44 / +0.30 | 226.30 | (0,11.5,+0.17),(11.5,87.4,−0.90) | −0.13 | 87.4 / 240 | graded_strip → OUTSIDE |
| CYXY (icao, 4D) | 32R | +0.64 / +0.94 | 701.69 | (0,74.3,−0.81) | −1.75 | 74.3 / 240 | graded_strip → OUTSIDE |
| HECA (icao, 4F) † | 05C | −0.09 / −0.32 | 116.24 | ±20 m: 0-60 m −0.89, end→edge −0.75 | +0.06 | 86.9 / 240 | graded_strip → OUTSIDE |
| CYXY (icao, 4D) | 14L | +0.17 / +0.17 | 694.39 | (0,74.3,−0.58) | −0.75 | 74.3 / 240 | graded_strip → OUTSIDE |
| CYXY (icao, 4E) | 14R | +0.09 / +0.30 | 694.11 | (0,74.3,−0.57) | −0.87 | 74.3 / 240 | graded_strip → OUTSIDE |
| KPDX (faa, 4E) | 10R | −0.02 / −0.15 | 6.93 | 12 m steps −0.25…−0.42, (71.9,148.2,−0.50) | −0.10 | 148.2 / 240 | graded_strip → OUTSIDE |
| CYXY (icao, 4E) † | 32L | +0.76 / +0.71 | 706.39 | ±20 m: (0,74.2,−0.39) | −1.10 | 74.2 / 240 | graded_strip → OUTSIDE (terrain_edge trim at the rim road, RULINGS 10d) |
| KCLT (faa, 4E) | 36C | −0.44 / −0.13 | 210.85 | (0,12,−0.25),(12,87.9,−0.41) | −0.12 | 87.9 / 240 | graded_strip → OUTSIDE |
| KBFI (faa, 4F) | 32L | −0.11 / −0.32 | 6.28 | (0,2.9,−7.24 lip),(2.9,75.7,+0.14),(75.7,248.6,−0.41 service_road) | lip step | 265 / 240 | service_road |
| KPDX (faa, 4E) | 10L | −0.03 / −0.07 | 9.04 | 12 m steps −0.08, (71.9,147.8,−0.47) | −0.01 | 147.8 / 240 | graded_strip → OUTSIDE |
| KPDX (faa, 4E) | 28L | −0.08 / −0.25 | 6.89 | 12 m steps −0.34…−0.50, (120,148,−0.80),(148,168,−2.03), … | −0.09 | 322 / 240 | service_road |
| KASE (faa, 4D) | 33 | +1.53 / +1.13 | 2389.30 | (0,75.5,−0.16) | −1.29 | 75.5 / 240 | graded_strip → OUTSIDE |
| KPDX (faa, 4E) | 28R | −0.01 / −0.04 | 9.39 | 12 m steps −0.08, (147.5,157.8,−0.98), (275,279,−3.32) | −0.04 | 279 / 240 | service_road |
| KPDX (faa, 4D) | 21 | +0.16 / +0.15 | 7.92 | (0,10.2,−0.78),(10.2,44.4,+0.20),(44.4,71.2,+0.37),(71.2,88.8,−1.99),(88.8,228.6,+0.77),… | −0.93 | 356 / 240 | graded_strip |
| OTHH (icao, 4E) | 16L/16R/34L/34R | 0.00 / 0.00 | 3.96-3.97 | 0.00 % in 12 m steps to 251 m, one −0.6…−2.7 % step of 3 m at 251-254, then 0 | 0.00 | 326-333 / 240 | graded_strip (34R: service_road) |
| CYXY (icao, 1B) | 20 | −0.02 / +0.05 | 693.77 | 12 m steps 0…+0.25 | +0.03 | 71.1 / 60 | primary_parallel / runway |
| KBFI (faa, 2D) | 14L | +0.10 / +0.15 | 5.59 | (0,76,−0.64),(76,129,+0.02),(129,139,+2.86),… | −0.79 | 387 / 90 | cross_connector |
| KBFI (faa, 2D) | 32R | −0.02 / −0.10 | 5.10 | (0,75.8,−0.48),(75.8,150,+0.03),(150,180,+1.00),(180,211,+0.77) | −0.38 | 225 / 90 | cross_connector / junction |
| KBFI (faa, 4F) | 14R | +0.06 / +0.05 | 5.51 | 12 m steps +0.08…+0.50 to 226 m, (226.5,229.4,−2.76), (229,302,+0.45) | +0.03 | 302 / 240 | graded_strip |
| HECA (icao, 4F) | 23R | −0.11 / −0.02 | 60.65 | (0,2.8,+1.07),(2.8,75,−2.02),(75,254,+0.78),… | +1.09 | 271 / 240 | service_road |
| HECA (icao, 4F) † | 05R | +0.50 / +1.17 | 137.11 | (0,11.7,+1.28); ±20 m: end→edge +1.42 | +0.11 | 86.7 / 240 | graded_strip → OUTSIDE |
| NLWF (icao, 2C) | 07 | −0.04 / −0.05 | 4.88 | (0,40.3,+0.42) | +0.47 | 40.3 / 90 | graded_strip → OUTSIDE |
| CYXY (icao, 1B) | 02 | +0.25 / +0.44 | 694.33 | +1.5 … +2.0 % for 448 m (taxi bands chained) | +1.08 | 448 / 60 | cross_connector / graded_strip |
| NLWF (icao, 2C) | 25 | +0.17 / +0.62 | 4.88 | (0,39.6,**+4.45**) rising | +4.07 | 39.6 / 90 | graded_strip → OUTSIDE |

Pattern: wherever nothing else stands beyond the pavement, the governed ground ends at 74-76 m (= zone-2 half-width 75 m ICAO code 3/4, 76.2 m FAA C-F; 40 m NLWF code 2; 30 m code 1) and the whole fall is ONE segment from the pavement end to that outer ring — the outer ring carries the DEM datum (RULINGS 2026-09-10c (3)/§23 "weak per-vertex DEM datum") and the solve draws a single plane to it. Longer extents are chained taxiway bands/roads, never the end corridor itself.

Judged (i) engine today (5 % two-sided, no rate), (ii) ICAO A4+A11, (iii) FAA F1-F3 (unverified):

| end | engine | ICAO strip 1.5/1.75 % over 0-60 m | ICAO RESA 5 % beyond 60 m | FAA −3 % / 61 m | FAA −5 % | FAA ±2 %/30.5 m change at the end |
|---|---|---|---|---|---|---|
| SPJC 34L / 16R | lawful | **over** (−2.78 / −2.70 over 60 m) | ok | n/a | n/a | n/a |
| CYCG 15 | lawful | **over** (−2.77) | ok | (would be ok) | ok | (would be **over**: −2.28 pp step) |
| CYCG 33 | lawful | **over** (−2.26) | ok | (ok) | ok | (ok, −1.75) |
| KASE 15 | lawful | n/a (FAA) | n/a | ok (−2.35) | ok | ok (−0.35) |
| KPDX 3 | lawful | n/a | n/a | ok (−1.62) | ok | ok (−1.62) |
| HECA 23L † | lawful | over if the ±20 m read holds (−2.59) | ok | n/a | n/a | n/a |
| all other ends | lawful | ok | ok | ok | ok | ok (the 3 m lip steps at KBFI/NLWF ends are the lip family's, excluded) |
| NLWF 25 (+4.45 % rising) | lawful (≤5 %) | **over** the 2 % code-2 strip cap (up) | RESA has no up cap; approach surface (A10) not read here | n/a | n/a | n/a |

## D. What each candidate rule would change (fill = metres the outer ring must RISE to meet the cap, from the measured profile)

| candidate | source | ends bound (of 44) | by how much |
|---|---|---|---|
| D1 ICAO strip longitudinal cap over the 60 m beyond the end (extend `strip_longitudinal`/`strip_arc` to rings[1]/[2] for s ≤ 60 m) | A4, should | 4 ICAO ends (SPJC 34L, 16R; CYCG 15, 33) + HECA 23L if the ±20 m read holds; NLWF 25 on the rising side | fill at 60 m: SPJC 34L 0.77 m, 16R 0.72 m, CYCG 15 0.61 m, CYCG 33 0.30 m; NLWF 25 cut 1.47 m (4.45→2 % over 60 m, but its band ends at 40 m) |
| D1' the same cap over the whole band (to 75 m) | not in the text (RESA 5 % governs past 60 m) | same 4 + KASE 15 if FAA letter D took 1.5 % | SPJC 34L 1.37, 16R 1.28, CYCG 15 0.76, 33 0.38, KASE 15 0.65 m |
| D2 FAA 0 to −3 % first 61 m (`faa.end_skirt.near_max_down_grade`, already in the table, unread) | F1, unverified | 0 FAA ends (KASE 15 −2.35 is the closest) | 0 m |
| D3 5 % beyond (today's rule, one-sided) | A11/F2 | 0 ends | 0 m |
| D4 grade-change rate 2 %/30.5 m across the end (`end_skirt.rate`, in the table, unread; FAA F3; ICAO A5 is qualitative, so PROVISIONAL stays) | F3 unverified; A5 qualitative | CYCG 15 only (−0.49 → −2.77 = 2.28 pp in one step); the 3 m lip steps if the lip is not exempted | CYCG 15: ≈0.2 m at 75 m if the first 30.5 m is held to −2.49 % and the rest at −2.77; none elsewhere |
| D5 "continue the runway grade for X m" | **no standard** (A15) | — | would be an owner design rule, not law |
| D6 extent to the standards' RESA (60+90 = 150 m shall; 60+240 = 300 m should for code 3/4) instead of `hw` | A1+A8 | every end whose band stops at 75 m (CYCG, CYXY, KASE, SPJC, HECA 05L …) | ground is created 75-150/300 m out; where the terrain falls away (CYCG 15: a river bank, see below) that is fill or a §19 crest trim — exactly the CYXY 10b precedent |

Where the real ground falls away steeply right past the end (the owner's "airports with steep grades at the end"): the standards' own answers are (a) the RESA may be shorter than recommended with a risk assessment (CS GM1 C.215: "many aerodromes were constructed before requirements for RESAs were introduced … assess the risk"; Doc 9157 §5.4.6-5.4.7), (b) declared distances / displaced thresholds / arresting systems (CS C.215(b); Doc 9157 §5.4.4 "may be reduced … arresting system"), (c) the strip itself still carries the 60 m at the strip cap (A4) — a bank or wall stands at the END of the graded strip/RESA, never inside it. What our model represents: the governed band ends at `hw` (or at a §19 crest/road, or a shore) and the mesh past it is raw DEM with whatever bank the daylight walk gives (09g; 2026-10-09d (1) "bare edge = raw DEM"); the zone law "zones 1-2 graded, beyond → raw DEM; boundary steps" (memory `adjacent-ground-zone-law`). So a steep bank at s = 60-75 m is representable today; a steep fall INSIDE the first 60 m is what A4 forbids and what the engine permits up to 5 %.

Owner options, one line each:
1. Apply the ICAO strip cap (1.5/1.75/2 %) to the first 60 m beyond each end (D1): binds 4 of 44 measured ends, max 0.77 m of fill at 60 m; FAA ends unchanged (FAA has no strip-cap analogue beyond the end; F1 −3 % binds none).
2. Also read `end_skirt.rate` at the end edge (D4): binds CYCG 15 only (~0.2 m); ICAO text is qualitative, so it stays PROVISIONAL.
3. Make the 5 % end-corridor rows one-sided (down only) and move rising ground to the approach-surface family: changes NLWF 25 (+4.45 %) from "capped at 5 %" to "capped by the take-off climb surface"; no measured end binds either way.
4. Extend the band to the standards' RESA length (D6): every 75 m-ending end gains 75-225 m of designed ground; CYCG 15 then runs out over the river bank and needs the §19 crest trim or a bank — the CYXY 10b precedent, not recommended by this scout.
5. Give the census a reader for the end-corridor longitudinal rows (today 0 rows by construction, `verify/runway.py:39`): no geometry change, closes the blind spot that let #620 read as "0 rows judged".

## CYCG, explained

* Patch `/Users/noah/XPTerrainBuilderData/Patches/+40-120/+49-118/CYCG_auto.patch.osm` (engine 1.50.1835, `o4_ruleset='icao'`, 15/33 code 3E, 1,604 m axis; sidecar pins RWY 15 492.5568 m, RWY 33 494.6904 m).
* RWY 15: runway −0.39 % over the last 300 m, −0.49 % over the last 60 m; threshold 492.56; ONE strip segment to the outer ring 74.4 m out at 490.50 = −2.77 % (the master's −2.75 % at 74.8 m is the same node). RWY 33: −0.43 / −0.51 %; 494.69 → 493.00 at 74.9 m = −2.26 %.
* Why 75 m and not 150: `planar/zones.py:260` buffers the runway union by the zone-2 half-width (`zones.toml:24`: 75 m for code 3) with a mitre join; that buffer IS the band's end cap. `end_skirt.corridor_length_m = 150` (`rulesets.toml:119`) never creates ground — it only sizes the footprint the end-corridor rows are looked for in. No trim fired: the patch carries no `terrain_edge` feature (grep 0), the sidecar has no `shore_edges`/`natural_shore`, and the station past the ring is OUTSIDE PATCH (raw DEM). So it is neither a road, crest, boundary nor river-bank trim — it is the band's own width.
* Why −2.77 % is allowed: the only longitudinal rows beyond the end are `end_corridor_longitudinal`/`_end_foot_rows` at `end_skirt.max_down_grade` = 5 % (`strips.py:325`); the 1.75 % strip cap (`rulesets.toml:113`) is generated and censused over the lateral rectangle only (`strips.py:227` rings[0]; `check_grade.py:3795-3798`). The outer ring takes the DEM datum (10c (3)), so the band falls to the natural ground at 75 m at whatever grade ≤ 5 % that needs. The `strip_longitudinal`/`strip_arc`/`runway_end_skirt` census families report 0 because they do not read this ground, not because it passes.
* Under ICAO A4 as written the first 60 m should not exceed 1.75 %: 0.61 m of fill at 60 m (0.76 m at 75 m) on the 15 end, 0.30 m (0.38 m) on the 33 end.
