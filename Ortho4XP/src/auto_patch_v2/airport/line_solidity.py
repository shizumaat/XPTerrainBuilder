"""WHAT A LINE OBJECT IS MADE OF — read from its geometry and its
texture, never from its name (issue #2054; owner 2026-11-13 15:36Z: "smart
enough logic to determine if it's a wire fence, or low concrete barriers
that have to sit on the upper flat level, or if it's a solid wall that
should be a retaining wall and seat at the bottom").

A pure MEASUREMENT of one placed resource — an OBJ8, or a ``.fac`` with
the objects its walls attach — in its authored frame:

* ``base_y`` / ``top_y`` — the lowest and highest authored ``y``: a part
  under ``y = 0`` is authored BELOW the ground its zero stands on (a
  buried footing);
* ``solid_top_y`` — the top of the OPAQUE BAND rising from the base: the
  faces are sampled on a barycentric grid, each sample takes the
  texture's COVERAGE at its UV (its alpha box-filtered, so a cutout reads
  the share of wire over hole), and the band ends at the first
  :data:`BIN_M` slice whose opaque share falls under
  :data:`OPAQUE_SHARE`.  A chain-link fence on a concrete barrier
  (KSFO ``Fence_Concrete_Barrier.fac``) reads its barrier; a wire fence
  reads its foot; a solid wall reads its whole height;
* ``opaque_share`` — the opaque share of all its faces;
* ``half_width_m`` — half the plan width (``x``, across a facade wall)
  of the geometry within :data:`FOOT_M` of the base: the base a paved
  level must reach past.

:func:`kind_of` names the CLASS (wire fence / low barrier / solid wall /
retaining wall) from the thresholds the CALLER hands it (``classify/
rules.toml`` ``[service]`` ``line_*``, the record ``airport/wall_class``
takes); what a class does to the layout is decided by its
readers (``classify/edge_line_mint``)."""
from __future__ import annotations

import dataclasses as _dc
import os
import typing as _t

import numpy as np

__all__ = ["Solidity", "obj_solidity", "facade_solidity", "kind_of", "ON_TOP",
           "WIRE_FENCE", "LOW_BARRIER", "SOLID_WALL", "RETAINING_WALL", "ELEVATED", "BIN_M",
           "OPAQUE_SHARE", "FOOT_M"]

#: the height slice the opaque band is read in
BIN_M = 0.25
#: a slice is SOLID when at least this share of its face area is opaque
OPAQUE_SHARE = 0.5
#: the foot band whose plan width is the object's base
FOOT_M = 0.5
#: the texture is read box-filtered to this many pixels a side: a sample
#: then reads the COVERAGE of a fine cutout (a chain-link's wires over its
#: holes), never one wire or one hole
_TEX_PX = 128
#: the barycentric sample grid per triangle: the centres of the n x n
#: sub-triangles' lattice (weights equal)
_N = 8
_BARY = np.array([((i + 1 / 3) / _N, (j + 1 / 3) / _N, 1.0 - (i + j + 2 / 3) / _N)
                  for i in range(_N) for j in range(_N - i)])


@_dc.dataclass(frozen=True)
class Solidity:
    """One resource's measured make-up (module doc)."""

    base_y: float
    top_y: float
    solid_top_y: float
    opaque_share: float
    half_width_m: float

    @property
    def solid_m(self) -> float:
        """The height of the opaque band from the base."""
        return max(0.0, self.solid_top_y - self.base_y)

    @property
    def buried_m(self) -> float:
        """How far the geometry is authored under its zero."""
        return max(0.0, -self.base_y)


_ALPHA: dict[str, _t.Any] = {}


def _alpha(path: str | None):
    """The texture's alpha as ``(h, w)`` floats 0..1, box-filtered to
    :data:`_TEX_PX`; ``None`` = no texture known (every sample then reads
    opaque)."""
    if not path:
        return None
    if path not in _ALPHA:
        try:
            from PIL import Image
            with Image.open(path) as im:
                a = im.convert("RGBA").getchannel("A").resize(
                    (min(_TEX_PX, im.width), min(_TEX_PX, im.height)), Image.BOX)
            _ALPHA[path] = np.asarray(a, dtype=float) / 255.0
        except Exception:               # an unreadable texture is no witness
            _ALPHA[path] = None
    return _ALPHA[path]


