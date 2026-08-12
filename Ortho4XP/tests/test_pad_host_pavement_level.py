"""Pad-in-solved-pavement HOST LEVEL re-level (user 2026-07-10, round 6 site 3).

A building pad embedded in / abutting SOLVED pavement must sit FLAT at the level
the HOST pavement solved to at the contact — not at a raw-DEM frontage seat that
leaves the flat pad in a pit the apron humps around (CYXY apron #129 →
building8: a -333 %/1.1 m step, "a big hump in this apron").

Synthetic fixture (no airport build): an apron edge solved at a body level, a
flat pad abutting it seated at a PIT value (below the body), and a run of shared
"lip" apron nodes contaminated to the pit value.  The re-level must:

  * seat the pad FLAT at the host BODY level (adopt FROM the host);
  * lift the contaminated shared lip to the body level (no emit cliff);
  * leave the host BODY untouched (pad adopts from host, never the reverse);
  * leave a pad already agreeing with its host, and a pad far from any solved
    pavement, UNCHANGED;
  * honour the ``O4_PAD_HOST_PAVEMENT_LEVEL`` gate (off → no-op).
"""
import os

import pytest
from shapely.geometry import Polygon

from auto_patch.config import (
    PAD_HOST_LEVEL_TRIGGER_M, APRON_MAX_GRADE,
)
from auto_patch.layout import BuiltShape, ROLE_APRON, ROLE_BUILDING
from auto_patch.elevation_per_surface.route_profile.anchors import (
    relevel_pads_to_host_pavement,
)

BODY = 100.0                       # host apron solved (body) level
PIT = 96.5                         # DEM-low pad seat (a 3.5 m pit vs the body)


class _FakeLayout:
    def __init__(self, shapes):
        self.shapes = shapes


def _apron_with_lip():
    """An apron whose top edge (y=10) abuts the pad's bottom edge.

    Body vertices sit at ``BODY`` a couple of metres either side of the pad
    corners (so the pad has host BODY within the contact radius), and two
    vertices coincident with the pad corners are contaminated to ``PIT`` (the
    shared lip the old seat dragged down).
    """
    ring = [
        (0.0, 0.0), (40.0, 0.0), (40.0, 10.0),
        (32.0, 10.0),            # body, ~2 m right of the (30,10) pad corner
        (30.0, 10.0),            # shared lip @ pad corner  → PIT
        (28.0, 10.0),            # body, ~2 m left of (30,10)
        (22.0, 10.0),            # body, ~2 m right of (20,10)
        (20.0, 10.0),            # shared lip @ pad corner  → PIT
        (18.0, 10.0),            # body, ~2 m left of (20,10)
        (0.0, 10.0),
    ]
    alt = [BODY, BODY, BODY,
           BODY, PIT, BODY, BODY, PIT, BODY, BODY]
    poly = Polygon(ring)
    return BuiltShape(polygon=poly, role=ROLE_APRON,
                      node_altitudes=alt + [alt[0]])


def _pad(x0, y0, x1, y1, alt):
    return BuiltShape(polygon=Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]),
                      role=ROLE_BUILDING, altitude=alt)


def _pad_level(s):
    if s.altitude is not None:
        return s.altitude
    vals = [v for v in (s.node_altitudes or []) if v is not None]
    return sum(vals) / len(vals) if vals else None


def test_embedded_pit_pad_adopts_host_body(monkeypatch):
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _apron_with_lip()
    pad = _pad(20.0, 10.0, 30.0, 18.0, PIT)        # abuts the apron top edge
    layout = _FakeLayout([apron, pad])

    n = relevel_pads_to_host_pavement(layout)
    assert n == 1, "the embedded pit pad must be re-levelled"

    # (1) The pad seats FLAT at the host BODY level.
    assert pad.altitude == pytest.approx(BODY, abs=0.01)

    # (2) The contaminated shared lip is lifted to the body level (no cliff).
    lip_vals = [apron.node_altitudes[4], apron.node_altitudes[7]]
    assert all(abs(v - BODY) < 0.01 for v in lip_vals), (
        f"shared lip not lifted: {lip_vals}")

    # (3) The host BODY is untouched (pad adopts from host, never the reverse).
    body_idx = [0, 1, 2, 3, 5, 6, 8, 9]
    assert all(abs(apron.node_altitudes[i] - BODY) < 0.01 for i in body_idx)

    # (4) The step at the contact is gone — pad and host lip now agree, so the
    #     residual disagreement is within the apron grade cap over the contact.
    step = abs(_pad_level(pad) - max(lip_vals))
    assert step <= APRON_MAX_GRADE * 100.0 * 0.5, (
        f"a step of {step:.2f} m survives at the pad↔host contact")


