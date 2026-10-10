# apron523 — an apron follows its yielded runway (RULINGS 2026-10-10j, #523)

Lane `claude/apron523`, base main 6b6a4b9b9. Capture `frames/kase523/KASE.pkl` (lane kase523),
replayed `--from constraints --emit --verify --workers 6 --null-change` (18 s per arm). One tree,
one capture. Base replay == kase523's base (verify 4529, taxi_box 660, within_shape 2376).

## Which airports have a §50-yielded runway (sidecars sw11_*, sw12_HECA, othh513_OTHH)

Only KASE (15/33: table 1.5 %, built 2.023 %, two CIFP thresholds; 31 taxi faces yielded).
CYXY, HECA, KCLT, NLWF, OTHH, SPJC: 0 yielded runways, 0 `taxi_yield_caps`.

## Probe (scratch edits, reverted) — the candidates on the KASE capture

Tie witness in every arm: 30ah's own (an apron face holding a station of a route-network
component that a yielded runway's ridge touches) — KASE apron faces 23 and 58 (pav7, the 1.5 km
sheet); the cap `taxi_cap_for(1.5 %, 2.023 %)`; the 04t-2 edge portions read the same cap.

| arm | what | A → runway corner (29.4 m) | apron edge → corner | v2 verify rows | census adjudicated airside | hard set | null-change |
|---|---|---|---|---|---|---|---|
| base | main | 1.45 m, 4.95 % | 4.65 % | 4529 | 2518 | NOT settled (0.054 m; 2 runway rows in a law conflict, §7 STOP line) | 0/0 |
| cap only | cap 2.023 %, preference 1 % at `law` 300 | 1.25 m, 4.26 % | 3.96 % | 4409 | 2558 | not settled 0.021 | 0/0 |
| (a) | preference = cap (no flat tier on a tied apron) | 0.39 m, 1.34 % | 1.62 % | 2065 | 1250 | settled | 0/0 |
| (b) w=30 | preference 1 %, priced 30 on tied faces | 0.62 m, 2.10 % | 2.16 % | 2902 | — | settled | 0/0 |
| (b) w=10 | priced 10 | 0.57 m, 1.93 % | 2.02 % | 2488 | — | settled | 0/0 |
| (b) w=3 | priced 3 (= `ground_datum`, law/100) | 0.39 m, 1.33 % | 1.61 % | 2103 | 1321 | settled | 0/0 |
| (b) w=1 | priced 1 | 0.40 m, 1.35 % | 1.62 % | 2078 | — | settled | 0/0 |
| (c) | preference 1 % ACROSS the runway axis, the runway's grade ALONG it, priced 300 | 0.40 m, 1.37 % | 1.64 % | 2082 | 1254 | settled | 0/0 |

Census rows on the owner pair (taxi_box / airside_no_step `primary_parallel|runway`, d 29.385 m):
base 4.93 % vs 2.50 / 2.63 %; cap only 4.25 %; (a), (b) w=3, (c): NO row on the pair.

| (b) w=0.3 | priced 0.3 | 0.40 m, 1.35 % | 1.63 % | 2064 | — | settled | 0/0 |
| (b) w=0.03 LANDED | priced 0.03 (law / 10^4); tie also by contact (face 22) | 0.39 m, 1.33 % | 1.63 % | 2074 | 1259 | settled | pass1b 1/0/0.080 |

The three candidates land on the same surface at KASE (the solve needs nearly all of the runway's
grade along the whole sheet). CHOSEN: (b), tied faces only — it is the ruling's own sentence ("the
apron still prefers flat … the flat preference must not outrank a taxiway's cap"); (a) deletes the
flat tier on a tied apron, (c) keeps it only across the axis. Not for every apron: 09k's balance
at HECA is measured at `law`, and no other airport has a yielded runway.

