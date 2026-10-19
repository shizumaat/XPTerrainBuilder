"""§38 THE TILE SEAM IS A PIN family ``seam_residual`` (owner RULINGS
2026-09-13ah / 13am / 13an), SIDECAR-DECLARED.  Moved verbatim from
``check_grade.py`` (issue #857), which re-exports it."""
from __future__ import annotations

from typing import Dict, List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    # §38 THE TILE SEAM IS A PIN (owner RULINGS 2026-09-13ah / 13am /
    # 13an; spec §38 (5)).  Sidecar-declared like ``eat_ceiling`` above:
    # ``seam_pins`` = ``[lat, lon, the vertex's own tile's DEM sample]``
    # and ``seam_half_width_m`` = the band.  Before them the census had NO
    # patch-edge-vs-DEM family and could not see SPLP's 3.430 m seam berm
    # or the bank chain in the 1.6 mm crack that made the texture tear.
    ("seam_residual",
     "TILE-SEAM vertex OFF its own DEM sample (the pin the solve held)",
     "within"),
)


def _check_seam_residual(seam_pins_ll, nodes, ways) -> List[Violation]:
    """§38 (5) SEAM RESIDUAL: a seam band-edge vertex OFF its own DEM.

    The seam is an ANCHOR "like CIFP thresholds that everything else
    grades to" (owner 13ah), and a ``Pin`` holds exactly, so a row here
    means the EMITTED surface left the value the solve pinned — the only
    way this family can speak.  Until §38 the census had NO patch-edge-vs-
    DEM family at all and could not see the SPLP berm: 123 of 150 seam
    vertices off their DEM, worst 3.430 m, a 3 m ridge 10 m wide along the
    seam through the runway strip, with ``strip_seam_tear`` reading 0.

    The join is the canonical 11-dp lat/lon identity (memory
    ``canonical-identity-join``), never a proximity match.  A pin the
    patch does not carry is silently absent — a tile PIECE carries only
    its own side's vertices, and each side's pins are the ones it holds.
    A pre-§38 sidecar publishes 2-element pins with no value to price
    against, and this reports nothing for them.
    """
    if not seam_pins_ll:
        return []
    by_ll: Dict[Tuple[float, float], Tuple[float, Way]] = {}
    for w in ways:
        for nid, z in zip(w.nids, w.elevs):
            if z is None or nid not in nodes:
                continue
            lat, lon = nodes[nid]
            by_ll.setdefault((round(lat, 7), round(lon, 7)), (float(z), w))
    out: List[Violation] = []
    for pin in seam_pins_ll:
        if len(pin) < 3 or pin[2] is None:
            continue                      # a pre-§38 pin: no value published
        try:
            lat, lon, dem = float(pin[0]), float(pin[1]), float(pin[2])
        except (TypeError, ValueError):
            continue
        got = by_ll.get((round(lat, 7), round(lon, 7)))
        if got is None:
            continue
        z, way = got
        if abs(z - dem) <= _SEAM_RESIDUAL_TOL_M:
            continue
        v = Violation(
            grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
            de_m=abs(z - dem), way_a=way, way_b=way,
            pt_a=(0.0, 0.0), pt_b=(0.0, 0.0), elev_a=z, elev_b=dem)
        v.lat, v.lon = lat, lon
        out.append(v)
    return out


#: The materiality the seam is read at: the same elevation quantum the
#: emitted surface carries (``emit.materiality.elevation_m``), so a row
#: here is surface, never rounding.
_SEAM_RESIDUAL_TOL_M = 0.01
