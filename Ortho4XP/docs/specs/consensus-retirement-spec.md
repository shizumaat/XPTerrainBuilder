# Consensus retirement: single-authority emission

Fable spec, 2026-08-04 (lead-reviewed, approved). Implements the single-solve architecture
ruling (RULINGS 2026-08-03): "to_osm consensus averaging retires in
favor of single-authority emission; the lower-party-retreats machinery
already exists." EMITTERS EMIT, NEVER GRADE. This is the biggest
surface change of the campaign — acceptance is LAW-NOT-BYTES with
per-airport census matrices, and no default flips in this round. Lines
against 399c24d. BINDING: docs/RULINGS.md (single-solve; airside-is-
king; law compliance, not instrument-zero; grade-law completeness;
convergence guards).

## Mechanism

`to_osm` (layout.py:793) interns every vertex to a canonical node and
accumulates claims with precedence law > authority > skirt > soft
(:887-933, the 2026-07-19 no-stacked-nodes hard merge). Inside the
authority tier the emitted value is the MEAN of all authority claims
(`node_id_to_authority_alts`, :841-849): any shape carrying a slightly
different post-solve value at a shared vertex MOVES the node. That is a
second grading pass at emit, minting values no law produced. Evidence:

- **The measured runway vertex.** Spine-freeze round (spine_freeze/
  RESULTS.md #4): HECA node (30.13693252295, 31.40386604192) emitted
  63.73 → 63.79 (0.06 m) with the solver-side preserved set PROVEN held
  — a four-authority (runway 05L/23R + apron + junction + gap_fill_spine
  strip) consensus mean moved a runway vertex the solver never moved.
- **Census rising downstream of an improving solve.** Same round: the
  in-solve over-cap residual fell 1 755 → 1 530 while the law-true
  census rose +348 across the battery — the rise accrues in the
  post-solve writers and the emit consensus, not in the solve.
- **The dominant family.** drain_worklist/adjudication.json:
  `within_pair.apron.{micro,slope,cliff}` = 6 157+2 254+76 = 8 487 of
  12 115 law-true rows (70 %; the tasking's "69 %" recomputes to 70.0
  from worklist.json) — verdict FIX, mechanism ATTRIBUTED
  "emit-consensus + composed apron law", fix "to_osm consensus
  averaging retired + apron law as a directed constraint".
- **The precedent.** HECA's 1 497 groundside violations were minted by
  averaging two authorities; lower-party-retreats + retaining wall took
  them to 419 (memory canon, emit-consensus-mints-violations). The
  retreat machinery (`emit_stacked_conflict_walls`,
  adjacent_ground.py:1841) is production today.

## The design

1. **One author per node.** A total precedence order
   (`AUTHORITY_PRECEDENCE`, new, beside `SOFT_RECEIVER_ROLES`
   layout.py:310): LAW tier (bridge/tunnel plates — unchanged) → SOLVE
   tier — any node the solver owns (the canonical identity join: the
   11-decimal spelling carries solver node ids losslessly) emits the
   solve's value VERBATIM on every way referencing it; a shape's
   divergent private value becomes a forensics row, never a blend →
   skirt tier (semantics unchanged, now single-valued) → soft receivers
   adopt (`SOFT_RECEIVER_ROLES`, unchanged). The mean dies everywhere.
2. **Non-solve authority collisions** (lot vs ribbon, plate lip, etc.):
   the precedence winner keeps the node; a loser differing beyond
   `VERTEX_ALT_MERGE_TOL_M` retreats + retaining wall (the existing
   machinery, generalized exactly as it already resolved the groundside
   family); a loser within tol adopts. Within the non-solve tier the
   role order is airside-first (runway family > taxi > apron > building
   > service > groundside > terrain) — airside-is-king as constraint
   direction; the exact tail order is a lead review point, runway-first
   is load-bearing.
3. **Loud completeness.** An emitted valued node with NO author is a
   build ERROR naming the node and its claimant roles — never a silent
   fallback.
4. **Migration path — one gate, two phases.** `O4_SINGLE_AUTHORITY_EMIT`
   default "0": `report` — compute mean AND author value, emit
   UNCHANGED (byte-inert, proven on the anchors), write a divergence
   census (node, ll, roles, mean, author, |Δ|) through the forensics
   channel; `1` — emit the author value. The flip arm runs ONLY if the
   report confirms the attribution: join divergent nodes to the
   drain-worklist apron-family rows by ll — ≥50 % of rows within tol of
   a divergent node = confirmed; <20 % = attribution REFUTED, STOP
   before any flip arm is built.
5. **Cross-tile seam nodes keep the existing cross-tile contract**
   (consensus merge only — adjacent_ground.py:2108/:2546); tile seams
   are a different law and are out of scope.
6. **Validator twin.** Emit-value provenance: every `alt_abs` at a
   solver-owned node equals the solve's value exactly (sidecar-driven
   check_grade assertion — the binding half is the emitter, the twin
   reads it back, lockstep).

