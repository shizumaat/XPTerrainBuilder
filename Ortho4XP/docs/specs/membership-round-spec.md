# Membership round: the grade graph follows contiguity, not role labels

Fable spec, 2026-08-03. Fixes the ONE root under both constants-round
residuals. Lines against `dfca0a4`. BINDING: docs/RULINGS.md
(lateral-contiguity law + owner amendments — the spine ALWAYS remains;
airside-is-king; law compliance; convergence guards). Evidence:
scratchpad `constants_absorb/RESULTS.md` (the staged-probe attribution
and the shared-vertex residual analysis — read first).

**Mechanism (attributed, interventional):** solver membership is
role-keyed — `PAVEMENT_ROLES` contains `service_road`/`service_junction`
but not `groundside_pavement` — so absorbing a road into a lot DELETES
the road's edges from the unified grade graph. Consequences measured:
the solve changes globally (21 runway vertices move 0.01-0.06 m at HECA
— an airside-is-king violation), and at merged-ring vertices shared with
`service_junction` the junction (a member and emit authority) overwrites
the non-member lot's values (the CYXY residual 2, the HECA worst-lot
33/115 shared vertices).

## The fix (rides the existing gate `O4_SERVICE_LOT_ABSORPTION`)

**Membership follows the contiguous surface.** A merged
laterally-contiguous surface containing ANY component that was a grade-
graph member remains a member: its ring/edges enroll in the unified
grade graph exactly where the absorbed components' were enrolled, capped
by the lateral-contiguity law (the strictest-of caps already carried).
The service-road SPINE keeps its graph edges regardless (the owner's
spine-remains amendment — verify unchanged). Emit authority follows the
same rule: the merged surface is the authority for its own ring; a
shared `service_junction` vertex takes the solve's converged value, not
a post-hoc overwrite.

Implementation constraints: no second membership registry — extend the
existing enrollment path (`solver_primitives` node/edge assembly and
`PAVEMENT_ROLES` consumers found via blast.py) with a
membership-by-surface predicate; do NOT add `groundside_pavement`
wholesale to `PAVEMENT_ROLES` (un-absorbed lots stay non-members —
airside-is-king forbids groundside witnessing airside; the merged
surface is a member ONLY because it contains a road).

## Pre-registered

1. The 21 HECA runway vertices: byte-identical with the absorption gate
   on vs off (the airside control — THE acceptance criterion).
2. CYXY merged-ring residual 2 → 0; the HECA shared-vertex overwrite
   class → 0 (the lot's converged values stand at shared nodes).
3. HECA break nodes ≤ 216 (no regression; likely further fall).
4. Spine census identical in both arms at all three airports.
5. Gate-off byte identity vs the NEW baselines (CYXY `8eab3acd…`, SPLP
   `f460a8f7…`, HECA repaired `b7d02779…`), envs logged per arm.
6. Suite green over the same 23 reds; exclusive CYXY `--runs 3` medians
   (the gate-on delta adds to the +3.50 s already owed to the flip-time
   whole-pipeline review — quote it).

## Out of scope

The flip-and-kill round (next: its spec needs THIS round's readings —
with membership fixed, the absorption family should be closable and the
machinery deletable); the queued small items; rulesets/KCLT.

---

# V2 (2026-08-03) — SUPERSEDES V1 on measured falsification

Attempt 1 (spec-faithful, artifacts in scratchpad `membership/`,
patch `membership_attempt1.patch`) FALSIFIED v1's mechanism: restoring
graph membership left the 21 runway vertices bit-identical to the
pre-fix arm and REGRESSED the merged-ring class (CYXY worst pair
14.67% → 198.64%). The real mechanisms, both measured:

1. **Context, not membership, moves the runway vertices.** The gate
   still changes two solve inputs keyed on the road SHAPE absorption
   deletes: the `airside_buf` junction chord-visibility union
   (solver_primitives ~L1116) and `grade_graph.build_context`'s
   road-carve / `_ZONE_ROLES` buffered zones. Movers sit 4.2-4.6 km
   away — global coupling through context geometry.
2. **`finalize.emit_terrain_transition_features` is a SECOND groundside
   grading authority** (`_merge_touching_groundside` →
   `_separate_groundside_from_airside` → `_deconflict_groundside_
   overlaps` → `_grade_limit_groundside_chords`, self-described "LAST
   groundside-altitude writer"), constructing FRESH BuiltShapes (flags
   die, groundside.py:2917/:3107) and rewriting the merged rings after
   the solve.

## The v2 fix (same gate)

**A. Absorption is CONTEXT-CONSERVATIVE** (the spine-remains amendment
generalized): the absorbed road's FOOTPRINT remains in every solve-input
set it occupied — the `airside_buf` visibility union, the road-carve /
`_ZONE_ROLES` zones, and any other context consumer blast.py surfaces
for the deleted shape. Absorption changes surface identity and cap,
NEVER the solve's context geometry. Implement by contributing the
pre-merge road geometry to those sets (a retained context footprint on
the merged shape or the layout — not a resurrection of the shape).
Pre-registration #1 (unchanged, THE criterion): the 21 HECA runway
vertices byte-identical gate-on vs gate-off.

**B. Merged surfaces are EXEMPT from the finalize rewriting chain**
(Fable ruling under the no-second-authority principle in RULINGS: for
an absorbed surface, the lateral-contiguity law + the merged-host
regrade IS the single authority; finalize's chain — merge/separate/
deconflict/chord-limit — must not touch it; its values stand).
Ordinary un-absorbed lots keep the existing chain unchanged (its reform
belongs to the future lot-law round with the drainage minimum).
Identify merged surfaces robustly across the fresh-BuiltShape boundary
(the flag must survive or the exemption keys on the merged registry,
not a per-shape attribute — implementer chooses and justifies).
Pre-registered: merged-ring class CYXY → ≤ pre-merge counts (the v1
target restored), HECA worst-pair 201% class → gone; break nodes ≤ 240
and falling; graph membership from attempt 1 is NOT re-landed (it was
proven a non-mechanism — leave PAVEMENT_ROLES consumers untouched).

V1's graph-membership predicate is retired unimplemented. The rest of
v1's constraints stand (spine census identical; gate-off identity vs
the NEW baselines; airside_buf never gains un-absorbed groundside).

---

# V2.1 (2026-08-03) — the single-authority completion (Fable-approved)

V2.B's miss is attributed to one gap: `_regrade_merged_host` enforces
adjacent-ring pairs only, while the exempted finalize chain was the
ALL-PAIR (chord) authority — the replacement law was weaker than what
it replaced. COMPLETION: `_regrade_merged_host` additionally applies
the existing `chord_limit_ring_altitudes` (the same one-law family, at
the merged surface's lateral-contiguity cap) so the single authority
enforces everything the old chain did. This is the specified completion
of an attributed mechanism, not attempt 3 of a guess. Pre-registered:
CYXY merged-ring within-shape rows 39 → ≤ 2 (the pre-fix absorb
count); HECA groundside within-shape ≤ the control arm's 9,376 (the
exemption turns net-positive); pre-reg #1/#3/#4/#5 re-verified
unchanged (the completion touches only merged-host altitudes); suite
green; no timing battery needed (the call is per-merged-ring, bounded).
