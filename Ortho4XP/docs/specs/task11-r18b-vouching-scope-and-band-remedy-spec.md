# Task #11 — r18b: scoped path-vouching + the HECA band inversion, solver-side (Fable spec, 2026-08-12)

Lead: Fable session (deviations STOP and report to this spec's author;
`docs/RULINGS.md` canonical; PRE-SHIP DEV MODE in force).

## Context (measured, three sightings, all cited in the STOP report at
## `src/auto_patch/object_footprints.py:855-894`)

- `structure_ring`'s `name_vouched` matches "hangar"/"term_building"/
  "/terminal" ANYWHERE in the resource path (`object_footprints.py:890-893`).
  HECA's Tai Models pack files everything under `Airport/Hangar_Tower/`, so
  667/817 rings vouch, disabling both the hull-fill floor (`:970-973`) and
  the tall-base floor (`:946-948`). Building176's seed ring (hull fill
  0.00036) is kept. The CORRECT predicate already exists and is what the
  R18-2 evidence gate uses: `evidence_name_vouches` (`:209-231`) —
  basename-or-library-virtual-path only.
- Substituting the scoped predicate is measured-correct on population
  (HECA 817→210, every survivor hull fill 0.11-1.64) but HECA then fails
  `assert_no_final_band_inversion` at 679/4,792 nodes: pair 5984
  (110.610 m, 05C/23C) vs 3284 (60.980 m, 05L/23R), spread 49.630 vs
  budget 47.559, shortfall 2.0709 m. Third-arm attribution: it is the
  substitution, not the R18-2 gate.
- Decisive: the CIFP-FORCED spread FITS every observed budget
  (33.6-35.8 m vs 47.3-48.9 m; `lateral_spine_nodes.py:143-146`). HECA is
  feasible; the ~14 m above CIFP is world-dependent (DEM-follow ride,
  seating, flex-applied targets). The budget was IDENTICAL (47.559)
  across the R-b and r18b arms — the substitution moved anchor VALUES.
- Working mechanism hypothesis (NOT yet interventionally confirmed): the
  607 removed rings were phantom pads levelled to the host apron median;
  removing them changes the ground the runway profiles DEM-follow over,
  moving flex-applied station targets on 05L/23R. Exact precedent:
  `runway_redistribute.py:1878-1891` — dropped target ⇒ uniform band
  inversion; fixed by RELAX-don't-only-DROP.
- NOT the R8-2/R9 writeback crown defect — that shipped fixed
  (`solver_primitives.py:3556 _carried_band_closure`).

## Rulings (settling the open questions)

1. **The substitution is total.** `structure_ring` consumes
   `evidence_name_vouches`; the wide predicate is deleted (its only
   consumers are the two floors). ONE predicate implementation. The CYXY
   2026-07-28 calibration case is preserved by construction (the stock
   arched hangar vouches via its library virtual path
   `lib/airport/hangars/...`); CYXY keeping its hangar is an acceptance
   control, and the report notes for the owner that the scoped predicate
   is a narrowing of mechanism, not of the ruling's intent.
2. **The route budget is LAW and does not move.** The remedy operates on
   the world-dependent half of the spread: flex-applied / DEM-follow
   station targets relax toward band feasibility (the
   `runway_redistribute.py` relax-don't-drop machinery is the primary
   lever; the eatguard hard-anchor-contradiction predicate
   (`anchors.py:1689-1715` territory, KSTJ 31→0) is the secondary lever
   for apron-contact anchor caps projected against nearby hard anchors).
   Metres moved is not a defect metric (band-lawful displacement law);
   DEM-follow is a smoothing preference, never a feasibility authority.
3. **Anchor legitimacy is tested FIRST** (anchor-placement law; mechanism
   before fix). Phase 1 below must name the author and provenance of
   3284@60.980 (CIFP threshold? DEM sample? flex target?) and of
   5984@110.610 before any remedy lands. HECA's ~85 m relief is REAL —
   do not treat the spread as absurd on its face.
