"""THE CALL CENSUS — counters and input fingerprints for a profiled run.

THE v1 AIRPORT PROFILER THAT LIVED HERE IS RETIRED (stage B round 2 of the v1
retirement, lane ``v1cut``, 2026-10-04): its wall-clock sampler bucketed
stacks by ``auto_patch/pipeline.py`` step lines and its two targets were
``pipeline.build_airport_pavement`` and ``solve_cut.replay``.  ``main``
REFUSES BY NAME.  What remains is the engine-neutral census library
``tools/profile_tile_build.py`` imports (``install_census_counters`` /
``census_report_lines``), under its original name so that import is unmoved.

``--count MODULE:ATTR`` (repeatable) additionally wraps a named callable
with a call counter and an inclusive timer, for questions a sampler
cannot answer ("is this memo missing, or is the miss expensive?").  The
wrapper is installed for the profiled run only, on either target.

``--count-inputs MODULE:ATTR`` (repeatable) is the DUPLICATE-WORK CENSUS
mode: the same counter, plus an INPUT FINGERPRINT taken BEFORE each call
(after the call the inputs may have been mutated).  It answers the
owner's question "are we computing anything twice per build" with a
measurement instead of an assertion — per callable: calls, DISTINCT
fingerprints, DUPLICATE calls (a fingerprint already seen in this run)
and the inclusive seconds those duplicate calls spent.

The fingerprint is structural and by VALUE: scalars/str/bytes by value,
shapely geometries through ``shapely.to_wkb``, numpy arrays through
dtype + shape + ``tobytes``, tuples/lists/dicts recursively (in order),
sets by their sorted member digests.  An input with no rule — an
arbitrary object, a generator, anything the walk cannot price — makes
the WHOLE call ``UNFINGERPRINTABLE``: it is still counted as a call, it
never joins the duplicate population, and nothing is guessed.
``--count-inputs-identity MODULE:ATTR`` is the same census with one
addition: an object with no value rule falls back to ``type:id(obj)``,
and those calls' duplicates are reported in their OWN column, never
merged with the value-duplicate column — an identity duplicate says
"the same object was handed in again", which is a weaker claim than
"the same value was handed in again" and is labelled as one everywhere.
That mode is what makes a context-taking callable (``shape_constraints``,
``final_grade_projection``, the unified-graph builders) measurable at
all; the two columns are never added together.

The census is OBSERVATION-ONLY: the wrapper returns exactly what the
wrapped callable returns, fingerprinting reads inputs through pure
accessors and never mutates them, a fingerprinting FAILURE degrades to
counting (never to skipping the call), and the seconds spent
fingerprinting are measured separately and EXCLUDED from the inclusive
totals, so a duplicate-seconds figure is the wrapped work's own time.

``--count-clock {wall,cpu}`` selects the counters' clock: ``wall``
(``time.perf_counter``, the default, what a build's own numbers are) or
``cpu`` (``time.process_time``, this process's own CPU seconds — the
clock to use when other lanes hold the same machine).
"""

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Self-contained and ahead of every
# other import because a tool's own ``--help`` carries the house spelling
# (``Δ``, ``ε``, ``≥``, ``→``) and a Windows console RAISES on those
# rather than mangling them.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse
import collections
import hashlib
import os
import sys
import threading
import time

