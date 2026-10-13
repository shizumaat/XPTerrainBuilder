# robust591 — lane notes (#591, #600, #595, #602), 2026-10-12

Branch `claude/robust591` from main 89693e99d. One commit per issue.

## #591 — the overlay step never read its converter's result

- WRONG: `O4_Overlay_Utils.build_overlay` read `fingers_crossed.returncode`
  after a `readline` loop with no `wait()` — always `None`; the second
  conversion (`-text2dsf`) was not checked at all. A hung converter held
  the step for ever (the read loop has no bound).
- FIX: the DSFTool launch (`DsfToolError`, `_run`, `_exit_in_words`) moved
  out of `auto_patch_v2/airport/dsf_write.py` into `src/O4_DSFTool.py`
  (`run`, `exit_in_words`, `DsfToolError`) — importing the airport package
  from a tile step costs ~0.36 s and couples the legacy step to it;
  `dsf_write` keeps `_run` / `_exit_in_words` / `DsfToolError` / `subprocess` (where the twins stand in for the tool) as handles
  on the same objects, so `EXCEPTION_CODES["DsfToolError"]` and every
  caller are unchanged. `run` now returns what the tool printed.
- `O4_Overlay_Utils.convert_overlay_dsf(direction, source, converted)`:
  removes what an earlier run left under the output name, runs the tool
  bounded by `OVERLAY_CONVERSION_TIMEOUT_S` (900 s), and ends the step as
  `overlay_tool_failed` on a crash, a non-zero exit (file written or
  not), the time limit, and an exit 0 that wrote nothing.
- The tool's output is echoed after it ends (it was echoed line by line).
- NOT done: the 7-Zip extraction (`subprocess.run`, waited, exit not
  read, no time limit) — a failed extraction leaves no DSF and the next
  conversion now fails by name; a hung 7-Zip still hangs.

## #600 — a short `.dds` under the final name

- WRONG: `O4_Imagery_Utils.convert_texture` handed the converter the
  texture's final path; `O4_DSF_Utils.build_dsf` asked
  `os.path.isfile(target_tex)` at three sites.
- FIX: `src/O4_DDS_File.py`. `expected_size(header)` computes the file
  length from the 128-byte header (width, height, mip count, FourCC /
  DX10 format / bit count); checked against DDSTool's own output:
  4096 px DXT1 13 mips = 11,184,952 bytes, 256 px DXT5 = 87,536 — exact.
  `is_whole(path)` is the presence test (size >= expected; a format the
  module cannot size is judged by its header alone).
  The converter writes `<texture>.<pid>.<token>.partial.dds` beside the
  texture; `land` renames it on (`O4_Held_File.retrying_a_held_file`)
  only when whole. A conversion sweeps the partials an earlier killed
  conversion of the same texture left.
- WHY the partial keeps the `.dds` ending: the Windows / Linux converter
  is NVTT 3 `nvcompress` (`usage: … infile(or dir) [outfile(or dir)]`),
  which cannot be run here; a name it might read as a folder or another
  container was not risked. DDSTool (mac) was run with both names.
  Readers that list `*.dds` skip partials: `_count_dds_textures`, the
  `cover_airports_with_highres == "Existing"` scan (its name parser
  would have raised on one). `remove_unwanted_textures` removes a
  leftover partial as it removes any unreferenced `.dds`;
  `tile_time_model` and `O4_Qt_Map.texture_provider` do not match one.
- A DXT-format replacement is now an atomic replace too (it was a
  rewrite in place). NOT done: the `getsize < 20000000` DXT1/DXT5 test
  in `build_dsf` (the header's FourCC would answer it), mask PNGs
  rewritten in place, the geotiff path.

## #595 — `unavailable` rungs that are no cap

Corpus scan (read only, `/Users/noah/XPTerrainBuilderData/Elevation_data/
**/*_airport_insets/*.json`, 2026-10-12): 845 sidecars, 48 with a ladder;
rungs: 53 delivered, 11 no-coverage, 5 below-threshold, 4 out-of-coverage,
2 partial, 2 unavailable — both the CAP class (#594). ZERO rungs of the
classes below, zero `transient`.

Fake transport (`two_providers`), delivered rung 2, rung 1 refused:

| class | per build before | per build now |
|---|---|---|
| decoder missing | 2 index queries + 3 rung fetches (whole ladder) | 1 index query (the other finer rung), 0 fetches |
| refused download / other `unavailable` | 2 index queries + 3 rung fetches | unchanged |
| `transient` rung | 2 index queries + 3 rung fetches | unchanged |

- DECODER (implemented): the class is read from the ENGINE, not from the
  refusal's wording — a rung is in it when
  `provider_required_capabilities(rung)` holds one the engine lacks. The
  attempt records `missing_capabilities` and `declined_under`
  (`_rung_ask_signature`: definition digest, engine version,
  capabilities) and NO `listing_ids` (nothing is said about the listing).
  `_ladder_recheck_rungs` — the one selection `ladder_recheck` and
  `ladder_recheck_owed` share — drops such a rung while the signature
  holds. The capability appearing, a new engine or an edited `.elv`
  moves the signature and the rung is asked (every id new → ladder
  re-run once).
- REFUSED DOWNLOAD / TRANSIENT / OTHER (NOT implemented — needs a
  ruling). "Re-fetch only when the earlier refusal is gone" needs a way
  to learn that without fetching, and the re-check is ratified as
  `discover()` only (RULINGS 2026-09-30aw (2)); 2026-09-30bl says a
  transient rung "is asked again". ~50 `ProviderUnavailable` sites raise
  this class with no marker telling a refused download from a product
  the engine could not use (no CRS, unknown vertical units). Options:
  1. As is: whole ladder re-fetched every build while the refusal lasts.
  2. Remember under listing + signature like the cap: 1 index query per
     rung per build; the refusal clearing is not seen until the listing,
     the `.elv` or the engine version moves — a transient remembered.
  3. Option 2 with an age limit (re-run after N days): needs the number.
  4. A probe: the refusal records the refused source; the re-check asks
     the listing and one HEAD per refused source, re-fetching when it
     answers 200. 1 index query + 1 small request per build; covers
     whole-file downloads only (`downloads.download_whole`), not WCS /
     ArcGIS query refusals; a new network call in the re-check.
  5. Re-try the refused rung alone: no re-download of the good inset,
     but a rung of 62 tiles whose last tile refuses downloads 61 each
     build.

## #602 — `assert 7 == 6` on Windows

- READ: the product is bounded — `retrying_a_held_file` is a `for` over
  `HELD_FILE_ATTEMPTS` (6); a cutter makes at most 1 (EXDEV) + 6 calls.
- The twin's fixture let both threads run the REAL `os.replace` onto one
  name at once. On a real Windows runner that is the #205 condition
  itself: Windows refuses one of them, the product retries (backoff not
  slept, the fixture records it) — one uninjected attempt, 7. The run
  got as far as the count, so both cutters had succeeded, the
  destination was whole and no staging file was left.
- FIX (test only): the fixture runs the real replace one thread at a
  time; the loser's hold count is injected (1, 2, 5); the twin asserts
  the property — no error, destination whole, no leftovers, every
  injected refusal consumed, injected ≤ attempts ≤ 2 × (1 + 6).
