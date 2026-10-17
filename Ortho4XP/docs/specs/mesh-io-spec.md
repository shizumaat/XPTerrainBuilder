# Mesh I/O — spec (2026-10-17, Beta 3 W3)

Status: PROPOSAL. Plan: `beta3-build-speed-plan-20261017.md` W3; depends on the
frozen fixtures (W2, `code-quality-beta3-spec.md` §6). Issues: manifest B3-16,
B3-17. Prior art: E `docs/specs/mesh-triangle-io.md`, ADR 0004,
`native/triangle4xp/CHANGES.md`.

## 1. Problem (verified 2026-10-17)

Every Triangle4XP exchange file and the `.mesh` are parsed and written line by
line in Python:

| Site | What | Lines |
|---|---|---|
| `O4_Mesh_Utils.py:917, 1013, 2128` | `.node` input re-read (count + per-row float parse) | per-line |
| `O4_Mesh_Utils.py:985, 1511` | `.poly` input re-read | per-line |
| `O4_Mesh_Utils.py:2242-2278` | `post_process_nodes_altitudes`: `.1.node` (6 floats × N) and `.1.ele` (3 ints + attribute × T) | per-line |
| `O4_Mesh_Utils.py:2584-2635` | `write_mesh_file`: `{:.15f}` formatting per vertex, `.ele` copied per triangle | per-line |
| `O4_Mesh_Utils.py:3151-3197` | `read_mesh_file` (shared 1: `O4_DSF_Utils.py:864`) | per-line |
| `O4_Mask_Utils.py:1088-1113` | a second `.mesh` reader (neighbour meshes for masks) | per-line, duplicate of `read_mesh_file` |

E measured (ADR 0004): Triangle4XP 2.9 s for 1.2 M triangles, 7.3 s of text
parse/format around it in upstream Ortho4XP; binary I/O took its mesh step
8.51 → 2.79 s. Our `Utils/src/Triangle4XP.c` shares E's base (Feb 21 2024);
`Utils/CMakeLists.txt` builds it; binaries ship for mac, win, lin.

## 2. Consumer census of the `.mesh` file (RULINGS 2026-08-30l)

The `.mesh` text format is read by: `O4_DSF_Utils.build_dsf` via
`MESH.read_mesh_file` (`:862-864`); `O4_Mask_Utils` (`:185-189`, `:460`,
`:1056`, own parser `:1088-1113`); `auto_patch/mesh_sampler` through
`engine_v2.py:1419` (object stage); `o4_engine/mesh_commands.py:59`;
`tools/airport_inset_acceptance.py:157`; `O4_Step_Reuse._outputs` (identity
only); `O4_Tile_Utils` (stat/isfile only). Ruling: **the `.mesh` stays a text
file, byte-identical** — every consumer keeps reading it; what changes is HOW
it is read and written (one numpy reader/writer), and the Triangle exchange
files (`.node/.poly/.1.node/.1.ele`), which only `O4_Mesh_Utils` and
Triangle4XP touch, gain a binary form behind a flag.

## 3. Landing 1 — one shared numpy reader/writer (B3-16)

`src/O4_Mesh_IO.py` (new, ≤ 300 lines):

- `read_mesh(path) -> MeshArrays` (version, `xyz` float64 (N,3) with the
  100000 altitude scale applied, normals (N,2), triangles uint32 (T,3),
  attributes uint32 (T,)) — `numpy.loadtxt`/`fromstring` over the block
  slices; `read_mesh_file` becomes a thin adapter returning its current tuple
  (`O4_DSF_Utils` unchanged); `O4_Mask_Utils`' parser is deleted in favour of
  it (duplicate ratchet falls);
- `write_mesh(path, vertices, ele_path)` producing EXACTLY today's bytes:
  `numpy.savetxt` with `fmt="%.15f %.15f %.15f 0"` matches `"{:.15f}"` for
  finite doubles (same `%f` formatting in CPython); the `.ele` copy with the
  degenerate-attribute normalisation (`read_triangle_attribute`) kept; the
  temp-file + `os.replace` kept;
- `read_triangle_node(path)`, `read_triangle_ele(path)`, `read_node_input`,
  `read_poly_input` for the text exchange files (vectorised; replaces the six
  per-line sites);
- `post_process_nodes_altitudes` and `write_mesh_file` call these.

Gate: `.mesh` sha256 identical on the frozen fixture and on one real tile
(`run_tile_mesh_only.py` ×3 before/after for the wall). Twin:
`tests/test_mesh_io.py` — `read_mesh(fixture)` equals the legacy
`read_mesh_file` tuple field by field (the legacy function is kept in the test
module as the oracle, then deleted from `src`); `write_mesh` reproduces the
fixture bytes; a `.1.ele` with a float attribute reads as today
(`test_mesh_degenerate_attribute.py` stays).

## 4. Landing 2 — binary Triangle4XP I/O behind a flag (B3-17; owner Q6)

Re-implemented from E's layouts (`mesh-triangle-io.md`; simple enough that no
code is copied): a `-b` switch in `Utils/src/Triangle4XP.c` makes
`readnodes/readholes/writenodes/writeelements` and the `formskeleton` segment
read use binary tables — magic 8 bytes, `int32` header, `float64`/`int32`
tables, native byte order — with the text path intact and the `.alt`/`.weight`
rasters read in one `fread`. Python side: `O4_Mesh_IO.write_node_binary/
write_poly_binary/read_node_binary/read_ele_binary`, chosen by
`O4_TRIANGLE_IO=binary|text` (default `text`); `O4_Mesh_Utils` passes `-b` and
the binary names when on.

Admission: the three binaries rebuilt from the same source and placed in
`Utils/{mac,win,lin}` with the modification notice Triangle's licence requires
(`LICENSING.md` §3, §6; a `Utils/Triangle4XP-CHANGES.md`); the flag flips on
only when all three exist. Twin: on the fixture, text-mode and binary-mode
`.1.node`/`.1.ele` decode to identical doubles/ints and the `.mesh` written
from either is byte-identical (E's P0 test, re-done here). CI builds the
Linux binary from source (`cmake`) and runs the twin; mac/win twins run where
the binary exists.

## 5. Measurement

`tools/run_tile_mesh_only.py` ×3 per arm (text numpy, binary) on one tile with
the vector step reused; report medians; the mesh step is inside the 300 s tile
budget, so any regression ≥ 3 s on the default (text) arm is a review.
Hypothesis: landing 1 removes most of the Python parse/format time (E: ~5 s of
7.3 s); landing 2 removes the rest and Triangle's own text I/O.

## 6. Files (`tools/blast.py` 2026-10-17)

`src/O4_Mesh_Utils.py` (27 importers; env flags `O4_BANK_BLEND_DUMP`,
`O4_HAIRLINE_PREFLIGHT`; writes/reads `Data<tile>.alt`); `src/O4_Mask_Utils.py`
(15 importers); `src/O4_DSF_Utils.py` (via `read_mesh_file`, unchanged
signature); `Utils/src/Triangle4XP.c`, `Utils/CMakeLists.txt`; new
`src/O4_Mesh_IO.py` with `__all__` and docstring (the map twin). New env flag
`O4_TRIANGLE_IO` gets a test.

## 7. Out of scope

The mesh refinement itself (Triangle's criteria, `-pq… -S`), the `.alt` DEM
preparation, the `.mesh` format (stays text), the DSF encoder (W7).

## Licence

Triangle4XP modifications stay under Triangle's licence with the notice
(`LICENSING.md` §3). Python side re-implemented; `Ortho4XP/` (GPL-3).
