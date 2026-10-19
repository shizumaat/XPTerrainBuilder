"""THE CONSTRAINT STAGE AND THE JETWAY STRIPS THROUGH THEIR RECORDS
(stage-cache spec §4b.1, §4b.2, §6 back half; issue #843 step 9).

ONE RECORD PER GENERATOR (``constraints.gen.<name>``, code entry
``constraints.<name>``): its rows in the columnar codec
(``model/constraint_codec`` — RULINGS 2026-10-18e: never a pickle of row
objects), the run of row kinds that restores the generator's own row
order, and its ``STATS`` slice.  Keyed on the shape stage's output digest
(the map, its registries), the ``Airport`` digest, the whole law and the
DEM questions every generator before it asked (``dem_before``,
``pipeline/back_cache``): a memo one generator fills and a later one reads
never hides a question.

ONE ASSEMBLY RECORD (``constraints.assembly``): the post-passes
(``constraints/assembly.py``) and the joint filter (``shapes.joint_filter``).
It is keyed by its generators' OUTPUT digests (spec §4c early cutoff: a
generator that re-runs and yields the same rows leaves the assembly a hit —
the digest is the columns' sha256, taken on the miss arm, and a hit reads
every generator record anyway to rebuild the delta).  Later stages name the
assembly by its KEY (KEY CHAINING, RULINGS 2026-10-18e: decoding a
HECA-sized set misses the 1 s target, and its payload carries the post-pass
clocks).  It stores only its DELTA over the generators' rows —
per row kind, each assembled row's index into that kind's concatenation
(``-1`` for a row a post-pass minted) and the minted rows in the codec —
plus the post-pass counts, the seam pass's yielded rows and the
``ShapeStage`` fields the joint filter writes, installed on a hit.  Served
over a generator record that was recomputed (an evicted one), it holds
exactly when that generator's digest is the one it was keyed on.

``jetway_strip``: the strips record, keyed on the map, the assembly's key
and the airport (spec §4b.2).

:func:`constraints_stage` and :func:`strips_stage` are what
``pipeline/prefix.run_prefix`` calls; with no cache (or the cache off) they
are ``shapes.shape_constraints`` and ``jetway_strips`` exactly."""
from __future__ import annotations

import array as _array
import hashlib
import itertools as _it
import json
import pickle
import time
import typing as _t

from ..constraints import GENERATORS, run_generator, stack
from ..constraints.assembly import assemble
from ..model import constraint_codec as _codec
from ..model.constraints import ConstraintSet
from . import back_cache as _bc
from . import stage_code as _code
from .shapes import joint_filter, shape_constraints

__all__ = ["GenRows", "Constraints", "constraints_stage", "strips_stage", "set_delta",
           "from_delta", "kinds_of"]

#: The ``ConstraintSet`` fields, in the codec's order; a row's kind is its index.
_KINDS: tuple[str, ...] = tuple(attr for _cls, attr, _f in _codec.LAYOUT)
_KIND_OF: dict[type, int] = {cls: i for i, (cls, _a, _f) in enumerate(_codec.LAYOUT)}
_ASSEMBLY = "constraints.assembly"


def _gen_stage(name: str) -> str:
    return f"constraints.gen.{name}"


class GenRows(_t.NamedTuple):
    """One generator's record: its rows by kind (``cs``), the ``(kind,
    count)`` runs that put them back in the generator's own order, and its
    ``STATS`` slice."""

    cs: ConstraintSet
    runs: _array.array
    stats: dict

    @classmethod
    def of(cls, rows: _t.Sequence, stats: _t.Mapping[str, int]) -> "GenRows":
        runs = _array.array("i")
        for kind, grp in _it.groupby(map(type, rows)):
            runs.extend((_KIND_OF[kind], len(list(grp))))
        return cls(ConstraintSet.from_rows(rows), runs, dict(stats))

    def rows(self) -> list:
        """The rows in the generator's own order (the same objects)."""
        its = [iter(getattr(self.cs, a)) for a in _KINDS]
        out: list = []
        for k, n in zip(self.runs[::2], self.runs[1::2], strict=True):
            out.extend(_it.islice(its[k], n))
        return out


