# #2063 round 3 — an isolated object stands on its lowest contact feet (RULINGS 2026-11-13y (4)/(5); Fable, 2026-11-13)

Replaces Rule F (step 3) of `2063-round2-spec.md`; round 2's steps 1, 2, 4, 5 stand. Note: the plan-wide witness is stricter than lane lkrnt2's within-body clustering; at KRNT one aircraft share still fails the pavement bar (a C152 within 2 m of a building piece, −0.13…−0.11 m) — Q2.

## 1. Mechanism (code)
- Seat is always the median of every foot: `_generic_anchor` `zero = median(surface − y)` over every foot of every part (`anchor_rule.py:1139`); 12am (2) branch (`:1171`) only picks median vs low-side when residual > `split_tol_m`.
- A part's feet = up to `foot_samples_max` 4 vertices within `[basin] contact_band_m` 1.0 m of that part's own minimum (`contact.py:155-186`); every part with base ≤ `elevated_base_m` 0.5 (`structures.toml:830`) votes at its own height (gear legs, fuselage).
- §9 merge: `coarsen` joins raw bodies of one member whose zeros agree within 0.3 m within `coarsen_reach_m` 100 m, on the senior's zero (`placement_carrier.py:112`, called `placement_plan.py:510`).
- `ground_contact_feet` has one production caller, the §17 census (`placement_motion.py:144`); not part of any seat.

## 2. Evidence (replay of lkrnt2 frames `frames/lkrnt2/{KRNT.rebake.c2.json,place_c2_base.json}` + Rebuild_cache mesh +47-123; scripts scratchpad `fspec/fc2.py fc4.py fc5.py`)
Footed AIRCRAFT bodies with a wheel > 0.05 m under: today 25/29; this spec 1/29 (`c74ca6eb…-AIRCRAFT_C152v2_1` b0, 8 parts within 2 m of `KRNT_Buildings_05-Renton_2`, −0.13…−0.11). Qualifying shares 378. Aircraft clusters qualifying 66/86 (non-qualifying: 13 footless fragments, 3 spread > 0.3, 2 lowest y +0.44/+0.50 wheel-less sheets, 2 chained to a base-plane building). Worst burial (capped seat) −0.050; worst float +0.21; 10 floats > 0.05, all B737-size (apron fall across gear 0.10–0.26). Plain median of lowest feet: worst −0.13. Fences as links fail (chains > 150 m; uncapped 442 m fence+building chains). Scatter members in scope (owner-site C152 file carries no rings, seated by the median today).

