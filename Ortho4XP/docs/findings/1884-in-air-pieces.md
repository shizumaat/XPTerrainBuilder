# #1884: the walled pieces in the air that the TRUE setting would have put on our terrain

Owner RULINGS 2026-11-14a (1): `[placement] terrain_base_over_ground = false`. A walled building with no
carrier is put on our terrain only when its authored base is at or under our ground. A carrier-less piece
whose base stands above our ground keeps its authored height (13y (3), §16 (3): own ground + authored y).
This is the list of the pieces the TRUE setting (13y (2) read literally) would have dropped, for the owner's read.

**Amended by owner RULINGS 2026-11-14c (1)** (`[placement] terrain_base_within_m = 2.0`): a carrier-less walled
building whose rigid base stands **within 2.0 m** above our ground is seated on our terrain like one at or under it
(counted `terrain_carried_within_ground`); above 2.0 m 14a (1) stands. See "After 14c" below for which listed pieces
now go on our terrain; every other listed piece keeps its authored height.

## After 14c (lane lows4)

Measured with the same method (`tools/obj8_split_report.py PLAN --graded G --json`, two arms on lane lows4's code:
`terrain_base_within_m` = 0, the 14a reading, and = 2.0) on every airport whose listed pieces include one whose witness
margin is 2.0 m or less (CYYZ, LPSJ, VQPR; KDEN's units re-read: margins 4.27 / 4.30 / 4.75 m), and at LOWS by
`tools/v2_rebake_replay.py plan` on the lows4a closing build (+47+012 mesh, `--mesh-also` the installed +47+013 DSF)
judged by `tools/drawn_site.py --plan` on the installed +47+012 / +47+013 meshes. Every other listed piece's margin
(the "Base over our ground" column for bodies) is over 2.0 m, so it keeps its authored height.

**5 of the listed pieces now go on our terrain (3 drawn lower, 2 seated the same by a later pass); every other
listed piece keeps its authored height. The nearest miss is LPSJ body 6 (margin 2.35 m).**

| Airport | Piece | Witness margin (m) | Now | Drawn change |
|---|---|---|---|---|
| LOWS | `domiki_lows_13` row 217 b629 (47.74951, 13.00814) | 1.38 (installed mesh; 1.50 on lows3's) | on our terrain | **was 35.1-36.2 m in the air, now base 0.42-1.54 m into the hill** (drawn_site --plan; the low-side foot on a slope, nothing floats). The only body of the 5,533 in the +47+012 plan that changed. |
| VQPR | `airplanes/wreck_plane.obj` dsf:obj941 b0 | 0.96 | on our terrain | lowered 0.97 m |
| LPSJ | `lpsj2019_tps_13.obj` dsf:obj143 body 5 (unit fu:0:148) | 1.96 | on our terrain | lowered 2.91 m (the unit's walls' base y) |
| CYYZ | Terminal1_Parte55 b40 | 1.35 | on our terrain (witness) | 0.00: the 22o connected group seats it the same |
| CYYZ | Terminal1_Parte55 b63 | 1.40 | on our terrain (witness) | 0.00: the 22o connected group seats it the same |
| LPSJ | `lpsj2019_tps_13.obj` dsf:obj143 body 6 (unit fu:0:153) | 2.35 | keeps authored height | none |

Note: for the two LPSJ unit rows the "Base over our ground" column below is the unit's walls' base y (what TRUE lowers
it by), not the witness margin; the margins are 1.96 (body 5) and 2.35 (body 6).

LOWS bars (drawn_site --plan, both arms on the same replay): footed within 0.5 m 3,602 of 3,741 in both arms;
own-ground floats over 0.5 m 97 -> 96 (b629); the hilltop house `domiki_lows_14` b337 and the east hangars' bodies
unchanged (one body changed in all). Still in the air at that site, unchanged by this round and listed for the
owner: `domiki_lows_37` b21 (47.7495, 13.0081 area), own ground with authored y, drawn about 40 m up — the terrain witness never reads it
(no walled part, a structure under it, or a lifted frame), so it is not one of the pieces this list counts; it
needs its own reading.

## How it was counted

`tools/obj8_split_report.py PLAN --graded G --json` (the dry-run object split; the census lane lows2a used) on every
re-seat plan in the shared `Patches/` that has its design surface beside it, run twice: once with
`terrain_base_over_ground = true` (lane lows2a's code, the frozen tree) and once with `false`. A piece is listed
when the TRUE run reads its walls' base clearing our ground (`terrain_carried_over_ground`), with the height the
TRUE setting moves it (`drawn zero true - drawn zero false`, a 0 there means a later pass, usually the 22o
connected group, seats it the same either way). Coverage: 1017 of 1018 plans (EGLW not read: its design
surface is empty and the tool raises on it).

Lane lows2a counted 166 at 14 airports on its corpus; this run counts the numbers below on the current one
(plan vintages differ; CYYZ 77 vs 81, EDDF 15 vs 40). LOWS itself reads 0 on its graded surface (the piece
stands off the +47+012 surface); it is measured on the owner's drawn +47+012 / +47+013 meshes instead
(`tools/v2_rebake_replay.py plan ... --mesh-also`).

## Per airport

| Airport | Pieces counted (body + unit) | Pieces the TRUE setting actually moves | Largest move |
|---|---|---|---|
| CYYZ | 77 | 0 | 0.00 m |
| EDDF | 15 | 14 | 6.77 m |
| ENAT | 1 | 0 | 0.00 m |
| ENTC | 14 | 14 | 6.08 m |
| KBWI | 8 | 0 | 0.00 m |
| KDEN | 3 | 3 | 4.75 m |
| KDLH | 1 | 1 | 4.01 m |
| KTUL | 10 | 0 | 0.00 m |
| LIMC | 3 | 2 | 15.63 m |
| LOWS | 1 | 1 | 36.66 m |
| LPSJ | 2 | 2 | 2.91 m |
| SCEL | 8 | 4 | 8.19 m |
| VQPR | 1 | 1 | 0.97 m |

A piece counted but not moved stands where the TRUE run would have put it anyway (its final seat comes from a
later pass: a connected group, a terrain-adapted member). Unit-level pieces (a whole footprint unit's datum) are
listed by the bodies of the unit that moved.

## The pieces

Base over our ground = how far the rigid authored row would stand the walls' base above our ground (the witness
margin); for a unit, the height the TRUE setting would lower it. Moved = what the TRUE setting does to it (negative =
down; 0 = a later pass seats it the same either way). With the ruling in force a moved piece keeps §16 (3)'s seat:
its base drawn about `base y` above the ground under its own footprint.

**Read first — LOWS `domiki_lows_13` b629 (14a reading; RESOLVED by 14c, see above)**: its rigid base would stand 1.50 m over our ground, so the ruling refuses
the terrain seat; §16 (3) then writes it on its own ground with its authored y +35.68 kept — the house is drawn
**35.1 m in the air** (drawn_site --plan, owner meshes). The author raised it on HIS terrain (the domiki pack's 48
houses share one datum 435.51 m). Under the TRUE setting it sits on the hill (0.42 m). 'Keeps its authored height'
read as the RIGID row (frame zero + y) would draw it 1.50 m up; §16 (3) reads it as own ground + y. Owner's call.

| Airport | Object | DSF row | Body | Lat, lon | Where | Base over our ground (m) | base y (m) | Moved by TRUE (m) |
|---|---|---|---|---|---|---|---|---|
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b11_75e6e3af.obj | 43.685842, -79.616245 | 1677 m N of runway end 33R | 21.12 | +14.84 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b13_e815b5bd.obj | 43.685775, -79.616084 | 1668 m N of runway end 33R | 20.79 | +14.51 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b53_a0401acf.obj | 43.685144, -79.611450 | 1342 m NW of runway end 24R | 20.36 | +14.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b8_7e2ff237.obj | 43.685402, -79.616367 | 1629 m N of runway end 33R | 20.20 | +13.92 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b59_f06b4465.obj | 43.685008, -79.611036 | 1305 m NW of runway end 24R | 19.98 | +13.70 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b12_efab32fc.obj | 43.685334, -79.616185 | 1620 m N of runway end 33R | 19.87 | +13.59 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b60_8e3e9ec8.obj | 43.684802, -79.611047 | 1295 m NW of runway end 24R | 19.78 | +13.50 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b52_d37f58c2.obj | 43.685361, -79.611421 | 1351 m NW of runway end 24R | 19.66 | +13.38 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b66_76bb39d1.obj | 43.684660, -79.610644 | 1259 m NW of runway end 24R | 19.40 | +13.12 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b68_efe80671.obj | 43.684460, -79.610644 | 1249 m NW of runway end 24R | 19.20 | +12.92 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b16_f97bdb81.obj | 43.682859, -79.614037 | 1340 m N of runway end 33R | 18.90 | +12.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b17_5ff677b4.obj | 43.682954, -79.613897 | 1351 m N of runway end 33R | 18.42 | +12.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b46_e464c06c.obj | 43.685417, -79.611853 | 1385 m NW of runway end 24R | 18.36 | +12.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b9_a8616f2e.obj | 43.684955, -79.616308 | 1579 m N of runway end 33R | 18.30 | +12.98 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b50_607a9a5a.obj | 43.685751, -79.611543 | 1382 m NW of runway end 24R | 17.97 | +11.69 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b48_84b66edf.obj | 43.685702, -79.611654 | 1386 m NW of runway end 24R | 17.96 | +11.68 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b43_f82c5409.obj | 43.685880, -79.612105 | 1428 m NW of runway end 24R | 17.47 | +11.19 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b39_41061610.obj | 43.685683, -79.612353 | 1434 m NW of runway end 24R | 17.44 | +11.16 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b15_f9d05e64.obj | 43.683324, -79.614002 | 1392 m N of runway end 33R | 17.40 | +10.06 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b45_21082897.obj | 43.686132, -79.611896 | 1428 m NW of runway end 24R | 17.22 | +10.94 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b30_393c4270.obj | 43.685926, -79.612874 | 1484 m NW of runway end 24R | 16.84 | +10.56 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b38_fffcd65a.obj | 43.686294, -79.612348 | 1468 m NW of runway end 24R | 16.77 | +10.49 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b23_80acabb6.obj | 43.686570, -79.613420 | 1558 m NW of runway end 24R | 16.54 | +10.26 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b14_f4de342b.obj | 43.687350, -79.613896 | 1636 m NW of runway end 24R | 16.27 | +9.99 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b24_a9ea6ed5.obj | 43.686167, -79.613397 | 1534 m NW of runway end 24R | 16.12 | +9.84 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b61_b2408dc8.obj | 43.684990, -79.610897 | 1294 m NW of runway end 24R | 15.80 | +9.52 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b56_26ec0186.obj | 43.685399, -79.611157 | 1335 m NW of runway end 24R | 15.18 | +8.90 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b18_0eca59cc.obj | 43.686340, -79.613772 | 1570 m NW of runway end 24R | 15.06 | +8.78 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b29_cee3e913.obj | 43.686388, -79.612853 | 1508 m NW of runway end 24R | 14.38 | +8.10 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b67_a4b47bee.obj | 43.684735, -79.610615 | 1261 m NW of runway end 24R | 14.16 | +7.88 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b26_a7949a19.obj | 43.685756, -79.613300 | 1505 m NW of runway end 24R | 12.86 | +6.58 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b34_ac7c3881.obj | 43.685598, -79.612720 | 1455 m NW of runway end 24R | 12.86 | +6.58 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b22_17c7cdaf.obj | 43.687617, -79.613399 | 1620 m NW of runway end 24R | 12.81 | +6.53 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b82_50515c57.obj | 43.685604, -79.609305 | 1221 m NW of runway end 24R | 12.77 | +4.99 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b37_6260a66e.obj | 43.686222, -79.612337 | 1463 m NW of runway end 24R | 12.41 | +6.13 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b65_88f7b153.obj | 43.685048, -79.610771 | 1289 m NW of runway end 24R | 12.39 | +6.11 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b36_7e7dc7e0.obj | 43.686019, -79.612367 | 1454 m NW of runway end 24R | 12.16 | +5.88 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b47_7d00ed88.obj | 43.686056, -79.611702 | 1410 m NW of runway end 24R | 11.36 | +5.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b55_1a84984b.obj | 43.685729, -79.611193 | 1356 m NW of runway end 24R | 11.36 | +5.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b58_8809dd1f.obj | 43.685915, -79.611114 | 1362 m NW of runway end 24R | 11.36 | +5.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b71_3864e7fc.obj | 43.685793, -79.610517 | 1314 m NW of runway end 24R | 11.36 | +5.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b76_beaf7424.obj | 43.685502, -79.609992 | 1261 m NW of runway end 24R | 11.36 | +5.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b78_e4fb9dbc.obj | 43.685689, -79.609914 | 1267 m NW of runway end 24R | 11.36 | +5.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b32_7d7a3865.obj | 43.686142, -79.612767 | 1488 m NW of runway end 24R | 11.32 | +5.04 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b42_1850babf.obj | 43.685501, -79.612116 | 1408 m NW of runway end 24R | 11.13 | +4.85 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b72_c61ebc9d.obj | 43.684741, -79.610435 | 1248 m NW of runway end 24R | 9.96 | +3.67 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b74_d1d36dca.obj | 43.684394, -79.610247 | 1217 m NW of runway end 24R | 9.96 | +3.67 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b28_a1d07a5e.obj | 43.687954, -79.612990 | 1614 m NW of runway end 24R | 9.81 | +3.53 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b21_2a202b18.obj | 43.686427, -79.613599 | 1562 m NW of runway end 24R | 9.74 | +3.46 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b25_0a9b067c.obj | 43.686285, -79.613349 | 1537 m NW of runway end 24R | 9.59 | +3.31 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b20_2c3ff70f.obj | 43.687043, -79.613574 | 1596 m NW of runway end 24R | 9.36 | +3.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b44_e51fabd4.obj | 43.686232, -79.611954 | 1438 m NW of runway end 24R | 9.36 | +3.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b51_1526e2c8.obj | 43.686084, -79.611467 | 1396 m NW of runway end 24R | 9.34 | +3.06 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b10_d271f599.obj | 43.687355, -79.616225 | 1645 m SE of runway end 23 | 8.57 | +2.29 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b7_ffde149d.obj | 43.685638, -79.616494 | 1656 m N of runway end 33R | 8.36 | +2.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b33_0848f908.obj | 43.684851, -79.612797 | 1423 m NW of runway end 24R | 8.36 | +2.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b41_27a1b984.obj | 43.684873, -79.612177 | 1380 m NW of runway end 24R | 8.36 | +2.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b49_609d663d.obj | 43.684888, -79.611679 | 1344 m NW of runway end 24R | 8.36 | +2.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b54_96f7682b.obj | 43.684900, -79.611226 | 1313 m NW of runway end 24R | 8.36 | +2.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b70_1f8e89c9.obj | 43.684963, -79.610566 | 1270 m NW of runway end 24R | 8.36 | +2.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b77_6521851d.obj | 43.685030, -79.609954 | 1231 m NW of runway end 24R | 8.36 | +2.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b81_90f7cd5e.obj | 43.685058, -79.609336 | 1190 m NW of runway end 24R | 8.36 | +2.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b83_fde8e145.obj | 43.685043, -79.608717 | 1147 m NW of runway end 24R | 8.36 | +2.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b79_e87db5a9.obj | 43.685751, -79.609667 | 1254 m NW of runway end 24R | 7.98 | +1.70 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b64_e91eaa92.obj | 43.686220, -79.610761 | 1357 m NW of runway end 24R | 7.97 | +2.60 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b80_567b3fd2.obj | 43.686032, -79.609550 | 1265 m NW of runway end 24R | 7.93 | +1.65 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b57_a539c17f.obj | 43.685495, -79.611171 | 1341 m NW of runway end 24R | 7.89 | +1.61 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b75_45b59eb4.obj | 43.686110, -79.610160 | 1310 m NW of runway end 24R | 7.65 | +2.13 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b31_9a99bfdb.obj | 43.688348, -79.612693 | 1622 m NW of runway end 24R | 7.42 | +1.14 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b69_cf1d05ac.obj | 43.685607, -79.610594 | 1308 m NW of runway end 24R | 6.94 | +5.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b6_4bb27985.obj | 43.687510, -79.616921 | 1588 m SE of runway end 23 | 6.80 | +0.52 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b62_bb0994b9.obj | 43.685943, -79.610877 | 1347 m NW of runway end 24R | 5.77 | +2.61 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b73_e772ec4a.obj | 43.685832, -79.610277 | 1300 m NW of runway end 24R | 5.31 | +2.15 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b27_1dbf6691.obj | 43.686609, -79.613184 | 1544 m NW of runway end 24R | 5.20 | +3.08 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b35_f7d0d62c.obj | 43.688524, -79.612354 | 1613 m NW of runway end 24R | 4.74 | +0.97 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b63_67b4c5c8.obj | 43.685530, -79.610885 | 1324 m NW of runway end 24R | 1.40 | +0.67 | +0.00 |
| CYYZ | `Objetos/CA_CYYZ_Terminal/CA CYYZ Terminal 1/CA_CYYZ-Terminal1_Parte55.obj` | dsf:obj6096 | CA_CYYZ-Terminal1_Parte55__b40_d8a0ba0f.obj | 43.688491, -79.612120 | 1596 m NW of runway end 24R | 1.35 | +1.11 | +0.00 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b5_333f5f1a.obj | 50.051324, 8.563748 | 1798 m NW of runway end 25C | 2.09 | +6.75 | -6.77 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b23_26c664bf.obj | 50.049970, 8.566000 | 1594 m W of runway end 25C | 5.11 | +6.75 | -6.76 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b20_81ed1cb9.obj | 50.050051, 8.565434 | 1635 m W of runway end 25C | 4.83 | +6.75 | -6.76 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b10_24bf630d.obj | 50.052552, 8.563869 | 1847 m NW of runway end 25C | 3.09 | +6.75 | -6.75 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b6_875ef764.obj | 50.051154, 8.563869 | 1783 m W of runway end 25C | 2.69 | +6.75 | -6.75 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b12_4b7adef5.obj | 50.051969, 8.563662 | 1832 m NW of runway end 25C | 6.02 | +6.75 | -6.74 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b14_a1b2b53c.obj | 50.050003, 8.565716 | 1614 m W of runway end 25C | 5.80 | +6.75 | -6.74 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b18_e9a84e5a.obj | 50.050004, 8.567172 | 1516 m W of runway end 25C | 6.22 | +6.75 | -6.73 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b28_2d5f7b52.obj | 50.050114, 8.567712 | 1485 m W of runway end 25C | 5.62 | +6.75 | -6.73 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b16_119fe0ae.obj | 50.049954, 8.566288 | 1574 m W of runway end 25C | 5.72 | +6.75 | -6.72 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b8_ef50d502.obj | 50.050595, 8.564255 | 1735 m W of runway end 25C | 3.21 | +6.75 | -6.70 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b30_2e1e1a20.obj | 50.050052, 8.567448 | 1500 m W of runway end 25C | 6.42 | +6.75 | -6.69 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b27_366e92e6.obj | 50.049954, 8.566579 | 1554 m W of runway end 25C | 5.70 | +6.75 | -6.69 |
| EDDF | `Apt Buildings/Apron Equip/FRA_Terminal_Roads_Streetlights.obj` | dsf:obj4216 | FRA_Terminal_Roads_Streetlights__b24_71c01437.obj | 50.050177, 8.567971 | 1470 m W of runway end 25C | 4.61 | +6.75 | -6.65 |
| EDDF | `Apt Buildings/Apron Equip/Jetways_Connections_Details.obj` | dsf:obj4215 | Jetways_Connections_Details__b12_a7c5f602.obj | 50.050077, 8.583822 | 594 m N of runway end 25C | 4.62 | +4.62 | +0.00 |
| ENAT | `objects/ENAT_Terminal_Tile_02.obj` | dsf:obj64 | ENAT_Terminal_Tile_02__b0_6bfe2d48.obj | 69.976859, 23.350666 | 551 m S of runway end 11 | 3.05 | +2.87 | +0.00 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b22_624e8b46.obj | 69.671274, 18.910912 | 178 m S of runway end 36 | 6.68 | +6.06 | -6.08 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b23_3fa294a7.obj | 69.671021, 18.910713 | 207 m S of runway end 36 | 7.61 | +6.06 | -6.08 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b21_d94aa685.obj | 69.670772, 18.910548 | 235 m S of runway end 36 | 8.41 | +6.04 | -6.06 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b8_093b9907.obj | 69.671557, 18.910989 | 147 m S of runway end 36 | 5.63 | +6.03 | -6.04 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b27_e58a6e0c.obj | 69.671540, 18.911199 | 147 m S of runway end 36 | 5.64 | +6.03 | -6.04 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b31_b715d7d9.obj | 69.671527, 18.911367 | 147 m S of runway end 36 | 5.64 | +6.03 | -6.04 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b20_f8d1f0fb.obj | 69.671549, 18.911094 | 146 m S of runway end 36 | 5.63 | +6.03 | -6.04 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b4_3ed2cb42.obj | 69.671571, 18.910819 | 147 m S of runway end 36 | 5.62 | +6.03 | -6.04 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b19_7abd7f0d.obj | 69.670519, 18.910379 | 264 m S of runway end 36 | 8.53 | +5.32 | -5.34 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b26_a87ce189.obj | 69.670263, 18.910320 | 293 m S of runway end 36 | 8.53 | +4.44 | -4.46 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b9_482f8f5b.obj | 69.670271, 18.910215 | 292 m S of runway end 36 | 8.47 | +4.44 | -4.46 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b3_753e9daa.obj | 69.670293, 18.909940 | 293 m S of runway end 36 | 8.33 | +4.44 | -4.46 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b30_e9a946f9.obj | 69.670249, 18.910488 | 293 m S of runway end 36 | 8.62 | +4.44 | -4.46 |
| ENTC | `objects/ALS.obj` | dsf:obj2618 | ALS__b7_7fcbe915.obj | 69.670280, 18.910109 | 293 m S of runway end 36 | 8.42 | +4.44 | -4.46 |
| KBWI | `Buildings/Terminal/KBWI_WIndows.obj` | dsf:obj6074 | KBWI_WIndows__b6_fb85a2e6.obj | 39.187267, -76.676144 | 547 m NE of runway end 15R | 19.72 | +18.61 | +0.00 |
| KBWI | `Buildings/Terminal/KBWI_WIndows.obj` | dsf:obj6074 | KBWI_WIndows__b9_ffdcbd16.obj | 39.187554, -76.675652 | 599 m NE of runway end 15R | 19.71 | +18.61 | +0.00 |
| KBWI | `Buildings/Terminal/KBWI_WIndows.obj` | dsf:obj6074 | KBWI_WIndows__b5_dfd975eb.obj | 39.187796, -76.676642 | 535 m NE of runway end 15R | 19.67 | +18.61 | +0.00 |
| KBWI | `Buildings/Terminal/KBWI_WIndows.obj` | dsf:obj6074 | KBWI_WIndows__b7_6cb3f630.obj | 39.188079, -76.676146 | 588 m NE of runway end 15R | 19.64 | +18.61 | +0.00 |
| KBWI | `Buildings/Terminal/KBWI_WIndows.obj` | dsf:obj6074 | KBWI_WIndows__b12_fe60a202.obj | 39.186500, -76.674659 | 645 m E of runway end 15R | 16.66 | +18.61 | +0.00 |
| KBWI | `Buildings/Terminal/KBWI_WIndows.obj` | dsf:obj6074 | KBWI_WIndows__b10_d60e0201.obj | 39.186222, -76.675160 | 598 m E of runway end 15R | 16.60 | +18.61 | +0.00 |
| KBWI | `Buildings/Terminal/KBWI_WIndows.obj` | dsf:obj6074 | KBWI_WIndows__b11_5f3ef912.obj | 39.187029, -76.675158 | 618 m E of runway end 15R | 16.19 | +18.61 | +0.00 |
| KBWI | `Buildings/Terminal/KBWI_WIndows.obj` | dsf:obj6074 | KBWI_WIndows__b8_bb60ba92.obj | 39.186747, -76.675654 | 568 m E of runway end 15R | 16.09 | +18.61 | +0.00 |
| KDEN | `Objects/Jetways/Bridge_Old_Len_5.obj` | dsf:obj47177 | Bridge_Old_Len_5__b0_5f855286.obj | 39.853604, -104.670794 | 1244 m SW of runway end 17R | 4.75 | +4.75 | -4.75 |
| KDEN | `Objects/Landside/Signs/HS_30m_Airlines.obj` | dsf:obj45739 | body 1 | 39.837893, -104.671869 | 1077 m E of runway end 25 | 4.30 |  | -4.30 |
| KDEN | `Objects/Landside/Signs/HS_30m_Bridge_Directions.obj` | dsf:obj31317 | body 2 | 39.842177, -104.673628 | 897 m E of runway end 25 | 4.30 |  | -4.30 |
| KDLH | `Jetways-Steel/JetwayCon-05m-steel.obj` | dsf:obj147 | JetwayCon-05m-steel__b0_3133f52b.obj | 46.838860, -92.181388 | 303 m SW of runway end 27 | 3.97 | +4.00 | -4.01 |
| LIMC | `objects/flegs-FenchR_0080.obj` | dsf:obj13244 | flegs-FenchR_0080__b1_c1ad5ff9.obj | 45.627267, 8.711899 | 2092 m S of runway end 17R | 15.39 | +15.39 | -15.63 |
| LIMC | `objects/flegs-FenchR_0080.obj` | dsf:obj13244 | flegs-FenchR_0080__b0_183d9f90.obj | 45.627307, 8.711899 | 2088 m S of runway end 17R | 15.39 | +15.39 | -15.39 |
| LIMC | `objects/terminal-Extension-Dr_limc_Jetway.obj` | dsf:obj14300 | terminal-Extension-Dr_limc_Jetway__b6_5c44bf14.obj | 45.627444, 8.713987 | 2037 m S of runway end 17R | 3.69 | +3.69 | +0.00 |
| LOWS | `objects/domiki_lows_13.obj` | row 217 | domiki_lows_13 b629 | 47.749508, 13.008141 | 3623 m S of runway end 33 (the hillside houses south of the field, 55 m from the hilltop house domiki_lows_14) | 1.50 | +35.68 | -36.66 |
| LPSJ | `objects/lpsj2019_tps_13.obj` | dsf:obj143 | body 5 | 38.665340, -28.169158 | 423 m NW of runway end 31 | 2.91 |  | -2.91 |
| LPSJ | `objects/lpsj2019_tps_13.obj` | dsf:obj143 | body 6 | 38.665171, -28.168869 | 394 m NW of runway end 31 | 1.81 |  | -1.81 |
| SCEL | `OBJETOS_NEW/Luz_Sobre_Calle_02.obj` | dsf:obj1246 | Luz_Sobre_Calle_02__b1_931850c9.obj | -33.399641, -70.793618 | 1057 m NE of runway end 35L | 8.23 | +8.18 | -8.19 |
| SCEL | `OBJETOS_NEW/Luz_Sobre_Calle_02.obj` | dsf:obj1246 | Luz_Sobre_Calle_02__b0_1462b812.obj | -33.399624, -70.793172 | 1089 m NE of runway end 35L | 8.07 | +8.18 | -8.18 |
| SCEL | `OBJETOS_NEW/Espigon_E_Interior.obj` | dsf:obj439 | Espigon_E_Interior__b0_296ce458.obj | -33.403386, -70.797887 | 484 m NE of runway end 35L | 4.58 | +4.58 | -4.58 |
| SCEL | `OBJETOS_NEW/Espigon_F_Interior.obj` | dsf:obj441 | Espigon_F_Interior__b0_4d043f6a.obj | -33.403143, -70.791602 | 970 m NW of runway end 35R | 4.58 | +4.58 | -4.58 |
| SCEL | `OBJETOS_NEW/Espigon_C_Interior.obj` | dsf:obj438 | Espigon_C_Interior__b0_c7955b73.obj | -33.400180, -70.798086 | 754 m NE of runway end 35L | 4.58 | +4.58 | +0.00 |
| SCEL | `OBJETOS_NEW/Espigon_D_Interior.obj` | dsf:obj440 | Espigon_D_Interior__b0_140baca6.obj | -33.399988, -70.791764 | 1165 m NE of runway end 35L | 4.58 | +4.58 | +0.00 |
| VQPR | `airplanes/wreck_plane.obj` | dsf:obj941 | wreck_plane__b0_aaa2e382.obj | 27.396232, 89.427391 | 362 m NW of runway end 33 | 0.96 | +0.95 | -0.97 |
