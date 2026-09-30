# FLAT PAD v2 — THE RUNWAY IS FIXED BEFORE THE AIRSIDE SOLVES, THE PAD'S DATUM IS CERTIFIED BY A PAIR-GRAPH INTERVAL, THE STAND ZONE IS A PLATEAU, AND THE CAPS THAT CARRY THE RELIEF ARE HARD ON THE FRONTING SET

Fable 2026-09-30. Issue **#128** (blocker). Owner law: RULINGS **30y** (+ addendum: a flat plateau across the stand/jetway zone, the grade change pushed into the taxi lanes within caps), **30z (3)** (straight chords welded to the pad and to the taxiway, slope minimised, twist allowed), **30z (4)** (T2 = ONE flat pad under the hard hold; seat numbers re-read before any further T2 decision), **30f**, **30aa** (a road never moves an airside column — the same class). Measured basis **30ae** (branch `claude/hardhold128` f3b19a20, frames `/Users/noah/XPTerrainBuilderData/.harness/frames/hardhold128/`). Supersedes `flat-pad-apron-spec.md` §1 (2)/(4), §2 (1), §3 C13/C21 and its §4 bar; the rest stands. **NOT implemented here** (§8 is the lane brief).

## §0 THE MEASURED FACTS THIS SPEC DESIGNS AGAINST (30ae; verified against `hardhold128_SPJC.osm.axes.json`)

| # | fact | number |
|---|---|---|
| 1 | The hard hold works AT the pads | SPJC b5 site contact +0.46 → 0.00 (datum 19.096), low end −1.38 → 0.00 (17.857); feet 634/985 → 860/1096; building13 38/38 held; HECA T3 site 15/89 → 25/89 |
| 2 | The runway moved | HECA 191 movers, worst **1.20 m** at 30.13117487837, 31.39605456510; KCLT 15, worst 0.05 m; chain `cross_connector#81/runway#73` → `runway_profile` → `runway_crown` → vertical curve, 110 hops to the 23R pin. Between pins the runway is held only by the PRICED chord (`emit.toml:339` `chord = 300`, priced at `solve/design.py:389-393`); its hard rows (`emit.toml:792-805`: transverse, K, longitudinal, end zone) are RELATIVE, so the profile translates for 300/station |
| 3 | The soft caps were spent | +880 HECA / +294 KCLT / +153 SPJC adjudicated rows (within_shape, airside_no_step, transverse, taxi_box); HECA CRITICAL motion 18 → 26. Every 1.5 % cap is priced at `law = 300` (`emit.toml:367`); only 5 % / 8 % are hard (`:796-797`) |
| 4 | The route-metric band certifies nothing | SPJC `building5/b0` `reach_band` [−29.475, 62.691] (92.2 m wide), `b1` [−22.159, 55.376] (77.5 m), `building13` [14.74, 32.503] (17.8 m), `building20` [10.182, 30.318]; **`b2`, `building31`, `building34`: `reach_band: None`** — 3 of 8 held blocks had NO interval (`band_roles` strips apron vertices of their hop band, `emit.toml:263`; `reach` returns graph vertices only, `routes.py:902`). HECA T2 EMPTY (66.909; 45 held / 18 residual; datum 69.83 → 66.91) |
| 5 | The plateau is inexpressible | SPJC b5 jetway strip: 174 vertices = 159 contacts + 13 ramp + 2 interior — pad edge to taxi lane is ONE triangle span |
| 6 | CYXY never runs the hold | building9 4,455 m² at 60.714245, −135.076351 (ring relief 0.78 m), building7 1,649 m² at 60.708614, −135.072644 (0.47 m): §20 pads — a platform is minted only for a UNIT pad ≥ `cluster_pad_min_m2` (`structures.toml:499`); a §20 pad follows its apron one-way (`emit.toml:920-921`) and tilts ≤ 1 % (`emit.toml:80`); the owner read that tilt as the same defect (30y) |

## §1 THE RUNWAY IS FIXED — STAGE 0

