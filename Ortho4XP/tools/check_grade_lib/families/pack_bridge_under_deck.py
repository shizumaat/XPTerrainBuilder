"""THE PACK'S BRIDGE OR OURS, NEVER BOTH family ``pack_bridge_under_deck``
(owner RULINGS 2026-11-20a (1); issue #2191), SIDECAR-DECLARED.

The build makes ONE decision per crossing (``planar/deck_takeover.
_one_decision``): where it generates a deck, every pack bridge body over
the crossing is hidden in the pack copy.  The sidecar
``pack_bridge_under_deck`` names each pack placement still drawing a
deck-level top under a generated deck's footprint after it
(``{"deck", "object", "resource", "lat", "lon", "area_m2"}``); every
record is one PRESENCE row.  A patch with no key reports nothing, which is
every patch built before the decision (KMCO 1.0.567: ``puente.obj`` under
our decks, no row).

THE WRITTEN PACK TOO (:func:`written_pack_records`): the sidecar is the
DECISION; the pack copy is what X-Plane draws.  The pack write reads its
own written text back (``airport/dsf_row_hide.drawn_rows``: a hidden
placement or a body of its split still drawn) into its record
(``o4_placement_provenance.json``, ``o4_generated.counts.hides_drawn``);
each such row is a presence row here, so the census cannot pass while the
pack still draws a hidden bridge (MEASURED KRDU 1.0.570: the split-renamed
``STH_TML__b0_*.obj`` stayed drawn, the sidecar named none)."""
from __future__ import annotations

import glob
import json
import os
from typing import List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    ("pack_bridge_under_deck",
     "PACK BRIDGE left under a GENERATED deck (the pack's bridge or ours, never both)",
     "within"),
)


def check_pack_bridge_under_deck(records) -> List[Violation]:
    """The family's rows (module doc)."""
    out: List[Violation] = []
    for rec in records or ():
        w = Way(str(rec.get("object")), "pack_bridge", str(rec.get("deck")), "", [], [], {})
        v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
                      de_m=float(rec.get("area_m2") or 0.0), way_a=w, way_b=w,
                      pt_a=(0.0, 0.0), pt_b=(0.0, 0.0), elev_a=0.0, elev_b=0.0)
        v.lat, v.lon = float(rec.get("lat") or 0.0), float(rec.get("lon") or 0.0)
        out.append(v)
    return out


def _json(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def written_pack_records(osm_path) -> list:
    """The records of every hidden placement row the WRITTEN pack DSF still
    draws (module doc), read off the rebake plans beside the patch
    (``o4_v2_rebake_*.json``: their ``dsf_path``) and each DSF's record;
    ``[]`` where none is written or none is drawn."""
    out: list = []
    seen: set = set()
    for plan in sorted(glob.glob(os.path.join(os.path.dirname(str(osm_path)),
                                              "o4_v2_rebake_*.json"))):
        pd = _json(plan)
        dsf = pd.get("dsf_path") if isinstance(pd, dict) else None
        if not dsf or dsf in seen:
            continue
        seen.add(dsf)
        doc = _json(os.path.join(os.path.dirname(dsf), "o4_placement_provenance.json"))
        if not isinstance(doc, dict):
            continue
        base = os.path.basename(dsf)
        entry = (doc.get("dsfs") or {}).get(base) if isinstance(doc.get("dsfs"), dict) \
            else (doc if doc.get("dsf") == base else None)
        counts = ((entry or {}).get("o4_generated") or {}).get("counts") or {}
        for r in counts.get("hides_drawn") or ():
            out.append({"deck": f"written pack {base}", "object": str(r[0]),
                        "resource": str(r[0]), "lon": float(r[1]), "lat": float(r[2]),
                        "area_m2": 0.0})
    return out
