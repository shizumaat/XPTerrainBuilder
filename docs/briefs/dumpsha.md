# Brief pack — lane `dumpsha`

Base: main `26c093f0` · generated 2026-10-04 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

# Lane dumpsha — a pack DSF text dump is found by the DSF's content, not by its file name

Found by sweep1032 (2026-10-04), reported by the landing master; an issue is being filed by that session (ask the master for the number before you write the commit message).

THE DEFECT, as reported (verify every statement before acting on it):
- After the app's object-stage rebake of OTHH at 13:05, a harness OTHH build was REFUSED: the engine asked for `Airport_mod_cache/Aeroscape OTHH Hamad Intl/+25+051.dsf.anchor_bak.4229c95f.text`, which does not exist — while `+25+051.dsf.4229c95f.text`, same sha `4229c95f`, same bytes, is already in the shared corpus.
- So the dump lookup is keyed on the DSF's FILE NAME plus the content tag, and a renamed copy of the same DSF (the rebake's `.anchor_bak` backup) misses a dump that exists.
- Sites named: the loader at `auto_patch_v2/airport/load.py` ~424–433 and `dsf.find_text_dump`; the harness's `missing_pack_dsf_dumps` at `tools/harness/build_airport.py` ~1310 must agree with whatever the loader does. `auto_patch/dsf_reader.py::dsf_content_tag` is "the 8-hex tag that names a DSF's text dump: sha256 over…" — the tag already exists.

FIRST, attribution (no edit before this):
1. Reproduce the lookup on the real corpus READ-ONLY: which path the loader computes for the `.anchor_bak` DSF, what is on disk beside it, and whether the two dumps are byte-identical. Trace every reader and writer of a dump path (`tools/blast.py --find text dump`, `--find content tag`, then `blast.py <file>` for each): the v2 loader, the v1 KEEP reader (`dsf_reader`), the object stage / rebake that makes `.anchor_bak`, the DSFTool dump cache (`O4_DSF_CACHE_DIR`), the harness's `missing_pack_dsf_dumps`, `redirect_engine_caches`, and the freshness stamp. One table: site, what key it uses, read or write.
2. Why does the engine read the `.anchor_bak` copy at all after a rebake — is that intended (the pristine pack DSF) or itself a defect? Report it; do not change it in this lane unless the table shows it is the same bug.

THEN the fix, in ONE place: a dump is located by the DSF's content tag, with the file-name-keyed name still accepted so existing caches stay warm (no cache invalidation, no rewrite of corpus files). Every site in your table goes through that one function — the harness's refusal check included, or the harness will refuse what the engine can now read (or the reverse). No second implementation: extend the existing lookup, do not add a sibling.

Constraints:
- This is data-repo law territory (root `CLAUDE.md`, "One shared data repo"): NO write to `/Users/noah/XPTerrainBuilderData`, no `--refresh-data`, no `--allow-degraded-dem`. The landing master is running an explicit ledgered `--refresh-data airport_mod_cache` for OTHH itself — so the missing-file state may be gone from the corpus by the time you look; reproduce with a synthetic twin (a pack dir holding `X.dsf.<tag>.text` and a DSF named `X.dsf.anchor_bak` with the same bytes) as the primary evidence.
- A patch freshness stamp or sidecar that records the dump path must not change for an airport whose lookup already succeeded: byte-identical output is required.
- Twins: the renamed-copy case finds the dump; two different DSFs with different content never share a dump; the harness check and the loader agree on a synthetic pack. `test_console_encoding` / `test_windows_text_io` / `test_fresh_import` stay green.
- Closing: the standing suite once; a replay of a registered HECA capture `--from classify --emit --verify` equal to main's; ONE HECA harness build with body hash equal to `sw1028_HECA`. Do NOT build OTHH or LEMD (the owner's packs were just rebaked by the app and the master is refreshing them).
- Use your own scratch folder `<scratchpad>/dumpsha/`.

Whether this lands before Beta 2 is the owner's decision, not yours and not the master's assumption: finish it to a green branch and report.

THE FOUR NEVERS (single master): never comment on an issue, never merge, never create a routine/trigger or follow-up, never notify the owner. Final report only: the site table, the answer to "why the .anchor_bak copy is read", branch, sha, the fix site, twins, hash comparison, suite, ratchets, net lines, new public symbols, every item NOT done.

## RULINGS

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
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`.
  Do NOT set `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR`: the harness makes its own
  overlay, and with them set a build refuses ("pack DSF dump MISSING", #342) — they are
  the pytest suite's mechanism, set by `tests/conftest.py`.
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

