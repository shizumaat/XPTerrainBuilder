# Vendored AppImage type-2 runtime

`runtime-x86_64` is the small launcher that becomes the first bytes of every
Linux AppImage we ship: it runs first on the tester's machine, mounts (or
extracts) the squashfs payload and executes `AppRun`.

| | |
|---|---|
| Source | <https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64> |
| Upstream commit | `75849dce7cc37e4319b633df1f116ca895c71a12` (release `continuous`, asset updated 2026-06-23) |
| Downloaded | 2026-09-17, by the session, on the owner's explicit approval |
| Size | 944,632 bytes |
| SHA-256 | `1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf` |
| Type | ELF 64-bit, x86-64, static-pie |
| Licence | MIT (© 2004-23 probonopd); statically links third-party components — see `LICENSING.md` |

## Why it is vendored (owner decision 2026-09-17)

`appimagetool` is pinned by checksum in the release workflow, but by default
it DOWNLOADS this runtime at build time from upstream's `continuous` tag — a
rolling release upstream overwrites. The first code a Linux tester runs
would then come from a URL whose contents can change between two of our
releases, unverified by us. A checksum pin alone would eventually fail a
release, because upstream publishes no immutable versions. Vendoring one
verified copy removes the network dependency and the drift together:
`scripts/make_appimage.sh` passes it with `--runtime-file` and refuses to
build if its SHA-256 differs from the one recorded here.

## Updating it

Deliberately, never as a build side effect: download the new asset, verify
it is a static ELF, replace the file, update the table above (commit, date,
size, SHA-256) and the pinned hash in `scripts/make_appimage.sh` in the same
commit, and prove it with one Release dispatch on a branch (the Linux job
builds a tile and solves an airport through the AppImage before upload).
