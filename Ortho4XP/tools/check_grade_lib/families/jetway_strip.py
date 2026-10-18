"""THE JETWAY STRIP family ``jetway_strip`` (owner RULINGS 2026-09-18t Q3;
jetway-strip spec §2 (6)), SIDECAR-DECLARED.  Moved verbatim from
``check_grade.py`` (issue #857), which re-exports it."""
from __future__ import annotations

from typing import Dict, List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    # THE JETWAY STRIP (owner RULINGS 2026-09-18t Q3; jetway-strip spec
    # §2 (6)).  SIDECAR-DECLARED like the family above: the build
    # publishes each strip's ONE level, its vertices by identity and its
    # projection's clamps (``jetway_strips``), and this prices exactly that.
    ("jetway_strip",
     "JETWAY STRIP vertex off its ONE level, or a CLAMP the strip reported",
     "within"),
)


#: jetway-strip spec §2 (6) (a): a strip vertex off its strip's ONE level
#: by more than this is a row — §31's visual floor, the spec's materiality.
_JETWAY_STRIP_TOL_M = 0.05


def _check_jetway_strip(jetway_strips_ll, nodes, ways) -> List[Violation]:
    """THE JETWAY STRIP (owner RULINGS 2026-09-18t Q3: "UNDER THE JETWAYS
    THE APRON STRIP IS LEVEL WITH THE TERMINAL"; jetway-strip spec §2 (6)).

    SIDECAR-DECLARED, like ``pad_airside_renode`` and ``seam_residual``:
    the build publishes per strip its ONE level, its vertices by the
    canonical 11-dp identity and the clamps its projection reported, and
    this prices the EMITTED surface against exactly that —

      (a) a strip vertex standing off its target — the PAD'S PLANE at
          that vertex (spec-author ruling Q-32a (d); the strip's level for
          a sidecar with 2-element vertices) — by more than
          ``_JETWAY_STRIP_TOL_M``;
      (c) every clamp the projection reported (a taxi / runway / pinned /
          other-pad vertex the field would have moved, never absorbed) —
          one row each, carrying its metres.

    (b), a transition pair over the apron ``max``, is the ``within_shape``
    family's own apron pair — the transition changes no role and no cap,
    so a second reading here would count the same pair twice.  A patch
    with no key reports nothing."""
    if not jetway_strips_ll:
        return []
    by_ll: Dict[Tuple[float, float], Tuple[float, Way]] = {}
    for w in ways:
        for nid, z in zip(w.nids, w.elevs):
            if z is None or nid not in nodes:
                continue
            lat, lon = nodes[nid]
            by_ll.setdefault((round(lat, 7), round(lon, 7)), (float(z), w))
    out: List[Violation] = []
    for st in jetway_strips_ll:
        if not isinstance(st, dict):
            continue
        lvl = st.get("level")
        ref = f"jetway_strip:{st.get('pad_ref', '')}"
        if lvl is not None:
            for ll in st.get("vertices_ll") or ():
                try:
                    lat, lon = float(ll[0]), float(ll[1])
                    # Q-32a (d): the vertex's own target on the pad plane
                    tgt = float(ll[2]) if len(ll) > 2 else float(lvl)
                except (TypeError, ValueError, IndexError):
                    continue
                got = by_ll.get((round(lat, 7), round(lon, 7)))
                if got is None:
                    continue
                z, way = got
                if abs(z - tgt) <= _JETWAY_STRIP_TOL_M:
                    continue
                v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
                              de_m=abs(z - tgt), way_a=way, way_b=way,
                              pt_a=(0.0, 0.0), pt_b=(0.0, 0.0),
                              elev_a=z, elev_b=tgt)
                v.lat, v.lon = lat, lon
                out.append(v)
        for c in st.get("clamps") or ():
            try:
                lat, lon, m = float(c[0]), float(c[1]), float(c[3])
            except (TypeError, ValueError, IndexError):
                continue
            got = by_ll.get((round(lat, 7), round(lon, 7)))
            way = got[1] if got is not None else Way(
                "jetway_strip", "apron", ref + f":clamp:{c[2]}", "", [], [], {})
            z = got[0] if got is not None else 0.0
            v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
                          de_m=abs(m), way_a=way, way_b=way,
                          pt_a=(0.0, 0.0), pt_b=(0.0, 0.0),
                          elev_a=z, elev_b=z + m)
            v.lat, v.lon = lat, lon
            out.append(v)
    return out
