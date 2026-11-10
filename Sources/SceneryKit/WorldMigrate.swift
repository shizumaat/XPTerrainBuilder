import Foundation

/// The answer of `world_migrate` (World spec §13 M1, capability
/// `world_migrate`, `Ortho4XP/src/o4_engine/world_migrate.py`): the
/// per-tile `zOrtho4XP_` packs moved into the World pack. The engine
/// writes the sentence (`summary`); both apps only show it. The keys are
/// those of the `WorldReady` event's `result`.
public struct O4WorldMigrateResult: Sendable, Equatable {
    /// `dry_run`, `migrate` or `revert`.
    public let action: String
    /// One sentence, ready to show.
    public let summary: String
    /// Tiles that failed (their names), migrate only.
    public let failed: [String]
    /// A migration stopped before the end (resumable).
    public let stopped: Bool
    /// Dry run: entries that would move (copy + stage + resume).
    public let toMove: Int

    public static func parse(_ result: O4JSON) -> O4WorldMigrateResult {
        let actions = result["totals"]?["by_action"]?.objectValue ?? [:]
        let move = ["copy", "stage", "resume"].reduce(0) { $0 + (actions[$1]?.intValue ?? 0) }
        return O4WorldMigrateResult(
            action: result["action"]?.stringValue ?? "",
            summary: result["summary"]?.stringValue ?? "",
            failed: (result["failed"]?.arrayValue ?? []).compactMap { $0["name"]?.stringValue },
            stopped: result["stopped"]?.boolValue ?? false,
            toMove: move)
    }
}

/// The Library ▸ Convert words (`O4_Qt_Convert_Tiles` in the Qt window:
/// the same strings).
public enum O4WorldMigrateText {
    public static let title = "Convert existing tiles"
    public static let intro = "Moves your per-tile ortho packs (zOrtho4XP_…) into the World pack, so X-Plane can take new tiles while it runs. Tiles on another drive get a small local copy and their files stay where they are. Nothing is deleted: Undo puts every tile back."
    public static let measure = "Measure"
    public static let convert = "Convert…"
    public static let stop = "Stop"
    public static let undo = "Undo…"
    public static let measuring = "Measuring (a few tiles are converted into a temporary folder to time it)…"
    public static let converting = "Converting…"
    public static let confirmTitle = "Move these tiles into the World pack?"
    public static let confirmText = "Quit X-Plane first. Each tile's own pack is turned off in scenery_packs.ini (a copy of the file is kept) and the World pack draws it. You can stop at any time and convert again later."
    public static let undoTitle = "Put every converted tile back?"
    public static let undoText = "Quit X-Plane first. Each tile's own pack is turned on again and the World pack gives the tile back."
}

extension OrthoEngineClient {
    /// `world_migrate`: the dry run (`dryRun`), the migration, or its
    /// undo (`revert`). Asynchronous on the engine side: the reply is
    /// `{"status": "started"}` and the `WorldReady` event naming this
    /// command's id carries the result.
    public func worldMigrate(dryRun: Bool, revert: Bool = false,
                             sceneryDir: String) async throws -> O4WorldMigrateResult {
        let once = O4ResumeOnce<O4WorldMigrateResult>()
        let arguments: [String: Any] = ["dry_run": dryRun, "revert": revert,
                                        "scenery_dir": sceneryDir]
        return try await withCheckedThrowingContinuation { continuation in
            once.set(continuation)
            send(command: "world_migrate", arguments: arguments,
                 completion: { reply in
                     if !reply.ok {
                         once.resume(.failure(O4CommandError(reply.error ?? "The engine refused world_migrate.")))
                     }
                 },
                 completionEvent: { event in once.resume(Self.decodeWorldMigrateReady(event)) })
        }
    }

    /// Ask a running migration to stop after the tiles in hand.
    public func stopWorldMigrate() {
        send(command: "world_migrate", arguments: ["stop": true])
    }

    static func decodeWorldMigrateReady(_ event: O4JSON?) -> Result<O4WorldMigrateResult, Error> {
        guard let event else { return .failure(O4CommandError("The engine exited before the conversion finished.")) }
        if case .string(let text)? = event["error"], !text.isEmpty {
            return .failure(O4CommandError(text))
        }
        guard let result = event["result"], result != .null else {
            return .failure(O4CommandError("The engine sent no conversion result."))
        }
        return .success(O4WorldMigrateResult.parse(result))
    }
}
