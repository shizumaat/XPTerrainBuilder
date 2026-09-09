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

## 10. SHAPES = APRON BODIES (owner RULINGS 2026-09-08p) — consumer census, written by lane `v2shapes` round 2 BEFORE editing (owner 30l)

08p amends 08k's membership: the taxiway NETWORK is never part of a
shape.  THE PREDICATE (`planar/shapes.py::network_faces`): a face is
NETWORK iff (a) its role is of the runway family, or (b) a taxi-centreline
breakline edge (`STATION_KIND`, the 1202 network) whose two endpoints are
RUNWAY-CONNECTED lies on it (the edge's left or right face — a centreline
along a face boundary makes both faces network).  Runway-connected: the
vertex lies in a connected component of the taxi-centreline breakline
graph that contains a vertex incident to a runway-family face or on a
runway ridge breakline (`RIDGE_KIND`) — the planar reading of
`constraints.routes.reach` from the thresholds (the route graph's
CENTRELINE / CROSSING walk from the runway; the planar layer may not
import `constraints`, so the predicate is the breakline graph's own and
the replay cross-checks it against `reach` at HECA — DEVIATION reported).
A centreline no runway reaches (an apron taxilane, a disconnected
fragment) is part of the body it lies in — the 05w "junction" hangar
aprons no route crosses are bodies.  THE NETWORK VERTICES `N` = every
vertex incident to a network face; they carry `NO_SHAPE` always: an
apron body's ring along the network is WELDED (08p (3): its rows to the
body's interior are never dropped, no contour is drawn there, no gap
joint faces the network).

