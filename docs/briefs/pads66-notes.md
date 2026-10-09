# pads66 notes — finishes `claude/pads63` (PR #480) for the master's merge, 2026-10-09

Scratch `<scratch>/pads66/` (`.progress`; `build.sh` / `hold.sh` = the sweep builds, serial, held on other lanes' engine work with a 20 s
poll; `inst.sh ICAO` = one airport's whole read against its main reference, each census / feet under its own tree's tool; `zat.py`
= the surface at a coordinate on two graded.json; `bank.py` = the pad-rim bank read; `fam.py`, `feetbins.py`, `rw.py`, `feet10.sh`).

## Item 1 — `airside_no_step` reads the pad-weld face allowance (`ffd3dde2`)

* `tools/check_grade.py` `_check_published_law_edges(..., weld_nodes=)`: the §1.1 published route pair answers to `budget_m +
  _weld_give(...)` — the ONE reader the three pavement families use — with `d` = the record's `dist_m` (the ROUTE distance the
  engine's `Diff` row is stated on, which is what `weld_floor.widen_face_rows` multiplies `delta` by). The lattice family calls
  the same function without the argument and reads as before.
* DEVIATION 2 of pads65 closed: the sidecar now carries the set itself. `constraints/no_step.hold_interval` writes
  `weld_widened.face_nodes` = the 11-dp coordinates of the vertices of the faces the closing contacts touch (`face_widen[pref][0]`
  — the very set `widen_face_rows` and `pair_graph(bump=)` test membership in), and `weld_widened_nodes(nodes, platforms)` joins
  by identity. The `ways` argument and the join by way `ref` are gone (a `ref` names every face of an apron: at HECA `pav39` is
  20 faces, the contacts touch 2 of them + the plateau face; `face_nodes` 348). The record's `faces` refs stay, informational.
* Twins: `tests/test_weld_floor_census.py` (the face join by identity, a record with refs only reads nothing, the no-step pair on a
  widened face over its route distance / one end off / under-allowance / no record), `tests/auto_patch_v2/test_nearmiss148.py`
  (the engine's record carries `face_nodes`, a subset of the listed face's vertices that contains the near-miss contacts).
* Bodies are unchanged by it (sidecar key only): KASE 718538f4d2e2, SPJC 3ef3e7c7013d, HECA 527f80ef55e7, KCLT e52fc9b4c757,
  OTHH 96d1b4d6cfbc = pads65's `p65_*`.
* HECA re-read (`swq_HECA`, rows within 200 m of `building147`'s west contact 30.12910063740, 31.40069373691): **16 → 7** (bar
  ≤ 4: MISSED by 3). 6 `apron|junction` direct rows 1.63–1.76 % over 94–135 m + the one `apron|apron` RATE row. The 6 are pairs
  with ONE end outside the engine's widened set — two junction vertices of `pav39` faces the contacts do not touch
  (30.12993504303, 31.40049126053 and 30.13017406863, 31.40023697366) — over their unwidened budget by 0.13–0.20 m; no
  `hard_conflict` is recorded within 250 m in the taxi tier. Under pads65's ref join they were allowed (the over-allowance);
  under the engine's own set they are rows the engine did not widen and the emitted surface does not meet. NOT attributed
  further (attempt cap; the seat review's "spill into rows the widening does not name": 62 at p64, 6 now). Family total
  4,026 (main) → 4,038; adjudicated airside 12,204 → 12,010 (p65 under the ref join: 12,024).
* The `apron|apron` 3.33 % row (30.128918, 31.399319, way -10255) is a §1.2 RATE row (grade CHANGE 3.33 %/station over 37.9 m,
  |dz| 0.35) — the weld allowance is a grade allowance and does not apply to it. It is NOT on main's `swga_HECA`: main's one row
  within 200 m is a different rate row (2.69 % over 28.2 m at 30.12908, 31.40090, way -10218).

(the sweep table, the owner sites and the pad-rim bank follow below as they are measured)
