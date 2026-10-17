# Texture encode — spec (2026-10-17, Beta 3 W0 + W6)

Status: PROPOSAL. Plan: `beta3-build-speed-plan-20261017.md` W0 (§3) and W6
(§4). Issues: manifest B3-01, B3-15. Prior art: E `textures/mips.py`,
`textures/encode.py`, `docs/benchmarks/dds-encoder.md`, ADR 0005 (quality gate).

## 1. Problem (verified 2026-10-17)

`src/O4_Imagery_Utils.py::convert_texture` (`:2727`):

- a texture that needs a colour filter, a harmonization field or an alpha
  mask is re-saved as a full 4096² PNG in `Tmp_dir` with Pillow's DEFAULT
  compression — `big_image.save(file_to_convert)` at `:2844` and `:2893`, no
  `compress_level` — then handed to the converter; the PNG is deleted after;
- the converter is a subprocess per texture: `DDSTool --png2dxt1|5` on macOS
  (`:199-202`, `:2908-2913`), `nvcompress -bc1|-bc3 -fast` on Windows/Linux
  (`:2915-2921`); `effective_convert_slots` = cores−2 threads launch them
  (`O4_Parallel_Utils.py:240-252`, `O4_Tile_Utils.py:500-512`);
- the partial-name discipline (#600, `O4_DDS_File`) and the `is_whole` skip in
  `O4_DSF_Utils.py:1229-1233` stay.

E measured (M4 Pro, nvcompress x86_64 under Rosetta): PNG save ~0.75 s per
texture; ispc_texcomp BC1 53 ms / BC3 64 ms per 4096² level 0; whole pipeline
0.33 s/texture, 6.8× on 12 workers; nvtt builds mips in LINEAR LIGHT (gamma
2.2, alpha on stored values, truncating quantiser) — a stored-value box chain
is 0.5–6.8 codes darker at distance (`dds-encoder.md` §1). Our DDSTool on
arm64 is unmeasured; the gain of §4 is unknown until it is.

## 2. Gates

- §3: `.dds` bytes IDENTICAL — the converter reads decoded pixels; PNG
  compression level changes the file, not the pixels.
- §4: `.dds` bytes CHANGE (different encoder, different mip filter). Gate is
  the owner's sim read (Q5) plus a per-mip PSNR/SSIM report against the
  current encoder; the flag stays OFF until ruled.

## 3. W0 — the temp PNG (B3-01)

`big_image.save(file_to_convert, compress_level=1)` at both sites (one helper,
`_save_temp_png(image, path)`, so the two sites cannot drift). Twin: a 64² RGBA
image saved at level 1 and at default decodes to equal arrays
(`tests/test_dds_file.py` neighbourhood). Measurement: one tile with a colour
filter or masks, conversion wall per texture from the convert-queue timings,
×3 both arms; `.dds` sha256 identical. Hypothesis: 0.5–0.75 s per filtered or
masked texture.

Also consider (same lane, same gate): on macOS DDSTool can read JPEG? No —
`--png2dxt` takes PNG; keep the PNG. On Windows/Linux nvcompress reads PNG and
TGA; keep the PNG.

## 4. W6 — in-process BC1/BC3 with linear-light mips (B3-15; owner Q4, Q5)

`src/O4_DDS_Encode.py` (new):

- `mip_chain(rgba, mode="gamma22")`: level 0 uint8; RGB carried in float32
  linear light via a 256-entry LUT, 2×2 box per level, re-encoded with a 2.2
  power and rounding; alpha box-filtered on stored values (E's finding on
  nvtt; our DDSTool's chain is MEASURED first — §5 step 1 — and the mode is
  set to match it, not E);
- `encode_bc1/bc3(level) -> bytes` through `ispc_texcomp` (in-process,
  releases the GIL); fallback `nvcompress`/`DDSTool` subprocess when the
  wheel is absent (today's path, unchanged);
- flat-block post-pass for uniform 4×4 blocks (E §4: ispc quantises uniform
  blocks to the nearest 5:6:5, −4 to −6 dB on open sea; the fix is the
  optimal two-endpoint single-colour table) — part of the first landing, since
  sea textures are most of many tiles;
- DDS header writer (`O4_DDS_File` is the shared DDS module: extend it with
  `write_header`); `dxt5` flag → BC3;
- a process pool of `effective_convert_slots` workers replaces the
  subprocess-per-texture threads when the flag is on; the partial-name
  discipline is kept (write partial, `DDS.land`).

Flag: `O4_DDS_ENCODER=inprocess|tool` (default `tool`). Dependency:
`ispc_texcomp` wheels for the three platforms (owner Q4; licence MIT, to be
verified and recorded in `LICENSING.md` §3).

## 5. Measurement and acceptance for §4

1. Identify DDSTool's and nvcompress's mip filter on one texture (decode the
   reference mips, compare with stored-value, sRGB and gamma-2.2 chains — E
   §1's method, our own numbers). The mode that matches is the default.
2. Quality: PSNR/SSIM per mip level 0–6 against the source chain, in-process vs
   current tool, on the textures of one tile (land, sea, masked). Report the
   table; no threshold is set here — the owner reads the sim.
3. Speed: textures/s on one tile, `--runs 3`, both encoders, each platform
   where a wheel exists.
4. Owner sim read of one tile built with the flag on. Default flips only on a
   written ruling.

Rollback: `O4_DDS_ENCODER=tool`, `git revert`.

## 6. Files (`tools/blast.py` 2026-10-17)

`src/O4_Imagery_Utils.py` (25 importers; tests `test_dds_file`,
`test_imagery_*`); `src/O4_DDS_File.py` (shared `is_whole/partial_name/land`);
`src/O4_Tile_Utils.py` (convert workers); `src/O4_Parallel_Utils.py`
(`effective_convert_slots` shared). No wire protocol, no env default-ON flag
without a test.

## 7. Out of scope

Changing the JPEG orthophoto cache format; per-texture content cache (that is
`step-reuse-content-keys-spec.md` §2.5); `.ter` file generation; the gdal
geotiff path of `convert_texture`.

## Licence

Re-implemented from E's documented measurements; `Ortho4XP/` (GPL-3).
`ispc_texcomp` is Intel's (MIT) — the wheel's licence file ships with the
engine if admitted.
