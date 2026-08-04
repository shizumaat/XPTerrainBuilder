# Ref-pull interim round: the Pareto weight, the loud stall, the back door

Fable spec, 2026-08-04. From s7_attrib/ (read §§2-4 first). Lines against
c46d800. BINDING: docs/RULINGS.md. The ENDGAME (seam-continuity as a
constraint, pull deleted) is a separate spec in design; this round lands
the measured interim.

## §1 O4_YIELD_REF_WEIGHT default 0.2 → 0.02
The 0.2 entered in a sweep commit with no measurement; 0.02 is the
measured Pareto point (keeps ~90% of the displacement benefit for ~65%
of the cap excess; battery census −852; restores the full projection
budget; seam regression held to +11 rows vs w=0's +88; CYXY's outright
minimum). This is an ungated DEFAULT change: full-battery verification
(all FIVE airports — s7_attrib measured three; SPLP+KCLT are owed),
new default baselines minted 2x each, census matrix quoted both frames
vs the w=0.2 arms. Pre-registered: HEAZ/CYXY/HECA reproduce s7_attrib's
w=0.02 numbers exactly; SPLP/KCLT improve-or-hold (a rise at either =
STOP); seam rows ≤ +11 battery-wide.

## §2 The equilibrium break becomes a loud stall
one_solve.py:1283's steady-state break exits UNCERTIFIED as silent
success (HECA finals: 38 sweeps of 2400, 6.74 m residual). Convert: the
break stands (terminating is correct) but emits the stall report
(the existing stall-report machinery — detection data, carrier, sweeps
abandoned) and never sets certified. Report-only; byte-inert on
surfaces (prove: hashes unchanged vs §1's arms).

## §3 O4_CORRIDOR_REF_STRING measured A/B (adjudication, not a flip)
Default "1" promotes rod-held string values to z_ref on 2,020 HEAZ
nodes — the paused string acting as a surface authority through the
back door (contradicts the string purpose statement). One A/B arm per
airport (=0 vs default) at the NEW weight: census both frames, seam
rows, the displacement sum. Deliver the adjudication table for the
lead's ruling — do NOT change its default this round.

## Acceptance
Suite same 23 reds (§1 changes surfaces — enumerate any law-true test
expectation that legitimately moves, cite per test); runway vertices
byte-identical at all five; only the sanctioned timing instrument's
exclusive-run output is quotable (spot-check CYXY+HECA vs baselines —
expect neutral-or-better: the restored projection spends more sweeps;
quote honestly, the 1% trigger applies); foreground; per-arm envs;
worktree if main is occupied; do NOT commit. STOP: any airport's census
rises; seam > +11; a §2 hash change; second miss.

## LEAD ADJUDICATION (2026-08-04 evening; evidence scratchpad
## refpull_interim/, lane worktree refpull-lane, uncommitted)

Sections 1-3 complete and measured: battery law-true 13,199 -> 11,963
(-1,236; SPLP -24, KCLT -360 — both previously-unmeasured airports
improve, no airport rises); seam exactly +11 (at bound); s7_attrib
reproduced bit-for-bit at three airports on a proven same-code tree;
two strict-xfail DRAIN-LEDGER markers legitimately closed (the CYXY
1.9%-vs-1.5% apron pair now grades in bounds — a real adjudicated
drain-list defect closed by the weight change). Honest cost noted:
HECA building|building 440->486 (the frontage class pays for the
weaker pull; KCLT's 46->8 more than offsets battery-wide).

1. **§3 RULING: O4_CORRIDOR_REF_STRING default STAYS "1" for the
   interim.** Closing the back door now trades KCLT +95 / HEAZ +5 /
   CYXY +1 / SPLP +1 for HECA -196: four of five airports worse, the
   FAA fixture worst. The purpose-statement violation is real but its
   correct remedy is the seam-continuity endgame (the refs channel
   dies WITH the pull, corridor shape carried by composed rods) — not
   an interim flip that degrades surfaces before the replacement
   exists. The adjudication table is the endgame round's baseline.
2. **Deviation ACCEPTED with attribution:** HECA 2/514 runway-vertex
   moves (0.16 m) are the APRON side of shared welds — runway-
   EXCLUSIVE vertices byte-identical at all five, the runway solve
   untouched, no runway census row minted. Acceptance for this round
   is re-expressed as runway-exclusive byte-identity; the shared-weld
   consensus class is the CONSENSUS-RETIREMENT round's named
   territory (O4_SINGLE_AUTHORITY_EMIT).
3. **Timing spot-check GATES THE COMMIT** (hard law: the restored
   projection budget plausibly costs solve time — HEAZ ref-call sweeps
   36 -> 2400). PENDING-EXCLUSIVE for a quiet machine. FORM AMENDED:
   recorded baselines read 13-32% fast (machine drift), so the honest
   instrument is a same-session A/B — exclusive --runs 2 at CYXY+HECA
   on BOTH the old-default and new-default arms, quoting the A/B
   delta against the 1% trigger, not the stale-baseline comparison.

## §3 RULING SUPERSEDED (owner, 2026-08-04, RULINGS.md): retire the
## back door NOW. O4_CORRIDOR_REF_STRING default → "0" rides this
## lane; new-default baselines (w=0.02 + ref=0) minted 2x at all five;
## the transitional census cost (KCLT +95 et al.) is ACCEPTED by
## ruling — no degradation-shield interims. The timing A/B compares
## old default (0.2, ref=1) vs the NEW default (0.02, ref=0).

## TIMING ITEM DROPPED (owner policy, RULINGS 2026-08-04 defer+tripwire):
## the exclusive A/B no longer gates the commit; acceptance is complete
## when the corridor-ref flip + new-default baselines land. Ledger
## tripwire only.
