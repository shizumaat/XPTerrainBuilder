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
