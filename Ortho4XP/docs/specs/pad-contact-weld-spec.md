# Pad contact weld — the coupling mechanism 01g/01i require
# (Fable spec, 2026-09-01. The buildings lane measured the gap: not
# cutting back is not a weld; welds are NODE IDENTITY, and revealed
# ground welded to nothing sits wherever its class puts it.)

## Law (owner 01g/01i, restated as mechanism)

A pad edge in CONTACT with pavement (airside always; groundside in
the uniform-groundside case) is COUPLED to it: the pad's boundary
vertices along the contact stretch are INSERTED into the abutting
pavement ring (T-vertex insertion — the conformance family's own
primitive, census §4a: `conformance.enforce_conformance` inserts
role-agnostically; extend that machinery, never fork it), and the
shared vertices carry the pad seat's value (contact = value, 29c).
The pavement then grades away from those welded vertices under its
own class caps — no new grading law, just a new anchored population.
Mixed-frontage pads insert on the AIRSIDE stretches only; the
groundside side keeps the 0.6 m cut-back cliff (01i).

## Scope discipline (30l)

The insertion adds a shared-vertex population to the solve. Census
the consumers BEFORE the edit: the writeback/authority resolution
(the two convergence points), the chord limiter's node book, the
adjacent-ground band (welded pad vertices are pinned sources, the
airside-frozen class), seat machinery (the pad seat is the value
authority at the shared nodes), and the census's row-side join.
Contact detection: pad edge within the shared-vertex weld distance
of a pavement ring edge (the emitted-frame identity rules apply —
insertion happens pre-solve so the solve couples, not at emit).

## Acceptance

The lane's own four-arm table is the frame: with the close retired +
frontage law + THIS weld, LEMD and SPJC return to ≤ their control
class (the >60 m no-step pairs collapse because the ground between
grades to the welded seat), HECA holds its −248, welded-pad counts
rise to ≈ the contact population, basin/site invariants held. Twins:
a pad touching an apron shares vertices with it post-insertion; the
apron's profile grades away at cap; a mixed pad inserts only on its
airside stretches. THREE closing arms (HECA/LEMD/SPJC).

## Cutoff (beta safety)

HARD CUTOFF Wednesday 12:00 local: green by then → the full pad law
(retirement + frontage + weld) merges for the beta. Miss → the beta
ships the split-only configuration (already on main); the pad law
merges post-beta with the owner's Thursday read as extra evidence.
Below-bar at cutoff = park, no exceptions.
