"""WHAT MAY BE AN APRON (#2134, spec ``sim-review/2134-apron-rules.md``
§4; owner 2026-11-17).

The owner's spine (14:12Z): "The more strict the grade requirements, the
more strict and certain we need to be about classifying pavement."  The
apron carries the strictest non-runway grade law, so a face the slice
scored ``apron`` (the residual kind: no taxi centreline claimed it) keeps
``apron`` only on a STRONG witness — and where the evidence is uncertain
it takes the LESS strict class.

``open_default.apron_witness`` is the one reader of the evidence on a
face; this module is the one place that turns it into a verdict, over the
whole slice at once (contiguity is a property of the set):

* ``A1`` — a stand on the face — and ``A2`` — a parking LOBE (somewhere
  ``corridor.max_width_m`` wide) with OSM apron over the cell's majority or
  an authored apron name — are APRON, and seed the APRON BODY;
* the body grows over LOBED faces sharing at least ``lot.airside_edge_min_m``
  of edge with it (one apron), and over A2' LANES: faces with no lobe and
  no taxi centreline whose edge contact is mostly with the body (03j,
  free-road, 12f);
* a lobed face left out with airside evidence is owner Q3 (14:37Z): "If the
  area is wider than our widest taxiway class plus an allowance for a
  shoulder, and it touches a building, mark it apron, otherwise taxiway.
  This type should get the largest (strictest) taxiway grade rule" — the
  widest letter of the authority's ``taxi.width_m`` plus a taxiway
  shoulder each side (``apron.arm_road_max_width_m``, the 11-10m shoulder
  depth), a building by Rule T's touch (``pad_touch.is_touching``);
* a face with no lobe that a taxi centreline or a taxi-family face touches
  is TAXI FAMILY (owner Q1 14:33Z: a taxi centreline is airside evidence,
  never apron) — ``junction`` at the nearest through route's letter, after
  the 11-10m shoulder join has taken what it qualifies (:func:`settle`);
* everything else goes to §110's groundside verdict and §27 — unless the
  source's LIBRARY PATH names a taxiway (owner Q5 14:38Z: the lowest rung,
  "in the absence of other evidence"), which makes it ``junction``.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.strtree import STRtree

from ..law import Law
from .open_default import A1, A2, has_lobe
from .pad_touch import is_touching
from .rules import Rules

__all__ = ["PENDING_KEY", "resolve_aprons", "settle"]

#: a face left ``apron`` for the 11-10m shoulder join to read, then
#: :func:`settle`d to ``junction`` at the letter stored under this key
PENDING_KEY = "apron_gate_junction"


class _Verdict(_t.NamedTuple):
    """The gate's answer for one face: ``role`` is ``apron``, ``junction``,
    or ``None`` (§110's groundside verdict, then §27)."""

    role: str | None
    letter: str | None
    evidence: dict


def _q3_width_m(law: Law, rules: Rules) -> tuple[float, str | None]:
    """``(width, letter)`` of owner Q3: the widest taxiway class of the
    authority plus a taxiway shoulder on each side, and that class's
    letter (the strictest taxiway grade rule)."""
    tbl = law.ruleset.taxi.width_m
    bounds = (tbl.by_letter or {}) if tbl is not None else {}
    if not bounds:
        return float("inf"), None
    letter, width = max(bounds.items(), key=lambda kv: (float(kv[1]), kv[0]))
    return float(width) + 2.0 * float(rules.apron.arm_road_max_width_m), letter


def _shared(face: Polygon, tree: STRtree | None, polys, tol: float,
            skip: int = -1) -> float:
    """Metres of ``face``'s boundary within ``tol`` of any of ``polys``
    (``polys[skip]``, the face itself, excluded)."""
    if tree is None:
        return 0.0
    run = 0.0
    edge = face.boundary
    for j in tree.query(face.buffer(tol), predicate="intersects"):
        if int(j) != skip:
            run += edge.intersection(polys[int(j)].buffer(tol)).length
    return run


def _tree(polys):
    return STRtree(polys) if polys else None


def resolve_aprons(faces: _t.Mapping[int, Polygon],
                   witness: _t.Mapping[int, tuple[str | None, str | None]],
                   taxi_faces: _t.Sequence[Polygon],
                   other_airside: _t.Sequence[Polygon],
                   pads: _t.Sequence[Polygon], *,
                   taxi_on: _t.Callable[[Polygon], bool],
                   letter_of: _t.Callable[[Polygon], str | None],
                   path_taxi: _t.Mapping[int, str], no_landside: bool = False,
                   law: Law, rules: Rules) -> dict[int, _Verdict]:
    """The verdict of every face the slice scored ``apron``.

    ``faces`` / ``witness`` are keyed alike (``apron_witness``'s rung and
    why per face); ``taxi_faces`` the taxi-family faces, ``other_airside``
    the runway family; ``taxi_on(face)`` whether a taxi centreline touches
    it, ``letter_of(face)`` the nearest through route's letter,
    ``path_taxi`` the faces whose source's library path names a taxiway.

    ``no_landside``: the airport has NO TERMINAL, so it has no landside
    (user 2026-06-11, ``groundside.requires_terminal``: "every paved island
    is aircraft parking").  Every face is then airside on that word alone —
    the weak rung — and what would have gone groundside is taxi family:
    airside, and less strict than an apron no witness vouches for."""
    if no_landside:
        witness = {i: (w if w[0] is not None else
                       ("A3", "no terminal: no landside (user 2026-06-11)"))
                   for i, w in witness.items()}
    tol = float(law.tables.emit.identity.weld_spacing_m)
    min_m = float(rules.lot.airside_edge_min_m)
    lobe = {i: has_lobe(f, rules.corridor.max_width_m) for i, f in faces.items()}
    why = {i: w[1] for i, w in witness.items() if w[0] in (A1, A2)}
    body = set(why)
    taxi_tree = _tree(list(taxi_faces))
    fixed = list(taxi_faces) + list(other_airside)
    fixed_tree = _tree(fixed)
    while True:
        grown = _grow(faces, body, lobe, why, fixed, fixed_tree, taxi_on, tol, min_m)
        if not grown:
            break
    q3_w, q3_letter = _q3_width_m(law, rules)
    pad_tree = _tree(list(pads))
    out: dict[int, _Verdict] = {}
    for i, face in faces.items():
        rung, seen = witness[i]
        ev: dict = {"apron_witness": seen or "none"}
        if i in body:
            out[i] = _Verdict("apron", None, dict(ev, apron_verdict=why[i]))
        elif rung is not None and lobe[i]:
            out[i] = _q3(face, ev, q3_w, q3_letter, pad_tree, pads, law)
        elif rung is not None and (taxi_on(face) or _shared(
                face, taxi_tree, taxi_faces, tol) >= min_m):
            out[i] = _Verdict("apron", None, dict(
                ev, apron_verdict="taxi contact, no lobe: taxi family (Q1)",
                **{PENDING_KEY: letter_of(face) or ""}))
        elif i in path_taxi:
            out[i] = _Verdict("junction", letter_of(face), dict(
                ev, apron_verdict=f"library path names a taxiway ({path_taxi[i]}, Q5)"))
        elif no_landside:
            out[i] = _Verdict("junction", letter_of(face), dict(
                ev, apron_verdict="no terminal, no apron witness: taxi family"))
        else:
            out[i] = _Verdict(None, None, ev)
    return out


def _grow(faces, body, lobe, why, fixed, fixed_tree, taxi_on, tol, min_m) -> int:
    """One round of the apron body's growth; returns the faces added.  A
    LANE (no lobe, no taxi centreline) joins when its contact with the body
    is at least its contact with every other airside face."""
    members = sorted(body)
    mpolys = [faces[j] for j in members]
    btree = _tree(mpolys)
    rest = [j for j in faces if j not in body]
    rpolys = [faces[j] for j in rest]
    rtree = _tree(rpolys)
    added = []
    for k, i in enumerate(rest):
        face = faces[i]
        m_body = _shared(face, btree, mpolys, tol)
        if m_body < min_m:
            continue
        if lobe[i]:
            added.append((i, "lobe, one body with a witnessed apron (A2)"))
            continue
        if taxi_on(face):
            continue
        m_other = _shared(face, fixed_tree, fixed, tol) + _shared(
            face, rtree, rpolys, tol, skip=k)
        if m_body >= m_other:
            added.append((i, "lane of a witnessed apron (A2')"))
    for i, w in added:
        body.add(i)
        why[i] = w
    return len(added)


def _q3(face: Polygon, ev: dict, width: float, letter: str | None, pad_tree,
        pads, law: Law) -> _Verdict:
    """Owner Q3 for a lobed face no stand or apron body vouches for."""
    wide = has_lobe(face, width)
    touches = pad_tree is not None and any(
        is_touching(law, face.distance(pads[int(j)]))
        for j in pad_tree.query(face.buffer(1.0), predicate="intersects"))
    if wide and touches:
        return _Verdict("apron", None, dict(
            ev, apron_verdict=f"wider than {width:.0f} m and touches a building (Q3)"))
    return _Verdict("junction", letter, dict(
        ev, q3_taxiway=1.0,
        apron_verdict=(f"{'wide' if wide else 'narrower than'} {width:.0f} m, "
                       f"{'touches' if touches else 'no'} building: taxiway at the "
                       f"strictest letter (Q3)")))


def settle(final: list[list]) -> int:
    """After the 11-10m shoulder join: every face still pending is
    ``junction`` at its stored letter (``final`` rows are ``[role, ref,
    face, letter, evid, kind]``, edited in place).  Returns the count."""
    n = 0
    for row in final:
        if row[0] == "apron" and PENDING_KEY in row[4]:
            letter = row[4][PENDING_KEY] or None
            row[0], row[3] = "junction", letter
            row[4] = dict(row[4], kind="junction")
            row[5] = "junction"
            n += 1
    return n
