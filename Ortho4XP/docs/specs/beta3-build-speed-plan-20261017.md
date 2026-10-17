# Beta 3 build-speed plan of record (2026-10-17)

Status: PLAN OF RECORD — owner decisions ruled 2026-10-17 (RULINGS 2026-10-17a). Written by the Fable spec lane, owner-approved launch 2026-10-17). The master
files the issues from `beta3-build-speed-issues-20261017.md` and runs the plan one
lane and one landing at a time. It dispatches nothing by itself.

Source: `docs/findings/orthostudio-xp-comparison-20261017.md` (three scouts' reading
of radioharris/orthostudio-xp, "E", against our tree), re-verified against the code
on 2026-10-17; the corrections are in that file's "Corrections" section. Every
number below is CITED (with its source) or a HYPOTHESIS to measure. Nothing was
built or timed for this plan; there is no corpus in the container that wrote it.

Law it serves: the hard build-time law (`Ortho4XP/CLAUDE.md` item 6: ≤ 60 s per
airport, ≤ 300 s per tile, both COLD, excluding downloads; ≥ 1 % of a budget needs
the whole-pipeline review); BUILD ECONOMY (synthetic-first, one closing build, no
sweep in a lane); RULINGS 2026-08-30l (consumer census before a cross-cutting
change); 2026-10-04a/b/c (reuse before new, size is a warning, the duplicate
ratchet is the gate); 2026-10-05e (no airport-specific code).

## 1. What E taught us, in one paragraph

E's own thesis (ADR 0003) is that ~90 % of its speed over upstream Ortho4XP is
orchestration — a content-keyed artefact graph, binary intermediates, in-process
encoding, a bounded async fetcher — not language. Our tree already has the pieces
E lacks (source-digest code identity, witness-on-read, the pristine-input rule,
ledgered data refreshes, three nested parallel levels) but applies them to ONE
cache (the pack partition) and to a step-reuse record that keys on stat identity
and a whole-tree digest. The plan is to generalise what we have, not to import E.

## 2. Workstreams, order and dependencies

