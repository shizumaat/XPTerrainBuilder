# Bundled DSFTool

`Utils/<platform>/DSFTool[.exe]` is **DSFTool**, part of the X-Plane
Scenery Tools (XPTools), copyright Laminar Research.  The engine runs it
as a separate subprocess to turn a DSF into text and back
(`--dsf2text`, `--text2dsf`).

## Source

* Repository: https://github.com/X-Plane/xptools
* Release: Scenery Tools **24-5**, `DSFTool 2.4.0-b1` — commit
  `c31ed76b58d9cb3ab6e08e6c4026b2e3bf242e52` (2024-05-08).
* A build made by this project (`"patched": true` in
  `DSFTool.identity.json`) adds two upstream commits that no tool release
  carries yet — the `--dsf2text` crash on an overlay that sets a 16-bit
  object definition before its first pool select:
  * `9c1a06c7b21a63da1f862de1e1cdb7d0dd0baff1` "Fix dsf2text crash for
    object def indices over 255" (2026-03-08)
  * `a3725c8f5ed6d9681573496ab0153e550d54cd09` "Fix minor error"
    (2026-04-14)

  Nothing else is changed: the version string stays `2.4.0-b1`.  The
  recipe is `Utils/toolchains/build_dsftool.sh`; the CI workflow is
  `.github/workflows/build-dsftool.yml` at the repository root.

## Licence

xptools carries **no top-level licence file**.  The licence is stated in
its `README.md`, section "Licensing and Copyright":

> The code original to Laminar Research lives in the sub-directory "src"
> and is licensed under the MIT/X11 license.

and in the header of each source file (for DSFTool:
`src/DSFTools/DSFToolCmdLine.cpp`, `src/DSFTools/DSF2Text.cpp`,
`src/DSF/DSFLib.cpp`, `src/DSF/DSFLibWrite.cpp`, `src/DSF/DSFPointPool.cpp`
and the `src/Utils` files it compiles), reproduced here as the MIT/X11
licence requires:

    Copyright (c) 2004, Laminar Research.

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.

(The year in the header varies by file.)

Third-party code compiled into DSFTool, each under the terms in its own
source header in the xptools tree:

| Component | Where in xptools | Terms |
| --- | --- | --- |
| Tri Stripper 1.01, (C) 2002 Tanguy Fautré | `src/DSF/tri_stripper_101/` | zlib-style licence, in `tri_stripper.h` |
| LZMA SDK 19 (7z decoder), Igor Pavlov | `src/lzma19/C/` | public domain |
| MD5, (C) 1990 RSA Data Security, Inc. | `src/Utils/md5.c` | "derived from the RSA Data Security, Inc. MD5 Message-Digest Algorithm" |
| minizip `zip.c` / `unzip.c` 0.15, Gilles Vollant | `src/Utils/` | zlib licence |
| zlib, Jean-loup Gailly and Mark Adler | linked: the OS library on macOS and Linux; static `zlibstat.lib` (zlib 1.2.11, xptools `msvc_libs`) on Windows | zlib licence |

`Licence/copyright.txt` carries the engine's short DSFTool notice; this
file is the full one and ships beside the binaries (`Ortho4XP.spec` ships
the whole `Utils/` folder).

## Binaries currently bundled

The machine-checked record is `Utils/DSFTool.identity.json` (sha256 and
`--version` line per file; `tests/test_dsftool_identity.py`).  This table
is its readable copy — update both together.

| Path | Platform | Build | Notes |
| --- | --- | --- | --- |
| `mac/DSFTool` | macOS universal (arm64 + x86_64) | patched (24-5 + the two commits), compiled Oct 12 2026, CI run 38296810739 | Xcode 16.4 on macOS 15.7; deployment target 12.0; links OS libz, libc++, Carbon; ad-hoc signed (the app build re-signs it) |
| `win/DSFTool.exe` | Windows x64 | patched, compiled Oct 12 2026, CI run 38296810739 | MSBuild 18.10 (toolset v143); static CRT and upstream's static zlib 1.2.11, imports KERNEL32.dll only |
| `lin/DSFTool` | Linux x86_64 | patched, compiled Oct 12 2026, CI run 38296810739 | gcc 11.4 on Ubuntu 22.04; needs glibc >= 2.34 (the stock build needed 2.14); dynamic libz, libstdc++, libm, libgcc_s |

The stock files these replaced (Laminar's own build of 24-5, compiled May 9
2024) had sha256 `4abaed05…` (mac), `42cacb1f…` (win), `5645a338…` (lin);
they are in git history before the vendoring commit.

To replace them with a later build: `docs/DSFTOOL-VENDORING.md` at the
repository root.
