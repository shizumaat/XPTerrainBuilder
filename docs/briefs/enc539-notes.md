# enc539 — text files read in the machine's default encoding (issue #539)

Branch `claude/enc539`, based on `origin/claude/flaky510` + `origin/main`.

## What was measured before the fix (old reader, emulated code page)

`O4_Imagery_Utils.initialize_providers_dict` opened each `.lay` with no
encoding and NO `except`. `Providers/Albania/AL.lay` carries one UTF-8
em dash in a comment.

| ANSI code page | old `.lay` reader |
|---|---|
| cp932, cp936, cp949, cp950 | `UnicodeDecodeError` raised out of `initialize_providers_dict` at AL.lay — every provider listed after it is gone too (20 of 66 were parsed on this machine's directory order). `Ortho4XP_Qt.py:343` calls it unwrapped: the Qt app does not start. `o4_engine/jsonl.py:221` wraps it: the engine goes on with a partial imagery registry and no combined providers |
| cp1250, cp1252, cp1253, cp874 … | all 66 parse (the dash is in a comment) |

Other shipped non-ASCII files: `Providers/Switzerland/capabilities_CH_ZH.xml`
(undecodable under cp950/1253/1255/1257/874, but no shipped `.lay` names it —
latent), `capabilities_FIN.xml` and `Extents/LowRes/France.ext` (decode
everywhere; the `.ext` reader already named UTF-8), `Licence/copyright.txt`
(no reader in src). `.flt`, `.comb`, the two server lists: ASCII.

## Census — text opens in `Ortho4XP/src`, `Ortho4XP.py`, `Ortho4XP_Qt.py`

Scan: `tests/test_windows_text_io._offences` (AST; `open` / `read_text` /
`write_text` with no `encoding=`, text writes with no `newline=`).
**Start: 139** (134 in the engine + 5 in `src/Unused`, which is not
imported). **Now: 93**, all in the last class of the table.

| class | readers (file:line at start) | encoding named? | a decode error did | reading now, and why |
|---|---|---|---|---|
| Imagery registry, shipped and user-extensible: `.lay` `.comb` `.flt` `.ext`, capabilities XML | `O4_Imagery_Utils` 668 (.lay), 961 (.comb), 328 (.flt), 368 (XML), 252 (.ext) | no ×4; `.ext` utf-8 | `.lay` `.flt` `.ext`: RAISE (no except); `.comb`: skip, message without file or error; XML: skip the provider, message without error | `TEXT.open_supplied`: UTF-8 (BOM dropped), latin-1 when the bytes are not UTF-8. People add their own provider files; a cp1252 comment must not stop the app. The bundle's self-check still demands UTF-8 of OUR files |
| Elevation registry `.elv` | `O4_Airport_Elevation_Insets` 524 | utf-8-sig (flaky510) | skip with file + error type | unchanged; the constant is now `TEXT.SHIPPED_ENCODING` |
| Shipped server lists | `O4_Mesh_Utils` 43 (`community_server.txt`), `O4_OSM_Utils` 34 (`overpass_servers.txt`) | no | silent skip (bare `except: pass`; `lvprint(1, e)`) | `TEXT.open_supplied` (user-editable, cannot fail on a byte) |
| Law / rules `.toml` | `law/model.py` 956, `classify/rules.py` 233 | binary (`tomllib`) | — | none needed |
| Config: `Ortho4XP.cfg`, per-tile `.cfg` | read `O4_Config_Utils` 112, 302; `O4_Settings_Model` 285; `O4_Tile_Info` 102; `planar/__main__` 39. write `O4_Config_Utils` 145; `O4_Settings_Model` 324 | no (reads and writes) | 112: RAISE at import (only `FileNotFoundError` is caught); 285, 102: RAISE; 302: returns 0; writers: `UnicodeEncodeError` on a path outside the code page | writers UTF-8; readers `TEXT.open_supplied(legacy_ansi=True)`: UTF-8, else this machine's ANSI page (a cfg beta 1 wrote), else latin-1 |
| X-Plane installer list `x-plane_install_1N.txt` | `O4_Qt_Wizard` 50 | no, `errors="replace"` | garble (path not found) | `TEXT.open_supplied(legacy_ansi=True)` |
| X-Plane / pack text, STREAMED: `apt.dat`, DSF text dumps, `library.txt`, CIFP, OBJ8 | already named: `apt_dat_reader` 849/949, `airport/apt_dat` 340, `agp_reader` 124, `O4_MSFS_XPlane_Pack` 259/297, `O4_OSM_Utils` 96–434 (`.osm`, utf-8), obj8 readers (latin-1). Unnamed, 16 sites: `cifp_reader` 111, `dsf_reader` 228/901, `obj8_reader` 305, `object_rebake` 1202, `backup_state` 534/536, `airport/cifp` 57, `airport/dsf` 232/426, `dsf_write` 1017/1063, `facade` 236/324, `partition_cache` 246, `placement_write` 314 | 16 no, each with `errors="replace"`/`"ignore"` | garble only — but under a double-byte page a lead byte can take the ASCII character after it into one glyph, so a token next to a non-ASCII name could change | `encoding="utf-8"` with the site's own `errors=`: X-Plane text is UTF-8 by spec, files are large (not loaded twice), and this is exactly what macOS/Linux already read |
| OBJ8 patch objects (user) | `O4_Vector_Map` 3432 (first-line sniff), 4337 (body) | no | sniff: skip with message (kept); body: RAISE, ends the tile build | sniff `utf-8` (same acceptance as macOS); body `utf-8`, `errors="replace"` (only numeric lines are read) |
| Overlay DSF text, read and written back for DSFTool | `O4_Overlay_Utils` 143 / 149 | no | RAISE | both `utf-8` + `surrogateescape` (bytes survive the round trip; the pattern `dsf_write` already uses) |
| Engine-written, may carry non-ASCII | `O4_UI_Utils` 219 (`Ortho4XP.log`), `O4_DSF_Utils` 351 (`.ter`), `O4_Mask_Utils` 1654/1677 (`.ext`, read back by the utf-8 extents reader), `O4_Bathymetry_Band` 468 (GDAL `.vrt`, UTF-8 paths) | no | log: line lost (bare except); `.ext`: written cp1252, read utf-8; `.vrt`: garbled paths | UTF-8 (log with `backslashreplace`; vrt with `surrogateescape`) |
| Engine-written and read back, ASCII on disk — NOT changed, recorded in the ratchet | 93 sites in 28 files: JSON indexes / stamps / sidecars / provenance (`O4_Airport_Elevation_Insets` 18, `elevation_access/strategies/*` 17, `O4_Elevation_Level` 5, `O4_OSM_Extracts` 3, `tile_time_model` 3, `O4_Qt_GUI` 4, `object_rebake` 3, …), numeric mesh text `.node` `.ele` `.poly` `.mesh` (`O4_Mesh_Utils` 17, `O4_Mask_Utils` 4, `O4_Vector_Utils` 2), `/proc/meminfo`, a write probe | no | — | none: every JSON writer in src is `json.dump(s)` with the default `ensure_ascii=True` (no `ensure_ascii=False` anywhere in src), so the bytes are ASCII under every code page; mesh text is numbers |

Counts of the 41 sites fixed: shipped registry and lists 6, config 8,
streamed third-party 16, OBJ8 + overlay 4, engine-written 7.

## The helper

`src/O4_Text_Files.py` (new; `tools/blast.py --find` had no file-layer
helper — `O4_Console_Encoding` is the console's and says so):
`SHIPPED_ENCODING` (`utf-8-sig`), `WRITE_ENCODING`,
`decode_supplied`, `open_supplied(path, legacy_ansi=False)`.
`INSETS.ELV_ENCODING` is now that constant.

## Parse identity (this machine)

`scratch snap.py`: all four imagery registries, the 97 `.elv` definitions,
the overpass list and the community server, as sorted JSON — sha256
`bd88ae4c5e7a033a` before and after (40 extents, 8 filters, 66 providers,
1 combined, 97 elevation providers). Only difference by design: a BOM at
the head of a file is dropped (no shipped file has one).

## Silent skips

- `.lay`: an unreadable file is now ONE provider gone with
  `WARNING: could not read provider file <dir/file> (<ErrorType>)`
  (it raised before).
- `.comb`: the message names the file and the exception type.
- capabilities XML: the message names the `.lay` and the exception type.
- `.elv`: already done by flaky510.
No file that parsed before is refused now; files that could not be decoded
are now read.

## Self-check

`src/O4_Imagery_Selfcheck.imagery_registry_selfcheck()`, called by
`O4_Proj_Runtime.import_selfcheck_main` (the frozen app runs it on all
three release legs; no workflow edit). New fourth line:

    imagery provider registry: ok 66 providers, 1 combined, 39 extents, 7 filters

Fails with `FAIL n of m files; not parsed …; not read as UTF-8 …`. The
registries and `FNAMES` directories in force are restored.

## Dotfiles

`Providers/Sweden/.SE.lay.swp` (`file`: Vim swap file, version 8.1)
removed. The four imagery walks and the `.elv` walk skip names starting
with `.`: before, `._NAME.lay` (a macOS resource fork) registered a
provider with the code `""` and its binary bytes went through the reader.

## Wire (step 7)

No gap. `o4_engine/jsonl.py` writes `json.dumps` lines (ASCII) after
`configure_console_streams()`; both entry files pin the console to UTF-8
before `freeze_support()`; the Qt app's worker pipes use
`child_console_pipe()` (utf-8, `replace`). `OrthoEngineClient.swift`
decodes UTF-8. `tests/test_console_encoding.py` holds it.

## Ratchet

`tests/test_windows_text_io.py`: `RECORDED_UNNAMED` (per file, 93 in 28
files; start 134) — a file may not exceed its recorded count, and the
recorded table equals the measured one.

## Found, not fixed

- The 93 recorded sites (ASCII on disk; see the last table row).
- Streamed third-party readers keep `errors="replace"`: a NON-UTF-8 path
  token in a pack's `library.txt` / DSF text is still lost (as on macOS
  today). `open_supplied` would keep it but loads the file whole.
- `Providers/Switzerland/capabilities_CH_ZH.xml` and `capabilities_CH_VS.xml`
  are named by no shipped `.lay`.
- `Licence/copyright.txt` is non-ASCII and has no reader in src.

## Measured (d299d7ddd)

- twins `tests/test_text_files_encoding.py`: 19; with the named suites
  (provider self-check, windows_text_io, console_encoding, v1_retired,
  no_airport_specific_code, newline_pinned, overlay_7z): 244 passed
- full non-Qt split: 9258 passed, 19 skipped, 1 xfailed, 1 xpassed, 1 failed
  (`test_newline_pinned`: `**kwargs` at the overlay `open` hid the mode
  from that gate — spelled literally in d299d7ddd, green)
- Qt `-n0`: 311 passed
- `tools/ratchets.py`: exit 0 (size warnings: `O4_Imagery_Utils` +24,
  `O4_Airport_Elevation_Insets` +5 here, `O4_Mesh_Utils` +3,
  `O4_Settings_Model` +3, `O4_Vector_Map` +2)
- CYXY harness build `CYXY_20261010T111625`: body_sha `5280c1eefe96`
  (the expected one), artifact ledger `edcfdc2a2a85`
