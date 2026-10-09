# seatspec notes — the pad SEAT under RULINGS 2026-10-09d (1) / 08c (4) / 08d (2) / 09c (2a): classes C, D, E, M, B of the pads67 edge read

Lane `seatspec` (Fable, SPEC AUTHOR with probes; no engine code lands). Worktree `.claude/worktrees/seatspec`, branch
`claude/seatspec` = `origin/claude/pads67` 9ab7b36e + `origin/main` f314564d (one conflict, `docs/frames.jsonl`, both sides kept).
Scratch `<scratch>/seatspec/` (`.progress`). Probes: replays of the registered pads67 captures
(`/Users/noah/XPTerrainBuilderData/.harness/frames/pads67/<ICAO>.pkl`, merged head 4b433195), `--workers 9` (valley2 holds the
other half). No airport build.

## Step 0 — orientation (what seats a pad today, read from the code before any probe)

* A pad that FRONTS AIRSIDE (`frontage_roles` = rolled-on roles) and is >= `cluster_pad_min_m2` is a HELD unit pad
  (`planar/platform.platform_split` -> `model.platform.HELD`): stage 1 solves its datum column as a FREE column with the hard
  weld rows (contact = D, `HOLD_RULING`), the hard flat rows (`platform_plane_rows`), the apron's hard caps, and ONE SOFT
  zero-width `Band` at `datum_chosen` = the median of the contacts' pass-1a value (`no_step.hold_interval`,
  `HOLD_DATUM_RULING`). The pair-graph interval and the reach-band intersection are REPORTS (`reach_band`, `reach_isect`); the
  Band on the reach intersection is stated only where it cuts the interval. 08d (2) widening (`weld_floor`) opens one over-cap
  grade on the closing contacts' faces for a misfit under 1 m.
* A pad that fronts ONLY groundside pavement (no platform record) is seated by `pads.pad_frontage_level` (10l): one one-way
  row on the pad's own mean against the groundside face's leaders — the PAD follows the lot/road; §28 mints nothing back
  (`pad_fronts_airside` is the switch). A pad that fronts nothing keeps its DEM datum (09p (3)).
* A gap piece never shares a vertex with a pad (`gap_mint` stand-off); its parts carry PAD STATIONS (`late_stage.late_stations`,
  class `pad`, knife = `groundside_cutback_m` + snap margin) and `gap_follow_rows` binds a part vertex within
  `cap x (d - knife)` of the station; the cut (`classify/gap_terrace.consistent`) groups stations within `cap x d +
  pad_terrace_floor_m` (1 m) and knifes otherwise.

Sidecar read (sw8_HECA): the class-E pads ARE held platforms on `apron:dsf:objpav402` (a standing apron, NOT a gap piece;
faces apron 344 v + junction 66 v + apron 12 v) whose solved `datum` stands far from `datum_chosen`:
building100 101.248 vs 101.242 (reach_band [None, None], 12 of 12 contacts UNREACHED), building101 93.394 vs 96.944
(band [85.73, 99.37]), building104 92.421 vs 94.889, building98 103.502 vs 103.649 (unreached), building64 86.369 vs 88.662,
building164 77.360 vs 78.036. `hard_conflict` pad 101 at HECA (main 27). The class-C pads (building12 / 15 / 8) have NO
platform record; building12 is cluster `unit:43#850` (30,172 m2, 16 bodies, pad_offset_spread 2.39).

## Step 1 — the base solve (HECA, pads67 capture, `--from constraints --workers 9`, 6 min) and the first whys

`<scratch>/seatspec/base/` (`solved.pkl`, `emit/HECA.graded.json`, `rep.json`, `edge_base.json`). The replay's own edge read
reproduces the build's P classes except the gap pieces (no late stage in a `--from constraints` replay: the raw pieces stand
whole, GAP 118 runs): GS-NEAR 15 (build 16) / 515 m, AIR-TOUCH 21 = 21 (232 m), AIR-NEAR 7 = 7, ARMED 1 = 1 (building164),
GS-TOUCH 1 = 1. Stage-2 hard set: 41 of 269,099 rows over 0.02 m, worst 0.1263 m at 30.12086521267,31.41819005825 — the
building75 vertex — on a `pavement_road_cap` row (29ac fallback, v22865 pad rim | v40607 road, 1.04 m apart).

