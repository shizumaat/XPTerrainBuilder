"""Twin for the DUPLICATE-WORK CENSUS in ``tools/profile_airport_build.py``.

The census answers "are we computing anything twice per build" with a
MEASUREMENT: each counted call's inputs are fingerprinted BEFORE the call,
and a fingerprint already seen in the run makes that call a duplicate.
Three properties are load-bearing and each has a test here:

  (a) duplicate detection FIRES on a known-duplicate fixture — including
      through the shapely / numpy value rules, which is what most of this
      engine's expensive callables are handed;
  (b) the instrument is OBSERVATION-ONLY — the wrapped callable's return
      value, its arguments and its call count are exactly what they would
      be without the wrapper, and the seconds spent fingerprinting are
      EXCLUDED from the inclusive seconds the report quotes;
  (c) an UNFINGERPRINTABLE input still COUNTS the call — it degrades to
      counting, never to skipping, and never joins a duplicate
      population (a guessed duplicate is a fabricated defect, and this
      instrument's whole product is a list of suspected duplicates).

Headless: no engine import, no build, no network, no shared-repo access.
"""
import importlib.util
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
PROFILER = ROOT / "tools" / "profile_airport_build.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def prof():
    return _load("_dupcensus_profile_airport_build", PROFILER)


class _Owner:
    """A stand-in module object for ``_install_counters`` to patch."""


def _install_on(prof, owner, name, fn, **kw):
    owner_name = f"_dupcensus_owner_{id(owner):x}"
    sys.modules[owner_name] = owner
    setattr(owner, name, fn)
    counters = prof._install_counters([f"{owner_name}:{name}"], **kw)
    return counters[0]


# ── (a) duplicate detection fires ────────────────────────────────────

def test_value_duplicates_are_detected_and_timed(prof):
    owner = _Owner()
    calls = []

    def work(a, b=1):
        calls.append((a, b))
        time.sleep(0.01)
        return a + b

    counter = _install_on(prof, owner, "work", work,
                          fingerprint=prof.InputFingerprinter())
    assert owner.work(1, b=2) == 3
    assert owner.work(5, b=5) == 10
    assert owner.work(1, b=2) == 3          # the duplicate
    assert owner.work(1, b=2) == 3          # and again

    assert counter.calls == 4
    assert counter.distinct == 2
    assert counter.duplicate_calls == 2
    assert counter.unfingerprintable_calls == 0
    assert counter.identity_duplicate_calls == 0
    # the duplicates' own inclusive seconds, not the whole total
    assert counter.duplicate_seconds > 0.0
    assert counter.duplicate_seconds < counter.seconds
    # the wrapped function really ran every time — never skipped
    assert calls == [(1, 2), (5, 5), (1, 2), (1, 2)]


def test_positional_and_keyword_spellings_of_one_call_agree(prof):
    owner = _Owner()
    counter = _install_on(prof, owner, "work", lambda a, b: (a, b),
                          fingerprint=prof.InputFingerprinter())
    owner.work(1, b=2)
    owner.work(1, b=2)
    assert counter.duplicate_calls == 1
    # ... but a DIFFERENT value is a different fingerprint
    owner.work(1, b=3)
    assert counter.distinct == 2
    assert counter.duplicate_calls == 1


def test_containers_sets_and_dicts_are_priced_by_value(prof):
    owner = _Owner()
    counter = _install_on(prof, owner, "work", lambda payload: payload,
                          fingerprint=prof.InputFingerprinter())
    owner.work({"a": [1, 2.0, "x"], "b": (None, True)})
    owner.work({"a": [1, 2.0, "x"], "b": (None, True)})
    assert counter.duplicate_calls == 1
    # a set is order-free: two spellings of one set are ONE fingerprint
    owner.work({1, 2, 3})
    owner.work({3, 2, 1})
    assert counter.duplicate_calls == 2
    # 2.0 and 2 are not the same input
    owner.work({"a": [1, 2, "x"], "b": (None, True)})
    assert counter.duplicate_calls == 2


