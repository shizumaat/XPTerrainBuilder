# Master ↔ cloud coordination, 2026-10-18

From the master session (local, has the corpus, the apps and the sim owner).
The owner asked the two of us to work together without duplicating work or
colliding. Re-read this file before every pick: the master updates it.
The cloud lane reports only through PR bodies (root `CLAUDE.md`, "Single
master").

## 1. Your ten PRs

| PR | State | Notes |
|---|---|---|
| #886 ADRs | merged | the master split two `;` lines in `tools/docq.py` (E702 lint) |
| #887 ruff ratchet | merged | |
| #888 registries record | merged | HECA + CYXY byte-identical (patch, sidecar, rebake plan) |
| #889 stage code identity | merged | |
| #890 Triangle4XP win/lin | merged | #875 reopened: cross-platform mesh identity on a corpus tile is still unmeasured (master's) |
| #893 registry plumbing | **master is landing it** | HECA + CYXY byte-identical. The master pushed fixes to `claude/cloudregplumb`: main merged in, two corpus-only twins calling `install()` with the old signature, `stage_code.CODE_MODULES` (`model.registries` added to classify, planar, road_profile and shapes; `model.pad_terrace` dropped from shapes), and lint back to baseline. **Do not push to this branch.** |
| #892, #894, #895, #896 step reuse | **master is landing them** | All verified on tile +60-136 (reuse, byte-identity, Stop/resume). The master fixed one #896 twin that fails on machines with a corpus (`monkeypatch.undo()` dropped the fixture's redirects). **Do not push to these branches.** |

### What cost a CI round, so check it before you open a PR

1. **Merge current `origin/main` into your branch and run `tools/ratchets.py`, including `lint`.** The lint ratchet is now in CI. Its baseline is 7,970 after `tools/attic` and `scratch` were deleted (RULINGS 2026-10-18a). #888 raised B007/B023 and #893 raised E501/I001.
2. **Run the whole-tree registry twins.** They walk the tree, so `blast.py` never lists them:
   - `test_windows_text_io`
   - `test_patch_env_classification` (every new `O4_*` variable is classified in `provenance_env`)
   - `test_tile_failures` (every new exception class gets a catalogue code)
   - `test_console_encoding` (every argparse tool pins the console)
   - `test_stage_code_closure` (#889: a new import inside a stage is a code-key change)
3. **Tests that skip without the corpus are invisible to you.** Two of #893's did. When you change a signature, grep every caller, skipped twins included.

## 2. Who takes what

**Local, master only** (needs the corpus, a frozen app, the sim or the owner):

- **Fixes in flight:**
  - #900 / #901, the encoder crash and silent missing textures: PR #903.
  - #904, masks never reused: the master does it after the step-reuse stack lands.
- **Waiting on a read:**
  - #883, KBOI census: waiting on the owner's sim read.
  - #875, cross-platform mesh identity.
- **Stage cache:** #843 implementation (spec PR #905 first, then owner answers), #844, #880, #879.
- **Airport-site defects** (#491–#810 range), and anything that needs a build to prove.

**Cloud may take** (code and twins only), one PR per issue:

| Issue | Note |
|---|---|
| #874 | the lower-angle mesh retry drops `regional_areas` |
| #884 | flaky Windows test `test_waiter_resumes_from_the_other_process_cells` (`KeyError: 'vrt'`) |
| #853 | failure catalogue: severity, domain, DEGRADED. Wire stays additive; Mac and Qt both in one PR |
| #852 | retire the duplicate v1 readers (#740 wave F). Behaviour table first; a pair that differs is an owner question |
| #857 | split `tools/check_grade.py` into a package |
| #831, #827, #823, #822, #829, #566 | usability (Mac and Qt together, per #832's shared rules) |
| #850, #851 | DSF / masks profiling. These need the corpus to measure: write the code path and twins, and leave the measurement to the master in the PR body |

**Off limits while their PRs are open** (files):

- #903: `O4_DDS_Encode.py`, `O4_Imagery_Utils.py` convert path, `O4_Tile_Staging.py`, `O4_Tile_Utils.build_tile`, `O4_Tile_Failures.py`, `O4_Imagery_Fetch_Selfcheck.py`.
- #905: `Ortho4XP/docs/specs/v2-stage-cache-spec.md` and the two beta3 spec files.
- The step-reuse stack: `O4_Step_Reuse.py`, `o4_engine/session.py`, `O4_Config_Utils.py`.

**Claiming:** open a **draft** PR titled `#N: …` as soon as you start an issue. The master checks open PRs before dispatching anything, and never starts an issue that has one. If your list holds something not in either column, open the draft PR and say in its body why it is cloud-safe; the master answers there or in this file.
