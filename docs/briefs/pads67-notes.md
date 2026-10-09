# pads67 notes — `claude/pads63` (PR #480) merged up to main `729e140d`, the seven-airport read, and THE EDGE READ for RULINGS 2026-10-09d (1)

Scratch `<scratch>/pads67/` (`.progress`; `build.sh` / `hold.sh` / `inst.sh` = pads66's, retagged `sw8_`, references `sw7_*` and
`surf337b_OTHH`).

## Step 1 — the merge (`4b433195`)

* `tools/harness/lane_worktree.sh up pads67 origin/claude/pads63` → `git switch -c claude/pads67` → `git merge origin/main`.
* ONE conflict: `docs/frames.jsonl` (both sides appended) — both kept, 1,028 rows, every row parses.
* Spec: auto-merged, no heading collides — pads carry §56 / §57, main carries §59 / §60; nothing renumbered.
* Suites on `4b433195`: non-Qt split `9097 passed, 19 skipped, 1 xpassed` (283 s).

## Step 2a — `tools/pad_edge_read.py` (bank.py promoted on its second use; INDEX row; twin `tests/test_pad_edge_read.py`, 6 passed)

Reads one build's `ICAO.graded.json` + the build's DEM off any capture pickle of the airport (`airport.dem`; the patch carries no
DEM). Per pad-rim vertex: non-pad cells touching or within 10 m, and the uncovered DEM on 8 bearings at 2 / 5 / 10 m. Flagged when
anything stands > 1 m off the rim. Classes: `P` pavement itself off (touching, or within the 3 m stand-off): seat candidates; `M`
pavement at the rim's level beside a bare bank; `S` graded strip only; `B` bare. Runs = same-class chains along one pad's rim.

## Step 2b — the builds (`sw8_<ICAO>`, harness through the ledger, tree `88e925bb` / `38f2ba5a` = the merge + tools only)

Progress (references `sw7_*`, OTHH `surf337b_OTHH`; each census under its own tree's tool):
* CYXY rc 0, body cf8e9e89ec62 → b20103c51fd7 (= pads66's `swq`), runway movers 0, structure 0.
* NLWF rc 0, 45ec40e74dcb → 369eabe9dfef (= swq), 0 movers in every frame.
* KASE rc 0, f9b157158a39 → 718538f4d2e2 (= swq), runway 0, structure 0.
* SPJC rc 0, 61f66f149737 → 3ef3e7c7013d (= swq), runway 0, structure 8 ≤ 0.05.
* Edge reads (`<scratch>/pads67/edge_<ICAO>.{txt,json}`): CYXY 16 runs (P 2), NLWF 5 (P 0), KASE 6 (P 0), SPJC 66 (P 6).
