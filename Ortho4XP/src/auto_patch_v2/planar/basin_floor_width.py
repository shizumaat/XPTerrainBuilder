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

THE RULE.  A region is admitted only when at least one of its MEMBER
witnesses holds a floor: the part of its plate at least
``footprint_close_m`` wide (the plate opened by half of it — the scale the
region itself is closed at, below which the region model resolves no
floor) is ``bank_band_plate_min`` or more of that plate (the share §47 (3)
AMENDED already uses for "the floor inside still keeps this share of the
witnessed plate").  A footing strip keeps a few corner slivers (KMCI:
22 m2 of 868, 2.6 %); a pit's floor keeps nearly all of it (LEMD85
100 %, VHHH ``sea.obj`` 93 %, the sea-barrier wells 71-95 %).

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


def footing_refusal(bid: str, ring_area_m2: float, wits: _t.Sequence, width_m: float,
                    share_min: float, site: str, names: _t.Sequence[str] = ()) -> str | None:
    """``None`` when one of ``wits`` (the region's member witnesses) holds
    a floor (module doc); else the refusal line, naming the widest
    reading."""
    shares = [floor_share(w.plate, width_m) for w in wits]
    if not shares or max(shares) >= share_min:
        return None
    i = max(range(len(shares)), key=shares.__getitem__)
    w = wits[i]
    who = names[i] if i < len(names) else f"#{w.comp_index}"
    return (f"{bid}: {ring_area_m2:.0f} m2 — no member's floor plate is a floor: the widest "
            f"reading, {who}, keeps {shares[i]:.1%} of its {w.plate_area_m2:.0f} m2 plate at "
            f"footprint_close_m {width_m:g} m wide (< bank_band_plate_min {share_min:.0%}) — a "
            f"WALL'S FOOTING, never a pit (#1950/#1952) at {site}")
