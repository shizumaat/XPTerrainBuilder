# Beta 3 build-speed — issue manifest (2026-10-17)

For the master to file. One entry = one GitHub issue = one lane landing. Issues
are PUBLIC: no licence text, no half-formed ideas (those stay in the plan and
specs). Milestone for every entry: **Beta 3**. Paths are under `Ortho4XP/`
unless prefixed. Prior art is named as "OrthoStudio XP
(https://github.com/radioharris/orthostudio-xp)" where its documents are the
source of a design or a figure; its figures are its own measurements, never ours.

Plan: `docs/specs/beta3-build-speed-plan-20261017.md`. Dependencies use the ids
below; "after" means the earlier landing is merged.

**FILED 2026-10-17** by the master: B3-00 = #858 (tracking), B3-01…B3-25 = #833…#857 in order; comments posted on #740, #615, #622, #412. Companion usability pass: #832 (#817–#831).

---

## B3-00 — umbrella → #858

**Title:** Beta 3 build speed: content-keyed caches, step reuse, imagery fetch, texture and mesh I/O (tracking)

**Labels:** `feature`, `performance`, `area:engine-build`

**Body:**
Tracking issue for the Beta 3 build-speed plan, `Ortho4XP/docs/specs/beta3-build-speed-plan-20261017.md`.
Prior art read for it: OrthoStudio XP (https://github.com/radioharris/orthostudio-xp), whose
own benchmarks attribute ~90 % of its speed over upstream Ortho4XP to orchestration (a
content-keyed artefact graph, binary intermediates, in-process encoding, a bounded fetcher).
Our tree already has the mechanisms (source-digest code identity, witness-on-read, the pristine-
input rule); this plan generalises them. Every number in the specs is cited or a hypothesis; the
measurement protocol is the standard harness with `--runs N`, `--no-ledger`, no single-run A/B.

Order: B3-01/02/03 (cheap, byte-identical) → B3-24, B3-04, B3-05 → B3-08…B3-11 → B3-16, B3-13 →
B3-06, B3-07, B3-17, B3-14 → B3-15, B3-18, B3-19; code quality (B3-20…B3-25) interleaved.

- [ ] B3-01 … B3-25 (link each as filed)
- Existing issues extended: #740 (readers wave F, step-4 rows), #615 (step reuse follow-ups),
  #622 (fetch side), #412 (what the caches do not change).

---

## B3-01 → #833

**Title:** Temp PNG for filtered/masked textures saved at `compress_level=1` (byte-identical DDS)

**Labels:** `performance`, `area:imagery`, `area:engine-build`

**Body:**
`O4_Imagery_Utils.convert_texture` re-saves a texture that needs a colour filter, a
harmonization field or an alpha mask as a full 4096² PNG at Pillow's default compression before
the converter reads it (`src/O4_Imagery_Utils.py:2844`, `:2893`). The converter decodes pixels,
so the compression level cannot change the DDS. Spec: `docs/specs/texture-encode-spec.md` §3.
Change: one helper used at both sites, `compress_level=1`. Gate: `.dds` sha256 identical on one
tile with filters/masks, both arms; twin on pixel equality. Hypothesis: 0.5–0.75 s per such
texture (OrthoStudio XP measured its PNG save at ~0.75 s). Dependencies: none.

---

## B3-02 → #834

**Title:** Imagery download honours 429/503 `Retry-After` and backs off instead of failing the piece

**Labels:** `bug`, `area:imagery`

**Body:**
`http_request_to_image` (`src/O4_Imagery_Utils.py:1172-1272`) matches 200/404/403/5xx and lets a
429 fall to "Unmanaged Server answer", breaks and returns the piece as failed (`:1247-1250`);
connection failures sleep a fixed 2 s. Spec: `docs/specs/imagery-fetch-spec.md` §3.1. Change:
obey `Retry-After` (bounded pause budget), exponential backoff with jitter for 429/503/5xx and
connection errors, a per-host pause so the other threads wait too. No output change; twins with
a stub session. Dependencies: none.

---

## B3-03 → #835

**Title:** Bing imagery through the provider's https HTTP/2 host (same bytes)

**Labels:** `performance`, `area:imagery`, `needs-owner`

**Body:**
`Providers/Global/BI.lay:2` fetches `http://r{0-3}.ortho.tiles.virtualearth.net/...?g=136`
(cleartext HTTP/1.1). The provider's `https://ecn.t{0-3}.tiles.virtualearth.net/tiles/a{quadkey}.jpeg?g=15312`
serves the same imagery over HTTP/2; OrthoStudio XP measured identical bodies over 300 tiles and
+30 % request rate at equal concurrency (its network). Spec: `docs/specs/imagery-fetch-spec.md`
§3.2. Gate: ≥ 300 quadkeys fetched from both hosts, sha256 identical; placeholder still detected
(the 1033-byte test kept, the `X-VE-Tile-Info: no-tile` header added beside it); rate reported
as a range over three cold runs. Needs the owner's yes (plan Q9). Dependencies: none.

---

## B3-04 → #836

**Title:** Step reuse keys each step on its own code closure, not the whole-tree digest

**Labels:** `performance`, `area:engine-build`

**Body:**
`O4_Step_Reuse._code_identity` (`src/O4_Step_Reuse.py:211-215`) keys vector, mesh and masks on
`provenance_code.code_digest()` — every `.py`/`.toml` under `src` — so any commit reruns all three
and a no-op rebuild never hits during development. Spec: `docs/specs/step-reuse-content-keys-spec.md`
§2.1. Change: `O4_Step_Code.py` with per-step `ENTRY_MODULES`, the closure computed and held by a
twin as `partition_code.CODE_MODULES` is, written at freeze. The patch freshness gate (#346) is
unchanged. Gate: `test_step_reuse` twins; one tile rebuilt after an unrelated commit reuses the
three steps; `.mesh`/`.dsf` byte-identical. Extends #615. Dependencies: none.

---

## B3-05 → #837

**Title:** Step reuse keys on predecessor OUTPUT content (early cutoff) and identifies outputs by digest

**Labels:** `performance`, `area:engine-build`

**Body:**
A step's `previous` input is the predecessor's record digest (`src/O4_Step_Reuse.py:269-274`) and
outputs are identified by path/size/mtime (`provenance.identity_list`), so a vector step that
reran and wrote identical bytes still stales the mesh, and a touched file reads as changed.
Spec: `docs/specs/step-reuse-content-keys-spec.md` §2.2. Change: `path|size|sha256` outputs
(stat pre-check, digest on difference), `previous` = the predecessor's output digest. Cost of the
digests measured with `tools/run_tile_mesh_only.py` ×3 (law: ≥ 3 s is a review). Gate: twins;
byte-identical outputs. Extends #615. Dependencies: B3-04.

---

## B3-06 → #838

**Title:** Step records commit when the step ends (resume after a Stop); the scenery-file step becomes reusable

**Labels:** `feature`, `performance`, `area:engine-build`, `needs-owner`

**Body:**
Records are pending until the scenery-file step completes; a Stop commits nothing (`src/O4_Step_Reuse.py`
module doc). Spec: `docs/specs/step-reuse-content-keys-spec.md` §2.3–2.4. Change (a): commit each
step at its end — `forget_from` and the pack-DSF output keys keep a put-back pack from being
reused wrongly; twins for Stop-after-mesh and Stop-during-vector. Change (b, last, may be dropped
after measurement): `dsf` joins `REUSABLE_STEPS` for the no-op rebuild. Needs the owner's ruling
on (a) (plan Q3). Dependencies: B3-05.

---

## B3-07 → #839

**Title:** Per-texture DDS cache keyed on content, shared across build dirs and neighbour tiles

**Labels:** `performance`, `area:imagery`, `area:engine-build`, `needs-owner`

**Body:**
A texture is converted whenever its `.dds` is not whole in THIS build dir (`src/O4_DSF_Utils.py:
1229-1233`); grid-aligned textures shared with a neighbour tile, and every texture after a cleared
build dir, are converted again. Spec: `docs/specs/step-reuse-content-keys-spec.md` §2.5. Change:
key = source JPEG(s) + mask + filter + harmonization field + converter identity; store under the
data root (lane-local under the harness), hardlink into `textures/`, LRU size cap, `O4_DDS_CACHE=0`.
Gate: `.dds` sha256 identical cached vs converted; one tile with cleared `textures/` converts
zero on the second build. Owner decides the disk cap (plan Q1). Dependencies: B3-01.

---

## B3-08 → #840

**Title:** v2 planar stage returns its registries as an explicit output record; the build installs it

**Labels:** `bug`, `area:airport-solve`

**Body:**
Seven stage products are module globals the planar stage fills and later stages read
(`src/auto_patch_v2/pipeline/capture_state.py` REGISTRIES: HELD, PLATEAUS, LANDINGS,
LANDING_RUNOUTS, PLATFORMS, TERRACES, PAD_AIRSIDE). The replay carries them since #208/#224; the
build still hands them through the modules, which is what any stage cache would get wrong.
Spec: `docs/specs/v2-stage-cache-spec.md` §3 (consumer census), §10 step 1. Change: `build_planar`
returns the `capture_state.collect()` record; `build` installs it explicitly before the shape
stage; twin T1 (AST census of module globals read across stages == declared fields) and T2
(build's record == capture's). No geometry change; patch byte-identical. Dependencies: none.

---

## B3-09 → #841

**Title:** Constraint generators and publication read the registries from the stage record; module globals deleted

**Labels:** `feature`, `area:airport-solve`

**Body:**
Follow-up of B3-08: `constraints/{platform,no_step,jetway_strip,pads,ramp_runout,pad_fronting}`
and `pipeline/publication` take a `Registries` argument; `stage_one_map` and `capture_state` read
the record; `model.platform.HELD` and the other six module globals are removed. Spec:
`docs/specs/v2-stage-cache-spec.md` §10 step 2. Split per registry group if the diff passes
~600 lines. Gate: patch + sidecar byte-identical on HECA and CYXY; replay twins green.
Dependencies: B3-08.

---

## B3-10 → #842

**Title:** Per-stage code identity for the v2 pipeline (`stage_code.py`, closure twin, freeze digest)

**Labels:** `feature`, `area:airport-solve`

**Body:**
Only the pack partition has a code closure (`src/auto_patch_v2/airport/partition_code.py`
`CODE_MODULES`, held by `tests/auto_patch_v2/test_partition_code_closure.py`). Spec:
`docs/specs/v2-stage-cache-spec.md` §4. Change: `pipeline/stage_code.py` with `ENTRY_MODULES` per
cacheable stage (classify, planar, flat_site, road_profile, shapes), the closure held by a twin,
one `stage_code.sha256` written by both `.spec` files at freeze. No behaviour change.
Dependencies: none (parallel to B3-08).
(Merged as #889. The back-half stages' `ENTRY_MODULES` — 57 generators, assembly, jetway_strip,
solve, late_cut, late_solve, emit, verify — are added by B3-11e, spec §10 step 9.)

---

## B3-11 → #843

**Title:** Content-keyed per-stage cache for the whole v2 airport build (front half + constraints, solve, late_stage, emit, verify) with DEM and law witnesses

**Labels:** `feature`, `performance`, `area:airport-solve`, `needs-owner`

**Body:**
AMENDED 2026-10-18 (owner RULINGS 2026-10-18b): the cache covers the whole airport build. Spec:
`docs/specs/v2-stage-cache-spec.md` §4–9 (front half) and §1 "The back half", §3b, §4b, §4c, §12–§14
(back half). Median shares of the last sweep's builds (`<ICAO>.report.json` `wall_s`, 2026-10-16/17):
front (load…shapes) 28.3, constraints + jetway 6.0, solve 39.0, late_stage 23.4, emit 1.4,
verify 2.2 %; only the partition is cached today. Change: `airport/stage_cache.py` beside
`partition_cache.py` — key = stage + stage code digest + law witness + input OUTPUT digests +
environment fingerprint; DEM witness as the partition's; LRU under the user's data folder, 2 GB
cap (17a Q1); `O4_V2_STAGE_CACHE=0` (read in `auto_patch/engine_v2.py`). Back half: one record per
constraint generator plus an assembly delta, jetway_strip, solve (served only after its residual
certificate is re-evaluated on the cached `z`), late cut / late solve, emit (file bodies), verify
(served only for the patch bytes on disk it judged); the prefix re-runs inside the solve and the
late stage go through the same records; `HARD_CONFLICT` / `RUNWAY_FLEX` become solve-record fields.
Landings: spec §10 steps 4 and 6–9 (B3-11, B3-11b…e). Gate: patch + sidecar byte-identical cold vs
full hit vs each single-stage miss on HECA (closing) and CYXY; two cold builds byte-identical first
(T7); `check_build_time.py --run HECA --runs 3` cache-OFF vs miss arm, the miss arm judged (17a Q2).
Hypothesis: an emit- or verify-only change rebuilds HECA in ≈ 25–45 s instead of ≈ 807 s; a law
edit is a full rebuild until the law-row witness lands. Owner questions: spec §14 (cap, verify,
determinism only if T7 fails). Dependencies: B3-09, B3-10 (both merged or in review: #888/#893,
#889).

---

## B3-12 → #844

**Title:** `v2_solve_replay` reads and writes the v2 stage cache

**Labels:** `feature`, `area:harness-tools`

**Body:**
`--capture` pickles the same records the stage cache stores; once B3-11 lands, `--capture` can
write stage entries and `--replay --from constraints` can read them, keeping the `capture_state`
refusals by field name. Spec: `docs/specs/v2-stage-cache-spec.md` §7. `tools/INDEX.md` row
updated; `--why-miss` prints the recipe field that differed (extends `partition_cache.peek`).
Dependencies: B3-11.

---

## B3-13 → #845

**Title:** Imagery download: adaptive per-provider concurrency (AIMD) and hedged requests in the threaded fetcher

**Labels:** `performance`, `area:imagery`

**Body:**
Concurrency is a fixed `max_threads` per provider (16 default, `src/O4_Imagery_Utils.py:1571-1574`)
× 2 orthophotos; a slow request has no hedge. Spec: `docs/specs/imagery-fetch-spec.md` §4
(prior art: OrthoStudio XP `docs/specs/net-download.md` R2–R3). Change: a per-provider window
that grows on success up to `max_threads` (the cap), halves on 429/503/latency spikes, pauses on
`Retry-After`; one hedge after `max(3 s, 5×p50)`. Output bytes unchanged; twins with a stub
session; rate and failed-piece range over three cold runs. Dependencies: B3-02.

---

## B3-14 → #846

**Title:** Async HTTP/2 imagery fetcher behind `O4_IMAGERY_FETCHER` (per-provider cap, auth headers, placeholders kept)

**Labels:** `feature`, `performance`, `area:imagery`, `needs-owner`

**Body:**
The threaded `requests` fetcher costs a thread and a connection per request. Spec:
`docs/specs/imagery-fetch-spec.md` §5. Change: `O4_Imagery_Fetch.py` on one HTTP/2 session per
orthophoto with the B3-13 window and hedging in asyncio; default stays `threads` until measured
on three platforms; `max_threads`, `request_headers`, the placeholder tests and `red_flag` are
preserved. Needs the owner's decision on the new dependency (plan Q4) and three-platform wheels in
the freeze. Gate: orthophoto bytes identical; rate range; failed pieces not higher.
Dependencies: B3-13.

---

## B3-15 → #847

**Title:** In-process BC1/BC3 texture encoder with linear-light mips behind `O4_DDS_ENCODER` (owner sim read)

**Labels:** `feature`, `performance`, `area:imagery`, `needs-owner`, `needs-sim-read`

**Body:**
Every texture is a converter subprocess: DDSTool on macOS (`src/O4_Imagery_Utils.py:2908-2913`),
`nvcompress -fast` on Windows/Linux (`:2915-2921`). Spec: `docs/specs/texture-encode-spec.md` §4–5.
Change: in-process BC1/BC3 (`ispc_texcomp`) with a measured-to-match mip chain, flat-block
post-pass, process pool; flag default `tool`. DDS bytes CHANGE: the gate is a per-mip PSNR/SSIM
table against the current converter AND the owner's sim read of one tile before the default
flips; speed `--runs 3` textures/s per platform. OrthoStudio XP measured 0.33 s/texture against
nvcompress under Rosetta; our DDSTool on arm64 is unmeasured. Dependencies: B3-01; owner Q4, Q5.

---

## B3-16 → #848

**Title:** One numpy reader/writer for the mesh and Triangle exchange files (text `.mesh` byte-identical)

**Labels:** `performance`, `area:engine-build`

**Body:**
Six per-line Python parse sites (`src/O4_Mesh_Utils.py:917, 985, 1013, 1511, 2128, 2242-2278`), a
`{:.15f}` per-vertex writer (`:2584-2635`), `read_mesh_file` (`:3151`) and a duplicate `.mesh`
parser in `src/O4_Mask_Utils.py:1088-1113`. Spec: `docs/specs/mesh-io-spec.md` §3 (consumer
census §2: the `.mesh` stays text). Change: `O4_Mesh_IO.py` with vectorised readers/writers;
`read_mesh_file` a thin adapter; the masks parser deleted (duplicate ratchet falls). Gate:
`.mesh` sha256 identical on the frozen fixture and one tile; `run_tile_mesh_only.py` ×3.
Dependencies: B3-24.

---

## B3-17 → #849

**Title:** Binary Triangle4XP I/O (`-b`) behind `O4_TRIANGLE_IO` with a text==binary twin; binaries for mac/win/linux

**Labels:** `feature`, `performance`, `area:engine-build`, `needs-owner`

**Body:**
Triangle4XP exchanges `.node/.poly/.1.node/.1.ele` as text (`%.17g`); OrthoStudio XP's binary
sidecar exchange took its mesh step 8.5 → 2.8 s (`docs/specs/mesh-triangle-io.md`, its figure).
Spec: `docs/specs/mesh-io-spec.md` §4. Change: a `-b` switch in `Utils/src/Triangle4XP.c`
(magic + int32 header + float64/int32 tables, text path intact), Python readers/writers in
`O4_Mesh_IO`, flag default `text` until the three binaries are in `Utils/`; CI builds the Linux
binary and runs the twin. Gate: text and binary `.1.node`/`.1.ele` decode identically; `.mesh`
byte-identical; mesh-only ×3. Owner approves the modification and rebuild (plan Q6).
Dependencies: B3-16.

---

## B3-18 → #850

**Title:** DSF encoder: profile `build_dsf`'s per-triangle loops, vectorise only what the profile earns (byte-identical)

**Labels:** `performance`, `area:engine-build`

**Body:**
`build_dsf` (`src/O4_DSF_Utils.py:814`, 1,349 lines) is partly vectorised (`:34-64`, `:1965`);
per-triangle loops remain at `:868`, `:1320`, `:1574`; it runs beside the imagery download.
Spec: `docs/specs/dsf-and-masks-measure-first-spec.md` §1. Rule: `cProfile` ×3 first; vectorise a
loop only if its median is ≥ 3 s and the step is on the warm critical path; else record "not
worth it" with the profile. Gate for any change: `.dsf` sha256 identical on the fixture and one
tile (`test_dsf_encoding_vectorized` pattern). The helpers are the first cuts of the #740
step-4 split. Dependencies: B3-24, B3-16.

---

## B3-19 → #851

**Title:** Masks: profile the shore-transition loop after the shared mesh reader; record the finding

**Labels:** `performance`, `area:engine-build`

**Body:**
Masks already run 2–12 workers (`src/O4_Mask_Utils.py:69, 438`); the remaining cost is the
neighbour-mesh read (fixed by B3-16) and the GaussianBlur-threshold loop at `:1414-1425`, whose
replacement by a distance transform would change mask bytes. Spec:
`docs/specs/dsf-and-masks-measure-first-spec.md` §2. Rule: profile ×3 on one coastal tile after
B3-16; write the numbers; no mask-changing edit in this plan (that would need a sim read).
Dependencies: B3-16.

---

## B3-20 → #852

**Title:** Retire the duplicate v1 readers (cifp, flat_site, obj8, apt_dat, dsf) — #740 wave F

**Labels:** `feature`, `area:engine-build`, `area:harness-tools`

**Body:**
Five v1 readers duplicate their v2 counterparts (`auto_patch/apt_dat_reader.py` 1,976 vs
`auto_patch_v2/airport/apt_dat.py` 823; `dsf_reader.py` 2,485 vs `airport/dsf.py` 661;
`obj8_reader` 587 vs `obj8` 1,518; `cifp_reader` 252 vs `cifp` 168; `flat_site` 892 vs 486) with
live callers in `src`, `tools` and `tools/attic`. Spec: `docs/specs/code-quality-beta3-spec.md`
§1 and the addendum to `docs/specs/unused-code-plan-20261015.md` (wave F). One lane per pair,
smallest first: behaviour table, callers re-pointed, `test_v1_retired.KEEP` shrinks, the module
deleted, dead `tools/attic` scripts with it. A pair that differs in behaviour is an owner
question. Gate: sweep patches byte-identical; `blast.py --tests-for` tests; duplicate ratchet
falls. Dependencies: #740 step 1 (measure) recommended first.

---

## B3-21 → #853

**Title:** Failure catalogue gains severity, domain and the "degraded" class; registry twin extended (wire additive)

**Labels:** `feature`, `area:engine-build`, `area:app-mac`, `area:app-qt`

**Body:**
`src/O4_Tile_Failures.py` is the coded registry (`CATALOGUE`, `REMEDIES`, `EXCEPTION_CODES`,
`STAGE_CODES`; twins in `tests/test_tile_failures.py`); it knows tile-ending failures and
airports without a patch, not DEGRADED outcomes (white-squared textures, a skipped inset, a
mask not built), which are prints today. Spec: `docs/specs/code-quality-beta3-spec.md` §2.
Change: `Entry.severity`/`domain` (additive), a census of degradation sites as the test's table,
degraded entries carried in `BuildDone.warnings` with an optional `severity` key (protocol 1.13,
additive; codes never renamed — `code` is wire data the Swift client parses), renderers show it.
Also fixes the `ImageryDownloadsDone` wire drift `tools/blast.py` reports. Dependencies: none.

---

## B3-22 → #854

**Title:** Architecture decision records beside RULINGS (format, index twin, first five)

**Labels:** `documentation`, `area:engine-build`, `needs-owner`

**Body:**
`docs/RULINGS.md` is the canonical, append-only owner law (9,983 lines); there is no one-page
record per architectural decision. Spec: `docs/specs/code-quality-beta3-spec.md` §4. Proposal:
`docs/adr/NNNN-slug.md` (Date, Status, Context, Decision, Consequences; never rewritten,
superseded by a new one), RULINGS links its ADR, `tools/docq.py adr NNNN`, a twin on numbering
and headings; the first five summarise existing rulings (v2 only engine; one shared data repo;
no airport-specific code; synthetic-first; content-keyed derived caches). Owner approves the
format (plan Q7). Dependencies: none.

---

## B3-23 → #855

**Title:** `ruff check` in CI as a baseline ratchet (`tools/ratchets.py lint`; counts may fall, never rise; no reformat)

**Labels:** `feature`, `area:tools`, `needs-owner`

**Body:**
CI runs pytest and swift only; `ruff` is not installed. Spec: `docs/specs/code-quality-beta3-spec.md`
§5. Change: `ruff` pinned in the CI dev tail, rule set `E, F, W, I, B`, line length 100, a
`[tool.ruff]` in a root `pyproject.toml`; `tools/ratchets.py lint` records the count per rule in
`tools/ratchet_baseline.json` and fails on a rise (the duplicate gate's shape); no `ruff format`.
Owner approves the rule set (plan Q8). Dependencies: none.

---

## B3-24 → #856

**Title:** Frozen reference fixture for the inherited vector → mesh → DSF stages (byte oracle)

**Labels:** `feature`, `area:engine-build`, `area:harness-tools`, `needs-owner`

**Body:**
The airport law has census and oracle instruments; the inherited `O4_*` mesh and DSF stages have
no frozen reference, so a change there is gated by "one tile looks right". Spec:
`docs/specs/code-quality-beta3-spec.md` §6. Change: a synthetic 0.02° window (DEM window, a
hand-written `.poly/.node`, no imagery) produced once by `tools/fixtures/make_mesh_dsf_fixture.py`
on a machine with Triangle4XP; `.1.node/.1.ele/.mesh/.dsf` + sha256 manifest committed if ≤ 2 MB;
twins reproduce the `.mesh` and `.dsf` bytes on main. A change that must move the bytes
regenerates the fixture in the same PR with the reason. This gates B3-16/17/18. Owner decides
where the fixture lives (plan Q10). Dependencies: none.

---

## B3-25 → #857

**Title:** Split `tools/check_grade.py` (14,715 lines) into a package, one module per law family; census byte-identical

**Labels:** `feature`, `area:harness-tools`

**Body:**
`tools/check_grade.py` is the harness library (`LAW_FAMILIES`, `run_checks` 1,215 lines at
`:13422`, `law_context_from_sidecar`); `tests/test_harness.py` twin-asserts one code path with
the census. Spec: `docs/specs/code-quality-beta3-spec.md` §3 and the #740 step-4 addendum.
Change: `tools/check_grade/` package re-exporting today's names, `families/<family>.py`
registering into `LAW_FAMILIES`, `context.py`, `run_checks` the dispatcher; one lane per 4–6
families, the first builds the package and moves two. Gate: `tools/harness/census.py` output
byte-identical on the sweep patches; `test_harness` green. Dependencies: none.

---

# Existing issues to update (comment text, ready to paste)

## #740 — Unused-code clean-up plan

> Addendum 2026-10-17 (from the OrthoStudio XP comparison, `Ortho4XP/docs/specs/unused-code-plan-20261015.md`
> "Addendum"): step 3 gains **wave F** — the duplicate v1 readers (`cifp_reader`, `flat_site`,
> `obj8_reader`, `apt_dat_reader`, `dsf_reader`; ~6,200 lines, live callers in `src`, `tools` and
> `tools/attic`), one lane per pair, behaviour table first, a differing pair is an owner question
> (filed as B3-20). Wave C also takes `Ortho4XP/tools/attic/` (17 files, 4,108 lines). Step 4 gains
> named rows: `tools/check_grade.py` → package (B3-25), `build_dsf` 1,349 lines (first cuts in
> B3-18), `pipeline/build.py::build` 1,046 lines (per-stage functions, needed by the stage cache
> B3-11), `structure_deltas` 1,240 lines (wave A deletes it). Plan of record for the speed items:
> `Ortho4XP/docs/specs/beta3-build-speed-plan-20261017.md`.

## #615 — Step reuse

> Follow-ups filed from `Ortho4XP/docs/specs/step-reuse-content-keys-spec.md`: B3-04 (per-step code
> closure instead of the whole-tree digest — today any commit reruns vector/mesh/masks), B3-05
> (outputs by content digest and early cutoff on the predecessor's output), B3-06 (commit per step
> for resume after a Stop; the scenery-file step as a reusable step, owner ruling needed), B3-07
> (per-texture DDS content cache). `O4_Step_Reuse.py` and `tests/test_step_reuse.py` are extended,
> not replaced.

## #622 — Imagery progress / prefetch

> The fetch side is specified in `Ortho4XP/docs/specs/imagery-fetch-spec.md` and filed as B3-02
> (429/Retry-After), B3-03 (https Bing host), B3-13 (adaptive concurrency + hedging), B3-14 (async
> HTTP/2 fetcher behind a flag). Items 1, 2 and 4 here are unchanged; item 3 (prefetch step) keeps
> its plan `docs/findings/imagery-prefetch-plan-622.md`. `download_meter` is the measure for all of them.

## #412 — Airport patch build under 300 s

> Note from the Beta 3 build-speed plan (`Ortho4XP/docs/specs/beta3-build-speed-plan-20261017.md`):
> the v2 stage cache (B3-08…B3-11) does NOT lower the cold figure this issue tracks — both budgets
> are cold. It removes classify/planar/shapes from REBUILDS after a law/solve/emit change
> (hypothesis 40–70 % of the wall on a hit) and is measured on its miss arm against the law. The
> cold work stays here, #803, #149 and #579.