def _sha(*parts: _t.Any) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, (bytes, memoryview)) else str(p).encode())
        h.update(b"\0")
    return h.hexdigest()


def _encode_gen(g: GenRows) -> tuple[bytes, _t.Callable[[], str]]:
    enc = _codec.encode(g.cs)
    blob = pickle.dumps((enc, g.runs, g.stats), protocol=5)
    runs = _array.array("i", g.runs)
    return blob, lambda: _sha(enc.digest(), list(runs), json.dumps(g.stats, sort_keys=True))


def _decode_gen(blob: bytes) -> GenRows:
    enc, runs, stats = pickle.loads(blob)
    return GenRows(_codec.decode(enc), runs, stats)


#: The per-generator record's codec.
GEN_CODEC = _bc.Codec(_encode_gen, _decode_gen)


class _Assembly(_t.NamedTuple):
    cs: ConstraintSet
    counts: dict
    walls: dict
    yielded: list
    joints: dict          # the ShapeStage fields the joint filter wrote


def _concat(gens: _t.Sequence[GenRows]) -> dict[str, tuple]:
    return {a: tuple(_it.chain.from_iterable(getattr(g.cs, a) for g in gens)) for a in _KINDS}


def _delta(final: tuple, concat: tuple) -> tuple[_array.array, list]:
    """Each row of ``final`` as its index into ``concat`` (by identity),
    ``-1`` and kept apart for a row ``concat`` does not hold."""
    at: dict[int, int] = {}
    for i, r in enumerate(concat):
        at.setdefault(id(r), i)
    idx, new = _array.array("i"), []
    for r in final:
        i = at.get(id(r), -1)
        idx.append(i)
        if i < 0:
            new.append(r)
    return idx, new


def set_delta(final: ConstraintSet, base: _t.Mapping[str, tuple]) -> dict:
    """``final`` as a DELTA over ``base`` (per row kind, the rows it is
    made of): per kind each row's index into ``base`` (``-1``: a row
    ``base`` does not hold) and those rows in the columnar codec — never a
    pickle of rows (RULINGS 2026-10-18e).  :func:`from_delta` inverts it."""
    idx, new = {}, {}
    for k in _KINDS:
        idx[k], new[k] = _delta(getattr(final, k), base[k])
    return {"idx": idx,
            "minted": _codec.encode(ConstraintSet(**{k: tuple(v) for k, v in new.items()}))}


def from_delta(rec: _t.Mapping[str, _t.Any], base: _t.Mapping[str, tuple]) -> ConstraintSet:
    """The set :func:`set_delta` encoded, over the same ``base``."""
    minted = _codec.decode(rec["minted"])
    kinds = {}
    for k in _KINDS:
        fresh = iter(getattr(minted, k))
        kinds[k] = tuple(base[k][i] if i >= 0 else next(fresh) for i in rec["idx"][k])
    return ConstraintSet(**kinds)


def kinds_of(cs: ConstraintSet) -> dict[str, tuple]:
    """``cs``'s rows per kind — the ``base`` of :func:`set_delta`."""
    return {k: tuple(getattr(cs, k)) for k in _KINDS}


def _assembly_codec(gens: _t.Sequence[GenRows]) -> _bc.Codec:
    def encode(a: _Assembly) -> tuple[bytes, _t.Callable[[], str]]:
        yielded = GenRows.of(a.yielded, {})
        blob = pickle.dumps({**set_delta(a.cs, _concat(gens)),
                             "yielded": (_codec.encode(yielded.cs), yielded.runs),
                             "counts": a.counts, "walls": a.walls,
                             "joints": a.joints}, protocol=5)
        return blob, lambda: hashlib.sha256(blob).hexdigest()

    def decode(blob: bytes) -> _Assembly:
        rec = pickle.loads(blob)
        y_cs, y_runs = rec["yielded"]
        return _Assembly(from_delta(rec, _concat(gens)), rec["counts"], rec["walls"],
                         GenRows(_codec.decode(y_cs), y_runs, {}).rows(), rec["joints"])
    return _bc.Codec(encode, decode)


