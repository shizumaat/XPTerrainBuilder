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

## 8. SHAPES (owner RULINGS 2026-09-08k) — consumer census, written by lane `v2shapes` BEFORE editing (owner 30l)

08k withdraws §3 (the 2 m step law and its re-solve passes), 06n's
station-joined partition (`planar/terraces.py`) and 07g's serving-contact
territories (`planar/territories.py`, `pipeline/territory.py`, the
fallback links — measured never fired: `territories.links == []` in the
latest HECA / CYXY / LEMD / SPJC / OTHH reports).  What replaces them:

* A SHAPE is a connected component of touching / overlapping pavement
  (`planar/shapes.py::build_shapes`, at the planar build): the union of
  the `terrace.shape_roles` faces (runway + taxi families, apron, junction
  — a road is never a member: it is a SEPARATOR), closed by
  `terrace.separation_m` (0.5 m: pavement closer than this is one shape;
  the 04u weld already shares the vertices of gaps under its 1.0 m
  pre-snap tolerance ≈ 0.65 m post-snap, so `separation_m` governs only
  unwelded pavement between the two — reported as a deviation), and then
  OPENED by `terrace.narrow_mouth_max_m` (12 m): the bodies of one
  component are the connected parts of its erosion by half the mouth
  width; every vertex of a shape-role face takes the body nearest to it
  (a neck narrower than the mouth width, a point contact, an edge
  contact shorter than 12 m: two bodies, the boundary across the neck's
  middle); a component with one body is one shape.  A road-family face's
  vertices take the label of the nearest labelled vertex (a road between
  two shapes carries the boundary mid-road, 07g (4) unchanged); a rigid
  pad's vertices take the pad's majority label (07c (3)); a zone / open
  vertex shared with pavement carries the pavement's label, any other
  vertex none.  The runway strip keep-out (06n) welds the two bodies of
  any boundary edge inside it (union-find: transitive, a shape is an
  equivalence class).  The record: `PlanarMap.shape_of_vertex`,
  `shape_of_face` (replacing `terrace_group`), `shape_joints`
  (`ShapeJoint`, replacing `LabelJoint` / `TerraceJoint`).
