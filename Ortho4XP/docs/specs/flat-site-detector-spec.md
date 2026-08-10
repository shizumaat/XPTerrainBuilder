# FLAT-SITE detector — spec (2026-08-09, FROZEN; pre-ship mode)

Author: lead session (Fable). Charter: owner 2026-08-09 — "we want to
see if we can implement a simplification for airports like OTHH that
are pretty much at sea level, and are genuinely flat... I'd like to
add a test for this type of situation so we can handle it better...
recommend a plan for identifying this scenario at other airports."
Phase 1 of the plan the owner approved ("Proceed"): the DETECTOR,
report-only, no behavior change. Phase 2 (FLAT-SITE solve mode at the
CIFP consensus elevation) is a separate spec, written after the owner
reads this detector's sweep. Rulings: docs/RULINGS.md ("Instrument
truth is law"; "CIFP thresholds absolute for v1"; PRE-SHIP MODE).

## 1. Measured foundation (2026-08-09; cite, don't re-derive)

OTHH, the type specimen: CIFP thresholds all 13 ft = 3.96 m (spread
0); apt.dat 13 ft; the pack's 9,226 non-drainage object seat requests
median 4.00 m (|Δ vs CIFP| = 0.04 m, p95−p5 2.17 m); the raw DEM
(Viewfinder 3-arcsec, 93 m posts, integer metres) over the airport
extent reads median 0 m — 4 m BELOW instrument truth, 69 % exactly 0
(coastal/reclaimed void-fill), p95−p5 6.0 m, plane-fit slope 0.067 %,
residual std 1.82 m. Every metre of "relief" the solver chases there
is DEM noise. Negative type specimen: HECA — ~85 m of REAL relief
(DEM and CIFP agreeing; memory/rulings) — must never classify flat.

## 2. The detector

Runs at pipeline entry (phase 1, once the CIFP thresholds, pavement
extent and DEM are in hand), pure measurement:

* **S1 — threshold consensus:** spread = max − min CIFP runway
  threshold elevation < `FLAT_SITE_THRESHOLD_SPREAD_M` (**5.0 —
  owner ruling 2026-08-09**: "CIFP threshold spread < 5m should be a
  flat candidate"; the original 0.5 was the lead's provisional
  value). Consensus Z0 = their mean. Phase-2 note: at nonzero spread
  the RUNWAYS keep their CIFP-absolute profiles (standing ruling);
  the flat elevation applies off-runway — the phase-2 spec owns that
  seam.
* **S2 — no credible DEM relief:** over (pavement ∪ boundary) ⊕
  `FLAT_SITE_MARGIN_M` (200 m — the margin ring is load-bearing: a
  graded PLATEAU in hilly terrain shows its relief in the ring even
  when the pavement is flat): plane-fit slope ≤
  `FLAT_SITE_MAX_SLOPE_PCT` (0.15) AND p95−p5 relief ≤ the DEM
  source's noise floor: `FLAT_SITE_RELIEF_FLOOR_BY_CLASS` — ≥3-arcsec
  sources 8 m, 1-arcsec 5 m, sub-10 m rasters 2 m. A metre-credible
  (LIDAR-class) source short-circuits: verdict `lidar_credible`,
  flat-candidacy not applicable (the DEM is trustworthy; the normal
  path already handles a flat site correctly under a truthful DEM).
  Source class comes from the EXISTING DEM/inset provenance surface —
  if no clean provenance is reachable at pipeline entry, STOP and
  report; never invent a second provenance.
* **S2a — THE SEA-BAND EXCLUSION (v2 amendment, 2026-08-09; from
  the six-airport sweep).** At sites whose Z0 sits meaningfully above
  sea level (Z0 ≥ `FLAT_SITE_SEA_BAND_MIN_Z0_M`, 1.0 — a below-sea
  site like Schiphol keeps every sample: its zeros ARE plausible
  terrain), DEM samples at ≤ 0.0 m are SEA SURFACE or VOID FILL, not
  terrain testimony: they are EXCLUDED from S2's relief percentiles
  and plane fit, and the excluded fraction is reported in the record
  (`s2_sea_excluded_frac`). Measured basis: every refusal in the
  owner's six-airport sweep is this contaminant — VHHH judged at DEM
  median 0.33 m vs instrument 7.32; YSSY carrying p5 −2.67 m INSIDE
  the reclaimed airport; KSFO's "slope" being the land-to-bay-zero
  gradient; and OTHH itself passing only by dilution (69 % literal
  zeros). Sea-excluded statistics measure the LAND the airport is
  built on. Consequence to record, not hide: coastal near-misses
  (OTBD, OTBH) may lawfully flip to flat_candidate under clean land
  statistics — every flip vs the v1 sweep is reported.
* **S3 — DEM-vs-instrument offset** (reported, never gated):
  |DEM median − Z0|. Large offset at a flat-candidate site is
  EVIDENCE FOR DEM unreliability (OTHH: 3.96 m), not against
  candidacy.
* **S4 — pack-object consensus** (confirmatory, custom packs only,
  only when a prior post-mesh request sidecar exists): |median
  non-below-grade seat target − Z0| ≤ 1.0 and p95−p5 ≤ 3.0. Absent
  data → `no_data`, never a fail.

VERDICT `flat_candidate` ⇔ S1 ∧ S2 (and not lidar_credible). Output:
one log line at verbosity 0 and a sidecar evidence key
`site_class` = {verdict, z0_m, s1_spread_m, s2_slope_pct,
s2_relief_m, s2_source_class, s3_offset_m, s4} — register the key in
`check_grade.SIDECAR_EVIDENCE_KEYS` (the harness sidecar-contract
twin fails otherwise; that failing is the signal to register, not to
work around). NO behavior changes on any path.

Constants in config.py beside the other site/DEM knobs, comments
citing §1's measurements.

## 3. The sweep (the deliverable the owner reads)

Run the detector IN-PROCESS (no harness builds — CIFP + DEM + extent
reads only) for every airport the shared corpus has DEM + CIFP for:
OTHH, OTBD, OTBH, HEAZ, HECA, SPJC, SPLP, CYXY, KCLT (+ KBNA if its
tile data is present). Report one table: per airport, all four
signals + verdict. Recorded expectations: OTHH → flat_candidate;
HECA, KCLT, CYXY → not. Any surprise is a FINDING to report with its
numbers, never silently accepted or "fixed" by tuning a constant.

**Owner-named flat test airports (2026-08-09): VHHH, VMMC, YSSY,
KSFO, KOAK, KBOS** — expected flat candidates; any that refuses is a
FINDING reported with its numbers. Their base rasters (N22E113,
S34E151, N37W123, N42W072) are not in the shared corpus: fetch them
LANE-LOCAL for the sweep (the sweep tool takes a DEM path — no
shared-repo write, no corpus ceremony); if these airports later
become fixtures their tiles join the corpus through the recorded
refresh path, not as a sweep side effect. Document the download
source per tile in the sweep output.

## 4. Tests (pre-ship mode: these files only, run once)

Synthetic fixtures: flat DEM + identical thresholds → candidate;
plateau (flat pavement, sloped margin ring) → NOT (the ring catches
it); identical thresholds + real relief → NOT; LIDAR-class source →
lidar_credible short-circuit; missing CIFP/DEM → `no_data` verdict,
never a crash; sidecar-key registration twin.

## 5. Budget

One Opus implementer; unit tests once; the in-process sweep; ZERO
airport/tile builds. Ledger line goes to docs/DEFERRED_VERIFICATION.md
(battery patch-level effects: none — report-only).
