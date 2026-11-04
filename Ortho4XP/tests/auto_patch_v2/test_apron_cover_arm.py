"""#1696 (owner 2026-10-30, KBNA ``dsf:pol267`` / ``dsf:pol295``): a
narrow taxiway whose far end runs under OSM's ``aeroway=apron`` is not
apron end to end.

§40 (2) refuses the corridor kind on that cover and the width reading
finds no lobe (the whole face is under ``corridor.max_width_m``), so the
whole taxiway came out apron.  ``neck.cover_arms`` reads §43 (1)'s arm
against the MAPPED apron instead: the covered pavement is the wide body,
and what leaves it across a cross-section and follows a path is an arm —
taxiway on taxi evidence, the covered end stays apron.
"""
from __future__ import annotations

from auto_patch_v2.classify.neck import cover_arms
from auto_patch_v2.classify.roles import _neck_pieces
from auto_patch_v2.classify.rules import load_rules
from shapely.geometry import box

ident = lambda x, y: (x, y)                            # noqa: E731


def _centreline(*xy):
    """Taxi evidence as ``_neck_pieces`` takes it (``roles._touching``)."""
    import types

    from auto_patch_v2.classify.roles import _touching
    from shapely.geometry import LineString
    from shapely.strtree import STRtree
    parts = [(LineString(xy), types.SimpleNamespace(id=1))]
    tree = STRtree([ln for ln, _c in parts])
    return lambda poly: _touching(poly, tree, parts, load_rules())


def _taxiway():
    """A 14 m x 800 m taxiway; OSM's apron covers its last 120 m."""
    return box(0.0, 0.0, 800.0, 14.0), box(680.0, -40.0, 900.0, 60.0)


def test_the_taxiway_leaving_the_mapped_apron_is_an_arm():
    rules = load_rules()
    face, apron = _taxiway()
    arms = cover_arms(face, apron, rules)
    assert len(arms) == 1 and arms[0].kind == "arm" and arms[0].reread
    along = _centreline((0.0, 7.0), (800.0, 7.0))
    stats: dict = {}
    pieces = _neck_pieces(face, rules, ident, [], stats, None, along, apron)
    assert stats["apron_cover_arms"] == 1
    taxi = [p for p, m in pieces if m.get("neck_cut")]
    rest = [p for p, m in pieces if m.get("neck_new_apron")]
    assert len(taxi) == 1 and len(rest) == 1
    assert abs(rest[0].area - 120.0 * 14.0) < 1.0      # the covered end stays apron


def test_no_centreline_no_cut():
    """Gated as the #314 re-read: without taxi evidence it stays apron."""
    rules = load_rules()
    face, apron = _taxiway()
    assert _neck_pieces(face, rules, ident, [], {}, None, None, apron) == []


def test_without_cover_nothing_changes():
    """The cover read runs only where §40 (2) refused the corridor."""
    rules = load_rules()
    face, _apron = _taxiway()
    along = _centreline((0.0, 7.0), (800.0, 7.0))
    assert _neck_pieces(face, rules, ident, [], {}, None, along) == []


def test_a_flank_under_the_apron_is_not_an_arm():
    """Apron drawn ALONG the taxiway (a flank, not a mouth) cuts nothing:
    the mouth-factor half of the arm verdict."""
    rules = load_rules()
    face = box(0.0, 0.0, 800.0, 14.0)
    flank = box(0.0, 7.0, 800.0, 60.0)
    assert cover_arms(face, flank, rules) == []


def test_a_wide_piece_between_two_mapped_aprons_is_not_cut():
    """HECA (batch BA): the cover is not a width.  A 55 m-wide piece
    between two mapped aprons separates them, but it is no path: neither
    narrow nor hanging off a mouth, so it is not cut."""
    rules = load_rules()
    face = box(0.0, 0.0, 400.0, 55.0)
    cover = box(-10.0, -10.0, 60.0, 65.0).union(box(340.0, -10.0, 410.0, 65.0))
    assert cover_arms(face, cover, rules) == []
    narrow = box(0.0, 0.0, 400.0, 14.0)                 # a taxiway between them IS a path
    assert len(cover_arms(narrow, cover, rules)) == 1
