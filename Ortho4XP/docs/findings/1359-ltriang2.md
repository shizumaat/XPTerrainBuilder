# #1359 lane ltriang2 — the terrain witness, first round

Spec: `docs/specs/multi-source-terrain-spec.md` (PR #1448; §8.1 holds the
measured bars). Rulings: 2026-10-26q, 26v, 26w, 26x, 26y, 26z, 27a.

## Attribution (KDIJ, the owner's site, #1358)

Both CIFP `RWY` records sit 594 m north-east of the runway the photo shows:
RW04's is mid-runway on plain centreline dashes, RW22's lies in a crop field
past the 22 end. The installed layout (apt.dat ends, displaced 0) and the
built texture (piano keys at both apt.dat ends) agree with each other and
not with CIFP. Main pinned RW04's CIFP height 593.5 m in and RW22 on the
CIFP line: the 22 end stood +0.55 m over the lidar, with a 1.7–1.96 m
`within_shape` cluster on the parallel taxiway beside it.

## The rule (26v, at the one derivation site)

`airport/runway_end_witness.witness_runway_ends`, called by `airport/load`
before `end_pins.verify`: per CIFP runway end, the layout's threshold
station, the record's (unclamped, so a record beyond the end reads
negative) and the imagery's (the first threshold-marking row less 6 m; the
stripes must run along the axis, so chevrons and digits do not read) vote
(`airport/witness_vote.decide`). A record that yields to both the layout
and the imagery, more than the 30 m join radius from the layout's
threshold, is dropped (position and height); the end carries
`PIN_OUTVOTED` and follows the lidar with no noise floor
(`constraints/runway_profile.end_pin_cases`; 26v "the end follows the
lidar" — the datum line it would otherwise keep inside 0.5 m is the apt.dat
header, no survey).

## Acceptance (closing build `ltriang2_kdij2`, body `d7a573cb8355`)

| site | before (main = the `--no-imagery` arm) | after |
|---|---|---|
| RWY 22 end vs lidar | +0.548 m | **−0.002 m** |
| RWY 04 end vs lidar | −0.082 m | **+0.008 m** |
| RW04 CIFP pin 593.5 m in | pinned | **gone** (both records dropped, loud lines) |
| census ADJUDICATED | 246 | **243** |

Same-tree A/B (`--capture --no-imagery` vs the witness on, replayed
`--from constraints --emit --verify`): the OFF arm reproduces lrwypin's
patch census exactly (3124 / 246). Rows: 21 new, 22 gone. Gone: the 22-end
cluster (`within_shape` primary_parallel|runway 1.69–1.96 m, four
`taxi_box`). **New: 15 rows in the pre-existing RWY 4 end cluster where the
parallel taxiway meets the runway end** (it already carries
`strip_transverse` 1.94 m and `within_shape` 1.6 m on main): the end rose
0.09 m to the lidar, the taxiway there 0.05 m, and 0.42–0.86 m
`airside_no_step` / `taxi_box` rows crossed their thresholds. So the bar
"zero new adjudicated violations" is NOT met to the row: the net is −3 and
the new rows sit in a cluster that is defective before the change.
