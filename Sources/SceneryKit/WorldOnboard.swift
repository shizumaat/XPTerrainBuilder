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

    public var id: Int { offer }

    /// The World folder is not one the app made: say so, offer nothing.
    public var isForeign: Bool { reason == "world_foreign" }

    /// The foreign folder's sentence (the engine's, else `O4StorageText`'s).
    public var foreignText: String {
        message ?? O4StorageText.worldForeignText(target ?? "")
    }

    public init(created: Bool, offer: Int, restartNeeded: Bool,
                reason: String? = nil, target: String? = nil, message: String? = nil) {
        self.created = created
        self.offer = offer
        self.restartNeeded = restartNeeded
        self.reason = reason
        self.target = target
        self.message = message
    }

    private enum CodingKeys: String, CodingKey {
        case created, offer, restartNeeded = "restart_needed", reason, target, message
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
    public func worldOnboard(sceneryDir: String) async throws -> O4WorldOnboard {
        try await request("world_onboard", ["scenery_dir": sceneryDir])
    }
}
