# Modifications to Triangle4XP.c (notice required by Triangle's licence)

`Utils/src/Triangle4XP.c` is Jonathan Richard Shewchuk's **Triangle 1.6**,
modified by Oscar Pilote for Ortho4XP (his changes are delimited in the source
by `Start of : Added for Triangle4XP` / `End of : Added for Triangle4XP`), and
modified further as listed below. It stays under Triangle's own licence (see
the header of the source file and `LICENSING.md` §3 and §6: free-of-charge
distribution only, source shipped with the object code, the header notice kept
intact, modifications stated). It is **not** covered by the GPL of the rest of
this repository.

Base: Ortho4XP's `Utils/src/Triangle4XP.c` ("Last modified : Feb 21st 2024"),
vendored in this repository at `38b3eaf54`.

## 1. XPTerrainBuilder: the stock maximum-area test (2026-09-09, `ea85d3732`)

`testtriangle()`: Shewchuk's maximum-area test (stock `triangle.c:7336`) is
restored ahead of the fork's `if (attribute >= 8) return;` exemption, with the
`area = fabs(...)` line hoisted above it (RULINGS 2026-09-09aa). The comment in
the source names the ruling. Nothing else in that commit.

## 2. OrthoStudio XP: binary exchange files (switch `-b`) and one-read rasters (2026-10-17)

Taken from OrthoStudio XP (radioharris, <https://github.com/radioharris/orthostudio-xp>,
`native/triangle4xp/Triangle4XP.c` and `CHANGES.md` at
`7c028d82dcc59a27296972973aa0663ef37efddc`), three-way merged onto this file
(base = the vendored file above, ours = with change 1, theirs = OrthoStudio
XP's): every hunk is delimited in the source by `Start of : Added for
OrthoStudio XP` / `End of : Added for OrthoStudio XP` (or `Modified for
OrthoStudio XP`). Credit for these changes is radioharris's; their list, as
OrthoStudio XP's `CHANGES.md` gives it, all ten items taken:

1. Header: one line after "Last modified" (here two lines, pointing to this file).
2. `#include <stdint.h>` after `<string.h>`.
3. Forward declarations of `osxp_malloc()` and `osxp_read_exact()` after the
   `readline()` / `findfield()` prototypes.
4. `struct behavior`: new field `int binary_io`.
5. `parsecommandline()`: `b->binary_io = 0`; new switch letter `b`; `-b`
   combined with `-r` prints an error and exits with status 1.
6. `syntax()`: two help lines documenting `-b`.
7. `main()`: the `.alt` raster (`nxdem * nydem` float32) and the `.weight`
   raster (`1001 * 1001` float32) are read with one `fread` each instead of one
   per sample; a short read is an error (`triexit(1)`) where it previously left
   the tail of the array uninitialised. The unused `dummy` variable is removed.
8. New static helpers `osxp_malloc()`, `osxp_read_exact()`,
   `osxp_write_exact()`, `osxp_check_magic()`, the magics `OSXPNOD1`,
   `OSXPPOL1`, `OSXPELE1`, and a compile-time error if `SINGLE` is defined.
9. New functions (non-`TRILIBRARY` builds): `readnodes_binary()`,
   `readholes_binary()`, `writenodes_binary()`, `writeelements_binary()`, with
   the same effects and values as their text counterparts.
10. Dispatch: `readnodes()`, `readholes()`, `writenodes()` and
    `writeelements()` call the binary variant when `b->binary_io` is set; in
    `formskeleton()` the binary path reads the segment table in three `fread`
    calls before the unchanged insertion loop.

Merge notes (XPTerrainBuilder): change 1 is kept untouched (no OrthoStudio XP
hunk touches `testtriangle()`); OrthoStudio XP's base differs from ours on one
line, `parsecommandline()`'s `scaly2 = scalx * scalx;` — ours (`scaly *
scaly`) is kept (the variable is never read). Not changed: `triunsuitable()`,
the curvature map, `altitude()`, `set_normal()`, the Delaunay, segment
insertion, hole carving, attribute plague and quality code, all text readers
and writers, the text mode's exit codes and messages.

## Binaries

| Platform | File | Built from this source | How |
|---|---|---|---|
| macOS (universal x86_64 + arm64) | `Utils/mac/Triangle4XP` | yes, 2026-10-17, sha1 `87dec0d0f852e4bd06e616dcabd7c7daf451aa67` | `cc -O2 -arch arm64 -arch x86_64 -o Utils/mac/Triangle4XP Utils/src/Triangle4XP.c -lm` (Apple clang 21.0.0); floating-point contraction left at the compiler default, as the shipped binary was built |
| Windows x64 | `Utils/win/Triangle4XP.exe` | **no** — upstream Ortho4XP's binary (predates change 1 and change 2) | — |
| Linux x86_64 | `Utils/lin/Triangle4XP` | **no** — upstream Ortho4XP's binary (predates change 1 and change 2) | — |

The engine uses `-b` only when `O4_TRIANGLE_IO=binary` is set, the run does
not refine (`-r`), and the platform's binary carries the switch (default
`text`); RULINGS 2026-10-17a Q6 keeps the flag off until all three binaries
are rebuilt from this source and the text == binary twin
(`tests/test_mesh_triangle_binary.py`) passes on each.
