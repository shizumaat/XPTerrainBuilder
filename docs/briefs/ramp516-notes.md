# ramp516 — issue #516, the ramp end that sinks into the ground

Branch `claude/ramp516` off main 87683f880. Master's reading (2026-10-13 night,
pending the owner): RULINGS 2026-09-13bi ("sink into the ground so its ramp
meets DEM") and 13cm ("the top deck meeting the sloping terrain at the ramp
ends") give OUTCOME (1); 10-03e (landings, graded up) covers fill only.

## Mechanism (sw24_SPJC = main bd950d682)
* The ramp is `SPJC_LIMANUEVA_xp11_007.obj` (unit:1, not deck-classified), its
  deck at y 0.2 rising 5.6 % NNW from the owner's site; its walls run 8.76 m
  under its zero. Its whole footprint was in cluster pad `building5` (19.09):
  an 8 m finger cut 3.9 m into DEM 23.0 under the ramp end. sw23 (1.0.385
  era): road `-5709` at DEM fell a 4.1 m step into it; sw24 (#631): it ramps
  at 6.3 % into a trench with 3.3–3.9 m DEM walls each side.
* Cutter: the object's footprint inside the unit pad (flat claim). Not a deck
  datum, wall corridor or terrace.

## The rule (`airport/sunken_ramp.py`)
Inside a pad-minting cluster's outline: raster 2 m; D = DEM median over the
outline; G = DEM; T = the member's top surface. Candidate ground G > D + 0.5
(`[cockpit] visual_m`). A 4-way component of T-continuous cells (step ≤ 12 %
of the cell: one road deck; a wall, roof edge or roof pitch breaks it) is a
SUNKEN RAMP iff it is under the ground somewhere (D+T < G−0.5, T ≥ −0.5), over
it elsewhere (D+T > G+0.5), comes down to its own zero (min T ≤ 0.5) and
climbs ≥ 1 m. Its cells, widened 2 cells to the deck's walls, clipped to the
member's part rings and the candidate ground, leave the pad like a welded
deck's shade. Parse gate: only members with a part under their own zero over
the candidate ground (the pack authors such a ramp to sink).
Law: `[placement] sunken_ramp_grid_m 2.0` (0 disarms), `sunken_ramp_climb_min_m
1.0`, `sunken_ramp_step_grade 0.12`.

## Consumer census (before editing; one derivation site)
| reader | reads | ruled |
|---|---|---|
| `classify/evidence._cluster_pads` (pad MINT) | cluster outline − shades | + `Airport.sunken_ramps` via `geom.with_shade` |
| `classify/evidence._pads` fallback footprints | − deck shades | + same (a v1 footprint never re-pads the ramp) |
| `constraints/cluster_pad.cluster_polys` (mismatch census, cluster faces, plane groups) | outline − shades | + same value (constraints may not import airport: it travels on the Airport) |
| pad roads (`ribbon_mint`, `pad_road_exit`, `pad_ramp`, `pad_road_reach` — crossfall609's) | emitted pads | untouched: they see no pad there |
| `planar/landing` | deck members only | untouched (007 is not a deck) |
| `planar/platform` block datum | pad rim contacts | untouched; MEASURED +4 welded contacts → building5 19.089 → 19.116 |
| object stage (`footprint_unit` seat on the pad) | pad level | untouched; follows the pad (+0.03) |
| tools `pad_gap_diff.py`, `pack_stage_profile.py` | cluster_outlines with deck shades only | NOT updated (measurement tools; they will not show the trim) |

Attached at load beside the clusters (`pipeline/build`, `v2_solve_replay`
capture + backfill for older captures).

## Measured (closing `ramp516b_SPJC`, body cebe261f2b20 = `ramp516_SPJC`)
See the PR body. Dry read on fresh captures at 87683f880: HECA 0, OTHH 0,
KCLT 0, KASE 0 (KASE FireStation_7 refused by the 12 % deck bound; at 25 % it
was taken), CYXY 0, NLWF 0 (Oct-9 captures). Cost: SPJC 0.5 s, HECA 4.1 s.
