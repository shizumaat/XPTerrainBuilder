# seatspec notes — the pad SEAT under RULINGS 2026-10-09d (1) / 08c (4) / 08d (2) / 09c (2a): classes C, D, E, M, B of the pads67 edge read

Lane `seatspec` (Fable, SPEC AUTHOR with probes; no engine code lands). Worktree `.claude/worktrees/seatspec`, branch
`claude/seatspec` = `origin/claude/pads67` 9ab7b36e + `origin/main` f314564d (one conflict, `docs/frames.jsonl`, both sides kept).
Scratch `<scratch>/seatspec/` (`.progress`). Probes: replays of the registered pads67 captures
(`/Users/noah/XPTerrainBuilderData/.harness/frames/pads67/<ICAO>.pkl`, merged head 4b433195), `--workers 9` (valley2 holds the
other half). No airport build.

## Step 0 — orientation (what seats a pad today, read from the code before any probe)

* A pad that FRONTS AIRSIDE (`frontage_roles` = rolled-on roles) and is >= `cluster_pad_min_m2` is a HELD unit pad
  (`planar/platform.platform_split` -> `model.platform.HELD`): stage 1 solves its datum column as a FREE column with the hard
  weld rows (contact = D, `HOLD_RULING`), the hard flat rows (`platform_plane_rows`), the apron's hard caps, and ONE SOFT
  zero-width `Band` at `datum_chosen` = the median of the contacts' pass-1a value (`no_step.hold_interval`,
  `HOLD_DATUM_RULING`). The pair-graph interval and the reach-band intersection are REPORTS (`reach_band`, `reach_isect`); the
  Band on the reach intersection is stated only where it cuts the interval. 08d (2) widening (`weld_floor`) opens one over-cap
  grade on the closing contacts' faces for a misfit under 1 m.
* A pad that fronts ONLY groundside pavement (no platform record) is seated by `pads.pad_frontage_level` (10l): one one-way
  row on the pad's own mean against the groundside face's leaders — the PAD follows the lot/road; §28 mints nothing back
  (`pad_fronts_airside` is the switch). A pad that fronts nothing keeps its DEM datum (09p (3)).
* A gap piece never shares a vertex with a pad (`gap_mint` stand-off); its parts carry PAD STATIONS (`late_stage.late_stations`,
  class `pad`, knife = `groundside_cutback_m` + snap margin) and `gap_follow_rows` binds a part vertex within
  `cap x (d - knife)` of the station; the cut (`classify/gap_terrace.consistent`) groups stations within `cap x d +
  pad_terrace_floor_m` (1 m) and knifes otherwise.

Sidecar read (sw8_HECA): the class-E pads ARE held platforms on `apron:dsf:objpav402` (a standing apron, NOT a gap piece;
faces apron 344 v + junction 66 v + apron 12 v) whose solved `datum` stands far from `datum_chosen`:
building100 101.248 vs 101.242 (reach_band [None, None], 12 of 12 contacts UNREACHED), building101 93.394 vs 96.944
(band [85.73, 99.37]), building104 92.421 vs 94.889, building98 103.502 vs 103.649 (unreached), building64 86.369 vs 88.662,
building164 77.360 vs 78.036. `hard_conflict` pad 101 at HECA (main 27). The class-C pads (building12 / 15 / 8) have NO
platform record; building12 is cluster `unit:43#850` (30,172 m2, 16 bodies, pad_offset_spread 2.39).