def _opaque(sy: np.ndarray, su: np.ndarray, sv: np.ndarray, alpha: _t.Sequence
            ) -> np.ndarray:
    """Per sample, the opacity (0..1) of the texture its triangle draws."""
    out = np.ones(sy.shape, dtype=float)
    for a in {id(x): x for x in alpha if x is not None}.values():
        rows = np.array([x is a for x in alpha])
        h, w = a.shape
        px = np.clip(((su[rows] % 1.0) * w).astype(int), 0, w - 1)
        py = np.clip(((1.0 - sv[rows] % 1.0) * h).astype(int), 0, h - 1)
        out[rows] = a[py, px]
    return out


def _measure(xyz: np.ndarray, uv: np.ndarray, alpha: _t.Sequence) -> Solidity | None:
    """``xyz`` ``(n, 3, 3)`` and ``uv`` ``(n, 3, 2)`` triangles; ``alpha``
    per triangle (the texture's alpha array or ``None``)."""
    if xyz.shape[0] == 0:
        return None
    ys = xyz[:, :, 1]
    base, top = float(ys.min()), float(ys.max())
    area = 0.5 * np.linalg.norm(np.cross(xyz[:, 1] - xyz[:, 0],
                                         xyz[:, 2] - xyz[:, 0]), axis=1)
    sy = np.einsum("kj,nj->nk", _BARY, ys)                  # (n, k) sample y
    opaque = _opaque(sy, np.einsum("kj,nj->nk", _BARY, uv[:, :, 0]),
                     np.einsum("kj,nj->nk", _BARY, uv[:, :, 1]), alpha)
    wgt = np.repeat(area[:, None] / sy.shape[1], sy.shape[1], axis=1)
    total = float(wgt.sum())
    share = float((wgt * opaque).sum() / total) if total > 0.0 else 0.0
    solid_top = top                     # opaque all the way up, unless a slice says not
    nbin = max(1, int(np.ceil((top - base) / BIN_M)))
    b = np.clip(((sy - base) / BIN_M).astype(int), 0, nbin - 1)
    for k in range(nbin):
        m = b == k
        tot = float(wgt[m].sum())
        if tot > 0.0 and float((wgt * opaque)[m].sum()) / tot < OPAQUE_SHARE:
            solid_top = base + k * BIN_M      # an empty slice is no witness
            break
    foot = xyz[:, :, 0][ys <= base + FOOT_M]
    half = float((foot.max() - foot.min()) / 2.0) if foot.size else 0.0
    return Solidity(base, top, solid_top, share, half)


def _texture(owner: str, name: str | None) -> str | None:
    if not name:
        return None
    from .dsf import texture_file
    return texture_file(owner, name)


def _obj_tris(path: str, dy: float = 0.0):
    """``(xyz, uv, alpha)`` of an OBJ8's solid triangles (authored frame,
    lifted ``dy``)."""
    from .obj8 import _floats, parse_obj8
    g = parse_obj8(path)
    tex = None
    vt: list[bytes] = []
    with open(path, "rb") as fh:
        for ln in fh:
            s = ln.strip()
            if s.startswith(b"VT"):
                vt.append(s[2:])
            elif tex is None and s.split(None, 1)[:1] == [b"TEXTURE"]:
                parts = s.split(None, 1)
                tex = parts[1].decode("utf-8", "replace").strip() if len(parts) == 2 else None
    uvs = _floats(vt, 8)[:, 6:8] if vt else np.zeros((0, 2))
    tri = g.solid
    if tri.shape[0] == 0 or uvs.shape[0] < g.vertices.shape[0]:
        return np.zeros((0, 3, 3)), np.zeros((0, 3, 2)), []
    xyz = g.vertices[tri] + np.array([0.0, dy, 0.0])
    a = _alpha(_texture(path, tex))
    return xyz, uvs[tri], [a] * tri.shape[0]


