# OrthoStudio XP portability: port vs re-implement (2026-10-17, master session)

Asked by the owner after RULINGS 2026-10-17b reopened port vs re-implement.
Opus scout, read-only. E = radioharris/orthostudio-xp at
`7c028d82dcc59a27296972973aa0663ef37efddc` (v1.1.0, 2026-10-17). Nothing of E
was run, imported or installed. E timings are E's, on E's machine. Effort
figures are judgement, not measurement. Companion to
`orthostudio-xp-comparison-20261017.md`.

## Corrections to earlier notes

- Imagery has no authenticated sessions: `O4_Authenticated_Sessions` serves
  elevation_access, o4_engine and the UIs only. Imagery needs per-provider
  `request_headers` (`O4_Imagery_Utils.py:1297-1337`), which E's
  `FetchRequest.headers` carries.
- Our `Utils/src/Triangle4XP.c` is not E's base: we added the stock area test
  (`ea85d3732`, RULINGS 09-09aa, `:7233-7249`). E's `-b` hunks do not touch
  that region (diff-read, not compiled).

## Part 1: per module

| Module | Rating | E core taken | Glue we write | Deps / hazards | Port vs re-implement |
|---|---|---|---|---|---|
| (a) HTTP/2 imagery fetcher | PORT-AND-ADAPT; skip imagery-fetch-spec §4 | `net/fetch.py` 898 + `net/certs.py` 81; tile/provider-agnostic (fetch.py:28) | ~200–300 lines in `O4_Imagery_Utils`: request list per texture, placeholder tests, paste into `big_image`, `download_meter`, `red_flag` → `asyncio.Event`, `max_threads` as window cap | `curl_cffi` 0.16.3 abi3 wheels (mac arm64/x86_64, win, manylinux) + certifi. (1) certifi bundle vs our OS-store `truststore` policy (#121). (2) libcurl sockets bypass the suite socket guard (`tests/conftest.py:106-109`; inference) | 1 round + 1 freeze-admission round vs ~2 rounds + re-finding E's five recorded field fixes (fetch.py:268-306, 801-808; certs.py:4-16). Port clearly cheaper. E tests: 36 (`test_net_fetch.py`) |
| (b) In-process texture encoder | PORT-AND-ADAPT | `textures/{encode,mips,dds,refine,bcdecode}.py` 867 lines, numpy + `ispc_texcomp` | ~150 lines: drop E's nvcompress fallback, merge header writer into `O4_DDS_File.py`, process pool at the convert site (`O4_Imagery_Utils.py:2895-2930`), `O4_DDS_ENCODER` flag; mip mode matched to DDSTool, measured first | `ispc-texcomp` 1.0.1 abi3 (4 targets); pulls `lazy_loader` (PyInstaller hidden-import trap) | 1 round vs ~2. E solved the 5:6:5 flat-block table, forced four-colour mode, ispc 1.0.1 BC1 over-allocation (encode.py:102, 149, 195-197); `bcdecode.py` gives the W6 PSNR/SSIM tool. Owner sim read either way. E tests: 30 |
| (c) Binary mesh / Triangle I/O | PORT-AND-ADAPT | `mesh/mesh_file.py` 259, `mesh/triangle_io.py` 418, `numtext.py` 39 (numpy); ~520 delimited C lines | ~150 lines rewiring the six parse sites (mesh-io-spec §1); keep our `.ele` degenerate-attribute normalisation (`O4_Mesh_Utils.py:2634`); three-way merge of the C onto our area-test fork | No wheel. Triangle licence (non-commercial) + CHANGES notice; binaries for mac/win/linux (Q6). E `-b` refuses `-r` (our use unchecked) | 1 round + 1 binaries round vs ~2. E tests: 16 |
| (d) Content-keyed cache / step graph | RE-IMPLEMENT (lift at most `canon.py`, 78) | — | — | E's model (rules writing into a content store, pydantic rules, hand-bumped `version: int`) does not fit ours (fixed names in the tile build dir; v2 in-memory stages with law witnesses). E's hand-bumped version served +43+005's vectors to +43+004 (E `docs/benchmarks/p2-build.md` §5) | Porting costs more. Follow step-reuse-content-keys and v2-stage-cache specs (W1 ~2–3 rounds, W4 ~3–4) |

Python: E needs ≥ 3.12; we run 3.14.3; every wheel above is abi3 or has cp314.

## Part 2: adopting E's pipeline for the inherited stages

| Area | Verdict |
|---|---|
| Orchestration / caching | E better today; our source-digest code identity is the stronger idea; W1/W4 close most of the gap |
| Kernels | E better on I/O (binary mesh, in-process encode, async fetch); same algorithms (E's DSF is byte-identical to upstream) |
| Concurrency | Different, not worse |
| Error model | E somewhat ahead (severity, DEGRADED, domains) |
| Testability | E has oracle fixtures vs upstream; we have none for the O4_* stages (W2) |
| Readability | E better (5 functions > 200 lines vs our 124) |
| Packaging | Ours better (PyInstaller, notarized, Win/Linux CI gate); E is uv + python-build-standalone, unsigned, mac arm64 only |
| Behaviour | **Deciding.** Our inherited stages are no longer upstream: the seven O4 core files went from a 10,494-line base by +7,922 / −1,295 (`git diff 38b3eaf54 HEAD`): insets, graded coverage, fade masks, bank blend, sea-nodata fill, harmonisation, inset-box mesh rule. E reproduces upstream, not us |

Seams where the airport engine plugs in today: vector step
(`O4_Vector_Map.py:20-26, 261, 526, 678, 969, 1315, 1580`), DEM insets
(`O4_DEM_Utils.py:93, 183, 992, 1276`), post-mesh rebake
(`O4_Mesh_Utils.py:2645`, called at `:3072`, `:3112`), DSF fade masks
(`O4_DSF_Utils.py:13`), orchestration (`o4_engine/session.py:1225-1258` + JSONL).
E has none of these hooks (its patch reader is not wired: `vectors/patches.py:14-15`).

Breakage on adoption: the JSONL wire protocol (`session.py` rewritten against
E's graph, `events.py` names kept for Swift), the Qt `O4_UI_Utils` contract,
step-reuse twins, the build-time baselines, harness tile paths, the shared data
repo vs E's `~/.orthostudio` store, `O4_Cfg_Vars`/`.lay` vs E's pydantic config,
six new frozen dependencies, the #813 cross-platform grid, and a GPL §7 body
tracking a fast-moving upstream (22 releases in about a month).

Cost: whole-pipeline adoption ~10–15 lane rounds to parity, high risk, every
tile output changes. Porting (a)(b)(c): ~1 round each plus admission/binary
rounds, low risk, each behind a flag with byte-identity gates.

**Recommendation:** do not adopt E's pipeline (a faithful port of a pipeline we
have already left). Port (a), (b), (c) under `Ortho4XP/src/` with E's per-file
header and NOTICE; re-implement (d) per W1/W4; optionally take E's oracle-
fixture approach for W2.

## Owner decisions

1. Port (a)(b)(c), re-implement (d)?
2. E NOTICE §7(b): radioharris's attribution in our credits (About/Settings).
3. TLS trust for the ported fetcher: certifi for imagery only, or an OS-store bundle export (#121).
4. Drop imagery-fetch-spec §4 (threaded AIMD) and go straight to the ported §5 fetcher behind `O4_IMAGERY_FETCHER`?
5. (Master) a suite guard for libcurl sockets that bypass the Python socket guard.

## Not verified

Wheel licences (curl_cffi, ispc-texcomp, lazy_loader); PyInstaller freezing of
curl_cffi and ispc_texcomp; E's C patch compiling on our fork and our `-r` use;
E's `.mesh`/`.ele` writer vs our normalisation byte for byte; every E timing;
every effort estimate.
