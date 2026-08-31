"""THE BRIDGE-DECK PIN IN THE CORE CLAMP (redesign spec §4).

RULINGS 2026-08-30c §5 — *"The deck's value is a PIN in the free-road
profile solve; the chain reaches it at ``SERVICE_ROAD_MAX_GRADE`` like
any other pinned end"* — RE-EXPRESSED.  That pass is retired (RULINGS
2026-08-31b) and general roads belong to the CORE, so the pin is a
clamped-station override inside ``O4_Vector_Utils.cap_lipschitz_profile``
and the §6 refusal is priced there too.

What the pin is FOR (2026-08-30d): not moving the deck — the deck sits at
the road solve's own level and the structure beneath holds bore datum —
but making the APPROACHES reach it at the cap instead of draping to
terrain and stepping at the abutment, and detecting the §6 case where
two abutment values cannot both be reached.
"""
from __future__ import annotations

import numpy
import pytest
from shapely.geometry import LineString, MultiLineString, Polygon

import O4_Vector_Utils as VECT

CAP = 0.08


def _grades(alt, s):
    ds = numpy.diff(s)
    return numpy.abs(numpy.diff(alt) / numpy.where(ds == 0, 1e-9, ds))


class TestTheUnpinnedClampIsUnchanged:

    def test_flat_terrain_stays_flat_and_returns_a_bare_array(self):
        """No pins offered ⇒ the old signature, byte-for-byte: one
        return value, and cap-lawful terrain is its own answer."""
        s = numpy.arange(0.0, 200.0, 10.0)
        z = numpy.zeros(len(s))
        out = VECT.cap_lipschitz_profile(s, z, CAP)
        assert not isinstance(out, tuple)
        assert float(numpy.abs(out - z).max()) == 0.0

    def test_an_empty_pin_list_is_no_pins(self):
        s = numpy.arange(0.0, 100.0, 10.0)
        z = numpy.zeros(len(s))
        out = VECT.cap_lipschitz_profile(s, z, CAP, [], [])
        assert not isinstance(out, tuple)


class TestThePinIsTakenExactlyAndReachedAtTheCap:

    def test_the_pinned_station_takes_the_deck_level(self):
        s = numpy.arange(0.0, 200.0, 10.0)
        z = numpy.zeros(len(s))
        out, rep = VECT.cap_lipschitz_profile(s, z, CAP, [10], [5.0])
        assert out[10] == pytest.approx(5.0, abs=0.01)
        assert rep["pins"] == 1 and not rep["refused"]

    def test_the_approaches_reach_it_at_the_cap_and_never_over(self):
        """§5's own sentence, as a measurement: every step of the pinned
        profile is <= the cap, and the steepest one IS the cap (the
        chain is reaching, not sagging)."""
        s = numpy.arange(0.0, 200.0, 10.0)
        z = numpy.zeros(len(s))
        out, _rep = VECT.cap_lipschitz_profile(s, z, CAP, [10], [5.0])
        g = _grades(out, s)
        assert g.max() <= CAP + 1e-9
        assert g.max() == pytest.approx(CAP, abs=1e-6)

    def test_a_slack_pin_leaves_the_profile_alone(self):
        """A deck at the level the road already holds moves nothing —
        which is 2026-08-30d's normal case (the pin's function is the
        refusal test, not a lever)."""
        s = numpy.arange(0.0, 200.0, 10.0)
        z = numpy.zeros(len(s))
        out, rep = VECT.cap_lipschitz_profile(s, z, CAP, [10], [0.0])
        assert float(numpy.abs(out - z).max()) < 0.01
        assert rep["max_pin_move_m"] < 0.01

    def test_two_reachable_pins_are_both_taken(self):
        """Two decks on one way, far enough apart for the cap."""
        s = numpy.arange(0.0, 400.0, 10.0)
        z = numpy.zeros(len(s))
        out, rep = VECT.cap_lipschitz_profile(
            s, z, CAP, [5, 35], [3.0, 6.0])
        assert out[5] == pytest.approx(3.0, abs=0.01)
        assert out[35] == pytest.approx(6.0, abs=0.01)
        assert not rep["refused"]
        assert _grades(out, s).max() <= CAP + 1e-9


