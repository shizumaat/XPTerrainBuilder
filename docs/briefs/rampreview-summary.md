# rampreview — review of the groundside road-ramp design grade AS BUILT (lane `roadramp484`, PR #487)

Fable 5.1, 2026-10-09. Reviewed: branch `claude/roadramp484` @ `2676e011` against main
`e2eec15c`; the lane's arms (`<scratch>/roadramp484/`: `avd_*`, `cen_*`, `probe_*`, `A/`, `B/`,
`cap/*.pkl`), the closing build `/tmp/harness/rr484_HECA.*`, the gap-lane frames
(`gapapron4/late_B.txt`, `swga_HECA*.osm`). Law: RULINGS 2026-10-07d, 08c (1), 08d (1),
09c (2b); spec §37 (6)/(6a), §34 (1a), §55. No engine code edited here. Reads this review
made (durable copies in `/Users/noah/XPTerrainBuilderData/.harness/frames/rampreview/`):
`firstmeet_probe.py` / `firstmeet_KCLT.txt` (the KCLT capture's ramp targets under three
semantics, no solve), `ground_probe.py` / `ground_KCLT.txt` (what ground each first-meet ramp
stands over), `rcs_diff.txt` + `rows_{A,B}_KCLT.json` (harness census `--rows-json` of both
KCLT arms, row-joined), `gap8_read.py` / `gap8_read.txt` (the gap:8/s0/lot rings across five
HECA patches), `node_read.py` (a node's ways and A/B alts). One replay arm (KCLT, `--site
35.21461,-80.93110 --solved-out`, 2 min) and one `--probe-site` off it.

The spec: §37 (6a) amended IN PLACE in the CANONICAL copy of the section — the FIRST
occurrence (spec lines ~7478–7600 at `2676e011`). The file carries §38–§41 (and with them
§37 (6)–(9)) TWICE; the second copy (from the second `## §38 THE TILE SEAM IS A PIN`, ~line
9733, to before `## §42`) is a STALE snapshot: it lacks §37 (10) round 2 "AIRSIDE IS KING —
ROUND 2" (commit `ed9af972`) that the first carries (`diff` of the two copies: 771 lines). It
now carries a one-line HTML marker at its head; it must be DELETED as its own docs-only
follow-up (F3 below). The implementer amended both copies' (6a); this review amended only
the canonical one.

## R1 — SEMANTICS: the persistent cone. REPLACE: a contact's cone ENDS AT ITS FIRST MEET with the road's floor (§34 (1a)'s rule); the intent beyond that is the owner's (Q1).

* As built: `road_descent.envelope` is a max-label walk over the WHOLE connected road graph
  with `target = max(floor, cone)`; a cone that met the floor re-emerges wherever the floor
  later falls faster than 5 %. KCLT `max reach` 594 m (main 540 m at 10 %): a road hundreds
  of metres from its contact was re-graded by it.
* Measured (KCLT capture, no solve, `firstmeet_KCLT.txt`): first-meet ramps 55 → 49; the six
  gone = two 148 / 144 m cones at 5 % that had met the floor at their own mouth and re-emerged
  (mouths 12195 / 12196), 12173 (140 m), 14249 (62 m), two 7–9 m stubs; ramp length 1,264 →
  755 m; longest 148 → 109 m; max reach 594 → 109 m; targets LOWERED at 15 vertices (worst
  0.76 m), raised at none. 49 of the 55 stay exactly as they are. The `_Shelf` twin is
  unchanged by first meet (its cone meets once, at 12 / design); the "safety net across route
  changes" the lane kept the persistent cone for is the floor beyond the meet (the clamp,
  cap-lawful by construction, 13be).
* What "only where needed" does NOT settle, and the owner must (Q1): of the 49 first-meet
  ramps, 40 stand over FOLLOWABLE ground at every governed vertex (`ground_KCLT.txt`: the
  floor IS the terrain there — a 5–10 % hillside the road could sit on at its own cap), 2
  over clamped ground only, 1 mixed; the longest (109 m) carries 1.28 m of fill over 6 %
  ground, the worst fill 1.98 m. Reading A ("comes down gently at 5 %") = the branch after
  F1/F2. Reading B ("only where needed" = a ramp is the earthwork where there is no ground to
  follow) = main's behaviour over followable ground, the 5 % ramp only off a fill or a
  clamped (steeper-than-cap) fall. I recommend B. Spec §37 (6a) (iv) carries both; the
  engine builds A until the owner answers.

