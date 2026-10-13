# tunnel548 — lane notes (#548, owner RULING 2026-10-10q)

Branch `claude/tunnel548` off main 89693e99d. Scratch:
`/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/466e18b3-e03c-471f-b042-c64d8df4e04d/scratchpad/tunnel548`
(`bore_witness.py` = the dry `python -m auto_patch_v2.planar ICAO --stage structures` with every
bore's witness readings logged; `run_arm.sh ARM`; `tab.py base q10`).

## Step 1 — the admission order (one function: `planar/structure_service.terrain_tunnel_witness`)

Asked by `structure_approach.mouths` of every bore that kept an on-field mouth (§29 (1) first).

BEFORE (main): (a) an end inside an OSM enclosure -> refused; an end inside a pack building
(`_PackBuildings.at`) -> refused; (c) classified cover >= `terrain_cover_min_m` -> built;
`layer <= terrain_layer_max` -> built; a road / railway at grade across the interior -> built;
DEM rise over the mouth chord >= `terrain_rise_m` -> built; (d) a mapped tunnel inside the
fence: `_PackBuildings.passage` -> refused, else built; else refused. `passage` was consulted
LAST and only inside the fence.

AFTER (10q): (a) unchanged; then, for a MAPPED bore (`_osm_tunnel`) whose `layer` does not say
below ground (`layer <= terrain_layer_max`), `passage` -> refused with the pack part named;
then cover, layer, crossing, rise, fence exactly as before (reasons byte-identical). (d) no
longer asks `passage` (already asked).

Two things the ruling's sentence does not spell out and the code decides (REPORTED):
- the passage also outranks the at-grade CROSSING witness (the ruling names cover and rise;
  "asked FIRST" is what is built). No bore at the nine airports read depends on it.
- the passage is asked of a mapped bore inside OR outside the fence (10i (1) asked it only
  inside). No bore at the nine airports depends on it either.

## Step 2 — code

`src/auto_patch_v2/planar/structure_service.py` only (witness body + docstrings).
Twins `tests/auto_patch_v2/test_tunnelwitness2.py`: 16 pass (the #522 "cover or rise still
builds under a passage" twin is replaced by five 10q twins: cover + passage refused; rise 0.7 /
2.0 m + passage refused; `layer=-1` kept with cover / rise / neither, `layer=0` refused; cover or
rise with no passage (no pack, or a pack part at grade) kept; outside the fence refused).

## Step 3 — bore table, nine airports (dry structure replay, base = main 89693e99d, branch = dd1ad2204)

`Ortho4XP/tools/bore_table.py` (promoted from kclt546's scratch on its second use; index row;
twin `tests/test_bore_table.py`). Every mapped bore the engine ASKED (kept an on-field mouth).
ONE verdict changes: KCLT `-32111+-27411`. `structure_replay_diff`: KCLT tunnels 11 -> 10 (the
record `tunnel:-32111+-27411@0` gone, the other 10 byte-identical; the refusal
`tunnel:-32111+-27411@1 ... against building pad building75` disappears with its bore); HECA
11, OTHH 23 (+10 basins), SPJC 8, KASE 3, CYXY 2, NLWF 0, KPDX 2, KSEA 5: IDENTICAL.
KPDX `-8765` (6.8 m, no layer, no pack passage) stays BUILT by its crossing witness
("under -10210[rail] at grade"). The four KCLT bores with cover and no layer that stay BUILT
(-32134, -30362+-30359, -30360+-30358, -31625) are synthesised §34 (5) underpasses, not mapped
bores, and report no passage.

```
== KCLT: 17 bore(s) asked (base), 17 (branch)
  -32111+-27411              312.9 m  layer None  cover 273.0  rise 0.82  passage paredes_8_charlotte.obj @ 3.03 m  | BUILT [under the classified cover for 273.0 m]  -> REFUSED  *** CHANGED: bore -32111+-27411 PASSES UNDER AN ELEV
  -31620                      13.1 m  layer -1  cover 21.7  rise 0.0  passage -  | REFUSED [bore -31620 ENTERS A PACK BUILDING at 601,1442 — Terminals/paredes_10_ch]  -> REFUSED
  -11768                     100.1 m  layer -1  cover 100.1  rise 1.47  passage -  | REFUSED [bore -11768 ENTERS A PACK BUILDING at 569,984 — Terminals/paredes_10_cha]  -> REFUSED
  -11198                       9.7 m  layer None  cover 0.0  rise 0.0  passage paredes_11_charlotte.obj @ 5.12 m  | REFUSED [bore -11198 ENTERS A PACK BUILDING at 273,1397 — Terminals/paredes_11_ch]  -> REFUSED
  -11194                       9.9 m  layer None  cover 0.0  rise 0.0  passage paredes_10_charlotte.obj @ 3.12 m  | REFUSED [bore -11194 PASSES UNDER AN ELEVATED PACK PART AT GRADE (10 m; cover 0.0]  -> REFUSED
  -11160                       9.2 m  layer None  cover 0.0  rise 0.05  passage -  | REFUSED [bore -11160 PASSES UNDER NOTHING AT GRADE (9 m; cover 0.0 m, no road or ]  -> REFUSED
  -11131                      20.1 m  layer -1  cover 32.3  rise 0.03  passage paredes_10_charlotte.obj @ 4.13 m  | REFUSED [bore -11131 ENTERS A PACK BUILDING at 239,726 — Terminals/suelos_interio]  -> REFUSED
  -9541                       50.6 m  layer -1  cover 53.9  rise 0.03  passage techos_2_charlotte.obj @ 2.98 m  | REFUSED [bore -9541 ENTERS A PACK BUILDING at 620,801 — Terminals/paredes_8_charl]  -> REFUSED
  -8739                      153.0 m  layer -1  cover 56.5  rise 3.23  passage -  | BUILT [under the classified cover for 56.5 m]  -> BUILT
  -7373                       78.2 m  layer -1  cover 78.2  rise 0.23  passage paredes_10_charlotte.obj @ 3.0 m  | REFUSED [bore -7373 ENTERS A PACK BUILDING at 605,729 — Terminals/paredes_10_char]  -> REFUSED
  -7372                       61.7 m  layer -1  cover 61.7  rise 0.03  passage Paredes_7_charlotte.obj @ 3.36 m  | REFUSED [bore -7372 ENTERS A PACK BUILDING at 386,694 — Terminals/paredes_8_charl]  -> REFUSED
  -6958                       95.6 m  layer -1  cover 61.9  rise 3.73  passage -  | BUILT [under the classified cover for 61.9 m]  -> BUILT
  -6954                       58.6 m  layer -1  cover 52.6  rise 3.41  passage -  | BUILT [under the classified cover for 52.6 m]  -> BUILT
  -32134                      12.2 m  layer None  cover 12.2  rise 0.17  passage -  | BUILT [under the classified cover for 12.2 m]  -> BUILT
  -30362+-30359               81.8 m  layer None  cover 81.8  rise 2.45  passage -  | BUILT [under the classified cover for 81.8 m]  -> BUILT
  -30360+-30358               81.9 m  layer None  cover 82.0  rise 1.82  passage -  | BUILT [under the classified cover for 82.0 m]  -> BUILT
  -31625                      39.9 m  layer None  cover 39.9  rise 3.83  passage -  | BUILT [under the classified cover for 39.9 m]  -> BUILT
== HECA: 10 bore(s) asked (base), 10 (branch)
  -20899                      31.0 m  layer -1  cover 0.0  rise 0.0  passage concrete_2.obj @ 2.63 m  | BUILT [the bore carries layer -1]  -> BUILT
  -19181                      63.6 m  layer -1  cover 8.4  rise 0.88  passage concrete_2.obj @ 2.63 m  | BUILT [under the classified cover for 8.4 m]  -> BUILT
  -3949                       63.0 m  layer -1  cover 7.8  rise 1.06  passage concrete_2.obj @ 2.63 m  | BUILT [under the classified cover for 7.8 m]  -> BUILT
  -1758                       42.2 m  layer -1  cover 0.0  rise 0.16  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -1743                       32.2 m  layer -1  cover 0.0  rise 0.59  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -1730                       53.0 m  layer -1  cover 0.0  rise 0.36  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -1725                       31.4 m  layer -1  cover 0.0  rise 0.34  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -1721                       38.4 m  layer -1  cover 0.0  rise 0.17  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -1210                      262.3 m  layer -1  cover 0.0  rise 5.96  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -1209                      269.8 m  layer -1  cover 0.0  rise 6.66  passage -  | BUILT [the bore carries layer -1]  -> BUILT
== OTHH: 10 bore(s) asked (base), 10 (branch)
  -10442                      23.4 m  layer -1  cover 1.9  rise 0.0  passage OTHH_Terminal_Parking_Parking-Left_005.obj @ 0.55 m  | REFUSED [bore -10442 ENTERS A PACK BUILDING at 575,-1783 — Buildings/Terminal/OTH]  -> REFUSED
  -5215                      473.4 m  layer -1  cover 261.5  rise 0.0  passage -  | BUILT [under the classified cover for 261.5 m]  -> BUILT
  -5214                      473.9 m  layer -1  cover 98.8  rise 0.0  passage -  | BUILT [under the classified cover for 98.8 m]  -> BUILT
  -1355                       76.8 m  layer -1  cover 37.3  rise 0.0  passage -  | BUILT [under the classified cover for 37.3 m]  -> BUILT
  -1258                      346.9 m  layer -1  cover 208.1  rise 0.0  passage -  | BUILT [under the classified cover for 208.1 m]  -> BUILT
  -1257                      340.2 m  layer -1  cover 189.4  rise 0.0  passage -  | BUILT [under the classified cover for 189.4 m]  -> BUILT
  -1240                      332.5 m  layer -1  cover 165.7  rise 0.0  passage -  | BUILT [under the classified cover for 165.7 m]  -> BUILT
  -1239                      341.3 m  layer -1  cover 175.4  rise 0.0  passage -  | BUILT [under the classified cover for 175.4 m]  -> BUILT
  -918                       811.3 m  layer -1  cover 508.1  rise 0.0  passage -  | BUILT [under the classified cover for 508.1 m]  -> BUILT
  -917                       809.9 m  layer -1  cover 518.6  rise 0.0  passage -  | BUILT [under the classified cover for 518.6 m]  -> BUILT
== SPJC: 7 bore(s) asked (base), 7 (branch)
  -10252+-2827                39.2 m  layer -1  cover 0.0  rise 0.03  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -5552+-900                  39.2 m  layer -1  cover 0.0  rise 0.0  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -5548                       22.3 m  layer -1  cover 0.0  rise 0.11  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -5546                       31.8 m  layer -1  cover 0.0  rise 0.15  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -5724                       35.2 m  layer None  cover 0.0  rise 0.0  passage -  | BUILT [an OSM tunnel inside the airport boundary (§34 (12) (5) (d), owner RULIN]  -> BUILT
  -2525                     1264.1 m  layer -1  cover 141.9  rise 0.2  passage -  | BUILT [under the classified cover for 141.9 m]  -> BUILT
  -641                      1258.5 m  layer -1  cover 142.5  rise 0.34  passage -  | BUILT [under the classified cover for 142.5 m]  -> BUILT
== KASE: 3 bore(s) asked (base), 3 (branch)
  -550                        11.3 m  layer -1  cover 0.0  rise 0.16  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -549                        18.2 m  layer -1  cover 0.0  rise 0.01  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -411                        31.6 m  layer -1  cover 0.0  rise 0.0  passage -  | BUILT [the bore carries layer -1]  -> BUILT
== CYXY: 1 bore(s) asked (base), 1 (branch)
  -725                        30.1 m  layer -1  cover 0.0  rise 2.59  passage -  | BUILT [the bore carries layer -1]  -> BUILT
== NLWF: 0 bore(s) asked (base), 0 (branch)
== KPDX: 1 bore(s) asked (base), 1 (branch)
  -8765                        6.8 m  layer None  cover 0.0  rise 0.01  passage -  | BUILT [under -10210[rail] at grade]  -> BUILT
== KSEA: 16 bore(s) asked (base), 16 (branch)
  -33257                      41.8 m  layer -1  cover 14.3  rise 0.78  passage -  | REFUSED [bore -33257 ENTERS A PACK BUILDING at 1052,-572 — objects/bdaa42ba4cc030]  -> REFUSED
  -33256                      30.0 m  layer -1  cover 14.4  rise 0.1  passage -  | REFUSED [bore -33256 ENTERS A PACK BUILDING at 978,-645 — objects/bdaa42ba4cc030d]  -> REFUSED
  -33255                      27.6 m  layer -1  cover 0.0  rise 0.02  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -33250                      32.6 m  layer -1  cover 0.0  rise 0.25  passage -  | REFUSED [bore -33250 ENTERS A PACK BUILDING at 976,-750 — objects/bdaa42ba4cc030d]  -> REFUSED
  -30038                      28.9 m  layer -1  cover 0.0  rise 0.0  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -23055                      34.8 m  layer -1  cover 9.7  rise 0.0  passage -  | REFUSED [bore -23055 ENTERS A PACK BUILDING at 1005,-779 — objects/bdaa42ba4cc030]  -> REFUSED
  -22780                      20.2 m  layer None  cover 0.0  rise 0.11  passage -  | REFUSED [bore -22780 PASSES UNDER NOTHING AT GRADE (20 m; cover 0.0 m, no road or]  -> REFUSED
  -11322                      44.9 m  layer -1  cover 0.0  rise 0.98  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -8592                      444.0 m  layer -2  cover 302.0  rise 0.59  passage ce0e807c4d111d0420c899bdf50b41da-KSEA_AR_08.obj @ 2.75 m  | REFUSED [bore -8592 ENTERS AN ENCLOSURE at 803,-552 — way -21 building=transporta]  -> REF
  -8176                       73.6 m  layer -1  cover 0.0  rise 0.75  passage -  | REFUSED [bore -8176 ENTERS A PACK BUILDING at 1394,1132 — objects/101644dc4d8ba5d]  -> REFUSED
  -5118                      789.6 m  layer -1  cover 654.3  rise 7.75  passage -  | BUILT [under the classified cover for 654.3 m]  -> BUILT
  -4946                     1082.6 m  layer -1  cover 1172.3  rise 0.27  passage -  | REFUSED [bore -4946 ENTERS AN ENCLOSURE at 675,-168 — way -22 building=yes: it is]  -> REFUSED
  -4945                     1010.4 m  layer -1  cover 1197.3  rise 2.58  passage -  | REFUSED [bore -4945 ENTERS A PACK BUILDING at 637,-1229 — objects/76e5558d489a49c]  -> REFUSED
  -29331                      51.1 m  layer -1  cover 0.0  rise 0.0  passage -  | BUILT [the bore carries layer -1]  -> BUILT
  -17954                     330.5 m  layer -1  cover 111.3  rise 6.96  passage -  | BUILT [under the classified cover for 111.3 m]  -> BUILT
  -1926                      330.5 m  layer -1  cover 111.4  rise 6.85  passage -  | BUILT [under the classified cover for 111.4 m]  -> BUILT
VERDICT: only the expected bores changed
```

## Step 4 — closing build `tunnel548_KCLT` (harness, tree = dd1ad2204's engine source)

rc 0, body 74d08d3d2cdc (main `sw20_KCLT` 9731f0b70610), ways 1693 -> 1690. Log line:
"bore -32111+-27411 PASSES UNDER AN ELEVATED PACK PART AT GRADE (313 m; classified cover
273.0 m, ground +0.82 m over its mouth chord, layer none) — Terminals/paredes_8_charlotte.obj
(unit:31) stands over its carriageway with 3.0 m of clear space beneath and no pack part at
grade". Frame registered: `frames/tunnel548/tunnel548_KCLT.osm`.

