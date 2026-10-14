# lotroads — notes (RULINGS 2026-10-14a (2) "roads inside a lot are the lot"; 14c (3); issue #609)

Branch `claude/lotroads` (worktree `.claude/worktrees/lotroads`) off main ef73ed27a (= sw28 engine a95f77932 + rulings).
Scratch `<scratch>/lotroads/`: captures `SPJC.pkl`, `KCLT.pkl` (this base); `two.sh NAME ICAO [TREE]` (gap-free base +
late stage replay pair), `clsites.py` (cells near sites), `plot.py` (PIL map of cells + ways), `faces_ll.py`,
`transect.py` (z / DEM along a ray), `siterows.py` (census rows near sites), `approach.py` (steepest 8-12 m pair on
every face welded to a pad and one ring further, read off an emitted patch), `gapcmp.py`.

## Consumer census — where a mapped road is minted, and what a road inside / along a lot is today

| pass | what it mints / reads | a road INSIDE a lot | a road ALONG (edge-sharing) a lot | after this lane |
|---|---|---|---|---|
| `classify/roles` §27 + demotion ladder | lots (`parking_lot`, `groundside_pavement`) from pavement pages | — | — | unchanged |
| `roles` service corridors (1206 truck chains) | `service_road` `route<i>` = corridor − pavement − pads | not minted (pavement subtracted) | a strip beside the lot, road law | unchanged (apt.dat network, senior; out of scope) |
| `roles._cut_back_groundside` (1st, `hold=True`) | lot vs pad: weld / held terrace / gapped | — | — | unchanged (lots beside building24 stay `pad_held`) |
| `ribbon_mint.mint_osm_ribbons` (stage-1 patch ribbons) | ribbon − every cell − pad knives | not minted (`occupied`) | a ribbon strip beside the lot, ROAD law (stage 1) | **unchanged — see Q1** |
| `gap_mint.mint_gap_pieces` (§53, last stage) | gap pieces off every standing cell | — | — | unchanged |
| `ribbon_mint.mint_pad_roads` (#609 pad roads, last stage) | ribbon − every cell (no knife) | not minted | a PAD ROAD strip welded to the pad and the lot — SPJC `-6132#1`: 24.36 at the rim, 28.1 at the lots across 7 m (#658 rows) | **the stretch along the lot is minted as THE LOT** (`classify/lot_roads`): the lot's role/kind, ref `<lot>#road<k>`, evidence `lot_road` / `lot_of` / `lot_road_pad`; no `pad_road` flag ⇒ a STAGE-1 cell (`stage_one_map.gap_free` keeps it) |
| `roles._cut_back_groundside(hold=False, only=new)` | the pad roads' touch witness | — | — | reads the lot strips too: one touching a pad is WELDED (13a (3) "ramp it"); the lot it continues is welded THROUGH it |
| `pad_road_exit.extend_pad_roads` (late stage) | exits walked off pad roads / pad edges | — | an exit along a lot stays road | unchanged (exits leave the patch; not read) |
| `PlanarMap.pad_roads`, `pad_ramp`, `pad_road_reach` (13d/e/f) | faces flagged `pad_road` | — | — | lot strips are not pad roads: no ramp row, no 13e release, never a pad shift reason |
| `late_followers` / `gap_follower_faces` | ribbons (`is_osm_ribbon_ref`) follow | — | — | lot strips are not ribbons: they stand (stage 1) |
| census / `check_grade` | role caps | — | — | lot strips judged as their lot's role (`groundside_pavement` 10 %, `parking_lot` 5 %) |
| refs joined on `ref.split("#")[0]` (publication, structures, gap_follow) | — | — | — | a lot strip joins its lot |

THE WITNESS (`lot_roads.lot_stretches`): the road's AXIS within the ribbon half-width + one identity cell
(`pad_touch.touch_limit_m`) of a standing lot, outside it, over ≥ 2 lane widths. A road meeting a lot end-on
(≈ one half-width inside the band) and a road across open ground between two lots stay road. Lots = standing
`parking_lot` / `groundside_pavement` cells that are not §53 gap pieces; NOT transitive (a road beside a lot strip is
not lot: a dual carriageway beside a lot would otherwise become lot whole).

## Q1 (owner) — the patch's own ribbons

Arm A (both mint passes read the witness, commit 30302ea22, harness `lotroads_<ICAO>` vs sw28): the patch ribbons'
lot strips change STAGE 1 and stage 1 moves airside — HECA apron `dsf:objpav402` 0.62 m (189 nodes), 30 pads up to
0.87 m (`building4` landing collars, `building101` 0.45 m), junction / taxi strips ≤ 0.05 m (20 strips on lot
`dsf:pol10`, from primary `big_roads` ways along it); KCLT `building59` −0.54 m, `building67` +0.27 m, runway 18L/36R
2 nodes 0.05 m (21 strips, mostly 1-10 m² slivers). SHIPPED: arm B, the pad roads only (d08b9e868).

## 14c (3) — the paved approaches to KCLT's garages (building86 / 88 / 90)

No lot, gap piece or slab stands within 30 m of the three garages in the classification — every paved face welded
to them is a mapped-road ribbon (pad road). The witness of 14a (2) converts none of them (none runs along a lot).
Steepest 10 m (patch `lotroads_KCLT`, identical to sw28 at all 18 approach ways): see the lane report.
KCLT approach ways, steepest 10 m on the patch (`road_course_profile --on-patch`, lotroadsb = sw28 byte for byte):
`-24655` 10.3 % at 35.225785, −80.944365 (garage building88/90 side; its tip 1 m beyond building90's lip reads 45.4 %
at the patch edge, 35.225615, −80.945279 — the pruned dead end of round 5); `-16664` 9.1 % at 35.224370, −80.945166
(building86); `-30417` 7.9 % at 35.225809, −80.943321; `-24658` 7.5 % at 35.225825, −80.943008; `-24659` 7.2 % at
35.224139, −80.943324; every other approach ≤ 6.2 %. Face pairs 8-12 m apart (`approach.py`): `-8194` 18.4 % at
35.2238051, −80.9428249 → 35.2237330, −80.9428084 (one ring off building88; its centreline reads 4.0 %: a
transverse pair across the face, not the course). NOT DONE: an implementation of 14c (3) (b) — at KCLT's garages
no non-road pavement leads to an entry, so the instrument finds no case; the owner's "very steep paved areas" need
a site (lat/lon) to attribute (pack objects / draped pavement outside the model are rampfoot669's or unmodelled).

## Closing proof (arm B d08b9e868, harness `lotroadsb_<ICAO>` vs `/tmp/harness/sw28_<ICAO>`)

| airport | body | airside row-side / solve-owned / structures movers | rebake | lot / road refs > 0.05 m |
|---|---|---|---|---|
| SPJC | changed | 0 / 0 / 0 | counts only (stock 3291→3290, unresolved 0→1: the library index, as rounds 5-6) | lots `dsf:pol35` 3.97, `pol36#1` 3.93, `pol36` 3.74, `pol37` 3.67, `pol37#1` 3.35 (all down to the pad: 24.36-24.39 at the rim); 200 service-road refs (worst `-6163#2` 3.89) — the parking aisles east of building24 follow the lot down |
| HECA | IDENTICAL | 0 | identical | none |
| KCLT | IDENTICAL | 0 | identical | none (garages 223 m unchanged) |
| KASE | IDENTICAL | 0 | identical | none |
| OTHH | changed | 0 / 0 / 0 | identical | `gap:13` 0.14 m at 25.2512508, 51.6200956 and `gap:3` 0.02 m — no lot strip at OTHH (no ref added or removed): unattributed late-stage variance |

SPJC census (law-true, sw28 → lotroadsb): total 3826 → 3793; airside 2932 → 2934 (hairline_pair +2, 0.00 m);
groundside 787 → 750 (road_cross_section 80 → 69, mid_edge_step 40 → 21, pavement_over_road_cap 20 → 6,
within_shape 24 → 27, hairline 531 → 537, hard_conflict 67 → 68). At −12.0220780, −77.1078060: 63 → 30 rows, only
hairlines left (the `building|service_road` cross-fall 1.45 m and pavement_over_road_cap 3.74 m rows gone). At
−12.0238250, −77.1070160: the `building|service_road` rows 3.74 m → 0.27 m; road_cross_section service|service 22
(2.26 m) → 27 (1.57 m) on the pad roads between the pad and pol37's south end (`-10971`, `-1186#1`, `-6213#1`:
their stretch along the lot is under two lane widths). Last-stage relaxations: worst 3.53 m → 1.46 m.

THE LOT AT building24 (14a (2) site): flush with the pad at 24.36-24.39 at the shared rim; it climbs to 26.2-27.1 m
at its east edge (`pol37` 26.22, `pol36#1` 26.38, `pol36` 26.50, `pol35` 27.06) against DEM 28.2-28.5 — it does NOT
reach the terrain within its width (8-15 m at ≤ 10 %, the `groundside_pavement` cap); the aisles beyond (pad roads)
carry the climb at ≤ 10 % (`-5577` 24.84 → 28.18 over ~36 m) and the ground between them meets them under the
adjacent-ground law (no terrace declared).
