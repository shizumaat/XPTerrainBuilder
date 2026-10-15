# Law-table audit against the regulations (2026-10-15)

Scout `lawaudit`, read-only, for RULINGS 2026-10-15k ("every law-table value that
the standard states by runway code or by instrument status is read by that code
and status"). Standards: FAA AC 150/5300-13B Chg 1 (`Ortho4XP/regs/`), ICAO Annex
14 Vol I 8th ed. (local extraction). TP 312 was not available locally. Engine
runway classes come from the sidecars' `runway_caps`. Instrument status comes
from CIFP, for NLWF, CYXY, KBJC and KASE only.

Two errors were already found and are corrected on PR #763 (15k): the code-1 RESA
of 60 m, and `[icao.eat]` 2 % from 60 m applied at every code.

## 1. Wrong or collapsed values (worst first)

| # | Key / file:line | Engine | Standard | Verdict | Sweep airports |
|---|---|---|---|---|---|
| 1 | `zones.toml:27` `band_max_down` (read `tables.py:441`) | 3 % code 3/4, 5 % code 1/2 | Annex 14 §3.4.15: 2.5 % code 3/4, 3 % code 1/2 | WRONG VALUE (FAA-style numbers; 15c (4) "ICAO keeps 3 %" restated it) | NLWF CYXY SPJC HECA OTHH |
| 2 | Airside grade-change rate, `constraints/no_step.py:1270` reads `strip.arc_rate` (`rulesets.toml:114`) | 2 % per 30.5 m on all airside pavement | Taxiway: Annex 14 §3.9.9 1 % per 30 m (C–F), 1 % per 25 m (A/B); FAA §4.14.1 1 % per 100 ft, 3 % max change | WRONG VALUE (2× loose) + COLLAPSED | all |
| 3 | Taxiway graded strip `zones.toml:31`, buffered from the pavement EDGE (`planar/zones.py:318-323`) | A 10.25 … F 22 m from the edge | Annex 14 §3.11.4: from the CENTRELINE; FAA §4.5.3 TSA = wingspan (half 7.5/12.0/18.0/26.0/32.6/39.9 m) | WRONG BASIS (code C reaches 20 m instead of 12.5 m; FAA airports get the ICAO table) | all |
| 4 | FAA runway band: main `zones.toml:27` by length code; #763 `band_max_down_faa` 5 % | main 3 %/5 %; #763 5 % everywhere | AC Table 3-6 S-3: 1.5–3.0 % AAC C–E, 1.5–5 % A/B | COLLAPSED; 15c (4) conflicts with 15k (owner question) | KASE KCLT KDEN KATL KBJC |
| 5 | FAA rise beyond the end, `[faa.eat]` `rulesets.toml:212-213` (`tables.py:579-583`) | 40:1 from the end after a 61 m hold | §3.16.5 (3): no penetration of the approach surface / clearway; Tables 3-2…3-4: 20:1 or 34:1 from 61 m, 30:1 from the threshold | WRONG SURFACE + COLLAPSED (at 61 m engine allows +1.52 m where 34:1 allows 0) | instrument FAA runways |
| 6 | ICAO RESA code 3, `rulesets.toml:130` | 150 m | §3.5.3 ≥ 90 m, §3.5.4 recommends 240 m | WRONG VALUE; code 2 non-instrument 90 m COLLAPSED (30 m recommended) | none |
| 7 | FAA RSA by letter, `zones.toml:25` / #763 `rsa_length_m` | C–F 76.2 m half × 304.8 m | App. G Table G-5: A/B-III 300 × 600 ft; A/B-I/II lower-visibility 300 × 600 ft | COLLAPSED (ADG, visibility) | none confirmed |
| 8 | RAOA, `strips.py:785` (`rulesets.toml:138-140`) | every ICAO runway end | §3.8.1: precision approach runways only | COLLAPSED (instrument status), stricter | NLWF CYXY |
| 9 | Zone-1 lip `zones.toml:14-16` | 3–5 % over 3 m, every class | FAA taxiway §4.14.2 (4): 5 ± 0.5 %; ICAO §3.4.15: up to 5 %, no minimum | COLLAPSED | FAA airports |
| 10 | Apron cap `rulesets.toml:27` | 1.5 % hard, 1 % preferred, stands included | ICAO §3.13.5 / FAA §5.9.2: 1 % at stands | COLLAPSED (owner ruled 06w) | all |
| 11 | FAA `shoulder_transverse_max` `rulesets.toml:168` | 2.5 % | Table 3-6 S-2: 1.5–5.0 % | stricter (owner ruled 13dd); 1.5 % minimum missing | FAA airports |
| 12 | Code-1 instrument, `rulesets.toml:126`, `zones.toml:24` | strip end 30 m, graded half 30 m | §3.4.2 60 m; §3.4.8 40 m | COLLAPSED | none |
| 13 | Code-3 end zone `runway_profile.py:280` | always dropped | §3.1.14: 0.8 % for Cat II/III at code 3 | COLLAPSED (no approach-category witness) | none |

## 2. Checked and correct

- **ICAO runway:** longitudinal 2 / 1.5 / 1.25 %; slope change 2 / 1.5 %;
  curve length 75 / 150 / 300 m per 1 %; transverse by letter; shoulder 2.5 %.
- **ICAO strip:** longitudinal; end length at codes 2–4; graded half-width
  75 / 40 / 30 m.
- **ICAO RESA:** 5 %; width rule.
- **ICAO RAOA:** figures correct.
- **ICAO taxiway:** longitudinal and transverse by letter; strip 5 % down.
- **FAA runway:** longitudinal; 0.8 % end zone; grade change; curve lengths;
  transverse.
- **FAA RSA beyond the end:** first 61 m 0 to −3 %, then 5 % down,
  ±2 % per 30.5 m.
- **FAA taxiway:** longitudinal and transverse; TSA 1.5–5 %.
- **FAA apron:** minimum 0.5 %; change 2 %.
- **FAA EAT:** 40:1, 457.2 m, tail heights.

## 3. Engine-invented values (not defects by themselves)

- `pavement_max_grade` 5 %, road 10 %, parking 5 %, ramps (VDOT/AASHTO).
- `apron_fan_ramp_max`; the ICAO hard apron 1.5 %.
- The provisional ICAO `strip.arc_rate`, still read (`strips.py:255`,
  `no_step.py:1270`).
- The ICAO lip minimum 3 % and band minimum 1.5 %.
- `[common.eat]`: 600 m maximum crossing, 75 m gap, 150 m along, minimum code 3.
- No-step window 150 m / k 16; `groundside_ramp_max`.

## 4. Missing witnesses and missing laws

- **Missing witnesses:**
  - Code number comes from physical length, not the reference field length.
    The classifier exists twice: `airport/load.py:47` and
    `constraints/strips.py:105`.
  - Runway letter is a width proxy (`load.py:51-53`) that moves FAA widths up
    a class: 60 ft → B, 100 ft → D, 150 ft → E.
  - FAA AAC has no witness, yet every AAC-keyed grade reads the width letter.
  - Also missing: precision category, approach visibility, the ≤ 30,000 lb
    taxiway case, and clearways.
  - The taxiway letter does have a witness: the apt.dat 1202 width class.
- **Laws with no generator:**
  - ICAO §3.1.13 mean slope 1 % at code 3/4 (`rulesets.toml:88` cites §3.1.13
    but carries the §3.1.14 values).
  - Minimum distance between grade changes (ICAO §3.1.18; FAA).
  - FAA C–E: no grade change in the end quarters.
  - The ungraded strip beyond the graded portion (§3.4.16): `ungraded_max_up`
    is read by nothing.
  - The taxiway strip beyond the graded portion (§3.11.6).
  - The FAA ROFA.

## 5. Not verified

- TP 312.
- CIFP approach types at SPJC, HECA, OTHH, KCLT, KDEN and KATL.
- Real FAA approach categories.
- Annex 14 amendments after the 8th edition.
- No builds; no row counts.
