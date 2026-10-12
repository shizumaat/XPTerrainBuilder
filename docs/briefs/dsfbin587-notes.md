# Lane dsfbin587 — notes (issue #587, RULINGS 2026-10-12f)

Branch `claude/dsfbin587`, on top of `claude/dsftool568` @ 33602bdd6.

## RESUME HERE

State 2026-10-12: steps 1-4 of the brief DONE and committed. NOT done, by
the brief: the workflow has not been dispatched, no binary was replaced.
The Linux and Windows recipes have never run anywhere (no container tool
on this Mac) — the master's first dispatch is their proof. Procedure for
the master: `docs/DSFTOOL-VENDORING.md`.

Scratch (lane-local): `<session scratchpad>/dsfbin587/` — `proof/` (the script's own clone and the built tool; the full clone and
the Xcode build folders are deleted), `DSFTool.new` (the
local candidate, universal), `*.jsonl` (census rows), `diff_*.json` /
`census_diff_files.json` (which files differ), `diff_dumps.py`,
`encode_ab2.py` (one-off A/B scripts). The four `--keep-text` folders
(4 x 1.3 GB) are deleted.

## 1. What is delivered

| File | What |
| --- | --- |
| `.github/workflows/build-dsftool.yml` | `workflow_dispatch` only; jobs macos (macos-15, universal), linux (ubuntu-22.04), windows (windows-latest), bundle. Never commits. |
| `Ortho4XP/Utils/toolchains/build_dsftool.sh` | ALL pins + the unix recipe; `--source-only` for the windows job. |
| `Ortho4XP/Utils/toolchains/smoke_test_dsftool.py` | stdlib-only smoke: version pin, plain round trip, the #568 trait file. |
| `Ortho4XP/Utils/DSFTool.identity.json` + `tests/test_dsftool_identity.py` | sha256 + `--version` line per platform file; the twin (4 tests). Records the STOCK binaries today. |
| `Ortho4XP/Utils/DSFTool-NOTICE.md` | licence / attribution, ships with `Utils/`. |
| `docs/DSFTOOL-VENDORING.md` | run, download, verify, judge, replace, frozen checks, closing test, cache statement. |
| `Ortho4XP/tools/dsftool_dump_census.py --diff-text OLD NEW` | the census diff, promoted from scratch on its second use (+1 twin). |

## 2. The build recipe (read from the source at c31ed76b5)

DSFTool = 14 xptools sources + 16 LZMA-SDK C files (`makerules/DSFTool`)
+ zlib. No `libs` submodule, no CGAL/boost/Qt/FLTK/curl.

* macOS: `xcodebuild -project SceneryTools.xcodeproj -target DSFTool
  -configuration Release` — the project already builds `arm64 x86_64`
  (`ONLY_ACTIVE_ARCH=NO`), `-Ofast`, LTO; links OS libz / libc++ / Carbon.
* Linux: `make conf=release_opt DSFTool` (gcc, g++, make, zlib1g-dev);
  `-Ofast -flto`, gold if present; dynamic libz/libstdc++ like the stock.
* Windows: `msvc/DSFTool/DSFTool.vcxproj` Release|x64, static CRT
  (`RuntimeLibrary MultiThreaded`), `zlibstat.lib` + `zlib.h` from the
  `msvc_libs` submodule (gitlink 782be015 at the pin; a PREBUILT lib from
  X-Plane/xptools_msvc_libs — upstream's recipe, what the stock exe
  linked). Toolset v142 in the project, overridden to v143.

Three things the pinned source needs on a current toolchain (all found by
building, all command-line settings — no source edit beyond the two picks):

1. `MACOSX_DEPLOYMENT_TARGET=12.0` — the project's 10.12 is refused by
   Xcode 27 ("supported 12.0 to 27.0").
2. A wrapper prefix header that includes `<fstream>` before
   `src/Obj/XDefs.h` — XDefs defines `fopen(a,b)` as a macro and current
   libc++ `<fstream>` calls `std::fopen(...)`; `tri_stripper.cpp` fails to
   compile otherwise.
3. `-fno-delete-null-pointer-checks` — **the x86_64 slice built at the
   project's `-Ofast` with Xcode 27 died with SIGSEGV in `--text2dsf` of
   every overlay** (`DSF32BitPointPool::WritePoolAtoms`,
   `DSFPointPool.cpp:601/608`: `&*longs.begin()` on an empty vector is UB
   and the optimiser acts on it; -O0 does not crash, arm64 does not;
   upstream master 0137e80cd still has the line). With the flag both
   slices encode and dump. The smoke test runs per slice for this reason.

