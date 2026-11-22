# Fastest solve pipeline (#2206, RULINGS 2026-11-21a) — Fable design, 2026-11-21

Bar (21a): wall time, at a result within ±1 m of the current one with zero new grade violations. "Exact" = patch bytes unchanged.
Code citations on origin/claude/lonesolve 42d258cae, under Ortho4XP/src/auto_patch_v2/.

## Measured (app report.json, 1.0.569)
| | KATL | KDFW |
|---|---|---|
| total | 3,873.8 | 1,539.6 |
| partition / classify | 39 / 215 | 81 / 75 |
| planar / constraints | 241 / 84 | 223 / 199 (channels 116.7) |
| solve clock | 583.6 (stage 1 148.9, stage 2 333.9) | 148.0 |
| late cut / derive / solve | 101 / 1,955 (×3) / 35 | 18 / 298 (×1) / 2 |
| emit / verify | 90 / 262 (lateral_contiguity 165.6) | 27 / 379 (lateral_contiguity 294.8) |
Fleet (58 builds >300 s): late derive 30.7 %, solve 20.0 %, planar 15.6 %, classify 7.2 %, partition 6.8 %, verify 5.2 %, constraints 4.3 %. Stage-2 pin yield released pins at only 3 airports (KGYY, LFAQ, LFFE) but every build pays ≥1 extra full stage-2 solve. Straddling airports build twice (LFPG 5,662 + 5,607 s, 0 of 324 cache keys shared).

## Target
load → partition → classify; worker: stage-1 map started at classify end; main: ONE full map (base + ribbons + late cells in pre-solve geometry) → planar → channels → constraints once; stage 0/1a/1b with retargets folded; stage 2 one full solve, late followers dormant, pin yield as a local solve; late solves on the same map (views), no derive; post-solve true-cut check (fallback re-derive); emit → verify. Derives 5 → 2; full stage solves ~9–11 → 4.

## Changes, biggest safe win first
| # | change | KATL s | KDFW s | kind |
|---|---|---|---|---|
| 0 | land lonesolve's one late derive (+ LGAV dissolve, measured) | ≈ −1,300 | 0 | 21a |
| 1 | verify `lateral_contiguity` nearest-cap via cKDTree (contiguity.py:86; same at structures.py:239, frontage.py:68) | −160 | −290 | exact |
| 2 | stage-2 pin yield as a local solve (pin_yield.py:196/205; design.py:343-353; also flex.py:73-100): free within 150 m of candidates, rest constant; round 1 falls back to global if a pin is forced | −190 | ≈ −55 | exact (r1) / 21a (r2) |
| 3 | late cells ride the main derive (3a gating measurement of pre-solve vs solved cut; 3b pre-solve exits/run-outs sized from predicted pad level + margin, true cut checked after, fallback re-derive; 3c one map, followers dormant via a new assemble argument — NOT `drop`; car lots cut in planar between pass B and C; filter dormant rows before assembly) | ≈ −590 | ≈ −270 | 21a + R1 |
| 4 | fold stage-1 retarget passes (15i(3) trend, #517 hold, weld re-widen) into the passes that first carry their rows | ≈ −80 | ≈ −8 | 21a |
| 5 | start stage-1 derive at classify end; hand decks after structures, anchors after channels; digest check kept | ≈ −100 | ≈ −4 | exact |
| 6 | profile-led: 6a per-stage solve/planar clocks; 6b KDFW channels; 6c pool generators (junction_mesh 36–38 s); 6d classify + late cut (extend_pad_roads); 6e front memo served (one Airport object); 6f stage-cache writes off-thread; 6g §5a LP memo when hard set unchanged; 6h planar RJTT/LOWS/LFPG/KJFK | ≈ −250 | ≈ −165 | exact |
| 7 | one build per airport across tiles (in-flight lock) + stable keys (#2205) | 0 | 0 (LFPG/KORD/KIAH/KPHX: one whole build) | exact |
| 8 | shadow solve only near decks (stage_shadow.py:30-58), bar 20b | KRDU −75 | 0 | 21a/20b |
Not now: stage 1 as a view of the main map (different pad set in 35/58 builds; 1.10 m at HECA); CHOLMOD (frozen-engine dependency).

## Running totals (as-measured, loaded)
1.0.569 KATL 3,874 / KDFW 1,540 → after 0: 2,570 / 1,540 → 1: 2,410 / 1,250 → 2: 2,220 / 1,195 → 3: 1,630 / 925 → 4,5: 1,450 / 913 → 6: ≈1,200 / ≈750.

## Owner ruling needed
R1: may pad-road exits and ramp run-outs be sized before the solve from the pad's predicted level plus a margin (≈0.5–1 m → 10–20 m more road at 5 % at ground level; no ramp steeper)? Recommendation: yes — it makes one derive possible; without it 52/58 airports keep a late derive.
Covered by 21a (record, don't ask): item 4 amends 2026-10-15i (3)(b) and 2026-10-08d (2); item 3's knives from predicted levels amend §55's "cut by the base's levels".

## Not verified
Solve call counts (walls confirmed, counts from lonesolve); item 0's ≈1,300 s is an estimate; no KATL/KDFW capture exists (frames MISSING); no profile taken (item 6 seconds estimated).