## 3. Law
### 3.1 Isolated cluster and share (certain witness; any failure → today's behaviour, 13r)
Cluster = closure of the plan's solid parts under plan gap < `[placement] rigid_reach_m` (2.0) (outline `Part.rings`, else `Part.box`). Share = the cluster's parts within one `Unit` (one anchor frame). Isolated seat only when ALL hold:
- I1 Isolation: closed over every non-line part of this plan and every sibling plan of the airport (main + companions, passed as `foreign` outlines); sibling parts block but never join; `Part.line` parts neither link nor block (10bb).
- I2 No structure: no member skirted, deck, plate, datum, basin, connector, authored-seat or adapted-frame; none with a welded base plane (`Member.base_profile["planes"] >= 1`).
- I3 Compact: cluster plan diagonal ≤ `[placement] group_span_max_m` (150).
- I4 Feet at the author's ground: share has feet and its lowest authored y within `split_tol_m` (0.3) of `−Unit.agl_m`.
- I5 One readable ground: every lowest contact foot reads the design surface, not water, not on an object pad (`pad_majority`), deck face or inside a rim.
- I6 One terrain: spread of `surface − y` over the lowest contact feet ≤ `split_tol_m`.
No new law constants; every refusal counted by reason.
### 3.2 Lowest contact feet and the seat
L = share feet with authored y ≤ y_min + `[cockpit] motion_step_m` (0.05) (one foot allowed). r = surface(f) − y_f over L; `Z = max(median(r), max(r) − motion_step_m)` (no contact foot buried > 0.05; the fall shows as float ≤ spread − 0.05). Anchor = foot of L with r nearest Z (max-r foot when the cap binds), `y_zero = r_f + y_f − Z`. One frame per share: every body of every member in the share written at that one anchor (sheets `_1/_2/_3` rigid). Object stays level (I6 keeps shares out of 10-01k/#708 tilt). Tailwheel: L holds the mains; tailwheel joins only if within 0.05. B737 +0.18 = fall across gear, listed (Q1).
### 3.3 Files
Isolated bodies of one member merge only with each other when zeros agree within 0.5 × `motion_step_m` (0.025) and contiguous under `coarsen` reach; never with a non-isolated body.

## 4. Consumer census (passes 3–4 rows "(grep)": lane confirms each skip site at step 0)
| Reader | Where | Ruling |
|---|---|---|
| generic anchor, 12am (2) | `anchor_rule._generic_anchor` 1099-1187 | unchanged for non-isolated; isolated never reach it |
| raw-body grouping | `placement_body._raw_bodies` 104-128 | groups of one share unioned; one raw body per member and share, share anchor, no cut |
| part/foot/triangle/arc cuts | `placement_body.py` 232-420 | skipped for isolated (rigid, as `one_cluster`) |
| elevated test | `placement_carrier.is_elevated` 74 | False when `anchor.isolated` |
| §9 merge | `coarsen`, `placement_plan.py:510` | isolated coarsen apart at 0.025 |
| plan-overlap bind, terrain re-cut, split by unit, leaves | `placement_plan.py` 520-547; `placement_file._split_by_unit` 596; `placement_leaves.attach_leaves` 49 | skip isolated (leaves explicitly: `piece_reach_m` 2.5 > 2.0) |
| orphans | `placement_orphan.place_orphans` 57 | unchanged; verify an aircraft's non-solid comps land in its own file |
| §16c (7) | `placement_atom.bind_unit` 800, `unit_rigid` 388, `RigidNode` 355 | isolated node `bindable=False` |
| 12ap (A) | `placement_atom.py` 597-603 | unchanged; not reached by isolated |
| carrier search | `placement_carrier.CandidateIndex` 520, `carriers_for` 575 | isolated never offered as carrier |
| §16g unit seats, §16f | `footprint_unit.bind_footprint_units` 81, `_seat` 1530, `_bind_plan_wide` 1172 | skip isolated (removes `fu:18:2947@one_building` from B737_1 b0) |
| viaduct seat | `footprint_unit.seat_viaducts` 267 | skip (grep) |
| 22o / 22q | `open_frame_seat.group_zero` 531; `airside_group_seat.airside_zeros` 145 | skip (grep); consistent with 13y (4) |
| pad-level/block seats (10-28p (2)), deck seat (§49) | `pad_block_seat`, `placement_deck` | never co-occur (I5); assert in a twin |
| seat/frame tilt | `placement_seat_tilt.seat_tilt`, `frame_tilts` | skip isolated (I6) |
| riders/contents (13r, F.9) | `riders`, `frame_riders`, `footprint_carry.contents_seat` | unaffected (rider within 2 m of host); twin |
| authored keep (14g) | `build_splits(authored_keep_tol_m)` | unchanged |
| §17 census | `placement_motion.census_motion` 94, `ground_contact_feet` 67 | isolated judged at lowest contact feet; new `lowest_contact_feet(feet, band_m)` = one implementation for seat and census |
| records | `placement_plan.to_placement_records` 1426-1460 | add `isolated_of` |
| tools | `obj8_split_report.py`, `v2_rebake_replay.py`, `seat_feet_census.py`, `drawn_site.py` | pass new args; ISOLATED block in the report |
| writers | `dsf_write`, body files, provenance | more files; verify round trip |

## 5. Ordered changes (fresh Opus lane on `claude/lkrnt2` rebased onto current main; LAST round)
0. Replay base: `tools/v2_rebake_replay.py plan` on the registered c2 frame reproduces `place_c2_base.json`; grep the (grep) rows; a missing anchor-replacing pass → STOP.
1. Exclusion witness (round 2 step 1): fold in scratchpad `lkrnt2/step1-exclusion-draft.patch` (`O4_Overlay_Pack.exclusion_boxes`, `airport/exclusion.py`); write the `companion.find` hook, log line, twins; check `ratchets.py layers` for its `O4_*` imports.
2. `own_claim` over served airports (round 2 step 2) and the `also` witness (step 4).
3. New `airport/isolated_seat.py`: `clusters(plan, reach_m, foreign)`, `shares(plan, surface, pads, rims, decks, …) -> {pid: Share}`, pure `seat(readings, band_m)`; extend `placement_contact` (`ring_metres`, `rings_touch`, `boxes_touch`, `_clusters`) for the gap test, don't fork.
4. `Anchor.isolated: str = ""`, `is_elevated`, `placement_motion.lowest_contact_feet`.
5. `_raw_bodies(isolated=…)`.
6. `build_splits`: compute shares once beside `_fu.plan_wide_seats` (`placement_plan.py:390`); kwargs `motion_step_m`, `isolated_span_max_m`, `isolated_foreign` wired from law in `placement_write`, engine, tools; production passes sibling plans' outlines; a tool run without them prints "isolation read within this plan only".
7. The skips, the census change, `isolated_of`, counts (`isolated_shares`, `isolated_refused_<reason>`).
8. Spec text: new §9a in `object-placement-spec.md` citing 13y (4)/(5), 22o, 13r; amend §17 (2) item 3.

## 6. Blast radius / required census (master reads before landing)
Every non-walled compact isolated object everywhere (aircraft, GSE, cars, benches, cones, non-line signs; main packs + companions) moves toward its lowest feet (expect 0.1–0.5 m, mostly downward relief of burial... i.e. raising buried wheels). Corpus replay base vs branch over every airport with a rebake frame (EFHK, EGLL, ELLX, HECA, KASE, KATL, KCLT, KLAX, KMCI, KPAE, KSEA, LEMD, LFMN, LFPG, LGAV, OTHH, PHNY, SBGL, SBRJ, SPJC, VHHH + KRNT c2); certified KEGE, BIKF, KSUN, KBTV listed separately (each needs one patch build to register frames). Per airport: shares qualifying, refused by reason, every body whose zero moves > 0.1 m (resource, landmark, before, after), file-count change, plan-stage seconds. Instrument: `obj8_split_report --zero-diff BASE.json` + INDEX row same commit. Named false positive: any walled thing or > 150 m post-feet structure that changes seat.

## 7. Bars (materiality 0.01 m)
Replay on c2: footed AIRCRAFT bodies with a contact foot > 0.05 under: 25 → ≤ 1 (named); no isolated share's lowest foot under > 0.05; float ≤ max(0.05, spread − 0.05), listed > 0.05.
KRNT closing build (`drawn_site`): every drawn isolated aircraft's wheels within ±0.05 of pavement or residual = listed fall, none under > 0.05; off pavement ±0.3; Cub/C152 at 47.4928, −122.2142 within bars; each non-isolated aircraft named with reason/residual; the 15 round-1 FLOAT rows classified.
Neighbours: KSEA, KBFI, KPAE no drawn body worse > 0.1. DD body files at KRNT ≤ 670 (else STOP). Plan-stage cost for KRNT, LEMD, OTHH; STOP if > +3 s anywhere.

## 8. Closing build
`venv/bin/python tools/harness/build_airport.py KRNT --tile 47 -123 --pack-copy <scratch> --tag krnt2063r3` (~2,581 s; 30 GB free); reuse round 1's base reads; report the drawn-gate verdict.

## 9. Tests
`test_isolated_seat.py`: gap 1.9 → one cluster, 2.1 → two; line part neither links nor blocks; sibling-plan part within 2 m refuses; each of I2–I6 refuses with reason; wheel+leg+belly body seats wheels at 0 (median would bury 0.27); 0.2 m fall → burial exactly 0.05, rest float; single foot; tailwheel 0.2 above mains keeps attitude; three sheets one anchor; two shares merge at 0.02, not 0.04. `test_v2objsplit.py`: isolated not bound by `unit_rigid`, not §16g-seated, not carried, not a carrier; rider in a walled booth unchanged (13r); base-plane shed unchanged; `census_motion` judges isolated at lowest feet. Round 2's exclusion / served-claim / `also` twins. Gates: `test_no_airport_specific_code`, `ratchets.py`, `test_windows_text_io`.

## 10. Risks
Convex-hull rings read nose-to-tail aircraft as one cluster (safe). File inflation on slopes (≤ 670 bar). Orphan components joining a neighbour's file within 100 m reach (check KRNT). A missed pass in placement_plan passes 3–4 (lines 700-1300) moving an isolated anchor afterwards (step 0 grep). Cost at OTHH (137,908 rings) unmeasured. `planes == 0` is member-level: atlas file mixing a slab + aircraft refuses all its shares (conservative).

## 11. Owner questions (lane uses defaults)
Q1 large aircraft on a sloping apron keep float = fall across gear (KRNT 10, worst +0.21): accept and list (alt: extend 10-01k/#708 baked tilt). Q2 aircraft/cart within 2 m of a building not isolated, keeps today's seat (KRNT one C152 −0.11…−0.13): unchanged. Q3 a line object beside an object doesn't group it: yes. Q4 isolated walled/slab things keep median: yes. Q5 burial capped at 0.05, rest as float: yes. Q6 certified airports re-read only if the census shows a body moving > 0.1 m there.

## Amendment A1 (Fable, 2026-11-13; owner held round 3 at 23:35Z until wall pieces stay grouped)
Measured (static read of rebake plans through the branch's `isolated_seat.shares`/`clusters`; scripts scratchpad `wit.py bf.py bfall.py bf45.py aon.py ev.py`): part height ≥ 2.5 m rejected (B737 parts 5.2–7.6 m); lowest-contact extent rejected (tall walls read low: KCLT `paredes_12` 0.11, `paredes_3/4` 0.10); same-file sibling "any part near a structure" rejected (KRNT refuses 10/75 aircraft); "≥ 2.5 m part near a structure" rejected (KPAE refuses 8 B777); member all-or-nothing rejected (87/142 KRNT survive). Adopted:
Definitions over solid non-line parts P: height(P) = max(base_y + height_m) − min(base_y); base_spread(P) = greatest plan distance between any two feet of P (all `Part.feet`) ÷ `_span_m(P)` (0 with < 2 feet); WALLED-BASE(P) = height(P) ≥ `[placement] chain_min_height_m` (2.5, `structures.toml:1143`) AND base_spread(P) ≥ new key `[placement] isolated_base_min_fraction` = 0.45 (aircraft ≤ 0.43: KRNT Seaplanes 0.43, B737 0.32–0.37, B777 0.35, Lear25 0.36, ERJ140 0.39, Bell412 0.23; lowest walled refused 0.52 KPAE ILS mast, 0.54 LGAV lamps, 0.56 KRNT GSE cluster, buildings 0.57–1.00; counts identical at 0.45 and 0.50 except LFMN 6/6 vs 3/6).
I7 `building_file`: a member is a BUILDING FILE when any member-local cluster (`clusters(the member's own solid non-line parts, rigid_reach_m)`, incl. parts dropped "by structure") is WALLED-BASE; every share of a plan cluster holding any part of a building file is refused.
I8 `walled`: the plan cluster itself is WALLED-BASE → every share refused.
Plug-in: in `shares()` after the `structure`/`not_isolated`/`span` verdict (`isolated_seat.py:243-246`), before `_share` (I4–I6); `REFUSALS` += "building_file", "walled" after "span"; kwargs `wall_min_h_m`, `base_min_fraction` wired from law beside `isolated_span_max_m` (`placement_plan.py:403`, `obj8_split_report._isolated_kwargs:2046`), either at 0 disarms both; pure helpers `base_spread(parts)`, `building_files(members, reach_m, min_h, min_frac) -> frozenset[member id]` computed lazily (members holding a candidate part surviving I1–I3), cached. No ICAO/name/texture test. Refused beyond buildings (keep today's median, Q4): box vans, train cars, masts, ILS antennas, multi-object clusters > 2.5 m.
§3.4 cluster-senior (frozen election): the election is held WITH the isolated present — no non-isolated body's anchor, zero, senior or carrier may differ from the base run because a share exists. Defect: `_isolated_raw` (`placement_body.py:447-478`) strips isolated parts before raws are made → `coarsen` (`placement_plan.py:532`) elects a different senior → `bind_unit` (`placement_atom.py:853-862`) builds `RigidNode.footprint_m2/feet/zero` from the shrunken candidate (KCLT −4.34). Mechanism: (1) `_isolated_raw` stops stripping (today's raws from full groups as base; isolated raws added beside, invisible to every pass); (2) passes 2–4 run on today's raws unchanged; `without_parts` goes away (`bind_footprint_units` takes the full `_pw`, `placement_plan.py:673`); (3) one `isolated_seat.vacate(...)` before `to_placement_records`: drop every today raw all of whose parts are isolated, hand its components (and attached orphan/carried components) to its share's isolated body, recompute surviving bodies' pids/feet/boxes from remaining raws; anchors frozen; (4) a today raw with both isolated and non-isolated parts refuses that share, reason `welded`. Isolated side's skips stay. BAR: on the replay zero-diff, non-isolated bodies whose zero moves > 0.01 m = 0 at every census airport (any row → STOP and report).
Tests (`test_isolated_seat.py`): wall slab (height 3, feet along its base) refused `walled`, 2.4 m admitted; three-wheel aircraft 7.6 m tail spread 0.3 admitted; file with a walled-base piece inside a structure closure + a small isolated piece → small piece refused `building_file`; aircraft atlas with one aircraft touching a structure → others admitted; plan cluster of an admitted member + a building-file member refused; either key 0 disarms; `vacate` identity with no shares; synthetic unit where the isolated group is today's coarsen senior and largest footprint → remainder's anchor and §16c (7) senior equal with/without the share; mixed raw refused `welded`; gates `test_no_airport_specific_code`, `ratchets.py`, law-key registry.
Census expectation (unique mover shares → refused): KCLT 8 → 8 (paredes 0 movers); KRNT c2 123 → 46 (77 stay: aircraft, cars, signs, `Dirt_04`, `Fence_01` ×3 worst −1.36; 71/75 aircraft admitted, 4 refused multi-object clusters `walled`: C172 group 44 parts h 4.7 spread 0.70 (+0.38 mover), YellowCart + B737 82 parts 0.69, two `Handling_02-AIRCRAFT_B737_1` 0.56 — re-read the §7 "25 → ≤ 1" bar on the c2 replay with these named); KPAE 154 → 64 (68/68 aircraft admitted); LGAV 132 → 61; KMCI 30 → 29; KASE 3 → 2; ELLX 29 → 25; LFMN 6 → 6; EFHK 15 → 12; EGLL 19 → 19; HECA 7 → 1 (`OB-asphalt_3` ×6 +2.12 stays — low sheets not caught, report); KSEA 2 → 0. Non-isolated movers 0 everywhere.
Risks: 0.43 vs 0.52 gap is narrow (safe direction); low sheets (HECA `OB-asphalt_3` h 0.4 span 41.7 +2.12, EFHK gate pieces) not caught — report for the master; `vacate` is the big piece (passes 3–4 `placement_plan.py` ~700–1330 unread; cut-triangle raws and `forced`/`cluster_out` re-index — confirm), high effort; OTHH cost unmeasured (plan stage already +179 s there); old plans with `Part.height_m` 0.0 → I8 never fires → disarm the isolated seat for such a plan and say so.
