# Pad rod coupling — the apron edge at a pad face references the seat

Owner approval 2026-07-29 ("go ahead with the pad rod coupling").
Completes bounded-yield-spec §7.3 at building faces; governed by the
pad-weld ruling ("airside pavement welds SMOOTH to a building's
airside face") and "the seat is the rod for the building."

## 1. Defect (measured, post band-single-source)

The corrected route-metric band raised apron ceilings more than pad
seats: HECA strip SEAM tears 22 → 37; worst pad-frontage pair at
building199's face 2.89 m over 2.94 m (98.3 %).  Cause is the §7
implementation's documented deviation: z_ref = yield-entry state —
the apron fabric's entry state near a pad is phase-A/B-shaped and now
solves ABOVE the pad seat, so the two references disagree exactly at
the weld where the law says smooth.  The pads themselves are correct
(they end exactly at their seats); it is the APRON SIDE's reference
that ignores the seat priority.

## 2. Semantics (fixed)

For every airside soft-fabric vertex WELDED to a building pad face
(canonical shared vertex with the pad ring, or within the weld
tolerance — the same contact set the near-miss frontage law uses):
its z_ref IS the pad's seat value at that contact.  Fabric outward
strings from that value at its own transverse rate (§7 "aprons grade
out"), so the frontage transition is graded, not stepped.  Priority
order unchanged: anchors > seats (now including their weld shadow on
the neighbouring fabric) > strings.  Where a fabric vertex touches TWO
pads with different seats, reference the nearer contact and let the
caps grade between (pads may legitimately differ — the inter-pad
step exemption stays).

## 3. Scope

z_ref field construction at the yield sites (`route_profile/solve.py`,
the §7 reference machinery) — this is a reference-FIELD change; no new
projection machinery, no band changes, no grade_graph/pavement_scoring
changes.  Gate `O4_PAD_ROD_COUPLING` default ON, `=0` byte-identical.

## 4. Acceptance (emitted patch; cheap-first)

* Offline replay first (the §7 replay harness): building199-face
  contact vertices end at the seat, outward fabric grades ≤ its caps.
* HECA build: strip SEAM tears ≤ 22 (pre-regression level; target the
  pad-face contributors → ~0), the building199 pair ≤ weld-tolerance
  class (≲0.2 m), seam site stays ≥ 106-class, corridor sag not
  worsened (report the number), within-shape count reported.
* Flats CYXY/SPJC/SPLP: step/tear sections stay ZERO; counts reported.
* One battery on the final state; full matrix.

## 5. Constraints

Same as rod-compose-and-band-single-source-spec §Constraints
(main tree, venv, one build/process, no KCLT, git log/status before
and after every build — another session commits omnibus sweeps —
PID/artifact-verified waits, report-don't-improvise).  STATUS/memory
documentation stays with the parent session.
