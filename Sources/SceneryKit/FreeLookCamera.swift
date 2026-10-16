import Foundation
import simd

/// The 3D preview's camera as plain state, so the Mac and its tests share
/// one set of rules (spec §5; owner #794: "I want the scene to be fixed,
/// and the viewpoint moves and 'looks' around"). The camera is an EYE in
/// the scene's frame (x east, y up, z south) with a compass `heading`
/// (radians, 0 = looking north, positive = turned right / east), a `pitch`
/// (radians above the horizon, negative looks down) and a field of view.
/// The scene never moves. Input moves the GOAL; `step` eases the shown
/// camera toward it, so neither a jerky mouse nor a held key makes the
/// view jump. The Qt preview's `FreeLook` (O4_Qt_Preview3D_Camera.py) is
/// the same rules.
///
/// Keys are X-Plane's view commands as its default `X-Plane Keys.prf`
/// binds them, applied to the eye: Q E turn the heading, R F tilt the
/// pitch, ← → ↑ ↓ move sideways / forward / back in the horizontal plane,
/// `.` `,` move forward / back along the view, `=` `-` zoom the field of
/// view. Plain is X-Plane's rate, Shift is fast, Control slower — its
/// `_fast` / `_slow` variants. Scroll and pinch move along the view.
public struct FreeLookCamera {
    public struct Pose: Equatable, Sendable {
        public var eye: SIMD3<Float>
        public var heading: Float
        public var pitch: Float
        /// Vertical field of view, degrees.
        public var fov: Float
    }

    /// One held X-Plane view command.
    public enum Key: Hashable, Sendable {
        case left, right, forward, backward          // ← → ↑ ↓: the horizontal plane
        case viewForward, viewBackward               // . ,: along the view
        case zoomIn, zoomOut
        case turnLeft, turnRight, tiltUp, tiltDown
    }

    public enum Speed: Sendable { case slow, normal, fast }

    public static let maxPitch: Float = 89 * .pi / 180
    public static let minFov: Float = 5
    public static let maxFov: Float = 90
    public static let defaultFov: Float = 45
    /// The eye stays this far above the terrain under it.
    public static let minClearance: Float = 2
    /// Moves scale with the eye's height above the ground, never below this.
    public static let minMoveScale: Float = 30

    // Mouse rates: radians per point of drag (a third of the first cut's,
    // owner 2026-10-15: "too jumpy with the mouse"), and metres of travel
    // per scroll unit per metre of height.
    public static let dragRadiansPerPoint: Float = 0.003
    public static let preciseScrollRate: Float = 0.002
    public static let wheelScrollRate: Float = 0.02
    /// Metres per point of a move drag, per metre of height.
    public static let movePerPointPerMetre: Float = 0.0012

    // Key rates at normal speed, per second.
    public static let keyTurnRadians: Float = 0.35        // ~20°/s
    public static let keyTiltRadians: Float = 0.26        // ~15°/s
    public static let keyMoveFractionOfHeight: Float = 0.4
    public static let keyZoomPerSecond: Float = 1.6       // field of view ÷1.6 per second
    public static func multiplier(_ speed: Speed) -> Float {
        switch speed {
        case .slow: 0.25
        case .normal: 1
        case .fast: 4
        }
    }

    /// Fraction of the remaining way the shown camera closes per 1/60 s.
    public static let easing: Float = 0.25

    public private(set) var goal: Pose
    public private(set) var shown: Pose
    /// The view `reset` set, which `home` returns to.
    public private(set) var home: Pose
    /// The terrain's y under a scene (x, z), or nil where unknown. The eye
    /// is kept `minClearance` above it.
    public var ground: ((Float, Float) -> Float?)?

    public init(eye: SIMD3<Float> = SIMD3(0, 1200, 1800), heading: Float = 0,
                pitch: Float = -0.6, ground: ((Float, Float) -> Float?)? = nil) {
        let pose = Pose(eye: eye, heading: heading, pitch: pitch, fov: Self.defaultFov)
        goal = pose; shown = pose; home = pose
        self.ground = ground
    }

    /// The initial view of a ground extent: above and south of it, outside
    /// the box, looking north and down at its centre — at once, no easing.
    public mutating func reset(center: SIMD3<Float>, radius: Float) {
        let d = max(radius * 2.2, 50), e: Float = 0.6
        let eye = center + SIMD3(0, sin(e) * d, cos(e) * d)
        home = Pose(eye: eye, heading: 0, pitch: -e, fov: Self.defaultFov)
        home.eye = aboveGround(home.eye)
        goHome()
    }

    /// Back to the view `reset` set, at once (the reset key).
    public mutating func goHome() {
        goal = home
        shown = home
    }

    // MARK: Mouse

