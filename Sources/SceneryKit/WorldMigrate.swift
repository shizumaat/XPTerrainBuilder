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
    /// Journalled tiles made dynamic before that the choice adopts again
    /// (`world_adopt.plan`; none in Custom Scenery any more).
    public var again: Int = 0

    public static func parse(_ row: O4JSON) -> O4WorldMigrateChoice {
        O4WorldMigrateChoice(id: row["id"]?.stringValue ?? "",
                             line: row["line"]?.stringValue ?? "",
                             kept: row["kept"]?.intValue ?? 0,
                             dynamic: row["dynamic"]?.intValue ?? 0,
                             again: row["again"]?.intValue ?? 0)
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
    /// Tiles that failed (their names): migrate, and undo (a name Custom Scenery already has).
    public let failed: [String]
    /// A migration stopped before the end (resumable).
    public let stopped: Bool
    /// Dry run: entries that would move (copy + stage + resume).
    public let toMove: Int
    /// Dry run: each choice's figures, in the order the apps list them.
    public var choices: [O4WorldMigrateChoice] = []
    /// Dry run: when it was measured (`world_measure`; nil from an older engine).
    public var measuredAt: Date?

    /// Tiles `choice` moves, adopts again or makes dynamic (the plain
    /// move count when the engine sent no choices).
    public func toMove(choice: String) -> Int {
        guard let row = choices.first(where: { $0.id == choice }) else { return toMove }
        return row.kept + row.dynamic + row.again
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
            choices: (result["choices"]?.arrayValue ?? []).map(O4WorldMigrateChoice.parse),
            measuredAt: result["measured_at"]?.doubleValue.map { Date(timeIntervalSince1970: $0) })
    }
}

/// The answer of `world_measure_state` (capability `world_measure`,
/// `Ortho4XP/src/o4_engine/world_measure.py`; owner 2026-11-12T19:08Z:
/// Measure runs by itself in the background): the kept measure, whether
/// it is stale, and `auto`: start one now.
public struct O4WorldMeasureState: Sendable, Equatable {
    public let result: O4WorldMigrateResult?
    public let measuredAt: Date?
    public let stale: Bool
    public let wanted: Bool
    public let running: Bool
    public let auto: Bool

    public init(result: O4WorldMigrateResult?, measuredAt: Date?, stale: Bool,
                wanted: Bool, running: Bool, auto: Bool) {
        self.result = result
        self.measuredAt = measuredAt
        self.stale = stale
        self.wanted = wanted
        self.running = running
        self.auto = auto
    }

