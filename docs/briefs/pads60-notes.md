# pads60 notes — §56 (10) fix list F1–F4 and the re-measures (Opus implementer, 2026-10-08)

Branch `claude/pads56` (PR #463). Continues `pads59-notes.md`. Spec `tools/docq.py spec '§56'` (10).
Scratch `<scratch>/pads60/`; the read scripts and the mover lists are committed under
`docs/briefs/padspec-scratch/pads60/`. Replays ran from a frozen second tree
(`.claude/worktrees/pads60r`, local branch `claude/pads60r`, never pushed) so the lane tree could be
edited while one ran. OTHH replay: `perfB362/OTHH.pkl --from classify --emit --verify --workers 6`
(≈ 4 min); HECA: `gaps3/HECA.pkl` (≈ 10 min); KASE / KCLT: `conc333/*_main28500ecf.pkl`.

## Commits

| sha | what | state |
|---|---|---|
| `1c9011b5` | F1 as specified: `y_land ≥ −BAND_M`, `landing_below_unit`, `_unit_collar` deleted, sidecar `landings` | acceptance MISSED on the rows (below) |
| `9d4ebbeb` | F1b — DEVIATION, revertable alone: the band read upward (`y_land ≤ +BAND_M`, `landing_above_unit`) | pending spec-author review |
| `bc704947` + `5cfcbafc` | F2 `planar/pad_sliver.rerole_plateau_scraps` (attempt 1: own plateau only → 0 re-roled; attempt 2: structure borders allowed) | bar MISSED twice, STOPPED |
| — | F3 | BLOCKED, nothing landed |
| `0a4b93db` | F4 step 4F: datum columns take no `apron_trend` / `detached` row | (c) MET; (d) MET against the matched arm only |

## F1 — the reviewer's attribution of the 27 rows is REFUTED

On `p59c_OTHH` all 27 landing `hard_conflict` rows stand on `building6/landing0` (18) and `landing1` (9),
none on `landing2/3`. `landing0/1` belong to `OTHH_TerminalRoads_01_001.obj`, whose LOWEST authored y is
**+10.75 / +10.94 m** over the unit's pad: an elevated road end, not a foot. The law asked the ground for
3.96 + 10.7 m; the solve relaxed the rows (max `s_m` 10.14) and left the "landings" at 4.34 / 4.26 — which
is what the review read as "+0.38 / +0.30 m ramp feet". `landing2/3` (the pier footings, y −1.74 / −1.89)
carried 0 rows.

| OTHH replay | landings | landing rows | max `s_m` | `hard_conflict` total |
|---|---|---|---|---|
| `p59c` build | 4 | 27 | 10.14 | 64 |
| F1 as specified (`1c9011b5`) | 2 (`landing0/1`), `landing_below_unit` 2 | **30** | **10.14** | 69 |
| + F1b (`9d4ebbeb`) | **0**, `landing_above_unit` 2 | 0 | — | **4** (pad tier, the terminal's ramp tops) |

HECA: body `8b8eba6c5a48` on the gaps3 replay before and after F1 + F1b + F2 (= pads59's arm); its T3
landings have y −0.005..−0.234 and stay (5 with faces + `landing5`, minted with no face, as before).

QUESTION (yes / no): may a landing also be refused where `y_land > +BAND_M`? RECOMMEND YES — same
witness, restores main's OTHH (0 landings, 0 rows). NO = revert `9d4ebbeb`; OTHH then carries 30 relaxed
rows up to 10.14 m.

## F2 — 8 → 4, not 2; levels not byte-identical

Probe (`f2probe.py`, every non-largest pad face under 300 m² with its neighbours by shared run): the six
site scraps are NOT bordered only by the plateau. Four (0.25–1.0 m²) are triangles between
`pav4#plateau:building6` and a `retaining_wall` face (`basin_wall:N`, 0.5–2.9 m of run); `building6#4`
102 m² borders only the plateau but its mean width is 3.42 m (rule 6's floor is 2.0); `building6#3`
105 m² has mean width 3.42 m AND 17.3 m of run on the open apron `pav4`.

| arm | re-roled (airport) | site building faces | levels vs the F1b arm |
|---|---|---|---|
| attempt 1 (own plateau only) | 0 | 8 | identical (vertex sha `00c7fcf62f0e` both) |
| attempt 2 (+ structure borders) | 9 / 28.2 m² | **4** | 36 vertices differ, 6 over 0.02 m, worst −0.08 m at 25.26455, 51.61256 |

The 36 movers: building 28, wall_corridor_ramp 11 (0.01), tunnel_trench 4 (0.02), apron 3 (0.010, the
plateau); taxi / runway 0. They stand where the terminal's 4 relaxed `pad_slope_max ceiling` rows stand
(`s_m` 0.42 / 0.08 / 0.04 / 0.05 → 0.42 / 0.11 / 0.04 / 0.06): the relaxation re-chose. To reach 2 the rule
needs another floor than rule 6 and a level argument for a scrap the open apron borders — not improvised.

## F3 — BLOCKED: `plan_blocks` cannot plan the #112 pad, and its base read says one block

Probe (`f3probe.py`, `heca_f3_pad_plan_probe.json`; every pad ≥ `cluster_pad_min_m2` at
`platform_split`): the joined pad `building5` (12,490 m²) has **0 airside regions within
`pad_frontage_m` (3.0 m), 0 welded samples; `plan_blocks` returns `None`** (it partitions FRONTAGE
contacts: `fronted` empty → `None`, < 3 contacts → `None`). And `unit_base` reads it **`flat`**
(`unit:43#6330`), which by 10-02aj (2) is `cap_blocks = 1` — the planner would leave it whole even with a
frontage. So "runs `plan_blocks` … the planner's base read decides" changes nothing at the site.

Every HECA join (lane level | main's pieces):

| join | lane pad | lane level | main pieces | welded? |
|---|---|---|---|---|
| `unit:43#6330/1+/2` | `building5` | 93.036 | 92.028 / 100.383 | no (cand 0) |
| `unit:42#2829/0+/1` | `building2` | 94.479 | 95.000 / 93.999 | no (cand 0), base `feet` |
| `unit:43#222/0+/1` | `building88` | 82.617 | 82.683 / 84.994 | yes, planned `one_block`, base `feet` |
| `unit:43#784/0+/1` | `building60` | 81.443 | 81.899 / 81.145 | under 5,000 m² |
| `unit:43#784/3+/4` | `building80` | 80.263 | 80.365 / 80.059 | under 5,000 m² |
| `unit:43#744/1+/2` | `building103` | 77.115 | 77.043 / 77.052 | under 5,000 m² |

What the feet say at the site (main `swg_HECA` → lane `p60_HECA`, 60 m of 30.1125123, 31.3961245): feet
within 0.3 m 11 → 14 of 156, floating 142 = 142, buried 3 → 0, worst −10.31 → −9.39; cross-body contact
pairs over 0.5 m **9 (worst 8.081 m) → 0 (worst 0.005 m)**. The pit the review predicts is not in the
feet read; the pad still stands at 93.04 where main had 100.38 / 92.03.

QUESTION (yes / no): is an UNWELDED joined pad to be seated per pre-join piece (each a §20 plate at its own
ground, the 2b closure a `#strip`) when the pieces' ground differs by more than a stated bar? It needs the
pre-join pieces at the planar stage (today only `OUTLINE_STATS` ids reach the constraints stage) and a bar
— a design, not a call site.

## F4 — step 4F on the HECA gaps3 replay

| bar | result |
|---|---|
| (a) / (b) | released set and `released_max_m` identical to the pre-F4 arm |
| (c) vs the 4A arm | runway 0 = 0, apron 0 = 0, taxi 70 → 73: `gap:15` 0.153 and 0.088 at 30.10462, 31.39655 / 30.10470, 31.39653, `dsf:objpav3` 0.038 at 30.12166, 31.42041 — the same three as before F4, none over 0.2 m |
| (d) vs 4A + the same step (`pads59/heca_4a_notrend`) | every pad ≤ **0.005 m** (`building141` included) |
| (d) vs plain 4A | ten pads −0.118..−0.120 (`building51 / 61 / 62 / 63 / 64 / 81 / 82 / 88 / 90 / 101`) — the step's own shift on main's frame (spec R4: "moves main's levels at 10 HECA pads by ≤ 0.12 m") |
| datum vs the pre-F4 lane arm | max −0.026 (`building81`) |

AIRSIDE MOVERS of the step (pre-F4 → F4, 0.02 m): **1,040** — taxi-family 768 (junction 623, cross_connector
160, secondary_parallel 40, primary_parallel 31, stub 15), apron-only 272 (worst −0.07), runway 0; worst
−0.43 m at 30.1021369, 31.3971543. 67 clusters (`heca_f4_airside_mover_clusters.txt`, every vertex in
`heca_f4_airside_movers.txt`). 21 clusters / 741 vertices stand within 150 m of a cluster the NULL-change
control moves (`heca_null_control_clusters.txt`: the null change moves 262 taxi-family vertices in 32
clusters, far beyond the SW box — 30.1064, 31.3962 −0.50; 30.1114, 31.4088 +0.32; 30.1026, 31.3927 −0.21);
46 clusters / 299 vertices do not, worst −0.32 at 30.1168239, 31.4174895 (`dsf:objpav72`), +0.18 at
30.1301611, 31.4071485, then ≤ 0.13. Only 33 of the 1,040 are inside the SW box. NONE was tied to a
changed row: the step removes rows at ≈ 42 datum columns and the movers are junction-mesh vertices
hundreds of metres from any pad.

KCLT (replay, pre-F4 → F4): **623** airside movers, taxi-family 555, worst −0.58 (cross_connector at
35.2307950, −80.9557540), primary_parallel −0.55 / +0.47, junction −0.57, stub +0.46; runway 0; taxi-tier
`hard_conflict` 57 = 57. KASE: 0.

## Found, not fixed

- KCLT vs main (`swg_KCLT` → `p60_KCLT`): 3,044 airside movers over 0.02 m (taxi-family 1,313), worst
  −1.29 m at 35.2225116, −80.9414574; taxi-tier `hard_conflict` 19 → 57 — already there before F4.
- KASE vs main: 113–117 airside movers, taxi-family 65–69, worst +0.40 at `building1`'s rim, ONE runway
  vertex −0.03 m at 39.22186, −106.86917 — all before F4 (F4 adds 0).
- OTHH census `within_shape` 366 → 1,095 (`building|building`, the terminal face against the structure
  vertices it carries, worst 9.02 m at 25.25795, 51.61436): present in `p59c` (1,098).
- OTHH jetway anchors over `ground`: 45 = main's 45 (`anchor_role_probe.py`).
- HECA census: a `terrace_actual_step [apron|apron]` 3.16 m over 4.73 m at 30.1215552, 31.4199516 now
  reads CRITICAL motion; main carries the same levels there (98.62 / 95.40), only the row's class changed.
- `obj8_split_report --feet-in` prints counts per site, not per-foot hosts: "feet whose host changed"
  cannot be read; missing is a per-foot row (lat, lon, host face ref) in its `--json` (`census.rows` is per
  body).
- `constraints/platform.py` 1,203 lines: not split (the landing pair path is the candidate).
- The artifact ledger refused to store `p60_OTHH` (`CONTAMINATED-KEY`: an untracked docs folder appeared
  in the tree mid-build; no code moved, rc 0).