### building75 (HECA), attributed: the generator is `pavement_road_cap`, not `pad_slope_ceiling`

`--why-hard`: 809 violated hard rows (pads 425, road_ramp 112, pavement_ceiling 85, roads 77, apron 45, platform_collar 34,
transverse 14, pavement_road_cap 8, no_step 6, taxi 3). Every pad-tier row on v22865 (14: `platform plane` and 13
`pad_slope_max ceiling`, the other end 100.07–100.86) has v22865 at 99.70 — and the one row that HOLDS v22865 there is the
29ac fallback cap pairing the pad rim vertex with the service-road vertex v40607 at 10 % x 1.04 m = 0.10 m. A hard two-sided
pavement pair over a PAD vertex against the hard plane: the LP relaxes the pad tier (81 rows). pads67's `--drop-generator
pad_slope_ceiling` could not touch it. Arm to run: `--drop-generator pavement_road_cap`.

### building12 (HECA, class C), attributed by `--why-at`: the pad is seated by the SERVICE ROAD it fronts, through the same fallback cap

v26980 (rim 96.11, DEM 106.33): binding rows on it are the pad's own plate (7 `pads` rows); the chain to a fixed terminal is 14
hops / +8.46 m: pad -> `pavement_road_cap` 10 % x 1.0 m -> `service_road#1119` (route3) at 96.03 -> `road_cross_section`
1.5 % x 58 m x 2 (+1.76) -> `road_within_shape` -> apron#189 at 92.24 -> `apron_preference` to the apron at 87.8. So the
landside pad's level is the road's, and the road's is the apron's through the road law (§37). The lot `pav57` 0.66 m away at
+3.29 m has NO row to the pad: `pad_frontage_level` fits the pad to its SENIOR groundside frontage (road > lot in
`precedence.toml`) and reports the lot as a junior residual; §28 mints nothing back (`pad_fronts_airside` false); the fallback
cap did not pair the lot (0.66 m) — only the road (1.0 m).

### building147 (HECA), read: the six `airside_no_step` rows are the census's, the engine holds no such row