def test_numpy_arrays_are_priced_by_value(prof):
    numpy = pytest.importorskip("numpy")
    owner = _Owner()
    counter = _install_on(prof, owner, "work", lambda arr: arr.sum(),
                          fingerprint=prof.InputFingerprinter())
    owner.work(numpy.array([1.0, 2.0, 3.0]))
    owner.work(numpy.array([1.0, 2.0, 3.0]))     # equal VALUE, other object
    assert counter.duplicate_calls == 1
    owner.work(numpy.array([1.0, 2.0, 4.0]))
    assert counter.duplicate_calls == 1
    # dtype and shape are part of the fingerprint
    owner.work(numpy.array([1, 2, 3]))
    owner.work(numpy.array([[1.0, 2.0, 3.0]]))
    assert counter.duplicate_calls == 1
    assert counter.unfingerprintable_calls == 0


def test_shapely_geometries_are_priced_by_wkb(prof):
    shapely = pytest.importorskip("shapely")
    from shapely.geometry import Polygon
    owner = _Owner()
    counter = _install_on(prof, owner, "work", lambda geom: geom.area,
                          fingerprint=prof.InputFingerprinter())
    square = [(0, 0), (0, 1), (1, 1), (1, 0)]
    owner.work(Polygon(square))
    owner.work(Polygon(square))                  # equal VALUE, other object
    assert counter.duplicate_calls == 1
    assert counter.unfingerprintable_calls == 0
    owner.work(Polygon([(0, 0), (0, 2), (2, 2), (2, 0)]))
    assert counter.duplicate_calls == 1
    assert counter.distinct == 2
    assert shapely is not None


# ── (b) observation-only ─────────────────────────────────────────────

def test_outputs_and_arguments_are_untouched(prof):
    owner = _Owner()
    seen = []

    def work(rows, table, *rest, **kw):
        seen.append((rows, table, rest, kw))
        return {"rows": rows, "table": table, "rest": rest, "kw": kw}

    counter = _install_on(prof, owner, "work", work,
                          fingerprint=prof.InputFingerprinter())
    rows = [1, 2, 3]
    table = {"k": {"deep": [4, 5]}}
    out = owner.work(rows, table, "extra", flag=True)

    assert out == {"rows": [1, 2, 3], "table": {"k": {"deep": [4, 5]}},
                   "rest": ("extra",), "kw": {"flag": True}}
    # the callee received the SAME objects, unmodified
    assert seen[0][0] is rows
    assert seen[0][1] is table
    assert rows == [1, 2, 3]
    assert table == {"k": {"deep": [4, 5]}}
    assert counter.calls == 1


def test_an_exception_propagates_unchanged_and_the_call_is_counted(prof):
    owner = _Owner()

    def work(a):
        raise ValueError("boom")

    counter = _install_on(prof, owner, "work", work,
                          fingerprint=prof.InputFingerprinter())
    with pytest.raises(ValueError, match="boom"):
        owner.work(1)
    assert counter.calls == 1


def test_fingerprint_seconds_are_excluded_from_the_inclusive_seconds(prof):
    """The instrument's own tax never lands on the measured work."""
    numpy = pytest.importorskip("numpy")
    owner = _Owner()
    big = numpy.arange(2_000_000, dtype="float64")   # ~16 MB to digest

    counter = _install_on(prof, owner, "work", lambda arr: None,
                          fingerprint=prof.InputFingerprinter())
    owner.work(big)
    owner.work(big)
    assert counter.calls == 2
    assert counter.fingerprint_seconds > 0.0
    # the wrapped callable does nothing, so its inclusive total must stay
    # far below the digesting cost the wrapper paid around it
    assert counter.seconds < counter.fingerprint_seconds


def test_a_plain_counter_is_unchanged_by_the_census_extension(prof):
    """--count with no fingerprinter keeps its original contract."""
    owner = _Owner()
    counter = _install_on(prof, owner, "work", lambda a: a * 2)
    assert owner.work(3) == 6
    assert owner.work(3) == 6
    assert counter.calls == 2
    assert counter.fingerprint is None
    assert counter.distinct == 0
    assert counter.duplicate_calls == 0
    assert counter.fingerprint_seconds == 0.0


