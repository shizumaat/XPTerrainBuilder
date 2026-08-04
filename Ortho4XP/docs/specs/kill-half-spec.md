# The kill half: flip, delete, error loudly

Fable spec, 2026-08-04, OWNER-APPROVED (build-time regressions SPJC
+8.5 s / HECA +9.1 s approved 2026-08-04; recorded in the b56b37a
commit). Lines against b56b37a. BINDING: docs/RULINGS.md — this round
executes "nothing can be quarantined" and the default flip. Evidence:
quarret2/ task 4 (the deletion inventory), flipbattery/, solveprofile/,
stallguard/.

## §1 Defaults flip
The 11 candidate gates flip to default "1" (config.py, each citing its
round's evidence commit): ROUTE_METRIC_ENVELOPE, RETIRE_TERRAIN_PIN_
QUARANTINE, LATERAL_CONTIGUITY_LAW, SERVICE_LOT_ABSORPTION,
NEEDLE_SOURCE_GUARD, SOURCE_COVERAGE_CHECK, RUNWAY_STRIP_WALL_LAW,
DRAINAGE_SPINE_LAW, ROUTE_LEG_EXACT, TRIANGLE_PLANE_REPORTS,
BAND_SEED_EXACT (PROJECTION_STALL_REPORT follows via its implication).
EXCLUDED, still default 0: SCORER_SERVICE_ADJ (re-key queued), all
string gates (owner pause), BREAK_BLEND_CONTINUOUS (see §2 — the blend
dies, the gate dies with it).

## §2 Quarantine machinery deletion (the kill; quarret2 task-4 list)
Delete outright (not gate): check_grade's break-region split
(:3233-3270), plane split (:3261-66), step split _step_touches_break +
_STEP_BREAK_TOL_M (:3377-3405), break_nodes_ll plumbing; the sidecar
emission (layout.py:2419-21); the solve sinks (solve.py:3645,
:5785-94) and the _final_projection_broken_keys carry; the break-blend
(one_solve.py:1974-2230) and O4_BREAK_BLEND_CONTINUOUS with it;
grade_graph_validate break scoping. Remaining minters (A2/A3/A4/B3
report-only forms) keep their REPORT halves only. Where a deletion
exposes a consumer, STOP and report — the quarret2 inventory says the
consumers are enumerated, but verify by blast.py per file.

## §3 The loud error
Post-solve check (ungated — it IS the law): any node in the FINAL
spine_value_fields output with floor−ceiling > 0.01 m ⇒ build ERROR
naming the nodes, values, and route distances. Measured to fire ZERO
times on today's battery (HECA 0/18,073; HEAZ max 0.00035 m post
seed-fix) — a firing after this round is a genuine regression caught.

## §4 Suite reconciliation
(a) The 7 gate-pin tests + the superseded cap-carry test: rewritten for
the new defaults (assert the flip, not the old world). (b) The 2 CYXY
tests red from the EXPOSED 1.9% apron violation: xfail with the drain
reference (an adjudicated, previously-quarantined defect — honest, not
hidden). (c) The 23 standing reds: enumerate what each encodes; update
only those whose expectations the flip legitimately changes (cite per
test); the remainder stay red as the drain's ledger. (d) Fix the
law-true test's assertion short-circuit (report all sections, no
masking).

## §5 Baselines + governance files
New DEFAULT-build baselines (2× each) for all five airports;
tools/build_time_approvals.json gains the owner-approved ceilings
(SPJC 153.2 s, HECA 315.4 s, dated, citing the approval);
build_time_baselines.json refreshed; handover §0 rewritten to the
post-flip state.

## §6 The sim tile
One +30+031 tile at the NEW DEFAULTS (no env gates at all — that is the
point), packaged as sim_review/zOrtho4XP_+30+031_DEFAULT/ (textures
symlinked), with an updated note: this is what every user build now
produces.

Acceptance: per-§ pre-registrations before builds; the loud error fires
zero times across the battery; suite green except the documented drain
ledger; exclusive timing spot-check confirms the approved envelope
(SPJC ≤155, HECA ≤318 - the approval's numbers + noise margin);
foreground builds; per-arm envs logged. Deviations STOP per standing
law.
