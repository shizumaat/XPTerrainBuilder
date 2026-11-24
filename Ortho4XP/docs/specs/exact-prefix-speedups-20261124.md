# Exact prefix speedups (#2206; replaces the withdrawn one-map spec)

Fable two-round-cap review, 2026-11-24, of the lonemap and lfast3b rounds. Read-only at 3a12d1d09.
Tags: [M] measured, [C] read from code, [E] estimate. Paths are under `Ortho4XP/src/auto_patch_v2/`.

## Why the one-map spec is withdrawn

No design that deletes the late derive meets 23e. The KBUF null control repeated the control
byte-for-byte (law-true 2,009 = 2,009, adjudicated 537 = 537), so every difference below is real.

- One map, KBUF: adjudicated 537 to 540. Standing pads re-noded by a late cell solve differently
  (42.9343, -78.7315: pad edge 0.49 to 0.65 m; 42.9396, -78.7422: two new cross-fall rows).
- Predicted knives: predicted pad levels miss the solve by up to 9.4 m (KATL), 6.8 m (KRDU), 5.4 m
  (KASE). KATL `gap:1/lot` keeps 12 m of relief without its knife; KRDU's partition is wrong.
- Ring cut with ties, KRDU: 36 real adjudicated rows, since 19 more knives are 19 more steps.
- The late derive is smaller than assumed: KATL 270.5 s warm (not 650 s); 6.9 % of 21 builds on this
  branch; 9.7 % of 101 ledger builds. Deleting it moves the ledger from 86 to 87 of 101 under 300 s.

## Ranked work on this branch (21 builds, partly warm)

| Item | Seconds | Share | Exact? |
|---|---|---|---|
| Stage-1 solve passes (3-5 per build) | 414 | 11.4 % | Not here; skipping two refused 11-21 |
| One prefix run's planar 734 + constraints 219, paid again in the late derive and stage-1 worker | 953 | 26.2 % | Yes: Step 4 |
| Late derive | 251 | 6.9 % | About 28 % of it at KATL: Steps 1-2 |
| Classify 547 + partition 228 | 775 | 21.3 % | Other lanes |
| Waiting on the stage-1 worker | 90 | 2.5 % | Yes: Step 3 |
| Stage-2 shadow solve (KPHX) | 39 | 1.1 % | No |

Defect found [C]: the arrangement front memo has probably served no late derive since stage 1 moved to
a worker. The main pass holds its front under the airport object (`planar/overlay.py:331-334, 550`);
`run_prefix` replaces that object for the flat-site verdict (`pipeline/prefix.py:340`); the late derive
presents the new one (`pipeline/stage_one_ahead.py:265-278`, `pipeline/build.py:746-753`); `served`
compares by identity and misses (`planar/arrangement_memo.py:73-82`). The front is 77 of 410 profiled s
at KATL.

## Steps (one commit each; every step leaves the patch body identical)

- **Step 0, clocks.** Clock `_channels` (`pipeline/prefix.py:363-367`), `hold_pass` (431) and the
  classification digest (479). Record each arrangement-memo call's outcome (served, computed, value key
  held under another airport). Publish both in `prefix_clocks` (`pipeline/build.py:1014-1018`).
  Acceptance: each run's steps sum to within 2 s of its wall.
- **Step 1, serve the main front to the late derive.** In `planar/arrangement_memo.py:73-96`, hold the
  airport's fields other than `flat_site` with its `ground_class` and compare field by field (the test
  `rebind` applies, `stage_one_ahead.py:271-277`). Kill test: a headless twin runs `build_arrangement`
  twice under `scoped`, the second with `dataclasses.replace(airport, flat_site=...)`, and is served with
  equal output. Promote the scratch `warmprof.py` into `tools/v2_solve_replay.py` as an arm deriving base
  then late in one process under `scoped`; on KBUF the late map digest is equal with the memo on and
  off. If Step 0 shows the value key differs at most airports, delete the memo instead
  (`planar/arrangement_memo.py`, `overlay.py:330-334, 550-556`, the decorator at `build.py:494`).
  Expected: about 19 % of a late derive [E]; HECA about 40 s.
- **Step 2, one crossing decision per build.** Targets `planar/build.py:415-418`,
  `planar/deck_takeover.py:952`, `planar/deck_pack_cover.py:107` (`_cover_plan`, 109 calls of 0.33 s at
  KATL). Write the consumer census of what `decide_crossings` reads of the classification first, then
  memoise at the lowest pure function on the build scope. Kill test on KATL and KRDU: served equals
  recomputed.
- **Step 3, the stage-1 worker is ready before classify ends.** `pipeline/derive_ahead.py:108-126`,
  `airport/pool.py:443-473`, `pipeline/build.py:516, 674-676`: start the worker and import the prefix
  at the start of `build`; hand the payload at classify's end. Keep `may_start` and close on every exit.
  Kill test: KBQR, KOLE, KLXV `waited_s` under 1 s (now 4.5, 4.4, 6.7) with equal bodies.
- **Step 4, hot loops in profile order.** Profile the main pass on KBUF and CYYZ first and drop targets
  under 2 %. KATL late-derive profile (nested): `constraints/zones.py:162 _nearest_edge` 45.0 s,
  `planar/low_level.py:96 unit_share` 39.0 s, `constraints/stretches.py:346 _best` 21.1 s,
  `airport/road_profile.py:383 answer` 19.6 s, `airport/dem_production.py:754 z_many` 16.8 s. Cut call
  counts by pre-selecting candidates; never replace `geom/exact.py` arithmetic (Linux and Windows bodies
  must agree).

## Verification

Per commit: `tools/v2_solve_replay.py --replay <capture> --from classify --emit DIR` on both arms;
compare the sha of `<ICAO>_auto.patch.osm` and `<ICAO>.graded.json`. Captures: KBUF, KRDU
(`frames/lkrdue2`); KATL, KDFW (`frames/lfast1`); KDEN (`frames/lkden`); HECA (`frames/lb8fix`); CYXY
needs a fresh capture. A mismatch reverts the commit; two fix attempts per step. Timing claims use
`--runs 3`. The integration builds each touched airport once (17r) with no MOVED in the drawn gate.

Expected [E]: Steps 1-2 take about 76 s off KATL's 270 s; Step 4 about 15 % off every prefix run if the
named loops halve; about 8 % of fleet build time together.

## Not verified

No build ran for this spec. The front-memo miss is read from code (Step 0 confirms or kills it).
Savings come from one loaded KATL replay profile. The main pass was not profiled. KATL, KDFW, KRDU,
KDEN and CYXY have no build on this branch.
