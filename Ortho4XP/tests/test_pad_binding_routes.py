"""PAD BINDING ROUTES — the sidecar, the single implementation, the tool.

Spec: ``docs/specs/pad-binding-routes-spec.md`` §3 twins 2, 4 and 5.  The
ENGINE CAPTURE twin (§3.1) lives with its fixture family in
``tests/test_seat_band_and_coupler.py``; the KEY-CLASSIFICATION twin (§3.3)
already exists in ``tests/test_harness.py`` and is untouched.

WHAT THIS ROUND IS.  Answering "show me the calculated route for
building25's pad at HECA" used to require a full in-process rebuild,
because the reach band is live solver state and ``trace_reach_route.py``
deliberately reads the LIVE band (a re-derivation offline is a second
engine, and being one is how that tool became wrong once already).  So the
engine PUBLISHES, at emit time, the route evidence it already computed,
and the tool gains a mode that renders the published record.  Publication
only — no law changes, no second engine.

Hermetic: ``tmp_path``, hand-written sidecars, no build, no network.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


# ══════════════════════════════════════════════════════════════════════
# §3.2 THE SIDECAR WRITE TWIN
# ══════════════════════════════════════════════════════════════════════

def _sidecar(layout, tmp_path):
    p = tmp_path / "p.osm"
    layout._write_axes_sidecar(str(p))
    return json.loads((tmp_path / "p.osm.axes.json").read_text(encoding="utf-8"))


def test_the_key_is_classified_as_evidence():
    """§1.5.  EVIDENCE, deliberately: the census REPORTS the routes and
    adjudicates nothing from them.  (``tests/test_harness.py`` is the twin
    that makes an unclassified key fail; this states the SIDE it is on.)"""
    spec = importlib.util.spec_from_file_location(
        "pad_routes_twin_check_grade", ROOT / "tools" / "check_grade.py")
    cg = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cg
    spec.loader.exec_module(cg)
    assert "pad_binding_routes" in cg.SIDECAR_EVIDENCE_KEYS
    assert "pad_binding_routes" not in cg.SIDECAR_LAW_KEYS


# ══════════════════════════════════════════════════════════════════════
# §3.4 THE SINGLE-IMPLEMENTATION TWIN
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# §3.5 THE TOOL SIDECAR-MODE TWIN — hermetic
# ══════════════════════════════════════════════════════════════════════


def _write_sidecar(tmp_path, box, name="HECA_auto.patch.osm"):
    patch = tmp_path / name
    patch.write_text("<osm version='0.6'></osm>", encoding="utf-8", newline="")
    (tmp_path / (name + ".axes.json")).write_text(json.dumps(
        {"anchor": [30.0, 31.0], "ruleset": "icao",
         **({} if box is None else {"pad_binding_routes": box})}), encoding="utf-8", newline="")
    return patch