**Rule.** The runway family (`precedence.toml:35-36`, `role_family == "runway"`) is solved ALONE first — **stage 0** — from every row whose every column is a runway-family column: threshold / apt.dat pins (`constraints/runway_profile.py:239`, `:152`), the chord target at 300 (`design.py:389-393`), longitudinal / end-zone (`runway_profile.py:264`), crown (`:425`), transverse (`:468`), vertical curve K (`:545`), within-shape ring chords (`:589`), crossing knots (`runway_chord.py:617`), seam pins (`constraints/seams.py:62`), EAT pins on runway vertices (`constraints/eat.py:254`). Stage 0's solved values are then substituted as CONSTANTS for stage 1 exactly as a `Pin` is today (`solve/design.py:190-195`: "a vertex already FIXED … is never foreign; the rows footed on it belong to stage 1"). Site: `solve/design.py:841-848` — one more `_solve_stage` call with `stage_roles = runway family`, its `levels` merged into stage 1's `fixed`. No lag, no one-way row, no re-solve of a built step (08k (4) is kept: the stages are the §20b architecture, not passes over a built surface).

**Why not the alternatives.** (a) A hard chord: measured mutually unsatisfiable against crossings and ring chords (CYXY 127/1432 ring chords missed by 0.77 m, `emit.toml` note beside `hard_weight`). (b) One-way pad/hold rows: the hold row never touches a runway column — the runway moved through the TAXI chain (fact 2); making every taxi↔runway row one-way is the lag, and "a LAGGED row is not a fixed value" (§20b preamble; the lag does not contract at LEMD, `emit.toml` §20a note). Stage 0 is 30aa rule 1 generalised: **no row minted by anything but the runway ever moves a runway column**, by construction.

**Consequences.** Stage-1 unknowns drop by the runway-family column count (HECA: the lane quotes it against 19,446 / 123,289, 30aa). A taxi row footed on a fixed runway vertex can be VIOLATED where reality is steeper than the taxi table (KASE, Q-133, 30ad) — priced and adjudicated, never a runway move. **Gate G0** (§8 step 2): stage 0 with NO hold on the four captures vs the references (sw0929c_HECA, sw0930 SPJC/CYXY, cifp119 KCLT): runway movers at `airside_value_delta --tol 0.02` = **0**. A non-zero count means a non-runway row was pulling the reference's runway (30z (1)'s class): movers named (site, row, family), posted as an owner question, never absorbed by re-cutting the reference.

## §2 THE FEASIBILITY INTERVAL

**Definition.** For block `b` with hold set `C_b` = its held welded contacts (`constraints/platform.platform_contacts`, ramp contacts excluded, branch `frontage_hold_rows` `constraints/platform.py:492`) ∪ its plateau vertices (§3):

`I_b = ∩_{c ∈ C_b} [ max_p (z_p − B(p,c)), min_p (z_p + B(p,c)) ]`