THE WEIGHT. A quadratic price ranks by weight x row count, so "below the taxi caps" is geometry
dependent: KASE is saturated from 3 down, the twin's field (runway 2.5 %, parallel on two stubs,
apron welded behind it; cap 2.52 %) reads stubs 4.4 % at 300, 3.6 % at 30, 3.0 % at 3, 2.6 % at
0.3, 0.8 / 1.4 % at 0.03, 0 / 0.6 % at 0.003. Landed 0.03 = law / 10^4 (30bf's spacing for a
yielding row). CONSEQUENCE: on a tied apron the preference is also under `apron_trend` (30) — no
weight is above the trend and under the taxi caps at KASE (30 -> 2.10 %, over the 2.02 % cap) —
so a tied apron follows its ground's long-wave trend inside the wider cap. 09k's order holds on
every apron that did not yield.

## Landed (8a35ab705)

- `runway_yield.derive_taxi` records tied APRON faces beside the taxi faces (`_tied_aprons`): a
  station on a component the yielded runway touches, or contact with a tied taxi face / a face of
  that runway. KASE: faces 23, 58 (stations) and 22 (touches the runway) — 34 records (31 taxi).
  Plateau faces (pad law) and pav6 keep 1.5 %.
- `precedence.face_cap` / `verify/frame.Patch.taxi_yield` read the record for an apron; the census
  reads the way tag unchanged.
- `apron.py`: the tied face is hard at its cap; its preference row cites
  `common.roles.apron preferred tier under a yielded cap`; edge portions read the cap of the apron
  the pair runs along.
- `[design] yielded_preference = 0.03` + `yielded_preference_rulings`; `Base.yielded_pref_i`.
- `verify/contiguity` reads `Patch.cap` (it priced a yielded runway at its table cap: KASE's 4
  standing `lateral_contiguity` rows).
