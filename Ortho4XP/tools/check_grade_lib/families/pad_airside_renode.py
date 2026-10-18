"""§16g (10) (12) (2) THE ARRANGEMENT CLIP PRESERVES THE AIRSIDE VERTEX SET
family ``pad_airside_renode`` (RULINGS 2026-09-16b), SIDECAR-DECLARED.
Moved verbatim from ``check_grade.py`` (issue #857), which re-exports it."""
from __future__ import annotations

from typing import List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    # §16g (10) (12) (2) THE ARRANGEMENT CLIP PRESERVES THE AIRSIDE VERTEX
    # SET (Fable 2026-09-16; RULINGS 2026-09-16b).  SIDECAR-DECLARED, like
    # ``eat_ceiling`` and ``seam_pins`` below: the only place the airside's
    # pre-pad and post-pad node sets both exist is inside the build's own
    # arrangement, so the build publishes what its pad stage did and this
    # prices exactly that.  A PRESENCE family and a GUARD on the
    # derivation, never a defect magnitude.
    ("pad_airside_renode",
     "AIRSIDE CELL VERTEX minted or deleted BY THE PAD STAGE",
     "within"),
)


#: §16g (10) (12) (2): the two witness ways a re-node row is reported on.
#: The role is ``apron`` because an airside CELL is what was re-noded; the
#: refs name the direction so a row reads without its source.
_RENODE_WAYS = {
    "minted": Way("pad_airside_renode", "apron", "pad_airside_renode:minted",
                  "", [], [], {}),
    "deleted": Way("pad_airside_renode", "apron", "pad_airside_renode:deleted",
                   "", [], [], {}),
}


def _check_pad_airside_renode(renode_ll, nodes) -> List[Violation]:
    """§16g (10) (12) (2) THE ARRANGEMENT CLIP PRESERVES THE AIRSIDE VERTEX
    SET (Fable 2026-09-16; RULINGS 2026-09-16b).

    ONE ROW PER AIRSIDE NODE the pad stage minted or deleted, read from the
    sidecar's ``pad_airside_renode`` — the build's own pass A (the airside
    noded before any pad exists) against its pass B.  It is a PRESENCE
    family and a GUARD on that derivation, never a grade count: an emitted
    surface carrying an extra airside vertex breaks no grade law, which is
    why 15ah's far-field attribution — the clip alone deleting 1,082
    solve-owned airside vertices and minting 235 at HECA — had no
    instrument at all and had to be measured with a lane arm.  The bar is
    an EMPTY list, and a patch with no key reports nothing.

    A MINTED node is joined back to the patch by the canonical 11-dp
    lat/lon identity (memory ``canonical-identity-join``) so the row names
    the way it stands on; a DELETED node is by definition absent from the
    patch and carries its own coordinate alone.
    """
    if not renode_ll:
        return []
    out: List[Violation] = []
    for row in renode_ll:
        if not row or len(row) < 2:
            continue
        try:
            lat, lon = float(row[0]), float(row[1])
        except (TypeError, ValueError):
            continue
        kind = str(row[2]) if len(row) > 2 else "minted"
        way = _RENODE_WAYS[kind if kind in _RENODE_WAYS else "minted"]
        v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
                      de_m=0.0, way_a=way, way_b=way,
                      pt_a=(0.0, 0.0), pt_b=(0.0, 0.0),
                      elev_a=0.0, elev_b=0.0)
        v.lat, v.lon = lat, lon
        out.append(v)
    return out