4. **OTHH's 20 unadjudicated R18-2 pads are out of scope** — quoted in the
   consolidated acceptance, adjudication stays a DEFERRED line.
5. **No default-OFF interim unless the remedy misses its attempt cap.**
   Target posture: both halves land default-ON and HECA passes. If phase 2
   misses twice (cap), STOP: land nothing default-ON, park the substitution
   behind a default-OFF flag with the STOP report, and return to the Fable
   lead. A default-ON change may not refuse a battery airport
   (`lateral_spine_nodes.py:150-154` precedent).

## Implementation plan (one Opus implementer, coupled change-set)

Phase 1 — substitution + interventional attribution:
1. Swap the predicate (ruling 1); keep the STOP-report comment, rewritten
   as history.
2. HECA arm (--patch-only) with the substitution live and the band law
   allowed to report (capture, don't crash the arm): dump per-node
   membership via `grade_graph_validate.py:909 final_band_excess_report`
   plus the anchor provenance for 3284/5984 and the 05L/23R flex-applied
   target set, baseline-vs-arm. CONFIRM (or refute) the phantom-pad →
   DEM-follow → target-shift mechanism interventionally (e.g. an arm with
   substitution live but the removed rings' pad levelling force-retained
   is a clean isolation if cheap; otherwise target-set diff suffices as
   the interventional read — justify in the report).
3. If attribution refutes the hypothesis (e.g. 3284 is itself a misplaced
   or minted anchor): STOP, report to the Fable lead. A misplaced anchor
   is itself the defect — do not relax around it.

Phase 2 — solver-side remedy (only after phase 1 confirms):
4. Extend the verify-and-relax machinery so world-dependent (flex/DEM-
   follow) station targets on a runway profile RELAX into the
   band-feasible interval when the final-band record would otherwise
   invert — never dropping law targets (CIFP-forced values are law and
   immovable), never widening the budget. Bounded by `reach_band_unified`
   (ONE band; both seats and endpoints already consume it).
5. Tests: twins for (a) a flex target relaxing exactly to feasibility with
   CIFP targets untouched; (b) a CIFP-forced infeasibility still refusing
   loudly (feasibility-is-guaranteed law: real airport + real thresholds
   ⇒ lawful surface exists — a refusal here means minted law, so the twin
   uses a synthetic impossible CIFP pair); (c) the existing
   `test_final_band_inversion.py` suite stays green.
6. Per-law test files once via `run_with_ledger` (check `--history`);
   `blast.py` quoted per touched file.

## Acceptance (named claims)

- HECA (--patch-only, production frame): rc=0, `assert_no_final_band_
  inversion` PASS (residuals ≤ 0.01 m = `FINAL_BAND_INVERSION_TOL_M`);
  rings 817→210 (±0 — the population number is exact); survivors' hull
  fill within [0.11, 1.64]; pads 172/176/177/186 all absent; the two
  owner coordinates ground-conformant.
- CYXY control: the stock arched hangar ring still vouches (hangar kept),
  patch census Δ explained or 0.
- KSTJ control: 0 inversions preserved (eatguard predicate unregressed);
  byte-identical patch expected — quote the body hash (tail -n +3).
- OTHH control: build rc=0, pad/ring population quoted (86→66 / 1358→1245
  expected from R18-2; adjudication deferred).
- Census before/after per airport under the honest instrument
  (`grade-check` skill frame — never bare check_grade).
- Shared repo UNCHANGED; arms named in the ledger; convergence guards:
  materiality floor 0.01 m, attempt cap 2 (STOP on second miss),
  `.progress` heartbeat.
- Build-time impact statement (predicate swap is O(1) per ring; the relax
  pass must quote its measured cost; ledger tripwire ~2x escalates).

## Out of scope

Route-metric/budget changes; scorer-side LAWFUL-AIRSIDE VOUCHING
(`RULINGS.md:1578` — different mechanism, do not conflate); OTHH pad
adjudication; any anchors.py seat machinery beyond the contradiction
predicate if phase 1 points there (that is a STOP-and-report instead).
