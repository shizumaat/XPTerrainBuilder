# Cycle 10 — road-feed verdict follow-through — spec

Author: lead (Fable), 2026-08-07. Charter: the cycle-10 clean-tree
probe verdict (HANDOVER §0 block "CYCLE-10 PROBE VERDICT"; raw
artifacts `.claude/worktrees/c9feed/Ortho4XP/tmp/c10/`, arms A
`b6936ed` / B `0c003ba`, worlds −500/10,000). Owner sanction: the
2026-08-07 "c9feed probe runs parallel" ruling; instrument-truth is
standing law and puts fix 1 first.

## Fix 1 — the transverse::apron|apron instrument hole (ZERO builds)

LAW (already the instrument's own stated rule — this makes it hold):
a transverse cross-section minted from a SERVICE axis must never
carry a pair in which either role is non-groundside
(`_axis_is_svc` … `not in _GROUNDSIDE_ROLES`). Rows violating it are
instrument defects, not surface findings.

Work: locate the stamping site in the c9feed instrument
(`tools/check_grade.py` sha `6016aed1…` on the lane branch — NOT
main's, which differs) and enforce the rule at mint time.

Acceptance (offline re-census of the four `tmp/c10` patches, one
instrument, frames labelled):
1. Every removed row is provably service-axis-minted (dump the
   removed set with axis ids; a single removed row NOT traceable to a
   service axis is a STOP — the predicate is wrong, do not widen).
2. The A→B delta on `transverse::apron|apron` collapses to ~0
   (was +136 @10k own-frame / +143 @−500); B 10k own-frame airside
   lands ≈4,474 (the lane's own base-frame cross-check).
3. No other class moves at either arm or world.
4. Twin fixture: a service-axis transverse row with a non-groundside
   pair asserts REFUSED-at-mint; a groundside pair on the same axis
   asserts kept. Registered per the LAW_FAMILIES lockstep rule if the
   family surface is touched.

## Fix 2 — probe hooks become committed, gated code

The cycle-9 probe died with its dirty tree; that is why cycle 10 had
to re-derive it. Land `O4_PROBE_NO_SERVICE_EDGES`,
`O4_PROBE_NO_MOUTHS`, and the new `O4_PROBE_NO_ROAD_PAIR_LAW`
(fix 3's knife) as default-OFF env gates in the lane branch, each
with a one-line docstring naming what it withholds and a twin
asserting default-OFF inertness (byte-identical patch with gate
unset — the 20260731d evidence pattern).

## Measurement M1 — the pre-registered pair-law knife (2–4 builds, cap 6)

Hypothesis (pre-registered): the surface half of the +604 —
`within_shape::apron|apron` 3,541→3,985 (+444 @10k) — is carried by
the roads' PAIR LAW inside the airside solve, not by graph edges
(eliminated) or mouths (eliminated).

Arms: B (`0c003ba`) with `O4_PROBE_NO_ROAD_PAIR_LAW=1` vs B unmodified,
both worlds, `build_airport.py HECA` through the ledger, one build
per process, clean worktrees, body-sha identity discipline as in the
probe report.

Read: does `within_shape::apron|apron` return to ≈3,541 @10k with the
knife in? Report the class table both worlds, both frames (own/base).
STOP at findings — the surface CURE is a lead/owner design decision;
this measurement only names the carrier.

## Budget

Fix 1 + fix 2: 0 builds (offline censuses + pytest via run_with_ledger).
M1: 2–4 HECA-class builds, hard cap 6. No timing claims. Build-time
impact: fix 2 gates are default-OFF (zero production cost); fix 1 is
instrument-side only.
