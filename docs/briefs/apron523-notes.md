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

The three candidates land on the same surface (the solve needs nearly all of the runway's grade
along the whole sheet). CHOSEN: (b), tied faces only — it is the ruling's own sentence ("the apron
still prefers flat … the flat preference must not outrank a taxiway's cap"); (a) deletes the flat
tier on a tied apron, (c) keeps it only across the axis. Not for every apron: 09k's balance at
HECA is measured at `law`, and no other airport has a yielded runway.

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