    /// A drag turns the view about the eye: right turns right, up looks up.
    /// The eye does not move.
    public mutating func look(dx: Float, dy: Float) {
        goal.heading += dx * Self.dragRadiansPerPoint
        goal.pitch = Self.clampPitch(goal.pitch - dy * Self.dragRadiansPerPoint)
    }

    /// ⌥-drag / right-drag: the eye moves the way the pointer goes —
    /// right moves right, up moves forward — in the horizontal plane.
    public mutating func move(dx: Float, dy: Float) {
        let k = moveScale * Self.movePerPointPerMetre
        translate(right(goal) * dx * k - ahead(goal) * dy * k)
    }

    /// Scroll moves the eye along the view (positive = forward).
    public mutating func scroll(_ delta: Float, precise: Bool) {
        let rate = precise ? Self.preciseScrollRate : Self.wheelScrollRate
        translate(viewDirection(goal) * delta * rate * moveScale)
    }

    /// Pinch out moves forward along the view, pinch in moves back.
    public mutating func magnify(_ magnification: Float) {
        translate(viewDirection(goal) * magnification * 0.5 * moveScale)
    }

    // MARK: Keys

    /// Advance the goal by `dt` seconds of the held keys.
    public mutating func hold(_ keys: Set<Key>, speed: Speed, dt: Float) {
        guard !keys.isEmpty, dt > 0 else { return }
        let m = Self.multiplier(speed) * dt
        func axis(_ plus: Key, _ minus: Key) -> Float {
            (keys.contains(plus) ? 1 : 0) - (keys.contains(minus) ? 1 : 0)
        }
        goal.heading += axis(.turnRight, .turnLeft) * Self.keyTurnRadians * m
        goal.pitch = Self.clampPitch(goal.pitch + axis(.tiltUp, .tiltDown) * Self.keyTiltRadians * m)
        let step = moveScale * Self.keyMoveFractionOfHeight * m
        translate((right(goal) * axis(.right, .left) + ahead(goal) * axis(.forward, .backward)
                   + viewDirection(goal) * axis(.viewForward, .viewBackward)) * step)
        let z = axis(.zoomIn, .zoomOut)
        if z != 0 {
            goal.fov = min(max(goal.fov * pow(Self.keyZoomPerSecond, -z * m), Self.minFov), Self.maxFov)
        }
    }

    // MARK: Easing

    /// Ease the shown camera toward the goal over `dt` seconds, keeping it
    /// above the ground. Returns whether it is still moving.
    @discardableResult
    public mutating func step(dt: Float) -> Bool {
        let a = 1 - pow(1 - Self.easing, max(dt, 0) * 60)
        goal.eye = aboveGround(goal.eye)
        shown.eye = aboveGround(shown.eye + (goal.eye - shown.eye) * a)
        shown.heading += (goal.heading - shown.heading) * a
        shown.pitch += (goal.pitch - shown.pitch) * a
        shown.fov += (goal.fov - shown.fov) * a
        if isSettled { shown = goal; return false }
        return true
    }

    public var isSettled: Bool {
        simd_length(goal.eye - shown.eye) < max(0.001 * moveScale, 0.01)
            && abs(goal.heading - shown.heading) < 1e-4
            && abs(goal.pitch - shown.pitch) < 1e-4
            && abs(goal.fov - shown.fov) < 1e-3
    }

    /// Where the shown camera looks: a unit vector from the eye.
    public var lookDirection: SIMD3<Float> { viewDirection(shown) }

    // MARK: -

    /// The ground's y under `p`, or nil where unknown.
    public func groundY(under p: SIMD3<Float>) -> Float? { ground?(p.x, p.z) }

    private func aboveGround(_ p: SIMD3<Float>) -> SIMD3<Float> {
        guard let g = groundY(under: p) else { return p }
        return SIMD3(p.x, max(p.y, g + Self.minClearance), p.z)
    }

    private mutating func translate(_ d: SIMD3<Float>) {
        goal.eye = aboveGround(goal.eye + d)
    }

    /// Metres that one "unit" of motion is worth: the goal eye's height
    /// above the ground, so travel is slow near the ground and fast high up.
    private var moveScale: Float {
        max(goal.eye.y - (groundY(under: goal.eye) ?? 0), Self.minMoveScale)
    }

    private static func clampPitch(_ p: Float) -> Float { min(max(p, -maxPitch), maxPitch) }

    private func right(_ p: Pose) -> SIMD3<Float> { SIMD3(cos(p.heading), 0, sin(p.heading)) }
    private func ahead(_ p: Pose) -> SIMD3<Float> { SIMD3(sin(p.heading), 0, -cos(p.heading)) }
    private func viewDirection(_ p: Pose) -> SIMD3<Float> {
        let c = cos(p.pitch)
        return SIMD3(sin(p.heading) * c, sin(p.pitch), -cos(p.heading) * c)
    }
}
