import Foundation

/// What the engine says it can do, read off its `EngineHello`.
///
/// The protocol number is FROZEN at 1.32 (owner RULINGS 2026-11-03d (1),
/// item 3): a new engine feature is a CAPABILITY FLAG the hello names, so
/// parallel PRs add flags without colliding on one number. An engine from
/// before the freeze names none of the new flags, so a flag that names a
/// 1.20–1.32 feature is also granted by that engine's protocol number.
/// The flag names are STRING LITERALS matched against
/// `Ortho4XP/src/o4_engine/events.py` `CAPABILITIES`;
/// `tests/test_engine_capabilities.py` fails when one here is not there.
public struct O4EngineCapabilities: Equatable, Sendable {
    public static let insertShape = "patch_insert_shape"
    public static let insertTunnelRamp = "patch_insert_tunnel_ramp"
    public static let objectSeatSet = "object_seat_set"

    /// The protocol number each pre-freeze flag arrived in.
    static let since: [String: (Int, Int)] = [
        insertShape: (1, 20),
        insertTunnelRamp: (1, 24),
        objectSeatSet: (1, 30),
    ]

    public let protocolVersion: String
    public let flags: Set<String>

    public init(protocolVersion: String, flags: [String]) {
        self.protocolVersion = protocolVersion
        self.flags = Set(flags)
    }

    /// No engine yet: nothing is offered.
    public static let none = O4EngineCapabilities(protocolVersion: "", flags: [])

    /// True when the hello names `flag`, or the engine predates the flag
    /// and its protocol number is at least the one that added the feature.
    public func supports(_ flag: String) -> Bool {
        if flags.contains(flag) { return true }
        guard let (major, minor) = Self.since[flag] else { return false }
        return O4ProtocolVersion.isAtLeast(protocolVersion, major, minor)
    }

    public static func == (a: Self, b: Self) -> Bool {
        a.protocolVersion == b.protocolVersion && a.flags == b.flags
    }
}