def test_pad_already_agreeing_is_untouched(monkeypatch):
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _apron_with_lip()
    # Seat the pad already at the body level; its lip is not contaminated.
    for i in (4, 7):
        apron.node_altitudes[i] = BODY
    pad = _pad(20.0, 10.0, 30.0, 18.0, BODY)
    layout = _FakeLayout([apron, pad])

    n = relevel_pads_to_host_pavement(layout)
    assert n == 0
    assert pad.altitude == pytest.approx(BODY, abs=0.01)


def test_pad_far_from_pavement_is_untouched(monkeypatch):
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _apron_with_lip()
    pad = _pad(500.0, 500.0, 510.0, 510.0, PIT)    # nowhere near the apron
    layout = _FakeLayout([apron, pad])

    n = relevel_pads_to_host_pavement(layout)
    assert n == 0
    assert pad.altitude == pytest.approx(PIT, abs=0.01)


def test_gate_off_is_noop(monkeypatch):
    # The env override died 2026-08-05; ``config.PAD_HOST_PAVEMENT_LEVEL``
    # is the law's own switch and the function reads it at call time.
    import auto_patch.config as _cfg
    monkeypatch.setattr(_cfg, "PAD_HOST_PAVEMENT_LEVEL", False)
    apron = _apron_with_lip()
    pad = _pad(20.0, 10.0, 30.0, 18.0, PIT)
    layout = _FakeLayout([apron, pad])

    n = relevel_pads_to_host_pavement(layout)
    assert n == 0
    assert pad.altitude == pytest.approx(PIT, abs=0.01)
    # lip stays contaminated (byte-identical to the pre-fix behaviour)
    assert apron.node_altitudes[4] == pytest.approx(PIT, abs=0.01)


# ══════════════════════════════════════════════════════════════════════
# R19-1 — A PAD WELDED INTO A COARSE HOST RING FINDS ITS BODY
# ══════════════════════════════════════════════════════════════════════
#
# The class this removes: the host-body probe only ever looked within
# ``PAD_HOST_LEVEL_CONTACT_M`` (2.5 m) of the pad ring.  A pad WELDED INTO
# a coarse host ring has no differing host vertex there at all — every
# host node near it IS a pad node carrying the pad's own value — and the
# host's first body vertex sits one long ring edge away.  HECA
# building114: contacts -771/-772/-773/-774 all at the pad's 88.50, body
# -767 at 85.63 7.84 m off; the pad never re-levelled and the apron's
# 36.6 % edge and 14 building|building 2.87 m rows stood.  53 of HECA's
# 214 pads share the geometry.

WELD_BODY = 85.63                  # the host apron's body level
WELD_PAD = 88.50                   # building114's stranded pad level


def _welded_apron(body_arc_m=7.84, body=WELD_BODY, lip=WELD_PAD):
    """A host apron ring whose vertices at the pad corners ARE the pad's
    (welded lip run), with the first body vertex ``body_arc_m`` further
    along the ring — the building114 geometry."""
    ring = [
        (0.0, 0.0), (60.0, 0.0), (60.0, 10.0),
        (30.0 + body_arc_m, 10.0),   # first body vertex past the run
        (30.0, 10.0),                # welded lip @ pad corner
        (20.0, 10.0),                # welded lip @ pad corner
        (20.0 - body_arc_m, 10.0),   # first body vertex the other way
        (0.0, 10.0),
    ]
    alt = [body, body, body, body, lip, lip, body, body]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                      node_altitudes=alt + [alt[0]])


def test_a_pad_welded_into_a_coarse_host_ring_finds_its_body(monkeypatch):
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _welded_apron()
    pad = _pad(20.0, 10.0, 30.0, 18.0, WELD_PAD)
    layout = _FakeLayout([apron, pad])

    assert relevel_pads_to_host_pavement(layout) == 1, (
        "the pad has NO differing host vertex within the contact radius — "
        "the lip-run walk is the only thing that can find its body")
    assert pad.altitude == pytest.approx(WELD_BODY, abs=0.01)
    # The host BODY is untouched (the pad adopts FROM the host).
    assert apron.node_altitudes[3] == pytest.approx(WELD_BODY, abs=0.01)
    assert apron.node_altitudes[6] == pytest.approx(WELD_BODY, abs=0.01)