About the picks: `9c1a06c7b` also carries a "local-only macOS build
workaround" hunk in `DSFPointPool.cpp` (`#undef fopen`) that upstream
REMOVED before merging the PR (115202ae5, 649277d8c). Picking exactly the
two commits the brief names keeps that hunk; `DSFPointPool.cpp` calls no
`fopen`, so it changes nothing. The patched tree is pinned by its git tree
id `6dc3a2dc7e821baf6ca261fc9e6da745877a9cd9`.

The version string is NOT changed (`DSFTool 2.4.0-b1`, release 24-5):
line 2 of every dump is `800 written by DSFTool 2.4.0-b1` and
`compare_dumps` compares it as a structural row (measured: a `-b2` there
is a refusal). The patched tool is told apart by its sha256 and its
compile date.

## 3. Local proof (macOS, Xcode 27.0, the script's own fresh clone)

`sh Utils/toolchains/build_dsftool.sh <scratch>/proof` -> universal
DSFTool, 585 KB, minos 12.0, `--version` "DSFTool 2.4.0-b1 … Compiled on
Oct 12 2026 / release: 24-5". Smoke OK on both slices. Builds are not
byte-reproducible (two builds of one tree: different sha256).

Census, stock Global Airports, 7,077 DSFs, `--jobs 8`:

| | dump | crash |
| --- | --- | --- |
| stock tool, arm64 slice | 7,069 | 8 |
| stock tool, x86_64 slice | 7,069 | 8 |
| new tool, arm64 slice | 7,077 | 0 |
| new tool, x86_64 slice | 7,077 | 0 |

Diff old -> new over the 7,069 both dump (`# file:` not compared):

* arm64: 7,003 identical, 66 differ. Row classes: `# pool N: #
  obj_pools found: K` 66 rows / 66 files (K drops, e.g. 16 -> 12);
  `HEIGHTS` 14 rows / 14 files — the BASE only (e.g. `+28-082`
  -82.0 -> -22.0; the stock base was the tile's longitude, stray memory),
  quantum 0.03125 unchanged on all 14. No other row. (The 286 the
  dsftool568 notes predicted was the count of files using
  SetDefinition16; 66 is what changes.)
* x86_64: the same 66 files; `HEIGHTS` 17 files (the 14 + `+30-088`,
  `+35+024` base 0.0 -> -6.0 / -8.0, and `+33-082` QUANTUM 1.00000 ->
  0.03125 — the stock x86_64 slice printing stray memory, the #181 class).
* new arm64 vs new x86_64: 637 files differ, all by the SIGN OF ZERO
  (`-0.000000000` vs `0.000000000`, 43,389 rows, 0 otherwise) — and the
  stock tool's two slices differ the same way (633 files). Not new.
* The 8 crashers, new tool vs the engine-retry dump of dsftool568
  (`crashers/<tile>/fixed.text`): 0-2 rows differ per file, only the same
  two classes.

Rows the engine reads: none changes meaning. `HEIGHTS` is read only by
`dsf_write` (`_split_rows` keeps keyword + quantum; `_heights_reconciled`
compares by encodable range); `pool_tolerances` reads `# pool N: p=…`
lines, which did not change.

Write half (`--text2dsf`, 368 stock dumps = every 20th + the HEIGHTS
files, same text through both tools): 209 byte-identical, 159 differ
(same length; CMDS atom in 159, GEOD in 18) — the new build ORDERS
polygons and road segments differently; `compare_dumps(old-encoded,
new-encoded)` ok on all 159. x86_64 slices: 161 differ, all ok. Engine
round trip with the new tool (`dsf_write.encode` -> `dump` ->
`compare_dumps`) on the 8 crashers + the HEIGHTS files: 22/22 ok (arm64),
25/25 ok (x86_64).

## 4. Caches

See `docs/DSFTOOL-VENDORING.md` "What a new tool invalidates": nothing
must be deleted; the tool identity was not added to the dump key (no
natural slot in `text_dump_tag`).

## Tests

`tests/test_dsftool_identity.py` 4 (new), `tests/test_dsftool_dump_census.py`
2 (1 new). Covering files run once: 227 passed
(`test_ci_workflow_triggers`, `test_no_airport_specific_code`,
`test_console_encoding`, the three DSFTool files) + 56 passed
(`test_tools_index`, `test_blast_index`). `tools/ratchets.py`: duplicate
PASS, layers PASS; no size warning for a touched file.

## Open, for the master

1. Linux + Windows recipes unproven until the first dispatch.
2. macOS CI uses the runner's default Xcode (16.x), the local proof used
   27.0 — the smoke per slice is the guard.
3. Windows links upstream's prebuilt `zlibstat.lib` (option: vcpkg
   `zlib:x64-windows-static` built from source + a project override).
4. `-fno-delete-null-pointer-checks` is a build flag standing in for a
   source fix nobody upstream has made (option: carry a third, local
   one-line patch `longs.data()`; or report the UB upstream).
5. Linux arm64 is not built (the bundle has no `lin/DSFTool-aarch64`
   today either).
