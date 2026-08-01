# Taut-string fix arm: grip completeness, neighbour bounding, pin carry

Fable spec, 2026-08-01. Implements the fixes for the three attributed
mechanisms of this session (mover-ledger commit `50a12ea`; flip-gate and
attribution reports in the session scratchpad). Line numbers against
`50a12ea`.

**Owner ruling governing acceptance (2026-08-01):** band-lawful airside
displacement is CORRECT regardless of magnitude ("probably more accurate
than whatever the rough DEM says"), conditional on: string ends within
band, spines true to grade law, edge nodes moving with their spines.
Displacement is not a defect metric; lawfulness is. Do not "fix" movement.

**Attributed mechanisms this spec fixes:**
1. The 88 `law_anchor` conflicts are STATIC — born in the kept pin set
   (mover ledger: 100% `unchanged_since_freeze` both sides). Cause: the
   grip enumerates only pin-vs-pin pairs (`taut_string.py:1105-1112`,
   `if j not in pins: continue`); a pin one spine edge from a hard
   anchor (seat, runway join, seam) is never examined.
2. The free-member conflicts are MANUFACTURED by the spine-yield
   projections' clamp/blend phase (mover ledger: 94.0% `proj_u.blend`,
   5.2% `proj_shape.blend`, zero sweeps) — the stage Ruling 55 names.
3. The G2 pin drag (identity-joined median 0.2564 m, max 6.73) is minted
   in `final_grade_projection` (85.8% `final_proj_2`): pins are Dirichlet
   only in phase A; nothing downstream holds them.

## 0. Constraints (all standing law applies)

* Owner constants untouched. The probe machinery from `50a12ea` stays
  intact and working — the fix arm is read through it.
* Gating for A/B honesty: fixes 2 and 3 land behind NEW gates, default
  `"0"`; fix 1 lives inside the existing string gate (it changes the kept
  pin set only, so gate-off is untouched by construction). The flip
  decision for the new gates is the lead's, AFTER the readings.
  - Fix 2: `O4_HARD_NEIGHBOUR_BOUND` (default "0"). NOTE: this law is
    stated for ALL hard nodes (Ruling 55), so when it flips on it will
    change gate-off (α) output too — 75 of the 88 anchor conflicts
    pre-exist in α. That is intended and is why it needs its own gate.
  - Fix 3: `O4_STRING_PINS_FINAL_HOLD` (default "0"); only active when
    strings are on.
* With ALL gates at their defaults (`O4_TAUT_STRING_CONSTRUCTION=0`, new
  gates "0"): byte identity against SPLP `d8d0f065…` / CYXY `dcebb6ff…`
  (full hashes in the handover §3).
* No behaviour change to `feasibility_project`'s other callers when
  fix 2's gate is off (plumb via parameter/out-param idiom, no module
  globals, exactly as the probes did).
* Build-time impact statement required; stay under the 1% triggers or
  stop and report.

## 1. Fix 1 — grip completeness: pin-vs-hard pairs

`filter_pins_by_grade_law` additionally enumerates pairs `(i, j)` where
`i ∈ pins` and `j ∈ hard \ pins`, over the same `spine_adj` edge walk,
with the hard side's value read from `elev` (the hook receives it; hard
values P0-P5 are stamped by then). Over-cap ⇒ the PIN is the release
candidate (the existing machinery already excludes hard nodes from
candidacy and already skips hard-hard pairs as pre-existing genuine
steps — extend, do not restructure). Grip-yield witnesses for these
releases carry `"rule": "pin_vs_hard"` plus the existing fields.
Endpoint protection unchanged: Ruling 52's re-admission minimality pass
runs over the union of both pair families.

Corollary the readings must confirm: released stations hand back to the
solver, which rides its cap toward the anchor — the owner's own sentence
("grade law overrules the string when needed") applied where "when
needed" is true. Expect the three flat-116.360 strings (38/41/74) to
lose their seat-adjacent pins, not their chords.

## 2. Fix 2 — Ruling 55 neighbour bounding (verbatim law)

In `feasibility_project`'s clamp/blend phase (everything before the
blend/sweep boundary at `one_solve.py:2092` — the envelope clamp
`:1867-1883`, the break blend `:1807-1834`, the chain-rigid rod blend),
gated by `O4_HARD_NEIGHBOUR_BOUND=1`: a yield/blend candidate `v`
adjacent (grade-graph edge, budget `cap·d`) to one or more HARD nodes
moves only within `⋂ₕ [elev[h] − cap·d, elev[h] + cap·d]` intersected
with its own law (its envelope/band/bounds as today). BOUNDING, never
freezing — `cap·d` is the law's own freedom; corridors still descend
away from hard nodes at cap rate. Hard = the projection's own `hard`
set for that call (pins ride in via `yield_hard` per Ruling 54 — no new
plumbing of pin identity into `one_solve`).

