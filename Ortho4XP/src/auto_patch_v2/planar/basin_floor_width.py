"""A PIT NEEDS A FLOOR YOU COULD STAND ON — a below-grade region whose
witnessed floor plates are all narrower than ``footprint_close_m`` is a
WALL'S FOOTING, never a pit (issues #1950 / #1952, KMCI).

04i rule 1 admits a region when one of its components carries
near-horizontal solid faces ``admission_depth_m`` under the local ground.
It never asks how WIDE that plate is.  A retaining wall modelled down to
its foundation carries exactly such faces: the underside of its footing,
a strip as wide as the wall, running the wall's whole length.  KMCI's
border wall (``Airport/Border/KCMO-Trimsheet-16.obj``, the pack's shared
datum) is one: 868 m2 of plate at y -12.2 / -14.0 along ~750 m — about a
metre wide — so the region pass took the wall's own plan as a pit and cut
a slot 13-20 m deep along it (the drawn mesh read 281.9-290 m beside a
wall whose visible foot stands at 296.5 m, #1952), its south-west end left
as a 39 m2 hole (#1950).

THE RULE.  A region is refused as a FOOTING when none of its MEMBER
witnesses holds a floor — the part of its plate at least
``footprint_close_m`` wide (the plate opened by half of it, the scale the
region itself is closed at) is under ``bank_band_plate_min`` of that plate
(the share §47 (3) AMENDED uses for "the floor inside still keeps this
share of the witnessed plate") — AND its narrow plate runs as long as a
wall: ``[service] retaining_wall_min_length_m`` (the wall-class
classifier's own length, ``airport/wall_class``) or more along its
minimum rotated rectangle.  A footing strip keeps a few corner slivers
(KMCI: 22 m2 of 868, 2.6 %, ~750 m long); a pit's floor keeps nearly all of
it (LEMD85 100 %, VHHH ``sea.obj`` 93 %, the sea-barrier wells 71-95 %).
A SHORT narrow well is still a pit: RULINGS 2026-10-10h (2) rules the band
of a well narrower than two bands (OTHH's jetway rotunda wells; twin
``test_basins526``'s 1.6 x 10 m cup), so width alone never refuses.

The test is read on the REGION, not per witness: a narrow plate inside a
region a floor admits still witnesses depth there (§24 (7) (a)'s rule for
buried plates), so LEMD's T4S pit keeps every member it had.  It refuses
BASINS only; ``PlacedObject.witnesses`` is unchanged for every other
reader.  No new law number."""
from __future__ import annotations

import typing as _t

__all__ = ["floor_share", "footing_refusal"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def floor_share(plate, width_m: float) -> float:
    """The share of ``plate``'s area at least ``width_m`` wide (the plate
    opened by ``width_m / 2``); 0 for an empty plate."""
    area = float(getattr(plate, "area", 0.0) or 0.0)
    if area <= 0.0:
        return 0.0
    r = width_m / 2.0
    return float(plate.buffer(-r, **_MITRE).buffer(r, **_MITRE).area) / area


def _plate_length(plate) -> float:
    """The long side of ``plate``'s minimum rotated rectangle; 0 when empty."""
    if plate is None or plate.is_empty:
        return 0.0
    r = plate.minimum_rotated_rectangle
    xy = list(getattr(r, "exterior", r).coords)
    if len(xy) < 3:
        return 0.0
    return max(((xy[i + 1][0] - xy[i][0]) ** 2 + (xy[i + 1][1] - xy[i][1]) ** 2) ** 0.5
               for i in range(len(xy) - 1))


def footing_refusal(bid: str, ring_area_m2: float, wits: _t.Sequence, width_m: float,
                    share_min: float, wall_min_length_m: float, site: str,
                    names: _t.Sequence[str] = ()) -> str | None:
    """``None`` when one of ``wits`` (the region's member witnesses) holds
    a floor, or when no narrow plate among them runs ``wall_min_length_m``
    (a short narrow well is a pit, module doc); else the refusal line,
    naming the longest narrow plate."""
    shares = [floor_share(w.plate, width_m) for w in wits]
    if not shares or max(shares) >= share_min:
        return None
    lengths = [_plate_length(w.plate) for w in wits]
    i = max(range(len(lengths)), key=lengths.__getitem__)
    if lengths[i] < wall_min_length_m:
        return None
    w = wits[i]
    who = names[i] if i < len(names) else f"#{w.comp_index}"
    return (f"{bid}: {ring_area_m2:.0f} m2 — no member's floor plate is a floor: {who} keeps "
            f"{shares[i]:.1%} of its {w.plate_area_m2:.0f} m2 plate at footprint_close_m "
            f"{width_m:g} m wide (< bank_band_plate_min {share_min:.0%}) over {lengths[i]:.0f} m "
            f"(>= retaining_wall_min_length_m {wall_min_length_m:g}) — a WALL'S FOOTING, never a "
            f"pit (#1950/#1952) at {site}")