- Site 35.2214617,-80.9460653: sw20 = a vertex of way -10877 `tunnel_ramp` (216.46..220.84 m)
  inside `tunnel_wall` -11683 (220.82..225.51). Branch: no way within 17 m (nearest: pad
  building75, 222.68 m). Patch counts: `tunnel_ramp` strings 24 -> 22, `tunnel_wall` 14 -> 13.
- Site 35.2215158,-80.9458896 (the "tiny arm"): a vertex of pad building75 (222.68 m) in BOTH
  patches. It is the pad's thin arm (kclt546 finding 3), not a structure; unchanged, not this
  lane's.
- Within 200 m of the site: 36 structure nodes removed (21 wall + 17 ramp labels), 0 added,
  0 moved > 0.005 m. The terminal pads and apron `pav14#plateau` there are untouched.
- WHAT THE REFUSED WAY BECOMES: NOTHING. `airport/road_ways.road_ways` (the one at-grade road
  source) skips every `tunnel` way whether or not its bore is built, so -27411 / -32111 mint no
  surface road; no way of either patch carries -27411, -32111 or the approach -27509. The
  ground where the ramp stood is ungraded DEM (mouth DEM 221.60 m beside the pad at 222.68).
- `airside_value_delta` sw20 -> branch (tol 0.01): structure frame 284 -> 248 nodes, 0 moved.
  Row-side: 19 movers, worst 0.05 m; by family runway 4, strip 10, taxi 3, apron 2. THE RUNWAY
  BAR 0 IS NOT MET AT 0.01: two runway-labelled nodes shared with strip / parallel `pav114` at
  35.22475551650,-80.93645381248 (0.05) and 35.22443553439,-80.93642640101 (0.04), ~940 m from
  the bore, and two nodes of 18C/36C at 0.01. The first node is a TWO-STATE vertex across
  builds of unrelated code: 227.08 in sw11 / sw19 / sw20, 227.13 in tunnel522 / kclt546 /
  sw15 / sw16 / sw17 and here (tunnel522 reported the same "4 movers, worst 0.05 m, ~900 m from
  the bore"). Not attributed further (one build per round). Far field also: 12 runway-edge /
  strip vertices only in sw20, 23 only in the branch (18C/36C, 18L/36R, zone-1 strips), none
  within 300 m of the site.
- Census sw20 -> branch: law-true TOTAL 17488 -> 17485; ADJUDICATED 6155 -> 6177 (+22, all
  airside): 22 taxi-chord rows left the withdrawn-law (05aa) class (7445 -> 7423,
  primary_parallel|primary_parallel 2840 -> 2819, stub|stub 935 -> 934) — the same far-field
  parallel; within_shape +2, taxi_box -1, hairline_pair -3, airside_no_step -1.

## Step 5 — suites / ratchets

Full non-Qt once (`pytest --ignore-glob='tests/test_qt_*.py' tests`, includes the v2 suite):
9638 passed / 4 failed / 19 skipped / 1 xfailed / 1 xpassed in 437 s. Three failures were the
new tool's own conventions (console pin before argparse x2, `write_text` without encoding) —
fixed; the fourth, `tests/test_auto_patch_freshness.py::
test_a_relaunched_app_reuses_and_a_rebuild_names_its_key`, is outside this change and passed
on the re-run. Re-run of the affected files (`test_bore_table`, `test_console_encoding`,
`test_windows_text_io`, `test_auto_patch_freshness`, `test_tunnelwitness2`,
`test_no_airport_specific_code`): 341 passed. `tools/ratchets.py`: DUPLICATE RATCHET PASS,
LAYER RATCHET PASS; no size or long-function line for a file this lane touched.

## NOT DONE
- Spec text: `design-surface-spec.md` §34 (12) (5) still reads "(d) NARROWED" (10i (1)); the 10q
  order lives in the code docstring only. Fable authors specs — owed by the spec author.
- Two decisions inside "asked FIRST" the ruling does not spell out (passage over the CROSSING
  witness; passage asked outside the fence too): built as written above, no bore at the nine
  airports depends on either. For the spec author / owner if they matter.
- The "tiny arm" (pad building75's thin strip) — the pad-outline thin-piece question, untouched.
- The two-state vertex at 35.22475551650,-80.93645381248 — not attributed.
- Qt suite not run (no Qt or app code touched).

## RESUME HERE
Everything measured; commit dd1ad2204 (code + twins + tool), then notes + frames row.