class TestSixRefusesLoudlyAndLeavesThePreLawSurface:

    def test_two_pins_the_cap_cannot_both_reach_are_refused(self):
        """20 m apart and 10 m of level difference is 50 % — the road cap
        is 8 %.  RULINGS 2026-08-30c §6: the span is REFUSED and the
        pre-law surface stands."""
        s = numpy.arange(0.0, 200.0, 10.0)
        z = numpy.zeros(len(s))
        out, rep = VECT.cap_lipschitz_profile(
            s, z, CAP, [5, 7], [0.0, 10.0])
        assert rep["refused"] is True
        assert rep["worst_infeasibility_m"] > 0.01
        # the PRE-LAW surface: the unpinned clamp, untouched
        assert numpy.allclose(
            out, VECT.cap_lipschitz_profile(s, z, CAP))

    def test_the_refusal_carries_its_own_arithmetic(self):
        """§6 asks for sidecar evidence a reader can re-derive the
        refusal from — so the number, not just the verdict."""
        s = numpy.arange(0.0, 100.0, 10.0)
        z = numpy.zeros(len(s))
        _out, rep = VECT.cap_lipschitz_profile(
            s, z, CAP, [1, 2], [0.0, 20.0])
        assert set(("pins", "refused", "worst_infeasibility_m")) \
            <= set(rep)


class TestTheNetworkPassCarriesThePinsAndPublishesThem:

    def _net(self):
        # one straight way along constant latitude, ~0.01 deg long
        return MultiLineString([LineString([(0.0, 0.0), (0.01, 0.0)])])

    def _flat_dem(self, pts):
        return numpy.zeros(len(numpy.asarray(pts)))

    def test_a_station_inside_a_deck_footprint_is_pinned(self):
        deck = Polygon([(0.004, -0.001), (0.006, -0.001),
                        (0.006, 0.001), (0.004, 0.001)])
        lr = VECT.clamp_road_network(
            self._net(), self._flat_dem, CAP, 4.0,
            deck_pins=[(deck, 7.0, "-2070")])
        n_ways, n_pins, n_ref, worst = lr.deck_pin_summary()
        assert n_ways == 1 and n_pins >= 1 and n_ref == 0
        w = lr.ways[0]
        inside = [k for k, (x, y) in enumerate(w["points"])
                  if 0.004 <= x <= 0.006]
        assert inside, "the fixture must put a station under the deck"
        for k in inside:
            assert w["alt"][k] == pytest.approx(7.0, abs=0.01)

    def test_a_deck_nowhere_near_the_network_pins_nothing(self):
        far = Polygon([(0.5, 0.5), (0.51, 0.5), (0.51, 0.51), (0.5, 0.51)])
        lr = VECT.clamp_road_network(
            self._net(), self._flat_dem, CAP, 4.0,
            deck_pins=[(far, 7.0, "-1")])
        assert lr.deck_pin_summary() == (0, 0, 0, 0.0)
        assert lr.summary()["deck_pinned_stations"] == 0

    def test_the_summary_and_sidecar_publish_the_pins(self):
        deck = Polygon([(0.004, -0.001), (0.006, -0.001),
                        (0.006, 0.001), (0.004, 0.001)])
        lr = VECT.clamp_road_network(
            self._net(), self._flat_dem, CAP, 4.0,
            deck_pins=[(deck, 7.0, "-2070")])
        summary = lr.summary()
        assert summary["deck_pinned_ways"] == 1
        assert summary["deck_pins_refused"] == 0
        side = lr.sidecar(40.0, -3.0)
        assert side["summary"]["deck_pinned_stations"] >= 1
        pinned = [w for w in side["ways"] if w["deck_pins"]]
        assert pinned and pinned[0]["deck_pins"]["deck_ways"] == ["-2070"]

    def test_no_deck_pins_leaves_the_sidecar_shape_unchanged(self):
        lr = VECT.clamp_road_network(
            self._net(), self._flat_dem, CAP, 4.0)
        side = lr.sidecar(40.0, -3.0)
        assert all(w["deck_pins"] is None for w in side["ways"])
        assert side["summary"]["deck_pinned_ways"] == 0


