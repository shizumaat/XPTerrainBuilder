# #1201 — KSEA runway-end retaining walls capping the RSA (lane lwalls): SCOPING, no fix

Owner (issue #1201, 2026-10-21 14:57Z): the runway-end retaining walls "are
built to cap the runway end safety area with a road running by their foot,
and their top should be flush with the runway safety area terrain. They
should be recognized by shape, position, and surrounding features so they're
seated correctly and the terrain is graded to match them."

## What the geometry shows (dry, registered KSEA capture `jetbay612/KSEA.pkl`, main a11299a48)

* The wall classifier (`airport/wall_class`) does NOT see them. Over the
  runway-end windows (400 m beyond each end, 200 m either side of the
  axis) its only components are thin 4–8 m parts of `…KSEA_KJ_01.obj`
  roughly 220–245 m off the 16C/34C and 16R/34L axes, none retaining.
* What stands beyond the north ends are large multi-part terrain objects:
  `91fd33a8…-KSEA_KJ_01.obj` beyond 16C (unit:33 in the rebake plan; base
  profile `stepped`, feet down to y −43.5 m, a deck CANDIDATE), and
  `KSEA_RWY16R_APP-KSEA_KJ_02.obj` beyond 16R (unit:32; 208 parts, feet
  down to y −55.5 m, "plate: 5,363 m² of near-horizontal face ... deck top
  y −9.819, 45.65 m above the family's lowest feet", a deck CANDIDATE with
  "no spanning evidence"). `c046e846…-KSEA_KJ_01.obj` beyond 16L has 16
  parts to 5 m, base to −7.8 m.
* So the pack authors the RSA cap as a PLATE over a tall walled structure,
  not as a slender wall: the slender-wall witness of #715/#1197 cannot
  recognise it, and the deck reader holds it as an unproven candidate.

## Why no code here

The fix is a new recognition rule (a walled plate beyond a runway end whose
top meets the RSA, with a road at its foot) plus a seat rule (top flush with
the RSA terrain) plus the terrain law that grades the RSA to that top. That
is a spec at the object-placement level (the seat of a deck candidate and
the RSA's relation to it), and the consumer census (RULINGS 2026-08-30l)
of the RSA, the deck and the seat readers comes first. Recommended: a spec
lane (high effort) on a fresh KSEA capture; then the implementation round.

## For the owner, in the sim

North end of runway 16C and of 16R at KSEA: the retaining structure capping
the end safety area, and the road along its foot (north of the 16C and 16R
thresholds). Say whether its top meets the safety-area ground and whether
the ground in front of the threshold is flat to it.
