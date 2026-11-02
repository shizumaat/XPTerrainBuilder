"""Clip cache under concurrency (#1734) and sea-aware cover pruning
(#1735).

#1734: two clips sharing a corner cut at the same moment evicted each
other, and a reader whose clip vanished fell back to Overpass with the
extract on disk.  #1735: a grouping region whose sea-buffered polygon
alone reached part of a coastal box was kept over the leaves serving
all of its land.  Real (tiny) pbf files through the pyosmium cutter;
no network.
"""

from __future__ import annotations

import os
import threading

import O4_Land_Witness as LAND
import O4_OSM_Extract_Filter as FILTER
import O4_OSM_Extracts as EXTRACTS
import test_osm_extracts_store as STORE
from test_osm_extracts_store import store  # noqa: F401  (fixture)

# Two query boxes inside portugal sharing the clip corner +38-010 but
# not the clip box: the second reaches one degree further north.
SMALL_BOX = (38.0, -9.5, 39.0, -8.5)
TALL_BOX = (38.0, -9.5, 40.0, -8.5)
STATEMENTS = ['way["natural"="water"]']
PORTUGAL = [("portugal", None)]


def _portugal(tmp_path):
    return STORE.TestClipCutterDispatch._make_region_pbf(None, tmp_path)


def _serve(box):
    return EXTRACTS.osm_xml_from_local_extracts(STATEMENTS, box)


def _base(parts):
    return parts[0][:parts[0].rindex("-part")]


def _clip_present(box):
    return EXTRACTS._read_clip_parts(EXTRACTS._clip_path(
        PORTUGAL, EXTRACTS._clip_bounding_box([box]))) is not None


def _run_threads(target, argument_list):
    threads = [threading.Thread(target=target, args=(argument,))
               for argument in argument_list]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)


class TestConcurrentClips:
    def test_corner_sharing_clips_never_evict_each_other(
            self, store, tmp_path):  # noqa: F811
        """Concurrent cutters and readers of two areas sharing a corner:
        every read is extract-served, and both clips survive."""
        region_file = _portugal(tmp_path)
        expected = {
            box: FILTER.filter_extracts_to_osm_xml(
                [region_file], STATEMENTS, box)
            for box in (SMALL_BOX, TALL_BOX)}
        (results, errors) = ([], [])

        def worker(box):
            try:
                for _ in range(3):
                    results.append((box, _serve(box)))
            except Exception as error:  # surfaced below
                errors.append(error)

        _run_threads(worker, (SMALL_BOX, TALL_BOX) * 3)
        assert not errors
        assert len(results) == 18
        assert all(xml == expected[box] for (box, xml) in results)
        assert _clip_present(SMALL_BOX) and _clip_present(TALL_BOX)

    def test_concurrent_requests_for_one_area_cut_once(
            self, store, tmp_path, monkeypatch):  # noqa: F811
        _portugal(tmp_path)
        real_cut = EXTRACTS._cut_clip
        cuts = []

        def counting_cut(*args):
            cuts.append(args[2])
            return real_cut(*args)

        monkeypatch.setattr(EXTRACTS, "_cut_clip", counting_cut)
        _run_threads(_serve, [SMALL_BOX] * 6)
        assert len(cuts) == 1

    def test_vanished_clip_is_recut_never_overpass(
            self, store, tmp_path, monkeypatch):  # noqa: F811
        """A part deleted between the manifest read and the filter read
        (another process's prune) is re-cut from the extract on disk."""
        region_file = _portugal(tmp_path)
        assert _serve(SMALL_BOX) is not None
        parts = EXTRACTS._clip_for_query(PORTUGAL, [SMALL_BOX])
        real_filter = FILTER.filter_extracts_to_osm_xml
        state = {"deleted": False}

        def deleting_filter(paths, statements, boxes):
            if paths == parts and not state["deleted"]:
                state["deleted"] = True
                os.remove(parts[0])
            return real_filter(paths, statements, boxes)

        monkeypatch.setattr(FILTER, "filter_extracts_to_osm_xml",
                            deleting_filter)
        served = _serve(SMALL_BOX)
        assert state["deleted"]
        assert served == real_filter([region_file], STATEMENTS, SMALL_BOX)
        assert os.path.isfile(parts[0])


class TestSupersededClips:
    def test_refreshed_extract_prunes_old_clip_unless_in_use(
            self, store, tmp_path):  # noqa: F811
        region_file = _portugal(tmp_path)
        old = EXTRACTS._clip_for_query(PORTUGAL, [SMALL_BOX])
        other_area = EXTRACTS._clip_for_query(PORTUGAL, [TALL_BOX])
        stat = os.stat(region_file)
        os.utime(region_file, (stat.st_atime, stat.st_mtime + 100))
        with EXTRACTS._clip_in_use(_base(old)):
            new = EXTRACTS._clip_for_query(PORTUGAL, [SMALL_BOX])
        assert new != old
        assert os.path.isfile(old[0])          # in use: kept
        assert os.path.isfile(other_area[0])   # another area: kept
        EXTRACTS._prune_stale_clips(_base(new))
        assert not os.path.isfile(old[0])      # superseded: pruned
        assert os.path.isfile(other_area[0])


class TestSeaOnlyContributionPruned:
    # iberia alone reaches lat 34-36 west of lon -7.4; this box's
    # southern strip (35.5-36) is iberia's only unique part.
    BOX = (35.5, -9, 37, -8)

    def _cover(self, monkeypatch, land):
        monkeypatch.setattr(LAND, "holds_land", lambda geometry: land)
        regions = EXTRACTS.covering_regions(self.BOX)
        return [region_id for (region_id, _u) in regions]

    def test_grouping_region_falls_when_its_unique_part_is_sea(
            self, store, monkeypatch):  # noqa: F811
        assert self._cover(monkeypatch, False) == ["portugal"]

    def test_grouping_region_kept_when_its_unique_part_holds_land(
            self, store, monkeypatch):  # noqa: F811
        assert self._cover(monkeypatch, True) == ["iberia"]
