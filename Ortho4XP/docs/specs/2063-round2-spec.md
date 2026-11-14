# #2063 round 2 — exclusion witness, served-airport claim, Rule F free-standing clusters (Fable review of lkrnt2063 6b1bee1f6, 2026-11-13)

Verdict: round 1's companion extension (pack whose apt.dat defines only OTHER airports is a candidate; `object_window.own_claim`) is right and fixed the owner's floaters (CUB +1.67 → −0.32, C152 +1.61 → −0.06/−0.32). Not landable as is: (1) six aircraft at −0.30…−0.45 m (placement-law tolerances on a sloped apron, §2); (2) rows X-Plane never draws (under a higher pack's `sim/exclude_obj`) are adopted and rewritten — nothing in `auto_patch_v2` reads exclusions; (3) `own_claim` ignores #1630 airports (DD serves KBFI, KPAE as object pack); (4) after-read lists 15 FLOAT rows > 0.5 m (max +7.93) vs 5 before, unadjudicated. Keep the branch; next round is a fresh Opus lane on it. LAST Opus round: a miss goes to the owner.

## Mechanism
DD "AIRCRAFT" files are texture-atlas scatters: `KRNT_STAT_-AIRCRAFT_C172v2_1.obj` 132 components, 87×146 m, base y −0.06, 15 clusters at 2 m 3D reach; `KRNT_STAT_-AIRCRAFT_B737_1.obj` 349 comps, 92×288 m, 28 clusters; `c74ca6eb…-AIRCRAFT_CUBv2_1.obj` 15 comps, one aircraft. One real aircraft = parts of 2–3 files (`_1/_2/_3` sheets) around one shared anchor; the author's frame is flat, KRNT's apron is not. Three tolerances stack: `placement_atom.py:31` `RIGID_REACH_COMPONENTS_MAX = 64` skips reach for these files; a body is a level group (atoms whose ground agrees within `[placement] split_tol_m` 0.3, `structures.toml:915`) so one body holds several aircraft tens of m apart; `unit_rigid` (`placement_atom.py:388`) unions bodies through the contact graph, so one multi-aircraft body chains the ramp up to `UNIT_CLUSTER_SPAN_MAX_M` 300; the 12ap (A) release fires only above `bind_ground_m` = `[cockpit] visual_m` 0.5 (`emit.toml:153`; `placement_atom.py:597-603`). Residuals −0.45/−0.43/−0.34 (< 0.5, bind kept), −0.32/−0.32/−0.30 (0.3 same-file merge). Inferred from code; step 0 confirms. Owner law already covers it: RULINGS 2026-10-22o (`RULINGS.md:10261`) "we only split and seat separately, objects that are clearly at least a couple meters apart with no above ground connecting shape".
Exclusions (approx. bbox): pack order `KRNT Renton` (ini 857) > DD (868) > `Orbx_A_US_Washington_TE_Airports` (1087). KRNT Renton has 3 `sim/exclude_obj` boxes on the east; ~55 of 260 DD rows in the KRNT box lie inside (6 AIRCRAFT rows + `B737fuselage-KRNT_B2` = the +7.93 "FLOAT", not drawn). Of 9 Orbx rows at KRNT 6 drawn (Tower, Ace Aviation, Rainer Flight Service, Seattle Aircraft Charter, South Hangar, Boeing 4-20), 3 excluded. KSEA: ~19 of 25 Orbx non-library rows inside DD's exclusion boxes.

## Changes (general; KRNT only the closing test)
0. Attribution on a replay (one KRNT patch build, not `--tile`, for the companion plan JSONs; then `tools/v2_rebake_replay.py plan <companion plan> MESH --graded …` and `obj8_split_report --motion-rows`): for the six over-bar bodies print atoms, plan box, zero source (own anchor / §9 same-file merge / §16c (7) bind with senior + own-ground disagreement / §16f family / 22o `group_zero`), footprint unit. If not §9 merge + §16c (7) bind → STOP and report.
1. Exclusion witness — new small `airport/exclusion.py`: `sim/exclude_obj` boxes of every enabled pack ABOVE a given pack with a DSF for the tile. Reuse `O4_DSF_Header.dsf_property_pairs` (header only, 7z), `O4_Scenery_Packs.load_order`, the box parse in `O4_Overlay_Pack._network_excluded` (extend, don't copy). Read the pristine DSF; unreadable header = not excluded. `companion.find` drops excluded rows before `admitted`, one line `[companion] <pack>: N row(s) under <pack>'s exclusion — not drawn, left alone`. Applies to every companion incl. the apt-less 10-28p (5) class.
2. `own_claim` covers SERVED airports: union the read area of every other airport whose `pack.select_pack(...).root` is this pack (#1630 included), derived from `select_pack`/`object_pack.find`; bound to airports whose region holds a pack-local row of this DSF. Doc: "where the airports this pack SERVES read it".
3. Rule F — a free-standing footed cluster seats on its own feet. F-cluster = connected parts of one pack's plan across members, linked by the plan contact graph or a plan gap under `[placement] rigid_reach_m` (2.0) (reuse the §16g footprint-unit chain with the reach as spacing; `blast.py --find` first). Free-standing footed, all required: own ground-contact feet (`placement_motion.ground_contact_feet`); every other part ≥ 2 m away in plan; not line/deck/connector/basin/floor member/rider; not on an object pad. Any failure → today's behaviour (13r). Seat: one zero per F-cluster, the senior footed atom's, read at its own feet; `unit_rigid` never binds across two F-clusters (F-cluster id on `RigidNode` beside `unit`; elevated pieces join their own cluster); the §9 same-file merge joins atoms of different F-clusters only when zeros agree within `0.5 * split_tol_m`. Plan-only reach over existing part boxes/polygons (not the 3D sweep the 64-cap avoids). Every plan, main pack and companion; no ICAO/pack/size threshold.
4. `also` witness: count KRNT rows admitted only by `also` and how many are drawn owner-site aircraft; zero → delete `also` and `_plan_centre`; else replace the box centre with "every ground-contact foot inside the boundary" (use `pack.authored_source` as `_objects` does). LFPG +4 / LOWW +1 kept only if they pass the tightened form, listed for the master.
5. Spec text: Rule F into `object-placement-spec.md` as a §16c sub-block citing 22o; amend 12ap (A) in place; exclusion + served-airport paragraphs in `companion.py` doc.

## Consumer census
| Reader | File | Ruling |
|---|---|---|
| candidates | `pack_local.tile_candidates(icao=)` | keep |
| pre-build dumps | `engine_v2._fresh_companion_dumps`, `companion.dump_candidates` | keep; exclusion reads headers only |
| row admission | `pack_local.admitted(inside, also)` | step 4; `object_pack._first_placing` unchanged |
| #1630 selection | `object_pack.find`, `pack.select_pack` | read-only reuse (step 2) |
| serving window | `load.py:562-585`, `object_window.Window`/`rivals` | unchanged; follow-up noted |
| claim | `object_window.own_claim` | step 2 |
| companion plan | `companion.plans` → `partition_pack` → `rebake_plan` | fewer rows |
| §9 merge | `placement_plan._ride`, `_pc.group_at_zero`, `placement_cut.terrain_groups` | step 3 half tolerance across F-clusters |
| §16c (6)/(8) | `placement_atom.comp_cluster` | unchanged |
| §16c (7) | `unit_rigid`, `bind_unit`, `follow_seniors`, `_fu.cluster_zero_allowed` | step 3 never across F-clusters |
| 12ap (A) | `placement_atom.py:597-603` | stays for non-free bodies |
| roof witness #610 | `placement_atom.py:624-668` | unchanged |
| §16g (4) | `placement_plan._atom_targets` | unchanged |
| 22o (1) | `open_frame_seat.group_zero` | consistent; verify step 0 |
| §16f / 10-28p (2) | family, pad-level passes | F not on pads; confirm no re-join off pads else STOP |
| 13r rider | rider seat | unaffected |
| writers | `dsf_write`, `body_files`, `o4_placement_provenance.json` | verify round trip; no orphaning across airports |
| instruments | §17 census, drawn gate, `drawn_site` | adjudicate the 15 FLOAT rows |

## Bars
KRNT: every adopted drawn aircraft body with ground-contact feet within ±0.3 m of drawn ground (the six + the round-1 site list); CUB/C152 within ±0.3; no drawn footed body floats > 0.3; each of the 15 FLOAT rows classified (a) elevated piece on a carrier (carrier clearance quoted), (b) excluded/not drawn, (c) real float = miss; 6 drawn Orbx buildings stay seated, 3 excluded unwritten. KSEA/KBFI/KPAE: no drawn body worse > 0.1 m vs base; Orbx rows under DD's exclusion unwritten. DD body files at KRNT ≤ 670 (round 1: 335); corpus-wide file delta from replays. Census for the master (13r): every corpus airport incl. #1630 ones — rows adopted/dropped per pack, bodies whose zero moves > 0.1 m under Rule F; KEGE and BIKF listed separately (certified). Materiality 0.01 m. Plan-stage cost reported (< 1 s expected).

## Closing build
One: `venv/bin/python tools/harness/build_airport.py KRNT --tile 47 -123 --pack-copy <scratch> --tag krnt2063r2` (round 1 2581 s; df ≥ 30 GB). Covers KRNT, KSEA, KBFI, KPAE. Same `drawn_site` site list as round 1; reuse round 1's base reads (`scratchpad/krnt/build/`); no control. Report the drawn gate verdict.

## Tests
`test_companion_other_airport_pack.py`: row inside a higher pack's exclude box not adopted; lower pack's box doesn't exclude; #1630-served sibling's area in the claim. Rule F twin in `unit_rigid`: two footed bodies ≥ 2 m apart joined only through a third multi-cluster body not bound; same pair < 2 m bound; walls + roof across members bound; body on a pad unchanged. §9 merge twin: two F-clusters 0.2 m apart in ground → two files; 0.1 → one. `also` twin. Gates: `test_no_airport_specific_code`, `ratchets.py`, `test_windows_text_io`.

## Risks
Rule F moves airside free-standers (GSE, aircraft, cars) everywhere by up to 0.5 m toward their ground — touches certified airports (census is the control). File-count inflation (LEMD 13,924 precedent): STOP and report if it explodes, don't tune. Plan-level reach over clutter (OTHH) must stay box-swept. Exclusion header cap 64 KB (`HEAD_BYTES`) → reads as no exclusion (safe). Shared DSF re-apply across airports in one tile build — re-verify.

## Owner questions (lane uses defaults)
Q1 aircraft < 2 m apart stay one group (default yes, 22o's threshold). Q2 rival packs' drawn rows stay unseated (default: unchanged). Q3 simHeaven as LOWW companion (185 rows) despite 10-28p (5): default keep the content witness. Q4 main pack rows under a higher exclusion: not this round. Q5 Rule F may move seats at KEGE/BIKF: accept a re-read (no per-airport scope, 05e).
