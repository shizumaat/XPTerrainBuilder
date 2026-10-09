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
