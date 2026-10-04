# Brief pack — lane `archmap`

Base: main `49fca06e` · generated 2026-10-04 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

# Lane archmap — the generated architecture map and the layering check (RULINGS 2026-10-04a (3)(4), 04c)

The owner's question: how does every agent see the whole architecture cheaply, so it reuses and extends what exists rather than writing new? Answer ruled: the map is GENERATED from the code, never hand-written, and the spawner puts it in the brief.

Measured: all 274 v2 modules have a module docstring; 263 declare `__all__`; but 373 names in `__all__` are used only inside their own file (over-exposure — it would make the map noisy).

Deliver:
1. `--map <package>` and `--find <keyword>`. `tools/blast.py` already parses and indexes the tree and self-rebuilds; extend IT (consult `tools/docq.py index blast` first; `blast.py` is 1,285 lines, so put the logic in a module beside it, as `tools/ratchets.py` did, with thin flags on `blast.py`).
   - `--map <package>`: one line per module — first docstring line + public names — sorted so a reader can scan it; target about 1.5k tokens for the largest package (`auto_patch_v2/airport`, ~75 modules). Works for `auto_patch_v2/<pkg>`, `auto_patch` (the 27 kept modules), `o4_engine`, the top-level `O4_*.py` modules, `Ortho4XP/tools`, and `Sources/` (Swift: file + its top-level types; a simple scan is enough).
   - `--find <keyword>`: functions / classes whose name or first docstring line matches, with signature and `file:line`, about 100 tokens for a typical answer. This is what a lane runs before adding a function.
   - `--map` with no argument: the package-level map (one line per package: what it owns).
2. HONEST INPUTS. A twin fails a v2 module with no docstring or no `__all__`. For over-exposure: `--map` shows only names imported by ANOTHER module (or declare-and-enforce some other rule you can defend); report how many of the 373 remain, and do not mass-edit `__all__` in this lane.
3. THE BRIEF CARRIES IT. `tools/brief_pack.py` gains `--map <package>` (repeatable) and attaches the map of each named package to the pack. Lane mover353 is editing the STANDING block's cache-variable sentence in the same file — keep your edit away from that sentence.
4. LAYERING CHECK for `auto_patch_v2`. The plan (`tools/docq.py spec --list`; `docs/specs/auto-patch-v2-plan.md` table of packages 1 `airport/` … 7 `emit/`) orders the packages. FIRST measure the actual package-to-package import graph and print it as a matrix; then propose the order that the code actually obeys and list every edge that violates it. The check is a ratchet like the duplicate count: recorded violations may fall, never rise (extend `tools/ratchets.py` and its baseline; do not write a second ratchet tool). Do not fix violations in this lane.
5. THE PACKAGE MAP FOR HUMANS AND SESSIONS: a short `Ortho4XP/src/CLAUDE.md` (about one screen; loads only during engine work) that says: run `--map` / `--find` before adding code; the package order; where a new family member goes. It must not restate what `--map` prints. The master reviews and applies this file — write it as `docs/briefs/archmap-src-CLAUDE.proposed.md` and say so in your report; do not create `src/CLAUDE.md` yourself.
6. `tools/INDEX.md` rows; twins (map is stable and deterministic; `--find` finds a known symbol; the layering ratchet fails on a new upward import in a synthetic tree).

No engine code changes; no airport build.

Avoid: everything under `Ortho4XP/src` except reading it; the STANDING cache sentence in `brief_pack.py`.

THE FOUR NEVERS (single master): never comment on an issue, never merge, never create a routine/trigger or follow-up, never notify the owner. Final report only: branch, sha, sample `--map auto_patch_v2/airport` size in characters, a sample `--find` answer, the import matrix, the proposed order and violation count, tests run, net lines, new public symbols, every item NOT done.

## RULINGS

