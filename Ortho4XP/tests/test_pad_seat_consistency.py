"""Twins for the PAD-SEAT CONSISTENCY INTERVAL.

Spec: ``docs/specs/pad-seat-consistency-spec.md`` (twins (a)-(e) of its
"Twins" section, plus its implementation ruling of 2026-08-25).

Synthetic and headless by construction: the narrowing is pure interval
arithmetic over the frontage provenance the seat pass captured, so every
twin below constructs the provenance directly instead of building an
airport.  ``elev`` is a plain list — the solve's own array at the
post-phase-A slot.
"""


class _Layout:
    """The two attributes the narrowing touches: the node-space store (for
    ``seat_boxes``) and the provenance the seat pass published."""

    def __init__(self, units):
        self._pad_seat_consistency_units = units


def _rec(anchor, route_m, *, off_mask_m=0.0, floor=0.0, ceiling=0.0,
         seat_m=0.0):
    """One frontage band record in the shape ``_frontage_band_records``
    emits (``anchor_nodes`` / ``route_m`` / ``off_mask_m`` come straight
    from ``band.attachment_at``)."""
    return {"pad": "buildingX", "ll": [0.0, 0.0],
            "floor": float(floor), "ceiling": float(ceiling),
            "anchor_nodes": list(anchor), "route_m": float(route_m),
            "off_mask_m": float(off_mask_m),
            "floor_at_anchor": float(floor), "ceiling_at_anchor": float(ceiling),
            "seat_m": float(seat_m), "seat_final_m": float(seat_m)}


# ── the budget's units (the measured correction to the spec's wording) ──


# ── twin (a): the seat interval IS the intersection ─────────────────────


# ── twin (b): empty intersection is a SEAT DEFECT, never a silent pick ──


# ── the consistency intersection can itself be EMPTY ────────────────────


# ── twin (c): a pad with no frontage band behaves exactly as today ──────


# ── twin (d): the flag ──────────────────────────────────────────────────


# ── twin (e): the sidecar export carries the narrowed interval ──────────


def test_twin_e_unnarrowed_record_keeps_seat_final_equal_to_seat():
    """A record captured but never narrowed ships ``seat_final_m ==
    seat_m`` — the capture stamps it, so the census never sees a hole."""
    rec = _rec([3], 1.0, seat_m=107.0)
    assert rec["seat_final_m"] == rec["seat_m"]


# ── the yield-hard seats are narrowed too, and counted apart ────────────


