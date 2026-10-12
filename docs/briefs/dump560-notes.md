# Lane dump560 — notes (issue #560)

## RESUME HERE

State 2026-10-12: attribution DONE, fix + twins DONE and committed on
`claude/dump560`. Left: nothing in this lane's scope. NOT done (master's
call): the 0-byte file in the shared corpus is untouched; no KBFI closing
build was run, because it cannot pass — see "Found and not fixed".

## 1. Attribution (measured, not narrated)

**The 0-byte dump was written by DSFTool crashing, not by a race, a cancel
or a timeout.** `DSFTool 2.4.0-b1 --dsf2text` dies with SIGSEGV
(`KERN_INVALID_ADDRESS at 0x18`) on the stock Global Airports
`+47-123.dsf` (sha256[:8] `2f51dffe`), every time, in ~0.5 s. DSFTool
creates its output file before it reads the DSF, so each crash leaves a
0-byte file under the name it was given — the final dump name.

Evidence:
- macOS crash reports `~/Library/Logs/DiagnosticReports/Retired/DSFTool-2026-10-11-1954{25,26,27,28}*.ips`:
  12 reports in 4 s, parent process `Ortho4XP`, path
  `XPTerrainBuilder.app/…/Engine/_internal/Ortho4XP_Data/Utils/mac/DSFTool`,
  faulting frames at image offsets 36268 / 21776. The dump's mtime is
  19:54:28. 12 = 6 airports x 2 launches (the wrapper retried each crash
  into a temp file). Five more reports at 19:15:45 are the earlier run.
- Reproduced on a COPY in the lane scratchpad: `DSFTool --dsf2text
  <copy> out.text` exits 139, `out.text` is 0 bytes; the two crash reports
  it made carry the same frame offsets (36268 / 21776). The neighbour
  `+45-123.dsf` dumps fine (rc 0, 1.49 MB).
- Reproduced through the engine's own wrapper at base `aed288725`:
  `dsf_reader.ensure_dsf_text_path(copy, cache)` printed
  `[dsf-reader] WARN: DSFTool failed … died with <Signals.SIGSEGV: 11>`,
  returned `None`, and left `cache/+47-123.dsf.2f51dffe.text` at 0 bytes —
  the owner's file, same name, same size.

The chain in the app: `engine_v2.fresh_pack_dump` (called per airport in
each worker) -> `ensure_dsf_text_path` -> DSFTool crash -> warning at
verbosity 1 (not in `engine-stderr.log`) -> `None` -> `fresh_pack_dump`
returns `None` -> `load.py` finds no dump and raises "the pack DSF is
newer than every cached text dump", which was never the condition.

Why a retry could not heal it: the wrapper DID treat the empty file as
"re-convert" (#60), and re-ran DSFTool — which crashed again. The empty
file was a symptom on every run, not the blocker.

Why KSEA built: it is served by a custom pack
(`c_USA - 100_airport - KSEA Seattle Airports XP (DD)`), so its tile DSF
is another file. KRNT and KTIW likewise. The six refused airports are the
ones served by Global Airports.

Two workers / cancel: not the cause here. But the old write WAS unsafe
for both — DSFTool wrote straight to the final name, so a killed run or
two writers could leave an empty or half file there.

## 2. Fix

- `auto_patch_v2/airport/dsf_write.py` — `dump()` is the ONE dsf2text
  launch and is atomic: DSFTool writes `<dump>.<pid>.<token>.partial`
  beside the dump; it is renamed on only after exit 0 with bytes written;
  always removed otherwise. New `DsfToolError(RuntimeError)` says
  "crashed (SIGSEGV)" / "failed (exit N): …" / "did not finish within N s"
  / "wrote no text". Stale `.partial` litter (> 1 h) is swept.
- `auto_patch/dsf_reader.py` — `ensure_dsf_text_path` calls that `dump`
  (its own two `subprocess.run` launches are gone);
  `raise_on_failure=True` raises the real cause instead of `None`.
- `auto_patch/engine_v2.py` — `fresh_pack_dump` passes it, so the failure
  is raised AT the refresh: "KBFI: the scenery pack 'Global Airports'
  cannot be read — …+47-123.dsf could not be converted to text: … DSFTool
  --dsf2text crashed (SIGSEGV). Nothing was left in the cache; the next
  build tries again."
- `auto_patch_v2/airport/dsf.py` — `missing_dump_reason()`: empty dump /
  dumps of another version / no dump, in plain words.
- `auto_patch_v2/airport/load.py` — the refusal uses it; "newer than
  every cached text dump" is gone.

## 3. Found and not fixed

**The six airports still cannot build after this fix** — DSFTool cannot
dump that DSF. They now fail with the true cause and leave no litter.
Narrowed: removing the single header property `sim/overlay 1` from a copy
makes DSFTool dump it completely (86,731 lines, 722 object defs, 13,129
objects, 6,474 polygons, 20 network segments); no other property matters.
So the crash is in DSFTool's overlay-mode handling of this file's
commands, not in the header. Not root-caused further (closed binary,
debugger attach is refused on this machine). Needs its own issue.

Also: the wrapper's temp-file fallback has left ~60 `tmp*.dsf.text` files
in the system temp dir over time (now removed on failure, old ones not
cleaned).