`rows_sw8_HECA.json` (pads67's row dump) carries 93 `airside_no_step` rows on ways -10218/-10219 with grade > cap; the six the
lane named are `apron|junction` 1.63–1.76 % vs 1.54–1.58 % over 94–135 m (over by 0.12–0.19 m) at 30.1295–30.1297,
31.4005–31.4007. The engine's violated hard set carries 6 `no_step` rows (listed in `why/hard_all.json`).

## Step 2 — class E attributed (HECA `building100` | `building101` on `apron:dsf:objpav402`)

`<scratch>/seatspec/siteE.py` (every vertex within 25 m of 30.12285430598,31.41820570991 in the solved pickle) and
`rows_on.py` (every constraint row on a vertex): v11868 (building100's contact, 101.25) and v11597 (apron only, 93.56, 6.0 m
away) are BOTH stage-1 vertices and share NO ROW. v11868's apron rows are ring edges to v11867 (29 m) / v11869 (44 m) and
frontage chords to v11870–11872 — every one on the SAME hole ring (building100's rim, all at 101.25). v11597's are ring
edges to v11596 / v11598 (the sheet's own ring), a `frontage_near_miss` to building101's v12276 and the 5 % ceilings.
`constraints/apron.apron_within_shape` enumerates pairs INSIDE one ring (`for ring in [rings, *holes]: for i, j in ring`):
a hole rim never pairs with another hole rim or with the outer ring, so an apron SHEET with the terminal pads as holes
has no within-shape law across it — each hole ring is seated on its own: building100's datum = its contacts' pass-1a median
101.24 (the ring on the apron's DEM plane: `reach_band [None, None]`, 12 of 12 contacts unreached by the pair graph);
building101's contacts chain through `apron_preference` (1 % SOFT, +13.7 m over 1.2 km) to the taxi reach band at 77.21
(`--why-at` on v11604: 12 hops, sum dz +16.18 m). The 6–8 m steps between pads 6 m apart on one sheet (HECA 21 AIR-TOUCH
runs, 17 pads) are the missing rows, not wrong seats: no reach band reaches a hole ring the pair graph cannot see.
Arm E (scratch `armE.py`, generator `apron_cross_ring`): the body-chord rows ALSO between the rings of one face (hole|hole,
hole|outer), cover-tested like the body chords, at the apron cap with its 1 % preference.

## Step 3 — class B attributed (HECA `building164` | `service_road:dsf:objpav405`): §28's priced row against a HARD road-ramp equality

`--why-at` on the pad vertex v11181 (77.36): the pad is airside-led (14 hard plane rows + 14 holds; chain apron#359 ->
`apron_within_shape` -> `apron_preference` +4.3 m over 306 m -> the reach band at 71.12). The road's nearest vertices
v37218 (78.08) / v37221 (78.28), 16–18 m along the rim, carry: 2 `groundside_frontage` rows (§28 ARMED, priced at the
pad's plate weight: joint 0.00 to the pad at 77.36) AND a `road_ramp` `roads.groundside_road ramp to the DEM` Linear with
lo = hi = 81.616 (a HARD equality) plus the `ramp ceiling` Band hi 82.12, 21 `common.roles longitudinal` 10 % rows over
206–254 m and a `pavement_road_cap` 10 % x 52 m to v37219 at 82.24. Two laws name one vertex's level — §28 says the pad's
77.36, §37's ramp says 81.62 — and the hard one wins by 3.5 m of relaxation (the 112 violated `road_ramp` rows); the
vertex lands at 78.08 and the rim edge between the vertices reads +2.70 / +3.33 in the edge read. Mechanism, not yet an
intervention: arm `--drop-generator road_ramp` queued (`chain2.sh`, `armRR`).

## Step 4 — building75 by `--why-vertex 22865`: ONE hop

Binding rows on v22865 (99.71): 8 `groundside_frontage_level` rows (v22865 is a §28 LEADER of the road's frontage vertices
v40601…, pad_flat weight) and ONE `pavement_road_cap` 10 % x 1.0 m to v40607 (`service_road#1887` = `small_roads:-20325`,
99.48) whose level is the hard `roads.groundside_road ramp ceiling` Band. Chain: 1 hop, +0.23 m. The pad rim is welded to
the road by the fallback cap and the road is held by its ramp ceiling; the pad's hard plane loses (81 relaxed pad-tier rows).
Same pair of mechanisms as building164 (step 3): the road's ramp law fixes the road vertex, a two-sided hard pavement row
(the 29ac fallback here, §37's ramp equality there) ties the pad|road pair, and the pad-side law is what the LP relaxes.

## Step 5 — ARM A1: `--drop-generator pavement_road_cap` (HECA base capture, 6 min)

`cmp_arm.py base armA1` + `airside_value_delta --tol 0.02`:
* hard_conflict by tier 175 / 108 / 62 (groundside / pad / taxi) -> 143 / 20 / 59: the pad tier loses 88 of its 108 rows.
* platform datums moved > 0.02 m: 0 of 47 (every held pad keeps its seat; building75's datum 100.859 unchanged).
* airside value delta: runway 0; solve-owned taxi 104 nodes (worst 0.23 m), apron 18 (worst 0.04), strip 197 (0.64);
  row-side "other" 602 nodes, worst 3.60 m at 30.11458199456,31.40540642024 (building15).
* P classes: AIR-TOUCH 21 = 21, AIR-NEAR 7 = 7, GAP 118 -> 117, ARMED 1 -> 2, **GS-NEAR 15 -> 20 runs, 515 -> 1,555 m**
  (building15 | objpav394 now −7.04 m over 307 m of rim; building5 | pol10 −7.33).
READING: the 29ac fallback cap is today's de-facto SEAT of a landside-only pad — a hard two-sided 10 % weld to the nearest
road vertex inside ~1 m; with it gone the §20 senior fit (priced) lets the pad drift metres (building15 3.6 m). So R-F
cannot land alone: the pad|pavement pair across the stand-off must be re-stated as the SEAT relation in the same step —
one-way, HARD, the pad following its one leader (R-C rule 1), the other faces following the pad (R-C rule 2) — and the
fallback excludes every pad vertex. (why-hard on the arm and a why at building15 queued: `whyA1.sh`.)

## Step 6 — ARM E (`armE.py`: `apron_cross_ring`, body chords across the rings of one apron face; HECA, 349 s solve)

Generator: 13 faces with holes, 13,197 cross-ring pairs inside the body gate, 5,695 kept by the face cover (hard apron cap +
1 % preference each). Results (`cmp_arm.py base armE`, `airside_value_delta --tol 0.02`):
* **AIR-TOUCH 21 / 232 m -> 0 / 0; AIR-NEAR 7 / 231 m -> 4 / 46 m**; GS-NEAR 15 = 15, ARMED 1 = 1, GAP 118 -> 116.
* hard_conflict 175 / 108 / 62 -> 180 / 88 / 62 (pad −20: the objpav402 pads' relaxed rows).
* held datums moved > 0.02 m: 32 of 47 — the sheet's pads come to ONE grade: building100 101.25 -> 93.79, building98 103.50
  -> 94.43, building117 101.74 -> 95.12, building68 92.11 -> 85.35, building64 86.37 -> 85.52, building84 / 83 85.59 -> 84.06 /
  84.08, building169 74.63 -> 75.63. Owner site z−DEM: base mean −6.02 (min −8.83 max −1.28) -> arm −8.55 (−8.74 .. −8.28):
  the HIGH pads came DOWN to the sheet's level, the sheet did not come up — its level is the 1 % `apron_preference` trend
  chained 1.2 km to the taxi reach band at 77.21 (the base's building101 chain), so the terminal row now stands 8.5 m under
  the DEM in a cutting, uniformly.
* airside value delta (solve-owned): **runway 113 nodes, worst 0.14 m at 30.13264540548,31.39706615547** (1.7 km from the
  sheet; over 09b's accepted 0.1 m), taxi 2,347 (worst 0.82 m), apron 2,120 (worst 2.17 m at 30.12212,31.42030 = the sheet),
  strip 1,295 (0.85). 5,695 new hard rows re-solve stage 1 whole; the far runway movers are the §61 re-levelling class
  (the owner's open question), not a row of this arm — stated, not resolved.
READING: R-E does what 08c (4) asks (every pad on one sheet seated from one reach interval; no step at any rim) and exposes
the next intent question: the sheet's LEVEL. Today's law lets the 1 % preference trend carry it to the taxiway's level
8.5 m under the terrain; the DEM-plane term does not hold it up. Q2 is rewritten on that.

## Step 7 — the late-stage pair reproduces the build; KCLT `building26` attributed

* Late pair (`--from classify --gap-free --solved-out` 156 s solve; `--late-from` cut 1.5 s: 27 pieces -> 71 parts, 37 knives,
  2,499 stations, 40 merged by the floors; gap_follow 1,599 rows, 15 vertices between disagreeing neighbours, 56 bounds of
  another group's ring declared, lot rows 227; relaxed: follow 19 (worst 1.61 m), last-stage ceiling 13 (2.31 m); fixed
  vertices off their constant 0 of 34,436). Edge read = the build's table: GAP 51 / 339 m (sw8 50 / 339), GS-NEAR 16 / 570,
  AIR-TOUCH 21 / 232, AIR-NEAR 7 / 231, ARMED 1, T28 1, M 255. Of the 53 GAP runs, the nearest part vertex stands
  1.21 / 1.55 / 2.30 / 2.96 m off the rim (p10 / p50 / p90 / max); **16 beyond the 1.95 m follow reach** (mechanism (a)),
  37 inside it (mechanisms (b) the Voronoi group, (c) the floor merge). Arm D (`armD.py`: reach = stand-off 1.45 + snap
  0.5 + 2 identity cells = 2.81 m) queued on the same base (`chain4.sh`).
* KCLT `building26` | `dsf:pol50` (−1.60 across 0.80 m), `--why-at`: pad vertex v16419 (215.97) bound by 3
  `groundside_frontage_level` rows (the pad LEADS the road's frontage vertices v20648…), its plate, its §20 fit; chain ONE hop
  through the §28 row to v20654 (`service_road#1349` = pol50) at 214.17, which is a **PIN**: `roads.coverage_edge join`
  (§37 (9)). The §28 priced row (joint 0.00) loses 1.80 m to a hard pin on the road vertex inside the pad's frontage — the
  same shape as HECA building164 (the road-ramp equality) with a different hard row. R-B generalises to every road law
  that fixes a road vertex inside a seated pad's frontage: the ramp target / ceiling AND the coverage-edge join pin start
  from the first road vertex OUTSIDE the frontage.