def test_the_field_sample_has_no_reach(monkeypatch):
    """R19-1 RE-RULED (2026-08-12).  The pad adopts its HOST'S SOLVED
    SURFACE at its own ring — a surface has a value everywhere, so there
    is no radius to satisfy.  This twin used to assert the opposite (a
    bounded ring walk, ``PAD_HOST_BODY_REACH_M``), and the bound is
    exactly what missed HECA building114 twice: its host body sits
    16.59 m out.  Here the body is 30 m out and the pad still finds it.
    """
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _welded_apron(body_arc_m=30.0)
    pad = _pad(20.0, 10.0, 30.0, 18.0, WELD_PAD)
    layout = _FakeLayout([apron, pad])

    assert relevel_pads_to_host_pavement(layout) == 1, (
        "a host body 30 m out is still the host's surface at this pad — "
        "the reach cap is retired, not renamed")
    assert pad.altitude == pytest.approx(WELD_BODY, abs=0.01)


def test_a_neighbour_pads_lip_is_never_the_value(monkeypatch):
    """WHY THE REACH COULD BE RETIRED: neighbour-swap is impossible by
    construction.  A neighbouring pad's lip sits NEARER this pad than
    the host's own body does — the geometry that made the vertex-hunting
    mechanisms swap two pads (HECA 140↔141, 146↔151, 210↔211) — and it
    is still never the value read, because the field is ONE host
    polygon's own vertex set with this pad's lips removed by value.

    A mutation that goes back to "nearest differing vertex" takes the
    neighbour's 120.00 and fails here."""
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    NEIGHBOUR = 120.0
    ring = [
        (0.0, 0.0), (60.0, 0.0), (60.0, 10.0),
        (34.0, 10.0),                 # the NEIGHBOUR pad's lip, 4 m off
        (30.0, 10.0), (20.0, 10.0),   # this pad's welded lip run
        (-14.0, 10.0),                # the host's own body, 34 m off
        (0.0, 10.0),
    ]
    alt = [WELD_BODY, WELD_BODY, WELD_BODY,
           NEIGHBOUR, WELD_PAD, WELD_PAD, WELD_BODY, WELD_BODY]
    apron = BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                       node_altitudes=alt + [alt[0]])
    # The neighbour's lip is a WELD: the apron vertex at (34,10) is a
    # vertex of the neighbour pad's own ring, which is what makes it that
    # pad's value rather than the host's surface.
    neighbour = BuiltShape(
        polygon=Polygon([(30.0, 10.0), (34.0, 10.0), (38.0, 10.0),
                         (38.0, 18.0), (30.0, 18.0)]),
        role=ROLE_BUILDING, altitude=NEIGHBOUR)
    pad = _pad(20.0, 10.0, 30.0, 18.0, WELD_PAD)
    layout = _FakeLayout([apron, neighbour, pad])

    relevel_pads_to_host_pavement(layout)
    assert pad.altitude == pytest.approx(WELD_BODY, abs=0.6), (
        f"the pad took {pad.altitude} — the neighbour's lip is nearer "
        f"than the host body, and a vertex hunt would read it")
    assert abs(pad.altitude - NEIGHBOUR) > 5.0


def test_a_lawful_lip_run_on_a_flat_host_moves_nothing(monkeypatch):
    """LIPS STAY LIPS.  A pad welded into a host that agrees with it
    reads AGREEMENT through the walk too — the vertex past the run is
    within the trigger, so there is no body and no re-level."""
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _welded_apron(body=WELD_PAD + 0.2, lip=WELD_PAD)
    pad = _pad(20.0, 10.0, 30.0, 18.0, WELD_PAD)
    layout = _FakeLayout([apron, pad])

    assert relevel_pads_to_host_pavement(layout) == 0
    assert pad.altitude == pytest.approx(WELD_PAD, abs=0.01)


