"""THE COVERED-SPAN MASK — no synthesised road pavement over a roofed bore.

Spec ``docs/specs/tunnel-integrity-round-spec.md`` §T7:

    A COVERED-SPAN MASK (union of mapped bores' covered stretches, the
    data the tunnel pass already derives) is published ONCE and consumed
    by ``build_service_road_network`` (rects and fills never minted
    inside it) and by a POST-MINT SUPPRESSION that catches any other
    emitter's synthesised road-corridor pavement there.  Mapped REAL
    pavement polygons (OSM/apt.dat authored) are NOT suppressed — the
    mask kills synthesis, not data.

Measured population (the lane/lemdtun attribution): 22 road-corridor
pieces at grade over roofed bores across two airports — 6.00 m rects,
3.50x6.00 fills and their groundside demotions.  A car driving one of
them drives on the roof of the tunnel it is supposed to be inside.

WHY A MASK AND NOT A LATER CLIP.  The roofing (``tunnel_roof``) is
emitted in phase 6, long after the service-road network is minted in
phase 4; by the time a roof exists the rect is already a shape with a
solved profile and a census row.  The BORE, though, is known from the
road feed in phase 1 — a ``tunnel=yes`` way is a covered stretch by
definition — so the mask is derivable at mint time and the pieces are
never minted at all.

ONE DERIVATION.  The bore ways come from ``bridges._load_tunnel_road_
network``, memoised on the layout, so publishing the mask does not load
the road caches a second time: the tunnel pass in phase 6 reuses this
pass's load.  Two loads would be two populations as well as two costs.
"""
from __future__ import annotations

import os

import O4_UI_Utils as UI

_ENV = "O4_COVERED_SPAN_MASK"
_ATTR = "_covered_span_mask"

#: Half-width margin (m) beyond the bore's own carriageway.  A rect
#: minted a metre off the bore edge is still on its roof; the mask is the
#: ground the bore occupies, not its centreline.
COVERED_SPAN_MARGIN_M = 2.0


def enabled() -> bool:
    return os.environ.get(_ENV, "1") == "1"


def publish(layout) -> None:
    """Derive and stash the mask.  Idempotent; never raises."""
    if not enabled():
        return
    if getattr(layout, _ATTR, "unset") != "unset":
        return                                  # published once per build
    mask = None
    try:
        from shapely.geometry import LineString
        from shapely.ops import unary_union

        from .bridges import (
            TUNNEL_DEFAULT_CARRIAGEWAY_WIDTH_M, TUNNEL_VALUES,
            _carriageway_width_from_tags, _load_tunnel_road_network,
            _local_meter_projections, _tunnelable,
        )
        nodes_r, ways_r, _big, _ntags = _load_tunnel_road_network(layout)
        to_m, _m_to_ll = _local_meter_projections(layout.anchor)
        bodies = []
        for _wid, nrefs, tags in ways_r:
            # COVERED, not merely BELOW GRADE.  ``_has_tunnel_tag_
            # evidence`` (the R4 admission test) also accepts ``layer<0``
            # alone — an open cut, which has no roof and therefore no
            # roof for a road to stand on.  §T7's subject is the COVERED
            # stretch, so the tag test is ``tunnel=``.  Measured at LEMD:
            # 24 of 24 bore ways carry ``tunnel=`` and 0 are layer-only,
            # so this narrows the mask without changing it there — and it
            # cannot widen it anywhere.
            if not _tunnelable(tags) or tags.get("tunnel") not in \
                    TUNNEL_VALUES:
                continue
            pts = []
            for n in nrefs:
                ll = nodes_r.get(n)
                if ll is None:
                    continue
                pts.append(to_m(ll[1], ll[0]))
            if len(pts) < 2:
                continue
            half = 0.5 * float(_carriageway_width_from_tags(
                tags.get("highway"), tags,
                TUNNEL_DEFAULT_CARRIAGEWAY_WIDTH_M)) \
                + COVERED_SPAN_MARGIN_M
            try:
                bodies.append(LineString(pts).buffer(
                    half, cap_style=2, join_style=2))
            except Exception:                            # pragma: no cover
                continue
        if bodies:
            mask = unary_union(bodies)
            if mask.is_empty:
                mask = None
    except Exception as exc:
        UI.vprint(1, f"  [covered-span] mask NOT derived ({exc!r}) — "
                     f"§T7 suppression is INACTIVE this build.")
        mask = None
    try:
        setattr(layout, _ATTR, mask)
    except (AttributeError, TypeError):                  # pragma: no cover
        return
    if mask is not None:
        UI.vprint(1,
            f"  [covered-span] mask published: {mask.area:.0f} m² over "
            f"the mapped bores' covered stretches — no SYNTHESISED road "
            f"corridor is minted or kept inside it (§T7).  Authored "
            f"pavement is untouched: the mask kills synthesis, not data.")
    else:
        UI.vprint(1,
            "  [covered-span] mask published: EMPTY (no mapped bore in "
            "this airport's road feed).")


def mask_of(layout):
    """The published mask, or ``None``.  Never derives — a consumer that
    finds nothing published measured nothing, and saying so is the point
    (a lazily-derived mask would be a second derivation)."""
    if not enabled():
        return None
    m = getattr(layout, _ATTR, None)
    return None if m == "unset" else m


def suppress_synthesised_road_pavement(layout, icao: str = "") -> int:
    """POST-MINT SUPPRESSION (§T7.1): drop any SYNTHESISED road-corridor
    pavement standing inside the mask, whatever emitter minted it.

    SYNTHESISED means minted by this pipeline as a corridor surface —
    the ``service_road`` rects, the ``service_junction`` fills, and the
    groundside demotions of either.  An AUTHORED polygon (an OSM or
    apt.dat pavement ring that happens to lie over a bore) is NOT
    suppressed: the mask kills synthesis, not data, and a real roof-top
    car park is real.  The discriminator is
    ``BuiltShape.synthesised_road_corridor``, stamped by the minter and
    riding the shape through every clip and re-role — a role test could
    not tell the two apart after the scorer has spoken.

    Every suppression is NAMED per piece (§T4.1's form).  Returns the
    count.
    """
    mask = mask_of(layout)
    if mask is None:
        return 0
    from .road_piece_ledger import log_removal
    try:
        from shapely.prepared import prep
        mprep = prep(mask)
    except Exception:                                    # pragma: no cover
        mprep = None
    kept, n = [], 0
    for s in layout.shapes:
        poly = getattr(s, "polygon", None)
        if (poly is None or poly.is_empty
                or not getattr(s, "synthesised_road_corridor", False)):
            kept.append(s)
            continue
        try:
            if mprep is not None and not mprep.intersects(poly):
                kept.append(s)
                continue
            over = poly.intersection(mask).area
        except Exception:                                # pragma: no cover
            kept.append(s)
            continue
        # MOSTLY over the bore: a corridor grazing a bore's edge on its
        # way past is not standing on the roof.
        if over <= 0.5 * poly.area:
            kept.append(s)
            continue
        log_removal(layout, s, "covered-span mask (synthesised road "
                               "pavement over a roofed bore)")
        n += 1
    if n:
        layout.shapes = kept
        try:
            UI.vprint(1,
                f"  [covered-span] {icao}: {n} synthesised road-corridor "
                f"piece(s) suppressed over covered bore stretches — each "
                f"named above.  Authored pavement over a bore is "
                f"untouched.")
        except Exception:                                # pragma: no cover
            pass
    return n