def test_reentrant_calls_are_counted_once_into_inclusive_seconds(prof):
    owner = _Owner()

    def work(n):
        if n:
            owner.work(n - 1)
        return n

    counter = _install_on(prof, owner, "work", work,
                          fingerprint=prof.InputFingerprinter())
    owner.work(2)
    assert counter.calls == 3            # every activation is a call
    assert counter.distinct == 3         # 2, 1, 0 are three inputs
    assert counter.duplicate_calls == 0
    owner.work(2)                        # the whole chain repeats
    assert counter.duplicate_calls == 3


# ── (c) UNFINGERPRINTABLE still counts ───────────────────────────────

class _Opaque:
    """An object the value walk has no rule for."""


def test_unfingerprintable_inputs_still_count_calls(prof):
    owner = _Owner()
    ran = []
    counter = _install_on(prof, owner, "work",
                          lambda ctx: ran.append(ctx) or "ok",
                          fingerprint=prof.InputFingerprinter())
    ctx = _Opaque()
    assert owner.work(ctx) == "ok"
    assert owner.work(ctx) == "ok"       # the SAME object, twice

    assert counter.calls == 2            # counted
    assert len(ran) == 2                 # never skipped
    assert counter.unfingerprintable_calls == 2
    assert counter.distinct == 0         # joins NO duplicate population
    assert counter.duplicate_calls == 0
    assert counter.identity_duplicate_calls == 0
    assert counter.seconds >= 0.0


def test_a_fingerprint_failure_degrades_to_counting(prof, monkeypatch):
    """A raising accessor must never break the profiled build."""
    owner = _Owner()

    class _Hostile:
        def __iter__(self):
            raise RuntimeError("do not touch me")

    fingerprinter = prof.InputFingerprinter()

    def _explode(*a, **kw):
        raise RuntimeError("digest exploded")

    monkeypatch.setattr(fingerprinter, "_feed", _explode)
    counter = _install_on(prof, owner, "work", lambda x: "ok",
                          fingerprint=fingerprinter)
    assert owner.work(_Hostile()) == "ok"
    assert counter.calls == 1
    assert counter.unfingerprintable_calls == 1
    assert counter.duplicate_calls == 0


def test_identity_mode_reports_its_duplicates_in_a_separate_column(prof):
    """An identity duplicate is a WEAKER claim and is never merged."""
    owner = _Owner()
    counter = _install_on(prof, owner, "work", lambda ctx, n: n,
                          fingerprint=prof.InputFingerprinter(
                              identity_fallback=True))
    ctx = _Opaque()
    other = _Opaque()
    owner.work(ctx, 1)
    owner.work(ctx, 1)               # same object AND same value -> ident dup
    owner.work(other, 1)             # a different object is not a duplicate
    owner.work(ctx, 2)               # same object, different value

    assert counter.calls == 4
    assert counter.unfingerprintable_calls == 0
    assert counter.identity_calls == 4
    assert counter.identity_duplicate_calls == 1
    assert counter.duplicate_calls == 0          # NEVER merged
    assert counter.duplicate_seconds == 0.0
    assert counter.distinct == 3


def test_identity_mode_cannot_mint_a_duplicate_from_id_reuse(prof):
    """CPython recycles a freed object's address — the census must not.

    Measured before the fix, on the first HECA replay census:
    ``shape_constraints`` read 12,078 calls / 1,009 distinct / 11,069
    identity duplicates worth 47 s, entirely because each call was handed
    a FRESH short-lived ``GradeShape`` whose id() the allocator kept
    handing back.  A false duplicate is a fabricated defect.
    """
    owner = _Owner()
    fingerprinter = prof.InputFingerprinter(identity_fallback=True)
    counter = _install_on(prof, owner, "work", lambda ctx: None,
                          fingerprint=fingerprinter)
    for _ in range(200):
        # each object is dropped immediately, so without a keep-alive the
        # allocator hands the same address back within a few iterations
        obj = _Opaque()
        owner.work(obj)
        del obj

    assert counter.calls == 200
    assert counter.identity_duplicate_calls == 0, (
        "id() reuse minted a duplicate — the fingerprinter is not holding "
        "a reference to every object whose identity it priced")
    assert counter.distinct == 200
    # the mechanism, named: one strong reference per identity priced
    assert len(fingerprinter._alive) == 200

    # a control proving the loop really does recycle addresses without it
    recycled = set()
    for _ in range(200):
        obj = _Opaque()
        recycled.add(id(obj))
        del obj
    assert len(recycled) < 200, (
        "this platform did not reuse an address, so the twin's premise "
        "is untested here")


