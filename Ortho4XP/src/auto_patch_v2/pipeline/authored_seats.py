"""THE SEAT DECISION per below-grade object — authored to the cut, or
re-seated (object-placement spec §18 (3); owner RULINGS 2026-10-07b (1),
2026-10-07c (3)-(5)).

ONE site decides, for every tunnel wall object and every basin witness the
planar map admitted, whether the AUTHOR'S seat already works over the
terrain the engine cuts: :func:`seat_records` reads the two witnesses the
planar pass stamped (``Tunnel.authored_crest_m``, ``Basin.rim_cut_m``)
against the two law bands and returns one record per placement.  The
plate site (``pipeline/build._plate_seats``) enters only the RE-SEATED
ones, the rebake inputs exclude the kept ones from every seat, and the
plan publishes the records (``RebakePlan.authored_seats``).

The arithmetic is ``airport/authored_seat``'s; nothing here names a pack
or an airport.
"""
from __future__ import annotations

import typing as _t

from ..airport import authored_seat as _seat

__all__ = ["seat_records", "kept_ids", "seat_lines"]


def seat_records(pm: _t.Any, law: _t.Any) -> dict[str, dict[str, _t.Any]]:
    """Placement id -> the seat record: ``seat`` (``authored (cut)`` /
    ``re-seated``), ``datum`` (``crest`` / ``rim``), ``h_cut_m`` (the
    datum over the grade with the authored seat on the cut terrain),
    ``h_uncut_m`` (a wall's, on uncut ground), ``proud_m`` (a re-seated
    wall's target over the grade — the pack's median stated height, 0.0 =
    flush), and for a pit ``agl_authored_m`` (its authored lift) and
    ``members`` (its basin's placements).  A structure carrying no witness
    (a PLAIN pit — no lift, no stated seat; a record older than §18; a
    twin's stand-in) has no record and seats as before."""
    st = law.tables.structures
    crest_max = float(st.tunnel.object.authored_crest_max_m)
    walls: list[tuple[str, str, float, float]] = []
    for tn in getattr(pm, "structures", ()):
        if getattr(tn, "source", "") != "object":
            continue
        for oid, hh in zip(tn.objects, getattr(tn, "authored_crest_m", ()) or ()):
            walls.append((oid, tn.resource, float(hh[0]), float(hh[1])))
    proud = _seat.pack_proud_height(_seat.stated_height(hc, hu, crest_max)
                                    for _o, _r, hc, hu in walls)
    out: dict[str, dict[str, _t.Any]] = {}
    for oid, res, hc, hu in walls:
        kept = _seat.crest_in_band(hc, crest_max)
        out[oid] = {"id": oid, "resource": res, "datum": "crest",
                    "seat": _seat.SEAT_AUTHORED if kept else _seat.SEAT_RESEATED,
                    "h_cut_m": hc, "h_uncut_m": hu,
                    "proud_m": None if kept else float(proud or 0.0),
                    "stated": _seat.stated_height(hc, hu, crest_max) is not None}
    rim_tol = float(st.basin.authored_rim_tol_m)
    for b in getattr(pm, "basins", ()):
        r = getattr(b, "rim_cut_m", None)
        if not getattr(b, "witness_id", "") or r is None or b.witness_id in out:
            continue
        kept = _seat.rim_in_band(r, rim_tol)
        out[b.witness_id] = {"id": b.witness_id, "resource": b.id, "datum": "rim",
                             "seat": _seat.SEAT_AUTHORED if kept else _seat.SEAT_RESEATED,
                             "h_cut_m": float(r), "agl_authored_m": float(b.agl_m),
                             "members": sorted(b.member_ids)}
    return out


def kept_ids(records: _t.Mapping[str, _t.Mapping[str, _t.Any]]) -> set[str]:
    """The placements whose authored seat is KEPT: never plate-seated,
    never re-seated by any other rule — a kept wall, and a kept pit with
    every member of its basin AND of their anchor families (``Basin.
    member_ids`` carries both: the placements whose floors ARE the pit and
    the ones the author lifted with them at the same anchor — one shell of
    two is not moved against the other)."""
    out: set[str] = set()
    for oid, r in records.items():
        if r.get("seat") == _seat.SEAT_AUTHORED:
            out.add(oid)
            out.update(r.get("members") or ())
    return out


def seat_lines(records: _t.Iterable[_t.Mapping[str, _t.Any]], pad: str = "  ") -> list[str]:
    """THE SEAT COLUMN (spec §18 (6), last row): one line per wall / pit
    placement — its ``seat`` and the numbers it was decided on — for the
    replay's ``--emit`` / ``--verify`` report and ``obj8_split_report``
    (which reads ``RebakePlan.authored_seats``): one formatter, two
    reports.  Empty where the map admits no below-grade object."""
    rows = sorted(records, key=lambda r: (str(r.get("datum")), str(r.get("resource")),
                                          str(r.get("id"))))
    if not rows:
        return []

    def m(v: _t.Any) -> str:
        return "    -" if v is None else f"{float(v):+5.2f}"
    kept = sum(1 for r in rows if r.get("seat") == _seat.SEAT_AUTHORED)
    out = [f"{pad}SEAT (spec §18): {len(rows)} wall / pit placement(s) — {kept} "
           f"{_seat.SEAT_AUTHORED}, {len(rows) - kept} {_seat.SEAT_RESEATED}",
           f"{pad}  {'seat':<14} {'datum':<5} {'h_cut':>6} {'h_uncut':>7} {'proud':>6}  id  resource"]
    for r in rows:
        out.append(f"{pad}  {str(r.get('seat')):<14} {str(r.get('datum')):<5} "
                   f"{m(r.get('h_cut_m')):>6} {m(r.get('h_uncut_m')):>7} "
                   f"{m(r.get('proud_m')):>6}  {r.get('id')}  {r.get('resource')}")
    return out