over every FIXED airside vertex `p` (stage-0 runway values — solved, not `preferred_z`; plus every stage-1 `Pin`: EAT pins `eat.py:254`, seam pins `seams.py:62`), `B(p,c)` = the least-budget path in the **PAIR GRAPH** `G`: one edge per stage-1 `Diff` cap row between airside columns, budget `cap · d` — taxi longitudinal / transverse (`taxi.py:221`, `:263`; `transverse.py:141`), taxi_box pairs (`taxi.py:412`), apron ring-edge / frontage-chord / body chords at 1.5 % (`apron.py:214-220`), no-step pairs (`no_step.py:268`), the 5 % / 8 % ceilings (`pavement_cap.py:74`). Not the route graph: it reaches an apron contact only by a station hop and not at all on `band_roles` faces (fact 4). The pair graph is the rows themselves, so a datum inside `I_b` is EXACTLY one for which a Lipschitz extension of every pair cap exists between the fixed set and the hold set (McShane–Whitney on a metric graph). **Precondition:** every fixed pair satisfies `|z_p − z_q| ≤ B(p,q)`; a pair that does not (KASE's parallel beside a 2 % runway) is reported `fronting_cap_infeasible` and the rows on that path are EXCLUDED from §5's promotion — Q-133 stays the owner's.

**Derivation site.** ONE function `constraints/no_step.hold_interval(planar, law, cs, fixed)` replacing `runway_reach_band_values`: a `RouteGraph` (`routes.py:130`, `budget :175`, `csr :189`) built from the `Diff` rows of `cs`, read by `reach` (`:902`) through the branch's super-source walk (`_reach_super`, KEEP). Called in `solve_design` after stage 0, before stage 1 (`design.py:841`); output = ONE hard `Band` per datum column (`model/constraints.py:114`, KEEP) + sidecar `platforms[].reach_band` / `reach_width_m` / `reach_gap_m` (`publication.py:573`). The mint-time DEM test (`pad_blocks.plan_blocks :583`) keeps choosing the CUTS only (30n) and certifies nothing.

**The datum.** The solver chooses `D_b` inside `I_b` (the hold rows + the apron trend at 30 + `ground_datum` 3 pull it toward the ground's long wave) — "the datum comes from the feasibility graph" (30y (2)) with no DEM proxy deciding it (30u (b) closed).

**EMPTY interval.** (i) The block is a RESIDUAL: `D_b` = the bound nearest the median of the contact bands' mid-points (branch mechanism, KEEP); a contact whose band excludes `D_b` keeps its hold PRICED at 300 under the now-hard fronting caps (§5) — the apron comes as close as the caps allow, the rest is carried by the collar and REPORTED (`pad_frontage_infeasible`, `families.toml:226`, with `reach_gap_m`); never a silent collar (30y (4)), never a runway move. (ii) T2 pre-registered: `building280` ONE block (30z (4)); expected EMPTY under the exact metric too (5.99 m over 344 m = 1.74 % > 1.5 %: no flat datum exists with the caps held, whatever the runway does); the lane posts the gap, held/residual (branch 45/18), site feet vs 20/107 (branch) and 31/108 (control). The further cut along wall lines (30n, narrowest neck) is the NEXT round's, after the owner reads those numbers. (iii) Any other unit with an empty interval and ≥ 2 blocks: STOP.

## §3 THE STAND LINE — A PLATEAU INSIDE THE APRON FACES

**Geometry.** STAND ZONE of held block `b` = (a) the apron within `[design] jetway_strip_m` (40 m, `emit.toml:604`) of the block's rider edges (`jetway_strip.rider_hosts :134`, `strike_set :97` — the strip's geometry, reused) ∪ (b) every apt.dat 1300 startup (`model/airport.py:172-178`, `apt_dat.py:68`, already read at `classify/roles.py:281`) of kind `gate` / `tie_down` within 60 m of the HELD contacts, buffered by NEW `[design] stand_zone_radius_m = 30.0` (code-D half wingspan + clearance; owner may set); clipped to the fronting apron bodies and to the span of the HELD contacts (ramp contacts `samples_ramp` excluded, so adjacent blocks' plateaus never touch — the ramp between them, ≥ `|ΔD| / cap`, stays a ramp: SPJC b0|b1 2.09 m needs ≥ 139 m). **Cut site:** `planar/pad_cut.py` right after `apron_cut_to_pads` (`:58`, the 23a precedent for cutting airside faces by pad geometry) as `plateau_cut`; the boundary is snapped to existing apron vertices within the identity spacing as `airside_clip` quantises crossings to rim nodes (`:189`; 30aa rule 9). The plateau piece keeps role `apron` (every role reader untouched) under ref `<apron ref>#plateau:<block ref>`, the grammar extended at its one site (`model/planar.py`, v1 C3).

**Rows.** Every plateau vertex (ring + 50 m interior lattice) joins the block's hold set: the same HARD row `z_v − z_D = 0` (`frontage_hold_rows`, membership via a `plateau_vertices(planar, law)` accessor). Beyond the ring NO new family: the transition faces' apron rows (ring edge / spine / body at 1.5 %, preference 1 %) and the taxi lanes' rows, HARD on the fronting set (§5), ARE 30z (3)'s chords — each transition face a chord set between a ring at `D_b` and a taxi edge, slope minimised by the 1 % tier, twist allowed.

**Emittable:** yes — the plateau is a planar polygon at `D_b`, the transition a polygon with one ring at `D_b` and one at the taxi edge, one `z` per vertex; `merge_sub_spacing` (`osm_adapter.py:852`) sees identity spacing by construction. The jetway strip (`jetway_strips :186`, `project_strip.project_strips :96`, `_pad_plane :330`, `verify/jetway.py:31`, `publication.jetway_strips_ll :586`, `[jetway_strip]` `families.toml:154`) is DISARMED on a held block — the plateau is its law in stage 1, not a post-stage-1 projection; after §4 no airside-fronting pad is unheld, so the strip machinery is DELETED once §6 is met (family kept registered, reads 0).

**Consumer census (30l) — every pass that reads apron faces / rings, ruled before any edit:**

| # | consumer | ruling |
|---|---|---|
| P1 | `planar/pad_cut.apron_cut_to_pads :58` | EDITED — `plateau_cut` after it, the ONE site |
| P2 | `pad_cut._renode_counts :336`, `airside_clip :189`, `publication.py:484` `pad_airside_renode` | EDITED — plateau ring vertices are published under `plateau_rings` and EXCLUDED from the renode count (minted by law, not a re-noding artefact); the family still reads 0 for everything else |
| P3 | `planar/pad_terrace.pad_terrace_split :117`, `planar/weld.weld_cells :57` | UNCHANGED (run before the cut; the ring is snapped to identity spacing) |
| P4 | `planar/shapes.network_faces :220`, `_label_pavement :276`, `_gap_joints :764`, `joint_planar_edges :636` | UNCHANGED — plateau and transition touch: ONE shape, no joint (08k (2)) |
| P5 | `apron.apron_within_shape :173` (ring edge :214, frontage chord :216, body :218, `tiered_rows :155`) | UNCHANGED; the ring adds ring edges on both faces (0 inside the plateau; the transition's bound the ramp) |
| P6 | `constraints/apron_trend._apron_bodies :85`, `apron_trend_targets :158` | UNCHANGED — adjacency → one body; the hold overrides locally |
| P7 | `constraints/pads.airside_vertices :176`, `_pavement_faces :210`, `pad_frontage_level :819`, `frontage_contacts :929`, `frontage_near_miss :1015` | UNCHANGED for an unheld pad; a held pad mints no `frontage_level` row (v1 C6) |
| P8 | `constraints/pad_fronting.facing :109`, `pad_fronting_level :275` | UNCHANGED (facing frontages not held, 30k Q3) |
| P9 | `no_step.pad_contacts :206`, `pad_pavement_edges :232`, `no_step_pairs :268`; `pavement_cap.pavement_road_cap :74` | UNCHANGED — pairs over the ring met at 0 |
| P10 | `transverse.priced_roles :94` / `transverse :141`; `stretches.APRON_ROLE :73`, `edge_cap :172`, `pair_caps :257`; `taxi.taxi_box :412`; `structure_underpass.py:96`, `classify/airside_edge.py` | UNCHANGED (taxi faces untouched; upstream) |
| P11 | `constraints/routes.build_routes :485`, `_nearest_station hop :414`, `reach :902` | UNCHANGED as the 04o route metric; REPLACED as the interval's metric by §2's pair graph (`hold_interval`) |
| P12 | `constraints/jetway_strip.*`, `solve/project_strip.*`, `verify/jetway.py:31`, `publication.jetway_strips_ll :586` | DISARMED on held blocks, then DELETED (above) |
| P13 | `model/islands.courtyard_faces :59` | UNCHANGED — a plateau piece shares vertices with non-courtyard airside (`islands.py:28-29`), never a courtyard |
| P14 | `solve/design_roles.airside_stage_vertices :71`; `classify/roles.py:281`, `evidence.py:427` (startups); `emit/osm_adapter.render_patch :345`, `merge_sub_spacing :852`; `verify/within.within_shape :309`; check_grade `within_shape` (`families.toml:40`), `airside_no_step`, `apron_over_preference` | UNCHANGED (role readers, upstream readers, emitted-face readers) |
| P18 | `constraints/eat.py:112` `EXTRA_ROLES` / `eat_pins :254` | UNCHANGED; EAT-pinned apron vertices are FIXED points of §2's interval |
| P19 | `tools/airside_value_delta.py:252-257` (`--tol`, `--json` a/b-only nodes, 30aa KEEP) | EDITED — plateau ring vertices on a held block's fronting apron are EXPECTED added nodes (`plateau_nodes`), reported apart from the 0-added-airside-nodes bar |
| P20 | `pipeline/publication.cluster_pads :255`, `_platforms :573` | EDITED — `platforms[]` gains `plateau_vertices`, `stand_zone_source`, `reach_band` / `reach_width_m` / `reach_gap_m`, `held_within_tol` (branch, KEEP) |
| P21 | `solve/why` `--why-at` | EDITED — names the plateau hold on a plateau vertex and the promoted hard cap on a fronting pair |

An apron-ring reader not in this table is a STOP (add the row, rule it, then edit).

## §4 §20 CONFORMING PADS (CYXY's class) COME UNDER THE SAME LAW

Every welded pad ≥ `min_area_m2` (250, `structures.toml:494`) with airside contacts (`no_step.pad_contacts :206`) is a HELD block — "EVERY building" (30y (1)). No platform / collar is minted for it (the `cluster_pad_min_m2` gate `planar/platform.py:203-218` stands); the mechanism is ONE register move: a §20 pad is already a rigid `Flat` plate whose contacts ARE its ring vertices (09-01g) — its cap-0 flatness row, today one-way `flat airside-led` (`emit.toml:920`) at `pad_flat` 3000 (`:535`), becomes HARD TWO-WAY in stage 1 when its interval is non-empty (the plate's columns are stage 1's already: `design.py:184-186`); the datum column is the plate's; Band and sidecar as for a block; `pad_frontage_level` (`pads.py:819`) not minted. A plateau forms only where riders or startups are within reach (§3); a shed gets none. **Empty interval → residual as §2** = today's §20 behaviour plus the report — no regression by construction. Pre-registered CYXY: building9 / building7 tilt 0.000, footed bodies within 0.3 m, runway 0, movers only on their fronting set. HECA: held / residual / plateau counts quoted; > 30 % residual is a STOP (the metric, not the pads).

## §5 HARD vs PRICED AFTER THIS SPEC

| row set | today | after | site |
|---|---|---|---|
| runway profile between pins (chord 300 + relative hard rows) | priced chord, hard relatives; TRANSLATABLE by any airside row | **FIXED** (stage 0 solved alone, then constant) | `design.py:841` |
| frontage hold `z_c − z_D = 0` (contacts + plateau) | hard (branch) | **HARD**, stage 1; residual contacts of an empty interval PRICED at 300 | `constraints/platform.py:492` |
| datum Band | hard (branch, route metric, absent on 3/8 blocks) | **HARD**, pair-graph interval, present on every held block | `no_step.hold_interval` |
| taxi longitudinal / transverse / taxi_box, apron 1.5 % max, no_step | priced 300 everywhere | **HARD on the FRONTING SET** `F_b` (the apron bodies welded to `b`, the junction/taxi faces sharing a vertex with them, and every face on the least-budget path from each `c ∈ C_b` to its nearest fixed vertex, `routes.route_path :926`); priced elsewhere. Promotion is ONE filter in `design.assemble` (`design.py:206`, the 30aa rule-1 site) reading a published `planar.fronting_pairs`; no generator edited; `is_hard` (`design_roles.py:176`) unchanged for heads | `design.py:206`, `:1093` |
| apron 1 % preference tier | priced | priced (the design's PRICE lives here, `apron_over_preference` REPORT) | `apron.py:88` |
| DEM trends (`apron_trend` 30, `taxi_trend` 30), `ground_datum` 3 | priced | priced (choose `D_b` inside `I_b`) | `emit.toml:445/410/395` |
| §20 pad plate at cap 0 | one-way, 3000 | HARD two-way for a held §20 pad (§4) | `emit.toml:920`, `:535` |
| 5 % / 8 % ceilings | hard | hard | `emit.toml:796-797` |

**Census effect, reconciled with 30o.** With the fronting caps hard, the rows the hold "spends" are held at `hard_tol_m` 0.02 (`emit.toml:909`), not violated; the price moves into the preference tier and the trends. So adjudicated families on the fronting set read ≤ the reference (fact 3's +880 / +294 / +153 reverse) and the design's price is REPORTED as `apron_over_preference` per block — a report, never a regression. Taxi / apron MOVERS ≥ 0.05 m on the fronting set are the ruling's content (30f, 30y (3)), quoted per block (count, worst, route); 30o's STOP stands for any mover OFF the fronting set, any runway mover, any un-named CRITICAL-motion change. The hard-set report (`design.py:1093-1103`) shows 0 violated fronting rows; a violated one is named and, at attempt 2 only, its FAMILY (never the runway or the hold) may be demoted to priced on that set with the number posted — `taxi_box` plane rows are the expected candidate (three-column rows lie outside §2's pair metric).

## §6 ACCEPTANCE (site numbers first; replays on the hardhold128 captures, then ONE HECA + ONE SPJC build)

| # | bar |
|---|---|
| A1 | **Runway 0 at 0.02** vs the references on HECA (sw0929c), SPJC + CYXY (sw0930), KCLT (cifp119 replay); G0 (stage 0 alone) 0 first |
| A2 | Every HELD contact and every plateau vertex within `hard_tol_m` 0.02 of its datum: SPJC b0 ≥ 76/85, b1 ≥ 106/128, b2 ≥ 131/144 (ramp contacts excluded: 9/22/13), building13 38/38, HECA T3 b1–b4 100 %; `held_within_tol` published per block |
| A3 | Plateau tilt 0.000 per block; plateau present at SPJC b5 (riders) and HECA T3; each plateau's vertex count and area quoted |
| A4 | Every apron / taxi pair on the fronting set within its cap at 0.02 (hard-set violated = 0); `apron_over_preference` quoted per block |
| A5 | Feet within 0.3 m ≥ the hardhold128 numbers − 0 at every owner site: SPJC b5 site 80/80, pad-wide 860/1096, building13 147/175; HECA T3 site 25/89; T2 site 20/107 (residual, §2 (ii)) |
| A6 | Adjudicated airside on the fronting families ≤ reference (HECA ≤ 18,046, KCLT ≤ 6,582, SPJC ≤ 1,143 on the build); CRITICAL motion HECA ≤ 18, SPJC 0, KCLT ≤ 4; every changed CRITICAL row named |
| A7 | T2 pre-registered: interval EMPTY, gap quoted; residual report present; feet re-read (20/107 site vs 31/108 control) — posted as the owner's numbers per 30z (4), no further T2 mechanism this lane |
| A8 | CYXY: building9 / building7 flat, feet within 0.3 m ≥ today's, runway 0, movers only on their fronting set |
| A9 | `pad_airside_renode` 0 outside `plateau_rings`; `airside_value_delta --json` a/b-only nodes = the plateau rings only |
| A10 | Fresh full suite, no NEW red vs a clean main worktree; twins: stage 0 (a taxi row cannot move the runway), `hold_interval` on a synthetic graph (consistent fixed points → non-empty; a 1.74 % frontage → empty), the fronting-set promotion, the plateau cut (snapped ring, renode 0), §4's register move |

## §7 STOP LIST (report, never decide)

Any runway mover (A1, G0); a violated hold / plateau row at hard_tol; an empty interval on an already-cut unit other than T2; an unsnapped plateau vertex inside the identity spacing; an apron-ring reader not in §3's table; a fronting hard row still violated at attempt 2; > 30 % residual §20 pads at HECA; any airside vertex minted / deleted outside `plateau_rings`; a new contact pair stepped > 0.5 m outside a declared neck strip (v1 §7).

## §8 THE LANE BRIEF (lane `flatpad128v2`, `model: "opus"`, `subagent_type: lane`, base `origin/main`, attempt cap 2, replay-first)

1. `lane_worktree.sh up flatpad128v2 origin/main`; port f3b19a20's KEEP set (§9); captures `frames/hardhold128/{HECA,SPJC,KCLT,CYXY}.pkl` (at 3b3e4ed1; re-capture if `--replay` refuses); quote at start: `census.py` on the references, `airside_value_delta` self-diff 0, `held_within_tol` per block from `hardhold128_SPJC.osm.axes.json`.
2. **Stage 0** (`design.py:841`): replay all four `--from constraints` with the hold OFF (`[building_pad] frontage_hold = false`) → G0 runway 0 at 0.02 vs the references; post the unknown/row counts. STOP on a mover.
3. **`hold_interval`** (`no_step.py`, pair graph from `cs`): per held block `[lo, hi]`, width, gap, binding fixed vertex + path; SPJC b2 / building31 / building34 must now HAVE an interval; T2 gap quoted; `--why-at −12.0284806 −77.1162727` names the hold and the Band.
4. **Fronting-set promotion** (`design.assemble`): replay HECA + SPJC `--emit --verify`; fronting hard rows violated 0; families vs reference (A4/A6).
5. **Plateau cut** (`pad_cut.py`) + hold membership + strip disarm + P2/P19/P20/P21; replay; A3, A9; `--why-at` on a plateau vertex.
6. **§4 register move**; replay CYXY + HECA; A8 and the held/residual pad counts.
7. **Closing:** ONE HECA + ONE SPJC build via `build_airport.py` (parallel, untimed); KCLT + CYXY replays; `census.py`; `airside_value_delta` in three counts (runway / fronting set / elsewhere); feet at the owner sites with `feet_site.py` / `feet_agg.py` PROMOTED into `tools/` with an INDEX row first (30ae); register frames (`frames.py --copy`); post on #128 A1–A10 in order, then every item NOT done; RULINGS letter after the tail (absolute path).

Pre-registered per site: SPJC b5 site contact 0.00, low end 0.00, apron to the junction ≤ 1.5 % worst 10 m window, plateau under the jetways flat; building13 38/38; HECA T3 site ≥ 25/89, runway 0; T2 as §2 (ii); KCLT runway 0 (its 18C/36C are apt.dat/CIFP-pinned since #119/#129 — stage 0 fixes them regardless); CYXY as A8.

## §9 WHAT TO KEEP FROM f3b19a20, WHAT TO DELETE

**KEEP:** the hard hold rows and `HOLD_RULING` in `hard_rulings` (`constraints/platform.py:492-600`, `emit.toml:799`); `held_within_tol` / `ramp_contacts` / `reach_band` / `reach_empty` / `residual` in `platform_records` (`:672-703`); the ramp mask `samples_ramp` (`pad_blocks.py:106-118`, `:583-587`; `planar/platform.py:254-258`, `:336-341`); `_reach_super` + `_SUPER_SOURCE_PINS` (`routes.py:902-940`); the deletions of the priced hold (`emit.toml` `frontage_hold = 30` / `frontage_hold_rulings`, `design.py:1148-1153`) and `pin_datums` (`model/platform.py`, `design.py:889-893`); `test_hardhold128.py`; the empty-interval residual mechanism (`platform.py:558-571`).

**DELETE:** `runway_reach_band_values` (`no_step.py:178-208`) — replaced by `hold_interval` after stage 0 (it pinned `preferred_z`, not solved values, on a metric that reached 5 of 8 blocks); the route dependency inside `frontage_hold_rows` (the interval is passed in, computed once in `solve_design`); the stand-hold arm (already gone — the plateau is its lawful form).
