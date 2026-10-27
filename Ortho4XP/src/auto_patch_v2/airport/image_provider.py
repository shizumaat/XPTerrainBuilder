"""THE IMAGE-PROVIDER INTERFACE (#1359; spec
``docs/specs/multi-source-terrain-spec.md`` §7.3; owner RULINGS 2026-10-26q).

What an image method sees, what it answers, and the registry the law's
``terrain_witness.image.provider`` key names.  The classic edge finder
(``image_edges_classic``) is the first member of the family; the learned
model the side branch explores is one more file
(``airport/image_edges_<name>.py``) registered under its own key — it needs
nothing else from the witness.

A provider sees ONLY an :class:`ImagePatch` (pixels of the build's own
texture, resampled north-up into the airport frame) and line or window
probes in that frame.  It never opens a file, never sees another source,
and never knows which airport it is on (RULINGS 2026-10-05e).  The vote
reads only :class:`ImageEvidence`; a strength below the question's floor is
an abstain.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

__all__ = ["ImagePatch", "Probes", "ImageEvidence", "register", "provider", "NONE"]

#: the label of an evidence that found nothing
NONE = "none"


@_dc.dataclass(frozen=True)
class ImagePatch:
    """Pixels of the build's own texture under a window of the airport
    frame, north-up: pixel ``(row, col)``'s centre lies at
    ``(origin_xy[0] + (col + 0.5) * m_per_px, origin_xy[1] - (row + 0.5) * m_per_px)``.
    ``valid`` is False where no texture covers the pixel."""

    rgb: np.ndarray
    m_per_px: float
    origin_xy: tuple[float, float]
    source: str
    valid: np.ndarray

    def luminance(self) -> np.ndarray:
        """Rec. 601 luminance, float32, NaN where not ``valid``."""
        rgb = self.rgb.astype(np.float32)
        lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        return np.where(self.valid, lum, np.nan).astype(np.float32)

    def saturation(self) -> np.ndarray:
        """HSV saturation ``(max - min) / max`` of the RGB, float32 in 0..1,
        NaN where not ``valid`` (0 on black): asphalt and concrete are grey,
        dirt and grass are not."""
        rgb = self.rgb.astype(np.float32)
        hi, lo = rgb.max(axis=-1), rgb.min(axis=-1)
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(hi > 0.0, (hi - lo) / hi, 0.0)
        return np.where(self.valid, s, np.nan).astype(np.float32)

    def rowcol(self, xy: np.ndarray) -> np.ndarray:
        """Fractional ``(row, col)`` of airport-frame points ``xy`` (N×2),
        in the pixel-centre convention of :func:`scipy.ndimage.map_coordinates`."""
        xy = np.asarray(xy, dtype=float)
        col = (xy[..., 0] - self.origin_xy[0]) / self.m_per_px - 0.5
        row = (self.origin_xy[1] - xy[..., 1]) / self.m_per_px - 0.5
        return np.stack([row, col], axis=-1)


@_dc.dataclass(frozen=True)
class Probes:
    """N line probes: station ``xy[i]``, unit ``normal[i]``, the signed
    ``offsets_m`` sampled along the normal, and ``half_width_m`` of
    along-track (perpendicular to the normal) support each sample is the
    median over — the width of the strip a profile summarises."""

    xy: np.ndarray
    normal: np.ndarray
    offsets_m: np.ndarray
    half_width_m: float = 0.0


@_dc.dataclass(frozen=True)
class ImageEvidence:
    """One answer: where along the probe's normal (``offset_m``; ``None`` =
    nothing found), how strongly (calibrated 0..1), and what it is
    (``pavement_edge`` | ``graded_edge`` | ``threshold_marking`` |
    ``paved_contact`` |
    ``portal_opening`` | ``shadow_line`` | ``none``)."""

    offset_m: float | None
    strength: float
    label: str


class ImageProvider(_t.Protocol):
    """An image method: a registry ``name`` and a ``version`` that joins the
    patch freshness inputs (spec §6.5)."""

    name: str
    version: str

    def edges(self, patch: ImagePatch, probes: Probes, kind: str) -> list[ImageEvidence]:
        """One evidence per probe station: the ``kind`` edge along its normal."""
        ...

    def presence(self, patch: ImagePatch, window_xy: np.ndarray, kind: str) -> ImageEvidence:
        """Whether a ``kind`` feature fills the polygon ``window_xy`` (K×2)."""
        ...


_REGISTRY: dict[str, ImageProvider] = {}


def register(p: ImageProvider) -> ImageProvider:
    """Add provider ``p`` under ``p.name`` (a module registers itself on import)."""
    _REGISTRY[p.name] = p
    return p


def provider(name: str) -> ImageProvider:
    """The registered provider ``name`` (the law's ``image.provider``)."""
    if name not in _REGISTRY:
        # the classic family member registers on import: import it here so a
        # caller never depends on import order
        from . import image_edges_classic  # noqa: F401
    if name not in _REGISTRY:
        raise KeyError(f"no image provider {name!r} (registered: {sorted(_REGISTRY)})")
    return _REGISTRY[name]
