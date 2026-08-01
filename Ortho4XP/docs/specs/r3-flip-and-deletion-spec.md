# R3 — band envelope ON + legacy deletion + the battery (Opus-executable)

Sub-spec of `taut-string-model-spec.md` §4.5/§4.6 / §5 R3 and
`taut-string-implementation-plan.md` P5.  Fable-authored 2026-07-30.
Deviation rule binds.  ORDER: last implementation step of the line —
after R1, S1, R2 are landed and measured.  PRECONDITION — **SATISFIED
2026-07-31**: P0b closed BY ATTRIBUTION (the flake is the
`o4_provenance_built` wall-clock stamp, root line only; the body hash
this spec's identity protocol uses excludes it BY MECHANISM, so
battery-scale gate-off identity was never exposed).  P0c's test fix
should land before the battery as hygiene.

## §1 Shape of the step: TWO STAGES, each falsifiable

**Stage A — flip, legacy intact.**  Flip `O4_ENVELOPE_FROM_BAND`
default to "1" at BOTH read sites (`solve.py` and `one_solve.py` —
they must land together; `blast.py` currently warns on their
conflicting defaults) with every legacy mechanism still present and
gated.  This preserves the A/B lever through the measurement.  Run
the R2 gate set on HECA (≤ 2 builds) + the §1.2 cross-match
(`xmatch.py`: the healed-10,307 class retained, the NEW-pair class
≈ 0 — the R1 field + R2 tube are the mechanisms that §1.3/§1.5 said
were missing when ON failed alone).
**Stage B — delete.**  Only after Stage A's gates hold.  Delete the
§2 inventory below.  Deletion of truly-dead code is HASH-NEUTRAL at
default env: prove each deletion group by the copied-tree three-way
protocol (SPLP + CYXY; HECA rides the battery).  **Any deletion that
changes a hash was not dead — STOP, deviation report, do not
rationalise.**

## §2 The deletion inventory (locate by content anchors, never line
numbers — the tree drifts daily)

