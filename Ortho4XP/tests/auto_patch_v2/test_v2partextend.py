"""THE EXTENSION'S PLAN ROWS (owner RULINGS 2026-09-12as (2)).

``pack_partition._parts_by_member`` builds its per-part foot count array
``nf`` POSITIONALLY over the parts it is handed, and used to index it by
``p.pid`` — the part's GLOBAL load-numbering id.  In the load pass the
two coincide; in ``extend_partition`` the ``fake`` Partition holds ONLY
the new parts, whose pids continue the numbering (OTHH: 2 parts with
pids 164,799 and 164,800), so the read was
``IndexError: index 164799 is out of bounds for axis 0 with size 2``
and the whole OTHH tile aborted.  This twin is that fake partition.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from auto_patch_v2.airport import contact as _contact
from auto_patch_v2.airport.pack_partition import _parts_by_member


def _part(pid: int, member: int, x: float, feet: np.ndarray) -> _contact.PlacedPart:
    pts = np.array([[x, 0.0, 0.0], [x + 1.0, 0.0, 0.0], [x, 3.0, 1.0]])
    return _contact.PlacedPart(
        pid=pid, member=member, comp=0, pts=pts,
        tris=np.array([[0, 1, 2]]), base_y=0.0, area_m2=1.5,
        centroid=(x + 0.5, 0.5),
        box_min=np.array([x, 0.0, 0.0]),
        box_max=np.array([x + 1.0, 3.0, 1.0]),
        feet=feet)


def _to_ll_batch(xs, ys):
    """A stand-in frame: metres straight through as degrees."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    return xs / 1000.0, ys / 1000.0


def test_the_extension_partition_rows_index_by_position_not_by_pid():
    # the OTHH shape: two NEW parts whose pids continue the load
    # numbering, each with feet, each its own member
    a = _part(164799, 512, 0.0, np.array([[0.0, 0.0, 1.25], [1.0, 0.0, 1.5]]))
    b = _part(164800, 513, 10.0, np.array([[10.0, 0.0, 2.0]]))
    fake = _contact.Partition((a, b), (), 0, 0, 0, 0, ())

    rows = _parts_by_member(fake, _to_ll_batch)

    assert sorted(rows) == [512, 513]
    ra, = rows[512]
    rb, = rows[513]
    assert ra.pid == 164799 and rb.pid == 164800
    # THE FEET land on the right row, in order, with their AUTHORED y
    assert [f[2] for f in ra.feet] == [1.25, 1.5]
    assert [f[2] for f in rb.feet] == [2.0]
    assert [round(f[0], 8) for f in ra.feet] == [0.0, 0.001]
    assert [round(f[0], 8) for f in rb.feet] == [0.01]


def test_the_load_order_is_unchanged_when_pid_equals_position():
    """The load pass hands parts whose pid IS their position: the
    positional read must give exactly what the pid read gave."""
    a = _part(0, 0, 0.0, np.array([[0.0, 0.0, 1.0]]))
    b = _part(1, 1, 10.0, np.array([[10.0, 0.0, 2.0], [11.0, 0.0, 2.5]]))
    rows = _parts_by_member(_contact.Partition((a, b), (), 0, 0, 0, 0, ()),
                            _to_ll_batch)
    assert [f[2] for f in rows[0][0].feet] == [1.0]
    assert [f[2] for f in rows[1][0].feet] == [2.0, 2.5]


def test_a_footless_extension_part_still_rows():
    a = _part(9001, 3, 0.0, np.zeros((0, 3)))
    rows = _parts_by_member(_contact.Partition((a,), (), 0, 0, 0, 0, ()),
                            _to_ll_batch)
    assert rows[3][0].feet == ()


# ── issue #362 (lane perfC362): the extension re-places a NEIGHBOUR for the
# contact passes alone, and only its components within reach ──────────────

from auto_patch_v2.airport import obj8 as _obj8                   # noqa: E402


