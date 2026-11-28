# RESUME — lane lenvelope (building envelope, RULINGS 2026-11-27h)

Paused 2026-11-27 (owner: usage). Branch `claude/lenvelope`, base `cac5a41a0`
(`origin/claude/project-thread-ddpu46`). Spec: `building-envelope-20261127.md`.

## Done

- STOP 0 (measure): `airport/building_split.py` (B1-B9 on the
  `footprint_touch_m` lattice; wall runs from `geom/underside_map.supercover`,
  regions / roofed fill in `geom/plan_lattice.py`), census
  `tools/underside_census.py --buildings` (library `tools/envelope_census.py`).
  Twin `tests/auto_patch_v2/test_building_split.py`. RULINGS 2026-11-27h recorded.
- STOP 1 (the record): `PackPartition.buildings` (the `Split`, load reading only,
  cached with the partition), say-line `[ICAO] buildings: ...` in
  `pipeline/build.pack_stage`, sidecar key `buildings`
  (`pipeline/building_publication.py`, registered in `emit/osm_adapter.SIDECAR_KEYS`).
  Bar: `tools/pack_stage_profile.py ICAO --cache off` stage digests (partition /
  connectors / clusters / objects / readings) base `cac5a41a0` vs lane: KEGE
  EQUAL (partition bf71de1086a2, connectors 2e38e77b22c3, clusters
  09b6fde4283d, objects 83f601d4ec52, readings 7ec2f751f0c8).  Base digests of
  the others (lane arm NOT compared: the session scratchpad was wiped mid-run,
  KMCI/KATL/RJTT lane runs failed on the missing output dir; BIKF/OMDB/LGAV lane
  logs lost): BIKF 9f9a47c3babb/2e38e77b22c3/23396e9cc98e, OMDB
  a279f5bd3e00/e649ce70f64d/000aaf17ff54, LGAV dee73f50a9b5/87864d61d633/3b66de33cb63,
  KMCI 54bed7cd7652/7d0d087a63b2/cd539bf587d0, KATL 306cbbd38eb2/abeda3f0b6d0/9b9a83e08590,
  RJTT 949b6ae15542/1f6d76196645/ad3162dd509d (partition/connectors/clusters).
  Re-run `tools/pack_stage_profile.py ICAO --runs 1 --cache off` on the lane
  head and compare.  Nothing downstream reads `buildings`, so patch / rebake /
  placement are unchanged by construction.  Base pack-stage walls (one run,
  not a timing): KMCI 136.8 s, KATL 206.2, RJTT 264.7, OMDB 25.4, LGAV 19.2,
  BIKF 42.4, KEGE 12.4.

## Stop 0 measurements (captures as the spec §1; 0.5 m cell 8-linked / 0.25 m two-cell)

| ICAO | solid | wall | interior+sheet | attached | exterior | buildings (>=100 / >=5000 m2) | clusters -> folded | contacts in one building | split s 0.5 / 0.25 |
|---|---:|---:|---:|---:|---:|---|---|---|---|
| KEGE | 2,524 | 399 | 1,911 | 172 | 42 | 50 (28/4) | capture pids unmapped | 97 % | 0.11 / 0.19 |
| BIKF | 4,310 | 625 | 3,168 | 371 | 146 | 102 (62/6) | 290 -> 234 | 81 % | 0.34 / 0.39 |
| OMDB | 7,627 | 4,705 | 2,255 | 224 | 443 | 485 (216/41) | 1,349 -> 956 | 80 % | 2.8 / 9.5 |
| LGAV | 11,166 | 1,739 | 1,866 | 1,049 | 6,512 | 574 (75/14) | 2,690 -> 1,166 | 20 % | 0.45 / 1.3 |
| KMCI | 60,281 | 11,142 | 38,848 | 2,525 | 7,766 | 603 (104/17) | 17,662 -> 13,608 | 77 % | 5.6 / 8.4 |
| KATL | 77,767 | 23,344 | 34,394 | 3,628 | 16,401 | 696 (123/28) | 22,244 -> 11,357 | 65 % | 4.6 / 13.7 |
| RJTT | 27,766 | 5,096 | 10,961 | 2,008 | 9,701 | 419 (179/25) | 6,585 -> 2,249 | 60 % | 15.8 / 29.7 |
| CYYZ | 11,659 | 3,053 | 5,163 | 1,012 | 2,431 | 481 (143/28) | capture pids unmapped | 67 % | 2.3 / 6.6 |
| LEMD | 13,577 | 4,914 | 5,145 | 1,674 | 1,844 | 991 (162/11) | 2,845 -> 1,365 | 48 % | 2.3 / 6.2 |

Certified airports, today's walled clusters not one-to-one (0.5 m), every one
named by the census: BIKF 0 split / 3 merged (sheet+placement join, 14x floor
split, lattice band); OMDB 15 split (leaf over two walled bodies 5, ringless
piece chained by its lat/lon box 4, walled body chaining on its thin pieces'
rings 3, outline rings touch where triangles do not 3) / 44 merged (lattice
band 30, floor split 10, different anchors 3, joined 1); LGAV 21 split
(ringless box 11, leaf 7, rings 2, thin 1) / 57 merged (lattice band 37, floor
split 15, joined 4, anchors 1); KEGE: its 11-17 capture's cluster pids do not
map — needs a fresh capture to read.

## Next

0. Finish stop 1's digest comparison (above).
1. The master picks the cell (0.5 m 8-linked recommended: half the seconds,
   same classes within a few %).
2. Merge `origin/claude/lfilecache` (98edf05c4, or the integration head that
   lands it): one conflict, the appended blocks at the end of
   `pipeline/stage_code.py` (keep both).
3. STOP 2 (spec §10): one body / unit / cluster / map / shift per building —
   contact weld (A5-A7), connectors (A9), `plan_clusters` (A10, no floor split
   and no leaf cluster inside a building), `plan_units_and_connectors` (A11),
   `unit_underside` population (A12), bodies/splits/pad-block (B1-B5).  Fresh
   captures of the certified four + KMCI/KATL/RJTT are needed for its bars
   (§9).  OMDB: report its split list before stop 3.
4. STOPS 3-4 as the spec; stop 4 (levels from the envelope's underside map) is
   owner-approved (22:57Z).

Not done: stops 2-5; no captures taken; KEGE mapping unread.