def obj_solidity(path: str) -> Solidity | None:
    """THE MEASUREMENT of one OBJ8 file (module doc); ``None`` when it
    has no solid face or cannot be read."""
    try:
        return _measure(*_obj_tris(path))
    except (OSError, ValueError, IndexError):
        return None


def _fac_mesh(path: str):
    """The ``.fac``'s own wall meshes ``(xyz, uv)``, its texture, and the
    ``(object, y)`` of every segment attachment."""
    tex, objects = None, []
    verts: list[list[float]] = []
    tris: list[list[int]] = []
    attach: set[tuple[str, float]] = set()
    base = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            t = raw.split()
            if not t:
                continue
            k = t[0]
            try:
                if k == "TEXTURE" and tex is None and len(t) > 1:
                    tex = raw.split(None, 1)[1].strip()
                elif k == "OBJ" and len(t) > 1:
                    objects.append(raw.split(None, 1)[1].strip().replace("\\", "/"))
                elif k == "MESH":
                    base = len(verts)
                elif k == "VERTEX" and len(t) >= 9:
                    verts.append([float(x) for x in t[1:9]])
                elif k == "IDX":
                    ids = [base + int(x) for x in t[1:]]
                    tris.extend(ids[i:i + 3] for i in range(0, len(ids) - 2, 3))
                elif k in ("ATTACH_GRADED", "ATTACH_DRAPED") and len(t) >= 6:
                    oi = int(t[1])
                    if 0 <= oi < len(objects):
                        attach.add((objects[oi], float(t[3])))
            except ValueError:
                continue
    v = np.asarray(verts, dtype=float).reshape(-1, 8)
    tri = np.asarray([x for x in tris if max(x) < len(v)],
                     dtype=np.int64).reshape(-1, 3)
    return v[tri][:, :, :3], v[tri][:, :, 6:8], tex, sorted(attach)


def _fac_v800(path: str):
    """A v800 (TYPE 1) facade's first WALL as quads ``(xyz, uv)`` and its
    texture: its ``CENTER`` / ``LEFT`` / ``RIGHT`` panels (texture ``s``
    pixels) side by side, each stacked ``BOTTOM`` -> ``MIDDLE`` -> ``TOP``
    (``t`` pixels), metres by ``SCALE`` over ``TEX_SIZE``, its foot
    ``BASEMENT_DEPTH`` pixels under its zero (X-Plane's library fences,
    KCRW ``fence_MeshHigh_05.fac``)."""
    tex, size, scale, depth = None, (1.0, 1.0), (1.0, 1.0), 0.0
    cols: list[tuple[float, float]] = []
    rows: dict[str, list[tuple[float, float]]] = {"BOTTOM": [], "MIDDLE": [], "TOP": []}
    walls = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            t = raw.split()
            if not t:
                continue
            k = t[0]
            try:
                if k == "TEXTURE" and tex is None and len(t) > 1:
                    tex = raw.split(None, 1)[1].strip()
                elif k == "TEX_SIZE":
                    size = (float(t[1]), float(t[2]))
                elif k == "WALL":
                    walls += 1
                elif walls > 1:
                    continue                    # the first wall stands for the file
                elif k == "SCALE":
                    scale = (float(t[1]), float(t[2]))
                elif k == "BASEMENT_DEPTH":
                    depth = float(t[1])
                elif k in ("LEFT", "CENTER", "RIGHT"):
                    cols.append((float(t[1]), float(t[2])))
                elif k in rows:
                    rows[k].append((float(t[1]), float(t[2])))
            except (ValueError, IndexError):
                continue
    stack = rows["BOTTOM"] + rows["MIDDLE"] + rows["TOP"]
    quads, uvs = [], []
    z = 0.0
    for s0, s1 in cols:
        w = (s1 - s0) / size[0] * scale[0]
        y = -depth / size[1] * scale[1]
        for t0, t1 in stack:
            h = (t1 - t0) / size[1] * scale[1]
            a, b, c, d = (0.0, y, z), (0.0, y + h, z), (0.0, y + h, z - w), (0.0, y, z - w)
            ua, ub = (s0 / size[0], t0 / size[1]), (s0 / size[0], t1 / size[1])
            uc, ud = (s1 / size[0], t1 / size[1]), (s1 / size[0], t0 / size[1])
            quads += [(a, b, c), (a, c, d)]
            uvs += [(ua, ub, uc), (ua, uc, ud)]
            y += h
        z -= w
    return (np.asarray(quads, float).reshape(-1, 3, 3), np.asarray(uvs, float).reshape(-1, 3, 2),
            tex)


