# LEMD basin trench extension under the ramp (owner sim read 2026-08-28)

Owner read of app 1.0.264 (LEMD big pit): "rim of the pit and elevation are
all perfect now, just the terrain is poking through the ramp at
40.4923132,-3.5697896 — extend the trench/pit bottom under the ramp to about
40.4924064,-3.569366."

## Current geometry (owner patch `+40-010/+40-004/LEMD_auto.patch.osm`, 07:09)

- `object_basin_trench` floor way -11774 (shapeID 1775), 587.75 m, ends
  ~1.2 m from the first coordinate.
- `object_basin_rim` ways -11776/-11777/-11775/-11783 at 600.51 m.
- The target point sits ~11 m outside the floor polygon; between the floor
  edge and the target the mesh stands at rim/DEM height and pokes through
  the authored ramp object descending into the pit.
- Distance to cover: ~29 m ESE from the current floor edge, under the ramp
  span, through 40.4924064,-3.569366.

## Law

Extend the basin trench FLOOR region (the founding-geometry derivation, not
a hand-edit of the emitted patch) so the floor pan covers the ramp's span
through the target coordinate. The extension keeps floor value 587.75 (or
the ramp's underside profile if the founding machinery already carries one —
do not invent a slope). Rim, walls, and the committed basin arc invariants
(founding c446edba, group seat 690d0568, the ONE G=596.682 relationship at
0.000000 m — see memory lemd-aerosoft-patch-ground-truth) are untouched;
any change to them is a STOP, not a side effect.

## AMENDMENT 1 (Fable, 2026-08-28, on lane/lemdtrench's STOP report)

The lane proved region-completion is the WRONG LEVER: the facility ring is
the single measurement body (floor value, rim value, pad coverage, R_mesh
group-seat band all read from it), so growing it moved floor 587.75→588.69,
rim 600.51→600.47, un-flattened the building8 pad, and drifted G
596.682→597.492 — and the widened pan was differenced away by earlier-born
shapes regardless (probes 5.14/2.51 m, worse than control). That machinery
stays committed DEFAULT-OFF (retired-kept-gated; its ledger is the evidence).

RULED design:
1. The ADMITTED region/ring is untouched. All committed reads stand.
2. The fix is at EMIT: a RAMP-REACH FLOOR PLATE — a corridor polygon from
   the current floor edge through the owner's target point (width bounded
   by the ramp span it serves), emitted as `tunnel_trench` floor at the
   region's floor value (587.75), with the `object_basin_rim` band
   STANDING DOWN inside the corridor only (differenced there, untouched
   elsewhere). The plate must survive differencing: it is born senior to
   the rim band within its corridor; it must NOT reach the apron or the
   building8 pad (the target sits 4 m short of both — clip defensively).
3. Instrument protection: the G=596.682 acceptance is re-read on the
   admitted ring exactly as committed; if the corridor plate falls inside
   R_mesh's sample band, the re-read excludes the plate (sample the
   pre-plate surface). If the instrument cannot exclude it, STOP and
   report — do not re-baseline G.

## AMENDMENT 2 (Fable, 2026-08-28, on the lane's second STOP — round closes UNSHIPPED)

Arm 2 (emit-time plate) is geometrically MET (both probes inside the pan,
floor 587.75, HECA/SPJC byte-identical, shipped LEMD default = control) but
REFUSED for shipping: building8's pad goes non-flat ([587.75,600.49]) and
census +196 airside `within_shape` rows — because BOTH owner coordinates lie
INSIDE the building8 pad ring (9.87 m / 3.88 m, containment-measured). The
ground under the ramp BELONGS to the pad's flattening authority
(`BASIN_PAD_FLOOR_SEAT` yields only OUTSIDE the facility); that authority,
not the trench footprint, is what holds it at 600.51 through the ramp.

RULED: both trench-side levers are exhausted and stay committed DEFAULT-OFF
(one shared derivation, `_ramp_lobes_of` batter/ramp separation retained —
the batter annulus is never emitted). The NEXT ROUND's lever is the PAD
AUTHORITY BOUNDARY: carve the ramp corridor out of building8's flattening
authority so the floor plate can own it, with (a) the pad edge along the
corridor treated as a declared wall/terrace, and (b) a G-instrument ruling
(8 of 70 R_mesh stations fall in the corridor; pre-plate read reproduces
596.680, dropping them reads 596.000 — a real rebake moves G either way).
PENDING OWNER: confirm the pad carve is wanted given it edits the committed
basin founding's authority map. The stale-sidecar cache fix (v26) and the
24 twins SHIP with the lane merge regardless.

## Acceptance (amended)

- Both owner probes at 0.00 m ON THE EMITTED FLOOR PLATE.
- Floor value stays 587.75; rim stays 600.51 outside the corridor;
  building8 pad stays flat at 600.51.
- G acceptance reproduces the committed value (with plate excluded per §3).
- LEMD census not worsened; the region-arm's artifact classes
  (within_shape +18, terrace_joint_route 11.777 m) must NOT appear.
- Controls (HECA byte-identical; SPJC byte-identical) hold.

## Original acceptance (superseded by Amendment 1)

- Rebuilt LEMD patch: floor polygon covers a probe at 40.4924064,-3.569366;
  `osm_site.py --at` shows `object_basin_trench` at 0 m from both owner
  coordinates.
- The basin relationship invariant unchanged (byte-diff the basin sidecar
  rows / re-run the arc's own check).
- LEMD census not worsened; controls (HECA/OTHH arms) untouched.
