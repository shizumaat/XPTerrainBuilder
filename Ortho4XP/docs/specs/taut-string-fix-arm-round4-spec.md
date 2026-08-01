# Taut-string fix arm, round 4: pins live on the frozen graph

Fable spec, 2026-08-01. Follows rounds 1-2 (`b4ff1cd`, `676f8da`) and the
round-3 decision measurements (scratchpad `round3/`). Line numbers against
`676f8da`.

**Mechanism (round 3, exact):** S1b writes every kept pin
(`solve.py:6500-6505`) but the phase-A freeze covers only
`spine_adj`-keyed nodes (`:6506`/`:6654` → `solve.py:1415-1417`), so a pin
on a node with no `u_spine_adj` entry is written, overwritten by phase B,
and then held at phase B's value by Ruling 54. Separation is exact: 32/32
off-spine kept pins moved (0.46-6.16 m), 1,620/1,620 on-spine pins held to
0.000000 m, both rounds; HECA has zero off-spine pins and zero movers.
Four SPJC strings (43/45/47/53) are WHOLLY off-spine (51 targets). 164 of
the 244-row SPJC apron created-defect family sit on these movers.

**Fable ruling (design):** a pin the phase-A solve structurally cannot
hold is not a pin. Pins are restricted to the freeze-covered graph;
off-graph targets are LEDGERED, never applied. Chords are untouched (the
string still exists; it just does not pin what the solve does not govern).

## 1. The fix (inside the string gate; no new gate)

At the grip call site in `solve_route_profile` (after
`filter_pins_by_grade_law`, before `string_pins=` is passed): split kept
pins into `applied = {v: z for v in kept if v in u_spine_adj}` and
`off_graph` (the rest). Only `applied` reaches `_solve_spine_profile`,
Ruling 54's `yield_hard`, the final-hold export, and the mover watch set.
Ledger: each pin row gains `"pin_frozen": bool` (the one-bit field —
true iff the vertex is in the set the phase-A solve freezes); `off_graph`
rows get disposition `"off_graph"`; summary gains `n_pins_off_graph` and
the affected string ids. G2/pin-drag delivery covers APPLIED pins only —
an off-graph target is not a drag population member (round 3's 11
crown-frame rows also fall out: the reader compares uncrowned z′, which
the sidecar already carries as `z_emit_uncrowned`).

Tenure, decoration, substrate: UNTOUCHED this round. Whether an
all-off-spine chain should spend tenure or exist at all is measured
first (§3 reads), ruled after.

## 2. The α-arm caveat closer

One gate-off lab build each for HECA and SPJC at this tree with the axes
sidecar enabled (`tools/full_airport_build.py`, `O4_LOG_VERBOSITY=1` is
its default), artifacts kept. Purpose: round 3 could not test whether the
BREAK REGIONS the declared web lives in are string-created, because no
same-tree α axes sidecar existed. Read: break-node set α vs β (same tree,
same code — a lawful comparison), overlap with the declared-node set, and
the α/β actionable within-shape counts at the declared nodes.

## 3. Measurement battery

1. Unit suite (rounds 1-2 sets + new tests: off-graph split, ledger
   fields, G2 population rule). No new reds.
2. All-gates-off byte identity: SPLP `d8d0f065…` / CYXY `dcebb6ff…`.
3. HECA + SPJC gate-on builds (all round-2 gates + probes), plus §2's two
   gate-off lab builds.
4. Flip-gate β re-read vs the ledgered α.

**Pre-registered outcomes:**
* SPJC G2 identity-joined tail: 32 → **0** movers among applied pins;
  `n_pins_off_graph` = 51 at SPJC, **0 at HECA**; `pin_frozen` true for
  100% of applied pins at both airports.
* The 244-row SPJC apron family: collapses toward its non-Q1 residue
  (~80 by round-3 arithmetic; the 164 Q1-linked rows clear or migrate to
  α-equivalent behaviour). Quote what remains by shape.
* Created slice 747 → **~450 ± 50**, decomposed as: `adjacent_ground`
  clamp class (~362, side task), release-induced junctions (~37,
  re-measured post-fix — this class interacts with the pin web),
  CYXY pin-vs-free apron class (~12, re-measured), post-solve-minted
  unattributed (~90). Any class OUTSIDE this decomposition is a new
  finding.
* W-CHORD1 worst bin: no regression from −4.78. Chord sets byte-identical.
* Monitoring ledger (round-3 escalation ruling): from the fresh arms,
  quote the two alarm readings — unquarantined declared residual
  (single digits expected) and declared-at-created-defect count (≤
  random-node control) — beside their controls.
* §2 read: break-node α∩β overlap and whether the declared web's break
  regions pre-exist the strings. A large string-created break population
  is a FINDING for the lead, not something to fix this round.

Budget: implementation + tests, 2 identity builds, 2 gate-on + 2 gate-off
lab builds, one β battery (~712 s). Honest total ≈ 30 min.

## 4. Out of scope

The release-induced junction mechanism (candidate only — needs the
post-fix re-read before any design), the CYXY pin-vs-free blind spot
(probe after re-read), the post-solve-minted emitter ledger (next probe
spec), tenure/decoration scope for off-spine chains (ruled after §3
reads), gate-flip decisions (after this round; the
`O4_HARD_NEIGHBOUR_BOUND` default flip changes α output and goes to the
owner with the battery evidence), R1/R2.
