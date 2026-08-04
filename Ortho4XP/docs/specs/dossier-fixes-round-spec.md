# Dossier fixes round: the named small fixes from the carrier attribution

Fable spec, 2026-08-04. From carrier_attrib/DOSSIER.md (read first).
Lines against ec45709. BINDING: docs/RULINGS.md; convergence guards.
Four small, disjoint fixes; the spine-freeze class and the terrace/
split-seat laws are separate upcoming specs — do NOT touch them here.

## §1 The envelope-gap pinned-set fix (instrument correctness)
one_solve._stall_envelope_gap (:768-800) marks a node pinned if it has
zero weight on ANY edge; correct: a node is pinned only if it NEVER
carries positive weight on any incident edge (the dossier measured 666
of 3,300 "pinned" nodes moving up to 0.85 m). Fix the set construction;
the report's adjudication class may flip on some carriers (HEAZ call07
flips INFEASIBLE→FEASIBLE per the dossier — pre-register that).
Report-only machinery: byte-inert on surfaces by construction; prove it
(HEAZ default arm hash unchanged 74c4731f-era? NO - HEAZ hash is its
own; use the current HEAZ default body hash, 2x).

## §2 Seat-vs-band consistency (wrong-value class)
HECA building181's seat is 1.858 m ABOVE its own node-band ceiling —
_frontage_band chose a level the band the solve enforces cannot reach.
Fix at selection: the seat level clamps into the intersection of
_frontage_band's interval AND the node-band interval at its contact
node(s); if that intersection is empty, LOUD attribution (the split-
seat law's future trigger — report, never silently ship). Gated
O4_SEAT_BAND_CONSISTENT default "1" is NOT allowed (no new default-on
gates without a battery) — default "0" this round, flip with the next
battery. Pre-register: HECA carrier (1020,4970)'s pocket shrinks
(the dossier: one bad anchor poisons 75% of the component — quantify
the drain); no other airport's seats move.

## §3 The seat-coupler visibility predicate
Two HEAZ pad seats 17.6 m apart, 1.108 m apart in value, rejected by
not_visible(frac=0.057) while their ring nodes share an apron. The
predicate gains the dossier's case: seats whose rings share a paved
surface (the sliced arrangement's literal adjacency — the lateral-
contiguity definition) are couplable regardless of the visibility
fraction. Same gate as §2. Pre-register: the HEAZ (35,37) pair couples;
carrier (37,1295)'s 8k sweeps return; HEAZ census delta quoted.

## §4 Empty-polytope loudness
anchors.py:367-370 silently keeps conflicting seats when the coupling
polytope is empty (HECA building197↔201: touching, shipped 5.9 m
apart). Under the split-level-seats ruling the FULL fix is sectioned
seats (own spec); THIS round lands the loudness only: an empty polytope
emits a named report (buildings, gap, ring relief) through the existing
forensics channel — never silent. No behavior change to the shipped
values yet.

## Acceptance
Gate-off byte identity on the current default baselines (CYXY/SPLP/
HEAZ/HECA default-arm body hashes from the killhalf/kclt rounds — 2x
each where a fix's gate could touch that airport); gates-on arms HEAZ +
HECA with the pre-registrations above; the stall-report carrier tables
re-emitted with the corrected §1 instrument (the adjudication deltas
quoted); suite green over the same 23 reds + new tests per fix; honest
cost. STOP rules per standing law.
