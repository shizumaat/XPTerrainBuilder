# Spec 2068 A2 — a unit's fence stands on the author's ground: the fence-foot plane (#2068 LPPI tower) (Fable, 2026-11-14)

Base: main `d381a76e4`. Follows `2068-upper-pad-spec.md`, `-A1.md`, RULINGS 2026-11-14a/14b. Owner sim read 2026-11-14T14:44Z (issue #2068, comment 6879120302). One Opus round, effort high. Never raise the lane cap; delete scratch builds when you report.

Main finding: the owner's black wire fence is a pack OBJ whose own base heights give the intended ground directly. Its upper stations lie on one plane tilted 3.5 % within 0.21 m rms. The spec builds that plane out to the fence, rather than a flat level.

## 0. Measured

Sources: capture `/Users/noah/XPTerrainBuilderData/.harness/frames/llppi2068/LPPI_deg.pkl` (degraded DEM), the pack's files, and the ltower3 closing patch `.../frames/ltower3/LPPI_auto.patch.osm`. Frame xy in metres.

**The fence.**
- The black wire fence is `New term/lppi_terminal_10.obj`. Its texture `@pico_cerca.png` is 25.5 % opaque, mean opaque RGB 20/25/24.
- It is a member of unit 0 (the terminal's objects, one anchor, heading 350.997).
- `line_solidity.obj_solidity` reads base 0.0, top 7.908, solid_top 0.0, opaque 0.285, so `kind_of` gives `wire_fence` (`airport/line_solidity.py:308-331`, `classify/rules.toml:93`).
- It has 6 vertical-sheet components. Components 4 and 5 run 249 m round the tower, with these authored base heights (panel 3.3–3.5 m):

| Leg | From → to (frame xy) | Length | Base y |
|---|---|---|---|
| W | (−186.2, −263.1) → (−178.2, −313.6) | 51 m | 0.00, 0.04, 0.10, 0.48, 0.93, 2.03, 3.54 (owner's point E), 4.15 |
| S1 | → (−136.6, −307.0) | 42 m | 4.15 → 4.41 |
| S2 | → (−104.9, −302.0) | 32 m | 4.44 → 4.47 |
| E1 (tower's east side) | → (−110.8, −259.2) | 43 m | 4.47, 4.46, 4.48, 4.36, 3.97, 3.69, 3.13 |
| N (apron side) | → (−82.6, −254.8) | 28 m | 3.13 – 3.15 |
| E2 | → (−86.1, −305.3) | 52 m | 3.14, 3.43, 3.72, 4.22, 4.42, 4.42, 4.46, 4.61 |

**The plane.**
- 126 stations at 2 m; 107 are upper (base ≥ t + ½ rise = 2.35, with t 0.0 and y_p 4.70). The 19 that are not are all on the W leg north of y ≈ −300.
- One least-squares plane through the 107: tilt 3.47 % (falls 3.2 % toward the apron, 1.3 % toward the west), rms 0.21 m, residuals +0.53 / −1.03.
- Plane minus y_p at the owner's sites: tower −0.40; B −1.36; beside the road at C −1.44; D −0.84; E −0.94; N leg middle −1.43; SW corner −0.66.
- The plinth (`lppi_terminal_09` comp 8, y 4.70) is level on a 3.5 % site: 0.2 m proud at its south edge, 0.9 m at its north.

**Why nothing reads it today.**
- It is not a line object. Component 4's y extent is 7.91 m, at or over `line_object_max_h` 6.0, because it climbs 4.15 m on 3.5 m panels (`airport/line_object.py:54, 63`; `law/structures.toml:873`). The verdict is per resource (`line_object.py:70-81`), so every part is solid (capture parts pid 255/256 `line False`).
- Consequence: `building1`'s pad ring carries a 0.2 m spur along 173 m of fence, (−185.2, −269.2) → (−178.1, −313.5) → (−104.7, −301.9). Patch nodes at the fence's SW corner read 33.41 (= D) where the DEM reads 38.1–38.7.
- It is not in `Airport.edge_lines`, which holds DSF line facades only (`airport/load.py:1189-1198`). At LPPI these are `dsf:line0` (165 m, 345 m away) and `dsf:line1` (library `Fence.fac`, the 5,577 m perimeter, `wire_fence`). `dsf:line1` runs 2–8 m outside the black fence on W and S, and crosses the east enclosure 6 m inside the black fence's N leg. It is not the fence the owner means.
- Classify stats today: `edge_strips 0`, `edge_hosts_grown 6` (606 m²), `fence_split_faces 1`.
- `wall_class` skips nothing here: "cerca" is deliberately not a fence word (`airport/wall_class.py:99-101`). Component 2 already publishes a `wall_terrace` joint in the ltower3 sidecar.

**Enclosures.**
- Tower compound: 3,513 m² gross, 2,356 m² free of cells; fence on 69 % of its outline. The rest is `building1`'s south face and apron `dsf:pol96`, whose neck ends at y −274.9, the owner's point C.
- East enclosure (the owner's A→B pavement): 1,281 m², no cell inside; fence on 87 %; a 19.1 m mouth toward the south road.

**Shipped (ltower3 patch).** Level 38.11 (D 33.41 + 4.70); rim steps 3.29–3.66 m. Road at C 33.55, at D 34.35–34.45. South road 39.3–39.8 beside the tower, 40.69 at A; ground outside the SW corner 34.9–35.4. DEM (capture): A 40.80, B 35.35, C 35.70, D 37.36, E 37.24. The 30 m DEM reads a 10 % slope where the author has a 3.5 % terrace.

Not read here (for Q2/Q3): road barriers `lppi_terminal_08` comps 33/34/40, base +4.64 along the south road; tanks comps 23–28, bases 0.08–2.71.

## 1. The rule (general; no airport named — RULINGS 2026-10-05e)

A fence stands on the ground. A wire fence, low barrier or wall-on-its-zero that the pack authored inside a unit's own frame carries the author's ground along its foot: unit zero + its base y. Where such a fence stands a storey up beside an upper pad of the same unit, the ground it encloses is the fence-foot plane: the upper ground runs out to the fence on that plane; the cut or fill to natural ground and to lower pavement happens at or outside the fence; a road that climbs to the pad runs in a cut through it. This is 10-03b's second witness and 10-03c ("the wall identifies the place for the terrace") read for a fence that carries heights.

Gates (doubt → today, 13r):
- **G1** An upper pad already read by T1–T4 (`airport/unit_storey.py:265-315`). No upper pad → no yard; classify and planar byte-identical.
- **G2** Only fences that are members of that pad's own unit. A DSF line facade, an OSM fence (13y (1)) or another unit's fence is not read here.
- **G3** Class in `line_solidity.ON_TOP`. A retaining wall is the step itself (`wall_class`) and is not read.
- **G4** A station is upper when base ≥ t + ½ (y_p − t) (`unit_storey.py:248, 251`, `classify/storey_edge.py:136`). Needs upper runs ≥ `[edge_lines] min_run_m` and a rank-3 plane.
- **G5** Plane rms over the upper stations ≤ `[edge_lines] step_min_m` (0.5).
- **G6** The yard's DEM median stands ≥ ½ rise over the floor's airside median (T4's own `za`, `unit_storey.py:243-248`).
- **G7** Airside is king: the yard is a late cell, projected after the solve, and never a row.

## 2. Pieces (in this order)

**F0 — a fence on a slope is a line object** (`airport/line_object.component_shape`, `:39-55`). For a zero-plan-width sheet, height becomes the largest column extent (top − base of the vertices at one plan position), not the component's y extent. Stacked sheets at one position still read their full height; components with plan width are unchanged. At LPPI `lppi_terminal_10` becomes a line object (`pack_partition.py:503-506`): drapes per segment (09-10bb), forms no body, chains nothing (14a (2)), leaves `building1`'s ring, no longer wall-class (`wall_class.py:137`). Recapture LPPI after F0.

**F1 — unit fences join the one fence list.** New `airport/unit_fence.py`, `attach_unit_fences(airport, cfg, cache)`, called beside `attach_wall_shade` at `pipeline/build.py:393-394`, `tools/v2_solve_replay.py:690-692` and `:2224-2226`. For each unit member whose parts are all `line` and whose file reads `ON_TOP`: read its sheets' bottom edges through `sunken_ramp._member_tris` (`:124`); columns by plan position, welded at `min_distinct_spacing_m`, chained into runs ≥ `min_run_m`. Append one `EdgeLine` per run, id `unit:<ui>:<member>#<comp>`, with new defaulted fields `unit`, `base_ys`, `panel_m` (`model/airport.py:275-291`). `fence_division.fence_lines` (`classify/fence_division.py:59-67`) and `edge_line_mint.mint_edge_strips` (`classify/edge_line_mint.py:209-218`) skip `el.unit is not None` this round (Q4).

**F2 — the yard** (new `classify/fence_yard.py`, called right after `mint_edge_strips`, `classify/roles.py:927-928`; reads `upper` from `roles.py:821`).
1. Stations every `station_m` along the pad's unit fences; upper by G4.
2. Plane: `solve/project_strip._pad_plane`'s construction (`:330-357`), moved to `geom/` and shared. Tilt capped at the `groundside_pavement` longitudinal cap. G5.
3. Region = (flood ∪ pockets) ∩ upper Voronoi − stand-off. Flood: free ground connected to within `host_reach_m` of the pad, inside the convex hull of the upper stations and the pad (grown by `host_reach_m`); never crosses a unit fence or a standing cell that is not a groundside road-family cell. Pocket: a face of `polygonize(unit fence runs ∪ one chord per run end to the nearest fence vertex not on its own run)` fenced on ≥ 0.75 of its outline sharing ≥ `min_run_m` of upper fence with the flood or an accepted pocket. Upper Voronoi: only points whose nearest fence station is upper. Stand-off: `edge_line_mint`'s `keep_off` (`:200-203`, factored out), out to the fence line plus its base half-width (`:221`). Pieces under `[cells] min_area_m2` dropped. G6.
4. Mint each piece as `groundside_pavement`, ref `fenceyard:<k>:<pad ref>`; new prefix in `model/planar.py` beside `EDGE_STRIP_PREFIX` (`:1172-1190`), inside `is_facade_ref` (`:1175-1179`), so a late ref (`:1360-1366`). Evidence carries plane, rms, station counts and pad.

**F3 — the yard's heights.** `planar/group_up.plan_group_up` copies the plane into the level's landing record (`:123-127`, key `yard_plane` beside `arms`). `solve/project_strip.project_facade_strips` (`:374-473`) gives every `fenceyard` vertex z = L + plane(x, y) − y_p, L the solved level of the record's `<block>/p<k>` faces. An airside-side vertex is never moved (`:452-454`); another standing face's vertex yields and is counted (expected 0).

**F4 — the road climbs in its cut.** K0 first: `--why-at 38.551706,-28.442893` (D) must name what holds the road at 34.4. Candidates: (a) a stage-1 `foot` on apron `dsf:pol96` within 10-03b's reach (`airport/road_ramp.py:1410-1421`); (b) arm vertices with no usable station (`:1314`; `constraints/road_ramp.py:776`). Fix both at `road_terrace`: for a level's arm vertices and road faces sharing a vertex with an arm, a stage-1 foot is kept only on the neck; where the frame has no answer, the arm set is its own route (station = distance over its own edges from the neck; `_graph`/`_connected` `:380-404`, merged like `runout_frames` `:644, 657-685`). The run is then `_upper_run` (`constraints/road_ramp.py:633-657`) at `[road_contact] upper_pad_road_grade` 0.20 (RULINGS 14b). No cap changes.

**F5 — publication.** `upper_pads` sidecar record (`pipeline/publication.py:747`, `pipeline/upper_pad_publication.py:114`) gains `yard`. Every yard-edge run stepping more than `[cockpit] visual_m` across its stand-off is a declared joint through `wall_terrace`, beside `upper_rim_joints` (`publication.py:1095-1112`). Code keys: `airport.unit_fence`, `classify.fence_yard` in `pipeline/stage_code.py`, `src/O4_Step_Code.py`, `src/auto_patch/provenance_code.py`.

Emittable in a heightfield: yes (planar faces on one plane; steps in the stand-off gap as edge strips already do, `edge_line_mint.py:36-38`).

## 3. Consumer census (RULINGS 2026-08-30l)

| Consumer | file:line | Ruling |
|---|---|---|
| `fence_lines` → §27 band, `split_at_fences`, `airside_both_sides` | `classify/fence_division.py:59, 112, 135, 260`; `roles.py:807-815, 937`; `gap_apron.py:72` | skip `unit` lines; byte-identical; twin |
| `mint_edge_strips`, `grow_feet_to_walls` | `classify/edge_line_mint.py:186, 254` | skip `unit` lines; `keep_off` shared |
| `is_line_object` / `is_line_shaped` | `pack_partition.py:503`; `placement_cut.py:153, 165`; `placement_atom.py:174`; `scatter.py:153-158`; `deck_family_contact.py:94` | F0; corpus flip list for the master |
| `Part.line` readers | `unit_storey.py:135-137, 251`; `wall_class.py:137`; `open_frame_seat.py:386`; `model/rebake.py:108-113` | fence leaves solids, walls and chains |
| pad footprints, `building1` ring | `planar/cluster.py` | spur gone; D within 0.05 of control |
| `upper_pads` T1–T4, `arm_storeys` | `unit_storey.py:222-315`; `storey_edge.py:189-246` | unchanged |
| `plan_group_up`, `level_cut` | `planar/group_up.py:69-133`; `low_level.py:328` | level unchanged; record gains `yard_plane` |
| late-ref readers | `roles.py:996`; `apt_shoulder.py:226`; `constraints/pads.py:236, 290, 518`; `pad_fronting.py:132`; `planar/landing.py:573`; `planar/zones.py:384`; `tools/pad_edge_read.py:391` | yard reads as an edge strip does; twin each |
| `project_facade_strips` | `solve/project_strip.py:374` | F3 branch; others byte-identical |
| `road_terrace`, `terrace_profile`, `terrace_rewrite`, `_upper_levels` | `airport/road_ramp.py:1209`; `constraints/road_ramp.py:660, 883, 1004` | F4; identical with no arm |
| `riser_sets`, `upper_arm_sets`, rim joints | `constraints/riser.py:58, 126`; `upper_pad_publication.py:86` | unchanged; rim steps shrink |
| census families across a stand-off | `law/families.toml:526` | yard edges declared; a row still priced → STOP |
| sidecar, `drawn_check`, `drawn_gate` | `publication.py:747`; `tools/harness/drawn_gate.py` | one `yard` record; gate at the five sites |

## 4. Round

1. F0 with twins and the corpus flip list. 2. Recapture LPPI. 3. F1; print the leg table vs §0. 4. F2/F3; replay `--replay <pkl> --from classify --allow-degraded-dem --solved-out`; print plane, rms, yard m², yard z at the five sites. 5. K0, then F4; replay with `--why-at` D and `--why-hard` within 100 m. 6. F5. 7. Corpus census: yards minted (expected LPPI only), line flips, pad rings changed. 8. Close: `build_airport.py LPPI --tile 38 -29 --pack-copy`, then `drawn_gate.py LPPI --tag T --against <main control>` with `--site tower=38.551644,-28.442702,60 --site A=38.551531,-28.442341,40 --site B=38.551988,-28.442453,40 --site road=38.551785,-28.442910,40 --site E=38.551578,-28.443396,40`.

MEMORY: run replays one at a time in the foreground (capture 433 MB). Any script that imports classify needs an `if __name__ == "__main__":` guard — classify's worker pool re-imports it (the 2026-11-14 out-of-memory).

## 5. Bars (z relative to the level L)

- **Y1** `lppi_terminal_10` parts `line`; no `building1` ring vertex within 1 m of the fence; D within 0.05 of control; `building2` still the one upper pad, L = D + 4.70 ± 0.05.
- **Y2** One plane: tilt 3.2–3.8 %, rms ≤ 0.3, 100–115 upper stations. East enclosure yard 1,150–1,300 m² in one piece; compound ≥ 1,200 m². No yard vertex on an airside face; `yielded` 0.
- **Y3** Replay and drawn ground, ± 0.3: B L − 1.36; E (yard side) L − 0.94; yard beside the road at C L − 1.44; within 5 m of the plinth L − 0.9 … L − 0.2; A→B slope ≤ 5 %, no step > 0.5 m.
- **Y4** N leg: drawn ground 3 m outside the fence ≥ 1.0 m under the yard; yard inside within 0.3 of the plane. E: drawn ground 3 m west of the fence reported.
- **Y5** Road: C within 0.1 of control (33.55). D ≥ L − 1.2. Grade C→D ≤ 20 %. Rim steps declared, all under control's 3.29–3.66. `--why-at` D ends on the upper run.
- **Y6** Airside movers > 0.05 vs control: none beyond 15 m of the arm's cut. 0 hard violations within 100 m. No new undeclared census row within 100 m. `drawn_gate` PASS at the five sites, no MOVED outside them.
- **Y7** With no unit fence or no upper pad, classify and planar byte-identical on one other capture; `fence_division` and `edge_strips` stats equal control at LPPI.
- Reported, not gated: banks by A and along the S legs; fence base vs drawn ground at B and E.

## 6. Tests

Line-object twin (3.5 m sheet climbing 4 m is line-shaped; two stacked 5 m sheets are not; boxed wall unchanged). `test_unit_fence.py` (runs + base profile of a synthetic U fence; retaining/elevated refused; DSF lines untouched). `test_fence_yard.py` (U fence at +4.5 round a pad on a hill → one plane, yard to the fence, nothing outside; low stations excluded; pocket across a shared fence accepted, one-sided corridor refused; non-planar / no upper pad / level ground refuse). `test_edge_lines.py`, `test_fence_division.py` identical with unit lines. `test_group_up.py` record carries the plane. Projection twin. `test_roadterrace100.py` arm climbs neck → level at 20 %. Also `test_harness.py`, `test_no_airport_specific_code.py`, registry twins (`windows_text_io`, `patch_env_classification`, `tile_failures`, `console_encoding`), `ratchets.py dupes --near` / `unused` / `layers`.

## 7. Risks and STOP rules

F0 changes object seating elsewhere — list first, master reads before landing. A census family prices a declared yard edge → STOP. K0 names a third cause → STOP F4, ship F0–F3 + F5. Cut sides are one-triangle steps (up to 3.1 m across ~1.1–1.6 m). South road and lot `dsf:pol99` not moved (Q2/Q3). `roles.py` is at its guide: one call only.

## 8. Owner questions

- **Q1** Fence-foot plane falling 3.5 % toward the apron (a) vs dead flat at the tower's level (b)? Recommend (a).
- **Q2** Cut a road running along an upper fence down to the fence-foot plane (~150 m of south road)? Recommend yes, own round after this sim read.
- **Q3** Tank lot's floor at E from the tanks' authored bases? Recommend wait for the read.
- **Q4** Admit unit OBJ fences to the §27 division and edge strips? Recommend yes after this round's census.

Unverified at spec time: the road's 3.5 m shortfall cause (K0 measures it); heights are from the ltower3 closing patch; the `building1` spur's drawn look; pad rings after F0; census families beside a late cell; plane numbers ± 0.1 from the lane's reader; capture is degraded-DEM.