- Spec §50.8 (lane amendment, owed the author's review). Twins `test_apronyield523.py` (6).

Controls (capture pads67, `--from constraints --emit --verify`, main tree vs lane tree): CYXY
patch 775b12754580 = 775b12754580, sidecar and z identical, verify 243 = 243; SPJC patch
563a0892c4cb = 563a0892c4cb, sidecar and z identical, verify 1283 = 1283.

## KASE after (replay of the capture on 8a35ab705)

Owner site: A 2370.75 -> 2372.34 (DEM 2372.28); runway corner 2372.20 -> 2372.73; A -> corner
1.45 m / 4.95 % -> 0.39 m / 1.33 %; apron edge -> corner 4.65 % -> 1.63 %. Census rows on the
pair: none (base: taxi_box 4.93 % vs 2.50 %, airside_no_step vs 2.63 %). Rows within 60 m of A:
170 -> 75. Two short pairs 28 m away remain (0.30 m, 2.08 % vs 1.71 / 1.69 %).

See-saw, mean built − DEM by 150 m station north of A (base -> after):

| station m | runway | taxi | apron/junction |
|---|---|---|---|
| −150..0 | +0.39 -> +0.42 | −0.96 -> +0.20 | −2.04 -> +0.00 |
| 0..150 | +0.73 -> +0.81 | −0.23 -> +0.59 | −0.62 -> +1.24 |
| 150..300 | +0.84 -> +0.91 | −0.21 -> +0.63 | −0.26 -> +1.63 |
| 300..450 | +0.92 -> +0.92 | −0.50 -> +0.45 | −0.13 -> +1.59 |
| 450..600 | +0.54 -> +0.54 | +0.50 -> +0.51 | +0.21 -> +0.39 |
| 600..750 | +0.60 -> +0.59 | +0.64 -> +0.54 | +1.16 -> +1.12 |
| 750..900 | +0.89 -> +0.83 | +1.03 -> +0.42 | +2.13 -> +1.13 |
| 900..1050 | +1.22 -> +1.22 | +1.07 -> +0.35 | +2.64 -> +1.23 |
| 1050..1200 | +1.52 -> +1.52 | +2.52 -> +0.51 | +4.20 -> +1.52 |
| 1200..1350 | +2.11 -> +1.54 | +3.84 -> +0.66 | +5.25 -> +1.45 |

Census (harness): adjudicated airside 2518 -> 1259 — airside_no_step 1247 -> 629, taxi_box
633 -> 125, within_shape 482 -> 488, transverse 71 -> 3, strip_transverse 58 -> 4,
drainage_minimum 41 -> 47, resa_transverse 2, plane_gradient 1, strip_arc 1. v2 verify 4529 ->
2074, DEFECT families all zero. Hard set: NOT settled (0.054 m, 2 runway rows in a law conflict,
§7 STOP line) -> settled (0.010 m, 0 relaxed, no conflict). Null-change pass1a 0/0, pass1b
1/0/0.080, stage2 1/0/0.080 (bar 20 / 0).

RUNWAY (724 runway-role vertices; movers > 0.02 m: 128; over 0.5 m: 21, all 29–76 m off the axis):
- |lat| < 16 m: 18 movers, worst −0.168 m; 16–25 m: 26, worst −0.382 m; 25–60 m: 6 over 0.5 m,
  worst −1.43 m; 60–200 m: 15 over 0.5 m, worst −3.33 m (v333) — the runway-role lobes where the
  north connector meets apron pav7 (+4.35 m over the DEM before, about +1.0 m after), and +0.5 m
  at four lobe corners further south (v644, the owner's corner, +0.52 m).
- Centreline: a wedge from 251 m to 455 m from the 15 end, −0.02 … −0.168 (at 395 m) … −0.02 m,
  0.1 pp per 12 m station. It REMOVES a kink: built grade over 30 m 2.092 % -> 2.027 % (cap
  2.023 %), largest change between adjacent 30 m windows 0.321 pp -> 0.106 pp (60 m: 0.344 ->
  0.205 pp, at the 33 end). Thresholds 0.000 / −0.002 m.

Found, not fixed: an apron vertex's lateral hop to the route network keeps the apron's 1.5 %
transverse cap (spec §50.8 (6)); KASE 7 v2 `transverse apron|apron` rows, 0 census rows.

## The runway (all three candidates identical on the centreline)

Runway-role vertices by lateral offset from the axis ((b) w=3 vs base):
- |lat| < 16 m (212): 18 movers > 0.02 m, worst −0.168 m, 0 over 0.5 m
- 16–25 m (322): 26 movers, worst −0.382 m
- 25–60 m (104): 6 over 0.5 m, worst −1.43 m — the runway-role connector lobes
- 60–200 m (86): 11 over 0.5 m, worst −3.33 m (v333/v332, 76 m off the axis, where the runway-role
  lobe meets apron pav7 / the parallel; base stood 4.35 m above the DEM there, now +1.0 m)

Centreline shape: base had a KINK there — built grade 2.092 % over 30 m (cap 2.023 %), 0.321 pp
between adjacent 30 m windows at 405 m from the 15 end (the two "runway rows in a law conflict").
The arm removes it: max 2.027 %, largest change between adjacent 30 m windows 0.106 pp (at the 33
end), a wedge of −0.02 … −0.17 … −0.02 m over 200 m (0.1 pp). Thresholds unmoved (0.00 / −0.002 m).

## Closing build

`apron523_KASE` (harness, rc 0, 34.7 s, not timed): body 9aceb887dd67, v2 verify 2074, == the
replay of the capture (1817 nodes, 0 movers); frame registered. Census: adjudicated airside
1259 (sw11_KASE 2518). Owner A 2370.75 -> 2372.34; B (39.2185627, −106.8658607, the runway-role
lobe) 2372.61 -> 2372.61 (DEM 2371.77): the dip between them 1.86 m -> 0.27 m.

Suites on 8a35ab705: non-Qt 9229 passed / 19 skipped / 1 xfailed / 1 xpassed; Qt 311 passed;
the four named files 204 passed; `tools/ratchets.py` duplicate + layer PASS.
