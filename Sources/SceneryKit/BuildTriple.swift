import Foundation

/// The three numbers a beta bug report has to quote: the app version, the
/// engine version and the commit (docs/BETA-PLAN-20260916.md §1 B3).
///
/// "It broke in 1.0.347" identifies nothing — the app and the engine carry
/// independent build numbers, and only the commit says which tree produced
/// them. Every release artifact root carries a `VERSION.txt` with all three
/// (`scripts/write_version_txt.sh`); `scripts/make_app.sh` stamps the engine
/// version and the commit into the app's Info.plist so the About box can show
/// them without reading anything outside the bundle.
///
/// A development tree has neither, and says `dev` rather than inventing one.
public struct BuildTriple: Equatable, Sendable {
    public static let unknown = "dev"

    public let app: String
    public let engine: String
    public let commit: String

    public init(app: String, engine: String, commit: String) {
        self.app = app
        self.engine = engine
        self.commit = commit
    }

    /// Builds the triple from whatever the bundle carries. `app` is already
    /// resolved by the caller (the tracked VERSION resource wins there);
    /// `engine` and `commit` come from the Info.plist keys make_app.sh stamps,
    /// with `engineFallback` covering a `swift run` tree where a live engine
    /// handshake is the only source. Blank or missing values read `dev`.
    public init(app: String,
                infoDictionary: [String: Any]?,
                engineFallback: String? = nil) {
        let stampedEngine = infoDictionary?["XPTBEngineVersion"] as? String
        let stampedCommit = infoDictionary?["XPTBCommitSHA"] as? String
        self.init(app: Self.clean(app),
                  engine: Self.clean(stampedEngine ?? engineFallback),
                  commit: Self.clean(stampedCommit))
    }

    private static func clean(_ value: String?) -> String {
        let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        // make_app.sh leaves the placeholder in a tree it could not read a
        // version or a commit out of; treat it exactly like an absent key.
        if trimmed.isEmpty || trimmed == "unknown" { return unknown }
        return trimmed
    }

    /// The commit as an About box shows it: seven characters is what every
    /// other tool in this project prints, and a tester pasting it back is
    /// unambiguous. A non-sha value (`dev`) passes through whole.
    public var shortCommit: String {
        let hex = commit.prefix(while: \.isHexDigit)
        guard hex.count >= 7 else { return commit }
        let suffix = commit.dropFirst(hex.count)   // keeps a "-dirty" marker
        return String(hex.prefix(7)) + String(suffix)
    }

    /// The three labelled lines the About box shows and a report pastes.
    public var displayLines: [String] {
        ["App version: \(app)",
         "Engine version: \(engine)",
         "Commit: \(shortCommit)"]
    }
}