# ══════════════════════════════════════════════════════════════════════
# R19-3 — OBJECT PADS RECONCILE WITH THE HOST
# ══════════════════════════════════════════════════════════════════════
#
# An object pad's target is the OBJECT's rendered/draped ground
# (``object_anchor.target_ground_metres``) and NOTHING reconciled it with
# the pavement the solve produced: HECA's object_pad:56 sat at 105.51
# welded to an apron solved to ~93.5, and the apron ring carried its
# 106 m values into the airport's two worst edges (148.4 % over 8.49 m,
# 55.6 % over 22.39 m).  Same machinery, by role, at the pad's own relief
# budget (``DSF_OBJECT_PAD_MAX_RELIEF_M``).

OPAD_HOST = 93.45                  # the apron's solved body level
OPAD_TARGET = 105.51               # object_pad:56's draped target


def _object_pad_group(core_alt, blend_alts, x0=20.0, y0=10.0):
    """A pad REQUEST as the emitter writes it: a flat core plus one blend
    plate ramping out of it (``object_pad:7`` / ``object_pad_blend:7``)."""
    from auto_patch.layout import ROLE_OBJECT_PAD
    core = BuiltShape(
        polygon=Polygon([(x0, y0), (x0 + 8, y0), (x0 + 8, y0 + 8),
                         (x0, y0 + 8)]),
        role=ROLE_OBJECT_PAD, ref="object_pad:7",
        node_altitudes=[core_alt] * 5)
    blend = BuiltShape(
        polygon=Polygon([(x0 - 2, y0 - 2), (x0 + 10, y0 - 2),
                         (x0 + 10, y0 + 10), (x0 - 2, y0 + 10)]),
        role=ROLE_OBJECT_PAD, ref="object_pad_blend:7",
        node_altitudes=list(blend_alts) + [blend_alts[0]])
    return core, blend


def _welded_object_apron(contact_alt, body=OPAD_HOST, body_arc_m=8.49):
    """The apron ring at an object pad's contact: the welded nodes carry
    the PAD's value (the contamination), the body is one long ring edge
    further along."""
    ring = [
        (0.0, -30.0), (60.0, -30.0), (60.0, 8.0),
        (30.0 + body_arc_m, 8.0),
        (30.0, 8.0), (20.0, 8.0),
        (20.0 - body_arc_m, 8.0), (0.0, 8.0),
    ]
    alt = [body, body, body, body, contact_alt, contact_alt, body, body]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                      node_altitudes=alt + [alt[0]])


def test_an_over_budget_object_pad_adopts_the_host_level(monkeypatch):
    from auto_patch.layout import ROLE_OBJECT_PAD
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    core, blend = _object_pad_group(OPAD_TARGET,
                                    [OPAD_TARGET + 0.5] * 4)
    apron = _welded_object_apron(OPAD_TARGET + 0.55)
    layout = _FakeLayout([apron, core, blend])

    n = relevel_pads_to_host_pavement(layout, pad_role=ROLE_OBJECT_PAD)
    assert n == 1, (
        "a pad 12 m above the pavement it welds to is exactly what "
        "nothing reconciled")
    assert core.node_altitudes[0] == pytest.approx(OPAD_HOST, abs=0.01)
    # PAD + BLEND: the blend moves by the SAME delta, keeping its ramp.
    delta = OPAD_HOST - OPAD_TARGET
    assert blend.node_altitudes[0] == pytest.approx(
        OPAD_TARGET + 0.5 + delta, abs=0.01)
    # The host BODY is untouched.
    assert apron.node_altitudes[3] == pytest.approx(OPAD_HOST, abs=0.01)


def test_an_object_pad_within_its_relief_budget_keeps_its_target(
        monkeypatch):
    """Within the budget the pad keeps its own value — an object seated a
    metre or two above its apron is the relief the pad exists to build."""
    from auto_patch.config import DSF_OBJECT_PAD_MAX_RELIEF_M
    from auto_patch.layout import ROLE_OBJECT_PAD
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    near = OPAD_HOST + float(DSF_OBJECT_PAD_MAX_RELIEF_M) - 0.5
    core, blend = _object_pad_group(near, [near + 0.2] * 4)
    apron = _welded_object_apron(near + 0.25)
    layout = _FakeLayout([apron, core, blend])

    assert relevel_pads_to_host_pavement(
        layout, pad_role=ROLE_OBJECT_PAD) == 0
    assert core.node_altitudes[0] == pytest.approx(near, abs=0.01)


