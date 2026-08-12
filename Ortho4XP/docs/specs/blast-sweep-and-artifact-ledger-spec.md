# Sweep selection + the artifact ledger — verification gets cheap

Spec: 2026-08-12, FROZEN (Fable lead). Lane: **sweeptools**. Pre-ship
mode as amended (RULINGS 2026-08-12: measured arms lawful). Owner
directive 2026-08-12: "spec and implement the enhancement to
regression sweeps"; stated pain: builds are the longest thing.
Deviations STOP-and-report; cap 2.

## BS1 SYMBOL-LEVEL SWEEP SELECTION (the ordered enhancement)

`tools/blast.py` (repo root; extend, never fork) gains
`--tests-for <file> [--since <ref>|--diff]`: from the working-tree
diff (or diff vs `<ref>`), detect the CHANGED SYMBOLS (top-level
defs/classes/constants touched, via AST on before/after — follow the
index's own parsing idiom), and select the test files whose recorded
symbol USE intersects them. Selection law (recall over precision):
* symbol-attributed tests of the changed symbols, UNION
* ALL direct-importer tests of any changed file whose total
  direct-importer test count is small (≤ a threshold, e.g. 15 —
  cheap files just run everything), UNION
* ALL direct-importer tests for any changed symbol the index cannot
  attribute (dynamic use, re-exports, `__all__` — fall back wide,
  never silently narrow), UNION
* tests whose file itself changed.
Output: the file list (one per line, pipeable to pytest) + a stamped
header (changed symbols, selection sizes, fallbacks fired). The
existing `--audit` grows a twin mode: seed N synthetic mutations
(one per hot symbol of a sample file), assert the selected set
contains every test the FULL direct-importer sweep fails on that
mutation — recall 100 % on the mutation set is the acceptance, and
the audit prints precision (files selected vs 110) beside it.

## BS2 THE BASE-ARM ARTIFACT LEDGER (the build-count cutter)

Measured waste: base arms at identical trees (e.g. 7e6df36, 7c03dc4)
were rebuilt 2–4× across lanes this session at 7–10 min each. The
run ledger remembers PASS/FAIL; it forgets the artifact.
`tools/harness/build_airport.py` gains an ARTIFACT LEDGER (extend
the harness + `run_with_ledger` idioms; one implementation): on a
successful `--patch-only` build, store the emitted patch + sidecar +
frame.json content-addressed by (code-tree hash, ICAO, the O4_* env
the run ledger already keys on, corpus stamp from frame.json) in a
gitignored store OUTSIDE the shared data repo (e.g.
`~/.ortho4xp/artifact_ledger/`); on a later request for the same
key, `--from-ledger` (default ON for explicitly-requested BASE arms
via a `--base-arm` flag; plain builds unchanged) serves the stored
artifact into the lane's out dir with a loud provenance line
(source key, original build's timestamp + duration) instead of
rebuilding. NEVER for timing runs (refuse the combination), never a
write to the shared repo, guard semantics untouched; a corpus-stamp
mismatch is a MISS (the KCLT road-feed lesson — a changed corpus is
a different measurement). Eviction: size-capped LRU, stamped.

## Tests
Twins, mutation-checked: BS1 selection law (each union clause; the
fallback fires on an unattributable symbol; recall audit on seeded
mutations of a real file); BS2 store/hit/miss (tree-hash miss,
env miss, corpus-stamp miss, timing-run refusal, provenance line,
byte-identical served artifact). Directly-covering files once,
ledgered.

## Acceptance
* BS1 on `src/auto_patch/layout.py` with a real one-symbol change:
  selection ≤ ~15 files vs the 110 full sweep, audit recall 100 %
  on the mutation set; quote both numbers.
* BS2: build one airport (CYXY, ~35 s class), request the same key
  as a base arm — served from the ledger, body sha identical,
  ≪ build time; quote the provenance line.
* tools/INDEX.md rows updated same commit (both tools).

## Bookkeeping
Cap 2; `.progress` heartbeat; DEFERRED lines per skip. No engine
changes; no auto_patch changes. Cross-refs: RULINGS 2026-08-12
(measured arms), [[single-pass-principle]] (build once, filter per
consumer — BS2 is that law applied to builds),
[[consult-before-create]].
