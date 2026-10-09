# surf337 — notes (implementing spec §60: a `.pol` admitted by its own SURFACE is a gap sheet; #337; RULINGS 2026-10-04e (1), 2026-10-09a, 09b)

Lane `surf337`, branch `claude/surf337` off main `e2eec15c` + `claude/surfspec` (docs).
Scratch `<scratch>/surf337/`. Updated after each step.

## Step 1 — the gate (`6e55b6bc`)

`airport/dsf.pavement_verdict(path, decl) -> "source" | "sheet" | None`;
`is_pavement_def` = `== "source"`; `pol_declaration` / `PolDeclaration` replace
`pol_surface`; `pavement_gate` returns `(verdict, surface)`. Suite 9016 passed.

NON-BLOCKING DOUBT, decided toward the spec's stated invariant ("every
existing `dsf:pol<i>` id stays as today"): §60 (1) step 4 says "source when the
NAME also carries the `conc` word". A name with the `conc` word AND a
paint/sign word (`g/conc_lines.pol`) is REFUSED by main's name gate; if its
file declares a hard surface on a non-paint layer, a literal reading would
make it a NEW source (a new `dsf:pol` index). Built: a source is exactly what
the name alone admits (the `conc` word with no decorative word); that page is
a SHEET. Pinned by `test_a_source_is_exactly_what_the_name_gate_admitted`.
No such def exists on the seven measured packs.

## Step 2 — the population site

`airport/load.py`: a sheet page is read from the dump, consumed before the
polygon index advances, passes the 1,000 m admission (`n_far`), and is
appended to `Airport.gap_sheets` after the object bodies. `LoadReport`
`dsf_gap_sheets`, `dsf_gap_sheet_m2` (the raw page area after the admission —
NOT clipped to the classify gate as the spec's probe number was).
`pipeline/build.py`: one `[load]` line. Twins (a)–(c) in `test_airport_load.py`.
NO-OP: fresh CYXY capture on this tree (14 s) → `--from classify --emit`
body `cf8e9e89ec62` = main's `sw6_CYXY`. Suite 9019 passed.

## Step 3 — mint twin (d)

`test_a_page_sheet_on_a_runway_cell_mints_nothing_and_lists_nothing`.

## Step 4 — ONE tool

`Ortho4XP/tools/pavement_admission_report.py` ported from 2f348508 (`refused`,
`diff`) and the spec's `admit_probe.py` promoted INTO it as the `sheets`
subcommand (INDEX row; twin 4 tests). The probe's own copy of the branch gate
and its control/arm mint re-run are gone: the gate is the tree's, and the
control arm is `--strip-out` (the capture without its page sheets, replayed
`--from classify`). Six `surface337` frame rows ported to `docs/frames.jsonl`.

`sheets` on the registered captures (this tree's gate; polygons source / sheet / refused):

| ICAO | capture | source / sheet / refused | hard-surface defs refused, why |
|---|---|---|---|
| CYXY | fresh, this tree | 44 / 0 / 20 | `lib/airport/markings/DrapedDirSigns` 20 — decorative namespace |
| SPJC | conc333 main28500ecf | 107 / 0 / 284 | `objectfede/lines/red_grid` 46, `lib/airport/lines/safety_area_red` 42, `_yellow` 4 — decorative namespace |
| KCLT | conc333 | 101 / 0 / 1,858 | `DrapedDirSigns` 958 (namespace), `DrapedRwySigns` 759 + `ground_marks/mark_dir_amarillo` 115 (paint layer), `safety_area_white` 21, `colored_area_green` 1, `safety_area_yellow` 1 (namespace) |
| KASE | conc333 | 9 / 0 / 25 | none declares a hard surface |
| NLWF | conc333 | 0 / 0 / 2 | none |
| OTHH | surface337 main900727f2 | 70 / 281 / 8,446 | 6 sheet defs, 5,314,001 m² in the gate (712,279 on runway cells, 1,880,707 taxi, 822,710 apron); refused: markings namespaces 1,812, `Grass3` 3 (terrain word) |
| HECA | gapapron3 | 1 / 2 / 0 | `Asphalt_1_NOLINE` 2 / 63,175 m² |
