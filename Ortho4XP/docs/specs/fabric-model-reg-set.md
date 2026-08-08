# The fabric model — REG SET enumeration (Phase 0)

Charter: `docs/specs/fabric-model-spec.md` §Phases, Phase 0 — "the exact
FAA/ICAO requirements for strips, RESA/OFZ graded surfaces, and drainage
(crowns, pavement-edge, taxiway-edge): dimensions, slopes, applicability,
per ruleset; mapped against existing machinery (keep/retire/build)."
Owner law it serves: RULINGS "THE FABRIC MODEL" (2026-08-08) §2/§4 —
explicit shaping exists ONLY in the reg set; unregulated ground gets
NOTHING; "that should include drainage requirements along all taxiways".
Ruleset law: RULINGS "Region-specific rulesets" (2026-08-02) —
jurisdictional fidelity, each authority's OWN value, never "the stricter".

Research only. No code was changed by this round.

---

## 0. Sources and verification status

| # | Source | Edition read | Reached? | Status |
|---|--------|--------------|----------|--------|
| S1 | ICAO Annex 14 Vol I, *Aerodrome Design and Operations* | **Eighth Edition, July 2018** (supersedes all previous on 8 Nov 2018; incl. Amdt 14) | YES — full text read | **PRIMARY-VERIFIED 2026-08-08** |
| S2 | EASA CS-ADR-DSN (*Certification Specifications and Guidance Material for Aerodrome Design*) | **Issue 7, 16 May 2025**, Annex to ED Decision 2025/004/R (326 pp) | YES — full text read | **PRIMARY-VERIFIED 2026-08-08** |
| S3 | FAA AC 150/5300-13B *Airport Design* w/ Chg 1 (Chg 1 signed 16 Aug 2024) | — | **NO** — `faa.gov` returns HTTP 403 to the fetch tool on both the `documentLibrary` PDF and the AC landing page; the browser pane returns a file-download dialog, not a page; `web.archive.org` is not fetchable by this tool; the `shepair.com` mirror is 404 | **NOT RE-VERIFIED 2026-08-08.** FAA values below are carried forward from the repo's own earlier primary reads (transverse-grade research 2026-07-07; gap audit 2026-07-08; adjacent-ground plan 2026-07-08; rulesets phase-B research 2026-08-02) and are labelled **PV-PRIOR** |
| S4 | FAA AC 150/5320-5D *Airport Drainage Design* | — | NO (same `faa.gov` block) | NOT REACHED — no value in this document depends on it |

Verification legend used in every table below:

* **PV-2026-08-08** — I read the authority's own words this round (S1/S2).
* **PV-PRIOR** — primary-verified in a named earlier repo round; not
  re-read this round because the source is unreachable (S3). Flagged.
* **SECONDARY** — value known only from a summary. *(No row in this
  document is SECONDARY; every FAA row is PV-PRIOR.)*

**Edition WATCH.** ICAO Annex 14 Vol I is quoted here at the **8th
edition (2018)**. Later amendments and the 9th edition exist and were
not obtained; every ICAO paragraph number below is an 8th-edition
number. The repo already carries a matching WATCH item for Amendment 18
(OLS/OFS, applicable 2028-11-26) in `docs/STANDARDS.md`.

---

## 1. What the standards actually mandate as SHAPED GROUND

The fabric-model question is narrower than "what does the code say":
*which ground, other than pavement, must the builder deliberately shape?*
Three answers fall out of the primary text, and one of them is a
negative:

1. **The graded portion of the runway strip and of the taxiway strip.**
   Both authorities say a defined band around the pavement "should
   provide a graded area", state its width, and then bound its
   longitudinal and transverse slopes. This is the largest genuinely
   mandated shaped-ground class.
2. **The runway end safety area.** "A runway end safety area should
   provide a **cleared and graded** area" (Annex 14 §3.5.8; CS
   ADR-DSN.C.225), with bounded longitudinal and transverse slopes.
   Mandated shaped ground — but see the anchor finding in §3.
3. **Drainage.** The only *numeric* drainage floors in the ICAO family
   are the **runway transverse minimum (1 %)** and the mandatory
   negative first-3 m lip at the runway-strip edge. Everything else in
   the ICAO family is a qualitative "sufficient to prevent the
   accumulation of water". The FAA family adds numeric minima
   (taxiways, aprons). See §4 and OWNER QUESTION Q2.
4. **OFZ — NOTHING.** The obstacle free zone is defined as *airspace*:
   "the airspace above the inner approach surface, inner transitional
   surfaces, and balked landing surface and that portion of the strip
   bounded by these surfaces, **which is not penetrated by any fixed
   obstacle** other than a low-mass and frangibly mounted one required
   for air navigation purposes" (Annex 14 Vol I, Ch. 1 Definitions —
   PV-2026-08-08). It is a *clearance volume*, not a graded surface.
   Its ground floor inside the strip is already governed by the strip
   grading law (§2). **The OFZ adds no shaped-ground requirement and
   the fabric model builds nothing for it.** The same reading applies
   to the whole obstacle-limitation family (Annex 14 Ch. 4): those are
   surfaces above which objects must not stand, and the repo's OLS cut
   law already documents itself as a deliberate scenery reinterpretation,
   not a regulatory grading mandate (`docs/STANDARDS.md` §OLS).

---

## 2. Runway strips