def _boxes_geom(name: str, boxes) -> _obj8.ObjGeometry:
    """One OBJ of several disjoint axis boxes ``(x0, x1, z0, z1, y0, y1)``
    — one solid component each."""
    vs, ts = [], []
    for x0, x1, z0, z1, y0, y1 in boxes:
        k = len(vs)
        vs += [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1],
               [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]]
        ts += [[k + a, k + b, k + c] for a, b, c in
               ((0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
                (2, 3, 7), (2, 7, 6), (1, 2, 6), (1, 6, 5), (3, 0, 4), (3, 4, 7))]
    tris = np.array(ts, dtype=int)
    return _obj8.ObjGeometry(name, np.array(vs, dtype=float), tris,
                             np.ones(len(tris), dtype=int), np.zeros((0, 3), dtype=int))


def _member_geom(oid: str, name: str, xy, heading: float, boxes):
    geom = _boxes_geom(name, boxes)
    o = _obj8.PlacedObject(oid, name, name, xy, heading, 0.0, "OBJECT", 100.0,
                           None, None, None, None, None, None)
    return (o, geom, list(enumerate(_obj8.solid_components(geom))))


_EXT_ARGS = dict(eps=0.05, weld_mm=0.001, budget=4_000_000, chunk_rows=200_000,
                 foot_band_m=1.0, foot_samples_max=4, elevated_base_m=2.0,
                 station_span_m=25.0, stations_max=8,
                 abutment_gap_m=3.0, abutment_extent_min_m=1.0, abutment_spacing_m=0.3)


def _world():
    # a "terminal": 40 components in a row, 4 m apart (most of them far
    # from the plate), and a second base member beside its first cells
    row = [(6.0 * i, 6.0 * i + 2.0, 0.0, 2.0, 0.0, 3.0 + 0.1 * i) for i in range(40)]
    base = [_member_geom("dsf:obj0", "terminal.obj", (0.0, 0.0), 0.0, row),
            _member_geom("dsf:obj1", "annex.obj", (0.0, -2.0), 0.0,
                         [(0.0, 2.0, 0.0, 2.0, 0.0, 2.5), (40.0, 41.0, 0.0, 1.0, 0.0, 9.0)])]
    # the added plates: one 2-3 cm off terminal cells 0-1 (no shared vertex:
    # the NARROW pass decides) with a slab floating 1.2 m over cell 0 (an
    # ABUTMENT, never an ε-contact), one touching nothing, one two-component
    # kerb 2 cm off cell 20
    new = [_member_geom("dsf:obj7", "plate.obj", (2.0, 0.0), 0.0,
                        [(0.02, 3.97, 0.0, 2.0, 0.0, 0.5),
                         (-1.5, -0.5, 0.2, 1.8, 4.2, 5.0)]),
           _member_geom("dsf:obj8", "plate.obj", (500.0, 500.0), 30.0,
                        [(0.0, 4.0, 0.0, 2.0, 0.0, 0.5)]),
           _member_geom("dsf:obj9", "kerb.obj", (122.0, 0.0), 0.0,
                        [(0.02, 3.0, 0.0, 2.0, 0.0, 0.4), (3.0, 3.5, 0.0, 2.0, 0.0, 0.4)])]
    return base, new


def _extend(base, new):
    part = _contact.partition(base, _EXT_ARGS["eps"], _EXT_ARGS["weld_mm"],
                              _EXT_ARGS["budget"], 0.5, _EXT_ARGS["chunk_rows"],
                              anchor_of_member=[0, 0], abutment_gap_m=3.0,
                              abutment_extent_min_m=1.0, abutment_spacing_m=0.3)
    return _contact.extend(_contact.base_index(part), base, new,
                           anchor_of_member=[0, 0, 0, 1, 0], **_EXT_ARGS)


def _same_part(a: _contact.PlacedPart, b: _contact.PlacedPart) -> bool:
    return (a.pid == b.pid and a.member == b.member and a.comp == b.comp
            and a.line == b.line and a.scatter == b.scatter
            and a.base_y == b.base_y and a.area_m2 == b.area_m2
            and a.centroid == b.centroid
            and all(np.array_equal(getattr(a, k), getattr(b, k))
                    for k in ("pts", "tris", "box_min", "box_max", "tri_lo", "tri_hi", "feet"))
            and len(a.rings) == len(b.rings)
            and all(np.array_equal(x, y) for x, y in zip(a.rings, b.rings))
            and (a.solid_h == b.solid_h or (a.solid_h != a.solid_h and b.solid_h != b.solid_h)))


def test_contact_only_places_the_same_part_for_the_contact_passes():
    base, _new = _world()
    o, geom, comps = base[0]
    full = _contact.placed_parts([base[0]], 1.0, 1)
    some = _contact.placed_parts([(o, geom, [c for c in comps if c[0] in (3, 17, 39)])],
                                 1.0, 1, contact_only=True)
    by_comp = {p.comp: p for p in full}
    assert [p.comp for p in some] == [3, 17, 39]
    for p in some:
        q = by_comp[p.comp]
        assert p.base_y == q.base_y and p.area_m2 == q.area_m2 and p.centroid == q.centroid
        for k in ("pts", "tris", "box_min", "box_max", "tri_lo", "tri_hi"):
            assert np.array_equal(getattr(p, k), getattr(q, k)), k
        # what the contact passes never read is not computed
        assert p.feet.shape == (0, 3) and p.rings == () and p.solid_h != p.solid_h
        assert q.rings and q.feet.shape[0] >= 1


def test_the_extension_equals_the_whole_member_replacing(monkeypatch):
    """OLD vs NEW on one world: with every neighbour re-placed WHOLE, feet
    and outlines and all (the pre-#362 call), the extension is the same
    parts, contacts, abutments and counts."""
    base, new = _world()
    got = _extend(base, new)
    assert got.contacts and got.abutments and got.pairs_tested >= 3   # the twin bites
    assert 0 < got.neighbours < 42            # ... and most components are far
    real = _contact.placed_parts
    whole = {id(m[0]): m for m in base}
    calls = []

    def old(members, *a, contact_only=False, **k):
        calls.append(contact_only)
        if contact_only:
            members = [whole[id(members[0][0])]]
        return real(members, *a, **k)
    monkeypatch.setattr(_contact, "placed_parts", old)
    want = _extend(base, new)
    assert True in calls
    assert (got.contacts, got.abutments, got.structures, got.pairs_tested,
            got.pairs_unproved, got.neighbours) == \
           (want.contacts, want.abutments, want.structures, want.pairs_tested,
            want.pairs_unproved, want.neighbours)
    assert len(got.parts) == len(want.parts)
    assert all(_same_part(a, b) for a, b in zip(got.parts, want.parts))


def test_the_indexed_neighbourhood_is_the_full_scan():
    """``_near_base`` asks a tree for candidates and then makes the SAME
    box test the pre-#362 loop made against every base part."""
    rng = np.random.default_rng(362)
    lo = rng.uniform(-200.0, 200.0, (3000, 3))
    hi = lo + rng.uniform(0.0, 6.0, (3000, 3))
    scatter = rng.random(3000) < 0.1
    flo = rng.uniform(-200.0, 200.0, (150, 3))
    fhi = flo + rng.uniform(0.0, 9.0, (150, 3))
    # boxes exactly AT the reach, where a looser or tighter test would differ
    eps = 0.05
    flo[:20] = hi[:20] + eps
    fhi[:20] = flo[:20] + 1.0
    fhi[20:40] = lo[20:40] - eps
    flo[20:40] = fhi[20:40] - 1.0
    for sc in (None, scatter):
        base = _contact.BaseIndex(lo, hi, np.zeros(3000, dtype=np.int64),
                                  np.zeros(3000, dtype=np.int64),
                                  np.zeros(3000, dtype=bool),
                                  np.arange(3000, dtype=np.int64), sc)
        want: set[int] = set()
        for i in range(flo.shape[0]):
            m = ((lo - eps <= fhi[i]) & (flo[i] - eps <= hi)).all(axis=1)
            if sc is not None:
                m &= ~sc
            want.update(np.flatnonzero(m).tolist())
        assert want and _contact._near_base(base, flo, fhi, eps) == want


# ── issue #362: THE EXTENSION IS CACHED beside the partition ─────────────

def _ext_world(tmp_path, monkeypatch):
    """A load reading with two deferred plate placements, a partition cache
    file under its fingerprint, and a COUNTED stand-in for the compute."""
    from types import SimpleNamespace as NS
    from auto_patch_v2.airport import pack_partition as PP
    from auto_patch_v2.airport import partition_cache as PC
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.rebake import Member, Part, Unit
    root = tmp_path / "pack"
    (root / "Earth nav data").mkdir(parents=True)
    (root / "Earth nav data" / "apt.dat").write_text("I\n", encoding="utf-8", newline="")
    (root / "plate.obj").write_text("A\n800\nOBJ\n", encoding="utf-8", newline="")
    dump = tmp_path / "+25+051.dsf.0a0a0a0a.text"
    dump.write_text("OBJECT_DEF plate.obj\n", encoding="utf-8", newline="")
    air = NS(icao="OTHH", dsf_objects=(), frame=NS(crs="EPSG:32639", lat0=25.2, lon0=51.6),
             pack=NS(name="pack", apt_dat_path=str(root / "Earth nav data" / "apt.dat"),
                     borrowed_apt_dat_path="", borrowed_block_sha256=""))
    law = Law.for_airport("")

    def placement(oid, x):
        return NS(id=oid, path="plate.obj", resolved=str(root / "plate.obj"), xy=(x, 0.0),
                  heading_deg=0.0, agl_m=0.0, kind="OBJECT", anchor_z=3.5,
                  deck_kind=None, hard_deck=None)
    deferred = (((25.0, 51.0, 0.0), placement("dsf:obj1", 10.0)),
                ((25.1, 51.0, 0.0), placement("dsf:obj2", 90.0)),
                ((25.2, 51.0, 0.0), NS(**{**vars(placement("dsf:obj3", 50.0)),
                                          "path": "other.obj"})))
    ix = _contact.BaseIndex(np.zeros((2, 3)), np.ones((2, 3)), np.zeros(2, dtype=np.int64),
                            np.arange(2, dtype=np.int64), np.zeros(2, dtype=bool),
                            np.arange(2, dtype=np.int64), np.zeros(2, dtype=bool))
    geom = PP._LoadGeom(ix, PP.MemberGeometries(
        [PP.MemberRecipe(placement("dsf:obj0", 0.0), (0, 1))]),
        (((24.0, 51.0, 0.0), "base.obj", "dsf:obj0"),), (0,), {(24.0, 51.0, 0.0): 0},
        frozenset())
    base_m = Member("dsf:obj0", "base.obj", "base.obj", "base.obj", 0.0)
    part = PP.PackPartition("OTHH", "pack", str(root), (Unit("unit:0", (24.0, 51.0), 0.0, (base_m,)),),
                            (("plate.obj", "placed at 2 anchors"),),
                            {"multi_anchor": 1, "pairs_tested": 7, "pairs_unproved": 0},
                            ((0, 1),), (), {(0, 0): ("dsf:obj0", "base.obj")},
                            deferred=deferred, geom=geom)
    calls = []

    def compute(part_, geom_, add, airport, cache, law_):
        calls.append([o.id for _k, o in add])
        row = Part(2, 0, 25.0, 51.0, 0.0, 1.0, (25.0, 51.0, 25.0, 51.0), (), False, (), 2.0)
        return {"icao": part_.icao,
                "new_ref": tuple((k, o.path, o.id) for k, o in add),
                "members": tuple(Member(o.id, o.path, o.path, o.path, 0.0, parts=(row,))
                                 for _k, o in add),
                "readded": tuple(sorted({o.path for _k, o in add})),
                "counts": dict(part_.counts), "skipped": {},
                "contacts": ((1, 2),), "abutments": ((0, 2),), "structures": 1,
                "pairs_tested": 5, "pairs_unproved": 1, "neighbours": 2}
    monkeypatch.setattr(PP, "_extension", compute)
    monkeypatch.setattr(PC, "_TAKEN", {})
    monkeypatch.setattr(PC, "_FILED", {})
    return NS(PP=PP, PC=PC, air=air, law=law, part=part, calls=calls, root=root,
              dump=str(dump), mod=str(tmp_path / "mod"))


def _file_partition(w):
    fp = w.PC.fingerprint(w.air, w.law, dump_path=w.dump, radius_deg=0.05)
    path = w.PC.cache_path(w.air, w.mod, w.dump)
    assert w.PC.write(path, fp, "the load reading")
    return path, fp


def test_no_partition_cache_no_extension_cache(tmp_path, monkeypatch):
    w = _ext_world(tmp_path, monkeypatch)
    a = w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"})
    b = w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"})
    assert w.calls == [["dsf:obj1", "dsf:obj2"]] * 2 and a == b
    # fingerprinted but never read or written: still nothing to stand beside
    w.PC.fingerprint(w.air, w.law, dump_path=w.dump, radius_deg=0.05)
    w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"})
    assert len(w.calls) == 3
    assert not list(tmp_path.rglob("*.ext*"))


def test_the_extension_is_revived_and_every_changed_input_misses(tmp_path, monkeypatch):
    import dataclasses as dc
    w = _ext_world(tmp_path, monkeypatch)
    path, fp = _file_partition(w)
    first = w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"})
    assert len(w.calls) == 1 and Path(path + w.PP._extcache.SUFFIX).is_file()
    again = w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"})
    assert len(w.calls) == 1                      # HIT: nothing recomputed
    assert again == first and repr(again) == repr(first)
    assert first.counts["pairs_tested"] == 12 and first.counts["plate_readded"] == 1
    assert first.contacts == ((0, 1), (1, 2)) and first.deferred == () and first.geom is None
    # a fresh process that READS the partition (a HIT) finds the companion too
    monkeypatch.setattr(w.PC, "_TAKEN", {})
    monkeypatch.setattr(w.PC, "_FILED", {})
    fp2 = w.PC.fingerprint(w.air, w.law, dump_path=w.dump, radius_deg=0.05)
    assert fp2 == fp and w.PC.read(path, fp2) == "the load reading"
    assert w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"}) == first
    assert len(w.calls) == 1
    # (1) a different PLATE SET brings different placements back
    w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj", "dsf:obj3"})
    assert w.calls[-1] == ["dsf:obj1", "dsf:obj2", "dsf:obj3"] and len(w.calls) == 2
    w.PP.extend_partition(w.part, w.air, None, w.law, {"dsf:obj2"})
    assert w.calls[-1] == ["dsf:obj2"] and len(w.calls) == 3
    # (2) one re-added placement MOVED (the same ids and paths)
    d = list(w.part.deferred)
    d[0] = (d[0][0], type(d[0][1])(**{**vars(d[0][1]), "anchor_z": 3.6}))
    w.PP.extend_partition(dc.replace(w.part, deferred=tuple(d)), w.air, None, w.law,
                          {"plate.obj"})
    assert len(w.calls) == 4
    # (3) the LOAD READING in hand is not the one cached: one base box
    ix = w.part.geom.index
    hi = ix.box_hi.copy(); hi[1, 2] += 0.25
    moved = dc.replace(w.part, geom=dc.replace(w.part.geom, index=dc.replace(ix, box_hi=hi)))
    w.PP.extend_partition(moved, w.air, None, w.law, {"plate.obj"})
    assert len(w.calls) == 5
    # (4) the PARTITION'S FINGERPRINT moved (a pack file grew): no file
    # under the new key -> no companion; filed -> its own companion, a MISS
    (w.root / "plate.obj").write_text("A\n800\nOBJ\n# v2\n", encoding="utf-8", newline="")
    fp3 = w.PC.fingerprint(w.air, w.law, dump_path=w.dump, radius_deg=0.05)
    assert fp3 != fp and w.PC.read(path, fp3) is None
    w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"})
    assert len(w.calls) == 6
    assert w.PC.write(path, fp3, "the load reading, re-read")
    w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"})
    assert len(w.calls) == 7                      # the old companion is refused
    w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"})
    assert len(w.calls) == 7                      # ... and the new one HITS
    # (5) changed partition CODE moves the fingerprint the same way
    monkeypatch.setattr(w.PC, "_CODE_DIGEST", "c" * 64)
    fp4 = w.PC.fingerprint(w.air, w.law, dump_path=w.dump, radius_deg=0.05)
    assert fp4 not in (fp, fp3)
    assert w.PC.write(path, fp4, "the load reading, new code")
    w.PP.extend_partition(w.part, w.air, None, w.law, {"plate.obj"})
    assert len(w.calls) == 8
    monkeypatch.setattr(w.PC, "_CODE_DIGEST", None)