class Constraints(_t.NamedTuple):
    """The constraint stage's answer: the set, the counts and walls per
    generator, the assembly's KEY (``None``: not cached) and the DEM chain
    after it (``dem_before`` of the next record)."""

    cs: ConstraintSet
    counts: dict
    walls: dict
    key: str | None
    chain: str


def constraints_stage(fc: _t.Any, pm, law, airport, stage, inputs: _t.Mapping[str, str | None],
                      yielded_out: list) -> Constraints:
    """``shapes.shape_constraints`` through the per-generator and the
    assembly records (module doc); ``yielded_out`` takes the seam pass's
    yielded rows and ``stage`` the joint filter's fields, hit or miss."""
    if fc is None or not fc.active:
        for name in [*(_gen_stage(n) for n, _f in GENERATORS), _ASSEMBLY]:
            if fc is not None:
                fc.bypassed(name)
        cs, counts, walls = shape_constraints(pm, law, airport, stage, yielded_out=yielded_out)
        return Constraints(cs, counts, walls, None, "")
    chain = hashlib.sha256()
    gens, gots, counts, walls = [], [], {}, {}
    for name, fn in GENERATORS:
        t = time.perf_counter()
        got = _bc.record(fc, _gen_stage(name), {**inputs, "dem_before": chain.hexdigest()},
                         lambda fn=fn: GenRows.of(*run_generator(fn, pm, law, airport)),
                         code=_code.generator_stage(name), codec=GEN_CODEC)
        walls[name] = time.perf_counter() - t
        g: GenRows = got.value
        counts[name] = len(g.cs.rows())
        counts.update({f"{name}.{k}": v for k, v in g.stats.items()})
        chain.update(got.dem.encode())
        gens.append(g)
        gots.append(got)
    digests = None if any(g.key is None for g in gots) else _sha(*(g.digest for g in gots))

    def run() -> _Assembly:
        acounts: dict = {}
        awalls: dict = {}
        yielded: list = []
        rows = assemble([r for g in gens for r in g.rows()], acounts, awalls, pm, law,
                        None, yielded)
        cs = joint_filter(stack(rows), stage, acounts, awalls)
        return _Assembly(cs, acounts, awalls, yielded,
                         {"dropped": dict(stage.dropped),
                          "flats_straddling": stage.flats_straddling,
                          "bands_withdrawn": stage.bands_withdrawn})
    got = _bc.record(fc, _ASSEMBLY, {"pm": inputs.get("pm"), "generators": digests}, run,
                     codec=_assembly_codec(gens))
    a: _Assembly = got.value
    stage.dropped = dict(a.joints["dropped"])
    stage.flats_straddling = a.joints["flats_straddling"]
    stage.bands_withdrawn = a.joints["bands_withdrawn"]
    yielded_out.extend(a.yielded)
    counts.update(a.counts)
    walls.update(a.walls)
    chain.update(got.dem.encode())
    return Constraints(a.cs, counts, walls, got.key, chain.hexdigest())


def strips_stage(fc: _t.Any, pm, law, airport, con: Constraints,
                 inputs: _t.Mapping[str, str | None]) -> _bc.Got:
    """THE JETWAY STRIPS (``constraints.jetway_strip.jetway_strips`` on the
    airport's riders) through their record (spec §4b.2): the record's
    :class:`~pipeline.back_cache.Got` (``value`` the strips; ``digest`` what
    the solve's key names them by)."""
    from ..airport.riders import rider_candidates
    from ..constraints.jetway_strip import jetway_strips

    def run():
        return jetway_strips(pm, law, airport, con.cs, rider_candidates(airport, law))
    return _bc.record(fc, "jetway_strip", {**inputs, "assembly": con.key,
                                           "dem_before": con.chain}, run)
