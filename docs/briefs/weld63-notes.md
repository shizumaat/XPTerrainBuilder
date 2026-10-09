# weld63 notes — implementing spec §63 (a cell touching a pad in the source is welded; a gapped cell is free)

Lane `weld63` (Opus, implementation). Worktree `.claude/worktrees/weld63`, branch `claude/weld63` off
`origin/claude/chainlag` ded211fb + `origin/main` 116152e0 (docs-only). Scratch `<scratch>/weld63/` (`.progress`).
Master rulings carried in the brief: Q-A YES (a §28 (6) held terrace > 2.4 m keeps the knife); Q-B = 09j literal
(a landside pad keeps its own seat, the touching road / lot comes to it within its cap).

## Sub-steps

| step | commit | state | what |
|---|---|---|---|
| S | (this) | landed | `constraints/pads._airside_only` drops every groundside role: a pad fronts airside or nothing (its §9b datum). Twin `test_v2frontage::test_a_pad_between_a_road_and_a_lot_keeps_its_datum_and_takes_no_level_row` (red before, green after); 80 pad tests green. `pad_seat.py` / R-C / the solver change were never on this tree. |
| T | 23ad159e | landed | the witness `classify/pad_touch.py` (new module: `touch_distances`, `is_touching`, `touch_records`), read in `classify/roles._cut_back_groundside` BEFORE the knife on identity-gridded rings against every pad within `pad_frontage_m`; `Cell.evidence['pad_touch'] = {pad ref: d}`; sidecar evidence key `pad_touch` (`pipeline/publication.pad_touch`, registered in `emit/osm_adapter` + `check_grade.SIDECAR_EVIDENCE_KEYS`); `tools/pad_edge_read.py --source SIDECAR|CAP.pkl` (classes TOUCH-OFF / HELD / GAPPED / AIRSIDE / ENGINE / UNWITNESSED; INDEX row; 5 twins) ; twin `tests/auto_patch_v2/test_pad_touch.py` (overlap, 0.3 m, 0.8 m, 2 m, beyond the radius, the sidecar record). No surface change. |
| W | | | |
| B′ | | | |
| P / L | | | |

## T — the seven-airport touch census (`<scratch>/weld63/census/census.py`; classify of the pads67 captures under T, the edge read of main's sweep products `/tmp/harness/sw1041_<ICAO>[_cold].v2/<ICAO>.graded.json`)

| airport | pads | pads with a groundside neighbour within 3 m (touching ≥ 1) | pairs touching / gap ≤ 1 m / gap ≤ 3 m | knife cuts today | P runs TOUCH-OFF (runs / m) | GAPPED | ENGINE (ribbon / facade / gap piece: the engine's own stand-off) | AIRSIDE |
|---|---|---|---|---|---|---|---|---|
| HECA | 212 | 28 (24) | 42 / 1 / 11 | 17 | **17 / 612** | 2 / 66 (`building164` \| `objpav405` 1.31 m, `building8` \| `route3` 1.53 m) | 4 / 61 (`building75` \| `small_roads:-20325` −5.13 m over 57 m; `building165`, `building6`, `building147`) | 31 / 528 |
| KCLT | 98 | 31 (24) | 38 / 2 / 9 | 1 (cells) | **11 / 65** | 2 / 24 (`building62` / `building61` \| `pol48` 1.79 / 1.75 m) | 1 / 0 (`building59` \| `small_roads:-7033#1`) | 7 / 17 |
| SPJC | 66 | 10 (5) | 15 / 1 / 7 | 8 | 1 / 0 (`building24` \| `pol37#1` +1.51 — 09f's held pair) | 2 / 0 (`building28` \| `pol68` 1.12 m, `building46` \| `pol74` 2.76 m) | 1 / 32 (`building52` \| `facstrip:building53`) | 2 / 0 |
| CYXY | 14 | 4 (4) | 5 / 0 / 0 | 4 | 2 / 157 (`building13` \| `pav4` +3.97 over 111 m, `building14` \| `pol129` +3.52 over 46 m — 13o's hillside terraces: HELD under Q-A) | 0 | 0 | 0 |
| OTHH | 33 | 4 (3) | 55 / 0 / 1 | 54 | 0 | 0 | 0 | 0 |
| KASE | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| NLWF | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Reading. (a) HECA / KCLT reproduce §63 (2) on the gridded witness (HECA 17 TOUCH-OFF runs / 612 m where the spec read 15 / 565 on
`m`; the two extra are `building15` | `route3` 117 m and `building12` | `route3` 72 m, which the spec's read took by the larger
lot cell). (b) OTHH is the airport W changes most by COUNT — 55 touching pairs, 54 cut by the knife today — and it shows no P run
at all today: every one of those pairs is level across the stand-off, so the weld there is geometry-only; the master's sweep
reads it. (c) FOUND, NOT IN §63's CENSUS: the mapped-road RIBBONS, facade cells and gap pieces are minted AFTER the witness site
with the pads' knife in their own `occupied` union (`classify/ribbon_mint.py:170`, `facade_mint`, `gap_mint`) — a SECOND site of
the engine's gap; the edge read classes them ENGINE (HECA 4 runs / 61 m incl. `building75` | `small_roads:-20325`, KCLT 1, SPJC 1).
§63 (2) read `building147` | `small_roads:-3929` (0.76 m) and KCLT `building27` | `-7016#1` (0.72 m) as source gaps; they are that
knife less the snap. Not changed by this lane (C11 keeps the stand-off for gap / facade pieces; the ribbon is not named).
