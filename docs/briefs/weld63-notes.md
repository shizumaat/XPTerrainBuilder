# weld63 notes — implementing spec §63 (a cell touching a pad in the source is welded; a gapped cell is free)

Lane `weld63` (Opus, implementation). Worktree `.claude/worktrees/weld63`, branch `claude/weld63` off
`origin/claude/chainlag` ded211fb + `origin/main` 116152e0 (docs-only). Scratch `<scratch>/weld63/` (`.progress`).
Master rulings carried in the brief: Q-A YES (a §28 (6) held terrace > 2.4 m keeps the knife); Q-B = 09j literal
(a landside pad keeps its own seat, the touching road / lot comes to it within its cap).

## Sub-steps

| step | commit | state | what |
|---|---|---|---|
| S | (this) | landed | `constraints/pads._airside_only` drops every groundside role: a pad fronts airside or nothing (its §9b datum). Twin `test_v2frontage::test_a_pad_between_a_road_and_a_lot_keeps_its_datum_and_takes_no_level_row` (red before, green after); 80 pad tests green. `pad_seat.py` / R-C / the solver change were never on this tree. |
| T | | next | |
| W | | | |
| B′ | | | |
| P / L | | | |
