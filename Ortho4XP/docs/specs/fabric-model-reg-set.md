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

Research only. **No code has been changed by either round** — nothing in
`config.py`, the rulesets or `grade_law.py` was touched, including where
this document now records a value as DISCREPANT.

**Revision history.**

* **2026-08-08 (round 1)** — ICAO Annex 14 8th ed. and EASA CS-ADR-DSN
  Issue 7 read in full; FAA rows carried from earlier repo rounds
  because `faa.gov` was 403-blocked to every fetch path. 23 mapped rows,
  8 findings, 5 owner questions.
* **2026-08-08 (round 2, this revision)** — the owner supplied
  AC 150/5300-13B Chg 1 (consolidated, with errata) and the 2025-04-03
  errata sheet into `regs/`, executing the provenance contract in
  `regs/README.md`. **Every FAA row primary-verified against the AC's own
  text**; the missing Appendix G RSA length-beyond-end column pulled
  (§3.1); the errata mapped row-by-row (§0.1); four DISCREPANT marks and
  one new requirement row (R24) raised; all five owner questions closed
  by the RULINGS entries of the same date.

---

## 0. Sources and verification status

| # | Source | Edition read | Reached? | Status |
|---|--------|--------------|----------|--------|
| S1 | ICAO Annex 14 Vol I, *Aerodrome Design and Operations* | **Eighth Edition, July 2018** (supersedes all previous on 8 Nov 2018; incl. Amdt 14) | YES — full text read | **PRIMARY-VERIFIED 2026-08-08** |
| S2 | EASA CS-ADR-DSN (*Certification Specifications and Guidance Material for Aerodrome Design*) | **Issue 7, 16 May 2025**, Annex to ED Decision 2025/004/R (326 pp) | YES — full text read | **PRIMARY-VERIFIED 2026-08-08** |
| S3 | FAA AC 150/5300-13B *Airport Design* w/ Chg 1 (Chg 1 signed 16 Aug 2024) | **13B + Chg 1, consolidated "with errata" PDF, 413 pp** — `regs/AC-150-5300-13B-Airport-Design-Chg1-w-errata.pdf` (owner-supplied 2026-08-08 after the automated fetch was 403-blocked) | YES — §1.2.1, §3.7.3–3.7.4, §3.10, §3.11 def., §3.12, §3.16.1–3.16.6, Tables 3-6/3-7, Figures 3-33/3-34/3-35, §4.5.3, Tables 4-1/4-2, §4.13, §4.14.1–4.14.3, Figure 4-29, §5.9–5.10, **Appendix G Tables G-1…G-12 + footnotes 1–14** read | **PRIMARY-VERIFIED 2026-08-08** |
| S3e | FAA errata sheet for AC 150/5300-13B Chg 1 | **4 Mar→3 Apr 2025 sheet, 11 items** — `regs/errata-AC-150-5300-13B-Airport-Design-Chg1-2025-04-03.pdf` | YES — full sheet read | **PRIMARY-VERIFIED 2026-08-08.** All 11 items already incorporated in the S3 PDF (confirmed in situ: errata #7's "Notice to Airmen" wording is present at §3.16.4 Design Considerations item 5). **No errata item touches any value in this document** — see §0.1 |
| S4 | FAA AC 150/5320-5D *Airport Drainage Design* | — | NO (`faa.gov` fetch block; not owner-supplied) | NOT REACHED — no value in this document depends on it |

Verification legend used in every table below:

* **PV-2026-08-08** — the authority's own words were read this round
  (S1/S2 on 2026-08-08 morning; S3/S3e on 2026-08-08 from the in-repo
  PDFs). **Every row in this document is now PV-2026-08-08.**
* **DISCREPANT** — the primary text disagrees with a value or key this
  repo carried. Both are shown; nothing was silently corrected. Four
  rows carry this mark (F-9, F-10, F-11 and the taxiway-shoulder-width
  key); none of them is a wrong *number* on a runway surface.
* **SECONDARY** — value known only from a summary. *(No row is
  SECONDARY.)*
* **PV-PRIOR** — retired 2026-08-08. It formerly marked FAA rows carried
  from earlier repo rounds while `faa.gov` was unreachable; the owner
  supplying the AC closed that gap. No row uses it any more.

### 0.1 Errata applicability (S3e), per row of this document

The 2025-04-03 errata sheet lists 11 corrections. Mapped against the
surfaces this reg set uses — strips, RSA, drainage, shoulders — **the
applicability is zero**:

| Errata # | Location | Touches our reg set? |
|---|---|---|
| 1 | ¶4.2 ("widest TDG" → "widest MGW") | No — TDG determination, no graded surface |
| 2 | ¶D.1.4 (EAT visual screen) | No — Appendix D |
| 3 | Figure 4-15 note (→ ¶4.7.2) | No — fillet geometry |
| 4 | Appendix D (V1 label → CL) | No |
| 5 | Table L-1 ("IV" → "VI", 550 column) | No — approach reference codes |
| 6 | ¶J.4.3 item 3 (added "m") | No — fillet dimensions |
| 7 | ¶3.16.4.2 ("Notice to Air Missions" → "Notice to Airmen") | **Inside §3.16**, but wording only — zero dimensional effect. Used as the in-situ proof that the repo's PDF is the corrected consolidation |
| 8 | Figures 4-25 & 4-26 geometry | No — holding-bay plan geometry |
| 9 | ¶4.3.5.1 item 2c (entrance-taxiway reorientation) | No — plan geometry |
| 10 | ¶4.3.5.2 item 2c deleted (holding position) | No — plan geometry |
| 11 | ¶4.7.1/4.7.2 subparagraph move | No — fillets |

**Consequence for the repo:** no ruleset constant changes because of the
errata, and no row of this table needed a Chg-1-era re-derivation. The
worry recorded in the previous revision of §7 — that Chg 1 (16 Aug 2024)
post-dated several citation rounds — is **discharged**: the Chg-1 text
was read directly and the values below are Chg-1 values.

### 0.2 The AC's own normative hierarchy (§1.2.1) — load-bearing here

The AC distinguishes four levels, and this document's KEEP/RETIRE calls
depend on which one a clause sits under:

* **Standard** — "A physical characteristic, quality, configuration,
  function, operation, or procedure established by the FAA as a
  benchmark…" (¶1.2.1, p. 1-1).
* **Recommended Practice** — "Supplemental measures and guidelines the
  FAA recognizes as promoting safety, capacity, or efficiency. An
  airport has the discretion to implement a recommended practice…"
* **Requirement** — reserved for obligations originating in federal
  statute or regulation; the AC states it "does not establish or modify
  any statutory or regulatory requirements".
* **Design Consideration** — factors that may influence application.

So the FAA analogue of ICAO's *shall* / *should* split is
**Standard** / **Recommended Practice**, and it is printed as a heading
above every clause. Every FAA row below now names which heading its
value sits under. This is what makes the apron-surround retirement
(RULINGS 2026-08-08 reg-set ruling 4) primary-sourced rather than
inferred: §5.9.2's apron shoulder sits under *Recommended Practices*,
verified by read.

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
   **The FAA agrees in its own words**, now primary-verified: "The OFZ
   is the three-dimensional airspace along the runway and extended
   runway centerline that is clear of obstacles for the protection of
   aircraft landing or taking off from the runway and for missed
   approaches. The OFZ consists of four distinct surfaces: Runway OFZ,
   Precision OFZ, Inner-Transitional OFZ, and the Inner-Approach OFZ."
   (AC 150/5300-13B ¶1.5 Definitions #69, p. 1-9 — PV-2026-08-08). Every
   Appendix G table likewise refuses to give the OFZ a dimension,
   deferring to ¶3.11. Its ground floor inside the strip is already
   governed by the strip grading law (§2). **The OFZ adds no
   shaped-ground requirement and the fabric model builds nothing for
   it — on either ruleset.** The same reading applies
   to the whole obstacle-limitation family (Annex 14 Ch. 4): those are
   surfaces above which objects must not stand, and the repo's OLS cut
   law already documents itself as a deliberate scenery reinterpretation,
   not a regulatory grading mandate (`docs/STANDARDS.md` §OLS).

---

## 2. Runway strips

### 2.1 Footprint — how far the shaped ground extends

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Strip extends BEYOND runway/stopway end | 60 m (code 2, 3, 4; and code 1 instrument); 30 m (code 1 non-instrument) | Annex 14 §3.4.2 (**shall**); CS ADR-DSN.B.155 — PV-2026-08-08 | FAA has no separate "strip"; the RSA itself extends beyond the end, by an Appendix G length that is **per-end** and keyed to approach equipage — see §3.1 | AC §3.10.1 *Dimensions* + App. G (dims **R**, **P**), fn 9/11 — **PV-2026-08-08** |
| Strip lateral half-width (**full** strip, precision approach) | 140 m (code 3/4); 70 m (code 1/2) | Annex 14 §3.4.3 (**shall**, "wherever practicable") — PV-2026-08-08 | n/a (ROFA is the FAA analogue): ROFA width **Q** = 250/400 ft (A/B-I), 500 ft (A/B-II), 800 ft (all others), 800 ft whenever visibility is lower than 3/4 mile | AC App. G G-1…G-12 row *ROFA Width* — **PV-2026-08-08** |
| Strip lateral half-width (non-precision approach) | 140 m (3/4); 70 m (1/2) | Annex 14 §3.4.4 (rec.) — PV-2026-08-08 | n/a | — |
| Strip lateral half-width (non-instrument) | 75 m (3/4); 40 m (2); 30 m (1) | Annex 14 §3.4.5 (rec.) — PV-2026-08-08 | n/a | — |
| **GRADED portion half-width — instrument runway** | **75 m (code 3/4); 40 m (code 1/2)** | Annex 14 §3.4.8; **CS ADR-DSN.B.175(a)** — PV-2026-08-08 | RSA **width C**, halved: 18.3 m (A/B-I, 120 ft), 22.9 m (A/B-II, 150 ft), 45.7 m (A/B-III, 300 ft), 76.2 m (A/B-IV and **all** C/D/E, 500 ft). **Second key: visibility minimums.** Lower than 3/4 mile raises A/B-I→300 ft, A/B-II→300 ft, A/B-III→400 ft (C/D/E unchanged at 500 ft) | AC App. G G-1…G-12 row *RSA Width* (dim **C**), **Standards** via §3.10.1 *Dimensions* — **PV-2026-08-08**; fn 13: where 500 ft "is not practical", 400 ft is permissible (C/D/E-I and C/D/E-II only) |
| **GRADED portion half-width — non-instrument runway** | **75 m (3/4); 40 m (2); 30 m (1)** | Annex 14 §3.4.9; **CS ADR-DSN.B.175(b)** — PV-2026-08-08 | as above (the FAA table is keyed by AAC×ADG×visibility, not by instrument/non-instrument) | **PV-2026-08-08** |
| Wider graded strip, precision approach code 3/4 | 105 m, tapering to 75 m over the last 150 m at each end — **GUIDANCE ONLY in the source; ADOPTED AS LAW IN BOTH RULESETS** by RULINGS 2026-08-08 (reg-set Q5) | Annex 14 §3.4.8 Note + Att. A §9; EASA GM1 ADR-DSN.B.175(a) Fig. GM-B-4 — PV-2026-08-08 | **no FAA equivalent.** The AC's RSA width is a flat 500 ft (76.2 m half-width) for every C/D/E code and does **not** widen for a precision approach; the only visibility-driven widening is in the A/B families (F-9). So the adopted 105 m half-width **exceeds the FAA RSA half-width (76.2 m) by 28.8 m** and lands inside the ROFA (800 ft ⇒ 121.9 m half-width). On the FAA ruleset it is therefore a deliberate scenery choice sitting on top of a Standard, not a citation — flag it as such wherever it is encoded | AC App. G rows *RSA Width* / *ROFA Width* — PV-2026-08-08 |

> **FINDING F-1 (defect, small).** The repo's
> `RUNWAY_STRIP_HALF_WIDTH_BY_CODE = {1: 30, 2: 40, 3: 75, 4: 75}` is the
> **non-instrument** table (§3.4.9). For an **instrument** runway ICAO
> §3.4.8 / CS ADR-DSN.B.175(a) gives **40 m at code 1**, not 30 m. The
> graded-strip width must be keyed by *(code number, instrument
> /non-instrument)*, not by code number alone. Affects code-1 instrument
> runways only — none in the current five-airport battery, so it is a
> correctness fix, not a battery mover.

> **FINDING F-9 (DISCREPANT — applicability keys, FAA side).** The
> repo's FAA RSA half-widths (18.3 / 22.9 / 76.2 m) are **correct
> numbers read off the wrong-sized table**. Appendix G is keyed on
> **three** axes — AAC group (A/B vs C/D/E) × ADG (I…VI) × **visibility
> minimums** (Visual / not lower than 1 mile / not lower than 3/4 mile /
> lower than 3/4 mile) — and the repo carries a single column.
> Two consequences, both primary-verified this round:
> 1. **Two rows are missing entirely**: A/B-III is 300 ft (45.7 m
>    half-width) and A/B-IV is 500 ft (76.2 m). The repo's three-value
>    table collapses A/B to two entries.
> 2. **The visibility axis is absent**: at *lower than 3/4 mile*
>    minimums the RSA widens to 300 ft for A/B-I **and** A/B-II and to
>    400 ft for A/B-III. The C/D/E families are flat at 500 ft across
>    all four visibility columns, which is why the omission has never
>    shown at KCLT.
> Carried value: RSA half-width by RDC {A/B-I: 18.3, A/B-II: 22.9,
> C/D/E: 76.2}. AC value: a 12-table × 4-column matrix, tabulated in
> §3.1. Nothing was changed in `config.py` by this round.

### 2.2 Slopes on the graded strip

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Longitudinal slope of the graded strip | ≤1.5 % (code 4); ≤1.75 % (code 3); ≤2 % (code 1/2) | Annex 14 §3.4.13; **CS ADR-DSN.B.180(b)** — PV-2026-08-08 | *Standard.* "Longitudinal grades, longitudinal grade changes, vertical curves, and distance between changes in grades for that part of the RSA between the runway ends are the same as the comparable standards for the runway and stopway" ⇒ **±1.50 % (AAC C/D/E)**, **±2.0 % (A/B)**. **Rider now carried through**: for C/D/E the runway standard *also* forbids grades beyond ±0.80 % in the first and last quarter (or first/last 2,500 ft (762 m), whichever is less), so the same restriction rides into the RSA abeam those thirds | AC ¶3.16.5 *Standards* item 1 (p. 3-62), resolving through ¶3.16.1 items 1–2 (pp. 3-55, 3-56) — **PV-2026-08-08** |
| Longitudinal slope CHANGE rate | **QUALITATIVE** — "should be as gradual as practicable, and abrupt changes or sudden reversals of slopes should be avoided". No number. | Annex 14 §3.4.14; **CS ADR-DSN.B.180(c)** — PV-2026-08-08 | *Standard.* "Limitations on longitudinal grade changes are ±2.0 percent per 100 feet (30.5 m)" | AC ¶3.16.5 *Standards* item 5 (p. 3-62), also Figure 3-35 note — **PV-2026-08-08**, verbatim |
| Transverse slope, graded strip | "adequate to prevent the accumulation of water on the surface but should not exceed" **2.5 % (code 3/4)**, **3 % (code 1/2)**. No stated minimum. | Annex 14 §3.4.15; **CS ADR-DSN.B.185(a)** — PV-2026-08-08 | *Standard.* RSA side slope **S-3** = **1.5 %–5.0 % (AAC-A, AAC-B)**, **1.5 %–3.0 % (AAC-C, D, E)** — a real **minimum** of 1.5 %. Applies "along the runway up to 200 feet (61 m) beyond the runway end"; beyond that Figure 3-35 caps transverse at **±5.0 %** | AC Table 3-6 row **S-3** (p. 3-60) + ¶3.16.5 item 6 + Figure 3-35 — **PV-2026-08-08**, exact |
| **Pavement-edge drainage lip** | first **3 m** outward from the runway, shoulder or stopway edge **shall be negative** measured away from the runway, and **may be as great as 5 %** | Annex 14 §3.4.15 (final clause); **CS ADR-DSN.B.185(a)** — PV-2026-08-08 | *Standard (figure note).* "Maintain between a 3% -5% negative grade for 10 ft (3 m) of unpaved surface adjacent to the paved surface." **Runway only** — the taxiway lip is a different band, see §4.5 and F-10 | AC Figure 3-33 **Detail A**, note 2 (p. 3-57) — **PV-2026-08-08**, verbatim |
| Strip surface abutting pavement | **shall be FLUSH** with the runway, shoulder or stopway | Annex 14 §3.4.10 (**shall** — one of the few hard SARPs here); CS ADR-DSN.B.175(c) — PV-2026-08-08 | *Standard.* Paved shoulder "flush with the runway pavement"; then "Design a 1.5-inch (38 mm) drop-off with a ±1/2-inch (13 mm) tolerance from the edge of the pavement to the adjacent unpaved areas to enhance drainage off the pavement." So the FAA "flush" datum is the **paved** edge and the drop-off applies at the **paved→unpaved** transition | AC ¶3.7.3 *Standards* items 2c and 4a (pp. 3-20, 3-21) + Figure 3-33 Detail A note 1 — **PV-2026-08-08**. *(The previous citation, "§4.14.2 item 2 / §5.9.1", pointed at the taxiway and apron drop-offs; same value, wrong surface — see F-11.)* |
| Ground BEYOND the graded portion | upward slope ≤5 % measured away from the runway. **No downward mandate** — drops and open storm-water conveyances are lawful there | Annex 14 §3.4.16 + Notes 1–2; **CS ADR-DSN.B.185(b)** + GM1 — PV-2026-08-08 | *Standard.* OFA back slope **S-5** = 8:1 (ADG-I, II), 10:1 (III, IV), 16:1 (V, VI), applied over run **D-1** = 25/40/59/86/107/131 ft (7.6/12.2/18.0/26.2/32.6/39.9 m) for ADG-I…VI. Table note: S-5 and D-1 "represent values for an acceptable back slope on the far side of the ROFA that provides adequate wingtip clearance" | AC Table 3-7 rows **S-5**, **D-1** (p. 3-61) — **PV-2026-08-08**, exact. ROFA S-4 (≤0 %, "negative … to facilitate surface water drainage away from the RSA") **does not bind** per RULINGS "ROFA exemption approved" 2026-08-02; the AC itself carries a matching relief at ¶3.12.1 item 4d — for existing runways a positive ROFA grade lateral to the RSA is permissible "provided there is adequate drainage of the RSA" |
| Blast-erosion preparation | that portion of the strip to at least **30 m before the start of a runway** should be prepared against blast erosion | Annex 14 §3.4.11; CS ADR-DSN.B.175(d) — PV-2026-08-08 | *Standard.* Blast pad "Design to the same longitudinal and transverse grades as the safety area"; "Design the blast pad to be flush with the runway pavement"; 1.5 in (38 mm) ±1/2 in (13 mm) drop-off at the unpaved edge. Blast-pad **length** (Appendix G, all visibility columns): 60 ft (A/B-I small aircraft), 100 ft (A/B-I, C/D/E-I), 150 ft (A/B-II incl. small, C/D/E-II), 200 ft (A/B-III, A/B-IV, C/D/E-III, C/D/E-IV), 400 ft (C/D/E-V, C/D/E-VI) | AC ¶3.7.4 *Standards* items 4, 6a, 6b (pp. 3-21, 3-22) + App. G row *Blast Pad Length* — **PV-2026-08-08** |

> **FINDING F-2 (jurisdictional).** The **1.5 % transverse MINIMUM** on
> the graded strip is **FAA-only** (Table 3-6 S-3). ICAO §3.4.15 and CS
> ADR-DSN.B.185 state *no* minimum — only "adequate to prevent the
> accumulation of water" and a maximum. The repo currently carries the
> blended mandatory-DOWN band on **both** rulesets, deliberately and
> visibly (`config.py` ICAO_RULESET rows 7/8 comment: "UNTIL THE OWNER
> ANSWERS, BOTH RULESETS KEEP THE BLENDED MANDATORY-DOWN VALUES").
> That deferral was exactly OWNER QUESTION Q1 below — **answered
> 2026-08-08: the ICAO ruleset DROPS the mandatory fall, flagged
> PROVISIONAL** — and the fabric model
> makes it load-bearing: under jurisdictional fidelity the ICAO-side
> graded strip would have **no mandatory fall at all**, only a 2.5 %/3 %
> ceiling and the 3 m negative lip.

> **FINDING F-3 (jurisdictional, narrower) — REVISED 2026-08-08 after the
> primary FAA read.** The **3 m negative lip** is stated only in the
> **runway-strip** clause (§3.4.15 / B.185(a)). The **taxiway-strip**
> clause (§3.11.5 / D.330(b)) has **no lip** — it states flush at the
> edge, an upward cap, and a 5 % downward cap.
> `grade_law.adjacent_ground_envelope` applies `strip_lip_*` to the
> taxiway branch as well. Under jurisdictional fidelity the **ICAO**
> taxiway lip is unsourced — that half of F-3 stands.
> **What the FAA read changes:** the previous revision said the FAA
> taxiway lip was "sourced (TSA 1.5–5 %, §4.14.2 item 5)". It is sourced,
> but **not by that clause and not at that band** — ¶4.14.2 *Standards*
> item 4 states its own lip, at **5 ±0.5 %** over the first 10 ft (3 m),
> and item 5 explicitly subtracts it from the TSA band ("except as noted
> in subparagraph 4 above"). So the FAA has **two different lips**: 3–5 %
> at a runway edge, 4.5–5.5 % at a taxiway/apron edge. See **F-10**.

---

## 3. RESA and the runway-end corridor

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Provision | **shall** where code 3/4, and where code 1/2 and the runway is instrument; recommended for code 1/2 non-instrument | Annex 14 §3.5.1–3.5.2 — PV-2026-08-08 | *Standard.* An RSA is provided at every runway end and its dimensions are **non-waivable**: "the FAA will not consider a modification of standard to address non-standard RSA dimensions. RSA dimensional standards remain in effect regardless of the presence of natural objects, man-made objects, or surface conditions…" | AC ¶3.10.1 *Location* / *Dimensions* (p. 3-36) + ¶3.10.2.1 (p. 3-37) — **PV-2026-08-08** |
| Length — hard floor | **shall extend from the END OF THE RUNWAY STRIP** at least **90 m** | Annex 14 §3.5.3 (**shall**); CS ADR-DSN.C.215(a)(1) — PV-2026-08-08 | **PULLED THIS ROUND — see §3.1.** Appendix G dim **R** *RSA length beyond departure end* and dim **P** *RSA length prior to threshold*; 240–1,000 ft depending on AAC×ADG×visibility, applied **per runway end** | AC App. G Tables G-1…G-12 + footnotes 9, 10, 11 (p. G-13) — **PV-2026-08-08** |
| Length — recommended | **240 m** (code 3/4); **120 m** (code 1/2 instrument); **30 m** (code 1/2 non-instrument) | Annex 14 §3.5.4; CS ADR-DSN.C.215(a) — PV-2026-08-08 | the FAA publishes no separate "recommended" length — Appendix G values are *Standards* (§0.2), and the only relief is footnote 10 (shortening to the length an EMAS installation requires) | AC App. G fn 10 — **PV-2026-08-08** |
| **Length — DATUM** | measured from the **end of the runway strip** (itself 60 m past the runway end) | Annex 14 §3.5.3 — PV-2026-08-08 | measured from the **runway end**, or from the **stopway end where a stopway is present**: "The RSA length beyond the runway end begins at the runway end when a stopway is not present. When a stopway is present, the length begins at the stopway end." | AC App. G **footnote 9** (p. G-13) — **PV-2026-08-08**, verbatim. *This settles the FAA half of RULINGS reg-set ruling 3.* |
| Width | **shall** be at least **twice the runway width**; *should*, wherever practicable, equal the **graded portion of the strip** | Annex 14 §3.5.5 (shall) / §3.5.6 (rec.); CS ADR-DSN.C.215(c) — PV-2026-08-08 | dim **C**: 120 ft (A/B-I), 150 ft (A/B-II), 300 ft (A/B-III), 500 ft (A/B-IV and all C/D/E); widened to 300/300/400 ft for A/B-I/II/III at visibility lower than 3/4 mile. fn 13: 400 ft permissible for C/D/E-I and C/D/E-II where 500 ft "is not practical" | AC App. G row *RSA Width* + fn 13 — **PV-2026-08-08**. Previous revision's "300/150/120 ft for A/B groups" omitted A/B-IV = 500 ft — see F-9 |
| Grading mandate | "should provide a **cleared and graded area**"; the surface "does not need to be prepared to the same quality as the runway strip" | Annex 14 §3.5.8 + Note; CS ADR-DSN.C.225 + GM1 — PV-2026-08-08 | *Standard.* Provide an RSA that is "Cleared and graded with no potentially hazardous ruts, humps, depressions, or other surface variations"; "Drained by grading or storm sewers to prevent water accumulation"; capable under dry conditions of supporting SRE/ARFF and occasional aircraft passage; and "Graded to the longitudinal and transverse grades in paragraph 3.16.5" | AC ¶3.10.1 *Grading* items 1–4 (p. 3-36) — **PV-2026-08-08**. *(Previous citation "§3.16.5" gave the grades but not the grading mandate.)* |
| Longitudinal slope | ≤ **5 % downward**; changes "as gradual as practicable", abrupt changes / sudden reversals avoided (no number) | Annex 14 §3.5.10; **CS ADR-DSN.C.230(a)(2)** — PV-2026-08-08 | *Standard.* "For the first 200 feet (61 m) of the RSA beyond the runway ends, the longitudinal grade is between 0 and 3.0 percent, with any slope being downward from the ends"; "The maximum allowable negative grade is 5.0 percent"; grade change ±2.0 % per 100 ft (30.5 m) | AC ¶3.16.5 *Standards* items 2, 4, 5 (p. 3-62) — **PV-2026-08-08**, verbatim |
| Transverse slope | ≤ **5 % upward OR downward** — one symmetric cap, no near-zone column; transitions gradual | Annex 14 §3.5.11; **CS ADR-DSN.C.230(b)** — PV-2026-08-08 | *Standard.* Table 3-6 (S-3 band: 1.5–5 % AAC-A/B, 1.5–3 % AAC-C/D/E) governs "the RSA along the runway **up to 200 feet (61 m) beyond the runway end**"; Figure 3-35 then shows **Maximum ±5.0 %** transverse across the RSA beyond 200 ft, with "a gradual transition between transverse grade changes" | AC ¶3.16.5 item 6 + Table 3-6 + Figure 3-35 (pp. 3-62, 3-63) — **PV-2026-08-08**. The near-zone/far-zone split the repo models is *exactly* the AC's structure |
| Surface-penetration rule | RESA slopes "should be such that **no part of the RESA penetrates the approach or take-off climb surface**" | Annex 14 §3.5.9; **CS ADR-DSN.C.230(a)(1)** — PV-2026-08-08 | **NOT an "equivalent constraint" — an explicit FAA Standard**, and it is the clause that *sets* the positive longitudinal cap: "Beyond the first 200 feet (61 m), the maximum allowable positive longitudinal grade is such that no part of the RSA penetrates any applicable approach surface or clearway plane." Figure 3-35 labels the same rule "Maintain grade clear of approach surface" | AC ¶3.16.5 *Standards* item 3 + Figure 3-35 (pp. 3-62, 3-63) — **PV-2026-08-08**, verbatim. Upgrades R14/F-5 from an ICAO-only BUILD to a **both-rulesets** BUILD |

### 3.1 Appendix G — the RSA length-beyond-the-end column (the BUILD item)

RULINGS 2026-08-08 reg-set ruling 3 named this a BUILD item requiring the
primary text. Here it is, read off Tables G-1…G-12 and reproduced whole
(all four visibility columns), because the repo's gap was not a wrong
number but a **missing axis**. Dimension letters are Figure 3-1's; feet
are the AC's own units, metres are `ft × 0.3048` (the AC's own tables
state "1 foot = 0.305 meters" and are rounded to the nearest foot).

**R — RSA length beyond departure end** (and **P** — length prior to
threshold). Both are *per runway end*.

| App. G table | AAC–ADG | Visual | ≥1 mi | ≥3/4 mi | <3/4 mi | P (prior to threshold), all columns |
|---|---|---|---|---|---|---|
| G-1 | A/B–I small aircraft | 240 ft (73.2 m) | 240 ft | 240 ft | 600 ft (182.9 m) | 240 ft; 600 ft at <3/4 mi |
| G-2 | A/B–I | 240 ft (73.2 m) | 240 ft | 240 ft | 600 ft (182.9 m) | 240 ft; 600 ft at <3/4 mi |
| G-3 | A/B–II small aircraft | 300 ft (91.4 m) | 300 ft | 300 ft | 600 ft (182.9 m) | 300 ft; 600 ft at <3/4 mi |
| G-4 | A/B–II | 300 ft (91.4 m) | 300 ft | 300 ft | 600 ft (182.9 m) | 300 ft; 600 ft at <3/4 mi |
| G-5 | A/B–III | 600 ft (182.9 m) | 600 ft | 600 ft | 800 ft (243.8 m) | **600 ft (182.9 m)** in all four |
| G-6 | A/B–IV | 1,000 ft (304.8 m) | 1,000 ft | 1,000 ft | 1,000 ft | 600 ft (182.9 m) |
| G-7 | C/D/E–I | 1,000 ft (304.8 m) | 1,000 ft | 1,000 ft | 1,000 ft | 600 ft (182.9 m) |
| G-8 | C/D/E–II | 1,000 ft (304.8 m) | 1,000 ft | 1,000 ft | 1,000 ft | 600 ft (182.9 m) |
| G-9 | C/D/E–III | 1,000 ft (304.8 m) | 1,000 ft | 1,000 ft | 1,000 ft | 600 ft (182.9 m) |
| G-10 | C/D/E–IV | 1,000 ft (304.8 m) | 1,000 ft | 1,000 ft | 1,000 ft | 600 ft (182.9 m) |
| G-11 | C/D/E–V | 1,000 ft (304.8 m) | 1,000 ft | 1,000 ft | 1,000 ft | 600 ft (182.9 m) |
| G-12 | C/D/E–VI | 1,000 ft (304.8 m) | 1,000 ft | 1,000 ft | 1,000 ft | 600 ft (182.9 m) |

The **ROFA** length beyond the runway end (dim R) is identical to the RSA
length in every one of the twelve tables, and its "length prior to
threshold" is identical to the RSA's; only the widths differ (ROFA dim
**Q**: 250 ft A/B-I small, 400 ft A/B-I, 500 ft A/B-II, 800 ft everywhere
else, 800 ft in every table's <3/4-mile column).

Three footnotes are part of the value and must travel with it:

* **fn 9 (the datum).** "The RSA length beyond the runway end begins at
  the runway end when a stopway is not present. When a stopway is
  present, the length begins at the stopway end."
* **fn 10 (the only relief).** "The RSA length beyond the runway end may
  be reduced to that required to install an EMAS (the designed set-back
  of the EMAS included)." Out of scope for the builder — no EMAS model.
* **fn 11 (which of R/P applies).** "This value only applies if that
  runway end is equipped with electronic or visual vertical guidance.
  ILS, GLS, LPV, VNAV, and RNP lines of minima provide electronic
  vertical guidance. A PAPI or VASI provides visual vertical guidance. If
  there is no such guidance for that runway, use the value for 'length
  beyond departure end.'"

**What this means for the builder.** The FAA end-corridor length is
per-end and depends on (a) the runway design code, (b) that end's
approach *visibility minimum*, and (c) whether that end has vertical
guidance. The repo's `RUNWAY_END_CLEARANCE_LENGTH_BY_CODE` is a single
symmetric ICAO-derived length. CIFP already gives the builder approach
type per end (RULINGS "Instrument truth is law", 2026-08-06), so key (c)
and most of (b) are available without new data.

> **FINDING F-12 (BUILD, now fully specified).** The FAA RSA length gap
> named in F-4 is closed as a *research* item: the values, the datum and
> the three footnotes are above. It remains open as an *implementation*
> item. The shape of the fix is not "add a constant" — it is
> `runway_end_governed_length` becoming a function of
> (ruleset, RDC, per-end visibility minimum, per-end vertical guidance,
> stopway presence). Only the FAA ruleset consumes keys (b)/(c); the
> ICAO ruleset keeps the strip-end datum of ruling 3.

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
> QUESTION Q3 — **answered**, RULINGS 2026-08-08 reg-set ruling 3: fix
> both per source. Compounding it: the **FAA RSA length-beyond-the-end
> column of Appendix G had never been pulled into the repo** —
> `FAA_RULESET` carries RSA/ROFA *widths* only, so an FAA airport's
> end-corridor LENGTH is today the ICAO-derived blend. That is a hole in
> the FAA ruleset, not a datum preference. **The column is now pulled and
> primary-verified — §3.1** — and both datums are settled from primary
> text: ICAO measures from the strip end (§3.5.3), the FAA from the
> runway end, or the stopway end where a stopway exists (App. G fn 9).

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
| Runway transverse — form | surface **should be cambered** (centre crown), except where a single crossfall from high to low in the direction of the rain-bearing wind ensures rapid drainage; for a cambered surface the slope each side of the centre line **should be symmetrical** | Annex 14 §3.1.19; **CS ADR-DSN.B.080(b),(c)** — PV-2026-08-08 | *Standard.* "The standard configuration is a center crown with equal, constant transverse grades on either side." | AC ¶3.16.2 *All Runways* (p. 3-58) — **PV-2026-08-08**, verbatim |
| Runway transverse — band | **not less than 1 %** and **not more than 1.5 %** (code letter C/D/E/F); **not less than 1 %** and **not more than 2 %** (A/B); flatter permitted **only at runway or taxiway intersections** | **CS ADR-DSN.B.080(b)(1),(2)** (EASA states the floor positively); Annex 14 §3.1.19 same numbers ("nor be less than 1 per cent except at runway or taxiway intersections") — PV-2026-08-08 | *Standard.* **S-1 = 1.0 %–2.0 % (AAC-A, AAC-B)**, **1.0 %–1.5 % (AAC-C, D, E)**; prose: "Design the transverse slope within a 1.0 to 1.5 percent range from the center crown" (C/D/E) | AC Table 3-6 row **S-1** (p. 3-60) + ¶3.16.2 (p. 3-58) — **PV-2026-08-08**, exact |
| Runway transverse — permitted variances | (ICAO/EASA state none beyond the intersection clause) | — | *Standard.* Three named cross-slope variances: **off-centre crown** offset ≤25 ft (7.6 m) from the pavement centreline; **varied cross-slope** (different gradients each side); **non-uniform cross-slope** — a transverse grade change <0.5 % located more than 25 ft (7.6 m) from the crown | AC ¶3.16.2 *Cross-Slope Variations* + Figure 3-34 (pp. 3-58, 3-59) — **PV-2026-08-08**. Note "The runway crown is not necessarily the runway centerline" (Fig. 3-34 note 2) |
| Runway transverse — intersection relaxation | flatter permitted at runway/taxiway intersections; no floor stated | Annex 14 §3.1.19 — PV-2026-08-08 | *Standard.* At a runway/runway intersection the higher-category runway may be flattened to a constant-slope transverse grade provided "A minimum transverse slope of 0.5 percent is available to permit positive drainage", the runway is grooved, and no control-losing bump results; transition to the Table 3-6/3-7 standard over ≥150 ft (46 m) | AC ¶3.16.4.1 items 3–4 (pp. 3-59, 3-60) — **PV-2026-08-08**. The FAA floor at an intersection is **0.5 %, not zero** |
| Runway transverse — uniformity | "substantially the same throughout the length of a runway except at an intersection … where an even transition should be provided" | Annex 14 §3.1.20; CS ADR-DSN.B.080(d) — PV-2026-08-08 | *Standard.* "Maintain the surface gradient standards of the runway through intersections with taxiways" + "Provide positive drainage off intersection pavement to prevent accumulation of surface water" | AC ¶3.16.3 items 1–2 (p. 3-58) — **PV-2026-08-08** |

**The runway crown minimum of 1 % is real, numeric, and present in BOTH
authorities.** It is the single strongest drainage mandate in the reg
set, and the owner already bound it (RULINGS 2026-08-05, `d48bc0a`;
`config.CROWN_MINIMUM_BOUND_RUNWAYS = True`).

### 4.2 Taxiway transverse — the owner's all-taxiways rider

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Taxiway transverse | "should be **sufficient to prevent the accumulation of water** on the surface of the taxiway but should not exceed" **1.5 % (C/D/E/F)**, **2 % (A/B)**. **NO NUMERIC MINIMUM. NO CROWN MANDATE.** | Annex 14 §3.9.11; **CS ADR-DSN.D.280(b)** — PV-2026-08-08 | *Standard.* **1.0 to 1.5 percent from centerline to pavement edge**; 1–2 % where the pavement exclusively serves aircraft weighing **less than** 30,000 lb (13,605 kg); a constant-slope "shed" section is acceptable for high-speed exits or where terrain makes a crown impractical | AC ¶4.14.2 *Standards* item 1 (p. 4-46) — **PV-2026-08-08**, verbatim in §4.2.1 below |
| Taxiway longitudinal | ≤1.5 % (C/D/E/F); ≤3 % (A/B) | Annex 14 §3.9.8; **CS ADR-DSN.D.265(b)** — PV-2026-08-08 | *Standard.* Max longitudinal grade **1.50 %**; 2.0 % for taxiways exclusively serving aircraft ≤30,000 lb (13,605 kg) — relaxation **not taken**, the builder does not know a taxiway's fleet. Also: max longitudinal grade **change 3.0 %**; parabolic vertical curve ≥100 ft (30.5 m) per 1 % of change; no curve needed below 0.40 %; PVI spacing ≥100 ft (30.5 m) × the sum of the two absolute grade changes | AC ¶4.14.1 *Standards* items 1–3 (pp. 4-43, 4-44) — **PV-2026-08-08** |
| General drainage CS | EASA states a **safety objective only** — "minimise water depth on the surface by draining surface water off the runway in the shortest path practicable" — and its GM explicitly defers the numbers: "Slopes for the various parts of the movement area and adjacent parts are described in Chapters B to G". **No independent numeric floor anywhere.** | **CS ADR-DSN.B.191 + GM1** — PV-2026-08-08 | *Standard.* ¶4.14.3 makes the transverse gradient itself the drainage instrument: "Design taxiways and taxilanes with transverse gradients, per paragraph 4.14.2, to prevent standing water on the pavement and within the limits of the safety area." Ditches and headwalls go outside the safety area; inlets flush. AC 150/5320-5D (S4) carries the storm design and was **not** reached — no value here depends on it | AC ¶4.14.3 *Standards* items 1–3 (p. 4-47) — **PV-2026-08-08** |

#### 4.2.1 The 1.0 % taxiway transverse minimum — verbatim

RULINGS 2026-08-08 reg-set ruling 2 adopts this FAA number as a **named
PROVISIONAL house constant on the ICAO ruleset**, and requires the ICAO
text quoted alongside it. Both texts, exactly:

> **FAA — AC 150/5300-13B Chg 1, ¶4.14.2 *Taxiway/Taxilane Transverse
> Gradient*, Standards, item 1 (page 4-46):**
>
> "Design taxiway/taxilane pavement transverse gradient as follows:
> a. 1.0 to 1.5 percent from centerline to pavement edge.
> b. For taxiways/taxilanes exclusively serving aircraft weighing less
> than 30,000 lbs (13,605 kg), it is acceptable to apply a cross-slope of
> 1 to 2 percent.
> c. A constant slope section (aka shed section) may be more suitable:
> i. For high-speed exit taxiways. ii. When existing terrain makes it
> impractical to provide a crown and slope cross section."
>
> and, under *Recommended Practices* on the same page, item 2:
> "The ideal configuration is a center crown with equal, constant
> transverse grades on either side."

> **ICAO — Annex 14 Vol I 8th ed. §3.9.11 (and CS ADR-DSN.D.280(b)),
> the clause the house constant stands in for:** the transverse slope
> "should be **sufficient to prevent the accumulation of water** on the
> surface of the taxiway but should not exceed" 1.5 % (code letter
> C, D, E, F) or 2 % (A, B). **No minimum is stated anywhere in the ICAO
> or EASA text.**

Two notes the ruleset entry must carry with the constant:

1. The FAA sentence is a *Standard* (§0.2), not a Recommended Practice —
   it is the strongest form the AC uses for a design value. The
   *crown* itself, by contrast, is a Recommended Practice ("the ideal
   configuration"), so binding a 1.0 % **minimum cross-fall** is
   primary-sourced while binding a **centre crown** is not.
2. 1.0 % is simultaneously the FAA **runway** transverse minimum
   (Table 3-6 S-1) and the FAA **taxiway** transverse minimum, so the
   provisional ICAO-side constant is one number, not two, and it sits
   inside the ICAO ceiling (1.5 % C–F) with 0.5 pp of headroom.

> **FINDING F-6 (the rider is jurisdictionally asymmetric — decisive for
> the fabric model).** "Drainage requirements along all taxiways" has a
> **numeric FAA requirement** (1.0 % transverse minimum, §4.14.2 item 1a)
> and **no numeric ICAO/EASA requirement at all** — only "sufficient to
> prevent the accumulation of water" plus a ceiling. Under jurisdictional
> fidelity the rider therefore binds at KCLT and is a **no-op at SPJC,
> SPLP, CYXY and HECA**. Four of the five battery airports would emit no
> taxiway crown. Manufacturing an ICAO number would be MINTED, not cited
> — the same trap `config.py` already refuses for the ICAO apron minimum.
> OWNER QUESTION Q2 — **answered 2026-08-08**: the owner took reading
> (b), so the ICAO ruleset carries 1.0 % as a **named PROVISIONAL house
> constant** rather than a citation. The distinction F-6 draws is
> preserved *in the label*, not erased by it: the constant is house, the
> ICAO clause it satisfies is quoted beside it (§4.2.1), and a future
> ICAO amendment that states a real floor replaces the constant rather
> than merely re-blessing it. That is what keeps this out of the
> minted-value trap.

### 4.3 Apron / stand

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Apron slopes | "should be **sufficient to prevent accumulation of water** … but should be kept **to the minimum required to facilitate effective drainage**" (EASA) / "kept as level as drainage requirements permit" (ICAO). **QUALITATIVE — no number.** | Annex 14 **§3.13.4**; **CS ADR-DSN.E.360(a)** — PV-2026-08-08 | ***Standard.*** "Provide a minimum 0.5 percent apron gradient to facilitate aircraft maneuvering operations and apron drainage"; "Limit maximum grade change to 2 percent"; "Design and construct apron grades for positive drainage of surface water to inlets or off the apron pavement edge"; edge drop-off 1.5 in ±1/2 in (38 mm ±13 mm) at the paved→unpaved transition | AC ¶5.9.1 *Standards* (pp. 5-9, 5-10) — **PV-2026-08-08**, verbatim |
| Aircraft stand maximum | ≤ **1 %** (EASA adds "**in any direction**") | Annex 14 **§3.13.5**; **CS ADR-DSN.E.360(b)** — PV-2026-08-08 | ***Recommended Practice*** — "Maximum: 1 percent for parking positions". Two further ceilings in the same list, not currently in the repo: 1.5 % for apron taxilanes serving aircraft **over** 30,000 lb (13,605 kg), 2.0 % for apron taxilanes serving 30,000 lb or less | AC ¶5.9.2 *Recommended Practices* (p. 5-10) — **PV-2026-08-08**. Note the ICAO 1 % is a *Recommendation* too, so both authorities agree on both the value **and** its normative weight |
| Apron shoulder | **NOTHING.** Neither Annex 14 §3.13 nor CS ADR-DSN Chapter E governs ground beyond an apron edge. | (absence verified by reading §3.13.1–3.13.6 / E.345–E.365 in full) — PV-2026-08-08 | ***Recommended Practice*** — "Provide a 10-foot (3 m) wide shoulder at the edge of the apron with a 1-3 percent slope to promote flow of surface water away from the apron pavement… Beyond the shoulder edge, provide a 3-5 percent slope to facilitate the flow of surface water away from the apron area." | AC ¶5.9.2 *Recommended Practices* (p. 5-10) — **PV-2026-08-08**, verbatim. The *Recommended Practices* heading is now read, not inferred: this is the primary basis for RULINGS reg-set ruling 4 (T2/T3/T4 **RETIRE OUTRIGHT**) |

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
| Runway shoulder — provision | where code letter D, E or F | Annex 14 §3.2.1; CS ADR-DSN.B.125 — PV-2026-08-08 | *Standard.* Paved shoulders for runways accommodating **ADG-IV and larger**; stabilized (turf or soil treatment) for ADG-I/II/III. *Recommended Practice*: paved for ADG-III, for erosion-prone soil, and where turf will not establish | AC ¶3.7.3 *Standards* items 2–3 / *Recommended Practices* (pp. 3-20, 3-21) — **PV-2026-08-08**. Note the key is **ADG**, not RDC |
| Runway shoulder — width | overall runway+shoulders ≥60 m (D/E), 60 m (F, 2–3 engines), 75 m (F, 4+ engines), for OMGWS 9–15 m | Annex 14 §3.2.2; **CS ADR-DSN.B.135** — PV-2026-08-08 | *Standard*, Appendix G row *Shoulder Width*, per side: **10 ft (3.0 m)** A/B-I, A/B-II, C/D/E-I, C/D/E-II; **20 ft (6.1 m)** A/B-III, C/D/E-III; **25 ft (7.6 m)** A/B-IV, C/D/E-IV; **35 ft (10.7 m)** C/D/E-V, C/D/E-VI. fn 12: C/D/E-III over 150,000 lb (68,027 kg) MTOW takes 25 ft. fn 14: ADG-VI aircraft with four or more engines take **50 ft (15.2 m)**. Repo caps detected shoulder extent at 15 m/side — just above the largest standard, so the cap does not clip any lawful shoulder | AC App. G Tables G-1…G-12 + fn 12, 14 — **PV-2026-08-08** |
| Runway shoulder — slope | **flush** with the runway; transverse ≤ **2.5 %**. **No minimum.** | Annex 14 §3.2.3; **CS ADR-DSN.B.130(b)** — PV-2026-08-08 | *Standard.* **S-2 = 1.5 %–5.0 %** for **every** AAC (A through E — the band does not vary by category, unlike S-1 and S-3); flush with the runway pavement; paved→unpaved edge drop-off 1.5 in (38 mm) ±1/2 in (13 mm) | AC Table 3-6 row **S-2** (p. 3-60) + ¶3.7.3 items 2c, 4a + Figure 3-33 note 3 ("Slope S-2 applies when paved shoulders are present") — **PV-2026-08-08**, exact |
| Taxiway shoulder — width | overall taxiway+shoulders ≥25 m (C), 34 m (D), 38 m (E), 44 m (F) | Annex 14 §3.10.1; **CS ADR-DSN.D.305(a)** — PV-2026-08-08 | **DISCREPANT KEY** — the AC keys taxiway shoulder width by **TDG**, not ADG: **10 ft (3.0 m)** TDG 1A/1B, **15 ft (4.6 m)** 2A/2B, **20 ft (6.1 m)** 3/4, **30 ft (9.1 m)** 5/6; **40 ft (12.2 m)** where the most demanding aircraft has four engines and is TDG 6. Provision: paved for ADG-IV and larger (¶4.13.1 item 2) — so *provision* is ADG-keyed and *width* is TDG-keyed | AC Table 4-2 row *Taxiway Shoulder Width* + fn 3 (p. 4-10), reached via ¶4.13.1 *Standards* item 1 — **PV-2026-08-08**. Carried in the repo as "by ADG"; see F-11 |
| Taxiway shoulder — slope | **no number** — §3.10 / D.305 give width, erosion resistance and strength only; the taxiway-strip clause supplies the flush edge | Annex 14 §3.10.1–3.10.2; CS ADR-DSN.D.305 — PV-2026-08-08 | *Standard.* "Design paved taxiway shoulders with a transverse gradient between 1.5 to 5 percent"; paved shoulder flush with the taxiway pavement (¶4.13.1 item 2c); shoulders must "provide proper surface drainage away from the edge of the taxiway pavement, per paragraph 4.14.2" (¶4.13.1 item 4) | AC ¶4.14.2 *Standards* item **3** (p. 4-46) — **PV-2026-08-08**. The previous citation, "§4.14.2 item 5", is the **TSA** band; same 1.5–5 % numbers, different surface — see F-11 |

### 4.5 Taxiway strips

| Key | ICAO / EASA | Citation | FAA | Citation |
|-----|-------------|----------|-----|----------|
| Graded half-width | by **OMGWS**, not code letter: 10.25 m (<4.5 m), 11 m (4.5–<6), 12.50 m (6–<9), 18.50 m (9–<15, letter **D**), 19 m (9–<15, **E**), 22 m (9–<15, **F**) | Annex 14 §3.11.4; **CS ADR-DSN.D.325(b)** — PV-2026-08-08 | *Standard.* "The TSA width equals the maximum wingspan of the ADG" — full widths 49 / 79 / 118 / 171 / 214 / 262 ft = **14.9 / 24.1 / 36.0 / 52.1 / 65.2 / 79.9 m** for ADG-I…VI, i.e. **half-widths 7.45 / 12.05 / 18.0 / 26.05 / 32.6 / 39.95 m**. Symmetric about the centreline on straight segments; widened at intersections and turns by (TSA width − W)/2 off the inner edge | AC ¶4.5.3 *Standards* items 1–2 (p. 4-13) + Table 4-1 (p. 4-10) — **PV-2026-08-08**. Note the ICAO table is OMGWS-keyed and the FAA table is **wingspan/ADG**-keyed: the two are not interconvertible, which is why the repo's letter table is a proxy on both sides |
| Grading mandate | (the flush + slope clause below is the whole of it) | — | *Standard.* "Clear and grade the TSA to remove potentially hazardous ruts, humps, depressions, or other surface variations" and "Prevent accumulation of surface water by grading the TSA to drain away from taxiway pavement or using flush grated catch basins" | AC ¶4.5.3 *Standards* items 3–4 (p. 4-14) — **PV-2026-08-08**, verbatim. This is the FAA's affirmative mandate to *shape* taxiway-side ground |
| Slopes | strip surface **flush** at the taxiway/shoulder edge; graded portion **upward** transverse ≤2.5 % (C–F) / 3 % (A/B), measured against the **adjacent taxiway surface, not the horizontal**; **downward** ≤5 % measured against the **horizontal** | Annex 14 §3.11.5; **CS ADR-DSN.D.330(b)** — PV-2026-08-08 | *Standard.* "TSA transverse gradient: Design a 1.5 to 5 percent transverse gradient **except as noted in subparagraph 4 above**" — i.e. the band applies *outside* the first 3 m, which the lip below owns | AC ¶4.14.2 *Standards* item **5** (p. 4-46) — **PV-2026-08-08**, verbatim |
| **Taxiway-edge lip** (first 3 m) | **NONE** — §3.11.5 / D.330(b) state flush, an up cap and a down cap; no lip clause | (absence verified by full read) — PV-2026-08-08 | *Standard.* "For an unpaved surface adjacent to a paved surface, design a 5 ±0.5 percent transverse gradient for a minimum distance of 10 feet (3 m) from the paved surface" ⇒ **4.5 %–5.5 % over the first 3 m**, plus the 1.5 in ±1/2 in edge drop-off at the paved→unpaved transition (item 2) | AC ¶4.14.2 *Standards* items **4** and **2** (p. 4-46) — **PV-2026-08-08**, verbatim. **This band is not the runway's 3–5 %** — see F-10 |
| Beyond the graded portion | up **or** down ≤5 % away from the taxiway | Annex 14 §3.11.6; **CS ADR-DSN.D.330(c)** — PV-2026-08-08 | *Standard.* TOFA side slope: qualitative — "Design transverse gradient to promote positive drainage away from the TSA" (no number, unlike the runway's S-4 ≤0 %). TOFA **back** slope, when one is necessary: **≤4:1 (25 %)**, "provided the area immediately adjacent to the TSA edge permits positive drainage of surface water away from the TSA" | AC ¶4.14.2 *Standards* item 6 (p. 4-46) + Figure 4-29 (p. 4-45) — **PV-2026-08-08**. The previous revision left this cell empty; the FAA taxiway back-slope ceiling is 4:1, far steeper than the runway ROFA's 8:1/10:1/16:1 |

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
> **Q1 is now answered** (RULINGS 2026-08-08 reg-set ruling 1: the ICAO
> ruleset **drops** the mandatory fall, flagged PROVISIONAL), so the
> two-frame band described here is live work, not a conditional.

> **FINDING F-10 (DISCREPANT — the FAA taxiway lip is a different band
> from the FAA runway lip).** The repo has one lip family,
> `ADJACENT_GROUND_LIP_{WIDTH_M,MIN,MAX}_DOWN_SLOPE`, consumed by
> `_adjacent_strip_envelope` on **both** the runway and the taxiway
> branch, carrying the runway values (3 m at 3–5 %). The AC states two
> distinct lips:
>
> | Edge | AC clause | Width | Band |
> |---|---|---|---|
> | Runway / shoulder / stopway | Figure 3-33 **Detail A** note 2 | 10 ft (3 m) | **3 % – 5 %** negative |
> | Taxiway / taxilane / apron (any paved→unpaved) | ¶4.14.2 *Standards* item **4** | 10 ft (3 m) minimum | **5 ± 0.5 %** ⇒ 4.5 % – 5.5 % |
>
> Carried value on the taxiway branch: 3–5 %. AC value: 4.5–5.5 %.
> The widths agree (3 m); only the band differs, and it differs in both
> directions — the FAA taxiway lip is *steeper at the floor* (4.5 vs 3.0)
> and *exceeds the runway ceiling* (5.5 vs 5.0). Note also that ¶4.14.2
> item 5 explicitly carves this strip out of the TSA band ("except as
> noted in subparagraph 4 above"), so the two are a near-zone/far-zone
> pair exactly like the RSA's, not alternatives.
> Consequence for F-3: the ICAO taxiway lip remains **unsourced** (retire
> it there under ruling 1's jurisdictional-fidelity logic), while the FAA
> taxiway lip is **sourced but mis-valued** in the repo today. Nothing
> was changed in `config.py` by this round.

> **FINDING F-11 (citation drift, FAA side — the mirror of F-7).** Four
> FAA citations in the previous revision of this document pointed at a
> clause with the right *number* on the wrong *surface*. All four values
> survive verification; only the pointers move. Recorded because the
> provenance contract in `regs/README.md` is what makes an edition bump
> auditable, and a citation that resolves to another surface silently
> defeats it.
>
> | Row | Was cited | Should be | Value |
> |---|---|---|---|
> | Runway strip flush + drop-off | ¶4.14.2 item 2 / ¶5.9.1 (the **taxiway** and **apron** drop-offs) | **¶3.7.3 items 2c, 4a** + Fig. 3-33 Detail A note 1 | 1.5 in ±1/2 in — unchanged |
> | Taxiway shoulder slope | ¶4.14.2 item 5 (the **TSA** band) | **¶4.14.2 item 3** | 1.5–5 % — unchanged |
> | RSA provision / grading mandate | ¶3.16.5 (which gives *grades*, not the mandate) | **¶3.10.1** *Location* / *Dimensions* / *Grading* | unchanged |
> | Taxiway shoulder width key | "by ADG" | **by TDG**, Table 4-2 (¶4.13.1 item 1) | widths newly pulled — §4.4 |
>
> One further drift of the same class, in the opposite direction: the
> RESA/approach-penetration rule was recorded as an FAA "equivalent
> constraint" with no citation at all. It is an explicit *Standard* at
> **¶3.16.5 item 3**, quoted in §3, and it is the clause that sets the
> RSA's positive longitudinal cap.

### 4.6 Recorded, not shaped ground (for completeness)

ICAO §3.1.13 effective slope (1 %/2 %), §3.1.15 slope change, §3.1.16
curve rate, §3.1.17/§3.9.10 sight distance, §3.1.18 PVI spacing, §3.9.9
taxiway vertical curves, §3.8 radio altimeter operating area (300 m ×
±60 m, ≤2 % per 30 m — **ICAO only**; the FAA absence is now
**PRIMARY-VERIFIED 2026-08-08**: the string "radio altimeter" occurs
**zero** times in the full 413-page AC 150/5300-13B Chg 1, upgrading the
2026-08-02 round's secondary finding). These govern PAVEMENT profile, not
adjacent ground; `config.py` already carries them with citations.

The FAA adds two pavement-profile items with no ICAO twin, both read this
round and both already inside existing machinery or out of scope:
`Turf runways` (¶3.20.1 *Grading* — ≥2.0 % away from the centreline for
40 ft (12.2 m) each side, then 5.0 % to the RSA edge, drainage swales
≤3.0 % outside the RSA) and the apron transitional-grade design
consideration (¶5.9.3 — a 20–25 ft (6.1–7.6 m) transitional section in
lieu of a vertical curve where an apron-taxilane longitudinal grade
change exceeds 1 %). Turf runways are out of the battery; the apron item
is a *Design Consideration*, the AC's weakest level (§0.2).

---

## 5. Mapping to existing machinery — KEEP / EXTEND / BUILD

Every row names the law function and its constant; emitter↔validator
lockstep is the repo's existing discipline (grade-law completeness
standard, RULINGS 2026-08-02) and is assumed, not re-audited here.

| # | Requirement | Machinery today | Verdict |
|---|-------------|-----------------|---------|
| R1 | Runway crown min/max (§3.1.19 / B.080 / Table 3-6 S-1) | `crown.py` (`build_crown_drop_field`, `runway_crown_drop_m`); `grade_law.runway_crown_rate`, `transverse_surface_bounds`, `transverse_minimum_binds`; `config.CROWN_MINIMUM_BOUND_RUNWAYS=True`, `RUNWAY_CROWN_TRANSVERSE=0.010`; ruleset `runway_transverse_min/max`; census `transverse` | **KEEP** |
| R2 | Runway longitudinal profile + curves + end-zone (§3.1.14–3.1.16 / B.060 / AC §3.16.1) | `pavement/runway_segments.faa_joint_solve`, `runway_regrade.py`, `runway_redistribute.py`; ruleset `runway_max_grade`, `runway_end_grade`, `runway_vertical_curve_k_m` | **KEEP** |
| R3 | Graded runway-strip FOOTPRINT (§3.4.8–3.4.9 / B.175) | `config.RUNWAY_STRIP_HALF_WIDTH_BY_CODE`, `ruleset_strip_half_width_m`, `grade_law.runway_strip_lateral_footprint_ring`, `adjacent_ground.runway_strip_lateral_zone` | **EXTEND** — ICAO: add the instrument/non-instrument key (F-1), code-1 instrument = 40 m. FAA: the RSA-width table is keyed AAC×ADG×**visibility minimum** and the repo carries one column; A/B-III and A/B-IV are missing outright (**F-9**) |
| R4 | Strip abeam-longitudinal cap (§3.4.13 / B.180(b) / AC §3.16.5 item 1) | `grade_law.runway_strip_max_longitudinal_slope`, `runway_strip_longitudinal_clamp`, `strip_longitudinal_law`; ruleset `strip_max_longitudinal_slope`; census `strip_longitudinal` | **KEEP** |
| R5 | Strip longitudinal grade-CHANGE rate (§3.4.14 qualitative / AC ±2 %/30.5 m) | ruleset `strip_arc_rate_per_m` (+`strip_arc_rate_provisional=True` on ICAO); census `strip_arc` | **KEEP** — ICAO side remains an operationalization of a qualitative clause; the provisional flag is correct and must survive the fabric round |
| R6 | Strip transverse graded band (§3.4.15 / B.185(a) / Table 3-6 S-3) | `grade_law.adjacent_ground_envelope` runway branch + `_adjacent_strip_envelope`; `adjacent_ground.emit_adjacent_ground_bands`; `RUNWAY_STRIP_BAND_{MIN,MAX}_DOWN_SLOPE*` | **KEEP** (this band IS the reg set) — but the mandatory-DOWN blend on the ICAO ruleset is Q1 |
| R7 | Pavement-edge lip, first 3 m negative ≤5 % (§3.4.15 final clause / B.185(a) / Fig 3-33 Detail A) | `ADJACENT_GROUND_LIP_{WIDTH_M,MIN,MAX}_DOWN_SLOPE`, consumed in `_adjacent_strip_envelope` | **EXTEND** — ICAO: scope it to the RUNWAY strip (F-3), the ICAO taxiway-strip clause has no lip. FAA: the lip is **per-surface** — 3–5 % at a runway edge (Fig. 3-33 Detail A), **4.5–5.5 % at a taxiway/apron edge** (¶4.14.2 item 4); the repo applies the runway band to both (**F-10**) |
| R8 | Flush strip/pavement edge (§3.4.10 **shall** / B.175(c)) | `flatedge_snap.py`, `emit_snap.py`, step families + FAA-only drop-off exemption (`ruleset_shoulder_edge_dropoff`) | **KEEP** |
| R9 | Taxiway graded strip: OMGWS widths + up/down caps (§3.11.4–3.11.5 / D.325, D.330) | `TAXIWAY_STRIP_GRADED_HALF_WIDTH_BY_LETTER`, `taxiway_strip_graded_half_width_for_letter`; `adjacent_ground_envelope` taxiway branch; `_adjacent_strip_envelope` (single horizontal frame) | **EXTEND** — the ICAO up-cap is measured against the taxiway crossfall, not the horizontal, and is unexpressible today (F-8); the ICAO widths are **OMGWS**-keyed and the FAA's are **ADG wingspan**-keyed (7.45…39.95 m half-width, Table 4-1), so the repo's letter table is a proxy on *both* sides (document it). The FAA also states an affirmative TSA grading mandate, ¶4.5.3 items 3–4 |
| R10 | Ungraded strip rising-ground ceiling ≤5 % up (§3.4.16, §3.11.6 / B.185(b), D.330(c)) | `ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE`, zone-3 of `_adjacent_strip_envelope`; FAA `rofa_back_slope_ceiling` | **KEEP** — note it is a **ceiling (cut)**, never a mandate to shape; it must not mint fill under the fabric model |
| R11 | RESA extent — length + width (§3.5.3–3.5.6 / C.215) | `config.RUNWAY_END_CLEARANCE_LENGTH_BY_CODE`, `grade_law.runway_end_governed_length_m` / `…_beyond_pavement_m`, `runway_end_corridor_half_width_m` | **EXTEND** — per-ruleset datum (ICAO strip-end §3.5.3; FAA runway-or-stopway end, App. G fn 9) + the ICAO ≥2× runway-width / graded-strip-width rule (F-4), **and the FAA Appendix G length column, now pulled in §3.1** — a per-end function of RDC × visibility minimum × vertical guidance, not a constant (**F-12**). Q3 answered by RULINGS 2026-08-08 reg-set ruling 3 |
| R12 | RESA longitudinal ≤5 % down (+ FAA 0–3 % near zone) (§3.5.10 / C.230(a)(2) / AC §3.16.5) | `grade_law.runway_end_skirt_law`, `runway_end_skirt_floor_profile*`, `runway_end_envelope`; `RUNWAY_END_RESA_MAX_SLOPE=0.05`; census `runway_end_skirt` | **KEEP** |
| R13 | RESA transverse ≤5 % (ICAO symmetric) / FAA near-zone S-3 band (§3.5.11 / C.230(b)) | `grade_law.resa_transverse_band/_envelope/_clamp`; ruleset `resa_transverse_near*`, `resa_transverse_max`; census `resa_transverse` | **KEEP** |
| R14 | RESA/RSA must not penetrate the approach or take-off climb surface (§3.5.9 / C.230(a)(1) / **AC ¶3.16.5 item 3**) | **nothing** — `ols.py` cuts terrain to the approach surface but nothing bounds the emitted end-skirt against it | **BUILD** (cheap: `grade_law.ols_approach_ceiling` already exists) — and now a **both-rulesets** build: the FAA states it as a *Standard* that sets the RSA's positive longitudinal cap beyond 200 ft, not merely an "equivalent constraint" |
| R15 | Blast-pad / stopway grade inheritance (§3.4.11 / B.175(d) / AC §3.7.4) | blast pad is a skirt anchor/constraint only (gap audit GAP 5) | **BUILD** |
| R16 | Runway shoulder flush + transverse band (§3.2.3 / B.130 / Table 3-6 S-2) | `ruleset_shoulder_transverse_band`, `shoulder_edge_dropoff*`, `RUNWAY_SHOULDER_EXTENT_MAX_M`, `pavement/runways._detect_runway_shoulder_extent`, shoulder sub-band in `adjacent_ground_envelope` | **KEEP** |
| R17 | Taxiway shoulder — ICAO width/erosion only, **no** slope number (§3.10 / D.305); FAA **does** give one, 1.5–5 % (AC ¶4.14.2 item 3) | rides the taxiway-strip band | **KEEP** — still a no-op, but now for a *verified* reason rather than an assumed one: the FAA taxiway-shoulder band (1.5–5 %) is numerically identical to the FAA TSA band (item 5), so riding the strip band reproduces it exactly. Width key is **TDG** not ADG (F-11) |
| R18 | Apron drainage minimum — FAA 0.5 %, ICAO none (§5.9.1 / §3.13.4 / E.360(a)) | `grade_law.drainage_minimum_grade/_band/_shortfall`; ruleset `apron_min_drainage_grade` (FAA 0.005, ICAO `None`); census `drainage_minimum` | **KEEP** — remains **VERSION-DEFERRED** by RULINGS 2026-08-05 §3 |
| R19 | Aircraft-stand maximum 1 % (§3.13.5 / E.360(b) / AC §5.9.2) | `ruleset_stand_max_grade`, `ROLE_GRADE_LIMITS["stand"]`, apron split into `ROLE_STAND` pads | **KEEP** — fix the ICAO paragraph number (F-7) |
| R20 | Taxiway transverse — the all-taxiways drainage rider (§3.9.11 / D.280 / AC §4.14.2 1a) | ruleset `taxi_transverse_max` binds; `taxi_transverse_min` **recorded, not bound** (`CROWN_MINIMUM_BOUND_TAXIWAYS=False`); `TAXI_CROWN_TRANSVERSE=0.010` exists but unbound | **EXTEND** — flipping the FAA side is one line (`transverse_minimum_binds`). Q2 answered by RULINGS 2026-08-08 reg-set ruling 2: the ICAO side takes the FAA 1.0 % as a **named PROVISIONAL house constant**, and the ruleset entry must carry the ICAO text verbatim — supplied in **§4.2.1** (F-6) |
| R21 | Radio altimeter operating area — ICAO only (§3.8 / B.205) | `grade_law.raoa_footprint_ring`, `raoa_applies`, `raoa_rate_clamp`; census `raoa` | **KEEP** — the FAA absence is now primary-verified (zero occurrences of "radio altimeter" in the whole AC), so the ICAO-only gate is sourced on both sides |
| R22 | ROFA back slope — FAA only (Table 3-7 S-5, run D-1) | `grade_law.rofa_back_slope_ceiling`, ruleset `rofa_back_slope_*` | **KEEP** — verified exact (8:1 / 10:1 / 16:1 over 25/40/59/86/107/131 ft) |
| R23 | OFZ | **nothing to build** — clearance volume, not shaped ground (§1 item 4) | **KEEP-AS-NOTHING** (record the negative so it is not re-litigated; the FAA's own definition, ¶1.5 #69, says "three-dimensional airspace") |
| R24 | **TOFA back slope ≤4:1 — FAA only** (AC ¶4.14.2 item 6b); TOFA side slope qualitative | **nothing** — `rofa_back_slope_ceiling` covers the *runway* object free area only; the taxiway side has no back-slope ceiling | **EXTEND** — new row, surfaced by this round's primary read. A ceiling (cut), never a mandate to shape; same discipline as R10/R22. 4:1 is far steeper than any ROFA value, so it will rarely bind — but its absence means the taxiway branch currently has *no* far-zone ceiling on the FAA ruleset |

**Counts: KEEP 15 · EXTEND 6 · BUILD 2 · KEEP-AS-NOTHING 1** (24 rows).
*(Was 23 rows / EXTEND 5 before the FAA primary read; R24 is the one
requirement the unreachable-source round could not see.)*

### 5.1 RETIRE — machinery no standard requires

The fabric model's §4 is "unregulated ground: NOTHING". Everything below
exists today, shapes ground, and has **no requirement behind it** in
either authority. Each needs a twin proving the successor behaviour
(fabric-model-spec.md Retire list).

| # | Machinery | Why it is not in the reg set |
|---|-----------|------------------------------|
| T1 | Fan zones / apron fan ramps — `elevation_per_surface/route_profile/apron_terrace.split_aprons_at_fan_zones`, its `FanRampPlan`, and the `layout.py` / `grade_graph.py` consumers | Owner: "RETIRE OUTRIGHT" (RULINGS 2026-08-08 §1); no standard mentions apron fans |
| T2 | Apron shoulder band — `APRON_SHOULDER_WIDTH_M`, `APRON_SHOULDER_{MIN,MAX}_DOWN_SLOPE` | AC ¶5.9.2 sits under a ***Recommended Practices*** heading — **read directly 2026-08-08**, not inferred — and §0.2 records what that heading means ("An airport has the discretion to implement a recommended practice"); Annex 14 §3.13 and CS ADR-DSN Ch. E govern **nothing** beyond an apron edge (verified by full read) — **RETIRE OUTRIGHT**, RULINGS 2026-08-08 reg-set ruling 4 |
| T3 | Apron beyond-shoulder fill target — `APRON_BEYOND_SHOULDER_{MIN,MAX}_DOWN_SLOPE` | the second clause of the same ¶5.9.2 *Recommended Practice* ("Beyond the shoulder edge, provide a 3-5 percent slope…"), one band further out; already documented in `STANDARDS.md` as "a render target, not a corridor" — **RETIRE OUTRIGHT**, ruling 4 |
| T4 | Apron edge retaining-wall family — `APRON_EDGE_WALL_MIN_DROP_M`, `APRON_WALL_RUN_HYSTERESIS_M`, `APRON_WALL_MIN_RUN_M`, `APRON_WALL_MIN_AREA_M2`, `APRON_WALL_PAVEMENT_ADJACENCY_M` | pure design (2026-07-25 scoping ruling already narrowed it because "no code mandates grading beyond an apron edge"); under the drape model the raw DEM meets the apron edge — **RETIRE OUTRIGHT**, ruling 4 |
| T5 | Service-road roadside clearance band — `CLEARANCE_MAX_REACH_M["service"]` 15 m cut-only shadow | `STANDARDS.md` states it outright: "**design choice, NOT an AASHTO mandate**"; no aviation authority regulates service roads |
| T6 | Adjacent-ground daylight slope limit — `ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT`, `grade_law.adjacent_ground_supported_depths` | "engineering judgment — **NO external citation**" (its own STANDARDS.md row). It exists to keep dense emitted bands from knife-slotting; sparse emission removes the failure mode it patches |
| T7 | Flat lateral clearance shadow — `CLEARANCE_LATERAL_MAX_SLOPE = 0`, `clearance.emit_surface_clearance_cuts` Pass A3 beyond the strip footprints | design; the regulated ceilings are §3.4.16/§3.11.6 (R10) and the FAA ROFA back slope (R22), both already modelled |
| T8 | Stationing density beyond the adequate spine/curve floor; the census relief vocabulary and its exemptions | fabric-model-spec.md Retire list — no standard specifies vertex density |

**RETIRE: 8 items.** T2–T4 were RETIRE-CANDIDATE pending Q4; Q4 is
answered (RULINGS 2026-08-08 reg-set ruling 4 — **RETIRE OUTRIGHT**,
"the drape takes apron surroundings on both rulesets"), and the primary
FAA read confirms the basis: every apron-surround value in the AC lives
under a *Recommended Practices* heading, so nothing is being retired
against a Standard.

**One apron value is NOT retired and must survive:** the ¶5.9.1
*Standard* 1.5 in ±1/2 in edge drop-off at the apron's paved→unpaved
edge, and — on the FAA ruleset — the ¶4.14.2 item 4 lip (4.5–5.5 % over
3 m), which is written for "an unpaved surface adjacent to a paved
surface" and therefore reaches apron edges too. Retiring the apron
*shoulder band* is not the same act as retiring the apron *edge*.

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

## 6. Owner questions — ALL FIVE ANSWERED 2026-08-08

The questions are kept verbatim below because the *reasoning* behind each
ruling is the reasoning in the question. The answers are in
`docs/RULINGS.md` ("Reg-set rulings", and "105 m precision-approach
graded strip: ADOPTED"); this section is the index, not the authority.

| Q | Owner answer (RULINGS 2026-08-08) |
|---|---|
| **Q1** graded-strip mandatory-DOWN | **ICAO ruleset DROPS it, flagged PROVISIONAL** — revisit at the owner's sim look at a strip without the band. Strip bands stop being emitted at SPJC/SPLP/CYXY/HECA; KCLT keeps the FAA form |
| **Q2** all-taxiway drainage | reading **(b)** — the FAA 1.0 % transverse minimum becomes a **named house constant, PROVISIONAL**, on the ICAO ruleset, satisfying "sufficient to prevent accumulation", **with the ICAO text quoted in the ruleset entry**. The verbatim for both sides is §4.2.1 |
| **Q3** RESA datum | **fix both per source.** ICAO: strip-end datum, 90 m *shall* vs 240 m *should* handled as mandate-vs-recommendation. FAA: the Appendix G length-beyond-end column is a BUILD item requiring the primary text — **now supplied, §3.1**, with its datum footnote |
| **Q4** apron surround | **T2/T3/T4 RETIRE OUTRIGHT.** Nothing mandates them; the drape takes apron surroundings on both rulesets. Confirmed against the AC's *Recommended Practices* heading (§5.1 note) |
| **Q5** 105 m precision-approach graded strip | **ADOPTED as law in BOTH rulesets** — "Follow the guidance 105m graded strip half width for precision approach runways." Recorded as guidance-adopted-as-law, the one deliberate exceedance of bare specification in this reg set |

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

* ~~**FAA AC 150/5300-13B is unreachable from this toolchain.**~~
  **CLEARED 2026-08-08.** The owner supplied the consolidated Chg 1
  "with errata" PDF and the 2025-04-03 errata sheet into `regs/`; both
  were read directly. §3.16 (all of 3.16.1–3.16.6), Tables 3-6 and 3-7,
  Figures 3-33 / 3-34 / 3-35, §3.7.3, §3.7.4, §3.10, §3.12, §4.5.3,
  Tables 4-1 and 4-2, §4.13, §4.14 (all of 4.14.1–4.14.3), Figure 4-29,
  §5.9, §5.10 and **Appendix G Tables G-1…G-12 with footnotes 1–14** are
  primary-verified. **Every FAA row in this document is now
  PV-2026-08-08.** The Chg-1 worry is discharged (§0.1).
* **No FAA VALUE was found wrong.** Every number the repo carried
  survives the primary read. The four DISCREPANT marks are an
  **applicability key** (F-9, RSA width table), a **per-surface band the
  repo collapsed** (F-10, the taxiway lip), **citation pointers** (F-11)
  and **one missing requirement** (R24, TOFA back slope ≤4:1). That is
  the failure mode this document should expect on an edition bump too:
  not a changed constant, a changed *key*.
* **ICAO paragraph numbers are 8th-edition (2018).** F-7's off-by-one in
  `config.py` / `grade_law.py` / `STANDARDS.md` suggests some citations
  were taken against a different edition. Values check out; numbers need
  a sweep. F-11 is the FAA-side twin of the same class.
* **Edition WATCH stands** for ICAO Annex 14 (8th ed. quoted; 9th ed. and
  Amdt 18 not obtained) and for the FAA AC (13B Chg 1 is current as of
  the errata sheet of 2025-04-03; a Chg 2 would require re-running §0.1
  and this section per `regs/README.md` "Updating an edition").
* **AC 150/5320-5D *Airport Drainage Design* remains unreached** (S4).
  Confirmed this round that **no value in this document depends on it**:
  ¶4.14.3 and ¶5.10.1 delegate storm-event design to it, and storm
  design is not a shaped-ground dimension.
* **Extracted primary texts.** `Ortho4XP/tmp/regset/` holds the working
  extractions — `annex14.txt`, `cs-adr-dsn.txt`, and this round's
  `ac13b.txt` (413 pp) and `errata.txt`, produced with
  `pdftotext -layout` from the in-repo PDFs. Lane-local scratch, not
  committed; the FAA PDFs themselves ARE committed (public domain,
  `regs/README.md`), so `ac13b.txt` is reproducible in one command and
  the ICAO extraction deliberately is not.
