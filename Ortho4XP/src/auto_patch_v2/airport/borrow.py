"""§44 THE PAVEMENT BORROW — a custom pack whose apt.dat authored (next
to) no pavement borrows the Global Airports block's pavement, and its
boundary when it has none (owner RULINGS 2026-09-15f; spec §44).

THE DEFECT (LGAV, the owner's tile build 2026-09-14).  The FlyTampa LGAV
pack authors its pavement as IMAGERY — 41 draped ``Ground_*.obj`` pages
declared ``ATTR_layer_group_draped markings -2``, which §42's gate
rightly refuses — and its apt.dat carries just two row-110 polygons,
both runway-length strips (369,545 m²).  The engine's precedence rule
("a Custom Scenery pack carrying the airport WITH row-110 pavement
wins") saw pavement, and LGAV was graded with ZERO taxiways and ZERO
aprons: every apron object on raw 30 m DEM.  The Global Airports block
for LGAV carries 63 pavement polygons (2,409,902 m² as a union) and one
row-130 boundary; the custom block's pavement covers 1.3 % of it.

THE LAW, in two halves:

* :func:`decide` — THE TRIGGER, called from the ONE derivation site
  (``pack.select_pack``; §44 (5)).  ``coverage = area(custom ∩ global) /
  area(global)`` of the two row-110 unions, measured in the airport frame
  (metres) built from the CUSTOM block's reference point — the borrow
  never moves the frame.  Under ``law.structures.load
  .pavement_borrow_coverage_max`` (0.25) the pack BORROWS.  A custom
  block with no row-110 rows has coverage 0 and borrows; no Global block
  → nothing borrowed; the key at 0 never borrows, at 1 always does when a
  Global block exists.
* :func:`compose` — THE COMPOSITION, called from the ONE parse site
  (``load.load_with_report``).  The Global block's row-110 polygons are
  parsed by the SAME parser and APPENDED to the custom block's own
  (borrowing ADDS, never removes: LGAV's two strips are real pavement and
  §40 classifies them as the runway's; overlaps are the planar
  partition's business, as they already are among Global's own 63), and
  the Global row-130 boundary is taken ONLY when the custom block has
  none.  NOT borrowed: runways, lines, the taxi network, startups,
  metadata, the DSF — the pack stays the pack (§44 (1), (3)).

The Global apt.dat is 383 MB and both halves need its block, so the
block read is memoised on ``(path, icao, size, mtime)`` — one scan per
build, the one ``find_apt_dat`` no longer pays for a custom pack that
wins outright.
"""
from __future__ import annotations

import dataclasses as _dc
import functools
import os
import typing as _t

from ..model.frame import Frame
from . import apt_dat as _apt

__all__ = ["BorrowDecision", "BorrowResult", "decide", "compose",
           "global_block", "find_global_block", "BORROWED_SOURCE"]

#: what a borrowed :class:`~..model.airport.Pavement` /
#: :class:`~..model.airport.Boundary` says of itself (§44 (3))
BORROWED_SOURCE = "global_airports"


@_dc.dataclass(frozen=True)
class BorrowDecision:
    """What ``select_pack`` decided.  ``apt_dat_path`` is ``""`` when
    nothing is borrowed — the only field a consumer needs to test."""

    apt_dat_path: str = ""
    block_sha256: str = ""
    #: ``"coverage"`` when the borrow fired, else why it did not
    reason: str = ""
    coverage: float = 0.0
    custom_pavements: int = 0
    global_pavements: int = 0
    coverage_max: float = 0.0


