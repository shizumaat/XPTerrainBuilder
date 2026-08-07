# XPTerrainBuilder 1.0.221 — test build, 2026-08-07

App 1.0.221 · frozen engine 1.50.1666 (self-contained, arm64) · Mac only,
no tag, no CI. Built under the 2026-08-07 owner ruling: the 08-06
"HECA airside < 100" gate is superseded for this build — ship the test
app now with the remainder named. This is a TEST build, not acceptance;
the campaign goal (five-airport zero-adjudicated law compliance) is
unchanged.

Tiles are NOT bundled and are not part of any release (owner directive
2026-08-07: the owner builds tiles in-app).

## Honest known-remaining

Frames are labelled; do not mix them.

- **HECA adjudicated airside 3,734** (−500 world) / **4,006** (canyon) —
  retrospective frame, tip `13d7ef1` + lane/c9air, 2026-08-07 00:30.
  The mechanism ladder proves this is structural, not tuning:
  convergence contributes ~2%, and with every box/interval removed the
  law itself is satisfiable (742 over-cap, worst 0.08 m).
- **Battery 15,530 adjudicated** across both flat worlds, airside
  10,718 — post-c8fin frame. Plus **12,320 deferred** drainage_minimum
  rows (version-deferred; generation work, scoped with the relief
  round).
- All eight flat-world builds succeed; every solve still exits with
  over_cap > 0 (no certified exit yet).

### The four remaining defect structures (each needs a designed round)

1. **Pad-frontage chords, ~1,870 rows** — pads seat lawfully from the
   band, but the frontage chord between a seated pad and its apron is
   not yet priced. Long chords (≥ 50 m) are relief work; short chords
   (< 10 m) are step/wall work. Spec round ratified first in line.
2. **Relief generation incomplete, 1,368 rows even at a blanket 5%
   cap** — no cap change reaches zero; the generator must create more
   relief coverage. Scoped with the deferred drainage project.
3. **Feature-weld hardening, 2,045 both-hard edges** — hard-node set
   grows 1,120 → 9,527 between the final projections; an over-cap edge
   between two frozen ends is unfixable by any projection. Upstream
   round.
4. **On-DEM airside stranding, 89 rows / 140 vertices** — owner
   adjudication pending; coupling-classified evidence dossier in
   progress.

Groundside ships named (08-06 ruling): the groundside mass is the D′
DEM-stranded ring class; the cycle-9 road-feed round that dissolves it
is parked pending a clean probe (cycle 10).

## What to expect in the sim

Graded surfaces are law-shaped but not law-clean: expect visible
artifacts at pad/apron frontages (up to ~7.4 m seat-to-apron steps at
HECA), at undeclared-relief apron interiors, and at graded/DEM
boundaries where groundside rings sit on raw DEM. Seam tears: +15 vs
the pre-flip baseline, ruled accepted 2026-08-04.

## Practical notes

- First launch of this bundle may re-prompt for volume access (new code
  identity). If an engine process sits at 0% CPU, that is the pending-
  TCC signature: run `scripts/unstick_tcc.sh`.
- Building the app requires `DEVELOPER_DIR=/Applications/Xcode-beta.app`
  — the CLT toolchain on macOS 27 beta no longer ships the SwiftUI
  macro plugin.