| consumer | today (08k, round 1) | after 08p |
|---|---|---|
| `planar/shapes.py::_label_pavement` | the union of every `shape_roles` face | the union of the `shape_roles` faces NOT network (+ rigid pads, 03h) → components → bodies; a vertex in `N` is never labelled; a body face all of whose vertices are in `N` (a sliver between two taxiways) is welded whole (`faces_unlabelled`) |
| `_label_others` (roads by nearest label, pads by majority) | every road / pad vertex | skips `N` |
| `_weld_strip` | strip keep-out welds; a boundary edge on ANY taxi centreline welds | unchanged in code: a connected centreline's vertices are in `N` (never a boundary), an unconnected one's still weld their bodies (07g: the route is never cut) |
| `_contour_joints` | faces with two labels | unchanged: a network face has no labelled vertex; a road between two bodies still carries the contour mid-road (08k separator) |
| `_gap_joints` | ring edges of `shape_roles` faces | body faces only (a network ring edge has no label anyway) — never between a shape and the network |
| `build_shapes` record (`shape_of_face`, `by_shape`, stats) | every shape-role face has a shape | a network face has NO `shape_of_face` entry; `ShapeStats` gains `network_faces`, `network_by_role`, `network_vertices`, `body_faces`, `faces_unlabelled`, `connected_stations`, `unconnected_station_edges` |
| `pipeline/shapes.py::shape_stage` withdraw set | labelled non-station vertices of `band_roles` faces | non-station vertices of `band_roles` faces (the label condition dropped: the same population — a network junction's vertices lost the band in round 1 too, as labelled) |
| `apply_joints` (the filter) | rows carrying two shapes dropped | unchanged: `N` never straddles, so a body's rows to the network survive (the weld); rows between two bodies across the network are dropped (they connect by ROUTE: the network's hard chain + the body's hop rows) — counted per generator as today |
| `constraints/yielding.py::yield_rows` | every family row yields | a TAXI-class row (`junction_mesh`, `taxi_box`, `no_step_pairs`) whose vertices ALL lie in `N` STAYS HARD — "the network hard at its route law" (08p (2)); `taxi_chain_at_runway` keeps yielding (08i-1); the apron and road classes yield whatever their endpoints touch (measured on the twin: an apron frontage chord between two contacts on the network spans the BODY — held hard it made the pinned two-contact solve INFEASIBLE); `YieldStats.network_hard` per family; `yielded_rows.by_shape` reads the LABELLED end of a row |
| `constraints/pads.py` (`shape_of_face`) | a pad never fronts a soft face of another shape | a network face has no entry → a pad may front it (welded pavement) |
| `pipeline/publication.py`, `verify/*`, `check_grade.py`, `census.py` | read `shape_of_vertex` / the sidecar `terrace_joints` | unchanged (`terrace_joint_route` reads 0 by construction: no joint touches a connected centreline) |
| `pipeline/build.py`, `tools/v2_solve_replay.py` | the 08k log line / report | + network faces / bodies / shapes counts; the replay cross-checks the predicate against `routes.reach` |
| `emit.toml [terrace]`, `terrace_schema.py` | `shape_roles` = runway + taxi + apron roles | unchanged keys (the network is a predicate, not a role list: a stub no route reaches is a body) — the comment amended |
| twins `tests/auto_patch_v2/test_v2shapes.py` | 08k | + 08p: two aprons through a taxiway → two shapes, no joint, the taxiway's rows intact; apron against a taxiway → welded; 0.3 m → one shape; a wider gap → joint (the 04u weld deviation stands: 0.6 m is welded, the twin reads 1.2 m under a 2 m horizon); a hangar junction with no route → body; an unconnected taxilane → body; twin 1's count reads 1 shape (the runway is network) |

### 10.1 Round 3 — owner RULINGS 2026-09-08r (08r-1 the runway-contact chain has NO ceiling; 08r-2 a road between two shapes belongs to NEITHER) — consumer census, written by lane `v2shapes` round 3 BEFORE editing

| consumer | round 2 | after 08r |
|---|---|---|
| `law/yield_schema.py`, `emit.toml [yield]` | `taxi_chain_at_runway = "taxi"` (ceiling `taxi_yield_max` 3 %); `network_hard_classes = ["taxi"]` the round-2 experiment knob | the family moves to its own class `runway_contact`, which states NO `<class>_yield_max` (the table's existing rule: an absent key yields unbounded) — `check_yield` REFUSES a stated `runway_contact_yield_max` (08r-1: no ceiling at a runway contact); the knob is DELETED from the schema and the table (arm B refuted; arm A is the mechanism) |
| `constraints/yielding.py::yield_rows` | rows of the classes the knob names, wholly on `N`, stay hard | `NETWORK_HARD_CLASSES = {"taxi"}` in code (the network's own surface law; the apron / road classes span the body and yield whatever their endpoints touch — the round-2 measurement, deviation (3)); `taxi_chain_at_runway` yields unbounded everywhere it is selected (the runway contact) — the ceiling stays on `junction_mesh`, `taxi_box`, `no_step_pairs` (3 %) and `roads` (8 %) |
| `yielded_rows` (report + sidecar) | per family / per shape | + `runway_contacts`: per runway-family CONTACT VERTEX of the chain rows (the endpoint on a runway face) — its ll, the taxi face/ref, rows, yielded, the max built grade; the build log prints the steepest contacts |
| `planar/shapes.py::_label_others` (roads) | every road vertex not yet labelled takes the NEAREST labelled vertex's shape → a road between two shapes carries the contour MID-ROAD (08k literal: HECA route8 8.8 m wall ACROSS the road, 9,580 road rows dropped) | `_label_roads`: per road-family face, its CONTACTS = its vertices the pavement labelling already labelled (shared with a body's face). ONE contact shape (or none: the nearest labelled vertex's shape by majority) → ALONG: every vertex of the road takes that shape, the ones shared with another body included. TWO or more → the two most-shared shapes A (more shared vertices) and B, their contact vertices projected on the road's long axis (`constraints.geometry.long_axis`): projection intervals that OVERLAP → ALONG the boundary: every vertex takes A (the step then stands at the road's FAR edge: B's faces along it carry two labels and the contour hugs their edge inside B); DISJOINT intervals → CROSSING: every vertex of the road is UNLABELLED (a `RoadRamp` record on the map: face, ref, shapes, the contact vertices of each side, the axis length between the contact centroids) — the road's rows all survive the filter (no vertex straddles), it ramps along its length at its own row law (the `roads` yield ceiling = the core clamp 8 %), no contour crosses it, the two shapes step elsewhere. A vertex in `N` is never labelled, as before |
| `model/planar.py::PlanarMap` | `shape_of_vertex`, `shape_of_face`, `shape_joints` | + `road_ramps: tuple[RoadRamp, ...]` (the crossing roads) |
| `_contour_joints`, `_gap_joints`, `joint_planar_edges` | a road face with two labels carries a contour | unchanged in code: no road face carries two labels now (an along road is one label, a crossing road none); the contour of an along road stands in the OTHER shape's faces at the road edge |
| `pipeline/shapes.py::apply_joints` | 9,580 road rows straddled at HECA | unchanged: a crossing road's rows never straddle (unlabelled ends); an along road's rows never straddle (one label); the other shape's rows from the road edge inward are the ones dropped (its contour) |
| `pipeline/shapes.py::joint_steps` | per role pair, per road face the step at a joint edge | + `ramps`: per crossing road the built |Δz| between the two contact centroids, the axis length, the grade, the road's cap; `too_short` when the built grade reaches the cap (the road is at its ceiling: the shapes conformed instead) — the build log names them |
| `constraints/pads.py` (`shape_of_face`) | a road face has an entry | a crossing road has none → a pad may front it (welded pavement, the network precedent) |
| `verify/*`, `check_grade.py` (the joint-aware allowance) | `within_shape` / `road_cross_section` already add `Σ declared step` for a pair crossing a declared joint — BOTH instruments, every role (`verify/within.py:313`, `check_grade.py:6223`) | unchanged: MEASURED on the round-2 patch (`v2shapes3`, 999 service_road rows): 16 rows cross a declared joint, 983 do NOT (median chord 232 m, 408 of them > 60 m from any joint) — the 829 were the DROPPED straddling chords of the crossing roads whose chords miss the 6 m contour across the road (a bent road's chord leaves the face; `chords_outside_face` is apron-only), not rows at road joints. Under 08r-2 no road row is dropped, the road's rows over its 1.5 % contiguity cap are published `yielded_rows` (ceiling 8 %) and both readers count them apart |
| `tools/v2_solve_replay.py` | the shapes / joints / yielded lines | + the ramps line and the runway-contact line |
| twins `tests/auto_patch_v2/test_v2shapes.py` | 08k / 08p | + 08r: an along-boundary road takes its shape's level and the step stands at its far edge (the contour inside the other apron, the road's rows intact, both censuses 0 on the road); a crossing road ramps at 8 % with no joint (unlabelled, a `RoadRamp`, `dropped.roads == 0`, the built grade ≤ 8 % + tol, no contour touches the road); the chain at the runway yields past 3 % when the runway demands (`ceiling is None`, a pinned solve grades the stub at > 3 %); the knob is gone (`Yield` has no `network_hard_classes`; `runway_contact_yield_max` stated → `LawError`) |

## 11. Acceptance — lane `v2shapes` round 2 closing build (08p apron bodies), 2026-09-08

Build `v2shapes3` (`/tmp/harness/v2shapes3.osm`, artifact ledger
15926ecf77e5), HECA `--engine v2`, production frame N30E031, status
optimal, harness wall 209.9 s.  v1 control `HECA_20260908T073420`;
round 1 = `v2shapes2` (§9).  Base arms at this tree:
`CYXY_20260908T191218` (479c70620319), `LEMD_20260908T191218`
(62b5efab491b), `OTHH_20260908T191623`.  Replay arms on the recaptured
`HECA.pkl` (this tree): **A** = the brief's literal (`[yield]
network_hard_classes = ["taxi"]`, the closing build), **B** = round 1's
yielding network (`[]`), **C1** = every taxi generator dropped (`taxi`,
`no_step`, `junction_mesh`), the hump's joint attribution.

THE PREDICATE AT HECA: 232 of 354 pavement faces are NETWORK (runway 6;
taxi family 226: cross_connector 70, junction 49, primary_parallel 35,
secondary_parallel 41, stub 31), 8,619 network vertices, 1,275
runway-connected stations, 965 centreline edges no runway reaches (part
of a body); the planar predicate and `routes.reach` from the thresholds
name the SAME 226 taxi-family faces (symmetric difference 0).  The 122
body faces (24 welded whole: every vertex on the network) form 383
components → 396 bodies → **60 shapes** (largest 637,504 m² / 13 faces,
279,133 / 7, 193,228 / 5 = pav132's shape 2); joints **26 contours, 0
gap** (56 of 63 joint edges service_road|service_road: the 08k road
separator); `terrace_joint_route` 0 / `terrace_joint_strip` 0 /
`terrace_actual_step` 0 by construction.

| read | v1 control | round 1 (§9) | **round 2 build (A)** | replay B | verdict |
|---|---|---|---|---|---|
| 05R/23L bow | −4.25 | −2.17 | **−4.95** (s 575; z−DEM +4.62 / −0.55 / +8.59; max grade 1.18 %) | −2.21 | 0.70 m DEEPER than v1 — the hard network drags the runway (08d (1)) |
| 05C/23C bow | −9.53 | −7.08 | **−9.42** (s 2,625; z−DEM −1.27 / −5.91 / +1.28; max grade 1.40 %) | −7.10 | v1-like (the owner's 6.1 m floor missed by 3.3 as v1 misses it) |
| 05L/23R bow | −0.28 | +0.01 | **+0.01**; hump s 2,025–2,425 63.7 / 64.9 / 64.9 vs v1 60.8 / 61.4 / 61.5 (**+3.4 m**, round 1 +3.3) | −0.36; hump 62.8 / 64.7 / 64.7 | the hump STANDS in both arms |
| the hump `why` (ridge v3269, s 2,303, z 65.01, chord +5.18, DEM +6.37; binding rows: `runway_vertical_curve` dual 2.2e5, `runway_profile` transverse 22) | | owed | relax-one-family re-solves over 34 ridge vertices (dz median): **taxi_chain −0.81**, strip_transverse −0.71, runway_vertical_curve −0.18, no_step_rate −0.05, junction_mesh −0.04, no_step_pairs −0.03, transverse −0.01, taxi_centreline 0.00, reach 0.00, runway_profile 0.00, zone_bands +0.05, taxi_box +0.12; **C1 (every taxi generator dropped): the runway lands ON THE CHORD (z 59.93 at s 2,423, chord +0.00, z−DEM +0.89; 05R/23L bow 0.00), −5.06 m** | | the hump is held by the taxi NETWORK JOINTLY — its redundant hard forms (chain hops/chords away from the runway, box, pairs, mesh) each cover the others, so no single family releases more than 0.8 m; the network sits on the NW high ground (DEM fit) and the runway-contact chain, yielding to a 3 % CEILING, lifts the runway to it. v1 lets the taxiways fall to the runway. Owner decision 11-1: the chain-at-runway ceiling (3 %) — raise / remove it, or accept the hump |
| \|dz\| > 1 m vs v1 | — | 55.2 % | **52.5 %** (11,119 of 21,182) | | MISSED (bar 30 %): the SW fill class (sites 1–4, 6, 8, 12: v1 +3–5 m above the DEM, v2 ±0.5) + pav132 (sites 5, 7, 9, 11: v2 **+5.2 to +7.3 m over v1**, v1 cut −7 to −10 z−DEM) |
| \|dz\| > 6 m vs v1 | — | 328 | **248** | | MISSED (bar 200) |
| owner's site 30.1139552,31.4095465 | 2 steps 3.3–3.5 m | 0 | **0** pairs ≤ 3 m with \|dz\| > 2 within 60 m: 8 nodes z 101.93–103.81, max short-pair step 0.00, plane grade 3.81 %, max pair grade 0.84 %; z−DEM mean −3.17 (v1 −1.30; v2 1.87 below v1); shape 33 | same | PASS |
| the neck 30.127729,31.412022 | continuous 1.19 % | continuous 2.97 % | **continuous**: 9 nodes z 77.96–79.12, 0 steps, plane grade 3.37 %, steepest pair 6.80 %; z−DEM −4.73 (v1 −4.26); inside shape 2 (pav132) | z−DEM −3.72 | PASS |
| pav132 sites 1–4 (30.1268,31.4170 / 30.1214,31.4171 / 30.1266,31.4149 / 30.1287,31.4150) | z−DEM −8.0 / −7.4 / −9.2 / −6.5 | +5.7–7.3 over v1 | z−DEM **−3.50 / +0.14 / −4.11 / −1.33**, vs v1 **+4.5 / +7.6 / +5.1 / +5.1**; 0 steps within 60 m at every site (site 2 is a building pad at the DEM, no shape) | −2.96 / +0.14 / −3.58 / −0.90 | the grade-through class stands: the 08p bodies do not cut as v1 did |
| max apron grade inside pav132 (shape 2) | — | 13.3 % (face 336, one 1 m row) | **13.8 %** face 336 at 30.121835,31.414211 over 1.0 m (381 of 5,794 rows over cap); shape 33 (pav131, face 193) 12.7 % over 2.2 m; rows on the network (shape −1) 16.5 % face 242 over 1.4 m at 30.131685,31.399931 | 13.3 % | attributed: the 1–2 m apron ring rows beside a pad / at the network weld carry the body's relief in ONE hop (the apron rows yield unbounded, 08k (3)); the long chords stay ≤ 5 % |
| joints / walls | 0 | 0 joints | **26 contours, max step 8.82 m**: joints 20/21/22 (shapes 0 ↔ 33, service road `route8`, 30.1155,31.4100–31.4114: 8.82 / 7.25 / 7.67 m); 6 (apron\|parking_lot 2.66 m), 12 (2.51), 25 (2.13), 17 (2.08); 19 under 2 m | 9.02 m | 08k's road separator at HECA: a service road between pav131's shape and the main shape carries an 8.8 m WALL ACROSS THE ROAD (road rows dropped at the joint: 9,580 road rows straddle). Owner decision 11-2: does a road between two shapes STEP (08k literal) or RAMP through at its 8 % law? |
| `yielded_rows` | — | 4,008 / 236,224 | **1,594 / 117,344**: apron 969 / 27,395 (max 16.4 %), apron_edge_portion 29 / 3,689 (5.0 %), junction_mesh 29 / 2,019 (3 %), no_step_pairs 211 / 13,762 (3 %), roads 155 / 66,425 (8 %), taxi_box 136 / 3,101 (3 %), taxi_chain_at_runway 63 / 938 (1.72 %), groundside_ramp 2 / 15 (33.9 % over a 1.0 m row, face 54 at 30.108465,31.399576 — owed); network-hard: no_step_pairs 75,111, taxi_box 25,265, junction_mesh 9,788 rows stay hard | 4,000-class | |
| v2 verify rows | — | 51 | **829 = service_road\|service_road 829** (within_shape 449 at 1.5–22.7 %, road_cross_section 348 at up to 28.2 %, transverse 6, lateral_contiguity 26): the roads cut at the 26 joints; airside 0 (the round-1 stub\|stub 25 read yielded / withdrawn now) | | the v2 verify does not honour a ROAD joint (instrument gap, owed) |
| oracle census, adjudicated | 1,065 airside | 35 | **67** (airside 57 = stub\|stub 1.51–1.55 % over 26 m at 30.1070,31.4178 + kin; groundside 10) | | FAIL by the letter |
| oracle census, law-true | 1,065 + 1,741 gs | 1,364 (net of withdrawn) | LAW-TRUE TOTAL 28,051 − withdrawn taxi chords 27,427 = **624** (67 adjudicated + 557 `yielded_by_08d`) | | |
| solve wall | 47 s (1.0.293) | 152.3 s | **82.3 s, ONE pass** (LP 206,428 columns, 676,643 + 6,479 rows, 1.78 M nnz) | 127.7 s (replay) | ×1.75 vs 1.0.293, −70 s vs round 1 (the hard network is 110,164 fewer preference groups) |
| CYXY base arm | 0 (main) | 4 | **45** = service_road\|service_road 38 (1.55–1.77 % over 85 m at the 6 road joints, max joint step 1.07 m) + primary_parallel 3 + stub 4 (round 1's class); 6 shapes, 63 of 76 faces network; 7.4 s | | +41, all the road-joint class |
| OTHH base arm | 0 | 1 | **1** (the 08j 0.0004 m rim residual, hard set INFEASIBLE at the door as in round 1, 12 rows ≤ 0.0015); 101 shapes, 95 contours, max step 0.00 m; 492.7 s | | 0 |
| LEMD base arm | 16 | 11 | **12** (taxi_box 2, strip_seam_tear 3, vertex_to_edge_step 1, tunnel_mouth_canonical 6); 53 shapes, 8 contours max 0.86 m; 230.6 s | | +1 (one taxi_box) |

Reads not made: SPJC (`ColdDemFrame S12W078`, corpus refresh pending),
the five-airport sweep (orchestrator), the sim read.  DEVIATIONS reported
(not decided): (1) the predicate is the planar breakline graph from the
runway roots, not `routes.reach` from the pins (the dependency law;
cross-checked equal at HECA); (2) the network is the TAXI FAMILY + runway
faces only — an apron a 1202 taxilane runs onto stays a body (the twin
`two_contacts` reads network aprons otherwise: every apron with a dangling
route would harden); (3) only the TAXI class is held hard on the network
(`network_hard_classes`): an apron frontage chord between two contacts
on the network spans the body — held hard it made the pinned twin
INFEASIBLE; (4) the brief's "0.6 m → joint" twin stands at 1.2 m under a
2 m horizon (the 04u weld shares vertices under ≈ 1 m, round 1's
deviation); (5) `network_hard_classes` is the round's experiment knob
(arm A vs B) awaiting the spawner's ruling — the closing build is A.
OWED: the hump (owner 11-1), the road-joint walls (owner 11-2), the v2
verify's road-joint reading, the 33.9 % groundside ramp row, the
divergence bars (the SW fill envelope 08i + pav132), SPJC.

Build-time statement (HECA `v2shapes3`, one run, `report.wall_s` — not a
timing measurement): load 3.6 s, classify 2.0, planar 46.4, flat_site 0.1,
road_profile 0.6, shapes 0.2, constraints 27.4, solve 82.3, emit 2.0,
rebake_plan 21.2, verify 19.8, v2 total 205.6, harness wall 209.9 s
(round 1 280.5 s; 1.0.293 193 s).  The network predicate costs < 0.1 s
inside `shapes` (0.23 s total).  Solve 82 s in one pass vs 47 s on 1.0.293
(×1.75): the ≥ 1 % regression on the auto-patch budget stands under the
owner's 08g-1 decision, 70 s better than round 1.

## 12. Acceptance — lane `v2shapes` round 3 closing build (owner RULINGS 2026-09-08r), 2026-09-08

Build `v2shapes4` (`/tmp/harness/v2shapes4.osm`, artifact ledger
`5006181d2c06`, `code_tree_hash` `629084e27335`, harness wall 218.9 s),
against the v1 control `/tmp/harness/HECA_20260908T073420.osm` and round
2's `v2shapes3`.  The shape partition is unchanged (60 shapes over 2,351
vertices); what changed is the ROADS: 45 road faces run ALONG a shape (320
vertices labelled, 0 relabelled), 22 CROSS between two shapes (74 vertices
freed) → **8 ramps**, and the joints fall from **26 contours to 7** — no
joint edge is a road pair any more (apron|apron 2, apron|graded_strip 4,
parking_lot|parking_lot 1).

| read | v1 control | round 2 | **round 3 (08r)** | verdict |
|---|---|---|---|---|
| 05R/23L bow | −4.25 | −4.95 | **−4.95** (s 575; z−DEM +4.62 / −0.55 / +8.59; max grade 1.18 %) | unchanged by 08r |
| 05C/23C bow | −9.53 | −9.42 | **−9.42** (s 2,625; z−DEM −1.28 / −5.91 / +1.28) | unchanged |
| 05L/23R bow | −0.28 | +0.01 | **+0.01** | unchanged |
| the 05L/23R hump | 60.8 / 61.4 / 61.5 at s 2,025 / 2,225 / 2,425 | 63.7 / 64.9 / 64.9 (+3.4) | **64.0 / 65.2 / 65.2 = +3.2 / +3.8 / +3.7 over v1** (round 2 63.7 / 64.9 / 64.9 = +2.9 / +3.5 / +3.4): **0.3 m HIGHER than round 2, not lower** | **08r-1 DID NOT MOVE THE HUMP.** The contact chain's max yielded grade is **1.72 %** — the 3 % ceiling was never binding, so removing it is a no-op. MEASURED: widening the contact family to every taxi-class row touching a runway vertex moved the ridge 0.06 m (contacts to 4.9 % over sub-metre hops, bows −2.98 / −8.18); the contact is held one station in by the `no_step` §1.1 route pairs and the §1.2 RATE law, neither a yield family (twin `…_no_ceiling_and_what_holds_the_contact` pins this: a 3 % first hop is INFEASIBLE in the hard set). The widening was deleted. Owner 11-1 stands: the hump needs the §1.2 rate law, not a yield ceiling |
| joints / walls | 0 | 26 contours, **max step 8.82 m** (route8, a wall ACROSS the road) | **7 contours, max step 2.66 m** (joint 1, 89.7 m, shapes 1 ↔ 4, apron\|parking_lot, at 30.1216,31.4069); then 2.13 (apron\|apron), 1.65, 0.85, 0.58, 0.26, 0.24. Zero road step rows (`joint_steps.roads == []`) | **route8's 8.8 m wall is GONE** |
| road ramps (08r-2) | — | — | **8 crossings, none at the cap**: #233 route8 4.92 m over 194 m = **2.54 %**, #181 route8 7.49 / 432 m = 1.73 %, #202 route8 7.67 / 469 = 1.64 %, #202 7.89 / 515 = 1.53 %, #176 6.67 / 601 = 1.11 %, #72 route2 0.89 / 378 = 0.23 %, #145/#144 route5 ≈ 0.02 m | the 8.8 m wall became a 2.5 % ramp, under the 8 % road cap |
| `runway_contacts` (08r-1) | — | — | **343 contacts, 15 yielded, max 1.72 %** at v3664 face 44 (30.133291,31.398887); then 1.68 % v420 face 7, 1.63 %, 1.61 %, 1.59 %, 1.59 % | reported per contact, as ruled |
| v2 verify rows | — | **829** (within_shape 449, road_cross_section 348, transverse 6, lateral_contiguity 26) — all service_road | **26 = lateral_contiguity 26** (within_shape 0, road_cross_section 0, transverse 0) | **the 829 road rows are gone.** Not by a new allowance: the joint-step allowance in BOTH instruments (`verify/within.py:313`, `check_grade.py:6218`) is already role-agnostic and applies to a road pair — LEMD joint 1 (roles apron/parking_lot/service_road, step 0.86 m) reads 0 road rows. The 829 were the DROPPED straddling chords of roads cut mid-road by 08k's literal; under 08r-2 no road row is dropped |
| oracle census, adjudicated | 1,065 airside | 67 (apron\|apron 56, service_road 10, pad 1) | **41** (within_shape apron\|apron **40**, vertex_to_edge_step apron\|building 1; worst 7.86 m at 5.39 %/5.0 % @30.12772,31.41241) | **all 10 service_road rows gone**; the apron class −16 |
| oracle census, law-true | — | 624 | **LAW-TRUE TOTAL 27,858 − withdrawn taxi chords 27,269 = 589** (41 adjudicated + 548 `yielded_by_08d`) | −35 |
| `yielded_rows` | — | 1,594 / 117,344 | **1,871 / 125,412**: apron 968 / 27,395 (max 16.68 %, max over 5.66 m), apron_edge_portion 31 / 3,689 (8 %), groundside_ramp 3 / 15 (33.94 %), junction_mesh 34 / 2,019 (3 %), no_step_pairs 213 / 13,762 (3 %), roads **416 / 74,493** (8 %), taxi_box 142 / 3,101 (3 %), taxi_chain_at_runway 64 / 938 (**1.72 %, no ceiling**) | the roads' rows are kept and priced instead of dropped |
| owner's site 30.1139552,31.4095465 | — | 0 steps | **0 census rows of any family within 60 m** (adjudicated, yielded or withdrawn) | PASS |
| the neck 30.127729,31.412022 | continuous 1.19 % | continuous, 0 steps, steepest pair 6.80 % | **32 rows within 60 m: 27 `yielded_by_08d` + 5 adjudicated apron\|apron (worst 7.86 m, 5.39 % vs a 5.0 % cap, 6.78 % worst grade)** — the SAME 5 rows round 2 carried (`v2shapes3` re-censused: 56 apron\|apron adjudicated, the identical worst three rows) | no regression; the neck's apron relief is the residual |
| divergence vs v1 | — | 52.5 % over 1 m, 248 over 6 m | **52.2 %** (bands <0.5 6,309 / 0.5–1 3,799 / 1–3 7,714 / 3–6 3,134 / >6 **226**) | both bars still MISSED (30 % / 200); the class is unchanged (SW fill + pav132) |
| solve wall | 47 s (1.0.293) | 82.3 s, one pass | **91.3 s, ONE pass** (LP 214,496 columns, 695,313 + 6,479 rows, 1.83 M nnz) | +9 s: the crossing roads' rows are no longer dropped (74,493 road rows vs 66,425) |
| CYXY base arm | 0 (main) | **45** (service_road\|service_road 38 at 6 road joints + primary_parallel 3 + stub 4) | **0 — PASS** (law-true 800, adjudicated 0); 6 shapes, 13 road faces along / 13 crossing → 0 ramps (both ends in one shape), **0 joints**; 7.6 s | **the 38 road-joint rows are gone, and so are the other 7** |
| OTHH base arm | 0 | 1 | **1** (`structure_rim_gap`, the 08j 0.0004 m rim residual); 101 shapes, 95 contours, max step **0.00 m**, 0 ramps; 518.4 s | unchanged |
| LEMD base arm | 16 | 12 | **12** (taxi_box 2, strip_seam_tear 3, vertex_to_edge_step 1, tunnel_mouth_canonical 6); 53 shapes, 6 contours max 0.86 m, 1 ramp (#101 pav145 0.07 m over 63 m); 242.4 s | unchanged |

**The 33.9 % `groundside_ramp` row (face 54, 30.108465,31.399576 —
attributed, NOT fixed).** ONE LINE: the row pairs an apron ring vertex
with the nearest groundside-pavement vertex across the stand-off, and that
stand-off is **1.0 m** — at `groundside_ramp_max` 5 % a 1 m gap buys 5 cm,
so the 0.339 m by which the apron edge and the DEM-fit groundside actually
differ reads as 33.9 %.  It is structural, not local: the generator's
horizon is `groundside_cutback_m 0.6 + weld_spacing_m 1.0 + snap margin
≈ 1.95 m`, so EVERY one of the 15 rows spans ≤ 2 m and the 5 % GRADE can
never buy more than ≈ 10 cm — the "ramp" has no ramp length.  The other
two over-cap rows are 7.1 % over 1.5 m and 7.0 % over 0.5 m; the remaining
12 agree within 5 cm.  No fix made: the row is a preference with NO
ceiling by law and both censuses count it apart (`yielded_by_08d`), so
nothing is violated — what to do about it is an INTENT question for the
owner (should the allowance across a ≤ 2 m stand-off be a STEP the
groundside may take, `groundside_ramp_max × <a ramp length>`, rather than
a grade over the cutback?), not a mechanism defect.  A 20-line change
cannot answer it.

DEVIATIONS reported (not decided): (1) **the brief's "extend the
joint-aware allowance to road pairs" was NOT written** — measured
unnecessary: the allowance is already role-agnostic in both instruments
and the 829 rows were dropped chords, not joint rows; round 3 reads 0 road
rows in v2 verify and 0 in the oracle without touching either.  (2) The
contact family stays the ruling's literal (the chain's hops/chords with an
endpoint on a runway face); the measured widening to every taxi-class row
at a runway vertex was deleted (it bought 0.06 m and cost the bows).
(3) Round 2's deviations (1)–(4) stand; (5) is discharged —
`network_hard_classes` is deleted, arm A is the mechanism, and
`NETWORK_HARD_CLASSES = {"taxi"}` now lives in code.
OWED: the hump (owner 11-1, now attributed to the §1.2 rate law), the
33.9 % ramp row (owner intent, above), the divergence bars, SPJC, the sim
read.

Build-time statement (HECA `v2shapes4`, ONE run, `report.wall_s` — not a
timing measurement, single runs swing ±25 %): load 3.6 s, classify 2.0,
planar 46.7, flat_site 0.1, road_profile 0.6, shapes 0.2, constraints
27.4, solve 91.3, emit 2.1, rebake_plan 21.4, verify 19.2, v2 total 214.6,
harness wall 218.9 s (round 2 209.9 s).  Base arms: CYXY 7.6 s, LEMD
242.4 s, OTHH 518.4 s.
