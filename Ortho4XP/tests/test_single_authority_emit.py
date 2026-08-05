"""Single-authority emission (``O4_SINGLE_AUTHORITY_EMIT``).

The emit consensus averages every claim inside the winning precedence
tier, so any shape carrying a slightly different post-solve value at a
shared vertex MOVES the node — a second grading pass at emit, minting a
value no law produced and no solver computed.  The single-solve ruling
(RULINGS 2026-08-03, "EMITTERS EMIT, NEVER GRADE") retires it in favour
of ONE author per node, chosen by ``AUTHORITY_PRECEDENCE``.

The measured case these twins encode is the four-authority runway
vertex: HECA node (30.13693252295, 31.40386604192) emitted 63.73 -> 63.79
with the solver-side preserved set PROVEN held — runway 05L/23R + apron +
junction + a strip averaged a runway vertex the solver never moved.  The
acceptance is identity to the AUTHORITY, deliberately not to the old
bytes.

The gate defaults OFF and the OFF path must stay byte-inert: the report
arm reproduced all five campaign anchors exactly.
"""
import json
import re
import tempfile
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from auto_patch.layout import (
    AUTHORITY_PRECEDENCE,
    BuiltShape,
    PavementLayout,
    ROLE_APRON,
    ROLE_BUILDING,
    ROLE_GRADED_STRIP,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_JUNCTION,
    ROLE_RUNWAY,
    ROLE_SERVICE_ROAD,
    authority_rank,
)

# The shared vertex every shape below claims, and the per-role values
# they claim it with (all inside VERTEX_ALT_MERGE_TOL_M = 1.0 so the
# no-stacked-nodes hard merge interns ONE node).
RUNWAY_Z = 63.73
JUNCTION_Z = 63.79
APRON_Z = 63.85
STRIP_Z = 63.91


def _emit(layout, path):
    layout.to_osm(path)
    return Path(path).read_text()


def _node_alt_at_origin(text):
    """alt_abs of the node at the projection anchor (the shared vertex).

    The anchor projects to (0, 0), so the shared corner is the node whose
    lat/lon round-trips to the anchor.
    """
    node_re = re.compile(
        r"<node id='(-?\d+)'[^>]*lat='([^']+)' lon='([^']+)'"
        r"[^>]*?>\s*<tag k='alt_abs' v='([^']+)'", re.DOTALL)
    best = None
    for m in node_re.finditer(text):
        lat, lon, alt = (float(m.group(2)), float(m.group(3)),
                         float(m.group(4)))
        d = abs(lat - 51.87) + abs(lon - (-0.37))
        if best is None or d < best[0]:
            best = (d, alt)
    assert best is not None, "no valued node emitted"
    return best[1]


def _four_authority_layout():
    """Four shapes meeting at the origin, each claiming it differently.

    Quadrant squares: the runway (I), junction (III), apron (II) and a
    terrain strip (IV).  Every ring's first vertex is the shared corner,
    so ``node_altitudes[0]`` is that shape's claim on it.
    """
    layout = PavementLayout(icao="KFAKE", anchor=(51.87, -0.37))
    for role, ref, ring, z in (
            (ROLE_RUNWAY, "rwy",
             [(0, 0), (10, 0), (10, 10), (0, 10)], RUNWAY_Z),
            (ROLE_JUNCTION, "jct",
             [(0, 0), (0, -10), (-10, -10), (-10, 0)], JUNCTION_Z),
            (ROLE_APRON, "apr",
             [(0, 0), (-10, 0), (-10, 10), (0, 10)], APRON_Z),
            (ROLE_GRADED_STRIP, "strip",
             [(0, 0), (10, 0), (10, -10), (0, -10)], STRIP_Z)):
        layout.shapes.append(BuiltShape(
            polygon=Polygon(ring), role=role, ref=ref,
            node_altitudes=[z, z, z, z, z]))
    return layout


