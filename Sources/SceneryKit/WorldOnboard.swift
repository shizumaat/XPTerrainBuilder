import Foundation

/// The answer of `world_onboard` (#2007, RULINGS 2026-11-11a,
/// `Ortho4XP/src/o4_engine/world_commands.py`): at the app's start the
/// World pack is made when its folder does not exist; `offer` is how many
/// per-tile packs Convert existing tiles could move, non-zero once (11h (2):
/// the engine records the offer, Not now included).
public struct O4WorldOnboard: Decodable, Equatable, Sendable, Identifiable {
    public let created: Bool
    public let offer: Int
    public let restartNeeded: Bool
    /// `world_foreign` when the World folder is not the app's own (a link,
    /// or a folder outside Custom Scenery): no offer; `target` is where it
    /// really is and `message` the sentence the apps show.
    public let reason: String?
    public let target: String?
    public let message: String?
    /// Where the tiles and packages live now (RULINGS 2026-11-12g/h, the
    /// engine's `world_home`): the data folder's moved into the World
    /// folder at this start. Nil from an engine before it.
    public let home: O4WorldHome?

    public var id: Int { offer }

    /// The World folder is not one the app made: say so, offer nothing.
    public var isForeign: Bool { reason == "world_foreign" }

    /// The foreign folder's sentence (the engine's, else `O4StorageText`'s).
    public var foreignText: String {
        message ?? O4StorageText.worldForeignText(target ?? "")
    }

    public init(created: Bool, offer: Int, restartNeeded: Bool,
                reason: String? = nil, target: String? = nil, message: String? = nil,
                home: O4WorldHome? = nil) {
        self.created = created
        self.offer = offer
        self.restartNeeded = restartNeeded
        self.reason = reason
        self.target = target
        self.message = message
        self.home = home
    }

    private enum CodingKeys: String, CodingKey {
        case created, offer, restartNeeded = "restart_needed", reason, target, message, home
    }
}

/// `world_onboard`'s `home` (`o4_engine/world_home.py`): `tilesDir` is
/// every build folder's parent, `packagesDir` the `.xptb` store; `active`
/// when they are the World folder's; `left` items the next start moves.
public struct O4WorldHome: Decodable, Equatable, Sendable {
    public let tilesDir: String
    public let packagesDir: String
    public let active: Bool
    public let moved: Int
    public let left: Int
    public let error: String?

    public init(tilesDir: String, packagesDir: String, active: Bool,
                moved: Int = 0, left: Int = 0, error: String? = nil) {
        self.tilesDir = tilesDir
        self.packagesDir = packagesDir
        self.active = active
        self.moved = moved
        self.left = left
        self.error = error
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        tilesDir = try c.decodeIfPresent(String.self, forKey: .tilesDir) ?? ""
        packagesDir = try c.decodeIfPresent(String.self, forKey: .packagesDir) ?? ""
        active = try c.decodeIfPresent(Bool.self, forKey: .active) ?? false
        moved = try c.decodeIfPresent(Int.self, forKey: .moved) ?? 0
        left = try c.decodeIfPresent(Int.self, forKey: .left) ?? 0
        error = try c.decodeIfPresent(String.self, forKey: .error)
    }

    private enum CodingKeys: String, CodingKey {
        case tilesDir = "tiles_dir", packagesDir = "packages_dir", active, moved, left, error
    }
}

/// The onboarding's words (`O4_Qt_World_Onboard` in the Qt window: the
/// same strings, `tests/test_world_onboard.py` holds them equal).
public enum O4WorldOnboardText {
    public static let title = "Let XPTerrainBuilder manage your ortho tiles?"
    public static let intro = "XPTerrainBuilder can move the {count} ortho tile(s) you already have into its World folder in Custom Scenery."
    public static let advantages = "One disk budget: everything the app keeps fits the space you give it.|Low-res placeholders: fly anywhere, sharp imagery arrives as you fly.|Build-ahead and the flight manager make the scenery for your flights.|Safe give-back: nothing is deleted, and Undo puts every tile back."
    public static let note = "Quit X-Plane first. Not now: ask again from Settings ▸ Storage ▸ Convert existing tiles."
    public static let move = "Move…"
    public static let notNow = "Not now"
    public static let done = "Done"

    public static func introText(_ count: Int) -> String {
        intro.replacingOccurrences(of: "{count}", with: "\(count)")
    }

    public static var advantageLines: [String] {
        advantages.components(separatedBy: "|")
    }
}

extension OrthoEngineClient {
    /// `world_onboard` (capability `world_onboard`): sync.
    /// `legacyBuildDir`: the retired custom build folder, moved once
    /// (RULINGS 2026-11-12g).
    public func worldOnboard(sceneryDir: String, legacyBuildDir: String = "") async throws -> O4WorldOnboard {
        try await request("world_onboard", ["scenery_dir": sceneryDir,
                                             "legacy_build_dir": legacyBuildDir])
    }
}
