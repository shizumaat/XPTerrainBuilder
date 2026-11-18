# RJTT riser rim, round 6 — the body datum never levels a riser's free rim

Status: SPEC for ONE Opus round (effort medium). Written 2026-11-18 by the
one-miss review of `claude/lrjtt5` (c6ff228fd = ba945f991 + lint).
Base for the round: `origin/claude/lrjtt5`. New branch: `claude/lrjtt6`.
No airport-specific code: RJTT is where the defect was found and the
closing replay, never the scope.

## 1. What lrjtt5 left, and why (MEASURED)

Replay of `frames/l2079r2/RJTT.pkl --from classify` on c6ff228fd
(2026-11-18, 34 min wall): the owner's vertex (35.54365754, 139.78988369;
v24607 in the owner's 1.0.557 solve, **v24300 in this replay**) solves to
**16.93 m over a DEM of 8.154 m (+8.78)**; `--why-from … --why-at` prints
"no row binds the vertex — the objective holds it".

The vertex's only face is `building56/p1#strip` (face 1252), a 1.1 m sliver
of the lower level's riser that lies between the level (0.98 m) and the
pad's own boundary, with no face beyond (the coverage edge). Its one design
triangle is (20267, 22854, 24300); `solve/wall_cut._riser_edges` cuts edge
(20267, 24300) and the other edge's cotangent weight is clamped (obtuse), so
it has **no bending row**. `constraints/riser.riser_exempt` withdraws every
law row across the riser and `block_strip_rows` mints no bank row for a
level's riser, so it has **no law row** (0 one-sided rows name it).

Every objective row on the vertex (stage 2 `assemble`, read by logging
`_Rows.add`):

| row | weight | coefficient on v | wants v at |
|---|---|---|---|
| `ground_datum` (lrjtt5) | 3 | 1 | 8.15 |
| `body_datum` (19742, mean) | 300 | 1/54 | 235.79 |
| `body_datum` (19742, tilt_u) | 300 | -0.0187 | 53.64 |
| `body_datum` (19742, tilt_v) | 300 | 0.0123 | 16.59 |

Closed-form optimum of those four rows with every other vertex held:
**16.9348 m = the solved value.** Without the three body rows: 8.154 m.

Body 19742 (kind `apron`, 54 vertices, `design_assemble.py` step 9b, the
`datum_roles` loop at line 731) is building56's lower level, its riser and
the block's edge. The level is held by its landing rows a storey (5.95 m)
under the block, so the body stands 4.05 m under its own DEM plane on
average and its mean / tilt rows cannot be met by the held vertices. The
riser's free rim vertices are the only free columns in those rows and
absorb the whole residual. Before lrjtt5 nothing opposed them (107.45 m,
130.17 m); the weak datum (3 against 300/54² per row) only brought the
balance down to 16.93 m. This is not a real feature: it is the pad body's
datum levelling a vertex that is not the pad's body.

Same mechanism, same replay (strip-only coverage-edge vertices, two bodies):

| vertex | z now | DEM | without body rows |
|---|---|---|---|
| v24300 (owner) | 16.93 | 8.15 | 8.15 |
| v22870 | 11.06 | 3.89 | 3.89 |
| v22871 | 10.92 | 4.72 | 4.72 |
| v22872 | 13.96 | 8.20 | 8.20 |
| v22868 | 10.04 | 4.83 | 4.83 |
| v20750 | 15.13 | 8.18 | 8.30 |
| v28478 | 14.96 | 8.71 | 8.63 |
| v28477 | 14.34 | 8.39 | 8.28 |

(body 19742: the first five; body 20699, 43 vertices: the last three and
v20724, 7.46 → 7.03, which a hard proximity row ties to the block.)

Second finding, an over-reach of lrjtt5: its set also takes every LEVEL
vertex on the coverage edge (faces = the level and its strip): 29 of the 81
strip members at RJTT, e.g. v20267 (level 0.98, DEM 8.17) and v28138
(`building75/p2`, level -9.05, DEM 6.74). Each now carries a `ground_datum`
row — a per-vertex DEM pull on a held, designed level (08t (1) forbids it).
The landing rows hold them, so nothing visible moved, but the pull is on
the pad's datum column.

