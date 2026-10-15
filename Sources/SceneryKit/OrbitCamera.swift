import Foundation
import simd

/// The 3D preview's camera as plain state, so the Mac and its tests share
/// one set of rules (spec §5). The camera orbits a ground `target` at
/// `distance`, `azimuth` (radians, 0 = looking north from the south) and
/// `elevation` (radians above the horizon). Input moves the GOAL; `step`
/// eases the shown camera toward it, so neither a jerky mouse nor a held
/// key makes the view jump.
///
/// Keys are X-Plane's view commands as its default `X-Plane Keys.prf`
/// binds them: ← → move left/right, ↑ ↓ move up/down, `.` `,` forward/back,
/// `=` `-` zoom in/out, Q E rotate left/right, R F tilt up/down. Plain is
/// slow, Shift is fast, Control is slower still — X-Plane's `_fast` /
/// `_slow` variants.
public struct OrbitCamera: Equatable, Sendable {
    public struct Pose: Equatable, Sendable {
        public var target: SIMD3<Float>
        public var distance: Float
        public var azimuth: Float
        public var elevation: Float
    }

    /// One held X-Plane view command.
    public enum Key: Hashable, Sendable {
        case left, right, up, down, forward, backward
        case zoomIn, zoomOut
        case rotateLeft, rotateRight, tiltUp, tiltDown
    }

    public enum Speed: Sendable { case slow, normal, fast }

    public static let minElevation: Float = 0.05
    public static let maxElevation: Float = 1.55
    public static let minDistance: Float = 20
    public static let maxDistance: Float = 100_000

    // Mouse rates: radians per point of drag, and the zoom exponent per
    // scroll unit. A third of the first cut's (owner 2026-10-15: "too
    // jumpy with the mouse").
    public static let dragRadiansPerPoint: Float = 0.003
    public static let preciseScrollRate: Float = 0.002
    public static let wheelScrollRate: Float = 0.02
    /// Ground metres per point of pan drag, per metre of distance — about
    /// "the ground follows the pointer" at the 45° field of view.
    public static let panPerPointPerMetre: Float = 0.0012

    // Key rates at normal speed, per second.
    public static let keyRotateRadians: Float = 0.35      // ~20°/s
    public static let keyTiltRadians: Float = 0.26        // ~15°/s
    public static let keyMoveFractionOfDistance: Float = 0.25
    public static let keyZoomPerSecond: Float = 1.6       // ×1.6 per second
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

    public init(target: SIMD3<Float> = .zero, distance: Float = 2000,
                azimuth: Float = 0, elevation: Float = 0.6) {
        let pose = Pose(target: target, distance: distance, azimuth: azimuth,
                        elevation: elevation)
        goal = pose
        shown = pose
    }

    /// Frame a ground extent from the south, looking north and down — at
    /// once, without easing.
    public mutating func reset(center: SIMD3<Float>, radius: Float) {
        goal = Pose(target: center, distance: max(radius * 2.2, 50), azimuth: 0, elevation: 0.6)
        shown = goal
    }

    // MARK: Mouse

    public mutating func orbit(dx: Float, dy: Float) {
        goal.azimuth -= dx * Self.dragRadiansPerPoint
        goal.elevation = Self.clampElevation(goal.elevation + dy * Self.dragRadiansPerPoint)
    }

    public mutating func pan(dx: Float, dy: Float) {
        let k = goal.distance * Self.panPerPointPerMetre
        goal.target += (-right(goal) * dx + forward(goal) * dy) * k
    }

    public mutating func scroll(_ delta: Float, precise: Bool) {
        zoom(by: exp(-delta * (precise ? Self.preciseScrollRate : Self.wheelScrollRate)))
    }

    public mutating func magnify(_ magnification: Float) {
        zoom(by: 1 / max(1 + magnification * 0.5, 0.1))
    }

    // MARK: Keys

    /// Advance the goal by `dt` seconds of the held keys.
    public mutating func hold(_ keys: Set<Key>, speed: Speed, dt: Float) {
        guard !keys.isEmpty, dt > 0 else { return }
        let m = Self.multiplier(speed) * dt
        func axis(_ plus: Key, _ minus: Key) -> Float {
            (keys.contains(plus) ? 1 : 0) - (keys.contains(minus) ? 1 : 0)
        }
        goal.azimuth += axis(.rotateLeft, .rotateRight) * Self.keyRotateRadians * m
        goal.elevation = Self.clampElevation(
            goal.elevation + axis(.tiltUp, .tiltDown) * Self.keyTiltRadians * m)
        let step = goal.distance * Self.keyMoveFractionOfDistance * m
        goal.target += right(goal) * axis(.right, .left) * step
        goal.target += forward(goal) * axis(.forward, .backward) * step
        goal.target.y += axis(.up, .down) * step
        let z = axis(.zoomIn, .zoomOut)
        if z != 0 { zoom(by: pow(Self.keyZoomPerSecond, -z * m)) }
    }

    // MARK: Easing

    /// Ease the shown camera toward the goal over `dt` seconds. Returns
    /// whether it is still moving.
    @discardableResult
    public mutating func step(dt: Float) -> Bool {
        let a = 1 - pow(1 - Self.easing, max(dt, 0) * 60)
        shown.target += (goal.target - shown.target) * a
        shown.distance += (goal.distance - shown.distance) * a
        shown.azimuth += (goal.azimuth - shown.azimuth) * a
        shown.elevation += (goal.elevation - shown.elevation) * a
        if isSettled { shown = goal; return false }
        return true
    }

    public var isSettled: Bool {
        let d = shown.distance
        return simd_length(goal.target - shown.target) < max(0.001 * d, 0.01)
            && abs(goal.distance - d) < max(0.001 * d, 0.01)
            && abs(goal.azimuth - shown.azimuth) < 1e-4
            && abs(goal.elevation - shown.elevation) < 1e-4
    }

    /// Where the shown camera stands, in the scene's frame (y up).
    public var eye: SIMD3<Float> {
        let c = cos(shown.elevation)
        return shown.target + SIMD3<Float>(c * sin(shown.azimuth), sin(shown.elevation),
                                           c * cos(shown.azimuth)) * shown.distance
    }

    // MARK: -

    private mutating func zoom(by factor: Float) {
        goal.distance = min(max(goal.distance * factor, Self.minDistance), Self.maxDistance)
    }

    private static func clampElevation(_ e: Float) -> Float {
        min(max(e, minElevation), maxElevation)
    }

    private func right(_ p: Pose) -> SIMD3<Float> { SIMD3(cos(p.azimuth), 0, -sin(p.azimuth)) }
    private func forward(_ p: Pose) -> SIMD3<Float> { SIMD3(-sin(p.azimuth), 0, -cos(p.azimuth)) }
}
