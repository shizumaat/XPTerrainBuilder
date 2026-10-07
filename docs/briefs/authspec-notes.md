# Lane `authspec` — resumption notes (2026-10-07, machine shutdown mid-lane)

## DONE (committed, a71782e7 + this)
- Spec §18 in `Ortho4XP/docs/specs/auto-patch-v2/object-placement-spec.md` (rule, witness, rulings table, consumer census, pits, owner questions, step plan). `docs/briefs/authspec-summary.md`.
- Attribution (ESTABLISHED, from the three pristine dumps in the shared mod cache): `authspec-scratch/wall_history.txt` (every cached dump's wall AGL, date order), `dsfdiff.py` output quoted in §18 (1): 09-11→09-17 only the 8 walls change materially; 09-17→09-28 88 resources lifted OBJECT→OBJECT_AGL (pits +4.2985 / +13.4978, bridges +4.0, ILS docks +3.0/+3.5).
- Today's terrain under each wall/pit anchor on `swg_OTHH` (ESTABLISHED): `authspec-scratch/probe1_today.txt`. 7 of 9 crests at 1.99–2.21 m over the cut with the authored seat; west 1 / west 3 stand over uncut ground (no cut today). Today's stage moves the 5 admitted walls −2.0 m (flush).
- Other sweep packs: rebake plans carry 0 plate members / 0 below-grade (HECA, KCLT, SPJC, KASE, CYXY) — §18 reads nothing there.

## PARTIAL / GUESSED
- The September terrain under the four refused walls is RECONSTRUCTED from the full-length ramp law and the model extents (§18 (2) prose), not measured; `tunnel west 1` is undecided (ramp → h 4.95, flat portal → h 2.4). The pit rim numbers (+0.48 / +0.36) assume the basin law cuts at the deepest floor plate (verified only on Drainage_06 basin:0: floor −0.239 = Z0 + feet_y).
- No replay was run (the sibling `othhwalls` worktree was mid-edit); no LEMD read.

## NOT STARTED
- Step 1 of §18 (8): on `claude/othhwalls` (c1f50c88 + main), `cd Ortho4XP && venv/bin/python tools/v2_solve_replay.py --replay /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/perfA362/cap/OTHH.pkl --from planar --json <scratch>/authspec/othh9.json` — then read each corridor's `floor_z` at its wall's anchor station to complete the §18 (2) table (9 of 9) and decide west 1.
- Register the probes: `tools/harness/frames.py register …` was not done.