## 2026-10-04a — OWNER: FILE SIZE, RATCHETS AND THE ARCHITECTURE MAP (confirmed in session 2026-10-04; SUPERSEDES the numbers of 2026-09-13bz, keeps its sentence "split by responsibility, never fold comments to make a number"). MEASURED at main bc036d1e (tracked `.py` lines, comments and blanks included): v1 `src/auto_patch/` 130 files / 229,736 lines — the stage-B round-2 cut never landed (`claude/v1retire` @ 711f21b5, halted 2026-09-17, main 1,361 commits ahead; `tests/test_v1_retired.py` KEEP = 27 modules / 44,717 lines); v2 `src/auto_patch_v2/` 26,646 lines on 2026-09-05 → 113,478 (274 files; median 316, p75 594, p90 959, max 1,481; 23 files past 1,000); `O4_Airport_Elevation_Insets.py` 12,933 → 19,820 between 09-28 and 10-04 (eight provider strategy classes in one file, #130 #153 #154); 102 files under `Ortho4XP/src` past 1,000 lines. 13bz's twin covered `auto_patch_v2` only and refused at 1,500 — every other tree was unguarded. RULED: (1) **SIZE** — soft limit 600 lines (a PR that takes a file past it states why the file is not split); hard limit 1,000 lines for any NEW source file; a file already past 1,000 at the baseline is RATCHETED — it may shrink, never grow. Scope: `Ortho4XP/src`, `Ortho4XP/tools`, `tools`, `Sources`; tests are reported, not gated. (2) **ONE FILE PER FAMILY MEMBER** — a family (elevation providers, solver constraints, emit adapters, law tables) is a package with a base interface, a registry and one module per member; a new member is a new file, never an append. (3) **RATCHETS AT MERGE** — the size baseline and a duplicate count (functions with identical normalised bodies across files) may fall and never rise; v2's package order (plan table, 1 `airport/` … 7 `emit/`) becomes an import-direction check. (4) **THE MAP IS GENERATED** — `tools/blast.py --map <package>` / `--find <keyword>` from module docstrings and `__all__`; `tools/brief_pack.py` attaches the map of every package a brief touches; a twin fails a module with no docstring or no `__all__`. No hand-written class list. (5) **EVERY LANE REPORT / PR BODY** carries net lines added and removed and the new public symbols. ORDER: ratchets (lane `sizeratchet`) and the v1 cut (lane `v1cut`) in parallel, with scout `v2growth` attributing the 87k v2 lines; then the map tooling and layering check; then the insets split into a providers package.

## 2026-10-04c — OWNER: 1,000 LINES IS A GUIDE AND A WARNING, NEVER A GATE; BANK PASS DELETED; DIAGNOSTICS LEAVE THE ENGINE PACKAGE (amends 04b (1); decides three questions from scout `v2growth`). Owner (verbatim): "The 1000 line should be a guide and warning, not a hard limit that results in code being split just to meet it and resulting in more mess and confusion. The goal is splitting functionality, and writing clean, human readable, easy to understand code that also is the most efficient for each new session to fix and add to." RULED: (1) **SIZE NEVER FAILS A TEST OR A MERGE.** `tools/ratchets.py` reports files past 1,000 lines and files that grew, as a warning the master reads at merge; `--justify` stays as an optional note, not a pass condition. A split is made because a file holds two responsibilities, never to reach a number — the 71 v2 files that cite the line law in prose and the two at exactly 999 lines are the anti-pattern. The same applies to FUNCTIONS: 38 v2 functions run 200+ lines (`pipeline/build.py::build` 890, `planar/structures.py::build_structures` 867, `airport/placement_plan.py::build_splits` 833); they are reported the same way and are the better target. (2) **THE DUPLICATE RATCHET STANDS** (identical bodies may fall, never rise; near-duplicates reported): a second implementation of an existing thing is the defect this round exists to stop. (3) **THE BANK PASS IS DELETED** — `bank_omit = true` has shipped since 13cy; `emit/bank.py`, `emit/terrain_edge.py`, `emit/seam_band.py` and the bank law keys go, `coverage_polygon` (used by `emit/road_join.py`) moves to a geometry module. Output must be byte-identical. (4) **DIAGNOSTICS MOVE OUT OF `auto_patch_v2`** to `Ortho4XP/tools` (the why / explain / census / xplat reporting, ~6,050 lines) wherever production does not call them; anything production calls stays and is named. (5) **RULING-HISTORY PROSE IN SOURCE STAYS** as it is. MEASURED by scout `v2growth` at 208380fd: v2 113,478 lines = code 57.7%, docstring 20.7%, comment 12.3%, blank 9.2%; the plan budgeted 20,100 with no object-placement stage; growth since 09-05 is scope — object placement +27,541, structures +15,799, pads/platforms/terraces +11,765, groundside roads +6,809 (71% of +86,832); duplication ~500 lines, dead top-level symbols 1,036 (lower bound), gated-off ~1,700.

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file. SIZE (owner 2026-10-04c, `tools/ratchets.py`): 1,000 lines is a guide and a
  warning, never a gate — the report (files past 1,000, files that grew, functions of
  200+ lines) is read by the master at merge. Split by responsibility, never to make a
  number. THE PRIORITY IS REUSE: small one-responsibility modules, no second
  implementation of a thing that exists (the identical-body duplicate count IS a gate:
  it may fall, never rise; `dupes --near` is reported).
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
  intent questions with their measurement; files touched; net lines added/removed
  + new public symbols (owner 2026-10-04a (5)).

