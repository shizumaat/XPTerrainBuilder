"""The columnar ConstraintSet codec (stage-cache spec §4c, §10 step 7):
exact round trip over every row kind and every optional-field variant,
out-of-band pickling, digest determinism and refusals."""
from __future__ import annotations

import dataclasses
import math
import pickle
import struct

import pytest
from auto_patch_v2.model.constraint_codec import LAYOUT, ColumnarSet, decode, digest, encode
from auto_patch_v2.model.constraints import (
    Band,
    ConstraintSet,
    Diff,
    Flat,
    Linear,
    Offset,
    Pin,
    Source,
)

S1 = Source("runway_profile", "2026-08-27", ("apt:12", "osm:way/99"))
S2 = Source("apron_within_shape", "RULINGS-10y", ())
S3 = Source("pads", "ruling é ✓", ("face:7",))


def _every_variant() -> ConstraintSet:
    return ConstraintSet(
        pins=(Pin(0, 12.5, S1), Pin(7, -0.0, S2), Pin(3, 1e300, S1)),
        diffs=(Diff(0, 1, 0.015, 30.0, S1),
               Diff(1, 2, 0.02, 12.25, S2, soft="end_zone", ceiling=0.05),
               Diff(2, 3, 0.01, 4.0, S3, follows=3, rel=-0.375),
               Diff(4, 5, 0.01, 4.0, S3, soft="x", follows=(4, 5, 6)),
               Diff(5, 6, 0.01, 4.0, S1, follows=(9,)),
               Diff(6, 7, 0.01, 4.0, S1, follows=())),
        flats=(Flat((1, 2, 3), S3), Flat((8,), S1), Flat((), S2)),
        bands=(Band(0, None, 5.0, S1), Band(1, -2.0, None, S2), Band(2, None, None, S3),
               Band(3, 1.0, 2.0, S1)),
        offsets=(Offset(4, 5, 6.5, S2),),
        linears=(Linear(((0, 1.0), (1, -2.0), (2, 1.0)), -0.1, 0.1, S1),
                 Linear(((3, 0.25),), None, 3.0, S2, soft="trend", ceiling=0.2, follows=3),
                 Linear((), 0.0, None, S3, follows=(1, 2, 3))))


def _bits(cs: ConstraintSet) -> list:
    """Every float field's bit pattern, row by row (``==`` cannot tell
    ``-0.0`` from ``0.0``)."""
    out = []
    for r in cs.rows():
        for v in vars(r).values():
            if isinstance(v, float):
                out.append(struct.pack("<d", v))
    return out


def test_round_trip_every_row_kind_and_variant():
    cs = _every_variant()
    back = decode(encode(cs))
    assert back == cs
    assert _bits(back) == _bits(cs)
    for kind in ("pins", "diffs", "flats", "bands", "offsets", "linears"):
        assert [type(r) for r in getattr(back, kind)] == [type(r) for r in getattr(cs, kind)]
    # the frozen rows stay frozen and hashable
    assert hash(back.diffs[3]) == hash(cs.diffs[3])
    with pytest.raises(dataclasses.FrozenInstanceError):
        back.pins[0].z = 1.0


def test_layout_covers_every_kind_and_field():
    assert {cls for cls, _a, _f in LAYOUT} == {Pin, Diff, Flat, Band, Offset, Linear}


def test_empty_set_and_empty_kinds():
    assert decode(encode(ConstraintSet())) == ConstraintSet()
    only_pins = ConstraintSet(pins=(Pin(1, 2.0, S1),))
    assert decode(encode(only_pins)) == only_pins


def test_pickle_protocol5_out_of_band():
    enc = encode(_every_variant())
    bufs: list = []
    head = pickle.dumps(enc, protocol=5, buffer_callback=bufs.append)
    assert len(bufs) == len(enc.columns)
    back = pickle.loads(head, buffers=[b.raw() for b in bufs])
    assert isinstance(back, ColumnarSet) and back.digest() == enc.digest()
    assert decode(back) == _every_variant()
    # in band (no callback) and an older protocol round-trip too
    for proto in (5, 4):
        assert decode(pickle.loads(pickle.dumps(enc, protocol=proto))) == _every_variant()


def test_digest_is_by_value_and_sensitive():
    cs = _every_variant()
    twin = _every_variant()                     # fresh objects, equal values
    assert digest(cs) == digest(twin) == encode(decode(encode(cs))).digest()
    variants = [
        ConstraintSet(**{**vars(cs), "pins": (Pin(0, 12.500000000000002, S1),) + cs.pins[1:]}),
        ConstraintSet(**{**vars(cs), "pins": (Pin(0, 12.5, S2),) + cs.pins[1:]}),
        ConstraintSet(**{**vars(cs), "pins": cs.pins[::-1]}),
        ConstraintSet(**{**vars(cs), "bands": (Band(0, 0.0, 5.0, S1),) + cs.bands[1:]}),
        ConstraintSet(**{**vars(cs), "flats": (Flat((1, 2), S3),) + cs.flats[1:]}),
        ConstraintSet(**{**vars(cs), "diffs": cs.diffs[:4] + (Diff(5, 6, 0.01, 4.0, S1,
                                                                    follows=9),) + cs.diffs[5:]}),
        ConstraintSet(**{**vars(cs), "pins": (Pin(0, 12.5, Source("runway_profile",
                                                                   "2026-08-27",
                                                                   ("apt:12",))),)
                         + cs.pins[1:]}),
    ]
    seen = {digest(cs)}
    for v in variants:
        d = digest(v)
        assert d not in seen
        seen.add(d)


def test_digest_is_pinned():
    """The layout's digest on a fixed set: a layout change bumps
    ``CODEC_VERSION`` and this value; the same value on every platform."""
    cs = ConstraintSet(pins=(Pin(0, 1.5, S1),), bands=(Band(1, None, 2.0, S2),))
    assert digest(cs) == PINNED


@pytest.mark.parametrize("bad", [
    ConstraintSet(pins=[Pin(0, 1.0, S1)]),                              # list, not tuple
    ConstraintSet(diffs=(Diff(0, 1, 0.1, 1.0, S1, follows=True),)),     # bool follows
    ConstraintSet(pins=(Pin(0, "1", S1),)),
    ConstraintSet(flats=(Flat([1, 2], S1),)),
    ConstraintSet(linears=(Linear([(0, 1.0)], 0.0, 1.0, S1),)),
    ConstraintSet(linears=(Linear(((0, 1.0, 2.0),), 0.0, 1.0, S1),)),
    ConstraintSet(diffs=(Diff(0, 1, 0.1, 1.0, S1, follows=[1]),)),
    ConstraintSet(pins=(Pin(0, 1.0, Source("g", "r", ["x"])),)),
    ConstraintSet(pins=(Diff(0, 1, 0.1, 1.0, S1),)),                    # wrong kind
    ConstraintSet(pins=(Pin(2 ** 31, 1.0, S1),)),                       # past int32
])
def test_refuses_what_it_cannot_keep(bad):
    with pytest.raises((TypeError, OverflowError)):
        encode(bad)


def test_nan_value_survives_with_its_mask():
    cs = ConstraintSet(bands=(Band(0, math.nan, None, S1),))
    back = decode(encode(cs)).bands[0]
    assert math.isnan(back.lo) and back.hi is None


PINNED = "8c5afec9fc3120feedeed9cd22af3c78c5a146eb5e4444c3cde8a6116824f9b2"