@_dc.dataclass(frozen=True)
class BorrowResult:
    """What ``compose`` did: the airport block with the borrowed records
    appended, and the census §44 (4) reports."""

    airport: _apt.AptAirport
    custom_pavements: int = 0
    borrowed_pavements: int = 0
    borrowed_boundary: bool = False
    decision: BorrowDecision = _dc.field(default_factory=BorrowDecision)

    @property
    def borrowed(self) -> bool:
        return bool(self.decision.apt_dat_path)

    def record(self, pack_name: str) -> dict[str, _t.Any]:
        """``report.load.pavement_source`` (§44 (4))."""
        d = self.decision
        return {"pack": pack_name,
                "borrowed_from": d.apt_dat_path or None,
                "coverage": round(d.coverage, 6),
                "custom_pavements": self.custom_pavements,
                "borrowed_pavements": self.borrowed_pavements,
                "borrowed_boundary": self.borrowed_boundary,
                "reason": d.reason,
                "coverage_max": d.coverage_max}

    def line(self, icao: str) -> str:
        """THE ONE log line (§44 (4)); ``""`` when nothing was borrowed."""
        if not self.borrowed:
            return ""
        d = self.decision
        what = "pavement + boundary" if self.borrowed_boundary else "pavement"
        return (f"{icao}: the pack's apt.dat carries {self.custom_pavements} "
                f"pavement(s) covering {100 * d.coverage:.1f} % of Global "
                f"Airports' {d.global_pavements} "
                f"(< {100 * d.coverage_max:.0f} %): {what} BORROWED from "
                f"{d.apt_dat_path} (§44)")


# ── the block read, memoised ─────────────────────────────────────────────

def _stamp(path: str) -> tuple[int, float]:
    st = os.stat(path)
    return (st.st_size, st.st_mtime)


@functools.lru_cache(maxsize=8)
def _block_cached(path: str, icao: str,
                  _stamp_: tuple[int, float]) -> tuple[str, ...] | None:
    lines = _apt.read_airport_block(path, icao)
    return tuple(lines) if lines else None


def global_block(path: str, icao: str) -> list[str] | None:
    """``icao``'s block in the Global Airports file, read once per build
    (the file is 383 MB; both halves of §44 need the same block)."""
    try:
        lines = _block_cached(path, icao.upper(), _stamp(path))
    except OSError:
        return None
    return list(lines) if lines else None


def find_global_block(xplane_root: str, icao: str,
                      exclude: str = "") -> tuple[str, list[str] | None]:
    """``(path, block)`` of the first Global Airports candidate carrying
    ``icao`` (``apt_dat.global_candidates`` order), ``("", None)`` when
    none does.  The has-check and the read are the SAME walk — asking
    twice would scan 383 MB twice (single-pass principle)."""
    for p in _apt.global_candidates(xplane_root):
        if not os.path.isfile(p):
            continue
        if exclude and os.path.realpath(p) == os.path.realpath(exclude):
            continue
        b = global_block(p, icao)
        if b:
            return p, b
    return "", None


# ── (2) the trigger ──────────────────────────────────────────────────────

def _to_xy(frame: Frame) -> _t.Callable[[float, float], tuple[float, float]]:
    """§46 (9) census row 2: apt.dat row-110 rings are INPUT — the ENTRY
    projection, never the exact one."""
    return frame.entry()


