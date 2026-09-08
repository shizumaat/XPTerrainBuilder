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

## 7. Replay arms for owner decisions 08g-1 / 08g-2 (lane `v2chord2`, 2026-09-08, NO build)

Instrument: `tools/v2_solve_replay.py` on a HECA capture (rows `main`..`+4`:
lane v2chord's capture of the pre-merge tree, `scratchpad/v2chord/replay0-4.json`;
rows A0..C2: this lane's capture of the merged tree, main `fafb5b67` into
`claude/v2chord`, 75 s, 23,561 vertices / 1,147 faces), `--from constraints`,
foreground, one arm at a time so the walls are clean († = ran under
contention).  A0 reproduces `replay4` to the centimetre and, emitted through
the build's own emit half (`--emit`), reproduces the 08g divergence bars
against the v1 control `/tmp/harness/HECA_20260908T073420.osm`
(`patch_proximity_diff.py`, 21,328 joined nodes: |dz| > 1 m 11,368 = 53.3 %,
> 6 m 250; the closing build `HECA_v2chord.osm`: 11,361 / 252) — a replay
arm's patch IS a same-frame instrument.  Sites: z − DEM (mean) over the
capture's vertices within 40 m of each of the six SW strip/connector points,
in the brief's order (30.105079,31.398396; 30.106722,31.398259;
30.104965,31.394201; 30.105199,31.395914; 30.114188,31.402235;
30.112146,31.435712); v1 sits +4–5 m over the DEM at all six.