* A JOINT is a boundary between two shapes and nothing else: (a) the
  label-boundary contour through every face carrying two labels (07g's
  CDT contour, unchanged construction); (b) a GAP joint — the midline
  between two shapes whose rings come within `instrument.step_contact_tol_m`
  (the step readers' own horizon; a wider gap is priced by no reader).
  Both are declared in the sidecar `terrace_joints` (v1's record shape),
  the step the built |Δz| over the joint's vertex pairs, no cap.
* INSIDE a shape no joint exists and no step is lawful: the apron
  families yield with NO ceiling (`[yield] apron_yield_max` absent →
  unbounded preference: 1 % preferred (`apron:` groups), 1.5 % the
  second tier (`yield:apron…`), steeper where the routes demand).
* The taxi CHAIN yields where it meets a runway-family vertex (08i-1
  default): the `taxi` generator's chain hops / centreline chords with an
  endpoint on a runway-family face become preferences at `taxi_yield_max`
  (family `taxi_chain_at_runway`); crossings (the runway's own cap) and
  every other chain row stay hard.
* ONE solve pass: `Config.joint_passes_max`, `weld_built_steps`,
  `terrace_welds`, `WELD_GEN`, `terrace.max_step_m`, `min_step_m`,
  `simplify_factor`, `cell_roles`, `neighbour_roles`, `joint_gap_m`,
  `complex_roles`, `route_links`, `route_link_rows` are DELETED.

| consumer (reader of groups / joints / territories / links / passes) | today | after 08k |
|---|---|---|
| `planar/build.py` (`split_terraces`, `BuildStats.terraces`) | 06n split copies at group boundaries | `build_shapes` labels vertices and faces, declares the contours + gap joints; `BuildStats.shapes` |
| `pipeline/territory.py` → `pipeline/shapes.py` (`territory_stage` / `territory_constraints` / `apply_joints` / `joint_steps`) | labels, predicate, fallback links, the filter, the yield transform, the welds | `shape_stage` (route bands + the withdraw set), `shape_constraints` (generators → filter → yield transform), `apply_joints` unchanged in kind (a row straddles ⇔ its vertices carry two shape ids), `joint_steps` over the declared joints |
| `pipeline/build.py` (`Config.joint_passes_max`, the joint step loop, the report's `territories` / `joint_steps`) | ≤ 2 re-solves on the built step | one solve; report `shapes` (count, by area, joints, gap joints) |
| `pipeline/why.py` | `territory_stage` + `territory_constraints` | `shape_stage` + `shape_constraints` (the LP `why` reads is the build's) |
| `pipeline/publication.py` (`terrace_joints_ll`, `straddles`) | 06n runs + label contours; `over_max_step` | `pm.shape_joints` (contours and gap joints, `shapes: [a, b]`, `gap: bool`); `straddles` read from `pm.shape_of_vertex` — the parameters go |
| `constraints/pads.py` (`planar.terrace_group`) | a pad never fronts across a group boundary | `planar.shape_of_face` — a pad never fronts a soft face of another shape |
| `constraints/routes.py` (`pm.route_links`, `route_link_rows`), `constraints/__init__.GENERATORS` | the fallback link rows | deleted (never fired) |
| `constraints/no_step.reach_band_values` → `REACH` bands | withdrawn for labelled non-station vertices (07g (2) measured infeasible) | withdrawn for the non-station vertices of `terrace.band_roles` faces (the same population: apron / junction / the road family inside pavement) — the kept rows carry the reach |
| `constraints/yielding.py` (`FAMILY_SELECTORS`, ceilings) | six families, every ceiling a grade | + `taxi_chain_at_runway`; a class without a `<class>_yield_max` key yields unbounded (`ceiling=None`, the groundside-ramp precedent); `yielded_rows` gains `by_shape` (max apron grade per shape) |
| `law/terrace_schema.py`, `law/yield_schema.py`, `emit.toml`, `tables.yield_ceiling` | the 06n / 07g / 08d keys | `[terrace] separation_m, narrow_mouth_max_m, shape_roles, band_roles`; `[yield] apron_yield_max` absent; `YIELD_FAMILIES` + `taxi_chain_at_runway` |
| `model/planar.py` | `TerraceJoint`, `LabelJoint`, `terrace_joints`, `terrace_group`, `route_links` | `ShapeJoint`, `shape_joints`, `shape_of_vertex`, `shape_of_face` |
| `verify/steps.py`, `verify/no_step.py`, `verify/transverse.py`, `tools/check_grade.py`, `tools/harness/census.py` | read the sidecar `terrace_joints` | unchanged (the sidecar key and record shape are the same) |
| `emit/osm_adapter.py` | lists the sidecar key | unchanged |
| `tools/v2_solve_replay.py` | `--joint-passes`, the weld loop, `--from territory` | one pass, `--from shapes`, the shapes / joints / by-shape apron grade report |
| twins `test_v2terrace.py` (06n) / `test_v2terrace3.py` (07g) / `test_v2chord.py` ×3 (the step law) | | RETIRED (the mechanisms are deleted; the `why` KML twin moves to `test_why.py`); `test_v2shapes.py` carries 08k |

## 9. Acceptance — lane `v2shapes` closing build (08k shapes + chord fit + yielding + site ramp), 2026-09-08

Build `v2shapes2` (`/tmp/harness/v2shapes2.osm`, head 775dbec4), HECA
`--engine v2`, production DEM frame N30E031, status optimal, 280.5 s.
v1 control `HECA_20260908T073420` (813 s). Base arms at the same tree:
`CYXY_20260908T175459` (artifact ledger 637ed1003b09),
`OTHH_20260908T175517` (fd55f056c716), `LEMD_20260908T180428`
(ee8adb3ec705). Instruments: `tools/rwy_profile.py --binned --compare`,
`tools/patch_proximity_diff.py`, `tools/harness/census.py --no-cache`,
the report / sidecar of the build.

| read | bar / reference | v1 control | 1.0.293 | parity before shapes (08g) | **v2shapes2** | verdict |
|---|---|---|---|---|---|---|
| 05R/23L bow (m) | v1-like | −4.25 | −9.64 | −3.25 | **−2.17** (s 2,275; z−DEM +6.26 / +1.41 / +9.11; max grade 0.80 %; K 0.46 %/100 m) | PASS |
| 05C/23C bow (m) | v1-like, owner floor 6.1 m | −9.53 | −9.20 | −6.96 | **−7.08** (s 2,525; z−DEM −0.09 / −3.75 / +2.13; max grade 1.60 % (50 m bin); K 0.52) | PASS |
| 05L/23R bow (m) | v1-like | −0.28 | −2.02 | +0.01 | **+0.01** (z−DEM +2.71 / +0.52 / +6.23; max grade 1.02 %; K 0.50) | PASS on the bow; hump at s 2,025–2,425 **+3.3 m over v1** (63.6 / 64.8 / 64.8 vs 60.8 / 61.4 / 61.5) STANDS after the chain yield (`taxi_chain_at_runway` 115 of 938 rows yielded at the 3 % ceiling) — owed |
| \|dz\| > 1 m vs v1 | ≤ 30 % | — | 57 % | 53.3 % | **55.2 %** (11,700 of 21,182) | MISSED |
| \|dz\| > 6 m vs v1 | ≤ 200 | — | 917 | 250 | **328** | MISSED — the SW strip fill class (sites 1–4, 6, 9, 15, 16: v1 +3–5 m above the DEM, v2 ±0.3; 08i-refuted, needs the fill-only envelope) plus the NEW pav132 class: sites 5, 7, 8, 10 (30.1268,31.4170 / 30.1214,31.4171 / 30.1266,31.4149 / 30.1287,31.4150) where v2 is **+5.7 to +7.3 m above v1** — v1 cut pav132 7–10 m below the DEM, v2's single shape grades through at −4.3 / −0.1 / −3.2 / −0.8 z−DEM |
| z_v2 − z_v1 by role (mean / p10 / p90) | — | | | | runway +1.40 / −0.44 / +4.17; stub +0.56; primary_parallel +0.65; secondary_parallel −1.87; cross_connector −0.79; junction +0.22; apron +0.28 / −2.97 / +5.44; service_road −1.15; graded_strip −0.49; ALL +0.07 / −2.76 / +2.41 | |
| owner's site 30.1139552,31.4095465 | 0 pairs ≤ 3 m with \|dz\| > 2 m within 60 m | 2 (3.30, 3.49 m) | 6.2 m joint | 0 | **0** — 8 nodes (service_road 3, service_junction 5, apron 2), z 98.86–101.93, max step over any pair ≤ 3 m **0.03 m**, plane grade 5.73 % (the 5 % groundside ramp + apron yield), max pair grade 1.31 % | PASS |
| the neck 30.127729,31.412022 | continuous | continuous (1.19 %) | — | — | **continuous**: 9 nodes (junction 3, apron 7, building 3), z 78.95–80.06, max step 0.00 m, plane grade **2.97 %** toward 198° (08k predicted ≈ 3.1 %); steepest 3–30 m pair 6.46 % over 5.6 m (a junction/apron edge beside a pad) | PASS |
| shapes | 08k | — | — | 06n groups | **1 shape** (354 faces, 4,120,129 m², 11,451 vertices; roles apron, cross_connector, junction, primary_parallel, runway, secondary_parallel, stub) | as ruled: all HECA pavement touches |
| joints | only at physical separations; `terrace_joint_route` = 0 | 0 | 73 (8 > 2 m) | 42 (≤ 2 m) | **0** contour joints, **0** gap joints, sidecar `terrace_joints` = 0; `terrace_joint_route` 0 / `terrace_joint_strip` 0 / `terrace_actual_step` 0 | PASS (vacuous) |
| hangar island #363 | 08k: separate only across a gap > 0.5 m or a road | — | — | separate cell, 1,193 m | face 363 (pav132, junction, code E) is **inside shape 0** — no gap, no road: it grades with the shape | as ruled |
| max apron grade inside the pav132 shape | no ceiling inside a shape (08k (3)) | — | — | — | **13.3 %** (face 336, pav132 apron, at 30.12183,31.41421 over a 1.0 m row; 675 of 5,828 rows over the 1 % preference); face 193 (pav131) 8.4 %; `yielded_rows.by_shape[0]` max 0.1331 | reported |
| `yielded_rows` per family | — | — | — | 3,797 | **4,008 of 236,224**: apron 1,043 / 27,451 (max 13.3 %, max over 4.86 m); apron_edge_portion 38 / 3,919 (8 %); junction_mesh 654 / 11,807 (3 %); no_step_pairs 400 / 88,873 (3 %); roads 381 / 74,855 (8 %); taxi_box 1,377 / 28,366 (3 %); taxi_chain_at_runway 115 / 938 (3 %); groundside_ramp 0 / 15 | |
| v2 verify rows | — | — | — | 27 | **51** = within_shape 25 (all stub\|stub, 1.54–1.56 % over 354–414 m of route, 5.5–6.4 m, one cluster at 30.1137,31.4154) + lateral_contiguity 26 (groundside service_road\|service_road, 0.065 m, the 8 % road profile against the 1.5 % strictest class; rows carry no lat/lon — instrument gap) | |
| oracle census, adjudicated (yielded stamped apart) | — | 1,065 airside | 8 | 42 | **35** airside (within_shape 30,384 of which 29,878 withdrawn-law chords and 1,329 `yielded_by_08d`; airside_no_step 296; taxi_box 551; vertex_to_edge_step 1 (0.95 m); road_cross_section 10 groundside) | FAIL by the letter (35 > 0) |
| oracle census, law-true | v1's reading | 1,065 + 1,741 gs | — | — | LAW-TRUE TOTAL 31,242 (within 31,241, steps 1); minus the withdrawn taxi chords = **1,364** (35 adjudicated + 1,329 yielded) | |
| solve wall | 47 s (1.0.293); 357 s (two joint passes) | — | 47 | 248 + 172 + 177 | **152.3 s, ONE pass** (HiGHS optimal, 113,438 iterations; LP 325,594 columns, 697,205 + 6,479 rows, 2.06 M nnz; 275,698 preference groups, 11,311 yielded) | ×3.2 vs 1.0.293 — the build-time law (owner 08g-1) |
| CYXY base arm | verify 0 (main) | | | 7 (08g) | **4** within_shape: primary_parallel 1.55 / 1.72 / 1.57 % over 111–123 m at 60.7121,−135.0708 (×3), stub 1.54 % over 205 m at 60.7017,−135.0592; 11 joints, max step 0.79 m (cross_connector/service_road contour); 7.7 s | +4 |
| OTHH base arm | verify 0 (main) | | | 0 | **1** structure_rim_gap = the 08j 0.0004 m door-ramp rim residual (stamped out of scope, under materiality) → effectively 0; hard set INFEASIBLE, 04t-1 relaxed 12 door-ramp descent rows by 0.0007–0.0015 (8.07–8.15 % vs 8 %, certificate OK) — the same Parking-Right door 08j reported; 68 joints max step 0.00 m; 492.7 s (door wells 58 s, verify 111 s) | 0 |
| LEMD base arm | 16 + the owed 4 transverse (main) | | | 19 | **11**: taxi_box 1 (1.90 % vs 1.79 cap over 30 m at 40.4740,−3.5680), strip_seam_tear 3 (1.59–1.92 m over 3 m), vertex_to_edge_step 1 (0.61 m parking_lot), tunnel_mouth_canonical 6 (site notes, stamped); **transverse 0** (the owed 4 gone); hard set feasible; 231 s | −5 (−9 against the owed) |

Reads not made: SPJC (`ColdDemFrame S12W078`, corpus refresh pending),
the five-airport sweep (orchestrator), the sim read. Owed: the 05L/23R
hump (+3.3 m over v1 after the chain yield — a `why` on the ridge with
the chain already soft), the divergence bars (SW fill envelope 08i;
the pav132 grade-through class is 08k's own consequence, +5.7–7.3 m
over v1's cut), the 25 stub\|stub rows at 1.54–1.56 % (0.04–0.06 pp
over cap, above the 0.01 pp materiality floor), the 26 groundside
lateral_contiguity rows without lat/lon, the OTHH hard-set
infeasibility at the 08j door (12 rows, ≤ 0.0015 excess).

Build-time statement (HECA, from `.result.json`, one run — not a timing
measurement): load 3.6 s, classify 2.1, planar 48.5, flat_site 0.1,
road_profile 0.6, shapes 0.2, constraints 28.1, solve 152.3, emit 1.6,
rebake_plan 22.3, verify 17.2, v2 total 276.5, harness wall 280.5 s.
Solve 152 s in one pass vs 47 s on 1.0.293 (×3.2) and 357 s with the
deleted joint passes; the ≥ 1 % regression on the auto-patch budget
stands under the owner's 08g-1 decision.