| Id | Workstream | Spec | Depends on | Gate class |
|---|---|---|---|---|
| W0 | Cheap byte-identical wins: temp-PNG `compress_level`, 429/Retry-After, https Bing host | `imagery-fetch-spec.md` §3, `texture-encode-spec.md` §3 | — | byte-identical |
| W1 | Step reuse: per-step code identity, early cutoff on output content, resume, DSF step, DDS content cache | `step-reuse-content-keys-spec.md` | — (W1.3 after owner Q3) | byte-identical |
| W2 | Frozen reference fixtures for the inherited `O4_*` vector/mesh/DSF stages | `code-quality-beta3-spec.md` §6 | — | twins |
| W3 | Mesh I/O: shared numpy reader/writer; binary Triangle4XP I/O behind a flag | `mesh-io-spec.md` | W2 | byte-identical |
| W4 | v2 per-stage content-keyed cache (registries → stage outputs; stage code identity; law witness; the store) | `v2-stage-cache-spec.md` | — | byte-identical (hit == miss) |
| W5 | Imagery fetch: adaptive concurrency + hedging; async HTTP/2 fetcher behind a flag | `imagery-fetch-spec.md` §4–5 | W0 | byte-identical orthophotos |
| W6 | Texture encode: in-process BC1/BC3 with linear-light mips, behind a flag | `texture-encode-spec.md` §4 | owner Q4, Q5 | **owner sim read** |
| W7 | DSF encoder and masks: measure first, vectorise only what the profile earns | `dsf-and-masks-measure-first-spec.md` | W2, W3 | byte-identical / "not worth it" |
| W8 | Code quality: readers wave F (#740 addendum), coded-error registry, ADRs, ruff ratchet, `check_grade` split | `code-quality-beta3-spec.md`, `unused-code-plan-20261015.md` addendum | — | tests; census does not move |

Order of landing (one lane, one landing, one sweep at a time):

1. **W0 first** — three one-file changes, each byte-identical, each a measurement
   the later work is read against (texture conversion wall, request failure
   rate, request rate).
2. **W2 then W1.1/W1.2** — the fixtures cost nothing and gate W3/W7; the per-step
   code identity and the output-content key are small and make every later
   rebuild measurement honest (today any commit stales every step).
3. **W4** — the largest item; starts with its census and registry work, which is
   also what makes `v2_solve_replay` faithful by construction.
4. **W3, W5** in parallel lanes (disjoint files), W8 items interleaved as slots open.
5. **W6, W7** last: W6 waits for the owner's decisions and a sim read; W7 may end
   as "not worth it" and is written to say so cheaply.

What this plan does NOT do: solve-time work (#412, #803, #149, #579 — the cold
solve is governed by the law and its own lanes); the imagery PREFETCH step
(#622 item 3, `docs/findings/imagery-prefetch-plan-622.md` stands as written);
the USGS `/vsicurl` inset fetch (#158, a DEM-provider matter); the five-airport
sweep (orchestrator, per merged batch).

## 3. The measurement protocol (every item)

Through the standard harness only (`CLAUDE.md` "The standard test harness");
the `ab-time` rules apply to every timing:

- **Airport wall**: `venv/bin/python tools/check_build_time.py --run ICAO --runs N`
  (N ≥ 3; per-metric MEDIAN; builds through `tools/harness/build_airport.py
  --no-ledger`, fresh interpreter per run, reads v2's `wall_s` stage clocks from
  `<ICAO>.report.json`). Never one run per side; never through the run ledger;
  foreground only (background inherits nice 5).
- **Tile compute**: no `--run` mode exists; build the tile twice in the engine
  with imagery and insets cached and read the second record from
  `~/.ortho4xp/tile_build_times/<tile>.json` (`check_build_time.py` qualifies it
  on `textures_missing == 0` and `insets_fetched == 0`). Mesh-only timings use
  `tools/run_tile_mesh_only.py` (guard-armed), N ≥ 3.
- **Download**: excluded from both budgets. Measured as request rate and failure
  count from `o4_engine.download_meter` (#622) over one cold-cache tile, three
  runs at three times of day, reported as a range, never a single figure.
- **Warm-vs-cold**: a cache item reports BOTH arms (miss, then hit) with the same
  N; the hit arm's saving is the claim, the miss arm's cost is the law's
  question (≥ 1 % of a budget → the whole-pipeline review before landing).
- **Byte identity**: the harness's sweep patches (`Patches/<tile>/<ICAO>_auto.patch.osm`
  + `.axes.json`), the `.mesh`, the `.dsf` and the `.dds` set, compared by
  sha256 between arms; the first time a change is NOT byte-identical the gate
  becomes "census does not move" (`tools/harness/census.py`) or "owner sim
  read", never a judgement call in a lane.
- **The closing build**: ONE representative airport per lane (HECA by default;
  CYXY as the cheap control), controls shared through the artifact ledger
  (`build_airport --base-arm`), never rebuilt.

## 4. Acceptance gates by item

| Item | Gate | Measured by |
|---|---|---|
| W0 PNG `compress_level=1` | `.dds` sha256 identical to the default-compression arm on one tile | one tile, both arms; unit twin on pixel equality |
| W0 429/Retry-After | unit twins (stub session); no output change | tests only |
| W0 https Bing host | sampled tile bodies sha256-identical between hosts; placeholder still detected | sample of ≥ 300 quadkeys, one run; twin on the `.lay` parse |
| W1 per-step code identity, output-content key | step records; a no-op rebuild reuses vector/mesh/masks after an unrelated commit; `.mesh`/`.dsf` byte-identical | `test_step_reuse.py` twins; one tile rebuild pair |
| W1 DDS content cache | `.dds` sha256 identical hit vs miss | one tile, both arms |
| W2 fixtures | the frozen digests reproduce on main | twins |
| W3 shared reader/writer | `.mesh` byte-identical; reader == legacy reader on the fixture | twins; `run_tile_mesh_only.py` ×3 |
| W3 binary Triangle I/O | text == binary `.1.node`/`.1.ele` values; `.mesh` byte-identical; flag OFF by default until the three binaries ship | twins; ×3 mesh-only |
| W4 stage cache | patch + sidecar byte-identical hit vs miss; replay == build on a registered capture | `check_build_time --run HECA --runs 3` both arms; `frames.py` capture replay |
| W5 AIMD/hedging/async | orthophoto bytes identical; failure count not higher; rate reported as range | download_meter, three cold runs |
| W6 in-process encoder | **owner sim read**; PSNR/SSIM against the current encoder reported per mip | sim read; `--runs 3` textures/s |
| W7 DSF/masks | byte-identical `.dsf`/masks, or a written "not worth it" with the profile | profile first; ×3 if touched |
| W8 readers wave F | `test_v1_retired.KEEP` shrinks; sweep patches byte-identical | twins; one closing build |
| W8 error registry, ADRs, ruff, `check_grade` split | registry twin; `test_harness` twins; ratchet baseline can only fall | tests only |

## 5. Target numbers — hypotheses, not promises

Cited figures are E's, measured against UPSTREAM Ortho4XP on a Mac with
nvcompress under Rosetta (E `docs/benchmarks/*`); none was measured on our tree.

| Item | Hypothesis | Source of the figure |
|---|---|---|
| W0 PNG compress_level | 0.5–0.75 s saved per filtered/masked texture | E `dds-encoder.md` (PNG save ~0.75 s) |
| W0 https host | +30–40 % request rate at today's concurrency; HTTP/2 | E `network.md` §1 (222 → 287–317 req/s at 32 in flight) |
| W1 no-op rebuild | vector+mesh+masks skipped after any unrelated commit (today: never during development) | `O4_Step_Reuse.py:211-215` keys on the whole-tree digest |
| W1 DDS cache | the shared-edge textures of a neighbour tile and every rebuild after a cleared build dir skip conversion | mechanism only; count the shared names on one tile pair |
| W4 stage cache | a law/solve change reruns constraints/solve/emit only: ~55–75 % of the airport wall skipped on a hit (OTHH comment: 75 % in partition+structures+planar) | `engine_v2.py:70-84`; median shares load 6.4 / partition 13.5 / classify 17.0 / planar 9.9 % |
| W4 miss arm | ≤ 1 s added per airport (digests of in-memory products) | hypothesis; the law's 1 % is 0.6 s — measured before landing |
| W5 fetcher | 3–6× request rate on a cold cache (E: 1,436 req/s at 128 in flight vs 222 on our host/pattern) | E `network.md` §2; our line and provider terms differ |
| W3 mesh I/O | mesh step 8.5 → 2.8 s class saving (E), on top of Triangle's own ~3 s | E ADR 0004 |
| W6 encoder | 0.33 s/texture (E) vs our DDSTool (unmeasured on arm64) | E `dds-encoder.md`; gain unknown until measured |
| W7 | unknown; the profile decides | — |

## 6. Lane sizing

One Opus lane per manifest entry, one landing, one sweep after it. A lane that
finds its diff heading past ~600 lines splits by responsibility and reports the
split, never the number. Every lane: attribution before fix, site numbers first,
`tools/ratchets.py` green before the report, net lines and new public symbols
in the report, build-time impact statement in the brief. Fable is not launched
for implementation (RULINGS 13c); deviations from a spec come back to a Fable
reviewer.

## 7. Owner decisions needed

**RULED 2026-10-17 (RULINGS 2026-10-17a): every question below answered with the recommended option.** Q1 data folder, capped (start 2 GB stage / 20 GB DDS); Q2 cold law, warm reported; Q3 resume yes; Q4 all three libraries, each behind a flag after measurement; Q5 flag + owner sim read; Q6 Triangle modification approved, flag off until three binaries; Q7 ADRs approved as proposed; Q8 ruff E,F,W,I,B ratchet approved; Q9 Bing https yes; Q10 fixture in this repo.

Q1. **Where the v2 stage cache lives and how big it may get.** The partition
cache writes into the pack's Ortho4XP mod-cache folder (derived, self-
invalidating, never corpus). The stage cache holds a `PlanarMap` and a
classification per airport (tens of MB at OTHH, hypothesis). Same folder, with a
size cap and LRU sweep (`v2-stage-cache-spec.md` §7)? Or a lane-local/app-local
root only?

Q2. **Do caches count toward the law?** Both budgets are COLD. A cache cannot
lower a cold figure and may raise it (the miss arm's digests). The plan treats
caches as development and rebuild speed, measured against the law only on the
miss arm. Confirm, or rule that warm figures are also reported.

Q3. **Resume after a stop.** Today a stopped build commits no step record
(`O4_Step_Reuse.py` module doc) and puts the scenery packs back. The spec proposes
committing each finished step at its end, so a Stop after the mesh loses nothing
before it; the pack put-back correctly stales the mesh record. Rule yes/no.

Q4. **New dependencies.** `curl_cffi` (async HTTP/2), `blake3` (hashing), and
`ispc_texcomp` (BC1/BC3) are new wheels in the frozen engine, each needing a
licence check and three platforms. The specs are written to work WITHOUT them
first (`hashlib.file_digest`, `requests` with an adapter, DDSTool/nvcompress) and
to admit each behind a flag once measured. Admit none, some, or all?

Q5. **DDS bytes may change** (W6). An in-process encoder produces different
blocks and different mips from DDSTool/nvcompress (E measured −0.41 dB on
textured blocks before refinement; linear-light mips are brighter at distance).
This needs your sim read of one tile before it is on by default — and a decision
whether a quality delta of that size is acceptable at all.

Q6. **Binary Triangle4XP.** A `-b` switch is a modification of Triangle, rebuilt
for mac/win/linux, with the modification notice Triangle's licence requires
(`LICENSING.md` §3, §6). The flag stays OFF until the three binaries are in
`Utils/`. Approve the modification and the rebuild process?

Q7. **ADRs beside RULINGS.** `Ortho4XP/docs/adr/NNNN-title.md`, one page,
Context/Decision/Consequences, never rewritten (superseded by a new one);
RULINGS stays canonical and the ruling links its ADR. Approve the format and
the first five proposed in `code-quality-beta3-spec.md` §4?

Q8. **ruff in CI** as a baseline ratchet (violation count may fall, never rise;
no reformat). Approve the rule set proposed in `code-quality-beta3-spec.md` §5?

Q9. **The Bing host change** replaces a cleartext HTTP/1.1 host with the
provider's https host serving the same bytes (E measured identity over 300
tiles; we re-measure). Provider terms are unchanged (same property, same
imagery). Any objection?

Q10. **Reference fixtures** (W2) are produced ONCE on the machine that has the
corpus, from a tiny synthetic window; the files (not only digests) are committed
if under ~2 MB. Acceptable in the repo, or in the data repo under `.harness/`?

## 8. Licence

`Ortho4XP/` is GPL-3 (`LICENSING.md` §1–2); `Sources/`, `tools/`, `scripts/`
are MIT. E is GPL-3 with GPL §7 attribution terms (E `NOTICE`) that travel with
any copied material. Rule for this plan: **re-implement from E's specs; copy no
file.** Where a design is E's (the AIMD window, the binary layouts, the linear-
light mip rule), the spec says so and names the E document as prior art. If a
lane ever copies E code, it may land ONLY under `Ortho4XP/` and must carry E's
notice — never under `tools/` or `Sources/`. Triangle4XP changes stay under
Triangle's licence (`LICENSING.md` §3). Third-party wheel licences (`curl_cffi`
MIT, `blake3` CC0/Apache-2.0, `ispc_texcomp` MIT — to be verified by the lane
that admits each) are checked before the dependency is pinned.

## 9. Files

- this plan; `beta3-build-speed-issues-20261017.md` (the manifest);
- specs: `v2-stage-cache-spec.md`, `step-reuse-content-keys-spec.md`,
  `imagery-fetch-spec.md`, `texture-encode-spec.md`, `mesh-io-spec.md`,
  `dsf-and-masks-measure-first-spec.md`, `code-quality-beta3-spec.md`;
- `unused-code-plan-20261015.md` gains an addendum (wave F, `tools/attic`,
  step-4 rows); `docs/findings/orthostudio-xp-comparison-20261017.md` gains
  its corrections.
