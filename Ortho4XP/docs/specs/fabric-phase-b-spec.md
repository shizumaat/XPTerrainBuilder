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
