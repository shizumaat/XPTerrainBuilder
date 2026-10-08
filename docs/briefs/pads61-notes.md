# pads61 notes — §56 (11) fix list 1–3 and the re-ladder (Opus implementer, 2026-10-08)

Branch `claude/pads56` (PR #463). Continues `pads60-notes.md`. Spec `tools/docq.py spec '§56'` (11) and its
"AS BUILT" paragraph. Scratch `<scratch>/pads61/`; probes, the arm runner and the instrument reader are
committed under `docs/briefs/padspec-scratch/pads61/` (`arms.sh`, `inst.py`, `pinprobe.py`, `pincost.py`,
`joinprobe.py`, `padgeo.py`, `weldgeo.py`, `arm_PF1_not_landed.patch`). Arm patches: `frames.py list ICAO`,
lane `pads61`. Method = padreview2's: lane code replayed from a main-era capture `--from classify --emit
--verify --workers 6`, `airside_value_delta --tol 0.02` against `swg_*`, solve-owned frame.

## Commits

| sha | what | state |
|---|---|---|
| `3f8002ff` | fix 1 R-W: `geom/outline_pin.Frontage`, `simplified_outline(front=)`, mint / census / absorption pass it | acceptance MET at KASE, HECA, OTHH; MISSED at KCLT (below) — STOPPED, no closing builds |
| `448044ba` | fix 2 R-C: `check_grade._one_row_per_pad_vertex` | done |
| `fcc50d22` | fix 3: the absorb / close coupling STATED (law comment, docstring, spec, twin) | done |

## Fix 1 — the ladder (solve-owned movers vs main at 0.02 m)

| airport / arm | movers | runway | taxi / worst | apron / worst | strip / worst | > 0.3 m (far-field) | `hard_conflict` taxi / pad tier | welded | outline vertices | roads absorbed |
|---|---|---|---|---|---|---|---|---|---|---|
| KCLT main `swg` | — | | | | | | 19 / 4 | | | |
| KCLT `OA0` (padreview2) | 1,531 | 0 | 261 / 0.61 | 810 / 0.23 | 460 / 0.58 | 16 (16) | 19 / 28 | 1,437 | 3,106 (rule 2) | 0 |
| KCLT `F` before the pin (= `p60`) | 2,643 | 0 | 527 / 0.67 | 1,466 / 0.92 | 650 / 0.98 | 226 (162) | 57 / 102 | 1,220 | 1,464 | 21 |
| KCLT `P` pin, before the absorption retry | 2,309 | **2** (+0.05 / +0.04) | 368 / 0.59 | 1,368 / 0.58 | 571 / 0.82 | 107 (91) | **19** / 16 | 1,412 | 2,814 | 8 |
| KCLT `PA0` pin, absorb key 0 | 2,362 | 0 | 369 / 0.65 | 1,371 / 0.41 | 622 / 0.79 | 96 (80) | 19 / 34 | 1,408 | 2,814 | 0 |
| KCLT `P2` pin at 3.5 m (`pad_frontage_m` + spacing; NOT landed) | 2,290 | 2 | 356 / 0.62 | 1,367 / 0.42 | 565 / 0.73 | 86 (70) | 19 / 28 | 1,407 | 2,889 | 2 |
| KCLT `PF1` = `P` + the fallback join undone (NOT landed) | 1,720 | 2 | 289 / 0.65 | 830 / 0.51 | 599 / 0.83 | 77 (77) | 19 / 16 | 1,438 | 2,814 | 8 |
| **KCLT `P3` = the landed code `fcc50d22`** | 2,411 | **2** | 384 / 0.66 | 1,388 / 0.45 | 637 / 0.65 | 81 (64) | **54** / 17 | 1,418 | 2,814 | 10 |
| KASE main | — | | | | | | 0 / 68 | 43 | | |
| KASE `OA0` | 107 | 0 | 36 / 0.33 | 52 / 0.34 | 19 / 0.23 | 2 (2) | 0 / 59 | 40 | 872 | 0 |
| KASE `F` | 103 | 1 (0.03) | 33 / 0.31 | 45 / 0.40 | 24 / 0.25 | 4 (3) | 0 / 12 | 15 | 497 | 0 |
| **KASE `P3`** | 108 | **0** | 36 / 0.33 | 53 / 0.34 | 19 / 0.23 | 2 (2) | 0 / 51 | **40** (`building2` 33, `building1` 7 = `OA0`) | 571 | 0 |
| HECA main | — | | | | | | 72 / 27 | 1,023 | | |
| HECA `OA0` (this lane, `gaps3/HECA.pkl`) | 2,063 | 0 | 713 / 0.40 | 860 / 0.19 | 490 / 0.64 | 10 (10) | 74 / 215 | 1,020 | 4,943 | 0 |
| HECA `F` (= `p60_HECA` build) | 4,507 | 0 | 1,943 / 0.40 | 1,534 / 1.05 | 1,030 / 1.05 | 43 (16) | 73 / 121 | 922 | 2,921 | 20 |
| **HECA `P3`** | 1,596 | **0** | 635 / 0.40 | 514 / 0.12 | 447 / 0.43 | 8 (8) | **74** / 153 | **1,020** | 3,622 | 3 |
| OTHH main | — | | | | | | 0 / 0 | 1,081 | | |
| OTHH `p60` build | 0 | 0 | | | | 0 | 0 / 4 | 841 | 2,424 | 34 |
| **OTHH `P3`** (`perfB362/OTHH.pkl`) | **0** | 0 | | | | 0 | 0 / 3 | 1,087 | 3,598 | 14 |

Caveat: main's own replay of `gaps3/HECA.pkl` was not taken, so HECA's rows carry the replay-vs-build frame
(the two HECA arms share it; `P3` vs `OA0` is exact).

**KCLT per pad `welded`, `P3` vs `OA0`** (7 of 32 clusters differ; all others equal): `unit:31#0/0`
(`building75`, the terminal) 308 → 291, level 221.034 → 221.206; `unit:3#728/0` 19 → 23; `unit:3#33` 19 → 18;
`unit:3#756` 26 → 27; `unit:3#787` 12 → 13; `unit:31#1117/4` → `/1` renumbered (0 welded both). The four
review sites on `P3`: taxi-tier `pavement_max_grade ceiling` rows 8 (max 1.67 m) / 21 (1.05) / 2 (0.96) / 0 —
on `P`, `PA0`, `P2`, `PF1`: none at any of the four.

### What the three KCLT misses are (each by intervention)

1. **The terminal's datum (+0.17 m, apron movers 810 → 1,370) is a JOIN, not the frontage.** `pinprobe.py`:
   inside the true airside cells' 0.5 m zone the pinned pads' ground is identical to rule 2's (0 m² at every
   one of 98 pads). `joinprobe.py`: main / `OA0` carry a 11,137 m² FALLBACK pad `building83` (13 welds, level =
   the terminal's) nested in the terminal's cluster pad; the closing's groundside fills (432 + 377 + 154 m²,
   20–80 m from any airside) make the terminal's shell COVER it, and `classify/evidence._pads`' enclosure rule
   (#6 "never one shape inside another") merges it. With that one merge undone (`PF1`,
   `arm_PF1_not_landed.patch`): terminal 305 welds / 221.035, welded total 1,438, apron 830 / worst 0.51.
   This is the R-J2 class (a join that changes a welded pad's datum), not R-W.
2. **The taxi-tier "19 → 54" is a PACKAGE that one 16 m² absorption switches.** `P` → `P3` is one change: the
   absorption retry lets `building26` (`unit:3#95`, welded 0, level +0.013 m) absorb `small_roads:-27552` and
   `#1` (16.4 m² of road, 307 m² of fill). 35 stage-2 `pavement_max_grade ceiling` rows appear together: 5 near
   that pad (35.208–35.209, −80.931), 21 at 35.204, −80.940 (≈ 1 km away) and 6 at 35.225, −80.933 (≈ 1.9 km).
   The same package is in the review's `A0`, `C0`, `F`; absent in `OA0`, `O0` and in six of the seven pin arms.
   NOT attributed further: how a pad-side change reaches rows a kilometre off (the road-terrace chain 10-03b
   is the candidate). The retry is kept: per-road is what §56 (2) 8 / 4 (d) say, and dropping it to make KCLT
   read 19 would be tuning to one airport.
3. **The two runway vertices** (+0.05 / +0.04 m at 35.22476, −80.93645 and 35.22444, −80.93643, strip-edge
   vertices of the 18L/36R parallel) move in `A0`, `P`, `P2`, `PF0`, `PF1`, `P3` and not in `OA0`, `C0`, `F`,
   `PA0`, `PJ0` — 6 of 11 arms, with and without the pin, 650 m from the terminal. Bistable; not attributed.

### What the pin costs the owner's goal

| | rule 2 | before the pin | after the pin |
|---|---|---|---|
| OTHH `unit:28#8/0` outline vertices | 1,315 | **552** | **1,232** |
| OTHH `unit:28#8/0` roads absorbed (kept near the pad) | — | 29 (0) | 14 (27) |
| OTHH airport outline vertices | 6,133 | 2,424 | 3,598 |
| HECA airport outline vertices / roads absorbed | 4,943 | 2,921 / 20 | 3,622 / 3 |
| KCLT airport outline vertices / roads absorbed | 3,106 | 1,464 / 21 | 2,814 / 10 |
| KASE airport outline vertices | 872 | 497 | 571 |

`pincost.py` on OTHH: the terminal cell `building6` has 1,717 ring vertices and 939 of them end an edge within
0.5 m of airside — 940 against the true airside cells, so it is NOT the evidence-time union being a superset
(that costs 66 vertices at one other pad, `building23`). The owner's terminal fronts airside on 55 % of its
ring; the pin returns it to within 6 % of rule 2 there. OTHH owner-site rows not re-read on a build (STOP).

## Fix 2 — OTHH census (lane tool on the lane's `p60_OTHH`; main tool on main's `swg_OTHH`)

| | main tool, main patch | lane tool before | lane tool after |
|---|---|---|---|
| `within_shape` | 366 | 1,095 | **64** (61 `building\|building`; worst 9.02 m unchanged) |
| adjudicated total / airside for acceptance | 486 / 482 | 1,183 / 1,179 | **140 / 136** |
| in-build `pad_flat` | 77 | 56 | 56 |

Reading: the pair law is untouched; the over-allowance pairs of one `building` way are settled a vertex at a
time. `verify/within.within_shape` (in-build) still reads rigid pairs — NOT changed (the brief named
`check_grade` only; the spec's fix-list row names both).

## Fix 3 — stated

With `outline_close_m = 0` a road the set-back holds off its pad cannot join (the re-close is what fills the
stand-off); a cell already touching the pad still joins. Twin
`test_with_the_outline_close_disarmed_no_held_off_road_is_absorbed`.

## Found, not fixed

- KCLT misses 1–3 above; the closing builds (KCLT / KASE / HECA / OTHH) were NOT run (the brief's STOP).
- `tools/pack_stage_profile.py` and `tools/pad_gap_diff.py` call `cluster_outlines` without `frontage=`: they
  draw the un-pinned outline (they hold no airside union). Profile tools, not gates.
- The census's fallback where this process did not mint (a replay `--from planar` or later) pins against
  `airside_union(planar, law)`, not the mint's evidence-time union.
- `geom/cluster_outline.py` 1,058 → 1,105 lines (`AirsideRim` + `airside_vertex_snap`, ≈ 270 lines, are the
  second responsibility to move out).
- `verify/within` per-vertex reading (above); R-J2 and the landing lip-vs-pier follow-up (next round).
