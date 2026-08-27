# Pads as band-bounded variables — seats chosen UNDER the narrowing
# (Fable spec, 2026-08-27; owner rulings: pads-move-within-band, and
# "grade law outranks shared-datum preservation" — RULINGS 2026-08-27)

Owner: "why anchor the building pads at all, but allow them to move —
within their band — to accommodate the ideal pavement grade?" and, for
pack groups: "if necessary we split the objects and seat them
individually rather than violate grade law."

## §0 Measured frame (lane/lawband 8ace54d3, merged 16889bc9)

- The seat-anchor arm is the founding refutation of seats-as-authority:
  feeding placed seats back into the band ADDED +4,069 rows at SPJC
  (`within_shape` 66 → 4,219, `building|building` to 11.1 m at 1 %) and
  HECA reproduced it (942 → 5,427). Mechanism: a rigid pre-committed
  seat contradicts the narrowing computed after it — the lane's own
  conclusion was "seats must be chosen UNDER the narrowing, one joint
  pass". This spec is that pass.
- Ring-median instability: building25's seat moved 90.42 → 82.52 from a
  data edit near a DIFFERENT building; the lawband round re-seated 32
  of HECA's 51 pads (worst −11.3 m, building17) — the drifted-high
  class the wide band had permitted.
- The band is now trustworthy at pad scale (building25 frontage
  interval 6.31 / 2.41 m) — the precondition the owner named.

## §1 THE LAW

1. **A DERIVED AIRSIDE PAD IS ONE FREE FLAT VARIABLE.** Its domain is
   the INTERSECTION of the narrowed band intervals over its ring
   vertices (the pad is flat: one value must be lawful at every
   vertex). Its law edges — frontage chords, no-step pairs, weld
   identities — enter the solve SYMMETRICALLY with the membrane.
   Runway and centerline profiles remain the only hard tiers above it;
   "buildings are the heaviest constraint" survives as the caps on the
   frontage edges themselves, binding whichever side moves.
2. **THE RING-MEDIAN SEAT PASS RETIRES for this class** (gated, see
   §1.5): the seat IS the solved value. Object y-bake ordering is
   unchanged (bake reads the solved pad after the solve, as today).
3. **AUTHORED-DATUM GROUPS: ACCOMMODATE, ELSE SPLIT (the owner's
   ruling verbatim in RULINGS 2026-08-27).** A shared-datum pack group
   is ONE variable whose domain is the intersection of member domains
   shifted by their authored offsets. A lawful accommodation is
   preferred — pack-relationship preservation is the TIEBREAKER among
   lawful placements, never the authority. When the intersection is
   empty, or the group optimum leaves any member's frontage/no-step
   law over cap, the group SPLITS: sub-bodies by connected proximity
   first, individual pads last, each piece re-solved in its own
   domain. Every split is LOUD and recorded in a sidecar
   `pack_group_splits` ledger (group identity, members, the violating
   rows that forced it, the split chosen) — the census prints the
   count and worst site; the ledger is also a bad-pack detector (a
   flat-plane-authored pack on a hill reads as a many-way split).
   This amends basin docket-B rigid group seating per the ruling.
4. **EMPTY PAD DOMAIN** = a `law_band_contradictions` entry (the
   Amendment-1 report-first mechanics, same ledger, same ship-gate
   promotion path).
5. Flag `O4_PADS_BAND_VARIABLES`, default ON; OFF byte-identical
   (restores the ring-median seat pass exactly).
6. **PROVENANCE:** the per-pad sidecar publication EXTENDS
   `pad_binding_routes` (the 2026-08-27 chip round's key — extend,
   never fork): domain interval, solved value, and the binding
   constraints at the optimum, so "why is this pad here" stays a file
   read.
7. **CENSUS:** no new family — the existing frontage/no-step/
   within-shape families adjudicate the result; `pack_group_splits`
   is evidence, not law (the contradiction-ledger precedent).

## §2 Twins

- Pad between two-level aprons: solved value lands inside its domain
  and minimises over-cap rows vs the median-seat control; OFF
  reproduces the control byte-identically.
- Group accommodation: two pads with authored offsets on gentle ground
  → group stays whole, offsets preserved exactly.
- Group split: the same group over a synthetic hill with no lawful
  common value → split recorded in the ledger with the forcing rows,
  members lawful individually, authored offsets preserved WITHIN each
  split piece.
- Empty domain → contradiction ledger entry, build continues
  (report-first), refuse arm raises.
- Solver symmetry: the pad variable moves toward the membrane optimum
  (no one-sided seniority for derived pads).

## §3 Acceptance (ONE HECA build + LEMD + SPJC/CYXY/HEAZ; census A/B
## vs the lawband frame — HECA lawband arm ≈ 6,543)

- HECA: the five worst lawband re-seats (building17 / 140 / 8 / 138 /
  25) re-read with their published binding constraints; the
  `within_shape building|building` and frontage populations reported;
  overall census honest A/B.
- LEMD: the shared-datum stress fixture (the 358-object mega-pool +
  docket-B group machinery). Report every group split with its site
  and forcing rows — the owner reviews each (splits visibly shear
  authored geometry; that review is the acceptance, not a count
  target). If LEMD's groups all accommodate, say so — that is the
  preferred outcome, not a missing result.
- SPJC/CYXY/HEAZ matched flag-off controls; conform-pass residuals
  re-reported (the retirement question's evidence continues to
  accumulate).
- Build-time statement (the pad variables are ~dozens per airport —
  expect noise-floor; the group-domain intersection is per-group
  linear; state both).
- Convergence guards: materiality 0.01 m, attempt cap 2, STOP on
  second miss, heartbeat; no shared-repo writes; no timing claims.
