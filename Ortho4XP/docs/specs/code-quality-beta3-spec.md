# Code quality for Beta 3 — spec (2026-10-17, W8)

Status: PROPOSAL. Plan: `beta3-build-speed-plan-20261017.md` W8 and W2. Issues:
manifest B3-20 … B3-25 and the #740 comment. The clean-up itself is #740's
plan (`unused-code-plan-20261015.md`); this spec adds what the comparison
found and #740 does not cover, and the addendum to that plan carries the new
wave and rows.

## 1. Duplicate v1/v2 readers — #740 addendum wave F (B3-20)

Verified line counts (2026-10-17): `auto_patch/apt_dat_reader.py` 1,976 vs
`auto_patch_v2/airport/apt_dat.py` 823; `dsf_reader.py` 2,485 vs `airport/
dsf.py` 661 (the duplicate ratchet already flags `dsf_reader.py:1136` vs
`airport/dsf.py:603`); `obj8_reader.py` 587 vs `airport/obj8.py` 1,518;
`cifp_reader.py` 252 vs `airport/cifp.py` 168; `flat_site.py` 892 vs
`airport/flat_site.py` 486. Live callers outside tests:
`apt_dat_reader` — `tools/harness/build_airport.py` (`find_airport_apt_dat`),
`auto_patch/{driver,engine_v2,post_mesh,…}`; `cifp_reader` —
`O4_Airport_Elevation_Insets.py`, `o4_engine/patch_commands.py`; `flat_site` —
`auto_patch/flat_site_mode.py`; `dsf_reader` — `O4_Default_Terrain_Map.py`,
`o4_engine/pack_objects.py`, `auto_patch_v2/airport/{dsf,dsf_write,load,
object_pavement}.py`, `auto_patch_v2/planar/__main__.py`, eight `tools/`
scripts and seven `tools/attic/` scripts (`grep -rln` 2026-10-17; the lane
re-derives the exact list with `blast.py` before each cut).