class TestTheTransportFromAutoPatchToTheCore:
    """The pin's ONE authority: auto_patch publishes it in the patch
    sidecar it already writes, and the core reads it there.  Nothing
    re-derives a deck or its level."""

    def _write_sidecar(self, tmp_path, records):
        import json
        p = tmp_path / "LEMD_auto.patch.osm.axes.json"
        p.write_text(json.dumps({"road_bridge_decks": records}))
        return p

    def _tile(self):
        import types
        return types.SimpleNamespace(lat=40, lon=-4)

    def _read(self, monkeypatch, tmp_path, records):
        import O4_File_Names as FNAMES
        import O4_Vector_Map as VM
        self._write_sidecar(tmp_path, records)
        monkeypatch.setattr(FNAMES, "patch_dir",
                            lambda lat, lon: str(tmp_path))
        return VM.road_bridge_deck_pins(self._tile())

    def _ring(self):
        return [[40.4836, -3.5810], [40.4836, -3.5808],
                [40.4838, -3.5808], [40.4838, -3.5810],
                [40.4836, -3.5810]]

    def test_a_confirmed_terrain_deck_becomes_a_tile_relative_pin(
            self, monkeypatch, tmp_path):
        pins = self._read(monkeypatch, tmp_path, [{
            "way_id": "-2070", "verdict": "confirmed_terrain",
            "deck_pin_m": 603.18, "corridor_ll": self._ring()}])
        assert len(pins) == 1
        poly, level, wid = pins[0]
        assert (level, wid) == (603.18, "-2070")
        # tile-relative: (lon - tile.lon, lat - tile.lat)
        x0, y0, x1, y1 = poly.bounds
        assert x0 == pytest.approx(-3.5810 + 4, abs=1e-9)
        assert y0 == pytest.approx(40.4836 - 40, abs=1e-9)

    def test_an_unconfirmed_or_object_governed_deck_pins_nothing(
            self, monkeypatch, tmp_path):
        """§1's unconfirmed decks drape as today, and an object-governed
        span keeps the object law — neither carries a terrain pin."""
        assert self._read(monkeypatch, tmp_path, [
            {"way_id": "-1", "verdict": "unconfirmed",
             "deck_pin_m": 600.0, "corridor_ll": self._ring()},
            {"way_id": "-2", "verdict": "object_governed",
             "deck_pin_m": 600.0, "corridor_ll": self._ring()},
        ]) == []

    def test_a_record_missing_its_value_or_its_ring_pins_nothing(
            self, monkeypatch, tmp_path):
        assert self._read(monkeypatch, tmp_path, [
            {"way_id": "-1", "verdict": "confirmed_terrain",
             "deck_pin_m": None, "corridor_ll": self._ring()},
            {"way_id": "-2", "verdict": "confirmed_terrain",
             "deck_pin_m": 600.0, "corridor_ll": []},
        ]) == []

    def test_no_patch_dir_is_no_pins_and_never_an_error(
            self, monkeypatch, tmp_path):
        import O4_File_Names as FNAMES
        import O4_Vector_Map as VM
        monkeypatch.setattr(FNAMES, "patch_dir",
                            lambda lat, lon: str(tmp_path / "nope"))
        assert VM.road_bridge_deck_pins(self._tile()) == []