| # | what dies | where (content anchor) | replaced by |
|---|---|---|---|
| 1 | pair-closure envelope: `_reach` Dijkstras, `ceil/floor/edge_lim` closure fields, every-hard-node seeding | `one_solve.py`, the block headed by the envelope comment around `_reach(+1, ceil_radj, …)` | the band envelope (#13), already default-ON after Stage A |
| 2 | break blend t-ramp, EXCEPT the empty-interval containment (§3) | `one_solve.py` break-blend region | field hold `clamp(Z_ref, hard-neighbour interval)` |
| 3 | chain-rigid + branch-rigid blends (#7, #8) | `one_solve.py`, the rigid Δ-shape placement blocks | the field carries chain/branch shape |
| 4 | GS witness gates + machinery (#15): `O4_GS_NO_AIRSIDE_WITNESS[,_FINAL]`, the second Dijkstra, the weld classification block | `one_solve.py` + `solve.py` witness-limited plumbing | structural under the band (band seeds runway anchors only) — re-run the SPJC 78→121 check ONCE at deletion (spec §4.6) |
| 5 | per-pass `z_ref` snapshot builders + per-pass R rebuild (the gate-OFF branches R1 left standing) | `solve.py`, the three `node_refs` blocks | R1's field views (already default path) |
| 6 | honesty-ladder rule 2 + `_BandView` resampling | `apron_reference.py` + its `solve.py` call plumbing | field-sourced anchors (R1) |
| 7 | gates collapse: `O4_YIELD_REFERENCE_RODS`, `O4_CORRIDOR_REF_STRING`, `O4_APRON_R_LAW_TRUE`, `O4_PAD_ROD_COUPLING` | their read sites | `O4_REFERENCE_FIELD` is the one reference gate (spec §4.6) |
| 8 | pad lift-only restore (#21) | `solve.py`, the `_pad_seed_levels` revert loop | ONLY IF the battery measures it never fires (log its fire count in Stage A); if it fires, it stays + report |

Each row is its own deletion group with its own hash proof.  Rows
1-3 are the `one_solve.py` hot region — the riskiest surgery of the
whole line; take them one row at a time.

**Warning-comment harvest (OBLIGATION, plan register 16 — added
2026-07-31 after R1's absorption reproduced a ★-documented failure):
before deleting each row, its warning/★ comments are harvested into
the step report as CONFORMANCE OBLIGATIONS on whatever replaces it,
each marked met-by-<mechanism> or NOT-COVERED (a NOT-COVERED is a
deviation, not a judgment call).**

## §3 Broken-node semantics after deletion (frozen, conservative)

BROKEN = band inversion only (unchanged, #13).  A broken node holds
at `clamp(Z_ref, hard-neighbour interval)` through the SAME
tube/bounds path as every other node (spec §4.5 — breaking a node no
longer changes which reference law governs it).  **Empty-interval
containment:** where the node's hard-neighbour interval is itself
empty/inverted (a genuine break region), the EXISTING t-ramp value
remains the containment value — unchanged code path, minimal surgery
— and every such node is exported as a break witness.  No new blend
is invented; the t-ramp dies everywhere else.

## §4 The battery (the ONE full acceptance of the line)

4 airports × 2 arms (gate-off identity by body hash, sequential
copied-tree protocol) + the HECA pytest battery + the full suite.
Gates (spec §5 R3, updated by the P0 rulings):
* all R2 gates (W-CHORD2 in full; building199 ≤ 0.2 m; no NEW-pair
  class; within-shape ≤ baseline);
* **W-CHORD1 in full**: every bin within ε_taxi (0.50 m) of the
  string except declared bends, no local V (witness-covered);
* total over-cap ≤ the 9,096 class;
* flats: ZERO step/tear sections;
* **suite at the §5.0 comparator**: zero failures outside the LIVE
  comparator (the 24F historical set minus the attributed-removal
  ledger — **24 members as of 2026-07-31**: ledger entry 1 was VOIDED
  the same day, the flake was never a member; §5.0 rebase semantics
  + reconciliation rule); healed members become ledger removals with
  evidence; any surviving airport-build member goes to R4 with its
  witness — it does not block sign-off by itself, it blocks
  UNATTRIBUTED;
* build-time statement (`check_build_time --run --runs 3` CYXY +
  the whole-battery wall recorded); any ≥ 1 % regression ⇒ owner
  approval BEFORE landing (hard law);
* `O4_BREAK_FORENSICS` enabled on the LAST development build so R4
  needs no build of its own.

## §5 Checkpoints

* **R3-CP1** — after Stage A's measurement, before ANY deletion:
  Fable reviews the gate table + cross-match.  No deletion without
  this ruling.
* **R3-CP2** — after Stage B, before the battery: the per-row hash
  table.  Fable eyeballs the `one_solve.py` diff personally (plan
  risk register #2).
* **R3-CP3** — battery sign-off: Fable + owner.

## §6 Build-time statement

Stage A: measured at R3-CP1 (the enlarged free set was §1.6's +5.47 s
phase FAIL when ON ran alone; with the field+tube the sweeps start at
near-solution — expected to recover it, MEASURED not assumed).
Stage B: deletions are hash-neutral, so timing-neutral by
construction; the battery records the totals.  Any budget crossing ⇒
owner approval before landing.

## §7 EXPECT DIVERGENCE

(i) Concurrent tree edits WILL collide with the `one_solve.py`
region — re-run `blast.py` and the row's tests between every row;
if a row's content anchor has moved beyond recognition, STOP.
(ii) Row 8 may fire (the restore is load-bearing) — keep + report;
the spec predicted this possibility.
(iii) SPLP/SPJC mouth-relax break exports change under the flip
(spec anticipated); the comparator judges, not intuition.
(iv) Row 4's SPJC 78→121 re-check may show a delta — that means the
OFF-gated machinery was NOT inert: STOP, deviation.
(v) The Stage A cross-match may show the NEW-pair class ≠ 0 — that
is the R1/R2 mechanisms not fully closing §1.3/§1.5; STOP at R3-CP1
(this is a design question, not a tuning target).
(vi) RESOLVED 2026-07-31: P0b's attribution confines the
nondeterminism to the root line the body hash excludes — the
battery's identity legs are sound.  Residual: if P0c has not landed,
expect the idempotency test itself to flake at its ~5-10 % base rate
during the battery's suite leg; that is the KNOWN flake, recorded
against the comparator, not a new failure.

## §8 FROZEN / DISCRETION

**FROZEN:** the two-stage shape; both flip sites landing together;
the row-by-row deletion with per-row hash proof; §3's broken
semantics; §4's gates; the checkpoints; the P0b precondition; row 8's
fire-count condition.
**DISCRETION:** row order within 1-3 safety guidance; test selection
per row (from `blast.py`); report formatting; battery scheduling
within the exclusive-builds rule.
