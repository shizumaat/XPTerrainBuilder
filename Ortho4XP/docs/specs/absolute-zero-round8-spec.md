# Absolute-zero round 8: provisional open-boundary floor + zone-1/2 tear
# attribution + portal-step attribution + strip recon

Fable spec, 2026-08-01. Owner rulings this implements (same day):
* **Open-boundary unwalled-terrace floor → 15 m PROVISIONAL** ("I want to
  see it with no wall, raise it to 15 m until I can view some test cases
  in the sim"). Applies ONLY to tear pairs classified OPEN-BOUNDARY
  (ungraded ground in the pair interior, the v2 clause); zone-1/2 and
  pocket tears keep the 1.0 m floor — they are real defects.
* **B1's permanent fix is STRIP RESTRUCTURING** (strips should not be
  separate shapes across steep relief) — this round does the RECON for
  that spec, not the change.

Line numbers against `e6f387d`. Batched per the batching policy: no
airport builds — every part runs on existing patches + code reading.

## Part A — FIX (validator): the provisional open-boundary floor

`tools/check_grade.py`: new constant
`STRIP_SEAM_OPEN_BOUNDARY_FLOOR_M = 15.0` with a comment marking it
PROVISIONAL (owner 2026-08-01, pending in-sim review; the pre-ruling
floor was `STRIP_SEAM_TEAR_MIN_STEP_M` 1.0). In
`_check_strip_seam_tears`, a pair that satisfies the v2 OPEN-GROUND test
(interior leaves the graded domain > 1 cm) is flagged only if its step
exceeds the open-boundary floor; pairs failing the open-ground test keep
the 1.0 m floor and every existing rule (wall straddle etc. unchanged —
walls can still dissolve zone-boundary rows when the owner lowers the
floor later). Tests: open-boundary 9.61 m step passes, 15.1 m fails;
zone-1/2 2.0 m step still flagged. Re-run the round-6 quantification
instrument on all 8 patches; pre-registered: open-boundary column → 0
both arms; α tears 44 → 25, β 380 → 318; acceptance arithmetic α ~596
(−class-C = 548), β created ~521. Report exact.

## Part B — ATTRIBUTION: the zone-1/2 tear class (now the largest: β 318
= CYXY 163 / HECA 93 / SPLP 62; α 25)

Tears INSIDE the graded corridor — law fully applies. Attribute with the
round-6 toolkit (existing patches, identity joins, code reading): per
row, which two strips/shapes disagree, whether the pair is a
band-vs-band, band-vs-pavement-weld, or strip-vs-strip seam; whether the
coincidence-vs-radius emitter mechanism (round-6 Part 2: the blend only
levels coincident points, `_EDGE_COINCIDE_TOL_M = 0.01`) explains them;
α/β membership and the string-displacement dependence (β/α ≈ 13× —
why?). Deliver named classes with code-cited mechanisms, dz
distributions, and the fix-shape recommendation per class (emitter
radius-keying? blend window? weld coverage?). No fixes.

## Part C — ATTRIBUTION: census priority 2, the portal-step classes
(B 71 rows / 2 clusters + G 28 rows / 2 sites; all survive into β)

Two post-solve emitters meeting with no mutual conformance law
(census: `_POSTSOLVE_FEATURE_OWNER_ROLES`, conformance is
airside-directed only, `pipeline.py:5324-5349`). For the 4 sites:
which emitter wrote each side (values + code path), what rule SHOULD
bind them (candidate: the junction of two post-solve features conforms
to whichever is airside-closer, or they share a seam profile), and
whether HECA's portal and SPLP's portal are the same defect. Evidence
for a fix spec; no fixes.

## Part D — RECON for the strip-restructure spec (owner: B1 permanent)

Read the graded_strip cutting/emission path (strips.py / adjacent_ground
band builder — find where strip shapes are SPLIT into separate shapes)
and report: what determines strip boundaries today (length? role
change? band edges? tile cuts?); where the B1 rows' strip pairs got
split (join round-6 part2_rows.json geometry to the splitting code
path); what a merge/re-cut across steep relief would touch (data
structures, per-band node_altitudes, downstream consumers); and the
constraint set a Fable restructure spec must respect. Cite file:line
throughout. No design, no changes — the lead writes that spec.

## Acceptance

Part A: tests + quantification table + arithmetic. Parts B-D: reports.
Files editable: tools/check_grade.py, tests/test_check_grade_strip_seam.py
ONLY. No builds (the validator is not in the build path; identity is
unaffected — do not spend builds proving it). Suite: the check_grade +
chip suites only (the full suite ran at e6f387d; nothing else changed).
Budget: offline analysis + one scoped suite run. Honest total quoted.

## Out of scope

The wall emitter (deferred by the 15 m provisional ruling); the strip
restructure ITSELF (Fable specs it from Part D); census priorities 3-5;
the probe-purity fix and SPLP bisect (round 7, running); gate flips.