## Pre-registered outcomes (bands; full class matrix quoted OFF→ON for
## all five airports, both frames)

1. The 70 % family: HECA apron-family rows (4 618+2 128+76 = 6 822,
   drain frame) and SPJC (1 418+106) fall 30–70 % = success, 10–30 % =
   partial. STATED HONESTLY: full collapse is NOT expected from this
   round alone — the composed apron law / terrace panelization is the
   co-author of the family; this round retires the emit half only. Any
   NET RISE at any airport ⇒ STOP.
2. Runway vertices, gate on: every runway vertex equals the runway
   profile's solved value EXACTLY at all five airports — the 0.06 m
   consensus class = 0. (Identity to the AUTHORITY, deliberately not to
   the old bytes.)
3. The downstream-rise signature: re-run the spine-yield arm
   (`O4_SPINE_YIELD_HARD=1`) on top of this gate — the law-true delta
   OFF→ON is ≤0 at ≥4 of 5 airports (the +348-rows-downstream signature
   disappears when the emit stops re-grading).
4. Wall census: retreat-minted walls per airport quoted; inside strip
   footprints = 0 and at runway edges = 0 (hard — runway-edge law).
5. No new over-cap class at any airport (the spine-freeze round's
   failure mode; this round must not repeat it); worst-|de| severity
   does not rise at any airport.

## Acceptance

Gate-off byte identity (body hashes, 2×): SPLP 1531e6d0 / CYXY
5b7a1912 / HEAZ 5854d6e7 / HECA 2a28d01b / KCLT 74c4731f. Suite: same
23 reds; new tests (per-tier author selection, unclaimed-node error,
divergence report write-only, the four-role runway-vertex twin from the
spine-freeze finding, retreat-vs-adopt boundary at tol, cross-tile
contract preserved). Only `check_build_time --run` timings quotable; no
timing claim; any measured cost ≥1 % of budget ⇒ Fable-5 optimization
review per hard law. Build budget (the biggest of the three specs, as
befits the surface): report arms ×5 + flip arms ×5 + identity 2×5 ≈
3–4 h honest wall total, foreground, WORKTREE (venv/OSM_data
symlinked), no commit. Convergence guards: 0.01 m materiality, 2
attempts, `.progress` heartbeat.

## STOP rules

Attribution refuted at phase-report (<20 % join) — report, do not build
the flip arms; net census rise anywhere; a new over-cap class; any
retreat wall inside a strip footprint or at a runway edge; the
unclaimed-node error firing on the battery (that is attribution to
return, not a license to patch inline); second miss on any target.

## Out of scope

The composed apron law / terrace panels (co-author — own spec); the
tile-seam contract; the OTHER scheduled post-solve value-writers
(finalize terrain-transition chain, OLS road regrade, adjacent-ground
band values, tunnel-ramp lerps, drainage re-clamps — each its own
round per the single-solve ruling); emit decimation; any default flip
(a later battery with owner approval).
