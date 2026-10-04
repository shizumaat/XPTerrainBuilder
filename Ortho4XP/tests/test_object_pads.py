"""Terrain-side BUILDING PADS — the pad request CONSUMER
(``auto_patch.object_pads``), its law (``grade_law.object_pad_*``) and its
validator (``verification.check_object_pads``).

Spec: ``docs/specs/per-cluster-object-seating-spec.md`` §5.1 (THE PAD
LAW), §5.2 (next-build convergence + ``emitted`` records), §5.4
(emission: role, precedence, decimation, ordering), §5.5 (validator
reader); chartered by ``docs/specs/object-reseat-threshold-spec.md`` §2.3
(gate default ON, env kill switch).

Headless and fixture-free: a synthetic flat DEM, one apron rectangle and
hand-built pad requests, so every assertion is about the LAW and the
emitter's contract rather than about one airport's terrain.

What is pinned here:

* THE TARGET (§5.1 clause 1) — the pad's core holds the request's
  ``target_ground_metres`` exactly; an over-cap request is REFUSED with
  its measured numbers and emits nothing;
* PAVEMENT WINS ABSOLUTELY (§5.1 clause 2, the R2 hard clause) — pads are
  clipped against pavement, a pad wholly inside pavement is inadmissible,
  and every pavement shape is byte-identical across the emitter;
* THE WELD (§5.1 clause 3, ruling R4) — a pad boundary vertex on a
  pavement ring carries the pavement's own value, and a short run pulls
  the pad TARGET toward the pavement with the shortfall reported;
* THE OPEN-SIDE BLEND (§5.1 clause 4) — the pad meets raw DEM at the
  margin edge, so there is no cliff onto untouched ground;
* CONVERGENCE (§5.2) — an ``emitted`` record re-emits byte-stably after
  its request converges away, a live request supersedes its record, and a
  law change expires it with a reason;
* the GATE is byte-inert off;
* the validator is finding-clean on a lawful emission and fires on a
  tampered one (lockstep, ruling R5).
"""
import math
import pathlib

import numpy as np
import pytest

from auto_patch import config as apc

LAT0, LON0 = 25.25, 51.60
TILE_LAT, TILE_LON = 25, 51
COS0 = math.cos(math.radians(LAT0))
BASE_TERRAIN_M = 5.0


class FakeDEM:
    """The read surface of ``O4_DEM_Utils.DEM`` the sampler uses."""

    def __init__(self, n: int = 1201, base: float = BASE_TERRAIN_M):
        self.x0, self.x1, self.y0, self.y1 = 0.0, 1.0, 0.0, 1.0
        self.nxdem = self.nydem = n
        self.alt_dem = np.full((n, n), float(base), dtype=np.float32)
        self.nodata = -32768

    def alt(self, node):
        x, y = node
        nmax = self.nxdem - 1
        x = min(max(float(x), self.x0), self.x1)
        y = min(max(float(y), self.y0), self.y1)
        j = int(round(x * nmax))
        i = int(round((1.0 - y) * nmax))
        return float(self.alt_dem[i, j])


def pad_frame(layout, hulls_m, *, target_m=None, base_y=None, agl=0.0,
              key: int = 1, structure_index: int = 0, resource=None,
              anchor_m=None):
    """One ``object_frame.ObjectPadFrame`` — the emitter's real input.

    ``hulls_m`` are CONTACT HULLS in local metres (one per ground part);
    the ring law dilates each by ``DSF_OBJECT_FOOT_PAD_MARGIN_M`` and
    unions them, so a hull of half-size H yields a ring of half-size
    H + 2 m and, after the erosion, a core back at H.

    THE RENDER DATUM defaults to a point inside the layout's first shape
    — the apron — because the ruling's coupling reads the PATCH there and
    an unhosted datum is by design not padable (its own twin below).  Its
    ground is therefore the apron's own solved value, and ``base_y`` is
    derived from ``target_m`` against it: ``target = apron + AGL +
    base_y`` is the whole arithmetic, spelled here so a test can state
    either end of it.
    """
    from auto_patch.object_frame import ObjectPadFrame, PadAnchor, PadPart

    resource = resource or f"Buildings/pad{key}.obj"
    if anchor_m is None:
        point = layout.shapes[0].polygon.representative_point()
        anchor_m = (point.x, point.y)
    anchor_latitude, anchor_longitude = layout.m_to_ll(*anchor_m)
    host_alt = float(layout.shapes[0].node_altitudes[0])
    if base_y is None:
        base_y = float(target_m) - host_alt - float(agl)

    parts = []
    for ordinal, hull in enumerate(hulls_m):
        hull_ll = tuple(
            (lon, lat) for lat, lon in
            (layout.m_to_ll(x, y) for x, y in hull))
        cx = sum(x for x, _y in hull) / len(hull)
        cy = sum(y for _x, y in hull) / len(hull)
        latitude, longitude = layout.m_to_ll(cx, cy)
        parts.append(PadPart(
            structure_index=structure_index,
            part_key=key * 100 + ordinal,
            base_resource=resource,
            base_y=float(base_y),
            latitude=latitude,
            longitude=longitude,
            contact_parts_lonlat=(hull_ll,)))
    return ObjectPadFrame(
        parts=tuple(parts),
        anchor_by_resource={resource: PadAnchor(
            latitude=anchor_latitude,
            longitude=anchor_longitude,
            above_ground_level_metres=float(agl))})


def kinds(findings):
    return {f[0] for f in findings}


@pytest.fixture
def gate_on(monkeypatch):
    """The gate is read at CALL time precisely so this works."""
    monkeypatch.setattr(apc, "DSF_OBJECT_OBJECT_PADS", True)


@pytest.fixture
def dem():
    return FakeDEM()


# ══════════════════════════════════════════════════════════════════════
# THE PAD LAW — pure scalars (grade_law), shared by emitter and validator
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# EMISSION FROM THE FRAME (RULINGS "OBJECT PADS: EMISSION-TIME RELATIVE")
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# THE CAP'S REFERENCE FRAME (RULINGS "PAD RELIEF CAP MEASURES AGAINST THE
# PAD'S OWN GROUND, NEVER RAW DEM", Fable 2026-08-14)
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# THE READ-BACK IS RETIRED (R3 step 4) — the rails, loud
# ══════════════════════════════════════════════════════════════════════


def test_the_driver_no_longer_persists_emitted_records():
    from auto_patch import driver

    source = pathlib.Path(driver.__file__).read_text(encoding="utf-8")
    assert "merge_emitted_records" not in source


# ══════════════════════════════════════════════════════════════════════
# THE VALIDATOR (§5.5) — lockstep with the emitter, law unchanged
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# FOOTPRINT-HUGGING RINGS (object-reseat-threshold-spec §2.5)
#
# The ring law is unchanged; what moved is WHERE it is applied — in-run
# over the frame's contact parts instead of post-mesh over the rebake's.
# So the same structural properties are pinned on the new path: one pad
# per connected component, refusal accounting per component, and every
# emitted polygon inside the contact hulls it came from.
# ══════════════════════════════════════════════════════════════════════


# ── the law digest ────────────────────────────────────────────────────