| arm | 05R/23L bow; z−DEM mean/min/max | 05C/23C bow; z−DEM mean/min/max | 05L/23R bow; z−DEM max | 07g joints > 2 m | 06n joints > 2 m | solve wall per pass (s) | divergence vs v1: \|dz\| > 1 m % (n) / > 6 m | six SW sites z−DEM mean (m) | note |
|---|---|---|---|---|---|---|---|---|---|
| main / replay 0 (1.0.293 tree) | −9.64; +0.57 / −0.20 / +2.59 | −9.20; −1.62 / −5.73 / +1.48 | −2.02; +7.78 | 6 | 10 | 50.2 (1 pass) | build 1.0.293: 57 % / 917 (08g) | not read¹ | v1: −4.25 / −9.53 / −0.28 |
| +1 chord fit | −4.84; +4.68 / −0.19 / +8.65 | −9.03; −1.46 / −5.61 / +1.41 | −0.53; +7.81 | 6 | 13 | 47.6 (1) | not emitted | not read¹ | |
| +2 yielding families | −3.21; +5.66 / +0.26 / +9.09 | −6.93; −0.07 / −3.76 / +2.42 | −0.53; +6.67 | 6 | 11 | 88.5 (1) | not emitted | not read¹ | |
| +3 joint step law | −3.21; +5.66 / +0.26 / +9.09 | −6.97; −0.09 / −3.80 / +2.41 | −0.49; +6.63 | 0 | 2² | 260.5 (3 passes, total) | not emitted | not read¹ | |
| +4 owner's site (= a52593d0) | −3.27; +5.64 / +0.26 / +9.09 | −6.99; −0.09 / −3.81 / +2.40 | −0.49; +6.62 | 0 | 2² | 305.0 (3, total) | closing build: 53.3 % (11,361) / 252 | not read¹ | build 248 + 172 + 177 |
| **joint passes 2 = A0 (today, merged tree)** | −3.27; +5.64 / +0.26 / +9.09 | −6.99; −0.09 / −3.81 / +2.40 | −0.49; +6.62 | **0** | **0** (10 contours, 33 joints; worst 07g 1.82, 06n 1.96) | 113.3 + 127.0 + 116.7 = **357.0** | 53.3 % (11,368) / 250 | −0.04, +0.03, −0.04, +0.36, −0.14, +5.73 | taxi max \|z−DEM\| stub/junction/primary/cross/secondary 8.33 / 8.82 / 8.59 / 6.56 / 6.50; strip 8.19 |
| joint passes 1 (A1) | identical to A0 | identical | identical | 0 | **2** (06n 367\|391 3.00 m, 336\|391 2.99 m — the pair the second re-solve welds) | 113.8 + 128.0 = **241.8** | 53.4 % (11,378) / 252 | identical to A0 | |
| joint passes 0 (A2, joints from the first solve only) | −3.21; +5.66 / +0.26 / +9.09 | −6.94; −0.06 / −3.76 / +2.42 | −0.50; +6.63 | **2** (2.71, 2.16) | **5** (334\|335 5.98, 40\|335 5.83, 335\|336 4.14, 335\|350 4.14, 92\|103 2.07) | **109.8** | 54.5 % (11,614) / 290 | identical to A0 | |
| taxi DEM-fit 0 (B: `primary_parallel, secondary_parallel, stub, cross_connector, junction` 8 → 0; strip 1/m kept) | −3.09; +5.97 / +0.26 / +9.39 | −7.03; −0.09 / −3.85 / +2.86 | −0.46; +6.97 | 0 | 0 | 136.7 + 141.8 + 160.4 = 438.9 | **55.3 % (11,790) / 262** (worse) | +0.07, +0.35, +0.08, +0.51, −0.06, +6.81 | nothing floats: taxi max 9.24 / 8.83 / 8.86 / 7.73 / 7.73, strip 8.57 (the runway's own fill is +9.39); feasible, optimal |
| taxi + strip DEM-fit 0 (B2: + `graded_strip` 1 → 0) † | −3.09; +6.00 / +0.26 / +9.52 | −7.03; −0.08 / −3.85 / +3.02 | −0.46; +7.09 | 0 | 0 | 156.3 + 316.4 + 340.7 = 813.4 † | **56.2 % (11,982) / 761** | +0.33, +0.75, +0.56, +1.60, −0.45, +7.55 | FLOATS: strip −142.56 m at 30.122285,31.450696, primary_parallel −14.78 m, stub +12.41; hard set INFEASIBLE → 04t(1) relief Σ 0.054 m |
| chord-fill (C2: strip + the five taxi roles within the strip take the crown-plane chord target, `runway_chord.fill_roles`; weights as today) | −2.95; +6.02 / +0.26 / +9.44 | −6.98; +0.09 / −3.80 / +2.91 | −0.43; +6.44 | 0 | 0 (9 contours) | 127.1 + 451.6 + 522.6 = **1,101.3** | 53.8 % (11,478) / **318** | **+3.76, +3.43, +3.53, +5.02**, +0.23, +7.11 (v1's +4–5 at five of six) | strip −37.15 m at 30.095584,31.418625 (1,117 strip vertices > 6 m off; A0 359), primary_parallel +10.86; hard set INFEASIBLE → relief Σ 0.013 m; dz range −35.9 / +31.7 |
| combined best | = A0 | = A0 | = A0 | 0 | 0 | 357.0 | 53.3 % / 250 | as A0 | no separate solve: joint passes 2 is the only arm at 0 / 0; both 08g-2 arms (B, B2) and the fill arm (C2) move the divergence bars the WRONG way and C2/B2 float, so the best measured combination is today's configuration |

¹ the `main`..`+4` z arrays belong to the pre-merge capture (a different
planar map after change 4's sliver merge) — the site read is not
cross-capture-comparable and was not taken.  ² lane v2chord's replay
reported 2 06n joints > 2 m at `+3`/`+4`; the same configuration on the
merged tree (A0) reads 0 — the closing build's 42 joints, none > 2 m, is
the ruling figure.

### 7.1 Reading for 08g-1 (the joint law's re-solves, `Config.joint_passes_max`)

The re-solves buy joints, not runways (the three profiles are within
0.06 m across A0/A1/A2).  ONE re-solve clears the first solve's 7
over-step joints to 2 (both 3.0 m, one contour: the 06n pair around
face 391); the second clears those.  Each re-solve costs one full solve
(≈ 115–130 s here; 172–177 s in the build).  Single-pass (A1) would be
241.8 s at 2 joints of 3.0 m; the cheapest arm A2 (109.8 s) leaves a
5.98 m step.

### 7.2 Reading for 08g-2 (the taxi family's DEM fit → 0, `pipeline/build.py DEFAULT_WEIGHTS`)

Weights changed: arm B `primary_parallel, secondary_parallel, stub,
cross_connector, junction` 8 → **0**; arm B2 additionally `graded_strip`
1 → **0** (the zone / reach / strip-tie families are ROWS, not weights —
nothing else holds a strip to the DEM by preference).  **08g-2's
mechanism is refuted.**  The taxi weight is not what holds the SW
connectors on the DEM: with it at 0 the five SW sites move +0.1 to
+0.2 m (v1 is +4–5 m there), nothing floats (every taxi face stays
within the runway's own +9.4 m fill), and the divergence bars get WORSE
(55.3 % / 262).  The holder is the STRIP's 1/m DEM fit acting through
the strip-tie rows (a strip at its transverse cap over ~150 m lets a
connector sit 3–4 m under the runway's fill); removing that too (B2)
lets the strip and the taxiways float (strip 142.6 m, primary parallel
14.8 m off the DEM) — a taxiway with no DEM preference floats where
nothing holds it, exactly the brief's fear.  v1's strips do not float
because v1 gives them a FILL TARGET (the runway's chord surface), not
the absence of a preference.  Arm C2 is that mechanism: it puts five of
the six sites at v1's +3.4–5.0 m and leaves 05L/23R's max z−DEM at its
best (+6.44), but the fill target is not a v1 profile — where a strip
lies beyond a pin's DEM the crown-plane target CUTS (−37 m at
30.095584,31.418625), the hard set goes infeasible (relief 0.013 m),
the > 6 m count rises to 318 and the solve triples (1,101 s).  Not a
shippable arm as written; if the owner wants v1's fill, the target
needs v1's envelope (fill only, never cut, bounded by the strip's own
transverse law) — a spec item, not a knob.

### 7.3 The 05L/23R hump (s 2,025–2,425): `why` on the highest ridge vertex

Vertex **v3269 at s = 2,303**: z 65.20, **+5.38 m over the chord**, DEM
58.64 (z − DEM +6.56).  Binding rows on the vertex (duals solve of the
same LP, |z_dual − z_tiers| max 0.000 m): `runway_vertical_curve` 1 row at
its LOW bound, Σ|dual| 255,289 (the crest is a minimum-K curve);
`runway_profile` 1 row (Σ|dual| 22.5).  Chain trace: 2 hops (vertical
curve +0.01, runway transverse lateral hop +0.47) to v3662
(runway#39 / primary_parallel#44) — FREE, nothing hard blocks it.  So the
crest itself is held by K; what holds the profile HIGH is read
interventionally — relax-one-family arms over the hump's 34 ridge vertices
(full re-solve each; dz = z_arm − z_A0):

| family dropped (with the reach envelope) | rows | hump dz median (min / max) |
|---|---|---|
| **taxi_chain** (the hard 1.5 % taxi chain, untouched by §6.1) | 11,257 | **−2.59 (−3.80 / −1.04)** |
| **taxi_centreline** | 8,306 | **−1.31 (−1.33 / −1.24)** |
| runway_vertical_curve (K) | 6,999 | −0.27 (−0.40 / +0.43) |
| no_step_rate | 22,412 | −0.10 |
| taxi_box | 34,351 | +0.06 |
| junction_mesh | 17,824 | −0.03 |
| no_step_pairs | 94,793 | −0.01 |
| strip_transverse | 7,240 | +0.00 |
| reach_bands (envelope alone) | 6,028 | 0.00 |

One line per hard family holding it: CHAIN — the taxi chain's hard 1.5 %
rows hold the runway up to the NW complex (2.6 m of the 3.6 m over v1;
07a's finding again, now on the chord fit); CENTRELINE — 1.3 m of it
(the same routes, the centreline rows alone); K — 0.27 m (the crest's
shape, not its height); REACH — nothing (0.00); everything soft —
nothing.  The hump is the price of the taxi chain staying HARD while the
runway follows the chord: v1 lets the taxi chain yield at the runway
(08d (2)); v2's chain rows are excluded from the yield transform by §6.1
("the taxi CHAIN … untouched (hard)").  That exclusion is the next
decision (not measured here: the brief's arms were 08g-1 and 08g-2).
