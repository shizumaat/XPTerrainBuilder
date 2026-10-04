# Brief pack — lane `v2growth`

Base: main `bc036d1e` · generated 2026-10-04 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

# Scout v2growth — attribute v2's growth (read-only)

`src/auto_patch_v2/` was 26,646 lines on 2026-09-05 (24a561a9) and is 113,478 at bc036d1e (274 files; airport/ 41,387, planar/ 18,972, constraints/ 18,309, solve/ 6,943, pipeline/ 5,562, verify/ 4,946, classify/ 4,390, law/ 4,200, model/ 3,926, emit/ 3,098). The owner expected roughly 20k. Attribute the ~87k added lines; this report decides what gets consolidated.

Deliver, per package, with numbers and file:line citations:

1. Composition: code vs docstring vs comment vs blank (use the ast / tokenize modules, streaming per file; the session's awk estimate was about 49% code).
2. Growth by cause, from `git log --numstat` grouped by lane / issue: new scope (name it, e.g. object placement), ported v1 logic, per-site special cases, retired-but-kept gated machinery (default-OFF flags), dead code (public symbols with no importer outside their own file and tests).
3. Duplication: identical and near-identical function bodies across v2 files, and between v2 and the v1 KEEP set (`Ortho4XP/tests/test_v1_retired.py`); the ten largest groups.
4. The 23 files past 1,000 lines: for each, the responsibilities it mixes and the split that follows.
5. The same questions, briefly, for `src/O4_Airport_Elevation_Insets.py` (19,820 lines, eight `*Strategy` classes of 430–730 lines): what the strategies share, and the provider-package layout RULINGS 2026-10-04a (2) implies.
6. A ranked list of consolidation candidates with estimated lines removed and risk.

Measure; do not recommend rewrites. No airport runs, no edits, no suite runs.

THE FOUR NEVERS (single master): never comment on an issue, never merge, never create a routine/trigger or follow-up, never notify the owner. Report only in your final report.

## RULINGS

## 2026-10-04a — OWNER: FILE SIZE, RATCHETS AND THE ARCHITECTURE MAP (confirmed in session 2026-10-04; SUPERSEDES the numbers of 2026-09-13bz, keeps its sentence "split by responsibility, never fold comments to make a number"). MEASURED at main bc036d1e (tracked `.py` lines, comments and blanks included): v1 `src/auto_patch/` 130 files / 229,736 lines — the stage-B round-2 cut never landed (`claude/v1retire` @ 711f21b5, halted 2026-09-17, main 1,361 commits ahead; `tests/test_v1_retired.py` KEEP = 27 modules / 44,717 lines); v2 `src/auto_patch_v2/` 26,646 lines on 2026-09-05 → 113,478 (274 files; median 316, p75 594, p90 959, max 1,481; 23 files past 1,000); `O4_Airport_Elevation_Insets.py` 12,933 → 19,820 between 09-28 and 10-04 (eight provider strategy classes in one file, #130 #153 #154); 102 files under `Ortho4XP/src` past 1,000 lines. 13bz's twin covered `auto_patch_v2` only and refused at 1,500 — every other tree was unguarded. RULED: (1) **SIZE** — soft limit 600 lines (a PR that takes a file past it states why the file is not split); hard limit 1,000 lines for any NEW source file; a file already past 1,000 at the baseline is RATCHETED — it may shrink, never grow. Scope: `Ortho4XP/src`, `Ortho4XP/tools`, `tools`, `Sources`; tests are reported, not gated. (2) **ONE FILE PER FAMILY MEMBER** — a family (elevation providers, solver constraints, emit adapters, law tables) is a package with a base interface, a registry and one module per member; a new member is a new file, never an append. (3) **RATCHETS AT MERGE** — the size baseline and a duplicate count (functions with identical normalised bodies across files) may fall and never rise; v2's package order (plan table, 1 `airport/` … 7 `emit/`) becomes an import-direction check. (4) **THE MAP IS GENERATED** — `tools/blast.py --map <package>` / `--find <keyword>` from module docstrings and `__all__`; `tools/brief_pack.py` attaches the map of every package a brief touches; a twin fails a module with no docstring or no `__all__`. No hand-written class list. (5) **EVERY LANE REPORT / PR BODY** carries net lines added and removed and the new public symbols. ORDER: ratchets (lane `sizeratchet`) and the v1 cut (lane `v1cut`) in parallel, with scout `v2growth` attributing the 87k v2 lines; then the map tooling and layering check; then the insets split into a providers package.

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

