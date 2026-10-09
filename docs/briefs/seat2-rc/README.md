# claude/seat2-rc — the §62 sub-steps that were STOPPED (not for merge as is)

This branch carries, on the lane's pre-merge base (b6eecfed), the whole tree lane `seat2` measured its stopped arms on:
R-F (full) + R-C rules 1 and 2 in the spec's own one-way hard form (`constraints/pad_seat.py`, the hard ∩ one-way lag in
`solve/design.py`), R-B (`road_ramp.frontage_release`) and R-D rule 1 (which DID land, on `claude/seat2`).
Numbers and verdicts: `docs/briefs/seat2-notes.md` on `claude/seat2`.

Known red on this tree: five twins of `test_road_descent.py` / `test_surfacesettle2.py` call `reach_seed_rewrite` on a
stub map `frontage_release` cannot read.

Reference files (text copies, not imported):
* `pavement_cap.airside_half.py.txt`, `test_pavcap_seated62.py.txt` — R-F restricted to airside-seated pads (probe `f`).
* `test_roadfrontage62.py.txt` — R-B's twins as a file of their own.
* `armT.py.txt` — the two-way seat probe driver; `d2_patch.py.txt` — the R-D rule 2 floor-merge probe.
