import Foundation

/// A product version — `MAJOR.MINOR.BUILD`, where BUILD is the number the
/// build scripts increment once per build (`scripts/make_engine.sh` for the
/// engine's `1.50.<build>`, `scripts/make_app.sh` for the app's
/// `1.0.<build>`), so every binary traces back to the commit that made it.
///
/// Used to sanity-check and normalize the version strings the app reads out
/// of files it did not write this run: its own tracked VERSION resource, the
/// engine's `O4_Version.py` or `VERSION.txt`, and the engine handshake.
public struct ProductVersion: Equatable, Sendable, CustomStringConvertible {
    public let major: Int
    public let minor: Int
    public let build: Int

    public init(major: Int, minor: Int, build: Int) {
        self.major = major
        self.minor = minor
        self.build = build
    }

    /// Parses `MAJOR.MINOR.BUILD`, tolerating surrounding whitespace and the
    /// quotes the engine's `version='…'` line carries. Returns nil for
    /// anything else — including the two-component versions older engines
    /// shipped, which have no build number to show.
    public init?(_ text: String) {
        let trimmed = text.trimmingCharacters(in: CharacterSet(charactersIn: " \t\r\n'\""))
        let parts = trimmed.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 3 else { return nil }
        guard let major = Int(parts[0]), let minor = Int(parts[1]), let build = Int(parts[2]),
              major >= 0, minor >= 0, build >= 0,
              parts.allSatisfy({ $0.allSatisfy(\.isNumber) })
        else { return nil }
        self.init(major: major, minor: minor, build: build)
    }

    public var description: String { "\(major).\(minor).\(build)" }

    /// The first candidate that parses, rendered canonically; `"unknown"`
    /// when none do. Callers pass their sources in order of authority — the
    /// app hands over its VERSION resource, then the bundle's
    /// CFBundleShortVersionString.
    public static func firstValid(_ candidates: String?...) -> String {
        for candidate in candidates {
            if let text = candidate, let version = ProductVersion(text) {
                return version.description
            }
        }
        return "unknown"
    }
}
