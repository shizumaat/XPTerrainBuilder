# gapapron3 — notes (lane resumes gapapron2; spec §59, RULINGS 2026-10-08c (6) / 08g)

Branch `claude/gapapron`, worktree `.claude/worktrees/gapapron`. Scratch
`<scratch>/gapapron3/`. Kept current after every step: done / partial / next
command / numbers.

## State

* DONE — main `d0b2f0f4` (walls branch) merged into the branch (`183edd34`;
  `docs/frames.jsonl` conflict resolved as the union).
* DONE — the dead lane's scratch read (`<scratch>/gapapron2/`), old tree
  (pre-walls), capture `gaps3/HECA.pkl`:
  * its arms, all stage-1-only ("base" mode: the late pieces dropped), all EXIT 0:
    `X0` = no piece apron (control), `X1` = 10 apron (gap:13 taken out of the
    class; its `solved.pkl` is gone, never compared), `X2` = 11 apron + its
    CANDIDATE RULE (`PROTO`: pass 1a solved without the rows that touch a
    gap-apron part's OWN vertices; pass 1b carries them under pass 1a's runway
    Bands).
  * `rw_dz.json` (unrounded, `gaps6/BASE` vs `gapapron/ARMBASE`): `05L/23R`
    worst 0.0172 m at v4219 30.12519288, 31.38877602; 4 nodes > 0.01, 88 > 0.005;
    `05C/23C` worst 0.0027 m; `05R/23L` 0.
  * read by this lane: `X0` vs `X2` (the PROTO): `05L/23R` worst 0.0081 m at
    30.12830117, 31.39221539, 0 nodes > 0.01, 40 > 0.005; `05C/23C` 0.0022;
    `05R/23L` 0. So the candidate halves the move and does NOT give 0 on the
    cm-rounded patch.
* RUNNING — fresh capture on this tree:
  `venv/bin/python tools/v2_solve_replay.py --capture HECA --out /Users/noah/XPTerrainBuilderData/.harness/frames/gapapron3/HECA.pkl`

## Next

S0 on the fresh capture: class table re-derived (`docs/briefs/gapapron/evidence_read.py`),
arms B0 (no apron) / B1 (all apron-class) stage-1 only, runway delta, then
intervention arms.