def test_identity_mode_still_prices_value_inputs_by_value(prof):
    owner = _Owner()
    counter = _install_on(prof, owner, "work", lambda a: a,
                          fingerprint=prof.InputFingerprinter(
                              identity_fallback=True))
    owner.work([1, 2, 3])
    owner.work([1, 2, 3])
    assert counter.duplicate_calls == 1          # a VALUE duplicate
    assert counter.identity_duplicate_calls == 0
    assert counter.identity_calls == 0


# ── arming, refusals and the report ──────────────────────────────────

def test_install_census_counters_refuses_a_double_wrapped_spec(prof):
    owner = _Owner()
    owner_name = f"_dupcensus_owner_{id(owner):x}"
    sys.modules[owner_name] = owner
    owner.work = lambda: None
    spec = f"{owner_name}:work"
    with pytest.raises(SystemExit, match="REFUSING"):
        prof.install_census_counters(count=[spec], count_inputs=[spec])


def test_install_census_counters_arms_each_mode(prof):
    owner = _Owner()
    owner_name = f"_dupcensus_owner_{id(owner):x}"
    sys.modules[owner_name] = owner
    owner.plain = lambda: None
    owner.value = lambda: None
    owner.ident = lambda: None
    counters = prof.install_census_counters(
        count=[f"{owner_name}:plain"],
        count_inputs=[f"{owner_name}:value"],
        count_inputs_identity=[f"{owner_name}:ident"],
        clock=time.process_time)
    plain, value, ident = counters
    assert plain.fingerprint is None
    assert value.fingerprint is not None and not value.fingerprint.identity_fallback
    assert ident.fingerprint is not None and ident.fingerprint.identity_fallback
    assert {c.clock_name for c in counters} == {"process_time"}


def test_from_import_aliases_are_rebound_so_the_census_cannot_undercount(prof):
    """``from module import name`` callers must reach the wrapper too."""
    import types
    owner = types.ModuleType("_dupcensus_alias_owner")
    sys.modules["_dupcensus_alias_owner"] = owner

    def work(a):
        return a * 3

    owner.work = work
    # a consumer that bound the ORIGINAL at ITS import time (finalize.py
    # binds elevation._drop_overlap_against_fixed_shapes exactly so)
    consumer = types.ModuleType("_dupcensus_alias_consumer")
    consumer.work = work
    consumer.unrelated = lambda a: a
    sys.modules["_dupcensus_alias_consumer"] = consumer

    counter = prof._install_counters(
        ["_dupcensus_alias_owner:work"],
        fingerprint=prof.InputFingerprinter())[0]

    assert owner.work(2) == 6
    assert consumer.work(2) == 6          # the aliased binding, same call
    assert counter.calls == 2
    assert counter.duplicate_calls == 1   # ... and they are ONE population
    assert "_dupcensus_alias_consumer:work" in counter.aliases
    # identity-only: an unrelated callable is never captured
    assert consumer.unrelated is not owner.work
    assert not any("unrelated" in a for a in counter.aliases)


def test_the_report_labels_both_duplicate_columns(prof):
    counter = prof.CallCounter("mod:fn", fingerprint=prof.InputFingerprinter())
    text = "\n".join(prof.census_report_lines([counter]))
    assert "DUPLICATE-WORK CENSUS" in text
    assert "identdup" in text
    assert "unfp" in text
    assert "never added together" in text


def test_both_profilers_share_one_census_implementation():
    """A second spelling of the census would be the census-wrapper defect."""
    source = (ROOT / "tools" / "profile_tile_build.py").read_text()
    assert "install_census_counters" in source
    assert "census_report_lines" in source
    assert "from profile_airport_build import" in source


def test_the_tool_index_documents_the_census():
    index = (REPO_ROOT / "tools" / "INDEX.md").read_text()
    assert "--count-inputs" in index, (
        "a tool absent from tools/INDEX.md is treated as absent "
        "(RULINGS 7e90032) — the census mode must carry its index row")
