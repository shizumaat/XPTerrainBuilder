import Foundation

/// How the map loads the patch of the airport in view (#2061). One rule in
/// both apps (Qt: `O4_Qt_Patch_View_Load`), twinned on
/// `Ortho4XP/tests/fixtures/patch_view_load_cases.json`.
///
/// The patch's staleness check (§1.4) reads the airport photos' cover,
/// which finds every nearby airport's apt.dat across the install: 11-24 s
/// in a fresh engine on the owner's 1,474 packs, and the whole wait before
/// the first patch appeared. An engine with the view lane
/// (`patch_view_lane`) loads the patch without it and answers it through
/// `patch_staleness`; the answer completes the document it was asked for —
/// the file the document was opened from — and nothing else.
public enum PatchViewLoad {
    /// `patch_load`'s arguments: `staleness: false` when the engine answers
    /// the check on its own (`fast`).
    public static func loadArguments(tile: String, icao: String, fast: Bool) -> [String: Any] {
        var arguments: [String: Any] = ["tile": tile, "icao": icao]
        if fast { arguments["staleness"] = false }
        return arguments
    }

    /// Whether a `patch_staleness` answer about `answerPath` completes the
    /// document opened from `openedPath` (another airport or a reload: no).
    public static func stalenessApplies(openedPath: String, answerPath: String) -> Bool {
        !openedPath.isEmpty && openedPath == answerPath
    }
}

/// The `patch_staleness` reply (#2061).
public struct O4PatchStaleness: Codable, Equatable, Sendable {
    public let path: String
    public let stale: Bool
    public let staleInputs: [String]

    private enum CodingKeys: String, CodingKey {
        case path, stale
        case staleInputs = "stale_inputs"
    }
}