## 2. The rule

**A riser's free rim is ground of its own: it takes the #302 weak datum and
is in no body's datum fit.** `design_ground.ground_rim_vertices` already
states one half ("their datum levels the vertex, never the pad's body") and
`assemble` step 9 applies it to anchoring (`rim_only`); this round applies
the other half — the pad's body datum never levels the rim vertex — to the
strip rim lrjtt5 added, and trims that set to the rim.

(a) `solve/design_ground.py`: new `riser_rim_vertices(planar) -> set[int]`
— the coverage-edge vertices (an edge with `left_face`/`right_face` None)
with a DEM sample whose EVERY incident face is a strip (`is_strip_ref`) of
one platform ref. `coverage_edge_collar_vertices` keeps its collar branch
byte-for-byte as before ba945f991 (`is_collar_ref` faces, "own collar or
platform") and returns that set united with `riser_rim_vertices`. A level's
own vertex is therefore no longer in the set. Export the new name in
`__all__`; the single derivation site stays this module.

(b) `solve/design_assemble.py`, step 9b body loop (line 745 filter): a
vertex in `riser_rim_vertices(planar)` leaves `vs_b` beside `pad_follow`,
`hard_v` and `court_v`, with a comment citing this spec and the measured
table. Derive the set once per `assemble` call. Collar rims and
`riser_outer_vertices` are NOT taken out of body fits in this round (they
carry a one-way bank or wall row that bounds them; taking them out moves
every collared pad and is a separate measurement).

Nothing else changes: no new weight, no new row, no law table.

Consumer table (RULINGS 2026-08-30l) — readers of the set:

| reader | effect |
|---|---|
| `ground_datum_vertices` → `assemble` step 7 datum rows | level vertices lose the lrjtt5 datum; strip-only rims keep it |
| `ground_rim_vertices` → `assemble` step 9 `rim_only` anchoring | unchanged for rims; level vertices were rim-only (never anchors), now simply absent |
| `assemble` step 9b body fit (new) | strip-only rims leave `vs_b` |
| `tools/v2_why_solve` terminal naming | reads the same function, no edit |
| `constraints/platform.py:288` | comment only, no read |

## 3. Files

- `Ortho4XP/src/auto_patch_v2/solve/design_ground.py` (a)
- `Ortho4XP/src/auto_patch_v2/solve/design_assemble.py` (b)
- `Ortho4XP/tests/auto_patch_v2/test_collarlag302.py` (twins)
- run `venv/bin/python ../tools/blast.py` on both source files first.

## 4. Twins (in `test_collarlag302.py`, beside lrjtt5's)

1. Set twin on `_stub_planar`: for `{1: ("u/p1", [0,1,4,5]), 2:
   ("u/p1#strip", [1,2,3,4])}` assert `{2, 3} == riser_rim_vertices(pm)`
   and `{0, 1, 4, 5}` disjoint from `coverage_edge_collar_vertices(pm)`
   (vertex 1 and 4 are level vertices on the coverage edge: in under
   lrjtt5, out now). Keep lrjtt5's `beside` assertion.
2. Body twin: on the module's existing `problem` fixture, monkeypatch
   `design_ground.riser_rim_vertices` (and the name `design_assemble`
   reads) to return the fixture's coverage rim, call `assemble`, and assert
   no row of `base.body` whose owner is `("body_datum", …)` carries a
   column of those vertices, while the unpatched call does (fails before
   (b), passes after). If `tests/auto_patch_v2/test_low_level.py` has a
   fixture with a strip-only coverage-edge vertex, use it unpatched instead.
3. `test_collarlag302` 5/5 + the two new; `test_low_level.py`,
   `test_v2aprontrend.py`, `test_v2cyxy.py`, `test_orphanshape.py`,
   `test_stage_code_closure`, `tools/ratchets.py` (dupes, unused, layers).

## 5. Replay evidence (no tile build: 17r, closing build at integration)

From `Ortho4XP/`, base tree = `origin/claude/lrjtt5`, arm tree = the round.
Run base and arm side by side (two processes), never one after the other.

RJTT (planar must be rebuilt under the current tree, so `--from classify`):

    venv/bin/python tools/v2_solve_replay.py --replay \
      /Users/noah/XPTerrainBuilderData/.harness/frames/l2079r2/RJTT.pkl \
      --from classify --site 35.54365754,139.78988369 --site-radius 12 \
      --verify --emit <scratch>/rjtt_{base,arm} \
      --solved-out <scratch>/rjtt_{base,arm}.solved.pkl --json <scratch>/rjtt_{base,arm}.json
    venv/bin/python tools/v2_solve_replay.py --why-from <scratch>/rjtt_arm.solved.pkl \
      --why-at 35.54365754,139.78988369 --site-radius 0.6
    venv/bin/python tools/v2_solve_replay.py --why-from <scratch>/rjtt_arm.solved.pkl --why-hard
    venv/bin/python tools/airside_value_delta.py <base>.osm <arm>.osm --by-ref --json <scratch>/rjtt_avd.json

(`--why-at` only runs with `--why-from`; on a `--replay` it is ignored.
`--probe-site` is not needed: no row binds the vertex.)

Movers on the solve only (`--replay PKL` default `--from constraints`,
`--emit`, then `airside_value_delta.py --by-ref`), captures from
`tools/harness/frames.py latest ICAO --kind capture`: KEGE
(`l1964/KEGE.pkl`), BIKF (`lkbna14/BIKF.pkl`), KATL (`lkatlWF2/KATL_m0.pkl`),
HECA (`lheca4/HECA.pkl`). KEGE and BIKF additionally against the
pre-lrjtt5 tree 721317bb0 (lrjtt5 did not replay them).

## 6. Bars

1. RJTT owner vertex: |z − DEM| ≤ 0.5 m (expected 8.15, +0.00); the seven
   siblings of §1 each within 0.5 m of their DEM.
2. RJTT, every member of `riser_rim_vertices`: not a spike or a pit —
   `min(DEM, lowest other vertex of its faces) − 0.5 ≤ z ≤ max(DEM, highest
   other vertex of its faces) + 0.5`. (v24308 and v28436 stand at their
   block's level over a lower DEM through `apron_trend`/bend rows; v20724
   and v28476 are tied to the block by hard rows: they pass this bar and
   are not this round's.)
3. RJTT `--verify`: `sentinel_elevation` 0, no DEFECT family above base;
   `--why-hard` count not above base.
4. Movers: airside 0 at RJTT, KATL, HECA, KEGE, BIKF; KEGE and BIKF
   ≤ 0.1 m anywhere (expected byte-identical: no level riser rim, to be
   confirmed); HECA expected byte-identical to base; KATL and RJTT movers
   listed by ref — expected only `…/p<k>#strip` rims and none on a level
   or block face above 0.05 m.
5. Report: net lines, new public symbol (`riser_rim_vertices`), the
   before/after table of §1 re-measured.

## 7. Stop conditions (report, do not iterate)

- Bar 1 misses after (a)+(b): stop; list every objective row on the vertex
  (wrap `solve.rows._Rows.add`, call `assemble(pm, cs, law, DesignReport(),
  fixed={airside vertices: z})` on the solved pickle's `pm`/`cs`, print
  owner, weight, coefficient, residual) and hand that table back.
- Any airside mover, or KEGE/BIKF > 0.1 m: stop; report the ref and the row.
- A level or block face moves > 0.05 m at RJTT or KATL (the body's datum
  shifting once the rims stop absorbing it): stop and report the pad's
  datum column and its rows — do not add a weight or a second exclusion.
- Do not widen (b) to collar rims or to the level's own vertices, and do
  not touch `body_datum`, `ground_datum` or bending weights.

## 8. Not in this round (for the master)

- The root of the residual is that a lower level and its riser, held a
  storey off the ground by law, sit in a body's DEM-plane fit at all (body
  19742: mean −4.05 m). Taking levels out of the fit moves every pad with
  levels (KATL, KMCI, LPHR) and needs its own measured round.
- `apron_trend` rows also name riser rims (v24308, v28436, v28476, v24298).
- `building75/p2` is held at −9.05 m (14 m under its DEM) in this replay;
  not attributed here.
