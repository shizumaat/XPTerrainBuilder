# v2 — HECA parity with v1: the priority model (spec, 2026-09-08)

Owner (RULINGS 2026-09-08a): v2 "much worse almost everywhere" than v1
at HECA; determine the changes. Measured by scout `hecav1v2` (RULINGS
08d, one tree, one frame). Author: session (Fable). Implementer: lane
`v2chord`. The owner may veto 08d-1 before the merge.

## 1. Change 1 — the runway fits the THRESHOLD CHORD, not the DEM

Today: `pipeline/build.py:40` DEM-fit 20/m on runway vertices;
`rulesets.toml:39 runway_profile_smoothness 5000` straightens between
holds. v1: `runway_redistribute.py` anchors a CIFP-chord parabolic
envelope and fills (05R/23L +4.70 m, bow −4.25 vs v2 −9.61 at the DEM).
Change: a per-vertex CHORD target for every runway ridge vertex — the
straight line between the two CIFP threshold pins (`runway_profile`'s
pins) at the vertex's station — and the runway family's fit term
becomes |z − chord| (weight `common.runway_chord_fit`, senior to the DEM
fit, junior to the K/max-grade/transverse HARD rows and to the
smoothness preference). The DEM fit stays for every other role. Keys in
`rulesets.toml [common]`; law python limits as always. Expected: 05R/23L
bow −9.6 → ≈ −4 (fill); 05C/23C descends steadily from 05C; the
05L/23R hump falls with change 2. Twin: a two-pin ridge over a valley
DEM sits on the chord.

## 2. Change 2 — surface families beyond the route graph YIELD (04i as tiers)

Today every surface family is hard (`law_tiers.mode hard`); 07a and 08d
measured them as redundant 1.5 % shortcuts that drag (05C/23C) or lift
(05L/23R +7.5 m) the runway. v1: per-edge caps that yield (junction max
9.1 %). Change: `junction_mesh`, `taxi_box`, `no_step_pairs` (§1.1),
`apron_within_shape` chords/edge portions and `roads` profiles are
minted as PREFERENCE rows (`Diff.soft`, escalation group per family per
face, `ceiling` = a per-family max: `taxi_yield_max` 3 % / `apron_yield_max`
3 % / roads their own core clamp — state keys) charged JUNIOR to the
chord term and senior to the DEM fit; the runway-connected route
graph's chain rows (05ac: centreline + lateral hops + crossings), the
reach bands, the K rows and the runway transverse law stay HARD. The
04t(1) last resort stays for what is still infeasible. Expected: the
05L/23R hump +7.61 → ≤ +1.59 (the measured drop arm), the SW strips
follow the runway fill (strip tie 06e), the census reads yielded rows
as v1's does — the `apron_over_preference`-style report figure per
family (`yielded_rows`, max grade) in sidecar/report/census.

## 3. Change 3 — a joint carries ≤ 2 m, hard; else the cell grades through

`emit.toml [terrace] max_step_m = 2.0` becomes LAW (v1
`APRON_TERRACE_MAX_STEP_M`): in `pipeline/territory.py apply_joints`, a
label boundary whose predicted step (the contacts' ceiling difference
less what the in-shape path can hold at the apron cap) exceeds 2 m is
NOT a joint — its rows stay (as change-2 preferences, so the cell grades
through at the apron cap toward its contacts and yields where it must);
a joint under 2 m stays declared. Same rule for 06n's between-cell
joints. Expected: HECA joints 62/63/64/71/72/0/27/31 (5.9–9.45 m)
disappear, pav132 and pav131 become continuous surfaces (v1's −3.6 mean
cut); CYXY 3 / OTHH 15 joints (≤ 0.39 m) unchanged.

## 4. Change 4 — the owner's site: the apron edge RAMPS to the groundside

