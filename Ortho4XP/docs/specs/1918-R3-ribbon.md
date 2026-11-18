# #1918 R3: a kerb vertex has its opposite (abeam stations) — LGAV way -886 step

Fable review of l1918b item (b), 2026-11-16. One fresh Opus round, effort medium.

## 1. Mechanism (measured; owner DSF app 1.0.529 + frames/l1918b/LGAV_auto.patch.osm)
The 70.07 m drawn vertex at 37.9273613,23.9342527 is NOT a road-ribbon vertex and R18-1c is not
involved: it is a mesher-inserted vertex on the PATCH's own ring edge of small_roads:-886
(O4_Mesh_Utils.patch_segment_split_values :1088, called :2296-2317 — "mesher-inserted vertex(es)
lie on a patch ring segment and take the ring's value"); it matches the ring's linear value to
2-5 mm. Way -10543 (small_roads:-886) has one edge -12373 -> -12374 (z 69.68 -> 70.46, 30.76 m, no
intermediate node), shared with -10846 (small_roads:-2100). The same ring carries building24's pad
tip (flat 71.11) at -7764 / -7752 and -12379/-12378/-12377 (71.04-71.06), standing 0.42-1.28 m
from that edge: steps +0.73..+1.02 across the road. constraints/roads.py:286 road_within_shape
prices vertex<->vertex ring pairs only; a vertex facing a chord with no opposite vertex has no row.
Class scan (upper bounds; steps > 0.5 m): HECA 191, LGAV 84, KCLT 63, KBNA 47, CYYZ 28, EGLL 22,
OTHH 19, KIAH 18, LOWS 15, KLAX 15, KDEN 11, LPPI 4, ENTC 0. Scan script:
scratchpad/necks4.py (centreline read cl.py).

## 2. Rule — abeam stations (general; no airport, way or pad test; no mesher change)
Where: planar/overlay.py _ring_lines_of (:560-572), after ring_lines, the #2070 ground(ring) and
densify_within; same gate as #2070: r.role in ROAD_ROLES and r.ref not in stated.
What: a pure function in planar/chords.py (already in the three pipeline/stage_code.py lists),
e.g. abeam_stations(ring, within_m, min_gap_m, keep_off=None). For each ring vertex v and each
chord (a, b) of the same ring not incident to v, add the foot of the perpendicular from v when:
 1. min_distinct_spacing_m (0.5) <= d <= [road_contact] pair_lateral_m (6.0);
 2. the foot is >= min_distinct_spacing_m from both chord ends, every ring vertex and every
    station already minted (nearest wins);
 3. the segment v -> foot lies inside the ring's polygon;
 4. the foot is not within snap_margin_m of a contact or rigid polygon (reuse the STRtree / mouth
    test road_ground_densifier builds, extended to the rigid/pad rim).
One pass: feet from the ring's original vertices only. No new law key, no new row family:
road_within_shape prices (v, station); road_pair_side makes it one-way when v is airside;
planar/pad_cut._drop_rim_midpoints (:331) drops a point on the frozen rim.
Twin beside tests/auto_patch_v2/test_ground_chords2070.py: pad corner 1.3 m from a 30 m chord
gains one station; two feet < 0.5 m apart give one; foot outside the polygon gives none; foot on
a contact rim gives none; a ring with opposite vertices gains nothing.

## 3. Consumer census (first four rows read; rest from grep — verify)
| Consumer | Ruling |
|---|---|
| planar/ribbons._ribbons_pass_c noding + rim guard (:95-122) | unchanged; bar: ribbon_rim_mints_notched/left, renode_minted/deleted equal base |
| planar/pad_cut._drop_rim_midpoints | unchanged; drops stations on airside/pad rim |
| constraints/roads.road_within_shape | unchanged; now prices the neck; rows O(n) per ring |
| pipeline/stage_one_map.late_constraints | unchanged |
| constraints/road_ramp, pad_ramp, pad_road_reach, ceiling | unchanged; RISK ramp ceiling vs cross-section at a station beside a pad (stop 1) |
| airport/road_ramp.road_route_frame, contiguity.road_station_caps, public_road_release, emit/road_join | unchanged; one more vertex |
| verify/roads, verify/census | counts may move; report per family |
| emit/osm_adapter + sidecars | more nodes |
| O4_Vector_Map.include_patches, O4_Mesh_Utils.patch_segment_split_values | unchanged |
| structure/deck/wall readers of ROAD_ROLES | stated refs excluded; replay bar: structure face counts/areas identical |

## 4. Pre-registered (LGAV closing build --pack-copy; reasoned, not replayed)
Patch gains nodes on edge -12373 -> -12374 at the feet of -7764 (37.9273662,23.9342434), -7752
(37.9273793,23.9342204), -12378, -12377 (-12379's foot within 0.5 m of another: not minted); each
station within 0.02 m of its vertex (71.04-71.13; today 70.09-70.33). Drawn at 37.927340,23.934230:
70.95-71.11 (today 70.49). drawn_gate LGAV --site issue=37.927345,23.934221: -886 max step <= 0.2
(predicted 0.08-0.15; today 0.62); site sw stays PASS. Side effect to report: -2100's west kerb
rises ~0.6-1.0 m over ~9 m abeam the pad; -2100 centreline step <= 0.2.

## 5. Gates
1 Replays synthetic-first: v2_solve_replay.py --capture then --replay --from planar, base vs
  branch, on LGAV, HECA, KCLT, LOWS.
2 Airside: no airside vertex minted, deleted or moved (≤ 0.005 m); renode counts equal.
3 Solve converged; hard_max_violation_m no worse; hard_conflict rows only at minted stations, named.
4 Vertices moved > 0.05 m all within 60 m of a minted station.
5 Structures: face counts and areas identical.
6 Census adjudicated count does not rise per airport; report road_cross_section delta.
7 mesh_region_tris.py --hairline-audit: no new node_pairs / short_segments.
8 Closing: ONE LGAV tile build, drawn_gate --against frames/l1918b/l1918b.drawn.json; MOVED only
  within 60 m of a station, each listed.
9 KEGE and BIKF (certified): report station counts; any station there → master decides a re-read.

## 6. Stop rules
1 Replayed station at -7764's foot solves below 70.90 → stop, report --why-at rows; no second
  mechanism.
2 Any airside vertex moves or rim mint counts change → stop.
3 Any airport fails to converge, or > 20 new hard-conflict rows on any airport → stop.
4 In-bbox triangle count rises > 5 % on any airport → report before the build.
5 No z-dependent minting, no airport/way/pad-specific test, no mesher change.
Also correct the frame registry note for l1918b: the 70.07 vertex is the patch ring's own edge.
