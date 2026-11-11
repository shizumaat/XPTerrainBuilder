import Foundation

/// One choice of Convert existing tiles (owner 2026-11-11T15:32Z,
/// `o4_engine/world_retire.py`): `keep_all`, `keep_custom` or `dynamic`,
/// with the dry run's sentence and counts.
public struct O4WorldMigrateChoice: Sendable, Equatable, Identifiable {
    public let id: String
    /// The engine's sentence: what the choice keeps, frees and still needs.
    public let line: String
    public let kept: Int
    public let dynamic: Int

    public static func parse(_ row: O4JSON) -> O4WorldMigrateChoice {
        O4WorldMigrateChoice(id: row["id"]?.stringValue ?? "",
                             line: row["line"]?.stringValue ?? "",
                             kept: row["kept"]?.intValue ?? 0,
                             dynamic: row["dynamic"]?.intValue ?? 0)
    }
}

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
    /// Dry run: each choice's figures, in the order the apps list them.
    public var choices: [O4WorldMigrateChoice] = []

    /// Tiles `choice` moves or makes dynamic (the plain move count when
    /// the engine sent no choices).
    public func toMove(choice: String) -> Int {
        guard let row = choices.first(where: { $0.id == choice }) else { return toMove }
        return row.kept + row.dynamic
    }

    public static func parse(_ result: O4JSON) -> O4WorldMigrateResult {
        let actions = result["totals"]?["by_action"]?.objectValue ?? [:]
        let move = ["copy", "stage", "resume"].reduce(0) { $0 + (actions[$1]?.intValue ?? 0) }
        return O4WorldMigrateResult(
            action: result["action"]?.stringValue ?? "",
            summary: result["summary"]?.stringValue ?? "",
            failed: (result["failed"]?.arrayValue ?? []).compactMap { $0["name"]?.stringValue },
            stopped: result["stopped"]?.boolValue ?? false,
            toMove: move,
            choices: (result["choices"]?.arrayValue ?? []).map(O4WorldMigrateChoice.parse))
    }
}

/// How far a running `world_migrate` is (`class WorldMigrateProgress` in
/// `o4_engine/events.py`; owner 2026-11-11T15:32Z: a bar and a count while
/// it runs): `phase` `measure` (the dry run) or `move`, `done` of `total`
/// tiles, `tile` the pack in hand.
public struct O4WorldMigrateProgress: Sendable, Equatable {
    public let phase: String
    public let done: Int
    public let total: Int
    public let tile: String

    public init(phase: String, done: Int, total: Int, tile: String) {
        self.phase = phase
        self.done = done
        self.total = total
        self.tile = tile
    }

    public static func parse(_ object: [String: Any]) -> O4WorldMigrateProgress {
        O4WorldMigrateProgress(
            phase: object["phase"] as? String ?? "",
            done: (object["done"] as? NSNumber)?.intValue ?? 0,
            total: (object["total"] as? NSNumber)?.intValue ?? 0,
            tile: object["tile"] as? String ?? "")
    }
}

/// The Settings ▸ Storage ▸ Convert words (`O4_Qt_Convert_Tiles` in the Qt window:
/// the same strings).
public enum O4WorldMigrateText {
    public static let title = "Convert existing tiles"
    public static let intro = "Moves your per-tile ortho packs (zOrtho4XP_…) into the World pack, so X-Plane can take new tiles while it runs. Choose what to keep; Measure shows what each choice frees and still needs before anything moves. Files on another drive are never deleted, and Undo puts every tile back."
    public static let keepAllTitle = "Keep all existing tiles"
    public static let keepAllHint = "Every tile moves as it is; a drive that holds tiles stays required."
    public static let keepCustomTitle = "Keep tiles with custom airports, make the rest dynamic"
    public static let keepCustomHint = "Tiles holding an installed airport pack stay as they are; the rest are draped ahead in flight or built when you fly there."
    public static let dynamicTitle = "Make everything dynamic"
    public static let dynamicHint = "Every tile is draped ahead in flight or built when you fly there; no other drive is needed."
    public static let confirmDynamic = "Tiles made dynamic are drawn by the World pack, draped or built when you fly there; tiles not built by XPTerrainBuilder become our drape or build, not the same tile. Their links to another drive are removed from Custom Scenery (Undo puts them back)."
    public static let freeSpace = "Free space…"
    public static let freeTitle = "Remove the dynamic tiles from this Mac?"
    public static let freeText = "Quit X-Plane first. The tiles made dynamic are deleted from Custom Scenery and Undo can no longer bring them back; they are draped or built when you fly there. Files on other drives are never touched."

    /// The choices (`world_retire.CHOICES`; Qt `O4_Qt_Convert_Tiles.CHOICES`):
    /// id, title, and the line shown before a measure.
    public static let choices: [(id: String, title: String, hint: String)] = [
        ("keep_all", keepAllTitle, keepAllHint),
        ("keep_custom", keepCustomTitle, keepCustomHint),
        ("dynamic", dynamicTitle, dynamicHint),
    ]
    public static let measure = "Measure"
    public static let convert = "Convert…"
    public static let stop = "Cancel"
    public static let undo = "Undo…"
    public static let measuring = "Measuring (a few tiles are converted into a temporary folder to time it)…"
    public static let converting = "Converting…"
    public static let confirmTitle = "Move these tiles into the World pack?"
    public static let confirmText = "Quit X-Plane first. Each tile's own pack is turned off in scenery_packs.ini (a copy of the file is kept) and the World pack draws it. You can stop at any time and convert again later."
    public static let undoTitle = "Put every converted tile back?"
    public static let undoText = "Quit X-Plane first. Each tile's own pack is turned on again and the World pack gives the tile back."

    /// The count under the bar (Qt: `O4_Qt_Convert_Tiles.progress_line`).
    public static func progressLine(_ progress: O4WorldMigrateProgress) -> String {
        let verb = progress.phase == "measure" ? "Measuring" : "Converting"
        let line = "\(verb): \(progress.done.formatted()) of \(progress.total.formatted()) tiles"
        return progress.tile.isEmpty ? line : line + " · " + progress.tile
    }
}

extension OrthoEngineClient {
    /// `world_migrate`: the dry run (`dryRun`, every choice's figures),
    /// the migration under `choice`, its undo (`revert`), or Free space
    /// (`purge`). Asynchronous on the engine side: the reply is
    /// `{"status": "started"}` and the `WorldReady` event naming this
    /// command's id carries the result.
    public func worldMigrate(dryRun: Bool, revert: Bool = false, purge: Bool = false,
                             choice: String = "keep_all",
                             sceneryDir: String) async throws -> O4WorldMigrateResult {
        let once = O4ResumeOnce<O4WorldMigrateResult>()
        let arguments: [String: Any] = ["dry_run": dryRun, "revert": revert,
                                        "purge": purge, "choice": choice,
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
