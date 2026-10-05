# lawc396 — notes for the implementing lane (Opus)

Issue shizumaat/XPTerrainBuilder#396. Owner RULINGS 2026-10-05g (and 05e, 05f,
2026-09-27a (3), 2026-09-10ap). THE SPEC IS `othh-terminal-ramps-spec.md` §12h —
read it whole first: `tools/docq.py spec '§12h'` (it is in the ramps spec, not the
design spec; docq finds it without a flag). Findings:
`docs/mouthwitness-lawc-findings.md`. The master generates the pack from this file.

## What lands

Law C (kerb-wall corridors and garage ramps) becomes UNCONDITIONAL under the
four-clause rule R = (d) ∧ W1s ∧ W3 ∧ FIELD (§12h (1)); the per-airport switch, its
table, schema, gate and twins are DELETED (§12h (7)); `Affordances.group_span_max_m`
and its per-airport reading go with them, the pack-wide `[placement]
group_span_max_m` byte-identical (§12h (8)). No new law value, no new toml key.

## Base branch — read this before the first grep

The work lands AFTER `feature/parallel-v2`. The reader is split there into
`airport/wall_family.py` (lane pardoors 5, `7377cc8c`), which is on
`claude/parfinal d41e65db` (and `claude/pardoors`) but NOT on the
`origin/feature/parallel-v2` ref `1e30cbcf`. Every file:line in §12h is on
`claude/parfinal d41e65db`. Branch from the ref the master names; re-grep
once (`tools/blast.py --find wall_corridor affordances group_span_max_m`).

## Files you own

Engine: `src/auto_patch_v2/airport/wall_family.py` (the admission site, the
lazy pack-wide mouth index on `WallReader`, `WallField`), `airport/wall_corridors.py`
(docstring; `WallCorridorStats` + two fields), `airport/wall_geometry.py` only if
`_plan_segments` needs a public name, `airport/reader_work.py` (`begin`/`setup`/
`ReadWorker.field`, the worker's `wall_reader(..., field=)`), `airport/object_cut.py`
(docstring + the VHHH note → history), `planar/pack_reads.py` (`field` through to
the pool and the one-core read), `planar/build.py` (derive ONE `WallField` from the
classification, hand it), `planar/__main__.py` (hand `cl`), `planar/structure_approach.py`
(`cover_polygons(classification)`; `planar/structures.py:165-166` calls it),
`pipeline/build.py` (`field read` in the wall-corridor report line; nothing else),
`law/model.py`, `law/__init__.py`, `law/airports_schema.py`, `law/tables.py`,
`law/rebake_schema.py`, `law/structures.toml` (prose only), `planar/group.py` (prose
only), DELETE `law/airports.toml`, `Ortho4XP.spec` + `Ortho4XP_Qt.spec` count guards.

Tests: `tests/test_no_airport_specific_code.py` (`RECORDED = set()`),
`tests/auto_patch_v2/test_v2corridor.py` (the affordance twins out; the clause and
degenerate-case twins in, from `_corridor_obj` + a CLOSER placement + a cells list),
`test_v2wallcorridor.py`, `test_v2doorramp.py`, `test_v2canopy.py` (the span twin),
`test_parplanar.py` / `test_pardoors.py` (pooled = serial WITH the field handed),
`test_auto_patch_engine_dispatch.py` (comment), `tools/planar_read_arm.py` (the field).

Docs in the same commits: `tools/INDEX.md` rows naming `airports.toml`; root
`CLAUDE.md` / `.claude/agents/*.md` one-liners if they name the table.

## Order of work (one lane, synthetic-first)

1. Branch; `frames.py list OTHH LEMD KASE TFFJ VHHH` — reuse the registered
   captures (OTHH `perfB362` or the pardoors frame; LEMD `sheetchain`; KASE
   `conc333`; TFFJ `surfacesettle2`; VHHH `lawcspec`). Take NO new capture.
2. The mouth query + the three clauses at the single site, cheapest refusal first,
   the LINE exactly as §12h (4); `WallCorridorStats.field_read` / `field_cells`;
   the `narrow_cut` row fields. Keep every existing refusal text byte-identical.
3. The `WallField` plumbing: `planar/build.py` → `pack_reads` → `reader_work` →
   worker → `wall_reader`; the one-core path the same; `field=None` = NOT READ, said
   on every line. The index is built lazily once per process.
4. The deletions (§12h (7)) and the `group_span_max_m` reduction (§12h (8)).
5. Twins (§12h (9) 5–6), then the existing suites by changed files once.
6. Replays: OTHH `--from planar --emit` → 9 identical records, body sha
   `88794a1d264b…` (full sha in §12h (9) 1), rebake `eecf0d4d6ba1…`; OTHH
   `--from classify` once (the groups re-derive); KASE `--from planar --emit`
   body `738c2a8ceb64`; LEMD / KASE / TFFJ / VHHH `--stage structures` → corridors
   0 and the §12h (2)/(10) tables reproduced from the lines.
7. Build time: `read_s` both arms on the OTHH replay + the OTHH build's
   wall-corridor line under `ab-time` (never one run each).
8. ONE build: `tools/harness/build_airport.py OTHH` — body sha identical.
9. `tools/ratchets.py` passes; register nothing new (no new frames); report.

## Proofs to hand back (numbers first)

* OTHH: 9 corridors, record diff empty, body sha, rebake sha — replay AND the build.
* KASE replay body sha `738c2a8ceb64`.
* LEMD 0 / KASE 0 / TFFJ 0 / VHHH 0 with the per-clause counts against §12h (2)
  and (10) — any difference named per candidate (resource, placement, site, the
  clause values).
* `read_s` delta and the build line, both arms, with the run count.
* The test files run and their counts; `test_no_airport_specific_code` green with
  `RECORDED = set()`; the freeze guards at 8 datas.
* Net lines added/removed; new public symbols (`WallField`, `cover_polygons`, the
  `field` parameters, the two stats fields, any `_plan_segments` rename).
* Every item NOT done, and every deviation from §12h STOPPED and reported, not
  decided (Fable reviews deviations — CLAUDE.md 1a).

## The four NEVERs

1. NEVER an airport literal, table, key, pack name, coordinate window or threshold
   tuned to one airport (RULINGS 2026-10-05e; `test_no_airport_specific_code`).
   If R admits something somewhere, that is a FINDING for the master, not a clause.
2. NEVER run the five-airport sweep in the lane; ONE OTHH build at the close; the
   six-airport byte identity is the master's sweep at merge.
3. NEVER a second derivation of the mouth, the cover or the plate — the admission
   is ONE site (`read_family`), the cover polygons ONE helper, `plate_plan` read not
   re-derived; no consumer vetoes (RULINGS 2026-08-30l).
4. NEVER comment on the issue, merge, create a routine/trigger/follow-up, notify the
   owner, touch `~/Library/Logs/XPTerrainBuilder/` or the X-Plane install, or
   `--refresh-data`. Report to the master only.