os.environ.setdefault("O4_LOG_VERBOSITY", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (os.path.join(ROOT, "src"), ROOT, os.path.join(ROOT, "tests"),
             os.path.join(ROOT, "tools")):
    if path not in sys.path:
        sys.path.insert(0, path)

# ── the input fingerprint (duplicate-work census) ────────────────────
#
# Everything below is READ-ONLY over the call's inputs: ``to_wkb`` and
# ``tobytes`` are pure, the containers are only iterated, and nothing is
# sorted in place.  A component the walk has no rule for is a REFUSAL
# (``_Unfingerprintable``), never a guess — a wrong duplicate is a
# fabricated defect, and this instrument's whole product is a list of
# suspected duplicates.

_FP_MAX_BYTES = 64 * 1024 * 1024   # per call; beyond it, UNFINGERPRINTABLE
_FP_MAX_DEPTH = 12                 # nesting; beyond it, UNFINGERPRINTABLE


class _Unfingerprintable(Exception):
    """This input has no value rule — the call is not fingerprintable."""


class InputFingerprinter:
    """Digest a call's ``(args, kwargs)`` by VALUE, or refuse.

    ``digest`` returns ``(kind, hexdigest)`` where ``kind`` is
    ``"value"`` (every component priced by value) or ``"identity"``
    (identity fallback used for at least one component — only possible
    with ``identity_fallback=True``), or ``None`` for UNFINGERPRINTABLE.
    It never raises and never mutates its inputs.
    """

    def __init__(self, identity_fallback: bool = False):
        self.identity_fallback = identity_fallback
        # ── THE id() REUSE TRAP, and why this dict exists ────────────
        # CPython recycles the address of a freed object, so a callable
        # handed a FRESH short-lived object on every call can be given
        # the same ``id()`` over and over.  MEASURED on the first HECA
        # replay census before this fix: ``grade_graph.shape_constraints``
        # read 12,078 calls / 1,009 distinct / 11,069 "identity
        # duplicates" worth 47 s — a headline finding that was an
        # allocator artifact, not repeated work.  Holding ONE strong
        # reference per identity-fingerprinted object makes that
        # impossible: an id this run has priced can never be reused
        # while the run lasts.  The cost is memory (one reference per
        # DISTINCT object, live for the run) and it is paid knowingly:
        # a census that mints false duplicates is worse than useless,
        # because its entire product is a list of suspected defects.
        self._alive = {}

    # -- public -------------------------------------------------------
    def digest(self, args, kwargs):
        hasher = hashlib.blake2b(digest_size=16)
        state = {"budget": _FP_MAX_BYTES, "identity": False}
        try:
            self._feed(hasher, tuple(args), 0, state)
            # kwargs are keyword-ordered by name so two spellings of the
            # same call agree; keys are strings by construction.
            self._feed(hasher, tuple(sorted(kwargs.items())), 0, state)
        except Exception:
            # ANY failure degrades to counting.  A fingerprint that
            # crashes a build is not observation-only.
            return None
        kind = "identity" if state["identity"] else "value"
        return kind, f"{kind}:{hasher.hexdigest()}"

    # -- internals ----------------------------------------------------
    @staticmethod
    def _bump(hasher, tag: bytes, state, payload: bytes = b""):
        state["budget"] -= len(payload) + len(tag)
        if state["budget"] < 0:
            raise _Unfingerprintable("fingerprint budget exhausted")
        hasher.update(tag)
        hasher.update(len(payload).to_bytes(8, "little"))
        hasher.update(payload)

    def _child(self, obj, depth, state) -> bytes:
        sub = hashlib.blake2b(digest_size=16)
        self._feed(sub, obj, depth, state)
        return sub.digest()

    def _feed(self, hasher, obj, depth, state):
        if depth > _FP_MAX_DEPTH:
            raise _Unfingerprintable("too deep")
        if obj is None:
            return self._bump(hasher, b"none", state)
        if obj is True or obj is False:
            return self._bump(hasher, b"bool", state, b"\x01" if obj else b"\x00")
        if isinstance(obj, int):
            return self._bump(hasher, b"int", state, repr(obj).encode())
        if isinstance(obj, float):
            # repr round-trips exactly, and distinguishes -0.0 from 0.0
            # and every NaN payload spelling from the others.
            return self._bump(hasher, b"float", state, repr(obj).encode())
        if isinstance(obj, complex):
            return self._bump(hasher, b"complex", state, repr(obj).encode())
        if isinstance(obj, str):
            return self._bump(hasher, b"str", state, obj.encode("utf-8", "surrogatepass"))
        if isinstance(obj, (bytes, bytearray, memoryview)):
            return self._bump(hasher, b"bytes", state, bytes(obj))

        payload = self._numpy_payload(obj)
        if payload is not None:
            return self._bump(hasher, b"ndarray", state, payload)
        payload = self._shapely_payload(obj)
        if payload is not None:
            return self._bump(hasher, b"geom", state, payload)

        if isinstance(obj, (tuple, list)):
            self._bump(hasher, b"seq[" if isinstance(obj, list) else b"seq(", state,
                       len(obj).to_bytes(8, "little"))
            for item in obj:
                self._feed(hasher, item, depth + 1, state)
            return None
        if isinstance(obj, (set, frozenset)):
            # A set has no order: hash the SORTED member digests.
            members = sorted(self._child(item, depth + 1, state) for item in obj)
            self._bump(hasher, b"set", state, b"".join(members))
            return None
        if isinstance(obj, dict):
            self._bump(hasher, b"dict", state, len(obj).to_bytes(8, "little"))
            for key, value in obj.items():
                self._feed(hasher, key, depth + 1, state)
                self._feed(hasher, value, depth + 1, state)
            return None

        if self.identity_fallback:
            state["identity"] = True
            marker = id(obj)
            self._alive.setdefault(marker, obj)   # id() can never be reused
            token = f"{type(obj).__module__}.{type(obj).__qualname__}#{marker}"
            return self._bump(hasher, b"ident", state, token.encode())
        raise _Unfingerprintable(f"no value rule for {type(obj)!r}")

    @staticmethod
    def _numpy_payload(obj):
        numpy = sys.modules.get("numpy")
        if numpy is None:
            return None
        if isinstance(obj, numpy.ndarray):
            # ascontiguousarray is a no-op for the common case and a COPY
            # otherwise; it never touches the caller's array.
            arr = numpy.ascontiguousarray(obj)
            head = f"{arr.dtype.str}|{arr.shape}|".encode()
            return head + arr.tobytes()
        if isinstance(obj, numpy.generic):
            return f"{obj.dtype.str}|".encode() + obj.tobytes()
        return None

    @staticmethod
    def _shapely_payload(obj):
        shapely = sys.modules.get("shapely")
        if shapely is None:
            return None
        base = getattr(sys.modules.get("shapely.geometry.base"), "BaseGeometry", None)
        if base is None or not isinstance(obj, base):
            return None
        to_wkb = getattr(shapely, "to_wkb", None)
        if to_wkb is not None:
            # ISO WKB (shapely's default flavour) encodes the geometry
            # TYPE and its DIMENSION, so a 3D ring cannot collide with
            # its 2D twin and a LineString cannot collide with a ring
            # spelled over the same coordinates.
            return to_wkb(obj)
        return obj.wkb


class CallCounter:
    """Call count + INCLUSIVE seconds for one named callable.

    Reentrancy is tracked with a depth counter so a recursive or
    mutually-nested target is not double-counted into its own inclusive
    total (the outermost activation owns the interval).

    ``clock`` selects what "seconds" means.  The default is
    ``time.perf_counter`` — WALL time, which is what a build's own
    numbers are and what the sampler's attribution is measured against.
    A caller measuring a CPU-bound sink while other lanes hold the same
    machine passes ``time.process_time`` instead: this process's own CPU
    seconds, which do not move when someone else's build lands on the
    other cores (measured 2026-08-13: load average 32 moved a
    ``contact_graph`` wall total by 65 % between two identical arms).
    The clock is recorded on the counter so a report can never present
    one as the other.

    ``fingerprint`` (an :class:`InputFingerprinter`) turns the counter
    into the DUPLICATE-WORK CENSUS: each call's inputs are digested
    BEFORE the call, and a digest already seen in this run makes the
    call a DUPLICATE.  Value duplicates and identity duplicates are
    counted in separate fields and are never added together.  The
    seconds spent fingerprinting are accumulated in
    ``fingerprint_seconds`` and are NOT part of ``seconds`` — the
    instrument's own tax never lands on the measured work.
    """

    def __init__(self, label, clock=None, fingerprint=None):
        self.label = label
        self.clock = clock or time.perf_counter
        self.clock_name = getattr(self.clock, "__name__", "perf_counter")
        self.calls = 0
        self.seconds = 0.0
        self.fingerprint = fingerprint
        self.fingerprint_seconds = 0.0
        self.duplicate_calls = 0
        self.duplicate_seconds = 0.0
        self.identity_calls = 0
        self.identity_duplicate_calls = 0
        self.identity_duplicate_seconds = 0.0
        self.unfingerprintable_calls = 0
        self.aliases = []
        self._seen = {}
        self._depth = 0

    @property
    def distinct(self):
        """Distinct input fingerprints seen (0 when not fingerprinting)."""
        return len(self._seen)

    def _census(self, a, kw):
        """Fingerprint one call's inputs; return (kind, seen_before)."""
        t0 = self.clock()
        try:
            result = self.fingerprint.digest(a, kw)
        except Exception:                       # pragma: no cover - digest
            result = None                       # already swallows its own
        self.fingerprint_seconds += self.clock() - t0
        if result is None:
            self.unfingerprintable_calls += 1
            return None, False
        kind, key = result
        if kind == "identity":
            self.identity_calls += 1
        seen_before = key in self._seen
        self._seen[key] = self._seen.get(key, 0) + 1
        if seen_before:
            if kind == "value":
                self.duplicate_calls += 1
            else:
                self.identity_duplicate_calls += 1
        return kind, seen_before

    def wrap(self, fn):
        def wrapper(*a, **kw):
            self.calls += 1
            kind, seen_before = None, False
            if self.fingerprint is not None:
                kind, seen_before = self._census(a, kw)
            if self._depth:
                return fn(*a, **kw)
            self._depth = 1
            t0 = self.clock()
            try:
                return fn(*a, **kw)
            finally:
                self._depth = 0
                elapsed = self.clock() - t0
                self.seconds += elapsed
                if seen_before:
                    if kind == "value":
                        self.duplicate_seconds += elapsed
                    else:
                        self.identity_duplicate_seconds += elapsed
        wrapper.__name__ = getattr(fn, "__name__", self.label)
        wrapper.__wrapped__ = fn
        return wrapper


def _install_counters(specs, clock=None, fingerprint=None):
    """Wrap each ``MODULE:ATTR`` spec; return the counters (install order).

    ``ATTR`` may be DOTTED (``O4_Vector_Utils:Vector_Map.insert_edge``) to
    reach a method: the owner of the last component is walked to, and the
    wrapper is a plain function, so the descriptor protocol re-binds it as
    a method exactly as the original was.  Added for the tile lane, whose
    sinks are all methods of one class.

    ``fingerprint`` — an :class:`InputFingerprinter` — installs the
    DUPLICATE-WORK CENSUS on every counter made here.  One instance may
    be shared by every spec: the fingerprinter holds no per-callable
    state (the seen-set lives on the counter), so each callable keeps
    its own duplicate population.
    """
    import importlib
    counters = []
    for spec in specs:
        mod_name, _, attr = spec.partition(":")
        if not attr:
            raise SystemExit(f"--count wants MODULE:ATTR, got {spec!r}")
        module = importlib.import_module(mod_name)
        owner = module
        parts = attr.split(".")
        for part in parts[:-1]:
            owner = getattr(owner, part)
        target = getattr(owner, parts[-1])
        counter = CallCounter(spec, clock=clock, fingerprint=fingerprint)
        wrapper = counter.wrap(target)
        setattr(owner, parts[-1], wrapper)
        if len(parts) == 1:
            counter.aliases = rebind_aliases(module, target, wrapper)
        counters.append(counter)
    return counters


def rebind_aliases(owner_module, original, wrapper):
    """Point every OTHER live binding of ``original`` at ``wrapper``.

    THE SILENT-UNDERCOUNT HAZARD this closes: wrapping ``MODULE:ATTR``
    replaces one module-dictionary entry, so a caller that did
    ``from module import name`` at ITS import time still holds — and
    still calls — the ORIGINAL.  ``finalize.py`` binds
    ``elevation._drop_overlap_against_fixed_shapes`` exactly that way
    while ``pipeline.py`` imports it at CALL time, so a counter on the
    ``elevation`` spelling reports two of the three calls and looks
    right doing it.  A census that undercounts by an import style is
    the census-wrapper defect in its smallest form.

    The sweep is by OBJECT IDENTITY only — never by name — so it can
    never capture an unrelated callable, and every binding it moved is
    recorded on the counter and PRINTED with the report, because the
    reader has to know which call sites a number covers.
    """
    rebound = []
    for mod_name, module in list(sys.modules.items()):
        if module is None or module is owner_module:
            continue
        namespace = getattr(module, "__dict__", None)
        if not isinstance(namespace, dict):
            continue
        for attr_name, value in list(namespace.items()):
            if value is not original:
                continue
            try:
                setattr(module, attr_name, wrapper)
            except Exception:
                continue
            rebound.append(f"{mod_name}:{attr_name}")
    return rebound


def install_census_counters(count=(), count_inputs=(), count_inputs_identity=(),
                            clock=None):
    """Install the plain counters and both census modes; return the list.

    ONE implementation of the three-list arming, shared by this
    profiler's CLI and ``profile_tile_build.py``'s — a second, slightly
    different spelling of "which spec gets which fingerprinter" is the
    census-wrapper defect in miniature.  A spec named in more than one
    list is REFUSED: double-wrapping would count every call twice and
    silently halve the duplicate fraction.
    """
    seen = {}
    for name, specs in (("--count", count), ("--count-inputs", count_inputs),
                        ("--count-inputs-identity", count_inputs_identity)):
        for spec in specs:
            if spec in seen:
                raise SystemExit(
                    f"REFUSING: {spec!r} named by both {seen[spec]} and "
                    f"{name}.  Double-wrapping one callable counts every "
                    f"call twice and halves its duplicate fraction — name "
                    f"it once, in the mode you want.")
            seen[spec] = name
    counters = []
    counters += _install_counters(list(count), clock=clock)
    counters += _install_counters(list(count_inputs), clock=clock,
                                  fingerprint=InputFingerprinter(False))
    counters += _install_counters(list(count_inputs_identity), clock=clock,
                                  fingerprint=InputFingerprinter(True))
    return counters


def census_report_lines(counters):
    """The counted-callables + duplicate-census report block."""
    lines = []
    if not counters:
        return lines
    clocks = sorted({c.clock_name for c in counters})
    lines.append(f"\n== Counted callables (inclusive, clock={'/'.join(clocks)}) ==")
    for counter in counters:
        lines.append(f"  {counter.seconds:8.1f} s  {counter.calls:9d} "
                     f"call(s)  {counter.label}")
    census = [c for c in counters if c.fingerprint is not None]
    if not census:
        return lines
    lines.append("\n== DUPLICATE-WORK CENSUS (input fingerprints) ==")
    lines.append("  A duplicate call is one whose INPUT FINGERPRINT was already "
                 "seen in this run.")
    lines.append("  'value' duplicates were priced by value; 'ident' duplicates "
                 "only mean THE SAME OBJECT")
    lines.append("  was handed in again (weaker claim) — the two columns are "
                 "never added together.")
    lines.append("  'unfp' calls could not be fingerprinted and join NO "
                 "duplicate population.")
    lines.append("  fp-secs is the instrument's own tax and is EXCLUDED from "
                 "the seconds columns.")
    header = (f"  {'calls':>8} {'distinct':>9} {'dup':>7} {'dup s':>9} "
              f"{'identdup':>9} {'ident s':>9} {'unfp':>7} {'fp-secs':>8}  callable")
    lines.append(header)
    for counter in sorted(census, key=lambda c: -c.duplicate_seconds):
        lines.append(
            f"  {counter.calls:8d} {counter.distinct:9d} "
            f"{counter.duplicate_calls:7d} {counter.duplicate_seconds:9.2f} "
            f"{counter.identity_duplicate_calls:9d} "
            f"{counter.identity_duplicate_seconds:9.2f} "
            f"{counter.unfingerprintable_calls:7d} "
            f"{counter.fingerprint_seconds:8.2f}  {counter.label}")
    aliased = [c for c in counters if c.aliases]
    if aliased:
        lines.append("\n  -- from-import bindings rebound onto the wrapper "
                     "(the call sites these numbers cover) --")
        for counter in aliased:
            lines.append(f"     {counter.label} <- {', '.join(counter.aliases)}")
    return lines


def main():
    """THE AIRPORT PROFILER IS RETIRED WITH v1 — REFUSES BY NAME.

    Its sampler bucketed stacks by ``auto_patch/pipeline.py`` step lines and
    its targets were ``pipeline.build_airport_pavement`` and
    ``solve_cut.replay`` — all three went with the v1 engine (stage B round
    2, lane ``v1cut``, 2026-10-04).  The CALL CENSUS below (``--count`` /
    ``--count-inputs``) is engine-neutral and stays as the library
    ``tools/profile_tile_build.py`` imports.
    """
    raise SystemExit(
        "REFUSED: profile_airport_build.py profiled the v1 pipeline "
        "(auto_patch.pipeline / solve_cut), retired 2026-10-04. v2 publishes "
        "its own stage clocks in <ICAO>.report.json (wall_s) and "
        "tools/v2_solve_replay.py replays a stage; whole-tile profiling is "
        "tools/profile_tile_build.py, which imports this module's call "
        "census.")


if __name__ == "__main__":
    main()
