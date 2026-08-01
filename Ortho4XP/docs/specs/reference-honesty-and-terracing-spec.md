# Reference honesty + groundside terracing — the plan

Owner approval 2026-07-30 ("Accept groundside terracing … proceed with
implementing the plan").  Derived from the Fable review of the same
date, which measured the apron law CORRECT and the mega-apron U
FEASIBLE (arm-to-arm budget 37.6 m vs 34.35 m emitted).  **No apron-law
change is in scope.**

Owner goals this plan serves, in order: (1) all pavement within grade
law; (2) zero breaks, cliffs, errors, failing tests; (3) any residual
"infeasible" must yield a precise law change, since the real airport
proves feasibility.

---

## Track 1 — reference honesty (the dominant root)

**Defect.** R samples its spine and weld anchors from raw `elev` at
pass entry (`solve.py:1341-1349`, `:3539-3556`) — i.e. AFTER the
`solve.py:1169` quarantine blend — violating `bounded-yield-spec`
B.4's ★ clause ("never from raw elev at yield entry").  Only pad
anchors use rod levels.  Consequence measured: near corrupted low
anchors, free-node R sits 5-8 m below the incoming fabric (incoming
104.13 → R 95.88 at 2.5 m from the seam site).

**This one defect explains** the "8,093 anchor-vs-anchor over-cap
slabs" (an artefact of the blended field, not the law), R's
building199 weld regression 0.16 → 2.93 m, seam-box >5 % locals
14 → 33, CYXY `test_pavement_grade` 7 → 16 under R, the residual
0.552 m corridor sag, and D's ~1.2 m corridor-mouth step.

**Work, in order:**

1. **R anchors law-true.**  Sample spine anchors from the rod-held
   string (the store Part D already enforces); refuse or soften any
   anchor whose node is in a break region — a quarantined value is not
   law-true.  Fall back to rod/band-derived values, **never** raw
   `elev`.  ★ Risk named by the review: break regions cover 830 of 904
   mega-ring vertices, so a naive refusal may strip too many anchors —
   measure the surviving anchor count and report it.
2. **Part D.2(2)** (specified, never implemented): derive non-service
   corridor `z_ref` from the rod-implied string instead of the raw
   snapshot at `solve.py:1293-1296`.  Retain the yield-entry snapshot
   for SERVICE corridors (the CYXY 8.95 % mint reason).
3. **Rigid branch vertices**: give rod-degree-≥3 vertices the same
   rigid treatment as chains (memory `rod-chains-split-at-branches`
   names this as D's known residual).  ★ Preserve the chain-endpoint
   hard-neighbour clamp — it is the 05C runway-kink guard.
4. **Forensics measurement** (deliverable in its own right): one HECA
   build with the forensics dump; for every remaining broken node,
   name its floor>ceiling witness pair BY ANCHOR CLASS.  This is the
   honest answer to whether the mega-component is feasible whole, and
   the direct test of the groundside-bridge mechanism below.

**Acceptance:** anchor-vs-anchor over-cap collapses (report the new
figure against 8,093); building199 weld ≤ 0.2 m; seam-box locals back
toward 14; corridor sag ≤ 0.5 m with `test_spine_taut_string_heca`
green on merit and absolute stations held; corridor-mouth step gone;
HECA seam site holds the 106-109 class; flat fixtures at ZERO step and
tear sections; `test_single_graph_acceptance` 4/4.

---

## Track 2 — groundside terracing + the surfaces around it

### 2a. The terrace law (owner ruling 2026-07-30)

> Within groundside, the GRADED objects are the pavement surfaces and
> the ROADS — each graded along itself under its own cap (4 %
> groundside / 5 % service road).  The ground BETWEEN those graded
> pieces may **TERRACE**: step without limit, emitted as retaining
> walls.  A groundside region is NOT required to be one continuous
> graded surface.  A lot whose smoothed-DEM span exceeds its cap ×
> extent MUST terrace rather than hold one level.  Groundside values
> never act as a feasibility witness (floor or ceiling) for airside
> pavement beyond the Part-C mouth allowance.

Justification (measured): 1,518 of HECA's 1,582 emitted within-shape
violations are groundside-internal (worst 390 % = 14.8 m over 3.8 m);
47 clusters inside the mega-apron's U bridge its arms with emitted Δz
to 14.1 m against a 2.4 m budget.  Retaining-wall machinery exists
(8 walls emitted in that interior today) — reuse it, do not build a
second one (single-pass principle).

Implementation notes: terrace lines are a DESIGNATED set (where the
law says a step is allowed), not "anywhere the solver finds it hard";
the graded ribbons (pavement, roads) keep their existing caps and must
remain continuous along themselves; the airside-witness clause is a
change to what `apply_groundside_reach` / `_gs_hard` may assert
(Part C already bounds the value — this bounds the ROLE).

### 2b. Adjacent-ground re-solve after pavement moves

The `graded_strip ↔ adjacent_ground` tear class mints whenever
pavement legitimately moves (CYXY 0 → 6 under R, HECA 7 → 23) because
the strips do not re-solve afterwards.  Re-derive graded-strip /
adjacent-ground values AFTER the final pavement projection, or move
the existing reconcile pass last.  ★ Prefer reordering to a second
derivation (single-pass principle).

### 2c. Crown shed — runway keys

`crown.py:823-846`'s Lipschitz shed exempts runway keys on a
"uniform-drop profile" premise measured FALSE (39 on/off transitions
along HECA's rails).  Remove the exemption, or make the drop
assignment continuous along the rails.  Kills the 2 HECA runway
violations.

**Track 2 acceptance:** HECA groundside-internal within-shape
violations collapse from 1,518 (report the figure); strip seam tears
CYXY → 0 and HECA → 0-class; `test_runway_longitudinal_grade[HECA]`
green on merit; no airside regression (seam site, weld gate, flat
fixtures as above).

---

## Sequencing and gates

Track 1 and Track 2 are independent file sets and run in parallel:
Track 1 = `route_profile/{solve.py,one_solve.py}`, `apron_reference.py`;
Track 2 = `groundside.py`, `adjacent_ground.py`, `crown.py`, and any
pipeline ORDERING for 2b.  Coordinate through this spec; do not edit
outside your track.

`O4_APRON_STRING` is a SHIP BLOCKER until Track 1 step 1 lands (the
2.93 m weld cliff is user-visible).  Every other landed gate stays ON.
Each new change is default-ON behind its own named gate with gate-off
byte-identity proven.

**Final battery (parent session runs it once both tracks land):** flat
fixtures CYXY/SPJC/SPLP, HECA emitted battery, and
`tools/check_build_time.py --run --runs 3` for the ACCUMULATED
changes — each change has been measured sub-threshold individually but
the sum has not (CLAUDE.md hard law).

## Constraints

Main tree `/Users/noah/XPTerrainBuilder/Ortho4XP`, `venv/bin/python`
from that cwd; `git log --oneline -1 && git status --short` before AND
after every measurement; never commit/stash/revert; no KCLT (OOM); one
airport build per process; output to files, never pipes;
PID/artifact-verified waits with timeout arms; measure the EMITTED
patch, never the pre-yield dump; hash patch BODIES (`tail -n +3`) —
the `o4_provenance_built` header defeats whole-file hashing; never
baseline a session's FIRST build (cold cache); prove gate identity
with a copied `src/` tree (`/tmp/apron_R/src_base`,
`/tmp/apron_spec_work/build_alt_src.py`), never by mutating the shared
tree.  STATUS/memory documentation stays with the parent session.