Where the intersection is EMPTY (two hard nodes disagree beyond their
budgets through `v`), the pair is a DECLARED conflict: leave `v` where
its own law puts it today and emit the triple into the existing
`broken_out`/forensics channel with a `declared_hard_conflict` marker —
small and author-carrying is the pre-registered expectation; a LARGE
declared population is a finding that returns to the lead, not something
to suppress.

Implementation note: the sweeps need no change — the mover ledger proved
they manufacture nothing (zero sweep labels); if after this fix the
sweep labels light up, that is a new finding, report it.

## 3. Fix 3 — pins carried through the final projections

Gate `O4_STRING_PINS_FINAL_HOLD=1` (and strings on): the kept-pin set
crosses into BOTH `final_grade_projection` passes by CANONICAL KEY (the
probe's `_mover_rebind` machinery at `solve.py` already does this
crossing — reuse it, never an index carry), and joins each pass's
hard/yield-hard analog the same way Ruling 54 joined pins to the solve's
`yield_hard`: held, but law-overridable through the same bounded-yield /
declared-conflict path as fix 2 (which the final passes' projections
inherit when both gates are on). Uncrowned frame: pins are z′ values and
the passes operate in z′ between crown-in and crown-out — join inside
that window, exactly where the probe boundaries sit.

Known hazard, pre-registered: 48 emitted junction edges join kept pins
of DIFFERENT strings with pin values over role cap (worst 54.4%,
cross-string crossings; pre-existing in α, currently smoothed by the
unheld final passes). Under fix 3 these must surface as DECLARED
conflicts or be released by fix 1's grip extension where the partner is
hard — they must NOT freeze into new emitted violations. The readings
check this class explicitly.

## 4. Measurement battery (in order; quote the honest total)

All with the probe gates on (`O4_STRING_MOVER_LEDGER=1`, witness +
state dumps set) so every reading comes from production's own ledgers.

1. Unit suite: solve.py test set + `test_spine_taut_string_heca` +
   `test_taut_string_probes` + new tests for the three fixes (each gate
   on/off, headless). No new reds.
2. Byte identity, all-gates-off: SPLP + CYXY vs the §0 hashes.
3. HECA gate-on build, fixes on (`O4_TAUT_STRING_CONSTRUCTION=1`,
   `O4_HARD_NEIGHBOUR_BOUND=1`, `O4_STRING_PINS_FINAL_HOLD=1`).
4. SPJC gate-on build, same gates, WITH `O4_STRING_STATE_DUMP` — closes
   the two unclassified SPJC pairs (grip witnesses now name them).
5. Flip-gate re-read: `O4_TEST_AIRPORTS=HECA test_pavement_grade`, β arm
   with all three fixes on, via the run ledger (α baseline exists in the
   ledger from 2026-08-01, labels `flipgate-alpha-gate-off`; rebuild the
   created-slice diff with the flipgate scripts in the session scratchpad
   — geometric matching, same instrument).

**Pre-registered outcomes** (deviations are findings, not failures to
hide):
* `pin_yield_conflicts`: 888 → ~0 manufactured; any residual is
  `declared_hard_conflict`, small and author-carrying.
* `law_anchor` class: 88 → 0 (grip releases); released pins appear as
  `pin_vs_hard` grip-yield witnesses instead.
* Identity-joined G2 at surviving kept pins: returns to the 0-class
  where the neighbourhood is lawful (median ≤ 0.01 m); every nonzero row
  carries a declared cause in the ledger.
* Flip-gate created slice: 854 → 0 target. Residual classes must be
  named; a residual that is purely the `adjacent_ground` cut-piece clamp
  gap routes to that side task, not this line.
* The 48 cross-string junction-pair class: absent from the created
  slice (declared or released, never frozen violations).
* W-CHORD1 worst bin: no regression from −5.83.
* Chord/pin structure: string count, kept-pin count, and the three
  116.360 strings' chords unchanged except grip releases (the chord is
  never bent — verify from the sidecar, not assumed).

Budget: implementation + unit tests, 2 identity builds, HECA + SPJC
gate-on builds, one β battery (~712 s). Honest total ≈ 30 min of builds.

## 5. Out of scope

Chord-1 fragmentation (defect 3), substrate divergence (defect 6), the
`adjacent_ground` cut-piece clamp (side task, running separately), any
band change (there is ONE band and it is correct — owner 2026-08-01),
R1/R2 sequencing (after this arm reads out).