def test_the_building_pass_never_touches_an_object_pad(monkeypatch):
    """ONE implementation, TWO roles — and each pass moves only its own.
    A building-role pass that swept object pads would re-level them at
    the 0.5 m trigger instead of their 3 m relief budget."""
    from auto_patch.layout import ROLE_OBJECT_PAD
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    core, blend = _object_pad_group(OPAD_TARGET, [OPAD_TARGET + 0.5] * 4)
    apron = _welded_object_apron(OPAD_TARGET + 0.55)
    layout = _FakeLayout([apron, core, blend])

    assert relevel_pads_to_host_pavement(layout) == 0
    assert core.node_altitudes[0] == pytest.approx(OPAD_TARGET, abs=0.01)
    assert relevel_pads_to_host_pavement(
        layout, pad_role=ROLE_OBJECT_PAD) == 1


def _dense_welded_apron(body=WELD_BODY, lip=WELD_PAD, body_arc_m=7.84):
    """The PRODUCTION geometry: the host ring is denser than the pad's
    contact radius, so the lip run continues past it — vertices still at
    the pad's value that are NOT contacts of the pad."""
    ring = [
        (0.0, 0.0), (60.0, 0.0), (60.0, 10.0),
        (30.0 + body_arc_m, 10.0),   # body
        (33.0, 10.0),                # lip value, OUTSIDE the contact radius
        (30.0, 10.0), (25.0, 10.0), (20.0, 10.0),   # welded lip run
        (17.0, 10.0),                # lip value, outside the radius
        (20.0 - body_arc_m, 10.0),   # body
        (0.0, 10.0),
    ]
    alt = [body, body, body, body, lip, lip, lip, lip, lip, body, body]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                      node_altitudes=alt + [alt[0]])


def test_the_lip_run_is_defined_by_value_not_by_contact(monkeypatch):
    """R19-1 attempt 2, measured at HECA building114: a host ring denser
    than ``PAD_HOST_LEVEL_CONTACT_M`` carries the pad's own value at
    vertices that are not contacts.  Stopping at the first NON-CONTACT
    vertex reads agreement and the pad keeps its pit value while the
    host body sits metres below.  The run is every vertex still AT the
    pad's value; the reach cap is what bounds it."""
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    apron = _dense_welded_apron()
    pad = _pad(20.0, 10.0, 30.0, 18.0, WELD_PAD)
    layout = _FakeLayout([apron, pad])

    assert relevel_pads_to_host_pavement(layout) == 1, (
        "the walk stopped on a lip vertex that merely sat outside the "
        "contact radius — the HECA building114 class")
    assert pad.altitude == pytest.approx(WELD_BODY, abs=0.01)


def test_the_value_is_the_surface_not_the_nearest_vertex(monkeypatch):
    """THE RE-RULING'S OWN TEST.  "Evaluate the host polygon's solved
    elevation FIELD at the pad's ring positions" is not "find the right
    vertex": on a host that is not flat, the surface AT the pad is a
    MIXTURE of its ring values, and no vertex carries that number.

    The host's low body (80.00) is nearer to every pad ring position
    than its high body (90.00), so a nearest-vertex hunt — either of the
    mechanisms this law replaced — reads a flat 80.00.  The surface
    reads the mixture."""
    monkeypatch.setenv("O4_PAD_HOST_PAVEMENT_LEVEL", "1")
    LOW, HIGH, PIT = 80.0, 90.0, 100.0
    ring = [
        (-40.0, -30.0), (100.0, -30.0), (100.0, 10.0),
        (75.0, 10.0),                 # HIGH body, further from every
        (30.0, 10.0), (20.0, 10.0),   # the pad's welded lip run
        (0.0, 10.0),                  # LOW body, nearer to every
        (-40.0, 10.0),
    ]
    alt = [LOW, HIGH, HIGH, HIGH, PIT, PIT, LOW, LOW]
    apron = BuiltShape(polygon=Polygon(ring), role=ROLE_APRON,
                       node_altitudes=alt + [alt[0]])
    pad = _pad(20.0, 10.0, 30.0, 18.0, PIT)
    layout = _FakeLayout([apron, pad])

    assert relevel_pads_to_host_pavement(layout) == 1
    # Measured: the surface reads 82.76 here; the nearest body vertex
    # is 80.00 at every one of the pad's ring positions.
    assert pad.altitude > LOW + 1.0, (
        f"the pad took {pad.altitude} — that is the NEAREST body "
        f"vertex's value, not the host's surface, which carries the "
        f"high body too")
    assert pad.altitude < HIGH - 1.0
