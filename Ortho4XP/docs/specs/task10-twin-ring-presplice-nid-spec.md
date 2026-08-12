# Task #10 — Twin-ring pairing: pre-splice nid identity (Fable spec, 2026-08-12)

Lead: Fable session (deviations STOP and report to this spec's author;
`docs/RULINGS.md` canonical; PRE-SHIP DEV MODE in force). This spec is an
amendment-level continuation of
`docs/specs/round16-geometry-consistency-spec.md` (R16-1b, Amendments 1-2)
— read it first; its law stands unchanged.

## Context (measured; DEFERRED_VERIFICATION.md:42, R16-1b STOP)

20 twin-ring pairs / 46 vertices at OTHH. Tolerance EXONERATED
(5 mm→150 mm byte-identical ×3). The block is PAIRING: the pairs never
enter the R16-1b candidate loop. Root: hole rings intern PRIVATELY —
`layout.py:1599-1604` calls `_ring_to_nids(_hole.coords, None)` with no
lookup against the already-registered exterior chains, so pre-splice a
hole shares almost no nids with its pad; the candidate gate at
`layout.py:2081` (`_n_shared < 3 or _n_shared * 2 < len(_r_open)`) fails,
the ring is never scored, and the 4-32 shared nids visible in the EMITTED
frame are manufactured later by the splice (`layout.py:2249`). Everything
downstream of the gate (offset scoring, adopt, divergence report,
`layout.py:2035-2124`) is already Amendment-2-correct and merely starved.

## Ruling

**Fix shape (i): pre-splice nid identity at intern.** At
`layout.py:1599-1604`, hole-ring interning queries the canonical registry
(read-only query exists: `canonical_points.py:117-129 get`, nearest at
`:131`) so a hole vertex coincident with an already-interned exterior
vertex receives THAT nid instead of a fresh private one. The existing
candidate loop then pairs, scores and adopts under Amendment 2 unchanged.
Fix shape (ii) — a geometric pairing key at `layout.py:2069-2081` — is
REFUSED: it is a proximity join, and identity is carried by canonical
interning in this codebase (canonical-identity law; the census-wrapper
precedent for parallel re-implementations applies to identity too).

Constraints:
- NO new constant (Amendment 2, spec:210). Identity resolution uses the
  registry's own semantics (`SHARED_VERTEX_TOL_M` 0.5 via `get_or_add` /
  `get`) — the same law the exterior chains interned under.
- The adoption remains the candidate loop's act. This change only makes
  the pairs VISIBLE pre-splice; do not add a second adoption site.
- Ordering law stands: the splice remains the last geometry-affecting
  step (`layout.py:1654-1666`); the orphan purge (`layout.py:2130-2149`)
  must still prevent the splice undoing an adoption — extend its
  coverage if the new shared nids create a new orphan class.
- Watch R16-4b ring needle repair (`layout.py:1606-1650`) and hole dedup
  (`_hole_key`, `layout.py:1697-1734`): both now see holes that share
  nids with exteriors; their behavior must be unchanged for valued
  vertices (twins below).

## Implementation plan (one Opus implementer)

1. `Ortho4XP/venv/bin/python tools/blast.py Ortho4XP/src/auto_patch/layout.py`
   first; run the tests it names once via `run_with_ledger`.
2. Implement the registry-lookup intern for hole rings (ruling above).
3. Twins (extend `tests/test_round16_geometry_consistency.py:444-497`,
   never duplicate): (a) a hole spelled denser than its pad's chain now
   ADOPTS the pad's chain verbatim (pads-frame pair count 0, emitted
   spelling identical); (b) a hole vertex beyond `ONEDGE_SNAP_TOL_M`
   pre-move offset keeps both spellings and is REPORTED (existing
   discriminator twin still green); (c) hole dedup and R16-4b behavior
   byte-stable on a shared-nid fixture; (d) `chain_divergence_audit`
   twins stay green (`tests/test_chain_divergence_audit.py`).
4. Acceptance arm — the 4-step tile build (object pads REQUIRE it; a
   --patch-only run has no twin-ring population): `tools/harness/
   build_airport.py OTHH --tile 25 51` in the lane, then mesh replay
   `tools/run_tile_mesh_only.py` with `first_step=2` into a LANE-LOCAL
   build dir (NEVER the X-Plane install; step 1 re-run rewrites the
   inputs under test and arms the write guard).