def facade_solidity(path: str, index: _t.Mapping[str, str] | None = None
                    ) -> Solidity | None:
    """THE MEASUREMENT of one ``.fac``: its wall meshes with every object
    its segments attach (each at its own ``y``, the first variant of a
    library object) read as one body."""
    from .facade import object_variants
    try:
        xyz, uv, tex, attach = _fac_mesh(path)
        if xyz.shape[0] == 0 and not attach:     # a v800 facade: panels, no mesh
            xyz, uv, tex = _fac_v800(path)
        parts = [(xyz, uv, [_alpha(_texture(path, tex))] * xyz.shape[0])]
        for name, dy in attach:
            got = object_variants(name, os.path.dirname(path), index)
            if got:
                parts.append(_obj_tris(got[0], dy))
        return _measure(np.concatenate([p[0] for p in parts]).reshape(-1, 3, 3),
                        np.concatenate([p[1] for p in parts]).reshape(-1, 3, 2),
                        [q for p in parts for q in p[2]])
    except (OSError, ValueError, IndexError):
        return None


#: the classes :func:`kind_of` reads (owner 2026-11-13 15:36Z): the first
#: three stand ON the upper level (the drop is beyond them); a retaining
#: wall is seated at its low side's ground
WIRE_FENCE, LOW_BARRIER, SOLID_WALL, RETAINING_WALL, ELEVATED = (
    "wire_fence", "low_barrier", "solid_wall", "retaining_wall", "elevated")
ON_TOP = (WIRE_FENCE, LOW_BARRIER, SOLID_WALL)


def kind_of(sol: _t.Any, cfg: _t.Any) -> str:
    """THE CLASS of a measured line object (``sol``: a :class:`Solidity`
    or a record with ``base_y`` / ``solid_top_y``), thresholds from the
    CALLER's ``cfg`` (``classify/rules.toml`` ``[service]`` ``line_*``).

    A RETAINING WALL is authored at least ``line_retaining_buried_min_m`` under
    its zero and solid over that footing — the author drew the face the
    low side shows.  Otherwise it stands on its zero, on the upper level,
    read by the solid band OVER its zero (a fence sunk 0.6 m by design is
    as tall as it shows): a WIRE FENCE (under ``line_wire_max_solid_m``), a LOW
    BARRIER
    (up to ``line_low_barrier_max_solid_m``) or a SOLID WALL.  A body whose
    base stands more than ``line_elevated_base_m`` over its zero is ELEVATED (a
    jetway tunnel run, KSFO ``Tunnel_Steel_Old_5m.fac`` base 5.03 m): it
    stands on no ground and marks no edge."""
    base, solid_top = float(sol.base_y), float(sol.solid_top_y)
    if base > float(cfg.line_elevated_base_m):
        return ELEVATED
    buried = max(0.0, -base)
    if buried >= float(cfg.line_retaining_buried_min_m) and solid_top > 0.0:
        return RETAINING_WALL
    solid = max(0.0, solid_top - max(base, 0.0))     # what stands over its zero
    if solid < float(cfg.line_wire_max_solid_m):
        return WIRE_FENCE
    return LOW_BARRIER if solid <= float(cfg.line_low_barrier_max_solid_m) else SOLID_WALL