Wave F, one lane per pair, smallest first (cifp → flat_site → obj8 → apt_dat →
dsf): (1) a behaviour table — every public function of the v1 reader, its v2
counterpart or "no counterpart", and the callers; (2) a pair that differs in
behaviour is an OWNER QUESTION, not a choice (the #740 wave E rule); (3)
callers re-pointed; (4) the v1 module removed from `tests/test_v1_retired.KEEP`
and deleted; tools that die with it are retired with their `tools/INDEX.md`
rows; (5) gate: sweep patches byte-identical, `blast.py --tests-for` tests,
undefined-name scan, the duplicate ratchet falls. `tools/attic/` (17 files,
4,108 lines) joins wave C: a script nothing imports and no index row names is
deleted with the readers it called.

## 2. Coded-error registry (B3-21)

What exists (correcting the findings): the registry is
`src/O4_Tile_Failures.py` — `CATALOGUE` (code → what/why/remedy), `REMEDIES`,
`EXCEPTION_CODES`, `STAGE_CODES`, `code_for_exception` (class/attribute/errno,
never message text) — with registry twins in `tests/test_tile_failures.py`
(every exception class and every error exit has an entry). `o4_engine/
failure_report.py` RENDERS a failure (#565); `BuildDone.failures/warnings`
carry `{code, what, why, remedy, airports, detail}` on the wire (protocol
1.10), Swift parses `code` as a string (`OrthoEngineClient.swift:388`).

What E has that we do not: a domain prefix, a severity (`blocking|degraded|
info`) and a scheduler action per code, and the DEGRADED class — an output
produced but not as asked (white-squared textures, a mask not built, an inset
not fetched), today a `UI.vprint` at best.

Design (additive; codes are never renamed — `code` values are wire data):

- `Entry` gains `severity` and `domain` fields (defaults `blocking`, derived
  domain from the code's first word for existing entries); `CATALOGUE` gains
  the degraded codes found by a census of silent degradations (the lane's
  first deliverable: every `incomplete_imgs`, inset-skip, mask-skip and
  "WARNING" print that changes output, one row each with its site);
- `BuildDone.warnings` (exists) carries degraded entries for a BUILT tile, the
  same shape; `severity` is a new optional key → protocol 1.13, additive; the
  Swift and Qt renderers show it when present;
- the twin extends: every code matches `^[a-z][a-z0-9_]+$`, has a severity and
  a domain in the declared set, a remedy key in `REMEDIES`; every
  degradation site found by the census names a code (the census file is the
  test's table, E's `errors.md` pattern); the wire twin
  (`test_engine_jsonl`) checks the new key is optional.

Files: `src/O4_Tile_Failures.py` (stdlib only — keep), `src/o4_engine/
events.py` (WIRE: class names are JSONL names; add a key, rename nothing;
blast reports `ImageryDownloadsDone` drift already — fix in the same lane),
`Sources/SceneryKit/OrthoEngineClient.swift`, `src/O4_Qt_Tile_Failures.py`.

## 3. Long functions and `check_grade.py` — #740 step-4 rows (B3-25)

`tools/ratchets.py funcs` (2026-10-17): 124 functions ≥ 200 lines; the four
past 1,000: `O4_DSF_Utils.py:814 build_dsf` 1,349; `auto_patch/object_anchor.
py:2346 structure_deltas` 1,240 (wave A deletes it); `tools/check_grade.py:
13422 run_checks` 1,215; `auto_patch_v2/pipeline/build.py:645 build` 1,046.
`check_grade.py` is 14,715 lines and IS the harness library (`LAW_FAMILIES`,
`run_checks`, `law_context_from_sidecar`; `tests/test_harness.py` twin-asserts
one code path with the census).

Split rule (the #740 step-4 rule: by responsibility, behaviour identical):

- `check_grade.py` → a package `tools/check_grade/` with `__init__.py`
  re-exporting today's public names (every importer unchanged), one module
  per law family under `families/` registering into `LAW_FAMILIES` on import
  (the "one file per family member" rule, RULINGS 2026-10-04a (2)), the
  frame/sidecar/ruleset context in `context.py`, `run_checks` reduced to the
  dispatcher. Gate: the census of every sweep patch byte-identical before and
  after (`tools/harness/census.py` output diffed), `test_harness` green. One
  lane per 4–6 families; the first lane builds the package and moves two.
- `build_dsf` → the W7 helpers are its first cuts (one per loop); the
  texture-mode branches follow `texture-mode-spec.md`'s structure.
- `pipeline/build.py::build` → one function per stage block (load/pack,
  classify/planar, shapes/constraints, solve, emit/verify) returning the
  `wall` entries; behaviour identical, report JSON identical; this is also
  what the stage cache (W4) needs to wrap stages.

## 4. ADRs beside RULINGS (B3-22; owner Q7)

`Ortho4XP/docs/adr/NNNN-<slug>.md`, one page: Date, Status (proposed /
accepted / superseded by NNNN), Context, Decision, Consequences. Never
rewritten; a change is a new ADR that supersedes. `docs/RULINGS.md` stays the
canonical owner law (append-only, 9,983 lines today); a ruling that is also an
architectural decision gets an ADR and the ruling links it; `tools/docq.py adr
NNNN` reads one. First five, each a one-line summary of an existing ruling:

1. `0001` v2 is the only engine; v1 survives as readers and the object stage
   (RULINGS 2026-09-13au, `src/auto_patch/CLAUDE.md`).
2. `0002` One shared data repo; downloads are explicit ledgered events
   (RULINGS `e9daef5`).
3. `0003` No airport-specific code (RULINGS 2026-10-05e).
4. `0004` Synthetic-first iteration; one closing build; the sweep per merged
   batch (BUILD ECONOMY, 2026-08-29e/f).
5. `0005` Content-keyed derived caches with witness-on-read and pristine
   inputs (partition cache 2026-08-13, #362, #382; this plan's W1/W4).

Twin: `tests/test_adr_index.py` — numbering contiguous, every file has the
five headings, a superseded ADR names its successor and the successor exists.

## 5. ruff in CI as a baseline ratchet (B3-23; owner Q8)

`.github/workflows/ci.yml` runs pytest and swift only; `ruff` is not in the
venv or `requirements.txt`. Proposal: `ruff` pinned in the CI dev tail
(`reqs-ci.txt` recipe, `ci.yml:183-196`), rule set `E, F, W, I, B` (E's set
minus `UP, SIM, N, RUF` — those reformat idioms), line length 100,
`target-version py313`; **no `ruff format`** (a reformat of 270k lines would
bury history). `tools/ratchets.py lint` reads `ruff check --output-format
json --statistics` and records the count per rule in `ratchet_baseline.json`
(`lint: {E501: n, …}`); a count may fall and never rise — the duplicate
gate's shape, same `--regenerate` discipline. CI step: `ratchets.py lint`
fails on a rise. A rule whose baseline is zero becomes a hard gate for free.
Files touched: `tools/ratchets.py`, `tools/ratchet_baseline.json`,
`pyproject.toml` (new, `[tool.ruff]` only), `ci.yml`, `requirements.txt`
comment. Both MIT trees (`tools/`) and GPL trees (`Ortho4XP/`) are linted;
the config file sits at the repo root.

## 6. Frozen reference fixtures for the inherited stages (B3-24; W2; owner Q10)

We have census and oracle instruments for airport law and none for the
inherited `O4_*` vector → mesh → DSF stages: a change there is gated by
"one tile builds and looks right". E froze upstream Ortho4XP output as its
oracle (`p2-build.md` §4). Ours cannot be upstream's (patches, insets, the
object stage); it is OUR output, frozen once:

- a synthetic mini window: a 0.02° × 0.02° DEM window (36-px margin as the
  mesh step expects), a hand-written `.poly/.node` with one water polygon and
  one patch ring, no imagery (`default_xplane` texture mode); produced by a
  recipe script `tools/fixtures/make_mesh_dsf_fixture.py` on a machine with
  Triangle4XP, committed under `tests/fixtures/mesh_dsf/` if ≤ 2 MB
  (`.node/.poly/.1.node/.1.ele/.mesh/.dsf` + a `MANIFEST.json` of sha256s);
- twins: `tests/test_mesh_dsf_oracle.py` — `post_process_nodes_altitudes` +
  `write_mesh_file` on the fixture inputs reproduce the `.mesh` bytes;
  `build_dsf` on the fixture reproduces the `.dsf` bytes (MD5 footer
  included); skipped where Triangle4XP is absent only for the Triangle step
  itself (its outputs are in the fixture);
- a change that MUST move the bytes regenerates the fixture in the same PR
  with the reason in `MANIFEST.json` (the ratchet-baseline discipline).

This is the gate W3 and W7 stand on; it lands before them.

## 7. Out of scope

Deleting code (that is #740's waves A–E); mypy (E does not enforce it either);
any engine behaviour change; renaming failure codes.

## Licence

Formats and ideas (ADR layout, registry fields, oracle fixtures) are generic
and re-implemented; no E code. `tools/` is MIT, `Ortho4XP/` GPL-3.
