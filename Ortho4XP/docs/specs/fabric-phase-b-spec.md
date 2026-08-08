# Fabric Phase B — the emission overhaul — spec

Author: lead (Fable), 2026-08-08. Charter: THE FABRIC MODEL ruling +
Phase A outcome (emission VALIDATED; gate kept) + the pin-attribution
outcome (the late-freeze population; release-alone harmful; the
convergence thesis) + the five reg-set rulings + the fully
primary-verified fabric-model-reg-set.md with its Phase-B nuances.
Read all of it before any work; every banner is load-bearing.

> **W2+W3 OUTCOME (2026-08-08, lane/fabricB a0cb6fd —
> READY-FOR-BATTERY).** Ten default-ON flags, per-flag bisection +
> registry twins; retire/flip ledger executed; W3 hard_cat lands with
> ZERO unattributed hard nodes (CYXY late 1,224/0, HECA late
> 6,594/0 — and the classifier separates the strip's own ring freeze
> from pavement welded to a strip, which the pinattr instrument could
> not); gate-OFF whole-pipeline byte-identity proven (cf5165743075,
> three-way chain). DESIGN DECISION RATIFIED (Fable): `is_sparse`
> (density) and `bands_declined` (band scope) are separate predicates
> — every live taxiway maps to ROLE_JUNCTION and the taxiway strip is
> REG SET (R9), so one predicate over-retires; runway+taxiway strips
> stay banded, aprons drape. T6/T7 kept (reasons in fabric_flags.py)
> — RATIFIED. Battery round owes: the CYXY transverse +74 fix FIRST
> (named suspect: lateral-node restoration does not cover the
> groundside/service roles the thinning covers), the gap-fill
> crater-floor question at ICAO aprons (measure, don't assume the
> drape), the convergence-thesis read vs matched control, mesh spots
> (cap traded them away in-lane). POST-BATTERY items: R20 binding
> half (crown minimum not bound); F-8 residual (ICAO taxiway band
> still carries the blended mandatory fall — an ownerable question
> adjacent to ruling 1); fixture re-scope + CYXY lockstep (owner,
> 2026-08-08).**

> **BATTERY-ROUND STOP + LEAD RULINGS (2026-08-08, lane/fabricB
> 190a853; battery deliberately unspent on a tree that must change).**
> MEASURED: CYXY service-transverse fixed exactly (21==control) by
> restoring scope symmetry; the residual is a REAL wide-corridor
> class (axis on the near edge, far edge 17-24 m out; sparse
> interpolation carries an ~8% lateral cross-fall — a parked-aircraft
> lean, exactly the sharp-surface class the fabric model must not
> ship). DEEPER: restoring station nodes at HECA REFUSED the build —
> cross-section nodes minted CROSS EDGES that shortened route paths
> and SHRANK reach-band budgets (49.400 m spread vs a 47.723 m
> route budget → 1,655 inversions): the transverse law and the route
> metric were sharing one graph. CONVERGENCE READ: partial and
> ACCEPTED — total freeze −36.3%, band-freeze −49.6%, zero
> unattributed both arms; the survivor guards KEPT reg geometry
> (runway+taxiway strips); the deeper hardening read defers to
> post-battery. CRATER: the drape handles it (measured; the synthetic
> zero-chains twin is fixture-scale). FREE GREEN: the CYXY
> solver-validator lockstep red passed on the lane — the cleanup
> lane's charter shrinks. Suite: 10 reds, strict subset, no new.
>
> **LEAD RULINGS (from the owner's standing law):**
> R-a — LATERAL NODES ARE ROUTE-TRANSPARENT: cross-section/lateral
> nodes never mint route-graph edges; reach/route budgets price
> along spines and centerlines ONLY. This is the direct application
> of the owner's 2026-07-30 "Reach follows centerlines" ruling; the
> HECA inversion was the violation's measurement. Owner veto welcome;
> no new law is created here.
> R-b — the sparse floor gains its third member, completing the
> owner's rider (spines, curves, AND cross-sections): width-adaptive
> lateral rows at the existing 12 m step wherever pavement width
> exceeds the lateral pass reach, inserted ROUTE-TRANSPARENTLY per
> R-a. The wide-corridor cross-fall class is the defect this kills.
> R-c — the attempt cap resets for the transverse fix: it was
> reached under the pre-R-a frame; attempt 3 (the union span rule,
> currently gated OFF as O4_XSECTION_BRACKET) is authorized under
> R-a/R-b. The station-step re-arm flag flips back ON once laterals
> are route-transparent.
> CONTINUATION: implement R-a/R-b, prove HECA builds + CYXY
> transverse ~control, THEN the full battery per the original
> charter.**

> **R-a/R-b ROUND OUTCOME + LEAD RULINGS 2 (2026-08-08, lane/fabricB
> ac5ddbe).** R-a LANDED AND PROVEN: lateral feet are recorded at
> insertion and skipped by the spine walk — the HECA inversion
> refusal becomes rc 0 with ONE sub-materiality residual; the twin
> proves exact route-length invariance plus non-vacuity. R-b plants
> the validator's own span selection (verbatim rule, three-number
> lockstep twin) — and the class did NOT close, with the mechanism
> measured: the solve places planted far-edge feet within 2 cm of
> the straight chord and the decimator losslessly collapses them
> (35→2), i.e. THE CENSUS PRICES A PAIR THE SOLVE NEVER BINDS — the
> lockstep-gap class (the near-miss-frontage precedent).
> RULING (1): SOLVE-SIDE. Cross-section pairs enter the solve's law
> context — priced ⟺ bound, the generation-binding law. A fourth
> emit-survivor class is REJECTED: keeping unbound feet would emit
> the same unlawful chord with more vertices; once the pairs bind,
> the solved feet leave the chord and survive the decimator by
> construction. Fresh frame ⇒ fresh attempt cap.
> RULING (2): the two CYXY route-band floor rows (0.074/0.054 m,
> junction-adjacent) are SUB-MATERIALITY under the ruled bar (no
> sharp-guard trip) — NON-BLOCKING for R-a; the route-band twins
> join the group-1 fixture re-scope in the cleanup lane; the rows
> stay visible as named residuals.
> Riders: the per-station 80 m STRtree query is a final-profiling
> candidate (noted, not chased); the 18 suite errors from the
> backgrounded run are unattributed worker noise — the final suite
> re-runs FOREGROUND uncontended before any read.**