5. Measure with THE instrument: `tools/chain_divergence_audit.py` on the
   emitted patch (pads frame). KCLT control (patch frame) before/after.

## Acceptance (named claims)

- OTHH pads-frame twin-ring pairs **20 → 0**, or a residual set where
  every survivor's pre-move offset ≥ `ONEDGE_SNAP_TOL_M` (0.15 m),
  REPORTED per Amendment 2 — nothing in between.
- KCLT control: 0 pairs before AND after; patch body hash quoted
  (`tail -n +3` law) — byte-identical expected if KCLT has no holes in
  the affected class.
- Sub-micron clusters 0 every arm; unowned wall nodes stay OTHH 0 /
  KCLT 0; sub-2° tips stay 0.
- Census: re-baseline BOTH sides under the honest (post-R19-5)
  instrument — the R16 Δ0 was measured with the blind census and may not
  be quoted; then Δ0 beyond the 0.01 m materiality floor, via
  `tools/harness/census.py` with sidecars present.
- **Attempt cap: ONE.** This target was re-ruled at Amendment 2 — a miss
  is a STOP-and-report to the Fable lead, not a second attempt.
- `.progress` heartbeat; shared repo UNCHANGED; arms named in the
  ledger; build-time impact statement (a registry query per hole vertex —
  expected noise; quote it).

## Out of scope

R16-3 real-data arm; ramps-clipped-after-wall class (both stay DEFERRED
lines); any change to splice tolerance (`_WELD_TOL_M`), snap tolerance,
or the candidate gate's thresholds.

## AMENDMENT 3 (Fable lead, 2026-08-12, after the lane's attribution) —
## the real generator is slice-C decimation, and it joins the R16-1 frame

The lane's measured attribution REFUTES this spec's ruled root cause.
At the R16-1b loop, OTHH's hole rings are ALREADY the pad's spelling
(`same_spelling` 771/791; KCLT 116/116) — pre-splice nid identity holds
today and fix shape (i) is INERT (correctly unattempted; the one-attempt
budget is unspent). The splice signature is absent (0/281, 0/166 within
5 mm of a neighbour chord); the decimation signature is total (47/47
differing vertices within `_DEC_PERP_M` = 0.02 m of the pad chord;
interventional repro + control flip on that single variable).

Mechanism: CHAIN-AWARE FINAL DECIMATION (slice C, `layout.py:2519`)
builds `_occ` from `pending` only (`:2585-2595`), walks `pending` only
(`:2670`), writes back to `pending` only (`:2749`). `_interior_rings`
never enter, so a vertex shared by a pad exterior and its hole ring is
judged and removed ONE-SIDEDLY — the exact class the block's own comment
forbids, and the same one-sidedness R16-1 already cured in needle
removal.

RULED FIX (supersedes fix shape (i); fix shape (ii) stays refused):
slice-C decimation joins the R16-1 frame. `_interior_rings` enter
`_occ`, the chord-agreement/geometry predicates, the max-chord retention
walk, and the removal sweep as FIRST-CLASS CHAINS — a shared vertex is
kept or removed consistently on every chain that spells it. Ring-private
vertices keep their existing protection (the `_a1 is None` clause — rings
never lose their own vertices); the chord-agreement veto (`_cend !=
_chord`) stands; NO constant changes.

The attribution instrumentation (pairing census + candidate trace,
commits `5c7f7f2`/`8bf7947`, proven byte-neutral) is KEPT as the standing
window on this frame.

Amended acceptance (patch frame; no tile build required — the patch-only
build carries the pad population):
- OTHH twin-ring pairs **21 → 0** in this tree's frame (owner artifact
  24 — measured for the record, not a gate); every differing-vertex
  class within `_DEC_PERP_M` must vanish.
- KCLT: the 3 pairs within `_DEC_PERP_M` → 0; the 31.9 mm outlier is a
  DIFFERENT generator — REPORT it, do not chase it (it becomes a
  deferred attribution line).
- Sub-micron clusters 0; census re-baseline + Δ0 beyond the 0.01 m floor
  (honest instrument); KCLT body hash quoted before/after.
- The second decimator (`emit_decimate.py`) is NOT audited in this lane
  — recorded as a deferred line.
- Attempt cap: ONE attempt at the ruled fix (the budget is unspent).