### 2.1 Footprint — how far the shaped ground extends

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Strip extends BEYOND runway/stopway end | 60 m (code 2, 3, 4; and code 1 instrument); 30 m (code 1 non-instrument) | Annex 14 §3.4.2 (**shall**); CS ADR-DSN.B.155 — PV-2026-08-08 | FAA has no separate "strip"; the RSA itself extends beyond the end (see §3) | AC §3.16.5 / App. G — PV-PRIOR |
| Strip lateral half-width (**full** strip, precision approach) | 140 m (code 3/4); 70 m (code 1/2) | Annex 14 §3.4.3 (**shall**, "wherever practicable") — PV-2026-08-08 | n/a (ROFA is the FAA analogue) | — |
| Strip lateral half-width (non-precision approach) | 140 m (3/4); 70 m (1/2) | Annex 14 §3.4.4 (rec.) — PV-2026-08-08 | n/a | — |
| Strip lateral half-width (non-instrument) | 75 m (3/4); 40 m (2); 30 m (1) | Annex 14 §3.4.5 (rec.) — PV-2026-08-08 | n/a | — |
| **GRADED portion half-width — instrument runway** | **75 m (code 3/4); 40 m (code 1/2)** | Annex 14 §3.4.8; **CS ADR-DSN.B.175(a)** — PV-2026-08-08 | RSA half-width by RDC: 18.3 m (A/B-I), 22.9 m (A/B-II), 76.2 m (C/D/E, all ADG) | AC App. G tables G-1…G-12 — PV-PRIOR |
| **GRADED portion half-width — non-instrument runway** | **75 m (3/4); 40 m (2); 30 m (1)** | Annex 14 §3.4.9; **CS ADR-DSN.B.175(b)** — PV-2026-08-08 | as above | PV-PRIOR |
| Wider graded strip, precision approach code 3/4 | 105 m, tapering to 75 m over the last 150 m at each end — **GUIDANCE ONLY** | Annex 14 §3.4.8 Note + Att. A §9; EASA GM1 ADR-DSN.B.175(a) Fig. GM-B-4 — PV-2026-08-08 | — | — |

> **FINDING F-1 (defect, small).** The repo's
> `RUNWAY_STRIP_HALF_WIDTH_BY_CODE = {1: 30, 2: 40, 3: 75, 4: 75}` is the
> **non-instrument** table (§3.4.9). For an **instrument** runway ICAO
> §3.4.8 / CS ADR-DSN.B.175(a) gives **40 m at code 1**, not 30 m. The
> graded-strip width must be keyed by *(code number, instrument
> /non-instrument)*, not by code number alone. Affects code-1 instrument
> runways only — none in the current five-airport battery, so it is a
> correctness fix, not a battery mover.

### 2.2 Slopes on the graded strip

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Longitudinal slope of the graded strip | ≤1.5 % (code 4); ≤1.75 % (code 3); ≤2 % (code 1/2) | Annex 14 §3.4.13; **CS ADR-DSN.B.180(b)** — PV-2026-08-08 | "the same as the comparable standards for the runway and stopway" ⇒ 1.5 % (AAC C/D/E), 2 % (A/B) | AC §3.16.5 item 1 — PV-PRIOR |
| Longitudinal slope CHANGE rate | **QUALITATIVE** — "should be as gradual as practicable, and abrupt changes or sudden reversals of slopes should be avoided". No number. | Annex 14 §3.4.14; **CS ADR-DSN.B.180(c)** — PV-2026-08-08 | ±2.0 % per 100 ft (30.5 m) | AC §3.16.5 item 5 — PV-PRIOR |
| Transverse slope, graded strip | "adequate to prevent the accumulation of water on the surface but should not exceed" **2.5 % (code 3/4)**, **3 % (code 1/2)**. No stated minimum. | Annex 14 §3.4.15; **CS ADR-DSN.B.185(a)** — PV-2026-08-08 | RSA side slope 1.5–5 % (AAC A/B), 1.5–3 % (AAC C/D/E) — a real **minimum** 1.5 % | AC Table 3-6 row S-3 — PV-PRIOR |
| **Pavement-edge drainage lip** | first **3 m** outward from the runway, shoulder or stopway edge **shall be negative** measured away from the runway, and **may be as great as 5 %** | Annex 14 §3.4.15 (final clause); **CS ADR-DSN.B.185(a)** — PV-2026-08-08 | 3–5 % negative for the first 10 ft (3.05 m) | AC Fig. 3-33 Detail A — PV-PRIOR |
| Strip surface abutting pavement | **shall be FLUSH** with the runway, shoulder or stopway | Annex 14 §3.4.10 (**shall** — one of the few hard SARPs here); CS ADR-DSN.B.175(c) — PV-2026-08-08 | flush, with a mandated 1.5 in ± 0.5 in edge drop-off tolerance | AC §4.14.2 item 2 / §5.9.1 — PV-PRIOR |
| Ground BEYOND the graded portion | upward slope ≤5 % measured away from the runway. **No downward mandate** — drops and open storm-water conveyances are lawful there | Annex 14 §3.4.16 + Notes 1–2; **CS ADR-DSN.B.185(b)** + GM1 — PV-2026-08-08 | ROFA back slope 8:1 (ADG I/II), 10:1 (III/IV), 16:1 (V/VI) over run D-1 | AC Table 3-7 row S-5 — PV-PRIOR; ROFA S-4 (≤0 % side slope) **does not bind** per RULINGS "ROFA exemption approved" 2026-08-02 |
| Blast-erosion preparation | that portion of the strip to at least **30 m before the start of a runway** should be prepared against blast erosion | Annex 14 §3.4.11; CS ADR-DSN.B.175(d) — PV-2026-08-08 | blast pad takes "the same grades as the safety area", flush, 1.5 in drop-off | AC §3.7.4 — PV-PRIOR |