## R2 — GRADE PER CONTACT. REPLACE: the grade is per RUN (contact → one end).

`_need` takes the max over every end the contact's graph reaches, so one stub end the cap
cannot serve puts the contact's whole cone at the cap in every direction: KCLT 14 of 55 and
HECA 5 of 44 "at the cap", every one named by "the road's end at 5–9 m" (just past the lane
width) while the same contact's other runs fitted at 5 % — e.g. KCLT mouth 14714, 15.9 m of
ramp at 10 % for an end 6 m away; HECA 11883, 27.3 m at 10 % for an end 8 m away. That is
the cap used as a target in the other direction. Rule: each run (the walk to one end — the
road's own end or the next contact) is built at its own least grade; the stub's branch is at
the cap and ends in the air as before; the contact's other runs stay at 5 %. Stage 2's
`_run_grade` is already per run (the bare exit and the reach seed are single runs); only
`road_descent` changes.

## R3 — NOT CHANGED, same class. (a) CORRECT AS IS + named follow-up; (b) CORRECT AS IS.

* (a) `gap_terrace._lot_cut` (§55, 06d): the strip is where `(L − A) > cap × d_apron` —
  sized at the cap. It is the CUT's feasibility test (the lot = where the road's level can
  still be held flat from the apron at the piece's cap), and the strip's SURFACE is then
  solved by follow rows under the piece's own 10 % cap (07d: drive aisles and ramps 10 %),
  not built to a grade. Cutting it at 5 % doubles every strip's width (halves the lot) and
  re-cuts the HECA pieces the owner has not yet read (#430 / #292 / #358; 08c (6) "the other
  pavement-gap questions wait for the owner's HECA read"). Correct as is for Beta 2. NAMED
  FOLLOW-UP after the owner's HECA read: where a piece's road evidence makes it a road
  (08c (6)) its strip is a road ramp and the cut width takes the design grade — classify-time,
  ~0.5 day, re-cuts HECA gap:7 / gap:8; acceptance = the owner's three sites quoted before
  and after, lot rows missed 0.
* (b) the floor's clamp (`cap_lipschitz_profile`, 13be) is built at the cap wherever the
  TERRAIN exceeds it: the cap acting as a cap — the terrain forces it; the core levels the same
  road at the same cap outside the coverage, and §37 (9)'s join reads that value, so a 5 %
  clamp inside the patch would re-grade every road the ramp never governs and step at the
  coverage edge. Correct as is; no follow-up.

## R4 — UNEXPLAINED NUMBERS, attributed.

* KCLT `road_cross_section` 767 → 800 (worst 2.23 → 2.29): row-joined (`rcs_diff.txt`), 53
  rows new, 20 gone, 747 common (21 grew > 0.05 m, 11 shrank). **35 of the 53 new rows are on
  ONE page, `dsf:pol48`**, pairs 47–48 m apart across the page (a wide service-road page on a
  4.5–4.8 % cross-slope against its 2.06 % transverse cap; the road itself is on its DEM,
  z − DEM −0.42..+0.24 within 12 m of the worst row). The rows grew because pol48's kerb at
  35.21455,−80.93100 came DOWN 0.6–0.8 m in the branch (nodes −20090..−20093, −21268/9:
  223.1 → 222.3) while the far kerb stood. A descent cone can only RAISE a target (the
  lane's own probe: pre-solve targets rose at 212 vertices, fell at 0); the ONLY site this
  branch lowers a road is the fourth one, the coverage-join cone of the terrace profile
  (`terrace_profile` anchors: `clip(target, z_join ± g × d)`, a TWO-SIDED clip, now at
  g = 5 % — KCLT log: "340 held inside a coverage join's reach"; the lane: "roads that come
  DOWN in the patch do so through the join cone (tighter at 5 %)"). `small_roads:-7031#7/#8`
  (down 0.65 / 0.59 m, OSM roads that leave the coverage) are the same. RULING: a DEFECT of
  that site, not of the per-contact cone — at the cap the join clip was a feasibility
  envelope (a road may not stand farther from its pin than its cap allows); at the design
  grade it is a grade the road is BUILT TO in both directions: a road climbing away from its
  join on lawful 6–8 % ground is cut to 5 %. The join is a PIN the road reaches within its
  cap; the bare exit's one-sided run (already at the design grade, its end level the pin)
  is the ramp. Fix F3: the join clip returns to the cap. Expected: pol48's 14 nodes and
  −7031's back within 0.02 m of main; `road_cross_section` 800 → ~767; NLWF byte-identical
  again (its 1 node at 0.03 m was this cone); HECA 492 → ~487. Verify on the KCLT capture
  replay, `cen` A/B `--rows-json`.
* KCLT `tunnel_ramp` −0.13 m at 35.20105481,−80.94033935: node −16259 is the 9th of 10
  vertices of ramp ring −10843 (`node_read.py`), shares no other way; in the branch it took
  EXACTLY its ring neighbour's value (208.01 = the next vertex, unchanged) with the other
  neighbour unchanged (209.63). `tunnel_ramp` is not a `road_cross_section` role, so §37 (6)
  owns no vertex of it; its rows are the ramp's one-way `Diff` bounds (§34 (3)) — a band, no
  equality — so the vertex's level inside the band is the solve's choice, and this is the
  non-uniqueness the same two nodes showed (0.04–0.06 m) under two unrelated changes this
  week. Accepted. The 0.02–0.03 m `tunnel_ramp` nodes welded to moved service roads (KCLT 5,
  HECA 13) are movement within grade law (08c (1)). STRUCTURE-FRAME BAR for a change MEANT to
  move roads: every structure node (tunnel_ramp, deck, wall) moved > 0.02 m is NAMED with
  the row that holds it; accepted where that row is a band and the ring's STATED levels (a
  mouth, a ramp top, a deck end, a wall crest) are within 0.02 m of the control; a stated
  level moved > 0.02 m, or any structure node > 0.10 m with an equality row, is a STOP.

## R5 — the recurring HECA defect, named: a LOT PART whose LOT ROWS are infeasible against its own rim relaxes them at arbitrary rim vertices.

`gap:8/s0/lot` (9,755 m², rings −12252 / −12255) runs 375 m along `service_road:route3`,
which climbs ~7.5 m along it (the knife `gap:8/s0/lot | gap:8/s1` is 7.52 m,
`gapapron4/late_B.txt`). Its rim vertices share NO other way (`gap8_read.txt`: every ring
vertex `shares []`) — they stand across the stand-off from route3 and carry (i) FOLLOW rows
to the nearest ring and (ii) the LOT rows of §55 (06d: the road's level as the lot's target,
flat across). Those lot rows cannot all hold on one part under one level: the §5a LP relaxes
FIVE of them — 5.04 / 4.36 / 2.37 / 1.47 / 1.30 m, ALL on gap:8/s0/lot (`late_B.txt` "LOT
rows 186 on 3 parts; missed by > 0.02 m: 5") — and WHICH rim vertex carries the miss is the
solve's choice: v43232 (30.11510995, 31.41089018) 101.80 on main beside route3's 104.22 and
104.17 in the ramp arm; v43189/−43190 (30.11414469, 31.40954132) 105.64 / 106.38 / 104.91
across three arms; −43222 (30.11535802, 31.41080197) 97.92 → 100.29. Not the road ramp's
cause (both arms carry the five misses; the ramp arm only moved them between vertices) — the
"gap:8 interleave residual" and the "rim vertices only" piece of §55 line 1 are this one
thing. GENERAL FIX (follow-up F4, classify-time, ~1 day): the 06d lot cut takes the ROAD's
stations as level groups too — a lot is the region where the road's level ALONG the lot is
one level within the lot's cross cap (04u's step cut applied along the road), so a lot
beside a road climbing 8.8 % is several lots with declared joints between them, each with
feasible lot rows. Acceptance: HECA late-stage "LOT rows missed > 0.02 m" 5 → 0; owner
sites #430 / #292 / #358 quoted before and after; no gap-part rim vertex moving > 0.5 m
between two arms that differ in something unrelated.

## FIX LIST for the implementer (each separately committable, on `claude/roadramp484`)

| # | what | size | acceptance |
|---|---|---|---|
| F1 | R1 first meet: `road_descent.envelope` takes the floors and propagates from no non-seed vertex whose label ≤ its floor; `_need` walks the same way (an end beyond the meet is not the run's); the report's `ramps` counts a ramp only with a vertex ≥ 0.02 m over its floor (today 1e-9: 14252's "58.7 m" has none). Twin: a cone that met the floor does not re-emerge over a later fall. | 0.5 day | KCLT capture probe (no solve, `firstmeet_probe.py` pattern): ramps 55 → 49, length 1,264 → 755 m, max reach 594 → 109 m, targets lowered 15 (worst 0.76 m), raised 0; HECA quoted; `_Shelf` twins green |
| F2 | R2 per-run grade in `road_descent`: per contact the design-grade cone (first meet); each END it does not reach gets its own branch at that run's least grade along the shortest-path tree to that end only; the envelope is the max. | 1 day | KCLT: "at the cap" 14 → only the stub branches (ramps whose EVERY run needs the cap: count quoted); ramp length at 10 % quoted; HECA 5 → quoted; `test_a_run_that_fits_only_at_7_3_percent` green |
| F3 | R4a: the coverage-join clip of `terrace_profile` (anchors) returns to the CAP (a pin's feasibility envelope); the bare exit keeps the design grade with the pin as its end level; `max_join_grade` report line goes. | 0.5 day | KCLT capture replay + `census --rows-json`: `road_cross_section` 800 → ≈ 767, pol48 / −7031 nodes within 0.02 m of main; NLWF byte-identical to main; HECA 492 → ≈ 487 |
| F3b | the stale second copy of §38–§41 (+ §37 (6)–(9)) deleted (docs only). | 10 min | `grep -c '^## §38 THE TILE SEAM'` = 1; the surviving copy carries "AIRSIDE IS KING — ROUND 2" |
| F4 | R5 follow-up (NOT this branch): the 06d lot cut along the road. | 1 day | above |
| F5 | R3a follow-up (NOT this branch, after the owner's HECA read): the strip's cut width at the design grade where the piece is a road by 08c (6). | 0.5 day | above |

After F1–F3 the closing build is HECA again (the owner's gap sites), with the KCLT census
pair quoted from the capture.

## OWNER QUESTIONS (true intent only)

* **Q1 — what ground may a 5 % road ramp stand over?** At KCLT, 40 of the 49 ramps the rule
  builds stand on a 5–10 % hillside the road could lawfully follow (the floor is the terrain
  there); the ramp puts the road on an embankment up to 1.98 m (109 m long at the worst
  site) where main had it on the ground. (A) yes, a road leaving an apron comes down at 5 %
  wherever its ground falls faster than that; (B) no, a ramp only where there is no ground to
  follow — the apron on fill, or ground steeper than the road's cap — and otherwise the road
  stays on its ground. RECOMMENDATION: B (an earthwork the orthophoto does not show, over
  ground a road could sit on, reads as a defect to a taxiing pilot; the owner's picture was
  of ramps off a fill). Under A the branch after F1–F3 is the rule; under B the implementer
  proposes the "cannot stand on its floor" test (§37 (6a) (iv)) against the KCLT bar.

## What this review did NOT do

No engine code; no HECA or KCLT build (one KCLT replay arm + one probe, both off the lane's
registered capture); no replay of F1/F3 (the first-meet and ground numbers are capture-level
target reads, not solved surfaces — the solved effect is the implementer's to quote); the
stale spec copy not deleted (F3b); frames.py takes captures / patches / graded / mesh only —
this review produced none, its reads are copied to the durable frames root above.