    public static func parse(_ json: O4JSON) -> O4WorldMeasureState {
        let at = json["measured_at"]?.doubleValue.map { Date(timeIntervalSince1970: $0) }
        var result: O4WorldMigrateResult?
        if let raw = json["result"], raw != .null {
            var parsed = O4WorldMigrateResult.parse(raw)
            parsed.measuredAt = parsed.measuredAt ?? at
            result = parsed
        }
        return O4WorldMeasureState(result: result, measuredAt: at,
                                   stale: json["stale"]?.boolValue ?? false,
                                   wanted: json["wanted"]?.boolValue ?? false,
                                   running: json["running"]?.boolValue ?? false,
                                   auto: json["auto"]?.boolValue ?? false)
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
    public static let intro = "Moves your per-tile ortho packs (zOrtho4XP_…) into the World pack, so X-Plane can take new tiles while it runs. Choose what to keep; Measure shows what each choice frees and still needs before anything moves. The tile folders leave Custom Scenery for the World pack's keeping, files on another drive are never deleted, and Undo moves every tile back."
    public static let keepAllTitle = "Keep all existing tiles"
    public static let keepAllHint = "Every tile moves as it is; a tile another tool built is adopted: its mesh kept, its imagery low-res and sharpened as you fly."
    public static let keepCustomTitle = "Keep tiles with custom airports, make the rest dynamic"
    public static let keepCustomHint = "Tiles holding an installed airport pack are kept (a tile another tool built is adopted: its mesh kept); the rest are draped ahead in flight or built when you fly there."
    public static let dynamicTitle = "Make everything dynamic"
    public static let dynamicHint = "Every tile is draped ahead in flight or built when you fly there; no other drive is needed."
    public static let confirmDynamic = "Tiles made dynamic are drawn by the World pack, draped or built when you fly there; tiles not built by XPTerrainBuilder become our drape or build, not the same tile. Their links to another drive are removed from Custom Scenery (Undo puts them back)."
    public static let freeSpace = "Free space…"
    public static let freeTitle = "Remove the dynamic tiles from this Mac?"
    public static let freeText = "Quit X-Plane first. The folders of the tiles made dynamic are deleted from this Mac and Undo can no longer bring them back; they are draped or built when you fly there. Files on other drives are never touched."

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
    public static let measuringBackground = "Measuring in the background…"
    public static let sampling = "Timing a sample"
    public static let adopting = "Reading tiles made dynamic before"
    public static let elapsed = "{time} elapsed"
    public static let measuredJustNow = "Measured just now"
    public static let measuredMinutes = "Measured {n} min ago"
    public static let measuredHours = "Measured {n} h ago"
    public static let measuredDays = "Measured {n} days ago"
    public static let converting = "Converting…"
    public static let confirmTitle = "Move these tiles into the World pack?"
    public static let confirmText = "Quit X-Plane first. Each tile folder on this Mac moves out of Custom Scenery into the World pack's keeping (XPTerrainBuilder_world_migrate, beside Custom Scenery) and the World pack draws it (a copy of scenery_packs.ini is kept). You can stop at any time and convert again later."
    public static let undoTitle = "Put every converted tile back?"
    public static let undoText = "Quit X-Plane first. Each tile folder moves back into Custom Scenery, turned on, and the World pack gives the tile back."

    /// The words of a phase (`WorldMigrateProgress.phase`).
    public static func phaseVerb(_ phase: String) -> String {
        switch phase {
        case "measure": return "Measuring"
        case "sample": return sampling
        case "adopt": return adopting
        default: return "Converting"
        }
    }

    /// The count under the bar, with the time since the step began (Qt:
    /// `O4_Qt_Convert_Tiles.progress_line`).
    public static func progressLine(_ progress: O4WorldMigrateProgress,
                                    elapsed seconds: TimeInterval? = nil) -> String {
        var line = "\(phaseVerb(progress.phase)): \(progress.done.formatted()) of \(progress.total.formatted()) tiles"
        if !progress.tile.isEmpty { line += " · " + progress.tile }
        if let seconds { line += " · " + elapsedText(seconds) }
        return line
    }

    /// "4:07 elapsed" (h:mm:ss past an hour; Qt: `elapsed_text`).
    public static func elapsedText(_ seconds: TimeInterval) -> String {
        let total = max(0, Int(seconds))
        let (h, m, s) = (total / 3600, total % 3600 / 60, total % 60)
        let time = h > 0 ? String(format: "%d:%02d:%02d", h, m, s) : String(format: "%d:%02d", m, s)
        return elapsed.replacingOccurrences(of: "{time}", with: time)
    }

    /// "Measured 12 min ago" (Qt: `measured_ago`).
    public static func measuredAgo(_ seconds: TimeInterval) -> String {
        let s = max(0, Int(seconds))
        if s < 60 { return measuredJustNow }
        if s < 3600 { return measuredMinutes.replacingOccurrences(of: "{n}", with: "\(s / 60)") }
        if s < 2 * 86400 { return measuredHours.replacingOccurrences(of: "{n}", with: "\(s / 3600)") }
        return measuredDays.replacingOccurrences(of: "{n}", with: "\(s / 86400)")
    }
}

extension OrthoEngineClient {
    /// `world_migrate`: the dry run (`dryRun`, every choice's figures),
    /// the migration under `choice`, its undo (`revert`), or Free space
    /// (`purge`). Asynchronous on the engine side: the reply is
    /// `{"status": "started"}` and the `WorldReady` event naming this
    /// command's id carries the result.
    /// `background` (capability `world_measure`): the measure at the
    /// system's background priority (the automatic one).
    public func worldMigrate(dryRun: Bool, revert: Bool = false, purge: Bool = false,
                             choice: String = "keep_all", background: Bool = false,
                             sceneryDir: String) async throws -> O4WorldMigrateResult {
        let once = O4ResumeOnce<O4WorldMigrateResult>()
        let arguments: [String: Any] = ["dry_run": dryRun, "revert": revert,
                                        "purge": purge, "choice": choice,
                                        "background": background,
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

    /// `world_measure_state` (capability `world_measure`): the kept
    /// measure and whether to start one now; synchronous.
    public func worldMeasureState(sceneryDir: String) async throws -> O4WorldMeasureState {
        try await withCheckedThrowingContinuation { continuation in
            send(command: "world_measure_state", arguments: ["scenery_dir": sceneryDir]) { reply in
                guard reply.ok, let result = reply.result else {
                    continuation.resume(throwing: O4CommandError(
                        reply.error ?? "The engine refused world_measure_state."))
                    return
                }
                continuation.resume(returning: O4WorldMeasureState.parse(result))
            }
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