def _emit_origin(tmp_path, monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    for k in ("O4_SINGLE_AUTHORITY_EMIT", "O4_SINGLE_AUTHORITY_SOFT",
              "O4_EMIT_DIVERGENCE_CENSUS"):
        if k not in env:
            monkeypatch.delenv(k, raising=False)
    out = str(tmp_path / "p.osm")
    return _node_alt_at_origin(_emit(_four_authority_layout(), out))


# ── precedence table ────────────────────────────────────────────────────

def test_precedence_is_airside_first_and_total():
    """Runway outranks taxi outranks apron outranks landside; unnamed
    roles tail.  Airside-is-king as constraint DIRECTION."""
    assert authority_rank(ROLE_RUNWAY) < authority_rank(ROLE_JUNCTION)
    assert authority_rank(ROLE_JUNCTION) < authority_rank(ROLE_APRON)
    assert authority_rank(ROLE_APRON) < authority_rank(ROLE_BUILDING)
    assert authority_rank(ROLE_BUILDING) < authority_rank(ROLE_SERVICE_ROAD)
    assert (authority_rank(ROLE_SERVICE_ROAD)
            < authority_rank(ROLE_GROUNDSIDE_PAVEMENT))
    # A soft/terrain role is not in the table and must tail every
    # named authority without raising.
    assert (authority_rank(ROLE_GROUNDSIDE_PAVEMENT)
            < authority_rank(ROLE_GRADED_STRIP))
    assert authority_rank("a_role_that_does_not_exist") == len(
        AUTHORITY_PRECEDENCE)
    # Total order: no two named roles share a rank.
    ranks = [authority_rank(r) for r in AUTHORITY_PRECEDENCE]
    assert len(set(ranks)) == len(ranks)


# ── the four-authority runway vertex ────────────────────────────────────

def test_gate_off_emits_the_tier_mean(tmp_path, monkeypatch):
    """DEFAULT path unchanged: the shared vertex is the mean of the three
    AUTHORITY claims (the strip is a soft receiver and is excluded)."""
    got = _emit_origin(tmp_path, monkeypatch)
    expected = (RUNWAY_Z + JUNCTION_Z + APRON_Z) / 3.0
    assert got == pytest.approx(expected, abs=1e-6)
    # ...and that mean is NOT any shape's own value — the minted value.
    assert got != pytest.approx(RUNWAY_Z, abs=1e-6)


def test_gate_on_runway_vertex_is_the_runway_value_exactly(
        tmp_path, monkeypatch):
    """THE ACCEPTANCE: identity to the AUTHORITY.  With four claimants the
    runway supplies the value verbatim — the consensus class is 0, not a
    0.06 m compromise."""
    got = _emit_origin(tmp_path, monkeypatch,
                       O4_SINGLE_AUTHORITY_EMIT="1")
    assert got == pytest.approx(RUNWAY_Z, abs=1e-9)


def test_gate_on_does_not_average_when_runway_absent(
        tmp_path, monkeypatch):
    """Precedence, not position: drop the runway and the JUNCTION (next
    airside rank) authors — still no mean."""
    monkeypatch.setenv("O4_SINGLE_AUTHORITY_EMIT", "1")
    layout = _four_authority_layout()
    layout.shapes = [s for s in layout.shapes if s.ref != "rwy"]
    out = str(tmp_path / "p.osm")
    got = _node_alt_at_origin(_emit(layout, out))
    assert got == pytest.approx(JUNCTION_Z, abs=1e-9)


# ── the divergence census ───────────────────────────────────────────────

def test_report_mode_is_write_only(tmp_path, monkeypatch):
    """Report mode computes the author but emits the legacy mean: the
    patch is byte-identical to a plain build and the census is the ONLY
    observable difference.  This is what made the report arm provable
    against the campaign anchors."""
    plain = str(tmp_path / "plain.osm")
    monkeypatch.delenv("O4_SINGLE_AUTHORITY_EMIT", raising=False)
    monkeypatch.delenv("O4_EMIT_DIVERGENCE_CENSUS", raising=False)
    _emit(_four_authority_layout(), plain)

    census = tmp_path / "div.json"
    reported = str(tmp_path / "reported.osm")
    monkeypatch.setenv("O4_EMIT_DIVERGENCE_CENSUS", str(census))
    _emit(_four_authority_layout(), reported)

    assert Path(reported).read_bytes() == Path(plain).read_bytes()
    assert census.exists()
    payload = json.loads(census.read_text())
    assert payload["mode"] == "report"
    assert payload["n_unauthored"] == 0
    row = next(r for r in payload["rows"]
               if r["author_role"] == ROLE_RUNWAY)
    assert row["author"] == pytest.approx(RUNWAY_Z, abs=1e-9)
    assert row["mean"] == pytest.approx(
        (RUNWAY_Z + JUNCTION_Z + APRON_Z) / 3.0, abs=1e-6)
    assert set(row["roles"]) == {ROLE_RUNWAY, ROLE_JUNCTION, ROLE_APRON}


def test_emit_mode_census_records_applied_mode(tmp_path, monkeypatch):
    census = tmp_path / "div.json"
    monkeypatch.setenv("O4_SINGLE_AUTHORITY_EMIT", "1")
    monkeypatch.setenv("O4_EMIT_DIVERGENCE_CENSUS", str(census))
    _emit(_four_authority_layout(), str(tmp_path / "p.osm"))
    assert json.loads(census.read_text())["mode"] == "emit"


# ── the pure-soft sub-gate ──────────────────────────────────────────────

def _two_strip_layout():
    """Two terrain strips sharing a corner and NO authority claimant."""
    layout = PavementLayout(icao="KFAKE", anchor=(51.87, -0.37))
    for ref, ring, z in (
            ("s1", [(0, 0), (10, 0), (10, 10), (0, 10)], 20.0),
            ("s2", [(0, 0), (0, -10), (-10, -10), (-10, 0)], 21.0)):
        layout.shapes.append(BuiltShape(
            polygon=Polygon(ring), role=ROLE_GRADED_STRIP, ref=ref,
            node_altitudes=[z, z, z, z, z]))
    return layout


@pytest.mark.parametrize("soft,expected", [("1", 20.0), ("0", 20.5)])
def test_pure_soft_tier_subgate(tmp_path, monkeypatch, soft, expected):
    """A node claimed ONLY by soft receivers has no authority to adopt
    from.  ``O4_SINGLE_AUTHORITY_SOFT=1`` (spec-literal, "the mean dies
    everywhere") authors it by shape order; "0" keeps the all-soft mean.
    Measured consequence at CYXY: authoring the pure-soft tier minted 6
    extra seam rows, so the choice is load-bearing and is the lead's."""
    monkeypatch.setenv("O4_SINGLE_AUTHORITY_EMIT", "1")
    monkeypatch.setenv("O4_SINGLE_AUTHORITY_SOFT", soft)
    monkeypatch.delenv("O4_EMIT_DIVERGENCE_CENSUS", raising=False)
    out = str(tmp_path / "p.osm")
    got = _node_alt_at_origin(_emit(_two_strip_layout(), out))
    assert got == pytest.approx(expected, abs=1e-6)


def test_authority_beats_soft_regardless_of_subgate(
        tmp_path, monkeypatch):
    """The soft sub-gate must never let a strip outrank pavement: the
    strip ADOPTS the authority value in both settings (weld ruling
    2026-07-09, unchanged by this round)."""
    for soft in ("0", "1"):
        got = _emit_origin(tmp_path, monkeypatch,
                           O4_SINGLE_AUTHORITY_EMIT="1",
                           O4_SINGLE_AUTHORITY_SOFT=soft)
        assert got == pytest.approx(RUNWAY_Z, abs=1e-9)
        assert got != pytest.approx(STRIP_Z, abs=1e-6)