> **FINDING F-2 (jurisdictional).** The **1.5 % transverse MINIMUM** on
> the graded strip is **FAA-only** (Table 3-6 S-3). ICAO §3.4.15 and CS
> ADR-DSN.B.185 state *no* minimum — only "adequate to prevent the
> accumulation of water" and a maximum. The repo currently carries the
> blended mandatory-DOWN band on **both** rulesets, deliberately and
> visibly (`config.py` ICAO_RULESET rows 7/8 comment: "UNTIL THE OWNER
> ANSWERS, BOTH RULESETS KEEP THE BLENDED MANDATORY-DOWN VALUES").
> That deferral is exactly OWNER QUESTION Q1 below, and the fabric model
> makes it load-bearing: under jurisdictional fidelity the ICAO-side
> graded strip would have **no mandatory fall at all**, only a 2.5 %/3 %
> ceiling and the 3 m negative lip.

> **FINDING F-3 (jurisdictional, narrower).** The **3 m negative lip** is
> stated only in the **runway-strip** clause (§3.4.15 / B.185(a)). The
> **taxiway-strip** clause (§3.11.5 / D.330(b)) has **no lip** — it
> states flush at the edge, an upward cap, and a 5 % downward cap.
> `grade_law.adjacent_ground_envelope` applies `strip_lip_*` to the
> taxiway branch as well. Under jurisdictional fidelity the ICAO taxiway
> lip is unsourced; under FAA it is sourced (TSA 1.5–5 %, §4.14.2 item 5).

---

## 3. RESA and the runway-end corridor

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Provision | **shall** where code 3/4, and where code 1/2 and the runway is instrument; recommended for code 1/2 non-instrument | Annex 14 §3.5.1–3.5.2 — PV-2026-08-08 | RSA is required at every runway end | AC §3.16.5 — PV-PRIOR |
| Length — hard floor | **shall extend from the END OF THE RUNWAY STRIP** at least **90 m** | Annex 14 §3.5.3 (**shall**); CS ADR-DSN.C.215(a)(1) — PV-2026-08-08 | the RSA extends beyond the runway end by the Appendix G "RSA length beyond runway end" for the runway design code — **the repo has never pulled that column** (only the RSA/ROFA *widths* are in `config.py`) | AC App. G tables G-1…G-12 — **NOT VERIFIED**, see §7 |
| Length — recommended | **240 m** (code 3/4); **120 m** (code 1/2 instrument); **30 m** (code 1/2 non-instrument) | Annex 14 §3.5.4; CS ADR-DSN.C.215(a) — PV-2026-08-08 | — | — |
| Width | **shall** be at least **twice the runway width**; *should*, wherever practicable, equal the **graded portion of the strip** | Annex 14 §3.5.5 (shall) / §3.5.6 (rec.); CS ADR-DSN.C.215(c) — PV-2026-08-08 | RSA width 500 ft (C/D/E), 300/150/120 ft for A/B groups | AC App. G — PV-PRIOR |
| Grading mandate | "should provide a **cleared and graded area**"; the surface "does not need to be prepared to the same quality as the runway strip" | Annex 14 §3.5.8 + Note; CS ADR-DSN.C.225 + GM1 — PV-2026-08-08 | RSA "cleared and graded", capable of supporting aircraft and ARFF | AC §3.16.5 — PV-PRIOR |
| Longitudinal slope | ≤ **5 % downward**; changes "as gradual as practicable", abrupt changes / sudden reversals avoided (no number) | Annex 14 §3.5.10; **CS ADR-DSN.C.230(a)(2)** — PV-2026-08-08 | first 200 ft (61 m) beyond the end 0 to −3 %; beyond that −5 %; grade change ±2 % per 100 ft | AC §3.16.5 items 2–5 — PV-PRIOR |
| Transverse slope | ≤ **5 % upward OR downward** — one symmetric cap, no near-zone column; transitions gradual | Annex 14 §3.5.11; **CS ADR-DSN.C.230(b)** — PV-2026-08-08 | within the first 61 m the Table 3-6 S-3 band (1.5–5 % A/B, 1.5–3 % C/D/E); Fig. 3-35 shows ±5 % across the RSA | AC §3.16.5 item 6 + Table 3-6 — PV-PRIOR |
| Surface-penetration rule | RESA slopes "should be such that **no part of the RESA penetrates the approach or take-off climb surface**" | Annex 14 §3.5.9; **CS ADR-DSN.C.230(a)(1)** — PV-2026-08-08 | equivalent constraint via the approach/departure surfaces | PV-PRIOR |

> **FINDING F-4 (anchor, material).** ICAO measures the RESA **from the
> end of the runway STRIP**, and the strip itself already runs **60 m
> beyond the runway end** (§3.4.2). So an ICAO code-3/4 RESA occupies
> 60 m…150 m (hard floor) or 60 m…300 m (recommended) beyond the runway
> end. The repo's `RUNWAY_END_CLEARANCE_LENGTH_BY_CODE =
> {1: 60, 2: 90, 3: 150, 4: 240}` is measured **from the runway end**
> (`grade_law.runway_end_governed_length_beyond_pavement_m`, user ruling
> 2026-07-09). Read as "total governed length beyond the runway end" the
> code-3 value (150 m) coincides with 60 + 90; the code-4 value (240 m)
> is 60 + 180, i.e. neither the 90 m floor nor the 240 m recommendation
> measured from the strip end. This is a **datum question, not a bug
> report** — the numbers are defensible as a blend but they are not any
> single authority's number measured the way that authority measures it.
> Jurisdictional fidelity says pick the datum per ruleset. OWNER
> QUESTION Q3. Compounding it: the **FAA RSA length-beyond-the-end
> column of Appendix G has never been pulled into the repo** —
> `FAA_RULESET` carries RSA/ROFA *widths* only, so an FAA airport's
> end-corridor LENGTH is today the ICAO-derived blend. That is a hole in
> the FAA ruleset, not a datum preference.

> **FINDING F-5 (build).** §3.5.9 / C.230(a)(1) — *no part of the RESA
> may penetrate the approach or take-off climb surface* — has **no
> implementation**. `ols.py` models the approach surface as a terrain
> **cut ceiling** but nothing binds the emitted RESA/end-skirt geometry
> to it. This is a genuine BUILD item and it is cheap: the end-skirt
> already knows its stations, and `grade_law.ols_approach_ceiling`
> already computes the ceiling.

---

## 4. Drainage

This is the section where the two authorities genuinely diverge, and
where the owner's "drainage requirements along ALL taxiways" rider lands.

### 4.1 Runway crown / transverse

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Runway transverse — form | surface **should be cambered** (centre crown), except where a single crossfall from high to low in the direction of the rain-bearing wind ensures rapid drainage; for a cambered surface the slope each side of the centre line **should be symmetrical** | Annex 14 §3.1.19; **CS ADR-DSN.B.080(b),(c)** — PV-2026-08-08 | centre crown is the ideal configuration | AC §3.16.2 — PV-PRIOR |
| Runway transverse — band | **not less than 1 %** and **not more than 1.5 %** (code letter C/D/E/F); **not less than 1 %** and **not more than 2 %** (A/B); flatter permitted **only at runway or taxiway intersections** | **CS ADR-DSN.B.080(b)(1),(2)** (EASA states the floor positively); Annex 14 §3.1.19 same numbers ("nor be less than 1 per cent except at runway or taxiway intersections") — PV-2026-08-08 | 1.0–1.5 % (AAC C/D/E); 1.0–2.0 % (AAC A/B) | AC Table 3-6 row S-1 — PV-PRIOR |
| Runway transverse — uniformity | "substantially the same throughout the length of a runway except at an intersection … where an even transition should be provided" | Annex 14 §3.1.20; CS ADR-DSN.B.080(d) — PV-2026-08-08 | — | — |

**The runway crown minimum of 1 % is real, numeric, and present in BOTH
authorities.** It is the single strongest drainage mandate in the reg
set, and the owner already bound it (RULINGS 2026-08-05, `d48bc0a`;
`config.CROWN_MINIMUM_BOUND_RUNWAYS = True`).

### 4.2 Taxiway transverse — the owner's all-taxiways rider

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Taxiway transverse | "should be **sufficient to prevent the accumulation of water** on the surface of the taxiway but should not exceed" **1.5 % (C/D/E/F)**, **2 % (A/B)**. **NO NUMERIC MINIMUM. NO CROWN MANDATE.** | Annex 14 §3.9.11; **CS ADR-DSN.D.280(b)** — PV-2026-08-08 | **1.0–1.5 %** ("the ideal configuration is a center crown"); 1–2 % permitted where the pavement serves only aeroplanes ≤30,000 lb | AC §4.14.2 item 1a — PV-PRIOR |
| Taxiway longitudinal | ≤1.5 % (C/D/E/F); ≤3 % (A/B) | Annex 14 §3.9.8; **CS ADR-DSN.D.265(b)** — PV-2026-08-08 | 1.5 % (2 % for ≤30,000 lb pavement — relaxation **not taken**, the builder does not know a taxiway's fleet) | AC §4.14.1 — PV-PRIOR |
| General drainage CS | EASA states a **safety objective only** — "minimise water depth on the surface by draining surface water off the runway in the shortest path practicable" — and its GM explicitly defers the numbers: "Slopes for the various parts of the movement area and adjacent parts are described in Chapters B to G". **No independent numeric floor anywhere.** | **CS ADR-DSN.B.191 + GM1** — PV-2026-08-08 | AC 150/5320-5D is the drainage AC; not reached this round | — |

> **FINDING F-6 (the rider is jurisdictionally asymmetric — decisive for
> the fabric model).** "Drainage requirements along all taxiways" has a
> **numeric FAA requirement** (1.0 % transverse minimum, §4.14.2 item 1a)
> and **no numeric ICAO/EASA requirement at all** — only "sufficient to
> prevent the accumulation of water" plus a ceiling. Under jurisdictional
> fidelity the rider therefore binds at KCLT and is a **no-op at SPJC,
> SPLP, CYXY and HECA**. Four of the five battery airports would emit no
> taxiway crown. Manufacturing an ICAO number would be MINTED, not cited
> — the same trap `config.py` already refuses for the ICAO apron minimum.
> OWNER QUESTION Q2.

### 4.3 Apron / stand

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Apron slopes | "should be **sufficient to prevent accumulation of water** … but should be kept **to the minimum required to facilitate effective drainage**" (EASA) / "kept as level as drainage requirements permit" (ICAO). **QUALITATIVE — no number.** | Annex 14 **§3.13.4**; **CS ADR-DSN.E.360(a)** — PV-2026-08-08 | **minimum 0.5 % apron gradient**; maximum apron grade change 2 % | AC §5.9.1 — PV-PRIOR |
| Aircraft stand maximum | ≤ **1 %** (EASA adds "**in any direction**") | Annex 14 **§3.13.5**; **CS ADR-DSN.E.360(b)** — PV-2026-08-08 | ≤1 % (recommendation) | AC §5.9.2 — PV-PRIOR |
| Apron shoulder | **NOTHING.** Neither Annex 14 §3.13 nor CS ADR-DSN Chapter E governs ground beyond an apron edge. | (absence verified by reading §3.13.1–3.13.6 / E.345–E.365 in full) — PV-2026-08-08 | 3 m (10 ft) shoulder at 1–3 % down, then 3–5 % beyond — a **RECOMMENDATION** | AC §5.9.2 — PV-PRIOR |

> **FINDING F-7 (citation drift, cosmetic but load-bearing for audits).**
> `config.py` cites "§3.13.6" for the 1 % stand maximum and "§3.13.5" for
> the qualitative apron clause. In Annex 14 **8th edition** those are
> **§3.13.5** and **§3.13.4** respectively; §3.13.6 is *Clearance
> distances on aircraft stands*. `grade_law.drainage_minimum_grade`'s
> docstring carries the same off-by-one ("ICAO §3.13.5 is qualitative").
> The **values are correct**; only the paragraph numbers are shifted by
> one, presumably from a different edition. Same class:
> `docs/STANDARDS.md` cites taxiway longitudinal as "ICAO §3.9.3 /
> Table 3-2" — in the 8th edition it is **§3.9.8**, and Table 3-1 is the
> separation-distance table (there is no slope table).

### 4.4 Shoulders

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Runway shoulder — provision | where code letter D, E or F | Annex 14 §3.2.1; CS ADR-DSN.B.125 — PV-2026-08-08 | by RDC | PV-PRIOR |
| Runway shoulder — width | overall runway+shoulders ≥60 m (D/E), 60 m (F, 2–3 engines), 75 m (F, 4+ engines), for OMGWS 9–15 m | Annex 14 §3.2.2; **CS ADR-DSN.B.135** — PV-2026-08-08 | shoulder widths by ADG; repo caps detected shoulder extent at 15 m/side | PV-PRIOR |
| Runway shoulder — slope | **flush** with the runway; transverse ≤ **2.5 %**. **No minimum.** | Annex 14 §3.2.3; **CS ADR-DSN.B.130(b)** — PV-2026-08-08 | paved shoulders **1.5–5.0 %** down; mandated paved→unpaved edge drop-off **1.5 in ± 0.5 in** | AC Table 3-6 row S-2 / §4.14.2 items 2–3 — PV-PRIOR |
| Taxiway shoulder — width | overall taxiway+shoulders ≥25 m (C), 34 m (D), 38 m (E), 44 m (F) | Annex 14 §3.10.1; **CS ADR-DSN.D.305(a)** — PV-2026-08-08 | by ADG | PV-PRIOR |
| Taxiway shoulder — slope | **no number** — §3.10 / D.305 give width, erosion resistance and strength only; the taxiway-strip clause supplies the flush edge | Annex 14 §3.10.1–3.10.2; CS ADR-DSN.D.305 — PV-2026-08-08 | TSA transverse 1.5–5 % | AC §4.14.2 item 5 — PV-PRIOR |

### 4.5 Taxiway strips

| Key | ICAO / EASA | Citation | FAA |
|-----|-------------|----------|-----|
| Graded half-width | by **OMGWS**, not code letter: 10.25 m (<4.5 m), 11 m (4.5–<6), 12.50 m (6–<9), 18.50 m (9–<15, letter **D**), 19 m (9–<15, **E**), 22 m (9–<15, **F**) | Annex 14 §3.11.4; **CS ADR-DSN.D.325(b)** — PV-2026-08-08 | TSA widths by ADG — PV-PRIOR |
| Slopes | strip surface **flush** at the taxiway/shoulder edge; graded portion **upward** transverse ≤2.5 % (C–F) / 3 % (A/B), measured against the **adjacent taxiway surface, not the horizontal**; **downward** ≤5 % measured against the **horizontal** | Annex 14 §3.11.5; **CS ADR-DSN.D.330(b)** — PV-2026-08-08 | TSA 1.5–5 % — PV-PRIOR |
| Beyond the graded portion | up **or** down ≤5 % away from the taxiway | Annex 14 §3.11.6; **CS ADR-DSN.D.330(c)** — PV-2026-08-08 | — |

> **FINDING F-8 (two measurement frames in one clause — the ICAO taxiway
> strip is not expressible today).** Annex 14 §3.11.5 and CS
> ADR-DSN.D.330(b) state, in one sentence: the graded portion's **upward**
> transverse cap (2.5 % C–F / 3 % A/B) is measured *"with reference to the
> transverse slope of the adjacent taxiway surface and **not** the
> horizontal"*, while the **downward** cap (5 %) is measured *"with
> reference to the horizontal"*. `grade_law._adjacent_strip_envelope`
> (verified by read) builds every bound as `slope × distance` off the
> pavement-EDGE elevation — one frame, the horizontal — and the taxiway
> branch encodes the FAA-blended **mandatory-down** band (1.5 %…5 %)
> instead, so the ICAO up-cap does not appear at all. Today that is
> masked: a mandatory-down band has no up side. **If Q1 answers "the ICAO
> ruleset drops the mandatory fall", the ICAO taxiway zone 2 becomes a
> genuine two-frame band that the current `_adjacent_strip_envelope`
> signature cannot express** — the up bound would need the taxiway's own
> crossfall (up to 1.5 %) added to it. Q1 and this are one change, not two.

### 4.6 Recorded, not shaped ground (for completeness)

ICAO §3.1.13 effective slope (1 %/2 %), §3.1.15 slope change, §3.1.16
curve rate, §3.1.17/§3.9.10 sight distance, §3.1.18 PVI spacing, §3.9.9
taxiway vertical curves, §3.8 radio altimeter operating area (300 m ×
±60 m, ≤2 % per 30 m — **ICAO only**, verified absent from the FAA AC by
the 2026-08-02 round). These govern PAVEMENT profile, not adjacent
ground; `config.py` already carries them with citations.

---

## 5. Mapping to existing machinery — KEEP / EXTEND / BUILD

Every row names the law function and its constant; emitter↔validator
lockstep is the repo's existing discipline (grade-law completeness
standard, RULINGS 2026-08-02) and is assumed, not re-audited here.

| # | Requirement | Machinery today | Verdict |
|---|-------------|-----------------|---------|
| R1 | Runway crown min/max (§3.1.19 / B.080 / Table 3-6 S-1) | `crown.py` (`build_crown_drop_field`, `runway_crown_drop_m`); `grade_law.runway_crown_rate`, `transverse_surface_bounds`, `transverse_minimum_binds`; `config.CROWN_MINIMUM_BOUND_RUNWAYS=True`, `RUNWAY_CROWN_TRANSVERSE=0.010`; ruleset `runway_transverse_min/max`; census `transverse` | **KEEP** |
| R2 | Runway longitudinal profile + curves + end-zone (§3.1.14–3.1.16 / B.060 / AC §3.16.1) | `pavement/runway_segments.faa_joint_solve`, `runway_regrade.py`, `runway_redistribute.py`; ruleset `runway_max_grade`, `runway_end_grade`, `runway_vertical_curve_k_m` | **KEEP** |
| R3 | Graded runway-strip FOOTPRINT (§3.4.8–3.4.9 / B.175) | `config.RUNWAY_STRIP_HALF_WIDTH_BY_CODE`, `ruleset_strip_half_width_m`, `grade_law.runway_strip_lateral_footprint_ring`, `adjacent_ground.runway_strip_lateral_zone` | **EXTEND** — add the instrument/non-instrument key (F-1); code-1 instrument = 40 m |
| R4 | Strip abeam-longitudinal cap (§3.4.13 / B.180(b) / AC §3.16.5 item 1) | `grade_law.runway_strip_max_longitudinal_slope`, `runway_strip_longitudinal_clamp`, `strip_longitudinal_law`; ruleset `strip_max_longitudinal_slope`; census `strip_longitudinal` | **KEEP** |
| R5 | Strip longitudinal grade-CHANGE rate (§3.4.14 qualitative / AC ±2 %/30.5 m) | ruleset `strip_arc_rate_per_m` (+`strip_arc_rate_provisional=True` on ICAO); census `strip_arc` | **KEEP** — ICAO side remains an operationalization of a qualitative clause; the provisional flag is correct and must survive the fabric round |
| R6 | Strip transverse graded band (§3.4.15 / B.185(a) / Table 3-6 S-3) | `grade_law.adjacent_ground_envelope` runway branch + `_adjacent_strip_envelope`; `adjacent_ground.emit_adjacent_ground_bands`; `RUNWAY_STRIP_BAND_{MIN,MAX}_DOWN_SLOPE*` | **KEEP** (this band IS the reg set) — but the mandatory-DOWN blend on the ICAO ruleset is Q1 |
| R7 | Pavement-edge lip, first 3 m negative ≤5 % (§3.4.15 final clause / B.185(a) / Fig 3-33 Detail A) | `ADJACENT_GROUND_LIP_{WIDTH_M,MIN,MAX}_DOWN_SLOPE`, consumed in `_adjacent_strip_envelope` | **EXTEND** — scope it to the RUNWAY strip on the ICAO ruleset (F-3); the taxiway-strip clause has no lip |
| R8 | Flush strip/pavement edge (§3.4.10 **shall** / B.175(c)) | `flatedge_snap.py`, `emit_snap.py`, step families + FAA-only drop-off exemption (`ruleset_shoulder_edge_dropoff`) | **KEEP** |
| R9 | Taxiway graded strip: OMGWS widths + up/down caps (§3.11.4–3.11.5 / D.325, D.330) | `TAXIWAY_STRIP_GRADED_HALF_WIDTH_BY_LETTER`, `taxiway_strip_graded_half_width_for_letter`; `adjacent_ground_envelope` taxiway branch; `_adjacent_strip_envelope` (single horizontal frame) | **EXTEND** — the ICAO up-cap is measured against the taxiway crossfall, not the horizontal, and is unexpressible today (F-8); widths are OMGWS-keyed and the repo's letter table is a proxy (document it) |
| R10 | Ungraded strip rising-ground ceiling ≤5 % up (§3.4.16, §3.11.6 / B.185(b), D.330(c)) | `ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE`, zone-3 of `_adjacent_strip_envelope`; FAA `rofa_back_slope_ceiling` | **KEEP** — note it is a **ceiling (cut)**, never a mandate to shape; it must not mint fill under the fabric model |
| R11 | RESA extent — length + width (§3.5.3–3.5.6 / C.215) | `config.RUNWAY_END_CLEARANCE_LENGTH_BY_CODE`, `grade_law.runway_end_governed_length_m` / `…_beyond_pavement_m`, `runway_end_corridor_half_width_m` | **EXTEND** — per-ruleset datum + the ≥2× runway-width / graded-strip-width rule (F-4, Q3) |
| R12 | RESA longitudinal ≤5 % down (+ FAA 0–3 % near zone) (§3.5.10 / C.230(a)(2) / AC §3.16.5) | `grade_law.runway_end_skirt_law`, `runway_end_skirt_floor_profile*`, `runway_end_envelope`; `RUNWAY_END_RESA_MAX_SLOPE=0.05`; census `runway_end_skirt` | **KEEP** |
| R13 | RESA transverse ≤5 % (ICAO symmetric) / FAA near-zone S-3 band (§3.5.11 / C.230(b)) | `grade_law.resa_transverse_band/_envelope/_clamp`; ruleset `resa_transverse_near*`, `resa_transverse_max`; census `resa_transverse` | **KEEP** |
| R14 | RESA must not penetrate the approach / take-off climb surface (§3.5.9 / C.230(a)(1)) | **nothing** — `ols.py` cuts terrain to the approach surface but nothing bounds the emitted end-skirt against it | **BUILD** (cheap: `grade_law.ols_approach_ceiling` already exists) |
| R15 | Blast-pad / stopway grade inheritance (§3.4.11 / B.175(d) / AC §3.7.4) | blast pad is a skirt anchor/constraint only (gap audit GAP 5) | **BUILD** |
| R16 | Runway shoulder flush + transverse band (§3.2.3 / B.130 / Table 3-6 S-2) | `ruleset_shoulder_transverse_band`, `shoulder_edge_dropoff*`, `RUNWAY_SHOULDER_EXTENT_MAX_M`, `pavement/runways._detect_runway_shoulder_extent`, shoulder sub-band in `adjacent_ground_envelope` | **KEEP** |
| R17 | Taxiway shoulder (width/erosion only; no slope number) (§3.10 / D.305) | rides the taxiway-strip band | **KEEP** (no-op by design) |
| R18 | Apron drainage minimum — FAA 0.5 %, ICAO none (§5.9.1 / §3.13.4 / E.360(a)) | `grade_law.drainage_minimum_grade/_band/_shortfall`; ruleset `apron_min_drainage_grade` (FAA 0.005, ICAO `None`); census `drainage_minimum` | **KEEP** — remains **VERSION-DEFERRED** by RULINGS 2026-08-05 §3 |
| R19 | Aircraft-stand maximum 1 % (§3.13.5 / E.360(b) / AC §5.9.2) | `ruleset_stand_max_grade`, `ROLE_GRADE_LIMITS["stand"]`, apron split into `ROLE_STAND` pads | **KEEP** — fix the ICAO paragraph number (F-7) |
| R20 | Taxiway transverse — the all-taxiways drainage rider (§3.9.11 / D.280 / AC §4.14.2 1a) | ruleset `taxi_transverse_max` binds; `taxi_transverse_min` **recorded, not bound** (`CROWN_MINIMUM_BOUND_TAXIWAYS=False`); `TAXI_CROWN_TRANSVERSE=0.010` exists but unbound | **EXTEND** — flipping the FAA side is one line (`transverse_minimum_binds`); the ICAO side has no number to bind (F-6, Q2) |
| R21 | Radio altimeter operating area — ICAO only (§3.8 / B.205) | `grade_law.raoa_footprint_ring`, `raoa_applies`, `raoa_rate_clamp`; census `raoa` | **KEEP** |
| R22 | ROFA back slope — FAA only (Table 3-7 S-5) | `grade_law.rofa_back_slope_ceiling`, ruleset `rofa_back_slope_*` | **KEEP** |
| R23 | OFZ | **nothing to build** — clearance volume, not shaped ground (§1 item 4) | **KEEP-AS-NOTHING** (record the negative so it is not re-litigated) |

**Counts: KEEP 15 · EXTEND 5 · BUILD 2 · KEEP-AS-NOTHING 1** (23 rows).

### 5.1 RETIRE — machinery no standard requires

The fabric model's §4 is "unregulated ground: NOTHING". Everything below
exists today, shapes ground, and has **no requirement behind it** in
either authority. Each needs a twin proving the successor behaviour
(fabric-model-spec.md Retire list).

| # | Machinery | Why it is not in the reg set |
|---|-----------|------------------------------|
| T1 | Fan zones / apron fan ramps — `elevation_per_surface/route_profile/apron_terrace.split_aprons_at_fan_zones`, its `FanRampPlan`, and the `layout.py` / `grade_graph.py` consumers | Owner: "RETIRE OUTRIGHT" (RULINGS 2026-08-08 §1); no standard mentions apron fans |
| T2 | Apron shoulder band — `APRON_SHOULDER_WIDTH_M`, `APRON_SHOULDER_{MIN,MAX}_DOWN_SLOPE` | FAA §5.9.2 is a **recommendation**; Annex 14 §3.13 and CS ADR-DSN Ch. E govern **nothing** beyond an apron edge (verified by full read) — RETIRE-CANDIDATE, Q4 |
| T3 | Apron beyond-shoulder fill target — `APRON_BEYOND_SHOULDER_{MIN,MAX}_DOWN_SLOPE` | same FAA recommendation, one band further out; already documented in `STANDARDS.md` as "a render target, not a corridor" — RETIRE-CANDIDATE, Q4 |
| T4 | Apron edge retaining-wall family — `APRON_EDGE_WALL_MIN_DROP_M`, `APRON_WALL_RUN_HYSTERESIS_M`, `APRON_WALL_MIN_RUN_M`, `APRON_WALL_MIN_AREA_M2`, `APRON_WALL_PAVEMENT_ADJACENCY_M` | pure design (2026-07-25 scoping ruling already narrowed it because "no code mandates grading beyond an apron edge"); under the drape model the raw DEM meets the apron edge — RETIRE-CANDIDATE, Q4 |
| T5 | Service-road roadside clearance band — `CLEARANCE_MAX_REACH_M["service"]` 15 m cut-only shadow | `STANDARDS.md` states it outright: "**design choice, NOT an AASHTO mandate**"; no aviation authority regulates service roads |
| T6 | Adjacent-ground daylight slope limit — `ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT`, `grade_law.adjacent_ground_supported_depths` | "engineering judgment — **NO external citation**" (its own STANDARDS.md row). It exists to keep dense emitted bands from knife-slotting; sparse emission removes the failure mode it patches |
| T7 | Flat lateral clearance shadow — `CLEARANCE_LATERAL_MAX_SLOPE = 0`, `clearance.emit_surface_clearance_cuts` Pass A3 beyond the strip footprints | design; the regulated ceilings are §3.4.16/§3.11.6 (R10) and the FAA ROFA back slope (R22), both already modelled |
| T8 | Stationing density beyond the adequate spine/curve floor; the census relief vocabulary and its exemptions | fabric-model-spec.md Retire list — no standard specifies vertex density |

**RETIRE: 8 items** (T2–T4 are RETIRE-CANDIDATE pending Q4).

### 5.2 Not retired, not in the reg set — the OLS cut law

`ols.py` (transitional + approach first section) is a **cut ceiling on
terrain**, and `docs/STANDARDS.md` already states its charter honestly:
"The codes forbid new obstacles above it … they do **not** mandate
grading terrain down to it. Cutting terrain to it is therefore a
deliberate scenery-repair reinterpretation." It shapes no ground the
standards require, but it also emits no fill. It is out of scope for the
fabric model's reg set and untouched by it. Flagged so a future reader
does not read its absence from §5 as a retirement.

---

## 6. Owner questions (only the owner can answer these)

**Q1 — the mandatory-DOWN blend on the ICAO ruleset.** ICAO §3.4.15 /
CS ADR-DSN.B.185 state **no minimum** transverse fall on the graded
runway strip; the 1.5 % minimum is FAA Table 3-6 S-3. The repo currently
applies the FAA mandatory-DOWN band on **both** rulesets, visibly
deferred (`config.py` rows 7/8). Jurisdictional fidelity says the ICAO
graded strip has only a ceiling (2.5 %/3 %) plus the 3 m negative lip.
Does the ICAO ruleset drop the mandatory fall? *(This decides whether
graded-strip bands are emitted at all at SPJC/SPLP/CYXY/HECA.)*

**Q2 — "drainage along all taxiways" under jurisdictional fidelity.**
The FAA gives a 1.0 % taxiway transverse **minimum**; ICAO/EASA give
none, only "sufficient to prevent the accumulation of water" and a
1.5 %/2 % ceiling. Three readings: (a) bind the FAA minimum, ICAO taxiways
stay flat-lawful (strict fidelity — four of five battery airports emit no
taxiway crown); (b) bind a repo-chosen 1.0 % on both, flagged
PROVISIONAL like `GROUNDSIDE_MIN_DRAINAGE_GRADE`; (c) treat the ICAO
qualitative clause as satisfied by any non-zero cross-fall the solve
already produces. Which?

**Q3 — the RESA datum, per ruleset.** ICAO measures RESA from the **end
of the strip** (itself 60 m beyond the runway end): floor 90 m,
recommended 240 m. The repo measures a single governed length from the
**runway end** (60/90/150/240 by code). Adopt the ICAO datum on the ICAO
ruleset (60 m strip + RESA), and the FAA RSA-beyond-end datum on the FAA
ruleset? And take the ICAO **shall** (90 m) or the **recommendation**
(240 m) as the governed length?

**Q4 — the apron surround.** No authority requires any grading beyond an
apron edge; the FAA's 3 m at 1–3 % and 3–5 % beyond are
**recommendations**. Under "unregulated ground: NOTHING", do the apron
shoulder band, the beyond-shoulder target and the apron-edge retaining
wall family (T2/T3/T4) retire outright, or does the FAA recommendation
survive as reg set on the FAA ruleset only?

**Q5 — the wider precision-approach graded strip.** Annex 14 §3.4.8 Note
+ Att. A §9 and EASA GM1 ADR-DSN.B.175 Fig. GM-B-4 describe a **105 m**
graded half-width (tapering to 75 m over the last 150 m) for precision
approach code 3/4 runways. It is **guidance**, not a specification.
Adopt (wider shaped ground at HECA/KCLT/SPJC) or record-only?

---

## 7. Standing flags

* **FAA AC 150/5300-13B is unreachable from this toolchain**
  (`faa.gov` 403; archive.org not fetchable; mirrors dead). Every FAA row
  above is PV-PRIOR, not re-verified. Before the reg-set implementation
  lands, someone with a browser should re-read §3.16, §3.16.5, Table 3-6,
  Table 3-7, Fig 3-33/3-35, §4.14, §5.9 and Appendix G against this
  document — particularly because **Change 1 was signed 16 Aug 2024**,
  after several of the repo's citation rounds.
* **ICAO paragraph numbers are 8th-edition (2018).** F-7's off-by-one in
  `config.py` / `grade_law.py` / `STANDARDS.md` suggests some citations
  were taken against a different edition. Values check out; numbers need
  a sweep.
* **Extracted primary texts** used for this round live in
  `Ortho4XP/tmp/regset/` (`annex14.txt`, `cs-adr-dsn.txt`) — lane-local
  scratch, not committed.
