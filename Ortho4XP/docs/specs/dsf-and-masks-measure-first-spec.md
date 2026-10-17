# DSF encoder and masks — measure-first spec (2026-10-17, Beta 3 W7)

Status: PROPOSAL. Plan: `beta3-build-speed-plan-20261017.md` W7; after the
fixtures (W2) and the shared mesh reader (W3). Issues: manifest B3-18, B3-19.
Both items are written so that "not worth it" is a cheap, acceptable outcome.

## 1. DSF encoder (B3-18)

### Problem (verified)

`src/O4_DSF_Utils.py::build_dsf` (`:814`, 1,349 lines per `tools/ratchets.py
funcs`) is partly vectorised already: `_patch_triangle_commands` (`:34-64`,
numpy, "byte-identical to the historical per-word struct.pack loop";
`tests/test_dsf_encoding_vectorized.py`) and the pool writer (`:1965`).
Per-triangle Python loops remain at `:868` (water-type remap), `:1320`
(masked water triangles) and `:1574` (land and unmasked triangles). `build_dsf`
runs in its own thread beside the imagery download (`O4_Tile_Utils.py:
455-473`), so on a cold imagery cache it is off the critical path; on a warm
cache it is on it. E's numpy DSF encode is 1.8 s (ADR 0003) — E's figure for
E's encoder, not a measurement of ours.

### Rule

1. **Profile first** (one lane, read-mostly): `cProfile` of `build_dsf` on one
   tile with imagery and masks warm, ×3, through `O4_Tile_Utils` with the
   earlier steps reused (W1 makes this a one-step run). Report the wall of the
   three loops and of `build_dsf` as a share of tile compute.
2. **Threshold**: vectorise a loop only if its median wall is ≥ 3 s (1 % of
   the tile budget — the law's own unit of attention) AND `build_dsf` is on
   the critical path in the warm case. Below that, write "not worth it" with
   the profile in this file's §3 and close.
3. **Gate** for any vectorisation: `.dsf` sha256 identical on the fixture and
   on the tile (the `_patch_triangle_commands` precedent; MD5 footer included);
   `test_dsf_encoding_vectorized.py` gains the case.
4. The loop at `:868` is the natural first (a per-element remap is a numpy
   `where`); `:1320`/`:1574` carry the per-triangle terrain/texture
   assignment and the pool filling — split a helper per loop, never a second
   `build_dsf`. This is also #740 step-4 material (the 1,349-line function):
   the vectorised helpers are the first cuts of that split.

### Files

`src/O4_DSF_Utils.py` (imported by `O4_Tile_Utils` only in src; 10 tests);
no wire protocol; `use_test_texture` and the texture-mode branches untouched
(`texture-mode-spec.md`).

## 2. Masks (B3-19)

### Problem (verified)

`src/O4_Mask_Utils.py` already runs `masks_build_slots = max(2, min(12,
cores−2))` workers (`:69`, `:438`). The remaining per-mask cost is (a) the
neighbour-mesh read (`:1088-1113`, the duplicate text parser W3 replaces) and
(b) the shore transition: a loop of `GaussianBlur(1)` + threshold passes,
`stepsin = transin / 3` iterations (`:1414-1425`). An exact distance transform
(`scipy.ndimage.distance_transform_edt` — scipy is in the freeze? to be
checked; `scikit_fmm` wheel is in `Utils/win`) would replace the loop but
CHANGES the mask bytes: the blur-threshold iteration is not a Euclidean
distance.

### Rule

1. After W3 lands, profile `build_mask` ×3 on one coastal tile: mesh read vs
   transition loop vs image I/O.
2. The mesh read is fixed by W3 (byte-identical). If the transition loop is
   ≥ 3 s median per tile, write the finding with the profile; do NOT replace
   it in this plan — a mask change is a texture change in the sim and needs
   an owner sim read, which this plan does not request. Close as "measured,
   deferred" with the numbers.

### Files

`src/O4_Mask_Utils.py` (15 importers; tests `test_mask_blur`,
`test_bathymetry_masks`, `test_inland_shore_feather`, `test_harness`).

## 3. Results (filled by the lanes)

| Item | Profile (median of 3) | Decision |
|---|---|---|
| `build_dsf` loops `:868` / `:1320` / `:1574` | — | — |
| `build_mask` transition loop | — | — |

## Licence

Nothing from E; `Ortho4XP/` (GPL-3).