def _union(pavements: _t.Sequence[_apt.AptPavement],
           to_xy: _t.Callable[[float, float], tuple[float, float]]):
    """The row-110 union in the airport frame, or ``None`` when empty."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = []
    for p in pavements:
        ext = [to_xy(lo, la) for lo, la in p.rings[0]]
        if len(ext) < 3:
            continue
        holes = [[to_xy(lo, la) for lo, la in r] for r in p.rings[1:]
                 if len(r) >= 3]
        poly = Polygon(ext, holes)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not poly.is_empty:
            polys.append(poly)
    if not polys:
        return None
    u = unary_union(polys)
    return None if u.is_empty else u


def coverage_of(custom: _apt.AptAirport, glob: _apt.AptAirport,
                frame: Frame) -> float:
    """``area(custom ∩ global) / area(global)`` in ``frame``'s metres.
    ``0.0`` when the custom block has no pavement; ``1.0`` when the
    Global union is degenerate (nothing to borrow against)."""
    to_xy = _to_xy(frame)
    gu = _union(glob.pavements, to_xy)
    if gu is None or gu.area <= 0.0:
        return 1.0
    cu = _union(custom.pavements, to_xy)
    if cu is None:
        return 0.0
    try:
        inter = cu.intersection(gu)
    except Exception:                       # GEOS on a pathological ring
        inter = cu.buffer(0).intersection(gu.buffer(0))
    return float(inter.area) / float(gu.area)


def decide(xplane_root: str, icao: str, custom_apt_path: str,
           law) -> BorrowDecision:
    """§44 (2), at the ONE derivation site.  ``law`` is the airport's
    :class:`~...law.Law`; ``custom_apt_path`` the selected custom pack's
    apt.dat.  Never raises: a block that cannot be read or projected
    borrows nothing."""
    cmax = float(law.tables.structures.load.pavement_borrow_coverage_max)
    if cmax <= 0.0:
        return BorrowDecision(reason="coverage_max 0: the borrow is off",
                              coverage_max=cmax)
    gpath, gblock = find_global_block(xplane_root, icao,
                                      exclude=custom_apt_path)
    if not gblock:
        return BorrowDecision(reason="no Global Airports block",
                              coverage_max=cmax)
    cblock = _apt.read_airport_block(custom_apt_path, icao)
    if not cblock:
        return BorrowDecision(reason="no custom block", coverage_max=cmax)
    try:
        custom = _apt.parse_airport_block(cblock)
        glob = _apt.parse_airport_block(gblock)
        from ..law.tables import identity_dp, input_quantum_m
        # THE CUSTOM BLOCK'S FRAME — the borrow does not move it (§44 (2))
        frame = Frame(icao.upper(), custom.reference_point(), identity_dp(law),
                      input_quantum_m=input_quantum_m(law))
        cov = coverage_of(custom, glob, frame)
    except Exception as exc:                # a block v2 cannot project
        return BorrowDecision(reason=f"not measurable: {exc}",
                              coverage_max=cmax)
    common = dict(coverage=cov, custom_pavements=len(custom.pavements),
                  global_pavements=len(glob.pavements), coverage_max=cmax)
    if cov >= cmax:
        return BorrowDecision(reason="coverage at or above the key", **common)
    return BorrowDecision(apt_dat_path=gpath,
                          block_sha256=_apt.block_sha256(gblock),
                          reason="coverage", **common)


# ── (3) the composition ──────────────────────────────────────────────────

def compose(decision: BorrowDecision, icao: str,
            apt: _apt.AptAirport) -> BorrowResult:
    """§44 (3), at the ONE parse site.  The Global block's row-110
    polygons appended to ``apt``'s own (re-indexed so every id stays
    unique) and its row-130 boundary taken ONLY when ``apt`` has none.
    Nothing else of the Global block is read."""
    n_custom = len(apt.pavements)
    if not decision.apt_dat_path:
        return BorrowResult(apt, n_custom, 0, False, decision)
    gblock = global_block(decision.apt_dat_path, icao)
    if not gblock:
        return BorrowResult(apt, n_custom, 0, False,
                            _dc.replace(decision, apt_dat_path="",
                                        block_sha256="",
                                        reason="the Global block vanished"))
    glob = _apt.parse_airport_block(gblock)
    borrowed = tuple(_dc.replace(p, index=n_custom + k)
                     for k, p in enumerate(glob.pavements))
    boundaries = apt.boundaries
    took_boundary = False
    if not boundaries and glob.boundaries:
        boundaries = (_dc.replace(glob.boundaries[0], index=0),)
        took_boundary = True
    return BorrowResult(
        _dc.replace(apt, pavements=apt.pavements + borrowed,
                    boundaries=boundaries),
        n_custom, len(borrowed), took_boundary, decision)