## The convergence thesis (why #2 and #3 are one round)

The late final_grade_projection feature-weld agreement gate hardens
~9,000 nodes per airport with no seeder record, ~93% of them welded
to the GRADED STRIP. Reg-set ruling 1 (PROVISIONAL) retires strip
bands at ICAO airports; the fabric model retires all non-reg
adjacent-ground geometry. Retiring the geometry retires the welds
that necessitate the freeze — the hardening structure is dissolved
by emission redesign, not by unfreezing (measured: unfreezing alone
is +62 airside).

## Work items

**W1 — reg-set encoding (mechanical, from the verified table):**
the ruleset constants per fabric-model-reg-set.md, including the
four DISCREPANT key corrections (three-axis RSA widths incl. the
missing A/B-III/IV columns; TWO lip families — runway edge 3–5%,
taxiway/apron edge 4.5–5.5% carved out of the TSA band; taxiway
shoulder width by TDG; citation pointers), the per-end RSA length
function (RDC × visibility × vertical guidance × stopway; CIFP
supplies the guidance key), R24 (TOFA back slope ≤4:1, FAA-only),
the 1.0% taxiway cross-fall (FAA verbatim; ICAO PROVISIONAL house
constant, text quoted), and the 105 m precision strip labelled
OWNER-ADOPTED-BEYOND-CITATION on the FAA ruleset. Emitters and
validators read the SAME entries (lockstep; twins per family).

**W2 — the emission switch (the validated gate, generalized):**
sparse lawful emission default-ON for all pavements and pads (the
Phase A mechanics verbatim: law vertices + 12 m spine stations +
XY_TOL 0.02 m curves; MAX_CHORD lifted). RETIRE: fan zones;
non-reg adjacent-ground bands/rings/walls/feather everywhere;
strip bands at ICAO airports (ruling 1, gate-revertable for the
owner's sim look); general stationing beyond the floor. KEEP: FAA
strip forms at FAA airports per W1 values; apron-EDGE drop-off
Standard and lip (they survive ruling 4 — the verification pass's
nuance); reg drainage (crowns, pavement-edge, all-taxiway
cross-fall); carve structures.

**W3 — the freeze, redesigned with its geometry:** the agreement
gate gains a seeder record (`hard_cat`, instrument truth — 9,838
unattributed hard nodes is itself a defect); its scope re-derives
from the SURVIVING reg geometry only; the 145 both-frozen rows and
the 27 frozen-end aprons re-read on W2 arms (complete the class
table: one SPLP + one KCLT build). Prediction to test, not assume:
the freeze population collapses with the retired welds.

**W4 — acceptance and re-baseline:** full battery A/B vs matched
controls, both worlds where oracle-relevant: law-true and
adjudicated per family, sites + actionable (the floor), every moved
row attributed to a named class — lawful reclassifications reported,
airside-negative movement beyond them is a STOP; -10447 re-read as
its 94 rows; mesh area/aspect tables per airport (no new classes);
build-time expectation DOWN (sparse + retired geometry) — quote
phase notes; the frontweld parked hygiene (lane/frontweld 2d2a8e7)
re-measured on the W2 world and landed if ~free. Then the owner sim
pass (HECA + CYXY + KCLT — the ICAO strip look is the ruling-1
provisional revisit) and the frame-of-record re-mint.

## Sequencing and budget

W1 first (constants; offline + twins). W2 behind its gate with
per-airport A/B pairs; W3 on W2's arms; W4 last. Honest budget:
~12–16 harness builds + 4 mesh runs across the round, per-lane caps
stated in each brief. The concurrency trap (guarded builds vs
unguarded suites) applies to every lane.

## STOPs

Any reg row that cannot be encoded as specced; airside-negative
movement beyond attributed lawful reclassification; the freeze
population NOT collapsing on W2 arms (that falsifies the convergence
thesis — report, do not improvise a second unfreeze); ruling-1's
provisional strip drop failing the owner's sim look (gate reverts).
Deviations: STOP-and-report for Fable review.