At 30.1139552, 31.4095465 (pav131 face 215 vs the 3-node sliver face
269 of the same pavement, joint 27 = 6.20 m) — with change 3 the joint
cannot exist; the sliver face is a classification artefact: merge a
same-pavement face under `emit.identity.min_distinct_spacing_m` × k
area into its neighbour (state k). Where the apron meets GROUNDSIDE
(v1's 3 m step the owner disliked): the apron edge ramps to the
groundside ring at the groundside cap (`GROUNDSIDE_MAX_GRADE` 5 %, v1
`config.py:1519` — v2 key in `zones.toml` or `common`), a preference
under change 2. Twin: an apron 3 m above groundside 60 m away → a 5 %
ramp, no step.

## 5. Acceptance (ONE airport = HECA; then CYXY/SPJC/OTHH/LEMD `--base-arm`)

Synthetic-first on the HECA capture (the 60 s solve-arm pattern,
`docs/specs/auto-patch-v2/heca-sag-ablation/`): quote 05R/23L, 05C/23C,
05L/23R bows and z−DEM (mean/min/max) after each change. ONE build
`build_airport.py HECA --engine v2`: the three runway profiles vs v1's
(scout table §5: bows −9.53 / −4.25 / −0.28, z−DEM), z_v2 − z_v1 by role
vs today's (mean −0.43, p10 −4.08, p90 +2.49, > 1 m 57 %) — the bar is
the SAME-FRAME divergence halving (|dz| > 1 m ≤ 30 %, > 6 m ≤ 200), the
owner's site (no step > 2 m within 60 m), joints (none > 2 m), the
`yielded_rows` figure per family and the census under both readings
(law-true violations as v1's, and yielded-as-lawful), solve wall.
CYXY/SPJC/OTHH/LEMD verify unchanged (0/0/0/16). Build-time statement.
The scout's scripts (`scratchpad/hecav1v2/cmp2.py`, `rwy.py`) are the
comparison instrument — promote them to `tools/` with an INDEX entry
(second use).

## 6. Consumer census (owner RULINGS 2026-08-30l) — written by lane `v2chord` BEFORE editing

### 6.1 Change 2 — hard family rows become PREFERENCE rows (`Diff.soft` / `Linear.soft`, ceiling)

Mechanism: ONE transform at assembly (`constraints/yielding.py::yield_rows`, run
inside `pipeline/territory.territory_constraints` after the joint filter):
every HARD `Diff` / `Linear` of a generator named in `emit.toml [yield]
families` becomes `soft = "yield:<family>:<face>:<k>"` (one escalation group
PER ROW, the apron precedent — the solver pays for exactly the relief it
uses; the group name carries family + face for the report) with
`ceiling = <family>_yield_max` (a Diff: a grade; a Linear: ceiling metres =
(yield_max − cap) × the row's own span read from its bound).  Rows of the
runway family, the taxi CHAIN (`taxi` generator rulings "centreline" /
"chain"), reach bands, K, runway transverse, pads, structures, zones, strips,
seams, flat datum: untouched (hard).

| consumer (reads the rows) | what it does with a soft row today | ruling for the yield rows |
|---|---|---|
| `solve/assemble.to_sparse(soft="defer")` + `assemble` | slack column per group, bounded `[0, ceiling − cap]`, charged `preference[prefix] × max fit weight × Σd` | new prefix `yield` in `Weights.preference` (0.9, = the apron's: junior to the runway chord fit 20/m, senior to every other role's DEM fit) — one column per row |
| `to_sparse(soft="ceiling")` (IIS probes, `relax`/`variance`/`iis`) | a hard row at its ceiling | same: an IIS names LAW contradictions only; a yielded family is never named below its ceiling |
| `solve/relax.py` admission (`r.soft is None`) | a soft row is never relaxed by 04t(1) | the yield rows are not relaxable beyond their ceiling; 04t(1) keeps the remaining hard rows (pads, apron 1 % pref stays soft as before) |
| `solve/tiers.demote` / `row_tier` / `_yields` | a row already soft keeps its group; `law:` groups only in the yield report | unchanged; a demoted set never touches the yield rows |
| `solve/highs.residual` | judges a preference row at its escalated cap | unchanged |
| `solve/why.py` (binding chain) | cap + escalation of the group | unchanged: a yielded row binds at its escalated cap |
| `pipeline/why.py` | reads `prob.soft_cols` escalation | unchanged |
| `constraints/apron.apron_preference_report` / `preference_face` | `apron:` groups only | unchanged (the 1 % rows keep their prefix) |
| `pipeline/territory.apply_joints` | drops any straddling row | unchanged (runs BEFORE the transform) |
| `constraints.seam_exempt` | drops pin↔pin Diffs regardless of softness | unchanged |
| `pipeline/publication` (no_step edges, mesh edges, taxi pairs, portions) | publishes the priced pairs; the census prices them at the CAP | unchanged: the census reads a yielded row over its cap as a VIOLATION (v1's reading); NEW key `yielded_rows` (the `relaxed_rows` record shape + `family`, `cap_after`) so both readers can count them apart |
| `verify/census.mark_relaxed` | tags rows on relaxed vertices `relaxed_by` | NEW `mark_yielded`: rows whose endpoints are a yielded row's vertices carry `yielded_by = "08d"`; the build log prints the by-family summary under both readings |
| `tools/check_grade.stamp_relaxed_rows` | re-prices a pair at its relaxed cap, stamps `relaxed_by_04t1` | reused with the `yielded_rows` list and the stamp `yielded_by_08d` (a new `OUT_OF_SCOPE_CLASSES` heading; counted in its family, reported apart, never adjudicated); over its escalated cap the row stays a violation |
| `tools/harness/census.py` | prints out-of-scope classes at zero | the new class prints through the registry; the `yielded_rows` figure per family beside `apron_over_preference` |
| `tools/rwy_profile.py`, `v2_solve_replay.py` | read z only | report `yielded_rows` per family |
| LP size | HECA today 275,842 diffs / 43,713 linears, 24,935 apron + 10,423 portion soft groups | + ≈ 60 k groups (no_step 89 k pairs stay HARD? — NO: §2 names `no_step_pairs` §1.1 as yielding: + 89 k); measured in §5 (solve wall vs 47 s) |

Families and ceilings (`emit.toml [yield]`): `junction_mesh` and `taxi_box`
(the `taxi` generator's box rows only) → `taxi_yield_max` 3 %; `no_step` §1.1
pairs (not the §1.2 rate rows) → `taxi_yield_max`; `apron` /
`apron_edge_portion` hard rows → `apron_yield_max` 3 %; `roads` →
`road_yield_max` = the core clamp (8 %: the road cap itself — a road row
yields only where its cap is the stricter contiguous class's; a road at
its own 8 % cap has nothing to yield).

### 6.2 Change 3 — a joint carries ≤ `max_step_m` HARD

| consumer | today | ruling |
|---|---|---|
| `planar/territories.Territories._decide` (07g predicate) | joint ⇔ `gap > cap·d + min_step` | joint ⇔ `min_step < gap − cap·d ≤ max_step_m`; above it the labels AGREE (no joint: the rows stay, the cell grades through as change-2 preferences) |
| `_adjacency_report`, `joint_planar_edges`, `label_joints`, `apply_joints`, `publication(straddles)`, `joint_steps` | all derive from `terr.joint` | consistent by construction; `stats.over_max_pairs` NEW (pairs the step rule un-jointed, reported) |
| `planar/terraces.split_terraces` (06n joints: split copies at the planar build) | splits regardless of step | the split stays (the planar map is built before any elevation exists); after each solve `pipeline/territory.weld_built_steps` reads every declared joint's BUILT step (v1 reads `APRON_TERRACE_MAX_STEP_M` on the emitted step) and, above `max_step_m`, WELDS the 06n copies (`Flat((a, b))` per pair, generator `terrace_weld`, never dropped / demoted), withdraws the joint from `pm.terrace_joints` (the sidecar declares it not) and welds a label contour's label pairs; the set is re-solved (`Config.joint_passes_max` 2). A PRE-SOLVE predictor from the copies' reach ceilings was measured and REFUTED (lane v2chord: CYXY #17\|#87 predicted 8.10 m, built 0.002 m) and deleted |
| `pipeline/publication.terrace_joints_ll` | declares every `pm.terrace_joints` | declares only the kept ones (the stage's `pm`) |
| `verify/steps.py`, `check_grade` terrace readers | forgive steps across declared joints | an un-jointed boundary is not forgiven — a step there is a violation (v1's reading) |
| `constraints/pads.py` (`terrace_group`) | a pad belongs to its cell's group | unchanged (the groups stay; the weld couples the two cells' copies) |
| `emit/*` | no reader of `terrace_joints` | unchanged |
| CYXY 3 / OTHH 15 joints (≤ 0.39 m) | declared | unchanged (under 2 m) |

### 6.3 Change 4 — the owner's site

(a) `planar/build.py`: after the arrangement, a face whose area is under
`(identity.min_distinct_spacing_m × emit.yield.sliver_area_factor)²` and
whose ring shares an edge with a face of the SAME role and SAME ref is
merged into it (the arrangement's polygon union) before noding — a
classification artefact, never a cell; counted in `BuildStats.slivers_merged`.
(b) `constraints/yielding.groundside_ramps`: for every apron ring vertex
within `zones.adjacent_ground.groundside_cutback_m + weld_spacing_m` of a
groundside-pavement ring vertex (the stand-off pair the cut-back made), one
`Diff` at `emit.yield.groundside_ramp_max` (5 %, v1 `GROUNDSIDE_MAX_GRADE`)
as a preference (group `yield:groundside_ramp:<face>:<k>`, no ceiling):
the step is charged, a ramp is free.  Consumers: the census reads no such
pair (a groundside|apron cross pair is the stand-off's lawful terrace —
unchanged); the solve's DEM fit on the groundside (1/m) yields to the ramp
charge (18/m), so the groundside lifts/cuts to meet the apron edge and
grades away at its own cap.
