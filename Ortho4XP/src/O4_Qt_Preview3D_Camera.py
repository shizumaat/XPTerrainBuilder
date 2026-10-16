"""The 3D preview's free-look camera, pure maths (spec patch-editor-20261015
§5; owner #794: "I want the scene to be fixed, and the viewpoint moves and
'looks' around").  The Mac's ``FreeLookCamera`` is the same rules.

The camera is an EYE in the scene's frame (x east, y up, z south) with a
compass heading (degrees, 0 = looking north, positive = turned right), a
pitch above the horizon (negative looks down) and a vertical field of
view.  The scene never moves.  Input moves the GOAL; :meth:`FreeLook.step`
eases the SHOWN camera toward it, so neither a jerky mouse nor a held key
makes the view jump, and keeps the eye above the terrain.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

__all__ = ["KEYS", "SPEED", "Pose", "FreeLook"]

#: X-Plane's view commands as its default ``X-Plane Keys.prf`` binds them,
#: applied to the eye (the Mac's ``FreeLookCamera.Key``): ← → sideways and
#: ↑ ↓ forward / back in the horizontal plane, ``.`` ``,`` forward / back
#: along the view, ``=`` ``-`` zoom the field of view, Q E turn, R F tilt.
KEYS = ("left", "right", "forward", "backward", "view_forward", "view_backward",
        "zoom_in", "zoom_out", "turn_left", "turn_right", "tilt_up", "tilt_down")
#: Plain is X-Plane's rate, Shift fast, Control slower (its _fast / _slow).
SPEED = {"slow": 0.25, "normal": 1.0, "fast": 4.0}

Vec = tuple[float, float, float]
Ground = _t.Callable[[float, float], "float | None"]


@_dc.dataclass(frozen=True)
class Pose:
    eye: Vec
    heading: float          # degrees, clockwise from north
    pitch: float            # degrees above the horizon
    fov: float              # vertical, degrees


def _add(a: Vec, b: Vec, k: float = 1.0) -> Vec:
    return (a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k)


class FreeLook:
    """Eye, heading, pitch and field of view, eased goal → shown."""

    MAX_PITCH: _t.ClassVar[float] = 89.0
    MIN_FOV: _t.ClassVar[float] = 5.0
    MAX_FOV: _t.ClassVar[float] = 90.0
    DEFAULT_FOV: _t.ClassVar[float] = 45.0
    MIN_CLEARANCE: _t.ClassVar[float] = 2.0          # metres above the ground under the eye
    MIN_MOVE_SCALE: _t.ClassVar[float] = 30.0        # moves scale with the eye's height
    DRAG_DEG_PER_PX: _t.ClassVar[float] = 0.17       # ≈ 0.003 rad, the Mac's
    MOVE_PER_NOTCH: _t.ClassVar[float] = 0.04        # of the height, per wheel notch
    MOVE_PER_PX: _t.ClassVar[float] = 1.2            # × height / view height, a move drag
    KEY_TURN_DEG: _t.ClassVar[float] = 20.0          # per second, normal speed
    KEY_TILT_DEG: _t.ClassVar[float] = 15.0
    KEY_MOVE_FRACTION: _t.ClassVar[float] = 0.4      # of the height per second
    KEY_ZOOM_PER_S: _t.ClassVar[float] = 1.6
    EASING: _t.ClassVar[float] = 0.25                # of the way per 1/60 s

    def __init__(self, ground: Ground | None = None):
        self.ground = ground
        self.home = Pose((0.0, 1200.0, 1800.0), 0.0, -34.4, self.DEFAULT_FOV)
        self.goal = self.shown = self.home

    # ─── the first view ────────────────────────────────────────────────
    def frame(self, centre: _t.Sequence[float], radius: float) -> None:
        """Above and south of the extent, outside its box, looking north
        and down at its centre — at once ("Reset view")."""
        d, e = max(radius * 2.2, 50.0), 0.6
        cx, cy, cz = (float(v) for v in centre)
        eye = self._above((cx, cy + math.sin(e) * d, cz + math.cos(e) * d))
        self.home = Pose(eye, 0.0, -math.degrees(e), self.DEFAULT_FOV)
        self.go_home()

    def go_home(self) -> None:
        """Back to the view :meth:`frame` set (the reset key), at once."""
        self.goal = self.shown = self.home

    # ─── what the scene shows ──────────────────────────────────────────
    def position(self) -> Vec:
        return self.shown.eye

    def rotation(self) -> Vec:
        """Euler degrees for a camera looking down −z (y turns it left)."""
        return (self.shown.pitch, -self.shown.heading, 0.0)

    def look_direction(self) -> Vec:
        return self._view(self.shown)

    # ─── input (moves the goal) ────────────────────────────────────────
    def look(self, dx_px: float, dy_px: float) -> None:
        """A drag turns the view about the eye — right turns right, up looks
        up; the eye does not move."""
        g = self.goal
        self.goal = _dc.replace(g, heading=g.heading + dx_px * self.DRAG_DEG_PER_PX,
                                pitch=self._clamp_pitch(g.pitch - dy_px * self.DRAG_DEG_PER_PX))

    def move(self, dx_px: float, dy_px: float, view_height_px: float) -> None:
        """Alt-drag / right-drag: the eye goes the way the pointer goes —
        right moves right, up moves forward — in the horizontal plane."""
        k = self._scale() * self.MOVE_PER_PX / max(view_height_px, 1.0)
        right, ahead = self._right(self.goal), self._ahead(self.goal)
        self._translate(_add(_add((0.0, 0.0, 0.0), right, dx_px * k), ahead, -dy_px * k))

    def scroll(self, notches: float) -> None:
        """The wheel moves the eye along the view (positive = forward)."""
        self._translate(self._view(self.goal), notches * self.MOVE_PER_NOTCH * self._scale())

    def hold(self, keys: _t.Collection[str], speed: str, dt: float) -> None:
        """Advance the goal by ``dt`` seconds of the held X-Plane keys."""
        if not keys or dt <= 0:
            return
        m = SPEED[speed] * dt

        def axis(plus: str, minus: str) -> float:
            return float(plus in keys) - float(minus in keys)

        g = self.goal
        g = _dc.replace(g, heading=g.heading + axis("turn_right", "turn_left") * self.KEY_TURN_DEG * m,
                        pitch=self._clamp_pitch(g.pitch + axis("tilt_up", "tilt_down")
                                                * self.KEY_TILT_DEG * m))
        z = axis("zoom_in", "zoom_out")
        if z:
            g = _dc.replace(g, fov=min(self.MAX_FOV, max(self.MIN_FOV,
                                                         g.fov * self.KEY_ZOOM_PER_S ** (-z * m))))
        self.goal = g
        step = self._scale() * self.KEY_MOVE_FRACTION * m
        d = _add(_add(_add((0.0, 0.0, 0.0), self._right(g), axis("right", "left")),
                      self._ahead(g), axis("forward", "backward")),
                 self._view(g), axis("view_forward", "view_backward"))
        self._translate(d, step)

    # ─── easing ────────────────────────────────────────────────────────
    def step(self, dt: float) -> bool:
        """Ease the shown camera toward the goal, above the ground; whether
        it still moves."""
        a = 1.0 - (1.0 - self.EASING) ** (max(dt, 0.0) * 60.0)
        g = self.goal = _dc.replace(self.goal, eye=self._above(self.goal.eye))
        s = self.shown
        eye = self._above(tuple(se + (ge - se) * a for se, ge in zip(s.eye, g.eye)))
        s = self.shown = Pose(eye, s.heading + (g.heading - s.heading) * a,
                              s.pitch + (g.pitch - s.pitch) * a, s.fov + (g.fov - s.fov) * a)
        settled = (math.dist(s.eye, g.eye) < max(0.001 * self._scale(), 0.01)
                   and abs(g.heading - s.heading) < 0.005 and abs(g.pitch - s.pitch) < 0.005
                   and abs(g.fov - s.fov) < 0.001)
        if settled:
            self.shown = g
        return not settled

    def needs_lift(self) -> bool:
        """The ground rose through the shown eye (the exaggeration grew)."""
        g = self.ground_y(self.shown.eye)
        return g is not None and self.shown.eye[1] < g + self.MIN_CLEARANCE

    # ─── internals ─────────────────────────────────────────────────────
    def ground_y(self, p: Vec) -> float | None:
        return None if self.ground is None else self.ground(p[0], p[2])

    def _above(self, p: _t.Sequence[float]) -> Vec:
        x, y, z = (float(v) for v in p)
        g = self.ground_y((x, y, z))
        return (x, y if g is None else max(y, g + self.MIN_CLEARANCE), z)

    def _translate(self, d: Vec, k: float = 1.0) -> None:
        self.goal = _dc.replace(self.goal, eye=self._above(_add(self.goal.eye, d, k)))

    def _scale(self) -> float:
        """Metres one unit of motion is worth: the goal eye's height above
        the ground — slow near the ground, fast high up."""
        g = self.ground_y(self.goal.eye)
        return max(self.goal.eye[1] - (0.0 if g is None else g), self.MIN_MOVE_SCALE)

    def _clamp_pitch(self, p: float) -> float:
        return min(self.MAX_PITCH, max(-self.MAX_PITCH, p))

    @staticmethod
    def _right(p: Pose) -> Vec:
        h = math.radians(p.heading)
        return (math.cos(h), 0.0, math.sin(h))

    @staticmethod
    def _ahead(p: Pose) -> Vec:
        h = math.radians(p.heading)
        return (math.sin(h), 0.0, -math.cos(h))

    @staticmethod
    def _view(p: Pose) -> Vec:
        h, e = math.radians(p.heading), math.radians(p.pitch)
        return (math.sin(h) * math.cos(e), math.sin(e), -math.cos(h) * math.cos(e))
