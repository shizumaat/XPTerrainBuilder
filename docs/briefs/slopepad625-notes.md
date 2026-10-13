# slopepad625 — notes (follow-up of seat610; owner RULINGS 2026-10-13a (5) Q2: "Pad for a building on a slope", KASE FBO)

## RESUME HERE
* Branch `claude/slopepad625` from the merged `claude/seat610` head fd818af19 (main ac5406a3a + seat610). NO CODE
  YET — stopped after the measurement, as the master's brief says to when the rule mints more than a handful at an
  approved airport (HECA: 114). Scratch `<scratchpad 466e18b3…>/seat610/`: `p1_slope_pads.py` (the dry read, a
  capture → `planar.cluster.clusters` → `geom.cluster_outline.cluster_outlines` at `[building_pad] min_area_m2` 250
  instead of `[placement] cluster_pad_min_m2` 5000 → `airport.skirt.ring_relief_m(airport.dem.z, outline)`),
  `slope_pads3.log` (every row, lon,lat), `cap/KASE.pkl` (fresh capture on fd818af19), `cap/padread_base.txt`.

## HOW BUILDING PADS ARE MINTED TODAY, AND WHICH GATE REFUSES THE KASE FBO
`classify/evidence._pads` — ONE derivation site, two halves: (A) THE CLUSTER HALF `_cluster_pads` →
`geom.cluster_outline.cluster_outlines` over the pack's walled clusters, rules in order: no rings → nothing; outline
closed at `footprint_touch_m`; the ground floor owns the ground; airside subtracted (14ah); LEAVES get no pad and a
walled cluster mints a pad only where its outline reaches `[placement] cluster_pad_min_m2` = **5000 m²** (rule 5,
`under_min_m2`); wall lines (thin) dropped; deck shades subtracted; tall-base-fill (#101, v1) and building-evidence
(R18-2) gates (`[pad_admission]`, RULINGS 2026-10-02v (3)). (B) THE FALLBACK HALF: v1 footprint-cache rings
(`dsf:object:object`) and OSM buildings (`rules.buildings.sources`) not covered by a cluster pad, the unvouched role
refused without OSM evidence. Both halves then: runway difference, `[building_pad] min_area_m2` 250 (08-24 tiny pads
fold), the boundary gate (`_inside_gate`, #336 near-miss), `_absorb_enclosed` (#6), and `_drop_skirted` (10ag: a
skirted building mints no pad while the pad's DEM relief ≤ the skirt depth — SPJC's tower).
KASE (`cap/padread_base.txt`): 779 clusters, 305 walled, **under_min_m2 291**, leaf_dropped 474, cluster pads 5 →
2 emitted (`building1` 5,419 m² the main hangar block, `building2` 13,412 m²). **The FBO is cluster `unit:121#4`,
walled, outline 420 m² (FBO_3/5/6) — refused by rule 5 (420 < 5000), and no footprint-cache/OSM building covers it,
so the fallback mints nothing.** A "ground unit" is the consequence, not a gate.

## THE OWNER'S RULE AS STATED DOES NOT MINT THE FBO PAD — the slope under the FBO is the APRON'S FILL, not the DEM
`ring_relief_m(airport.dem.z, outline)` across the FBO outline = **0.54 m** (airport-smoothed DEM, the same reading
the skirt drop takes). On the app's MESH the building spans 1.47 m (walls' feet on the apron `pav7` at 2362.25–
2362.59, the NE posts' ground 2361.12): the apron beside the FBO is graded ~1 m above the DEM to reach the
taxiways, the walls stand on that apron and the posts on bare ground behind it. A DEM-relief witness at
`pad_terrace_floor_m` 1.0 does not see it; the witness that does is "feet on graded airside pavement AND feet on
bare ground whose DEM stands > floor below that pavement's level" — readable only after the solve, or pre-solve as
pavement-contact ∧ DEM step to the pavement side (the `[building_pad] groundside_cutback` mixed-pad class).

## THE MEASUREMENT (dry; `cluster_pad_min_m2` 5000 → 250 for walled clusters, DEM relief > `pad_terrace_floor_m` 1.0, inside the boundary gate; skirt and admission gates as today; airside clip not applied in this read)
| airport (capture) | walled outlines 250–5000 m² (no pad today) | relief > 1.0 m = NEW PADS |
|---|---|---|
| HECA (pads67) | 229 | **114** |
| KCLT (valley2) | 69 | 24 |
| KSEA (jetbay612) | 34 | 13 |
| KPDX (kpdx559) | 54 | 5 |
| KASE (fresh, fd818af19) | 9 | 4 — NOT the FBO (0.54 m) |
| SPJC (pads67) | 4 | 2 |
| NLWF (pads67) | 1 | 1 |
| OTHH (pads67) | 84 | 0 |
| CYXY (cyxyflip) | 0 | 0 |
| KBFI | no registered capture | — |
STOP: HECA 114 and KCLT 24 new hard flat pads are not "a handful" at approved airports; per the brief the rule is
not narrowed by a tuned threshold and the measurement goes to the owner. Approved-airport rows (lon,lat; relief,
area, cluster, members):
```
  relief  1.40 m  area    1546 m2  unit:6#0           at -77.108647,-12.019884  ('LAN_office.obj',)
  relief  1.04 m  area    2217 m2  unit:0#1           at -77.115049,-12.031704  ('Costa del sol_001.obj', 'Costa del sol_002.obj', 'Costa del sol_004.obj')
NLWF:
  relief  3.53 m  area     424 m2  unit:11#0          at -178.068907,-14.311173  ('Vele_terminal.obj',)
KPDX:
  relief  1.75 m  area    2809 m2  unit:7#3           at -122.600727,45.582220  ('kpdx_ANG_base-kpdx_base_11.obj', 'kpdx_ANG_base-kpdx_gen11.obj', 'kpdx_ANG_base-kpdx_roofs10.obj')
  relief  1.63 m  area    2142 m2  unit:7#12/1        at -122.597572,45.580935  ('kpdx_ANG_base-kpdx_base_11.obj', 'kpdx_ANG_base-kpdx_gen11.obj', 'kpdx_ANG_base-kpdx_greenery.obj')
  relief  1.46 m  area    1776 m2  unit:7#12/0        at -122.596719,45.580571  ('kpdx_ANG_base-kpdx_base_11.obj', 'kpdx_ANG_base-kpdx_gen11.obj', 'kpdx_ANG_base-kpdx_greenery.obj')
  relief  1.17 m  area    3571 m2  unit:10#25         at -122.608821,45.583325  ('kpdx_cargo_ramp_south_06.obj',)
  relief  1.06 m  area    2077 m2  unit:7#5           at -122.599720,45.581642  ('kpdx_ANG_base-kpdx_base_11.obj', 'kpdx_ANG_base-kpdx_gen11.obj', 'kpdx_ANG_base-kpdx_roofs10.obj')
KASE (4, none the FBO):
  relief  3.44 m  area     820 m2  unit:140#0         at -106.865439,39.225505  ('X-Obj-004.obj',)
  relief  2.93 m  area    1074 m2  unit:109#0         at -106.862873,39.221683  ('X-Obj-017.obj',)
  relief  2.03 m  area     711 m2  unit:149#0         at -106.865444,39.226303  ('X-Obj-001.obj',)
  relief  1.10 m  area     611 m2  unit:131#0         at -106.867406,39.224445  ('Hangar2_1.obj', 'Hangar2_2.obj', 'Hangar2_5.obj')
HECA top 25 of 114:
  relief  7.65 m  area    3733 m2  unit:43#830        at 31.407497,30.114502  ('T3_34.obj', 'T3_concrete_Yellow.obj', 'interior_glass.obj')
  relief  7.45 m  area    4878 m2  unit:43#727        at 31.391986,30.118458  ('T3_21.obj', 'building_2_texture.obj')
  relief  6.94 m  area    1911 m2  unit:43#6330/1     at 31.396558,30.112613  ('360_room.obj', 'AC_Electronics.obj', 'Asset_N_B.obj')
  relief  6.46 m  area    2892 m2  unit:42#3412       at 31.399480,30.115292  ('T3_14.obj', 'titles_1.obj')
  relief  5.99 m  area    3220 m2  unit:43#647        at 31.392760,30.117258  ('T3_17.obj', 'building.obj', 'building_2_texture.obj')
  relief  5.90 m  area    1373 m2  unit:42#11         at 31.399702,30.128462  ('Black_rock.obj', 'T2_glass_noanpha.obj', 'T3_51.obj')
  relief  5.02 m  area     795 m2  unit:41#139        at 31.415627,30.126395  ('T3_61.obj',)
  relief  4.70 m  area    3753 m2  unit:43#612        at 31.407266,30.119045  ('T2_glass_noanpha.obj', 'T3_37.obj', 'T3_concrete_Yellow.obj')
  relief  4.38 m  area    4724 m2  unit:43#323        at 31.409218,30.116760  ('Plastic.obj', 'Strip_metal_2_blue.obj', 'T3_37.obj')
  relief  4.24 m  area    3515 m2  unit:43#629        at 31.393030,30.114882  ('T3_15.obj', 'building_2_texture.obj')
  relief  4.19 m  area    4048 m2  unit:41#232        at 31.410573,30.136399  ('T3_69.obj',)
  relief  3.83 m  area    3995 m2  unit:43#842        at 31.406205,30.117446  ('T3_35.obj', 'T3_concrete_white.obj', 'black_plastic.obj')
  relief  3.48 m  area    2769 m2  unit:41#171        at 31.416295,30.130178  ('T3_64.obj',)
  relief  3.42 m  area    3933 m2  unit:43#8/1        at 31.406488,30.114700  ('360_room.obj', 'Black_rock.obj', 'Light_red_and_RED.obj')
  relief  3.31 m  area    3887 m2  unit:42#3415       at 31.399849,30.116850  ('T3_concrete_Yellow.obj', 'metal_blue.obj', 'titles_1.obj')
  relief  3.18 m  area    4855 m2  unit:43#593        at 31.397114,30.119398  ('T2_glass_noanpha.obj', 'T3_28.obj', 'T3_concrete_white.obj')
  relief  3.13 m  area     759 m2  unit:43#843        at 31.406089,30.117943  ('T3_35.obj', 'building_texture.obj', 'building_texture_3.obj')
  relief  2.98 m  area    4133 m2  unit:41#180        at 31.414731,30.130541  ('T3_65.obj',)
  relief  2.89 m  area    2753 m2  unit:43#784/1      at 31.397592,30.120263  ('T3_28.obj', 'T3_29.obj', 'building_2_texture.obj')
  relief  2.87 m  area    4068 m2  unit:43#644        at 31.398126,30.114938  ('Plastic.obj', 'T3_16.obj', 'blue.obj')
  relief  2.83 m  area     471 m2  unit:42#307/2      at 31.397930,30.127770  ('Plastic.obj', 'Strip_metal_2_blue.obj', 'T3_51.obj')
  relief  2.72 m  area     961 m2  unit:43#819        at 31.404590,30.121646  ('T3_33.obj',)
  relief  2.69 m  area    2166 m2  unit:41#418        at 31.418486,30.122454  ('metal_blue.obj', 'metal_strip_1.obj')
  relief  2.59 m  area    1656 m2  unit:41#22         at 31.417219,30.121486  ('Strip_metal_2_blue.obj', 'T3_58.obj', 'metal_strip_2.obj')
  relief  2.57 m  area    3721 m2  unit:42#641        at 31.402323,30.124124  ('T3_49.obj', 'Titles_not_metal.obj', 'building.obj')
KCLT top 10 of 24:
  relief  6.03 m  area    5000 m2  unit:31#1364       at -80.942309,35.226095  ('paredes_10_charlotte.obj', 'paredes_11_charlotte.obj', 'paredes_12_charlotte.obj')
  relief  5.51 m  area    1361 m2  unit:3#20          at -80.928011,35.218499  ('Charlotte_Airport_001_ALB.obj', 'Charlotte_Airport_004_ALB.obj')
  relief  4.75 m  area    2472 m2  unit:54#1          at -80.932970,35.225204  ('Charlotte_Airport_Museum.obj',)
  relief  4.05 m  area    2361 m2  unit:3#608         at -80.929222,35.214345  ('Charlotte_Airport_005_ALB.obj',)
  relief  3.99 m  area    1342 m2  unit:31#1117/4     at -80.945144,35.225548  ('paredes_10_charlotte.obj', 'paredes_11_charlotte.obj', 'paredes_12_charlotte.obj')
  relief  3.80 m  area    1766 m2  unit:3#610         at -80.930567,35.214208  ('Charlotte_Airport_005_ALB.obj',)
  relief  2.98 m  area    3147 m2  unit:31#1311       at -80.943584,35.227175  ('paredes_10_charlotte.obj',)
  relief  2.84 m  area     887 m2  unit:3#863         at -80.931937,35.214586  ('Charlotte_Airport_008_ALB.obj',)
  relief  2.71 m  area    1284 m2  unit:3#737         at -80.941026,35.208994  ('Charlotte_Airport_006_ALB.obj',)
  relief  2.49 m  area     560 m2  unit:3#525         at -80.941364,35.211033  ('Charlotte_Airport_004_ALB.obj',)
```

## CONSUMER CENSUS (what a new pad enters; nothing edited)
A pad minted by `_pads` is one more `building` region through the ONE derivation site, so every consumer reads it
as it reads every pad: `classify/roles.classify` (regions difference themselves by `pad_union`; `_cut_back_groundside`
touch witness → `pad_touch`/`pad_weld`), `planar/pad_blocks` + `platform` (the mint-time frontage-hold test, blocks,
`platforms_refused`), `planar/plateau`/`pad_terrace` (plateau rings, pad|apron terrace at ≥ `pad_terrace_floor_m`),
`planar/weld` (rim welds), `constraints/pads` (pad_flat target, 1 % ceiling, `pad_welded_vertices` = pad columns
senior to roads — 13a (1) "road yields to the pad", lane roads609), `pad_frontage_gs`, `cluster_pad`, `roads`/
`road_ramp` (a road welded to a pad ramps to it), `verify` pad_* families, the object stage (`pad_plurality` seats the
unit on the pad; the §16g unit becomes `@pad`). Risk named by the numbers: 114 new hard flat pads at HECA, each a
frontage/weld authority beside its apron and roads.

## OWNER QUESTIONS
- Q-a The rule as stated (DEM relief > 1 m) does not catch the KASE FBO (0.54 m DEM; 1.47 m on the mesh from the apron's fill). Witness options: (a) relief read against the graded pavement the building touches (a second mint after stage 1, or the pre-solve proxy pavement-contact ∧ DEM step), (b) keep the DEM witness and accept the FBO as a design-stage residual, (c) a pad for every walled cluster ≥ 250 m² that touches airside pavement (KASE 9 → count).
- Q-b 114 new pads at HECA / 24 KCLT / 13 KSEA under the stated rule: (a) go (owner re-reads HECA), (b) raise the relief floor (NOT this lane's call), (c) restrict to buildings with feet on airside pavement.
