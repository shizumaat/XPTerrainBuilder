#!/usr/bin/env python3
"""Texture seam census: per-texture colour shift vs source, step across every seam.

THE instrument for GitHub issue #1 (GEN-2, colour harmonizer seam lines) and
for ``docs/specs/color-harmonization-spec.md`` §4 acceptance.  Given a built
tile directory it answers two questions with one code path:

  1. Per texture: by how much did the build move the colours relative to
     the cached source JPEG?  (``shift`` = per-channel median of
     ``built - source`` over LAND pixels; ``shift_all`` over every pixel.)
  2. Per seam (every pair of edge-adjacent textures of one zoom level and
     provider, east and south): what is the colour step across the seam in
     the built DDS, what was it in the source, and what did the build
     INTRODUCE (``introduced = step_dds - step_src``)?  Only rows where
     both sides are land count, so a sea/land seam is judged on its land.

Water comes from the tile's own sea masks, ``textures/<y>_<x>_ZL<zl>.png``
(``O4_File_Names.mask_file``; 255 = land, 0 = water), the same file the
convert step and X-Plane read, so "land" here is the builder's land.

Usage (from ``Ortho4XP/``)::

    venv/bin/python tools/texture_seam_census.py TILE_DIR [--orthophotos ROOT]
        [--strip 16] [--top 12] [--json OUT] [--bar 2.0] [--fail-over-bar]
        [--only y_x_Prov16 ...]

``TILE_DIR`` is a build dir holding ``textures/`` (``.../zOrtho4XP_+25+051``).
Source JPEGs are looked up under ``ROOT`` (default: the ``Orthophotos`` root
the engine resolves, else the shared data repo) in the engine's ``grouped``
/ ``normal`` / ``code`` layouts.  Read-only on every input.

Exit code: 0; with ``--fail-over-bar``, 1 when any land seam's introduced
step exceeds ``--bar`` counts (the closing-test form).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

TEXTURE_RE = re.compile(r"^(\d+)_(\d+)_([A-Za-z][A-Za-z0-9]*?)(\d{2})\.dds$")
GRID_STEP = 16  # orthogrid tiles per texture edge, every zoom level
THUMB = 512  # statistics thumbnail edge (same as O4_Color_Harmonization)
LAND_THRESHOLD = 128  # mask value >= this is land


def _default_orthophoto_root() -> Path | None:
    here = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(here / "src"))
    try:
        import O4_File_Names as FNAMES  # noqa: WPS433

        root = Path(FNAMES.Imagery_dir)
        if root.is_dir():
            return root
    except Exception:  # pragma: no cover - engine config absent
        pass
    shared = Path("/Users/noah/XPTerrainBuilderData/Orthophotos")
    return shared if shared.is_dir() else None


def _tile_names(tile_dir: Path) -> tuple[str, str] | None:
    m = re.search(r"([+-]\d{2})([+-]\d{3})$", tile_dir.name)
    if not m:
        return None
    lat, lon = int(m.group(1)), int(m.group(2))
    short = "%+03d%+04d" % (lat, lon)
    block = "%+03d%+04d" % (lat // 10 * 10, lon // 10 * 10)
    return short, block


def find_source_jpeg(root: Path | None, tile_dir: Path, name: str,
                     provider: str, zl: int) -> Path | None:
    """Locate the cached source JPEG for a DDS name in the engine layouts."""
    if root is None:
        return None
    jpeg = name[: -len(".dds")] + ".jpg"
    sub = f"{provider}_{zl}"
    candidates = []
    names = _tile_names(tile_dir)
    if names:
        short, block = names
        candidates.append(root / block / short / sub / jpeg)  # grouped
        candidates.append(root / short / sub / jpeg)  # normal
    candidates.append(root / provider / sub / jpeg)  # code
    for c in candidates:
        if c.is_file():
            return c
    return None


def _load_rgb(path: Path) -> numpy.ndarray:
    with Image.open(path) as im:
        return numpy.asarray(im.convert("RGB"), dtype=numpy.uint8)


MASKS_ROOT: Path | None = None  # set from --masks / engine config in main()
MASK_ZLS = (14, 15, 16)  # mask_zl candidates (O4_Cfg_Vars ``mask_zl`` values)
ALL_WATER_MAX = 30  # O4_Mask_Utils.needs_mask: crop max <= 30 is all water


def _default_masks_dir(tile_dir: Path) -> Path | None:
    names = _tile_names(tile_dir)
    if names is None:
        return None
    short, block = names
    here = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(here / "src"))
    try:
        import O4_File_Names as FNAMES  # noqa: WPS433

        lat, lon = int(short[:3]), int(short[3:])
        d = Path(FNAMES.mask_dir(lat, lon))
        if d.is_dir():
            return d
    except Exception:  # pragma: no cover - engine config absent
        pass
    for cand in (Path("/Users/noah/XPTerrainBuilderData/Masks") / block / short,
                 Path("/Users/noah/XPTerrainBuilderData/Masks") / short):
        if cand.is_dir():
            return cand
    return None


def _load_land(tile_dir: Path, y: int, x: int, zl: int, size: int
               ) -> tuple[numpy.ndarray | None, str]:
    """Land mask at ``size`` x ``size`` (True = land) and its provenance.

    Mirrors what the builder itself knows (``O4_Mask_Utils.needs_mask``):
      1. ``textures/<y>_<x>_ZL<zl>.png`` written by the DSF step - the mask
         X-Plane draws with;
      2. else the shared ``Masks/<tile>/<y>_<x>.png`` square at the
         texture's own ZL or a coarser ``mask_zl`` (cropped): crop max
         <= 30 is ALL WATER (no PNG is written for such a texture);
      3. else no mask square exists for the area: all land.
    ``None`` means all land.
    """
    mask_path = tile_dir / "textures" / f"{y}_{x}_ZL{zl}.png"
    if mask_path.is_file():
        with Image.open(mask_path) as im:
            m = im.convert("L").resize((size, size), Image.BOX)
        return numpy.asarray(m) >= LAND_THRESHOLD, "tile-mask"
    masks_dir = MASKS_ROOT if MASKS_ROOT is not None else _default_masks_dir(tile_dir)
    if masks_dir is None:
        return None, "no-masks-dir"
    for mask_zl in sorted({zl, *MASK_ZLS}, reverse=True):
        if mask_zl > zl:
            continue
        factor = 2 ** (zl - mask_zl)
        m_x = (int(x / factor) // GRID_STEP) * GRID_STEP
        m_y = (int(y / factor) // GRID_STEP) * GRID_STEP
        square = masks_dir / f"{m_y}_{m_x}.png"
        if not square.is_file():
            continue
        with Image.open(square) as im:
            w = im.size[0]
            rx = int((x - factor * m_x) / GRID_STEP)
            ry = int((y - factor * m_y) / GRID_STEP)
            x0, y0 = int(rx * w / factor), int(ry * w / factor)
            crop = im.convert("L").crop((x0, y0, x0 + w // factor, y0 + w // factor))
            arr = numpy.asarray(crop)
            if arr.max() <= ALL_WATER_MAX:
                return numpy.zeros((size, size), bool), "all-water"
            m = crop.resize((size, size), Image.BOX)
        return numpy.asarray(m) >= LAND_THRESHOLD, f"shared-mask-zl{mask_zl}"
    return None, "no-mask-square"


def _thumb(arr: numpy.ndarray) -> numpy.ndarray:
    im = Image.fromarray(arr).resize((THUMB, THUMB), Image.BOX)
    return numpy.asarray(im, dtype=numpy.float64)


def _median_or_none(values: numpy.ndarray) -> list[float] | None:
    if values.shape[0] == 0:
        return None
    return [round(float(v), 2) for v in numpy.median(values, axis=0)]


class Texture:
    """Everything the census keeps per texture: strips + thumbnail stats."""

    def __init__(self, key, name, dds: numpy.ndarray, src: numpy.ndarray | None,
                 land_full: numpy.ndarray | None, strip: int):
        self.key = key  # (zl, provider, y, x)
        self.name = name
        self.size = dds.shape[0]
        s = strip
        self.strips_dds = self._strips(dds, s)
        self.strips_src = self._strips(src, s) if src is not None else None
        n = dds.shape[0]
        land = land_full if land_full is not None else numpy.ones((n, n), bool)
        self.land_strips = {
            "L": land[:, :s].all(axis=1), "R": land[:, -s:].all(axis=1),
            "T": land[:s, :].all(axis=0), "B": land[-s:, :].all(axis=0),
        }
        self.land_fraction = float(land.mean())
        td = _thumb(dds)
        lt = (numpy.asarray(Image.fromarray(land.astype(numpy.uint8) * 255)
                            .resize((THUMB, THUMB), Image.BOX)) >= LAND_THRESHOLD)
        self.median_dds_all = _median_or_none(td.reshape(-1, 3))
        self.median_dds_land = _median_or_none(td[lt])
        self.median_dds_sea = _median_or_none(td[~lt])
        self.shift = self.shift_all = None
        self.median_src_all = self.median_src_land = self.median_src_sea = None
        if src is not None:
            ts = _thumb(src)
            self.median_src_all = _median_or_none(ts.reshape(-1, 3))
            self.median_src_land = _median_or_none(ts[lt])
            self.median_src_sea = _median_or_none(ts[~lt])
            diff = td - ts
            self.shift_all = _median_or_none(diff.reshape(-1, 3))
            self.shift = _median_or_none(diff[lt]) or self.shift_all

    @staticmethod
    def _strips(arr, s):
        a = arr.astype(numpy.float64)
        return {  # per-row (or per-column) mean across the strip width
            "L": a[:, :s].mean(axis=1), "R": a[:, -s:].mean(axis=1),
            "T": a[:s, :].mean(axis=0), "B": a[-s:, :].mean(axis=0),
        }

    def as_row(self) -> dict:
        return {
            "texture": self.name, "zl": self.key[0], "provider": self.key[1],
            "y": self.key[2], "x": self.key[3],
            "land_fraction": round(self.land_fraction, 3),
            "land_source": getattr(self, "land_source", "?"),
            "shift": self.shift, "shift_all": self.shift_all,
            "median_src_all": self.median_src_all,
            "median_src_land": self.median_src_land,
            "median_src_sea": self.median_src_sea,
            "median_dds_all": self.median_dds_all,
            "median_dds_land": self.median_dds_land,
            "source_found": self.strips_src is not None,
        }


def _seam(a: Texture, b: Texture, side_a: str, side_b: str) -> dict | None:
    """Step across one seam: mean over land rows of (b's facing strip - a's)."""
    land = a.land_strips[side_a] & b.land_strips[side_b]
    n = int(land.sum())
    row = {"a": a.name, "b": b.name, "direction": "E" if side_a == "R" else "S",
           "land_rows": n, "rows": int(land.size)}
    if n == 0:
        row.update(step_dds=None, step_src=None, introduced=None, max_abs=None)
        return row
    step_dds = (b.strips_dds[side_b][land] - a.strips_dds[side_a][land]).mean(axis=0)
    row["step_dds"] = [round(float(v), 2) for v in step_dds]
    if a.strips_src is None or b.strips_src is None:
        row.update(step_src=None, introduced=None, max_abs=None)
        return row
    step_src = (b.strips_src[side_b][land] - a.strips_src[side_a][land]).mean(axis=0)
    intro = step_dds - step_src
    row["step_src"] = [round(float(v), 2) for v in step_src]
    row["introduced"] = [round(float(v), 2) for v in intro]
    row["max_abs"] = round(float(numpy.abs(intro).max()), 2)
    return row


def simulate_harmonizer(tile_dir: Path, orthophotos: Path | None,
                        providers: list[str], zls: list[int],
                        only: set[str] | None = None) -> dict:
    """Replay the SHIPPED harmonizer offline from the source JPEGs.

    Same statistic (``compute_texture_color_statistics`` on the JPEG opened
    with ``Image.draft("RGB", (512, 512))``, exactly as
    ``O4_Imagery_Utils.collect_color_statistics_for_harmonization``), same
    target field per (zoomlevel, provider) group, same strength-scheduled,
    capped shift.  Because the shipped shift is one constant per texture,
    the step it introduces across a seam is exactly
    ``round(shift_b) - round(shift_a)`` wherever neither side clips at
    0/255 - reported here as ``predicted``.  No texture is written.
    """
    here = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(here / "src"))
    import O4_Color_Harmonization as H  # noqa: WPS433

    textures_dir = tile_dir / "textures"
    dds_names = sorted(os.listdir(textures_dir)) if textures_dir.is_dir() else []
    stats, land_frac, medians, land_src = {}, {}, {}, {}
    for provider in providers:
        for zl in zls:
            sub = None
            if orthophotos is not None:
                names = _tile_names(tile_dir)
                for cand in ([orthophotos / names[1] / names[0] / f"{provider}_{zl}",
                              orthophotos / names[0] / f"{provider}_{zl}"] if names else []
                             ) + [orthophotos / provider / f"{provider}_{zl}"]:
                    if cand.is_dir():
                        sub = cand
                        break
            if sub is None:
                continue
            for jpeg in sorted(os.listdir(sub)):
                m = re.match(rf"^(\d+)_(\d+)_{provider}{zl}\.jpg$", jpeg)
                if not m or (only and jpeg[:-4] not in only):
                    continue
                y, x = int(m[1]), int(m[2])
                with Image.open(sub / jpeg) as im:
                    im.draft("RGB", (512, 512))
                    st = H.compute_texture_color_statistics(im)
                    thumb = numpy.asarray(im.convert("RGB").resize((THUMB, THUMB), Image.BOX),
                                          dtype=numpy.float64)
                land, land_source = _load_land(tile_dir, y, x, zl, THUMB)
                lt = land if land is not None else numpy.ones((THUMB, THUMB), bool)
                land_frac[(zl, provider, y, x)] = float(lt.mean())
                land_src[(zl, provider, y, x)] = land_source
                medians[(zl, provider, y, x)] = {
                    "all": _median_or_none(thumb.reshape(-1, 3)),
                    "land": _median_or_none(thumb[lt]), "sea": _median_or_none(thumb[~lt])}
                if st is not None:
                    stats[(zl, provider, y, x)] = numpy.array(st["channel_medians"])
    groups: dict[tuple, dict] = {}
    for (zl, prov, y, x), med in stats.items():
        groups.setdefault((zl, prov), {})[(x, y)] = med
    shifts, targets = {}, {}
    for (zl, prov), group in groups.items():
        field = H.compute_target_field(group)
        for (x, y), target in field.items():
            key = (zl, prov, y, x)
            targets[key] = target
            shifts[key] = H.compute_harmonization_shift(stats[key], target, zl)
    rows, seams = [], []
    for key in sorted(medians):
        zl, prov, y, x = key
        sh = shifts.get(key)
        rows.append({
            "texture": f"{y}_{x}_{prov}{zl}", "zl": zl, "provider": prov, "y": y, "x": x,
            "land_fraction": round(land_frac[key], 3), "land_source": land_src[key],
            "excluded": key not in stats,
            "median_all": medians[key]["all"], "median_land": medians[key]["land"],
            "median_sea": medians[key]["sea"],
            "target": None if key not in targets else [round(float(v), 2) for v in targets[key]],
            "shift": None if sh is None else [int(round(float(v))) for v in sh],
            "shift_raw": None if sh is None else [round(float(v), 2) for v in sh],
        })
    def _sh(k):
        v = shifts.get(k)
        return numpy.zeros(3) if v is None else numpy.round(v)
    for key in sorted(medians):
        zl, prov, y, x = key
        for nb, d in (((zl, prov, y, x + GRID_STEP), "E"), ((zl, prov, y + GRID_STEP, x), "S")):
            if nb not in medians:
                continue
            la, lb = land_frac[key], land_frac[nb]
            if la == 0.0 or lb == 0.0:
                continue  # an all-water side: no land seam to see
            pred = _sh(nb) - _sh(key)
            seams.append({"a": f"{y}_{x}_{prov}{zl}", "b": f"{nb[2]}_{nb[3]}_{prov}{zl}",
                          "direction": d, "predicted": [int(v) for v in pred],
                          "max_abs": float(numpy.abs(pred).max()),
                          "land_a": round(la, 2), "land_b": round(lb, 2)})
    return {"tile_dir": str(tile_dir), "orthophotos": str(orthophotos),
            "mode": "simulate-harmonizer", "textures": rows, "seams": seams}


def print_simulation(sim: dict, bar: float, top: int) -> dict:
    shifted = [t for t in sim["textures"] if t["shift"] is not None]
    seams = sorted(sim["seams"], key=lambda s: -s["max_abs"])
    over = [s for s in seams if s["max_abs"] > bar]
    capped = [t for t in shifted if max(abs(v) for v in t["shift"]) >= 20]
    summary = {
        "textures": len(sim["textures"]), "land_sources": dict(sorted(
            __import__("collections").Counter(
                t["land_source"] for t in sim["textures"]).items())),
        "all_water_textures_with_shift": sum(
            1 for t in shifted if t["land_fraction"] == 0.0 and any(t["shift"])),
        "excluded_lt20pct_valid": sum(
            1 for t in sim["textures"] if t["excluded"]),
        "textures_shifted": sum(1 for t in shifted if any(t["shift"])),
        "textures_at_cap_20": len(capped), "seams": len(seams), "bar_counts": bar,
        "seams_over_bar": len(over),
        "max_predicted_step": max((s["max_abs"] for s in seams), default=0.0),
        "median_predicted_step": round(float(numpy.median(
            [s["max_abs"] for s in seams])), 2) if seams else 0.0,
    }
    print("SIMULATED shipped harmonizer (O4_Color_Harmonization, from source JPEGs):",
          sim["tile_dir"])
    for k, v in summary.items():
        print("  %-24s %s" % (k, v))
    print(f"\nper-texture predicted shift, top {top} by |shift|:")
    print("  %-22s %-5s %-16s %-20s %-20s %-20s %-20s" % (
        "texture", "land", "shift", "target", "median_all", "median_land", "median_sea"))
    for t in sorted(shifted, key=lambda t: -max(abs(v) for v in t["shift"]))[:top]:
        print("  %-22s %-5.2f %-16s %-20s %-20s %-20s %-20s" % (
            t["texture"], t["land_fraction"], _fmt(t["shift"]), _fmt(t["target"]),
            _fmt(t["median_all"]), _fmt(t["median_land"]), _fmt(t["median_sea"])))
    print(f"\nseams by predicted introduced step, top {top}:")
    for s in seams[:top]:
        print("  %-5.0f %-22s %-22s %s  land %.2f/%.2f  %s" % (
            s["max_abs"], s["a"], s["b"], s["direction"], s["land_a"], s["land_b"],
            _fmt(s["predicted"])))
    return summary


def census(tile_dir: Path, orthophotos: Path | None, strip: int,
           only: set[str] | None = None) -> dict:
    textures_dir = tile_dir / "textures"
    if not textures_dir.is_dir():
        raise SystemExit(f"no textures/ under {tile_dir}")
    loaded: dict[tuple, Texture] = {}
    missing_source = []
    for name in sorted(os.listdir(textures_dir)):
        m = TEXTURE_RE.match(name)
        if not m or (only and name[:-4] not in only):
            continue
        y, x, provider, zl = int(m[1]), int(m[2]), m[3], int(m[4])
        dds = _load_rgb(textures_dir / name)
        src_path = find_source_jpeg(orthophotos, tile_dir, name, provider, zl)
        src = _load_rgb(src_path) if src_path else None
        if src is not None and src.shape != dds.shape:
            src = numpy.asarray(Image.fromarray(src).resize(dds.shape[1::-1], Image.BOX))
        if src is None:
            missing_source.append(name)
        land, land_source = _load_land(tile_dir, y, x, zl, dds.shape[0])
        tex = Texture((zl, provider, y, x), name, dds, src, land, strip)
        tex.land_source = land_source
        loaded[(zl, provider, y, x)] = tex
    seams = []
    for (zl, prov, y, x), tex in loaded.items():
        east = loaded.get((zl, prov, y, x + GRID_STEP))
        if east is not None:
            seams.append(_seam(tex, east, "R", "L"))
        south = loaded.get((zl, prov, y + GRID_STEP, x))
        if south is not None:
            seams.append(_seam(tex, south, "B", "T"))
    return {
        "tile_dir": str(tile_dir), "orthophotos": str(orthophotos),
        "strip_px": strip, "textures": [t.as_row() for t in loaded.values()],
        "seams": seams, "missing_source": missing_source,
    }


def summarize(report: dict, bar: float) -> dict:
    judged = [s for s in report["seams"] if s.get("max_abs") is not None]
    over = [s for s in judged if s["max_abs"] > bar]
    shifts = [t for t in report["textures"] if t["shift"] is not None]
    max_shift = max((max(abs(v) for v in t["shift"]) for t in shifts), default=0.0)
    return {
        "textures": len(report["textures"]), "textures_with_source": len(shifts),
        "seams": len(report["seams"]), "seams_all_water": sum(
            1 for s in report["seams"] if s["land_rows"] == 0),
        "seams_judged": len(judged), "bar_counts": bar,
        "seams_over_bar": len(over),
        "max_introduced_step": max((s["max_abs"] for s in judged), default=0.0),
        "median_introduced_step": round(float(numpy.median(
            [s["max_abs"] for s in judged])), 2) if judged else 0.0,
        "max_texture_shift": round(max_shift, 2),
        "land_sources": dict(sorted(
            __import__("collections").Counter(
                t.get("land_source", "?") for t in report["textures"]).items())),
    }


def _fmt(v):
    return "-" if v is None else "(" + ",".join("%+.1f" % c for c in v) + ")"


def print_report(report: dict, summary: dict, top: int) -> None:
    print("texture seam census:", report["tile_dir"])
    print("  sources:", report["orthophotos"], "| strip", report["strip_px"], "px")
    for k, v in summary.items():
        print("  %-24s %s" % (k, v))
    shifts = sorted((t for t in report["textures"] if t["shift"] is not None),
                    key=lambda t: -max(abs(v) for v in t["shift"]))
    print(f"\nper-texture shift (built - source, land median), top {top}:")
    print("  %-24s %-5s %-20s %-20s %-20s %-20s" % (
        "texture", "land", "shift", "src_median_land", "src_median_sea", "src_median_all"))
    for t in shifts[:top]:
        print("  %-24s %-5.2f %-20s %-20s %-20s %-20s" % (
            t["texture"], t["land_fraction"], _fmt(t["shift"]),
            _fmt(t["median_src_land"]), _fmt(t["median_src_sea"]),
            _fmt(t["median_src_all"])))
    seams = sorted((s for s in report["seams"] if s.get("max_abs") is not None),
                   key=lambda s: -s["max_abs"])
    print(f"\nseams by introduced step (dds step - source step), top {top}:")
    print("  %-6s %-24s %-24s %-2s %-9s %-20s %-20s %-20s" % (
        "maxabs", "a", "b", "d", "landrows", "introduced", "step_dds", "step_src"))
    for s in seams[:top]:
        print("  %-6.1f %-24s %-24s %-2s %4d/%-4d %-20s %-20s %-20s" % (
            s["max_abs"], s["a"], s["b"], s["direction"], s["land_rows"], s["rows"],
            _fmt(s["introduced"]), _fmt(s["step_dds"]), _fmt(s["step_src"])))
    if report["missing_source"]:
        print("\ntextures without a source JPEG (%d):" % len(report["missing_source"]),
              " ".join(report["missing_source"][:8]),
              "..." if len(report["missing_source"]) > 8 else "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tile_dir", type=Path)
    ap.add_argument("--orthophotos", type=Path, default=None)
    ap.add_argument("--masks", type=Path, default=None,
                    help="shared Masks/<tile> dir (default: the engine's mask_dir)")
    ap.add_argument("--strip", type=int, default=16)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--bar", type=float, default=2.0)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--fail-over-bar", action="store_true")
    ap.add_argument("--only", nargs="*", default=None,
                    help="texture stems (y_x_Prov16) to restrict the census to")
    ap.add_argument("--simulate-harmonizer", action="store_true",
                    help="replay the shipped harmonizer from the source JPEGs "
                         "(no build, nothing written) and predict every seam step")
    ap.add_argument("--providers", nargs="*", default=["Arc", "BI"])
    ap.add_argument("--zl", nargs="*", type=int, default=[16, 17, 18, 19])
    args = ap.parse_args(argv)
    root = args.orthophotos or _default_orthophoto_root()
    global MASKS_ROOT
    MASKS_ROOT = args.masks
    if args.simulate_harmonizer:
        sim = simulate_harmonizer(args.tile_dir.resolve(), root, args.providers,
                                  args.zl, set(args.only) if args.only else None)
        sim["summary"] = print_simulation(sim, args.bar, args.top)
        if args.json:
            args.json.write_text(json.dumps(sim, indent=1))
            print("\njson:", args.json)
        return 1 if args.fail_over_bar and sim["summary"]["seams_over_bar"] else 0
    report = census(args.tile_dir.resolve(), root, args.strip,
                    set(args.only) if args.only else None)
    summary = summarize(report, args.bar)
    report["summary"] = summary
    print_report(report, summary, args.top)
    if args.json:
        args.json.write_text(json.dumps(report, indent=1))
        print("\njson:", args.json)
    if args.fail_over_bar and summary["seams_over_bar"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
